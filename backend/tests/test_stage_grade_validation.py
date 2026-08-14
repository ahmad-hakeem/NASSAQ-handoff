"""
Regression tests for the canonical stage/grade hierarchy validator.

Covers:
  * normalize_stage accepts English ids, Arabic names, and grade numbers.
  * validate_stage_grade_pair rejects mismatched pairs with HTTP 422.
  * Foreign-tenant grade ids resolve to 404 (never a silent pass).
  * Legacy grade rows without a derivable stage are permissive.
  * Numeric grade ids without a backing row map to the right stage.
"""

import sys
import types
import pathlib
import pytest
from fastapi import HTTPException


# Resolve `backend/` into sys.path the same way the rest of the suite does.
_BACKEND = pathlib.Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


from src.common.utils.stage_grade import (  # noqa: E402
    normalize_stage,
    validate_stage_grade_pair,
)


class _StubSession:
    """Minimal stand-in for an AsyncSession; gd_find_one is mocked separately."""


@pytest.fixture
def patched_lookup(monkeypatch):
    """Replace gd_find_one with a controllable in-memory map."""
    rows: dict = {}

    async def _fake(session, table, query):
        if table != "grade_levels":
            return None
        gid = query.get("id")
        sid = query.get("school_id")
        row = rows.get((sid, gid))
        return dict(row) if row else None

    import src.common.utils.stage_grade as mod
    monkeypatch.setattr(mod, "gd_find_one", _fake)
    return rows


# ---------- normalize_stage ----------

@pytest.mark.parametrize("value,expected", [
    ("primary", "primary"),
    ("Middle", "middle"),
    ("HIGH", "high"),
    ("ابتدائي", "primary"),
    ("المرحلة المتوسطة", "middle"),
    ("ثانوي", "high"),
    (3, "primary"),
    ("8", "middle"),
    (11, "high"),
    (None, None),
    ("", None),
    ("kindergarten", None),
])
def test_normalize_stage_buckets(value, expected):
    assert normalize_stage(value) == expected


def test_normalize_stage_from_grade_row_dict():
    assert normalize_stage({"stage": "ابتدائي"}) == "primary"
    assert normalize_stage({"stage": None, "grade": 8}) == "middle"
    assert normalize_stage({"order": 11}) == "high"
    assert normalize_stage({}) is None


# ---------- validate_stage_grade_pair ----------

@pytest.mark.asyncio
async def test_pair_accepts_matching_stage_and_grade(patched_lookup):
    patched_lookup[("school-A", "g3")] = {"id": "g3", "school_id": "school-A", "stage": "ابتدائي", "grade": 3}
    await validate_stage_grade_pair(_StubSession(), "school-A", "primary", "g3")


@pytest.mark.asyncio
async def test_pair_rejects_stage_grade_mismatch(patched_lookup):
    patched_lookup[("school-A", "g8")] = {"id": "g8", "school_id": "school-A", "stage": "متوسط", "grade": 8}
    with pytest.raises(HTTPException) as exc:
        await validate_stage_grade_pair(_StubSession(), "school-A", "primary", "g8")
    assert exc.value.status_code == 422
    # Safe Arabic message — never a raw exception string.
    assert "الصف" in exc.value.detail


@pytest.mark.asyncio
async def test_pair_blocks_foreign_tenant_grade(patched_lookup):
    # Grade row exists but in another tenant; lookup scoped to school-A
    # must NOT find it, so we 404 instead of silently accepting.
    patched_lookup[("school-B", "g3")] = {"id": "g3", "school_id": "school-B", "stage": "ابتدائي", "grade": 3}
    with pytest.raises(HTTPException) as exc:
        await validate_stage_grade_pair(_StubSession(), "school-A", "primary", "g3")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_pair_permissive_when_row_has_no_stage(patched_lookup):
    # Legacy row pre-dating the stage column being populated → don't block.
    patched_lookup[("school-A", "leg")] = {"id": "leg", "school_id": "school-A", "stage": None, "grade": None}
    await validate_stage_grade_pair(_StubSession(), "school-A", "primary", "leg")


@pytest.mark.asyncio
async def test_pair_accepts_numeric_grade_id_without_row(patched_lookup):
    # Older callers send the raw grade number as the id.
    await validate_stage_grade_pair(_StubSession(), "school-A", "middle", "8")
    with pytest.raises(HTTPException) as exc:
        await validate_stage_grade_pair(_StubSession(), "school-A", "primary", "8")
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_pair_require_stage_flag(patched_lookup):
    patched_lookup[("school-A", "g3")] = {"id": "g3", "school_id": "school-A", "stage": "ابتدائي", "grade": 3}
    with pytest.raises(HTTPException) as exc:
        await validate_stage_grade_pair(_StubSession(), "school-A", None, "g3", require_stage=True)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_pair_skips_when_grade_id_empty(patched_lookup):
    # Other validators handle "grade required"; this helper returns silently.
    await validate_stage_grade_pair(_StubSession(), "school-A", "primary", None)
    await validate_stage_grade_pair(_StubSession(), "school-A", "primary", "")
