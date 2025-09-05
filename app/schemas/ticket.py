from typing import Optional, List, Dict, Any
from pydantic import BaseModel, validator, Field
from datetime import datetime
from app.models.ticket import TicketStatus, TicketPriority, TicketChannel


class TicketBase(BaseModel):
    """Base ticket schema"""
    title: str = Field(..., min_length=1, max_length=500, description="Ticket title")
    description: str = Field(..., min_length=1, description="Ticket description")
    customer_email: str = Field(..., description="Customer email address")
    customer_name: Optional[str] = Field(None, max_length=255, description="Customer name")
    customer_phone: Optional[str] = Field(None, max_length=50, description="Customer phone number")
    priority: TicketPriority = Field(TicketPriority.MEDIUM, description="Ticket priority")
    channel: TicketChannel = Field(..., description="Ticket channel/source")
    tags: Optional[List[str]] = Field(default_factory=list, description="Ticket tags")
    ticket_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

    @validator('customer_email')
    def validate_email(cls, v):
        if '@' not in v or '.' not in v.split('@')[-1]:
            raise ValueError('Invalid email format')
        return v.lower()

    @validator('title')
    def validate_title(cls, v):
        if not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()

    @validator('description')
    def validate_description(cls, v):
        if not v.strip():
            raise ValueError('Description cannot be empty')
        return v.strip()

    @validator('tags')
    def validate_tags(cls, v):
        if v:
            # Remove duplicates and empty tags
            return list(set(tag.strip().lower() for tag in v if tag.strip()))
        return []


class TicketCreate(TicketBase):
    """Schema for creating a new ticket"""
    integration_id: Optional[int] = Field(None, description="Integration ID if from external source")
    external_id: Optional[str] = Field(None, max_length=255, description="External system ticket ID")


class TicketUpdate(BaseModel):
    """Schema for updating an existing ticket"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, min_length=1)
    customer_name: Optional[str] = Field(None, max_length=255)
    customer_phone: Optional[str] = Field(None, max_length=50)
    priority: Optional[TicketPriority] = None
    status: Optional[TicketStatus] = None
    assigned_to: Optional[int] = None
    tags: Optional[List[str]] = None
    ticket_metadata: Optional[Dict[str, Any]] = None

    @validator('title')
    def validate_title(cls, v):
        if v is not None and not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip() if v else v

    @validator('description')
    def validate_description(cls, v):
        if v is not None and not v.strip():
            raise ValueError('Description cannot be empty')
        return v.strip() if v else v

    @validator('tags')
    def validate_tags(cls, v):
        if v is not None:
            return list(set(tag.strip().lower() for tag in v if tag.strip()))
        return v


class TicketAssign(BaseModel):
    """Schema for ticket assignment"""
    assigned_to: Optional[int] = Field(None, description="User ID to assign ticket to, null to unassign")


class TicketStatusUpdate(BaseModel):
    """Schema for updating ticket status"""
    status: TicketStatus = Field(..., description="New ticket status")


class TicketAIAnalysis(BaseModel):
    """Schema for AI analysis results"""
    sentiment_score: Optional[float] = Field(None, ge=-1, le=1, description="Sentiment score (-1 to 1)")
    category: Optional[str] = Field(None, max_length=100, description="AI-classified category")
    urgency_score: Optional[float] = Field(None, ge=0, le=1, description="Urgency score (0 to 1)")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="AI confidence score")
    needs_human_review: bool = Field(False, description="Whether ticket needs human review")
    tags: Optional[List[str]] = Field(default_factory=list, description="AI-generated tags")

    @validator('tags')
    def validate_tags(cls, v):
        if v:
            return list(set(tag.strip().lower() for tag in v if tag.strip()))
        return []


class TicketResponse(TicketBase):
    """Schema for ticket response"""
    id: int
    status: TicketStatus
    external_id: Optional[str] = None
    assigned_to: Optional[int] = None
    organization_id: int
    integration_id: Optional[int] = None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    
    # AI Analysis
    sentiment_score: Optional[float] = None
    category: Optional[str] = None
    urgency_score: Optional[float] = None
    confidence_score: Optional[float] = None
    
    # Processing flags
    is_processed: bool = False
    needs_human_review: bool = False
    
    # Relations (optional, loaded separately)
    assignee_name: Optional[str] = None
    integration_name: Optional[str] = None
    organization_name: Optional[str] = None

    class Config:
        from_attributes = True


class TicketSummary(BaseModel):
    """Schema for ticket summary (for lists)"""
    id: int
    title: str
    status: TicketStatus
    priority: TicketPriority
    customer_email: str
    customer_name: Optional[str] = None
    assigned_to: Optional[int] = None
    assignee_name: Optional[str] = None
    created_at: datetime
    last_activity_at: Optional[datetime] = None
    tags: List[str] = []
    sentiment_score: Optional[float] = None
    category: Optional[str] = None
    needs_human_review: bool = False

    class Config:
        from_attributes = True


class TicketFilter(BaseModel):
    """Schema for ticket filtering"""
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    channel: Optional[TicketChannel] = None
    assigned_to: Optional[int] = None
    unassigned: Optional[bool] = None
    customer_email: Optional[str] = None
    search: Optional[str] = Field(None, max_length=100, description="Search in title, description, customer info")
    tags: Optional[List[str]] = None
    needs_review: Optional[bool] = None
    is_processed: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None

    @validator('tags')
    def validate_tags(cls, v):
        if v:
            return [tag.strip().lower() for tag in v if tag.strip()]
        return v


class PaginatedTickets(BaseModel):
    """Schema for paginated ticket response"""
    items: List[TicketSummary]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


class TicketStats(BaseModel):
    """Schema for ticket statistics"""
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    closed_tickets: int
    pending_tickets: int
    unassigned_tickets: int
    high_priority_tickets: int
    urgent_tickets: int
    needs_review_tickets: int
    avg_resolution_time_hours: Optional[float] = None
    avg_first_response_time_hours: Optional[float] = None
