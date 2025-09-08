"""
Zendesk-specific data models
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ZendeskTicketStatus(str, Enum):
    """Zendesk ticket status values"""
    NEW = "new"
    OPEN = "open"
    PENDING = "pending"
    HOLD = "hold"
    SOLVED = "solved"
    CLOSED = "closed"


class ZendeskTicketPriority(str, Enum):
    """Zendesk ticket priority values"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ZendeskUser(BaseModel):
    """Zendesk user model"""
    id: int
    name: str
    email: Optional[str] = None
    role: str = "end-user"
    created_at: datetime
    updated_at: datetime


class ZendeskTicket(BaseModel):
    """Zendesk ticket model"""
    id: int
    subject: str
    description: Optional[str] = None
    status: ZendeskTicketStatus
    priority: ZendeskTicketPriority
    requester_id: int
    submitter_id: int
    assignee_id: Optional[int] = None
    organization_id: Optional[int] = None
    group_id: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    url: str
    
    # Additional fields for our system
    external_id: str = Field(default="")
    channel: str = "zendesk"
    
    def __post_init__(self):
        if not self.external_id:
            self.external_id = f"zendesk_{self.id}"


class ZendeskComment(BaseModel):
    """Zendesk ticket comment model"""
    id: int
    ticket_id: int
    author_id: int
    body: str
    html_body: Optional[str] = None
    public: bool = True
    created_at: datetime
    attachments: List[Dict[str, Any]] = Field(default_factory=list)


class ZendeskWebhookEvent(BaseModel):
    """Zendesk webhook event model"""
    event: str  # e.g., "ticket.created", "ticket.updated"
    ticket_id: int
    timestamp: datetime
    changes: Optional[Dict[str, Any]] = None
    current: Optional[Dict[str, Any]] = None
    previous: Optional[Dict[str, Any]] = None


class ZendeskSyncResult(BaseModel):
    """Result of a Zendesk synchronization operation"""
    total_fetched: int = 0
    total_processed: int = 0
    total_created: int = 0
    total_updated: int = 0
    total_errors: int = 0
    errors: List[str] = Field(default_factory=list)
    start_time: datetime
    end_time: Optional[datetime] = None
    sync_type: str = "full"  # "full" or "incremental"
    
    @property
    def duration_seconds(self) -> float:
        """Calculate sync duration in seconds"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


class ZendeskAPIResponse(BaseModel):
    """Generic Zendesk API response wrapper"""
    data: Any
    count: Optional[int] = None
    next_page: Optional[str] = None
    previous_page: Optional[str] = None
    end_time: Optional[int] = None
    after_cursor: Optional[str] = None
    before_cursor: Optional[str] = None


# Mapping functions to convert Zendesk data to our internal format
def zendesk_ticket_to_internal(zendesk_ticket: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Zendesk ticket to internal ticket format"""
    
    # Map Zendesk priorities to our system
    priority_mapping = {
        "low": "low",
        "normal": "medium", 
        "high": "high",
        "urgent": "urgent"  # Changed from "critical" to "urgent" to match TicketPriority enum
    }
    
    # Map Zendesk statuses to our system
    status_mapping = {
        "new": "open",
        "open": "open", 
        "pending": "pending",
        "hold": "pending",
        "solved": "closed",
        "closed": "closed"
    }
    
    # Extract customer email with fallbacks
    customer_email = ""
    if zendesk_ticket.get("requester", {}).get("email"):
        customer_email = zendesk_ticket["requester"]["email"]
    elif zendesk_ticket.get("requester_email"):
        customer_email = zendesk_ticket["requester_email"]
    elif zendesk_ticket.get("submitter_email"):
        customer_email = zendesk_ticket["submitter_email"]
    else:
        # If no email found, use a default or generate one
        customer_email = f"unknown_user_{zendesk_ticket.get('id', 'unknown')}@zendesk.local"
    
    # Ensure we have a title and description
    title = zendesk_ticket.get("subject", "").strip()
    if not title:
        title = f"Zendesk Ticket #{zendesk_ticket.get('id', 'unknown')}"
    
    description = zendesk_ticket.get("description", "").strip()
    if not description:
        description = "No description provided"
    
    # Convert datetime strings to datetime objects
    created_at = None
    updated_at = None
    
    if zendesk_ticket.get("created_at"):
        try:
            created_at = datetime.fromisoformat(zendesk_ticket["created_at"].replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception as e:
            logger.warning(f"Could not parse created_at '{zendesk_ticket['created_at']}': {e}")
    
    if zendesk_ticket.get("updated_at"):
        try:
            updated_at = datetime.fromisoformat(zendesk_ticket["updated_at"].replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception as e:
            logger.warning(f"Could not parse updated_at '{zendesk_ticket['updated_at']}': {e}")
    
    return {
        "title": title,
        "description": description,
        "status": status_mapping.get(zendesk_ticket.get("status"), "open"),
        "priority": priority_mapping.get(zendesk_ticket.get("priority"), "medium"),
        "customer_email": customer_email,
        "external_id": f"zendesk_{zendesk_ticket.get('id')}",
        "external_url": zendesk_ticket.get("url", ""),
        "channel": "zendesk",
        "tags": zendesk_ticket.get("tags", []),
        "created_at": created_at,
        "updated_at": updated_at,
        "zendesk_data": {
            "id": zendesk_ticket.get("id"),
            "requester_id": zendesk_ticket.get("requester_id"),
            "submitter_id": zendesk_ticket.get("submitter_id"),
            "assignee_id": zendesk_ticket.get("assignee_id"),
            "organization_id": zendesk_ticket.get("organization_id"),
            "group_id": zendesk_ticket.get("group_id")
        }
    }


def internal_ticket_to_zendesk(internal_ticket: Dict[str, Any]) -> Dict[str, Any]:
    """Convert internal ticket format to Zendesk format"""
    
    # Reverse mapping
    priority_mapping = {
        "low": "low",
        "medium": "normal",
        "high": "high", 
        "urgent": "urgent"  # Fixed to match the TicketPriority enum
    }
    
    status_mapping = {
        "open": "open",
        "pending": "pending", 
        "closed": "solved"
    }
    
    zendesk_data = {
        "subject": internal_ticket.get("title", ""),
        "comment": {
            "body": internal_ticket.get("description", "")
        },
        "priority": priority_mapping.get(internal_ticket.get("priority"), "normal"),
        "status": status_mapping.get(internal_ticket.get("status"), "open"),
        "tags": internal_ticket.get("tags", [])
    }
    
    # Add requester email if available
    if internal_ticket.get("customer_email"):
        zendesk_data["requester"] = {
            "email": internal_ticket["customer_email"]
        }
    
    return zendesk_data