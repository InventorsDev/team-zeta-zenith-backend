"""
Notification Service - Handles sending notifications via multiple channels
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
import logging
import asyncio
import httpx
from datetime import datetime

from app.models.alert import Alert
from app.models.organization import Organization
from app.ml.monitoring.slack_notifier import SlackNotifier
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class NotificationService:
    """Service for sending notifications through various channels"""

    def __init__(self, db: Session):
        self.db = db
        self.slack_notifier = SlackNotifier() if settings.slack_webhook_url else None

    async def send_alert_notifications(
        self,
        alert: Alert,
        channels: List[str],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, bool]:
        """
        Send alert notifications through specified channels

        Args:
            alert: Alert object to send
            channels: List of notification channels ("email", "slack", "webhook")
            config: Additional configuration for notifications

        Returns:
            Dict mapping channel names to success status
        """
        results = {}
        config = config or {}

        for channel in channels:
            try:
                if channel == "email":
                    success = await self._send_email_notification(alert, config)
                    results["email"] = success
                elif channel == "slack":
                    success = await self._send_slack_notification(alert, config)
                    results["slack"] = success
                elif channel == "webhook":
                    success = await self._send_webhook_notification(alert, config)
                    results["webhook"] = success
                else:
                    logger.warning(f"Unknown notification channel: {channel}")
                    results[channel] = False

            except Exception as e:
                logger.error(f"Error sending {channel} notification for alert {alert.id}: {e}")
                results[channel] = False

        # Update alert notification status
        if any(results.values()):
            alert.is_notified = True
            alert.notified_at = datetime.utcnow()
            self.db.commit()

        return results

    async def _send_email_notification(
        self,
        alert: Alert,
        config: Dict[str, Any]
    ) -> bool:
        """
        Send email notification

        Note: This is a placeholder. In production, integrate with your email service
        (SendGrid, AWS SES, etc.)
        """
        try:
            # Get organization details
            org = self.db.query(Organization).filter(
                Organization.id == alert.organization_id
            ).first()

            if not org or not org.email:
                logger.warning(f"No email configured for organization {alert.organization_id}")
                return False

            # Build email content
            subject = f"[{alert.severity.upper()}] {alert.title}"
            body = f"""
Alert Notification
==================

Severity: {alert.severity}
Type: {alert.alert_type}
Triggered: {alert.triggered_at}

Message:
{alert.message}

Ticket ID: {alert.ticket_id}
Organization: {org.name}

---
This is an automated alert from your Customer Support Analyzer
"""

            # TODO: Implement actual email sending
            # For now, just log it
            logger.info(f"Would send email to {org.email}: {subject}")
            logger.debug(f"Email body: {body}")

            # Simulated success
            return True

        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return False

    async def _send_slack_notification(
        self,
        alert: Alert,
        config: Dict[str, Any]
    ) -> bool:
        """Send Slack notification using existing SlackNotifier"""
        try:
            if not self.slack_notifier:
                logger.warning("Slack notifier not configured")
                return False

            # Use the existing SlackNotifier to send alert
            success = self.slack_notifier.send_alert(
                title=alert.title,
                message=alert.message,
                severity=alert.severity,
                metadata={
                    "ticket_id": alert.ticket_id,
                    "alert_type": alert.alert_type,
                    "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None
                }
            )

            return success

        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            return False

    async def _send_webhook_notification(
        self,
        alert: Alert,
        config: Dict[str, Any]
    ) -> bool:
        """
        Send webhook notification

        Args:
            alert: Alert to send
            config: Should contain "webhook_url" key
        """
        try:
            webhook_url = config.get("webhook_url")
            if not webhook_url:
                logger.warning("No webhook URL provided in config")
                return False

            # Build webhook payload
            payload = {
                "alert_id": alert.id,
                "organization_id": alert.organization_id,
                "ticket_id": alert.ticket_id,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "title": alert.title,
                "message": alert.message,
                "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
                "metadata": alert.alert_metadata
            }

            # Send POST request to webhook
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=payload)

                if response.status_code in [200, 201, 202, 204]:
                    logger.info(f"Webhook notification sent successfully to {webhook_url}")
                    return True
                else:
                    logger.warning(f"Webhook returned status {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")
            return False

    def send_alert_notifications_sync(
        self,
        alert: Alert,
        channels: List[str],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, bool]:
        """
        Synchronous wrapper for send_alert_notifications

        Used in Celery tasks where async isn't available
        """
        try:
            # Create new event loop for sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                results = loop.run_until_complete(
                    self.send_alert_notifications(alert, channels, config)
                )
                return results
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Error in sync notification wrapper: {e}")
            return {channel: False for channel in channels}
