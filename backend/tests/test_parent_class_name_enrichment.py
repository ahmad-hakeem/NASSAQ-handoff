"""Unit tests for enrich_children_with_class_names (Task #1014).

Covers:
  A. Two children in different classes both get the live class name.
  B. A child whose students.class_name is stale gets the corrected value.
  C. A child whose class_id belongs to a different school_id (cross-tenant)
     does NOT have its class_name resolved (returns fallback/blank).
  D. A mismatch between a returned class row id and the queried set triggers
     a logged error and does not crash the endpoint.
"""
from __future__ import annotations

import uuid
import logging

import pytest
import pytest_asyncio

from dependencies import db as _db
from engines.sql_utils import gd_insert
from src.common.utils.parent_children_resolution import enrich_children_with_class_names


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    return str(uuid.uuid4())


async def _mk_school() -> str:
    sid = _uid()
    await gd_insert(_db.session, "schools", {
        "id": sid,
        "name": f"School-{sid[:6]}",
        "code": f"S{sid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    return sid


async def _mk_class(school_id: str, name: str) -> str:
    cid = _uid()
    await gd_insert(_db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "name": name,
        "is_active": True,
    })
    return cid


# ---------------------------------------------------------------------------
# A. Two children in different classes both get correct live class names
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_two_children_different_classes_enriched():
    school_id = await _mk_school()
    class_id_1 = await _mk_class(school_id, "الصف الأول أ")
    class_id_2 = await _mk_class(school_id, "الصف الثاني ب")

    children = [
        {"id": _uid(), "class_id": class_id_1, "class_name": "STALE-1", "school_id": school_id},
        {"id": _uid(), "class_id": class_id_2, "class_name": "STALE-2", "school_id": school_id},
    ]

    result = await enrich_children_with_class_names(children, _db.session, school_id)

    assert result[0]["class_name"] == "الصف الأول أ"
    assert result[1]["class_name"] == "الصف الثاني ب"


# ---------------------------------------------------------------------------
# B. Stale class_name on the student row is corrected by the live class row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stale_class_name_corrected():
    school_id = await _mk_school()
    class_id = await _mk_class(school_id, "الصف الثالث ج")

    children = [
        {
            "id": _uid(),
            "class_id": class_id,
            "class_name": "اسم قديم خاطئ",
            "school_id": school_id,
        }
    ]

    result = await enrich_children_with_class_names(children, _db.session, school_id)

    assert result[0]["class_name"] == "الصف الثالث ج", (
        "Expected stale class_name to be replaced with the live value from the classes table"
    )


# ---------------------------------------------------------------------------
# C. Cross-tenant class_id does NOT resolve — fallback kept, no data leak
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_tenant_class_id_not_resolved():
    school_a = await _mk_school()
    school_b = await _mk_school()
    foreign_class_id = await _mk_class(school_b, "فصل من مدرسة أخرى")

    original_class_name = "اسم احتياطي"
    children = [
        {
            "id": _uid(),
            "class_id": foreign_class_id,
            "class_name": original_class_name,
            "school_id": school_a,
        }
    ]

    # school_a is passed as the tenant scope — the foreign class belongs to school_b
    result = await enrich_children_with_class_names(children, _db.session, school_a)

    assert result[0]["class_name"] == original_class_name, (
        "Cross-tenant class should not have its name resolved; fallback must be kept"
    )


# ---------------------------------------------------------------------------
# D. A class row whose id is not in the queried set logs an error but does
#    not crash, and leaves the child's class_name unchanged (fail-safe).
#    We simulate this by monkeypatching gd_find to inject a rogue row.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unexpected_class_row_id_logged_and_skipped(caplog, monkeypatch):
    school_id = await _mk_school()
    real_class_id = await _mk_class(school_id, "الصف الحقيقي")
    rogue_id = _uid()

    original_class_name = "احتياطي"

    import engines.sql_utils as sql_utils

    _real_gd_find = sql_utils.gd_find

    async def _patched_gd_find(session, table, query, **kwargs):
        rows = await _real_gd_find(session, table, query, **kwargs)
        if table == "classes":
            rows = rows + [{"id": rogue_id, "name": "فصل مزيف", "school_id": school_id}]
        return rows

    monkeypatch.setattr(sql_utils, "gd_find", _patched_gd_find)

    import src.common.utils.parent_children_resolution as mod
    monkeypatch.setattr(mod, "gd_find", _patched_gd_find)

    children = [
        {
            "id": _uid(),
            "class_id": real_class_id,
            "class_name": original_class_name,
            "school_id": school_id,
        }
    ]

    with caplog.at_level(logging.ERROR, logger="nassaq.parent_children_resolution"):
        result = await mod.enrich_children_with_class_names(children, _db.session, school_id)

    assert any("unexpected" in r.message.lower() or "not in queried" in r.message.lower()
               for r in caplog.records), "Expected an error log for the rogue row"

    assert result[0]["class_name"] == "الصف الحقيقي", (
        "The real child's class_name must still be resolved correctly despite the rogue row"
    )


# ---------------------------------------------------------------------------
# E. Child with no class_id — class_name left unchanged, no crash
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_child_without_class_id_unchanged():
    school_id = await _mk_school()

    original_name = "بدون فصل"
    children = [
        {"id": _uid(), "class_id": None, "class_name": original_name, "school_id": school_id}
    ]

    result = await enrich_children_with_class_names(children, _db.session, school_id)

    assert result[0]["class_name"] == original_name
