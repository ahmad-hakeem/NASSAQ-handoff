"""Integration tests for /noor-import/{parse,commit} — covers the
server-authoritative draft contract and cross-tenant scoping."""
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from dependencies import db, UserRole
from engines.sql_utils import gd_insert, gd_find_one
from tests.conftest import _mk_user, _headers, _mk_school

pytestmark = pytest.mark.asyncio

FIX = Path(__file__).parent / "fixtures" / "noor"


async def _seed_principal_with_school():
    school_id = str(uuid.uuid4())
    await _mk_school(school_id)
    user = await _mk_user(UserRole.SCHOOL_PRINCIPAL, school_id)
    return user, school_id


async def test_parse_returns_draft_id_and_no_writes(client, _db_session):
    user, school_id = await _seed_principal_with_school()
    # Pre-state: zero students for this school.
    pre = (await db.session.execute(
        text("SELECT count(*) FROM students WHERE school_id = :sid"),
        {"sid": school_id},
    )).scalar()
    files = {"file": ("StudentGuidance.xls", (FIX / "StudentGuidance.xls").read_bytes(), "application/vnd.ms-excel")}
    r = await client.post("/noor-import/parse", files=files, headers=_headers(user))
    await db.session.commit()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["detected_type"] == "students"
    assert body["import_draft_id"]
    assert body["counts"]["total"] >= 1
    # No students created during parse.
    post = (await db.session.execute(
        text("SELECT count(*) FROM students WHERE school_id = :sid"),
        {"sid": school_id},
    )).scalar()
    assert post == pre


async def test_commit_rejects_unknown_draft_id(client, _db_session):
    user, _sid = await _seed_principal_with_school()
    r = await client.post(
        "/noor-import/commit",
        json={"import_draft_id": "definitely-not-a-real-draft-id-xxxxxxxxxxxx"},
        headers=_headers(user),
    )
    assert r.status_code == 403
    body = r.json()
    msg = body.get("detail") or (body.get("error") or {}).get("message") or ""
    assert "صلاحية" in msg or "منتهية" in msg


async def test_commit_rejects_cross_tenant_draft(client, _db_session):
    """Draft minted by principal of school A cannot be committed by principal of school B."""
    user_a, school_a = await _seed_principal_with_school()
    user_b, _school_b = await _seed_principal_with_school()
    files = {"file": ("StudentGuidance.xls", (FIX / "StudentGuidance.xls").read_bytes(), "application/vnd.ms-excel")}
    r = await client.post("/noor-import/parse", files=files, headers=_headers(user_a))
    await db.session.commit()
    assert r.status_code == 200
    draft_id = r.json()["import_draft_id"]
    # User B tries to commit A's draft → 403.
    r2 = await client.post(
        "/noor-import/commit",
        json={"import_draft_id": draft_id},
        headers=_headers(user_b),
    )
    assert r2.status_code == 403


async def test_parse_rejects_non_excel(client, _db_session):
    user, _ = await _seed_principal_with_school()
    files = {"file": ("note.txt", b"hello", "text/plain")}
    r = await client.post("/noor-import/parse", files=files, headers=_headers(user))
    assert r.status_code == 400


async def test_commit_ignores_client_supplied_rows(client, _db_session):
    """Defense-in-depth: a fabricated `rows`/`payload` field on the
    commit body must NOT influence the write — only the server-side
    draft is read."""
    user, school_id = await _seed_principal_with_school()
    files = {"file": ("StudentGuidance.xls", (FIX / "StudentGuidance.xls").read_bytes(), "application/vnd.ms-excel")}
    rp = await client.post("/noor-import/parse", files=files, headers=_headers(user))
    await db.session.commit()
    assert rp.status_code == 200
    draft_id = rp.json()["import_draft_id"]
    expected_processed = rp.json()["counts"]["insert"] + rp.json()["counts"]["update"]

    # Send a wildly different `rows` array. Pydantic schema only declares
    # `import_draft_id` + `confirmations` so extras are silently dropped.
    fake_rows = [
        {"row_index": 9999, "data": {"student_number": "EVIL", "full_name": "DROP TABLE students;"},
         "issues": [], "dedupe": "insert"}
    ]
    rc = await client.post(
        "/noor-import/commit",
        json={
            "import_draft_id": draft_id,
            "confirmations": {},
            "rows": fake_rows,
            "payload": {"rows": fake_rows},
        },
        headers=_headers(user),
    )
    await db.session.commit()
    assert rc.status_code == 200, rc.text
    body = rc.json()
    # Outcome reflects the real fixture, NOT the injected row. The
    # fixture repeats one student_number 6× so the commit splits into
    # 1 insert + 5 in-batch updates — both numbers count as "real-row
    # processing", and zero come from the injected payload.
    assert (body["imported"] + body["updated"]) == expected_processed
    # No student with the injected sentinel was created anywhere in the DB.
    evil = (await db.session.execute(
        text("SELECT count(*) FROM students WHERE student_number = 'EVIL'"),
    )).scalar()
    assert evil == 0


async def test_parse_forbidden_for_non_school_role(client, _db_session):
    school_id = str(uuid.uuid4())
    await _mk_school(school_id)
    teacher = await _mk_user(UserRole.TEACHER, school_id)
    files = {"file": ("StudentGuidance.xls", (FIX / "StudentGuidance.xls").read_bytes(), "application/vnd.ms-excel")}
    r = await client.post("/noor-import/parse", files=files, headers=_headers(teacher))
    assert r.status_code == 403
