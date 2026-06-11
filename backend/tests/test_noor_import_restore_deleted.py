"""Restore-on-re-import semantics for the Noor student importer.

Regression for the principal-reported bug: students imported from Noor,
then DELETED (soft delete -> is_active=FALSE), then re-imported from a
corrected file were classified as "تحديث/update" and silently patched a
row that stayed invisible. The canonical rule is RESTORE:

  • An exact (school_id, student_number) match against a SOFT-DELETED row
    is classified "restore" in the preview (not "update").
  • /commit reactivates the row (is_active=TRUE) AND applies the corrected
    data — it never blind-inserts (that would collide with the surviving
    uq_students_number_school unique constraint).
  • An ACTIVE match is still "update". After a restore the row is active,
    so a further identical re-import is a plain no-op update.
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from dependencies import db, UserRole
from engines.noor_import.draft_store import create_draft
from engines.noor_import.student_mapper import insert_student_record_only
from routes.noor_import_routes import _annotate_student_rows
from tests.conftest import _mk_user, _headers, _mk_school

pytestmark = pytest.mark.asyncio


def _parsed(idx, num, name, grade, section):
    return {
        "row_index": idx,
        "data": {
            "student_number": num,
            "full_name": name,
            "grade_code": grade,
            "section_code": section,
        },
    }


def _draft_row(idx, num, name, grade, section):
    return {
        "row_index": idx,
        "data": {
            "student_number": num,
            "full_name": name,
            "grade_code": grade,
            "section_code": section,
        },
        "issues": [],
        "dedupe": "insert",  # advisory only — /commit recomputes from live DB
        "existing_id": None,
        "class_id": None,
        "class_unresolved": False,
        "student_number_generated": False,
    }


async def _seed_principal():
    school_id = str(uuid.uuid4())
    await _mk_school(school_id)
    user = await _mk_user(UserRole.SCHOOL_PRINCIPAL, school_id)
    return user, school_id


async def _seed_class(school_id, grade, section):
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
            "id": cid, "n": f"{grade}-{section}", "sid": school_id,
            "g": grade, "s": section, "now": datetime.now(timezone.utc),
        },
    )
    return cid


async def _soft_delete(student_id):
    await db.session.execute(
        text("UPDATE students SET is_active = FALSE WHERE id = :id"),
        {"id": student_id},
    )


async def test_annotate_deleted_match_is_restore_active_is_update(client, _db_session):
    """Preview: a soft-deleted exact-number match -> 'restore'; an active
    match -> 'update'."""
    user, school_id = await _seed_principal()
    cid = await _seed_class(school_id, "1", "1")

    deleted_id = await insert_student_record_only(
        db.session, school_id=school_id, student_number="1001",
        full_name="اسم قديم", grade_code="1", section_code="1",
        class_id=cid, mobile=None, created_by=user["id"],
    )
    await _soft_delete(deleted_id)
    await insert_student_record_only(
        db.session, school_id=school_id, student_number="1002",
        full_name="طالب نشط", grade_code="1", section_code="1",
        class_id=cid, mobile=None, created_by=user["id"],
    )
    await db.session.commit()

    annotated = await _annotate_student_rows(
        db.session,
        school_id=school_id,
        parsed_rows=[
            _parsed(1, "1001", "اسم صحيح", "1", "1"),
            _parsed(2, "1002", "طالب نشط", "1", "1"),
        ],
    )
    by_num = {r["data"]["student_number"]: r for r in annotated}
    assert by_num["1001"]["dedupe"] == "restore"
    assert by_num["1001"]["existing_id"] == deleted_id
    assert by_num["1002"]["dedupe"] == "update"


async def test_commit_restore_reactivates_and_applies_corrected_data(client, _db_session):
    """/commit on a deleted match reactivates the row + writes corrected
    data, with NO duplicate row and NO unique-constraint violation."""
    user, school_id = await _seed_principal()
    cid = await _seed_class(school_id, "1", "1")

    deleted_id = await insert_student_record_only(
        db.session, school_id=school_id, student_number="1001",
        full_name="اسم قديم", grade_code="1", section_code="1",
        class_id=None, mobile=None, created_by=user["id"],
    )
    await _soft_delete(deleted_id)
    await db.session.commit()

    draft_id = await create_draft(
        db.session,
        principal_id=user["id"],
        school_id=school_id,
        detected_type="students",
        header_row=1,
        sheet_name="Sheet1",
        mapped_columns={},
        rows=[_draft_row(1, "1001", "اسم صحيح", "1", "1")],
        counts={"total": 1, "insert": 1, "restore": 0},
    )
    await db.session.commit()

    rc = await client.post(
        "/noor-import/commit",
        json={"import_draft_id": draft_id},
        headers=_headers(user),
    )
    await db.session.commit()
    assert rc.status_code == 200, rc.text
    body = rc.json()
    assert body["restored"] == 1
    assert body["updated"] == 0
    assert body["imported"] == 0
    assert body["failed"] == 0

    rows = (await db.session.execute(
        text(
            "SELECT id, is_active, full_name, class_id FROM students "
            "WHERE school_id = :sid AND student_number = '1001'"
        ),
        {"sid": school_id},
    )).mappings().all()
    assert len(rows) == 1  # reactivated in place — no duplicate
    assert rows[0]["id"] == deleted_id
    assert rows[0]["is_active"] is True
    assert rows[0]["full_name"] == "اسم صحيح"
    assert str(rows[0]["class_id"]) == cid


async def test_restore_is_idempotent_second_reimport_is_update(client, _db_session):
    """After a restore the row is active again, so an identical re-import is
    a plain no-op update — not another restore."""
    user, school_id = await _seed_principal()
    cid = await _seed_class(school_id, "1", "1")

    deleted_id = await insert_student_record_only(
        db.session, school_id=school_id, student_number="1001",
        full_name="اسم صحيح", grade_code="1", section_code="1",
        class_id=cid, mobile=None, created_by=user["id"],
    )
    await _soft_delete(deleted_id)
    await db.session.commit()

    async def _commit_same():
        draft_id = await create_draft(
            db.session,
            principal_id=user["id"],
            school_id=school_id,
            detected_type="students",
            header_row=1,
            sheet_name="Sheet1",
            mapped_columns={},
            rows=[_draft_row(1, "1001", "اسم صحيح", "1", "1")],
            counts={"total": 1, "insert": 1},
        )
        await db.session.commit()
        rc = await client.post(
            "/noor-import/commit",
            json={"import_draft_id": draft_id},
            headers=_headers(user),
        )
        await db.session.commit()
        assert rc.status_code == 200, rc.text
        return rc.json()

    first = await _commit_same()
    assert first["restored"] == 1
    assert first["updated"] == 0

    second = await _commit_same()
    assert second["restored"] == 0
    assert second["updated"] == 1
    assert second["imported"] == 0
