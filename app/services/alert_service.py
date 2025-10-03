"""
Alert Service - Manages alerts and notifications for tickets
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.models.ticket import Ticket
from app.models.alert import Alert

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
