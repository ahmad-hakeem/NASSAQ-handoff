"""Task 1 — HardConstraintRegistry skeleton + tier-split tests."""

from dataclasses import replace

import pytest

from backend.engines.hard_constraints import (
    VALIDATION_REGISTRY,
    validate_full,
    validate_placement,
)
from backend.engines.hard_constraints.types import (
    ConstraintContext,
    ConstraintViolation,
    ValidatorMeta,
)
from backend.engines.smart_scheduling_engine import ConflictSeverity
from backend.seeds.timetable_hard_constraints import TIMETABLE_HARD_CONSTRAINTS as HARD_CONSTRAINTS


def _empty_ctx(active_keys=None):
    return ConstraintContext(
        school_id="school-test",
        sessions=[],
        demands=[],
        resources={},
        time_slots=[],
        settings={},
        active_validation_keys=set(active_keys) if active_keys is not None else set(VALIDATION_REGISTRY.keys()),
    )


def test_every_seeded_validation_key_has_registry_entry():
    seed_keys = {row["validation_key"] for row in HARD_CONSTRAINTS}
    assert seed_keys.issubset(set(VALIDATION_REGISTRY.keys()))


def test_no_orphan_validators():
    seed_keys = {row["validation_key"] for row in HARD_CONSTRAINTS}
    # School-level validators (e.g. school_period_bans) live in the registry
    # but are NOT seeded in timetable_hard_constraints — they are opted-in
    # per-school via school_constraints rows (Task 6).
    registry_keys = {
        k for k in VALIDATION_REGISTRY.keys() if not k.startswith("school_")
    }
    assert registry_keys.issubset(seed_keys)


def test_validate_placement_returns_list():
    result = validate_placement(_empty_ctx(active_keys=set()), candidate=None)
    assert result == []


def test_validate_full_collects_violations_from_all_active_validators(monkeypatch):
    calls = []

    def make_stub(key, code):
        def _fn(ctx):
            calls.append(key)
            return [ConstraintViolation(
                code=code,
                validation_key=key,
                severity=ConflictSeverity.HIGH,
                message_en=f"stub {key}",
                message_ar=f"stub {key}",
                refs={},
                tier="full",
            )]
        return _fn

    key_a = "teacher_weekly_load"
    key_b = "subject_weekly_periods"

    stub_registry = dict(VALIDATION_REGISTRY)
    stub_registry[key_a] = replace(stub_registry[key_a], fn=make_stub(key_a, "HC-08"), tier="full")
    stub_registry[key_b] = replace(stub_registry[key_b], fn=make_stub(key_b, "HC-09"), tier="full")

    monkeypatch.setattr(
        "backend.engines.hard_constraints.VALIDATION_REGISTRY",
        stub_registry,
    )

    ctx = _empty_ctx(active_keys={key_a, key_b})
    violations = validate_full(ctx)

    keys = {v.validation_key for v in violations}
    assert key_a in keys
    assert key_b in keys
    assert set(calls) == {key_a, key_b}


def test_inactive_constraint_is_not_dispatched(monkeypatch):
    calls = []

    def stub_a(ctx):
        calls.append("a")
        return [ConstraintViolation(
            code="HC-08", validation_key="teacher_weekly_load",
            severity=ConflictSeverity.HIGH, message_en="x", message_ar="x",
            refs={}, tier="full",
        )]

    def stub_b(ctx):
        calls.append("b")
        return [ConstraintViolation(
            code="HC-09", validation_key="subject_weekly_periods",
            severity=ConflictSeverity.HIGH, message_en="x", message_ar="x",
            refs={}, tier="full",
        )]

    stub_registry = dict(VALIDATION_REGISTRY)
    stub_registry["teacher_weekly_load"] = replace(
        stub_registry["teacher_weekly_load"], fn=stub_a, tier="full"
    )
    stub_registry["subject_weekly_periods"] = replace(
        stub_registry["subject_weekly_periods"], fn=stub_b, tier="full"
    )

    monkeypatch.setattr(
        "backend.engines.hard_constraints.VALIDATION_REGISTRY",
        stub_registry,
    )

    ctx = _empty_ctx(active_keys={"teacher_weekly_load"})
    violations = validate_full(ctx)

    assert calls == ["a"]
    assert len(violations) == 1
    assert violations[0].validation_key == "teacher_weekly_load"
