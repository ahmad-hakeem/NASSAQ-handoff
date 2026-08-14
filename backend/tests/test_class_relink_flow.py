"""
Tests for the post-restore class re-link flow (Task #648).

Covers `GET /classes/{id}/relink-candidates` and the six
`POST /classes/{id}/relink/{table}` endpoints added in
`backend/routes/academics_class_routes.py`.

Locks in:
  * Happy path — per-row vs. "all" reactivation only touches matching rows.
  * IT workspace pin (spec §8 inv. 3) — IT-B gets a 404, not 403/200, when
    poking IT-A's class id; nothing in IT-A's workspace is mutated.
  * Unsupported `{table}` path component returns 404 with a safe Arabic
    message and emits NO audit row.
  * Per-row mode with an empty ids list returns 400 and emits NO audit row.
  * Successful calls emit exactly one `audit_logs` row whose
    `action` / `entity_type` / `entity_id` / `school_id` / `performed_by`
    columns match the call.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find, gd_find_one, gd_count
from src.core.guards.tenant_guard import independent_workspace_id


def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_independent_teacher() -> dict:
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


async def _mk_class(school_id: str, active: bool = True) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "tenant_id": school_id,
        "name": f"C-{cid[:6]}",
        "capacity": 20,
        "current_students": 0,
        "is_active": active,
    })
    return cid


async def _seed_inactive_dependents(class_id: str, school_id: str, n: int = 3) -> dict:
    """Seed inactive dependents in two GenericDocument-backed tables so we
    don't need to satisfy FKs (teachers/subjects rows) for this test."""
    cs_ids, cl_ids = [], []
    for i in range(n):
        cs = str(uuid.uuid4())
        await gd_insert(db.session, "class_subjects", {
            "id": cs,
            "class_id": class_id,
            "school_id": school_id,
            "subject_id": f"subj-{i}",
            "subject_name": f"Subject {i}",
            "weekly_periods": 3,
            "is_active": False,
        })
        cs_ids.append(cs)
        cl = str(uuid.uuid4())
        await gd_insert(db.session, "curriculum_lessons", {
            "id": cl,
            "class_id": class_id,
            "school_id": school_id,
            "subject_id": f"subj-{i}",
            "title": f"Lesson {i}",
            "week": i + 1,
            "is_active": False,
        })
        cl_ids.append(cl)
    return {"class_subjects": cs_ids, "curriculum_lessons": cl_ids}


async def _count_audits(class_id: str, action: str = "relink") -> int:
    return await gd_count(db.session, "audit_logs", {
        "action": action,
        "entity_id": class_id,
    })


# ----------------------------------------------------------------------
# (1) Happy path — list candidates, then reactivate per-row and "all"
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_relink_lists_and_reactivates_per_row_only(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    cid = await _mk_class(wsid)
    seeded = await _seed_inactive_dependents(cid, wsid, n=3)

    # List candidates — must group, count, and preview both tables.
    resp = await client.get(f"/classes/{cid}/relink-candidates", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    groups = body["groups"]
    assert groups["class_subjects"]["count"] == 3
    assert {r["id"] for r in groups["class_subjects"]["items"]} == set(seeded["class_subjects"])
    assert groups["curriculum_lessons"]["count"] == 3
    # Untouched tables show count=0 but are still present in the response.
    assert groups["teacher_assignments"]["count"] == 0

    # Per-row reactivate: pick exactly one class_subjects row.
    target = seeded["class_subjects"][0]
    resp = await client.post(
        f"/classes/{cid}/relink/class_subjects",
        json={"ids": [target]},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reactivated"] == 1
    assert body["table"] == "class_subjects"
    assert body["class_id"] == cid

    # Only the picked row flipped; siblings remain inactive.
    flipped = await gd_find_one(db.session, "class_subjects", {"id": target})
    assert flipped["is_active"] is True
    others = await gd_count(
        db.session, "class_subjects",
        {"class_id": cid, "is_active": False},
    )
    assert others == 2

    # And the other table was not touched as a side-effect.
    cl_inactive = await gd_count(
        db.session, "curriculum_lessons",
        {"class_id": cid, "is_active": False},
    )
    assert cl_inactive == 3


@pytest.mark.asyncio
async def test_relink_all_reactivates_every_inactive_row_in_table(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    cid = await _mk_class(wsid)
    await _seed_inactive_dependents(cid, wsid, n=4)

    resp = await client.post(
        f"/classes/{cid}/relink/curriculum_lessons",
        json={"all": True},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["reactivated"] == 4

    still_inactive = await gd_count(
        db.session, "curriculum_lessons",
        {"class_id": cid, "is_active": False},
    )
    assert still_inactive == 0


# ----------------------------------------------------------------------
# (2) IT cross-workspace 404 (spec §8 inv. 3)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_relink_candidates_cross_workspace_returns_404(client):
    user_a = await _mk_independent_teacher()
    user_b = await _mk_independent_teacher()
    wsid_a = independent_workspace_id(user_a)
    wsid_b = independent_workspace_id(user_b)
    cid = await _mk_class(wsid_a)
    await _seed_inactive_dependents(cid, wsid_a, n=2)

    h_b = _headers(user_b["id"], user_b["role"], wsid_b)
    resp = await client.get(f"/classes/{cid}/relink-candidates", headers=h_b)
    assert resp.status_code == 404, resp.text
    msg = (resp.json().get("error") or {}).get("message") or resp.json().get("detail") or ""
    assert "غير موجود" in msg


@pytest.mark.asyncio
async def test_relink_reactivate_cross_workspace_returns_404_and_no_mutation(client):
    user_a = await _mk_independent_teacher()
    user_b = await _mk_independent_teacher()
    wsid_a = independent_workspace_id(user_a)
    wsid_b = independent_workspace_id(user_b)
    cid = await _mk_class(wsid_a)
    seeded = await _seed_inactive_dependents(cid, wsid_a, n=2)
    h_b = _headers(user_b["id"], user_b["role"], wsid_b)

    resp = await client.post(
        f"/classes/{cid}/relink/class_subjects",
        json={"ids": seeded["class_subjects"]},
        headers=h_b,
    )
    assert resp.status_code == 404, resp.text

    # Nothing in IT-A's workspace got reactivated.
    inactive_after = await gd_count(
        db.session, "class_subjects",
        {"class_id": cid, "is_active": False},
    )
    assert inactive_after == 2
    # No audit row was emitted on the foreign attempt.
    assert await _count_audits(cid) == 0


# ----------------------------------------------------------------------
# (3) Unsupported table → 404
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_relink_unsupported_table_guard_returns_404_and_no_audit(client):
    """The six relink endpoints each delegate to `_reactivate_dependents`,
    which carries an internal allow-list guard:

        if table not in _RELINK_TABLES:
            raise HTTPException(status_code=404, detail="نوع غير مدعوم")

    The HTTP layer can't ever reach the guard (the router only mounts the
    six approved paths), but the guard is the safety net if a new route
    is ever added without updating the allow-list. We exercise it directly
    here and assert NO audit row is emitted on the rejection."""
    from src.modules.academics.controllers.academics_class_routes import _reactivate_dependents, RelinkRequest
    from fastapi import HTTPException

    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    cid = await _mk_class(wsid)

    with pytest.raises(HTTPException) as exc:
        await _reactivate_dependents(
            cid,
            "students",  # not in _RELINK_TABLES
            RelinkRequest(all=True),
            current_user=user,
        )
    assert exc.value.status_code == 404
    assert "غير مدعوم" in str(exc.value.detail)
    assert await _count_audits(cid) == 0


# ----------------------------------------------------------------------
# (4) Empty ids in per-row mode → 400
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_relink_per_row_empty_ids_returns_400_and_no_audit(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    cid = await _mk_class(wsid)
    await _seed_inactive_dependents(cid, wsid, n=2)

    resp = await client.post(
        f"/classes/{cid}/relink/class_subjects",
        json={"ids": []},
        headers=h,
    )
    assert resp.status_code == 400, resp.text
    msg = (resp.json().get("error") or {}).get("message") or resp.json().get("detail") or ""
    assert "لم يتم تحديد" in msg

    # No dependents were flipped, and no audit row was written.
    inactive_after = await gd_count(
        db.session, "class_subjects",
        {"class_id": cid, "is_active": False},
    )
    assert inactive_after == 2
    assert await _count_audits(cid) == 0


# ----------------------------------------------------------------------
# (5) Audit-log row shape
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_relink_emits_audit_row_with_expected_shape(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    cid = await _mk_class(wsid)
    seeded = await _seed_inactive_dependents(cid, wsid, n=2)

    resp = await client.post(
        f"/classes/{cid}/relink/class_subjects",
        json={"ids": [seeded["class_subjects"][0]]},
        headers=h,
    )
    assert resp.status_code == 200, resp.text

    rows = await gd_find(db.session, "audit_logs", {
        "action": "relink",
        "entity_id": cid,
    })
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["action"] == "relink"
    assert row["entity_type"] == "class_subjects"
    assert row["entity_id"] == cid
    assert row["school_id"] == wsid
    assert row["performed_by"] == user["id"]

    # A second call lands a second audit row — one per relink call.
    resp2 = await client.post(
        f"/classes/{cid}/relink/curriculum_lessons",
        json={"all": True},
        headers=h,
    )
    assert resp2.status_code == 200, resp2.text
    assert await _count_audits(cid) == 2


# ----------------------------------------------------------------------
# (6) Soft-deleted class is not eligible for relink (precondition guard)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_relink_on_inactive_class_returns_404(client):
    """The relink surface requires the class itself to already be active —
    otherwise the caller must restore it first via /classes/{id}/restore.
    This pins the precondition the wizard relies on."""
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    cid = await _mk_class(wsid, active=False)
    await _seed_inactive_dependents(cid, wsid, n=1)

    list_resp = await client.get(f"/classes/{cid}/relink-candidates", headers=h)
    assert list_resp.status_code == 404, list_resp.text

    apply_resp = await client.post(
        f"/classes/{cid}/relink/class_subjects",
        json={"all": True},
        headers=h,
    )
    assert apply_resp.status_code == 404, apply_resp.text
    assert await _count_audits(cid) == 0
