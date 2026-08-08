"""Server-side avatar/logo normalisation.

Avatars are persisted as base64 ``data:`` URIs on ``users.avatar_url`` and are
therefore shipped inline by every serializer that returns a user — most
visibly ``GET /auth/me``, which the app shell calls on each load. A measured
production account carried a 159,546-byte PNG, making that response 160 kB
where the same endpoint is 682 bytes for a user without an avatar.

The client-side cropper only compresses when the cropped blob exceeds 500 kB,
so full-resolution images reach the server untouched. Normalisation therefore
belongs on the server, at every write site, so no upload path can persist an
oversized image regardless of what the client sends.

``normalize_avatar_data_url`` is deliberately synchronous and pure: decoding
and resampling are CPU-bound and must not run inline on the event loop for
large inputs. Route handlers call it through ``normalize_avatar_data_url_async``,
which offloads to a worker thread.
"""

from __future__ import annotations

import asyncio
import base64
import io
from typing import Optional

from PIL import Image, ImageOps, UnidentifiedImageError

# Avatars render at 40-128 px across the app (sidebar, cards, tables); 256 px
# keeps them crisp on high-DPI displays without paying for anything larger.
AVATAR_MAX_PX = 256
_QUALITY = 82
_DATA_PREFIX = "data:image/"

# A modest base64 payload can still decode to an enormous raster. Reject on
# declared dimensions before allocating pixels (decompression-bomb guard).
#
# 16 MP is already far beyond any legitimate source for a 256 px avatar — a
# photo that large does not fit under MAX_IMAGE_FIELD_CHARS as a JPEG anyway —
# while capping the transient decode at roughly 48 MB of RGB per job.
_MAX_PIXELS = 16_000_000

# Upper bound on the raw field a client may send. Matches the cap the two
# dedicated upload endpoints already enforced.
MAX_IMAGE_FIELD_CHARS = 2 * 1024 * 1024

# --------------------------------------------------------------------------
# Persistence-layer bound
# --------------------------------------------------------------------------
# The two columns that ship inline with every user/school serializer. Any
# ``data:`` URI stored here must be the OUTPUT of normalisation — never a raw
# client upload. The generic write helpers (``engines.sql_utils.gd_*``)
# enforce this, so a new route that forgets ``normalize_image_field_or_400``
# fails loudly at the write instead of silently persisting a bloated image.
BOUNDED_IMAGE_COLUMNS = {
    ("users", "avatar_url"),
    ("schools", "logo_url"),
}

# Worst case ever produced by normalize_avatar_data_url — 256 px random noise
# with a real alpha channel — measures ~18k chars as a base64 WEBP. 64k gives
# generous headroom for encoder drift while still rejecting even a modest
# unnormalised upload (the original production regression was a 159 kB PNG,
# ~213k chars as base64).
MAX_STORED_IMAGE_CHARS = 64_000


class OversizedImageWriteError(ValueError):
    """A write tried to persist an unbounded image on a guarded column.

    This always means a route skipped ``normalize_image_field_or_400`` —
    it is a programming error, not bad user input.
    """


def assert_stored_image_bounded(collection: str, key: str, value) -> None:
    """Reject a ``data:`` URI that is too large to be a normalised image.

    Plain URLs, ``None`` and non-strings pass through: only inline image
    payloads are bounded.
    """
    if (collection, key) not in BOUNDED_IMAGE_COLUMNS:
        return
    if (
        isinstance(value, str)
        and value.startswith(_DATA_PREFIX)
        and len(value) > MAX_STORED_IMAGE_CHARS
    ):
        raise OversizedImageWriteError(
            f"refusing to store unnormalised image on {collection}.{key} "
            f"({len(value)} chars > {MAX_STORED_IMAGE_CHARS}); the write path "
            "must call utils.avatar_image.normalize_image_field_or_400 first"
        )


class AvatarImageError(ValueError):
    """Raised when a ``data:`` avatar payload cannot be decoded as an image.

    Callers map this to HTTP 400 — it always means client-supplied input was
    malformed, never an internal failure.
    """


def _uses_alpha(img: Image.Image) -> bool:
    """True only when the alpha channel actually carries transparency.

    A fully opaque RGBA image should still become JPEG: keeping it in an
    alpha-capable format costs bytes for no visual gain.
    """
    try:
        alpha = img.getchannel("A")
    except (ValueError, KeyError):
        return False
    return alpha.getextrema()[0] < 255


def normalize_avatar_data_url(
    value: Optional[str], *, max_px: int = AVATAR_MAX_PX
) -> Optional[str]:
    """Bound a stored avatar to ``max_px`` and re-encode it compactly.

    Non-``data:`` values (plain URLs, empty, ``None``) are returned unchanged —
    a stored HTTP URL is a legitimate form and must not be mangled.

    Raises:
        AvatarImageError: the payload claims to be an image but cannot be
            decoded, or its dimensions are implausibly large.
    """
    if not value or not isinstance(value, str):
        return value
    if not value.startswith(_DATA_PREFIX):
        return value

    if "," not in value:
        raise AvatarImageError("malformed data URL: missing base64 separator")
    _, b64 = value.split(",", 1)

    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception as exc:  # binascii.Error and friends
        raise AvatarImageError("invalid base64 image payload") from exc
    if not raw:
        raise AvatarImageError("empty image payload")

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            width, height = probe.size
            if width * height > _MAX_PIXELS:
                raise AvatarImageError("image dimensions too large")
            probe.load()
            # Honour EXIF orientation before resizing, or phone photos land
            # rotated once the tag is dropped by re-encoding.
            img = (ImageOps.exif_transpose(probe) or probe).copy()
    except AvatarImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise AvatarImageError("payload is not a decodable image") from exc

    if img.mode == "P":
        img = img.convert("RGBA" if "transparency" in img.info else "RGB")

    # Only ever downscale: upscaling a small avatar would add bytes and no detail.
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px), Image.LANCZOS)

    buf = io.BytesIO()
    if _uses_alpha(img):
        # WEBP keeps transparency (the IT workspace logo reuses this field)
        # at a fraction of PNG's size.
        img.save(buf, format="WEBP", quality=_QUALITY, method=4)
        mime = "webp"
    else:
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=_QUALITY, optimize=True, progressive=True)
        mime = "jpeg"

    return f"data:image/{mime};base64," + base64.b64encode(buf.getvalue()).decode()


async def normalize_avatar_data_url_async(
    value: Optional[str], *, max_px: int = AVATAR_MAX_PX
) -> Optional[str]:
    """Await-able wrapper that keeps decode/resample off the event loop.

    Runs on the project's bounded CPU pool rather than a bare thread: decoding
    an attacker-chosen image is memory-hungry, and the pool supplies admission
    control, a timeout and metrics that a plain thread hop does not.

    Skips the offload entirely for the common no-op cases (``None``, empty, or
    a plain URL) so ordinary profile updates pay nothing.
    """
    if not value or not isinstance(value, str) or not value.startswith(_DATA_PREFIX):
        return value

    # Imported lazily: utils/ is imported very early, services/ is not.
    from services.cpu_offload import run_cpu_bound

    return await run_cpu_bound(
        normalize_avatar_data_url, value, max_px=max_px, kind="image"
    )


async def normalize_image_field_or_400(value: Optional[str]) -> Optional[str]:
    """Route-facing wrapper: bound a client-supplied image field.

    Every avatar and logo write path goes through this, so the size cap, the
    resulting dimensions and the error contract stay identical no matter which
    endpoint the value arrived on.
    """
    from fastapi import HTTPException
    from services.cpu_offload import CpuOffloadBusy, CpuOffloadTimeout

    if isinstance(value, str) and len(value) > MAX_IMAGE_FIELD_CHARS:
        raise HTTPException(
            status_code=413,
            detail="حجم الصورة كبير جداً (الحد الأقصى 2MB) | Image too large (max 2MB)",
        )
    try:
        return await normalize_avatar_data_url_async(value)
    except AvatarImageError:
        raise HTTPException(
            status_code=400,
            detail="بيانات الصورة غير صالحة | Invalid image data",
        )
    except (CpuOffloadBusy, CpuOffloadTimeout):
        raise HTTPException(
            status_code=503,
            detail="تعذّر معالجة الصورة حالياً، حاول مرة أخرى | Image processing is busy, please retry",
        )
