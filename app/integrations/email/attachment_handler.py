"""
Email Attachment Handler
Advanced attachment processing, metadata extraction, and file analysis
"""

import os
import logging
import mimetypes
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import hashlib
import base64
import tempfile

logger = logging.getLogger(__name__)

class AttachmentHandler:
    """Handles email attachment processing and metadata extraction"""
    
    # File type categories
    IMAGE_TYPES = {
        'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/bmp', 
        'image/tiff', 'image/webp', 'image/svg+xml'
    }
    
    DOCUMENT_TYPES = {
        'application/pdf', 'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'text/plain', 'text/csv', 'application/rtf'
    }
    
    ARCHIVE_TYPES = {
        'application/zip', 'application/x-rar-compressed', 'application/x-tar',
        'application/gzip', 'application/x-7z-compressed'
    }
    
    # Security-sensitive file types
    EXECUTABLE_TYPES = {
        'application/x-executable', 'application/x-msdos-program',
        'application/x-msdownload', 'application/octet-stream'
    }
    
    SCRIPT_TYPES = {
        'application/javascript', 'text/javascript', 'application/x-sh',
        'application/x-python-code', 'text/x-python'
    }
    
    def __init__(self, storage_config: Optional[Dict[str, Any]] = None):
        """
        Initialize attachment handler
        
        Args:
            storage_config: Optional storage configuration for saving attachments
        """
        self.storage_config = storage_config or {}
        self.temp_dir = tempfile.gettempdir()
        
        # File size limits (in bytes)
        self.max_file_size = self.storage_config.get("max_file_size", 25 * 1024 * 1024)  # 25MB
        self.max_total_size = self.storage_config.get("max_total_size", 100 * 1024 * 1024)  # 100MB
        
        # Security settings
        self.allow_executables = self.storage_config.get("allow_executables", False)
        self.scan_for_malware = self.storage_config.get("scan_for_malware", False)
        
    def process_attachments(self, email_message, parsed_email: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process all attachments in an email message
        
        Args:
            email_message: Email message object from imaplib
            parsed_email: Parsed email data
            
        Returns:
            List[Dict]: Processed attachment metadata
        """
        processed_attachments = []
        total_size = 0
        
        try:
            if email_message.is_multipart():
                for part in email_message.walk():
                    if self._is_attachment(part):
                        attachment = self._process_single_attachment(part, parsed_email)
                        if attachment:
                            processed_attachments.append(attachment)
                            total_size += attachment.get("size", 0)
                            
                            # Check total size limit
                            if total_size > self.max_total_size:
                                logger.warning(f"Total attachment size exceeds limit: {total_size}")
                                attachment["size_limit_exceeded"] = True
                                break
            
            # Add summary information
            summary = self._generate_attachment_summary(processed_attachments)
            
            return {
                "attachments": processed_attachments,
                "summary": summary
            }
            
        except Exception as e:
            logger.error(f"Error processing attachments: {e}")
            return {
                "attachments": [],
                "summary": {"error": str(e)},
                "processing_error": True
            }
    
    def _is_attachment(self, part) -> bool:
        """Check if email part is an attachment"""
        content_disposition = str(part.get('Content-Disposition', ''))
        return 'attachment' in content_disposition or part.get_filename() is not None
    
    def _process_single_attachment(self, part, parsed_email: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single email attachment
        
        Args:
            part: Email part containing attachment
            parsed_email: Parsed email data for context
            
        Returns:
            Optional[Dict]: Processed attachment metadata
        """
        try:
            # Get basic information
            filename = self._get_safe_filename(part.get_filename())
            if not filename:
                filename = f"attachment_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            content_type = part.get_content_type() or "application/octet-stream"
            content_disposition = str(part.get('Content-Disposition', ''))
            
            # Get attachment content
            payload = part.get_payload(decode=True)
            if payload is None:
                logger.warning(f"Could not decode attachment: {filename}")
                return None
            
            size = len(payload)
            
            # Check file size limit
            if size > self.max_file_size:
                logger.warning(f"Attachment {filename} exceeds size limit: {size}")
                return {
                    "filename": filename,
                    "content_type": content_type,
                    "size": size,
                    "error": "File size exceeds limit",
                    "size_limit_exceeded": True
                }
            
            # Generate file hash
            file_hash = hashlib.md5(payload).hexdigest()
            
            # Extract detailed metadata
            metadata = self._extract_file_metadata(payload, filename, content_type)
            
            # Perform security analysis
            security_info = self._analyze_security(payload, filename, content_type)
            
            # Determine file category
            file_category = self._categorize_file(content_type, filename)
            
            attachment_data = {
                "filename": filename,
                "original_filename": part.get_filename(),
                "content_type": content_type,
                "size": size,
                "size_formatted": self._format_file_size(size),
                "file_hash": file_hash,
                "file_extension": self._get_file_extension(filename),
                "file_category": file_category,
                "content_disposition": content_disposition,
                "metadata": metadata,
                "security": security_info,
                "processed_at": datetime.utcnow().isoformat(),
                "email_context": {
                    "email_uid": parsed_email.get("uid"),
                    "email_subject": parsed_email.get("subject"),
                    "sender_email": parsed_email.get("sender", {}).get("email")
                }
            }
            
            # Optionally save attachment to storage
            if self.storage_config.get("save_attachments", False):
                storage_info = self._save_attachment(payload, filename, attachment_data)
                attachment_data["storage"] = storage_info
            
            return attachment_data
            
        except Exception as e:
            logger.error(f"Error processing attachment {part.get_filename()}: {e}")
            return {
                "filename": part.get_filename() or "unknown",
                "error": str(e),
                "processing_failed": True
            }
    
    def _get_safe_filename(self, filename: Optional[str]) -> str:
        """Get safe filename by removing dangerous characters"""
        if not filename:
            return ""
        
        # Decode filename if needed
        if hasattr(filename, 'decode'):
            try:
                filename = filename.decode('utf-8', errors='ignore')
            except:
                pass
        
        # Remove path separators and dangerous characters
        import re
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', str(filename))
        safe_filename = safe_filename.strip('. ')
        
        # Limit length
        if len(safe_filename) > 255:
            name, ext = os.path.splitext(safe_filename)
            safe_filename = name[:240] + ext
        
        return safe_filename
    
    def _extract_file_metadata(self, payload: bytes, filename: str, content_type: str) -> Dict[str, Any]:
        """
        Extract detailed file metadata
        
        Args:
            payload: File content bytes
            filename: Filename
            content_type: MIME content type
            
        Returns:
            Dict: File metadata
        """
        metadata = {
            "mime_type_detected": self._detect_mime_type(payload, filename),
            "magic_bytes": payload[:16].hex() if len(payload) >= 16 else payload.hex(),
            "charset_detected": None,
            "creation_date": None,
            "modification_date": None
        }
        
        # Text file analysis
        if content_type.startswith('text/') or content_type == 'application/json':
            try:
                text_content = payload.decode('utf-8', errors='ignore')
                metadata.update({
                    "charset_detected": "utf-8",
                    "line_count": len(text_content.split('\n')),
                    "word_count": len(text_content.split()),
                    "character_count": len(text_content)
                })
            except:
                pass
        
        # Image file analysis
        if content_type.startswith('image/'):
            try:
                image_info = self._analyze_image(payload)
                metadata["image_info"] = image_info
            except Exception as e:
                logger.debug(f"Could not analyze image {filename}: {e}")
        
        # PDF analysis
        if content_type == 'application/pdf':
            try:
                pdf_info = self._analyze_pdf(payload)
                metadata["pdf_info"] = pdf_info
            except Exception as e:
                logger.debug(f"Could not analyze PDF {filename}: {e}")
        
        return metadata
    
    def _detect_mime_type(self, payload: bytes, filename: str) -> str:
        """Detect MIME type from file content and filename"""
        # Try to detect from content (magic bytes)
        if payload.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'image/png'
        elif payload.startswith(b'\xFF\xD8\xFF'):
            return 'image/jpeg'
        elif payload.startswith(b'%PDF-'):
            return 'application/pdf'
        elif payload.startswith(b'PK\x03\x04'):
            # ZIP-based formats
            if filename.endswith('.docx'):
                return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            elif filename.endswith('.xlsx'):
                return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            else:
                return 'application/zip'
        
        # Fallback to filename-based detection
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or 'application/octet-stream'
    
    def _analyze_image(self, payload: bytes) -> Dict[str, Any]:
        """Analyze image file (basic analysis without external libraries)"""
        info = {"format": "unknown", "size": len(payload)}
        
        # PNG analysis
        if payload.startswith(b'\x89PNG\r\n\x1a\n'):
            info["format"] = "PNG"
            if len(payload) >= 24:
                width = int.from_bytes(payload[16:20], 'big')
                height = int.from_bytes(payload[20:24], 'big')
                info["dimensions"] = f"{width}x{height}"
        
        # JPEG analysis
        elif payload.startswith(b'\xFF\xD8\xFF'):
            info["format"] = "JPEG"
            # Basic JPEG dimension extraction would require more complex parsing
        
        return info
    
    def _analyze_pdf(self, payload: bytes) -> Dict[str, Any]:
        """Basic PDF analysis"""
        info = {"format": "PDF", "size": len(payload)}
        
        try:
            # Look for PDF version
            if payload.startswith(b'%PDF-'):
                version_line = payload[:20].decode('ascii', errors='ignore')
                if 'PDF-' in version_line:
                    version = version_line.split('PDF-')[1][:3]
                    info["version"] = version
        except:
            pass
        
        return info
    
    def _analyze_security(self, payload: bytes, filename: str, content_type: str) -> Dict[str, Any]:
        """
        Analyze file for security concerns
        
        Returns:
            Dict: Security analysis results
        """
        security = {
            "risk_level": "low",
            "warnings": [],
            "is_executable": False,
            "is_script": False,
            "contains_macros": False,
            "suspicious_patterns": []
        }
        
        # Check for executable files
        if content_type in self.EXECUTABLE_TYPES or filename.endswith(('.exe', '.bat', '.cmd', '.com')):
            security["is_executable"] = True
            security["risk_level"] = "high"
            security["warnings"].append("File is executable")
        
        # Check for script files
        if content_type in self.SCRIPT_TYPES or filename.endswith(('.js', '.py', '.sh', '.ps1')):
            security["is_script"] = True
            security["risk_level"] = "medium"
            security["warnings"].append("File contains script code")
        
        # Check for Office macros (basic detection)
        if filename.endswith(('.docm', '.xlsm', '.pptm')) or b'vbaProject' in payload:
            security["contains_macros"] = True
            security["risk_level"] = "medium"
            security["warnings"].append("File may contain macros")
        
        # Look for suspicious patterns
        suspicious_patterns = [
            b'javascript:', b'vbscript:', b'<script', b'eval(',
            b'document.write', b'window.open', b'ActiveX'
        ]
        
        for pattern in suspicious_patterns:
            if pattern in payload.lower():
                security["suspicious_patterns"].append(pattern.decode('ascii', errors='ignore'))
                if security["risk_level"] == "low":
                    security["risk_level"] = "medium"
        
        return security
    
    def _categorize_file(self, content_type: str, filename: str) -> str:
        """Categorize file type"""
        if content_type in self.IMAGE_TYPES:
            return "image"
        elif content_type in self.DOCUMENT_TYPES:
            return "document"
        elif content_type in self.ARCHIVE_TYPES:
            return "archive"
        elif content_type in self.EXECUTABLE_TYPES:
            return "executable"
        elif content_type in self.SCRIPT_TYPES:
            return "script"
        elif content_type.startswith('text/'):
            return "text"
        elif content_type.startswith('audio/'):
            return "audio"
        elif content_type.startswith('video/'):
            return "video"
        else:
            return "other"
    
    def _save_attachment(self, payload: bytes, filename: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save attachment to storage (filesystem or cloud)
        
        Returns:
            Dict: Storage information
        """
        try:
            storage_method = self.storage_config.get("method", "filesystem")
            
            if storage_method == "filesystem":
                return self._save_to_filesystem(payload, filename, metadata)
            elif storage_method == "s3":
                return self._save_to_s3(payload, filename, metadata)
            else:
                return {"error": f"Unsupported storage method: {storage_method}"}
                
        except Exception as e:
            logger.error(f"Error saving attachment {filename}: {e}")
            return {"error": str(e)}
    
    def _save_to_filesystem(self, payload: bytes, filename: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Save attachment to local filesystem"""
        storage_dir = self.storage_config.get("directory", os.path.join(self.temp_dir, "email_attachments"))
        os.makedirs(storage_dir, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        file_hash = metadata.get("file_hash", "")[:8]
        unique_filename = f"{timestamp}_{file_hash}_{filename}"
        
        file_path = os.path.join(storage_dir, unique_filename)
        
        with open(file_path, 'wb') as f:
            f.write(payload)
        
        return {
            "method": "filesystem",
            "path": file_path,
            "filename": unique_filename,
            "saved_at": datetime.utcnow().isoformat(),
            "size": len(payload)
        }
    
    def _save_to_s3(self, payload: bytes, filename: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Save attachment to AWS S3 (placeholder implementation)"""
        # This would require boto3 and proper AWS configuration
        return {
            "method": "s3",
            "error": "S3 storage not implemented",
            "bucket": self.storage_config.get("s3_bucket"),
            "key": f"attachments/{filename}"
        }
    
    def _generate_attachment_summary(self, attachments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics for all attachments"""
        if not attachments:
            return {
                "total_count": 0,
                "total_size": 0,
                "total_size_formatted": "0 B",
                "categories": {},
                "risk_levels": {},
                "has_high_risk": False
            }
        
        total_size = sum(att.get("size", 0) for att in attachments)
        categories = {}
        risk_levels = {}
        has_high_risk = False
        
        for attachment in attachments:
            # Count categories
            category = attachment.get("file_category", "unknown")
            categories[category] = categories.get(category, 0) + 1
            
            # Count risk levels
            risk_level = attachment.get("security", {}).get("risk_level", "unknown")
            risk_levels[risk_level] = risk_levels.get(risk_level, 0) + 1
            
            if risk_level == "high":
                has_high_risk = True
        
        return {
            "total_count": len(attachments),
            "total_size": total_size,
            "total_size_formatted": self._format_file_size(total_size),
            "categories": categories,
            "risk_levels": risk_levels,
            "has_high_risk": has_high_risk,
            "largest_file": max(attachments, key=lambda x: x.get("size", 0))["filename"] if attachments else None
        }
    
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