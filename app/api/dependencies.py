"""
API Dependencies - Reusable dependency functions for FastAPI endpoints

Includes permission checking, resource ownership validation, etc.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User, UserRole
from app.models.ticket import Ticket
from app.models.organization import Organization
from app.core.permissions import Permission, has_permission
from app.api.v1.auth import get_current_user


def require_permission_dependency(required_permission: Permission):
    """
    Factory function to create permission-checking dependencies

    Usage:
        @router.get("/admin/users")
        async def get_users(
            current_user: User = Depends(get_current_user),
            _: None = Depends(require_permission_dependency(Permission.USER_READ))
        ):
            ...
    """
    def check_permission(current_user: User = Depends(get_current_user)):
        user_role = UserRole(current_user.role)
        if not has_permission(user_role, required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required: {required_permission.value}"
            )
        return None

    return check_permission


def require_admin(current_user: User = Depends(get_current_user)):
    """Dependency to require admin role"""
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_manager_or_above(current_user: User = Depends(get_current_user)):
    """Dependency to require manager or admin role"""
    if current_user.role not in [UserRole.ADMIN.value, UserRole.MANAGER.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or Admin access required"
        )
    return current_user


def get_ticket_or_404(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Ticket:
    """
    Get ticket by ID and verify organization access

    Raises 404 if ticket not found or user doesn't have access
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )

    # Verify user has access to this ticket's organization
    if ticket.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this ticket"
        )

    return ticket


def verify_organization_access(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Organization:
    """
    Verify user has access to the specified organization

    Admins can access any organization, others only their own
    """
    # Admins can access any organization
    if current_user.role == UserRole.ADMIN.value:
        org = db.query(Organization).filter(Organization.id == organization_id).first()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        return org

    # Other users can only access their own organization
    if organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this organization"
        )

    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    return org


def can_modify_user(
    target_user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Check if current user can modify target user

    Rules:
    - Users can modify themselves
    - Admins can modify anyone in their organization
    - Managers can modify agents and users in their organization
    """
    target_user = db.query(User).filter(User.id == target_user_id).first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Can always modify self
    if target_user_id == current_user.id:
        return target_user

    # Must be in same organization
    if target_user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify users in other organizations"
        )

    current_role = UserRole(current_user.role)
    target_role = UserRole(target_user.role)

    # Admins can modify anyone
    if current_role == UserRole.ADMIN:
        return target_user

    # Managers can modify agents and users
    if current_role == UserRole.MANAGER:
        if target_role in [UserRole.AGENT, UserRole.USER]:
            return target_user

    # No permission
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions to modify this user"
    )
