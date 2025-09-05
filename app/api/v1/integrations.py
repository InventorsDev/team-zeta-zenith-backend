from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.services.integration_service import IntegrationService
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.integration import IntegrationType, IntegrationStatus
from app.schemas.integration import (
    IntegrationCreate, IntegrationUpdate, IntegrationResponse, IntegrationSummary,
    IntegrationFilter, PaginatedIntegrations, IntegrationStats,
    IntegrationStatusUpdate, IntegrationTest, IntegrationConfigMask
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


def get_integration_service(db: Session = Depends(get_db)) -> IntegrationService:
    """Dependency to get integration service"""
    return IntegrationService(db)


@router.post("/", response_model=IntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_integration(
    integration_data: IntegrationCreate,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Create a new integration"""
    return integration_service.create_integration(integration_data, current_user)


@router.get("/", response_model=PaginatedIntegrations)
async def get_integrations(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    # Filters
    type: Optional[IntegrationType] = Query(None, description="Filter by integration type"),
    status: Optional[IntegrationStatus] = Query(None, description="Filter by status"),
    active_only: Optional[bool] = Query(None, description="Show only active integrations"),
    search: Optional[str] = Query(None, max_length=100, description="Search in integration name"),
    has_errors: Optional[bool] = Query(None, description="Filter integrations with errors"),
    sync_enabled: Optional[bool] = Query(None, description="Filter by sync enabled status"),
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Get paginated integrations with filtering"""
    # Create filter object
    filters = IntegrationFilter(
        type=type,
        status=status,
        active_only=active_only,
        search=search,
        has_errors=has_errors,
        sync_enabled=sync_enabled
    )
    
    return integration_service.get_integrations(
        organization_id=current_user.organization_id,
        filters=filters,
        page=page,
        size=size
    )


@router.get("/stats", response_model=IntegrationStats)
async def get_integration_stats(
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Get integration statistics for the current organization"""
    return integration_service.get_integration_stats(current_user.organization_id)


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Get a specific integration by ID"""
    return integration_service.get_integration(integration_id, current_user.organization_id)


@router.put("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: int,
    integration_data: IntegrationUpdate,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Update an integration"""
    return integration_service.update_integration(
        integration_id, current_user.organization_id, integration_data
    )


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Delete an integration"""
    integration_service.delete_integration(integration_id, current_user.organization_id)


@router.patch("/{integration_id}/status", response_model=IntegrationResponse)
async def update_integration_status(
    integration_id: int,
    status_data: IntegrationStatusUpdate,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Update integration status"""
    return integration_service.update_integration_status(
        integration_id, current_user.organization_id, status_data.status, status_data.error_message
    )


@router.post("/{integration_id}/test")
async def test_integration(
    integration_id: int,
    test_data: IntegrationTest,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Test integration connection"""
    return integration_service.test_integration(integration_id, current_user.organization_id)


@router.get("/{integration_id}/config", response_model=IntegrationConfigMask)
async def get_integration_config(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Get integration configuration (masked for security)"""
    return integration_service.get_integration_config(integration_id, current_user.organization_id)


# Additional endpoints for common operations

@router.get("/type/{integration_type}", response_model=PaginatedIntegrations)
async def get_integrations_by_type(
    integration_type: IntegrationType,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Get integrations by type"""
    filters = IntegrationFilter(type=integration_type)
    return integration_service.get_integrations(
        organization_id=current_user.organization_id,
        filters=filters,
        page=page,
        size=size
    )


@router.get("/active", response_model=PaginatedIntegrations)
async def get_active_integrations(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Get active integrations"""
    filters = IntegrationFilter(status=IntegrationStatus.ACTIVE)
    return integration_service.get_integrations(
        organization_id=current_user.organization_id,
        filters=filters,
        page=page,
        size=size
    )


@router.get("/errors", response_model=PaginatedIntegrations)
async def get_error_integrations(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Get integrations with errors"""
    filters = IntegrationFilter(status=IntegrationStatus.ERROR)
    return integration_service.get_integrations(
        organization_id=current_user.organization_id,
        filters=filters,
        page=page,
        size=size
    )


@router.patch("/{integration_id}/enable-sync")
async def enable_sync(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Enable ticket synchronization for an integration"""
    update_data = IntegrationUpdate(sync_tickets=True)
    return integration_service.update_integration(
        integration_id, current_user.organization_id, update_data
    )


@router.patch("/{integration_id}/disable-sync")
async def disable_sync(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Disable ticket synchronization for an integration"""
    update_data = IntegrationUpdate(sync_tickets=False)
    return integration_service.update_integration(
        integration_id, current_user.organization_id, update_data
    )


@router.patch("/{integration_id}/enable-webhooks")
async def enable_webhooks(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Enable webhook reception for an integration"""
    update_data = IntegrationUpdate(receive_webhooks=True)
    return integration_service.update_integration(
        integration_id, current_user.organization_id, update_data
    )


@router.patch("/{integration_id}/disable-webhooks")
async def disable_webhooks(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    integration_service: IntegrationService = Depends(get_integration_service)
):
    """Disable webhook reception for an integration"""
    update_data = IntegrationUpdate(receive_webhooks=False)
    return integration_service.update_integration(
        integration_id, current_user.organization_id, update_data
    )
