from typing import List, Optional, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.user import User
from app.database.repositories.ticket_repository import TicketRepository
from app.database.repositories.user_repository import UserRepository
from app.schemas.ticket import (
    TicketCreate, TicketUpdate, TicketResponse, TicketSummary,
    TicketFilter, PaginatedTickets, TicketStats, TicketAIAnalysis
)
from app.services.ml_service import ml_service


class TicketService:
    """Service layer for ticket operations with business logic"""

    def __init__(self, db: Session):
        self.db = db
        self.ticket_repo = TicketRepository(db)
        self.user_repo = UserRepository(db)

    def create_ticket(self, ticket_data: TicketCreate, current_user: User) -> Dict[str, Any]:
        """Create a new ticket with validation and ML enhancement"""
        # Ensure user belongs to an organization
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must belong to an organization to create tickets"
            )
        
        # Convert Pydantic model to dict
        ticket_dict = ticket_data.dict()
        
        # Set organization_id from current user
        ticket_dict["organization_id"] = current_user.organization_id
        
        # Get ML analysis for this ticket (but don't store in DB)
        ml_analysis = ml_service.enhance_ticket_data(ticket_dict)
        
        # Separate ML fields from database fields
        db_fields = {k: v for k, v in ticket_dict.items() if not k.startswith('ml_')}
        ml_fields = {k: v for k, v in ml_analysis.items() if k.startswith('ml_')}
        
        # Create ticket with only database fields
        ticket = self.ticket_repo.create_ticket(db_fields)
        
        # Convert to response and add ML fields
        ticket_response = self._to_ticket_response(ticket)
        
        # Convert response to dict and add ML fields
        response_dict = ticket_response.dict()
        response_dict.update(ml_fields)
        
        return response_dict

    def get_ticket(self, ticket_id: int, organization_id: int) -> TicketResponse:
        """Get a single ticket by ID with organization check"""
        ticket = self.ticket_repo.get(ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        if ticket.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this ticket"
            )
        
        return self._to_ticket_response(ticket)

    def update_ticket(self, ticket_id: int, organization_id: int, ticket_data: TicketUpdate) -> TicketResponse:
        """Update an existing ticket"""
        ticket = self.ticket_repo.get(ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        if ticket.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this ticket"
            )
        
        # Convert Pydantic model to dict, excluding None values
        update_dict = ticket_data.dict(exclude_unset=True)
        if not update_dict:
            return self._to_ticket_response(ticket)
        
        # Handle status change with timestamps
        if "status" in update_dict:
            ticket = self.ticket_repo.update_ticket_status(ticket, update_dict["status"])
            del update_dict["status"]
        
        # Handle assignment change
        if "assigned_to" in update_dict:
            if update_dict["assigned_to"] is None:
                ticket = self.ticket_repo.unassign_ticket(ticket)
            else:
                # Verify assignee exists and belongs to same organization
                assignee = self.user_repo.get(update_dict["assigned_to"])
                if not assignee or assignee.organization_id != organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid assignee"
                    )
                ticket = self.ticket_repo.assign_ticket(ticket, update_dict["assigned_to"])
            del update_dict["assigned_to"]
        
        # Apply remaining updates
        if update_dict:
            update_dict["last_activity_at"] = datetime.utcnow()
            ticket = self.ticket_repo.update(ticket, update_dict)
        
        return self._to_ticket_response(ticket)

    def delete_ticket(self, ticket_id: int, organization_id: int) -> bool:
        """Delete a ticket (soft delete by setting status to closed)"""
        ticket = self.ticket_repo.get(ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        if ticket.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this ticket"
            )
        
        # Instead of hard delete, mark as closed
        self.ticket_repo.update_ticket_status(ticket, TicketStatus.CLOSED)
        return True

    def get_tickets(
        self,
        organization_id: int,
        filters: TicketFilter = None,
        page: int = 1,
        size: int = 50,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> PaginatedTickets:
        """Get paginated tickets with filtering"""
        # Validate pagination parameters
        if page < 1:
            page = 1
        if size < 1 or size > 100:
            size = 50
        
        skip = (page - 1) * size
        
        # Convert filters to dict
        filter_dict = filters.dict(exclude_unset=True) if filters else {}
        
        # Get tickets and count
        tickets = self.ticket_repo.get_filtered_tickets(
            organization_id=organization_id,
            filters=filter_dict,
            skip=skip,
            limit=size,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        total = self.ticket_repo.count_tickets(organization_id, filter_dict)
        
        # Convert to summary format
        ticket_summaries = [self._to_ticket_summary(ticket) for ticket in tickets]
        
        # Calculate pagination info
        pages = (total + size - 1) // size
        has_next = page < pages
        has_prev = page > 1
        
        return PaginatedTickets(
            items=ticket_summaries,
            total=total,
            page=page,
            size=size,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )

    def assign_ticket(self, ticket_id: int, organization_id: int, user_id: int) -> TicketResponse:
        """Assign ticket to a user"""
        ticket = self.ticket_repo.get(ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        if ticket.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this ticket"
            )
        
        # Verify assignee
        assignee = self.user_repo.get(user_id)
        if not assignee or assignee.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid assignee"
            )
        
        ticket = self.ticket_repo.assign_ticket(ticket, user_id)
        return self._to_ticket_response(ticket)

    def unassign_ticket(self, ticket_id: int, organization_id: int) -> TicketResponse:
        """Unassign ticket from current user"""
        ticket = self.ticket_repo.get(ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        if ticket.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this ticket"
            )
        
        ticket = self.ticket_repo.unassign_ticket(ticket)
        return self._to_ticket_response(ticket)

    def update_ai_analysis(self, ticket_id: int, analysis: TicketAIAnalysis) -> TicketResponse:
        """Update AI analysis for a ticket"""
        ticket = self.ticket_repo.get(ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        analysis_dict = analysis.dict(exclude_unset=True)
        ticket = self.ticket_repo.update_ai_analysis(ticket, analysis_dict)
        
        return self._to_ticket_response(ticket)
    
    def analyze_ticket_with_ml(self, ticket_id: int, organization_id: int) -> Dict[str, Any]:
        """Perform ML analysis on a specific ticket"""
        ticket = self.ticket_repo.get(ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        if ticket.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this ticket"
            )
        
        # Get ticket content for analysis
        text = getattr(ticket, 'content', getattr(ticket, 'description', ''))
        if not text:
            return {"error": "No content available for analysis"}
        
        # Perform ML analysis
        classification = ml_service.classify_ticket(text)
        sentiment = ml_service.analyze_sentiment(text)
        similar_tickets = ml_service.find_similar_tickets(text, top_k=5)
        duplicates = ml_service.detect_duplicates(text, threshold=0.8)
        
        return {
            "ticket_id": ticket_id,
            "classification": classification,
            "sentiment": sentiment,
            "similar_tickets": similar_tickets,
            "potential_duplicates": duplicates,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
    
    def get_ml_analytics(self, organization_id: int) -> Dict[str, Any]:
        """Get ML-powered analytics for organization tickets"""
        # Get all tickets for the organization
        all_tickets = self.ticket_repo.get_by_organization(organization_id, skip=0, limit=10000)
        
        # Convert to format expected by ML service
        ticket_data = []
        for ticket in all_tickets:
            content = getattr(ticket, 'content', getattr(ticket, 'description', ''))
            if content:
                ticket_data.append({
                    'content': content,
                    'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
                    'status': ticket.status.value if ticket.status else None,
                    'priority': ticket.priority.value if ticket.priority else None
                })
        
        # Get ML analytics
        ml_analytics = ml_service.get_ticket_analytics(ticket_data)
        
        # Add trend analysis
        trends = ml_service.analyze_ticket_trends(ticket_data, days=30)
        ml_analytics['trends'] = trends
        
        return ml_analytics
    
    def find_similar_tickets(self, ticket_id: int, organization_id: int, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Find tickets similar to the given ticket"""
        ticket = self.ticket_repo.get(ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        if ticket.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this ticket"
            )
        
        text = getattr(ticket, 'content', getattr(ticket, 'description', ''))
        if not text:
            return []
        
        return ml_service.find_similar_tickets(text, threshold=threshold, top_k=10)

    def get_ticket_stats(self, organization_id: int) -> TicketStats:
        """Get ticket statistics for organization"""
        # Get all tickets for the organization
        all_tickets = self.ticket_repo.get_by_organization(organization_id, skip=0, limit=10000)
        
        # Calculate statistics
        total = len(all_tickets)
        open_count = sum(1 for t in all_tickets if t.status == TicketStatus.OPEN)
        in_progress_count = sum(1 for t in all_tickets if t.status == TicketStatus.IN_PROGRESS)
        resolved_count = sum(1 for t in all_tickets if t.status == TicketStatus.RESOLVED)
        closed_count = sum(1 for t in all_tickets if t.status == TicketStatus.CLOSED)
        pending_count = sum(1 for t in all_tickets if t.status == TicketStatus.PENDING)
        unassigned_count = sum(1 for t in all_tickets if t.assigned_to is None)
        high_priority_count = sum(1 for t in all_tickets if t.priority == TicketPriority.HIGH)
        urgent_count = sum(1 for t in all_tickets if t.priority == TicketPriority.URGENT)
        needs_review_count = sum(1 for t in all_tickets if t.needs_human_review)
        
        # Calculate average resolution time
        resolved_tickets = [t for t in all_tickets if t.resolved_at and t.created_at]
        avg_resolution_time = None
        if resolved_tickets:
            resolution_times = [(t.resolved_at - t.created_at).total_seconds() / 3600 for t in resolved_tickets]
            avg_resolution_time = sum(resolution_times) / len(resolution_times)
        
        # Calculate average first response time
        responded_tickets = [t for t in all_tickets if t.first_response_at and t.created_at]
        avg_first_response_time = None
        if responded_tickets:
            response_times = [(t.first_response_at - t.created_at).total_seconds() / 3600 for t in responded_tickets]
            avg_first_response_time = sum(response_times) / len(response_times)
        
        return TicketStats(
            total_tickets=total,
            open_tickets=open_count,
            in_progress_tickets=in_progress_count,
            resolved_tickets=resolved_count,
            closed_tickets=closed_count,
            pending_tickets=pending_count,
            unassigned_tickets=unassigned_count,
            high_priority_tickets=high_priority_count,
            urgent_tickets=urgent_count,
            needs_review_tickets=needs_review_count,
            avg_resolution_time_hours=avg_resolution_time,
            avg_first_response_time_hours=avg_first_response_time
        )

    def mark_first_response(self, ticket_id: int, organization_id: int) -> TicketResponse:
        """Mark first response timestamp for a ticket"""
        ticket = self.ticket_repo.get(ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        if ticket.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this ticket"
            )
        
        ticket = self.ticket_repo.add_first_response(ticket)
        return self._to_ticket_response(ticket)

    def _to_ticket_response(self, ticket: Ticket) -> TicketResponse:
        """Convert ticket model to response schema"""
        # Get assignee name if assigned
        assignee_name = None
        if ticket.assigned_to:
            assignee = self.user_repo.get(ticket.assigned_to)
            if assignee:
                assignee_name = assignee.full_name
        
        # Convert to response format
        response_data = {
            **ticket.__dict__,
            "assignee_name": assignee_name
        }
        
        return TicketResponse.from_orm(ticket)

    def _to_ticket_summary(self, ticket: Ticket) -> TicketSummary:
        """Convert ticket model to summary schema"""
        # Get assignee name if assigned
        assignee_name = None
        if ticket.assigned_to:
            assignee = self.user_repo.get(ticket.assigned_to)
            if assignee:
                assignee_name = assignee.full_name
        
        return TicketSummary(
            id=ticket.id,
            title=ticket.title,
            status=ticket.status,
            priority=ticket.priority,
            customer_email=ticket.customer_email,
            customer_name=ticket.customer_name,
            assigned_to=ticket.assigned_to,
            assignee_name=assignee_name,
            created_at=ticket.created_at,
            last_activity_at=ticket.last_activity_at,
            tags=ticket.tags or [],
            sentiment_score=ticket.sentiment_score,
            category=ticket.category,
            needs_human_review=ticket.needs_human_review
        )
