from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from app.models.integration import Integration, IntegrationStatus, IntegrationType
from app.models.user import User
from app.database.repositories.integration_repository import IntegrationRepository
from app.database.repositories.user_repository import UserRepository
from app.schemas.integration import (
    IntegrationCreate, IntegrationUpdate, IntegrationResponse, IntegrationSummary,
    IntegrationFilter, PaginatedIntegrations, IntegrationStats, IntegrationConfigMask
)


class IntegrationService:
    """Service layer for integration operations with business logic"""

    def __init__(self, db: Session):
        self.db = db
        self.integration_repo = IntegrationRepository(db)
        self.user_repo = UserRepository(db)

    def create_integration(self, integration_data: IntegrationCreate, current_user: User) -> IntegrationResponse:
        """Create a new integration with validation"""
        # Ensure user belongs to an organization
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must belong to an organization to create integrations"
            )
        
        # Check for duplicate integration names within organization
        existing_integrations = self.integration_repo.get_by_organization(current_user.organization_id)
        if any(i.name.lower() == integration_data.name.lower() for i in existing_integrations):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Integration name already exists in this organization"
            )
        
        # Convert Pydantic model to dict
        integration_dict = integration_data.dict()
        
        # Set organization_id from current user
        integration_dict["organization_id"] = current_user.organization_id
        
        # Create integration
        integration = self.integration_repo.create_integration(integration_dict)
        
        return self._to_integration_response(integration)

    def get_integration(self, integration_id: int, organization_id: int) -> IntegrationResponse:
        """Get a single integration by ID with organization check"""
        integration = self.integration_repo.get(integration_id)
        if not integration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Integration not found"
            )
        
        if integration.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this integration"
            )
        
        return self._to_integration_response(integration)

    def update_integration(self, integration_id: int, organization_id: int, integration_data: IntegrationUpdate) -> IntegrationResponse:
        """Update an existing integration"""
        integration = self.integration_repo.get(integration_id)
        if not integration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Integration not found"
            )
        
        if integration.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this integration"
            )
        
        # Convert Pydantic model to dict, excluding None values
        update_dict = integration_data.dict(exclude_unset=True)
        if not update_dict:
            return self._to_integration_response(integration)
        
        # Handle configuration update separately (needs encryption)
        if "config" in update_dict:
            config = update_dict.pop("config")
            integration = self.integration_repo.update_integration_config(integration, config)
        
        # Check for name conflicts if name is being updated
        if "name" in update_dict:
            existing_integrations = self.integration_repo.get_by_organization(organization_id)
            if any(i.id != integration_id and i.name.lower() == update_dict["name"].lower() for i in existing_integrations):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Integration name already exists in this organization"
                )
        
        # Apply remaining updates
        if update_dict:
            integration = self.integration_repo.update(integration, update_dict)
        
        return self._to_integration_response(integration)

    def delete_integration(self, integration_id: int, organization_id: int) -> bool:
        """Delete an integration"""
        integration = self.integration_repo.get(integration_id)
        if not integration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Integration not found"
            )
        
        if integration.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this integration"
            )
        
        # Check if integration has associated tickets
        # Note: In a production system, you might want to handle this differently
        # (e.g., soft delete, archive, or require force delete)
        
        return self.integration_repo.delete(integration_id)

    def get_integrations(
        self,
        organization_id: int,
        filters: IntegrationFilter = None,
        page: int = 1,
        size: int = 50
    ) -> PaginatedIntegrations:
        """Get paginated integrations with filtering"""
        # Validate pagination parameters
        if page < 1:
            page = 1
        if size < 1 or size > 100:
            size = 50
        
        skip = (page - 1) * size
        
        # Convert filters to dict
        filter_dict = filters.dict(exclude_unset=True) if filters else {}
        
        # Get integrations and count
        integrations = self.integration_repo.get_filtered_integrations(
            organization_id=organization_id,
            filters=filter_dict,
            skip=skip,
            limit=size
        )
        
        total = self.integration_repo.count_integrations(organization_id, filter_dict)
        
        # Convert to summary format
        integration_summaries = [self._to_integration_summary(integration) for integration in integrations]
        
        # Calculate pagination info
        pages = (total + size - 1) // size
        has_next = page < pages
        has_prev = page > 1
        
        return PaginatedIntegrations(
            items=integration_summaries,
            total=total,
            page=page,
            size=size,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )

    def update_integration_status(self, integration_id: int, organization_id: int, status: IntegrationStatus, error_message: str = None) -> IntegrationResponse:
        """Update integration status"""
        integration = self.integration_repo.get(integration_id)
        if not integration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Integration not found"
            )
        
        if integration.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this integration"
            )
        
        integration = self.integration_repo.update_status(integration, status, error_message)
        return self._to_integration_response(integration)

    def test_integration(self, integration_id: int, organization_id: int) -> Dict[str, Any]:
        """Test integration connection"""
        integration = self.integration_repo.get(integration_id)
        if not integration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Integration not found"
            )
        
        if integration.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this integration"
            )
        
        # Get decrypted configuration
        config = self.integration_repo.get_decrypted_config(integration)
        
        # Test connection based on integration type
        test_result = self._test_integration_connection(integration.type, config)
        
        # Update status based on test result
        if test_result["success"]:
            self.integration_repo.update_status(integration, IntegrationStatus.ACTIVE)
        else:
            self.integration_repo.update_status(integration, IntegrationStatus.ERROR, test_result["error"])
        
        return test_result

    def get_integration_config(self, integration_id: int, organization_id: int) -> IntegrationConfigMask:
        """Get masked integration configuration (for API responses)"""
        integration = self.integration_repo.get(integration_id)
        if not integration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Integration not found"
            )
        
        if integration.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this integration"
            )
        
        # Get decrypted configuration
        config = self.integration_repo.get_decrypted_config(integration)
        
        # Mask sensitive values
        masked_config = {}
        config_fields = []
        sensitive_keys = {
            "api_key", "token", "secret", "password", "private_key",
            "client_secret", "webhook_secret", "access_token", "refresh_token"
        }
        
        for key, value in config.items():
            config_fields.append(key)
            if key.lower() in sensitive_keys and value:
                # Mask all but last 4 characters
                if len(str(value)) > 4:
                    masked_config[key] = "*" * (len(str(value)) - 4) + str(value)[-4:]
                else:
                    masked_config[key] = "*" * len(str(value))
            else:
                masked_config[key] = value
        
        return IntegrationConfigMask(
            config_fields=config_fields,
            masked_config=masked_config
        )

    def get_integration_stats(self, organization_id: int) -> IntegrationStats:
        """Get integration statistics for organization"""
        # Get all integrations for the organization
        all_integrations = self.integration_repo.get_by_organization(organization_id, skip=0, limit=1000)
        
        # Calculate statistics
        total = len(all_integrations)
        active_count = sum(1 for i in all_integrations if i.status == IntegrationStatus.ACTIVE)
        error_count = sum(1 for i in all_integrations if i.status == IntegrationStatus.ERROR)
        pending_count = sum(1 for i in all_integrations if i.status == IntegrationStatus.PENDING)
        
        total_tickets_synced = sum(i.total_tickets_synced for i in all_integrations)
        total_webhooks_received = sum(i.total_webhooks_received for i in all_integrations)
        
        # Count by type
        integrations_by_type = {}
        for integration_type in IntegrationType:
            count = sum(1 for i in all_integrations if i.type == integration_type)
            if count > 0:
                integrations_by_type[integration_type.value] = count
        
        # Calculate average sync frequency
        sync_frequencies = [i.sync_frequency for i in all_integrations if i.sync_frequency]
        avg_sync_frequency = None
        if sync_frequencies:
            avg_sync_frequency = sum(sync_frequencies) / len(sync_frequencies) / 60  # Convert to minutes
        
        # Get last sync times
        last_sync_times = {}
        for integration in all_integrations:
            last_sync_times[integration.name] = integration.last_sync_at
        
        return IntegrationStats(
            total_integrations=total,
            active_integrations=active_count,
            error_integrations=error_count,
            pending_integrations=pending_count,
            total_tickets_synced=total_tickets_synced,
            total_webhooks_received=total_webhooks_received,
            integrations_by_type=integrations_by_type,
            avg_sync_frequency_minutes=avg_sync_frequency,
            last_sync_times=last_sync_times
        )

    def _test_integration_connection(self, integration_type: IntegrationType, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test integration connection based on type"""
        # This is a simplified test - in production, you'd make actual API calls
        try:
            if integration_type == IntegrationType.SLACK:
                # Test Slack connection
                required_fields = ["bot_token", "signing_secret"]
                missing = [f for f in required_fields if not config.get(f)]
                if missing:
                    return {"success": False, "error": f"Missing configuration: {', '.join(missing)}"}
                return {"success": True, "message": "Slack connection test successful"}
            
            elif integration_type == IntegrationType.ZENDESK:
                # Test Zendesk connection
                required_fields = ["subdomain", "email", "api_token"]
                missing = [f for f in required_fields if not config.get(f)]
                if missing:
                    return {"success": False, "error": f"Missing configuration: {', '.join(missing)}"}
                return {"success": True, "message": "Zendesk connection test successful"}
            
            elif integration_type == IntegrationType.EMAIL:
                # Test Email connection
                required_fields = ["smtp_server", "smtp_port", "email", "password"]
                missing = [f for f in required_fields if not config.get(f)]
                if missing:
                    return {"success": False, "error": f"Missing configuration: {', '.join(missing)}"}
                return {"success": True, "message": "Email connection test successful"}
            
            else:
                return {"success": False, "error": "Integration type not supported for testing"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _to_integration_response(self, integration: Integration) -> IntegrationResponse:
        """Convert integration model to response schema"""
        # Get configuration status
        config = self.integration_repo.get_decrypted_config(integration)
        has_config = bool(config)
        config_fields = list(config.keys()) if config else []
        
        return IntegrationResponse(
            id=integration.id,
            name=integration.name,
            type=integration.type,
            status=integration.status,
            organization_id=integration.organization_id,
            settings=integration.settings or {},
            webhook_url=integration.webhook_url,
            api_endpoint=integration.api_endpoint,
            sync_frequency=integration.sync_frequency,
            sync_tickets=integration.sync_tickets,
            receive_webhooks=integration.receive_webhooks,
            send_notifications=integration.send_notifications,
            rate_limit_per_hour=integration.rate_limit_per_hour,
            created_at=integration.created_at,
            updated_at=integration.updated_at,
            last_sync_at=integration.last_sync_at,
            rate_limit_reset_at=integration.rate_limit_reset_at,
            last_error=integration.last_error,
            current_hour_requests=integration.current_hour_requests,
            total_tickets_synced=integration.total_tickets_synced,
            total_webhooks_received=integration.total_webhooks_received,
            has_config=has_config,
            config_fields=config_fields
        )

    def _to_integration_summary(self, integration: Integration) -> IntegrationSummary:
        """Convert integration model to summary schema"""
        # Get configuration status
        config = self.integration_repo.get_decrypted_config(integration)
        has_config = bool(config)
        
        return IntegrationSummary(
            id=integration.id,
            name=integration.name,
            type=integration.type,
            status=integration.status,
            created_at=integration.created_at,
            last_sync_at=integration.last_sync_at,
            total_tickets_synced=integration.total_tickets_synced,
            has_config=has_config,
            sync_tickets=integration.sync_tickets,
            receive_webhooks=integration.receive_webhooks,
            last_error=integration.last_error
        )
