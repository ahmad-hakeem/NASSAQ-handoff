"""Regression: /auth/me must expose ``updated_at``.

The account-settings header renders "آخر تحديث" from ``user.updated_at``
in AuthContext. UserResponse never declared the field, so every role
(school teacher, independent teacher, school principal, platform admin)
permanently showed the "—" fallback even though the users row keeps a
live ``updated_at`` (bumped by PUT /users/me/profile).
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


def test_user_response_schema_exposes_updated_at():
    assert "updated_at" in UserResponse.model_fields


ROLES = [
    ("teacher", True),
    ("independent_teacher", False),
    ("school_admin", True),
    ("platform_admin", False),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("role,needs_school", ROLES)
async def test_auth_me_returns_updated_at_for_all_roles(client, role, needs_school):
    uid = str(uuid.uuid4())
    stamp = datetime.now(timezone.utc).isoformat()
    tenant = None
    if needs_school:
        tenant = str(uuid.uuid4())
        await gd_insert(db.session, "schools", {
            "id": tenant,
            "name": f"مدرسة اختبار {tenant[:6]}",
            "code": f"SCH-{tenant[:8]}",
            "is_active": True,
        })
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": role,
        "tenant_id": tenant,
        "email": f"upd-{role}-{uid}@t.test",
        "full_name": f"U-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "updated_at": stamp,
    })

    resp = await client.get("/auth/me", headers=_bearer(uid, role, tenant))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "updated_at" in body, list(body.keys())
    assert body["updated_at"], (
        "updated_at must be a truthy ISO string so the settings header "
        "renders a real date instead of the '—' fallback."
    )
    # Must be parseable as a date by the FE (new Date(...)).
    datetime.fromisoformat(body["updated_at"])


@pytest.mark.asyncio
async def test_profile_save_bumps_auth_me_updated_at(client):
    """PUT /users/me/profile (title change) must be visible as a fresh
    updated_at on the next /auth/me — the refresh path the FE uses."""
    uid = str(uuid.uuid4())
    old = "2020-01-01T00:00:00+00:00"
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"upd-save-{uid}@t.test",
        "full_name": f"معلم اختبار {uid[:4]}",
        "is_active": True,
        "password_hash": "x",
        "updated_at": old,
    })
    headers = _bearer(uid, UserRole.INDEPENDENT_TEACHER.value)

    resp = await client.put(
        "/users/me/profile", headers=headers, json={"title": "السيد"}
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get("/auth/me", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "السيد"
    assert body["updated_at"] and body["updated_at"] != old
    assert datetime.fromisoformat(body["updated_at"]).year >= 2026
