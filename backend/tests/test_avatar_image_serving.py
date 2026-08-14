"""Task #1139 — avatars/logos served from dedicated signed-URL endpoints.

Locks down the two contracts:

1. Serializers (``/auth/me`` most visibly) return a signed URL instead of the
   inline base64 payload, so the response is small and the image cacheable.
2. The image endpoint authorises via the HMAC signature: unauthenticated
   requests (no/invalid sig), forged cross-entity requests, and expired
   signatures all fail closed — a child's photo is never publicly guessable.
"""

import base64
import io
import time
import uuid

import pytest
from PIL import Image

from dependencies import db, create_access_token
from engines.sql_utils import gd_insert
from src.common.utils.avatar_serving import (
    IMAGE_COOKIE_NAME,
    content_version,
    mint_image_access_cookie,
    signed_image_url,
    verify_signature,
    _signature,
)


def _img_cookie(client, uid, tenant_id=None, role="teacher"):
    """Simulate the HttpOnly image-access cookie set by login//auth/me."""
    client.cookies.set(IMAGE_COOKIE_NAME, mint_image_access_cookie(uid, tenant_id, role))


def _tiny_avatar_data_url() -> str:
    img = Image.new("RGB", (8, 8), (200, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


async def _mk_user(avatar=None, role="teacher", tenant_id=None):
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "email": f"{uid[:8]}@test.local",
        "password_hash": "x",
        "full_name": "مستخدم اختبار حقيقي",
        "role": role,
        "tenant_id": tenant_id,
        "avatar_url": avatar,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00+00:00",
    })
    return uid


def _auth(uid, role="teacher", tenant_id=None):
    token = create_access_token({"sub": uid, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


async def _mk_school(logo=None):
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid,
        "name": "مدرسة اختبار حقيقية",
        "code": f"sch-{sid[:8]}",
        "logo_url": logo,
        "status": "active",
        "is_active": True,
        "created_at": "2026-01-01T00:00:00+00:00",
    })
    return sid


async def _email_of(uid):
    from engines.sql_utils import gd_find_one
    row = await gd_find_one(db.session, "users", {"id": uid})
    return row["email"]


def _parse_query(url):
    from urllib.parse import urlparse, parse_qs
    q = parse_qs(urlparse(url).query)
    return {k: v[0] for k, v in q.items()}


# ---------------------------------------------------------------------------
# URL minting / helper contract
# ---------------------------------------------------------------------------

def test_signed_url_passthrough_for_non_data_values():
    assert signed_image_url("avatar", "u1", None) is None
    assert signed_image_url("avatar", "u1", "") == ""
    assert signed_image_url("avatar", "u1", "https://cdn.example/x.png") == "https://cdn.example/x.png"


def test_signed_url_shape_and_stability():
    data = _tiny_avatar_data_url()
    url1 = signed_image_url("avatar", "u1", data)
    url2 = signed_image_url("avatar", "u1", data)
    # Stable within the day → browser cache key is stable.
    assert url1 == url2
    assert url1.startswith("/api/users/u1/avatar?")
    q = _parse_query(url1)
    assert verify_signature("avatar", "u1", q["v"], int(q["exp"]), q["sig"])
    # A signature for the avatar kind must not validate for the logo route.
    assert not verify_signature("logo", "u1", q["v"], int(q["exp"]), q["sig"])
    # ...nor for a different entity id (cross-user/cross-tenant forgery).
    assert not verify_signature("avatar", "u2", q["v"], int(q["exp"]), q["sig"])


def test_expired_signature_rejected():
    exp = int(time.time()) - 10
    sig = _signature("avatar", "u1", "deadbeef", exp)
    assert not verify_signature("avatar", "u1", "deadbeef", exp, sig)


# ---------------------------------------------------------------------------
# HTTP contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auth_me_returns_url_not_base64(client):
    data = _tiny_avatar_data_url()
    uid = await _mk_user(avatar=data)
    r = await client.get("/auth/me", headers=_auth(uid))
    assert r.status_code == 200
    avatar = r.json()["avatar_url"]
    assert avatar.startswith(f"/api/users/{uid}/avatar?")
    assert "base64" not in avatar
    # The whole payload is now small — the base64 image is gone.
    assert len(r.content) < 4096


@pytest.mark.asyncio
async def test_avatar_endpoint_serves_bytes_with_cache_headers(client):
    data = _tiny_avatar_data_url()
    uid = await _mk_user(avatar=data)
    me = await client.get("/auth/me", headers=_auth(uid))
    url = me.json()["avatar_url"].removeprefix("/api")
    _img_cookie(client, uid)

    # No Authorization header — the signature alone authorises.
    r = await client.get(url)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.headers["cache-control"] == "private, max-age=86400"
    etag = r.headers["etag"]
    assert etag == f'"{content_version(data)}"'
    assert r.content == base64.b64decode(data.split(",", 1)[1])

    # Conditional revalidation → 304.
    r304 = await client.get(url, headers={"If-None-Match": etag})
    assert r304.status_code == 304


@pytest.mark.asyncio
async def test_unauthenticated_or_forged_requests_fail_closed(client):
    data = _tiny_avatar_data_url()
    uid = await _mk_user(avatar=data)
    other = await _mk_user(avatar=_tiny_avatar_data_url())
    q = _parse_query(signed_image_url("avatar", uid, data))

    # No signature at all (bare unauthenticated fetch) → validation error.
    r = await client.get(f"/users/{uid}/avatar")
    assert r.status_code in (400, 403, 422)

    # Garbage signature → 403.
    r = await client.get(f"/users/{uid}/avatar", params={"v": q["v"], "exp": q["exp"], "sig": "0" * 32})
    assert r.status_code == 403

    # Signature minted for user A replayed against user B (cross-tenant /
    # cross-user guessing) → 403, and B's photo is never returned.
    r = await client.get(f"/users/{other}/avatar", params=q)
    assert r.status_code == 403

    # Expired signature → 403.
    exp = int(time.time()) - 5
    r = await client.get(
        f"/users/{uid}/avatar",
        params={"v": q["v"], "exp": exp, "sig": _signature("avatar", uid, q["v"], exp)},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_stale_version_and_missing_avatar_404(client):
    uid = await _mk_user(avatar=None)
    _img_cookie(client, uid)
    # Valid signature over a version, but the user has no avatar.
    exp = int(time.time()) + 3600
    sig = _signature("avatar", uid, "aaaaaaaaaaaaaaaa", exp)
    r = await client.get(f"/users/{uid}/avatar", params={"v": "aaaaaaaaaaaaaaaa", "exp": exp, "sig": sig})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_school_logo_route(client, tenant_a):
    from engines.sql_utils import gd_update_one
    data = _tiny_avatar_data_url()
    await gd_update_one(db.session, "schools", {"id": tenant_a}, {"logo_url": data})
    url = signed_image_url("logo", tenant_a, data).removeprefix("/api")
    _img_cookie(client, str(uuid.uuid4()), tenant_id=tenant_a)
    r = await client.get(url)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_echoed_signed_url_does_not_clobber_stored_avatar(client):
    """Transition guard: older FE flows re-submit the whole profile object on
    save. The signed URL they now receive must be treated as "unchanged",
    never stored over the real image."""
    from engines.sql_utils import gd_find_one
    data = _tiny_avatar_data_url()
    uid = await _mk_user(avatar=data)
    headers = _auth(uid)
    url = (await client.get("/auth/me", headers=headers)).json()["avatar_url"]

    r = await client.put("/users/me/profile", json={"avatar_url": url, "phone": "0550000001"}, headers=headers)
    assert r.status_code == 200, r.text

    row = await gd_find_one(db.session, "users", {"id": uid})
    assert row["avatar_url"] == data, "signed URL overwrote the stored image"


@pytest.mark.asyncio
async def test_platform_users_list_carries_no_inline_base64(client):
    """List payloads must hand out signed URLs, never the stored base64."""
    data = _tiny_avatar_data_url()
    uid = await _mk_user(avatar=data)
    admin = await _mk_user(role="platform_admin")
    r = await client.get("/users/platform-users", params={"search": (await _email_of(uid)).split("@")[0]}, headers=_auth(admin, role="platform_admin"))
    assert r.status_code == 200
    assert "data:image/" not in r.text
    row = next(u for u in r.json()["users"] if u["id"] == uid)
    assert row["avatar_url"].startswith(f"/api/users/{uid}/avatar?")
    # The emitted URL must actually resolve.
    _img_cookie(client, admin, role="platform_admin")
    img = await client.get(row["avatar_url"].removeprefix("/api"))
    assert img.status_code == 200


@pytest.mark.asyncio
async def test_users_list_and_by_school_carry_no_inline_base64(client):
    """GET /users and GET /users/by-school must mint signed URLs too."""
    data = _tiny_avatar_data_url()
    uid = await _mk_user(avatar=data, role="teacher")
    admin = await _mk_user(role="platform_admin")

    from engines.sql_utils import gd_find_one, gd_update_one
    row = await gd_find_one(db.session, "users", {"id": uid})
    tenant = row.get("tenant_id")

    r = await client.get("/users", params={"tenant_id": tenant} if tenant else {}, headers=_auth(admin, role="platform_admin"))
    assert r.status_code == 200
    assert "data:image/" not in r.text
    mine = next((u for u in r.json() if u["id"] == uid), None)
    if mine is not None:  # 1000-row cap on a dirty DB may page it out
        assert mine["avatar_url"].startswith(f"/api/users/{uid}/avatar?")
        _img_cookie(client, admin, role="platform_admin")
        img = await client.get(mine["avatar_url"].removeprefix("/api"))
        assert img.status_code == 200

    r2 = await client.get("/users/by-school", headers=_auth(admin, role="platform_admin"))
    assert r2.status_code == 200
    assert "data:image/" not in r2.text


@pytest.mark.asyncio
async def test_school_list_and_detail_carry_no_inline_base64_logo(client):
    """GET /schools and GET /schools/{id} must emit signed logo URLs."""
    from engines.sql_utils import gd_update_one
    data = _tiny_avatar_data_url()
    sid = await _mk_school(logo=data)
    admin = await _mk_user(role="platform_admin")
    headers = _auth(admin, role="platform_admin")

    r = await client.get(f"/schools/{sid}", headers=headers)
    assert r.status_code == 200
    assert "data:image/" not in r.text
    url = r.json()["logo_url"]
    assert url.startswith(f"/api/schools/{sid}/logo?")
    _img_cookie(client, admin, role="platform_admin")
    img = await client.get(url.removeprefix("/api"))
    assert img.status_code == 200

    r2 = await client.get("/schools", headers=headers)
    assert r2.status_code == 200
    assert "data:image/" not in r2.text


@pytest.mark.asyncio
async def test_minted_url_is_not_a_shareable_bearer(client):
    """A legitimately minted URL must NOT be fetchable without the
    image-access cookie (forwarded-link replay) nor by a cross-tenant user."""
    data = _tiny_avatar_data_url()
    tenant = await _mk_school()
    uid = await _mk_user(avatar=data, tenant_id=tenant)
    url = signed_image_url("avatar", uid, data).removeprefix("/api")

    # 1. Unauthenticated replay of a valid URL → 401.
    client.cookies.clear()
    r = await client.get(url)
    assert r.status_code == 401

    # 2. Authenticated but different-tenant requester → 404 (no oracle).
    _img_cookie(client, str(uuid.uuid4()), tenant_id=str(uuid.uuid4()), role="teacher")
    r = await client.get(url)
    assert r.status_code == 404

    # 3. Same-tenant colleague → allowed.
    _img_cookie(client, str(uuid.uuid4()), tenant_id=tenant, role="teacher")
    assert (await client.get(url)).status_code == 200

    # 4. Cross-tenant school logo replay → 404 as well.
    sid = await _mk_school(logo=data)
    logo_url = signed_image_url("logo", sid, data).removeprefix("/api")
    client.cookies.clear()
    assert (await client.get(logo_url)).status_code == 401
    _img_cookie(client, str(uuid.uuid4()), tenant_id=str(uuid.uuid4()))
    assert (await client.get(logo_url)).status_code == 404
    _img_cookie(client, str(uuid.uuid4()), tenant_id=sid)
    assert (await client.get(logo_url)).status_code == 200


@pytest.mark.asyncio
async def test_auth_me_sets_image_access_cookie(client):
    uid = await _mk_user()
    r = await client.get("/auth/me", headers=_auth(uid))
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "")
    assert IMAGE_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
