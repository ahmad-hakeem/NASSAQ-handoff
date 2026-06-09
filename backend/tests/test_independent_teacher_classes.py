"""
Independent-Teacher class creation tests
(spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §5.3, Task #188).

Covers the workspace-mode `POST /classes/create` flow:
  * Happy path — class is pinned to `itw_{user_id}`.
  * Spoofed `school_id` / `tenant_id` in the payload are ignored
    (server-side defensive tenant pin; spec §5.3 step 6).
  * Cross-workspace read isolation (IT-A cannot see IT-B's class).
  * Principal regression smoke — full-school create still works.

The quota 409 (6th class) is already covered by
`test_independent_teacher_phase0::test_class_quota_blocks_sixth_class_with_arabic_409`
and is intentionally not duplicated here.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find_one, gd_count
from auth_scope import independent_workspace_id
from quotas.independent_teacher import MAX_CLASSES


def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_independent_teacher() -> dict:
    """Mirror of the helper in test_independent_teacher_phase0 — duplicated
    here to keep this module self-contained."""
    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": now,
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
# Duplicate-name regression — distinct Arabic titles must not collide on
# auto-generated English labels (Grade N - section).
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_two_classes_same_grade_distinct_names_ok(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    shared_grade = "1"  # canonical grade id (IT now uses the shared catalogue)
    r1 = await client.post(
        "/classes/create",
        json={"name_ar": "حلقة تجويد أ", "grade_id": shared_grade, "capacity": 20},
        headers=h,
    )
    assert r1.status_code == 200, r1.text
    r2 = await client.post(
        "/classes/create",
        json={"name_ar": "حلقة تجويد ب", "grade_id": shared_grade, "capacity": 20},
        headers=h,
    )
    assert r2.status_code == 200, r2.text


@pytest.mark.asyncio
async def test_independent_teacher_duplicate_arabic_name_returns_structured_409(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    shared_grade = "2"  # canonical grade id (IT now uses the shared catalogue)
    first = await client.post(
        "/classes/create",
        json={"name_ar": "فصل موحد", "grade_id": shared_grade, "capacity": 15},
        headers=h,
    )
    assert first.status_code == 200, first.text
    dup = await client.post(
        "/classes/create",
        json={"name_ar": "فصل موحد", "grade_id": shared_grade, "capacity": 15},
        headers=h,
    )
    assert dup.status_code == 409, dup.text
    body = dup.json()
    err = body.get("error") or {}
    d = err.get("detail")
    assert isinstance(d, dict), body
    assert d.get("code") == "duplicate_class_name"
    assert "يوجد بالفعل" in (d.get("message") or "")


@pytest.mark.asyncio
async def test_independent_teacher_invalid_subject_id_returns_400(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    r = await client.post(
        "/classes/create",
        json={
            "name_ar": "فصل تجريبي",
            "grade_id": "3",
            "capacity": 12,
            "subject_id": str(uuid.uuid4()),
        },
        headers=h,
    )
    assert r.status_code == 400, r.text


# ----------------------------------------------------------------------
# (a) Happy path — workspace pin
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_create_class_pins_workspace(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    payload = {
        "name_ar": "حلقة القرآن - مستوى أول",
        "grade_id": "1",   # canonical grade id (IT now uses the shared catalogue)
        "capacity": 25,
    }
    resp = await client.post("/classes/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    cid = body["class"]["id"]

    row = await gd_find_one(db.session, "classes", {"id": cid})
    assert row is not None
    # The class MUST land in the IT's synthetic workspace, not the
    # user's nominal `tenant_id` (which is None for IT) nor any
    # client-supplied id.
    assert row["school_id"] == wsid
    assert row["school_id"].startswith("itw_")
    # IT is now canonicalized: the stored grade label is the canonical
    # catalogue label, not a free-text value.
    assert row.get("grade_level") == "الصف الأول الابتدائي"


# ----------------------------------------------------------------------
# (b) Defensive tenant pin — spoofed payload ids are ignored
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_create_class_ignores_spoofed_school_id(client):
    """ClassWizardCreate doesn't even declare `school_id` / `tenant_id`,
    so Pydantic strips them; this test pins that contract by asserting
    the persisted row uses the JWT-derived workspace regardless of what
    the client tries to send."""
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    foreign_school_id = "school_someone_else"
    foreign_tenant_id = "tenant_someone_else"
    payload = {
        "name_ar": "محاولة انتحال",
        "grade_id": "2",
        "capacity": 20,
        # Hostile fields — must have no effect.
        "school_id": foreign_school_id,
        "tenant_id": foreign_tenant_id,
    }
    resp = await client.post("/classes/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    cid = resp.json()["class"]["id"]

    row = await gd_find_one(db.session, "classes", {"id": cid})
    assert row["school_id"] == wsid, "Workspace pin failed — class leaked across tenants"
    assert row["school_id"] != foreign_school_id

    # And the foreign tenant didn't gain a row.
    foreign_count = await gd_count(db.session, "classes", {"school_id": foreign_school_id})
    assert foreign_count == 0


# ----------------------------------------------------------------------
# (c) Cross-workspace read isolation
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_cannot_read_other_workspace_class(client):
    user_a = await _mk_independent_teacher()
    user_b = await _mk_independent_teacher()
    wsid_a = independent_workspace_id(user_a)
    wsid_b = independent_workspace_id(user_b)
    h_a = _headers(user_a["id"], user_a["role"], wsid_a)
    h_b = _headers(user_b["id"], user_b["role"], wsid_b)

    # IT-A creates a class.
    payload = {"name_ar": "فصل خاص", "grade_id": "3", "capacity": 15}
    resp = await client.post("/classes/create", json=payload, headers=h_a)
    assert resp.status_code == 200, resp.text
    cid = resp.json()["class"]["id"]

    # IT-B's listing must not contain it.
    resp_list = await client.get("/classes", headers=h_b)
    assert resp_list.status_code == 200, resp_list.text
    items = resp_list.json()
    items = items if isinstance(items, list) else (items.get("classes") or items.get("items") or [])
    assert all(it.get("id") != cid for it in items), "Cross-workspace class leak via /classes"


# ----------------------------------------------------------------------
# (d) Principal regression — full-school create still works
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_get_class_by_id_isolation(client):
    """Direct ID lookup must also be tenant-scoped — IT-B knowing IT-A's
    class id (e.g. via a leak / log) must not be able to read it via
    GET /classes/{class_id}. Returns the safe Arabic 404."""
    user_a = await _mk_independent_teacher()
    user_b = await _mk_independent_teacher()
    wsid_a = independent_workspace_id(user_a)
    wsid_b = independent_workspace_id(user_b)
    h_a = _headers(user_a["id"], user_a["role"], wsid_a)
    h_b = _headers(user_b["id"], user_b["role"], wsid_b)

    payload = {"name_ar": "فصل سري", "grade_id": "4", "capacity": 12}
    resp = await client.post("/classes/create", json=payload, headers=h_a)
    assert resp.status_code == 200, resp.text
    cid = resp.json()["class"]["id"]

    # Owner can read.
    resp_owner = await client.get(f"/classes/{cid}", headers=h_a)
    assert resp_owner.status_code == 200, resp_owner.text

    # Foreign IT must get a clean 404 (not 200, not 500).
    resp_foreign = await client.get(f"/classes/{cid}", headers=h_b)
    assert resp_foreign.status_code == 404, resp_foreign.text
    body = resp_foreign.json()
    msg = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert "غير موجود" in msg


# ----------------------------------------------------------------------
# Quota boundary — 6th class blocked through the wired endpoint
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_create_class_quota_boundary(client):
    """Boundary check at the create-class surface used by Task #188.
    Complements (does not replace) the lower-level quota helper test in
    test_independent_teacher_phase0."""
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    # Pre-seed MAX_CLASSES rows directly to keep the test fast.
    for _ in range(MAX_CLASSES):
        await gd_insert(db.session, "classes", {
            "id": str(uuid.uuid4()),
            "name": "x",
            "school_id": wsid,
            "tenant_id": wsid,
            "capacity": 10,
            "current_students": 0,
            "is_active": True,
        })

    payload = {"name_ar": "فصل زائد", "grade_id": "الصف الخامس", "capacity": 10}
    resp = await client.post("/classes/create", json=payload, headers=h)
    assert resp.status_code == 409, resp.text
    body = resp.json()
    msg = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert "الحد الأقصى" in msg


# ----------------------------------------------------------------------
# Auto-create grade level path (frontend submit step 3)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_auto_create_grade_level_pins_workspace(client):
    """The IT submit handler may POST /grade-levels for an unmatched
    free-text label. The server must override any client-supplied
    school_id with the IT's synthetic workspace."""
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    payload = {
        "name": "الصف السادس الابتدائي",  # canonical approved label
        "name_en": "Grade 6",
        "order": 1,
        "is_active": True,
        "school_id": "school_someone_else",  # hostile — must be ignored
    }
    resp = await client.post("/grade-levels", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["school_id"] == wsid, "Grade-level row leaked across tenants"
    row = await gd_find_one(db.session, "grade_levels", {"id": body["id"]})
    assert row["school_id"] == wsid


# ----------------------------------------------------------------------
# Canonical stage enforcement (data-integrity boundary)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_grade_level_rejects_noncanonical(client):
    """An IT may only persist one of the twelve product-approved grades.
    A tampered / free-text label must be rejected with 422 so no
    inconsistent stage variant can ever be stored."""
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    for bad in ("الصف السادس", "1-أ", "اول ابتدائي", "garbage", ""):
        resp = await client.post(
            "/grade-levels",
            json={"name": bad, "order": 1, "is_active": True, "school_id": "x"},
            headers=h,
        )
        assert resp.status_code == 422, f"{bad!r} should be rejected, got {resp.status_code}"


@pytest.mark.asyncio
async def test_independent_teacher_grade_level_canonical_is_idempotent(client):
    """Submitting the same canonical stage twice must reuse the existing
    row (no duplicate stage variants) and normalize the stored value."""
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    label = "الصف الأول الابتدائي"
    r1 = await client.post(
        "/grade-levels",
        json={"name": label, "order": 9, "is_active": True, "school_id": "x"},
        headers=h,
    )
    assert r1.status_code == 200, r1.text
    r2 = await client.post(
        "/grade-levels",
        json={"name": label, "order": 1, "is_active": True, "school_id": "x"},
        headers=h,
    )
    assert r2.status_code == 200, r2.text
    assert r1.json()["id"] == r2.json()["id"], "Canonical stage was duplicated"

    rows = await gd_count(db.session, "grade_levels", {"school_id": wsid, "name_ar": label})
    assert rows == 1, "Duplicate canonical grade rows persisted"

    stored = await gd_find_one(db.session, "grade_levels", {"id": r1.json()["id"]})
    assert stored["name_ar"] == label
    assert stored["stage"] == "primary"
    assert stored["order"] == 1  # canonical grade number, not the submitted 9


@pytest.mark.asyncio
async def test_principal_create_class_regression(client):
    """Smoke test: the same /classes/create endpoint must still serve
    full-school principals. Defensive IT-only pin must not affect them."""
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
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "email": f"p-{uid}@t.test",
        "full_name": "Principal",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": now,
    })
    h = _headers(uid, UserRole.SCHOOL_PRINCIPAL.value, school_id)

    payload = {
        "name_ar": "فصل تجريبي",
        "grade_id": "1",
        "section": "أ",
        "capacity": 30,
    }
    resp = await client.post("/classes/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    cid = resp.json()["class"]["id"]
    row = await gd_find_one(db.session, "classes", {"id": cid})
    assert row["school_id"] == school_id
