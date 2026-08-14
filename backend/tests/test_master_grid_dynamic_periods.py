"""Task #119 — regression check that the Master Grid, the Smart Scheduling
engine, and the Smart Schedule frontend grid all honour each school's
configured period count instead of falling back to the legacy hardcoded
7 periods.

Two configurations are exercised:
- 10-period day driven by ``school_settings.periods_per_day = 10`` only
  (no rows in ``time_slots``) — the second tier of ``_resolve_periods_for_school``.
- 8-period day driven by 8 teaching ``time_slots`` plus a break row that must
  be filtered out — the first tier of ``_resolve_periods_for_school``.

Each configuration is verified at four layers:
1. The pure helper ``_resolve_periods_for_school``.
2. The public ``GET /api/schedule/master-grid`` endpoint.
3. The Smart Scheduling engine's ``load_school_settings`` (no silent 7).
4. End-to-end engine generation — produced ``timetable_sessions`` span
   period_number 1..10 with no hardcoded 7 leaking into the result.
5. Static check on ``SchedulePageNew.jsx`` — the MasterMatrix grid
   derives its column count from the dynamic ``periods`` payload and
   contains no hardcoded ``7`` period count.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dependencies import db
from engines.smart_scheduling_engine import SmartSchedulingEngine
from engines.sql_utils import gd_find, gd_insert
from src.modules.scheduling.controllers.schedule_master_grid_routes import _resolve_periods_for_school


async def _mk_settings(school_id: str, periods_per_day: int) -> None:
    await gd_insert(db.session, "school_settings", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "working_days": ["sunday", "monday", "tuesday", "wednesday", "thursday"],
        "periods_per_day": periods_per_day,
    })


async def _mk_time_slot(
    school_id: str,
    period_number: int,
    *,
    is_break: bool = False,
    is_prayer: bool = False,
) -> None:
    await gd_insert(db.session, "time_slots", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "name": f"Period {period_number}",
        "slot_number": period_number,
        "period_number": period_number,
        "start_time": f"{6 + period_number:02d}:00",
        "end_time": f"{7 + period_number:02d}:00",
        "duration_minutes": 45,
        "is_break": is_break,
        "is_prayer": is_prayer,
        "is_active": True,
    })


# ---------------------------------------------------------------------------
# 1. _resolve_periods_for_school helper — direct unit coverage.
# ---------------------------------------------------------------------------

async def test_resolve_periods_uses_periods_per_day_when_no_time_slots(tenant_a):
    await _mk_settings(tenant_a, periods_per_day=10)

    periods = await _resolve_periods_for_school(tenant_a)

    assert periods == list(range(1, 11)), (
        f"Expected 1..10 from periods_per_day=10, got {periods}"
    )


async def test_resolve_periods_uses_time_slots_and_skips_breaks(tenant_a):
    await _mk_settings(tenant_a, periods_per_day=10)  # should be ignored — slots win
    for n in range(1, 9):  # 8 teaching periods
        await _mk_time_slot(tenant_a, n)
    # Two non-teaching slots (break) interleaved among the period numbers
    # to make sure they're filtered regardless of slot_number value.
    await _mk_time_slot(tenant_a, 99, is_break=True)
    await _mk_time_slot(tenant_a, 100, is_break=True)

    periods = await _resolve_periods_for_school(tenant_a)

    assert periods == list(range(1, 9)), (
        f"Expected exactly 8 teaching periods (1..8), got {periods}"
    )
    assert 99 not in periods and 100 not in periods, (
        "Break slots must not appear in the period list"
    )


# ---------------------------------------------------------------------------
# 2. Public master-grid endpoint — surface the dynamic period list.
# ---------------------------------------------------------------------------

async def test_master_grid_returns_ten_periods_for_ten_period_school(
    client, school_principal_headers, tenant_a,
):
    await _mk_settings(tenant_a, periods_per_day=10)
    await db.session.commit()

    r = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}",
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["periods"] == list(range(1, 11)), (
        f"Master Grid must expose 10 period columns; got {body['periods']}"
    )
    # Defensive: no hardcoded 7 leaking back through the response.
    assert len(body["periods"]) != 7, "Hardcoded 7-period fallback regressed"


async def test_master_grid_returns_eight_periods_from_time_slots(
    client, school_principal_headers, tenant_a,
):
    await _mk_settings(tenant_a, periods_per_day=10)  # mismatched on purpose
    for n in range(1, 9):
        await _mk_time_slot(tenant_a, n)
    await _mk_time_slot(tenant_a, 50, is_break=True)
    await db.session.commit()

    r = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}",
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["periods"] == list(range(1, 9)), (
        f"Master Grid must derive 8 columns from time_slots; got {body['periods']}"
    )
    assert 50 not in body["periods"], "Break time_slot must not become a column"


# ---------------------------------------------------------------------------
# 3. Smart Scheduling engine — generation honours the configured count.
# ---------------------------------------------------------------------------

async def test_engine_load_school_settings_honours_ten_periods(tenant_a):
    await _mk_settings(tenant_a, periods_per_day=10)
    for n in range(1, 11):
        await _mk_time_slot(tenant_a, n)

    engine = SmartSchedulingEngine(db)
    loaded = await engine.load_school_settings(tenant_a)

    assert loaded["periods_per_day"] == 10, (
        f"Engine must surface 10 periods, not the legacy 7; got {loaded['periods_per_day']}"
    )
    assert loaded["teaching_period_numbers"] == list(range(1, 11)), (
        f"Engine teaching periods must span 1..10; got {loaded['teaching_period_numbers']}"
    )


# ---------------------------------------------------------------------------
# 4. End-to-end engine generation — produced sessions span periods 1..10.
# ---------------------------------------------------------------------------

async def _seed_full_ten_period_school(school_id: str) -> dict:
    """Seed the minimum data set needed for ``generate_timetable`` to run
    against a 10-period school. Returns ids the test can reference.

    The seed deliberately oversaturates demand (5 days × 10 periods = 50
    teaching slots, weekly_periods=50 across two subjects) so the gap-filler
    will reach the upper period numbers, exposing any silent 7-period cap.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Schedule timing — 10 teaching periods/day across 5 working days.
    await _mk_settings(school_id, periods_per_day=10)
    for n in range(1, 11):
        await _mk_time_slot(school_id, n)

    # Academic year + term (validate_data_readiness needs both).
    ay_id = str(uuid.uuid4())
    await gd_insert(db.session, "academic_years", {
        "id": ay_id,
        "school_id": school_id,
        "name": "2026-2027",
        "name_ar": "2026-2027",
        "start_date": "2026-09-01",
        "end_date": "2027-06-30",
        "is_current": True,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })
    await gd_insert(db.session, "academic_terms", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "academic_year_id": ay_id,
        "name": "Term 1",
        "is_active": True,
        "is_current": True,
    })

    # One grade level + one class on it.
    grade_id = str(uuid.uuid4())
    await gd_insert(db.session, "grade_levels", {
        "id": grade_id,
        "school_id": school_id,
        "name": "G1",
        "code": "1",
        "is_active": True,
    })
    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id,
        "school_id": school_id,
        "name": "1A",
        "grade_id": grade_id,
        "is_active": True,
    })

    # Two subjects, each with 25 weekly periods → 50 total = full week.
    subj_a = str(uuid.uuid4())
    subj_b = str(uuid.uuid4())
    for sid, name in ((subj_a, "Math"), (subj_b, "Arabic")):
        await gd_insert(db.session, "subjects", {
            "id": sid,
            "school_id": school_id,
            "name": name,
            "name_ar": name,
            "is_active": True,
        })
        await gd_insert(db.session, "grade_subjects", {
            "id": str(uuid.uuid4()),
            "school_id": school_id,
            "grade_id": grade_id,
            "subject_id": sid,
            "weekly_periods": 25,
            "is_active": True,
        })

    # Two teachers — each loaded for 25 periods/week, assigned to one subject.
    teach_a = str(uuid.uuid4())
    teach_b = str(uuid.uuid4())
    for tid, sid in ((teach_a, subj_a), (teach_b, subj_b)):
        await gd_insert(db.session, "teachers", {
            "id": tid,
            "school_id": school_id,
            "full_name": f"T-{tid[:6]}",
            "weekly_periods": 25,
            "primary_subject_id": sid,
            "is_active": True,
        })
        await gd_insert(db.session, "teacher_assignments", {
            "id": str(uuid.uuid4()),
            "school_id": school_id,
            "teacher_id": tid,
            "subject_id": sid,
            "class_id": class_id,
            "weekly_sessions": 25,
            "periods_per_week": 25,
            "is_active": True,
        })

    return {"class_id": class_id, "grade_id": grade_id}


async def test_generate_timetable_uses_all_ten_periods(tenant_a):
    """Run the engine end-to-end against a 10-period school and assert the
    saved sessions span period_number 1..10 — proving no hardcoded 7-period
    cap leaks into the generation result.
    """
    await _seed_full_ten_period_school(tenant_a)
    await db.session.commit()

    engine = SmartSchedulingEngine(db)
    result = await engine.generate_timetable(
        school_id=tenant_a,
        created_by="test",
        calling_user={"id": "test", "tenant_id": tenant_a, "role": "school_principal"},
    )

    assert result.success, (
        f"Generation must succeed for a 10-period school; got "
        f"status={result.status} message={result.message_ar}"
    )
    assert result.scheduled_sessions > 0, "Engine produced no sessions"

    # Pull the saved sessions and verify the period_number distribution.
    sessions = await gd_find(
        db.session, "timetable_sessions", {"school_id": tenant_a}, limit=1000,
    )
    assert sessions, "No sessions persisted to timetable_sessions"

    period_numbers = sorted({int(s["period_number"]) for s in sessions if s.get("period_number") is not None})
    assert period_numbers, "Sessions missing period_number"
    assert max(period_numbers) == 10, (
        f"Engine must schedule into period 10 for a 10-period school; "
        f"max scheduled period was {max(period_numbers)} — period numbers={period_numbers}"
    )
    assert max(period_numbers) != 7, (
        "Hardcoded 7-period cap regressed in the generation output"
    )
    # All session periods must be in 1..10 — no row outside the configured range.
    assert all(1 <= p <= 10 for p in period_numbers), (
        f"Engine emitted period_number outside 1..10: {period_numbers}"
    )


# ---------------------------------------------------------------------------
# 5. Static frontend check — SchedulePageNew uses dynamic period count.
# ---------------------------------------------------------------------------
# The frontend has no JS test runner installed (no @testing-library/react),
# so we guard the Smart Schedule grid contract with a static check on the
# JSX source: MasterMatrix must size its column grid from `periods.length`,
# and no hardcoded 7-period assumption may resurface.

def test_schedule_page_new_renders_dynamic_period_columns():
    repo_root = Path(__file__).resolve().parents[2]
    src = (repo_root / "frontend/src/pages/SchedulePageNew.jsx").read_text(encoding="utf-8")

    # Periods are read from the master-grid payload; tolerant of formatting
    # changes (e.g. `grid?.periods ?? FALLBACK_PERIODS`, line breaks, etc.).
    assert re.search(
        r"grid\??\.\s*periods\s*(?:\|\||\?\?)\s*FALLBACK_PERIODS",
        src,
    ), "SchedulePageNew must read `periods` from the master-grid payload"

    # FALLBACK_PERIODS must be an empty array so the dynamic payload always
    # wins. A non-empty literal here would mask a missing/incorrect API
    # response and silently re-introduce a static period count.
    assert re.search(
        r"FALLBACK_PERIODS\s*=\s*\[\s*\]",
        src,
    ), (
        "FALLBACK_PERIODS must be an empty array so the dynamic payload "
        "always drives the column count"
    )

    # MasterMatrix sizes its column grid from the dynamic period list, not
    # a literal. Accept any expression of the shape `… periods.length …`
    # multiplied by `days.length` for total data columns.
    assert re.search(
        r"[Dd]ays\.length\s*\*\s*periods\.length",
        src,
    ), (
        "MasterMatrix must compute totalDataCols from a days-count "
        "expression (e.g. `displayDays.length`) multiplied by "
        "`periods.length` so column count tracks the configured period "
        "list (10 for a 10-period school)"
    )
    assert re.search(
        r"repeat\(\s*\$\{\s*totalDataCols\s*\}",
        src,
    ), (
        "MasterMatrix gridTemplateColumns must repeat by totalDataCols "
        "so the column count tracks the dynamic period list"
    )

    # No literal 7-period cap may resurface in any period-related expression.
    # We scan code lines that touch `period` for a bare `7` literal in a
    # context that suggests a count or comparison (e.g. `=== 7`, `> 7`,
    # `length: 7`, `Array(7)`). Numeric `7` inside string literals or
    # comments is ignored to avoid false positives on Arabic period labels.
    def _strip_strings_and_comments(line: str) -> str:
        no_line_comment = re.sub(r"//.*$", "", line)
        no_strings = re.sub(r"(['\"`])(?:\\.|(?!\1).)*\1", "''", no_line_comment)
        return no_strings

    offenders: list[str] = []
    for line in src.splitlines():
        if not re.search(r"\bperiod", line, re.IGNORECASE):
            continue
        scrubbed = _strip_strings_and_comments(line)
        # Only flag a `7` literal that appears as a number token (not part
        # of a longer numeric like 70 / 7.5 / 7px and not an identifier).
        if re.search(r"(?<![\w.])7(?![\w.])", scrubbed):
            offenders.append(line.strip())

    assert not offenders, (
        f"Hardcoded 7-period assumption resurfaced near `period` lines: "
        f"{offenders[:3]}"
    )


# ---------------------------------------------------------------------------
# 6. End-to-end timing change → time_slots regen → master-grid headers.
#    Task #132 — strict E2E binding for Schedule Settings.
# ---------------------------------------------------------------------------

async def test_timing_change_via_put_settings_drives_master_grid_headers(
    client, school_principal_headers, tenant_a,
):
    """Saving a new dayStart/periodDuration/breakDuration via PUT
    /school/settings must regenerate time_slots and surface new headers
    through GET /api/schedule/master-grid — no hardcoded fallback."""
    # Seed minimal settings
    await _mk_settings(tenant_a, periods_per_day=6)
    await db.session.commit()

    payload = {
        "dayStart": "08:00",
        "periodsPerDay": 6,
        "periodDuration": 50,
        "breakDuration": 10,
    }
    r = await client.put(
        "/school/settings",
        headers=school_principal_headers,
        json=payload,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("time_slots_regenerated", {}).get("regenerated") is True, (
        f"PUT /school/settings must regenerate time_slots when timing "
        f"fields change; got {body.get('time_slots_regenerated')}"
    )

    # Master Grid must expose 6 columns and the first teaching slot must
    # start at the new dayStart (08:00) — proving the value flows from
    # Schedule Settings → DB → Master Grid headers with no fallbacks.
    r2 = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}",
        headers=school_principal_headers,
    )
    assert r2.status_code == 200, r2.text
    grid = r2.json()
    assert grid["periods"] == list(range(1, 7)), (
        f"Master Grid must expose 6 columns after settings change; "
        f"got {grid['periods']}"
    )

    period_times = grid.get("period_times") or {}
    first_slot = period_times.get("1") or period_times.get(1)
    assert first_slot, (
        f"Master Grid response must expose period_times for period 1; "
        f"got period_times={period_times}"
    )
    assert first_slot.get("start_time") == "08:00", (
        f"Period 1 must start at the configured dayStart (08:00); "
        f"got {first_slot.get('start_time')}"
    )
    # Period duration honoured (50min).
    assert first_slot.get("end_time") == "08:50", (
        f"Period 1 must end at start+periodDuration (08:50); "
        f"got {first_slot.get('end_time')}"
    )


# ---------------------------------------------------------------------------
# 7. AI engine matrix bounds — load_school_settings reflects whatever
#    periods_per_day is configured (no silent caps, no global default).
# ---------------------------------------------------------------------------

async def test_engine_matrix_bounds_track_settings_periods_per_day(tenant_a):
    """Two consecutive runs against the same school but with different
    periods_per_day must produce different teaching-period bounds in the
    engine's loaded settings — proving the AI matrix size is sourced
    strictly from Schedule Settings, never a hardcoded constant."""
    from engines.sql_utils import gd_delete_many, gd_update_one

    # Run A — 6 periods.
    await _mk_settings(tenant_a, periods_per_day=6)
    for n in range(1, 7):
        await _mk_time_slot(tenant_a, n)
    engine = SmartSchedulingEngine(db)
    loaded_a = await engine.load_school_settings(tenant_a)

    assert loaded_a["periods_per_day"] == 6, (
        f"Engine must reflect periods_per_day=6 from settings; "
        f"got {loaded_a['periods_per_day']}"
    )
    assert loaded_a["teaching_period_numbers"] == list(range(1, 7)), (
        f"Engine teaching periods must span 1..6 for a 6-period school; "
        f"got {loaded_a['teaching_period_numbers']}"
    )

    # Reconfigure school for 10 periods and re-load — the engine must
    # surface the new bound without restart and without leaking the prior
    # 6-period state.
    await gd_delete_many(db.session, "time_slots", {"school_id": tenant_a})
    await gd_update_one(db.session, "school_settings", {"school_id": tenant_a},
                       {"periods_per_day": 10})
    for n in range(1, 11):
        await _mk_time_slot(tenant_a, n)

    loaded_b = await engine.load_school_settings(tenant_a)
    assert loaded_b["periods_per_day"] == 10, (
        f"Engine must reflect updated periods_per_day=10; "
        f"got {loaded_b['periods_per_day']}"
    )
    assert loaded_b["teaching_period_numbers"] == list(range(1, 11)), (
        f"Engine teaching periods must span 1..10 after settings change; "
        f"got {loaded_b['teaching_period_numbers']}"
    )

    # Sanity: the two runs must differ — proving the engine does not cache
    # a hardcoded matrix dimension across calls.
    assert loaded_a["periods_per_day"] != loaded_b["periods_per_day"], (
        "Engine matrix bounds did not change when periods_per_day changed"
    )


async def test_engine_raises_when_periods_per_day_missing(tenant_a):
    """If Schedule Settings has no periods_per_day and no time_slots,
    the engine MUST raise loudly (no silent default to 7)."""
    # The strict helper `_required_periods_per_day` is the single guard
    # that prevents the engine from silently assuming 7 periods. Test it
    # directly so the contract is locked in regardless of any per-column
    # ORM defaults that might mask the missing value at the DB layer.
    from engines.smart_scheduling_engine import _required_periods_per_day

    raised = 0
    for bad in ({}, {"periods_per_day": None}, {"periods_per_day": 0}, {"periods_per_day": "abc"}):
        try:
            _required_periods_per_day(bad)
        except ValueError as e:
            raised += 1
            assert "periods_per_day" in str(e), (
                f"Error must point at the missing setting; got {e}"
            )
    assert raised == 4, (
        "Strict helper must raise ValueError for every missing/invalid "
        "periods_per_day input — silent fallback to 7 would re-introduce "
        "the bug Task #132 forbids"
    )

    # And — critical — the engine itself must route through this helper
    # whenever there are no time_slots and no explicit periods_per_day in
    # the loaded settings dict, so generation cannot proceed silently.
    from engines.smart_scheduling_engine import SmartSchedulingEngine as _Eng
    engine = _Eng(db)
    try:
        await engine.load_school_settings(
            tenant_a,
            context_payload={"timing": {"school_settings": {"working_days": ["sunday"]}, "time_slots": []}},
        )
        raised_engine = False
    except ValueError as e:
        raised_engine = "periods_per_day" in str(e)
    assert raised_engine, (
        "Engine must raise via _required_periods_per_day when no time_slots "
        "and no periods_per_day are supplied via context_payload"
    )
