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
"""
from __future__ import annotations

from typing import Dict, Tuple


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


__all__ = [
    "live_student_count",
    "live_teacher_count",
    "live_counts_by_tenant",
    "reconcile_school_counts",
]
