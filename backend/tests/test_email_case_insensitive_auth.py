"""
Regression tests for case-insensitive email handling in authentication.

Login and password-reset resolve the account through
``_find_user_by_email_ci`` (auth_routes_mod), and every account-creation
path (``/auth/register``, platform ``/users/create``, and the direct
teacher-registration route) uses the same helper to block a duplicate that
differs only by letter case. These tests lock in that behaviour, including
for legacy rows that were persisted with mixed/upper-case emails before
normalization existed.

The helper performs a pure ``SELECT`` (``lower(email) = lower(input)``) so
these tests never write through an endpoint: rows are seeded with
``gd_insert`` (flush-only) and rolled back by the ``_db_session`` fixture.
Emails are derived from a fresh UUID so real rows in the connected database
cannot satisfy the lookup by accident.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from dependencies import db
from engines.sql_utils import gd_insert
from routes.auth_routes_mod import _find_user_by_email_ci
from routes.registration_routes_mod import (
    _create_school_instant,
    _create_independent_teacher_instant,
)
from shared_models import RegistrationRequest


pytestmark = pytest.mark.asyncio


async def _seed_user(email: str, role: str = "teacher") -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "email": email,
        "full_name": "CI Email User",
        "role": role,
        "tenant_id": None,
        "is_active": True,
        "password_hash": "x",
    })
    return uid


async def test_ci_lookup_resolves_legacy_uppercase_row():
    """A row stored with mixed/upper case (legacy data) must resolve
    regardless of how the caller cases the email — this is the login and
    forgot-password lookup path."""
    base = uuid.uuid4().hex
    stored = f"Legacy_{base}@Example.TEST"
    uid = await _seed_user(stored)

    for variant in (stored, stored.lower(), stored.upper(), f"  {stored.lower()}  "):
        found = await _find_user_by_email_ci(variant)
        assert found is not None, f"lookup failed for variant {variant!r}"
        assert found["id"] == uid


async def test_ci_lookup_blocks_differently_cased_duplicate():
    """A lowercase-stored account must be found when queried with a
    differently-cased email — this is the uniqueness guard shared by
    register / users-create / teacher-registration."""
    base = uuid.uuid4().hex
    stored = f"dup_{base}@x.test"
    uid = await _seed_user(stored)

    found = await _find_user_by_email_ci(stored.upper())
    assert found is not None
    assert found["id"] == uid


async def test_ci_lookup_returns_none_for_unknown_and_blank():
    base = uuid.uuid4().hex
    assert await _find_user_by_email_ci(None) is None
    assert await _find_user_by_email_ci("") is None
    assert await _find_user_by_email_ci("   ") is None
    assert await _find_user_by_email_ci(f"missing_{base}@nowhere.test") is None


async def test_ci_lookup_returns_full_row_shape():
    """Callers drop the result in place of ``gd_find_one`` output, so the
    returned dict must carry the row fields (id, email, role)."""
    base = uuid.uuid4().hex
    stored = f"shape_{base}@Example.TEST"
    uid = await _seed_user(stored)

    found = await _find_user_by_email_ci(stored)
    assert found is not None
    assert found["id"] == uid
    assert found["role"] == "teacher"
    assert found["email"].lower() == stored.lower()


async def test_school_instant_signup_blocks_legacy_uppercase_duplicate():
    """The public instant school signup must reject a new account whose
    email differs only by case from a legacy uppercase-stored row."""
    base = uuid.uuid4().hex
    stored = f"Owner_{base}@School.TEST"
    await _seed_user(stored, role="school_admin")

    req = RegistrationRequest(
        full_name="Test School Owner",
        phone="",
        account_type="school",
        school_name="Test School",
        school_email=stored.lower(),
        school_city="Riyadh",
        password="password123",
    )

    with pytest.raises(HTTPException) as exc:
        await _create_school_instant(req, "Test School Owner", "", "")
    assert exc.value.status_code == 400
    assert "مسجل" in exc.value.detail


async def test_independent_teacher_instant_signup_blocks_legacy_uppercase_duplicate():
    """The public instant independent-teacher signup must reject a new
    account whose email differs only by case from a legacy uppercase row."""
    base = uuid.uuid4().hex
    stored = f"Teacher_{base}@Mail.TEST"
    await _seed_user(stored, role="independent_teacher")

    req = RegistrationRequest(
        full_name="Test Teacher",
        phone="",
        account_type="independent_teacher",
        email=stored.lower(),
        password="password123",
    )

    with pytest.raises(HTTPException) as exc:
        await _create_independent_teacher_instant(req, "Test Teacher", "", "")
    assert exc.value.status_code == 400
    assert "مسجل" in exc.value.detail
