"""
NASSAQ Security Tests
اختبارات الأمان الشاملة للنظام

Tests:
1. RBAC (Role-Based Access Control) enforcement
2. Tenant Isolation (School data isolation)
3. Authentication requirements
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from middleware.rbac import RBACMiddleware, Permission, ROLE_PERMISSIONS
from middleware.tenant_isolation import TenantIsolation, PLATFORM_ROLES


class TestRBAC:
    """Tests for Role-Based Access Control"""
    
    def test_platform_admin_has_all_permissions(self):
        """Platform Admin should have access to all permissions"""
        user = {"role": "platform_admin", "permissions": []}
        
        # Test critical permissions
        assert RBACMiddleware.has_permission(user, Permission.TENANTS_CREATE.value)
        assert RBACMiddleware.has_permission(user, Permission.USERS_CREATE.value)
        assert RBACMiddleware.has_permission(user, Permission.AUDIT_VIEW.value)
        assert RBACMiddleware.has_permission(user, Permission.TENANTS_MANAGE_AI.value)
    
    def test_school_principal_limited_permissions(self):
        """School Principal should have school-level permissions only"""
        user = {"role": "school_principal", "permissions": []}
        
        # Should have school management
        assert RBACMiddleware.has_permission(user, Permission.ACADEMIC_MANAGE_SECTIONS.value)
        assert RBACMiddleware.has_permission(user, Permission.USERS_CREATE.value)
        assert RBACMiddleware.has_permission(user, Permission.SCHEDULE_CREATE.value)
        
        # Should NOT have platform-level permissions
        assert not RBACMiddleware.has_permission(user, Permission.TENANTS_CREATE.value)
    
    def test_teacher_limited_permissions(self):
        """Teacher should have teaching-related permissions only"""
        user = {"role": "teacher", "permissions": []}
        
        # Should have teaching permissions
        assert RBACMiddleware.has_permission(user, Permission.ATTENDANCE_RECORD.value)
        assert RBACMiddleware.has_permission(user, Permission.ASSESSMENTS_GRADE.value)
        assert RBACMiddleware.has_permission(user, Permission.BEHAVIOUR_RECORD.value)
        
        # Should NOT have management permissions
        assert not RBACMiddleware.has_permission(user, Permission.USERS_CREATE.value)
        assert not RBACMiddleware.has_permission(user, Permission.TENANTS_CREATE.value)
    
    def test_student_minimal_permissions(self):
        """Student should have view-only permissions"""
        user = {"role": "student", "permissions": []}
        
        # Should have view permissions
        assert RBACMiddleware.has_permission(user, Permission.ASSESSMENTS_VIEW.value)
        assert RBACMiddleware.has_permission(user, Permission.SCHEDULE_VIEW.value)
        
        # Should NOT have any management permissions
        assert not RBACMiddleware.has_permission(user, Permission.ATTENDANCE_RECORD.value)
        assert not RBACMiddleware.has_permission(user, Permission.ASSESSMENTS_GRADE.value)
    
    def test_parent_limited_permissions(self):
        """Parent should have child monitoring permissions only"""
        user = {"role": "parent", "permissions": []}
        
        # Should have monitoring permissions
        assert RBACMiddleware.has_permission(user, Permission.ASSESSMENTS_VIEW.value)
        assert RBACMiddleware.has_permission(user, Permission.ATTENDANCE_VIEW.value)
        
        # Should NOT have any management permissions
        assert not RBACMiddleware.has_permission(user, Permission.USERS_CREATE.value)
    
    def test_custom_permissions_override(self):
        """Custom permissions should override role defaults"""
        user = {
            "role": "teacher",
            "permissions": [Permission.SCHEDULE_CREATE.value]  # Custom override
        }
        
        # Should have custom permission
        assert RBACMiddleware.has_permission(user, Permission.SCHEDULE_CREATE.value)
    
    def test_has_any_permission(self):
        """Test checking for any of multiple permissions"""
        user = {"role": "teacher", "permissions": []}
        
        # Teacher has ATTENDANCE_RECORD but not TENANTS_CREATE
        assert RBACMiddleware.has_any_permission(
            user, 
            [Permission.TENANTS_CREATE.value, Permission.ATTENDANCE_RECORD.value]
        )
        
        # Teacher has neither of these
        assert not RBACMiddleware.has_any_permission(
            user,
            [Permission.TENANTS_CREATE.value, Permission.USERS_DELETE.value]
        )


class TestTenantIsolation:
    """Tests for Tenant/School Data Isolation"""
    
    def test_platform_admin_is_platform_user(self):
        """Platform Admin should be identified as platform user"""
        user = {"role": "platform_admin"}
        assert TenantIsolation.is_platform_user(user)
    
    def test_school_principal_is_not_platform_user(self):
        """School Principal should not be platform user"""
        user = {"role": "school_principal", "tenant_id": "school_123"}
        assert not TenantIsolation.is_platform_user(user)
    
    def test_teacher_is_not_platform_user(self):
        """Teacher should not be platform user"""
        user = {"role": "teacher", "tenant_id": "school_123"}
        assert not TenantIsolation.is_platform_user(user)
    
    def test_get_user_tenant_id(self):
        """Should extract tenant_id correctly"""
        user = {"role": "teacher", "tenant_id": "school_123"}
        assert TenantIsolation.get_user_tenant_id(user) == "school_123"
        
        # Test with primary_tenant_id
        user2 = {"role": "teacher", "primary_tenant_id": "school_456"}
        assert TenantIsolation.get_user_tenant_id(user2) == "school_456"
    
    def test_tenant_filter_applied_for_non_platform_user(self):
        """Non-platform users should have tenant filter applied"""
        user = {"role": "teacher", "tenant_id": "school_123"}
        query = {"status": "active"}
        
        filtered = TenantIsolation.apply_tenant_filter(query, user)
        
        assert "tenant_id" in filtered
        assert filtered["tenant_id"] == "school_123"
        assert filtered["status"] == "active"
    
    def test_no_tenant_filter_for_platform_admin(self):
        """Platform Admin should see all data without tenant filter"""
        user = {"role": "platform_admin"}
        query = {"status": "active"}
        
        filtered = TenantIsolation.apply_tenant_filter(query, user)
        
        # Platform admin should NOT have tenant_id filter added
        assert filtered == query
    
    def test_validate_tenant_access_same_tenant(self):
        """User should access their own tenant data"""
        user = {"role": "teacher", "tenant_id": "school_123"}
        
        assert TenantIsolation.validate_tenant_access(user, "school_123")
    
    def test_validate_tenant_access_different_tenant(self):
        """User should NOT access different tenant data"""
        user = {"role": "teacher", "tenant_id": "school_123"}
        
        assert not TenantIsolation.validate_tenant_access(user, "school_456")
    
    def test_platform_admin_access_any_tenant(self):
        """Platform Admin should access any tenant"""
        user = {"role": "platform_admin"}
        
        assert TenantIsolation.validate_tenant_access(user, "school_123")
        assert TenantIsolation.validate_tenant_access(user, "school_456")
        assert TenantIsolation.validate_tenant_access(user, "any_tenant")


class TestDataLeakagePrevention:
    """Tests for preventing data leakage between tenants"""
    
    def test_query_with_tenant_filter(self):
        """Verify tenant filter is always applied for tenant users"""
        user = {"role": "school_principal", "tenant_id": "school_A"}
        
        # Any query should get tenant filter
        queries = [
            {},
            {"name": "test"},
            {"status": "active", "type": "class"},
            {"$or": [{"x": 1}, {"y": 2}]}
        ]
        
        for query in queries:
            filtered = TenantIsolation.apply_tenant_filter(query.copy(), user)
            assert filtered.get("tenant_id") == "school_A", f"Failed for query: {query}"
    
    def test_cross_tenant_access_blocked(self):
        """Verify cross-tenant access is blocked"""
        school_a_user = {"role": "teacher", "tenant_id": "school_A"}
        school_b_user = {"role": "teacher", "tenant_id": "school_B"}
        
        # User from school A should not access school B
        assert not TenantIsolation.validate_tenant_access(school_a_user, "school_B")
        
        # User from school B should not access school A  
        assert not TenantIsolation.validate_tenant_access(school_b_user, "school_A")
    
    def test_linked_roles_tenant_access(self):
        """User with linked roles should access allowed tenants"""
        user = {
            "role": "teacher",
            "tenant_id": "school_A",
            "linked_roles": [
                {"role": "teacher", "tenant_id": "school_B", "is_active": True}
            ]
        }
        
        # Should access primary tenant
        assert TenantIsolation.validate_tenant_access(user, "school_A")
        
        # Should access linked tenant
        assert TenantIsolation.validate_tenant_access(user, "school_B")
        
        # Should NOT access unrelated tenant
        assert not TenantIsolation.validate_tenant_access(user, "school_C")


class TestRoleHierarchy:
    """Tests for role hierarchy and permission inheritance"""
    
    def test_role_permissions_defined(self):
        """All roles should have permissions defined"""
        expected_roles = [
            "platform_admin",
            "school_principal",
            "teacher",
            "student",
            "parent"
        ]
        
        for role in expected_roles:
            assert role in ROLE_PERMISSIONS, f"Role {role} not defined"
            assert len(ROLE_PERMISSIONS[role]) > 0, f"Role {role} has no permissions"
    
    def test_platform_admin_has_most_permissions(self):
        """Platform Admin should have the most permissions"""
        admin_perms = len(ROLE_PERMISSIONS.get("platform_admin", []))
        
        for role, perms in ROLE_PERMISSIONS.items():
            if role != "platform_admin":
                assert len(perms) <= admin_perms, f"{role} has more perms than admin"
    
    def test_student_has_minimal_permissions(self):
        """Student should have minimal permissions"""
        student_perms = len(ROLE_PERMISSIONS.get("student", []))
        
        # Student should have fewer permissions than teacher
        teacher_perms = len(ROLE_PERMISSIONS.get("teacher", []))
        assert student_perms < teacher_perms


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
