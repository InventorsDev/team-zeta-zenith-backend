"""
Email Integration Module
Comprehensive email fetching, parsing, and processing for support ticket system
"""

from .imap_client import IMAPClient
from .email_parser import EmailParser
from .email_manager import EmailManager
from .email_deduplication import EmailDeduplicationManager
from .attachment_handler import AttachmentHandler

__all__ = [
    'IMAPClient',
    'EmailParser', 
    'EmailManager',
    'EmailDeduplicationManager',
    'AttachmentHandler'
]