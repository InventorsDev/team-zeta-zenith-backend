from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.services.integration_service import IntegrationService
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.integration import IntegrationType, IntegrationStatus
from app.schemas.integration import (
    IntegrationCreate, IntegrationUpdate, IntegrationResponse, IntegrationSummary,
    IntegrationFilter, PaginatedIntegrations, IntegrationStats,
    IntegrationStatusUpdate, IntegrationTest, IntegrationConfigMask
)

# Import Zendesk integration components
from app.integrations.zendesk import ZendeskClient, ZendeskSyncService, ZendeskWebhookHandler
from app.core.config import get_settings

settings = get_settings()

router = APIRouter(prefix="/integrations", tags=["integrations"])


def get_integration_service(db: Session = Depends(get_db)) -> IntegrationService:
    """Dependency to get integration service"""
    return IntegrationService(db)


def get_user_zendesk_client(
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
) -> ZendeskClient:
    """
    Get ZendeskClient configured with the user's integration settings from database
    """
    try:
        # Get the user's Zendesk integration from database
        from app.models.integration import IntegrationType
        
        from app.schemas.integration import IntegrationFilter
        filters = IntegrationFilter(type=IntegrationType.ZENDESK, active_only=True)
        integrations = integration_service.get_integrations(
            organization_id=current_user.organization_id,
            filters=filters
        )
        
        if not integrations.items:
            raise HTTPException(
                status_code=404, 
                detail="No active Zendesk integration found for your organization. Please create a Zendesk integration first by calling POST /api/v1/integrations with your Zendesk credentials."
            )
        
        # Get the first active Zendesk integration
        integration = integrations.items[0]
        
        # Get the actual integration record to access decrypted config
        integration_record = integration_service.integration_repo.get(integration.id)
        if not integration_record:
            raise HTTPException(
                status_code=404,
                detail="Integration record not found"
            )
        
        # Get decrypted config directly from repository
        decrypted_config = integration_service.integration_repo.get_decrypted_config(integration_record)
        
        # Create ZendeskClient with user's decrypted config
        return ZendeskClient(decrypted_config)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error loading Zendesk integration: {str(e)}"
        )


@router.post("/", response_model=IntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_integration(
    integration_data: IntegrationCreate,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Create a new integration"""
    return integration_service.create_integration(integration_data, current_user)


@router.get("/", response_model=PaginatedIntegrations)
async def get_integrations(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    # Filters
    type: Optional[IntegrationType] = Query(None, description="Filter by integration type"),
    status: Optional[IntegrationStatus] = Query(None, description="Filter by status"),
    active_only: Optional[bool] = Query(None, description="Show only active integrations"),
    search: Optional[str] = Query(None, max_length=100, description="Search in integration name"),
    has_errors: Optional[bool] = Query(None, description="Filter integrations with errors"),
    sync_enabled: Optional[bool] = Query(None, description="Filter by sync enabled status"),
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Get paginated integrations with filtering"""
    # Create filter object
    filters = IntegrationFilter(
        type=type,
        status=status,
        active_only=active_only,
        search=search,
        has_errors=has_errors,
        sync_enabled=sync_enabled
    )
    
    return integration_service.get_integrations(
        organization_id=current_user.organization_id,
        filters=filters,
        page=page,
        size=size
    )


@router.get("/stats", response_model=IntegrationStats)
async def get_integration_stats(
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Get integration statistics for the current organization"""
    return integration_service.get_integration_stats(current_user.organization_id)


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Get a specific integration by ID"""
    return integration_service.get_integration(integration_id, current_user.organization_id)


@router.put("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: int,
    integration_data: IntegrationUpdate,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Update an integration"""
    return integration_service.update_integration(
        integration_id, current_user.organization_id, integration_data
    )


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Delete an integration"""
    integration_service.delete_integration(integration_id, current_user.organization_id)


@router.patch("/{integration_id}/status", response_model=IntegrationResponse)
async def update_integration_status(
    integration_id: int,
    status_data: IntegrationStatusUpdate,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Update integration status"""
    return integration_service.update_integration_status(
        integration_id, current_user.organization_id, status_data.status, status_data.error_message
    )


@router.post("/{integration_id}/test")
async def test_integration(
    integration_id: int,
    test_data: IntegrationTest,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Test integration connection"""
    return integration_service.test_integration(integration_id, current_user.organization_id)


@router.get("/{integration_id}/config", response_model=IntegrationConfigMask)
async def get_integration_config(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Get integration configuration (masked for security)"""
    return integration_service.get_integration_config(integration_id, current_user.organization_id)


# Additional endpoints for common operations

@router.get("/type/{integration_type}", response_model=PaginatedIntegrations)
async def get_integrations_by_type(
    integration_type: IntegrationType,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Get integrations by type"""
    filters = IntegrationFilter(type=integration_type)
    return integration_service.get_integrations(
        organization_id=current_user.organization_id,
        filters=filters,
        page=page,
        size=size
    )


@router.get("/active", response_model=PaginatedIntegrations)
async def get_active_integrations(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Get active integrations"""
    filters = IntegrationFilter(status=IntegrationStatus.ACTIVE)
    return integration_service.get_integrations(
        organization_id=current_user.organization_id,
        filters=filters,
        page=page,
        size=size
    )


@router.get("/errors", response_model=PaginatedIntegrations)
async def get_error_integrations(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Get integrations with errors"""
    filters = IntegrationFilter(status=IntegrationStatus.ERROR)
    return integration_service.get_integrations(
        organization_id=current_user.organization_id,
        filters=filters,
        page=page,
        size=size
    )


@router.patch("/{integration_id}/enable-sync")
async def enable_sync(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Enable ticket synchronization for an integration"""
    update_data = IntegrationUpdate(sync_tickets=True)
    return integration_service.update_integration(
        integration_id, current_user.organization_id, update_data
    )


@router.patch("/{integration_id}/disable-sync")
async def disable_sync(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Disable ticket synchronization for an integration"""
    update_data = IntegrationUpdate(sync_tickets=False)
    return integration_service.update_integration(
        integration_id, current_user.organization_id, update_data
    )


@router.patch("/{integration_id}/enable-webhooks")
async def enable_webhooks(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Enable webhook reception for an integration"""
    update_data = IntegrationUpdate(receive_webhooks=True)
    return integration_service.update_integration(
        integration_id, current_user.organization_id, update_data
    )


@router.patch("/{integration_id}/disable-webhooks")
async def disable_webhooks(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Disable webhook reception for an integration"""
    update_data = IntegrationUpdate(receive_webhooks=False)
    return integration_service.update_integration(
        integration_id, current_user.organization_id, update_data
    )


# Zendesk-specific integration endpoints
zendesk_router = APIRouter(prefix="/zendesk", tags=["zendesk"])


@zendesk_router.get("/status")
async def get_zendesk_status(
    zendesk_client: ZendeskClient = Depends(get_user_zendesk_client)
):
    """Get Zendesk integration status and connection health"""
    try:
        sync_service = ZendeskSyncService(zendesk_client)
        
        # Get connection status
        connection_status = zendesk_client.test_connection()
        
        # Get sync status
        sync_status = sync_service.get_sync_status()
        
        # Get rate limit status
        rate_limit_status = zendesk_client.get_rate_limit_status()
        
        return {
            "integration": "zendesk",
            "enabled": zendesk_client.is_enabled,
            "connected": connection_status,
            "sync_status": sync_status,
            "rate_limit": rate_limit_status,
            "health": "healthy" if connection_status else "unhealthy"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking Zendesk status: {str(e)}")


@zendesk_router.post("/sync")
async def sync_zendesk_tickets(
    full_sync: bool = Query(False, description="Perform full sync (all tickets) or incremental"),
    zendesk_client: ZendeskClient = Depends(get_user_zendesk_client)
):
    """Manually trigger Zendesk ticket synchronization"""
    try:
        
        if not zendesk_client.is_enabled:
            raise HTTPException(
                status_code=400, 
                detail="Zendesk integration is not properly configured"
            )
        
        # Perform sync
        sync_result = zendesk_client.sync_tickets(full_sync=full_sync)
        
        return {
            "sync_triggered": True,
            "sync_type": sync_result.sync_type,
            "result": {
                "total_fetched": sync_result.total_fetched,
                "total_processed": sync_result.total_processed,
                "total_created": sync_result.total_created,
                "total_updated": sync_result.total_updated,
                "total_errors": sync_result.total_errors,
                "duration_seconds": sync_result.duration_seconds,
                "errors": sync_result.errors[:5] if sync_result.errors else []  # Show first 5 errors
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@zendesk_router.post("/sync/ticket/{zendesk_ticket_id}")
async def sync_single_zendesk_ticket(
    zendesk_ticket_id: int,
    zendesk_client: ZendeskClient = Depends(get_user_zendesk_client)
):
    """Sync a specific ticket by Zendesk ID"""
    try:
        sync_service = ZendeskSyncService(zendesk_client)
        
        if not zendesk_client.is_enabled:
            raise HTTPException(
                status_code=400,
                detail="Zendesk integration is not properly configured"
            )
        
        # Sync single ticket
        synced_ticket = sync_service.sync_single_ticket(zendesk_ticket_id)
        
        if synced_ticket:
            return {
                "synced": True,
                "zendesk_ticket_id": zendesk_ticket_id,
                "internal_ticket": synced_ticket
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Ticket {zendesk_ticket_id} not found or could not be synced"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing ticket: {str(e)}")


# @zendesk_router.post("/webhook")
# async def handle_zendesk_webhook(
#     request: Request,
#     signature: Optional[str] = Query(None, alias="X-Zendesk-Webhook-Signature")
# ):
#     """Handle incoming Zendesk webhooks"""
#     try:
#         # Get request body for signature verification
#         body = await request.body()
#         payload = await request.json()
        
#         # Initialize webhook handler
#         webhook_handler = ZendeskWebhookHandler()
        
#         # Process the webhook
#         result = webhook_handler.handle_webhook(
#             payload=payload,
#             signature=signature,
#             body=body
#         )
        
#         return result
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


# @zendesk_router.get("/webhook/info")
# async def get_zendesk_webhook_info():
#     """Get information about webhook configuration"""
#     try:
#         webhook_handler = ZendeskWebhookHandler()
        
#         # Validate webhook configuration
#         validation = webhook_handler.validate_webhook_config()
        
#         # Get webhook URL
#         if settings.environment == "development":
#             webhook_url = webhook_handler.get_webhook_url(settings.local_api_url or "http://localhost:8000")
#         else:
#             webhook_url = webhook_handler.get_webhook_url(settings.prod_api_url or "http://localhost:8000")
        
#         return {
#             "webhook_url": webhook_url,
#             "configuration": validation,
#             "supported_events": [
#                 "ticket.created",
#                 "ticket.updated", 
#                 "ticket.deleted",
#                 "ticket.comment_created",
#                 "ticket.status_changed"
#             ],
#             "setup_instructions": [
#                 "1. Go to Zendesk Admin → Settings → Extensions → Webhooks",
#                 "2. Create a new webhook with the URL above",
#                 "3. Configure events you want to receive",
#                 "4. Set authentication method to Bearer token or Signing secret",
#                 "5. Test the webhook with a sample event"
#             ]
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error getting webhook info: {str(e)}")


@zendesk_router.get("/tickets/{zendesk_ticket_id}")
async def get_zendesk_ticket(
    zendesk_ticket_id: int,
    zendesk_client: ZendeskClient = Depends(get_user_zendesk_client)
):
    """Get a specific ticket from Zendesk by ID"""
    try:
        
        if not zendesk_client.is_enabled:
            raise HTTPException(
                status_code=400,
                detail="Zendesk integration is not properly configured"
            )
        
        # Fetch ticket from Zendesk
        ticket = zendesk_client.get_ticket(zendesk_ticket_id)
        
        if ticket:
            return {
                "found": True,
                "zendesk_ticket": ticket
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Ticket {zendesk_ticket_id} not found in Zendesk"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching ticket: {str(e)}")


@zendesk_router.get("/rate-limit")
async def get_zendesk_rate_limit(
    zendesk_client: ZendeskClient = Depends(get_user_zendesk_client)
):
    """Get current Zendesk API rate limit status"""
    try:
        rate_limit_status = zendesk_client.get_rate_limit_status()
        
        return rate_limit_status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking rate limit: {str(e)}")


@zendesk_router.post("/test-connection")
async def test_zendesk_connection(
    zendesk_client: ZendeskClient = Depends(get_user_zendesk_client)
):
    """Test Zendesk API connection"""
    try:
        
        connection_test = zendesk_client.test_connection()
        
        return {
            "connected": connection_test,
            "configured": zendesk_client.is_enabled,
            "message": "Connection successful" if connection_test else "Connection failed"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")


# Secure webhook endpoints using unique tokens
webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@webhook_router.post("/{webhook_token}")
async def handle_integration_webhook(
    webhook_token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle webhooks using unique integration tokens"""
    try:
        # Find integration by webhook token
        integration_service = IntegrationService(db)
        integration = integration_service.get_integration_by_webhook_token(webhook_token)
        
        if not integration:
            raise HTTPException(status_code=404, detail="Webhook token not found")
        
        # Get request body and headers
        body = await request.body()
        headers = dict(request.headers)
        
        # Route to appropriate integration handler based on type
        if integration.type == "zendesk":
            from app.integrations.zendesk.webhook import ZendeskWebhookHandler
            
            # Get user's Zendesk client config
            integration_record = integration_service.integration_repo.get(integration.id)
            decrypted_config = integration_service.integration_repo.get_decrypted_config(integration_record)
            
            # Initialize webhook handler with user's config
            webhook_handler = ZendeskWebhookHandler(db)
            
            # Parse JSON payload
            payload = await request.json()
            
            # Get signature from headers (Zendesk uses X-Zendesk-Webhook-Signature)
            signature = headers.get("x-zendesk-webhook-signature")
            
            # Process the webhook
            result = webhook_handler.handle_webhook(
                payload=payload,
                signature=signature,
                body=body
            )
            
            # Update webhook stats
            integration_service.increment_webhook_count(integration.id)
            
            return result
            
        elif integration.type == "slack":
            # TODO: Implement Slack webhook handling
            return {"status": "success", "message": "Slack webhook received", "integration_type": "slack"}
            
        else:
            return {"status": "success", "message": f"Webhook received for {integration.type}", "integration_type": integration.type}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


@webhook_router.get("/{webhook_token}/info")
async def get_webhook_info(
    webhook_token: str,
    db: Session = Depends(get_db)
):
    """Get information about a webhook endpoint"""
    try:
        integration_service = IntegrationService(db)
        integration = integration_service.get_integration_by_webhook_token(webhook_token)
        
        if not integration:
            raise HTTPException(status_code=404, detail="Webhook token not found")
            
        return {
            "webhook_token": webhook_token,
            "integration_type": integration.type,
            "integration_name": integration.name,
            "organization_id": integration.organization_id,
            "webhook_enabled": integration.receive_webhooks,
            "total_webhooks_received": integration.total_webhooks_received,
            "supported_events": [
                "ticket.created",
                "ticket.updated", 
                "ticket.deleted",
                "comment.created"
            ] if integration.type == "zendesk" else ["generic.event"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting webhook info: {str(e)}")


# Include routers
router.include_router(zendesk_router)
router.include_router(webhook_router)
