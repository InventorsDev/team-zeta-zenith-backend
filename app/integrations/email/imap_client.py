"""
IMAP Email Client
Handles connections to email servers (Gmail, Outlook, etc.) and email fetching
"""

import imaplib
import email
import ssl
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import re

logger = logging.getLogger(__name__)

class IMAPClient:
    """IMAP client for fetching emails from various providers"""
    
    # Provider configurations
    PROVIDER_CONFIG = {
        "gmail": {
            "server": "imap.gmail.com",
            "port": 993,
            "ssl": True,
            "auth_method": "oauth2"  # Can also use "password"
        },
        "outlook": {
            "server": "outlook.office365.com", 
            "port": 993,
            "ssl": True,
            "auth_method": "oauth2"
        },
        "yahoo": {
            "server": "imap.mail.yahoo.com",
            "port": 993,
            "ssl": True,
            "auth_method": "password"
        },
        "icloud": {
            "server": "imap.mail.me.com",
            "port": 993,
            "ssl": True,
            "auth_method": "password"
        },
        "custom": {
            "server": None,  # User-defined
            "port": 993,
            "ssl": True,
            "auth_method": "password"
        }
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize IMAP client with configuration
        
        Args:
            config: Dictionary containing IMAP configuration
                - provider: gmail, outlook, yahoo, icloud, or custom
                - email: Email address
                - password: Password or app password
                - server: IMAP server (for custom provider)
                - port: IMAP port (optional)
                - ssl: Use SSL (optional)
        """
        self.config = config
        self.provider = config.get("provider", "custom").lower()
        self.email = config.get("email")
        self.password = config.get("password")
        
        # Get provider configuration
        if self.provider in self.PROVIDER_CONFIG:
            self.server_config = self.PROVIDER_CONFIG[self.provider].copy()
            if self.provider == "custom":
                self.server_config["server"] = config.get("server")
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        # Override with user config if provided
        self.server_config.update({
            "server": config.get("server", self.server_config["server"]),
            "port": config.get("port", self.server_config["port"]),
            "ssl": config.get("ssl", self.server_config["ssl"])
        })
        
        self.connection = None
        self.current_mailbox = None
        
    def connect(self) -> bool:
        """
        Connect to IMAP server
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            server = self.server_config["server"]
            port = self.server_config["port"]
            use_ssl = self.server_config["ssl"]
            
            if not server:
                raise ValueError("IMAP server not specified")
            
            logger.info(f"Connecting to IMAP server: {server}:{port} (SSL: {use_ssl})")
            
            # Create connection
            if use_ssl:
                self.connection = imaplib.IMAP4_SSL(server, port)
            else:
                self.connection = imaplib.IMAP4(server, port)
            
            # Login
            result = self.connection.login(self.email, self.password)
            
            if result[0] == 'OK':
                logger.info(f"Successfully connected to {self.email}")
                return True
            else:
                logger.error(f"Login failed: {result[1]}")
                return False
                
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP error during connection: {e}")
            return False
        except ssl.SSLError as e:
            logger.error(f"SSL error during connection: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from IMAP server"""
        if self.connection:
            try:
                # Only close if a mailbox is currently selected
                if self.current_mailbox:
                    self.connection.close()
                self.connection.logout()
                logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self.connection = None
                self.current_mailbox = None
    
    def list_mailboxes(self) -> List[str]:
        """
        List available mailboxes
        
        Returns:
            List[str]: List of mailbox names
        """
        if not self.connection:
            raise ConnectionError("Not connected to IMAP server")
        
        try:
            result, mailboxes = self.connection.list()
            
            if result != 'OK':
                logger.error(f"Failed to list mailboxes: {mailboxes}")
                return []
            
            mailbox_names = []
            for mailbox in mailboxes:
                # Parse mailbox name from IMAP LIST response
                # Format: (\\Flags) "delimiter" "name"
                mailbox_str = mailbox.decode('utf-8')
                match = re.search(r'"([^"]*)"$', mailbox_str)
                if match:
                    mailbox_name = match.group(1)
                    mailbox_names.append(mailbox_name)
                else:
                    # Fallback parsing
                    parts = mailbox_str.split(' ')
                    if len(parts) >= 3:
                        mailbox_names.append(parts[-1].strip('"'))
            
            logger.info(f"Found {len(mailbox_names)} mailboxes")
            return mailbox_names
            
        except Exception as e:
            logger.error(f"Error listing mailboxes: {e}")
            return []
    
    def select_mailbox(self, mailbox: str = "INBOX") -> bool:
        """
        Select a mailbox for operations
        
        Args:
            mailbox: Mailbox name (default: INBOX)
            
        Returns:
            bool: True if selection successful
        """
        if not self.connection:
            raise ConnectionError("Not connected to IMAP server")
        
        try:
            result, data = self.connection.select(mailbox)
            
            if result == 'OK':
                self.current_mailbox = mailbox
                message_count = int(data[0]) if data[0] else 0
                logger.info(f"Selected mailbox '{mailbox}' with {message_count} messages")
                return True
            else:
                logger.error(f"Failed to select mailbox '{mailbox}': {data}")
                return False
                
        except Exception as e:
            logger.error(f"Error selecting mailbox '{mailbox}': {e}")
            return False
    
    def search_emails(self, criteria: str = "ALL", days_back: int = 30) -> List[int]:
        """
        Search for emails matching criteria
        
        Args:
            criteria: IMAP search criteria (default: ALL)
            days_back: Number of days to look back (default: 30)
            
        Returns:
            List[int]: List of email UIDs
        """
        if not self.connection or not self.current_mailbox:
            raise ConnectionError("Not connected or no mailbox selected")
        
        try:
            # Add date filter if specified
            if days_back > 0:
                since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
                if criteria == "ALL":
                    criteria = f'SINCE "{since_date}"'
                else:
                    criteria = f'({criteria}) SINCE "{since_date}"'
            
            logger.info(f"Searching emails with criteria: {criteria}")
            result, data = self.connection.search(None, criteria)
            
            if result != 'OK':
                logger.error(f"Search failed: {data}")
                return []
            
            # Parse email UIDs
            email_ids = []
            if data[0]:
                email_ids = [int(uid) for uid in data[0].split()]
            
            logger.info(f"Found {len(email_ids)} emails matching criteria")
            return email_ids
            
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return []
    
    def fetch_email(self, email_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a single email by ID
        
        Args:
            email_id: Email UID
            
        Returns:
            Optional[Dict]: Email data or None if error
        """
        if not self.connection or not self.current_mailbox:
            raise ConnectionError("Not connected or no mailbox selected")
        
        try:
            # Fetch email data (use BODY[] for better compatibility)
            result, data = self.connection.fetch(str(email_id), '(BODY[])')
            
            if result != 'OK':
                logger.error(f"FETCH command failed for email {email_id}: {result}")
                return None
            
            if not data or not data[0] or len(data[0]) < 2:
                logger.error(f"No email data returned for email {email_id}")
                return None
            
            # Parse email
            email_message = email.message_from_bytes(data[0][1])
            
            return self._parse_email(email_message, email_id)
            
        except Exception as e:
            logger.error(f"Error fetching email {email_id}: {e}")
            return None
    
    def fetch_emails_batch(self, email_ids: List[int], batch_size: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch multiple emails in batches
        
        Args:
            email_ids: List of email UIDs
            batch_size: Number of emails to fetch per batch
            
        Returns:
            List[Dict]: List of parsed email data
        """
        emails = []
        
        for i in range(0, len(email_ids), batch_size):
            batch = email_ids[i:i + batch_size]
            logger.info(f"Fetching batch {i//batch_size + 1}: {len(batch)} emails")
            
            for email_id in batch:
                email_data = self.fetch_email(email_id)
                if email_data:
                    emails.append(email_data)
        
        logger.info(f"Successfully fetched {len(emails)} out of {len(email_ids)} emails")
        return emails
    
    def _parse_email(self, email_message, email_id: int) -> Dict[str, Any]:
        """
        Parse email message into structured data
        
        Args:
            email_message: Email message object
            email_id: Email UID
            
        Returns:
            Dict: Parsed email data
        """
        try:
            # Extract basic headers
            subject = self._decode_header(email_message.get('Subject', ''))
            from_addr = self._decode_header(email_message.get('From', ''))
            to_addr = self._decode_header(email_message.get('To', ''))
            cc_addr = self._decode_header(email_message.get('CC', ''))
            date_str = email_message.get('Date', '')
            message_id = email_message.get('Message-ID', '')
            
            # Parse date
            email_date = None
            if date_str:
                try:
                    email_date = email.utils.parsedate_to_datetime(date_str)
                except:
                    pass
            
            # Extract body and attachments
            body_text = ""
            body_html = ""
            attachments = []
            
            if email_message.is_multipart():
                for part in email_message.walk():
                    part_body_text, part_body_html, part_attachments = self._process_email_part(part)
                    if part_body_text and not body_text:
                        body_text = part_body_text
                    if part_body_html and not body_html:
                        body_html = part_body_html
                    attachments.extend(part_attachments)
            else:
                content_type = email_message.get_content_type()
                body = self._decode_email_body(email_message)
                
                if content_type == "text/plain":
                    body_text = body
                elif content_type == "text/html":
                    body_html = body
            
            # Log if no body content was found
            if not body_text and not body_html:
                logger.warning(f"No body content extracted for email {email_id}")
            
            return {
                "uid": email_id,
                "message_id": message_id,
                "subject": subject,
                "from": from_addr,
                "to": to_addr,
                "cc": cc_addr,
                "date": email_date,
                "body_text": body_text,
                "body_html": body_html,
                "attachments": attachments,
                "mailbox": self.current_mailbox,
                "raw_headers": dict(email_message.items())
            }
            
        except Exception as e:
            logger.error(f"Error parsing email {email_id}: {e}")
            return {
                "uid": email_id,
                "error": str(e),
                "mailbox": self.current_mailbox
            }
    
    def _process_email_part(self, part) -> Tuple[str, str, List]:
        """Process individual email part (body or attachment)"""
        content_type = part.get_content_type()
        content_disposition = str(part.get('Content-Disposition', ''))
        
        body_text = ""
        body_html = ""
        attachments = []
        
        # Check if it's an attachment
        if 'attachment' in content_disposition:
            filename = part.get_filename()
            if filename:
                filename = self._decode_header(filename)
                
                attachments.append({
                    "filename": filename,
                    "content_type": content_type,
                    "size": len(part.get_payload(decode=True)) if part.get_payload(decode=True) else 0,
                    "content_disposition": content_disposition
                })
        else:
            # It's part of the email body
            body = self._decode_email_body(part)
            
            if content_type == "text/plain":
                body_text = body
            elif content_type == "text/html":
                body_html = body
        
        return body_text, body_html, attachments
    
    def _decode_header(self, header: str) -> str:
        """Decode email header (handles encoding)"""
        if not header:
            return ""
        
        try:
            decoded_parts = email.header.decode_header(header)
            decoded_header = ""
            
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_header += part.decode(encoding)
                    else:
                        decoded_header += part.decode('utf-8', errors='ignore')
                else:
                    decoded_header += str(part)
            
            return decoded_header.strip()
        except:
            return str(header)
    
    def _decode_email_body(self, part) -> str:
        """Decode email body content"""
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                return ""
            
            # Try to determine charset
            charset = part.get_content_charset()
            if not charset:
                charset = 'utf-8'
            
            return payload.decode(charset, errors='ignore')
        except:
            return ""
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get current connection status
        
        Returns:
            Dict: Connection status information
        """
        return {
            "connected": self.connection is not None,
            "provider": self.provider,
            "email": self.email,
            "server": self.server_config.get("server"),
            "current_mailbox": self.current_mailbox,
            "ssl_enabled": self.server_config.get("ssl")
        }