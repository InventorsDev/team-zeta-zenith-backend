"""
Email Deduplication Manager
Prevents re-processing of duplicate emails using content hashes and message IDs
"""

import logging
import hashlib
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta
import json
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

class EmailDeduplicationManager:
    """Manages email deduplication to prevent re-processing"""
    
    def __init__(self, db: Session = None, integration_id: int = 0):
        """Initialize deduplication manager with database session"""
        self.db = db
        self.integration_id = integration_id
        
        # Deduplication settings
        self.cache_ttl_hours = 24 * 7  # 7 days
        
        # If no database, fall back to in-memory storage
        if not self.db:
            self.processed_message_ids: Set[str] = set()
            self.processed_content_hashes: Set[str] = set()
            self.processed_emails: Dict[str, Dict[str, Any]] = {}
        else:
            # Create deduplication table if it doesn't exist
            self._ensure_deduplication_table()
    
    def _ensure_deduplication_table(self):
        """Create deduplication table if it doesn't exist"""
        try:
            # Create table with SQLite-compatible syntax
            self.db.execute(text("""
                CREATE TABLE IF NOT EXISTS email_deduplication (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    integration_id INTEGER NOT NULL,
                    message_id TEXT,
                    content_hash TEXT,
                    subject TEXT,
                    sender_email TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create indexes separately (SQLite style)
            self.db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_email_dedup_message_id 
                ON email_deduplication (message_id)
            """))
            
            self.db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_email_dedup_content_hash 
                ON email_deduplication (content_hash)
            """))
            
            self.db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_email_dedup_integration_processed 
                ON email_deduplication (integration_id, processed_at)
            """))
            
            self.db.commit()
            logger.info("Email deduplication table and indexes created successfully")
        except Exception as e:
            logger.warning(f"Deduplication table creation error: {e}")
            self.db.rollback()
        
    def is_duplicate(self, parsed_email: Dict[str, Any]) -> bool:
        """
        Check if email is a duplicate based on multiple criteria
        
        Args:
            parsed_email: Parsed email data
            
        Returns:
            bool: True if email is duplicate
        """
        message_id = parsed_email.get("message_id", "")
        content_hash = parsed_email.get("content_hash", "")
        
        # Check by message ID (most reliable for true duplicates)
        if message_id and self._is_message_id_processed(message_id):
            logger.debug(f"Duplicate found by message ID: {message_id}")
            return True
        
        # Check by content hash (catches forwarded/re-sent emails)
        if content_hash and self._is_content_hash_processed(content_hash):
            logger.debug(f"Duplicate found by content hash: {content_hash}")
            return True
        
        # Advanced duplicate detection
        if self._is_advanced_duplicate(parsed_email):
            return True
        
        return False
    
    def mark_processed(self, parsed_email: Dict[str, Any]) -> None:
        """
        Mark email as processed to prevent future re-processing
        
        Args:
            parsed_email: Parsed email data
        """
        message_id = parsed_email.get("message_id", "")
        content_hash = parsed_email.get("content_hash", "")
        
        if not self.db:
            # In-memory fallback
            if message_id:
                self.processed_message_ids.add(message_id)
            if content_hash:
                self.processed_content_hashes.add(content_hash)
            
            # Store full email data for advanced duplicate detection
            unique_key = message_id or content_hash or f"{parsed_email.get('subject', '')}_{parsed_email.get('sender', {}).get('email', '')}"
            if unique_key:
                self.processed_emails[unique_key] = {
                    "message_id": message_id,
                    "content_hash": content_hash,
                    "subject": parsed_email.get("subject", ""),
                    "sender": parsed_email.get("sender", {}),
                    "date": parsed_email.get("date"),
                    "processed_at": datetime.now()
                }
            return
        
        try:
            subject = parsed_email.get("subject", "")
            sender_email = parsed_email.get("sender", {}).get("email", "")
            
            # Insert into deduplication table
            self.db.execute(text("""
                INSERT INTO email_deduplication 
                (integration_id, message_id, content_hash, subject, sender_email)
                VALUES (:integration_id, :message_id, :content_hash, :subject, :sender_email)
            """), {
                "integration_id": self.integration_id,
                "message_id": message_id or None,
                "content_hash": content_hash or None,
                "subject": subject[:1000] if subject else None,  # Truncate if too long
                "sender_email": sender_email[:255] if sender_email else None
            })
            self.db.commit()
            logger.debug(f"Marked email as processed: {message_id or content_hash}")
            
        except Exception as e:
            logger.error(f"Error marking email as processed: {e}")
            self.db.rollback()
        
    
    def _is_message_id_processed(self, message_id: str) -> bool:
        """Check if message ID has been processed"""
        if not message_id:
            return False
            
        if not self.db:
            # In-memory fallback
            return message_id in self.processed_message_ids
        
        try:
            result = self.db.execute(text("""
                SELECT 1 FROM email_deduplication 
                WHERE integration_id = :integration_id 
                AND message_id = :message_id 
                AND processed_at > :cutoff_date
                LIMIT 1
            """), {
                "integration_id": self.integration_id,
                "message_id": message_id,
                "cutoff_date": datetime.now() - timedelta(hours=self.cache_ttl_hours)
            })
            return result.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking message ID: {e}")
            return False
    
    def _is_content_hash_processed(self, content_hash: str) -> bool:
        """Check if content hash has been processed"""
        if not content_hash:
            return False
            
        if not self.db:
            # In-memory fallback
            return content_hash in self.processed_content_hashes
        
        try:
            result = self.db.execute(text("""
                SELECT 1 FROM email_deduplication 
                WHERE integration_id = :integration_id 
                AND content_hash = :content_hash 
                AND processed_at > :cutoff_date
                LIMIT 1
            """), {
                "integration_id": self.integration_id,
                "content_hash": content_hash,
                "cutoff_date": datetime.now() - timedelta(hours=self.cache_ttl_hours)
            })
            return result.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking content hash: {e}")
            return False
    
    def _is_advanced_duplicate(self, parsed_email: Dict[str, Any]) -> bool:
        """
        Advanced duplicate detection using multiple signals
        
        Args:
            parsed_email: Parsed email data
            
        Returns:
            bool: True if advanced duplicate patterns detected
        """
        # Check for near-identical emails from same sender
        sender_email = parsed_email.get("sender", {}).get("email", "").lower()
        subject = parsed_email.get("subject", "").strip()
        email_date = parsed_email.get("date")
        
        if not sender_email or not subject:
            return False
        
        # Look for similar emails from same sender within time window
        if not self.db:
            # In-memory mode: use processed_emails dict
            stored_emails = self.processed_emails.values()
        else:
            # Database mode: query for similar emails (simplified approach)
            try:
                result = self.db.execute(text("""
                    SELECT subject, sender_email FROM email_deduplication 
                    WHERE integration_id = :integration_id 
                    AND sender_email = :sender_email 
                    AND processed_at > :cutoff_date
                    LIMIT 10
                """), {
                    "integration_id": self.integration_id,
                    "sender_email": sender_email,
                    "cutoff_date": datetime.now() - timedelta(hours=1)  # 1 hour window
                })
                
                # Convert database results to similar format
                stored_emails = []
                for row in result:
                    stored_emails.append({
                        "sender": {"email": row[1] or ""},
                        "subject": row[0] or "",
                        "date": None  # We don't store dates in our simple schema
                    })
            except Exception as e:
                logger.error(f"Error in advanced duplicate detection: {e}")
                return False
        
        for stored_email in stored_emails:
            stored_sender = stored_email.get("sender", {}).get("email", "").lower()
            stored_subject = stored_email.get("subject", "").strip()
            stored_date = stored_email.get("date")
            
            # Same sender check
            if stored_sender != sender_email:
                continue
            
            # Subject similarity check
            if not self._are_subjects_similar(subject, stored_subject):
                continue
            
            # Time proximity check (within 1 hour)
            if email_date and stored_date:
                try:
                    time_diff = abs((email_date - stored_date).total_seconds())
                    if time_diff > 3600:  # 1 hour
                        continue
                except:
                    continue
            
            logger.debug(f"Advanced duplicate detected: similar email from {sender_email}")
            return True
        
        return False
    
    def _are_subjects_similar(self, subject1: str, subject2: str, threshold: float = 0.9) -> bool:
        """
        Check if two subjects are similar enough to be considered duplicates
        
        Args:
            subject1: First subject
            subject2: Second subject
            threshold: Similarity threshold (0-1)
            
        Returns:
            bool: True if subjects are similar
        """
        if not subject1 or not subject2:
            return False
        
        # Normalize subjects
        norm1 = self._normalize_subject(subject1)
        norm2 = self._normalize_subject(subject2)
        
        if norm1 == norm2:
            return True
        
        # Calculate similarity using simple character overlap
        similarity = self._calculate_string_similarity(norm1, norm2)
        return similarity >= threshold
    
    def _normalize_subject(self, subject: str) -> str:
        """Normalize subject for comparison"""
        import re
        
        # Convert to lowercase
        subject = subject.lower().strip()
        
        # Remove common prefixes
        subject = re.sub(r'^(re|fw|fwd):\s*', '', subject)
        
        # Remove extra whitespace
        subject = re.sub(r'\s+', ' ', subject)
        
        # Remove common punctuation
        subject = re.sub(r'[^\w\s]', '', subject)
        
        return subject.strip()
    
    def _calculate_string_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings using character overlap
        
        Returns:
            float: Similarity score (0-1)
        """
        if not str1 or not str2:
            return 0.0
        
        if str1 == str2:
            return 1.0
        
        # Simple character overlap calculation
        set1 = set(str1.split())
        set2 = set(str2.split())
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def _cleanup_cache(self) -> None:
        """Clean up cache to prevent memory issues"""
        if len(self.processed_emails) <= self.max_cache_size:
            return
        
        # Remove old entries
        cutoff_time = datetime.utcnow() - timedelta(hours=self.cache_ttl_hours)
        
        keys_to_remove = []
        for key, email_data in self.processed_emails.items():
            processed_at = email_data.get("processed_at")
            if processed_at and processed_at < cutoff_time:
                keys_to_remove.append(key)
        
        # Remove old entries
        for key in keys_to_remove:
            del self.processed_emails[key]
            
            # Also remove from sets
            message_id = self.processed_emails.get(key, {}).get("message_id")
            content_hash = self.processed_emails.get(key, {}).get("content_hash")
            
            if message_id:
                self.processed_message_ids.discard(message_id)
            if content_hash:
                self.processed_content_hashes.discard(content_hash)
        
        logger.info(f"Cleaned up {len(keys_to_remove)} old cache entries")
    
    def find_potential_duplicates(self, parsed_email: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find all potential duplicates for an email (for analysis)
        
        Args:
            parsed_email: Parsed email data
            
        Returns:
            List[Dict]: List of potential duplicate emails
        """
        duplicates = []
        
        message_id = parsed_email.get("message_id", "")
        content_hash = parsed_email.get("content_hash", "")
        sender_email = parsed_email.get("sender", {}).get("email", "").lower()
        subject = parsed_email.get("subject", "")
        
        for stored_email in self.processed_emails.values():
            duplicate_reasons = []
            
            # Check message ID match
            if message_id and stored_email.get("message_id") == message_id:
                duplicate_reasons.append("exact_message_id")
            
            # Check content hash match
            if content_hash and stored_email.get("content_hash") == content_hash:
                duplicate_reasons.append("exact_content")
            
            # Check sender and subject similarity
            if sender_email and stored_email.get("sender", {}).get("email", "").lower() == sender_email:
                if self._are_subjects_similar(subject, stored_email.get("subject", "")):
                    duplicate_reasons.append("similar_subject_same_sender")
            
            if duplicate_reasons:
                duplicates.append({
                    "stored_email": stored_email,
                    "duplicate_reasons": duplicate_reasons,
                    "confidence": len(duplicate_reasons) / 3.0  # Normalize to 0-1
                })
        
        # Sort by confidence
        duplicates.sort(key=lambda x: x["confidence"], reverse=True)
        
        return duplicates
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get deduplication statistics
        
        Returns:
            Dict: Deduplication stats
        """
        return {
            "processed_message_ids": len(self.processed_message_ids),
            "processed_content_hashes": len(self.processed_content_hashes),
            "total_processed_emails": len(self.processed_emails),
            "cache_size_limit": self.max_cache_size,
            "cache_ttl_hours": self.cache_ttl_hours,
            "oldest_entry": self._get_oldest_entry_date(),
            "newest_entry": self._get_newest_entry_date()
        }
    
    def _get_oldest_entry_date(self) -> Optional[str]:
        """Get date of oldest cache entry"""
        if not self.processed_emails:
            return None
        
        oldest_date = min(
            email_data.get("processed_at", datetime.utcnow())
            for email_data in self.processed_emails.values()
        )
        
        return oldest_date.isoformat() if oldest_date else None
    
    def _get_newest_entry_date(self) -> Optional[str]:
        """Get date of newest cache entry"""
        if not self.processed_emails:
            return None
        
        newest_date = max(
            email_data.get("processed_at", datetime.utcnow())
            for email_data in self.processed_emails.values()
        )
        
        return newest_date.isoformat() if newest_date else None
    
    def clear_cache(self) -> None:
        """Clear all deduplication cache (for testing/reset)"""
        self.processed_message_ids.clear()
        self.processed_content_hashes.clear()
        self.processed_emails.clear()
        logger.info("Deduplication cache cleared")
    
    def export_cache(self) -> Dict[str, Any]:
        """
        Export deduplication cache for persistence
        
        Returns:
            Dict: Serializable cache data
        """
        return {
            "processed_message_ids": list(self.processed_message_ids),
            "processed_content_hashes": list(self.processed_content_hashes),
            "processed_emails": {
                key: {
                    **data,
                    "processed_at": data["processed_at"].isoformat() if data.get("processed_at") else None,
                    "date": data["date"].isoformat() if data.get("date") else None
                }
                for key, data in self.processed_emails.items()
            },
            "exported_at": datetime.utcnow().isoformat()
        }
    
    def import_cache(self, cache_data: Dict[str, Any]) -> None:
        """
        Import deduplication cache from persistence
        
        Args:
            cache_data: Previously exported cache data
        """
        try:
            # Import message IDs
            if "processed_message_ids" in cache_data:
                self.processed_message_ids = set(cache_data["processed_message_ids"])
            
            # Import content hashes
            if "processed_content_hashes" in cache_data:
                self.processed_content_hashes = set(cache_data["processed_content_hashes"])
            
            # Import processed emails
            if "processed_emails" in cache_data:
                for key, data in cache_data["processed_emails"].items():
                    # Convert date strings back to datetime objects
                    if data.get("processed_at"):
                        try:
                            data["processed_at"] = datetime.fromisoformat(data["processed_at"])
                        except:
                            data["processed_at"] = datetime.utcnow()
                    
                    if data.get("date"):
                        try:
                            data["date"] = datetime.fromisoformat(data["date"])
                        except:
                            data["date"] = None
                    
                    self.processed_emails[key] = data
            
            logger.info(f"Imported deduplication cache: {len(self.processed_emails)} entries")
            
        except Exception as e:
            logger.error(f"Error importing deduplication cache: {e}")
            # Don't fail completely, just continue with empty cache