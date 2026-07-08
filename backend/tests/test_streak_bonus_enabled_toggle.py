"""
Tests for the excellence (التميز) streak-bonus ENABLE/DISABLE toggle.

The teacher can turn the excellence bonus on/off per class+subject from the
during-lesson settings dialog (خيارات الحصة). The flag is stored durably on the
``session_settings`` record as ``streak_bonus_enabled`` (mirroring
``homework_enabled`` / ``recitation_enabled``) and defaults to ``True`` so the
legacy behaviour is preserved for any lesson whose teacher never touched it.

Behaviour contract:
- ENABLED (or no setting at all): the bonus fires normally — the configured
  value is awarded on every 5th consecutive correct answer.
- DISABLED: NO bonus is ever added; only the base correct-answer points count.
  The per-session bonus VALUE override is irrelevant while disabled.
- Runtime scoring must respect a mid-session toggle immediately (no restart).

Mirrors the harness in test_streak_bonus_value.py.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_update_one, gd_insert, gd_find_one
from engines.session_engine import (
    TeacherSessionEngine as SessionEngine,
    AnswerResult,
)
from routes.role_dashboards_mod import save_session_settings


# ──────────────────── helpers ────────────────────

def _engine():
    class _DBShim:
        @property
        def session(self):
            return db.session
    return SessionEngine(_DBShim())


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


async def _mk_user(tenant_id: str, role: str = "teacher") -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": role, "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test", "full_name": "معلم", "is_active": True,
        "password_hash": "x",
    })
    return uid


async def _mk_student(tenant_id: str, class_id: str, name: str = "طالب") -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "tenant_id": tenant_id, "school_id": tenant_id,
        "class_id": class_id, "full_name": name, "is_active": True,
    })
    return sid


async def _mk_session(
    tenant_id: str, class_id: str, subject_id: str,
    teacher_id: str = None,
    streak_bonus_value: int = None,
) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": session_id,
        "school_id": tenant_id,
        "tenant_id": tenant_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "date": "2026-06-21",
        "status": "in_progress",
        "start_time": now,
        "attendance_approved": True,
        "created_at": now,
    }
    if teacher_id:
        doc["teacher_id"] = teacher_id
    if streak_bonus_value is not None:
        doc["streak_bonus_value"] = streak_bonus_value
    await gd_insert(db.session, "class_sessions", doc)
    return session_id


async def _mk_settings(
    tenant_id: str, class_id: str, subject_id: str,
    *, streak_bonus_enabled: bool = None, session_id: str = None,
):
    """Insert a durable session_settings record. Only sets streak_bonus_enabled
    when explicitly provided so we can also test the 'record exists but has no
    such key' legacy path (which must default to enabled)."""
    doc = {
        "id": str(uuid.uuid4()),
        "class_id": class_id,
        "subject_id": subject_id,
        "tenant_id": tenant_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if session_id is not None:
        doc["session_id"] = session_id
    if streak_bonus_enabled is not None:
        doc["streak_bonus_enabled"] = streak_bonus_enabled
    await gd_insert(db.session, "session_settings", doc)


async def _record_answer(eng, session_id, student_id, teacher_id,
                         result: AnswerResult = AnswerResult.CORRECT):
    return await eng.record_answer(
        session_id=session_id,
        student_id=student_id,
        result=result,
        teacher_id=teacher_id,
    )


# ──────────────────── _is_streak_bonus_enabled unit tests ────────────────────

@pytest.mark.asyncio
async def test_enabled_defaults_true_when_no_settings_record(tenant_a):
    """No session_settings row at all → bonus enabled (legacy behaviour)."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)

    eng = _engine()
    assert await eng._is_streak_bonus_enabled(session_id) is True


@pytest.mark.asyncio
async def test_enabled_defaults_true_when_key_absent_from_settings(tenant_a):
    """A settings row that predates the toggle (no streak_bonus_enabled key) →
    enabled, so existing tenants keep awarding the bonus after deploy."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    await _mk_settings(tenant_a, class_id, subject_id, session_id=session_id)

    eng = _engine()
    assert await eng._is_streak_bonus_enabled(session_id) is True


@pytest.mark.asyncio
async def test_enabled_true_when_setting_true(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    await _mk_settings(tenant_a, class_id, subject_id,
                       streak_bonus_enabled=True, session_id=session_id)

    eng = _engine()
    assert await eng._is_streak_bonus_enabled(session_id) is True


@pytest.mark.asyncio
async def test_enabled_false_when_setting_false(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    await _mk_settings(tenant_a, class_id, subject_id,
                       streak_bonus_enabled=False, session_id=session_id)

    eng = _engine()
    assert await eng._is_streak_bonus_enabled(session_id) is False


# ──────────────────── award-path e2e (enabled/disabled) ────────────────────

@pytest.mark.asyncio
async def test_disabled_awards_no_bonus_on_fifth_correct(tenant_a):
    """DISABLED: the 5th consecutive correct answer awards ONLY the base points
    (5) — no bonus is added and the interaction carries streak_bonus == 0."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    await _mk_settings(tenant_a, class_id, subject_id,
                       streak_bonus_enabled=False, session_id=session_id)
    student_id = await _mk_student(tenant_a, class_id)

    eng = _engine()
    results = [
        await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.CORRECT)
        for _ in range(5)
    ]
    for n, r in enumerate(results, start=1):
        assert r["streak_bonus"] == 0, f"answer #{n}: no bonus while disabled"
        assert r["score_change"] == r["base_points"] == 5, f"answer #{n}: base only"


@pytest.mark.asyncio
async def test_disabled_ignores_configured_value(tenant_a):
    """DISABLED overrides the per-session VALUE: even with streak_bonus_value=3
    set on the session, no bonus is awarded."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id, streak_bonus_value=3,
    )
    await _mk_settings(tenant_a, class_id, subject_id,
                       streak_bonus_enabled=False, session_id=session_id)
    student_id = await _mk_student(tenant_a, class_id)

    eng = _engine()
    results = [
        await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.CORRECT)
        for _ in range(5)
    ]
    assert results[4]["streak_bonus"] == 0
    assert results[4]["score_change"] == 5


@pytest.mark.asyncio
async def test_disabled_summary_has_no_bonus(tenant_a):
    """كشف المتابعة → درجات التميز: a disabled session accrues no bonus points."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    await _mk_settings(tenant_a, class_id, subject_id,
                       streak_bonus_enabled=False, session_id=session_id)
    student_id = await _mk_student(tenant_a, class_id)

    eng = _engine()
    for _ in range(10):
        await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.CORRECT)

    summary = await eng.get_streak_bonus_summary(session_id)
    pts = (summary.get(student_id) or {}).get("points", 0)
    cnt = (summary.get(student_id) or {}).get("count", 0)
    assert pts == 0 and cnt == 0, "disabled session must accrue no excellence bonus"


@pytest.mark.asyncio
async def test_enabled_awards_bonus_on_fifth_correct(tenant_a):
    """ENABLED explicitly: the 5th consecutive correct answer awards the default
    bonus of 5 (base 5 + bonus 5 = 10)."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    await _mk_settings(tenant_a, class_id, subject_id,
                       streak_bonus_enabled=True, session_id=session_id)
    student_id = await _mk_student(tenant_a, class_id)

    eng = _engine()
    results = [
        await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.CORRECT)
        for _ in range(5)
    ]
    assert results[4]["streak_bonus"] == 5
    assert results[4]["score_change"] == 10


@pytest.mark.asyncio
async def test_default_no_settings_still_awards_bonus(tenant_a):
    """Regression guard: with NO session_settings record the bonus still fires
    exactly as before this feature (default enabled)."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    student_id = await _mk_student(tenant_a, class_id)

    eng = _engine()
    results = [
        await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.CORRECT)
        for _ in range(5)
    ]
    assert results[4]["streak_bonus"] == 5
    assert results[4]["score_change"] == 10


@pytest.mark.asyncio
async def test_mid_session_disable_takes_effect_immediately(tenant_a):
    """Toggling OFF mid-session stops bonuses on the very next fire, without a
    restart. First run of 5 (enabled) awards a bonus; after disabling, the second
    run of 5 (the 10th consecutive correct) awards none."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    await _mk_settings(tenant_a, class_id, subject_id,
                       streak_bonus_enabled=True, session_id=session_id)
    student_id = await _mk_student(tenant_a, class_id)

    eng = _engine()
    first = [
        await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.CORRECT)
        for _ in range(5)
    ]
    assert first[4]["streak_bonus"] == 5, "enabled run must award the bonus"

    # Teacher flips the toggle OFF mid-lesson.
    await gd_update_one(
        db.session, "session_settings",
        {"class_id": class_id, "subject_id": subject_id, "tenant_id": tenant_a},
        {"streak_bonus_enabled": False},
    )

    second = [
        await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.CORRECT)
        for _ in range(5)
    ]
    # The 10th consecutive correct answer would normally fire a bonus, but the
    # toggle is now off → no bonus.
    assert second[4]["streak_bonus"] == 0, "disabled mid-run must suppress the next bonus"
    assert second[4]["score_change"] == 5


@pytest.mark.asyncio
async def test_mid_session_enable_takes_effect_immediately(tenant_a):
    """Toggling ON mid-session resumes bonuses on the next fire. First run of 5
    (disabled) awards none; after enabling, the 10th consecutive correct awards
    the bonus."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    await _mk_settings(tenant_a, class_id, subject_id,
                       streak_bonus_enabled=False, session_id=session_id)
    student_id = await _mk_student(tenant_a, class_id)

    eng = _engine()
    first = [
        await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.CORRECT)
        for _ in range(5)
    ]
    assert first[4]["streak_bonus"] == 0, "disabled run must award nothing"

    await gd_update_one(
        db.session, "session_settings",
        {"class_id": class_id, "subject_id": subject_id, "tenant_id": tenant_a},
        {"streak_bonus_enabled": True},
    )

    second = [
        await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.CORRECT)
        for _ in range(5)
    ]
    assert second[4]["streak_bonus"] == 5, "enabled mid-run must resume bonuses"
    assert second[4]["score_change"] == 10


# ──────────────────── route-level durability (partial-POST preservation) ────

def _owner_user(tenant_id: str, teacher_id: str) -> dict:
    """A current_user dict that _verify_session_owner accepts as the session owner."""
    return {
        "id": teacher_id,
        "teacher_id": teacher_id,
        "tenant_id": tenant_id,
        "school_id": tenant_id,
        "role": "teacher",
    }


@pytest.mark.asyncio
async def test_partial_post_preserves_disabled_flag(tenant_a):
    """Durability regression: after the teacher disables the bonus in the
    during-lesson dialog, a later PARTIAL settings POST that omits the key (e.g.
    the pre-teach correct-answer-weight control sends only subject_id +
    correct_answer_weight) must NOT silently re-enable it."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    user = _owner_user(tenant_a, teacher_id)

    # 1. Teacher disables the bonus from the during-lesson settings dialog.
    await save_session_settings(session_id, {"subject_id": subject_id,
                                             "streak_bonus_enabled": False}, user)
    rec = await gd_find_one(db.session, "session_settings",
                            {"class_id": class_id, "subject_id": subject_id,
                             "tenant_id": tenant_a})
    assert rec["streak_bonus_enabled"] is False

    # 2. Partial POST from the pre-teach weight control (no streak_bonus_enabled).
    await save_session_settings(session_id, {"subject_id": subject_id,
                                             "correct_answer_weight": 7}, user)
    rec2 = await gd_find_one(db.session, "session_settings",
                             {"class_id": class_id, "subject_id": subject_id,
                              "tenant_id": tenant_a})
    assert rec2["streak_bonus_enabled"] is False, (
        "partial POST must preserve the disabled flag, not reset it to default True"
    )

    # 3. The engine must agree — bonus stays suppressed at runtime.
    eng = _engine()
    assert await eng._is_streak_bonus_enabled(session_id) is False


@pytest.mark.asyncio
async def test_partial_post_defaults_true_when_no_existing_record(tenant_a):
    """A partial POST that omits the key AND has no prior settings record leaves
    the flag at the default (enabled), preserving legacy behaviour."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    user = _owner_user(tenant_a, teacher_id)

    await save_session_settings(session_id, {"subject_id": subject_id,
                                             "correct_answer_weight": 7}, user)
    rec = await gd_find_one(db.session, "session_settings",
                            {"class_id": class_id, "subject_id": subject_id,
                             "tenant_id": tenant_a})
    assert rec["streak_bonus_enabled"] is True


@pytest.mark.asyncio
async def test_explicit_enable_after_disable_via_full_post(tenant_a):
    """The during-lesson dialog always sends the key, so it can re-enable a
    previously disabled bonus."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    user = _owner_user(tenant_a, teacher_id)

    await save_session_settings(session_id, {"subject_id": subject_id,
                                             "streak_bonus_enabled": False}, user)
    await save_session_settings(session_id, {"subject_id": subject_id,
                                             "streak_bonus_enabled": True}, user)
    rec = await gd_find_one(db.session, "session_settings",
                            {"class_id": class_id, "subject_id": subject_id,
                             "tenant_id": tenant_a})
    assert rec["streak_bonus_enabled"] is True


@pytest.mark.asyncio
async def test_get_settings_reflects_saved_disabled_flag(tenant_a):
    """Reopen contract: after disabling, GET /session/{id}/settings returns the
    stored flag so the dialog re-renders with the toggle off."""
    from routes.role_dashboards_mod import get_session_settings
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    user = _owner_user(tenant_a, teacher_id)

    await save_session_settings(session_id, {"subject_id": subject_id,
                                             "streak_bonus_enabled": False}, user)
    got = await get_session_settings(session_id, user)
    assert got["streak_bonus_enabled"] is False
