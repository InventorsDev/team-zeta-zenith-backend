"""
API Key Service - Manages API key creation, validation, and lifecycle
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from app.models.api_key import APIKey
from app.core.security import get_password_hash, verify_password
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class APIKeyService:
    """Service for managing API keys"""

    def __init__(self, db: Session):
        self.db = db

    def create_api_key(
        self,
        organization_id: int,
        created_by: int,
        name: str,
        scopes: List[str],
        description: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        is_test_key: bool = False,
        ip_whitelist: Optional[List[str]] = None,
        rate_limit: Optional[int] = None,
    ) -> tuple[APIKey, str]:
        """
        Create a new API key

        Args:
            organization_id: Organization ID
            created_by: User ID creating the key
            name: Human-readable name
            scopes: List of permission scopes
            description: Optional description
            expires_in_days: Optional expiration (None = never expires)
            is_test_key: Whether this is a test/sandbox key
            ip_whitelist: Optional list of allowed IP addresses
            rate_limit: Optional custom rate limit

        Returns:
            (APIKey object, plain_text_key)
            Note: plain_text_key is only returned once and never stored
        """
        # Generate key
        if is_test_key:
            plain_key = APIKey.generate_test_key()
        else:
            plain_key = APIKey.generate_key()

        # Hash the key for storage
        key_hash = get_password_hash(plain_key)

        # Extract prefix for identification
        key_prefix = APIKey.extract_prefix(plain_key)

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Create API key record
        api_key = APIKey(
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            organization_id=organization_id,
            created_by=created_by,
            scopes=scopes,
            description=description,
            expires_at=expires_at,
            ip_whitelist=ip_whitelist,
            rate_limit=rate_limit,
            is_active=True,
        )

        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)

        # Log API key creation
        audit_service = AuditService(self.db)
        audit_service.log_action(
            action="api_key.create",
            status="success",
            user_id=created_by,
            organization_id=organization_id,
            resource_type="api_key",
            resource_id=str(api_key.id),
            severity="info",
            details={
                "key_name": name,
                "key_prefix": key_prefix,
                "scopes": scopes,
                "expires_at": expires_at.isoformat() if expires_at else None,
            }
        )

        logger.info(f"Created API key '{name}' (ID: {api_key.id}) for org {organization_id}")

        # Return both the database record and the plain key
        # WARNING: This is the only time the plain key is available
        return api_key, plain_key

    def validate_api_key(
        self,
        plain_key: str,
        required_scopes: Optional[List[str]] = None,
        client_ip: Optional[str] = None,
    ) -> Optional[APIKey]:
        """
        Validate an API key and check permissions

        Args:
            plain_key: The API key to validate
            required_scopes: Optional list of required scopes
            client_ip: Optional client IP for whitelist check

        Returns:
            APIKey object if valid, None otherwise
        """
        try:
            # Extract prefix for faster lookup
            key_prefix = APIKey.extract_prefix(plain_key)

            # Find keys with matching prefix
            possible_keys = self.db.query(APIKey).filter(
                APIKey.key_prefix == key_prefix,
                APIKey.is_active == True
            ).all()

            # Check each possible key (there should only be one, but be safe)
            for api_key in possible_keys:
                # Skip expired keys
                if api_key.is_expired:
                    continue

                # Verify the key hash
                if verify_password(plain_key, api_key.key_hash):
                    # Check IP whitelist if configured
                    if api_key.ip_whitelist and client_ip:
                        if client_ip not in api_key.ip_whitelist:
                            logger.warning(
                                f"API key {api_key.key_prefix} blocked - IP {client_ip} not whitelisted"
                            )
                            return None

                    # Check required scopes
                    if required_scopes:
                        if not all(scope in api_key.scopes for scope in required_scopes):
                            logger.warning(
                                f"API key {api_key.key_prefix} lacks required scopes: {required_scopes}"
                            )
                            return None

                    # Update usage tracking
                    api_key.usage_count += 1
                    api_key.last_used_at = datetime.utcnow()
                    self.db.commit()

                    return api_key

            logger.warning(f"Invalid API key attempt with prefix: {key_prefix}")
            return None

        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return None

    def get_api_keys(
        self,
        organization_id: int,
        include_inactive: bool = False
    ) -> List[APIKey]:
        """Get all API keys for an organization"""
        query = self.db.query(APIKey).filter(
            APIKey.organization_id == organization_id
        )

        if not include_inactive:
            query = query.filter(APIKey.is_active == True)

        return query.order_by(APIKey.created_at.desc()).all()

    def get_api_key(self, key_id: int, organization_id: int) -> Optional[APIKey]:
        """Get a specific API key"""
        return self.db.query(APIKey).filter(
            APIKey.id == key_id,
            APIKey.organization_id == organization_id
        ).first()

    def revoke_api_key(
        self,
        key_id: int,
        organization_id: int,
        revoked_by: int
    ) -> bool:
        """
        Revoke (deactivate) an API key

        Args:
            key_id: API key ID
            organization_id: Organization ID (for security check)
            revoked_by: User ID revoking the key

        Returns:
            True if successful, False otherwise
        """
        api_key = self.get_api_key(key_id, organization_id)
        if not api_key:
            return False

        api_key.is_active = False
        self.db.commit()

        # Log revocation
        audit_service = AuditService(self.db)
        audit_service.log_action(
            action="api_key.revoke",
            status="success",
            user_id=revoked_by,
            organization_id=organization_id,
            resource_type="api_key",
            resource_id=str(key_id),
            severity="warning",
            details={
                "key_name": api_key.name,
                "key_prefix": api_key.key_prefix,
            }
        )

        logger.info(f"Revoked API key {key_id} ({api_key.name}) for org {organization_id}")
        return True

    def delete_api_key(
        self,
        key_id: int,
        organization_id: int,
        deleted_by: int
    ) -> bool:
        """
        Permanently delete an API key

        Args:
            key_id: API key ID
            organization_id: Organization ID (for security check)
            deleted_by: User ID deleting the key

        Returns:
            True if successful, False otherwise
        """
        api_key = self.get_api_key(key_id, organization_id)
        if not api_key:
            return False

        # Log deletion before removing
        audit_service = AuditService(self.db)
        audit_service.log_action(
            action="api_key.delete",
            status="success",
            user_id=deleted_by,
            organization_id=organization_id,
            resource_type="api_key",
            resource_id=str(key_id),
            severity="warning",
            details={
                "key_name": api_key.name,
                "key_prefix": api_key.key_prefix,
            }
        )

        self.db.delete(api_key)
        self.db.commit()

        logger.info(f"Deleted API key {key_id} ({api_key.name}) for org {organization_id}")
        return True

    def cleanup_expired_keys(self) -> int:
        """
        Deactivate expired API keys

        Returns:
            Number of keys deactivated
        """
        expired_keys = self.db.query(APIKey).filter(
            APIKey.is_active == True,
            APIKey.expires_at.isnot(None),
            APIKey.expires_at < datetime.utcnow()
        ).all()

        count = 0
        for key in expired_keys:
            key.is_active = False
            count += 1

        if count > 0:
            self.db.commit()
            logger.info(f"Deactivated {count} expired API keys")

        return count

    def get_key_stats(self, organization_id: int) -> Dict[str, Any]:
        """Get API key usage statistics for an organization"""
        total_keys = self.db.query(APIKey).filter(
            APIKey.organization_id == organization_id
        ).count()

        active_keys = self.db.query(APIKey).filter(
            APIKey.organization_id == organization_id,
            APIKey.is_active == True
        ).count()

        expired_keys = self.db.query(APIKey).filter(
            APIKey.organization_id == organization_id,
            APIKey.expires_at.isnot(None),
            APIKey.expires_at < datetime.utcnow()
        ).count()

        return {
            "total_keys": total_keys,
            "active_keys": active_keys,
            "inactive_keys": total_keys - active_keys,
            "expired_keys": expired_keys,
        }
