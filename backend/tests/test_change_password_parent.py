"""Task #470 — Parent change-password via canonical /auth/change-password.

Pins three contracts the Parent Account Settings dialog now relies on:

  1. Legacy `PUT /users/{user_id}/password` is gone. It used to raise
     `NameError: pwd_context` → HTTP 500 on every call. The handler was
     deleted; the router must now return 404 or 405 for that path.

  2. A Parent (Tier C) with a fresh `mfa_recent_at` claim can call
     `POST /auth/change-password` successfully: the stored hash rotates,
     the old password no longer verifies, and a `password_changed` audit
     row is written.

  3. Same path with the wrong current password returns the canonical
     400 + safe Arabic detail, and the stored hash is unchanged.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from dependencies import (
    UserRole,
    create_access_token,
    hash_password,
    verify_password,
    db,
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert


_PASS = "Old@1234!"
_NEW = "Brand@New4567!"


async def _mk_parent(tenant_id: str) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.PARENT.value,
        "tenant_id": tenant_id,
        "email": f"parent-{uid}@nassaq-test.com",
        "full_name": "Parent Test User",
        "is_active": True,
        "password_hash": hash_password(_PASS),
    }
    await gd_insert(db.session, "users", user)
    return user


def _parent_token_with_recent_mfa(user: dict) -> str:
    now = int(datetime.now(timezone.utc).timestamp())
    return create_access_token(
        {"sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"]},
        mfa_recent_at=now,
        mfa_kind="totp",
    )


@pytest.mark.asyncio
async def test_legacy_put_users_password_is_gone(client, parent_headers):
    """The broken duplicate handler must not be reachable on any verb."""
    fake_id = str(uuid.uuid4())
    r = await client.put(
        f"/users/{fake_id}/password",
        json={"current_password": "x", "new_password": "y"},
        headers=parent_headers,
    )
    assert r.status_code in {404, 405}, r.text


@pytest.mark.asyncio
async def test_parent_change_password_succeeds_and_rotates_hash(client, tenant_a):
    user = await _mk_parent(tenant_a)
    token = _parent_token_with_recent_mfa(user)

    r = await client.post(
        "/auth/change-password",
        json={"current_password": _PASS, "new_password": _NEW},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text

    fresh = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert verify_password(_NEW, fresh.get("password_hash") or "")
    assert not verify_password(_PASS, fresh.get("password_hash") or "")
    # last_password_change advanced — the response side-effect the FE
    # session-revocation path depends on.
    assert fresh.get("last_password_change")

    audit_rows = await gd_find(
        db.session,
        "audit_logs",
        {"target_id": user["id"], "action": "password_changed"},
    ) or []
    assert len(audit_rows) >= 1, "expected at least one password_changed audit row"


@pytest.mark.asyncio
async def test_parent_change_password_wrong_current_returns_arabic_400(client, tenant_a):
    user = await _mk_parent(tenant_a)
    token = _parent_token_with_recent_mfa(user)

    r = await client.post(
        "/auth/change-password",
        json={"current_password": "WRONG@Pass1!", "new_password": _NEW},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400, r.text

    body = r.json() or {}
    # Accept both wrapped envelope and raw FastAPI shape.
    msg = None
    err = body.get("error") if isinstance(body.get("error"), dict) else None
    if err:
        msg = err.get("message") or err.get("detail")
    if not msg:
        det = body.get("detail")
        msg = det if isinstance(det, str) else (det or {}).get("message") if isinstance(det, dict) else None
    assert isinstance(msg, str) and msg.strip(), f"missing Arabic detail: {body!r}"
    # The safe Arabic message must mention the current password.
    assert "كلمة المرور" in msg, f"unexpected message: {msg!r}"

    # Hash MUST be unchanged.
    fresh = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert verify_password(_PASS, fresh.get("password_hash") or "")


@pytest.mark.asyncio
async def test_parent_change_password_weak_new_password_returns_422(client, tenant_a):
    """Pydantic complexity validator must reject a too-short new password
    with the existing safe Arabic message; hash MUST be unchanged."""
    user = await _mk_parent(tenant_a)
    token = _parent_token_with_recent_mfa(user)

    r = await client.post(
        "/auth/change-password",
        json={"current_password": _PASS, "new_password": "abc1"},  # < 8 chars
        headers={"Authorization": f"Bearer {token}"},
    )
    # FastAPI surfaces field-validator failures as 422.
    assert r.status_code in {400, 422}, r.text
    body_text = r.text
    assert "كلمة المرور" in body_text, f"missing Arabic complexity message: {body_text!r}"

    fresh = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert verify_password(_PASS, fresh.get("password_hash") or "")


async def _mk_user_with_role(tenant_id: str, role: str) -> dict:
    """Lightweight user factory for the no-regression smoke pass.
    Avoids touching fixtures that own multi-role test data."""
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": role,
        "tenant_id": tenant_id,
        "email": f"{role}-{uid}@nassaq-test.com",
        "full_name": f"{role.title()} Smoke User",
        "is_active": True,
        "password_hash": hash_password(_PASS),
    }
    await gd_insert(db.session, "users", user)
    return user


@pytest.mark.parametrize(
    "role",
    [UserRole.SCHOOL_PRINCIPAL.value, UserRole.TEACHER.value, UserRole.SCHOOL_ADMIN.value],
)
@pytest.mark.asyncio
async def test_other_roles_change_password_smoke(client, tenant_a, role):
    """No-regression smoke: principal/teacher/school-admin can still
    change their password via /auth/change-password. Task #338/#351
    own the deep coverage; this just proves Task #470 did not break
    those paths."""
    user = await _mk_user_with_role(tenant_a, role)
    token = _parent_token_with_recent_mfa(user)  # token shape is role-agnostic

    r = await client.post(
        "/auth/change-password",
        json={"current_password": _PASS, "new_password": _NEW},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text

    fresh = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert verify_password(_NEW, fresh.get("password_hash") or "")
