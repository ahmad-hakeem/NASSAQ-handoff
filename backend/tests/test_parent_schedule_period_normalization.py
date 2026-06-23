"""Unit tests for the parent schedule canonical period model.

These cover the pure builder ``_build_parent_period_model`` which powers the
Parent Portal timetable grid: it must resolve ONE canonical period list and
place each session on its TRUE teaching-period row regardless of whether the
timetable stored raw slot numbers (manual) or contiguous indexes (generator).
"""

from routes.parent_portal_routes import _build_parent_period_model


def _slots(*pairs):
    """Build teaching-slot dicts (breaks already excluded) from (slot_number,
    start, end) tuples."""
    return [
        {"slot_number": sn, "start_time": st, "end_time": et}
        for sn, st, et in pairs
    ]


def test_raw_gapped_slots_map_to_contiguous_index():
    """Dominant real-school shape: breaks occupy slots 4 and 8, so teaching
    slots are 1,2,3,5,6,7,9. Sessions store the RAW slot number → period 5
    maps to teaching index 4 and period 9 maps to index 7."""
    teaching = _slots(
        (1, "07:00", "07:45"),
        (2, "07:45", "08:30"),
        (3, "08:30", "09:15"),
        (5, "09:35", "10:20"),
        (6, "10:20", "11:05"),
        (7, "11:05", "11:50"),
        (9, "12:10", "12:55"),
    )
    session_periods = [1, 2, 3, 5, 6, 7, 9, 9, 5]  # raw-slot evidence (5, 9)
    periods, mapper = _build_parent_period_model(teaching, None, session_periods)

    assert [p["period"] for p in periods] == [1, 2, 3, 4, 5, 6, 7]
    assert mapper(1) == 1
    assert mapper(3) == 3
    assert mapper(5) == 4
    assert mapper(9) == 7
    # Period 4 is a break slot → not a teaching period → clamped out.
    assert mapper(4) is None
    # Orphans beyond the last teaching slot → clamped out (no phantom rows).
    assert mapper(10) is None
    assert mapper(11) is None
    assert mapper(12) is None


def test_break_slot_times_are_carried_on_periods():
    teaching = _slots(
        (1, "07:00", "07:45"),
        (2, "07:45", "08:30"),
        (5, "09:35", "10:20"),
    )
    periods, _ = _build_parent_period_model(teaching, None, [1, 2, 5])
    assert periods[2] == {
        "period": 3,
        "label": "3",
        "start_time": "09:35",
        "end_time": "10:20",
    }


def test_contiguous_slots_unchanged():
    """No break gaps: slot numbers already are 1..N, so the mapping is identity
    and orphans beyond N are clamped."""
    teaching = _slots(
        (1, "07:00", "07:45"),
        (2, "07:45", "08:30"),
        (3, "08:30", "09:15"),
        (4, "09:15", "10:00"),
        (5, "10:00", "10:45"),
    )
    periods, mapper = _build_parent_period_model(teaching, None, [1, 2, 3, 4, 5])
    assert [p["period"] for p in periods] == [1, 2, 3, 4, 5]
    for i in range(1, 6):
        assert mapper(i) == i
    assert mapper(6) is None
    assert mapper(0) is None


def test_gapped_slots_with_contiguous_session_data_uses_contiguous_encoding():
    """Generator timetable can have gapped slot rows but store CONTIGUOUS
    period_number. When the session data only matches the contiguous set, the
    contiguous encoding wins."""
    teaching = _slots(
        (1, "07:00", "07:45"),
        (2, "07:45", "08:30"),
        (3, "08:30", "09:15"),
        (5, "09:35", "10:20"),
        (6, "10:20", "11:05"),
    )  # N = 5, raw set {1,2,3,5,6}
    # Sessions use 4 (contiguous-only) and never 5/6-only beyond N → contiguous.
    session_periods = [1, 2, 3, 4, 4, 1, 2]
    _, mapper = _build_parent_period_model(teaching, None, session_periods)
    assert mapper(4) == 4
    assert mapper(5) == 5
    assert mapper(6) is None  # beyond N=5


def test_sparse_generator_gapped_slots_no_period_evidence_uses_times():
    """Sparse generator class on gapped slots {1,2,3,5,6,7,9}: every session
    period falls in the set shared by both encodings (no 4/8 contiguous-only
    and no 9 raw-only evidence), so the value counts tie. Sessions carry slot
    times → contiguous encoding wins and each session keeps its TRUE row
    (5→5, 6→6, 7→7) with row 4 left empty — none are dropped."""
    teaching = _slots(
        (1, "07:00", "07:45"),
        (2, "07:45", "08:30"),
        (3, "08:30", "09:15"),
        (5, "09:35", "10:20"),
        (6, "10:20", "11:05"),
        (7, "11:05", "11:50"),
        (9, "12:10", "12:55"),
    )  # N = 7
    session_periods = [1, 2, 3, 5, 6, 7]  # all in raw ∩ contiguous → tie
    periods, mapper = _build_parent_period_model(
        teaching, None, session_periods, sessions_have_times=True
    )
    assert [p["period"] for p in periods] == [1, 2, 3, 4, 5, 6, 7]
    assert mapper(5) == 5
    assert mapper(6) == 6
    assert mapper(7) == 7
    assert all(mapper(p) is not None for p in session_periods)  # none dropped


def test_sparse_manual_gapped_slots_no_period_evidence_no_times():
    """Same ambiguous sparse data, but manual timetable (no slot times) →
    raw-slot encoding: 5→4, 6→5, 7→6."""
    teaching = _slots(
        (1, "07:00", "07:45"),
        (2, "07:45", "08:30"),
        (3, "08:30", "09:15"),
        (5, "09:35", "10:20"),
        (6, "10:20", "11:05"),
        (7, "11:05", "11:50"),
        (9, "12:10", "12:55"),
    )
    session_periods = [1, 2, 3, 5, 6, 7]
    _, mapper = _build_parent_period_model(
        teaching, None, session_periods, sessions_have_times=False
    )
    assert mapper(5) == 4
    assert mapper(6) == 5
    assert mapper(7) == 6
    assert all(mapper(p) is not None for p in session_periods)  # none dropped


def test_raw_only_evidence_overrides_times():
    """Hard period-value evidence beats the structural signal: a period 9
    (raw-only, > N) proves raw encoding even if sessions happen to carry
    times."""
    teaching = _slots(
        (1, "07:00", "07:45"),
        (2, "07:45", "08:30"),
        (3, "08:30", "09:15"),
        (5, "09:35", "10:20"),
        (6, "10:20", "11:05"),
        (7, "11:05", "11:50"),
        (9, "12:10", "12:55"),
    )
    session_periods = [1, 2, 3, 5, 6, 7, 9]  # 9 is raw-only evidence
    _, mapper = _build_parent_period_model(
        teaching, None, session_periods, sessions_have_times=True
    )
    assert mapper(5) == 4
    assert mapper(9) == 7


def test_null_and_non_int_periods_excluded():
    teaching = _slots((1, "07:00", "07:45"), (2, "07:45", "08:30"))
    _, mapper = _build_parent_period_model(teaching, None, [1, 2])
    assert mapper(None) is None
    assert mapper("x") is None


def test_settings_fallback_when_no_time_slots():
    periods, mapper = _build_parent_period_model([], 6, [1, 2, 3, 7])
    assert [p["period"] for p in periods] == [1, 2, 3, 4, 5, 6]
    assert all(p["start_time"] == "" for p in periods)
    assert mapper(1) == 1
    assert mapper(6) == 6
    assert mapper(7) is None  # beyond periods_per_day → clamped


def test_distinct_fallback_when_no_config_preserves_all_sessions():
    """No time_slots and no settings: re-index distinct session periods so no
    session is dropped and no phantom rows appear."""
    periods, mapper = _build_parent_period_model([], None, [9, 1, 5, 5, 3])
    assert [p["period"] for p in periods] == [1, 2, 3, 4]
    # distinct sorted = [1,3,5,9] → mapped to 1,2,3,4
    assert mapper(1) == 1
    assert mapper(3) == 2
    assert mapper(5) == 3
    assert mapper(9) == 4
    assert mapper(2) is None


def test_empty_everything_returns_empty_model():
    periods, mapper = _build_parent_period_model([], None, [])
    assert periods == []
    assert mapper(1) is None
