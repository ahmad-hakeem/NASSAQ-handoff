"""
Independent-Teacher student creation tests
(spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §5.3, §5.6,
Task #192).

Covers the workspace-mode `POST /student-wizard/create` flow:
  * No parent payload — student lands with NULL parent_id and NULL
    pending_parent_*; no parents row is materialised.
  * Partial parent payload (only name/email, no phone) — pending_parent_*
    columns populated, parents row still NOT materialised.
  * Spoofed `school_id` / `tenant_id` — defensive tenant pin overrides.
  * Quota — 201st student returns 409 with Arabic message.
  * Cross-tenant `GET /students/{id}` — returns 404 (not 403) so the
    route never confirms cross-tenant existence.
  * Principal regression — full-school create (with parent) still works.
"""
import uuid

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find_one, gd_count
from auth_scope import independent_workspace_id
from quotas.independent_teacher import MAX_STUDENTS


def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_independent_teacher() -> dict:
    """Create an IT user and seed its synthetic workspace as a `schools`
    row so FK-style lookups resolve."""
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


def _student_payload(**overrides) -> dict:
    base = {
        "full_name": "طالب اختبار",
        "gender": "male",
        "date_of_birth": "2015-01-01",
        "education_level": "primary",
        "grade_id": "الصف الأول",
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------------------
# (a) No parent payload — pending_parent_* stay NULL, no parents row.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_create_student_without_parent(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    payload = _student_payload(parent=None)
    resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    sid = resp.json()["student"]["id"]

    row = await gd_find_one(db.session, "students", {"id": sid})
    assert row is not None
    assert row["school_id"] == wsid
    assert row.get("parent_id") is None
    assert row.get("pending_parent_name") is None
    assert row.get("pending_parent_phone") is None
    assert row.get("pending_parent_email") is None

    # No parents row should have been materialised in this workspace.
    parents_in_ws = await gd_count(db.session, "parents", {"school_id": wsid})
    assert parents_in_ws == 0


# ----------------------------------------------------------------------
# (b) Partial parent payload — phone-only still goes to pending columns
# (parent is FULLY optional in workspace mode per spec §5.6).
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_create_student_phone_only_writes_pending(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    payload = _student_payload(parent={"phone": "+966500000001"})
    resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    sid = resp.json()["student"]["id"]

    row = await gd_find_one(db.session, "students", {"id": sid})
    assert row.get("parent_id") is None
    assert row.get("pending_parent_phone") == "+966500000001"
    assert row.get("pending_parent_name") is None
    assert row.get("pending_parent_email") is None

    parents_in_ws = await gd_count(db.session, "parents", {"school_id": wsid})
    assert parents_in_ws == 0, "Phone-only parent must NOT materialise a parents row"


# ----------------------------------------------------------------------
# (b2) Name + email partial — also goes to pending, no parents row.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_create_student_name_email_writes_pending(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    payload = _student_payload(parent={
        "full_name": "أحمد ولي الأمر",
        "email": "guardian@example.com",
    })
    resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    sid = resp.json()["student"]["id"]

    row = await gd_find_one(db.session, "students", {"id": sid})
    assert row.get("parent_id") is None
    assert row.get("pending_parent_name") == "أحمد ولي الأمر"
    assert row.get("pending_parent_email") == "guardian@example.com"
    assert row.get("pending_parent_phone") is None

    parents_in_ws = await gd_count(db.session, "parents", {"school_id": wsid})
    assert parents_in_ws == 0


# ----------------------------------------------------------------------
# (c) Defensive tenant pin — spoofed school_id ignored.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_create_student_ignores_spoofed_school_id(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    foreign = "school_someone_else"
    payload = _student_payload(
        parent=None,
        school_id=foreign,
        tenant_id=foreign,
    )
    resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    sid = resp.json()["student"]["id"]

    row = await gd_find_one(db.session, "students", {"id": sid})
    assert row["school_id"] == wsid
    assert row["school_id"] != foreign
    foreign_count = await gd_count(db.session, "students", {"school_id": foreign})
    assert foreign_count == 0


# ----------------------------------------------------------------------
# (d) Quota — 201st student blocked with Arabic 409.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_create_student_quota_boundary(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    # Pre-seed MAX_STUDENTS rows directly to keep the test fast.
    for _ in range(MAX_STUDENTS):
        await gd_insert(db.session, "students", {
            "id": str(uuid.uuid4()),
            "school_id": wsid,
            "full_name": "x",
            "is_active": True,
        })

    resp = await client.post("/student-wizard/create",
                             json=_student_payload(parent=None), headers=h)
    assert resp.status_code == 409, resp.text
    body = resp.json()
    msg = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert "الحد الأقصى" in msg


# ----------------------------------------------------------------------
# (e) Cross-tenant GET /students/{id} returns 404 (NOT 403).
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_get_student_cross_tenant_returns_404(client):
    user_a = await _mk_independent_teacher()
    user_b = await _mk_independent_teacher()
    wsid_a = independent_workspace_id(user_a)
    wsid_b = independent_workspace_id(user_b)
    h_a = _headers(user_a["id"], user_a["role"], wsid_a)
    h_b = _headers(user_b["id"], user_b["role"], wsid_b)

    # IT-A creates a student.
    resp = await client.post("/student-wizard/create",
                             json=_student_payload(parent=None), headers=h_a)
    assert resp.status_code == 200, resp.text
    sid = resp.json()["student"]["id"]

    # Owner can read.
    resp_owner = await client.get(f"/students/{sid}", headers=h_a)
    assert resp_owner.status_code == 200, resp_owner.text

    # Foreign IT MUST get a clean 404 (not 200, not 403).
    resp_foreign = await client.get(f"/students/{sid}", headers=h_b)
    assert resp_foreign.status_code == 404, resp_foreign.text
    body = resp_foreign.json()
    msg = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert "غير موجود" in msg


# ----------------------------------------------------------------------
# (f) Principal regression — full-school create still requires parent.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_principal_create_student_without_parent_rejected(client):
    """The defensive IT-only optional-parent path must NOT loosen the
    school-admin contract: omitting `parent` for a principal still 422s."""
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": "Test School",
        "code": school_id,
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "email": f"p-{uid}@t.test",
        "full_name": "Principal",
        "is_active": True,
        "password_hash": "x",
    })
    h = _headers(uid, UserRole.SCHOOL_PRINCIPAL.value, school_id)

    resp = await client.post("/student-wizard/create",
                             json=_student_payload(parent=None), headers=h)
    assert resp.status_code == 422, resp.text
    body = resp.json()
    msg = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert "ولي الأمر" in msg


# ----------------------------------------------------------------------
# (g) Principal regression — full-school create WITH parent succeeds and
# materialises a real parents row (workspace-mode gate must NOT bleed
# into the school-admin path).
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_principal_create_student_with_parent_succeeds(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": "Test School",
        "code": school_id,
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "email": f"p2-{uid}@t.test",
        "full_name": "Principal2",
        "is_active": True,
        "password_hash": "x",
    })
    h = _headers(uid, UserRole.SCHOOL_PRINCIPAL.value, school_id)

    payload = _student_payload(parent={
        "full_name": "محمد ولي الأمر",
        "phone": "+966500000099",
        "relationship": "father",
    })
    resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    sid = resp.json()["student"]["id"]

    row = await gd_find_one(db.session, "students", {"id": sid})
    assert row["school_id"] == school_id
    # Standard school-admin path materialises a parents row + parent_id link.
    assert row.get("parent_id") is not None
    parents_in_school = await gd_count(db.session, "parents", {"school_id": school_id})
    assert parents_in_school == 1
    # Pending columns must remain unused on the standard path.
    assert row.get("pending_parent_name") is None
    assert row.get("pending_parent_phone") is None
