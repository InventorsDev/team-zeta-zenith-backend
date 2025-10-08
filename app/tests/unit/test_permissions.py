"""
Unit tests for RBAC Permission System

Tests role-based access control logic
"""

import pytest
from app.core.permissions import (
    Permission,
    UserRole,
    get_role_permissions,
    has_permission,
    has_any_permission,
    has_all_permissions,
)


@pytest.mark.unit
@pytest.mark.security
class TestPermissions:
    """Test suite for permission system"""

    def test_admin_has_all_permissions(self):
        """Admin role should have all permissions"""
        admin_perms = get_role_permissions(UserRole.ADMIN)

        # Test a sample of permissions
        assert Permission.USER_CREATE in admin_perms
        assert Permission.USER_DELETE in admin_perms
        assert Permission.ORG_DELETE in admin_perms
        assert Permission.SYSTEM_ADMIN in admin_perms
        assert Permission.API_KEY_CREATE in admin_perms
        assert Permission.AUDIT_READ in admin_perms

    def test_manager_permissions(self):
        """Manager should have appropriate permissions"""
        manager_perms = get_role_permissions(UserRole.MANAGER)

        # Should have these
        assert Permission.USER_CREATE in manager_perms
        assert Permission.TICKET_DELETE in manager_perms
        assert Permission.ANALYTICS_READ in manager_perms
        assert Permission.ALERT_RULE_MANAGE in manager_perms

        # Should NOT have these
        assert Permission.ORG_DELETE not in manager_perms
        assert Permission.SYSTEM_ADMIN not in manager_perms
        assert Permission.API_KEY_CREATE not in manager_perms

    def test_agent_permissions(self):
        """Agent should have limited permissions"""
        agent_perms = get_role_permissions(UserRole.AGENT)

        # Should have these
        assert Permission.TICKET_READ in agent_perms
        assert Permission.TICKET_UPDATE in agent_perms
        assert Permission.ANALYTICS_READ in agent_perms

        # Should NOT have these
        assert Permission.USER_CREATE not in agent_perms
        assert Permission.TICKET_DELETE not in agent_perms
        assert Permission.ALERT_RULE_MANAGE not in agent_perms
        assert Permission.API_KEY_CREATE not in agent_perms

    def test_user_permissions(self):
        """Regular user should have minimal permissions"""
        user_perms = get_role_permissions(UserRole.USER)

        # Should have these
        assert Permission.USER_READ in user_perms
        assert Permission.TICKET_READ in user_perms
        assert Permission.TICKET_CREATE in user_perms

        # Should NOT have these
        assert Permission.USER_CREATE not in user_perms
        assert Permission.TICKET_UPDATE not in user_perms
        assert Permission.ANALYTICS_EXPORT not in user_perms

    def test_has_permission(self):
        """Test has_permission function"""
        assert has_permission(UserRole.ADMIN, Permission.USER_DELETE)
        assert has_permission(UserRole.MANAGER, Permission.TICKET_UPDATE)
        assert not has_permission(UserRole.AGENT, Permission.USER_DELETE)
        assert not has_permission(UserRole.USER, Permission.TICKET_DELETE)

    def test_has_any_permission(self):
        """Test has_any_permission function"""
        # Admin has at least one
        assert has_any_permission(
            UserRole.ADMIN,
            [Permission.USER_DELETE, Permission.ORG_DELETE]
        )

        # Manager has at least one
        assert has_any_permission(
            UserRole.MANAGER,
            [Permission.TICKET_UPDATE, Permission.ORG_DELETE]
        )

        # User has none of these
        assert not has_any_permission(
            UserRole.USER,
            [Permission.USER_DELETE, Permission.ORG_DELETE]
        )

    def test_has_all_permissions(self):
        """Test has_all_permissions function"""
        # Admin has all
        assert has_all_permissions(
            UserRole.ADMIN,
            [Permission.USER_READ, Permission.USER_CREATE, Permission.USER_DELETE]
        )

        # Manager has some but not all
        assert not has_all_permissions(
            UserRole.MANAGER,
            [Permission.TICKET_READ, Permission.ORG_DELETE]
        )

        # Agent has limited
        assert has_all_permissions(
            UserRole.AGENT,
            [Permission.TICKET_READ, Permission.TICKET_UPDATE]
        )

        assert not has_all_permissions(
            UserRole.AGENT,
            [Permission.TICKET_READ, Permission.TICKET_DELETE]
        )
