"""
Email Integration Repository
Data access layer for email integration operations
"""

from typing import Optional, Dict, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from datetime import datetime, timedelta

from app.database.repositories.base_repository import BaseRepository
from app.models.email_integration import EmailIntegration, EmailProcessingLog


class EmailIntegrationRepository(BaseRepository[EmailIntegration]):
    """Repository for email integration operations"""
    
    def __init__(self, db: Session):
        super().__init__(EmailIntegration, db)
    
    def get_by_organization(self, organization_id: int) -> Optional[EmailIntegration]:
        """Get email integration by organization ID"""
        return self.db.query(EmailIntegration).filter(
            EmailIntegration.organization_id == organization_id
        ).first()
    
    def get_active_integrations(self) -> List[EmailIntegration]:
        """Get all active email integrations"""
        return self.db.query(EmailIntegration).filter(
            EmailIntegration.is_active == True
        ).all()
    
    def update_last_sync(self, integration_id: int, sync_time: datetime = None) -> None:
        """Update last sync time for integration"""
        if sync_time is None:
            sync_time = datetime.utcnow()
        
        self.db.query(EmailIntegration).filter(
            EmailIntegration.id == integration_id
        ).update({
            "last_sync_at": sync_time
        })
        self.db.commit()
    
    def update_processing_stats(self, integration_id: int, stats: Dict[str, Any]) -> None:
        """Update processing statistics for integration"""
        integration = self.get(integration_id)
        if not integration:
            return
        
        # Update cumulative stats
        updates = {}
        
        if "total_processed" in stats:
            updates["total_emails_processed"] = (
                integration.total_emails_processed + stats["total_processed"]
            )
        
        if "tickets_created" in stats:
            updates["total_tickets_created"] = (
                integration.total_tickets_created + stats["tickets_created"]
            )
        
        if "total_duplicates" in stats:
            updates["total_duplicates_filtered"] = (
                integration.total_duplicates_filtered + stats["total_duplicates"]
            )
        
        if "processing_time" in stats:
            # Update average processing time
            current_avg = integration.avg_processing_time or 0.0
            new_time = stats["processing_time"]
            total_sessions = integration.total_emails_processed + stats.get("total_processed", 0)
            
            if total_sessions > 0:
                updates["avg_processing_time"] = (
                    (current_avg * integration.total_emails_processed + new_time) / total_sessions
                )
        
        if "last_sync_at" in stats:
            updates["last_sync_at"] = stats["last_sync_at"]
        
        if "error_message" in stats:
            updates["last_error"] = stats["error_message"]
        
        # Apply updates
        if updates:
            self.db.query(EmailIntegration).filter(
                EmailIntegration.id == integration_id
            ).update(updates)
            self.db.commit()
    
    def get_processing_stats(self, organization_id: int) -> Dict[str, Any]:
        """Get processing statistics for organization"""
        integration = self.get_by_organization(organization_id)
        if not integration:
            return {}
        
        # Get today's stats from processing logs
        today = datetime.utcnow().date()
        today_stats = self.db.query(
            func.sum(EmailProcessingLog.tickets_created).label('tickets_today'),
            func.sum(EmailProcessingLog.emails_duplicate).label('duplicates_today'),
            func.avg(EmailProcessingLog.processing_time).label('avg_time_today')
        ).filter(
            and_(
                EmailProcessingLog.integration_id == integration.id,
                func.date(EmailProcessingLog.started_at) == today,
                EmailProcessingLog.status == 'success'
            )
        ).first()
        
        # Get mailbox stats from recent logs
        recent_logs = self.db.query(EmailProcessingLog).filter(
            and_(
                EmailProcessingLog.integration_id == integration.id,
                EmailProcessingLog.started_at >= datetime.utcnow() - timedelta(days=7),
                EmailProcessingLog.status == 'success'
            )
        ).order_by(desc(EmailProcessingLog.started_at)).limit(10).all()
        
        mailbox_stats = {}
        for log in recent_logs:
            if log.mailbox_results:
                for mailbox, results in log.mailbox_results.items():
                    if mailbox not in mailbox_stats:
                        mailbox_stats[mailbox] = {
                            "total_processed": 0,
                            "total_new": 0,
                            "total_duplicates": 0
                        }
                    
                    mailbox_stats[mailbox]["total_processed"] += results.get("processed", 0)
                    mailbox_stats[mailbox]["total_new"] += results.get("new", 0)
                    mailbox_stats[mailbox]["total_duplicates"] += results.get("duplicates", 0)
        
        return {
            "total_emails_processed": integration.total_emails_processed,
            "tickets_created_today": today_stats.tickets_today or 0,
            "duplicates_filtered_today": today_stats.duplicates_today or 0,
            "avg_processing_time": today_stats.avg_time_today or integration.avg_processing_time,
            "mailbox_stats": mailbox_stats
        }
    
    def create_processing_log(self, integration_id: int, log_data: Dict[str, Any]) -> EmailProcessingLog:
        """Create a processing log entry"""
        log = EmailProcessingLog(
            integration_id=integration_id,
            started_at=log_data.get("started_at", datetime.utcnow()),
            completed_at=log_data.get("completed_at"),
            status=log_data.get("status", "started"),
            emails_processed=log_data.get("emails_processed", 0),
            emails_new=log_data.get("emails_new", 0),
            emails_duplicate=log_data.get("emails_duplicate", 0),
            tickets_created=log_data.get("tickets_created", 0),
            processing_time=log_data.get("processing_time", 0.0),
            mailbox_results=log_data.get("mailbox_results"),
            error_message=log_data.get("error_message"),
            error_details=log_data.get("error_details")
        )
        
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        
        return log
    
    def update_processing_log(self, log_id: int, updates: Dict[str, Any]) -> Optional[EmailProcessingLog]:
        """Update a processing log entry"""
        log = self.db.query(EmailProcessingLog).filter(
            EmailProcessingLog.id == log_id
        ).first()
        
        if not log:
            return None
        
        for key, value in updates.items():
            if hasattr(log, key):
                setattr(log, key, value)
        
        self.db.commit()
        self.db.refresh(log)
        
        return log
    
    def get_processing_logs(self, integration_id: int, limit: int = 50) -> List[EmailProcessingLog]:
        """Get processing logs for integration"""
        return self.db.query(EmailProcessingLog).filter(
            EmailProcessingLog.integration_id == integration_id
        ).order_by(desc(EmailProcessingLog.started_at)).limit(limit).all()
    
    def get_recent_errors(self, organization_id: int, days: int = 7) -> List[EmailProcessingLog]:
        """Get recent error logs for organization"""
        integration = self.get_by_organization(organization_id)
        if not integration:
            return []
        
        return self.db.query(EmailProcessingLog).filter(
            and_(
                EmailProcessingLog.integration_id == integration.id,
                EmailProcessingLog.status == 'error',
                EmailProcessingLog.started_at >= datetime.utcnow() - timedelta(days=days)
            )
        ).order_by(desc(EmailProcessingLog.started_at)).all()
    
    def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """Clean up old processing logs"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        count = self.db.query(EmailProcessingLog).filter(
            EmailProcessingLog.started_at < cutoff_date
        ).count()
        
        self.db.query(EmailProcessingLog).filter(
            EmailProcessingLog.started_at < cutoff_date
        ).delete()
        
        self.db.commit()
        
        return count
    
    def get_organizations_by_sync_schedule(self) -> List[EmailIntegration]:
        """Get integrations that need syncing based on their schedule"""
        now = datetime.utcnow()
        
        # Get integrations where last_sync_at + sync_frequency < now
        integrations = self.db.query(EmailIntegration).filter(
            and_(
                EmailIntegration.is_active == True,
                func.coalesce(
                    EmailIntegration.last_sync_at + func.make_interval(seconds=EmailIntegration.sync_frequency),
                    datetime(1970, 1, 1)  # Default to epoch if never synced
                ) < now
            )
        ).all()
        
        return integrations