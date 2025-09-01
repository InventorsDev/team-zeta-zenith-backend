# app/monitoring/slack_notifier.py

import os
import json
import logging
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class SlackNotifier:
    """
    Slack notifier for sending monitoring and anomaly alerts.
    Uses an incoming webhook URL configured in environment variables.
    """

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        if not self.webhook_url:
            logger.warning("SlackNotifier initialized without a webhook URL. "
                           "Alerts will not be sent until SLACK_WEBHOOK_URL is set.")

    def send_message(self, text: str, blocks: Optional[List[Dict[str, Any]]] = None) -> bool:
        """
        Send a message to Slack.

        Args:
            text: Plain text fallback
            blocks: Slack Block Kit structured message (optional)
        """
        if not self.webhook_url:
            logger.error("No Slack webhook URL configured.")
            return False

        payload = {"text": text}
        if blocks:
            payload["blocks"] = blocks

        try:
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            response.raise_for_status()
            logger.info(f"Slack message sent: {text[:50]}...")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Slack message: {e}")
            return False

    def send_alert(self, alert: Dict[str, Any]) -> bool:
        """
        Send a structured alert to Slack.

        Args:
            alert: Dictionary containing alert details (type, severity, message, etc.)
        """
        severity_color = {
            "high": "#ff0000",
            "medium": "#ffa500",
            "low": "#36a64f"
        }

        color = severity_color.get(alert.get("severity", "medium"), "#439FE0")
        text = f":rotating_light: *{alert.get('type', 'Alert')}* - {alert.get('message', '')}"

        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "context", "elements": [
                {"type": "mrkdwn", "text": f"*Model:* {alert.get('model_name', 'N/A')}"},
                {"type": "mrkdwn", "text": f"*Severity:* {alert.get('severity', 'N/A')}"},
                {"type": "mrkdwn", "text": f"*Time:* {alert.get('timestamp', 'N/A')}"}
            ]}
        ]

        attachment = {
            "attachments": [
                {
                    "color": color,
                    "blocks": blocks
                }
            ]
        }

        return self.send_message(text=text, blocks=attachment["attachments"][0]["blocks"])


# Global instance (can be imported in FastAPI endpoints or monitoring code)
slack_notifier = SlackNotifier()
