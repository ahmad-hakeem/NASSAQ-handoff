import pytest
from fastapi import HTTPException
from backend.utils.tenant_scope import assert_school_access, resolve_school_id
from backend.models.enums import UserRole

PRINCIPAL_A = {"role": UserRole.SCHOOL_PRINCIPAL.value, "tenant_id": "school-A", "school_id": "school-A"}
PRINCIPAL_B = {"role": UserRole.SCHOOL_PRINCIPAL.value, "tenant_id": "school-B", "school_id": "school-B"}
PLATFORM_ADMIN = {"role": UserRole.PLATFORM_ADMIN.value, "tenant_id": None, "school_id": None}
TEACHER_A = {"role": UserRole.TEACHER.value, "tenant_id": "school-A", "school_id": "school-A"}


class TestAssertSchoolAccess:
    def test_principal_same_school_allowed(self):
        assert_school_access(PRINCIPAL_A, "school-A")  # no raise

    def test_principal_other_school_denied(self):
        with pytest.raises(HTTPException) as exc:
            assert_school_access(PRINCIPAL_A, "school-B")
        assert exc.value.status_code == 403

    def test_platform_admin_any_school_allowed(self):
        assert_school_access(PLATFORM_ADMIN, "school-A")
        assert_school_access(PLATFORM_ADMIN, "school-B")

    def test_teacher_same_school_allowed_by_default(self):
        assert_school_access(TEACHER_A, "school-A")

    def test_teacher_other_school_denied(self):
        with pytest.raises(HTTPException) as exc:
            assert_school_access(TEACHER_A, "school-B")
        assert exc.value.status_code == 403

    def test_missing_tenant_id_denied(self):
        with pytest.raises(HTTPException) as exc:
            assert_school_access({"role": UserRole.SCHOOL_PRINCIPAL.value}, "school-A")
        assert exc.value.status_code == 403


class TestResolveSchoolId:
    def test_principal_no_override_uses_tenant(self):
        assert resolve_school_id(PRINCIPAL_A, None) == "school-A"

    def test_principal_override_with_own_tenant_allowed(self):
        assert resolve_school_id(PRINCIPAL_A, "school-A") == "school-A"

    def test_principal_override_with_other_tenant_denied(self):
        with pytest.raises(HTTPException) as exc:
            resolve_school_id(PRINCIPAL_A, "school-B")
        assert exc.value.status_code == 403

    def test_platform_admin_no_override_returns_none(self):
        assert resolve_school_id(PLATFORM_ADMIN, None) is None

    # --- Task #368: X-School-Context impersonation bypass regression tests ---

    def test_platform_admin_plain_token_with_override_denied(self):
        """Plain platform-admin token + X-School-Context override must be rejected (403).

        This is the exact bypass described in task #368: a stolen or long-lived
        platform-admin access token must NOT grant cross-tenant access via header.
        """
        with pytest.raises(HTTPException) as exc:
            resolve_school_id(PLATFORM_ADMIN, "school-X")
        assert exc.value.status_code == 403

    def test_platform_admin_impersonating_matching_override_allowed(self):
        """Properly switched impersonation token with matching header override is allowed."""
        impersonating_admin = {
            "role": UserRole.PLATFORM_ADMIN.value,
            "tenant_id": "school-X",
            "school_id": None,
            "is_impersonating": True,
        }
        assert resolve_school_id(impersonating_admin, "school-X") == "school-X"

    def test_platform_admin_impersonating_mismatched_override_denied(self):
        """Impersonation token + override that doesn't match token tenant must be 403."""
        impersonating_admin = {
            "role": UserRole.PLATFORM_ADMIN.value,
            "tenant_id": "school-X",
            "school_id": None,
            "is_impersonating": True,
        }
        with pytest.raises(HTTPException) as exc:
            resolve_school_id(impersonating_admin, "school-Y")
        assert exc.value.status_code == 403

    def test_platform_admin_impersonating_missing_tenant_claim_denied(self):
        """Impersonation token without tenant_id claim must be explicitly rejected (403)."""
        impersonating_admin_no_tenant = {
            "role": UserRole.PLATFORM_ADMIN.value,
            "tenant_id": None,
            "school_id": None,
            "is_impersonating": True,
        }
        with pytest.raises(HTTPException) as exc:
            resolve_school_id(impersonating_admin_no_tenant, "school-X")
        assert exc.value.status_code == 403


def test_tenant_scoped_collections_includes_timetable_tables():
    from backend.middleware.tenant_isolation import TENANT_SCOPED_COLLECTIONS
    required = {
        "timetables",
        "schedule_sessions",
        "timetable_sessions",
        "time_slots",
        "teacher_assignments",
        "timetable_constraints",
        "school_constraints",
        "administrative_constraints",
        "admin_constraints",
        "constraint_patterns",
    }
    missing = required - TENANT_SCOPED_COLLECTIONS
    assert not missing, f"Missing timetable tables in tripwire: {missing}"
