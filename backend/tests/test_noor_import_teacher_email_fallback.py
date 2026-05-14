"""Unit tests for the Noor teacher email-fallback ladder."""
import uuid

import pytest

from engines.noor_import.teacher_mapper import resolve_login_email
from engines.sql_utils import gd_insert
from dependencies import db


pytestmark = pytest.mark.asyncio


async def _seed_school(code: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid, "name": "S", "code": code, "country": "SA",
        "language": "ar", "status": "active",
    })
    return sid


async def test_ladder_step1_uses_clean_noor_email(_db_session):
    seen: set = set()
    out = await resolve_login_email(
        db.session,
        noor_email="teacher.x@example.com",
        school_code="abc",
        seen_emails_in_batch=seen,
    )
    assert out["source"] == "noor"
    assert out["email"] == "teacher.x@example.com"
    assert "teacher.x@example.com" in seen


async def test_ladder_step2_falls_back_for_blank_email(_db_session):
    seen: set = set()
    out = await resolve_login_email(
        db.session,
        noor_email="",
        school_code="ABC-123",
        seen_emails_in_batch=seen,
    )
    assert out["source"] == "fallback"
    assert out["email"].startswith("import.tch.")
    # School code is sanitised to [a-z0-9-] in the domain.
    assert out["email"].endswith("@abc-123.nassaq.school")


async def test_ladder_step2_falls_back_for_dup_email_in_batch(_db_session):
    seen: set = {"shared@example.com"}
    out = await resolve_login_email(
        db.session,
        noor_email="shared@example.com",
        school_code="sch",
        seen_emails_in_batch=seen,
    )
    assert out["source"] == "fallback"
    assert out["email"] != "shared@example.com"


async def test_ladder_step2_falls_back_for_dup_email_in_db(_db_session):
    sid = await _seed_school(f"S{uuid.uuid4().hex[:6]}")
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "email": "collide@example.com", "role": "teacher",
        "tenant_id": sid, "is_active": True, "password_hash": "x",
        "full_name": "x",
    })
    seen: set = set()
    out = await resolve_login_email(
        db.session,
        noor_email="COLLIDE@EXAMPLE.COM",  # case-insensitive collision
        school_code="sch",
        seen_emails_in_batch=seen,
    )
    assert out["source"] == "fallback"
    assert "@sch.nassaq.school" in out["email"]
