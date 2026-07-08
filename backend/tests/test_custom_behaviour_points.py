"""Regression tests: a CUSTOM live-session behaviour (سلوك) must apply its
teacher-configured point value — not a hardcoded default of 2.

Reported bug: when a teacher creates a custom positive/negative behaviour with a
value (e.g. 1 point) and records it for a student during the lesson, the
confirmation toast said +2 and the participation (المشاركة) column in كشف
المتابعة also moved by 2, because the custom behaviour id (``bhv_*``) is not a
key in ``DEFAULT_SCORE_RULES`` and both ``record_behaviour`` and
``compute_session_scores`` fell back to the hardcoded ±2.

The fix mirrors the per-skill points snapshot: the route/engine accept a
``points_override`` for the custom behaviour, ``record_behaviour`` resolves the
signed ``score_change`` from it and persists ``points`` on the
``session_interactions`` row, and ``compute_session_scores`` reads that stored
value (falling back to the rules/default only for rows that carry no snapshot,
so predefined behaviours and historical sessions are unchanged).

``compute_session_scores`` is the single computation consumed by both
``build_followup_hydration`` (what the teacher sees) and
``commit_session_scores`` (what hits the gradebook), so asserting its
``participation_points`` bucket guards both paths — for both the School Teacher
and Independent Teacher accounts (same route + engine).
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_find, gd_find_one, gd_insert
from engines.session_engine import (
    TeacherSessionEngine as SessionEngine,
    InteractionType,
    BehaviourCategory,
)


def _engine():
    class _DBShim:
        @property
        def session(self):
            return db.session
    return SessionEngine(_DBShim())


async def _mk_user(tenant_id: str) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": "teacher", "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test", "full_name": "معلم", "is_active": True,
        "password_hash": "x",
    })
    return uid


async def _mk_class(tenant_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": tenant_id, "tenant_id": tenant_id, "name": "1A",
    })
    return cid


async def _mk_subject(tenant_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid, "school_id": tenant_id, "tenant_id": tenant_id,
        "name": "الرياضيات", "name_ar": "الرياضيات",
    })
    return sid


async def _mk_student(tenant_id: str, class_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "tenant_id": tenant_id, "school_id": tenant_id,
        "class_id": class_id, "full_name": "طالب", "is_active": True,
    })
    return sid


async def _mk_session(tenant_id: str, class_id: str, subject_id: str,
                      teacher_id: str) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "school_id": tenant_id,
        "tenant_id": tenant_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "date": "2026-06-25",
        "status": "in_progress",
        "start_time": now,
        "teacher_id": teacher_id,
        "attendance_approved": True,
        "created_at": now,
    })
    return session_id


async def _mk_teacher_auth(tenant_id: str):
    uid = await _mk_user(tenant_id)
    token = create_access_token({"sub": uid, "role": "teacher", "tenant_id": tenant_id})
    return uid, {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────
# The reported bug: a custom 1-point behaviour must apply 1, not 2
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_custom_positive_behaviour_applies_configured_value(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    sid = await _mk_student(tenant_a, class_id)

    eng = _engine()
    res = await eng.record_behaviour(
        session_id=session_id, student_id=sid,
        category=BehaviourCategory.POSITIVE, behaviour_type="bhv_1700000000000",
        details=None, teacher_id=teacher_id, points_override=1,
    )
    assert res["score_change"] == 1

    computed = await eng.compute_session_scores(session_id)
    assert computed["students"][sid]["participation_points"] == 1


@pytest.mark.asyncio
async def test_custom_negative_behaviour_applies_configured_value(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    sid = await _mk_student(tenant_a, class_id)

    eng = _engine()
    res = await eng.record_behaviour(
        session_id=session_id, student_id=sid,
        category=BehaviourCategory.NEGATIVE, behaviour_type="bhv_1700000000001",
        details=None, teacher_id=teacher_id, points_override=3,
    )
    # A negative custom behaviour deducts the configured magnitude, signed.
    assert res["score_change"] == -3


@pytest.mark.asyncio
async def test_custom_behaviour_interaction_snapshots_points(tenant_a):
    """The interaction row carries the resolved points so the report re-derives
    the real value instead of the hardcoded default."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    sid = await _mk_student(tenant_a, class_id)

    eng = _engine()
    await eng.record_behaviour(
        session_id=session_id, student_id=sid,
        category=BehaviourCategory.POSITIVE, behaviour_type="bhv_1700000000002",
        details=None, teacher_id=teacher_id, points_override=1,
    )
    interaction = await gd_find_one(
        db.session, "session_interactions",
        {"session_id": session_id, "behaviour_type": "bhv_1700000000002"},
    )
    assert interaction is not None
    assert interaction.get("points") == 1


@pytest.mark.asyncio
async def test_predefined_behaviour_still_uses_rules(tenant_a):
    """No regression: a predefined behaviour with no override keeps resolving
    from the score rules (respect = +2)."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    sid = await _mk_student(tenant_a, class_id)

    eng = _engine()
    res = await eng.record_behaviour(
        session_id=session_id, student_id=sid,
        category=BehaviourCategory.POSITIVE, behaviour_type="respect",
        details=None, teacher_id=teacher_id,
    )
    assert res["score_change"] == 2
    computed = await eng.compute_session_scores(session_id)
    assert computed["students"][sid]["participation_points"] == 2


@pytest.mark.asyncio
async def test_legacy_custom_behaviour_without_points_uses_default(tenant_a):
    """No regression: a custom behaviour interaction recorded before the fix
    (no ``points`` snapshot) still falls back to the ±2 default so historical
    follow-up sheets are unchanged."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    sid = await _mk_student(tenant_a, class_id)

    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "session_interactions", {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "student_id": sid,
        "type": InteractionType.BEHAVIOUR.value,
        "interaction_type": InteractionType.BEHAVIOUR.value,
        "behaviour_category": BehaviourCategory.POSITIVE.value,
        "behaviour_type": "bhv_legacy",
        "recorded_by": teacher_id,
        "recorded_at": now,
        "timestamp": now,
    })
    eng = _engine()
    computed = await eng.compute_session_scores(session_id)
    assert computed["students"][sid]["participation_points"] == 2


@pytest.mark.asyncio
async def test_custom_behaviour_route_reflects_in_followup_record(client, tenant_a):
    """End-to-end through the real route (shared by School + Independent
    Teacher): a custom +1 behaviour moves the participation column by 1, not 2."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id, headers = await _mk_teacher_auth(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    sid = await _mk_student(tenant_a, class_id)

    rec = await client.post(
        f"/session/{session_id}/behaviour",
        json={
            "student_id": sid, "category": "positive",
            "behaviour_type": "bhv_1700000000003", "points_override": 1,
        },
        headers=headers,
    )
    assert rec.status_code == 200, rec.text
    assert rec.json()["score_change"] == 1

    resp = await client.get(f"/session/{session_id}/followup-record", headers=headers)
    assert resp.status_code == 200, resp.text
    col = await gd_find_one(db.session, "grade_columns",
                            {"class_id": class_id, "name": "المشاركة"})
    assert col, "participation grade column should have been auto-created"
    assert resp.json()["data"][sid][col["id"]] == 1
