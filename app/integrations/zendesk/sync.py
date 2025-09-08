"""
Zendesk ticket synchronization service
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from app.integrations.zendesk.models import (
    ZendeskSyncResult, 
    zendesk_ticket_to_internal,
    internal_ticket_to_zendesk
)
from app.services.ticket_service import TicketService
from app.database.repositories.ticket_repository import TicketRepository
from app.database.connection import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ZendeskSyncService:
    """Service for synchronizing tickets between Zendesk and internal system"""
    
    def __init__(self, zendesk_client, db_session=None):
        self.zendesk_client = zendesk_client
        
        # Get database session - we'll need this for direct repository access
        if db_session is None:
            db_session = next(get_db())
        
        self.db_session = db_session
        self.ticket_service = TicketService(db_session)
        self.ticket_repo = TicketRepository(db_session)
        
    def sync_tickets(self, full_sync: bool = False) -> ZendeskSyncResult:
        """
        Synchronize tickets from Zendesk to internal system
        
        Args:
            full_sync: If True, sync all tickets. If False, sync only recent updates.
        """
        result = ZendeskSyncResult(
            start_time=datetime.utcnow(),
            sync_type="full" if full_sync else "incremental"
        )
        
        try:
            logger.info(f"Starting {'full' if full_sync else 'incremental'} Zendesk sync")
            
            # Determine sync time window
            start_time = None
            if not full_sync:
                # For incremental sync, get tickets updated in last 24 hours
                start_time = datetime.utcnow() - timedelta(hours=24)
                
                # Check if we have any Zendesk tickets to get the last sync time
                last_zendesk_ticket = self._get_last_synced_ticket()
                if last_zendesk_ticket:
                    start_time = last_zendesk_ticket.updated_at
            
            # Fetch tickets from Zendesk
            logger.info(f"Fetching tickets from Zendesk (start_time: {start_time})")
            
            for zendesk_ticket in self.zendesk_client.get_tickets(
                page_size=100,
                start_time=start_time,
                incremental=not full_sync
            ):
                try:
                    result.total_fetched += 1
                    
                    # Convert Zendesk ticket to internal format
                    internal_ticket_data = zendesk_ticket_to_internal(zendesk_ticket)
                    
                    # Check if ticket already exists
                    external_id = internal_ticket_data["external_id"]
                    existing_ticket = self.ticket_repo.get_by_external_id(external_id)
                    
                    if existing_ticket:
                        # Update existing ticket only if it has newer data
                        try:
                            zendesk_updated_at = datetime.fromisoformat(
                                zendesk_ticket["updated_at"].replace("Z", "+00:00")
                            )
                            if existing_ticket.updated_at < zendesk_updated_at.replace(tzinfo=None):
                                updated_ticket = self._update_existing_ticket(
                                    existing_ticket, 
                                    internal_ticket_data,
                                    zendesk_ticket
                                )
                                if updated_ticket:
                                    result.total_updated += 1
                                    logger.debug(f"Updated ticket {existing_ticket.id} from Zendesk {zendesk_ticket['id']}")
                            else:
                                logger.debug(f"Ticket {existing_ticket.id} from Zendesk {zendesk_ticket['id']} is already up to date")
                        except Exception as e:
                            logger.warning(f"Error comparing timestamps for ticket {zendesk_ticket['id']}: {e}")
                    else:
                        # Create new ticket
                        new_ticket = self._create_new_ticket(internal_ticket_data)
                        if new_ticket:
                            result.total_created += 1
                            logger.debug(f"Created new ticket from Zendesk {zendesk_ticket['id']}")
                    
                    result.total_processed += 1
                    
                    # Log progress every 100 tickets
                    if result.total_processed % 100 == 0:
                        logger.info(f"Processed {result.total_processed} tickets...")
                        
                except Exception as e:
                    result.total_errors += 1
                    error_msg = f"Error processing Zendesk ticket {zendesk_ticket.get('id', 'unknown')}: {e}"
                    result.errors.append(error_msg)
                    logger.error(error_msg)
                    
                    # Handle database session rollback if needed
                    try:
                        if 'transaction has been rolled back' in str(e):
                            logger.info("Rolling back database session due to previous error")
                            self.db_session.rollback()
                    except Exception as rollback_error:
                        logger.warning(f"Error during rollback: {rollback_error}")
                    
                    continue
            
            result.end_time = datetime.utcnow()
            
            logger.info(
                f"Zendesk sync completed: "
                f"Fetched: {result.total_fetched}, "
                f"Processed: {result.total_processed}, "
                f"Created: {result.total_created}, "
                f"Updated: {result.total_updated}, "
                f"Errors: {result.total_errors}, "
                f"Duration: {result.duration_seconds:.2f}s"
            )
            
        except Exception as e:
            result.total_errors += 1
            result.errors.append(f"Sync failed: {e}")
            result.end_time = datetime.utcnow()
            logger.error(f"Zendesk sync failed: {e}")
        
        return result
    
    def sync_single_ticket(self, zendesk_ticket_id: int) -> Optional[Dict[str, Any]]:
        """Sync a single ticket by Zendesk ID"""
        try:
            # Fetch ticket from Zendesk
            zendesk_ticket = self.zendesk_client.get_ticket(zendesk_ticket_id)
            if not zendesk_ticket:
                logger.error(f"Ticket {zendesk_ticket_id} not found in Zendesk")
                return None
            
            # Convert to internal format
            internal_ticket_data = zendesk_ticket_to_internal(zendesk_ticket)
            
            # Check if exists locally
            external_id = internal_ticket_data["external_id"]
            existing_ticket = self.ticket_repo.get_by_external_id(external_id)
            
            if existing_ticket:
                # Update existing
                return self._update_existing_ticket(existing_ticket, internal_ticket_data, zendesk_ticket)
            else:
                # Create new
                return self._create_new_ticket(internal_ticket_data)
                
        except Exception as e:
            logger.error(f"Error syncing single ticket {zendesk_ticket_id}: {e}")
            return None
    
    def push_ticket_to_zendesk(self, internal_ticket_id: int) -> Optional[Dict[str, Any]]:
        """Push an internal ticket to Zendesk"""
        try:
            # Get internal ticket
            ticket = self.ticket_repo.get_by_id(internal_ticket_id)
            if not ticket:
                logger.error(f"Internal ticket {internal_ticket_id} not found")
                return None
            
            # Convert to Zendesk format
            ticket_dict = {
                "title": ticket.title,
                "description": ticket.description,
                "status": ticket.status,
                "priority": ticket.priority,
                "customer_email": ticket.customer_email,
                "tags": ticket.tags or []
            }
            zendesk_data = internal_ticket_to_zendesk(ticket_dict)
            
            # Check if ticket already exists in Zendesk
            if ticket.external_id and ticket.external_id.startswith("zendesk_"):
                # Update existing Zendesk ticket
                zendesk_id = int(ticket.external_id.replace("zendesk_", ""))
                zendesk_ticket = self.zendesk_client.update_ticket(zendesk_id, zendesk_data)
            else:
                # Create new Zendesk ticket
                zendesk_ticket = self.zendesk_client.create_ticket(zendesk_data)
                
                # Update internal ticket with Zendesk ID
                if zendesk_ticket:
                    ticket.external_id = f"zendesk_{zendesk_ticket['id']}"
                    ticket.external_url = zendesk_ticket.get("url", "")
                    self.ticket_repo.update_ticket(ticket.id, {
                        "external_id": ticket.external_id,
                        "external_url": ticket.external_url
                    })
            
            return zendesk_ticket
            
        except Exception as e:
            logger.error(f"Error pushing ticket {internal_ticket_id} to Zendesk: {e}")
            return None
    
    def _get_last_synced_ticket(self):
        """Get the most recently synced Zendesk ticket for incremental sync"""
        try:
            # Query for tickets with Zendesk external_id, ordered by updated_at desc
            return self.ticket_repo.get_latest_by_channel("zendesk")
        except Exception as e:
            logger.warning(f"Could not get last synced ticket: {e}")
            return None
    
    def _create_new_ticket(self, ticket_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new internal ticket from Zendesk data"""
        try:
            # Remove zendesk_data before creating ticket (not a DB field)
            zendesk_metadata = ticket_data.pop("zendesk_data", {})
            
            # Set default organization_id if not present (should be handled at higher level)
            if "organization_id" not in ticket_data:
                # For now, set to 1 (first organization) - in production this should be configurable
                ticket_data["organization_id"] = 1
            
            # Get ML analysis for this ticket
            from app.services.ml_service import ml_service
            ml_analysis = ml_service.enhance_ticket_data(ticket_data)
            
            # Define valid database fields based on the Ticket model
            valid_db_fields = {
                'title', 'description', 'external_id', 'status', 'priority', 'channel',
                'customer_email', 'customer_name', 'customer_phone', 'assigned_to',
                'organization_id', 'integration_id', 'first_response_at', 'resolved_at',
                'closed_at', 'last_activity_at', 'sentiment_score', 'category',
                'urgency_score', 'confidence_score', 'tags', 'ticket_metadata',
                'is_processed', 'needs_human_review', 'created_at', 'updated_at'
            }
            
            # Start with original ticket data fields that are valid for database
            db_fields = {k: v for k, v in ticket_data.items() 
                        if k in valid_db_fields and not k.startswith('ml_')}
            
            # CRITICAL FIX: Merge ML analysis results into database fields
            ml_stored_fields = []
            for field, value in ml_analysis.items():
                if field in valid_db_fields and not field.startswith('ml_') and value is not None:
                    db_fields[field] = value
                    ml_stored_fields.append(f"{field}={value}")
            
            if ml_stored_fields:
                logger.info(f"ML analysis stored to database: {', '.join(ml_stored_fields)}")
            else:
                logger.info("ML analysis completed but no database fields to store")
            
            # Separate response-only ML fields (those starting with 'ml_')
            ml_fields = {k: v for k, v in ml_analysis.items() if k.startswith('ml_')}
            
            # Create ticket directly using repository
            new_ticket = self.ticket_repo.create_ticket(db_fields)
            
            # Convert to dict and add ML fields for response
            ticket_dict = {
                "id": new_ticket.id,
                "title": new_ticket.title,
                "description": new_ticket.description,
                "status": new_ticket.status.value if hasattr(new_ticket.status, 'value') else new_ticket.status,
                "priority": new_ticket.priority.value if hasattr(new_ticket.priority, 'value') else new_ticket.priority,
                "customer_email": new_ticket.customer_email,
                "channel": new_ticket.channel.value if hasattr(new_ticket.channel, 'value') else new_ticket.channel,
                "external_id": new_ticket.external_id,
                "created_at": new_ticket.created_at.isoformat() if new_ticket.created_at else None,
                "updated_at": new_ticket.updated_at.isoformat() if new_ticket.updated_at else None,
                **ml_fields  # Add ML enhancement fields
            }
            
            # Add external_url from original ticket_data if it exists (not a DB field, but useful for API response)
            if 'external_url' in ticket_data:
                ticket_dict['external_url'] = ticket_data['external_url']
            
            return ticket_dict
            
        except Exception as e:
            logger.error(f"Error creating new ticket: {e}")
            return None
    
    def _update_existing_ticket(
        self, 
        existing_ticket, 
        new_data: Dict[str, Any],
        zendesk_ticket: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update existing ticket with new data from Zendesk"""
        try:
            # Check if ticket needs updating (compare timestamps)
            zendesk_updated_at = datetime.fromisoformat(
                zendesk_ticket["updated_at"].replace("Z", "+00:00")
            )
            
            if existing_ticket.updated_at >= zendesk_updated_at.replace(tzinfo=None):
                logger.debug(f"Ticket {existing_ticket.id} is already up to date")
                return existing_ticket
            
            # Prepare update data (only include valid database fields)
            valid_update_fields = {
                'title', 'description', 'status', 'priority', 'tags', 'customer_email',
                'customer_name', 'customer_phone'
            }
            
            update_data = {}
            for field in valid_update_fields:
                if field in new_data:
                    update_data[field] = new_data[field]
            
            # Remove None values
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            # Update the ticket
            updated_ticket = self.ticket_repo.update_ticket(existing_ticket.id, update_data)
            return updated_ticket
            
        except Exception as e:
            logger.error(f"Error updating existing ticket {existing_ticket.id}: {e}")
            return None
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get synchronization status and statistics"""
        try:
            # Count tickets by channel
            zendesk_ticket_count = self.ticket_repo.count_by_channel("zendesk")
            
            # Get last sync time
            last_zendesk_ticket = self._get_last_synced_ticket()
            last_sync_time = last_zendesk_ticket.updated_at if last_zendesk_ticket else None
            
            return {
                "zendesk_tickets_count": zendesk_ticket_count,
                "last_sync_time": last_sync_time.isoformat() if last_sync_time else None,
                "zendesk_connected": self.zendesk_client.test_connection(),
                "rate_limit_status": self.zendesk_client.get_rate_limit_status()
            }
            
        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            return {
                "error": str(e),
                "zendesk_connected": False
            }