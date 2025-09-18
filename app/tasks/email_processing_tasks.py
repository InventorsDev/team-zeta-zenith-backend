"""
Email Processing Background Tasks
Handles scheduled email fetching and ticket creation
"""

import logging
from typing import Dict, Any
from celery import shared_task
from datetime import datetime
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.repositories.email_integration_repository import EmailIntegrationRepository
from app.services.ticket_service import TicketService
from app.services.ml_service import ml_service
from app.integrations.email import EmailManager

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def process_all_email_integrations(self) -> Dict[str, Any]:
    """
    Process emails for all active integrations
    This task should be scheduled to run periodically (e.g., every 5 minutes)
    """
    try:
        db = next(get_db())
        email_repo = EmailIntegrationRepository(db)
        
        # Get integrations that need syncing
        integrations_to_sync = email_repo.get_organizations_by_sync_schedule()
        
        results = {
            "task_id": self.request.id,
            "started_at": datetime.utcnow().isoformat(),
            "integrations_processed": 0,
            "total_emails": 0,
            "total_tickets": 0,
            "errors": []
        }
        
        for integration in integrations_to_sync:
            try:
                result = process_organization_emails.delay(integration.organization_id, integration.id)
                results["integrations_processed"] += 1
                logger.info(f"Started email processing for org {integration.organization_id}")
                
            except Exception as e:
                error_msg = f"Failed to start processing for org {integration.organization_id}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
        
        results["completed_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"Scheduled email processing: {results['integrations_processed']} integrations queued")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in scheduled email processing: {e}")
        return {
            "task_id": self.request.id,
            "error": str(e),
            "failed_at": datetime.utcnow().isoformat()
        }
    finally:
        if 'db' in locals():
            db.close()

@shared_task(bind=True)
def process_organization_emails(self, organization_id: int, integration_id: int) -> Dict[str, Any]:
    """
    Process emails for a specific organization
    """
    db = None
    processing_log = None
    
    try:
        db = next(get_db())
        email_repo = EmailIntegrationRepository(db)
        
        # Get integration configuration
        integration = email_repo.get(integration_id)
        if not integration or not integration.is_active:
            logger.warning(f"Integration {integration_id} not found or inactive")
            return {"error": "Integration not found or inactive"}
        
        # Create processing log
        processing_log = email_repo.create_processing_log(integration_id, {
            "status": "started",
            "started_at": datetime.utcnow()
        })
        
        # Create email manager configuration
        config = {
            "provider": integration.provider,
            "email": integration.email,
            "password": integration.password,  # Should be decrypted in production
            "server": integration.server,
            "port": integration.port,
            "ssl": integration.ssl,
            "mailboxes": integration.mailboxes,
            "batch_size": integration.batch_size,
            "days_back": integration.days_back
        }
        
        manager = EmailManager(config)
        tickets_created = 0
        
        # Process emails
        with manager:
            results = manager.fetch_all_emails()
            
            # Create tickets from new emails if auto-creation is enabled
            if integration.auto_create_tickets and results['total_new'] > 0:
                ticket_service = TicketService(db)
                
                for mailbox, mailbox_result in results['mailbox_results'].items():
                    for email_data in mailbox_result.get('emails', []):
                        if not email_data.get('is_duplicate') and not email_data.get('skipped'):
                            try:
                                # Create ticket from email
                                ticket_data = create_ticket_from_email(email_data, organization_id)
                                ticket = ticket_service.create_ticket(ticket_data, organization_id)
                                tickets_created += 1
                                
                                logger.info(f"Created ticket #{ticket.id} from email: {email_data.get('subject', 'No subject')}")
                                
                                # Send auto-reply if enabled
                                if integration.auto_reply and integration.auto_reply_template:
                                    try:
                                        send_auto_reply_email(email_data, ticket, integration)
                                    except Exception as e:
                                        logger.warning(f"Failed to send auto-reply: {e}")
                                
                            except Exception as e:
                                logger.error(f"Error creating ticket from email: {e}")
            
            # Update processing statistics
            email_repo.update_processing_stats(integration_id, {
                "total_processed": results['total_processed'],
                "total_new": results['total_new'], 
                "total_duplicates": results['total_duplicates'],
                "tickets_created": tickets_created,
                "last_sync_at": datetime.utcnow(),
                "processing_time": results['processing_time']
            })
            
            # Update processing log
            email_repo.update_processing_log(processing_log.id, {
                "completed_at": datetime.utcnow(),
                "status": "success",
                "emails_processed": results['total_processed'],
                "emails_new": results['total_new'],
                "emails_duplicate": results['total_duplicates'],
                "tickets_created": tickets_created,
                "processing_time": results['processing_time'],
                "mailbox_results": results['mailbox_results']
            })
            
            logger.info(f"Email processing completed for org {organization_id}: "
                       f"{results['total_processed']} processed, {tickets_created} tickets created")
            
            return {
                "task_id": self.request.id,
                "organization_id": organization_id,
                "integration_id": integration_id,
                "success": True,
                **results,
                "tickets_created": tickets_created
            }
            
    except Exception as e:
        logger.error(f"Error processing emails for org {organization_id}: {e}")
        
        # Update processing log with error
        if processing_log and db:
            try:
                email_repo.update_processing_log(processing_log.id, {
                    "completed_at": datetime.utcnow(),
                    "status": "error",
                    "error_message": str(e)
                })
            except:
                pass
        
        return {
            "task_id": self.request.id,
            "organization_id": organization_id,
            "integration_id": integration_id,
            "success": False,
            "error": str(e),
            "failed_at": datetime.utcnow().isoformat()
        }
        
    finally:
        if db:
            db.close()

def create_ticket_from_email(email_data: Dict[str, Any], organization_id: int) -> Dict[str, Any]:
    """
    Convert email data to ticket creation format with ML enhancement
    """
    ticket_info = email_data.get('ticket_info', {})
    sender = email_data.get('sender', {})
    main_content = email_data.get('main_content', '')
    
    # Base ticket data
    ticket_data = {
        "title": email_data.get('subject', 'Email Support Request')[:255],  # Limit title length
        "description": main_content,
        "priority": ticket_info.get('priority', 'medium'),
        "category": ticket_info.get('category', 'general'),
        "customer_email": sender.get('email', ''),
        "customer_name": sender.get('name', ''),
        "source": "email",
        "external_id": email_data.get('message_id'),
        "organization_id": organization_id
    }
    
    # Add ML analysis if available and content exists
    if main_content.strip():
        try:
            # Get ML classification
            classification = ml_service.classify_ticket(main_content)
            if classification.get('category'):
                ticket_data['ml_category'] = classification['category']
                ticket_data['ml_confidence'] = classification.get('confidence', 0.0)
                ticket_data['ml_confidence_label'] = classification.get('confidence_label', 'low')
            
            # Get sentiment analysis
            sentiment = ml_service.analyze_sentiment(main_content)
            if sentiment.get('sentiment'):
                ticket_data['ml_sentiment'] = sentiment['sentiment']
                ticket_data['ml_sentiment_score'] = sentiment.get('sentiment_score', 0.0)
            
            # Override priority if ML detected high urgency
            if (classification.get('confidence', 0) > 0.7 and 
                any(indicator in email_data.get('metadata', {}).get('urgency_indicators', []) 
                    for indicator in ['urgent', 'emergency', 'critical'])):
                ticket_data['priority'] = 'high'
                
        except Exception as e:
            logger.warning(f"ML analysis failed for email ticket: {e}")
    
    # Add attachment information
    attachments = email_data.get('attachments', [])
    if attachments:
        ticket_data['has_attachments'] = True
        ticket_data['attachment_count'] = len(attachments)
        
        # Add attachment metadata
        attachment_info = []
        for attachment in attachments:
            attachment_info.append({
                'filename': attachment.get('filename', 'unknown'),
                'size': attachment.get('size', 0),
                'content_type': attachment.get('content_type', ''),
                'file_category': attachment.get('file_category', 'other')
            })
        
        ticket_data['attachment_metadata'] = attachment_info
    
    return ticket_data

def send_auto_reply_email(email_data: Dict[str, Any], ticket, integration):
    """
    Send auto-reply email to customer
    """
    try:
        sender = email_data.get('sender', {})
        customer_email = sender.get('email')
        
        if not customer_email:
            logger.warning("No customer email found for auto-reply")
            return
        
        # Format auto-reply template
        template = integration.auto_reply_template or """
Thank you for contacting our support team!

We have received your email and created support ticket #{ticket_id} to track your request.

Subject: {subject}
Ticket ID: #{ticket_id}
Priority: {priority}

Our support team will review your request and respond within our standard response time based on the priority level.

You can reference ticket #{ticket_id} in any future communications regarding this issue.

Best regards,
{organization_name} Support Team
        """.strip()
        
        # Replace template variables
        auto_reply_content = template.format(
            ticket_id=ticket.id,
            subject=email_data.get('subject', 'Support Request'),
            priority=ticket.priority.title(),
            organization_name=ticket.organization.name if ticket.organization else "Support"
        )
        
        # TODO: Implement actual email sending
        # This would integrate with your email sending service (SMTP, SendGrid, etc.)
        logger.info(f"Auto-reply would be sent to {customer_email} for ticket #{ticket.id}")
        
    except Exception as e:
        logger.error(f"Error preparing auto-reply: {e}")

@shared_task
def cleanup_old_email_logs():
    """
    Cleanup old email processing logs
    This task should be scheduled to run daily
    """
    try:
        db = next(get_db())
        email_repo = EmailIntegrationRepository(db)
        
        # Clean up logs older than 30 days
        deleted_count = email_repo.cleanup_old_logs(days_to_keep=30)
        
        logger.info(f"Cleaned up {deleted_count} old email processing logs")
        
        return {
            "deleted_count": deleted_count,
            "completed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in email log cleanup: {e}")
        return {"error": str(e)}
    finally:
        if 'db' in locals():
            db.close()