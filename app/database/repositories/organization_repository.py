from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.organization import Organization
from .base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """Repository for Organization model"""

    def __init__(self, db: Session):
        super().__init__(Organization, db)

    def get_by_slug(self, slug: str) -> Optional[Organization]:
        """Get organization by slug"""
        return self.db.query(Organization).filter(Organization.slug == slug).first()

    def get_by_name(self, name: str) -> Optional[Organization]:
        """Get organization by name"""
        return self.db.query(Organization).filter(Organization.name == name).first()

    def get_active_organizations(self, skip: int = 0, limit: int = 100) -> List[Organization]:
        """Get active organizations"""
        return (
            self.db.query(Organization)
            .filter(Organization.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def search_organizations(self, search_term: str, skip: int = 0, limit: int = 100) -> List[Organization]:
        """Search organizations by name, slug, or description"""
        search_filter = or_(
            Organization.name.ilike(f"%{search_term}%"),
            Organization.slug.ilike(f"%{search_term}%"),
            Organization.description.ilike(f"%{search_term}%")
        )
        return (
            self.db.query(Organization)
            .filter(search_filter)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_organization(self, org_data: Dict[str, Any]) -> Organization:
        """Create organization with slug generation"""
        # Generate slug from name if not provided
        if not org_data.get("slug"):
            slug = self._generate_slug(org_data["name"])
            org_data["slug"] = slug
        
        # Ensure slug is unique
        org_data["slug"] = self._ensure_unique_slug(org_data["slug"])
        
        return self.create(org_data)

    def update_settings(self, organization: Organization, settings: Dict[str, Any]) -> Organization:
        """Update organization settings"""
        current_settings = organization.settings or {}
        current_settings.update(settings)
        return self.update(organization, {"settings": current_settings})

    def get_organizations_by_plan(self, plan: str, skip: int = 0, limit: int = 100) -> List[Organization]:
        """Get organizations by subscription plan"""
        return (
            self.db.query(Organization)
            .filter(Organization.plan == plan)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_users(self, organization_id: int) -> int:
        """Count users in organization"""
        org = self.get(organization_id)
        if org:
            return len(org.users)
        return 0

    def count_tickets(self, organization_id: int) -> int:
        """Count tickets in organization"""
        org = self.get(organization_id)
        if org:
            return len(org.tickets)
        return 0

    def count_integrations(self, organization_id: int) -> int:
        """Count integrations in organization"""
        org = self.get(organization_id)
        if org:
            return len(org.integrations)
        return 0

    def get_filtered_organizations(
        self,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 100
    ) -> List[Organization]:
        """Get organizations with filtering"""
        query = self.db.query(Organization)
        
        # Apply filters
        if filters.get("is_active") is not None:
            query = query.filter(Organization.is_active == filters["is_active"])
        
        if filters.get("plan"):
            query = query.filter(Organization.plan == filters["plan"])
        
        if filters.get("search"):
            search_term = filters["search"]
            search_filter = or_(
                Organization.name.ilike(f"%{search_term}%"),
                Organization.slug.ilike(f"%{search_term}%"),
                Organization.description.ilike(f"%{search_term}%")
            )
            query = query.filter(search_filter)
        
        return query.offset(skip).limit(limit).all()

    def count_organizations(self, filters: Dict[str, Any] = None) -> int:
        """Count organizations with optional filters"""
        query = self.db.query(Organization)
        
        if filters:
            if filters.get("is_active") is not None:
                query = query.filter(Organization.is_active == filters["is_active"])
            
            if filters.get("plan"):
                query = query.filter(Organization.plan == filters["plan"])
            
            if filters.get("search"):
                search_term = filters["search"]
                search_filter = or_(
                    Organization.name.ilike(f"%{search_term}%"),
                    Organization.slug.ilike(f"%{search_term}%"),
                    Organization.description.ilike(f"%{search_term}%")
                )
                query = query.filter(search_filter)
        
        return query.count()

    def _generate_slug(self, name: str) -> str:
        """Generate slug from organization name"""
        import re
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', name.lower())
        slug = re.sub(r'\s+', '-', slug.strip())
        slug = re.sub(r'-+', '-', slug)  # Remove multiple consecutive hyphens
        return slug[:50]  # Limit length

    def _ensure_unique_slug(self, slug: str) -> str:
        """Ensure slug is unique by appending number if needed"""
        original_slug = slug
        counter = 1
        
        while self.get_by_slug(slug):
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        return slug
