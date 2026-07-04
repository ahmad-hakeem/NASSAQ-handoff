"""
Phase 0 groundwork tests for the Independent-Teacher account
(spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §4).

Covers:
  * B-2 — `require_full_school_tenant` returns Arabic 403 on routers
    reserved for full school tenants.
  * B-4 — TenantIsolation derives `itw_{user_id}` for IT accounts so
    one IT cannot see another IT's classes/students.
  * B-5 — IT v1 quotas (5 classes, 200 students, 1 academic year)
    surface as a friendly Arabic 409.
  * B-6 — `GET /auth/me/permissions` returns the canonical permission
    list for the caller.
"""
import uuid

import pytest
import pytest_asyncio

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert
from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
)


def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_independent_teacher() -> dict:
    """Create an IT user (no real tenant) and bootstrap its synthetic
    workspace `schools` row so create-resource calls don't trip on a
    missing FK / lazy-materialiser (which Phase 0 deliberately removed).
    """
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-Workspace-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    return user


# ----------------------------------------------------------------------
# B-2 — capability gate
# ----------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    # Each entry covers a distinct router family wired with
    # `dependencies=[Depends(require_full_school_tenant)]` in app/routes.py.
    ("GET",  "/standby/candidates"),                       # standby_router
    ("GET",  "/teacher-attendance"),                       # teacher_attendance_router
    ("GET",  "/bulk/template/students"),                   # bulk_routes (template)
    ("GET",  "/bulk/export/students"),                     # bulk_routes (export)
    ("GET",  "/v1/hakeem-plan/tasks"),                     # hakeem_plan_routes
    ("GET",  "/smart-scheduling/timetable/versions"),      # scheduling_smart_router
    ("GET",  "/school/settings"),                          # school_settings_router
    ("GET",  "/principal/search-users"),                   # principal_mgmt_router
])
async def test_full_school_tenant_gate_denies_independent_teacher(client, method, path):
    user = await _mk_independent_teacher()
    # Phase 1 (#183): pass the synthetic workspace id so the perimeter
    # workspace-materialised gate is a no-op and the phase-0 router gate
    # under test (`require_full_school_tenant`) is exercised.
    h = _headers(user["id"], user["role"], independent_workspace_id(user))
    resp = await client.request(method, path, headers=h)
    # Anything reserved for full school tenants must be a clean 403 with
    # the canonical Arabic message — never a 404 / 500 / 405.
    assert resp.status_code == 403, (path, resp.status_code, resp.text)
    body = resp.json()
    msg = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert INDEPENDENT_TEACHER_DENIED_AR in msg, (path, body)


@pytest.mark.asyncio
async def test_communication_broadcast_denies_independent_teacher(client):
    user = await _mk_independent_teacher()
    h = _headers(user["id"], user["role"], independent_workspace_id(user))
    resp = await client.post(
        "/communication/broadcast",
        headers=h,
        json={"title": "x", "content": "y", "audience": "all", "channels": ["in_app"]},
    )
    assert resp.status_code == 403, resp.text
    body = resp.json()
    msg = (body.get("error") or {}).get("message") or ""
    assert INDEPENDENT_TEACHER_DENIED_AR in msg


# ----------------------------------------------------------------------
# B-4 — cross-IT tenant isolation
# ----------------------------------------------------------------------
async def _seed_class(wsid: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "name": "C", "school_id": wsid, "tenant_id": wsid,
        "capacity": 10, "current_students": 0, "is_active": True,
    })
    return cid


async def _seed_student(wsid: str, class_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": wsid, "tenant_id": wsid,
        "class_id": class_id, "full_name": "ط", "full_name_ar": "ط",
        "is_active": True,
    })
    return sid


async def _seed_assessment(wsid: str, class_id: str) -> str:
    aid = str(uuid.uuid4())
    await gd_insert(db.session, "assessments", {
        "id": aid, "school_id": wsid, "tenant_id": wsid,
        "class_id": class_id, "name": "ا", "title": "ا",
        "type": "quiz", "max_score": 10, "weight": 1.0,
    })
    return aid


@pytest.mark.asyncio
async def test_two_independent_teachers_cannot_see_each_others_classes(client):
    a = await _mk_independent_teacher()
    b = await _mk_independent_teacher()
    h_a = _headers(a["id"], a["role"], independent_workspace_id(a))
    h_b = _headers(b["id"], b["role"], independent_workspace_id(b))

    payload = {
        "name_ar": "فصل أ",
        "grade_id": str(uuid.uuid4()),
        "class_type": "regular",
        "capacity": 10,
    }
    create_a = await client.post("/classes/create", json=payload, headers=h_a)
    assert create_a.status_code == 200, create_a.text

    list_b = await client.get("/classes/", headers=h_b)
    assert list_b.status_code == 200, list_b.text
    items_b = list_b.json()
    if isinstance(items_b, dict):
        items_b = items_b.get("items") or items_b.get("classes") or []
    # B's workspace must be empty — A's class must NOT leak across IT
    # workspaces (synthetic itw_{user_id} scoping).
    assert items_b == [] or all(
        (it.get("school_id") or it.get("tenant_id")) == independent_workspace_id(b)
        for it in items_b
    )


@pytest.mark.asyncio
async def test_independent_teachers_cannot_see_each_others_students(client):
    a = await _mk_independent_teacher()
    b = await _mk_independent_teacher()
    wsid_a = independent_workspace_id(a)
    wsid_b = independent_workspace_id(b)
    cid_a = await _seed_class(wsid_a)
    sid_a = await _seed_student(wsid_a, cid_a)

    h_b = _headers(b["id"], b["role"], wsid_b)
    resp = await client.get("/students", headers=h_b)
    assert resp.status_code == 200, resp.text
    items = resp.json() if isinstance(resp.json(), list) else resp.json().get("items", [])
    # B must never see any record whose school_id is A's workspace.
    assert all(it.get("school_id") != wsid_a for it in items)
    assert all(it.get("id") != sid_a for it in items)


@pytest.mark.asyncio
async def test_independent_teachers_cannot_see_each_others_assessments(client):
    a = await _mk_independent_teacher()
    b = await _mk_independent_teacher()
    wsid_a = independent_workspace_id(a)
    cid_a = await _seed_class(wsid_a)
    aid_a = await _seed_assessment(wsid_a, cid_a)

    h_b = _headers(b["id"], b["role"], independent_workspace_id(b))
    resp = await client.get("/assessments", headers=h_b)
    assert resp.status_code == 200, resp.text
    items = resp.json() if isinstance(resp.json(), list) else resp.json().get("items", [])
    assert all(it.get("school_id") != wsid_a for it in items)
    assert all(it.get("id") != aid_a for it in items)


@pytest.mark.asyncio
async def test_independent_teachers_cannot_see_each_others_attendance(client):
    a = await _mk_independent_teacher()
    b = await _mk_independent_teacher()
    wsid_a = independent_workspace_id(a)
    cid_a = await _seed_class(wsid_a)
    sid_a = await _seed_student(wsid_a, cid_a)
    rec_id = str(uuid.uuid4())
    await gd_insert(db.session, "attendance", {
        "id": rec_id, "school_id": wsid_a, "tenant_id": wsid_a,
        "class_id": cid_a, "student_id": sid_a,
        "date": "2026-05-12", "status": "present",
    })

    h_b = _headers(b["id"], b["role"], independent_workspace_id(b))
    # B querying A's class must NOT receive A's attendance row even if
    # the class id were guessed; cross-IT isolation must hold at the
    # tenant-scope level rather than relying on path obscurity.
    resp = await client.get(f"/attendance/class/{cid_a}", headers=h_b)
    # Either 200 with an empty list or 403/404 — anything except a leak.
    assert resp.status_code in (200, 403, 404), resp.text
    if resp.status_code == 200:
        items = resp.json() if isinstance(resp.json(), list) else resp.json().get("items", [])
        assert all(it.get("id") != rec_id for it in items)
        assert all(it.get("school_id") != wsid_a for it in items)


# ----------------------------------------------------------------------
# B-5 — quotas
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_class_quota_allows_class_beyond_old_cap(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    # Pre-seed beyond the old cap directly to keep the test fast.
    for _ in range(6):
        await gd_insert(db.session, "classes", {
            "id": str(uuid.uuid4()),
            "name": "x",
            "school_id": wsid,
            "tenant_id": wsid,
            "capacity": 10,
            "current_students": 0,
            "is_active": True,
        })

    payload = {
        "name_ar": "فصل إضافي",
        "grade_id": str(uuid.uuid4()),
        "class_type": "regular",
        "capacity": 10,
    }
    resp = await client.post("/classes/create", json=payload, headers=h)
    assert resp.status_code in (200, 201), resp.text


@pytest.mark.asyncio
async def test_academic_year_quota_blocks_second_year(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    await gd_insert(db.session, "academic_years", {
        "id": str(uuid.uuid4()),
        "name": "1446",
        "name_ar": "1446",
        "school_id": wsid,
        "is_current": True,
        "start_date": "2025-09-01",
        "end_date": "2026-06-01",
        "status": "active",
    })

    resp = await client.post(
        "/academic-years",
        headers=h,
        json={
            "name": "1447",
            "start_date": "2026-09-01",
            "end_date": "2027-06-01",
            "is_current": False,
        },
    )
    assert resp.status_code == 409, resp.text
    body = resp.json()
    msg = (body.get("error") or {}).get("message") or ""
    assert "عاماً دراسياً واحداً" in msg


# ----------------------------------------------------------------------
# B-6 — /auth/me/permissions and /auth/permissions/role/{role}
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_auth_me_permissions_returns_independent_teacher_set(client):
    user = await _mk_independent_teacher()
    h = _headers(user["id"], user["role"], None)
    resp = await client.get("/auth/me/permissions", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] == UserRole.INDEPENDENT_TEACHER.value
    perms = set(body["permissions"])
    # A representative subset of the canonical IT permission list.
    assert "schedule.view" in perms
    assert "attendance.record" in perms
    assert "assessments.grade" in perms
    assert "assessments.edit" in perms  # Task #194 — IT Phase 1 grant
    assert "notifications.view" in perms


@pytest.mark.asyncio
async def test_independent_teacher_slice_grants_assessments_edit():
    """Task #194 — spec §5.5: IT slice must include ASSESSMENTS_EDIT so an
    IT can fix a typo / due date / rubric on an assessment they created."""
    from middleware.rbac import ROLE_PERMISSIONS, Permission
    assert Permission.ASSESSMENTS_EDIT.value in ROLE_PERMISSIONS["independent_teacher"]


@pytest.mark.asyncio
async def test_role_permissions_endpoint_returns_independent_teacher_set(client):
    """Phase 0 §4.B-6 — `/auth/permissions/role/{role}` is the wizard's
    backend source of truth for the assignable IT permission ids."""
    from dependencies import db as _db
    from engines.sql_utils import gd_insert as _gd_insert
    admin_id = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    await _gd_insert(_db.session, "schools", {
        "id": sid, "name": "S", "code": f"S{sid[:6]}",
        "status": "active", "country": "SA", "language": "ar",
    })
    await _gd_insert(_db.session, "users", {
        "id": admin_id, "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": sid, "email": f"p-{admin_id}@t.test",
        "full_name": "P", "is_active": True, "password_hash": "x",
    })
    h = _headers(admin_id, UserRole.SCHOOL_PRINCIPAL.value, sid)
    resp = await client.get("/auth/permissions/role/independent_teacher", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] == "independent_teacher"
    perms = set(body["permissions"])
    assert "schedule.view" in perms
    assert "attendance.record" in perms
