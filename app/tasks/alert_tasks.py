"""
Alert Tasks - Celery tasks for alert rule evaluation and notification
"""

from celery import shared_task
from sqlalchemy.orm import Session
import logging
from datetime import datetime, timedelta

from app.database.connection import SessionLocal
from app.models.ticket import Ticket
from app.models.alert_rule import AlertRule
from app.services.alert_service import AlertService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


@shared_task(name="evaluate_alert_rules")
def evaluate_alert_rules():
    """
    Periodic task to evaluate all active alert rules against tickets

    This task runs periodically (e.g., every 5 minutes) and checks all active
    alert rules against recent tickets to trigger alerts when conditions are met.
    """
    db = SessionLocal()
    try:
        alert_service = AlertService(db)
        notification_service = NotificationService(db)

        # Get all active alert rules
        active_rules = db.query(AlertRule).filter(
            AlertRule.is_active == True
        ).all()

        logger.info(f"Evaluating {len(active_rules)} active alert rules")

        alerts_triggered = 0

        for rule in active_rules:
            try:
                # Get tickets to evaluate (e.g., created/updated in last hour)
                # Adjust time window based on your needs
                tickets = db.query(Ticket).filter(
                    Ticket.organization_id == rule.organization_id,
                    Ticket.created_at >= datetime.utcnow() - timedelta(hours=1)
                ).all()

                for ticket in tickets:
                    # Evaluate conditions
                    matches = alert_service.evaluate_rule_conditions(
                        ticket=ticket,
                        conditions=rule.conditions,
                        logic=rule.logic
                    )

                    if matches:
                        # Trigger alert
                        alert = alert_service.trigger_alert_from_rule(
                            rule=rule,
                            ticket=ticket
                        )

                        if alert:
                            alerts_triggered += 1

                            # Send notifications
                            notification_service.send_alert_notifications_sync(
                                alert=alert,
                                channels=rule.notification_channels,
                                config=rule.notification_config
                            )

            except Exception as e:
                logger.error(f"Error evaluating rule {rule.id}: {e}")
                continue

        logger.info(f"Alert evaluation complete. Triggered {alerts_triggered} alerts")
        return {
            "rules_evaluated": len(active_rules),
            "alerts_triggered": alerts_triggered,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in evaluate_alert_rules task: {e}")
        raise
    finally:
        db.close()


@shared_task(name="evaluate_alert_rule_for_ticket")
def evaluate_alert_rule_for_ticket(ticket_id: int):
    """
    Evaluate all active alert rules for a specific ticket

    This task is triggered when a ticket is created or updated to immediately
    check if any alert rules should fire.

    Args:
        ticket_id: ID of the ticket to evaluate
    """
    db = SessionLocal()
    try:
        alert_service = AlertService(db)
        notification_service = NotificationService(db)

        # Get the ticket
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            logger.warning(f"Ticket {ticket_id} not found")
            return {"error": "Ticket not found"}

        # Get active rules for this organization
        active_rules = db.query(AlertRule).filter(
            AlertRule.organization_id == ticket.organization_id,
            AlertRule.is_active == True
        ).all()

        logger.info(f"Evaluating {len(active_rules)} rules for ticket {ticket_id}")

        alerts_triggered = 0

        for rule in active_rules:
            try:
                # Evaluate conditions
                matches = alert_service.evaluate_rule_conditions(
                    ticket=ticket,
                    conditions=rule.conditions,
                    logic=rule.logic
                )

                if matches:
                    # Trigger alert
                    alert = alert_service.trigger_alert_from_rule(
                        rule=rule,
                        ticket=ticket
                    )

                    if alert:
                        alerts_triggered += 1

                        # Send notifications asynchronously
                        send_alert_notification.delay(
                            alert_id=alert.id,
                            channels=rule.notification_channels,
                            config=rule.notification_config
                        )

            except Exception as e:
                logger.error(f"Error evaluating rule {rule.id} for ticket {ticket_id}: {e}")
                continue

        logger.info(f"Evaluated ticket {ticket_id}. Triggered {alerts_triggered} alerts")
        return {
            "ticket_id": ticket_id,
            "rules_evaluated": len(active_rules),
            "alerts_triggered": alerts_triggered,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in evaluate_alert_rule_for_ticket task: {e}")
        raise
    finally:
        db.close()


@shared_task(name="send_alert_notification")
def send_alert_notification(
    alert_id: int,
    channels: list,
    config: dict = None
):
    """
    Send notifications for an alert

    Args:
        alert_id: ID of the alert to send
        channels: List of notification channels
        config: Additional configuration
    """
    db = SessionLocal()
    try:
        from app.models.alert import Alert

        notification_service = NotificationService(db)

        # Get the alert
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            logger.warning(f"Alert {alert_id} not found")
            return {"error": "Alert not found"}

        # Send notifications
        results = notification_service.send_alert_notifications_sync(
            alert=alert,
            channels=channels,
            config=config or {}
        )

        logger.info(f"Sent notifications for alert {alert_id}: {results}")
        return {
            "alert_id": alert_id,
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in send_alert_notification task: {e}")
        raise
    finally:
        db.close()


@shared_task(name="cleanup_old_alerts")
def cleanup_old_alerts(days: int = 90):
    """
    Clean up old resolved alerts

    Args:
        days: Delete alerts resolved more than this many days ago
    """
    db = SessionLocal()
    try:
        from app.models.alert import Alert

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Delete old resolved alerts
        deleted_count = db.query(Alert).filter(
            Alert.is_resolved == True,
            Alert.resolved_at < cutoff_date
        ).delete()

        db.commit()

        logger.info(f"Cleaned up {deleted_count} old alerts")
        return {
            "deleted_count": deleted_count,
            "cutoff_date": cutoff_date.isoformat(),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in cleanup_old_alerts task: {e}")
        db.rollback()
        raise
    finally:
        db.close()
