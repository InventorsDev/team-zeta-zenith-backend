from typing import Optional, Dict, Any, List
from pydantic import BaseModel, EmailStr, validator, Field
from datetime import datetime


class OrganizationBase(BaseModel):
    """Base organization schema"""
    name: str = Field(..., min_length=1, max_length=255, description="Organization name")
    slug: Optional[str] = Field(None, max_length=100, description="Organization slug (auto-generated if not provided)")
    description: Optional[str] = Field(None, description="Organization description")
    email: Optional[str] = Field(None, max_length=255, description="Contact email")
    phone: Optional[str] = Field(None, max_length=50, description="Contact phone")
    website: Optional[str] = Field(None, max_length=255, description="Website URL")
    timezone: str = Field("UTC", max_length=50, description="Organization timezone")
    logo_url: Optional[str] = Field(None, max_length=512, description="Logo URL")
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Organization settings")

    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()

    @validator('email')
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower() if v else v

    @validator('website')
    def validate_website(cls, v):
        if v and not (v.startswith('http://') or v.startswith('https://')):
            v = f"https://{v}"
        return v

    @validator('slug')
    def validate_slug(cls, v):
        if v:
            import re
            # Ensure slug contains only lowercase letters, numbers, and hyphens
            if not re.match(r'^[a-z0-9-]+$', v):
                raise ValueError('Slug can only contain lowercase letters, numbers, and hyphens')
            if v.startswith('-') or v.endswith('-'):
                raise ValueError('Slug cannot start or end with a hyphen')
        return v


class OrganizationCreate(OrganizationBase):
    """Schema for creating a new organization"""
    plan: str = Field("free", description="Subscription plan")
    max_users: int = Field(5, ge=1, le=1000, description="Maximum number of users")
    max_tickets_per_month: int = Field(1000, ge=1, description="Maximum tickets per month")

    @validator('plan')
    def validate_plan(cls, v):
        allowed_plans = ['free', 'pro', 'enterprise']
        if v not in allowed_plans:
            raise ValueError(f'Plan must be one of: {", ".join(allowed_plans)}')
        return v


class OrganizationUpdate(BaseModel):
    """Schema for updating an existing organization"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    slug: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=255)
    timezone: Optional[str] = Field(None, max_length=50)
    logo_url: Optional[str] = Field(None, max_length=512)
    settings: Optional[Dict[str, Any]] = None
    plan: Optional[str] = None
    max_users: Optional[int] = Field(None, ge=1, le=1000)
    max_tickets_per_month: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None

    @validator('name')
    def validate_name(cls, v):
        if v is not None and not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip() if v else v

    @validator('email')
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower() if v else v

    @validator('website')
    def validate_website(cls, v):
        if v and not (v.startswith('http://') or v.startswith('https://')):
            v = f"https://{v}"
        return v

    @validator('slug')
    def validate_slug(cls, v):
        if v:
            import re
            if not re.match(r'^[a-z0-9-]+$', v):
                raise ValueError('Slug can only contain lowercase letters, numbers, and hyphens')
            if v.startswith('-') or v.endswith('-'):
                raise ValueError('Slug cannot start or end with a hyphen')
        return v

    @validator('plan')
    def validate_plan(cls, v):
        if v:
            allowed_plans = ['free', 'pro', 'enterprise']
            if v not in allowed_plans:
                raise ValueError(f'Plan must be one of: {", ".join(allowed_plans)}')
        return v


class OrganizationResponse(OrganizationBase):
    """Schema for organization response"""
    id: int
    is_active: bool
    plan: str
    max_users: int
    max_tickets_per_month: int
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    user_count: int = 0
    ticket_count: int = 0
    integration_count: int = 0

    class Config:
        from_attributes = True


class OrganizationSummary(BaseModel):
    """Schema for organization summary (for lists)"""
    id: int
    name: str
    slug: str
    is_active: bool
    plan: str
    user_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class OrganizationFilter(BaseModel):
    """Schema for organization filtering"""
    is_active: Optional[bool] = None
    plan: Optional[str] = None
    search: Optional[str] = Field(None, max_length=100, description="Search in name, slug, or description")

    @validator('plan')
    def validate_plan(cls, v):
        if v:
            allowed_plans = ['free', 'pro', 'enterprise']
            if v not in allowed_plans:
                raise ValueError(f'Plan must be one of: {", ".join(allowed_plans)}')
        return v


class PaginatedOrganizations(BaseModel):
    """Schema for paginated organization response"""
    items: List[OrganizationSummary]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


class OrganizationStats(BaseModel):
    """Schema for organization statistics"""
    user_count: int
    max_users: int
    user_usage_percent: float
    ticket_count: int
    max_tickets_per_month: int
    integration_count: int
    plan: str
    is_active: bool


class OrganizationSettings(BaseModel):
    """Schema for organization settings update"""
    settings: Dict[str, Any] = Field(..., description="Organization settings to update")


class OrganizationInvite(BaseModel):
    """Schema for inviting users to organization"""
    email: EmailStr = Field(..., description="Email address to invite")
    role: str = Field("user", description="Role to assign")
    
    @validator('email')
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower()

    @validator('role')
    def validate_role(cls, v):
        allowed_roles = ['admin', 'user', 'viewer']
        if v.lower() not in allowed_roles:
            raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v.lower()
