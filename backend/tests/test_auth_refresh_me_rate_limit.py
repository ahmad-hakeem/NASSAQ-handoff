"""Task #483 — rate limiting on /auth/refresh and /auth/me.

Covers:
  * normal login → refresh → me round-trip still works
  * RATE_LIMITS map exposes the two new entries
  * per-IP outer cap on /auth/refresh trips 429 with Retry-After
  * per-IP outer cap on /auth/me trips 429 with Retry-After
  * per-user inner cap on /auth/refresh trips 429 even from rotated IP
  * per-user inner cap on /auth/me trips 429 even from rotated IP
  * refresh-token rotation still rotates the JTI under the limiter
  * refresh-token reuse still revokes the family
  * 429 envelope is safe (no stack traces / PII)
"""
import os
import uuid

import pytest
import jwt as _jwt

os.environ.setdefault("MFA_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")

from src.core.middleware.rate_limiter import rate_store, RATE_LIMITS  # noqa: E402
from dependencies import (  # noqa: E402
    UserRole, hash_password, JWT_SECRET, JWT_ALGORITHM,
)
from engines.sql_utils import gd_insert  # noqa: E402
from dependencies import db  # noqa: E402

pytestmark = pytest.mark.asyncio

_PASS = "Test@1234!"


@pytest.fixture(autouse=True)
def _reset_rate_store():
    rate_store._store.clear()
    yield
    rate_store._store.clear()


async def _mk_login_user(tenant_id: str) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": tenant_id,
        "email": f"rl-{uid}@nassaq-test.com",
        "full_name": "rl user",
        "is_active": True,
        "password_hash": hash_password(_PASS),
    }
    await gd_insert(db.session, "users", user)
    return user


async def _login(client, user):
    r = await client.post(
        "/auth/login",
        json={"email": user["email"], "password": _PASS},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1. RATE_LIMITS table
# ---------------------------------------------------------------------------

async def test_refresh_and_me_in_rate_limits_map():
    refresh = RATE_LIMITS.get("/api/auth/refresh")
    me = RATE_LIMITS.get("/api/auth/me")
    assert refresh is not None and refresh["max"] >= 1 and refresh["window"] >= 60
    assert me is not None and me["max"] >= 1 and me["window"] >= 60


# ---------------------------------------------------------------------------
# 2. Happy path — login → refresh → me still works
# ---------------------------------------------------------------------------

async def test_happy_path_login_refresh_me(client, tenant_a):
    user = await _mk_login_user(tenant_a)
    tokens = await _login(client, user)

    r = await client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert r.status_code == 200, r.text
    rotated = r.json()

    me = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {rotated['access_token']}"},
    )
    assert me.status_code == 200, me.text
    assert me.json()["id"] == user["id"]


# ---------------------------------------------------------------------------
# 3. Refresh rotates JTI under the limiter
# ---------------------------------------------------------------------------

async def test_refresh_still_rotates_jti(client, tenant_a):
    user = await _mk_login_user(tenant_a)
    tokens = await _login(client, user)
    original_jti = _jwt.decode(
        tokens["refresh_token"], JWT_SECRET, algorithms=[JWT_ALGORITHM]
    )["jti"]

    r = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert r.status_code == 200
    new_jti = _jwt.decode(
        r.json()["refresh_token"], JWT_SECRET, algorithms=[JWT_ALGORITHM]
    )["jti"]
    assert new_jti != original_jti


# ---------------------------------------------------------------------------
# 4. Refresh-token reuse still revokes the family
# ---------------------------------------------------------------------------

async def test_refresh_reuse_still_revokes_family(client, tenant_a):
    user = await _mk_login_user(tenant_a)
    tokens = await _login(client, user)
    # first rotation succeeds
    r1 = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert r1.status_code == 200
    # replay of the original is reuse → 401 (family revoked)
    r2 = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert r2.status_code == 401, r2.text
    # and the rotated sibling is now killed too
    r3 = await client.post(
        "/auth/refresh", json={"refresh_token": r1.json()["refresh_token"]}
    )
    assert r3.status_code == 401, r3.text


# ---------------------------------------------------------------------------
# 5. Per-IP outer cap on /auth/refresh
# ---------------------------------------------------------------------------

async def test_refresh_per_ip_outer_429(client, tenant_a):
    user = await _mk_login_user(tenant_a)
    # Seed the per-IP bucket to the outer cap so the very next request 429s
    # at the middleware layer regardless of the body payload.
    limit = RATE_LIMITS["/api/auth/refresh"]["max"]
    for _ in range(limit):
        await rate_store.is_rate_limited(
            "127.0.0.1:/api/auth/refresh",
            limit, RATE_LIMITS["/api/auth/refresh"]["window"],
        )
    # Use a syntactically valid refresh token so we know we'd otherwise
    # reach the handler.
    tokens = await _login(client, user)
    # Reset the per-user inner bucket so it's not the one firing.
    await rate_store.forget(f"refresh_user:{user['id']}", 60)

    r = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert r.status_code == 429
    body = r.json()
    assert body.get("success") is False
    assert body["error"]["code"] == "RATE_LIMITED"
    assert r.headers.get("Retry-After")
    # no stack-trace / PII bleed
    assert "Traceback" not in r.text
    assert user["email"] not in r.text


# ---------------------------------------------------------------------------
# 6. Per-user inner cap on /auth/refresh — survives IP rotation
# ---------------------------------------------------------------------------

async def test_refresh_per_user_inner_429(client, tenant_a):
    user = await _mk_login_user(tenant_a)
    tokens = await _login(client, user)
    # Seed only the per-user bucket past its inner cap (20/60s).
    for _ in range(20):
        await rate_store.is_rate_limited(f"refresh_user:{user['id']}", 20, 60)
    # Keep the per-IP outer bucket clear so the inner cap is the one firing.
    await rate_store.forget("127.0.0.1:/api/auth/refresh", RATE_LIMITS["/api/auth/refresh"]["window"])

    r = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert r.status_code == 429
    assert r.headers.get("Retry-After")
    # Inner-cap 429 must not consume the refresh JTI: the same token still
    # rotates cleanly after we clear the bucket.
    await rate_store.forget(f"refresh_user:{user['id']}", 60)
    r2 = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert r2.status_code == 200, r2.text


# ---------------------------------------------------------------------------
# 7. Per-IP outer cap on /auth/me
# ---------------------------------------------------------------------------

async def test_me_per_ip_outer_429(client, tenant_a):
    user = await _mk_login_user(tenant_a)
    tokens = await _login(client, user)
    limit = RATE_LIMITS["/api/auth/me"]["max"]
    for _ in range(limit):
        await rate_store.is_rate_limited(
            "127.0.0.1:/api/auth/me",
            limit, RATE_LIMITS["/api/auth/me"]["window"],
        )
    await rate_store.forget(f"auth_me_user:{user['id']}", 60)

    r = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 429
    body = r.json()
    assert body.get("success") is False
    assert body["error"]["code"] == "RATE_LIMITED"
    assert r.headers.get("Retry-After")
    assert "Traceback" not in r.text


# ---------------------------------------------------------------------------
# 8. Per-user inner cap on /auth/me — survives IP rotation
# ---------------------------------------------------------------------------

async def test_me_per_user_inner_429(client, tenant_a):
    user = await _mk_login_user(tenant_a)
    tokens = await _login(client, user)
    for _ in range(60):
        await rate_store.is_rate_limited(f"auth_me_user:{user['id']}", 60, 60)
    await rate_store.forget("127.0.0.1:/api/auth/me", RATE_LIMITS["/api/auth/me"]["window"])

    r = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 429
    assert r.headers.get("Retry-After")
    body = r.json()
    # Inner-cap returns the Arabic detail wrapped in the standard envelope.
    assert body.get("success") is False
    # The Arabic message must not leak the user id / email.
    assert user["id"] not in r.text
    assert user["email"] not in r.text
