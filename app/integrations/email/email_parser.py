"""
Email Parser and Cleaner
Advanced email content parsing, cleaning, and extraction
"""

import re
import html
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import hashlib

# Optional dependency - BeautifulSoup for HTML parsing
try:
    from bs4 import BeautifulSoup
    HAS_BEAUTIFULSOUP = True
except ImportError:
    HAS_BEAUTIFULSOUP = False
    BeautifulSoup = None

logger = logging.getLogger(__name__)

class EmailParser:
    """Advanced email parsing and cleaning functionality"""
    
    def __init__(self):
        self.signature_patterns = [
            r"--\s*\n",  # Common signature delimiter
            r"^Sent from my iPhone",
            r"^Sent from my Android",
            r"^Get Outlook for",
            r"^This email was sent from",
            r"^Best regards,",
            r"^Kind regards,",
            r"^Sincerely,",
            r"^Thank you,",
            r"^Thanks,",
        ]
        
        self.reply_patterns = [
            r"^On .* wrote:$",
            r"^From:.*Sent:.*To:.*Subject:",
            r"^-----Original Message-----",
            r"^> .*",  # Quoted text
            r"^From: .*",
            r"^Date: .*",
            r"^Subject: .*",
            r"^To: .*",
        ]
        
        self.auto_reply_indicators = [
            "out of office",
            "automatic reply",
            "auto-reply",
            "vacation message",
            "away message",
            "delivery failure",
            "mailer-daemon",
            "postmaster",
        ]
    
    def parse_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and clean email data comprehensively
        
        Args:
            email_data: Raw email data from IMAP client
            
        Returns:
            Dict: Parsed and cleaned email data
        """
        try:
            # Extract sender information
            sender_info = self._parse_sender(email_data.get("from", ""))
            
            # Clean and extract body content
            body_text = self._clean_text_body(email_data.get("body_text", ""))
            body_html = email_data.get("body_html", "")
            
            # If no plain text, extract from HTML
            if not body_text and body_html:
                body_text = self._html_to_text(body_html)
            
            # Extract main content (remove signatures, replies, etc.)
            main_content = self._extract_main_content(body_text)
            
            # Parse subject
            subject = self._clean_subject(email_data.get("subject", ""))
            
            # Detect email type
            email_type = self._detect_email_type(email_data, main_content)
            
            # Extract metadata
            metadata = self._extract_metadata(email_data, main_content)
            
            # Generate content hash for deduplication
            content_hash = self._generate_content_hash(subject, main_content, sender_info["email"])
            
            return {
                "uid": email_data.get("uid"),
                "message_id": email_data.get("message_id"),
                "subject": subject,
                "subject_cleaned": self._extract_subject_keywords(subject),
                "sender": sender_info,
                "recipients": self._parse_recipients(email_data),
                "date": email_data.get("date"),
                "body_text": body_text,
                "body_html": body_html,
                "main_content": main_content,
                "content_preview": self._generate_preview(main_content),
                "email_type": email_type,
                "metadata": metadata,
                "content_hash": content_hash,
                "attachments": self._parse_attachments(email_data.get("attachments", [])),
                "mailbox": email_data.get("mailbox"),
                "parsing_info": {
                    "parsed_at": datetime.utcnow().isoformat(),
                    "content_length": len(main_content),
                    "has_attachments": len(email_data.get("attachments", [])) > 0,
                    "is_multipart": bool(body_html and body_text)
                }
            }
            
        except Exception as e:
            logger.error(f"Error parsing email {email_data.get('uid', 'unknown')}: {e}")
            return {
                "uid": email_data.get("uid"),
                "error": f"Parsing failed: {str(e)}",
                "raw_data": email_data
            }
    
    def _parse_sender(self, from_field: str) -> Dict[str, str]:
        """
        Parse sender information from 'From' field
        
        Args:
            from_field: Email from field
            
        Returns:
            Dict: Parsed sender information
        """
        if not from_field:
            return {"name": "", "email": "", "domain": ""}
        
        # Pattern to match "Name <email@domain.com>" or just "email@domain.com"
        match = re.match(r'(?:"?([^"<]*)"?\s*)?<?([^<>\s]+@[^<>\s]+)>?', from_field.strip())
        
        if match:
            name = (match.group(1) or "").strip()
            email_addr = (match.group(2) or "").strip()
            domain = email_addr.split('@')[1] if '@' in email_addr else ""
            
            return {
                "name": name,
                "email": email_addr,
                "domain": domain,
                "raw": from_field
            }
        
        return {
            "name": "",
            "email": from_field.strip(),
            "domain": "",
            "raw": from_field
        }
    
    def _parse_recipients(self, email_data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Parse recipient information"""
        recipients = {
            "to": [],
            "cc": [],
            "bcc": []
        }
        
        for field in ["to", "cc", "bcc"]:
            field_value = email_data.get(field, "")
            if field_value:
                # Split by comma and parse each recipient
                for recipient in field_value.split(','):
                    parsed = self._parse_sender(recipient.strip())
                    if parsed["email"]:
                        recipients[field].append(parsed)
        
        return recipients
    
    def _clean_text_body(self, body: str) -> str:
        """Clean plain text email body"""
        if not body:
            return ""
        
        # Remove excessive whitespace
        body = re.sub(r'\n\s*\n\s*\n', '\n\n', body)
        body = re.sub(r'[ \t]+', ' ', body)
        
        # Remove common email artifacts
        body = re.sub(r'\r\n', '\n', body)
        body = re.sub(r'\r', '\n', body)
        
        return body.strip()
    
    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML email to plain text"""
        if not html_content:
            return ""
        
        try:
            if HAS_BEAUTIFULSOUP and BeautifulSoup:
                # Parse HTML with BeautifulSoup if available
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Get text content
                text = soup.get_text()
                
                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                
                return text
            else:
                # Fallback: Basic HTML tag removal with regex
                logger.warning("BeautifulSoup not available, using basic HTML parsing")
                text = re.sub('<[^<]+?>', '', html_content)
                text = html.unescape(text)
                
                # Basic cleanup
                text = re.sub(r'\s+', ' ', text)
                return text.strip()
            
        except Exception as e:
            logger.warning(f"Error converting HTML to text: {e}")
            # Final fallback: strip HTML tags with regex
            text = re.sub('<[^<]+?>', '', html_content)
            return html.unescape(text).strip()
    
    def _extract_main_content(self, body_text: str) -> str:
        """Extract main content by removing signatures, replies, etc."""
        if not body_text:
            return ""
        
        lines = body_text.split('\n')
        main_lines = []
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Check for signature patterns
            is_signature = any(re.search(pattern, line, re.IGNORECASE | re.MULTILINE) 
                             for pattern in self.signature_patterns)
            
            # Check for reply patterns
            is_reply = any(re.search(pattern, line, re.IGNORECASE | re.MULTILINE) 
                          for pattern in self.reply_patterns)
            
            if is_signature or is_reply:
                # Stop processing at signature or reply
                break
            
            # Skip empty lines at the beginning
            if not main_lines and not line_stripped:
                continue
            
            main_lines.append(line)
        
        main_content = '\n'.join(main_lines).strip()
        
        # Remove excessive newlines
        main_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', main_content)
        
        return main_content
    
    def _clean_subject(self, subject: str) -> str:
        """Clean email subject"""
        if not subject:
            return ""
        
        # Remove Re:, Fwd:, etc.
        subject = re.sub(r'^(Re|RE|re|Fwd|FWD|fwd):\s*', '', subject)
        subject = re.sub(r'\[.*?\]\s*', '', subject)  # Remove [tags]
        
        return subject.strip()
    
    def _extract_subject_keywords(self, subject: str) -> List[str]:
        """Extract keywords from subject line"""
        if not subject:
            return []
        
        # Remove common words and extract meaningful terms
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'a', 'an'}
        
        # Extract words, removing punctuation
        words = re.findall(r'\b\w+\b', subject.lower())
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return keywords[:10]  # Limit to top 10 keywords
    
    def _detect_email_type(self, email_data: Dict[str, Any], content: str) -> str:
        """
        Detect email type (support request, auto-reply, newsletter, etc.)
        
        Returns:
            str: Email type classification
        """
        subject = email_data.get("subject", "").lower()
        content_lower = content.lower()
        sender_email = self._parse_sender(email_data.get("from", ""))["email"].lower()
        
        # Check for auto-replies
        for indicator in self.auto_reply_indicators:
            if indicator in subject or indicator in content_lower:
                return "auto_reply"
        
        # Check for system emails
        if any(keyword in sender_email for keyword in ["noreply", "no-reply", "mailer-daemon", "postmaster"]):
            return "system_email"
        
        # Check for newsletters/marketing
        if any(keyword in content_lower for keyword in ["unsubscribe", "newsletter", "marketing", "promotional"]):
            return "newsletter"
        
        # Check for support requests
        support_keywords = [
            "help", "problem", "issue", "error", "bug", "support", "assistance",
            "question", "trouble", "broken", "not working", "failed"
        ]
        
        if any(keyword in subject or keyword in content_lower for keyword in support_keywords):
            return "support_request"
        
        # Default to general inquiry
        return "general_inquiry"
    
    def _extract_metadata(self, email_data: Dict[str, Any], content: str) -> Dict[str, Any]:
        """Extract additional metadata from email"""
        metadata = {
            "word_count": len(content.split()),
            "line_count": len(content.split('\n')),
            "has_urls": bool(re.search(r'https?://', content)),
            "has_phone": bool(re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', content)),
            "has_email": bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)),
            "urgency_indicators": [],
            "sentiment_indicators": []
        }
        
        # Check for urgency indicators
        urgency_words = ["urgent", "asap", "immediately", "emergency", "critical", "high priority"]
        for word in urgency_words:
            if word in content.lower():
                metadata["urgency_indicators"].append(word)
        
        # Basic sentiment indicators
        positive_words = ["thank", "great", "excellent", "love", "perfect", "awesome"]
        negative_words = ["terrible", "awful", "hate", "worst", "angry", "frustrated"]
        
        for word in positive_words:
            if word in content.lower():
                metadata["sentiment_indicators"].append(f"positive:{word}")
        
        for word in negative_words:
            if word in content.lower():
                metadata["sentiment_indicators"].append(f"negative:{word}")
        
        return metadata
    
    def _generate_content_hash(self, subject: str, content: str, sender_email: str) -> str:
        """Generate hash for deduplication"""
        # Normalize content for hashing
        normalized_subject = re.sub(r'\W+', '', subject.lower())
        normalized_content = re.sub(r'\W+', '', content.lower())
        
        # Create hash from subject + content + sender
        hash_input = f"{normalized_subject}|{normalized_content}|{sender_email}"
        return hashlib.md5(hash_input.encode('utf-8')).hexdigest()
    
    def _generate_preview(self, content: str, max_length: int = 200) -> str:
        """Generate content preview"""
        if not content:
            return ""
        
        # Clean content for preview
        preview = content.replace('\n', ' ').strip()
        
        if len(preview) <= max_length:
            return preview
        
        # Truncate at word boundary
        truncated = preview[:max_length]
        last_space = truncated.rfind(' ')
        
        if last_space > max_length * 0.8:  # If we can find a good break point
            return truncated[:last_space] + "..."
        
        return truncated + "..."
    
    def _parse_attachments(self, attachments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse and enhance attachment information"""
        parsed_attachments = []
        
        for attachment in attachments:
            parsed = {
                "filename": attachment.get("filename", ""),
                "content_type": attachment.get("content_type", ""),
                "size": attachment.get("size", 0),
                "size_formatted": self._format_file_size(attachment.get("size", 0)),
                "file_extension": self._get_file_extension(attachment.get("filename", "")),
                "is_image": self._is_image_file(attachment.get("content_type", "")),
                "is_document": self._is_document_file(attachment.get("content_type", "")),
                "content_disposition": attachment.get("content_disposition", "")
            }
            parsed_attachments.append(parsed)
        
        return parsed_attachments
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension"""
        if not filename or '.' not in filename:
            return ""
        
        return filename.split('.')[-1].lower()
    
    def _is_image_file(self, content_type: str) -> bool:
        """Check if attachment is an image"""
        return content_type.startswith('image/')
    
    def _is_document_file(self, content_type: str) -> bool:
        """Check if attachment is a document"""
        document_types = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/plain'
        ]
        return content_type in document_types
    
    def is_duplicate_content(self, email1_hash: str, email2_hash: str) -> bool:
        """Check if two emails have duplicate content"""
        return email1_hash == email2_hash
    
    def extract_ticket_info(self, parsed_email: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract ticket-relevant information from parsed email
        
        Args:
            parsed_email: Parsed email data
            
        Returns:
            Dict: Ticket information ready for database storage
        """
        return {
            "title": parsed_email.get("subject", "Email Support Request"),
            "description": parsed_email.get("main_content", ""),
            "priority": self._determine_priority(parsed_email),
            "category": self._determine_category(parsed_email),
            "customer_email": parsed_email.get("sender", {}).get("email", ""),
            "customer_name": parsed_email.get("sender", {}).get("name", ""),
            "source": "email",
            "source_metadata": {
                "message_id": parsed_email.get("message_id"),
                "mailbox": parsed_email.get("mailbox"),
                "email_type": parsed_email.get("email_type"),
                "has_attachments": len(parsed_email.get("attachments", [])) > 0,
                "attachment_count": len(parsed_email.get("attachments", [])),
                "content_hash": parsed_email.get("content_hash")
            }
        }
    
    def _determine_priority(self, parsed_email: Dict[str, Any]) -> str:
        """Determine ticket priority based on email content"""
        urgency_indicators = parsed_email.get("metadata", {}).get("urgency_indicators", [])
        
        if urgency_indicators:
            return "high"
        
        # Check subject for priority keywords
        subject = parsed_email.get("subject", "").lower()
        if any(word in subject for word in ["urgent", "emergency", "critical"]):
            return "high"
        
        return "medium"
    
    def _determine_category(self, parsed_email: Dict[str, Any]) -> str:
        """Determine ticket category based on email content"""
        subject = parsed_email.get("subject", "").lower()
        content = parsed_email.get("main_content", "").lower()
        
        # Simple keyword-based categorization
        if any(word in subject or word in content for word in ["billing", "payment", "charge", "invoice"]):
            return "billing"
        
        if any(word in subject or word in content for word in ["bug", "error", "broken", "not working"]):
            return "technical"
        
        if any(word in subject or word in content for word in ["feature", "request", "enhancement"]):
            return "feature_request"
        
        if any(word in subject or word in content for word in ["login", "password", "account", "access"]):
            return "authentication"
        
        return "general"