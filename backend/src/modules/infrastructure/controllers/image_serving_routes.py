"""Task #1139 — dedicated image endpoints for user avatars and school logos.

Avatars/logos are stored as base64 ``data:`` URIs on ``users.avatar_url`` /
``schools.logo_url``. Serializers now return a short-lived HMAC-signed URL
(see ``utils/avatar_serving.py`` for the design rationale) pointing at these
endpoints, which serve the raw bytes with ``Cache-Control`` + ``ETag`` so the
browser fetches each image once instead of re-downloading it inline with
every ``/auth/me``.

Authorisation model — two independent factors, both required:

1. The HMAC signature in the query string binds WHAT may be fetched (entity
   id + content version + expiry). It cannot be forged or guessed, so photo
   URLs are not enumerable. It fails closed (403) before any row is read.
2. The HttpOnly image-access cookie (set alongside login/refresh//auth/me)
   identifies WHO is fetching — ``<img src>`` cannot attach a bearer header,
   but the browser sends the cookie automatically. Without it the request is
   401, so a signed URL forwarded to a third party is useless. The requester
   must then pass the same tenant rule as the serializers that minted the
   URL: self, same tenant, or a platform-level role — anything else is 404
   (indistinguishable from a missing image, no cross-tenant oracle).
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from dependencies import db
from engines.sql_utils import gd_find_one
from src.common.utils.avatar_serving import (
    IMAGE_COOKIE_NAME,
    content_version,
    decode_data_url,
    verify_image_access_cookie,
    verify_signature,
)

router = APIRouter()

_CACHE_CONTROL = "private, max-age=86400"

# Roles allowed to view images across tenant boundaries (platform staff).
_PLATFORM_ROLES = {
    "platform_admin",
    "platform_sub_admin",
    "platform_operations_manager",
    "ministry_rep",
}


def _authorized(kind: str, entity_id: str, row: dict, claims: dict) -> bool:
    """Mirror the serializers' tenant rule for the image bytes themselves."""
    role = claims.get("role")
    if role in _PLATFORM_ROLES:
        return True
    tenant = claims.get("tenant_id")
    if kind == "avatar":
        if claims.get("user_id") == entity_id:
            return True
        row_tenant = (row or {}).get("tenant_id")
        return bool(tenant) and tenant == row_tenant
    # logo: any member of the school may see its logo
    return bool(tenant) and tenant == entity_id


async def _serve(kind: str, table: str, column: str, entity_id: str,
                 v: str, exp: int, sig: str, request: Request) -> Response:
    # Fail closed BEFORE touching the row: an unauthenticated or tampered
    # request must not learn whether the entity even exists.
    if not verify_signature(kind, entity_id, v, exp, sig):
        raise HTTPException(status_code=403, detail="التوقيع غير صالح أو منتهي الصلاحية")

    # Requester authentication: a signed URL alone is a shareable string;
    # without a valid image-access cookie it must not yield the image.
    claims = verify_image_access_cookie(request.cookies.get(IMAGE_COOKIE_NAME))
    if claims is None:
        raise HTTPException(status_code=401, detail="غير مصرح")

    etag = f'"{v}"'
    headers = {"Cache-Control": _CACHE_CONTROL, "ETag": etag}

    row = await gd_find_one(db.session, table, {"id": entity_id})

    # Tenant authorization BEFORE any response that confirms content —
    # cross-tenant requesters get the same 404 as a missing image.
    if not _authorized(kind, entity_id, row or {}, claims):
        raise HTTPException(status_code=404, detail="الصورة غير موجودة")

    # Conditional revalidation for an authorized requester leaks nothing.
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)

    value = (row or {}).get(column)
    if not value or not isinstance(value, str) or not value.startswith("data:image/"):
        raise HTTPException(status_code=404, detail="الصورة غير موجودة")
    if content_version(value) != v:
        # Image changed since the URL was minted — the serializer will hand
        # out a fresh URL on the next payload.
        raise HTTPException(status_code=404, detail="الصورة غير موجودة")

    try:
        raw, media_type = decode_data_url(value)
    except ValueError:
        raise HTTPException(status_code=404, detail="الصورة غير موجودة")

    return Response(content=raw, media_type=media_type, headers=headers)


@router.get("/users/{user_id}/avatar")
async def get_user_avatar(
    user_id: str,
    request: Request,
    v: str = Query(...),
    exp: int = Query(...),
    sig: str = Query(...),
):
    return await _serve("avatar", "users", "avatar_url", user_id, v, exp, sig, request)


@router.get("/schools/{school_id}/logo")
async def get_school_logo(
    school_id: str,
    request: Request,
    v: str = Query(...),
    exp: int = Query(...),
    sig: str = Query(...),
):
    return await _serve("logo", "schools", "logo_url", school_id, v, exp, sig, request)
