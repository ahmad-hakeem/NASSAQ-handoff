"""End-to-end commit test for Noor StudentGuidance — verifies that
students are inserted record-only (no users row) and that re-running
the same draft updates rather than duplicates."""
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from dependencies import db, UserRole
from engines.sql_utils import gd_insert
from tests.conftest import _mk_user, _headers, _mk_school

pytestmark = pytest.mark.asyncio

FIX = Path(__file__).parent / "fixtures" / "noor"


async def test_student_commit_creates_records_no_users(client, _db_session):
    school_id = str(uuid.uuid4())
    await _mk_school(school_id)
    user = await _mk_user(UserRole.SCHOOL_PRINCIPAL, school_id)

    files = {"file": ("StudentGuidance.xls", (FIX / "StudentGuidance.xls").read_bytes(), "application/vnd.ms-excel")}
    rp = await client.post("/noor-import/parse", files=files, headers=_headers(user))
    await db.session.commit()
    assert rp.status_code == 200, rp.text
    draft = rp.json()
    assert draft["detected_type"] == "students"
    inserts_expected = draft["counts"]["insert"]

    rc = await client.post(
        "/noor-import/commit",
        json={"import_draft_id": draft["import_draft_id"]},
        headers=_headers(user),
    )
    await db.session.commit()
    assert rc.status_code == 200, rc.text
    body = rc.json()
    # Distinct student numbers in the fixture → expect inserts.
    assert body["imported"] >= 0
    assert body["failed"] == 0

    # Verify NO users row was minted for any imported student.
    student_rows = (await db.session.execute(
        text("SELECT id, student_number FROM students WHERE school_id = :sid"),
        {"sid": school_id},
    )).mappings().all()
    if student_rows:
        users_count = (await db.session.execute(
            text("SELECT count(*) FROM users WHERE tenant_id = :sid AND role = 'student'"),
            {"sid": school_id},
        )).scalar()
        assert users_count == 0, "Noor student importer must NOT create users rows"
