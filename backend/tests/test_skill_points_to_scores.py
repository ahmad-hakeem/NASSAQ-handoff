"""
Task #1080 — regression tests for skill point values flowing into scores.

The fix under guard: the per-skill configured point value is the single source
of truth for the score awarded when a skill is recorded. A future change to the
engine score-resolution (``record_skill`` ~3924) or the create/read path
(``create_skill_type`` ~3024) must not silently reintroduce the default-3 bug.

Invariants covered:
- Creating a skill type with ``points=1`` persists the value and it is returned
  by GET /skills-types.
- ``session_engine.record_skill`` awards the stored ``points`` for a registered
  skill type (authoritative — it wins even over a client-supplied override).
- It falls back to the global ``special_skill`` default when the registered
  type's ``points`` is NULL.
- For custom (ad-hoc) skills it awards the ``points_override``, and the default
  when the override is absent.
- The awarded value lands in the student score ledger (score flow), tenant
  isolation still rejects a cross-tenant skill (404), and undo compensates the
  exact awarded value back to zero and marks the skill record reversed.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token, session_engine
from engines.session_engine import DEFAULT_SCORE_RULES
from engines.sql_utils import gd_find, gd_find_one, gd_insert


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

async def _mk_user(role: str, tenant_id: str) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": role, "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test", "full_name": "مستخدم", "is_active": True,
        "password_hash": "x",
    })
    return uid


def _headers(user_id: str, role: str, tenant_id: str) -> dict:
    token = create_access_token({
        "sub": user_id, "role": role, "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_class(tenant_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": tenant_id, "tenant_id": tenant_id, "name": "1A",
    })
    return cid


async def _mk_student(tenant_id: str, class_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "tenant_id": tenant_id, "school_id": tenant_id,
        "class_id": class_id, "full_name": "طالب", "is_active": True,
    })
    return sid


async def _mk_session(tenant_id: str, class_id: str, teacher_id: str) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "school_id": tenant_id,
        "tenant_id": tenant_id,
        "class_id": class_id,
        "date": "2026-06-16",
        "status": "in_progress",
        "start_time": now,
        "teacher_id": teacher_id,
        "attendance_approved": True,
        "created_at": now,
    })
    return session_id


async def _mk_skill_type(tenant_id: str, points=None) -> str:
    """Insert a registered skill type for ``tenant_id`` with the given points.

    ``points=None`` leaves the column unset (NULL) so the engine should fall
    back to the global ``special_skill`` default.
    """
    skill_id = f"skill-{str(uuid.uuid4())[:8]}"
    doc = {
        "id": skill_id,
        "name": "Skill",
        "name_ar": "مهارة",
        "category": "general",
        "school_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if points is not None:
        doc["points"] = points
    await gd_insert(db.session, "skills_types", doc)
    return skill_id


async def _ledger_total(student_id: str) -> int:
    rows = await gd_find(db.session, "student_score_ledger", {"student_id": student_id}, limit=500)
    return sum(int(r.get("score_change", 0) or 0) for r in rows)


# ─────────────────────────────────────────────────────────────────
# Create / read path
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_skill_type_persists_points_and_returned_by_get(client, tenant_a):
    """POST /skills-types with points=1 persists the value and GET returns it."""
    principal_id = await _mk_user("school_principal", tenant_a)
    hdrs = _headers(principal_id, "school_principal", tenant_a)

    create_resp = await client.post(
        "/skills-types",
        json={"name": "Focus", "name_ar": "تركيز", "points": 1},
        headers=hdrs,
    )
    assert create_resp.status_code == 200, create_resp.text
    skill_id = create_resp.json()["skill"]["id"]

    # Persisted value is exactly 1 (not coerced to the default 3).
    skill_doc = await gd_find_one(db.session, "skills_types", {"id": skill_id})
    assert skill_doc is not None
    assert skill_doc.get("points") == 1

    # GET /skills-types surfaces the configured value back to the caller.
    list_resp = await client.get("/skills-types", headers=hdrs)
    assert list_resp.status_code == 200, list_resp.text
    by_id = {s["id"]: s for s in list_resp.json()}
    assert skill_id in by_id
    assert by_id[skill_id].get("points") == 1


@pytest.mark.asyncio
async def test_create_skill_type_omits_points_when_not_positive(client, tenant_a):
    """A missing/non-positive points value is left unset so the skill keeps the
    default behaviour (NULL → special_skill at scoring time)."""
    principal_id = await _mk_user("school_principal", tenant_a)
    hdrs = _headers(principal_id, "school_principal", tenant_a)

    # No points supplied.
    r1 = await client.post(
        "/skills-types", json={"name": "A", "name_ar": "أ"}, headers=hdrs,
    )
    assert r1.status_code == 200, r1.text
    d1 = await gd_find_one(db.session, "skills_types", {"id": r1.json()["skill"]["id"]})
    assert d1.get("points") is None

    # Zero / negative are rejected (not stored).
    r2 = await client.post(
        "/skills-types", json={"name": "B", "name_ar": "ب", "points": 0}, headers=hdrs,
    )
    assert r2.status_code == 200, r2.text
    d2 = await gd_find_one(db.session, "skills_types", {"id": r2.json()["skill"]["id"]})
    assert d2.get("points") is None


# ─────────────────────────────────────────────────────────────────
# Engine score resolution — configured value is the source of truth
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_skill_awards_stored_points_for_registered_type(client, tenant_a):
    """A registered skill type's stored ``points`` is awarded verbatim and lands
    in the student's score ledger."""
    teacher_id = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(tenant_a, class_id)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    skill_id = await _mk_skill_type(tenant_a, points=7)

    result = await session_engine.record_skill(
        session_id=session_id,
        student_id=student_id,
        skill_type_id=skill_id,
        teacher_id=teacher_id,
    )
    assert result["score_change"] == 7
    assert await _ledger_total(student_id) == 7


@pytest.mark.asyncio
async def test_registered_points_override_client_supplied_override(client, tenant_a):
    """The stored value is authoritative: a client-supplied points_override must
    NOT override a registered type's configured points."""
    teacher_id = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(tenant_a, class_id)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    skill_id = await _mk_skill_type(tenant_a, points=4)

    result = await session_engine.record_skill(
        session_id=session_id,
        student_id=student_id,
        skill_type_id=skill_id,
        teacher_id=teacher_id,
        points_override=99,
    )
    assert result["score_change"] == 4
    assert await _ledger_total(student_id) == 4


@pytest.mark.asyncio
async def test_record_skill_falls_back_to_default_when_points_null(client, tenant_a):
    """A registered type with NULL points falls back to the global
    ``special_skill`` default."""
    default_pts = DEFAULT_SCORE_RULES["special_skill"]
    teacher_id = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(tenant_a, class_id)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    skill_id = await _mk_skill_type(tenant_a, points=None)

    result = await session_engine.record_skill(
        session_id=session_id,
        student_id=student_id,
        skill_type_id=skill_id,
        teacher_id=teacher_id,
    )
    assert result["score_change"] == default_pts
    assert await _ledger_total(student_id) == default_pts


@pytest.mark.asyncio
async def test_custom_skill_awards_points_override(client, tenant_a):
    """A custom (ad-hoc) skill awards its points_override; absent override falls
    back to the default."""
    default_pts = DEFAULT_SCORE_RULES["special_skill"]
    teacher_id = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    student_a = await _mk_student(tenant_a, class_id)
    student_b = await _mk_student(tenant_a, class_id)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)

    # Override present → awarded.
    r1 = await session_engine.record_skill(
        session_id=session_id,
        student_id=student_a,
        skill_type_id=None,
        teacher_id=teacher_id,
        custom_name="مهارة مخصصة",
        points_override=6,
    )
    assert r1["score_change"] == 6
    assert await _ledger_total(student_a) == 6

    # Override absent → default rule.
    r2 = await session_engine.record_skill(
        session_id=session_id,
        student_id=student_b,
        skill_type_id=None,
        teacher_id=teacher_id,
        custom_name="مهارة بدون قيمة",
    )
    assert r2["score_change"] == default_pts
    assert await _ledger_total(student_b) == default_pts


# ─────────────────────────────────────────────────────────────────
# Tenant isolation + undo correctness (still asserted)
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cross_tenant_skill_rejected_no_score_awarded(client, tenant_a, tenant_b):
    """A skill owned by tenant A is rejected (404) inside a tenant B session and
    awards no score."""
    skill_a = await _mk_skill_type(tenant_a, points=5)

    teacher_b = await _mk_user("teacher", tenant_b)
    class_b = await _mk_class(tenant_b)
    student_b = await _mk_student(tenant_b, class_b)
    session_b = await _mk_session(tenant_b, class_b, teacher_b)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await session_engine.record_skill(
            session_id=session_b,
            student_id=student_b,
            skill_type_id=skill_a,
            teacher_id=teacher_b,
        )
    assert exc.value.status_code == 404
    assert await _ledger_total(student_b) == 0


@pytest.mark.asyncio
async def test_undo_compensates_exact_awarded_points(client, tenant_a):
    """Undo inserts a compensating ledger entry equal to the awarded value and
    nets the student score back to zero."""
    teacher_id = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(tenant_a, class_id)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    skill_id = await _mk_skill_type(tenant_a, points=8)

    rec = await session_engine.record_skill(
        session_id=session_id,
        student_id=student_id,
        skill_type_id=skill_id,
        teacher_id=teacher_id,
    )
    assert rec["score_change"] == 8
    assert await _ledger_total(student_id) == 8

    await session_engine.undo_last_action(
        session_id=session_id,
        teacher_id=teacher_id,
        user_id=teacher_id,
    )

    # Net score is back to zero (8 + -8): the compensation matches the exact
    # awarded value, not the default rule.
    assert await _ledger_total(student_id) == 0
    undo_rows = await gd_find(
        db.session, "student_score_ledger", {"student_id": student_id, "category": "undo"}, limit=10,
    )
    assert any(int(r.get("score_change", 0) or 0) == -8 for r in undo_rows), (
        "Undo must compensate exactly -8 (the awarded value)"
    )
