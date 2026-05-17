"""Tests for Noor import commit helpers and history recording.

Covers:
  • Unit tests for `_commit_students` — INSERT path, UPDATE path, and
    a mixed batch (insert + update + skipped) verifying that
    `created_ids`, `updated_ids`, and `imported_student_ids` are
    populated and partitioned correctly.
  • Unit tests for `_commit_teachers` — INSERT path (via
    TeacherManagementEngine.create_teacher), UPDATE path (matched by
    national_id), a mixed batch verifying id partitioning, and a
    skipped-row case.
  • Integration test for POST /noor-import/commit — verifies that one
    `noor_import_history` row is written with counts and id arrays that
    match the commit response.
  • Tenant isolation for GET /noor-import/history — school A must not
    see school B's history rows.
"""
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from dependencies import db, UserRole
from engines.sql_utils import gd_insert
from routes.noor_import_routes import _commit_students, _commit_teachers
from tests.conftest import _mk_user, _headers, _mk_school

pytestmark = pytest.mark.asyncio

FIX = Path(__file__).parent / "fixtures" / "noor"


# ---------------------------------------------------------------------------
# Unit tests: _commit_students
# ---------------------------------------------------------------------------


async def _seed_principal_and_school():
    sid = str(uuid.uuid4())
    await _mk_school(sid)
    user = await _mk_user(UserRole.SCHOOL_PRINCIPAL, sid)
    return user, sid


async def test_commit_students_insert_path_returns_created_ids(_db_session):
    """A row whose student_number does not exist must INSERT and surface
    the new id in `created_ids` (and `imported_student_ids`)."""
    user, school_id = await _seed_principal_and_school()
    rows = [
        {
            "row_index": 1,
            "data": {
                "student_number": f"S{uuid.uuid4().hex[:8]}",
                "full_name": "طالب جديد",
                "grade_code": "G1",
                "section_code": "A",
                "mobile": None,
            },
            "issues": [],
            "dedupe": "insert",
        }
    ]
    outcome = await _commit_students(
        db.session,
        school_id=school_id,
        rows=rows,
        created_by=user["id"],
        ambiguous_treat_as_new=set(),
    )
    assert outcome["imported"] == 1
    assert outcome["updated"] == 0
    assert outcome["failed"] == 0
    assert len(outcome["created_ids"]) == 1
    assert outcome["updated_ids"] == []
    new_id = outcome["created_ids"][0]
    assert outcome["imported_student_ids"] == [new_id]
    # Round-trip: the id is real and present in the students table.
    found = (await db.session.execute(
        text("SELECT id FROM students WHERE id = :id AND school_id = :sid"),
        {"id": new_id, "sid": school_id},
    )).scalar()
    assert found == new_id


async def test_commit_students_update_path_returns_updated_ids(_db_session):
    """A row whose student_number already exists must UPDATE and surface
    the existing id in `updated_ids` (and NOT `created_ids`)."""
    user, school_id = await _seed_principal_and_school()
    existing_id = str(uuid.uuid4())
    student_number = f"S{uuid.uuid4().hex[:8]}"
    await gd_insert(db.session, "students", {
        "id": existing_id,
        "school_id": school_id,
        "student_number": student_number,
        "full_name": "اسم قديم",
        "grade": "G1",
        "is_active": True,
    })
    rows = [
        {
            "row_index": 1,
            "data": {
                "student_number": student_number,
                "full_name": "اسم جديد",  # forces a real update
                "grade_code": "G1",
                "section_code": "A",
                "mobile": None,
            },
            "issues": [],
            "dedupe": "update",
        }
    ]
    outcome = await _commit_students(
        db.session,
        school_id=school_id,
        rows=rows,
        created_by=user["id"],
        ambiguous_treat_as_new=set(),
    )
    assert outcome["imported"] == 0
    assert outcome["updated"] == 1
    assert outcome["failed"] == 0
    assert outcome["created_ids"] == []
    assert outcome["updated_ids"] == [existing_id]


async def test_commit_students_mixed_batch_partitions_ids(_db_session):
    """A mixed batch (one insert + one update + one skipped issue row)
    must partition ids into `created_ids` vs `updated_ids` with no overlap."""
    user, school_id = await _seed_principal_and_school()
    existing_id = str(uuid.uuid4())
    existing_num = f"S{uuid.uuid4().hex[:8]}"
    await gd_insert(db.session, "students", {
        "id": existing_id,
        "school_id": school_id,
        "student_number": existing_num,
        "full_name": "موجود",
        "grade": "G2",
        "is_active": True,
    })
    new_num = f"S{uuid.uuid4().hex[:8]}"
    rows = [
        {
            "row_index": 1,
            "data": {
                "student_number": existing_num,
                "full_name": "موجود محدث",
                "grade_code": "G2",
                "section_code": "A",
            },
            "issues": [],
        },
        {
            "row_index": 2,
            "data": {
                "student_number": new_num,
                "full_name": "طالب جديد",
                "grade_code": "G3",
                "section_code": "B",
            },
            "issues": [],
        },
        {
            "row_index": 3,
            "data": {"student_number": "X", "full_name": "ناقص"},
            "issues": ["بيانات مفقودة"],
        },
    ]
    outcome = await _commit_students(
        db.session,
        school_id=school_id,
        rows=rows,
        created_by=user["id"],
        ambiguous_treat_as_new=set(),
    )
    assert outcome["imported"] == 1
    assert outcome["updated"] == 1
    assert outcome["skipped"] == 1
    assert outcome["updated_ids"] == [existing_id]
    assert len(outcome["created_ids"]) == 1
    # No overlap between the two id lists.
    assert set(outcome["created_ids"]).isdisjoint(set(outcome["updated_ids"]))


# ---------------------------------------------------------------------------
# Unit tests: _commit_teachers
# ---------------------------------------------------------------------------


async def test_commit_teachers_update_path_returns_updated_ids(_db_session):
    """A teacher row whose national_id matches an existing teacher must
    UPDATE and surface the existing id in `updated_ids`."""
    user, school_id = await _seed_principal_and_school()
    teacher_id = str(uuid.uuid4())
    nid = f"N{uuid.uuid4().hex[:8]}"
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "school_id": school_id,
        "full_name": "معلم قديم",
        "national_id": nid,
        "email": f"t-{teacher_id[:6]}@t.test",
        "phone": "0500000000",
        "is_active": True,
    })
    rows = [
        {
            "row_index": 1,
            "data": {
                "national_id": nid,
                "full_name": "معلم محدث",
                "phone": "0511111111",
                "email": f"t-{teacher_id[:6]}@t.test",
                "specialization": "رياضيات",
                "qualification": "بكالوريوس",
                "gender": "male",
            },
            "issues": [],
            "dedupe": "update",
        }
    ]
    outcome = await _commit_teachers(
        db.session,
        school_id=school_id,
        rows=rows,
        created_by=user["id"],
        ambiguous_treat_as_new=set(),
    )
    assert outcome["imported"] == 0
    assert outcome["updated"] == 1
    assert outcome["failed"] == 0
    assert outcome["created_ids"] == []
    assert outcome["updated_ids"] == [teacher_id]
    assert outcome["imported_teacher_ids"] == []


async def test_commit_teachers_insert_path_returns_created_ids(_db_session):
    """A teacher row whose national_id does not match any existing
    teacher must INSERT (via TeacherManagementEngine.create_teacher) and
    surface the new id in `created_ids` + `imported_teacher_ids`."""
    user, school_id = await _seed_principal_and_school()
    # 10-digit national_id is required by the engine validator.
    nid = "1" + "".join([str((i * 7) % 10) for i in range(9)])
    rows = [
        {
            "row_index": 1,
            "data": {
                "national_id": nid,
                "full_name": "معلم جديد",
                "phone": "0512345678",
                "email": f"new.teacher.{uuid.uuid4().hex[:6]}@example.com",
                "specialization": "علوم",
                "qualification": "بكالوريوس",
                "gender": "male",
            },
            "issues": [],
            "dedupe": "insert",
        }
    ]
    outcome = await _commit_teachers(
        db.session,
        school_id=school_id,
        rows=rows,
        created_by=user["id"],
        ambiguous_treat_as_new=set(),
    )
    assert outcome["failed"] == 0, outcome.get("errors")
    assert outcome["imported"] == 1
    assert outcome["updated"] == 0
    assert outcome["updated_ids"] == []
    assert len(outcome["created_ids"]) == 1
    new_id = outcome["created_ids"][0]
    assert outcome["imported_teacher_ids"] == [new_id]
    # Round-trip: the new teacher exists in this school's teachers table.
    found = (await db.session.execute(
        text("SELECT id FROM teachers WHERE id = :id AND school_id = :sid"),
        {"id": new_id, "sid": school_id},
    )).scalar()
    assert found == new_id


async def test_commit_teachers_mixed_batch_partitions_ids(_db_session):
    """A mixed teacher batch (insert + update + skipped issue row) must
    partition ids into `created_ids` vs `updated_ids` with no overlap."""
    user, school_id = await _seed_principal_and_school()
    # Pre-seed an existing teacher matched by national_id (update path).
    existing_tid = str(uuid.uuid4())
    existing_nid = "2" + "".join([str((i * 3) % 10) for i in range(9)])
    await gd_insert(db.session, "teachers", {
        "id": existing_tid,
        "school_id": school_id,
        "full_name": "معلم موجود",
        "national_id": existing_nid,
        "email": f"t-{existing_tid[:6]}@t.test",
        "phone": "0500000000",
        "is_active": True,
    })
    new_nid = "3" + "".join([str((i * 5) % 10) for i in range(9)])
    rows = [
        {
            "row_index": 1,
            "data": {
                "national_id": existing_nid,
                "full_name": "تحديث",
                "phone": "0511111111",
                "email": f"t-{existing_tid[:6]}@t.test",
                "gender": "male",
            },
            "issues": [],
        },
        {
            "row_index": 2,
            "data": {
                "national_id": new_nid,
                "full_name": "معلم جديد",
                "phone": "0522222222",
                "email": f"mix.{uuid.uuid4().hex[:6]}@example.com",
                "gender": "male",
            },
            "issues": [],
        },
        {
            "row_index": 3,
            "data": {"national_id": "9999999999", "full_name": "ناقص"},
            "issues": ["بيانات مفقودة"],
        },
    ]
    outcome = await _commit_teachers(
        db.session,
        school_id=school_id,
        rows=rows,
        created_by=user["id"],
        ambiguous_treat_as_new=set(),
    )
    assert outcome["failed"] == 0, outcome.get("errors")
    assert outcome["imported"] == 1
    assert outcome["updated"] == 1
    assert outcome["skipped"] == 1
    assert outcome["updated_ids"] == [existing_tid]
    assert len(outcome["created_ids"]) == 1
    assert set(outcome["created_ids"]).isdisjoint(set(outcome["updated_ids"]))


async def test_commit_teachers_skips_row_with_issues(_db_session):
    """A row carrying parse-time issues is counted as skipped, with no
    id in either created_ids or updated_ids."""
    user, school_id = await _seed_principal_and_school()
    rows = [
        {
            "row_index": 7,
            "data": {"national_id": "1234567890", "full_name": "x"},
            "issues": ["الاسم غير صالح"],
        }
    ]
    outcome = await _commit_teachers(
        db.session,
        school_id=school_id,
        rows=rows,
        created_by=user["id"],
        ambiguous_treat_as_new=set(),
    )
    assert outcome["skipped"] == 1
    assert outcome["imported"] == 0
    assert outcome["updated"] == 0
    assert outcome["created_ids"] == []
    assert outcome["updated_ids"] == []


# ---------------------------------------------------------------------------
# Integration: POST /noor-import/commit writes a history row
# ---------------------------------------------------------------------------


async def test_commit_endpoint_writes_history_row(client, _db_session):
    """Driving /parse + /commit end-to-end must persist one
    `noor_import_history` row whose counters match the commit outcome."""
    user, school_id = await _seed_principal_and_school()
    files = {
        "file": (
            "StudentGuidance.xls",
            (FIX / "StudentGuidance.xls").read_bytes(),
            "application/vnd.ms-excel",
        )
    }
    rp = await client.post(
        "/noor-import/parse", files=files, headers=_headers(user)
    )
    await db.session.commit()
    assert rp.status_code == 200, rp.text
    draft = rp.json()
    assert draft["detected_type"] == "students"

    pre_history = (await db.session.execute(
        text("SELECT count(*) FROM noor_import_history WHERE school_id = :sid"),
        {"sid": school_id},
    )).scalar()
    assert pre_history == 0

    rc = await client.post(
        "/noor-import/commit",
        json={"import_draft_id": draft["import_draft_id"]},
        headers=_headers(user),
    )
    await db.session.commit()
    assert rc.status_code == 200, rc.text
    body = rc.json()

    hist_rows = (await db.session.execute(
        text(
            """
            SELECT actor_id, actor_name, detected_type,
                   imported_count, updated_count, skipped_count,
                   failed_count, duplicates_count, unclassified_count,
                   created_ids, updated_ids
            FROM noor_import_history
            WHERE school_id = :sid
            """
        ),
        {"sid": school_id},
    )).mappings().all()
    assert len(hist_rows) == 1, "exactly one history row must be written per commit"
    h = hist_rows[0]
    assert h["actor_id"] == user["id"]
    assert h["actor_name"] == user["full_name"]
    assert h["detected_type"] == "students"
    assert h["imported_count"] == body["imported"]
    assert h["updated_count"] == body["updated"]
    assert h["skipped_count"] == body["skipped"]
    assert h["failed_count"] == body["failed"]
    assert h["duplicates_count"] == body.get("duplicates", 0)
    assert h["unclassified_count"] == body.get("unclassified", 0)
    # id lists must round-trip as JSONB lists.
    assert isinstance(h["created_ids"], list)
    assert isinstance(h["updated_ids"], list)
    assert len(h["created_ids"]) == body["imported"]
    assert len(h["updated_ids"]) == body["updated"]


# ---------------------------------------------------------------------------
# Tenant isolation: GET /noor-import/history
# ---------------------------------------------------------------------------


async def _seed_history_row(school_id: str, actor_id: str, detected_type: str,
                            imported: int) -> str:
    """Insert one synthetic noor_import_history row for the given school."""
    hid = str(uuid.uuid4())
    await db.session.execute(
        text(
            """
            INSERT INTO noor_import_history
                (id, school_id, actor_id, actor_name, detected_type,
                 imported_count, updated_count, skipped_count,
                 failed_count, duplicates_count, unclassified_count,
                 created_ids, updated_ids, created_class_ids,
                 credentials_csv, committed_at)
            VALUES
                (:id, :sid, :actor, 'test actor', :dt,
                 :imp, 0, 0, 0, 0, 0,
                 '[]'::JSONB, '[]'::JSONB, '[]'::JSONB,
                 '[]'::JSONB, NOW())
            """
        ),
        {"id": hid, "sid": school_id, "actor": actor_id, "dt": detected_type,
         "imp": imported},
    )
    return hid


async def test_get_history_is_tenant_isolated(client, _db_session):
    """Principal of school A must only see school A's history rows; the
    GET handler never leaks school B's rows even when they exist."""
    user_a, school_a = await _seed_principal_and_school()
    user_b, school_b = await _seed_principal_and_school()
    assert school_a != school_b

    a_hist_id = await _seed_history_row(school_a, user_a["id"], "students", 5)
    b_hist_id = await _seed_history_row(school_b, user_b["id"], "teachers", 9)
    await db.session.commit()

    # Principal A: sees only A's row.
    ra = await client.get("/noor-import/history", headers=_headers(user_a))
    assert ra.status_code == 200, ra.text
    a_ids = {row["id"] for row in ra.json()["history"]}
    assert a_hist_id in a_ids
    assert b_hist_id not in a_ids

    # Principal B: sees only B's row.
    rb = await client.get("/noor-import/history", headers=_headers(user_b))
    assert rb.status_code == 200, rb.text
    b_ids = {row["id"] for row in rb.json()["history"]}
    assert b_hist_id in b_ids
    assert a_hist_id not in b_ids
