"""Canonical live student/teacher counts for a school (tenant).

Task #826: the denormalized ``schools.current_students`` /
``schools.current_teachers`` columns used to drift because they were only
nudged by scattered ``_gd_inc(..., ±1)`` calls in the student/teacher
create/delete/restore routes and were never recomputed. This module is the
single source of truth for "how many students/teachers does a school really
have", so every write path can *reconcile* (recompute and overwrite) the
stored columns instead of blindly incrementing them, and every reader gets
numbers that match the in-school pages.

The predicates here MUST stay byte-for-byte identical to what the in-school
list endpoints apply, so the platform list, the stored columns, and each
school's own pages never disagree:

* Students — ``GET /students`` filters ``{"is_active": {"$ne": False}}``,
  rendered as ``is_active != FALSE``. In Postgres that excludes both ``FALSE``
  and ``NULL`` rows, so we use the identical ORM predicate.
* Teachers — ``GET /teachers`` (default active view) returns every teacher
  EXCEPT the soft-deleted ones (``is_active is False AND deleted_at`` set),
  mirrored here with ``NOT (is_active = False AND deleted_at IS NOT NULL)``.

The one-time backfill in the Alembic migration
``c8d7e6f5a4b3_backfill_school_entity_counts`` uses raw SQL that mirrors these
exact predicates — keep the three in lockstep if you ever change them.

Task #829: the class-level ``classes.current_students`` column had the exact
same drift problem (scattered ``_gd_inc(..., ±1)`` nudges in the student
create/delete/transfer routes, never recomputed). ``reconcile_class_counts``
is the self-healing equivalent for classes. Its predicate MUST match what the
class list / detail readers in ``academics_class_routes.py`` apply when they
aggregate the live roster — those use ``is_active == TRUE`` (active students
assigned to the class), which is a stricter predicate than the school-level
one above (it excludes ``NULL`` rows too). The backfill migration
``d9e8f7a6b5c4_backfill_class_student_counts`` mirrors this class predicate.
Note: ``student_count`` is NOT a real column on ``classes`` — it is computed
live in the response by the readers — so only ``current_students`` is stored.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


def _student_active_predicate():
    from pg_models import Student

    return Student.is_active != False  # noqa: E712 — match gd_find $ne semantics


def _teacher_active_predicate():
    from sqlalchemy import and_, not_
    from pg_models import Teacher

    return not_(
        and_(
            Teacher.is_active == False,  # noqa: E712
            Teacher.deleted_at.isnot(None),
        )
    )


async def live_student_count(session, school_id: str) -> int:
    """Live (canonical) active-student count for one school."""
    from sqlalchemy import select, func
    from pg_models import Student

    stmt = (
        select(func.count())
        .select_from(Student)
        .where(Student.school_id == school_id)
        .where(_student_active_predicate())
    )
    return int((await session.execute(stmt)).scalar() or 0)


async def live_teacher_count(session, school_id: str) -> int:
    """Live (canonical) active-teacher count for one school."""
    from sqlalchemy import select, func
    from pg_models import Teacher

    stmt = (
        select(func.count())
        .select_from(Teacher)
        .where(Teacher.school_id == school_id)
        .where(_teacher_active_predicate())
    )
    return int((await session.execute(stmt)).scalar() or 0)


async def live_counts_by_tenant(session) -> Tuple[Dict[str, int], Dict[str, int]]:
    """Batch live student/teacher counts grouped per tenant (no N+1).

    Returns ``(student_counts, teacher_counts)`` keyed by ``school_id``.
    """
    from sqlalchemy import select, func
    from pg_models import Student, Teacher

    student_stmt = (
        select(Student.school_id, func.count().label("cnt"))
        .where(Student.school_id.isnot(None))
        .where(_student_active_predicate())
        .group_by(Student.school_id)
    )
    student_result = await session.execute(student_stmt)
    student_counts = {sid: cnt for sid, cnt in student_result.all() if sid}

    teacher_stmt = (
        select(Teacher.school_id, func.count().label("cnt"))
        .where(Teacher.school_id.isnot(None))
        .where(_teacher_active_predicate())
        .group_by(Teacher.school_id)
    )
    teacher_result = await session.execute(teacher_stmt)
    teacher_counts = {sid: cnt for sid, cnt in teacher_result.all() if sid}

    return student_counts, teacher_counts


async def reconcile_school_counts(session, school_id: str) -> Tuple[int, int]:
    """Recompute and persist a school's ``current_students`` /
    ``current_teachers`` from the live row counts.

    This is the self-healing replacement for the scattered ``±1`` nudges:
    calling it after any student/teacher create/delete/restore overwrites the
    stored columns with the real counts, so drift is corrected on every write.
    Returns the ``(student_count, teacher_count)`` that were written. No-ops
    safely when ``school_id`` is falsy or the school row is missing.
    """
    if not school_id:
        return (0, 0)

    from sqlalchemy import select
    from pg_models import School

    student_count = await live_student_count(session, school_id)
    teacher_count = await live_teacher_count(session, school_id)

    obj = (
        await session.execute(select(School).where(School.id == school_id).limit(1))
    ).scalars().first()
    if obj is not None:
        obj.current_students = student_count
        obj.current_teachers = teacher_count
        await session.flush()

    return (student_count, teacher_count)


def _class_student_active_predicate():
    from pg_models import Student

    # Match the class list / detail readers in academics_class_routes.py, which
    # aggregate ``is_active == TRUE`` students per class. This is intentionally
    # stricter than the school-level student predicate (it excludes NULL rows).
    return Student.is_active == True  # noqa: E712


async def live_class_student_count(session, class_id: str, school_id: str | None = None) -> int:
    """Live (canonical) active-student count for one class.

    When ``school_id`` is provided the count is scoped by it too, so a stray
    cross-tenant class id can never inflate the result.
    """
    from sqlalchemy import select, func
    from pg_models import Student

    stmt = (
        select(func.count())
        .select_from(Student)
        .where(Student.class_id == class_id)
        .where(_class_student_active_predicate())
    )
    if school_id:
        stmt = stmt.where(Student.school_id == school_id)
    return int((await session.execute(stmt)).scalar() or 0)


async def reconcile_class_counts(session, class_id: str, school_id: str | None = None) -> int:
    """Recompute and persist a class's ``current_students`` from live rows.

    Self-healing replacement for the scattered ``±1`` nudges on the class
    counter: calling it after any student create/delete/transfer overwrites the
    stored column with the real count, so drift is corrected on every write.
    Returns the count that was written. No-ops safely when ``class_id`` is
    falsy or the class row is missing.
    """
    if not class_id:
        return 0

    from sqlalchemy import select
    from pg_models import Class

    count = await live_class_student_count(session, class_id, school_id)

    stmt = select(Class).where(Class.id == class_id)
    if school_id:
        stmt = stmt.where(Class.school_id == school_id)
    obj = (await session.execute(stmt.limit(1))).scalars().first()
    if obj is not None:
        obj.current_students = count
        await session.flush()

    return count


# ---------------------------------------------------------------------------
# Class capacity — single source of truth + backend-authoritative gate
# ---------------------------------------------------------------------------
# A class's maximum size is the per-class ``classes.capacity`` value the school
# manager set at create/edit time (30, 40, 44, 60, ...). It is NOT a global
# constant. The ONLY shared fallback is for legacy rows that never persisted a
# capacity (NULL / non-positive), which mirror the column default of 30.
DEFAULT_CLASS_CAPACITY = 30

# Stable, machine-readable error code for the "class is full" rejection. The
# frontend keys its localized copy off this code (see apiError.js
# ``ERROR_CODE_KEYS``), so the user-facing language is owned by the UI and the
# backend never has to ship a mixed-language string.
CLASS_CAPACITY_REACHED_CODE = "CLASS_CAPACITY_REACHED"

# Safe, Arabic-ONLY user-facing message surfaced (HTTP 409) on every assignment
# path when a class is full. This is the ``message`` the frontend renders via
# NassaqAlertDialog when no localized copy is mapped for the code. It must never
# contain English — a previous bilingual string leaked raw English into the
# principal popup (alongside the Arabic), which read like a danger/error dump.
CLASS_FULL_MESSAGE_AR = (
    "وصل هذا الفصل إلى الحد الأقصى لعدد الطلاب المسموح به. الرجاء اختيار فصل آخر."
)

# Internal English text kept for logs/observability ONLY. It is never placed in
# the user-facing ``message`` field nor returned in the API response body.
CLASS_FULL_DEBUG_EN = (
    "This class has reached its maximum capacity. Please choose another class."
)

# Back-compat alias. Older callers/tests referenced ``CLASS_FULL_DETAIL`` as the
# raw 409 detail string; it now points at the safe Arabic-only message so no
# code path can resurrect the mixed-language text.
CLASS_FULL_DETAIL = CLASS_FULL_MESSAGE_AR

# Bulk-import policy message: the class is full, so the student is imported
# WITHOUT a class (never overfilled, never dropped) and must be placed manually.
CLASS_FULL_NO_ASSIGN_WARNING = (
    "الفصل ممتلئ — تم استيراد الطالب بدون فصل، يرجى تعيين فصل له يدويًا / "
    "Class is full — student imported without a class; please assign one manually."
)

# Bulk-update policy message: the TARGET class is full, so a requested move is
# suppressed and the student is kept in their CURRENT class (never overfilled).
CLASS_FULL_KEPT_CURRENT_WARNING = (
    "الفصل الهدف ممتلئ — تم الإبقاء على الطالب في فصله الحالي ولم يُنقل / "
    "Target class is full — student kept in their current class; move not applied."
)


def resolve_class_capacity(class_doc) -> int:
    """Single source of truth for a class's effective maximum size.

    Returns the class's stored ``capacity`` when it is a positive integer;
    otherwise falls back to ``DEFAULT_CLASS_CAPACITY`` for legacy rows that
    never persisted one. Accepts either a dict (``gd_find_one`` result) or an
    ORM object.
    """
    cap = None
    if isinstance(class_doc, dict):
        cap = class_doc.get("capacity")
    elif class_doc is not None:
        cap = getattr(class_doc, "capacity", None)
    try:
        cap_int = int(cap)
    except (TypeError, ValueError):
        return DEFAULT_CLASS_CAPACITY
    return cap_int if cap_int > 0 else DEFAULT_CLASS_CAPACITY


async def class_has_room(
    session, class_doc, school_id: str | None = None, *, additional: int = 1
) -> bool:
    """Return True when ``additional`` more student(s) fit in ``class_doc``.

    Occupancy is the canonical LIVE active-student count (the same predicate as
    ``reconcile_class_counts`` and the class readers), so the decision never
    relies on a possibly-stale denormalized ``current_students`` column. No-ops
    to True when there is no class to check (unassigned student).
    """
    if not class_doc:
        return True
    class_id = (
        class_doc.get("id") if isinstance(class_doc, dict)
        else getattr(class_doc, "id", None)
    )
    if not class_id:
        return True
    capacity = resolve_class_capacity(class_doc)
    current = await live_class_student_count(session, class_id, school_id)
    return (current + additional) <= capacity


async def enforce_class_capacity(
    session, class_doc, school_id: str | None = None, *, additional: int = 1
) -> None:
    """Backend-authoritative capacity gate.

    Raises HTTP 409 with a structured, machine-readable error contract when
    placing ``additional`` more student(s) into ``class_doc`` would exceed its
    configured capacity. The detail carries a stable ``code``
    (``CLASS_CAPACITY_REACHED``) and a safe Arabic-only ``message`` — never a
    mixed-language string — so the frontend can localize off the code while a
    plain Arabic message is always available as the fallback.

    Callers MUST invoke this only for a NET addition to the target class (a
    brand-new student, or a move/restore into a class the student is not already
    an active member of), so an existing member is never double-counted. No-ops
    when there is no class (unassigned).
    """
    if not await class_has_room(session, class_doc, school_id, additional=additional):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=409,
            detail={
                "code": CLASS_CAPACITY_REACHED_CODE,
                "message": CLASS_FULL_MESSAGE_AR,
            },
        )


async def live_class_counts(session) -> Dict[str, int]:
    """Batch live active-student counts grouped per class (no N+1).

    Uses the same stricter class predicate as ``live_class_student_count``
    (``is_active == TRUE``) so the result matches what the class readers and
    ``reconcile_class_counts`` compute. Returns a map keyed by ``class_id``.
    """
    from sqlalchemy import select, func
    from pg_models import Student

    stmt = (
        select(Student.class_id, func.count().label("cnt"))
        .where(Student.class_id.isnot(None))
        .where(_class_student_active_predicate())
        .group_by(Student.class_id)
    )
    result = await session.execute(stmt)
    return {cid: cnt for cid, cnt in result.all() if cid}


async def sweep_count_divergences(session, *, fix: bool = False) -> Dict[str, List[dict]]:
    """Recompute every stored school/class counter from live rows and report
    any divergence between the stored column and the canonical live count.

    This is the "routine check" companion to the per-write ``reconcile_*``
    helpers: it scans the whole tenant inventory in a handful of grouped
    queries (no N+1) and surfaces any counter that drifted — e.g. because a
    future code path nudged a column without reconciling. Each divergence is
    logged at WARNING level so a periodic admin/cron invocation leaves an
    audit trail.

    Returns a dict with two lists, ``"schools"`` and ``"classes"``. Each entry
    records the row id, the ``stored`` value(s), and the ``live`` truth. When
    ``fix=True`` the stored columns are overwritten with the live counts
    (self-heal) and flushed; with the default ``fix=False`` the function is a
    pure read-only audit and mutates nothing.
    """
    from sqlalchemy import select
    from pg_models import School, Class

    student_counts, teacher_counts = await live_counts_by_tenant(session)
    class_counts = await live_class_counts(session)

    school_divergences: List[dict] = []
    class_divergences: List[dict] = []

    schools = (await session.execute(select(School))).scalars().all()
    for school in schools:
        live_students = int(student_counts.get(school.id, 0))
        live_teachers = int(teacher_counts.get(school.id, 0))
        stored_students = int(school.current_students or 0)
        stored_teachers = int(school.current_teachers or 0)
        if stored_students != live_students or stored_teachers != live_teachers:
            school_divergences.append({
                "school_id": school.id,
                "stored_students": stored_students,
                "live_students": live_students,
                "stored_teachers": stored_teachers,
                "live_teachers": live_teachers,
            })
            logger.warning(
                "Count drift for school %s: students stored=%s live=%s, "
                "teachers stored=%s live=%s",
                school.id, stored_students, live_students,
                stored_teachers, live_teachers,
            )
            if fix:
                school.current_students = live_students
                school.current_teachers = live_teachers

    classes = (await session.execute(select(Class))).scalars().all()
    for cls in classes:
        live_students = int(class_counts.get(cls.id, 0))
        stored_students = int(cls.current_students or 0)
        if stored_students != live_students:
            class_divergences.append({
                "class_id": cls.id,
                "school_id": getattr(cls, "school_id", None),
                "stored_students": stored_students,
                "live_students": live_students,
            })
            logger.warning(
                "Count drift for class %s (school %s): students stored=%s live=%s",
                cls.id, getattr(cls, "school_id", None),
                stored_students, live_students,
            )
            if fix:
                cls.current_students = live_students

    if fix and (school_divergences or class_divergences):
        await session.flush()

    return {"schools": school_divergences, "classes": class_divergences}


__all__ = [
    "live_student_count",
    "live_teacher_count",
    "live_counts_by_tenant",
    "reconcile_school_counts",
    "live_class_student_count",
    "live_class_counts",
    "reconcile_class_counts",
    "sweep_count_divergences",
]
