"""Task #95 — teacher preferences and constraints feeding the smart scheduler.

These are pure-Python unit tests for the helper methods added on
``SmartSchedulingEngine``. They do not require the database or the routes
layer because the helpers operate on already-built ``ResourceAvailability``
objects and an in-memory teacher_grid.
"""

from engines.smart_scheduling_engine import (
    SmartSchedulingEngine,
    ResourceAvailability,
)


def _make_resource(**overrides):
    base = dict(
        teacher_id="t1",
        teacher_name="Teacher One",
        subject_ids=[],
        weekly_load=20,
        availability={"sunday": [1, 2, 3, 4, 5], "monday": [1, 2, 3, 4, 5]},
    )
    base.update(overrides)
    return ResourceAvailability(**base)


# --------------------------------------------------------------------------- #
# max_consecutive_periods                                                     #
# --------------------------------------------------------------------------- #

def test_max_consecutive_disabled_when_unset():
    r = _make_resource()
    grid = {"sunday": {p: set() for p in [1, 2, 3, 4, 5]}}
    grid["sunday"][1] = {"t1"}
    grid["sunday"][2] = {"t1"}
    # No cap → never reject.
    assert SmartSchedulingEngine._would_exceed_max_consecutive(
        r, grid, "sunday", 3, [1, 2, 3, 4, 5]
    ) is False


def test_max_consecutive_blocks_third_in_a_row():
    r = _make_resource(constraints={"max_consecutive_periods": 2})
    grid = {"sunday": {p: set() for p in [1, 2, 3, 4, 5]}}
    grid["sunday"][1] = {"t1"}
    grid["sunday"][2] = {"t1"}
    assert SmartSchedulingEngine._would_exceed_max_consecutive(
        r, grid, "sunday", 3, [1, 2, 3, 4, 5]
    ) is True


def test_max_consecutive_allows_break():
    r = _make_resource(constraints={"max_consecutive_periods": 2})
    grid = {"sunday": {p: set() for p in [1, 2, 3, 4, 5]}}
    grid["sunday"][1] = {"t1"}
    grid["sunday"][2] = {"t1"}
    # Period 4 is non-adjacent → only itself.
    assert SmartSchedulingEngine._would_exceed_max_consecutive(
        r, grid, "sunday", 4, [1, 2, 3, 4, 5]
    ) is False


def test_max_consecutive_counts_back_and_forward():
    r = _make_resource(constraints={"max_consecutive_periods": 2})
    grid = {"sunday": {p: set() for p in [1, 2, 3, 4, 5]}}
    grid["sunday"][1] = {"t1"}
    grid["sunday"][3] = {"t1"}
    # Inserting at 2 chains 1,2,3 → 3 in a row, exceeds cap of 2.
    assert SmartSchedulingEngine._would_exceed_max_consecutive(
        r, grid, "sunday", 2, [1, 2, 3, 4, 5]
    ) is True


def test_max_consecutive_invalid_value_disables_check():
    r = _make_resource(constraints={"max_consecutive_periods": "abc"})
    grid = {"sunday": {p: set() for p in [1, 2, 3, 4, 5]}}
    grid["sunday"][1] = {"t1"}
    grid["sunday"][2] = {"t1"}
    assert SmartSchedulingEngine._would_exceed_max_consecutive(
        r, grid, "sunday", 3, [1, 2, 3, 4, 5]
    ) is False


# --------------------------------------------------------------------------- #
# preference scoring                                                          #
# --------------------------------------------------------------------------- #

def test_preference_scoring_no_preferences_is_noop():
    r = _make_resource()
    assert SmartSchedulingEngine._apply_teacher_preference_scoring(
        50, r, "math", "sunday"
    ) == 50


def test_preference_scoring_boosts_preferred_day():
    r = _make_resource(preferences={"preferred_days": ["sunday", "monday"]})
    assert SmartSchedulingEngine._apply_teacher_preference_scoring(
        50, r, "math", "sunday"
    ) > 50
    assert SmartSchedulingEngine._apply_teacher_preference_scoring(
        50, r, "math", "tuesday"
    ) == 50


def test_preference_scoring_boosts_preferred_subject():
    r = _make_resource(preferences={"preferred_subjects": ["math"]})
    assert SmartSchedulingEngine._apply_teacher_preference_scoring(
        50, r, "math", "sunday"
    ) > 50
    assert SmartSchedulingEngine._apply_teacher_preference_scoring(
        50, r, "english", "sunday"
    ) == 50


def test_preference_scoring_stacks_day_and_subject():
    r = _make_resource(preferences={
        "preferred_days": ["sunday"],
        "preferred_subjects": ["math"],
    })
    day_only = SmartSchedulingEngine._apply_teacher_preference_scoring(
        50, r, "english", "sunday"
    )
    subject_only = SmartSchedulingEngine._apply_teacher_preference_scoring(
        50, r, "math", "monday"
    )
    both = SmartSchedulingEngine._apply_teacher_preference_scoring(
        50, r, "math", "sunday"
    )
    assert both > day_only
    assert both > subject_only
