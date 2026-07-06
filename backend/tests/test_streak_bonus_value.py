"""
Unit + e2e tests for the per-session excellence (التميز) streak-bonus VALUE.

Mirrors test_correct_answer_weight_task1025.py. The teacher can override the
bonus MAGNITUDE (rule key ``three_correct_streak``) per session via
``streak_bonus_value`` on the class_sessions doc. Range 1–5, default 5. The
bonus is still awarded only on every 5th consecutive correct answer
(STREAK_BONUS_THRESHOLD = 5, unchanged).

Invariants covered:
- _get_session_score_rules returns the system default (5) when no override.
- _get_session_score_rules applies streak_bonus_value from the session doc.
- Boundary values 1 and 5 are honoured.
- Out-of-range values (0, 6) are silently ignored → fall back to default.
- Other score rule keys (correct_answer, participation…) are unaffected.
- record_answer awards the configured bonus on the 5th consecutive correct
  answer (the value that flows into the live toast).
- get_streak_bonus_summary accumulates the configured bonus (the كشف المتابعة
  → درجات التميز column).
- A mid-session update takes effect on the next call (no restart).
- API-layer validation rejects boolean/string/non-integer-float with 422 and
  enforces the 1–5 range.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_update_one, gd_insert
from engines.session_engine import (
    TeacherSessionEngine as SessionEngine,
    AnswerResult,
)


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


async def _mk_user(tenant_id: str) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": "teacher", "tenant_id": tenant_id,
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


async def _record_answer(eng, session_id, student_id, teacher_id,
                         result: AnswerResult = AnswerResult.CORRECT):
    return await eng.record_answer(
        session_id=session_id,
        student_id=student_id,
        result=result,
        teacher_id=teacher_id,
    )


# ──────────────────── engine waterfall tests ────────────────────

@pytest.mark.asyncio
async def test_default_bonus_five_when_no_override(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)

    eng = _engine()
    rules = await eng._get_session_score_rules(session_id)
    assert rules["three_correct_streak"] == 5


@pytest.mark.asyncio
async def test_bonus_applied_from_session_doc(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id, streak_bonus_value=3,
    )

    eng = _engine()
    rules = await eng._get_session_score_rules(session_id)
    assert rules["three_correct_streak"] == 3


@pytest.mark.asyncio
async def test_boundary_bonus_one(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id, streak_bonus_value=1,
    )
    eng = _engine()
    rules = await eng._get_session_score_rules(session_id)
    assert rules["three_correct_streak"] == 1


@pytest.mark.asyncio
async def test_boundary_bonus_five(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id, streak_bonus_value=5,
    )
    eng = _engine()
    rules = await eng._get_session_score_rules(session_id)
    assert rules["three_correct_streak"] == 5


@pytest.mark.asyncio
async def test_out_of_range_zero_falls_back_to_default(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id, streak_bonus_value=0,
    )
    eng = _engine()
    rules = await eng._get_session_score_rules(session_id)
    assert rules["three_correct_streak"] == 5, (
        "bonus=0 is invalid; engine must fall back to system default (5)"
    )


@pytest.mark.asyncio
async def test_out_of_range_six_falls_back_to_default(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id, streak_bonus_value=6,
    )
    eng = _engine()
    rules = await eng._get_session_score_rules(session_id)
    assert rules["three_correct_streak"] == 5, (
        "bonus=6 is out of the 1–5 range; engine must fall back to default (5)"
    )


@pytest.mark.asyncio
async def test_other_score_rules_unaffected_by_bonus(tenant_a):
    """Setting streak_bonus_value must not disturb other rule keys (incl.
    correct_answer, so the two per-session overrides are independent)."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)

    session_default = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    session_custom = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id, streak_bonus_value=2,
    )

    eng = _engine()
    rules_default = await eng._get_session_score_rules(session_default)
    rules_custom = await eng._get_session_score_rules(session_custom)

    for key in rules_default:
        if key == "three_correct_streak":
            continue
        assert rules_default[key] == rules_custom[key], (
            f"rule key '{key}' changed unexpectedly: "
            f"{rules_default[key]} → {rules_custom[key]}"
        )


@pytest.mark.asyncio
async def test_bonus_and_weight_overrides_are_independent(tenant_a):
    """Both per-session overrides can coexist on the same session doc."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id, streak_bonus_value=2,
    )
    await gd_update_one(
        db.session, "class_sessions", {"id": session_id},
        {"correct_answer_weight": 7},
    )
    eng = _engine()
    rules = await eng._get_session_score_rules(session_id)
    assert rules["three_correct_streak"] == 2
    assert rules["correct_answer"] == 7


# ──────────────────── award-path (toast + كشف المتابعة) e2e ────────────────────

@pytest.mark.asyncio
async def test_fifth_consecutive_correct_awards_configured_bonus(tenant_a):
    """With streak_bonus_value=3, the 5th consecutive correct answer awards a
    bonus of 3 (base 5 + bonus 3 = 8) — the exact numbers the live toast reads
    from record_answer's return value."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id, streak_bonus_value=3,
    )
    student_id = await _mk_student(tenant_a, class_id)

    eng = _engine()
    results = []
    for _ in range(5):
        results.append(
            await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.CORRECT)
        )

    for n, r in enumerate(results, start=1):
        if n == 5:
            assert r["base_points"] == 5, f"answer #{n} base"
            assert r["streak_bonus"] == 3, f"answer #{n} configured bonus"
            assert r["score_change"] == 8, f"answer #{n} total (5 + 3)"
        else:
            assert r["streak_bonus"] == 0, f"answer #{n} must carry no bonus"
            assert r["score_change"] == r["base_points"] == 5, f"answer #{n} plain"


@pytest.mark.asyncio
async def test_streak_bonus_summary_accumulates_configured_value(tenant_a):
    """كشف المتابعة → درجات التميز: over 10 consecutive correct answers with
    streak_bonus_value=2, the summary reports points=4 (2 bonuses × 2) count=2."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id, streak_bonus_value=2,
    )
    student_id = await _mk_student(tenant_a, class_id)

    eng = _engine()
    for _ in range(10):
        await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.CORRECT)

    summary = await eng.get_streak_bonus_summary(session_id)
    assert student_id in summary, "student earned bonuses; must appear in summary"
    assert summary[student_id]["count"] == 2, "two runs of 5 → two bonuses"
    assert summary[student_id]["points"] == 4, "2 bonuses × configured value 2 = 4"


@pytest.mark.asyncio
async def test_default_bonus_awards_five(tenant_a):
    """Regression guard: with no override the 5th consecutive correct answer
    still awards the default bonus of 5 (base 5 + bonus 5 = 10)."""
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
async def test_mid_session_bonus_change_takes_effect_immediately(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)

    eng = _engine()
    rules_before = await eng._get_session_score_rules(session_id)
    assert rules_before["three_correct_streak"] == 5

    await gd_update_one(
        db.session, "class_sessions", {"id": session_id},
        {"streak_bonus_value": 1},
    )

    rules_after = await eng._get_session_score_rules(session_id)
    assert rules_after["three_correct_streak"] == 1, (
        f"engine should reflect the updated bonus immediately; got "
        f"{rules_after['three_correct_streak']}"
    )


# ──────────────────── API-layer type/range validation ────────────────────
# Mirrors the guard in role_dashboards_mod.save_session_settings for the
# streak_bonus_value field (integer, range 1–5).

def _validate_bonus(raw):
    """Mirrors the guard logic in role_dashboards_mod.py for streak_bonus_value."""
    from fastapi import HTTPException
    if raw is None:
        return None  # explicit null → restore tenant/system default
    if isinstance(raw, bool) or isinstance(raw, str):
        raise HTTPException(
            status_code=422,
            detail="قيمة مكافأة التميز يجب أن تكون عدداً صحيحاً بين 1 و5",
        )
    if isinstance(raw, float) and not raw.is_integer():
        raise HTTPException(
            status_code=422,
            detail="قيمة مكافأة التميز يجب أن تكون عدداً صحيحاً (بدون كسور عشرية)",
        )
    val = int(raw)
    if not (1 <= val <= 5):
        raise HTTPException(
            status_code=422,
            detail="قيمة مكافأة التميز يجب أن تكون بين 1 و5",
        )
    return val


def test_bonus_rejection_string():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _validate_bonus("3")
    assert exc.value.status_code == 422


def test_bonus_rejection_boolean_true():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _validate_bonus(True)
    assert exc.value.status_code == 422


def test_bonus_rejection_boolean_false():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _validate_bonus(False)
    assert exc.value.status_code == 422


def test_bonus_rejection_non_integer_float():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _validate_bonus(2.5)
    assert exc.value.status_code == 422


def test_bonus_rejection_below_range():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _validate_bonus(0)
    assert exc.value.status_code == 422


def test_bonus_rejection_above_range():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _validate_bonus(6)
    assert exc.value.status_code == 422


def test_bonus_accepts_integer_float():
    assert _validate_bonus(3.0) == 3


def test_bonus_accepts_plain_int():
    assert _validate_bonus(5) == 5


def test_bonus_accepts_none():
    assert _validate_bonus(None) is None
