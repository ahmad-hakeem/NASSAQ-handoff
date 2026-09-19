"""Regression coverage for the existing school lifecycle access policy.

The school suspension workflow is deliberately stronger than a presentation
status change: it deactivates every active user in the tenant.  Authentication
and all protected routes then reject both new logins and already-issued bearer
tokens through the canonical ``get_current_user`` dependency.

These tests drive the real login route and representative timetable and core
management routes.  They intentionally do not introduce a separate school
status gate or otherwise change authorization policy.
"""
from __future__ import annotations

import uuid

import pytest

from dependencies import UserRole, db, hash_password
from engines.sql_utils import gd_find_one, gd_insert
from src.modules.schools.dto.school_dto import SchoolStatusChangeRequest
from src.modules.schools.services.school_crud_service import SchoolCrudService


pytestmark = pytest.mark.asyncio

_PASSWORD = "Lifecycle@123!"


async def _seed_principal(school_id: str) -> dict:
    user_id = str(uuid.uuid4())
    principal = {
        "id": user_id,
        "email": f"lifecycle-{user_id}@nassaq-test.com",
        "password_hash": hash_password(_PASSWORD),
        "full_name": "Lifecycle Principal",
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "is_active": True,
    }
    await gd_insert(db.session, "users", principal)
    return principal


async def _login(client, principal: dict):
    return await client.post(
        "/auth/login",
        json={"email": principal["email"], "password": _PASSWORD},
    )


async def test_active_principal_can_login_and_reach_timetable_and_management(
    client, tenant_a
):
    principal = await _seed_principal(tenant_a)

    login = await _login(client, principal)

    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    timetable = await client.get("/timetable-readiness/check", headers=headers)
    management = await client.get("/classes/", headers=headers)

    assert timetable.status_code == 200, timetable.text
    assert management.status_code == 200, management.text


async def test_suspension_blocks_new_login_and_existing_token_on_core_routes(
    client, tenant_a
):
    principal = await _seed_principal(tenant_a)
    login = await _login(client, principal)
    assert login.status_code == 200, login.text
    stale_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}",
    }

    await SchoolCrudService.suspend_school(
        db.session,
        tenant_a,
        SchoolStatusChangeRequest(reason="Lifecycle access regression"),
        {
            "id": principal["id"],
            "role": UserRole.PLATFORM_ADMIN.value,
            "email": "platform-operator@nassaq-test.com",
            "full_name": "Platform Operator",
        },
    )

    stored_school = await gd_find_one(db.session, "schools", {"id": tenant_a})
    stored_principal = await gd_find_one(
        db.session, "users", {"id": principal["id"]}
    )
    assert stored_school["status"] == "suspended"
    assert stored_principal["is_active"] is False

    relogin = await _login(client, principal)
    timetable = await client.get(
        "/timetable-readiness/check", headers=stale_headers
    )
    management = await client.get("/classes/", headers=stale_headers)

    assert relogin.status_code == 401
    assert timetable.status_code == 401
    assert management.status_code == 401
    assert "access_token" not in relogin.json()