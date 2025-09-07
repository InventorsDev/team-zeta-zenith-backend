from typing import Optional
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime
from app.models.user import UserRole


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    full_name: str
    is_active: Optional[bool] = True
    role: Optional[UserRole] = UserRole.USER
    organization_id: Optional[int] = None


class UserCreate(UserBase):
    """Schema for user registration"""
    password: str

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class UserResponse(UserBase):
    """Schema for user response (excludes sensitive data)"""
    id: int
    is_verified: bool
    avatar_url: Optional[str] = None
    timezone: str
    last_login: Optional[datetime] = None
    email_notifications: bool
    slack_notifications: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for user updates"""
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    email_notifications: Optional[bool] = None
    slack_notifications: Optional[bool] = None


class TokenResponse(BaseModel):
    """Schema for token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """Schema for JWT token payload"""
    sub: Optional[str] = None
    email: Optional[str] = None
    exp: Optional[datetime] = None
