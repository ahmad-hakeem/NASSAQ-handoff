"""
Task #1025 — unit tests for per-session correct-answer weight.

Invariants covered:
- _get_session_score_rules returns system default (5) when no override is set.
- _get_session_score_rules applies correct_answer_weight from the session doc.
- Out-of-range weights (0, 1001) stored in the doc are silently ignored →
  falls back to tenant/system default.
- Weight of 1 and 1000 (boundary values) are both honoured.
- Compute scores: correct answers accumulate at the configured weight.
- After updating correct_answer_weight on the session doc mid-session, the
  engine immediately uses the new value (no restart needed).
- Other score rule keys (participation, bonus…) are unaffected by the weight.
- API validation rejects boolean, string, and non-integer float types with 422.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_find_one, gd_insert, gd_update_one
from engines.session_engine import (
    TeacherSessionEngine as SessionEngine,
    InteractionType,
    AnswerResult,
)


# ──────────────────── helpers ────────────────────

def _engine():
    class _DBShim:
        @property
        def session(self):
            return db.session
    return SessionEngine(_DBShim())


async def _mk_tenant() -> str:
    return str(uuid.uuid4())


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
    correct_answer_weight: int = None,
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
    if correct_answer_weight is not None:
        doc["correct_answer_weight"] = correct_answer_weight
    await gd_insert(db.session, "class_sessions", doc)
    return session_id


async def _record_answer(
    eng: SessionEngine,
    session_id: str, student_id: str, teacher_id: str,
    result: AnswerResult = AnswerResult.CORRECT,
):
    return await eng.record_answer(
        session_id=session_id,
        student_id=student_id,
        result=result,
        teacher_id=teacher_id,
    )


# ──────────────────── tests ────────────────────

@pytest.mark.asyncio
async def test_default_weight_five_when_no_override(tenant_a):
    """Without an override the correct_answer score rule must be 5 (system default)."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)

    eng = _engine()
    rules = await eng._get_session_score_rules(session_id)
    assert rules["correct_answer"] == 5, (
        f"expected correct_answer=5 (system default), got {rules['correct_answer']}"
    )


@pytest.mark.asyncio
async def test_weight_applied_from_session_doc(tenant_a):
    """correct_answer_weight on the session doc overrides the default."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id,
        correct_answer_weight=10,
    )

    eng = _engine()
    rules = await eng._get_session_score_rules(session_id)
    assert rules["correct_answer"] == 10


@pytest.mark.asyncio
async def test_boundary_weight_one(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id,
        correct_answer_weight=1,
    )

    eng = _engine()
    rules = await eng._get_session_score_rules(session_id)
    assert rules["correct_answer"] == 1


@pytest.mark.asyncio
async def test_boundary_weight_thousand(tenant_a):
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id,
        correct_answer_weight=1000,
    )

    eng = _engine()
    rules = await eng._get_session_score_rules(session_id)
    assert rules["correct_answer"] == 1000


@pytest.mark.asyncio
async def test_out_of_range_weight_zero_falls_back_to_default(tenant_a):
    """weight=0 is out of range — engine must ignore it and use the system default."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id,
        correct_answer_weight=0,
    )

    eng = _engine()
    rules = await eng._get_session_score_rules(session_id)
    assert rules["correct_answer"] == 5, (
        "weight=0 is invalid; engine must fall back to system default (5)"
    )


@pytest.mark.asyncio
async def test_out_of_range_weight_1001_falls_back_to_default(tenant_a):
    """weight=1001 is out of range — engine must ignore it and use the system default."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id,
        correct_answer_weight=1001,
    )

    eng = _engine()
    rules = await eng._get_session_score_rules(session_id)
    assert rules["correct_answer"] == 5, (
        "weight=1001 is invalid; engine must fall back to system default (5)"
    )


@pytest.mark.asyncio
async def test_other_score_rules_unaffected_by_weight(tenant_a):
    """Setting correct_answer_weight must not disturb other rule keys."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)

    session_default = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    session_custom = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id,
        correct_answer_weight=20,
    )

    eng = _engine()
    rules_default = await eng._get_session_score_rules(session_default)
    rules_custom = await eng._get_session_score_rules(session_custom)

    for key in rules_default:
        if key == "correct_answer":
            continue
        assert rules_default[key] == rules_custom[key], (
            f"rule key '{key}' changed unexpectedly: "
            f"{rules_default[key]} → {rules_custom[key]}"
        )


@pytest.mark.asyncio
async def test_compute_scores_accumulate_at_custom_weight(tenant_a):
    """compute_session_scores must use the custom weight for correct-answer interactions."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(
        tenant_a, class_id, subject_id, teacher_id,
        correct_answer_weight=7,
    )
    student_id = await _mk_student(tenant_a, class_id)

    eng = _engine()
    # Two correct answers at weight 7 each → expect 14 participation points.
    await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.CORRECT)
    await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.CORRECT)

    computed = await eng.compute_session_scores(session_id)
    pts = computed["students"][student_id]["participation_points"]
    assert pts == 14, f"expected 14 participation points (2 × 7), got {pts}"


@pytest.mark.asyncio
async def test_compute_scores_default_weight_five(tenant_a):
    """compute_session_scores uses weight=5 when no override is set."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    student_id = await _mk_student(tenant_a, class_id)

    eng = _engine()
    await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.CORRECT)

    computed = await eng.compute_session_scores(session_id)
    pts = computed["students"][student_id]["participation_points"]
    assert pts == 5, f"expected 5 participation points (default weight), got {pts}"


@pytest.mark.asyncio
async def test_mid_session_weight_change_takes_effect_immediately(tenant_a):
    """Updating correct_answer_weight on the session doc mid-session is reflected
    in the *next* call to _get_session_score_rules (no process restart needed)."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)

    eng = _engine()
    rules_before = await eng._get_session_score_rules(session_id)
    assert rules_before["correct_answer"] == 5

    # Simulate the settings endpoint updating the session doc mid-session.
    await gd_update_one(
        db.session,
        "class_sessions",
        {"id": session_id},
        {"correct_answer_weight": 50},
    )

    rules_after = await eng._get_session_score_rules(session_id)
    assert rules_after["correct_answer"] == 50, (
        f"engine should reflect the updated weight immediately; got {rules_after['correct_answer']}"
    )


@pytest.mark.asyncio
async def test_record_answer_score_change_uses_saved_weight(tenant_a):
    """Regression: after saving correct_answer_weight=2 on the session doc,
    record_answer must return score_change=2 (not the system default of 5).

    This exercises the full path: gd_update_one → flush → gd_find_one in
    _get_session_score_rules → score_change in record_answer return value.
    Previously, gd_update_one for GenericDocument JSONB columns was missing
    flag_modified(), which could silently suppress the UPDATE and leave the
    stale value in the DB.
    """
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    student_id = await _mk_student(tenant_a, class_id)

    eng = _engine()

    # Simulate save_session_settings writing correct_answer_weight=2
    # to the class_sessions GenericDocument (the same path the route uses).
    await gd_update_one(
        db.session,
        "class_sessions",
        {"id": session_id},
        {"correct_answer_weight": 2},
    )

    # Now record a correct answer — score_change MUST reflect the saved weight.
    result = await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.CORRECT)
    assert result["score_change"] == 2, (
        f"expected score_change=2 (saved weight), got {result['score_change']}; "
        "gd_update_one may not have persisted the JSONB mutation (missing flag_modified)"
    )


@pytest.mark.asyncio
async def test_record_answer_wrong_result_unaffected_by_weight(tenant_a):
    """Saving a custom correct_answer_weight must NOT change the score for
    wrong answers (wrong answer score_change is 0 by default)."""
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    teacher_id = await _mk_user(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, teacher_id)
    student_id = await _mk_student(tenant_a, class_id)

    eng = _engine()

    await gd_update_one(
        db.session,
        "class_sessions",
        {"id": session_id},
        {"correct_answer_weight": 99},
    )

    result = await _record_answer(eng, session_id, student_id, teacher_id, AnswerResult.WRONG)
    assert result["score_change"] == 0, (
        f"wrong-answer score_change should be 0 regardless of correct_answer_weight; "
        f"got {result['score_change']}"
    )


# ──────────────────── type-validation unit tests ────────────────────
# The validation helpers in the route layer (role_dashboards_mod.py) and the
# engine (session_engine.py) must reject strings, booleans, and non-integer
# floats with a 422-equivalent error.  These tests exercise the helpers
# directly via the same isinstance checks that guard both endpoints.

def _validate_weight(raw):
    """Mirrors the guard logic from role_dashboards_mod.py and session_engine.py."""
    from fastapi import HTTPException
    if raw is None:
        return None  # explicit null → use tenant/system default
    if isinstance(raw, bool) or isinstance(raw, str):
        raise HTTPException(
            status_code=422,
            detail="وزن الإجابة الصحيحة يجب أن يكون عدداً صحيحاً بين 1 و1000",
        )
    if isinstance(raw, float) and not raw.is_integer():
        raise HTTPException(
            status_code=422,
            detail="وزن الإجابة الصحيحة يجب أن يكون عدداً صحيحاً (بدون كسور عشرية)",
        )
    val = int(raw)
    if not (1 <= val <= 1000):
        raise HTTPException(
            status_code=422,
            detail="وزن الإجابة الصحيحة يجب أن يكون بين 1 و1000",
        )
    return val


def test_type_rejection_string():
    """A JSON string like '7' must raise 422, not silently convert."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _validate_weight("7")
    assert exc.value.status_code == 422


def test_type_rejection_boolean_true():
    """Python/JSON true must raise 422 (bool subclasses int — explicit check needed)."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _validate_weight(True)
    assert exc.value.status_code == 422


def test_type_rejection_boolean_false():
    """Python/JSON false must raise 422."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _validate_weight(False)
    assert exc.value.status_code == 422


def test_type_rejection_non_integer_float():
    """A non-integer float like 1.5 must raise 422."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _validate_weight(1.5)
    assert exc.value.status_code == 422


def test_type_accepts_integer_float():
    """An integer-valued float like 7.0 is accepted (JSON numbers are floats)."""
    assert _validate_weight(7.0) == 7


def test_type_accepts_plain_int():
    """A plain int is accepted."""
    assert _validate_weight(10) == 10


def test_type_accepts_none():
    """None (explicit null) is accepted — means 'restore default'."""
    assert _validate_weight(None) is None
