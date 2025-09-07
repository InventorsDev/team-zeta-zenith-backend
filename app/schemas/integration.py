from typing import Optional, Dict, Any, List
from pydantic import BaseModel, validator, Field, HttpUrl
from datetime import datetime
from app.models.integration import IntegrationType, IntegrationStatus


class IntegrationBase(BaseModel):
    """Base integration schema"""
    name: str = Field(..., min_length=1, max_length=255, description="Integration name")
    type: IntegrationType = Field(..., description="Integration type")
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Non-sensitive settings")
    sync_frequency: int = Field(300, ge=60, le=86400, description="Sync frequency in seconds (1 min to 24 hours)")
    sync_tickets: bool = Field(True, description="Enable ticket synchronization")
    receive_webhooks: bool = Field(True, description="Enable webhook reception")
    send_notifications: bool = Field(True, description="Enable sending notifications")
    rate_limit_per_hour: int = Field(1000, ge=1, le=10000, description="Rate limit per hour")

    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()


class IntegrationCreate(IntegrationBase):
    """Schema for creating a new integration"""
    config: Dict[str, Any] = Field(..., description="Integration configuration (will be encrypted)")
    webhook_url: Optional[str] = Field(None, description="Webhook URL")
    webhook_secret: Optional[str] = Field(None, description="Webhook secret")
    api_endpoint: Optional[str] = Field(None, description="API endpoint")

    @validator('config')
    def validate_config(cls, v, values):
        integration_type = values.get('type')
        if not v:
            raise ValueError('Configuration is required')
        
        # Validate required fields based on integration type
        if integration_type == IntegrationType.SLACK:
            required_fields = ['bot_token', 'signing_secret']
        elif integration_type == IntegrationType.ZENDESK:
            required_fields = ['subdomain', 'email', 'api_token']
        elif integration_type == IntegrationType.EMAIL:
            required_fields = ['smtp_server', 'smtp_port', 'email', 'password']
        else:
            required_fields = []
        
        missing_fields = [field for field in required_fields if not v.get(field)]
        if missing_fields:
            raise ValueError(f'Missing required configuration fields: {", ".join(missing_fields)}')
        
        return v

    @validator('webhook_url')
    def validate_webhook_url(cls, v):
        if v and not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('Webhook URL must be a valid HTTP/HTTPS URL')
        return v


class IntegrationUpdate(BaseModel):
    """Schema for updating an existing integration"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    config: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    api_endpoint: Optional[str] = None
    sync_frequency: Optional[int] = Field(None, ge=60, le=86400)
    sync_tickets: Optional[bool] = None
    receive_webhooks: Optional[bool] = None
    send_notifications: Optional[bool] = None
    rate_limit_per_hour: Optional[int] = Field(None, ge=1, le=10000)

    @validator('name')
    def validate_name(cls, v):
        if v is not None and not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip() if v else v

    @validator('webhook_url')
    def validate_webhook_url(cls, v):
        if v and not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('Webhook URL must be a valid HTTP/HTTPS URL')
        return v


class IntegrationStatusUpdate(BaseModel):
    """Schema for updating integration status"""
    status: IntegrationStatus = Field(..., description="New integration status")
    error_message: Optional[str] = Field(None, description="Error message if status is ERROR")


class IntegrationTest(BaseModel):
    """Schema for testing integration connection"""
    test_connection: bool = Field(True, description="Test the integration connection")


class IntegrationResponse(IntegrationBase):
    """Schema for integration response (excludes sensitive config)"""
    id: int
    status: IntegrationStatus
    organization_id: int
    webhook_url: Optional[str] = None
    webhook_token: Optional[str] = None
    api_endpoint: Optional[str] = None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    last_sync_at: Optional[datetime] = None
    rate_limit_reset_at: Optional[datetime] = None
    
    # Error information
    last_error: Optional[str] = None
    
    # Statistics
    current_hour_requests: int = 0
    total_tickets_synced: int = 0
    total_webhooks_received: int = 0
    
    # Configuration status (without sensitive data)
    has_config: bool = Field(False, description="Whether integration has configuration")
    config_fields: List[str] = Field(default_factory=list, description="List of configured fields")
    
    class Config:
        from_attributes = True


class IntegrationSummary(BaseModel):
    """Schema for integration summary (for lists)"""
    id: int
    name: str
    type: IntegrationType
    status: IntegrationStatus
    created_at: datetime
    last_sync_at: Optional[datetime] = None
    total_tickets_synced: int = 0
    has_config: bool = False
    sync_tickets: bool = True
    receive_webhooks: bool = True
    last_error: Optional[str] = None

    class Config:
        from_attributes = True


class IntegrationConfig(BaseModel):
    """Schema for integration configuration (with decrypted sensitive data)"""
    config: Dict[str, Any] = Field(..., description="Decrypted configuration data")
    
    class Config:
        # This schema is only used internally, never returned to API
        pass


class IntegrationConfigMask(BaseModel):
    """Schema for masked integration configuration (for API responses)"""
    config_fields: List[str] = Field(..., description="List of configuration field names")
    masked_config: Dict[str, str] = Field(..., description="Configuration with sensitive values masked")


class IntegrationFilter(BaseModel):
    """Schema for integration filtering"""
    type: Optional[IntegrationType] = None
    status: Optional[IntegrationStatus] = None
    active_only: Optional[bool] = None
    search: Optional[str] = Field(None, max_length=100, description="Search in integration name")
    has_errors: Optional[bool] = None
    sync_enabled: Optional[bool] = None


class PaginatedIntegrations(BaseModel):
    """Schema for paginated integration response"""
    items: List[IntegrationSummary]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


class IntegrationStats(BaseModel):
    """Schema for integration statistics"""
    total_integrations: int
    active_integrations: int
    error_integrations: int
    pending_integrations: int
    total_tickets_synced: int
    total_webhooks_received: int
    integrations_by_type: Dict[str, int]
    avg_sync_frequency_minutes: Optional[float] = None
    last_sync_times: Dict[str, Optional[datetime]]  # integration_name -> last_sync_at


class IntegrationSyncResult(BaseModel):
    """Schema for integration sync result"""
    integration_id: int
    success: bool
    tickets_synced: int = 0
    error_message: Optional[str] = None
    sync_time: datetime
    duration_seconds: float


class WebhookPayload(BaseModel):
    """Schema for webhook payload"""
    integration_id: int
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime
    signature: Optional[str] = None

    @validator('event_type')
    def validate_event_type(cls, v):
        allowed_events = [
            'ticket.created', 'ticket.updated', 'ticket.closed',
            'message.posted', 'user.created', 'integration.test'
        ]
        if v not in allowed_events:
            raise ValueError(f'Invalid event type. Allowed: {", ".join(allowed_events)}')
        return v
