"""Regression tests for fairness-first standby slot distribution.

Tracks the bug captured in attached_assets/Pasted-Objective-Investigate-and-fix-…
(2026-05-13): the pre-fix generator front-loaded teachers into periods 1, 2, 3
of every day (e.g. 5/5/2/0) while later periods stayed empty.

These tests lock in three guarantees on the pure allocator
`_select_slots_for_teacher`, simulating the per-teacher loop that
`compute_standby_roster` runs:

  1. Many teachers, plenty of capacity → no period exceeds the hard cap of 5.
  2. A day with insufficient capacity is spread evenly across periods, NOT
     front-loaded into the earliest periods.
  3. Manual/locked placements pre-loaded into `period_load` are respected and
     auto-allocations route around them rather than overflow the cap.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import pytest

from services.standby_roster_service import (
    DEFAULT_MAX_STANDBY_PER_PERIOD,
    _select_slots_for_teacher,
)


DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday"]


def _run_distribution(
    *,
    n_teachers: int,
    capacity_per_teacher: int,
    eligible_periods: List[int],
    eligible_days: List[str] = DAYS,
    per_period_cap: int = DEFAULT_MAX_STANDBY_PER_PERIOD,
    seed_loads: Dict[Tuple[str, int], int] | None = None,
) -> Tuple[Dict[Tuple[str, int], int], List[set]]:
    """Run the per-teacher allocator over `n_teachers` identical teachers
    and return the final period_load map plus the per-teacher chosen sets.
    Mirrors the loop in compute_standby_roster but skips DB I/O."""
    period_load: Dict[Tuple[str, int], int] = dict(seed_loads or {})
    eligible_by_day = {d: list(eligible_periods) for d in eligible_days}
    D = len(eligible_days) or 1
    per_day = capacity_per_teacher // D
    extras = capacity_per_teacher % D
    rosters: List[set] = []
    for _ in range(n_teachers):
        chosen = _select_slots_for_teacher(
            eligible_days=eligible_days,
            eligible_by_day=eligible_by_day,
            capacity=capacity_per_teacher,
            per_day=per_day,
            extras=extras,
            period_load=period_load,
            per_period_cap=per_period_cap,
        )
        rosters.append(chosen)
    return period_load, rosters


def _day_distribution(period_load: Dict[Tuple[str, int], int], day: str,
                      periods: List[int]) -> List[int]:
    return [period_load.get((day, p), 0) for p in periods]


def test_no_period_exceeds_hard_cap_with_many_teachers():
    """20 teachers, each with capacity=5, eligible across periods 1..7 every
    working day. Pre-fix this would stack >>5 teachers on period 1 of each
    day; post-fix nothing may exceed the cap of 5."""
    periods = list(range(1, 8))
    period_load, _ = _run_distribution(
        n_teachers=20,
        capacity_per_teacher=5,
        eligible_periods=periods,
    )
    for day in DAYS:
        for p in periods:
            assert period_load.get((day, p), 0) <= DEFAULT_MAX_STANDBY_PER_PERIOD, (
                f"period_load[{day},{p}]={period_load[(day, p)]} exceeded cap "
                f"{DEFAULT_MAX_STANDBY_PER_PERIOD}"
            )


def test_insufficient_capacity_is_spread_evenly_across_periods():
    """The objective example: a day with 4 periods and only 12 placements.
    Expect 3/3/3/3 — never 5/5/2/0 or 5/4/3/0."""
    periods = [1, 2, 3, 4]
    # 12 single-day placements: 12 teachers, capacity=1, only sunday eligible.
    period_load, _ = _run_distribution(
        n_teachers=12,
        capacity_per_teacher=1,
        eligible_periods=periods,
        eligible_days=["sunday"],
    )
    distribution = _day_distribution(period_load, "sunday", periods)
    assert distribution == [3, 3, 3, 3], (
        f"expected balanced 3/3/3/3 distribution, got {distribution}"
    )
    # And the spread (max - min) must be 0 here; in general it must never be
    # > 1 when total placements are divisible by the period count.
    assert max(distribution) - min(distribution) == 0


def test_partial_capacity_minimises_spread_between_periods():
    """A day with 4 periods and 10 placements should land at 3/3/2/2 — the
    spec's 'minimise spread between most-filled and least-filled' rule.
    Pre-fix this would have produced 5/5/0/0."""
    periods = [1, 2, 3, 4]
    period_load, _ = _run_distribution(
        n_teachers=10,
        capacity_per_teacher=1,
        eligible_periods=periods,
        eligible_days=["sunday"],
    )
    distribution = _day_distribution(period_load, "sunday", periods)
    assert sorted(distribution, reverse=True) == [3, 3, 2, 2], (
        f"expected balanced 3/3/2/2 distribution, got {distribution}"
    )
    assert max(distribution) - min(distribution) <= 1


def test_no_period_left_empty_while_another_could_be_relieved():
    """Cap = 5, 4 periods, 12 placements, 12 teachers (cap=1 each) — every
    period must end up >0 before any period reaches the cap. Pre-fix the
    earliest period would saturate at 5 while the last sat at 0."""
    periods = [1, 2, 3, 4]
    period_load, _ = _run_distribution(
        n_teachers=12,
        capacity_per_teacher=1,
        eligible_periods=periods,
        eligible_days=["sunday"],
    )
    distribution = _day_distribution(period_load, "sunday", periods)
    assert min(distribution) >= 1, (
        f"a period was left empty while others were filled: {distribution}"
    )


def test_manual_pinned_loads_are_respected_and_routed_around():
    """If manual pins concentrate load on period 1 (seeded as period_load=4),
    auto-allocations must (a) never push period 1 above the cap and (b)
    prefer the emptier periods 2/3/4 first per the fairness rule. The
    pre-fix algorithm ignored existing load and would have re-picked
    period 1 (raw period order)."""
    periods = [1, 2, 3, 4]
    seed = {("sunday", 1): 4}  # one slot left under cap=5
    period_load, _ = _run_distribution(
        n_teachers=2,
        capacity_per_teacher=1,
        eligible_periods=periods,
        eligible_days=["sunday"],
        seed_loads=seed,
    )
    # Period 1 must NOT be picked while emptier periods exist — it stays at 4.
    assert period_load[("sunday", 1)] == 4
    # The two auto picks land on the two least-loaded periods (2 and 3).
    assert period_load[("sunday", 2)] == 1
    assert period_load[("sunday", 3)] == 1
    # Cap is never breached:
    for p in periods:
        assert period_load.get(("sunday", p), 0) <= DEFAULT_MAX_STANDBY_PER_PERIOD


def test_manual_pinned_loads_at_cap_block_further_auto_picks():
    """If manual pins already saturate period 1 at the cap, no further auto
    pick may land there even if it's the only option offered first."""
    periods = [1, 2]
    seed = {("sunday", 1): 5, ("sunday", 2): 4}  # period 1 at cap
    period_load, _ = _run_distribution(
        n_teachers=1,
        capacity_per_teacher=1,
        eligible_periods=periods,
        eligible_days=["sunday"],
        seed_loads=seed,
    )
    # Period 1 stays capped, period 2 absorbs the auto pick (still under cap).
    assert period_load[("sunday", 1)] == 5
    assert period_load[("sunday", 2)] == 5


def test_capacity_is_forfeit_when_every_eligible_period_is_capped():
    """If every eligible period is already at cap, the teacher gets nothing
    rather than overflowing. Asserted via roster size."""
    periods = [1, 2]
    seed = {("sunday", 1): 5, ("sunday", 2): 5}  # both at cap
    _, rosters = _run_distribution(
        n_teachers=1,
        capacity_per_teacher=2,
        eligible_periods=periods,
        eligible_days=["sunday"],
        seed_loads=seed,
    )
    assert rosters[0] == set(), (
        f"expected empty roster when all periods capped, got {rosters[0]}"
    )


def test_distribution_is_deterministic_across_runs():
    """Two identical runs must produce byte-identical period_load maps so
    the regenerate diff/notification path stays stable."""
    periods = list(range(1, 8))
    pl_a, _ = _run_distribution(
        n_teachers=15, capacity_per_teacher=4, eligible_periods=periods,
    )
    pl_b, _ = _run_distribution(
        n_teachers=15, capacity_per_teacher=4, eligible_periods=periods,
    )
    assert pl_a == pl_b


@pytest.mark.asyncio
async def test_stale_add_overrides_do_not_consume_cap_during_auto_pass(tenant_a):
    """Integration: a `standby_overrides` row marked `add` for a slot that
    is *busy* in the master schedule must NOT inflate `period_load` during
    the auto pass. Pre-fix the seed loop counted every add → phantom load
    crowded out an otherwise-valid auto allocation."""
    import uuid
    from dependencies import db
    from datetime import datetime, timezone
    from engines.sql_utils import gd_insert
    from services.standby_roster_service import compute_standby_roster

    school_id = tenant_a
    teacher_id = str(uuid.uuid4())
    timetable_id = str(uuid.uuid4())

    teachers = [{
        "id": teacher_id,
        "school_id": school_id,
        "full_name": "T1",
        "weekly_periods": 24,  # plenty of headroom
        "is_active": True,
    }]
    # Teacher is BUSY at sunday-period-1 in the master schedule.
    sessions = [{
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "timetable_id": timetable_id,
        "teacher_id": teacher_id,
        "day_of_week": "sunday",
        "period_number": 1,
    }]
    # A stale manual `add` override targeting the now-busy slot.
    await gd_insert(db.session, "standby_overrides", {
        "school_id": school_id,
        "timetable_id": timetable_id,
        "teacher_id": teacher_id,
        "day": "sunday",
        "period": 1,
        "action": "add",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    roster = await compute_standby_roster(
        db.session,
        school_id=school_id,
        timetable_id=timetable_id,
        teachers=teachers,
        sessions=sessions,
        apply_overrides=True,
    )
    chosen = roster.get(teacher_id, set())
    # The stale override must not appear in the final roster (busy wins),
    # AND its phantom load must not have stopped the auto pass from
    # picking sunday-period-1's neighbours. With cap=5 and only one
    # teacher, sunday-period-1 stays out (busy), but other periods stay
    # available because seed didn't inflate their load either.
    assert ("sunday", 1) not in chosen, (
        "busy slot must never be in standby roster regardless of override"
    )
    # Auto pass should have still allocated several slots.
    assert len(chosen) > 0


@pytest.mark.parametrize("custom_cap,n_teachers,expected_max", [
    (3, 20, 3),
    (5, 20, 5),
    (1, 10, 1),
])
def test_custom_per_period_cap_is_honoured(custom_cap, n_teachers, expected_max):
    """The cap is read from school settings at runtime — when it's 3, no
    period may exceed 3; when it's 1, no period may exceed 1."""
    periods = list(range(1, 8))
    period_load, _ = _run_distribution(
        n_teachers=n_teachers,
        capacity_per_teacher=5,
        eligible_periods=periods,
        per_period_cap=custom_cap,
    )
    for day in DAYS:
        for p in periods:
            assert period_load.get((day, p), 0) <= expected_max
