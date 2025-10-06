"""
API Key Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class APIKeyCreate(BaseModel):
    """Schema for creating an API key"""
    name: str = Field(..., min_length=1, max_length=255, description="Human-readable name for the key")
    description: Optional[str] = Field(None, max_length=1000, description="Optional description")
    scopes: List[str] = Field(..., min_items=1, description="List of permission scopes")
    expires_in_days: Optional[int] = Field(None, gt=0, le=3650, description="Expiration in days (max 10 years)")
    is_test_key: bool = Field(False, description="Whether this is a test/sandbox key")
    ip_whitelist: Optional[List[str]] = Field(None, description="Optional list of allowed IP addresses")
    rate_limit: Optional[int] = Field(None, gt=0, description="Optional custom rate limit (requests per minute)")


class APIKeyResponse(BaseModel):
    """Schema for API key response (without the actual key)"""
    id: int
    name: str
    description: Optional[str] = None
    key_prefix: str
    organization_id: int
    created_by: int
    is_active: bool
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    scopes: List[str]
    ip_whitelist: Optional[List[str]] = None
    rate_limit: Optional[int] = None
    usage_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class APIKeyCreatedResponse(BaseModel):
    """Schema for API key creation response (includes the actual key once)"""
    api_key: APIKeyResponse
    key: str = Field(..., description="The actual API key - save this, it won't be shown again!")
    warning: str = "Save this key securely - it will not be displayed again"


class APIKeyUpdate(BaseModel):
    """Schema for updating an API key"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    scopes: Optional[List[str]] = Field(None, min_items=1)
    is_active: Optional[bool] = None
    ip_whitelist: Optional[List[str]] = None
    rate_limit: Optional[int] = Field(None, gt=0)


class APIKeyStats(BaseModel):
    """API key usage statistics"""
    total_keys: int
    active_keys: int
    inactive_keys: int
    expired_keys: int


class APIKeyValidation(BaseModel):
    """Response for API key validation"""
    valid: bool
    organization_id: Optional[int] = None
    scopes: Optional[List[str]] = None
    message: Optional[str] = None
