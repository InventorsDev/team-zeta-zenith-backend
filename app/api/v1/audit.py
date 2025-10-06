"""
Audit Log API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app.database.connection import get_db
from app.models.user import User, UserRole
from app.services.audit_service import AuditService
from app.schemas.audit import AuditLogResponse, AuditLogStats
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    action: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    user_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get audit logs for the current organization

    Only admin users can access audit logs
    """
    # Check if user is admin
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can access audit logs"
        )

    audit_service = AuditService(db)

    logs = audit_service.get_logs(
        organization_id=current_user.organization_id,
        user_id=user_id,
        action=action,
        status=status,
        severity=severity,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset
    )

    return [AuditLogResponse.from_orm(log) for log in logs]


@router.get("/logs/failed-logins", response_model=List[AuditLogResponse])
async def get_failed_login_attempts(
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent failed login attempts

    Only admin users can access
    """
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can access audit logs"
        )

    audit_service = AuditService(db)
    logs = audit_service.get_failed_login_attempts(hours=hours)

    return [AuditLogResponse.from_orm(log) for log in logs]


@router.get("/logs/suspicious", response_model=List[AuditLogResponse])
async def get_suspicious_activity(
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get potentially suspicious activity

    Only admin users can access
    """
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can access audit logs"
        )

    audit_service = AuditService(db)
    logs = audit_service.get_suspicious_activity(
        organization_id=current_user.organization_id,
        hours=hours
    )

    return [AuditLogResponse.from_orm(log) for log in logs]


@router.get("/stats", response_model=AuditLogStats)
async def get_audit_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get audit log statistics for the organization

    Only admin users can access
    """
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can access audit logs"
        )

    audit_service = AuditService(db)

    # Get various counts
    total_logs = db.query(AuditService.db.query(AuditLog).filter(
        AuditLog.organization_id == current_user.organization_id
    ).count())

    failed_logins = len(audit_service.get_failed_login_attempts(hours=24))
    suspicious = len(audit_service.get_suspicious_activity(
        organization_id=current_user.organization_id,
        hours=24
    ))

    from app.models.audit_log import AuditLog
    unauthorized_attempts = db.query(AuditLog).filter(
        AuditLog.organization_id == current_user.organization_id,
        AuditLog.status == "unauthorized"
    ).count()

    critical_events = db.query(AuditLog).filter(
        AuditLog.organization_id == current_user.organization_id,
        AuditLog.severity == "critical"
    ).count()

    return AuditLogStats(
        total_logs=total_logs,
        failed_logins=failed_logins,
        unauthorized_attempts=unauthorized_attempts,
        critical_events=critical_events,
        recent_suspicious_activity=suspicious
    )
