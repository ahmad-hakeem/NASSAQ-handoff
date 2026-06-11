"""Tests for POST /noor-import/draft/{id}/map-existing-classes.

Covers Option B (bulk pair→existing-class mapping):
  • A distinct unmatched (grade, section) pair can be mapped to an
    EXISTING class of the school, even when the raw Noor code (e.g.
    "0125") can't normalise to a 1..12 grade.
  • The mapping is honoured at /commit (which re-resolves class_id
    from the live index and would otherwise drop a row-baked id).
  • Foreign / unknown / inactive class ids are hard-rejected (400).
  • Clearing a mapping returns the pair to "unclassified".
  • Cross-tenant draft → 403; teacher draft → 400.
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from dependencies import db, UserRole
from engines.noor_import.draft_store import create_draft
from tests.conftest import _mk_user, _headers, _mk_school

pytestmark = pytest.mark.asyncio


def _row(idx, num, name, grade, section):
    return {
        "row_index": idx,
        "data": {
            "student_number": num,
            "full_name": name,
            "grade_code": grade,
            "section_code": section,
        },
        "issues": [],
        "dedupe": "insert",
        "existing_id": None,
        "class_id": None,
        "class_unresolved": True,
        "student_number_generated": False,
    }


async def _seed_principal():
    school_id = str(uuid.uuid4())
    await _mk_school(school_id)
    user = await _mk_user(UserRole.SCHOOL_PRINCIPAL, school_id)
    return user, school_id


async def _seed_class(school_id, grade, section, *, is_active=True):
    cid = str(uuid.uuid4())
    await db.session.execute(
        text(
            """
            INSERT INTO classes (id, name, school_id, grade_level, section,
                                 capacity, current_students, is_active,
                                 created_at, updated_at)
            VALUES (:id, :n, :sid, :g, :s, 30, 0, :act, :now, :now)
            """
        ),
        {
            "id": cid, "n": f"{grade}-{section}", "sid": school_id,
            "g": grade, "s": section, "act": is_active,
            "now": datetime.now(timezone.utc),
        },
    )
    return cid


async def _seed_student_draft(principal_id, school_id, rows):
    counts = {
        "total": len(rows),
        "insert": len(rows),
        "update": 0,
        "skip": 0,
        "ambiguous": 0,
        "duplicate_in_file": 0,
        "unclassified": sum(1 for r in rows if r.get("class_unresolved")),
    }
    return await create_draft(
        db.session,
        principal_id=principal_id,
        school_id=school_id,
        detected_type="students",
        header_row=1,
        sheet_name="Sheet1",
        mapped_columns={},
        rows=rows,
        counts=counts,
    )


async def test_maps_unmatchable_pair_to_existing_class(client, _db_session):
    """The real-world failing case: `رقم الصف` = "0125" never normalises
    to a 1..12 grade, but the principal can still bind it to an existing
    class by explicit choice."""
    user, school_id = await _seed_principal()
    # Existing class deliberately on a DIFFERENT grade/section — the
    # mapping is an explicit override, not a normalised match.
    cid = await _seed_class(school_id, "3", "2")
    rows = [
        _row(1, "S1", "طالب أ", "0125", "1"),
        _row(2, "S2", "طالب ب", "0125", "1"),
    ]
    draft_id = await _seed_student_draft(user["id"], school_id, rows)
    await db.session.commit()

    r = await client.post(
        f"/noor-import/draft/{draft_id}/map-existing-classes",
        headers=_headers(user),
        json={"mappings": [
            {"grade_code": "0125", "section_code": "1", "class_id": cid},
        ]},
    )
    await db.session.commit()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["counts"]["unclassified"] == 0
    for row in body["rows"]:
        assert row["class_unresolved"] is False
        assert row["class_id"] == cid


async def test_mapped_pair_survives_commit(client, _db_session):
    user, school_id = await _seed_principal()
    cid = await _seed_class(school_id, "1", "1")
    rows = [_row(1, "S1", "طالب أ", "0125", "1")]
    draft_id = await _seed_student_draft(user["id"], school_id, rows)
    await db.session.commit()

    r = await client.post(
        f"/noor-import/draft/{draft_id}/map-existing-classes",
        headers=_headers(user),
        json={"mappings": [
            {"grade_code": "0125", "section_code": "1", "class_id": cid},
        ]},
    )
    await db.session.commit()
    assert r.status_code == 200, r.text

    rc = await client.post(
        "/noor-import/commit",
        json={"import_draft_id": draft_id},
        headers=_headers(user),
    )
    await db.session.commit()
    assert rc.status_code == 200, rc.text
    body = rc.json()
    assert body["failed"] == 0
    assert body["unclassified"] == 0
    # The persisted student carries the mapped class_id.
    db_cid = (await db.session.execute(
        text("SELECT class_id FROM students WHERE school_id = :sid AND student_number = 'S1'"),
        {"sid": school_id},
    )).scalar()
    assert str(db_cid) == cid


async def test_rejects_cross_tenant_class_id(client, _db_session):
    user_a, school_a = await _seed_principal()
    _user_b, school_b = await _seed_principal()
    cid_b = await _seed_class(school_b, "1", "1")
    rows = [_row(1, "S1", "طالب", "0125", "1")]
    draft_id = await _seed_student_draft(user_a["id"], school_a, rows)
    await db.session.commit()

    r = await client.post(
        f"/noor-import/draft/{draft_id}/map-existing-classes",
        headers=_headers(user_a),
        json={"mappings": [
            {"grade_code": "0125", "section_code": "1", "class_id": cid_b},
        ]},
    )
    assert r.status_code == 400
    # Draft untouched — pair is still unclassified.
    counts = (await db.session.execute(
        text("SELECT counts FROM noor_import_drafts WHERE id = :id"),
        {"id": draft_id},
    )).scalar()
    assert counts["unclassified"] == 1


async def test_rejects_unknown_class_id(client, _db_session):
    user, school_id = await _seed_principal()
    rows = [_row(1, "S1", "طالب", "0125", "1")]
    draft_id = await _seed_student_draft(user["id"], school_id, rows)
    await db.session.commit()

    r = await client.post(
        f"/noor-import/draft/{draft_id}/map-existing-classes",
        headers=_headers(user),
        json={"mappings": [
            {"grade_code": "0125", "section_code": "1", "class_id": str(uuid.uuid4())},
        ]},
    )
    assert r.status_code == 400


async def test_rejects_inactive_class(client, _db_session):
    user, school_id = await _seed_principal()
    cid = await _seed_class(school_id, "1", "1", is_active=False)
    rows = [_row(1, "S1", "طالب", "0125", "1")]
    draft_id = await _seed_student_draft(user["id"], school_id, rows)
    await db.session.commit()

    r = await client.post(
        f"/noor-import/draft/{draft_id}/map-existing-classes",
        headers=_headers(user),
        json={"mappings": [
            {"grade_code": "0125", "section_code": "1", "class_id": cid},
        ]},
    )
    assert r.status_code == 400


async def test_clearing_mapping_returns_pair_to_unclassified(client, _db_session):
    user, school_id = await _seed_principal()
    cid = await _seed_class(school_id, "1", "1")
    rows = [_row(1, "S1", "طالب", "0125", "1")]
    draft_id = await _seed_student_draft(user["id"], school_id, rows)
    await db.session.commit()

    # Map first.
    r1 = await client.post(
        f"/noor-import/draft/{draft_id}/map-existing-classes",
        headers=_headers(user),
        json={"mappings": [
            {"grade_code": "0125", "section_code": "1", "class_id": cid},
        ]},
    )
    await db.session.commit()
    assert r1.status_code == 200
    assert r1.json()["counts"]["unclassified"] == 0

    # Clear it (empty class_id).
    r2 = await client.post(
        f"/noor-import/draft/{draft_id}/map-existing-classes",
        headers=_headers(user),
        json={"mappings": [
            {"grade_code": "0125", "section_code": "1", "class_id": ""},
        ]},
    )
    await db.session.commit()
    assert r2.status_code == 200
    body = r2.json()
    assert body["counts"]["unclassified"] == 1
    assert body["rows"][0]["class_unresolved"] is True
    assert body["rows"][0]["class_id"] is None


async def test_cross_tenant_draft_returns_403(client, _db_session):
    user_a, school_a = await _seed_principal()
    user_b, _school_b = await _seed_principal()
    rows = [_row(1, "S1", "x", "0125", "1")]
    draft_id = await _seed_student_draft(user_a["id"], school_a, rows)
    await db.session.commit()

    r = await client.post(
        f"/noor-import/draft/{draft_id}/map-existing-classes",
        headers=_headers(user_b),
        json={"mappings": []},
    )
    assert r.status_code == 403


async def test_teacher_draft_rejected(client, _db_session):
    user, school_id = await _seed_principal()
    draft_id = await create_draft(
        db.session,
        principal_id=user["id"],
        school_id=school_id,
        detected_type="teachers",
        header_row=1,
        sheet_name="Sheet1",
        mapped_columns={},
        rows=[],
        counts={"total": 0},
    )
    await db.session.commit()
    r = await client.post(
        f"/noor-import/draft/{draft_id}/map-existing-classes",
        headers=_headers(user),
        json={"mappings": []},
    )
    assert r.status_code == 400
