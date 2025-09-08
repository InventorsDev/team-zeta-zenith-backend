"""
Zendesk integration module
"""

from .client import ZendeskClient
from .sync import ZendeskSyncService
from .webhook import ZendeskWebhookHandler
from .models import (
    ZendeskTicket,
    ZendeskUser,
    ZendeskSyncResult,
    ZendeskWebhookEvent,
    zendesk_ticket_to_internal,
    internal_ticket_to_zendesk
)

__all__ = [
    "ZendeskClient",
    "ZendeskSyncService", 
    "ZendeskWebhookHandler",
    "ZendeskTicket",
    "ZendeskUser",
    "ZendeskSyncResult",
    "ZendeskWebhookEvent",
    "zendesk_ticket_to_internal",
    "internal_ticket_to_zendesk"
]