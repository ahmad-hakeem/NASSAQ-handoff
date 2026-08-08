"""
Tests for Task #183 — Independent-Teacher first-login bootstrap.

Covers the spec checklist:
  (a) Pre-bootstrap IT calling a non-allow-listed route → 409 Arabic.
  (b) Bootstrap creates schools + school_settings + academic_year +
      academic_term + teachers and sets users.tenant_id atomically.
  (c) Optional first class is created (classes are unlimited for IT).
  (d) Replaying bootstrap is idempotent (no duplicate rows, 200 OK).
  (e) MFA enrolment and recent-assertion gates.
"""
import time
import uuid

import pytest
from datetime import datetime, timezone

from dependencies import db, UserRole, create_access_token
from auth_scope import (
    independent_workspace_id,
    WORKSPACE_NOT_MATERIALISED_AR,
)
from engines.sql_utils import gd_count, gd_find_one, gd_insert


def _headers(user_id: str, role: str, tenant_id=None, mfa_recent_at=None) -> dict:
    token = create_access_token(
        {"sub": user_id, "role": role, "tenant_id": tenant_id},
        mfa_recent_at=mfa_recent_at,
        mfa_kind="totp" if mfa_recent_at else None,
    )
    return {"Authorization": f"Bearer {token}"}


async def _mk_pre_bootstrap_it(*, mfa_enrolled: bool = True) -> dict:
    """Create an IT user with NO tenant_id and NO synthetic schools row."""
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    if mfa_enrolled:
        user["mfa_enrolled_at"] = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "users", user)
    return user


def _bootstrap_payload(with_class: bool = False) -> dict:
    payload = {
        "workspace_name_ar": "أكاديمية التجربة",
        "workspace_name_en": "Test Academy",
        "academic_year_label": "1447 - 1448 هـ",
        "term_label": "الفصل الأول",
        "working_days": ["sun", "mon", "tue", "wed", "thu"],
        "periods_per_day": 6,
    }
    if with_class:
        payload["first_class"] = {
            "name": "1-أ",
            "grade_level": "الأول الابتدائي",
            "subject": "الرياضيات",
            "capacity": 25,
        }
    return payload


# ----------------------------------------------------------------------
# (a) workspace gate — pre-bootstrap IT cannot use general API.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pre_bootstrap_it_blocked_with_409(client):
    user = await _mk_pre_bootstrap_it()
    h = _headers(user["id"], user["role"], None, mfa_recent_at=int(time.time()))
    # /students is NOT allow-listed and is a normal authenticated route.
    resp = await client.get("/students", headers=h)
    assert resp.status_code == 409, resp.text
    body = resp.json()
    msg = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert WORKSPACE_NOT_MATERIALISED_AR in msg, body


@pytest.mark.asyncio
async def test_auth_me_is_allowed_pre_bootstrap(client):
    """The allow-list lets /auth/me through so the wizard can bootstrap."""
    user = await _mk_pre_bootstrap_it()
    h = _headers(user["id"], user["role"], None, mfa_recent_at=int(time.time()))
    resp = await client.get("/auth/me", headers=h)
    # We don't care about the body shape here, only that it's not the 409
    # workspace gate. /auth/me may still 200 or 4xx for unrelated reasons,
    # but it must not be the workspace-not-materialised 409.
    assert resp.status_code != 409, resp.text


# ----------------------------------------------------------------------
# (e) MFA gates on the bootstrap endpoint.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bootstrap_requires_mfa_enrolment(client, enforce_mfa):
    user = await _mk_pre_bootstrap_it(mfa_enrolled=False)
    h = _headers(user["id"], user["role"], None, mfa_recent_at=int(time.time()))
    resp = await client.post(
        "/independent-teacher/bootstrap",
        headers=h,
        json=_bootstrap_payload(),
    )
    assert resp.status_code == 403, resp.text
    body = resp.json()
    err = body.get("error") or {}
    code = err.get("code") or (err.get("detail") or {}).get("code") or (
        body.get("detail") or {}
    ).get("code")
    assert code == "mfa_enrollment_required", resp.text


@pytest.mark.asyncio
async def test_bootstrap_requires_recent_mfa_assertion(client, enforce_mfa):
    user = await _mk_pre_bootstrap_it(mfa_enrolled=True)
    # No mfa_recent_at in the JWT.
    h = _headers(user["id"], user["role"], None, mfa_recent_at=None)
    resp = await client.post(
        "/independent-teacher/bootstrap",
        headers=h,
        json=_bootstrap_payload(),
    )
    # 401 + MFA_STEPUP_REQUIRED matches the contract the existing axios
    # step-up modal interceptor consumes (AuthContext.js).
    assert resp.status_code == 401, resp.text
    body = resp.json()
    err = body.get("error") or {}
    code = err.get("code") or (err.get("detail") or {}).get("code") or (
        body.get("detail") or {}
    ).get("code")
    assert code == "MFA_STEPUP_REQUIRED", resp.text


# ----------------------------------------------------------------------
# (b)+(c)+(d) — happy-path materialisation, idempotency, first-class.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bootstrap_materialises_workspace_atomically(client):
    user = await _mk_pre_bootstrap_it()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], None, mfa_recent_at=int(time.time()))

    resp = await client.post(
        "/independent-teacher/bootstrap",
        headers=h,
        json=_bootstrap_payload(with_class=True),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["already_materialised"] is False
    assert body["workspace"]["workspace_id"] == wsid
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["tenant_id"] == wsid

    # Verify each row landed.
    school = await gd_find_one(db.session, "schools", {"id": wsid})
    assert school is not None
    settings = await gd_find_one(db.session, "school_settings", {"school_id": wsid})
    assert settings is not None
    assert settings.get("periods_per_day") == 6
    year = await gd_find_one(db.session, "academic_years", {"school_id": wsid})
    assert year is not None and year.get("is_current") is True
    term = await gd_find_one(db.session, "academic_terms", {"school_id": wsid})
    assert term is not None and term.get("academic_year_id") == year["id"]
    teacher = await gd_find_one(db.session, "teachers", {"school_id": wsid})
    assert teacher is not None and teacher.get("user_id") == user["id"]
    refreshed = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert refreshed.get("tenant_id") == wsid
    assert refreshed.get("teacher_id") == teacher["id"]
    cls_count = await gd_count(db.session, "classes", {"school_id": wsid})
    assert cls_count == 1


@pytest.mark.asyncio
async def test_bootstrap_is_idempotent(client):
    user = await _mk_pre_bootstrap_it()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], None, mfa_recent_at=int(time.time()))

    first = await client.post(
        "/independent-teacher/bootstrap",
        headers=h,
        json=_bootstrap_payload(with_class=False),
    )
    assert first.status_code == 200, first.text

    schools_before = await gd_count(db.session, "schools", {"id": wsid})
    years_before = await gd_count(db.session, "academic_years", {"school_id": wsid})
    teachers_before = await gd_count(db.session, "teachers", {"school_id": wsid})

    # Replay — same caller, same payload. Should NOT duplicate.
    second = await client.post(
        "/independent-teacher/bootstrap",
        headers=h,
        json=_bootstrap_payload(with_class=False),
    )
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["already_materialised"] is True
    assert body["workspace"]["workspace_id"] == wsid

    assert await gd_count(db.session, "schools", {"id": wsid}) == schools_before
    assert await gd_count(db.session, "academic_years", {"school_id": wsid}) == years_before
    assert await gd_count(db.session, "teachers", {"school_id": wsid}) == teachers_before


@pytest.mark.asyncio
async def test_bootstrap_rolls_back_on_mid_transaction_failure(client, monkeypatch):
    """If any insert inside the bootstrap transaction raises, NOTHING must
    persist (no schools / school_settings / academic_years / academic_terms
    / teachers / classes / subjects rows, and users.tenant_id is still
    NULL). Proves the all-or-nothing contract from the spec.
    """
    user = await _mk_pre_bootstrap_it()
    # Commit the fixture insert so the route's rollback below cannot
    # also wipe out the test's user row (TestClient + app share the
    # module-level `db.session`).
    await db.session.commit()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], None, mfa_recent_at=int(time.time()))

    # Patch gd_insert to fail when the route inserts the `teachers` row —
    # this is mid-transaction (schools / settings / year / term already
    # inserted in the same session) so the rollback must wipe everything.
    import routes.independent_teacher_bootstrap_routes as it_module

    real_gd_insert = it_module.gd_insert

    async def failing_gd_insert(session, collection: str, doc: dict):
        if collection == "teachers":
            raise RuntimeError("simulated DB failure on teachers insert")
        return await real_gd_insert(session, collection, doc)

    monkeypatch.setattr(it_module, "gd_insert", failing_gd_insert)

    resp = await client.post(
        "/independent-teacher/bootstrap",
        headers=h,
        json=_bootstrap_payload(with_class=True),
    )
    assert resp.status_code == 500, resp.text

    # Nothing landed.
    assert await gd_count(db.session, "schools", {"id": wsid}) == 0
    assert await gd_count(db.session, "school_settings", {"school_id": wsid}) == 0
    assert await gd_count(db.session, "academic_years", {"school_id": wsid}) == 0
    assert await gd_count(db.session, "academic_terms", {"school_id": wsid}) == 0
    assert await gd_count(db.session, "teachers", {"school_id": wsid}) == 0
    assert await gd_count(db.session, "classes", {"school_id": wsid}) == 0
    assert await gd_count(db.session, "subjects", {"school_id": wsid}) == 0

    # users.tenant_id is still NULL — caller can re-attempt bootstrap.
    refreshed = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert refreshed is not None
    assert refreshed.get("tenant_id") in (None, "")
