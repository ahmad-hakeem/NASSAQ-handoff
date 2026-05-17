"""Tests for POST /noor-import/draft/{id}/create-missing-classes.

Covers the task-388 contract:
  • Endpoint creates classes for every (grade, section) pair surfaced
    by `class_unresolved` rows, then re-annotates the draft so the
    same rows resolve without a second upload.
  • Ambiguous / un-normalisable pairs are REJECTED, never invented.
  • Cross-tenant draft access still returns 403.
  • Detected-type guard: teacher drafts cannot trigger class creation.
"""
import uuid

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


async def test_creates_missing_classes_and_reannotates(client, _db_session):
    user, school_id = await _seed_principal()
    rows = [
        _row(1, "S1", "طالب أ", "الأول الابتدائي", "أ"),
        _row(2, "S2", "طالب ب", "الأول الابتدائي", "أ"),
        _row(3, "S3", "طالب ج", "2", "1"),
    ]
    draft_id = await _seed_student_draft(user["id"], school_id, rows)
    await db.session.commit()

    r = await client.post(
        f"/noor-import/draft/{draft_id}/create-missing-classes",
        headers=_headers(user),
    )
    await db.session.commit()
    assert r.status_code == 200, r.text
    body = r.json()
    # Two unique normalised pairs → two classes created.
    assert len(body["created_classes"]) == 2
    assert body["counts"]["unclassified"] == 0
    # All three rows now resolve.
    for row in body["rows"]:
        assert row["class_unresolved"] is False
        assert row["class_id"] is not None

    # Classes actually written with normalised grade_level/section.
    db_classes = (await db.session.execute(
        text("SELECT grade_level, section FROM classes WHERE school_id = :sid ORDER BY grade_level"),
        {"sid": school_id},
    )).mappings().all()
    assert {(c["grade_level"], c["section"]) for c in db_classes} == {("1", "1"), ("2", "1")}


async def test_rejects_unnormalisable_pair_fail_closed(client, _db_session):
    user, school_id = await _seed_principal()
    rows = [_row(1, "S1", "طالب أ", "خرابيش", "??")]
    draft_id = await _seed_student_draft(user["id"], school_id, rows)
    await db.session.commit()

    r = await client.post(
        f"/noor-import/draft/{draft_id}/create-missing-classes",
        headers=_headers(user),
    )
    await db.session.commit()
    assert r.status_code == 200
    body = r.json()
    assert body["created_classes"] == []
    assert len(body["rejected_pairs"]) == 1
    # Row stays unresolved — no class was invented.
    assert body["counts"]["unclassified"] == 1
    db_classes = (await db.session.execute(
        text("SELECT count(*) FROM classes WHERE school_id = :sid"),
        {"sid": school_id},
    )).scalar()
    assert db_classes == 0


async def test_cross_tenant_draft_returns_403(client, _db_session):
    user_a, school_a = await _seed_principal()
    user_b, _school_b = await _seed_principal()
    rows = [_row(1, "S1", "x", "1", "1")]
    draft_id = await _seed_student_draft(user_a["id"], school_a, rows)
    await db.session.commit()

    r = await client.post(
        f"/noor-import/draft/{draft_id}/create-missing-classes",
        headers=_headers(user_b),
    )
    assert r.status_code == 403


async def test_teacher_draft_rejected(client, _db_session):
    user, school_id = await _seed_principal()
    # Manually create a teacher-typed draft.
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
        f"/noor-import/draft/{draft_id}/create-missing-classes",
        headers=_headers(user),
    )
    assert r.status_code == 400


async def test_skips_pair_when_class_already_exists(client, _db_session):
    user, school_id = await _seed_principal()
    # Pre-create the class that the row would resolve to.
    cid = str(uuid.uuid4())
    from datetime import datetime, timezone
    await db.session.execute(
        text(
            """
            INSERT INTO classes (id, name, school_id, grade_level, section,
                                 capacity, current_students, is_active,
                                 created_at, updated_at)
            VALUES (:id, :n, :sid, '1', '1', 30, 0, TRUE, :now, :now)
            """
        ),
        {"id": cid, "n": "Existing", "sid": school_id, "now": datetime.now(timezone.utc)},
    )
    rows = [_row(1, "S1", "طالب", "1", "1")]
    draft_id = await _seed_student_draft(user["id"], school_id, rows)
    await db.session.commit()

    r = await client.post(
        f"/noor-import/draft/{draft_id}/create-missing-classes",
        headers=_headers(user),
    )
    await db.session.commit()
    assert r.status_code == 200
    body = r.json()
    assert body["created_classes"] == []
    assert len(body["skipped_existing_classes"]) == 1
    # Row now resolves to the pre-existing class.
    assert body["rows"][0]["class_id"] == cid
    assert body["counts"]["unclassified"] == 0
