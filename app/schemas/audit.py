"""
Audit Log Schemas
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class AuditLogBase(BaseModel):
    """Base audit log schema"""
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    status: str
    severity: str = "info"
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    endpoint: Optional[str] = None
    http_method: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class AuditLogResponse(AuditLogBase):
    """Audit log response schema"""
    id: int
    user_id: Optional[int] = None
    organization_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogQuery(BaseModel):
    """Query parameters for audit log search"""
    organization_id: Optional[int] = None
    user_id: Optional[int] = None
    action: Optional[str] = None
    status: Optional[str] = None
    severity: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


class AuditLogStats(BaseModel):
    """Audit log statistics"""
    total_logs: int
    failed_logins: int
    unauthorized_attempts: int
    critical_events: int
    recent_suspicious_activity: int
