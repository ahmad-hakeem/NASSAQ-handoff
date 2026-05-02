"""Task #126 — regression guard for the class-relocation flow.

The relocation feature spans three subsystems and relies on subtle
Arabic→English day mapping plus date-window math. This test file pins
that contract end-to-end so a future refactor can't silently:

(a) drop the period-aware notification fan-out that limits recipients of
    a *recurring* unavailability to the teacher who actually has a
    session in the affected (day, period) — ensuring a Sunday-period-2
    closure doesn't page the Monday teacher of the same class.

(b) bypass the date-window filter on a *long-term* unavailability — a
    closure scoped to dates that fall only on Mondays must not notify
    the Sunday teacher just because they're assigned to the class.

(c) stop tinting cells in the master grid: ``GET /schedule/master-grid``
    must surface ``is_relocated`` + ``alternative_location`` on both the
    regular timetable cell **and** the synthetic substitute cell that
    overlays today's ``substitute_assignments`` row.

All three hold the relocation overlay together — losing any one of them
silently breaks the principal's ability to see / coordinate a relocation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from dependencies import db
from engines.sql_utils import gd_count, gd_find, gd_insert


# ---------------------------------------------------------------------------
# Seed helpers — kept tiny and explicit so each test reads top-to-bottom.
# ---------------------------------------------------------------------------


async def _mk_teacher(school_id: str) -> str:
    """Insert a teacher row + matching users row.

    The notification fan-out writes to ``notifications.user_id`` which has
    a FK to ``users.id``; the codebase treats the teacher_id as the
    user_id for in-app notifications. The test fixtures otherwise create
    standalone ``teachers`` rows that lack a paired user, so we create
    the user row with the same id here to mirror production.
    """
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": tid,
        "role": "teacher",
        "tenant_id": school_id,
        "email": f"{tid}@t.test",
        "full_name": f"T-{tid[:6]}",
        "is_active": True,
        "password_hash": "x",
    })
    await gd_insert(db.session, "teachers", {
        "id": tid,
        "user_id": tid,
        "school_id": school_id,
        "full_name": f"T-{tid[:6]}",
        "is_active": True,
    })
    return tid


async def _mk_class(school_id: str, name: str = "1A") -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "name": name,
        "is_active": True,
    })
    return cid


async def _mk_timetable(school_id: str, *, status: str = "published") -> str:
    tid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "timetables", {
        "id": tid,
        "school_id": school_id,
        "name": f"TT-{tid[:6]}",
        "academic_year": "2026-2027",
        "semester": 1,
        "status": status,
        "version": 1,
        "total_sessions": 0,
        "created_at": now,
        "updated_at": now,
    })
    return tid


async def _mk_session(
    *,
    timetable_id: str,
    school_id: str,
    teacher_id: str,
    class_id: str,
    day: str,
    period: int,
    subject_id: str | None = None,
    class_name: str | None = None,
    subject_name: str | None = None,
) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "timetable_sessions", {
        "id": sid,
        "timetable_id": timetable_id,
        "school_id": school_id,
        "teacher_id": teacher_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "class_name": class_name,
        "subject_name": subject_name,
        "day_of_week": day,
        "period_number": period,
    })
    return sid


async def _mk_class_assignment(school_id: str, teacher_id: str, class_id: str) -> None:
    await gd_insert(db.session, "teacher_class_assignments", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "teacher_id": teacher_id,
        "class_id": class_id,
    })


async def _notifications_for(teacher_id: str) -> list[dict]:
    return await gd_find(db.session, "notifications", {"user_id": teacher_id}, limit=100)


# ---------------------------------------------------------------------------
# (a) Recurring unavailability: Arabic day name → only the slot teacher.
# ---------------------------------------------------------------------------


async def test_recurring_unavailability_with_arabic_day_notifies_only_slot_teacher(
    client, school_principal_headers, tenant_a,
):
    """A recurring closure for "الأحد" / period 2 must reach only the
    teacher whose published session lands on (sunday, period=2). The
    teacher that holds the class on Monday/period 2 must NOT be paged
    even though they're assigned to the same class — this is the
    period-aware fan-out the modal relies on.

    The Arabic day name is the headline detail: if the AR→EN translation
    in ``school_settings_mod.create_unavailability`` regresses, every
    recurring closure silently degrades to either notifying everyone or
    no-one (depending on which side of the bug).
    """
    cls_id = await _mk_class(tenant_a)
    teacher_sun = await _mk_teacher(tenant_a)
    teacher_mon = await _mk_teacher(tenant_a)
    teacher_other = await _mk_teacher(tenant_a)  # never teaches this class

    timetable = await _mk_timetable(tenant_a, status="published")
    await _mk_session(
        timetable_id=timetable, school_id=tenant_a, teacher_id=teacher_sun,
        class_id=cls_id, day="sunday", period=2,
    )
    await _mk_session(
        timetable_id=timetable, school_id=tenant_a, teacher_id=teacher_mon,
        class_id=cls_id, day="monday", period=2,
    )
    # Both Sunday & Monday teachers also have stale class_assignments rows;
    # the legacy fan-out used those, so this guards the period-aware path.
    await _mk_class_assignment(tenant_a, teacher_sun, cls_id)
    await _mk_class_assignment(tenant_a, teacher_mon, cls_id)
    await _mk_class_assignment(tenant_a, teacher_other, cls_id)
    await db.session.commit()

    payload = {
        "entity_type": "class",
        "entity_id": cls_id,
        "entity_name": "1A",
        "unavailability_type": "recurring",
        "day": "الأحد",  # critical: Arabic name, must map to "sunday".
        "period": "2",
        "alternative_location": "المعمل",
        "reason": "صيانة",
    }
    r = await client.post(
        "/school/settings/unavailability",
        json=payload, headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    # Only the Sunday/period-2 teacher should be notified.
    assert body["notifications_sent"] == 1, (
        f"Recurring closure must notify exactly the slot teacher; "
        f"got notifications_sent={body['notifications_sent']}"
    )

    sun_notes = await _notifications_for(teacher_sun)
    mon_notes = await _notifications_for(teacher_mon)
    other_notes = await _notifications_for(teacher_other)

    assert len(sun_notes) == 1, (
        f"Sunday teacher must receive the relocation notification; "
        f"got {len(sun_notes)}"
    )
    assert mon_notes == [], (
        "Monday teacher must NOT be paged for a Sunday closure even though "
        "they teach the same class on a different day"
    )
    assert other_notes == [], (
        "Teachers without any session in the affected slot must not be paged"
    )

    note = sun_notes[0]
    # alternative_location was provided → relocation-flavoured copy must win.
    # نطابق "نقل" بلا تشكيل لأن العناوين قد تستخدم أو لا تستخدم الضمّة.
    assert "نقل" in (note.get("title") or ""), (
        f"Relocation notification title must use the relocation phrasing; "
        f"got title={note.get('title')!r}"
    )
    assert "موقع بديل" in (note.get("title") or ""), (
        f"Relocation title must mention the alternative-location framing; "
        f"got title={note.get('title')!r}"
    )
    assert "المعمل" in (note.get("message") or ""), (
        f"Notification body must mention the alternative location; "
        f"got message={note.get('message')!r}"
    )
    assert note.get("type") == "schedule"
    assert note.get("priority") == "high"
    assert note.get("related_entity") == "class"
    assert note.get("related_entity_id") == cls_id


# ---------------------------------------------------------------------------
# (b) Long-term unavailability: weekday filter inside [start_date, end_date].
# ---------------------------------------------------------------------------


def _next_weekday_iso(target_weekday: int) -> str:
    """Return YYYY-MM-DD for the next future date with the given Python
    weekday (Monday=0 .. Sunday=6). We anchor far enough in the future
    that "today" can never fall inside any per-test window.
    """
    base = datetime.now(timezone.utc).date() + timedelta(days=30)
    while base.weekday() != target_weekday:
        base += timedelta(days=1)
    return base.isoformat()


async def test_long_term_unavailability_filters_by_window_weekdays(
    client, school_principal_headers, tenant_a,
):
    """A long-term closure scoped to a single Monday must page only the
    teacher whose session lands on Monday for this class — not the
    Sunday teacher (whose weekday is outside the window) and not an
    unrelated teacher.

    This pins the date-window math in
    ``school_settings_mod.create_unavailability`` (long_term branch):
    losing the weekday filter would page every teacher of the class
    regardless of when their session actually falls.
    """
    cls_id = await _mk_class(tenant_a, name="2B")
    teacher_sun = await _mk_teacher(tenant_a)
    teacher_mon = await _mk_teacher(tenant_a)
    teacher_tue = await _mk_teacher(tenant_a)

    timetable = await _mk_timetable(tenant_a, status="published")
    await _mk_session(
        timetable_id=timetable, school_id=tenant_a, teacher_id=teacher_sun,
        class_id=cls_id, day="sunday", period=1,
    )
    await _mk_session(
        timetable_id=timetable, school_id=tenant_a, teacher_id=teacher_mon,
        class_id=cls_id, day="monday", period=1,
    )
    await _mk_session(
        timetable_id=timetable, school_id=tenant_a, teacher_id=teacher_tue,
        class_id=cls_id, day="tuesday", period=1,
    )
    await db.session.commit()

    # A 1-day Monday-only window. Python weekday(): Monday=0.
    monday_iso = _next_weekday_iso(0)
    payload = {
        "entity_type": "class",
        "entity_id": cls_id,
        "entity_name": "2B",
        "unavailability_type": "long_term",
        "start_date": monday_iso,
        "end_date": monday_iso,
        "reason": "تعقيم",
    }
    r = await client.post(
        "/school/settings/unavailability",
        json=payload, headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["notifications_sent"] == 1, (
        f"Long-term Monday-only closure must notify exactly the Monday "
        f"teacher; got notifications_sent={body['notifications_sent']}"
    )

    assert len(await _notifications_for(teacher_mon)) == 1, (
        "Monday teacher must receive the closure notification"
    )
    assert await _notifications_for(teacher_sun) == [], (
        "Sunday teacher must NOT be paged — Sunday is outside the closure window"
    )
    assert await _notifications_for(teacher_tue) == [], (
        "Tuesday teacher must NOT be paged — Tuesday is outside the closure window"
    )


async def test_long_term_unavailability_multi_weekday_window_pages_all_in_range(
    client, school_principal_headers, tenant_a,
):
    """Sanity counter-test for (b): when the window spans 7+ days, every
    weekday is included so all class teachers get paged. Without this the
    weekday filter could regress to "always empty" and silently drop
    every long-term notification.
    """
    cls_id = await _mk_class(tenant_a, name="3C")
    teacher_sun = await _mk_teacher(tenant_a)
    teacher_mon = await _mk_teacher(tenant_a)

    timetable = await _mk_timetable(tenant_a, status="published")
    await _mk_session(
        timetable_id=timetable, school_id=tenant_a, teacher_id=teacher_sun,
        class_id=cls_id, day="sunday", period=3,
    )
    await _mk_session(
        timetable_id=timetable, school_id=tenant_a, teacher_id=teacher_mon,
        class_id=cls_id, day="monday", period=3,
    )
    await db.session.commit()

    start = datetime.now(timezone.utc).date() + timedelta(days=10)
    end = start + timedelta(days=8)  # 9 calendar days → all 7 weekdays
    payload = {
        "entity_type": "class",
        "entity_id": cls_id,
        "entity_name": "3C",
        "unavailability_type": "long_term",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    r = await client.post(
        "/school/settings/unavailability",
        json=payload, headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["notifications_sent"] == 2, (
        f"Window spanning all 7 weekdays must page both teachers; "
        f"got notifications_sent={body['notifications_sent']}"
    )
    assert len(await _notifications_for(teacher_sun)) == 1
    assert len(await _notifications_for(teacher_mon)) == 1


# ---------------------------------------------------------------------------
# (c) Master grid surfaces is_relocated + alternative_location on both the
#     regular cell and the synthetic substitute cell.
# ---------------------------------------------------------------------------


_DAYS_EN_TO_AR = {
    "sunday": "الأحد",
    "monday": "الإثنين",
    "tuesday": "الثلاثاء",
    "wednesday": "الأربعاء",
    "thursday": "الخميس",
    "friday": "الجمعة",
    "saturday": "السبت",
}


async def test_master_grid_surfaces_relocation_on_regular_and_substitute_cells(
    client, school_principal_headers, tenant_a,
):
    """Seed a class held by an absent teacher today plus a substitute
    assignment, then post a recurring "alternative_location" unavailability
    for that class on today's day/period. The master-grid response must
    expose ``is_relocated=True`` + the same ``alternative_location`` on:

      * the original (now ``is_substituted``) cell in the absent teacher's
        row, and
      * the synthetic ``is_substitute`` cell in the substitute teacher's row.

    This is the contract ``FilledCell`` reads to render the orange tint /
    "نُقل إلى" tooltip across all cell variants. If either cell loses the
    overlay the principal's view becomes inconsistent — half the cells
    show the relocation, half don't.
    """
    cls_id = await _mk_class(tenant_a, name="4D")
    absent_teacher = await _mk_teacher(tenant_a)
    sub_teacher = await _mk_teacher(tenant_a)
    today_key = datetime.now(timezone.utc).strftime("%A").lower()
    period = 4

    timetable = await _mk_timetable(tenant_a, status="published")
    orig_session = await _mk_session(
        timetable_id=timetable, school_id=tenant_a, teacher_id=absent_teacher,
        class_id=cls_id, day=today_key, period=period,
        class_name="4D", subject_name="رياضيات",
    )

    # Mark the original teacher absent today so the cell flips to vacant
    # before substitution is overlaid.
    today_iso = datetime.now(timezone.utc).date().isoformat()
    await gd_insert(db.session, "teacher_attendance", {
        "id": str(uuid.uuid4()),
        "school_id": tenant_a,
        "teacher_id": absent_teacher,
        "status": "absent",
        "date": today_iso,
    })

    # Pre-existing substitute assignment for today (we don't go through the
    # service since this is a regression test for the grid response).
    await gd_insert(db.session, "substitute_assignments", {
        "id": str(uuid.uuid4()),
        "school_id": tenant_a,
        "timetable_id": timetable,
        "original_session_id": orig_session,
        "original_teacher_id": absent_teacher,
        "substitute_teacher_id": sub_teacher,
        "absence_date": today_iso,
        "day_of_week": today_key,
        "period_number": period,
        "class_id": cls_id,
        "class_name": "4D",
        "subject_name": "رياضيات",
    })

    # Recurring relocation for today's day+period using the Arabic day name.
    alt_location = "الساحة الخارجية"
    await client.post(
        "/school/settings/unavailability",
        json={
            "entity_type": "class",
            "entity_id": cls_id,
            "entity_name": "4D",
            "unavailability_type": "recurring",
            "day": _DAYS_EN_TO_AR[today_key],
            "period": str(period),
            "alternative_location": alt_location,
        },
        headers=school_principal_headers,
    )
    await db.session.commit()

    # Sanity: the relocation row was persisted with the alt location.
    relocations = await gd_find(
        db.session, "unavailability",
        {"school_id": tenant_a, "entity_id": cls_id}, limit=10,
    )
    assert any(r.get("alternative_location") == alt_location for r in relocations), (
        "Relocation row must persist alternative_location on the class record"
    )

    r = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}",
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()

    cells = body.get("cells") or {}
    period_key = str(period)

    # ── Regular (substituted) cell on the absent teacher's row ──────────
    absent_cell = (
        cells.get(absent_teacher, {}).get(today_key, {}).get(period_key)
    )
    assert absent_cell is not None, (
        f"Absent teacher must still have a cell at today/{period_key}; "
        f"cells for teacher={cells.get(absent_teacher)}"
    )
    assert absent_cell.get("is_substituted") is True, (
        "Absent teacher's cell must flip to is_substituted once a "
        "substitute is assigned"
    )
    assert absent_cell.get("is_relocated") is True, (
        f"Master grid must surface is_relocated on the regular "
        f"(substituted) cell; got cell={absent_cell}"
    )
    assert absent_cell.get("alternative_location") == alt_location, (
        f"alternative_location on substituted cell must echo what was "
        f"saved; got {absent_cell.get('alternative_location')!r}"
    )

    # ── Synthetic substitute cell on the substitute teacher's row ───────
    sub_cell = cells.get(sub_teacher, {}).get(today_key, {}).get(period_key)
    assert sub_cell is not None, (
        f"Substitute teacher must receive a synthetic cell at "
        f"today/{period_key}; cells for teacher={cells.get(sub_teacher)}"
    )
    assert sub_cell.get("is_substitute") is True
    assert sub_cell.get("is_relocated") is True, (
        f"Synthetic substitute cell must also carry is_relocated so the "
        f"substitute teacher sees the relocation tint; got cell={sub_cell}"
    )
    assert sub_cell.get("alternative_location") == alt_location, (
        f"alternative_location on substitute cell must echo what was "
        f"saved; got {sub_cell.get('alternative_location')!r}"
    )


async def test_master_grid_relocation_uses_arabic_day_mapping(
    client, school_principal_headers, tenant_a,
):
    """Tighter unit-style guard: even when there is no substitution at
    play, a recurring relocation written with the *Arabic* day name must
    decorate the regular timetable cell. This pins the AR→EN mapping
    inside ``schedule_master_grid_routes`` (``_AR_DAY_TO_EN``) — losing
    it silently strips the orange tint from the grid even though the
    unavailability row is present in the DB.
    """
    cls_id = await _mk_class(tenant_a, name="5E")
    teacher = await _mk_teacher(tenant_a)
    timetable = await _mk_timetable(tenant_a, status="published")
    # Use Tuesday so we don't accidentally collide with absent-teacher
    # logic that depends on `today_key`.
    await _mk_session(
        timetable_id=timetable, school_id=tenant_a, teacher_id=teacher,
        class_id=cls_id, day="tuesday", period=5,
        class_name="5E", subject_name="فيزياء",
    )

    await client.post(
        "/school/settings/unavailability",
        json={
            "entity_type": "class",
            "entity_id": cls_id,
            "entity_name": "5E",
            "unavailability_type": "recurring",
            "day": "الثلاثاء",  # Arabic — must map to "tuesday" in the grid.
            "period": "5",
            "alternative_location": "المختبر",
        },
        headers=school_principal_headers,
    )
    await db.session.commit()

    r = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}",
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    cells = (r.json().get("cells") or {})
    cell = cells.get(teacher, {}).get("tuesday", {}).get("5")
    assert cell is not None, (
        f"Teacher row must contain a cell at tuesday/5; "
        f"got teacher cells={cells.get(teacher)}"
    )
    assert cell.get("is_relocated") is True, (
        "Recurring relocation written with Arabic day name must light up "
        "is_relocated on the matching grid cell"
    )
    assert cell.get("alternative_location") == "المختبر"


# ---------------------------------------------------------------------------
# Sanity wiring check — the handler stored exactly one unavailability row
# per POST. Guards against double-insert regressions that would also
# duplicate notifications.
# ---------------------------------------------------------------------------


async def test_create_unavailability_persists_single_row(
    client, school_principal_headers, tenant_a,
):
    cls_id = await _mk_class(tenant_a, name="6F")
    await db.session.commit()

    r = await client.post(
        "/school/settings/unavailability",
        json={
            "entity_type": "class",
            "entity_id": cls_id,
            "entity_name": "6F",
            "unavailability_type": "recurring",
            "day": "الأحد",
            "period": "1",
            "alternative_location": "غرفة المصادر",
        },
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text

    count = await gd_count(
        db.session, "unavailability",
        {"school_id": tenant_a, "entity_id": cls_id},
    )
    assert count == 1, (
        f"Each POST must persist exactly one unavailability row; got {count}"
    )
