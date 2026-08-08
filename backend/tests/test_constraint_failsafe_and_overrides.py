"""Task 907 — per-school hard-constraint overrides + engine fail-safe.

Covers the two behavioural guarantees added when canonical timetable
constraints were materialized into the DB:

1. ``_build_constraint_context`` enforces EVERY registered validator when not a
   single hard-constraint row carries a ``validation_key`` (empty/corrupt/
   unseeded collection) — it must never silently skip all hard rules.
2. When at least one row is validatable, only the active rows' validation keys
   are honored, so a school that disabled a ``can_disable`` rule keeps the rest.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from engines.smart_scheduling_engine import SmartSchedulingEngine
from engines.hard_constraints import VALIDATION_REGISTRY


def _mk_engine():
    db = MagicMock()
    db.session = MagicMock()
    return SmartSchedulingEngine(db)


def _build_ctx(hard_rows):
    engine = _mk_engine()
    return asyncio.run(
        engine._build_constraint_context(
            school_id="school-test",
            sessions=[],
            demands=[],
            time_slots=[],
            school_constraints_rows=[],
            hard_constraints_rows=hard_rows,
        )
    )


def test_failsafe_enforces_all_validators_when_no_rows():
    ctx = _build_ctx([])
    assert ctx.active_validation_keys == set(VALIDATION_REGISTRY.keys())


def test_failsafe_enforces_all_validators_when_rows_lack_validation_key():
    # Corrupt rows (e.g. category:"test", no validation_key) must still
    # trigger the fail-safe rather than disabling every hard rule.
    corrupt = [{"code": "HC-01"}, {"code": "HC-02", "validation_key": None}]
    ctx = _build_ctx(corrupt)
    assert ctx.active_validation_keys == set(VALIDATION_REGISTRY.keys())


def test_disabled_rule_is_not_enforced_when_others_present():
    # One real validatable row disabled, another active -> only the active
    # key is honored (no fail-safe, explicit choice respected).
    keys = list(VALIDATION_REGISTRY.keys())
    active_key, disabled_key = keys[0], keys[1]
    rows = [
        {"code": "HC-A", "validation_key": active_key, "is_active": True},
        {"code": "HC-B", "validation_key": disabled_key, "is_active": False},
    ]
    ctx = _build_ctx(rows)
    assert active_key in ctx.active_validation_keys
    assert disabled_key not in ctx.active_validation_keys


def test_active_defaults_true_when_is_active_missing():
    keys = list(VALIDATION_REGISTRY.keys())
    rows = [{"code": "HC-A", "validation_key": keys[0]}]
    ctx = _build_ctx(rows)
    assert keys[0] in ctx.active_validation_keys


# ---------------------------------------------------------------------------
# School-aware hard-constraint resolution (publish/generation parity).
# `_load_school_hard_constraints` merges the immutable system list with
# `school_hard_constraint_overrides`, honoring an override's is_active only for
# can_disable rules. This is the exact list `validate_before_publish` feeds the
# registry, so a principal-disabled rule for school A must NOT be enforced at
# publish for A, while school B (no override) is unaffected.
# ---------------------------------------------------------------------------
from unittest.mock import patch  # noqa: E402

_SYSTEM_HARD = [
    {"code": "HC-01", "is_system": True, "is_active": True, "can_disable": False,
     "validation_key": "teacher_clash"},
    {"code": "HC-10", "is_system": True, "is_active": True, "can_disable": True,
     "validation_key": "subject_spread"},
]


def _load_for(school_id, overrides_by_school):
    async def fake_gd_find(session, collection, query, **kw):
        if collection == "timetable_hard_constraints":
            return [dict(r) for r in _SYSTEM_HARD]
        if collection == "school_hard_constraint_overrides":
            return [dict(r) for r in overrides_by_school.get(query.get("school_id"), [])]
        return []

    with patch(
        "engines.smart_scheduling_engine.gd_find", new=fake_gd_find
    ):
        engine = _mk_engine()
        return asyncio.run(engine._load_school_hard_constraints(school_id))


def test_school_override_disables_can_disable_rule_only_for_that_school():
    overrides = {
        "school-A": [{"code": "HC-10", "is_active": False}],
        # school-B has no overrides
    }
    a = {r["code"]: r["is_active"] for r in _load_for("school-A", overrides)}
    b = {r["code"]: r["is_active"] for r in _load_for("school-B", overrides)}
    # School A's HC-10 is disabled; HC-01 (mandatory) stays on.
    assert a["HC-10"] is False
    assert a["HC-01"] is True
    # School B is unaffected — HC-10 stays enforced.
    assert b["HC-10"] is True
    assert b["HC-01"] is True


def test_stale_override_cannot_disable_mandatory_rule():
    # A stale/forged override row targeting a can_disable:false rule must be
    # ignored — mandatory blockers are never silenced.
    overrides = {"school-A": [{"code": "HC-01", "is_active": False}]}
    a = {r["code"]: r["is_active"] for r in _load_for("school-A", overrides)}
    assert a["HC-01"] is True


def test_disabled_can_disable_rule_excluded_from_active_validation_keys():
    # End-to-end with the context builder: a school that disabled HC-10 must
    # NOT have subject_spread in the active validator set (so publish won't
    # enforce it), while HC-01's teacher_clash remains active.
    merged = _load_for("school-A", {"school-A": [{"code": "HC-10", "is_active": False}]})
    ctx = _build_ctx(merged)
    assert "teacher_clash" in ctx.active_validation_keys
    assert "subject_spread" not in ctx.active_validation_keys
