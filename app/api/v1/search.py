"""
Search API Endpoints - Advanced search, autocomplete, and saved searches
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import Optional, List
from datetime import datetime
import time
import math

from app.database.connection import get_db
from app.models.user import User
from app.models.ticket import Ticket
from app.models.saved_search import SavedSearch
from app.schemas.search import (
    AdvancedSearchRequest,
    SearchResultsResponse,
    TicketSearchResult,
    SearchResultHighlight,
    SearchSuggestionsResponse,
    SearchSuggestion,
    SavedSearchCreate,
    SavedSearchUpdate,
    SavedSearchResponse,
    SearchOperator,
)
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/search", tags=["search"])


def highlight_text(text: str, query: str) -> str:
    """Highlight search terms in text"""
    if not text or not query:
        return text

    # Simple highlighting - wrap matches in <mark> tags
    import re
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(lambda m: f'<mark>{m.group()}</mark>', text)


def apply_search_condition(query, condition, model_class=Ticket):
    """Apply a single search condition to a query"""
    field_name = condition.field
    operator = condition.operator
    value = condition.value

    # Get the field attribute
    if not hasattr(model_class, field_name):
        return query

    field = getattr(model_class, field_name)

    # Apply operator
    if operator == SearchOperator.EQUALS:
        return query.filter(field == value)
    elif operator == SearchOperator.NOT_EQUALS:
        return query.filter(field != value)
    elif operator == SearchOperator.CONTAINS:
        return query.filter(field.contains(value))
    elif operator == SearchOperator.NOT_CONTAINS:
        return query.filter(~field.contains(value))
    elif operator == SearchOperator.STARTS_WITH:
        return query.filter(field.startswith(value))
    elif operator == SearchOperator.ENDS_WITH:
        return query.filter(field.endswith(value))
    elif operator == SearchOperator.GREATER_THAN:
        return query.filter(field > value)
    elif operator == SearchOperator.LESS_THAN:
        return query.filter(field < value)
    elif operator == SearchOperator.GREATER_THAN_OR_EQUAL:
        return query.filter(field >= value)
    elif operator == SearchOperator.LESS_THAN_OR_EQUAL:
        return query.filter(field <= value)
    elif operator == SearchOperator.IN:
        return query.filter(field.in_(value if isinstance(value, list) else [value]))
    elif operator == SearchOperator.NOT_IN:
        return query.filter(~field.in_(value if isinstance(value, list) else [value]))
    elif operator == SearchOperator.IS_EMPTY:
        return query.filter(or_(field == None, field == ''))
    elif operator == SearchOperator.IS_NOT_EMPTY:
        return query.filter(and_(field != None, field != ''))

    return query


@router.post("/advanced", response_model=SearchResultsResponse)
async def advanced_search(
    search_request: AdvancedSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Advanced search with multiple conditions and full-text search
    """
    start_time = time.time()

    # Base query
    query = db.query(Ticket).filter(Ticket.organization_id == current_user.organization_id)

    # Apply full-text search if query provided
    if search_request.query:
        search_term = f"%{search_request.query}%"
        query = query.filter(
            or_(
                Ticket.title.ilike(search_term),
                Ticket.description.ilike(search_term),
                Ticket.customer_email.ilike(search_term),
                Ticket.customer_name.ilike(search_term),
                Ticket.category.ilike(search_term),
            )
        )

    # Apply advanced conditions
    and_conditions = []
    or_conditions = []

    for i, condition in enumerate(search_request.conditions):
        if i == 0 or condition.logic == "AND" or condition.logic is None:
            query = apply_search_condition(query, condition)
        else:  # OR logic
            # For OR conditions, we need to collect them and apply together
            or_conditions.append(condition)

    # Apply OR conditions if any
    if or_conditions:
        or_filters = []
        for condition in or_conditions:
            field = getattr(Ticket, condition.field)
            if condition.operator == SearchOperator.EQUALS:
                or_filters.append(field == condition.value)
            elif condition.operator == SearchOperator.CONTAINS:
                or_filters.append(field.contains(condition.value))
        if or_filters:
            query = query.filter(or_(*or_filters))

    # Get total count
    total = query.count()

    # Apply sorting
    sort_field = getattr(Ticket, search_request.sort_by, Ticket.created_at)
    if search_request.sort_order == "asc":
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())

    # Apply pagination
    query = query.offset((search_request.page - 1) * search_request.size).limit(search_request.size)

    # Execute query
    tickets = query.all()

    # Build results with highlights
    results = []
    for ticket in tickets:
        highlights = []

        # Highlight matching fields
        if search_request.query:
            if ticket.title and search_request.query.lower() in ticket.title.lower():
                highlights.append(SearchResultHighlight(
                    field="title",
                    value=ticket.title,
                    highlighted=highlight_text(ticket.title, search_request.query)
                ))
            if ticket.description and search_request.query.lower() in ticket.description.lower():
                highlights.append(SearchResultHighlight(
                    field="description",
                    value=ticket.description[:200],
                    highlighted=highlight_text(ticket.description[:200], search_request.query)
                ))

        results.append(TicketSearchResult(
            id=ticket.id,
            title=ticket.title,
            description=ticket.description,
            status=ticket.status,
            priority=ticket.priority,
            category=ticket.category,
            channel=ticket.channel,
            customer_email=ticket.customer_email,
            customer_name=ticket.customer_name,
            created_at=ticket.created_at,
            highlights=highlights,
            score=None  # Could implement relevance scoring
        ))

    # Calculate execution time
    took_ms = int((time.time() - start_time) * 1000)

    return SearchResultsResponse(
        items=results,
        total=total,
        page=search_request.page,
        size=search_request.size,
        pages=math.ceil(total / search_request.size) if total > 0 else 0,
        query=search_request.query,
        took_ms=took_ms
    )


@router.get("/suggestions", response_model=SearchSuggestionsResponse)
async def get_search_suggestions(
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get search suggestions and autocomplete based on query
    """
    suggestions = []
    search_term = f"%{q}%"

    # Get suggestions from ticket titles
    title_matches = db.query(Ticket.title).filter(
        Ticket.organization_id == current_user.organization_id,
        Ticket.title.ilike(search_term)
    ).distinct().limit(limit // 2).all()

    for (title,) in title_matches:
        suggestions.append(SearchSuggestion(
            text=title,
            field="title",
            type="title"
        ))

    # Get suggestions from categories
    category_matches = db.query(
        Ticket.category,
        func.count(Ticket.id).label('count')
    ).filter(
        Ticket.organization_id == current_user.organization_id,
        Ticket.category.ilike(search_term),
        Ticket.category != None
    ).group_by(Ticket.category).limit(limit // 2).all()

    for category, count in category_matches:
        suggestions.append(SearchSuggestion(
            text=category,
            field="category",
            count=count,
            type="category"
        ))

    # Get suggestions from customer names
    customer_matches = db.query(
        Ticket.customer_name
    ).filter(
        Ticket.organization_id == current_user.organization_id,
        Ticket.customer_name.ilike(search_term),
        Ticket.customer_name != None
    ).distinct().limit(limit // 3).all()

    for (customer_name,) in customer_matches:
        suggestions.append(SearchSuggestion(
            text=customer_name,
            field="customer_name",
            type="customer"
        ))

    return SearchSuggestionsResponse(
        suggestions=suggestions[:limit],
        query=q
    )


# Saved Searches Endpoints

@router.get("/saved", response_model=List[SavedSearchResponse])
async def get_saved_searches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all saved searches for current user
    """
    # Get user's own searches and shared searches
    saved_searches = db.query(SavedSearch).filter(
        or_(
            and_(
                SavedSearch.user_id == current_user.id,
                SavedSearch.organization_id == current_user.organization_id
            ),
            and_(
                SavedSearch.is_shared == True,
                SavedSearch.organization_id == current_user.organization_id
            )
        )
    ).order_by(SavedSearch.is_default.desc(), SavedSearch.last_used_at.desc()).all()

    return [SavedSearchResponse.from_orm(search) for search in saved_searches]


@router.post("/saved", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    search_data: SavedSearchCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new saved search
    """
    # If setting as default, unset other defaults
    if search_data.is_default:
        db.query(SavedSearch).filter(
            SavedSearch.user_id == current_user.id,
            SavedSearch.is_default == True
        ).update({"is_default": False})

    saved_search = SavedSearch(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        name=search_data.name,
        description=search_data.description,
        query=search_data.query,
        conditions=[c.dict() for c in search_data.conditions],
        is_default=search_data.is_default,
        is_shared=search_data.is_shared,
        use_count=0
    )

    db.add(saved_search)
    db.commit()
    db.refresh(saved_search)

    return SavedSearchResponse.from_orm(saved_search)


@router.put("/saved/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: int,
    search_data: SavedSearchUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a saved search
    """
    saved_search = db.query(SavedSearch).filter(
        SavedSearch.id == search_id,
        SavedSearch.user_id == current_user.id
    ).first()

    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )

    # Update fields
    update_data = search_data.dict(exclude_unset=True)

    # If setting as default, unset other defaults
    if update_data.get("is_default"):
        db.query(SavedSearch).filter(
            SavedSearch.user_id == current_user.id,
            SavedSearch.id != search_id,
            SavedSearch.is_default == True
        ).update({"is_default": False})

    # Convert conditions to dict
    if "conditions" in update_data and update_data["conditions"]:
        update_data["conditions"] = [c.dict() if hasattr(c, 'dict') else c for c in update_data["conditions"]]

    for key, value in update_data.items():
        setattr(saved_search, key, value)

    saved_search.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(saved_search)

    return SavedSearchResponse.from_orm(saved_search)


@router.delete("/saved/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a saved search
    """
    saved_search = db.query(SavedSearch).filter(
        SavedSearch.id == search_id,
        SavedSearch.user_id == current_user.id
    ).first()

    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )

    db.delete(saved_search)
    db.commit()


@router.post("/saved/{search_id}/use", response_model=SavedSearchResponse)
async def use_saved_search(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a saved search as used (updates last_used_at and use_count)
    """
    saved_search = db.query(SavedSearch).filter(
        SavedSearch.id == search_id,
        or_(
            SavedSearch.user_id == current_user.id,
            and_(
                SavedSearch.is_shared == True,
                SavedSearch.organization_id == current_user.organization_id
            )
        )
    ).first()

    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )

    saved_search.last_used_at = datetime.utcnow()
    saved_search.use_count += 1

    db.commit()
    db.refresh(saved_search)

    return SavedSearchResponse.from_orm(saved_search)
