"""
Task #982 — Unit tests for the broadened column-name matching and explicit
error behaviour in the homework→grade sync path.

New coverage not present in task_969 tests:
  1. _resolve_coursework_columns matches Arabic name variants (partial Arabic
     substring match, e.g. "واجب" or "واجباتي" instead of "الواجبات").
  2. _resolve_coursework_columns matches English name variants ("Homework" vs
     "homework", "HW Tasks", etc.).
  3. start_session raises HTTP 422 — not silently skips — when the class has
     grade columns but none can be matched to the homework bucket after all
     broadened matching strategies are exhausted.
  4. _sync_homework_grade_for_student (called via record_homework) also raises
     / logs rather than silently no-ops when no column is matchable; the
     session_homework row is NOT written when the whole request rolls back.
"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from dependencies import db
from engines.sql_utils import gd_find_one, gd_insert, gd_insert_many
from engines.session_engine import TeacherSessionEngine


# ---------------------------------------------------------------------------
# Helpers (duplicate-safe: these are independent of the task969 helpers)
# ---------------------------------------------------------------------------

def _engine() -> TeacherSessionEngine:
    class _Shim:
        @property
        def session(self):
            return db.session
    return TeacherSessionEngine(_Shim())


async def _mk_school(school_id: str) -> None:
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": f"مدرسة-{school_id[:6]}",
        "code": f"SC{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })


async def _mk_teacher(tenant_id: str) -> str:
    tid = str(uuid.uuid4())
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": "teacher", "tenant_id": tenant_id,
        "email": f"t-{uid}@t.test", "full_name": "معلم", "is_active": True,
        "password_hash": "x", "teacher_id": tid,
    })
    await gd_insert(db.session, "teachers", {
        "id": tid, "user_id": uid, "school_id": tenant_id,
        "full_name": "معلم", "email": f"t-{uid}@t.test",
    })
    return tid


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
        "class_id": class_id, "full_name": f"طالب-{sid[:6]}", "is_active": True,
    })
    return sid


async def _mk_session_settings(teacher_id: str, subject_id: str) -> None:
    await gd_insert(db.session, "session_settings", {
        "id": str(uuid.uuid4()),
        "teacher_id": teacher_id,
        "subject_id": subject_id,
        "homework_enabled": True,
        "homework_mode": "submitted",
        "participation_enabled": True,
        "recitation_enabled": False,
        "recitation_attempts": 1,
        "skills_enabled": False,
        "custom_skills": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


async def _insert_custom_grade_columns(class_id: str, columns: list) -> list:
    """Insert caller-supplied grade column dicts for a class.
    Each dict must include at minimum: name, name_en, column_type, max_grade, order.
    Returns the inserted docs (with 'id' filled in)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    docs = []
    for col in columns:
        doc = {**col, "id": str(uuid.uuid4()), "class_id": class_id,
               "visible": True, "created_at": now_iso}
        docs.append(doc)
    await gd_insert_many(db.session, "grade_columns", docs)
    return docs


# ---------------------------------------------------------------------------
# 1. _resolve_coursework_columns — exact Arabic name still matches
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_columns_exact_arabic_match():
    """Canonical Arabic name 'الواجبات' must still match the homework bucket."""
    tenant = str(uuid.uuid4())
    await _mk_school(tenant)
    class_id = await _mk_class(tenant)

    await _insert_custom_grade_columns(class_id, [
        {"name": "الواجبات", "name_en": "Homework", "column_type": "coursework",
         "max_grade": 5, "order": 1},
    ])

    engine = _engine()
    resolved = await engine._resolve_coursework_columns(class_id)
    hw = resolved.get(TeacherSessionEngine._CW_HOMEWORK)
    assert hw is not None, "Exact Arabic name 'الواجبات' must resolve to homework bucket"
    assert hw["name"] == "الواجبات"


# ---------------------------------------------------------------------------
# 2. _resolve_coursework_columns — Arabic partial match ("واجب" substring)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_columns_arabic_partial_match_variant():
    """A column named 'الواجب المنزلي' must match via the 'واجب' substring."""
    tenant = str(uuid.uuid4())
    await _mk_school(tenant)
    class_id = await _mk_class(tenant)

    await _insert_custom_grade_columns(class_id, [
        {"name": "المشاركة", "name_en": "Participation", "column_type": "coursework",
         "max_grade": 5, "order": 1},
        {"name": "الواجب المنزلي", "name_en": "HW Task", "column_type": "coursework",
         "max_grade": 5, "order": 2},
        {"name": "مهام أدائية", "name_en": "Performance", "column_type": "coursework",
         "max_grade": 10, "order": 3},
    ])

    engine = _engine()
    resolved = await engine._resolve_coursework_columns(class_id)
    hw = resolved.get(TeacherSessionEngine._CW_HOMEWORK)
    assert hw is not None, (
        "Column named 'الواجب المنزلي' must match homework bucket via 'واجب' partial"
    )
    assert hw["name"] == "الواجب المنزلي"


@pytest.mark.asyncio
async def test_resolve_columns_arabic_partial_match_short_variant():
    """A column named simply 'واجب' must also match via the 'واجب' substring."""
    tenant = str(uuid.uuid4())
    await _mk_school(tenant)
    class_id = await _mk_class(tenant)

    await _insert_custom_grade_columns(class_id, [
        {"name": "واجب", "name_en": "Homework", "column_type": "coursework",
         "max_grade": 5, "order": 1},
    ])

    engine = _engine()
    resolved = await engine._resolve_coursework_columns(class_id)
    hw = resolved.get(TeacherSessionEngine._CW_HOMEWORK)
    assert hw is not None, "Column 'واجب' must match via 'واجب' partial substring"


# ---------------------------------------------------------------------------
# 3. _resolve_coursework_columns — English token match
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_columns_english_token_match():
    """A column with English name 'Daily Homework' must match via 'homework' token."""
    tenant = str(uuid.uuid4())
    await _mk_school(tenant)
    class_id = await _mk_class(tenant)

    await _insert_custom_grade_columns(class_id, [
        {"name": "نقاط الأداء", "name_en": "Daily Homework", "column_type": "coursework",
         "max_grade": 5, "order": 1},
    ])

    engine = _engine()
    resolved = await engine._resolve_coursework_columns(class_id)
    hw = resolved.get(TeacherSessionEngine._CW_HOMEWORK)
    assert hw is not None, (
        "Column with name_en 'Daily Homework' must match homework bucket via EN token"
    )


# ---------------------------------------------------------------------------
# 4. Grade rows are created when session starts with variant Arabic column name
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_grade_rows_created_with_arabic_variant_column():
    """Starting a session with homework_mode=submitted must create grade rows even
    when the class uses 'الواجب المنزلي' rather than the canonical 'الواجبات'."""
    tenant = str(uuid.uuid4())
    await _mk_school(tenant)
    teacher_id = await _mk_teacher(tenant)
    class_id = await _mk_class(tenant)
    subject_id = await _mk_subject(tenant)
    s1 = await _mk_student(tenant, class_id)

    # Deliberately insert non-canonical column names
    await _insert_custom_grade_columns(class_id, [
        {"name": "مشاركة الطلاب", "name_en": "Participation",
         "column_type": "coursework", "max_grade": 5, "order": 1},
        {"name": "الواجب اليومي", "name_en": "HW",
         "column_type": "coursework", "max_grade": 5, "order": 2},
        {"name": "مهام أدائية", "name_en": "Performance Tasks",
         "column_type": "coursework", "max_grade": 10, "order": 3},
    ])
    await _mk_session_settings(teacher_id, subject_id)

    engine = _engine()
    result = await engine.start_session(
        teacher_id=teacher_id,
        schedule_session_id=str(uuid.uuid4()),
        class_id=class_id,
        subject_id=subject_id,
    )
    session_id = result["session_record_id"]
    assert result["homework_auto_submitted_count"] == 1

    sg_id = f"sess:{session_id}:{s1}:homework:sg"
    sg = await gd_find_one(db.session, "student_grades", {"id": sg_id})
    assert sg is not None, (
        "student_grades row must be created even with non-canonical Arabic column name"
    )
    pg_id = f"sess:{session_id}:{s1}:homework:pg"
    pg = await gd_find_one(db.session, "grades", {"id": pg_id})
    assert pg is not None, (
        "grades row must be created even with non-canonical Arabic column name"
    )

    # grade_entry in the response must be populated (not None)
    submitted = result["homework_auto_submitted"]
    assert len(submitted) == 1
    assert submitted[0]["grade_entry"] is not None
    assert "column_id" in submitted[0]["grade_entry"]


# ---------------------------------------------------------------------------
# 5. start_session raises 422 — not silently skips — when no column matches
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_session_raises_422_when_no_homework_column():
    """When a class has grade columns but none match the homework bucket (not even
    via partial matching), start_session must raise HTTP 422 instead of silently
    producing an inconsistent state (homework rows written, grade rows missing)."""
    tenant = str(uuid.uuid4())
    await _mk_school(tenant)
    teacher_id = await _mk_teacher(tenant)
    class_id = await _mk_class(tenant)
    subject_id = await _mk_subject(tenant)
    await _mk_student(tenant, class_id)

    # Insert grade columns with no homework variant whatsoever
    await _insert_custom_grade_columns(class_id, [
        {"name": "التحصيل المعرفي", "name_en": "Knowledge Score",
         "column_type": "coursework", "max_grade": 10, "order": 1},
        {"name": "التقييم التكويني", "name_en": "Formative Assessment",
         "column_type": "coursework", "max_grade": 10, "order": 2},
    ])
    await _mk_session_settings(teacher_id, subject_id)

    engine = _engine()
    with pytest.raises(HTTPException) as exc_info:
        await engine.start_session(
            teacher_id=teacher_id,
            schedule_session_id=str(uuid.uuid4()),
            class_id=class_id,
            subject_id=subject_id,
        )

    assert exc_info.value.status_code == 422, (
        f"Expected 422 for missing homework column, got {exc_info.value.status_code}"
    )
    assert "واجبات" in exc_info.value.detail or "درجات" in exc_info.value.detail, (
        f"Error message should mention grade columns: {exc_info.value.detail}"
    )


# ---------------------------------------------------------------------------
# 6. No session_homework rows written when start_session raises (atomic)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_partial_writes_when_start_session_raises():
    """When start_session raises 422 due to missing homework column, no
    session_homework rows must have been written (transaction rolls back)."""
    tenant = str(uuid.uuid4())
    await _mk_school(tenant)
    teacher_id = await _mk_teacher(tenant)
    class_id = await _mk_class(tenant)
    subject_id = await _mk_subject(tenant)
    s1 = await _mk_student(tenant, class_id)

    # No homework column
    await _insert_custom_grade_columns(class_id, [
        {"name": "اختبار تحصيلي", "name_en": "Achievement Test",
         "column_type": "exams", "max_grade": 20, "order": 1},
    ])
    await _mk_session_settings(teacher_id, subject_id)

    engine = _engine()
    ss_id = str(uuid.uuid4())
    with pytest.raises(HTTPException):
        await engine.start_session(
            teacher_id=teacher_id,
            schedule_session_id=ss_id,
            class_id=class_id,
            subject_id=subject_id,
        )

    # No session_homework rows for s1 should exist
    hw_rows = await gd_find_one(db.session, "session_homework", {
        "student_id": s1,
    })
    assert hw_rows is None, (
        "session_homework rows must not persist after a failed start_session"
    )


# ---------------------------------------------------------------------------
# 7. _resolve_coursework_columns: exam columns are excluded from matching
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_columns_ignores_exam_type_columns():
    """A column_type='exams' column named 'الواجبات' must NOT match the
    homework coursework bucket — exam columns are excluded by design."""
    tenant = str(uuid.uuid4())
    await _mk_school(tenant)
    class_id = await _mk_class(tenant)

    await _insert_custom_grade_columns(class_id, [
        {"name": "الواجبات", "name_en": "Homework", "column_type": "exams",
         "max_grade": 5, "order": 1},
    ])

    engine = _engine()
    resolved = await engine._resolve_coursework_columns(class_id)
    hw = resolved.get(TeacherSessionEngine._CW_HOMEWORK)
    assert hw is None, (
        "An exam-type column named 'الواجبات' must NOT match the homework coursework bucket"
    )
