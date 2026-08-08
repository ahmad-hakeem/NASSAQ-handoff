"""Regression: time_format, date_format, first_day_of_week must persist.

All three preference columns were missing from the users table so every
PUT /users/me/preferences silently dropped them and GET always returned the
hardcoded "12h" default regardless of what was saved.
"""
import uuid
import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


def _bearer(user_id: str, role: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user_id, 'role': role})}"}


async def _seed_user(role: str = UserRole.PLATFORM_ADMIN.value):
    """Platform admin has no workspace gate — good for pure preference tests."""
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": role, "tenant_id": None,
        "email": f"pref-{uid}@t.test",
        "full_name": f"مستخدم {uid[:4]}",
        "is_active": True, "password_hash": "x",
    })
    return uid


# ── save + retrieve ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_and_retrieve_24h(client):
    uid = await _seed_user()
    h = _bearer(uid, UserRole.PLATFORM_ADMIN.value)

    r = await client.put("/users/me/preferences", headers=h, json={"time_format": "24h"})
    assert r.status_code == 200, r.text

    r = await client.get("/users/me/preferences", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["time_format"] == "24h"


@pytest.mark.asyncio
async def test_save_and_retrieve_12h_after_24h(client):
    """Round-trip 24h → 12h must work (not stuck on 24h after switch)."""
    uid = await _seed_user()
    h = _bearer(uid, UserRole.PLATFORM_ADMIN.value)

    r = await client.put("/users/me/preferences", headers=h, json={"time_format": "24h"})
    assert r.status_code == 200, r.text
    r = await client.put("/users/me/preferences", headers=h, json={"time_format": "12h"})
    assert r.status_code == 200, r.text

    r = await client.get("/users/me/preferences", headers=h)
    assert r.json()["time_format"] == "12h"


@pytest.mark.asyncio
async def test_default_is_12h_for_new_user(client):
    uid = await _seed_user()
    h = _bearer(uid, UserRole.PLATFORM_ADMIN.value)
    r = await client.get("/users/me/preferences", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["time_format"] == "12h"


@pytest.mark.asyncio
async def test_date_format_persists(client):
    uid = await _seed_user()
    h = _bearer(uid, UserRole.PLATFORM_ADMIN.value)
    r = await client.put("/users/me/preferences", headers=h, json={"date_format": "yyyy-mm-dd"})
    assert r.status_code == 200
    r = await client.get("/users/me/preferences", headers=h)
    assert r.json()["date_format"] == "yyyy-mm-dd"


@pytest.mark.asyncio
async def test_first_day_of_week_persists(client):
    uid = await _seed_user()
    h = _bearer(uid, UserRole.PLATFORM_ADMIN.value)
    r = await client.put("/users/me/preferences", headers=h, json={"first_day_of_week": "monday"})
    assert r.status_code == 200
    r = await client.get("/users/me/preferences", headers=h)
    assert r.json()["first_day_of_week"] == "monday"


@pytest.mark.asyncio
async def test_save_only_time_format_leaves_other_prefs_intact(client):
    """Partial save must not reset other fields to defaults."""
    uid = await _seed_user()
    h = _bearer(uid, UserRole.PLATFORM_ADMIN.value)

    await client.put("/users/me/preferences", headers=h, json={"date_format": "mm/dd/yyyy"})
    await client.put("/users/me/preferences", headers=h, json={"time_format": "24h"})

    r = await client.get("/users/me/preferences", headers=h)
    assert r.json()["time_format"] == "24h"
    assert r.json()["date_format"] == "mm/dd/yyyy"


# ── auth/me carries time_format ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_auth_me_carries_time_format_after_save(client):
    """After saving 24h, /auth/me must expose time_format=24h so every
    component can read it via AuthContext without a separate prefs fetch."""
    uid = await _seed_user()
    h = _bearer(uid, UserRole.PLATFORM_ADMIN.value)

    r = await client.put("/users/me/preferences", headers=h, json={"time_format": "24h"})
    assert r.status_code == 200, r.text

    r = await client.get("/auth/me", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "time_format" in body, list(body.keys())
    assert body["time_format"] == "24h"


@pytest.mark.asyncio
async def test_auth_me_time_format_default_for_new_user(client):
    uid = await _seed_user()
    h = _bearer(uid, UserRole.PLATFORM_ADMIN.value)
    r = await client.get("/auth/me", headers=h)
    assert r.status_code == 200
    assert r.json().get("time_format") == "12h"


# ── all targeted roles (platform-level, no school FK required) ─────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("role", [
    UserRole.PLATFORM_ADMIN.value,
    UserRole.PLATFORM_SUB_ADMIN.value,
])
async def test_platform_roles_persist_time_format(client, role):
    uid = await _seed_user(role)
    h = _bearer(uid, role)
    r = await client.put("/users/me/preferences", headers=h, json={"time_format": "24h"})
    assert r.status_code == 200
    r = await client.get("/users/me/preferences", headers=h)
    assert r.json()["time_format"] == "24h"
