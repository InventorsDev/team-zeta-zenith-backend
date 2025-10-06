"""
Alert Service - Manages alerts and notifications for tickets
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.models.ticket import Ticket
from app.models.alert import Alert
from app.models.alert_rule import AlertRule
from app.schemas.alert import AlertRuleCreate, AlertRuleUpdate

logger = logging.getLogger(__name__)


class AlertService:
    """Service for managing alerts and notifications"""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def create_urgency_alert(
        db: Session,
        ticket_id: int,
        classification_result: Dict[str, Any]
    ) -> Optional[Alert]:
        """
        Create an alert for high urgency tickets.

        Args:
            db: Database session
            ticket_id: ID of the ticket
            classification_result: Classification results

        Returns:
            Created Alert object or None
        """
        try:
            # Get the ticket
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                logger.warning(f"Ticket {ticket_id} not found for alert creation")
                return None

            # Check if urgency is high
            urgency = classification_result.get("urgency", "").lower()
            if urgency not in ["high", "urgent", "critical"]:
                return None

            # Check if alert already exists
            existing_alert = db.query(Alert).filter(
                Alert.ticket_id == ticket_id,
                Alert.alert_type == "high_urgency"
            ).first()

            if existing_alert:
                logger.info(f"Alert already exists for ticket {ticket_id}")
                return existing_alert

            # Create new alert
            alert = Alert(
                ticket_id=ticket_id,
                organization_id=ticket.organization_id,
                alert_type="high_urgency",
                severity="high" if urgency == "high" else "critical",
                title=f"High Urgency Ticket: {ticket.title[:100]}",
                message=f"Ticket #{ticket_id} has been classified as {urgency} urgency",
                alert_metadata={
                    "classification_result": classification_result,
                    "ticket_priority": ticket.priority,
                    "ticket_status": ticket.status,
                    "confidence_score": classification_result.get("confidence", 0)
                },
                is_resolved=False
            )

            db.add(alert)
            db.commit()
            db.refresh(alert)

            logger.info(f"Created urgency alert for ticket {ticket_id}")
            return alert

        except Exception as e:
            logger.error(f"Error creating urgency alert: {e}")
            db.rollback()
            return None

    def create_sla_alert(
        self,
        ticket_id: int,
        sla_type: str,
        time_remaining: float
    ) -> Optional[Alert]:
        """
        Create an alert for SLA violations.

        Args:
            ticket_id: ID of the ticket
            sla_type: Type of SLA (response_time, resolution_time)
            time_remaining: Time remaining in hours (negative if breached)

        Returns:
            Created Alert object or None
        """
        try:
            ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                return None

            severity = "critical" if time_remaining < 0 else "high"

            alert = Alert(
                ticket_id=ticket_id,
                organization_id=ticket.organization_id,
                alert_type=f"sla_{sla_type}",
                severity=severity,
                title=f"SLA Alert: {sla_type.replace('_', ' ').title()}",
                message=f"Ticket #{ticket_id} SLA {sla_type} - {abs(time_remaining):.1f}h {'breached' if time_remaining < 0 else 'remaining'}",
                alert_metadata={
                    "sla_type": sla_type,
                    "time_remaining": time_remaining,
                    "ticket_status": ticket.status
                },
                is_resolved=False
            )

            self.db.add(alert)
            self.db.commit()
            self.db.refresh(alert)

            logger.info(f"Created SLA alert for ticket {ticket_id}")
            return alert

        except Exception as e:
            logger.error(f"Error creating SLA alert: {e}")
            self.db.rollback()
            return None

    def get_active_alerts(
        self,
        organization_id: int,
        alert_type: Optional[str] = None
    ) -> List[Alert]:
        """
        Get active alerts for an organization.

        Args:
            organization_id: ID of the organization
            alert_type: Optional filter by alert type

        Returns:
            List of active alerts
        """
        query = self.db.query(Alert).filter(
            Alert.organization_id == organization_id,
            Alert.is_resolved == False
        )

        if alert_type:
            query = query.filter(Alert.alert_type == alert_type)

        return query.order_by(Alert.created_at.desc()).all()

    def resolve_alert(self, alert_id: int) -> bool:
        """
        Mark an alert as resolved.

        Args:
            alert_id: ID of the alert

        Returns:
            True if successful, False otherwise
        """
        try:
            alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
            if not alert:
                return False

            alert.is_resolved = True
            alert.resolved_at = datetime.utcnow()

            self.db.commit()
            logger.info(f"Resolved alert {alert_id}")
            return True

        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
            self.db.rollback()
            return False

    def resolve_alerts_for_ticket(self, ticket_id: int) -> int:
        """
        Resolve all alerts for a ticket.

        Args:
            ticket_id: ID of the ticket

        Returns:
            Number of alerts resolved
        """
        try:
            alerts = self.db.query(Alert).filter(
                Alert.ticket_id == ticket_id,
                Alert.is_resolved == False
            ).all()

            count = 0
            for alert in alerts:
                alert.is_resolved = True
                alert.resolved_at = datetime.utcnow()
                count += 1

            self.db.commit()
            logger.info(f"Resolved {count} alerts for ticket {ticket_id}")
            return count

        except Exception as e:
            logger.error(f"Error resolving alerts for ticket: {e}")
            self.db.rollback()
            return 0

    def get_alert_stats(self, organization_id: int) -> Dict[str, Any]:
        """
        Get alert statistics for an organization.

        Args:
            organization_id: ID of the organization

        Returns:
            Dictionary with alert statistics
        """
        try:
            total_alerts = self.db.query(Alert).filter(
                Alert.organization_id == organization_id
            ).count()

            active_alerts = self.db.query(Alert).filter(
                Alert.organization_id == organization_id,
                Alert.is_resolved == False
            ).count()

            critical_alerts = self.db.query(Alert).filter(
                Alert.organization_id == organization_id,
                Alert.is_resolved == False,
                Alert.severity == "critical"
            ).count()

            return {
                "total_alerts": total_alerts,
                "active_alerts": active_alerts,
                "critical_alerts": critical_alerts,
                "resolved_alerts": total_alerts - active_alerts
            }

        except Exception as e:
            logger.error(f"Error getting alert stats: {e}")
            return {
                "total_alerts": 0,
                "active_alerts": 0,
                "critical_alerts": 0,
                "resolved_alerts": 0
            }

    # Alert Rule CRUD Operations

    def create_alert_rule(
        self,
        organization_id: int,
        rule_data: AlertRuleCreate,
        created_by: int
    ) -> AlertRule:
        """Create a new alert rule"""
        rule = AlertRule(
            organization_id=organization_id,
            name=rule_data.name,
            description=rule_data.description,
            is_active=rule_data.is_active,
            conditions=[cond.dict() for cond in rule_data.conditions],
            logic=rule_data.logic,
            alert_type=rule_data.alert_type,
            severity=rule_data.severity,
            notification_channels=rule_data.notification_channels,
            notification_config=rule_data.notification_config or {},
            cooldown_minutes=rule_data.cooldown_minutes or 60,
            max_triggers_per_day=rule_data.max_triggers_per_day,
            title_template=rule_data.title_template,
            message_template=rule_data.message_template,
            created_by=created_by
        )

        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)

        logger.info(f"Created alert rule '{rule.name}' for organization {organization_id}")
        return rule

    def get_alert_rule(self, rule_id: int, organization_id: int) -> Optional[AlertRule]:
        """Get a specific alert rule"""
        return self.db.query(AlertRule).filter(
            AlertRule.id == rule_id,
            AlertRule.organization_id == organization_id
        ).first()

    def get_alert_rules(
        self,
        organization_id: int,
        is_active: Optional[bool] = None
    ) -> List[AlertRule]:
        """Get all alert rules for an organization"""
        query = self.db.query(AlertRule).filter(
            AlertRule.organization_id == organization_id
        )

        if is_active is not None:
            query = query.filter(AlertRule.is_active == is_active)

        return query.order_by(AlertRule.created_at.desc()).all()

    def update_alert_rule(
        self,
        rule_id: int,
        organization_id: int,
        rule_data: AlertRuleUpdate
    ) -> Optional[AlertRule]:
        """Update an existing alert rule"""
        rule = self.get_alert_rule(rule_id, organization_id)
        if not rule:
            return None

        update_data = rule_data.dict(exclude_unset=True)

        # Convert conditions to dict if present
        if "conditions" in update_data and update_data["conditions"]:
            update_data["conditions"] = [cond.dict() for cond in update_data["conditions"]]

        for field, value in update_data.items():
            setattr(rule, field, value)

        rule.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(rule)

        logger.info(f"Updated alert rule {rule_id}")
        return rule

    def delete_alert_rule(self, rule_id: int, organization_id: int) -> bool:
        """Delete an alert rule"""
        rule = self.get_alert_rule(rule_id, organization_id)
        if not rule:
            return False

        self.db.delete(rule)
        self.db.commit()

        logger.info(f"Deleted alert rule {rule_id}")
        return True

    def evaluate_rule_conditions(
        self,
        ticket: Ticket,
        conditions: List[Dict[str, Any]],
        logic: str = "AND"
    ) -> bool:
        """
        Evaluate if a ticket matches alert rule conditions

        Args:
            ticket: Ticket to evaluate
            conditions: List of condition dictionaries
            logic: "AND" or "OR" logic for multiple conditions

        Returns:
            True if conditions are met, False otherwise
        """
        if not conditions:
            return False

        results = []

        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator")
            value = condition.get("value")

            # Get ticket field value
            ticket_value = getattr(ticket, field, None)

            # Evaluate condition
            result = False
            if operator == "eq":
                result = ticket_value == value
            elif operator == "ne":
                result = ticket_value != value
            elif operator == "gt":
                result = ticket_value is not None and float(ticket_value) > float(value)
            elif operator == "lt":
                result = ticket_value is not None and float(ticket_value) < float(value)
            elif operator == "gte":
                result = ticket_value is not None and float(ticket_value) >= float(value)
            elif operator == "lte":
                result = ticket_value is not None and float(ticket_value) <= float(value)
            elif operator == "contains":
                result = ticket_value is not None and str(value).lower() in str(ticket_value).lower()
            elif operator == "in":
                result = ticket_value in value if isinstance(value, list) else False

            results.append(result)

        # Apply logic
        if logic == "OR":
            return any(results)
        else:  # AND
            return all(results)

    def check_cooldown(self, rule: AlertRule, ticket_id: int) -> bool:
        """
        Check if cooldown period has passed for this rule and ticket

        Returns:
            True if alert can be triggered, False if still in cooldown
        """
        if not rule.last_triggered_at:
            return True

        # Check if this specific ticket was recently alerted
        if isinstance(rule.last_triggered_at, dict):
            last_trigger = rule.last_triggered_at.get(str(ticket_id))
            if last_trigger:
                last_time = datetime.fromisoformat(last_trigger)
                cooldown_end = last_time.timestamp() + (rule.cooldown_minutes * 60)
                return datetime.utcnow().timestamp() > cooldown_end

        return True

    def check_daily_limit(self, rule: AlertRule) -> bool:
        """
        Check if rule has exceeded daily trigger limit

        Returns:
            True if alert can be triggered, False if limit reached
        """
        if not rule.max_triggers_per_day:
            return True

        # This is a simplified check - in production, track per-day counts
        return rule.trigger_count < rule.max_triggers_per_day

    def trigger_alert_from_rule(
        self,
        rule: AlertRule,
        ticket: Ticket
    ) -> Optional[Alert]:
        """
        Trigger an alert based on a rule match

        Args:
            rule: AlertRule that matched
            ticket: Ticket that triggered the rule

        Returns:
            Created Alert or None
        """
        try:
            # Check cooldown and limits
            if not self.check_cooldown(rule, ticket.id):
                logger.debug(f"Rule {rule.id} in cooldown for ticket {ticket.id}")
                return None

            if not self.check_daily_limit(rule):
                logger.warning(f"Rule {rule.id} has reached daily limit")
                return None

            # Format title and message using templates
            title = rule.title_template or f"{rule.name}: {ticket.title}"
            message = rule.message_template or f"Alert triggered by rule '{rule.name}'"

            # Simple template variable substitution
            title = title.format(ticket=ticket, rule=rule)
            message = message.format(ticket=ticket, rule=rule)

            # Create alert
            alert = Alert(
                ticket_id=ticket.id,
                organization_id=ticket.organization_id,
                alert_type=rule.alert_type,
                severity=rule.severity,
                title=title,
                message=message,
                notification_channels=rule.notification_channels,
                alert_metadata={
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "ticket_priority": ticket.priority,
                    "ticket_status": ticket.status,
                    "triggered_at": datetime.utcnow().isoformat()
                },
                is_resolved=False
            )

            self.db.add(alert)

            # Update rule trigger tracking
            rule.trigger_count += 1
            if not rule.last_triggered_at:
                rule.last_triggered_at = {}
            rule.last_triggered_at[str(ticket.id)] = datetime.utcnow().isoformat()

            self.db.commit()
            self.db.refresh(alert)

            logger.info(f"Triggered alert from rule {rule.id} for ticket {ticket.id}")
            return alert

        except Exception as e:
            logger.error(f"Error triggering alert from rule {rule.id}: {e}")
            self.db.rollback()
            return None
