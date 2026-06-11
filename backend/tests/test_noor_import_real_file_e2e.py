"""End-to-end validation of the Noor StudentGuidance importer using a REAL
Noor export.

The fixture's grade codes (0125, 0225, 0325, 0430, 0530, 0630) all normalise
OUT of the 1..12 range, so every student is initially unclassified
("بدون فصل") — the exact root-cause scenario the class-assignment feature
fixes. This test drives the full HTTP pipeline and proves BOTH assignment
paths resolve EVERY pair:

    parse  ->  map 3 pairs to EXISTING classes (Option B)
           ->  create classes for the other 3 via grade/section overrides
           ->  commit  ->  the imported student persists WITH a class_id.

NOTE on this real file: it is a Noor *template/sample* in which all 6 rows
carry the SAME student_number ("1234567899"). The importer therefore (and
correctly) flags 5 of them as in-file duplicates and only commits 1 row, so
`imported == 1` and `duplicates == 5`. The class-assignment logic itself is
validated against ALL 6 distinct (grade, section) pairs in the PREVIEW
(unclassified 6 -> 0). Per-pair commit assignment across multiple distinct
students is covered by test_noor_import_map_existing_classes.py and the
create-missing suite.
"""
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from dependencies import db, UserRole
from tests.conftest import _mk_user, _headers, _mk_school

pytestmark = pytest.mark.asyncio

FIX = Path(__file__).parent / "fixtures" / "noor" / "StudentGuidance_outofrange_grades.xls"


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
        {"id": cid, "n": f"{grade}-{section}", "sid": school_id, "g": grade,
         "s": section, "now": datetime.now(timezone.utc)},
    )
    return cid


async def test_real_noor_file_full_class_assignment_e2e(client, _db_session):
    school_id = str(uuid.uuid4())
    await _mk_school(school_id)
    user = await _mk_user(UserRole.SCHOOL_PRINCIPAL, school_id)

    # Three existing classes the principal can map unmatched pairs onto.
    cls_a = await _seed_class(school_id, "1", "1")
    cls_b = await _seed_class(school_id, "2", "1")
    cls_c = await _seed_class(school_id, "3", "1")
    await db.session.commit()

    # 1) Parse the real file — all 6 students unclassified.
    files = {"file": (FIX.name, FIX.read_bytes(), "application/vnd.ms-excel")}
    rp = await client.post("/noor-import/parse", files=files, headers=_headers(user))
    await db.session.commit()
    assert rp.status_code == 200, rp.text
    draft = rp.json()
    assert draft["detected_type"] == "students"
    rows = draft["rows"]
    assert len(rows) == 6
    # All 6 students start unclassified (grade codes out of the 1..12 range).
    assert draft["counts"]["unclassified"] == 6
    assert all(r["class_unresolved"] for r in rows)
    # This sample file reuses one student_number across all rows -> in-file
    # dedupe: 1 insert + 5 duplicates (documents why commit imports only 1).
    assert draft["counts"]["duplicate_in_file"] == 5
    draft_id = draft["import_draft_id"]

    # 2) Map 3 pairs to EXISTING classes (Option B).
    rm = await client.post(
        f"/noor-import/draft/{draft_id}/map-existing-classes",
        headers=_headers(user),
        json={"mappings": [
            {"grade_code": "0125", "section_code": "1", "class_id": cls_a},
            {"grade_code": "0225", "section_code": "1", "class_id": cls_b},
            {"grade_code": "0325", "section_code": "1", "class_id": cls_c},
        ]},
    )
    await db.session.commit()
    assert rm.status_code == 200, rm.text
    assert rm.json()["counts"]["unclassified"] == 3

    # 3) Create classes for the remaining 3 pairs (fallback). The raw codes
    #    can't normalise, so the principal corrects them to real grades.
    rc = await client.post(
        f"/noor-import/draft/{draft_id}/create-missing-classes",
        headers=_headers(user),
        json={"overrides": [
            {"grade_code": "0430", "section_code": "1", "grade_override": "4", "section_override": "1"},
            {"grade_code": "0530", "section_code": "2", "grade_override": "5", "section_override": "2"},
            {"grade_code": "0630", "section_code": "2", "grade_override": "6", "section_override": "2"},
        ]},
    )
    await db.session.commit()
    assert rc.status_code == 200, rc.text
    cdata = rc.json()
    created_ids = {c["class_id"] for c in cdata["created_classes"]}
    assert len(created_ids) == 3
    assert cdata["counts"]["unclassified"] == 0

    # Class CREATION truth: the 3 new classes are persisted with the corrected
    # (override) grades 4/5/6 and live alongside the 3 pre-seeded classes.
    created_rows = (await db.session.execute(
        text(
            "SELECT grade_level, section FROM classes "
            "WHERE school_id = :sid AND id = ANY(:ids)"
        ),
        {"sid": school_id, "ids": list(created_ids)},
    )).mappings().all()
    assert len(created_rows) == 3
    assert {r["grade_level"] for r in created_rows} == {"4", "5", "6"}
    total_classes = (await db.session.execute(
        text("SELECT COUNT(*) FROM classes WHERE school_id = :sid"),
        {"sid": school_id},
    )).scalar_one()
    assert total_classes == 6  # 3 seeded + 3 created

    # 4) Commit — every student must persist WITH a class_id.
    rco = await client.post(
        "/noor-import/commit",
        json={"import_draft_id": draft_id},
        headers=_headers(user),
    )
    await db.session.commit()
    assert rco.status_code == 200, rco.text
    body = rco.json()
    assert body["failed"] == 0
    # All resolved (no "بدون فصل"); 1 real insert + 5 in-file duplicates.
    assert body["unclassified"] == 0
    assert body["imported"] == 1
    assert body["duplicates"] == 5

    # 5) DB truth: the one imported student is the first row (0125), which we
    #    mapped to an EXISTING class — it must carry exactly that class_id and
    #    NOT be left "بدون فصل".
    students = (await db.session.execute(
        text("SELECT full_name, grade, class_id FROM students WHERE school_id = :sid"),
        {"sid": school_id},
    )).mappings().all()
    assert len(students) == 1
    s = students[0]
    assert s["class_id"], "imported student must have a class (not بدون فصل)"
    assert s["grade"] == "0125"
    assert str(s["class_id"]) == cls_a
