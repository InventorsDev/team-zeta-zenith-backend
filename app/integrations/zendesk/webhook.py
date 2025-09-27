"""
Zendesk webhook handlers for real-time updates
"""
import logging
import hmac
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import HTTPException, Header, Request

from app.integrations.zendesk.models import ZendeskWebhookEvent
from app.integrations.zendesk.sync import ZendeskSyncService
from app.integrations.zendesk.client import ZendeskClient
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ZendeskWebhookHandler:
    """Handler for Zendesk webhook events"""
    
    def __init__(self, db_session=None):
        self.zendesk_client = ZendeskClient()
        self.sync_service = ZendeskSyncService(self.zendesk_client, db_session)
        
    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """
        Verify Zendesk webhook signature for security
        
        Args:
            body: Raw request body
            signature: X-Zendesk-Webhook-Signature header value
        """
        if not settings.zendesk_signing_secret:
            logger.warning("Zendesk signing secret not configured, skipping signature verification")
            return True
        
        try:
            # Zendesk uses HMAC-SHA256 with base64 encoding
            expected_signature = hmac.new(
                settings.zendesk_signing_secret.encode(),
                body,
                hashlib.sha256
            ).digest()
            
            # Zendesk sends signature as base64
            import base64
            expected_signature_b64 = base64.b64encode(expected_signature).decode()
            
            return hmac.compare_digest(signature, expected_signature_b64)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    def handle_webhook(
        self, 
        payload: Dict[str, Any], 
        signature: Optional[str] = None,
        body: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Main webhook handler for Zendesk events
        
        Args:
            payload: Webhook payload from Zendesk
            signature: Webhook signature for verification
            body: Raw request body for signature verification
        """
        try:
            # Verify signature if provided
            if signature and body:
                if not self.verify_webhook_signature(body, signature):
                    raise HTTPException(status_code=401, detail="Invalid webhook signature")
            
            # Parse webhook event
            event = self._parse_webhook_event(payload)
            if not event:
                return {"status": "ignored", "reason": "Unable to parse event"}
            
            # Log the event appropriately
            if event.ticket_id and event.ticket_id > 0:
                logger.info(f"Processing Zendesk webhook event: {event.event} for ticket {event.ticket_id}")
            else:
                logger.info(f"Processing Zendesk webhook event: {event.event} (non-ticket event)")
            
            # Handle different event types
            result = self._handle_event(event)
            
            response = {
                "status": "success", 
                "event": event.event,
                "result": result
            }
            
            # Only include ticket_id if it's a ticket event
            if event.ticket_id and event.ticket_id > 0:
                response["ticket_id"] = event.ticket_id
                
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error handling Zendesk webhook: {e}")
            raise HTTPException(status_code=500, detail="Internal server error processing webhook")
    
    def _parse_webhook_event(self, payload: Dict[str, Any]) -> Optional[ZendeskWebhookEvent]:
        """Parse Zendesk webhook payload into event object"""
        try:
            # Handle new Zendesk event format (2022-11-06 version)
            if "type" in payload and "id" in payload and "subject" in payload:
                # New format: {"type":"zen:event-type:agent.channel_created", "id":"...", "subject":"zen:agent:10011", ...}
                event_type = payload.get("type", "")
                
                # Extract timestamp from 'time' field
                timestamp = datetime.utcnow()
                if "time" in payload:
                    try:
                        timestamp = datetime.fromisoformat(payload["time"].replace("Z", "+00:00")).replace(tzinfo=None)
                    except:
                        logger.warning(f"Could not parse timestamp: {payload['time']}")
                
                # For non-ticket events, we might not have a ticket_id
                ticket_id = None
                if "ticket_id" in payload:
                    ticket_id = payload["ticket_id"]
                elif "detail" in payload and isinstance(payload["detail"], dict):
                    # Some events might have ticket info in detail
                    detail = payload["detail"]
                    if "ticket_id" in detail:
                        ticket_id = detail["ticket_id"]
                
                return ZendeskWebhookEvent(
                    event=event_type,
                    ticket_id=ticket_id or 0,  # Use 0 for non-ticket events
                    timestamp=timestamp,
                    current=payload,
                    previous=None,
                    changes=None
                )
            
            # Legacy ticket event format
            elif "ticket_event" in payload:
                ticket_event = payload["ticket_event"]
                return ZendeskWebhookEvent(
                    event=f"ticket.{ticket_event.get('type', 'updated')}",
                    ticket_id=ticket_event.get("ticket_id"),
                    timestamp=datetime.fromisoformat(ticket_event.get("timestamp", datetime.utcnow().isoformat())),
                    current=ticket_event.get("current"),
                    previous=ticket_event.get("previous"),
                    changes=ticket_event.get("changes")
                )
            
            elif "ticket" in payload and "action" in payload:
                # Alternative legacy format
                return ZendeskWebhookEvent(
                    event=f"ticket.{payload['action']}",
                    ticket_id=payload["ticket"]["id"],
                    timestamp=datetime.utcnow(),
                    current=payload.get("ticket"),
                    previous=payload.get("previous_ticket"),
                    changes=payload.get("changes")
                )
            
            else:
                logger.warning(f"Unknown Zendesk webhook format: {list(payload.keys())}")
                logger.debug(f"Payload sample: {str(payload)[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing webhook event: {e}")
            return None
    
    def _handle_event(self, event: ZendeskWebhookEvent) -> Dict[str, Any]:
        """Handle specific webhook event types"""
        
        # Map of event types to handlers
        handlers = {
            # Legacy ticket events
            "ticket.created": self._handle_ticket_created,
            "ticket.updated": self._handle_ticket_updated,
            "ticket.deleted": self._handle_ticket_deleted,
            "ticket.comment_created": self._handle_comment_created,
            "ticket.status_changed": self._handle_status_changed,
            
            # New Zendesk event types
            "zen:event-type:ticket.created": self._handle_ticket_created,
            "zen:event-type:ticket.updated": self._handle_ticket_updated,
            "zen:event-type:ticket.deleted": self._handle_ticket_deleted,
            "zen:event-type:ticket.comment_created": self._handle_comment_created,
            "zen:event-type:agent.channel_created": self._handle_agent_event,
            "zen:event-type:agent.updated": self._handle_agent_event,
            "zen:event-type:organization.created": self._handle_organization_event,
            "zen:event-type:organization.updated": self._handle_organization_event,
        }
        
        # Get handler for event type
        handler = handlers.get(event.event, self._handle_generic_event)
        
        try:
            return handler(event)
        except Exception as e:
            logger.error(f"Error handling event {event.event}: {e}")
            return {"error": str(e)}
    
    def _handle_ticket_created(self, event: ZendeskWebhookEvent) -> Dict[str, Any]:
        """Handle ticket creation events"""
        logger.info(f"Handling ticket creation for Zendesk ticket {event.ticket_id}")
        
        # Sync the newly created ticket
        synced_ticket = self.sync_service.sync_single_ticket(event.ticket_id)
        
        if synced_ticket:
            return {
                "action": "ticket_created",
                "synced": True,
                "internal_ticket_id": synced_ticket.get("id")
            }
        else:
            return {
                "action": "ticket_created",
                "synced": False,
                "error": "Failed to sync new ticket"
            }
    
    def _handle_ticket_updated(self, event: ZendeskWebhookEvent) -> Dict[str, Any]:
        """Handle ticket update events"""
        logger.info(f"Handling ticket update for Zendesk ticket {event.ticket_id}")
        
        # Check what fields were changed
        changed_fields = []
        if event.changes:
            changed_fields = list(event.changes.keys())
        
        # Sync the updated ticket
        synced_ticket = self.sync_service.sync_single_ticket(event.ticket_id)
        
        if synced_ticket:
            return {
                "action": "ticket_updated",
                "synced": True,
                "changed_fields": changed_fields,
                "internal_ticket_id": synced_ticket.get("id")
            }
        else:
            return {
                "action": "ticket_updated",
                "synced": False,
                "changed_fields": changed_fields,
                "error": "Failed to sync updated ticket"
            }
    
    def _handle_ticket_deleted(self, event: ZendeskWebhookEvent) -> Dict[str, Any]:
        """Handle ticket deletion events"""
        logger.info(f"Handling ticket deletion for Zendesk ticket {event.ticket_id}")
        
        try:
            # Find the internal ticket by external_id
            external_id = f"zendesk_{event.ticket_id}"
            existing_ticket = self.sync_service.ticket_repo.get_by_external_id(external_id)
            
            if existing_ticket:
                # Mark as deleted or actually delete (based on business logic)
                # For now, we'll update the status to closed
                self.sync_service.ticket_repo.update_ticket(existing_ticket.id, {
                    "status": "closed",
                    "description": existing_ticket.description + "\n\n[Ticket deleted in Zendesk]"
                })
                
                return {
                    "action": "ticket_deleted",
                    "handled": True,
                    "internal_ticket_id": existing_ticket.id
                }
            else:
                return {
                    "action": "ticket_deleted",
                    "handled": False,
                    "reason": "Ticket not found in internal system"
                }
                
        except Exception as e:
            logger.error(f"Error handling ticket deletion: {e}")
            return {
                "action": "ticket_deleted",
                "handled": False,
                "error": str(e)
            }
    
    def _handle_comment_created(self, event: ZendeskWebhookEvent) -> Dict[str, Any]:
        """Handle new comment events"""
        logger.info(f"Handling comment creation for Zendesk ticket {event.ticket_id}")
        
        # For now, just sync the ticket to get updated comment count
        # In a full implementation, you might sync comments separately
        synced_ticket = self.sync_service.sync_single_ticket(event.ticket_id)
        
        return {
            "action": "comment_created",
            "synced": synced_ticket is not None,
            "note": "Ticket synced to capture comment updates"
        }
    
    def _handle_status_changed(self, event: ZendeskWebhookEvent) -> Dict[str, Any]:
        """Handle status change events"""
        logger.info(f"Handling status change for Zendesk ticket {event.ticket_id}")
        
        # Get old and new status from changes
        old_status = None
        new_status = None
        
        if event.changes and "status" in event.changes:
            status_change = event.changes["status"]
            old_status = status_change.get("previous_value")
            new_status = status_change.get("current_value")
        
        # Sync the updated ticket
        synced_ticket = self.sync_service.sync_single_ticket(event.ticket_id)
        
        return {
            "action": "status_changed",
            "synced": synced_ticket is not None,
            "old_status": old_status,
            "new_status": new_status
        }
    
    def _handle_agent_event(self, event: ZendeskWebhookEvent) -> Dict[str, Any]:
        """Handle agent-related events"""
        logger.info(f"Handling agent event {event.event}")
        
        # Extract agent information from the event
        agent_id = None
        if event.current and "detail" in event.current:
            detail = event.current["detail"]
            agent_id = detail.get("agent_id")
        
        return {
            "action": "agent_event_received",
            "event_type": event.event,
            "agent_id": agent_id,
            "message": "Agent event logged but no sync action needed"
        }
    
    def _handle_organization_event(self, event: ZendeskWebhookEvent) -> Dict[str, Any]:
        """Handle organization-related events"""
        logger.info(f"Handling organization event {event.event}")
        
        # Extract organization information
        org_id = None
        if event.current and "detail" in event.current:
            detail = event.current["detail"]
            org_id = detail.get("organization_id")
        
        return {
            "action": "organization_event_received", 
            "event_type": event.event,
            "organization_id": org_id,
            "message": "Organization event logged but no sync action needed"
        }
        
    def _handle_generic_event(self, event: ZendeskWebhookEvent) -> Dict[str, Any]:
        """Handle unknown or generic events"""
        
        # Check if it's a ticket event (has valid ticket_id)
        if event.ticket_id and event.ticket_id > 0:
            logger.info(f"Handling generic ticket event {event.event} for ticket {event.ticket_id}")
            # For unknown ticket events, try to sync the ticket
            synced_ticket = self.sync_service.sync_single_ticket(event.ticket_id)
            
            return {
                "action": "generic_ticket_sync",
                "event_type": event.event,
                "ticket_id": event.ticket_id,
                "synced": synced_ticket is not None
            }
        else:
            logger.info(f"Handling generic non-ticket event {event.event}")
            # For non-ticket events, just acknowledge
            return {
                "action": "generic_event_received",
                "event_type": event.event,
                "message": "Event received and logged"
            }
    
    def get_webhook_url(self, base_url: str) -> str:
        """Get the webhook URL that should be configured in Zendesk"""
        return f"{base_url}/api/v1/integrations/zendesk/webhook"
    
    def validate_webhook_config(self) -> Dict[str, Any]:
        """Validate webhook configuration"""
        issues = []
        
        if not settings.zendesk_signing_secret:
            issues.append("Zendesk signing secret not configured")
        
        if not self.zendesk_client.is_enabled:
            issues.append("Zendesk client not properly configured")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "recommendations": [
                "Configure ZENDESK_SIGNING_SECRET in environment",
                "Set up webhook target in Zendesk admin panel",
                "Test webhook with a sample event"
            ]
        }