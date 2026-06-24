"""Regression tests: the follow-up report (كشف المتابعة) performance-task
column must reflect the EXACT configured per-skill point value, not a flat
``special_skill`` default.

Reported bug: a skill configured for 1 point was awarded correctly in the
student score ledger (Task #1076) but the follow-up sheet المهام الأدائية column
showed 3, because ``compute_session_scores`` re-derived a flat
``special_skill`` (default 3) for every recorded skill instead of reading the
value that was actually awarded.

The fix: ``record_skill`` persists the resolved configured points on the
``session_interactions`` row, and ``compute_session_scores`` reads that stored
value (falling back to the ``special_skill`` default only for legacy rows that
predate the change, and for behaviour-strip skills that carry no configured
value).

``compute_session_scores`` is the single computation that both
``build_followup_hydration`` (what the teacher sees) and
``commit_session_scores`` (what hits the gradebook) consume, so asserting its
``performance_points`` bucket guards both paths.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, session_engine
from engines.session_engine import (
    DEFAULT_SCORE_RULES,
    BehaviourCategory,
    InteractionType,
)
from engines.sql_utils import gd_find_one, gd_insert


DEFAULT_SKILL_PTS = DEFAULT_SCORE_RULES["special_skill"]


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
        "date": "2026-06-24",
        "status": "in_progress",
        "start_time": now,
        "teacher_id": teacher_id,
        "attendance_approved": True,
        "created_at": now,
    })
    return session_id


async def _mk_skill_type(tenant_id: str, points=None) -> str:
    skill_id = f"skill-{str(uuid.uuid4())[:8]}"
    doc = {
        "id": skill_id,
        "name": "Skill",
        "name_ar": "التنظيم",
        "category": "general",
        "school_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if points is not None:
        doc["points"] = points
    await gd_insert(db.session, "skills_types", doc)
    return skill_id


async def _performance_points(session_id: str, student_id: str) -> int:
    computed = await session_engine.compute_session_scores(session_id)
    return computed["students"][student_id]["performance_points"]


# ─────────────────────────────────────────────────────────────────
# The reported bug: a 1-point skill must show 1, never 3
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_followup_performance_reflects_configured_skill_points(client, tenant_a):
    """A skill configured as 1 point contributes exactly 1 to the performance
    bucket the follow-up sheet renders — not the flat special_skill default."""
    teacher_id = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(tenant_a, class_id)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    skill_id = await _mk_skill_type(tenant_a, points=1)

    result = await session_engine.record_skill(
        session_id=session_id,
        student_id=student_id,
        skill_type_id=skill_id,
        teacher_id=teacher_id,
    )
    # Ledger already correct (Task #1076) ...
    assert result["score_change"] == 1
    # ... and now the follow-up performance bucket matches it.
    assert await _performance_points(session_id, student_id) == 1


@pytest.mark.asyncio
async def test_recorded_skill_interaction_persists_points(client, tenant_a):
    """The skill interaction row now carries the awarded points so the report
    can read it back (the mechanism behind the fix)."""
    teacher_id = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(tenant_a, class_id)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    skill_id = await _mk_skill_type(tenant_a, points=1)

    await session_engine.record_skill(
        session_id=session_id,
        student_id=student_id,
        skill_type_id=skill_id,
        teacher_id=teacher_id,
    )
    interaction = await gd_find_one(
        db.session,
        "session_interactions",
        {"session_id": session_id, "behaviour_category": BehaviourCategory.SKILL.value},
    )
    assert interaction is not None
    assert interaction.get("points") == 1


@pytest.mark.asyncio
async def test_followup_performance_null_points_uses_default(client, tenant_a):
    """A registered skill type with no configured points keeps the legacy
    behaviour: the performance bucket falls back to the special_skill default."""
    teacher_id = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(tenant_a, class_id)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)
    skill_id = await _mk_skill_type(tenant_a, points=None)

    await session_engine.record_skill(
        session_id=session_id,
        student_id=student_id,
        skill_type_id=skill_id,
        teacher_id=teacher_id,
    )
    assert await _performance_points(session_id, student_id) == DEFAULT_SKILL_PTS


@pytest.mark.asyncio
async def test_followup_performance_custom_skill_uses_override(client, tenant_a):
    """A custom (ad-hoc) skill contributes its configured points_override to the
    performance bucket, not the default."""
    teacher_id = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(tenant_a, class_id)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)

    await session_engine.record_skill(
        session_id=session_id,
        student_id=student_id,
        skill_type_id=None,
        teacher_id=teacher_id,
        custom_name="مهارة مخصصة",
        points_override=2,
    )
    assert await _performance_points(session_id, student_id) == 2


@pytest.mark.asyncio
async def test_followup_performance_legacy_interaction_uses_default(client, tenant_a):
    """A legacy skill interaction recorded before points were stored (no
    ``points`` field) still falls back to the special_skill default, so
    historical follow-up sheets are unchanged."""
    class_id = await _mk_class(tenant_a)
    teacher_id = await _mk_user("teacher", tenant_a)
    student_id = await _mk_student(tenant_a, class_id)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)

    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "session_interactions", {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "student_id": student_id,
        "type": InteractionType.BEHAVIOUR.value,
        "interaction_type": InteractionType.BEHAVIOUR.value,
        "behaviour_category": BehaviourCategory.SKILL.value,
        "behaviour_type": "skill-legacy",
        "recorded_by": teacher_id,
        "recorded_at": now,
        "timestamp": now,
    })
    assert await _performance_points(session_id, student_id) == DEFAULT_SKILL_PTS
