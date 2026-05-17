"""Tests for POST /noor-import/draft/{id}/undo-created-classes.

Covers the task-391 contract:
  • Undo deletes ONLY classes that still have zero students attached.
  • Classes with students are refused (never silently force-deleted).
  • Cross-tenant draft access returns 403.
  • Teacher drafts are rejected (students-only flow).
  • Cross-tenant class ids are reported as not_found, not deleted.
  • Draft is re-annotated so unresolved rows reflect the new state.
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


async def _create_class(school_id, grade, section):
    cid = str(uuid.uuid4())
    await db.session.execute(
        text(
            """
            INSERT INTO classes (id, name, school_id, grade_level, section,
                                 capacity, current_students, is_active,
                                 created_at, updated_at)
            VALUES (:id, :n, :sid, :g, :s, 30, 0, TRUE, :now, :now)
            """
        ),
        {
            "id": cid,
            "n": f"{grade}-{section}",
            "sid": school_id,
            "g": grade,
            "s": section,
            "now": datetime.now(timezone.utc),
        },
    )
    return cid


async def test_undo_deletes_empty_classes_and_reannotates(client, _db_session):
    user, school_id = await _seed_principal()
    rows = [_row(1, "S1", "طالب", "1", "1")]
    draft_id = await _seed_student_draft(user["id"], school_id, rows)
    # Pre-create the class as `/create-missing-classes` would have done.
    cid = await _create_class(school_id, "1", "1")
    await db.session.commit()

    r = await client.post(
        f"/noor-import/draft/{draft_id}/undo-created-classes",
        headers=_headers(user),
        json={"class_ids": [cid]},
    )
    await db.session.commit()
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["undone_classes"]) == 1
    assert body["undone_classes"][0]["class_id"] == cid
    assert body["refused_classes"] == []
    # Class is gone.
    n = (await db.session.execute(
        text("SELECT COUNT(*) FROM classes WHERE id = :id"), {"id": cid}
    )).scalar()
    assert n == 0
    # Row is unresolved again.
    assert body["rows"][0]["class_unresolved"] is True
    assert body["counts"]["unclassified"] == 1


async def test_undo_refuses_class_with_students(client, _db_session):
    user, school_id = await _seed_principal()
    rows = [_row(1, "S1", "طالب", "1", "1")]
    draft_id = await _seed_student_draft(user["id"], school_id, rows)
    cid = await _create_class(school_id, "1", "1")
    # Attach a student to the class — simulates /commit having already
    # populated it.
    sid = str(uuid.uuid4())
    await db.session.execute(
        text(
            """
            INSERT INTO students (id, school_id, class_id, student_number,
                                  full_name, is_active, created_at, updated_at)
            VALUES (:id, :sid, :cid, 'S1', 'طالب', TRUE, :now, :now)
            """
        ),
        {
            "id": sid,
            "sid": school_id,
            "cid": cid,
            "now": datetime.now(timezone.utc),
        },
    )
    await db.session.commit()

    r = await client.post(
        f"/noor-import/draft/{draft_id}/undo-created-classes",
        headers=_headers(user),
        json={"class_ids": [cid]},
    )
    await db.session.commit()
    assert r.status_code == 200
    body = r.json()
    assert body["undone_classes"] == []
    assert len(body["refused_classes"]) == 1
    refused = body["refused_classes"][0]
    assert refused["class_id"] == cid
    assert refused["reason"] == "has_students"
    assert refused["student_count"] == 1
    # Class still present.
    n = (await db.session.execute(
        text("SELECT COUNT(*) FROM classes WHERE id = :id"), {"id": cid}
    )).scalar()
    assert n == 1


async def test_undo_cross_tenant_class_id_is_not_found(client, _db_session):
    user_a, school_a = await _seed_principal()
    _user_b, school_b = await _seed_principal()
    rows = [_row(1, "S1", "طالب", "1", "1")]
    draft_id = await _seed_student_draft(user_a["id"], school_a, rows)
    foreign_cid = await _create_class(school_b, "1", "1")
    await db.session.commit()

    r = await client.post(
        f"/noor-import/draft/{draft_id}/undo-created-classes",
        headers=_headers(user_a),
        json={"class_ids": [foreign_cid]},
    )
    await db.session.commit()
    assert r.status_code == 200
    body = r.json()
    assert body["undone_classes"] == []
    assert body["refused_classes"] == [
        {"class_id": foreign_cid, "reason": "not_found"}
    ]
    # Foreign class untouched.
    n = (await db.session.execute(
        text("SELECT COUNT(*) FROM classes WHERE id = :id"), {"id": foreign_cid}
    )).scalar()
    assert n == 1


async def test_undo_cross_tenant_draft_returns_403(client, _db_session):
    user_a, school_a = await _seed_principal()
    user_b, _ = await _seed_principal()
    rows = [_row(1, "S1", "x", "1", "1")]
    draft_id = await _seed_student_draft(user_a["id"], school_a, rows)
    await db.session.commit()

    r = await client.post(
        f"/noor-import/draft/{draft_id}/undo-created-classes",
        headers=_headers(user_b),
        json={"class_ids": []},
    )
    assert r.status_code == 403


async def test_undo_teacher_draft_rejected(client, _db_session):
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
        f"/noor-import/draft/{draft_id}/undo-created-classes",
        headers=_headers(user),
        json={"class_ids": []},
    )
    assert r.status_code == 400


async def test_undo_rejects_malformed_body(client, _db_session):
    user, school_id = await _seed_principal()
    draft_id = await _seed_student_draft(user["id"], school_id, [])
    await db.session.commit()
    r = await client.post(
        f"/noor-import/draft/{draft_id}/undo-created-classes",
        headers=_headers(user),
        json={"class_ids": [123]},
    )
    assert r.status_code == 400
