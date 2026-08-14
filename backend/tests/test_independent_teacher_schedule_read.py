"""Tests for the Independent-Teacher schedule READ model (Task #772).

The IT read path is subtly different from full-school schedules: rows live
directly in ``schedule_sessions`` (``status="scheduled"``) with no published
``timetables`` / ``schedules`` parent, no ``time_slots`` collection, and the
editor stores short weekday codes (``sun``/``mon``/…). These tests pin that
read model so a future change can't silently regress IT timetables back to
empty in جدولي / إدارة الحصص and the dashboard "today" block.

Covers:
  - ``_resolve_it_teacher_sessions`` for an ``itw_`` workspace
    (normalization, derived slot times, denormalized-name preference,
    (day, slot) dedup, and the today/day filter).
  - ``GET /time-slots`` synthesizing virtual slots for an IT workspace.
  - A guard that non-IT (published-timetable) schools are unaffected.
"""
from __future__ import annotations

import uuid

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert
from src.modules.portals.controllers.role_dashboards_mod import (
    _resolve_it_teacher_sessions,
    _resolve_teacher_sessions,
)

from tests._it_fixtures import mk_it_workspace


def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _seed_it_settings(school_id: str, *, periods=7, duration=45,
                            start="07:00") -> None:
    await gd_insert(db.session, "school_settings", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "working_days": ["sun", "mon", "tue", "wed", "thu"],
        "periods_per_day": periods,
        "period_duration": duration,
        "custom_settings": {"school_day_start": start},
        "language": "ar",
    })


async def _seed_it_session(ctx: dict, *, day, slot, class_id=None,
                           subject_id=None, class_name=None,
                           subject_name=None, sid=None) -> str:
    sid = sid or str(uuid.uuid4())
    row = {
        "id": sid,
        "school_id": ctx["wsid"],
        "schedule_id": f"itw_schedule_{ctx['wsid']}",
        "teacher_id": ctx["teacher_id"],
        "status": "scheduled",
        "day_of_week": day,
        "slot_number": slot,
        "class_id": class_id,
        "subject_id": subject_id,
    }
    if class_name is not None:
        row["class_name"] = class_name
    if subject_name is not None:
        row["subject_name"] = subject_name
    await gd_insert(db.session, "schedule_sessions", row)
    return sid


@pytest.mark.asyncio
async def test_it_resolver_returns_sessions_and_normalizes_days(client):
    """Short weekday codes are normalized to full names and slot times are
    derived from the workspace period config."""
    ctx = await mk_it_workspace(with_student=False, with_parent=False,
                                with_passkey=False)
    await _seed_it_settings(ctx["wsid"], periods=7, duration=45, start="07:00")
    await _seed_it_session(ctx, day="sun", slot=1, class_id=ctx["class_id"])

    rows = await _resolve_it_teacher_sessions(ctx["wsid"], ctx["teacher_id"])
    assert len(rows) == 1
    row = rows[0]
    assert row["day_of_week"] == "sunday"  # sun -> sunday
    assert row["slot_number"] == 1
    assert row["period_number"] == 1
    # First slot starts at the configured day start; 45-min period.
    assert row["start_time"] == "07:00"
    assert row["end_time"] == "07:45"
    assert row["time"] == "07:00"


@pytest.mark.asyncio
async def test_it_resolver_prefers_denormalized_names(client):
    """The row's own denormalized class/subject names win over the joined
    rows; when absent, the joined rows provide the fallback."""
    ctx = await mk_it_workspace(with_student=False, with_parent=False,
                                with_passkey=False)
    await _seed_it_settings(ctx["wsid"])

    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id, "school_id": ctx["wsid"],
        "name": "Math", "name_ar": "الرياضيات", "is_active": True,
    })

    # Row 1: carries denormalized names → those must be preferred.
    await _seed_it_session(
        ctx, day="mon", slot=1, class_id=ctx["class_id"],
        subject_id=subject_id, class_name="فصل مخصص",
        subject_name="مادة مخصصة",
    )
    # Row 2: no denormalized names → fall back to the joined class/subject.
    await _seed_it_session(
        ctx, day="mon", slot=2, class_id=ctx["class_id"],
        subject_id=subject_id,
    )

    rows = await _resolve_it_teacher_sessions(ctx["wsid"], ctx["teacher_id"])
    by_slot = {r["slot_number"]: r for r in rows}

    assert by_slot[1]["class_name"] == "فصل مخصص"
    assert by_slot[1]["subject_name"] == "مادة مخصصة"
    # Fallbacks: class name from the classes row (fixture seeds "فصل أ"),
    # subject name from the subjects row's name_ar.
    assert by_slot[2]["class_name"] == "فصل أ"
    assert by_slot[2]["subject_name"] == "الرياضيات"


@pytest.mark.asyncio
async def test_it_resolver_dedups_by_day_and_slot(client):
    """A stale duplicate (same day + slot) must not double up the read."""
    ctx = await mk_it_workspace(with_student=False, with_parent=False,
                                with_passkey=False)
    await _seed_it_settings(ctx["wsid"])
    await _seed_it_session(ctx, day="tue", slot=3, class_id=ctx["class_id"])
    await _seed_it_session(ctx, day="tue", slot=3, class_id=ctx["class_id"])

    rows = await _resolve_it_teacher_sessions(ctx["wsid"], ctx["teacher_id"])
    keys = [(r["day_of_week"], r["slot_number"]) for r in rows]
    assert keys == [("tuesday", 3)]


@pytest.mark.asyncio
async def test_it_resolver_day_filter_today_path(client):
    """The day filter (dashboard 'today') restricts to one day and matches
    on the normalized full name even when callers pass a full name."""
    ctx = await mk_it_workspace(with_student=False, with_parent=False,
                                with_passkey=False)
    await _seed_it_settings(ctx["wsid"])
    await _seed_it_session(ctx, day="sun", slot=1, class_id=ctx["class_id"])
    await _seed_it_session(ctx, day="mon", slot=1, class_id=ctx["class_id"])

    # Caller passes the full name; stored rows use short codes.
    rows = await _resolve_it_teacher_sessions(
        ctx["wsid"], ctx["teacher_id"], day_of_week="sunday")
    assert len(rows) == 1
    assert rows[0]["day_of_week"] == "sunday"

    # Short-code caller resolves identically.
    rows_short = await _resolve_it_teacher_sessions(
        ctx["wsid"], ctx["teacher_id"], day_of_week="sun")
    assert len(rows_short) == 1
    assert rows_short[0]["day_of_week"] == "sunday"


@pytest.mark.asyncio
async def test_it_resolver_routes_through_shared_resolver(client):
    """The shared `_resolve_teacher_sessions` entry point branches into the
    IT-aware reader for an itw_ school, so the read page and dashboard agree."""
    ctx = await mk_it_workspace(with_student=False, with_parent=False,
                                with_passkey=False)
    await _seed_it_settings(ctx["wsid"])
    await _seed_it_session(ctx, day="wed", slot=2, class_id=ctx["class_id"])

    rows = await _resolve_teacher_sessions(ctx["wsid"], ctx["teacher_id"])
    assert len(rows) == 1
    assert rows[0]["day_of_week"] == "wednesday"
    assert rows[0]["slot_number"] == 2


@pytest.mark.asyncio
async def test_time_slots_synthesizes_virtual_slots_for_it_workspace(
    client, platform_admin_headers,
):
    """GET /time-slots synthesizes virtual rows for an IT workspace that has
    no persisted time_slots collection.

    The /time-slots router is gated by `require_full_school_tenant`, which
    denies IT callers; a platform admin manages the workspace and reaches the
    synthesis branch by passing the itw_ school_id explicitly.
    """
    ctx = await mk_it_workspace(with_student=False, with_parent=False,
                                with_passkey=False)
    await _seed_it_settings(ctx["wsid"], periods=7, duration=45, start="07:00")

    h = platform_admin_headers
    resp = await client.get(f"/time-slots?school_id={ctx['wsid']}", headers=h)
    assert resp.status_code == 200, resp.text
    slots = resp.json()
    assert len(slots) == 7
    assert [s["slot_number"] for s in slots] == [1, 2, 3, 4, 5, 6, 7]
    first = slots[0]
    assert first["start_time"] == "07:00"
    assert first["end_time"] == "07:45"
    assert first["id"] == f"itw_slot_{ctx['wsid']}_1"
    # Stable ids across loads so the FE list keys don't churn.
    resp2 = await client.get(f"/time-slots?school_id={ctx['wsid']}", headers=h)
    assert [s["id"] for s in resp2.json()] == [s["id"] for s in slots]


@pytest.mark.asyncio
async def test_non_it_published_schedule_unaffected(client):
    """Guard: a normal (non-IT) school keeps reading from its published
    timetable and never enters the IT synthetic-workspace path."""
    school_id = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": school_id, "name": "Regular School",
        "code": f"S{school_id[:6]}", "status": "active",
        "country": "SA", "language": "ar",
    })
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "school_id": school_id,
        "full_name": "T", "is_active": True,
    })
    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id, "school_id": school_id, "name": "1A", "is_active": True,
    })

    # Published timetable + a session in the standard (full-name day) shape.
    timetable_id = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": timetable_id, "school_id": school_id,
        "name": "TT", "academic_year": "2026-2027", "semester": 1,
        "status": "published", "version": 1, "total_sessions": 1,
        "published_at": "2026-06-01T00:00:00+00:00",
    })
    await gd_insert(db.session, "timetable_sessions", {
        "id": str(uuid.uuid4()), "timetable_id": timetable_id,
        "school_id": school_id, "teacher_id": teacher_id,
        "day_of_week": "sunday", "period_number": 1,
        "class_id": class_id,
    })

    rows = await _resolve_teacher_sessions(school_id, teacher_id)
    assert len(rows) == 1
    assert rows[0]["day_of_week"] == "sunday"

    # And a non-IT school must never enter the IT resolver: even a teacher
    # with schedule_sessions rows (which the IT reader would pick up) gets
    # nothing from the IT path because the school id isn't itw_.
    await gd_insert(db.session, "schedule_sessions", {
        "id": str(uuid.uuid4()), "school_id": school_id,
        "schedule_id": f"itw_schedule_{school_id}",
        "teacher_id": teacher_id, "status": "scheduled",
        "day_of_week": "mon", "slot_number": 1, "class_id": class_id,
    })
    rows_after = await _resolve_teacher_sessions(school_id, teacher_id)
    assert len(rows_after) == 1  # still only the published timetable session
    assert rows_after[0]["day_of_week"] == "sunday"
