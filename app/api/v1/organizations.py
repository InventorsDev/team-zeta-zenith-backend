from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.services.organization_service import OrganizationService
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.schemas.organization import (
    OrganizationCreate, OrganizationUpdate, OrganizationResponse,
    OrganizationSummary, OrganizationFilter, PaginatedOrganizations,
    OrganizationStats, OrganizationSettings
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


def get_organization_service(db: Session = Depends(get_db)) -> OrganizationService:
    """Dependency to get organization service"""
    return OrganizationService(db)


@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_data: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """Create a new organization (available to users without organizations)"""
    # Users can create organizations if they don't already belong to one
    if current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already belongs to an organization"
        )
    
    return org_service.create_organization(org_data, current_user.id)


@router.get("/", response_model=PaginatedOrganizations)
async def get_organizations(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    # Filters
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    plan: Optional[str] = Query(None, description="Filter by subscription plan"),
    search: Optional[str] = Query(None, max_length=100, description="Search in name, slug, or description"),
    current_user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """Get paginated organizations (admin only)"""
    # Create filter object
    filters = OrganizationFilter(
        is_active=is_active,
        plan=plan,
        search=search
    )
    
    return org_service.get_organizations(
        filters=filters,
        page=page,
        size=size,
        current_user=current_user
    )


@router.get("/current", response_model=OrganizationResponse)
async def get_current_organization(
    current_user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """Get the current user's organization"""
    return org_service.get_current_user_organization(current_user)


@router.get("/current/stats", response_model=OrganizationStats)
async def get_current_organization_stats(
    current_user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """Get statistics for the current user's organization"""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with any organization"
        )
    
    return org_service.get_organization_stats(current_user.organization_id, current_user)


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """Get a specific organization by ID"""
    return org_service.get_organization(organization_id, current_user)


@router.put("/current", response_model=OrganizationResponse)
async def update_current_organization(
    org_data: OrganizationUpdate,
    current_user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """Update the current user's organization"""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with any organization"
        )
    
    return org_service.update_organization(
        current_user.organization_id, org_data, current_user
    )


@router.put("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: int,
    org_data: OrganizationUpdate,
    current_user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """Update an organization by ID (admin only)"""
    return org_service.update_organization(organization_id, org_data, current_user)


@router.patch("/current/settings", response_model=OrganizationResponse)
async def update_current_organization_settings(
    settings_data: OrganizationSettings,
    current_user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """Update settings for the current user's organization"""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with any organization"
        )
    
    return org_service.update_organization_settings(
        current_user.organization_id, settings_data.settings, current_user
    )


@router.patch("/{organization_id}/settings", response_model=OrganizationResponse)
async def update_organization_settings(
    organization_id: int,
    settings_data: OrganizationSettings,
    current_user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """Update organization settings by ID (admin only)"""
    return org_service.update_organization_settings(
        organization_id, settings_data.settings, current_user
    )


@router.patch("/current/deactivate", response_model=OrganizationResponse)
async def deactivate_current_organization(
    current_user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """Deactivate the current user's organization"""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with any organization"
        )
    
    return org_service.deactivate_organization(current_user.organization_id, current_user)


@router.patch("/current/activate", response_model=OrganizationResponse)
async def activate_current_organization(
    current_user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """Activate the current user's organization"""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with any organization"
        )
    
    return org_service.activate_organization(current_user.organization_id, current_user)


@router.patch("/{organization_id}/deactivate", response_model=OrganizationResponse)
async def deactivate_organization(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """Deactivate an organization by ID (admin only)"""
    return org_service.deactivate_organization(organization_id, current_user)


@router.patch("/{organization_id}/activate", response_model=OrganizationResponse)
async def activate_organization(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """Activate an organization by ID (admin only)"""
    return org_service.activate_organization(organization_id, current_user)


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """Delete an organization (system admin only)"""
    org_service.delete_organization(organization_id, current_user)


@router.get("/stats/summary")
async def get_organizations_summary(
    current_user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """Get summary statistics across all organizations (system admin only)"""
    from app.models.user import UserRole
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # This would typically be implemented in the service layer
    # For now, return a simple response
    return {
        "message": "Organizations summary endpoint",
        "note": "Implementation would include total orgs, active orgs, plans distribution, etc."
    }
