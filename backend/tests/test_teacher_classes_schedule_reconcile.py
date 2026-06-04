"""
Regression tests for `_reconcile_teacher_assignments_from_schedule`
(`backend/routes/role_dashboards_mod.py`).

Bug: a school teacher with REAL scheduled lessons in the published timetable
("جدولي") saw an empty "My Classes" ("فصولي") page showing "لا توجد فصول",
because the two surfaces read different tables — the timetable grid reads the
teacher's scheduled sessions while "My Classes" (and class-level permissions via
``utils.tenant_scope.get_teacher_allowed_class_ids``) read only active
``teacher_assignments``.

Confirmed product rule: the published timetable/schedule is the source of truth.
The reconciler additively materializes active ``teacher_assignments`` for every
``(class_id, subject_id)`` the teacher is actually scheduled to teach so "My
Classes", permissions, and the grid all agree.

These tests lock in the reconciler's guarantees:
  * Materializes one active assignment per distinct scheduled (class, subject).
  * Idempotent — a second run creates nothing new (no duplicates).
  * Additive — a principal's pre-existing manual assignment is preserved.
  * Reactivation — a soft-deactivated (is_active=False) row matching a scheduled
    pair is flipped back on rather than duplicated.
  * Sessions missing a subject_id are skipped (subject_id is NOT NULL).
  * Independent-Teacher synthetic workspaces (``itw_*``) are skipped.

Safety: the reconciler commits via its own session in production. The test DB is
the same Postgres instance, so to avoid leaking rows past the conftest rollback
we patch the dedicated ``async_session_factory`` to reuse the rolled-back test
session and neutralize its ``commit()``.
"""
import contextlib
import uuid

import pytest

from dependencies import db
from engines.sql_utils import gd_insert, gd_find
import routes.role_dashboards_mod as rd


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
async def _mk_school() -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid,
        "name": f"School-{sid[:6]}",
        "code": f"S{sid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    return sid


async def _mk_teacher(school_id: str) -> str:
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid,
        "school_id": school_id,
        "full_name": "أحمد المعلم",
        "is_active": True,
    })
    return tid


async def _mk_class(school_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "name": f"Class-{cid[:6]}",
    })
    return cid


async def _mk_subject(school_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid,
        "school_id": school_id,
        "name": f"Subject-{sid[:6]}",
    })
    return sid


def _patch_dedicated_session(monkeypatch):
    """Make the reconciler's own ``async_session_factory()`` reuse the
    rolled-back conftest session, with ``commit()`` neutralized so nothing
    persists beyond the test transaction."""
    @contextlib.asynccontextmanager
    async def _factory():
        original_commit = db.session.commit

        async def _noop_commit():
            await db.session.flush()

        monkeypatch.setattr(db.session, "commit", _noop_commit, raising=False)
        try:
            yield db.session
        finally:
            monkeypatch.setattr(db.session, "commit", original_commit, raising=False)

    # The function does `from db import async_session_factory` at call time.
    import db as db_module
    monkeypatch.setattr(db_module, "async_session_factory", _factory, raising=False)


def _patch_sessions(monkeypatch, sessions):
    async def _fake_resolve(school_id, teacher_id):
        return sessions
    monkeypatch.setattr(rd, "_resolve_teacher_sessions", _fake_resolve)


async def _active_assignments(teacher_id, school_id):
    rows = await gd_find(
        db.session, "teacher_assignments",
        {"teacher_id": teacher_id, "school_id": school_id}, limit=1000,
    )
    return [r for r in rows if r.get("is_active") is not False]


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_materializes_assignments_from_schedule(monkeypatch):
    school_id = await _mk_school()
    teacher_id = await _mk_teacher(school_id)
    c1, c2 = await _mk_class(school_id), await _mk_class(school_id)
    s1, s2 = await _mk_subject(school_id), await _mk_subject(school_id)
    _patch_sessions(monkeypatch, [
        {"class_id": c1, "subject_id": s1},
        {"class_id": c2, "subject_id": s2},
        {"class_id": c1, "subject_id": s1},  # duplicate pair -> single row
    ])
    _patch_dedicated_session(monkeypatch)

    created = await rd._reconcile_teacher_assignments_from_schedule(
        school_id, teacher_id, "أحمد المعلم")
    assert created == 2

    active = await _active_assignments(teacher_id, school_id)
    pairs = {(a.get("class_id"), a.get("subject_id")) for a in active}
    assert pairs == {(c1, s1), (c2, s2)}


@pytest.mark.asyncio
async def test_idempotent_second_run_creates_nothing(monkeypatch):
    school_id = await _mk_school()
    teacher_id = await _mk_teacher(school_id)
    c1, s1 = await _mk_class(school_id), await _mk_subject(school_id)
    _patch_sessions(monkeypatch, [{"class_id": c1, "subject_id": s1}])
    _patch_dedicated_session(monkeypatch)

    first = await rd._reconcile_teacher_assignments_from_schedule(
        school_id, teacher_id, None)
    second = await rd._reconcile_teacher_assignments_from_schedule(
        school_id, teacher_id, None)
    assert first == 1
    assert second == 0

    active = await _active_assignments(teacher_id, school_id)
    assert len([a for a in active if a.get("class_id") == c1]) == 1


@pytest.mark.asyncio
async def test_preserves_existing_manual_assignment(monkeypatch):
    school_id = await _mk_school()
    teacher_id = await _mk_teacher(school_id)
    manual_class, manual_subj = await _mk_class(school_id), await _mk_subject(school_id)
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "teacher_id": teacher_id,
        "class_id": manual_class,
        "subject_id": manual_subj,
        "is_active": True,
    })
    sched_class, sched_subj = await _mk_class(school_id), await _mk_subject(school_id)
    _patch_sessions(monkeypatch, [{"class_id": sched_class, "subject_id": sched_subj}])
    _patch_dedicated_session(monkeypatch)

    created = await rd._reconcile_teacher_assignments_from_schedule(
        school_id, teacher_id, None)
    assert created == 1

    active = await _active_assignments(teacher_id, school_id)
    pairs = {(a.get("class_id"), a.get("subject_id")) for a in active}
    assert (manual_class, manual_subj) in pairs  # manual row preserved
    assert (sched_class, sched_subj) in pairs


@pytest.mark.asyncio
async def test_reactivates_soft_deleted_assignment(monkeypatch):
    school_id = await _mk_school()
    teacher_id = await _mk_teacher(school_id)
    c1, s1 = await _mk_class(school_id), await _mk_subject(school_id)
    revived_id = str(uuid.uuid4())
    await gd_insert(db.session, "teacher_assignments", {
        "id": revived_id,
        "school_id": school_id,
        "teacher_id": teacher_id,
        "class_id": c1,
        "subject_id": s1,
        "is_active": False,
    })
    _patch_sessions(monkeypatch, [{"class_id": c1, "subject_id": s1}])
    _patch_dedicated_session(monkeypatch)

    created = await rd._reconcile_teacher_assignments_from_schedule(
        school_id, teacher_id, None)
    assert created == 1

    rows = await gd_find(
        db.session, "teacher_assignments",
        {"teacher_id": teacher_id, "class_id": c1}, limit=10)
    assert len(rows) == 1  # reactivated, not duplicated
    assert rows[0].get("id") == revived_id
    assert rows[0].get("is_active") is True


@pytest.mark.asyncio
async def test_skips_sessions_without_subject(monkeypatch):
    school_id = await _mk_school()
    teacher_id = await _mk_teacher(school_id)
    c1 = str(uuid.uuid4())
    _patch_sessions(monkeypatch, [{"class_id": c1, "subject_id": None}])
    _patch_dedicated_session(monkeypatch)

    created = await rd._reconcile_teacher_assignments_from_schedule(
        school_id, teacher_id, None)
    assert created == 0
    active = await _active_assignments(teacher_id, school_id)
    assert active == []


@pytest.mark.asyncio
async def test_ignores_foreign_tenant_class_or_subject(monkeypatch):
    """Defense-in-depth: a (class_id, subject_id) whose class or subject belongs
    to ANOTHER school must never be materialized — teacher_assignments is the
    class-access permission source, so cross-tenant IDs in corrupted schedule
    data cannot widen access."""
    school_id = await _mk_school()
    teacher_id = await _mk_teacher(school_id)
    other_school = await _mk_school()

    valid_class, valid_subj = await _mk_class(school_id), await _mk_subject(school_id)
    foreign_class = await _mk_class(other_school)
    foreign_subj = await _mk_subject(other_school)

    _patch_sessions(monkeypatch, [
        {"class_id": valid_class, "subject_id": valid_subj},        # in-tenant -> kept
        {"class_id": foreign_class, "subject_id": valid_subj},      # foreign class -> dropped
        {"class_id": valid_class, "subject_id": foreign_subj},      # foreign subject -> dropped
        {"class_id": foreign_class, "subject_id": foreign_subj},    # both foreign -> dropped
    ])
    _patch_dedicated_session(monkeypatch)

    created = await rd._reconcile_teacher_assignments_from_schedule(
        school_id, teacher_id, None)
    assert created == 1

    active = await _active_assignments(teacher_id, school_id)
    pairs = {(a.get("class_id"), a.get("subject_id")) for a in active}
    assert pairs == {(valid_class, valid_subj)}


@pytest.mark.asyncio
async def test_skips_independent_teacher_workspace(monkeypatch):
    teacher_id = str(uuid.uuid4())
    itw_school = f"itw_{uuid.uuid4()}"
    called = {"resolved": False}

    async def _should_not_run(school_id, tid):
        called["resolved"] = True
        return [{"class_id": "x", "subject_id": "y"}]

    monkeypatch.setattr(rd, "_resolve_teacher_sessions", _should_not_run)
    _patch_dedicated_session(monkeypatch)

    created = await rd._reconcile_teacher_assignments_from_schedule(
        itw_school, teacher_id, None)
    assert created == 0
    assert called["resolved"] is False  # short-circuits before reading schedule
