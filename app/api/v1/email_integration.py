"""
Email Integration API Routes
Handles email configuration, processing, and ticket creation
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, status
from pydantic import BaseModel, EmailStr, Field
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from app.integrations.email import EmailManager, IMAPClient
from app.services.ticket_service import TicketService
from app.services.ml_service import ml_service
from app.api.v1.auth import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.ticket import TicketCreate
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email-integration", tags=["email-integration"])

# Pydantic models for requests/responses
class EmailIntegrationConfig(BaseModel):
    provider: str = Field(..., description="Email provider (gmail, outlook, yahoo, icloud, custom)")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., description="Email password or app password")
    server: Optional[str] = Field(None, description="Custom IMAP server (for custom provider)")
    port: Optional[int] = Field(993, description="IMAP port")
    ssl: Optional[bool] = Field(True, description="Use SSL/TLS")
    mailboxes: Dict[str, Dict[str, Any]] = Field(default_factory=lambda: {
        "INBOX": {"enabled": True, "process_all": True}
    }, description="Mailbox configuration")
    sync_frequency: Optional[int] = Field(300, description="Sync frequency in seconds")
    auto_create_tickets: Optional[bool] = Field(True, description="Automatically create tickets from emails")
    auto_reply: Optional[bool] = Field(False, description="Send auto-reply to customers")
    batch_size: Optional[int] = Field(50, description="Email processing batch size")
    days_back: Optional[int] = Field(7, description="Days to look back for emails")

class EmailIntegrationResponse(BaseModel):
    id: int
    organization_id: int
    provider: str
    email: str
    server: Optional[str]
    port: int
    ssl: bool
    mailboxes: Dict[str, Any]
    sync_frequency: int
    auto_create_tickets: bool
    auto_reply: bool
    is_active: bool
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
class EmailProcessingStats(BaseModel):
    total_emails_processed: int
    tickets_created_today: int
    duplicates_filtered_today: int
    last_sync_at: Optional[datetime]
    avg_processing_time: float
    mailbox_stats: Dict[str, Any]
    provider: str
    connection_status: str

class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    provider: str
    server: Optional[str]
    mailboxes_found: List[str]
    error: Optional[str] = None

class EmailProcessingResult(BaseModel):
    total_processed: int
    total_new: int
    total_duplicates: int
    tickets_created: int
    processing_time: float
    mailbox_results: Dict[str, Any]
    errors: List[str]

@router.post("/configure", response_model=EmailIntegrationResponse)
async def configure_email_integration(
    config: EmailIntegrationConfig,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Configure email integration for organization
    """
    try:
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must belong to an organization"
            )
        
        # Test connection first
        test_result = await test_email_connection(config)
        if not test_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection test failed: {test_result.error}"
            )
        
        # Store configuration in database (you'll need to create this model)
        from app.models.email_integration import EmailIntegration
        from app.database.repositories.email_integration_repository import EmailIntegrationRepository
        
        email_repo = EmailIntegrationRepository(db)
        
        # Check if integration already exists
        existing = email_repo.get_by_organization(current_user.organization_id)
        
        integration_data = {
            "organization_id": current_user.organization_id,
            "provider": config.provider,
            "email": config.email,
            "password": config.password,  # Should be encrypted in production
            "server": config.server,
            "port": config.port,
            "ssl": config.ssl,
            "mailboxes": config.mailboxes,
            "sync_frequency": config.sync_frequency,
            "auto_create_tickets": config.auto_create_tickets,
            "auto_reply": config.auto_reply,
            "batch_size": config.batch_size,
            "days_back": config.days_back,
            "is_active": True
        }
        
        if existing:
            integration = email_repo.update(existing, integration_data)
        else:
            integration = email_repo.create(integration_data)
        
        logger.info(f"Email integration configured for organization {current_user.organization_id}")
        
        return EmailIntegrationResponse(
            id=integration.id,
            organization_id=integration.organization_id,
            provider=integration.provider,
            email=integration.email,
            server=integration.server,
            port=integration.port,
            ssl=integration.ssl,
            mailboxes=integration.mailboxes,
            sync_frequency=integration.sync_frequency,
            auto_create_tickets=integration.auto_create_tickets,
            auto_reply=integration.auto_reply,
            is_active=integration.is_active,
            last_sync_at=integration.last_sync_at,
            created_at=integration.created_at,
            updated_at=integration.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring email integration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration failed: {str(e)}"
        )

@router.get("/test", response_model=ConnectionTestResponse)
async def test_email_connection(config: EmailIntegrationConfig):
    """
    Test email connection without saving configuration
    """
    try:
        # Create IMAP client with provided config
        imap_config = {
            "provider": config.provider,
            "email": config.email,
            "password": config.password,
        }
        
        if config.server:
            imap_config["server"] = config.server
        if config.port:
            imap_config["port"] = config.port
        if config.ssl is not None:
            imap_config["ssl"] = config.ssl
        
        client = IMAPClient(imap_config)
        
        # Test connection
        if client.connect():
            mailboxes = client.list_mailboxes()
            client.disconnect()
            
            return ConnectionTestResponse(
                success=True,
                message="Connection successful",
                provider=config.provider,
                server=imap_config.get("server"),
                mailboxes_found=mailboxes
            )
        else:
            return ConnectionTestResponse(
                success=False,
                message="Connection failed",
                provider=config.provider,
                server=imap_config.get("server"),
                mailboxes_found=[],
                error="Authentication failed"
            )
            
    except Exception as e:
        logger.error(f"Connection test error: {e}")
        return ConnectionTestResponse(
            success=False,
            message="Connection test failed",
            provider=config.provider,
            server=config.server,
            mailboxes_found=[],
            error=str(e)
        )

@router.get("/status", response_model=EmailIntegrationResponse)
async def get_email_integration_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current email integration configuration
    """
    try:
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No organization found"
            )
        
        from app.database.repositories.email_integration_repository import EmailIntegrationRepository
        email_repo = EmailIntegrationRepository(db)
        
        integration = email_repo.get_by_organization(current_user.organization_id)
        if not integration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No email integration configured"
            )
        
        return EmailIntegrationResponse(
            id=integration.id,
            organization_id=integration.organization_id,
            provider=integration.provider,
            email=integration.email,
            server=integration.server,
            port=integration.port,
            ssl=integration.ssl,
            mailboxes=integration.mailboxes,
            sync_frequency=integration.sync_frequency,
            auto_create_tickets=integration.auto_create_tickets,
            auto_reply=integration.auto_reply,
            is_active=integration.is_active,
            last_sync_at=integration.last_sync_at,
            created_at=integration.created_at,
            updated_at=integration.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting email integration status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/stats", response_model=EmailProcessingStats)
async def get_email_processing_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get email processing statistics
    """
    try:
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No organization found"
            )
        
        from app.database.repositories.email_integration_repository import EmailIntegrationRepository
        email_repo = EmailIntegrationRepository(db)
        
        integration = email_repo.get_by_organization(current_user.organization_id)
        if not integration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No email integration configured"
            )
        
        # Get processing stats from database or cache
        stats = email_repo.get_processing_stats(current_user.organization_id)
        
        return EmailProcessingStats(
            total_emails_processed=stats.get("total_emails_processed", 0),
            tickets_created_today=stats.get("tickets_created_today", 0),
            duplicates_filtered_today=stats.get("duplicates_filtered_today", 0),
            last_sync_at=integration.last_sync_at,
            avg_processing_time=stats.get("avg_processing_time", 0.0),
            mailbox_stats=stats.get("mailbox_stats", {}),
            provider=integration.provider,
            connection_status="active" if integration.is_active else "inactive"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting email processing stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/sync", response_model=EmailProcessingResult)
async def manual_email_sync(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger email synchronization
    """
    try:
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must belong to an organization"
            )
        
        from app.database.repositories.email_integration_repository import EmailIntegrationRepository
        email_repo = EmailIntegrationRepository(db)
        
        integration = email_repo.get_by_organization(current_user.organization_id)
        if not integration or not integration.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active email integration found"
            )
        
        # Add background task for email processing
        background_tasks.add_task(
            process_emails_for_organization,
            current_user.organization_id,
            integration.id
        )
        
        return EmailProcessingResult(
            total_processed=0,
            total_new=0,
            total_duplicates=0,
            tickets_created=0,
            processing_time=0.0,
            mailbox_results={},
            errors=[],
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting email sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/")
async def delete_email_integration(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete email integration configuration
    """
    try:
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must belong to an organization"
            )
        
        from app.database.repositories.email_integration_repository import EmailIntegrationRepository
        email_repo = EmailIntegrationRepository(db)
        
        integration = email_repo.get_by_organization(current_user.organization_id)
        if not integration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No email integration found"
            )
        
        email_repo.delete(integration.id)
        logger.info(f"Email integration deleted for organization {current_user.organization_id}")
        
        return {"message": "Email integration deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting email integration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Background task functions
async def process_emails_for_organization(organization_id: int, integration_id: int):
    """
    Background task to process emails for an organization
    """
    try:
        from app.database.connection import get_db
        from app.database.repositories.email_integration_repository import EmailIntegrationRepository
        
        db = next(get_db())
        email_repo = EmailIntegrationRepository(db)
        
        integration = email_repo.get(integration_id)
        if not integration or not integration.is_active:
            logger.warning(f"Integration {integration_id} not found or inactive")
            return
        
        # Create email manager configuration
        config = {
            "provider": integration.provider,
            "email": integration.email,
            "password": integration.password,
            "mailboxes": integration.mailboxes,
            "batch_size": integration.batch_size,
            "days_back": integration.days_back
        }
        
        # Add server config if specified (for custom providers)
        if integration.server:
            config["server"] = integration.server
            config["port"] = integration.port
            config["ssl"] = integration.ssl
        
        manager = EmailManager(config, db, integration_id)
        
        # Process emails
        with manager:
            results = manager.fetch_all_emails()
            
            # Create tickets from new emails
            tickets_created = 0
            if integration.auto_create_tickets:
                ticket_service = TicketService(db)
                
                for mailbox, mailbox_result in results['mailbox_results'].items():
                    for email_data in mailbox_result['emails']:
                        if not email_data.get('is_duplicate') and not email_data.get('skipped'):
                            try:
                                # Create ticket from email
                                ticket_data = create_ticket_from_email(email_data, organization_id)
                                ticket = ticket_service.create_ticket_from_email(ticket_data, organization_id)
                                tickets_created += 1
                                logger.info(f"Created ticket #{ticket['id']} from email '{email_data.get('subject')}'")
                                
                            except Exception as e:
                                logger.error(f"Error creating ticket from email '{email_data.get('subject')}': {e}")
                                # Continue processing other emails even if one fails
            
            # Update integration stats
            email_repo.update_processing_stats(integration_id, {
                "total_processed": results['total_processed'],
                "total_new": results['total_new'],
                "total_duplicates": results['total_duplicates'],
                "tickets_created": tickets_created,
                "last_sync_at": datetime.utcnow(),
                "processing_time": results['processing_time']
            })
            
            logger.info(f"Email processing completed for org {organization_id}: "
                       f"{results['total_processed']} processed, {tickets_created} tickets created")
            
    except Exception as e:
        logger.error(f"Error in email processing background task: {e}")
    finally:
        if 'db' in locals():
            db.close()

def create_ticket_from_email(email_data: Dict[str, Any], organization_id: int) -> Dict[str, Any]:
    """
    Convert email data to ticket creation format
    """
    ticket_info = email_data.get('ticket_info', {})
    sender = email_data.get('sender', {})
    
    # Enhance with ML analysis if available
    ml_analysis = {}
    main_content = email_data.get('main_content', '')
    
    # Fallback for empty content - try other content fields
    if not main_content.strip():
        logger.warning(f"Empty main_content for email '{email_data.get('subject', 'No Subject')}'. Trying fallbacks...")
        
        # Log available fields for debugging
        available_fields = list(email_data.keys())
        logger.debug(f"Available email fields: {available_fields}")
        
        main_content = (
            email_data.get('body_text', '') or
            email_data.get('body_html', '') or
            email_data.get('content', '') or
            'Email content could not be extracted'
        ).strip()
        
        logger.info(f"Using fallback content (length: {len(main_content)}): '{main_content[:100]}...' " + 
                   ("(truncated)" if len(main_content) > 100 else ""))
    if main_content:
        try:
            classification = ml_service.classify_ticket(main_content)
            sentiment = ml_service.analyze_sentiment(main_content)
            
            ml_analysis = {
                'ml_category': classification.get('category'),
                'ml_confidence': classification.get('confidence'),
                'ml_sentiment': sentiment.get('sentiment'),
                'ml_sentiment_score': sentiment.get('sentiment_score')
            }
        except Exception as e:
            logger.warning(f"ML analysis failed for email ticket: {e}")
    
    return {
        "title": email_data.get('subject', 'Email Support Request'),
        "description": main_content if main_content.strip() else 'Email content could not be extracted',
        "priority": ticket_info.get('priority', 'medium'),
        "status": "open",
        "category": ticket_info.get('category', 'general'),
        "customer_email": sender.get('email', ''),
        "customer_name": sender.get('name', ''),
        "channel": "email",
        "external_id": email_data.get('message_id'),
        "organization_id": organization_id,
        **ml_analysis
    }