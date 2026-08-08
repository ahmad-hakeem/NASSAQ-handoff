"""Avatar payload-size contract.

Root cause this locks down: avatars are stored as base64 ``data:`` URIs
directly on ``users.avatar_url``, and every serializer that returns a user
(most visibly ``GET /auth/me``) ships those bytes inline. A measured
production account carried a 159,546-byte PNG, making ``/auth/me`` 160 kB —
99% of which was this single field (the same endpoint is 682 bytes for a
user with no avatar).

The frontend cropper only compresses when the cropped blob exceeds 500 kB,
so a 159 kB PNG reaches the server at full resolution, untouched. The fix is
server-side normalisation at every write site: no upload path may persist an
oversized image, regardless of what the client sends.
"""

import base64
import io

import pytest
from PIL import Image

from utils.avatar_image import (
    AVATAR_MAX_PX,
    AvatarImageError,
    normalize_avatar_data_url,
)


def _noise_image(size, mode="RGB"):
    """Random-noise image: incompressible, so it reliably produces a large
    encoded payload (a flat-colour image would compress to a few hundred
    bytes and make the size assertions vacuous)."""
    bands = [Image.effect_noise(size, 96).convert("L") for _ in range(3)]
    img = Image.merge("RGB", bands)
    if mode == "RGBA":
        # A real transparency gradient, not a fully-opaque alpha channel: an
        # opaque RGBA image is expected to be re-encoded as JPEG.
        img.putalpha(Image.linear_gradient("L").resize(size))
    return img


def _data_url(img, fmt="PNG"):
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    raw = buf.getvalue()
    mime = {"PNG": "png", "JPEG": "jpeg", "WEBP": "webp"}[fmt]
    return f"data:image/{mime};base64," + base64.b64encode(raw).decode(), len(raw)


def _decode(data_url):
    head, b64 = data_url.split(",", 1)
    return head, base64.b64decode(b64)


# --------------------------------------------------------------------------
# Unit contract
# --------------------------------------------------------------------------

def test_normalizes_oversized_png_to_small_bounded_jpeg():
    """A full-resolution PNG like the one found in production must come back
    dramatically smaller and bounded to AVATAR_MAX_PX."""
    src, raw_len = _data_url(_noise_image((1024, 1024)), fmt="PNG")
    # Guard: the fixture must actually be large, or this test proves nothing.
    assert raw_len > 150_000, f"fixture too small to be meaningful: {raw_len}"

    out = normalize_avatar_data_url(src)

    head, raw = _decode(out)
    assert head.startswith("data:image/")
    img = Image.open(io.BytesIO(raw))
    assert max(img.size) <= AVATAR_MAX_PX, f"not bounded: {img.size}"
    # The production payload was ~160 kB; anything in that class is a failure.
    assert len(raw) < 40_000, f"still oversized: {len(raw)}"
    assert len(raw) < raw_len / 4


def test_alpha_is_preserved_not_flattened_to_black():
    """The IT workspace logo reuses this field, so transparency must survive
    rather than being composited onto an arbitrary background."""
    src, _ = _data_url(_noise_image((800, 800), mode="RGBA"), fmt="PNG")

    out = normalize_avatar_data_url(src)

    _, raw = _decode(out)
    img = Image.open(io.BytesIO(raw))
    assert img.mode in ("RGBA", "LA", "P"), f"alpha lost: {img.mode}"
    assert max(img.size) <= AVATAR_MAX_PX


def test_small_image_is_still_bounded_and_reencoded():
    src, _ = _data_url(_noise_image((64, 64)), fmt="PNG")
    out = normalize_avatar_data_url(src)
    _, raw = _decode(out)
    # Never upscale a small avatar.
    assert Image.open(io.BytesIO(raw)).size == (64, 64)


@pytest.mark.parametrize("value", [None, "", "https://cdn.example.com/a.png", "/api/x.png"])
def test_non_data_urls_pass_through_untouched(value):
    """Plain URLs are a legitimate stored form and must not be mangled."""
    assert normalize_avatar_data_url(value) == value


def test_undecodable_payload_is_rejected():
    with pytest.raises(AvatarImageError):
        normalize_avatar_data_url("data:image/png;base64,####not-base64####")


def test_non_image_payload_is_rejected():
    payload = base64.b64encode(b"this is not an image at all").decode()
    with pytest.raises(AvatarImageError):
        normalize_avatar_data_url(f"data:image/png;base64,{payload}")


# --------------------------------------------------------------------------
# HTTP contract — the write paths must not be bypassable from the client
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_self_avatar_upload_is_normalized_and_me_stays_small(
    client, teacher_headers
):
    """End-to-end: even when the client posts a full-resolution image, the
    stored avatar — and therefore /auth/me — must stay small."""
    # 400x400 noise mirrors the production case (a ~159 kB PNG) while staying
    # under the endpoint's 2 MB upload cap, so this exercises normalisation
    # rather than the size guard.
    src, raw_len = _data_url(_noise_image((400, 400)), fmt="PNG")
    assert raw_len > 150_000

    res = await client.post(
        "/users/me/avatar", json={"image_data": src}, headers=teacher_headers
    )
    assert res.status_code == 200, res.text

    # Task #1139 — the upload response now returns a signed image URL, not
    # the stored base64. Fetch the bytes through it to assert normalisation.
    stored_url = res.json()["avatar_url"]
    assert stored_url.startswith("/api/users/"), stored_url
    # Image fetches require the image-access cookie (set by /auth/me).
    me0 = await client.get("/auth/me", headers=teacher_headers)
    from utils.avatar_serving import IMAGE_COOKIE_NAME, mint_image_access_cookie
    client.cookies.set(IMAGE_COOKIE_NAME, mint_image_access_cookie(
        me0.json()["id"], me0.json().get("tenant_id"), me0.json().get("role")))
    img_res = await client.get(stored_url.removeprefix("/api"))
    assert img_res.status_code == 200
    assert len(img_res.content) < raw_len / 4, "upload endpoint persisted the raw image"

    me = await client.get("/auth/me", headers=teacher_headers)
    assert me.status_code == 200, me.text
    # The regression being prevented: a six-figure /auth/me response.
    #
    # The ceiling is deliberately loose. Random noise is the worst case a JPEG
    # encoder can face, and the stored value is base64 (a further 4/3 inflation)
    # — real photographs at this bound land near 10-20 kB. The invariant that
    # actually caps the payload is the pixel bound asserted below; the byte
    # ceiling only guards against the original full-resolution regression.
    # Task #1139 tightened this further: the image is no longer inline at
    # all, so /auth/me is tiny regardless of the avatar.
    assert len(me.content) < 4_096, f"/auth/me still oversized: {len(me.content)}"
    assert max(Image.open(io.BytesIO(img_res.content)).size) <= AVATAR_MAX_PX


@pytest.mark.asyncio
async def test_profile_update_path_is_also_normalized(client, teacher_headers):
    """PUT /users/me/profile accepts avatar_url directly — it must not be an
    unnormalised back door around the upload endpoint."""
    src, _ = _data_url(_noise_image((400, 400)), fmt="PNG")

    res = await client.put(
        "/users/me/profile", json={"avatar_url": src}, headers=teacher_headers
    )
    assert res.status_code == 200, res.text

    me = await client.get("/auth/me", headers=teacher_headers)
    assert me.status_code == 200
    assert len(me.content) < 60_000, f"/auth/me still oversized: {len(me.content)}"
    assert len(me.content) < len(src) / 4, "no meaningful reduction"


@pytest.mark.asyncio
async def test_school_logo_write_path_is_also_normalized(
    client, school_admin_headers, tenant_a
):
    """School logos live in the same shape of field (``schools.logo_url``) and
    are rendered on every page header, so an unbounded logo is the same bug
    with a wider blast radius.

    ``PATCH /schools/{id}`` copies ``logo_url`` through a generic allow-list
    loop, which is exactly the kind of path that silently skips a guard added
    only to the dedicated upload endpoints.
    """
    src, raw_len = _data_url(_noise_image((600, 600)), fmt="PNG")

    res = await client.patch(
        f"/schools/{tenant_a}",
        json={"logo_url": src},
        headers=school_admin_headers,
    )
    assert res.status_code == 200, res.text

    # Task #1139 — responses now carry a signed URL; fetch through it to
    # assert the stored bytes were normalised.
    logo_url = res.json().get("logo_url")
    assert logo_url and logo_url.startswith(f"/api/schools/{tenant_a}/logo?"), logo_url
    from utils.avatar_serving import IMAGE_COOKIE_NAME, mint_image_access_cookie
    client.cookies.set(IMAGE_COOKIE_NAME, mint_image_access_cookie("qa-admin", tenant_a, "school_admin"))
    img = await client.get(logo_url.removeprefix("/api"))
    assert img.status_code == 200
    assert len(img.content) < raw_len / 4, "logo was stored unnormalised"
    assert max(Image.open(io.BytesIO(img.content)).size) <= AVATAR_MAX_PX


@pytest.mark.asyncio
async def test_oversized_image_field_is_rejected_not_stored(client, teacher_headers):
    """The size cap must apply to the profile path too, so no write site can
    hand a multi-megabyte string to the decoder."""
    res = await client.put(
        "/users/me/profile",
        json={"avatar_url": "data:image/png;base64," + "A" * (2 * 1024 * 1024)},
        headers=teacher_headers,
    )
    assert res.status_code == 413, res.text
