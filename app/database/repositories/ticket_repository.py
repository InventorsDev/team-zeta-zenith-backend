from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from datetime import datetime
from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketChannel
from .base import BaseRepository


class TicketRepository(BaseRepository[Ticket]):
    """Repository for Ticket model with advanced querying capabilities"""

    def __init__(self, db: Session):
        super().__init__(Ticket, db)

    def get_by_organization(self, organization_id: int, skip: int = 0, limit: int = 100) -> List[Ticket]:
        """Get tickets filtered by organization"""
        return (
            self.db.query(Ticket)
            .filter(Ticket.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_status(self, organization_id: int, status: TicketStatus, skip: int = 0, limit: int = 100) -> List[Ticket]:
        """Get tickets by status within organization"""
        return (
            self.db.query(Ticket)
            .filter(and_(Ticket.organization_id == organization_id, Ticket.status == status))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_priority(self, organization_id: int, priority: TicketPriority, skip: int = 0, limit: int = 100) -> List[Ticket]:
        """Get tickets by priority within organization"""
        return (
            self.db.query(Ticket)
            .filter(and_(Ticket.organization_id == organization_id, Ticket.priority == priority))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_assignee(self, organization_id: int, user_id: int, skip: int = 0, limit: int = 100) -> List[Ticket]:
        """Get tickets assigned to specific user within organization"""
        return (
            self.db.query(Ticket)
            .filter(and_(Ticket.organization_id == organization_id, Ticket.assigned_to == user_id))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_unassigned(self, organization_id: int, skip: int = 0, limit: int = 100) -> List[Ticket]:
        """Get unassigned tickets within organization"""
        return (
            self.db.query(Ticket)
            .filter(and_(Ticket.organization_id == organization_id, Ticket.assigned_to.is_(None)))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def search_tickets(self, organization_id: int, search_term: str, skip: int = 0, limit: int = 100) -> List[Ticket]:
        """Search tickets by title, description, or customer info within organization"""
        search_filter = or_(
            Ticket.title.ilike(f"%{search_term}%"),
            Ticket.description.ilike(f"%{search_term}%"),
            Ticket.customer_email.ilike(f"%{search_term}%"),
            Ticket.customer_name.ilike(f"%{search_term}%")
        )
        return (
            self.db.query(Ticket)
            .filter(and_(Ticket.organization_id == organization_id, search_filter))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_filtered_tickets(
        self,
        organization_id: int,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> List[Ticket]:
        """Get tickets with advanced filtering and sorting"""
        query = self.db.query(Ticket).filter(Ticket.organization_id == organization_id)
        
        # Apply filters
        if filters.get("status"):
            query = query.filter(Ticket.status == filters["status"])
        
        if filters.get("priority"):
            query = query.filter(Ticket.priority == filters["priority"])
        
        if filters.get("channel"):
            query = query.filter(Ticket.channel == filters["channel"])
        
        if filters.get("assigned_to"):
            query = query.filter(Ticket.assigned_to == filters["assigned_to"])
        
        if filters.get("unassigned"):
            query = query.filter(Ticket.assigned_to.is_(None))
        
        if filters.get("customer_email"):
            query = query.filter(Ticket.customer_email.ilike(f"%{filters['customer_email']}%"))
        
        if filters.get("search"):
            search_term = filters["search"]
            search_filter = or_(
                Ticket.title.ilike(f"%{search_term}%"),
                Ticket.description.ilike(f"%{search_term}%"),
                Ticket.customer_email.ilike(f"%{search_term}%"),
                Ticket.customer_name.ilike(f"%{search_term}%")
            )
            query = query.filter(search_filter)
        
        if filters.get("tags"):
            # Search for tickets containing any of the specified tags
            tags = filters["tags"] if isinstance(filters["tags"], list) else [filters["tags"]]
            for tag in tags:
                query = query.filter(Ticket.tags.contains([tag]))
        
        if filters.get("needs_review"):
            query = query.filter(Ticket.needs_human_review == filters["needs_review"])
        
        if filters.get("is_processed"):
            query = query.filter(Ticket.is_processed == filters["is_processed"])
        
        # Apply sorting
        if hasattr(Ticket, sort_by):
            sort_column = getattr(Ticket, sort_by)
            if sort_order.lower() == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
        
        return query.offset(skip).limit(limit).all()

    def count_tickets(self, organization_id: int, filters: Dict[str, Any] = None) -> int:
        """Count tickets with optional filters"""
        query = self.db.query(Ticket).filter(Ticket.organization_id == organization_id)
        
        if filters:
            # Apply same filters as get_filtered_tickets but without pagination
            if filters.get("status"):
                query = query.filter(Ticket.status == filters["status"])
            
            if filters.get("priority"):
                query = query.filter(Ticket.priority == filters["priority"])
            
            if filters.get("channel"):
                query = query.filter(Ticket.channel == filters["channel"])
            
            if filters.get("assigned_to"):
                query = query.filter(Ticket.assigned_to == filters["assigned_to"])
            
            if filters.get("unassigned"):
                query = query.filter(Ticket.assigned_to.is_(None))
            
            if filters.get("customer_email"):
                query = query.filter(Ticket.customer_email.ilike(f"%{filters['customer_email']}%"))
            
            if filters.get("search"):
                search_term = filters["search"]
                search_filter = or_(
                    Ticket.title.ilike(f"%{search_term}%"),
                    Ticket.description.ilike(f"%{search_term}%"),
                    Ticket.customer_email.ilike(f"%{search_term}%"),
                    Ticket.customer_name.ilike(f"%{search_term}%")
                )
                query = query.filter(search_filter)
        
        return query.count()

    def create_ticket(self, ticket_data: Dict[str, Any]) -> Ticket:
        """Create a new ticket with timestamps"""
        ticket_data["last_activity_at"] = datetime.utcnow()
        return self.create(ticket_data)

    def update_ticket_status(self, ticket: Ticket, status: TicketStatus) -> Ticket:
        """Update ticket status with appropriate timestamps"""
        update_data = {
            "status": status,
            "last_activity_at": datetime.utcnow()
        }
        
        if status == TicketStatus.RESOLVED:
            update_data["resolved_at"] = datetime.utcnow()
        elif status == TicketStatus.CLOSED:
            update_data["closed_at"] = datetime.utcnow()
            if not ticket.resolved_at:
                update_data["resolved_at"] = datetime.utcnow()
        
        return self.update(ticket, update_data)

    def assign_ticket(self, ticket: Ticket, user_id: int) -> Ticket:
        """Assign ticket to a user"""
        return self.update(ticket, {
            "assigned_to": user_id,
            "last_activity_at": datetime.utcnow()
        })

    def unassign_ticket(self, ticket: Ticket) -> Ticket:
        """Unassign ticket from current user"""
        return self.update(ticket, {
            "assigned_to": None,
            "last_activity_at": datetime.utcnow()
        })

    def add_first_response(self, ticket: Ticket) -> Ticket:
        """Mark first response timestamp"""
        if not ticket.first_response_at:
            return self.update(ticket, {
                "first_response_at": datetime.utcnow(),
                "last_activity_at": datetime.utcnow()
            })
        return ticket

    def update_ai_analysis(self, ticket: Ticket, analysis: Dict[str, Any]) -> Ticket:
        """Update AI analysis results"""
        update_data = {
            "sentiment_score": analysis.get("sentiment_score"),
            "category": analysis.get("category"),
            "urgency_score": analysis.get("urgency_score"),
            "confidence_score": analysis.get("confidence_score"),
            "is_processed": True,
            "needs_human_review": analysis.get("needs_human_review", False),
            "last_activity_at": datetime.utcnow()
        }
        
        # Update tags if provided
        if analysis.get("tags"):
            update_data["tags"] = analysis["tags"]
        
        return self.update(ticket, update_data)
