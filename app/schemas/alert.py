"""
Alert Schemas - Pydantic models for alert-related requests and responses
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class AlertTypeEnum(str, Enum):
    """Alert type enumeration"""
    HIGH_URGENCY = "high_urgency"
    SLA_BREACH = "sla_breach"
    SLA_WARNING = "sla_warning"
    ANOMALY = "anomaly"
    SPIKE = "spike"
    CUSTOM = "custom"


class AlertSeverityEnum(str, Enum):
    """Alert severity enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertBase(BaseModel):
    """Base alert schema"""
    alert_type: AlertTypeEnum
    severity: AlertSeverityEnum
    title: str = Field(..., min_length=1, max_length=500)
    message: Optional[str] = Field(None, max_length=2000)
    ticket_id: Optional[int] = None
    notification_channels: Optional[List[str]] = Field(default_factory=list)
    alert_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AlertCreate(AlertBase):
    """Schema for creating an alert"""
    pass


class AlertUpdate(BaseModel):
    """Schema for updating an alert"""
    is_resolved: Optional[bool] = None
    resolved_at: Optional[datetime] = None


class AlertResponse(AlertBase):
    """Schema for alert response"""
    id: int
    organization_id: int
    is_resolved: bool
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None
    is_notified: bool
    notified_at: Optional[datetime] = None
    triggered_at: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertAcknowledge(BaseModel):
    """Schema for acknowledging an alert"""
    notes: Optional[str] = None


class AlertCondition(BaseModel):
    """Schema for alert rule condition"""
    field: str = Field(..., min_length=1)
    operator: str = Field(..., min_length=1)
    value: Any
    logic: Optional[str] = Field(None, pattern="^(AND|OR)$")


class AlertAction(BaseModel):
    """Schema for alert rule action"""
    type: str
    config: Dict[str, Any] = Field(default_factory=dict)


class AlertRuleBase(BaseModel):
    """Base alert rule schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    alert_type: AlertTypeEnum
    severity: AlertSeverityEnum
    conditions: List[AlertCondition]
    actions: List[AlertAction] = Field(default_factory=list)
    enabled: bool = True
    notification_channels: List[str] = Field(default_factory=list)


class AlertRuleCreate(AlertRuleBase):
    """Schema for creating an alert rule"""
    pass


class AlertRuleUpdate(BaseModel):
    """Schema for updating an alert rule"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    alert_type: Optional[AlertTypeEnum] = None
    severity: Optional[AlertSeverityEnum] = None
    conditions: Optional[List[AlertCondition]] = None
    actions: Optional[List[AlertAction]] = None
    enabled: Optional[bool] = None
    notification_channels: Optional[List[str]] = None


class AlertRuleResponse(AlertRuleBase):
    """Schema for alert rule response"""
    id: int
    organization_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertRuleTestRequest(AlertRuleBase):
    """Schema for testing an alert rule"""
    pass


class AlertRuleTestResponse(BaseModel):
    """Schema for alert rule test results"""
    matches: int
    sample_tickets: List[Dict[str, Any]]


class QuietHours(BaseModel):
    """Schema for quiet hours configuration"""
    enabled: bool = False
    start_time: str = Field("22:00", pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    end_time: str = Field("08:00", pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")


class NotificationPreferences(BaseModel):
    """Schema for notification preferences"""
    email_enabled: bool = True
    slack_enabled: bool = False
    alert_types: List[AlertTypeEnum] = Field(default_factory=list)
    severities: List[AlertSeverityEnum] = Field(default_factory=list)
    quiet_hours: Optional[QuietHours] = Field(default_factory=QuietHours)


class NotificationPreferencesResponse(NotificationPreferences):
    """Schema for notification preferences response"""
    user_id: int
    organization_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaginatedAlerts(BaseModel):
    """Schema for paginated alerts response"""
    items: List[AlertResponse]
    total: int
    page: int
    size: int
    pages: int
