"""
Alerts API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional, List
from datetime import datetime
import math

from app.database.connection import get_db
from app.models.user import User
from app.models.alert import Alert
from app.models.ticket import Ticket
from app.schemas.alert import (
    AlertResponse,
    AlertCreate,
    AlertAcknowledge,
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertRuleResponse,
    AlertRuleTestRequest,
    AlertRuleTestResponse,
    NotificationPreferences,
    NotificationPreferencesResponse,
    PaginatedAlerts,
    AlertSeverityEnum,
    AlertTypeEnum,
)
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


# Alert Management Endpoints

@router.get("", response_model=PaginatedAlerts)
async def get_alerts(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    is_resolved: Optional[bool] = None,
    severity: Optional[AlertSeverityEnum] = None,
    alert_type: Optional[AlertTypeEnum] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of alerts for the current organization
    """
    query = db.query(Alert).filter(Alert.organization_id == current_user.organization_id)

    # Apply filters
    if is_resolved is not None:
        query = query.filter(Alert.is_resolved == is_resolved)

    if severity:
        query = query.filter(Alert.severity == severity.value)

    if alert_type:
        query = query.filter(Alert.alert_type == alert_type.value)

    # Get total count
    total = query.count()

    # Apply pagination
    query = query.order_by(Alert.triggered_at.desc())
    query = query.offset((page - 1) * size).limit(size)

    alerts = query.all()

    return PaginatedAlerts(
        items=[AlertResponse.from_orm(alert) for alert in alerts],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0
    )


# Alert Rules Endpoints (must be before /{alert_id} to avoid route conflicts)

@router.get("/rules", response_model=List[AlertRuleResponse])
async def get_alert_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all alert rules for the current organization
    Note: Alert rules are stored in alert_metadata for now
    This is a placeholder implementation
    """
    # TODO: Implement proper alert rules storage table
    return []


@router.post("/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    rule_data: AlertRuleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new alert rule
    """
    # TODO: Implement proper alert rules storage
    # For now, return a mock response
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Alert rules creation not yet implemented. Rules will be added in a future update."
    )


@router.post("/rules/test", response_model=AlertRuleTestResponse)
async def test_alert_rule(
    rule_data: AlertRuleTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test an alert rule against existing tickets
    """
    # Build query based on conditions
    query = db.query(Ticket).filter(Ticket.organization_id == current_user.organization_id)

    # Apply conditions
    for condition in rule_data.conditions:
        field = condition.field
        operator = condition.operator
        value = condition.value

        # Map field names to ticket attributes
        if field == "priority":
            if operator == "eq":
                query = query.filter(Ticket.priority == value)
            elif operator == "ne":
                query = query.filter(Ticket.priority != value)
        elif field == "status":
            if operator == "eq":
                query = query.filter(Ticket.status == value)
            elif operator == "ne":
                query = query.filter(Ticket.status != value)
        elif field == "sentiment_score":
            if operator == "gt":
                query = query.filter(Ticket.sentiment_score > float(value))
            elif operator == "lt":
                query = query.filter(Ticket.sentiment_score < float(value))
            elif operator == "gte":
                query = query.filter(Ticket.sentiment_score >= float(value))
            elif operator == "lte":
                query = query.filter(Ticket.sentiment_score <= float(value))
        elif field == "category":
            if operator == "eq":
                query = query.filter(Ticket.category == value)
            elif operator == "contains":
                query = query.filter(Ticket.category.contains(value))
        elif field == "channel":
            if operator == "eq":
                query = query.filter(Ticket.channel == value)

    # Get total matches
    total_matches = query.count()

    # Get sample tickets (max 10)
    sample_tickets = query.limit(10).all()

    return AlertRuleTestResponse(
        matches=total_matches,
        sample_tickets=[
            {
                "id": ticket.id,
                "title": ticket.title,
                "priority": ticket.priority,
                "status": ticket.status,
                "category": ticket.category,
            }
            for ticket in sample_tickets
        ]
    )


@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific alert rule by ID
    """
    # TODO: Implement proper alert rules storage
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Alert rule not found"
    )


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: int,
    rule_data: AlertRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update an existing alert rule
    """
    # TODO: Implement proper alert rules storage
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Alert rule not found"
    )


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete an alert rule
    """
    # TODO: Implement proper alert rules storage
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Alert rule not found"
    )


# Notification Preferences Endpoints (must be before /{alert_id} to avoid route conflicts)

@router.get("/preferences", response_model=NotificationPreferences)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get notification preferences for the current user
    """
    # TODO: Implement proper notification preferences storage
    # For now, return default preferences
    return NotificationPreferences(
        email_enabled=True,
        slack_enabled=False,
        alert_types=[],
        severities=[],
    )


@router.put("/preferences", response_model=NotificationPreferences)
async def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update notification preferences for the current user
    """
    # TODO: Implement proper notification preferences storage
    # For now, just return the input
    return preferences


# Alert instance endpoints (parameterized routes must come AFTER specific routes)

@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific alert by ID
    """
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.organization_id == current_user.organization_id
    ).first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    return AlertResponse.from_orm(alert)


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    alert_data: AlertCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new alert
    """
    alert = Alert(
        organization_id=current_user.organization_id,
        alert_type=alert_data.alert_type.value,
        severity=alert_data.severity.value,
        title=alert_data.title,
        message=alert_data.message,
        ticket_id=alert_data.ticket_id,
        notification_channels=alert_data.notification_channels,
        alert_metadata=alert_data.alert_metadata,
        triggered_at=datetime.utcnow()
    )

    db.add(alert)
    db.commit()
    db.refresh(alert)

    return AlertResponse.from_orm(alert)


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: int,
    ack_data: AlertAcknowledge,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Acknowledge an alert
    """
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.organization_id == current_user.organization_id
    ).first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    # Store acknowledgment in metadata
    if not alert.alert_metadata:
        alert.alert_metadata = {}

    alert.alert_metadata["acknowledged_at"] = datetime.utcnow().isoformat()
    alert.alert_metadata["acknowledged_by"] = current_user.id
    if ack_data.notes:
        alert.alert_metadata["acknowledgment_notes"] = ack_data.notes

    db.commit()
    db.refresh(alert)

    return AlertResponse.from_orm(alert)


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Resolve an alert
    """
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.organization_id == current_user.organization_id
    ).first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by = current_user.id

    db.commit()
    db.refresh(alert)

    return AlertResponse.from_orm(alert)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete an alert
    """
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.organization_id == current_user.organization_id
    ).first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    db.delete(alert)
    db.commit()
