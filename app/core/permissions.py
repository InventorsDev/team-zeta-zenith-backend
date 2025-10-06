"""
RBAC Permission System - Role-Based Access Control

Defines permissions and scopes for different user roles
"""

from enum import Enum
from typing import List, Optional
from fastapi import HTTPException, status

from app.models.user import UserRole


class Permission(str, Enum):
    """Available permissions in the system"""

    # User Management
    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"

    # Organization Management
    ORG_READ = "org:read"
    ORG_UPDATE = "org:update"
    ORG_DELETE = "org:delete"
    ORG_SETTINGS = "org:settings"

    # Ticket Management
    TICKET_READ = "ticket:read"
    TICKET_CREATE = "ticket:create"
    TICKET_UPDATE = "ticket:update"
    TICKET_DELETE = "ticket:delete"
    TICKET_ASSIGN = "ticket:assign"

    # Analytics
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"

    # Integrations
    INTEGRATION_READ = "integration:read"
    INTEGRATION_CREATE = "integration:create"
    INTEGRATION_UPDATE = "integration:update"
    INTEGRATION_DELETE = "integration:delete"

    # Alerts
    ALERT_READ = "alert:read"
    ALERT_CREATE = "alert:create"
    ALERT_UPDATE = "alert:update"
    ALERT_DELETE = "alert:delete"
    ALERT_RULE_MANAGE = "alert:rule:manage"

    # API Keys
    API_KEY_READ = "apikey:read"
    API_KEY_CREATE = "apikey:create"
    API_KEY_REVOKE = "apikey:revoke"
    API_KEY_DELETE = "apikey:delete"

    # Audit Logs
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"

    # ML/AI Features
    ML_READ = "ml:read"
    ML_TRAIN = "ml:train"
    ML_DEPLOY = "ml:deploy"

    # System Administration
    SYSTEM_CONFIG = "system:config"
    SYSTEM_ADMIN = "system:admin"


# Role-to-Permissions mapping
ROLE_PERMISSIONS: dict[UserRole, List[Permission]] = {
    UserRole.ADMIN: [
        # Admins have all permissions
        Permission.USER_READ,
        Permission.USER_CREATE,
        Permission.USER_UPDATE,
        Permission.USER_DELETE,
        Permission.ORG_READ,
        Permission.ORG_UPDATE,
        Permission.ORG_DELETE,
        Permission.ORG_SETTINGS,
        Permission.TICKET_READ,
        Permission.TICKET_CREATE,
        Permission.TICKET_UPDATE,
        Permission.TICKET_DELETE,
        Permission.TICKET_ASSIGN,
        Permission.ANALYTICS_READ,
        Permission.ANALYTICS_EXPORT,
        Permission.INTEGRATION_READ,
        Permission.INTEGRATION_CREATE,
        Permission.INTEGRATION_UPDATE,
        Permission.INTEGRATION_DELETE,
        Permission.ALERT_READ,
        Permission.ALERT_CREATE,
        Permission.ALERT_UPDATE,
        Permission.ALERT_DELETE,
        Permission.ALERT_RULE_MANAGE,
        Permission.API_KEY_READ,
        Permission.API_KEY_CREATE,
        Permission.API_KEY_REVOKE,
        Permission.API_KEY_DELETE,
        Permission.AUDIT_READ,
        Permission.AUDIT_EXPORT,
        Permission.ML_READ,
        Permission.ML_TRAIN,
        Permission.ML_DEPLOY,
        Permission.SYSTEM_CONFIG,
        Permission.SYSTEM_ADMIN,
    ],
    UserRole.MANAGER: [
        # Managers can manage users and tickets, view analytics
        Permission.USER_READ,
        Permission.USER_CREATE,
        Permission.USER_UPDATE,
        Permission.ORG_READ,
        Permission.TICKET_READ,
        Permission.TICKET_CREATE,
        Permission.TICKET_UPDATE,
        Permission.TICKET_DELETE,
        Permission.TICKET_ASSIGN,
        Permission.ANALYTICS_READ,
        Permission.ANALYTICS_EXPORT,
        Permission.INTEGRATION_READ,
        Permission.ALERT_READ,
        Permission.ALERT_CREATE,
        Permission.ALERT_UPDATE,
        Permission.ALERT_RULE_MANAGE,
        Permission.ML_READ,
    ],
    UserRole.AGENT: [
        # Agents can read/update tickets and view analytics
        Permission.USER_READ,
        Permission.ORG_READ,
        Permission.TICKET_READ,
        Permission.TICKET_CREATE,
        Permission.TICKET_UPDATE,
        Permission.ANALYTICS_READ,
        Permission.INTEGRATION_READ,
        Permission.ALERT_READ,
        Permission.ML_READ,
    ],
    UserRole.USER: [
        # Regular users can only view their own data
        Permission.USER_READ,
        Permission.ORG_READ,
        Permission.TICKET_READ,
        Permission.TICKET_CREATE,
        Permission.ALERT_READ,
    ],
}


def get_role_permissions(role: UserRole) -> List[Permission]:
    """Get all permissions for a role"""
    return ROLE_PERMISSIONS.get(role, [])


def has_permission(user_role: UserRole, required_permission: Permission) -> bool:
    """Check if a role has a specific permission"""
    role_perms = get_role_permissions(user_role)
    return required_permission in role_perms


def has_any_permission(user_role: UserRole, required_permissions: List[Permission]) -> bool:
    """Check if a role has any of the required permissions"""
    role_perms = get_role_permissions(user_role)
    return any(perm in role_perms for perm in required_permissions)


def has_all_permissions(user_role: UserRole, required_permissions: List[Permission]) -> bool:
    """Check if a role has all of the required permissions"""
    role_perms = get_role_permissions(user_role)
    return all(perm in role_perms for perm in required_permissions)


def require_permission(required_permission: Permission):
    """
    Decorator to require a specific permission for an endpoint

    Usage:
        @router.get("/admin/users")
        @require_permission(Permission.USER_READ)
        async def get_users(current_user: User = Depends(get_current_user)):
            ...
    """
    def decorator(func):
        from functools import wraps

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current_user from kwargs
            current_user = kwargs.get("current_user")
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            # Check permission
            user_role = UserRole(current_user.role)
            if not has_permission(user_role, required_permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied. Required: {required_permission.value}"
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_any_permission(required_permissions: List[Permission]):
    """
    Decorator to require any of the specified permissions

    Usage:
        @router.get("/tickets")
        @require_any_permission([Permission.TICKET_READ, Permission.TICKET_UPDATE])
        async def get_tickets(current_user: User = Depends(get_current_user)):
            ...
    """
    def decorator(func):
        from functools import wraps

        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            user_role = UserRole(current_user.role)
            if not has_any_permission(user_role, required_permissions):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied. Required any of: {[p.value for p in required_permissions]}"
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_role(required_role: UserRole):
    """
    Decorator to require a specific role (or higher)

    Role hierarchy: ADMIN > MANAGER > AGENT > USER

    Usage:
        @router.delete("/tickets/{ticket_id}")
        @require_role(UserRole.MANAGER)
        async def delete_ticket(ticket_id: int, current_user: User = Depends(get_current_user)):
            ...
    """
    role_hierarchy = {
        UserRole.ADMIN: 4,
        UserRole.MANAGER: 3,
        UserRole.AGENT: 2,
        UserRole.USER: 1,
    }

    def decorator(func):
        from functools import wraps

        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            user_role = UserRole(current_user.role)
            required_level = role_hierarchy.get(required_role, 0)
            user_level = role_hierarchy.get(user_role, 0)

            if user_level < required_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role denied. Required: {required_role.value} or higher"
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator
