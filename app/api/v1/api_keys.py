"""
API Key Management Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database.connection import get_db
from app.models.user import User, UserRole
from app.services.api_key_service import APIKeyService
from app.schemas.api_key import (
    APIKeyCreate,
    APIKeyCreatedResponse,
    APIKeyResponse,
    APIKeyUpdate,
    APIKeyStats,
)
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("", response_model=APIKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new API key for programmatic access

    Only admin users can create API keys.
    The API key is only shown once - save it securely!
    """
    # Only admins can create API keys
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can create API keys"
        )

    api_key_service = APIKeyService(db)

    api_key, plain_key = api_key_service.create_api_key(
        organization_id=current_user.organization_id,
        created_by=current_user.id,
        name=key_data.name,
        scopes=key_data.scopes,
        description=key_data.description,
        expires_in_days=key_data.expires_in_days,
        is_test_key=key_data.is_test_key,
        ip_whitelist=key_data.ip_whitelist,
        rate_limit=key_data.rate_limit,
    )

    return APIKeyCreatedResponse(
        api_key=APIKeyResponse.from_orm(api_key),
        key=plain_key,
        warning="Save this key securely - it will not be displayed again"
    )


@router.get("", response_model=List[APIKeyResponse])
async def get_api_keys(
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all API keys for the current organization

    Only admin users can view API keys
    """
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can view API keys"
        )

    api_key_service = APIKeyService(db)
    keys = api_key_service.get_api_keys(
        organization_id=current_user.organization_id,
        include_inactive=include_inactive
    )

    return [APIKeyResponse.from_orm(key) for key in keys]


@router.get("/stats", response_model=APIKeyStats)
async def get_api_key_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get API key usage statistics"""
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can view API key stats"
        )

    api_key_service = APIKeyService(db)
    stats = api_key_service.get_key_stats(current_user.organization_id)

    return APIKeyStats(**stats)


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific API key by ID"""
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can view API keys"
        )

    api_key_service = APIKeyService(db)
    api_key = api_key_service.get_api_key(key_id, current_user.organization_id)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    return APIKeyResponse.from_orm(api_key)


@router.post("/{key_id}/revoke", response_model=APIKeyResponse)
async def revoke_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke (deactivate) an API key

    This immediately prevents the key from being used for authentication
    """
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can revoke API keys"
        )

    api_key_service = APIKeyService(db)
    success = api_key_service.revoke_api_key(
        key_id=key_id,
        organization_id=current_user.organization_id,
        revoked_by=current_user.id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    # Return updated key
    api_key = api_key_service.get_api_key(key_id, current_user.organization_id)
    return APIKeyResponse.from_orm(api_key)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Permanently delete an API key

    This action cannot be undone
    """
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can delete API keys"
        )

    api_key_service = APIKeyService(db)
    success = api_key_service.delete_api_key(
        key_id=key_id,
        organization_id=current_user.organization_id,
        deleted_by=current_user.id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )


# API Key Authentication Dependency
async def get_api_key_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to authenticate via API key

    Usage in endpoints:
        current_user: User = Depends(get_api_key_user)

    Looks for API key in X-API-Key header
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required in X-API-Key header"
        )

    api_key_service = APIKeyService(db)
    api_key = api_key_service.validate_api_key(x_api_key)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key"
        )

    # Get the user who created the key
    from app.models.user import User
    user = db.query(User).filter(User.id == api_key.created_by).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key user not found"
        )

    return user
