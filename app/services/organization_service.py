from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.database.repositories.organization_repository import OrganizationRepository
from app.database.repositories.user_repository import UserRepository
from app.schemas.organization import (
    OrganizationCreate, OrganizationUpdate, OrganizationResponse,
    OrganizationSummary, OrganizationFilter, PaginatedOrganizations,
    OrganizationStats
)


class OrganizationService:
    """Service layer for organization operations"""

    def __init__(self, db: Session):
        self.db = db
        self.org_repo = OrganizationRepository(db)
        self.user_repo = UserRepository(db)

    def create_organization(self, org_data: OrganizationCreate, created_by_user_id: int = None) -> OrganizationResponse:
        """Create a new organization"""
        # Check if organization name or slug already exists
        existing_by_name = self.org_repo.get_by_name(org_data.name)
        if existing_by_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization name already exists"
            )
        
        if org_data.slug:
            existing_by_slug = self.org_repo.get_by_slug(org_data.slug)
            if existing_by_slug:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization slug already exists"
                )
        
        # Convert Pydantic model to dict
        org_dict = org_data.dict()
        
        # Create organization
        organization = self.org_repo.create_organization(org_dict)
        
        # If a user created this, make them an admin
        if created_by_user_id:
            user = self.user_repo.get(created_by_user_id)
            if user:
                # Update user to be part of this organization and make them admin
                self.user_repo.update(user, {
                    "organization_id": organization.id,
                    "role": UserRole.ADMIN
                })
        
        return self._to_organization_response(organization)

    def get_organization(self, organization_id: int, current_user: User = None) -> OrganizationResponse:
        """Get organization by ID"""
        organization = self.org_repo.get(organization_id)
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Check if user has access to this organization
        if current_user and current_user.organization_id != organization_id:
            # Only allow if user is a system admin or similar
            if current_user.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this organization"
                )
        
        return self._to_organization_response(organization)

    def get_current_user_organization(self, current_user: User) -> OrganizationResponse:
        """Get the current user's organization"""
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User is not associated with any organization"
            )
        
        return self.get_organization(current_user.organization_id, current_user)

    def update_organization(self, organization_id: int, org_data: OrganizationUpdate, current_user: User) -> OrganizationResponse:
        """Update an organization"""
        print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        print("data", org_data)
        print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        organization = self.org_repo.get(organization_id)
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Check if user has permission to update this organization
        if current_user.organization_id != organization_id or current_user.role not in [UserRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update organization"
            )
        
        # Convert Pydantic model to dict, excluding None values
        update_dict = org_data.dict(exclude_unset=True)
        if not update_dict:
            return self._to_organization_response(organization)
        
        # Check for name conflicts if name is being updated
        if "name" in update_dict:
            existing = self.org_repo.get_by_name(update_dict["name"])
            if existing and existing.id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization name already exists"
                )
        
        # Check for slug conflicts if slug is being updated
        if "slug" in update_dict:
            existing = self.org_repo.get_by_slug(update_dict["slug"])
            if existing and existing.id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization slug already exists"
                )
        
        # Apply updates
        organization = self.org_repo.update(organization, update_dict)
        
        return self._to_organization_response(organization)

    def get_organizations(
        self,
        filters: OrganizationFilter = None,
        page: int = 1,
        size: int = 50,
        current_user: User = None
    ) -> PaginatedOrganizations:
        """Get paginated organizations with filtering (admin only)"""
        # Only system admins can list all organizations
        if current_user and current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to list organizations"
            )
        
        # Validate pagination parameters
        if page < 1:
            page = 1
        if size < 1 or size > 100:
            size = 50
        
        skip = (page - 1) * size
        
        # Convert filters to dict
        filter_dict = filters.dict(exclude_unset=True) if filters else {}
        
        # Get organizations and count
        organizations = self.org_repo.get_filtered_organizations(
            filters=filter_dict,
            skip=skip,
            limit=size
        )
        
        total = self.org_repo.count_organizations(filter_dict)
        
        # Convert to summary format
        org_summaries = [self._to_organization_summary(org) for org in organizations]
        
        # Calculate pagination info
        pages = (total + size - 1) // size
        has_next = page < pages
        has_prev = page > 1
        
        return PaginatedOrganizations(
            items=org_summaries,
            total=total,
            page=page,
            size=size,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )

    def update_organization_settings(self, organization_id: int, settings: Dict[str, Any], current_user: User) -> OrganizationResponse:
        """Update organization settings"""
        organization = self.org_repo.get(organization_id)
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Check permissions
        if current_user.organization_id != organization_id or current_user.role not in [UserRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update organization settings"
            )
        
        organization = self.org_repo.update_settings(organization, settings)
        return self._to_organization_response(organization)

    def get_organization_stats(self, organization_id: int, current_user: User) -> OrganizationStats:
        """Get organization statistics"""
        organization = self.org_repo.get(organization_id)
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Check permissions
        if current_user.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this organization"
            )
        
        # Get counts
        user_count = self.org_repo.count_users(organization_id)
        ticket_count = self.org_repo.count_tickets(organization_id)
        integration_count = self.org_repo.count_integrations(organization_id)
        
        # Calculate usage percentages
        user_usage_percent = (user_count / organization.max_users * 100) if organization.max_users > 0 else 0
        
        return OrganizationStats(
            user_count=user_count,
            max_users=organization.max_users,
            user_usage_percent=user_usage_percent,
            ticket_count=ticket_count,
            max_tickets_per_month=organization.max_tickets_per_month,
            integration_count=integration_count,
            plan=organization.plan,
            is_active=organization.is_active
        )

    def delete_organization(self, organization_id: int, current_user: User) -> bool:
        """Delete an organization (admin only)"""
        organization = self.org_repo.get(organization_id)
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Only system admins can delete organizations
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete organization"
            )
        
        # Check if organization has users (besides the admin)
        user_count = self.org_repo.count_users(organization_id)
        if user_count > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete organization with multiple users. Remove users first."
            )
        
        return self.org_repo.delete(organization_id)

    def deactivate_organization(self, organization_id: int, current_user: User) -> OrganizationResponse:
        """Deactivate an organization"""
        organization = self.org_repo.get(organization_id)
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Check permissions
        if current_user.organization_id != organization_id or current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to deactivate organization"
            )
        
        organization = self.org_repo.update(organization, {"is_active": False})
        return self._to_organization_response(organization)

    def activate_organization(self, organization_id: int, current_user: User) -> OrganizationResponse:
        """Activate an organization"""
        organization = self.org_repo.get(organization_id)
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Check permissions (system admin or org admin)
        if current_user.role != UserRole.ADMIN and current_user.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to activate organization"
            )
        
        organization = self.org_repo.update(organization, {"is_active": True})
        return self._to_organization_response(organization)

    def _to_organization_response(self, organization: Organization) -> OrganizationResponse:
        """Convert organization model to response schema"""
        # Get counts
        user_count = len(organization.users) if organization.users else 0
        ticket_count = len(organization.tickets) if organization.tickets else 0
        integration_count = len(organization.integrations) if organization.integrations else 0
        
        return OrganizationResponse(
            id=organization.id,
            name=organization.name,
            slug=organization.slug,
            description=organization.description,
            email=organization.email,
            phone=organization.phone,
            website=organization.website,
            is_active=organization.is_active,
            timezone=organization.timezone,
            logo_url=organization.logo_url,
            settings=organization.settings or {},
            plan=organization.plan,
            max_users=organization.max_users,
            max_tickets_per_month=organization.max_tickets_per_month,
            created_at=organization.created_at,
            updated_at=organization.updated_at,
            user_count=user_count,
            ticket_count=ticket_count,
            integration_count=integration_count
        )

    def _to_organization_summary(self, organization: Organization) -> OrganizationSummary:
        """Convert organization model to summary schema"""
        user_count = len(organization.users) if organization.users else 0
        
        return OrganizationSummary(
            id=organization.id,
            name=organization.name,
            slug=organization.slug,
            is_active=organization.is_active,
            plan=organization.plan,
            user_count=user_count,
            created_at=organization.created_at
        )
