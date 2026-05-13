"""Regression: /auth/me must expose ``mfa_enrolled_at``.

Without this field on UserResponse, the FE first-login orchestration
(LoginPage.resolveRedirectTarget, RouteGuards IT MFA gate, MfaEnrollPage
Continue button) treats every user as un-enrolled and bounces them
back to /auth/mfa/enroll on every login — even after they have already
enrolled a second factor. See the post-MFA continuation bug fix.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert
from shared_models import UserResponse


def _bearer(user_id: str, role: str, tenant_id: str | None = None) -> dict:
    claims = {"sub": user_id, "role": role}
    if tenant_id:
        claims["tenant_id"] = tenant_id
    return {"Authorization": f"Bearer {create_access_token(claims)}"}


def test_user_response_schema_exposes_mfa_enrolled_at():
    """Pydantic schema must declare the field — guards against future
    accidental drops from UserResponse."""
    assert "mfa_enrolled_at" in UserResponse.model_fields


@pytest.mark.asyncio
async def test_auth_me_returns_mfa_enrolled_at_when_enrolled(client):
    enrolled_iso = datetime.now(timezone.utc).isoformat()
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-enrolled-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": enrolled_iso,
    })

    resp = await client.get(
        "/auth/me",
        headers=_bearer(uid, UserRole.INDEPENDENT_TEACHER.value),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "mfa_enrolled_at" in body, list(body.keys())
    assert body["mfa_enrolled_at"], (
        "mfa_enrolled_at must be truthy for an enrolled user — without "
        "this the FE will bounce the user back to /auth/mfa/enroll on "
        "every login."
    )


@pytest.mark.asyncio
async def test_auth_me_returns_null_mfa_enrolled_at_when_not_enrolled(client):
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-fresh-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    })

    resp = await client.get(
        "/auth/me",
        headers=_bearer(uid, UserRole.INDEPENDENT_TEACHER.value),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "mfa_enrolled_at" in body
    assert body["mfa_enrolled_at"] is None
