"""
Audit Service - Handles audit logging for security-relevant actions
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from app.models.audit_log import AuditLog
from app.models.user import User

logger = logging.getLogger(__name__)


class AuditService:
    """Service for creating and querying audit logs"""

    def __init__(self, db: Session):
        self.db = db

    def log_action(
        self,
        action: str,
        status: str,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        endpoint: Optional[str] = None,
        http_method: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "info",
    ) -> AuditLog:
        """
        Create an audit log entry

        Args:
            action: Action identifier (e.g., "user.login", "ticket.create")
            status: "success", "failure", or "unauthorized"
            user_id: ID of user performing action (None for anonymous)
            organization_id: Organization context
            resource_type: Type of resource affected (e.g., "ticket", "user")
            resource_id: ID of affected resource
            ip_address: Client IP address
            user_agent: Client user agent string
            endpoint: API endpoint accessed
            http_method: HTTP method used
            details: Additional context as dictionary
            severity: "info", "warning", or "critical"

        Returns:
            Created AuditLog object
        """
        try:
            audit_log = AuditLog(
                user_id=user_id,
                organization_id=organization_id,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else None,
                status=status,
                ip_address=ip_address,
                user_agent=user_agent,
                endpoint=endpoint,
                http_method=http_method,
                details=details or {},
                severity=severity,
            )

            self.db.add(audit_log)
            self.db.commit()
            self.db.refresh(audit_log)

            # Log critical events to application logger as well
            if severity == "critical":
                logger.warning(
                    f"CRITICAL AUDIT: {action} by user {user_id} - {status}: {details}"
                )

            return audit_log

        except Exception as e:
            logger.error(f"Error creating audit log: {e}")
            self.db.rollback()
            # Don't fail the main operation if audit logging fails
            return None

    def log_auth_attempt(
        self,
        username: str,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> AuditLog:
        """Log authentication attempt"""
        return self.log_action(
            action="auth.login",
            status="success" if success else "failure",
            ip_address=ip_address,
            user_agent=user_agent,
            endpoint="/api/v1/auth/login",
            http_method="POST",
            details={
                "username": username,
                "reason": reason,
            },
            severity="warning" if not success else "info",
        )

    def log_permission_denied(
        self,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log permission denied events"""
        return self.log_action(
            action=action,
            status="unauthorized",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            severity="warning",
            details={"reason": "insufficient_permissions"},
        )

    def log_data_export(
        self,
        user_id: int,
        organization_id: int,
        export_type: str,
        record_count: int,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log data export events"""
        return self.log_action(
            action="data.export",
            status="success",
            user_id=user_id,
            organization_id=organization_id,
            resource_type="export",
            ip_address=ip_address,
            severity="info",
            details={
                "export_type": export_type,
                "record_count": record_count,
            },
        )

    def log_config_change(
        self,
        user_id: int,
        organization_id: int,
        config_type: str,
        changes: Dict[str, Any],
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log configuration changes"""
        return self.log_action(
            action="config.update",
            status="success",
            user_id=user_id,
            organization_id=organization_id,
            resource_type=config_type,
            ip_address=ip_address,
            severity="info",
            details={"changes": changes},
        )

    def get_logs(
        self,
        organization_id: Optional[int] = None,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLog]:
        """
        Query audit logs with filters

        Args:
            organization_id: Filter by organization
            user_id: Filter by user
            action: Filter by action type
            status: Filter by status
            severity: Filter by severity
            start_date: Filter logs after this date
            end_date: Filter logs before this date
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of AuditLog objects
        """
        query = self.db.query(AuditLog)

        if organization_id:
            query = query.filter(AuditLog.organization_id == organization_id)

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        if action:
            query = query.filter(AuditLog.action == action)

        if status:
            query = query.filter(AuditLog.status == status)

        if severity:
            query = query.filter(AuditLog.severity == severity)

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)

        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        query = query.order_by(AuditLog.created_at.desc())
        query = query.offset(offset).limit(limit)

        return query.all()

    def get_failed_login_attempts(
        self,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        hours: int = 24,
    ) -> List[AuditLog]:
        """Get recent failed login attempts"""
        query = self.db.query(AuditLog).filter(
            AuditLog.action == "auth.login",
            AuditLog.status == "failure",
            AuditLog.created_at >= datetime.utcnow() - timedelta(hours=hours),
        )

        if username:
            query = query.filter(AuditLog.details["username"].astext == username)

        if ip_address:
            query = query.filter(AuditLog.ip_address == ip_address)

        return query.order_by(AuditLog.created_at.desc()).all()

    def get_suspicious_activity(
        self, organization_id: int, hours: int = 24
    ) -> List[AuditLog]:
        """Get potentially suspicious activity"""
        query = self.db.query(AuditLog).filter(
            AuditLog.organization_id == organization_id,
            AuditLog.created_at >= datetime.utcnow() - timedelta(hours=hours),
        )

        # Filter for suspicious patterns
        query = query.filter(
            (AuditLog.status == "failure") |
            (AuditLog.status == "unauthorized") |
            (AuditLog.severity == "critical")
        )

        return query.order_by(AuditLog.created_at.desc()).all()

    def cleanup_old_logs(self, days: int = 90) -> int:
        """
        Delete audit logs older than specified days

        Args:
            days: Delete logs older than this many days

        Returns:
            Number of logs deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            deleted_count = (
                self.db.query(AuditLog)
                .filter(AuditLog.created_at < cutoff_date)
                .delete()
            )

            self.db.commit()
            logger.info(f"Cleaned up {deleted_count} old audit logs")
            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up audit logs: {e}")
            self.db.rollback()
            return 0
