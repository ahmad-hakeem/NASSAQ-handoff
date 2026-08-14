import pytest
from fastapi import HTTPException
from src.common.utils.tenant_scope import assert_school_access, resolve_school_id
from src.common.dto.enums import UserRole

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
    from src.core.middleware.tenant_isolation import TENANT_SCOPED_COLLECTIONS
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


class TestCanViewClassIndependentTeacher:
    """An Independent Teacher owns every class inside `itw_{user_id}`.

    Workspace class creation does not always write a `teacher_assignments`
    row, so gating IT owners on an assignment made their own class-level
    reads (attendance, class reports) 403. Ownership must be proven by the
    class's workspace id — never by tenant membership alone.
    """

    IT_USER = {
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "id": "it-user-1",
        "tenant_id": None,
        "school_id": None,
    }

    @staticmethod
    def _fake_lookup(owned_class_id, workspace_id):
        async def _gd_find_one(session, collection, query, *args, **kwargs):
            if collection == "classes":
                if query.get("id") == owned_class_id and query.get("school_id") == workspace_id:
                    return {"id": owned_class_id, "school_id": workspace_id}
                return None
            # No assignment / session rows exist in this workspace.
            return None
        return _gd_find_one

    @pytest.mark.asyncio
    async def test_owned_workspace_class_allowed_without_assignment(self, monkeypatch):
        import engines.sql_utils as sql_utils
        from src.common.utils.tenant_scope import can_view_class

        monkeypatch.setattr(
            sql_utils, "gd_find_one",
            self._fake_lookup("class-own", "itw_it-user-1"),
        )
        assert await can_view_class(None, self.IT_USER, "class-own") is True

    @pytest.mark.asyncio
    async def test_foreign_workspace_class_denied(self, monkeypatch):
        import engines.sql_utils as sql_utils
        from src.common.utils.tenant_scope import can_view_class

        # The class exists, but under ANOTHER independent teacher's workspace.
        monkeypatch.setattr(
            sql_utils, "gd_find_one",
            self._fake_lookup("class-own", "itw_someone-else"),
        )
        assert await can_view_class(None, self.IT_USER, "class-own") is False
