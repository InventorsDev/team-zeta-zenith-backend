from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.services.ticket_service import TicketService
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.ticket import TicketStatus, TicketPriority, TicketChannel
from app.schemas.ticket import (
    TicketCreate, TicketUpdate, TicketResponse, TicketSummary,
    TicketFilter, PaginatedTickets, TicketStats, TicketAssign,
    TicketStatusUpdate, TicketAIAnalysis
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


def get_ticket_service(db: Session = Depends(get_db)) -> TicketService:
    """Dependency to get ticket service"""
    return TicketService(db)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_ticket(
    ticket_data: TicketCreate,
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
) -> Dict[str, Any]:
    """Create a new ticket with ML enhancement"""
    return ticket_service.create_ticket(ticket_data, current_user)


@router.get("/", response_model=PaginatedTickets)
async def get_tickets(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    # Filters
    status: Optional[TicketStatus] = Query(None, description="Filter by status"),
    priority: Optional[TicketPriority] = Query(None, description="Filter by priority"),
    channel: Optional[TicketChannel] = Query(None, description="Filter by channel"),
    assigned_to: Optional[int] = Query(None, description="Filter by assignee ID"),
    unassigned: Optional[bool] = Query(None, description="Filter unassigned tickets"),
    customer_email: Optional[str] = Query(None, description="Filter by customer email"),
    search: Optional[str] = Query(None, max_length=100, description="Search in title, description, customer info"),
    needs_review: Optional[bool] = Query(None, description="Filter tickets needing review"),
    is_processed: Optional[bool] = Query(None, description="Filter by processing status"),
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """Get paginated tickets with filtering and sorting"""
    # Create filter object
    filters = TicketFilter(
        status=status,
        priority=priority,
        channel=channel,
        assigned_to=assigned_to,
        unassigned=unassigned,
        customer_email=customer_email,
        search=search,
        needs_review=needs_review,
        is_processed=is_processed
    )
    
    return ticket_service.get_tickets(
        organization_id=current_user.organization_id,
        filters=filters,
        page=page,
        size=size,
        sort_by=sort_by,
        sort_order=sort_order
    )


@router.get("/stats", response_model=TicketStats)
async def get_ticket_stats(
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """Get ticket statistics for the current organization"""
    return ticket_service.get_ticket_stats(current_user.organization_id)


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """Get a specific ticket by ID"""
    return ticket_service.get_ticket(ticket_id, current_user.organization_id)


@router.put("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: int,
    ticket_data: TicketUpdate,
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """Update a ticket"""
    return ticket_service.update_ticket(
        ticket_id, current_user.organization_id, ticket_data
    )


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """Delete a ticket (marks as closed)"""
    ticket_service.delete_ticket(ticket_id, current_user.organization_id)


@router.patch("/{ticket_id}/status", response_model=TicketResponse)
async def update_ticket_status(
    ticket_id: int,
    status_data: TicketStatusUpdate,
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """Update ticket status"""
    ticket_update = TicketUpdate(status=status_data.status)
    return ticket_service.update_ticket(
        ticket_id, current_user.organization_id, ticket_update
    )


@router.patch("/{ticket_id}/assign", response_model=TicketResponse)
async def assign_ticket(
    ticket_id: int,
    assign_data: TicketAssign,
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """Assign or unassign a ticket"""
    if assign_data.assigned_to is None:
        return ticket_service.unassign_ticket(ticket_id, current_user.organization_id)
    else:
        return ticket_service.assign_ticket(
            ticket_id, current_user.organization_id, assign_data.assigned_to
        )


@router.patch("/{ticket_id}/first-response", response_model=TicketResponse)
async def mark_first_response(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """Mark first response timestamp for a ticket"""
    return ticket_service.mark_first_response(ticket_id, current_user.organization_id)


@router.patch("/{ticket_id}/ai-analysis", response_model=TicketResponse)
async def update_ai_analysis(
    ticket_id: int,
    analysis: TicketAIAnalysis,
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """Update AI analysis results for a ticket"""
    return ticket_service.update_ai_analysis(ticket_id, analysis)


# Additional endpoints for common operations

@router.get("/assigned/{user_id}", response_model=PaginatedTickets)
async def get_tickets_assigned_to_user(
    user_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """Get tickets assigned to a specific user"""
    filters = TicketFilter(assigned_to=user_id)
    return ticket_service.get_tickets(
        organization_id=current_user.organization_id,
        filters=filters,
        page=page,
        size=size
    )


@router.get("/unassigned", response_model=PaginatedTickets)
async def get_unassigned_tickets(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """Get unassigned tickets"""
    filters = TicketFilter(unassigned=True)
    return ticket_service.get_tickets(
        organization_id=current_user.organization_id,
        filters=filters,
        page=page,
        size=size
    )


@router.get("/priority/{priority}", response_model=PaginatedTickets)
async def get_tickets_by_priority(
    priority: TicketPriority,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """Get tickets by priority level"""
    filters = TicketFilter(priority=priority)
    return ticket_service.get_tickets(
        organization_id=current_user.organization_id,
        filters=filters,
        page=page,
        size=size
    )


@router.get("/status/{status}", response_model=PaginatedTickets)
async def get_tickets_by_status(
    status: TicketStatus,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """Get tickets by status"""
    filters = TicketFilter(status=status)
    return ticket_service.get_tickets(
        organization_id=current_user.organization_id,
        filters=filters,
        page=page,
        size=size
    )


@router.get("/needs-review", response_model=PaginatedTickets)
async def get_tickets_needing_review(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """Get tickets that need human review"""
    filters = TicketFilter(needs_review=True)
    return ticket_service.get_tickets(
        organization_id=current_user.organization_id,
        filters=filters,
        page=page,
        size=size
    )


# ML-powered business endpoints
@router.get("/{ticket_id}/analysis")
async def get_ticket_analysis(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
) -> Dict[str, Any]:
    """Get ML analysis for a specific ticket"""
    return ticket_service.analyze_ticket_with_ml(ticket_id, current_user.organization_id)


@router.get("/{ticket_id}/similar")
async def get_similar_tickets(
    ticket_id: int,
    threshold: float = Query(0.7, ge=0.0, le=1.0, description="Similarity threshold"),
    current_user: User = Depends(get_current_user),
    ticket_service: TicketService = Depends(get_ticket_service)
) -> List[Dict[str, Any]]:
    """Find tickets similar to this one"""
    return ticket_service.find_similar_tickets(ticket_id, current_user.organization_id, threshold)


# Moved to /api/v1/analytics/overview for better organization
