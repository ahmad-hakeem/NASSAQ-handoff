"""Regression tests for the open-ended class roster policy."""

import pytest

from engines.entity_counts import (
    class_has_room,
    enforce_class_capacity,
    resolve_class_capacity,
)


@pytest.mark.parametrize(
    "class_doc",
    [
        {"id": "legacy-full", "capacity": 1},
        {"id": "legacy-large", "capacity": 50},
        {"id": "legacy-null", "capacity": None},
        {"id": "legacy-invalid", "capacity": "not-a-number"},
        None,
    ],
)
def test_resolve_class_capacity_is_always_unlimited(class_doc):
    assert resolve_class_capacity(class_doc) is None


@pytest.mark.asyncio
async def test_class_has_room_is_true_without_counting():
    class ExplodingSession:
        async def execute(self, *_args, **_kwargs):
            raise AssertionError("open-ended capacity must not query occupancy")

    assert await class_has_room(
        ExplodingSession(),
        {"id": "class-1", "capacity": 1},
        "school-1",
        additional=10_000,
    )


@pytest.mark.asyncio
async def test_enforce_class_capacity_is_noop_without_counting():
    class ExplodingSession:
        async def execute(self, *_args, **_kwargs):
            raise AssertionError("open-ended capacity must not query occupancy")

    await enforce_class_capacity(
        ExplodingSession(),
        {"id": "class-1", "capacity": 1},
        "school-1",
        additional=10_000,
    )
