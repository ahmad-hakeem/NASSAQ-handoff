"""
Task #201 — IT §5.7 MFA step-up backfill tests.

Verifies that the six routes called out in the spec emit the canonical
step-up envelope as **HTTP 403** for Independent-Teacher (IT) callers
that lack a recent MFA assertion, while keeping behaviour for non-IT
roles unchanged.

The frontend axios interceptor (frontend/src/contexts/AuthContext.js)
only replays a request after step-up when:

    response.status == 403
    response.data.detail.code in {
        "MFA_STEPUP_REQUIRED",
        "MFA_PASSKEY_REQUIRED",
        "MFA_RESTORE_REQUIRED",
    }

A 401 with the same body would be treated as a hard logout, so the
HTTP status assertion below is the meaningful contract. The full
canonical envelope additionally carries `challenge_endpoint` (so the
FE knows where to start the WebAuthn challenge) and `max_age_seconds`
(so it can compute its replay clock).

Routes covered:
  1. PUT /users/me/profile                                  IT-conditional
  2. GET /export/report/{report_type}                       IT-conditional
  3. GET /export/attendance                                 IT-conditional
  4. GET /independent-teacher/schedule/export.pdf           IT-only (uncond.)
  5. PUT /students/{student_id}                             IT-conditional
  6. DELETE /parents/{parent_id}                            IT-conditional
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from auth_scope import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find_one, gd_insert


# ---------------------------------------------------------------------------
# Shared helpers (mirror of test_independent_teacher_invite_parent.py)
# ---------------------------------------------------------------------------

_STEP_UP_CODES = {
    "MFA_STEPUP_REQUIRED",
    "MFA_PASSKEY_REQUIRED",
    "MFA_RESTORE_REQUIRED",
}


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


async def _seed_active_passkey(user_id: str) -> None:
    await gd_insert(db.session, "mfa_factors", {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "kind": "webauthn",
        "is_active": True,
        "is_primary": True,
        "webauthn_credential_id": uuid.uuid4().bytes,
        "webauthn_public_key": b"\x00",
        "webauthn_sign_count": 0,
    })


async def _mk_it() -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-Workspace-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher",
    })
    await _seed_active_passkey(uid)
    return user


def _it_headers(user: dict, *, with_mfa: bool = True) -> dict:
    claims = {
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": independent_workspace_id(user),
    }
    if with_mfa:
        token = create_access_token(
            claims, mfa_recent_at=_now_ts(), mfa_kind="webauthn",
        )
    else:
        token = create_access_token(claims)
    return {"Authorization": f"Bearer {token}"}


def _stepup_envelope(body: dict) -> dict | None:
    """Extract the canonical step-up envelope from either the raw
    FastAPI ``{detail: {...}}`` shape or the wrapped
    ``{error: {...}, success: False}`` shape produced by the global
    exception middleware. Returns the envelope dict (with `code`,
    `challenge_endpoint`, `max_age_seconds`, ...) or ``None``.
    """
    for key in ("detail", "error"):
        node = body.get(key)
        if isinstance(node, dict) and node.get("code") in _STEP_UP_CODES:
            return node
    return None


def _assert_canonical_stepup_403(resp) -> None:
    """Assert the response is the canonical 403 step-up envelope the
    frontend axios interceptor will recognise + replay. Verifies all
    three required envelope fields: `code`, `challenge_endpoint`,
    `max_age_seconds`."""
    assert resp.status_code == 403, (resp.status_code, resp.text)
    body = resp.json()
    env = _stepup_envelope(body)
    assert env is not None, body
    assert env["code"] in _STEP_UP_CODES, env
    assert isinstance(env.get("challenge_endpoint"), str) \
        and env["challenge_endpoint"], env
    assert isinstance(env.get("max_age_seconds"), int) \
        and env["max_age_seconds"] > 0, env


def _assert_no_stepup(resp) -> None:
    """Assert the response is NOT a step-up challenge — i.e. either a
    success or a non-MFA error. Used on the IT-with-MFA path and on
    non-IT no-regression checks."""
    assert resp.status_code != 401, resp.text
    if resp.status_code == 403:
        env = _stepup_envelope(resp.json())
        assert env is None, env


async def _seed_it_student(wsid: str, *, parent_id: str | None = None) -> str:
    sid = str(uuid.uuid4())
    doc = {
        "id": sid,
        "school_id": wsid,
        "tenant_id": wsid,
        "full_name": "طالب",
        "is_active": True,
    }
    if parent_id:
        doc["parent_id"] = parent_id
    await gd_insert(db.session, "students", doc)
    return sid


async def _seed_it_parent(wsid: str) -> str:
    pid = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": pid,
        "full_name": f"Parent-{pid[:6]}",
        "school_id": wsid,
        "is_active": True,
    })
    return pid


# ---------------------------------------------------------------------------
# 1. PUT /users/me/profile  (IT-conditional)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_users_me_profile_it_no_mfa_returns_403_stepup(client, enforce_mfa):
    user = await _mk_it()
    resp = await client.put(
        "/users/me/profile",
        json={"title": "Mr"},
        headers=_it_headers(user, with_mfa=False),
    )
    _assert_canonical_stepup_403(resp)


@pytest.mark.asyncio
async def test_users_me_profile_it_with_mfa_succeeds(client):
    user = await _mk_it()
    resp = await client.put(
        "/users/me/profile",
        json={"title": "Mr", "preferred_language": "ar"},
        headers=_it_headers(user, with_mfa=True),
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_users_me_profile_principal_unaffected(
    client, school_principal_headers,
):
    """Principal without MFA must NOT be challenged: the helper is
    IT-conditional and must be a no-op for non-IT roles."""
    resp = await client.put(
        "/users/me/profile",
        json={"title": "Dr"},
        headers=school_principal_headers,
    )
    _assert_no_stepup(resp)


# ---------------------------------------------------------------------------
# 2. GET /export/report/{report_type}  (IT-conditional)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_export_report_it_no_mfa_returns_403_stepup(client, enforce_mfa):
    user = await _mk_it()
    resp = await client.get(
        "/export/report/timetable?format=pdf",
        headers=_it_headers(user, with_mfa=False),
    )
    _assert_canonical_stepup_403(resp)


@pytest.mark.asyncio
async def test_export_report_it_with_mfa_passes_stepup_gate(client):
    user = await _mk_it()
    resp = await client.get(
        "/export/report/timetable?format=pdf",
        headers=_it_headers(user, with_mfa=True),
    )
    _assert_no_stepup(resp)


@pytest.mark.asyncio
async def test_export_report_principal_unaffected(
    client, school_principal_headers,
):
    resp = await client.get(
        "/export/report/timetable?format=pdf",
        headers=school_principal_headers,
    )
    _assert_no_stepup(resp)


# ---------------------------------------------------------------------------
# 3. GET /export/attendance  (IT-conditional, IT now in role allow-list)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_export_attendance_it_no_mfa_returns_403_stepup(client, enforce_mfa):
    user = await _mk_it()
    resp = await client.get(
        "/export/attendance?start_date=2026-01-01&end_date=2026-01-07",
        headers=_it_headers(user, with_mfa=False),
    )
    _assert_canonical_stepup_403(resp)


@pytest.mark.asyncio
async def test_export_attendance_it_with_mfa_passes_stepup_gate(client):
    user = await _mk_it()
    resp = await client.get(
        "/export/attendance?start_date=2026-01-01&end_date=2026-01-07",
        headers=_it_headers(user, with_mfa=True),
    )
    _assert_no_stepup(resp)


@pytest.mark.asyncio
async def test_export_attendance_teacher_unaffected(
    client, teacher_headers,
):
    resp = await client.get(
        "/export/attendance?start_date=2026-01-01&end_date=2026-01-07",
        headers=teacher_headers,
    )
    _assert_no_stepup(resp)


# ---------------------------------------------------------------------------
# 4. GET /independent-teacher/schedule/export.pdf  (unconditional 403)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_it_schedule_export_pdf_no_mfa_returns_403_stepup(client, enforce_mfa):
    user = await _mk_it()
    resp = await client.get(
        "/independent-teacher/schedule/export.pdf",
        headers=_it_headers(user, with_mfa=False),
    )
    _assert_canonical_stepup_403(resp)


@pytest.mark.asyncio
async def test_it_schedule_export_pdf_with_mfa_passes_stepup_gate(client):
    user = await _mk_it()
    resp = await client.get(
        "/independent-teacher/schedule/export.pdf",
        headers=_it_headers(user, with_mfa=True),
    )
    _assert_no_stepup(resp)


# ---------------------------------------------------------------------------
# 5. PUT /students/{student_id}  (IT-conditional, IT now in role allow-list)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_students_put_it_no_mfa_returns_403_stepup(client, enforce_mfa):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    sid = await _seed_it_student(wsid)
    resp = await client.put(
        f"/students/{sid}",
        json={"full_name": "اسم محدث"},
        headers=_it_headers(user, with_mfa=False),
    )
    _assert_canonical_stepup_403(resp)


@pytest.mark.asyncio
async def test_students_put_it_with_mfa_succeeds(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    sid = await _seed_it_student(wsid)
    resp = await client.put(
        f"/students/{sid}",
        json={"full_name": "اسم محدث"},
        headers=_it_headers(user, with_mfa=True),
    )
    assert resp.status_code == 200, resp.text
    row = await gd_find_one(db.session, "students", {"id": sid})
    assert row["full_name"] == "اسم محدث"


@pytest.mark.asyncio
async def test_students_put_principal_unaffected(
    client, school_principal_headers, a_student,
):
    resp = await client.put(
        f"/students/{a_student['id']}",
        json={"full_name": "اسم محدث"},
        headers=school_principal_headers,
    )
    _assert_no_stepup(resp)


# ---------------------------------------------------------------------------
# 6. DELETE /parents/{parent_id}  (IT-conditional, IT now in role allow-list)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_parents_delete_it_no_mfa_returns_403_stepup(client, enforce_mfa):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    pid = await _seed_it_parent(wsid)
    resp = await client.delete(
        f"/parents/{pid}",
        headers=_it_headers(user, with_mfa=False),
    )
    _assert_canonical_stepup_403(resp)


@pytest.mark.asyncio
async def test_parents_delete_it_with_mfa_succeeds(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    pid = await _seed_it_parent(wsid)
    resp = await client.delete(
        f"/parents/{pid}",
        headers=_it_headers(user, with_mfa=True),
    )
    assert resp.status_code == 200, resp.text
    assert await gd_find_one(db.session, "parents", {"id": pid}) is None


@pytest.mark.asyncio
async def test_parents_delete_principal_unaffected(
    client, school_principal_headers, a_student,
):
    resp = await client.delete(
        f"/parents/{a_student['parent_id']}",
        headers=school_principal_headers,
    )
    _assert_no_stepup(resp)
