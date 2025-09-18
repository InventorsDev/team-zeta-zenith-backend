"""
Email Manager
Handles multiple mailboxes, email fetching coordination, and processing workflow
"""

import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, timedelta
import time

from .imap_client import IMAPClient
from .email_parser import EmailParser
from .email_deduplication import EmailDeduplicationManager
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class EmailManager:
    """Manages email fetching from multiple mailboxes with deduplication"""
    
    def __init__(self, config: Dict[str, Any], db: Session = None, integration_id: int = None):
        """
        Initialize Email Manager
        
        Args:
            config: Email configuration including IMAP settings and mailbox config
            db: Database session for persistent deduplication (optional)
            integration_id: Integration ID for database deduplication (optional)
        """
        self.config = config
        self.imap_client = IMAPClient(config)
        self.parser = EmailParser()
        
        # Initialize deduplication manager with database if provided
        if db and integration_id:
            self.deduplication_manager = EmailDeduplicationManager(db, integration_id)
        else:
            # Fall back to in-memory deduplication (for testing/standalone use)
            self.deduplication_manager = EmailDeduplicationManager(None, 0)
        
        # Mailbox configuration
        self.mailbox_config = config.get("mailboxes", {
            "INBOX": {"enabled": True, "process_all": True},
            "Support": {"enabled": True, "process_all": True},
            "Help": {"enabled": True, "process_all": True}
        })
        
        # Processing settings
        self.batch_size = config.get("batch_size", 50)
        self.days_back = config.get("days_back", 30)
        self.max_emails_per_session = config.get("max_emails_per_session", 1000)
        
    def connect(self) -> bool:
        """
        Connect to email server
        
        Returns:
            bool: True if connection successful
        """
        return self.imap_client.connect()
    
    def disconnect(self) -> None:
        """Disconnect from email server"""
        self.imap_client.disconnect()
    
    def list_available_mailboxes(self) -> List[str]:
        """
        List all available mailboxes
        
        Returns:
            List[str]: Available mailbox names
        """
        if not self.imap_client.connection:
            return []
        
        return self.imap_client.list_mailboxes()
    
    def get_enabled_mailboxes(self) -> List[str]:
        """
        Get list of enabled mailboxes for processing
        
        Returns:
            List[str]: Enabled mailbox names
        """
        available_mailboxes = self.list_available_mailboxes()
        enabled_mailboxes = []
        
        for mailbox in available_mailboxes:
            # Check if explicitly configured
            if mailbox in self.mailbox_config:
                if self.mailbox_config[mailbox].get("enabled", False):
                    enabled_mailboxes.append(mailbox)
            else:
                # Auto-detect support-related mailboxes
                support_keywords = ["support", "help", "inbox", "customer", "service"]
                mailbox_lower = mailbox.lower()
                
                if any(keyword in mailbox_lower for keyword in support_keywords):
                    enabled_mailboxes.append(mailbox)
                    logger.info(f"Auto-detected support mailbox: {mailbox}")
        
        # Always include INBOX if available
        if "INBOX" in available_mailboxes and "INBOX" not in enabled_mailboxes:
            enabled_mailboxes.append("INBOX")
        
        logger.info(f"Enabled mailboxes: {enabled_mailboxes}")
        return enabled_mailboxes
    
    def fetch_all_emails(self, since_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Fetch emails from all enabled mailboxes
        
        Args:
            since_date: Fetch emails since this date (default: days_back from config)
            
        Returns:
            Dict: Processing results
        """
        if not self.imap_client.connection:
            raise ConnectionError("Not connected to email server")
        
        results = {
            "total_processed": 0,
            "total_new": 0,
            "total_duplicates": 0,
            "mailbox_results": {},
            "errors": [],
            "processing_time": 0,
            "started_at": datetime.utcnow().isoformat()
        }
        
        start_time = time.time()
        enabled_mailboxes = self.get_enabled_mailboxes()
        
        for mailbox in enabled_mailboxes:
            logger.info(f"Processing mailbox: {mailbox}")
            
            try:
                mailbox_result = self._process_mailbox(mailbox, since_date)
                results["mailbox_results"][mailbox] = mailbox_result
                results["total_processed"] += mailbox_result["processed"]
                results["total_new"] += mailbox_result["new"]
                results["total_duplicates"] += mailbox_result["duplicates"]
                
            except Exception as e:
                error_msg = f"Error processing mailbox {mailbox}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
        
        results["processing_time"] = time.time() - start_time
        results["completed_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"Email fetch completed: {results['total_processed']} processed, "
                   f"{results['total_new']} new, {results['total_duplicates']} duplicates")
        
        return results
    
    def _process_mailbox(self, mailbox: str, since_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Process emails from a single mailbox
        
        Args:
            mailbox: Mailbox name
            since_date: Fetch emails since this date
            
        Returns:
            Dict: Mailbox processing results
        """
        result = {
            "mailbox": mailbox,
            "processed": 0,
            "new": 0,
            "duplicates": 0,
            "errors": 0,
            "emails": []
        }
        
        # Select mailbox
        if not self.imap_client.select_mailbox(mailbox):
            raise Exception(f"Failed to select mailbox {mailbox}")
        
        # Calculate days back
        days_back = self.days_back
        if since_date:
            days_back = (datetime.utcnow() - since_date).days
        
        # Search for emails
        search_criteria = "ALL"
        email_ids = self.imap_client.search_emails(search_criteria, days_back)
        
        if not email_ids:
            logger.info(f"No emails found in {mailbox}")
            return result
        
        # Limit emails per session
        if len(email_ids) > self.max_emails_per_session:
            logger.warning(f"Limiting {len(email_ids)} emails to {self.max_emails_per_session}")
            email_ids = email_ids[:self.max_emails_per_session]
        
        # Fetch emails in batches
        all_emails = []
        for i in range(0, len(email_ids), self.batch_size):
            batch_ids = email_ids[i:i + self.batch_size]
            batch_emails = self.imap_client.fetch_emails_batch(batch_ids, len(batch_ids))
            all_emails.extend(batch_emails)
        
        # Process each email
        for email_data in all_emails:
            try:
                processed_email = self._process_single_email(email_data)
                if processed_email:
                    result["emails"].append(processed_email)
                    result["processed"] += 1
                    
                    if processed_email.get("is_duplicate"):
                        result["duplicates"] += 1
                    else:
                        result["new"] += 1
                        
            except Exception as e:
                logger.error(f"Error processing email {email_data.get('uid', 'unknown')}: {e}")
                result["errors"] += 1
        
        return result
    
    def _process_single_email(self, email_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single email through the full pipeline
        
        Args:
            email_data: Raw email data from IMAP client
            
        Returns:
            Optional[Dict]: Processed email data or None if error
        """
        try:
            # Parse email
            parsed_email = self.parser.parse_email(email_data)
            
            if "error" in parsed_email:
                logger.error(f"Failed to parse email {email_data.get('uid')}: {parsed_email['error']}")
                return None
            
            # Check for duplicates
            is_duplicate = self.deduplication_manager.is_duplicate(parsed_email)
            parsed_email["is_duplicate"] = is_duplicate
            
            if is_duplicate:
                logger.debug(f"Skipping duplicate email {parsed_email.get('uid')}")
                return parsed_email
            
            # Mark as processed
            self.deduplication_manager.mark_processed(parsed_email)
            
            # Extract ticket information
            ticket_info = self.parser.extract_ticket_info(parsed_email)
            parsed_email["ticket_info"] = ticket_info
            
            # Filter out auto-replies and system emails unless configured otherwise
            email_type = parsed_email.get("email_type", "")
            if email_type in ["auto_reply", "system_email", "newsletter"]:
                mailbox_config = self.mailbox_config.get(parsed_email.get("mailbox", ""), {})
                if not mailbox_config.get("process_auto_replies", False):
                    logger.debug(f"Skipping {email_type}: {parsed_email.get('subject')}")
                    parsed_email["skipped"] = True
                    parsed_email["skip_reason"] = f"Auto-filtered: {email_type}"
                    return parsed_email
            
            return parsed_email
            
        except Exception as e:
            logger.error(f"Error in email processing pipeline: {e}")
            return None
    
    def fetch_specific_mailbox(self, mailbox: str, search_criteria: str = "ALL", 
                              days_back: int = 7) -> Dict[str, Any]:
        """
        Fetch emails from a specific mailbox with custom criteria
        
        Args:
            mailbox: Mailbox name
            search_criteria: IMAP search criteria
            days_back: Number of days to look back
            
        Returns:
            Dict: Processing results
        """
        if not self.imap_client.connection:
            raise ConnectionError("Not connected to email server")
        
        logger.info(f"Fetching from {mailbox} with criteria '{search_criteria}'")
        
        result = self._process_mailbox_with_criteria(mailbox, search_criteria, days_back)
        
        return {
            "mailbox": mailbox,
            "search_criteria": search_criteria,
            "days_back": days_back,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _process_mailbox_with_criteria(self, mailbox: str, search_criteria: str, 
                                     days_back: int) -> Dict[str, Any]:
        """Process mailbox with specific search criteria"""
        if not self.imap_client.select_mailbox(mailbox):
            raise Exception(f"Failed to select mailbox {mailbox}")
        
        email_ids = self.imap_client.search_emails(search_criteria, days_back)
        
        if not email_ids:
            return {"processed": 0, "emails": []}
        
        emails = self.imap_client.fetch_emails_batch(email_ids, self.batch_size)
        processed_emails = []
        
        for email_data in emails:
            processed_email = self._process_single_email(email_data)
            if processed_email:
                processed_emails.append(processed_email)
        
        return {
            "processed": len(processed_emails),
            "emails": processed_emails
        }
    
    def get_mailbox_stats(self, mailbox: str = "INBOX") -> Dict[str, Any]:
        """
        Get statistics for a specific mailbox
        
        Args:
            mailbox: Mailbox name
            
        Returns:
            Dict: Mailbox statistics
        """
        if not self.imap_client.connection:
            raise ConnectionError("Not connected to email server")
        
        if not self.imap_client.select_mailbox(mailbox):
            raise Exception(f"Failed to select mailbox {mailbox}")
        
        # Get total message count
        total_emails = self.imap_client.search_emails("ALL", days_back=0)
        recent_emails = self.imap_client.search_emails("ALL", days_back=7)
        unread_emails = self.imap_client.search_emails("UNSEEN", days_back=0)
        
        return {
            "mailbox": mailbox,
            "total_messages": len(total_emails),
            "recent_messages": len(recent_emails),
            "unread_messages": len(unread_emails),
            "stats_generated_at": datetime.utcnow().isoformat()
        }
    
    def search_emails_by_sender(self, sender_email: str, mailbox: str = "INBOX", 
                               days_back: int = 30) -> List[Dict[str, Any]]:
        """
        Search emails by sender
        
        Args:
            sender_email: Sender email address
            mailbox: Mailbox to search in
            days_back: Days to look back
            
        Returns:
            List[Dict]: Found emails
        """
        search_criteria = f'FROM "{sender_email}"'
        result = self.fetch_specific_mailbox(mailbox, search_criteria, days_back)
        return result.get("result", {}).get("emails", [])
    
    def search_emails_by_subject(self, subject_keywords: str, mailbox: str = "INBOX", 
                                days_back: int = 30) -> List[Dict[str, Any]]:
        """
        Search emails by subject keywords
        
        Args:
            subject_keywords: Keywords to search in subject
            mailbox: Mailbox to search in
            days_back: Days to look back
            
        Returns:
            List[Dict]: Found emails
        """
        search_criteria = f'SUBJECT "{subject_keywords}"'
        result = self.fetch_specific_mailbox(mailbox, search_criteria, days_back)
        return result.get("result", {}).get("emails", [])
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get comprehensive connection and configuration status"""
        imap_status = self.imap_client.get_connection_status()
        
        return {
            "imap_connection": imap_status,
            "configured_mailboxes": self.mailbox_config,
            "processing_settings": {
                "batch_size": self.batch_size,
                "days_back": self.days_back,
                "max_emails_per_session": self.max_emails_per_session
            },
            "deduplication_stats": self.deduplication_manager.get_stats(),
            "last_check": datetime.utcnow().isoformat()
        }
    
    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate email configuration and connectivity
        
        Returns:
            Dict: Validation results
        """
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "connectivity": False,
            "mailboxes": []
        }
        
        # Test connection
        try:
            if self.connect():
                results["connectivity"] = True
                
                # Test mailbox access
                available_mailboxes = self.list_available_mailboxes()
                results["mailboxes"] = available_mailboxes
                
                # Check configured mailboxes exist
                for configured_mailbox in self.mailbox_config.keys():
                    if configured_mailbox not in available_mailboxes:
                        results["warnings"].append(
                            f"Configured mailbox '{configured_mailbox}' not found"
                        )
                
                self.disconnect()
                
            else:
                results["valid"] = False
                results["errors"].append("Failed to connect to email server")
                
        except Exception as e:
            results["valid"] = False
            results["errors"].append(f"Connection test failed: {str(e)}")
        
        return results
    
    def __enter__(self):
        """Context manager entry"""
        if not self.connect():
            raise ConnectionError("Failed to connect to email server")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()