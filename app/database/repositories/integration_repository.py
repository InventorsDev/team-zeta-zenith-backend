from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from app.models.integration import Integration, IntegrationType, IntegrationStatus
from app.core.encryption import encrypt_data, decrypt_data
from .base import BaseRepository


class IntegrationRepository(BaseRepository[Integration]):
    """Repository for Integration model with encrypted configuration storage"""

    def __init__(self, db: Session):
        super().__init__(Integration, db)

    def get_by_organization(self, organization_id: int, skip: int = 0, limit: int = 100) -> List[Integration]:
        """Get integrations filtered by organization"""
        return (
            self.db.query(Integration)
            .filter(Integration.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_type(self, organization_id: int, integration_type: IntegrationType) -> List[Integration]:
        """Get integrations by type within organization"""
        return (
            self.db.query(Integration)
            .filter(and_(Integration.organization_id == organization_id, Integration.type == integration_type))
            .all()
        )

    def get_active_integrations(self, organization_id: int) -> List[Integration]:
        """Get active integrations within organization"""
        return (
            self.db.query(Integration)
            .filter(and_(
                Integration.organization_id == organization_id,
                Integration.status == IntegrationStatus.ACTIVE
            ))
            .all()
        )

    def get_by_webhook_url(self, webhook_url: str) -> Optional[Integration]:
        """Get integration by webhook URL (for webhook handling)"""
        return self.db.query(Integration).filter(Integration.webhook_url == webhook_url).first()

    def create_integration(self, integration_data: Dict[str, Any]) -> Integration:
        """Create integration with encrypted config"""
        # Encrypt sensitive configuration data
        if integration_data.get("config"):
            integration_data["config"] = self._encrypt_config(integration_data["config"])
        
        # Set default values
        integration_data.setdefault("status", IntegrationStatus.PENDING)
        integration_data.setdefault("sync_frequency", 300)
        integration_data.setdefault("rate_limit_per_hour", 1000)
        integration_data.setdefault("current_hour_requests", 0)
        integration_data.setdefault("total_tickets_synced", 0)
        integration_data.setdefault("total_webhooks_received", 0)
        integration_data.setdefault("sync_tickets", True)
        integration_data.setdefault("receive_webhooks", True)
        integration_data.setdefault("send_notifications", True)
        
        return self.create(integration_data)

    def update_integration_config(self, integration: Integration, config: Dict[str, Any]) -> Integration:
        """Update integration configuration with encryption"""
        encrypted_config = self._encrypt_config(config)
        return self.update(integration, {"config": encrypted_config})

    def get_decrypted_config(self, integration: Integration) -> Dict[str, Any]:
        """Get decrypted configuration for an integration"""
        if not integration.config:
            return {}
        
        try:
            return self._decrypt_config(integration.config)
        except Exception:
            # If decryption fails, return empty dict
            return {}

    def update_status(self, integration: Integration, status: IntegrationStatus, error_message: str = None) -> Integration:
        """Update integration status and error information"""
        update_data = {"status": status}
        
        if error_message:
            update_data["last_error"] = error_message
        elif status == IntegrationStatus.ACTIVE:
            update_data["last_error"] = None
        
        return self.update(integration, update_data)

    def update_sync_info(self, integration: Integration, success: bool = True, error: str = None) -> Integration:
        """Update sync information after sync attempt"""
        update_data = {
            "last_sync_at": datetime.utcnow()
        }
        
        if success:
            update_data["status"] = IntegrationStatus.ACTIVE
            update_data["last_error"] = None
        else:
            update_data["status"] = IntegrationStatus.ERROR
            if error:
                update_data["last_error"] = error
        
        return self.update(integration, update_data)

    def increment_tickets_synced(self, integration: Integration, count: int = 1) -> Integration:
        """Increment the count of synced tickets"""
        new_count = integration.total_tickets_synced + count
        return self.update(integration, {"total_tickets_synced": new_count})

    def increment_webhooks_received(self, integration: Integration, count: int = 1) -> Integration:
        """Increment the count of received webhooks"""
        new_count = integration.total_webhooks_received + count
        return self.update(integration, {"total_webhooks_received": new_count})

    def update_rate_limit_info(self, integration: Integration, requests_count: int, reset_time: datetime) -> Integration:
        """Update rate limiting information"""
        return self.update(integration, {
            "current_hour_requests": requests_count,
            "rate_limit_reset_at": reset_time
        })

    def get_integrations_for_sync(self, organization_id: int = None) -> List[Integration]:
        """Get integrations that are ready for sync"""
        query = self.db.query(Integration).filter(
            and_(
                Integration.status == IntegrationStatus.ACTIVE,
                Integration.sync_tickets == True
            )
        )
        
        if organization_id:
            query = query.filter(Integration.organization_id == organization_id)
        
        return query.all()

    def get_webhook_integrations(self, organization_id: int = None) -> List[Integration]:
        """Get integrations that can receive webhooks"""
        query = self.db.query(Integration).filter(
            and_(
                Integration.status == IntegrationStatus.ACTIVE,
                Integration.receive_webhooks == True,
                Integration.webhook_url.isnot(None)
            )
        )
        
        if organization_id:
            query = query.filter(Integration.organization_id == organization_id)
        
        return query.all()

    def count_integrations(self, organization_id: int, filters: Dict[str, Any] = None) -> int:
        """Count integrations with optional filters"""
        query = self.db.query(Integration).filter(Integration.organization_id == organization_id)
        
        if filters:
            if filters.get("type"):
                query = query.filter(Integration.type == filters["type"])
            
            if filters.get("status"):
                query = query.filter(Integration.status == filters["status"])
            
            if filters.get("active_only"):
                query = query.filter(Integration.status == IntegrationStatus.ACTIVE)
        
        return query.count()

    def get_filtered_integrations(
        self,
        organization_id: int,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 100
    ) -> List[Integration]:
        """Get integrations with filtering"""
        query = self.db.query(Integration).filter(Integration.organization_id == organization_id)
        
        if filters.get("type"):
            query = query.filter(Integration.type == filters["type"])
        
        if filters.get("status"):
            query = query.filter(Integration.status == filters["status"])
        
        if filters.get("active_only"):
            query = query.filter(Integration.status == IntegrationStatus.ACTIVE)
        
        if filters.get("search"):
            search_term = filters["search"]
            query = query.filter(Integration.name.ilike(f"%{search_term}%"))
        
        return query.offset(skip).limit(limit).all()

    def _encrypt_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive configuration data"""
        if not config:
            return {}
        
        encrypted_config = {}
        sensitive_keys = {
            "api_key", "token", "secret", "password", "private_key",
            "client_secret", "webhook_secret", "access_token", "refresh_token"
        }
        
        for key, value in config.items():
            if key.lower() in sensitive_keys and value:
                encrypted_config[key] = encrypt_data(str(value))
            else:
                encrypted_config[key] = value
        
        return encrypted_config

    def _decrypt_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt sensitive configuration data"""
        if not config:
            return {}
        
        decrypted_config = {}
        sensitive_keys = {
            "api_key", "token", "secret", "password", "private_key",
            "client_secret", "webhook_secret", "access_token", "refresh_token"
        }
        
        for key, value in config.items():
            if key.lower() in sensitive_keys and value:
                try:
                    decrypted_config[key] = decrypt_data(value)
                except Exception:
                    # If decryption fails, skip this field
                    continue
            else:
                decrypted_config[key] = value
        
        return decrypted_config
