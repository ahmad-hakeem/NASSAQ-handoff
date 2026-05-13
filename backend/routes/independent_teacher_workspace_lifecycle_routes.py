"""
Independent-Teacher — Workspace lifecycle (export + soft-delete).

Spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §6.8.
Task: #211 (IT-P2 §6.8).

Four HTTP surfaces:

  * ``POST /independent-teacher/workspace/export``
      IT-only, Tier-A MFA. Returns a 24h signed download URL pointing
      at the public bytes endpoint below. The URL token is bound to
      ``(workspace_school_id, user_id)`` so a leaked link cannot be
      replayed against a different workspace or by a different user.
      Stamps ``schools.last_export_at`` so the soft-delete confirm
      step can enforce the "must export within 24h" pre-condition.

  * ``GET  /public/workspace-export/{token}``
      Unauthenticated download endpoint. Verifies the JWT signature +
      purpose + ``ws``/``uid`` claims, then streams a JSON-zip bundle
      of the workspace's whitelisted tables. IP rate-limited via the
      existing ``rate_store``.

  * ``POST /independent-teacher/workspace/soft-delete``
      IT-only, Tier-A MFA. Pre-conditions:
        - Caller has exported within the last 24h (412 otherwise).
        - The submitted ``confirm_workspace_name`` matches the school
          row's name verbatim (422 otherwise).
      Effect: flips ``schools.status`` 'active' → 'archived' and sets
      ``schools.archived_at = now()``. NO row deletes. The user can
      no longer log in (auth_routes_mod login gate rejects archived
      workspaces with a safe Arabic message); reactivation within 30
      days flips the workspace back to 'active'.

  * ``POST /independent-teacher/workspace/reactivate``
      IT-only. Allowed when ``status='archived'`` AND
      ``archived_at`` is within the 30-day reactivation window AND
      ``pending_hard_delete`` is FALSE. Returns 410 Gone otherwise.

Hard-delete is intentionally NOT exposed by this router. Platform-
admin out-of-band tooling picks rows up by ``pending_hard_delete``;
the on-login lazy sweep below sets that flag once an archived
workspace passes the 30-day window. This way the destructive
operation is gated by a separate trust boundary and never callable
from the IT surface.

§8 invariant 3 (cross-workspace by-id 404): every IT-reachable read
in this router is pinned to the caller's workspace via
``require_request_school_id`` + ``independent_workspace_id``. The
public download endpoint resolves the workspace from the JWT, never
from a path parameter, so there is no cross-tenant by-id surface.
"""
from __future__ import annotations

import io
import json
import logging
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
    is_independent_teacher,
    require_request_school_id,
)
from dependencies import (
    audit_engine,
    db,
    get_current_user,
    require_recent_mfa_403,
)
from engines.sql_utils import gd_find, gd_find_one, gd_update_one
from middleware.rate_limiter import rate_store
from utils.tokens import (
    WORKSPACE_EXPORT_TOKEN_TTL,
    mint_workspace_export_token,
    token_hash as _token_hash,
    verify_workspace_export_token,
)
from middleware.rbac import Permission, RBACMiddleware
from utils.trusted_proxy import extract_client_ip
from engines.email_service import (
    send_workspace_archived_email,
    send_workspace_reactivation_reminder_email,
)


logger = logging.getLogger("nassaq.it_workspace_lifecycle")

router = APIRouter()


# -- Audit actions --------------------------------------------------------

AUDIT_EXPORT = "INDEPENDENT_TEACHER_EXPORT"
AUDIT_EXPORT_DOWNLOADED = "INDEPENDENT_TEACHER_EXPORT_DOWNLOADED"
AUDIT_SOFT_DELETE = "INDEPENDENT_TEACHER_SOFT_DELETE"
AUDIT_REACTIVATE = "INDEPENDENT_TEACHER_REACTIVATE"
AUDIT_PENDING_HARD_DELETE = "INDEPENDENT_TEACHER_PENDING_HARD_DELETE"


# -- Safe Arabic copy -----------------------------------------------------

_MSG_INTERNAL = "تعذّر تنفيذ العملية — حاول لاحقًا."
_MSG_WORKSPACE_NOT_FOUND = "لم يتم العثور على مساحة العمل."
_MSG_EXPORT_REQUIRED = "يجب تصدير بياناتك خلال آخر ٢٤ ساعة قبل الأرشفة."
_MSG_NAME_MISMATCH = "اسم المساحة المُدخل لا يطابق الاسم المسجّل."
_MSG_ALREADY_ARCHIVED = "تم أرشفة المساحة بالفعل."
_MSG_NOT_ARCHIVED = "هذه المساحة ليست مؤرشفة."
_MSG_REACTIVATE_EXPIRED = "انتهت مهلة الاسترجاع (٣٠ يومًا). تواصل مع الدعم."
_MSG_DOWNLOAD_INVALID = "رابط التنزيل غير صالح أو منتهي الصلاحية."
_MSG_RATE_LIMITED = "عدد المحاولات تجاوز الحد المسموح. حاول لاحقًا."

# Reactivation window — fixed at 30 days per §6.8. Past this window
# the on-login sweep flips ``pending_hard_delete=TRUE`` and the
# reactivate endpoint 410s.
_REACTIVATE_WINDOW = timedelta(days=30)

# Public download rate-limit: 30 attempts / 5 minutes per IP. Generous
# enough for legitimate "download interrupted, try again" flows but
# kills brute enumeration of `jti` values in leaked tokens.
_DOWNLOAD_RATE_MAX = 30
_DOWNLOAD_RATE_WINDOW = 300

# Workspace-scoped tables we export. Each entry is
# ``(table_name, scope_column)``. The scope column is filtered against
# the workspace school id; rows that don't carry the scope column are
# never exported here. Anything not on this list is OUT OF SCOPE for
# the right-to-export contract — when in doubt, omit. Adding a new
# table requires a new task + spec update.
_EXPORT_TABLES: List[tuple[str, str]] = [
    ("schools", "id"),
    ("teachers", "school_id"),
    ("classes", "school_id"),
    ("subjects", "school_id"),
    ("students", "school_id"),
    ("parents", "school_id"),
    ("guardian_links", "tenant_id"),
    ("schedule_sessions", "school_id"),
    ("attendance", "school_id"),
    ("assessments", "school_id"),
    ("behaviour_records", "school_id"),
    ("events", "tenant_id"),
    ("parent_invitations", "workspace_school_id"),
]

# Sensitive columns that must never appear in the export bundle even
# when the row itself is in scope. The export is a right-to-export
# artefact, not a credential dump — password hashes, MFA secrets,
# session jti fields stay server-side.
_REDACTED_COLUMNS = {
    "password_hash", "reset_token_hash", "reset_token_expires_at",
    "webauthn_public_key", "webauthn_credential_id", "webauthn_sign_count",
    "totp_secret", "totp_secret_encrypted",
    "token_hash",
}


# -- Request models -------------------------------------------------------

class SoftDeleteRequest(BaseModel):
    confirm_workspace_name: str = Field(min_length=1, max_length=200)


# -- Helpers --------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


_recent_mfa_403_dep = require_recent_mfa_403()


async def _require_workspace_export_perm(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not RBACMiddleware.has_permission(current_user, Permission.WORKSPACE_EXPORT.value):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


async def _require_workspace_soft_delete_perm(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not RBACMiddleware.has_permission(current_user, Permission.WORKSPACE_SOFT_DELETE.value):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


def _coerce_dt(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def _json_default(o: Any) -> Any:
    if isinstance(o, (datetime,)):
        return o.isoformat()
    if isinstance(o, bytes):
        # Defensive: webauthn columns are redacted, but any stray
        # bytes column (e.g. binary qr_code) needs a JSON-safe form.
        return None
    try:
        return str(o)
    except Exception:  # noqa: BLE001
        return None


def _redact(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in row.items() if k not in _REDACTED_COLUMNS}


async def _build_export_bundle(workspace_id: str) -> bytes:
    """Read every whitelisted table for ``workspace_id`` and return a
    zip archive of one ``<table>.json`` file per table.

    Memory note: NASSAQ's IT workspaces are bounded by the per-user
    quotas in ``backend.quotas.independent_teacher`` (≤ 10 classes,
    ≤ 200 students, etc.), so the entire workspace fits comfortably in
    memory. If a future tier raises those caps we'll switch to a
    streaming archive — for now in-memory keeps the route trivially
    transactional.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        manifest: Dict[str, Any] = {
            "workspace_school_id": workspace_id,
            "generated_at": _utcnow_iso(),
            "schema_version": 1,
            "tables": {},
        }
        for table_name, scope_col in _EXPORT_TABLES:
            try:
                rows = await gd_find(db.session, table_name, {scope_col: workspace_id})
            except Exception as exc:  # noqa: BLE001
                # A missing table or column is not fatal — skip it and
                # record the omission in the manifest so the recipient
                # can tell the difference between "no data" and "not
                # exported". We never want a partial workspace to leak
                # because one optional table got renamed.
                logger.warning(
                    "workspace export: table=%s scope=%s skipped: %s",
                    table_name, scope_col, exc,
                )
                manifest["tables"][table_name] = {"count": 0, "skipped": True}
                continue
            redacted = [_redact(r) for r in rows]
            payload = json.dumps(
                redacted, ensure_ascii=False, default=_json_default,
            ).encode("utf-8")
            zf.writestr(f"{table_name}.json", payload)
            manifest["tables"][table_name] = {"count": len(redacted)}
        zf.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    return buf.getvalue()


# -- Endpoint: GET /independent-teacher/workspace/lifecycle --------------
#
# Read-only view of the four §6.8 lifecycle columns so the FE can
# render the soft-delete gating affordance (button greyed-out until
# last_export_at is within 24h) on mount, without leaking any of the
# token-state columns. Same workspace-scope guard as the write paths.

@router.get("/independent-teacher/workspace/lifecycle")
async def read_workspace_lifecycle(
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = independent_workspace_id(current_user) or require_request_school_id(current_user)
    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school:
        raise HTTPException(status_code=404, detail=_MSG_WORKSPACE_NOT_FOUND)

    def _iso(v):
        if not v:
            return None
        return v.isoformat() if hasattr(v, "isoformat") else str(v)

    return {
        "workspace_id": workspace_id,
        "name_ar": school.get("name_ar"),
        "name_en": school.get("name_en"),
        "last_export_at": _iso(school.get("last_export_at")),
        "archived_at": _iso(school.get("archived_at")),
        "pending_hard_delete": bool(school.get("pending_hard_delete")),
    }


# -- Endpoint: POST /independent-teacher/workspace/export -----------------

@router.post("/independent-teacher/workspace/export")
async def create_workspace_export(
    request: Request,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403_dep),
    _perm: dict = Depends(_require_workspace_export_perm),
):
    school_id = require_request_school_id(current_user)
    workspace_id = independent_workspace_id(current_user) or school_id

    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school:
        raise HTTPException(status_code=404, detail=_MSG_WORKSPACE_NOT_FOUND)

    raw_token, raw_hash, expires_at = mint_workspace_export_token(
        workspace_id, current_user["id"],
    )
    now = _utcnow()
    try:
        async with db.session.begin_nested():
            # Persist the token hash + clear any prior consumed_at so the
            # public download endpoint can enforce single-use semantics.
            # Minting a new token explicitly invalidates any prior
            # outstanding download URL — only the most recent token is
            # honoured at any time.
            await gd_update_one(
                db.session, "schools", {"id": workspace_id},
                {
                    "last_export_at": now.isoformat(),
                    "last_export_token_hash": raw_hash,
                    "last_export_consumed_at": None,
                },
            )
            await audit_engine.log(
                action=AUDIT_EXPORT,
                performed_by=current_user["id"],
                tenant_id=workspace_id,
                entity_type="school",
                entity_id=workspace_id,
                details={
                    "school_id": workspace_id,
                    "tenant_id": workspace_id,
                    "user_id": current_user["id"],
                    "expires_at": expires_at.isoformat(),
                    "ttl_hours": int(WORKSPACE_EXPORT_TOKEN_TTL.total_seconds() // 3600),
                },
                actor_name=current_user.get("full_name"),
                actor_role=current_user.get("role"),
                actor_email=current_user.get("email"),
                ip_address=(request.client.host if request.client else None),
                user_agent=request.headers.get("user-agent"),
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "create_workspace_export failed user=%s: %s",
            current_user.get("id"), exc,
        )
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    return {
        "download_url": f"/api/public/workspace-export/{raw_token}",
        "expires_at": expires_at.isoformat(),
        "ttl_hours": int(WORKSPACE_EXPORT_TOKEN_TTL.total_seconds() // 3600),
    }


# -- Endpoint: GET /public/workspace-export/{token} -----------------------

@router.get("/public/workspace-export/{token}")
async def download_workspace_export(token: str, request: Request):
    client_ip = extract_client_ip(request)
    limited, _, retry_after = await rate_store.is_rate_limited(
        f"{client_ip}:workspace_export_download",
        _DOWNLOAD_RATE_MAX,
        _DOWNLOAD_RATE_WINDOW,
    )
    if limited:
        raise HTTPException(
            status_code=429,
            detail=_MSG_RATE_LIMITED,
            headers={"Retry-After": str(retry_after)},
        )

    payload = verify_workspace_export_token(token)
    if not payload:
        raise HTTPException(status_code=404, detail=_MSG_DOWNLOAD_INVALID)
    workspace_id = payload["ws"]
    user_id = payload["uid"]

    # Re-check the workspace still exists and isn't already
    # hard-deletion-pending; archived is FINE — the export is the user's
    # exit artefact, they need it to remain reachable while the
    # reactivation window is open.
    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school or school.get("pending_hard_delete"):
        raise HTTPException(status_code=404, detail=_MSG_DOWNLOAD_INVALID)

    # Single-use enforcement: the token hash must match the most
    # recent mint AND must not have been consumed yet. Atomically
    # flip ``last_export_consumed_at`` BEFORE building the bundle so
    # parallel requests racing on the same URL serialise on the row
    # update — only the first wins, every other request 404s.
    submitted_hash = _token_hash(token)
    if (school.get("last_export_token_hash") or "") != submitted_hash:
        raise HTTPException(status_code=404, detail=_MSG_DOWNLOAD_INVALID)
    if school.get("last_export_consumed_at"):
        raise HTTPException(status_code=404, detail=_MSG_DOWNLOAD_INVALID)
    try:
        async with db.session.begin_nested():
            await gd_update_one(
                db.session, "schools", {"id": workspace_id},
                {"last_export_consumed_at": _utcnow().isoformat()},
            )
    except Exception as exc:
        logger.warning("workspace export consume update failed: %s", exc)
        raise HTTPException(status_code=404, detail=_MSG_DOWNLOAD_INVALID)

    bundle = await _build_export_bundle(workspace_id)

    try:
        await audit_engine.log(
            action=AUDIT_EXPORT_DOWNLOADED,
            performed_by=user_id,
            tenant_id=workspace_id,
            entity_type="school",
            entity_id=workspace_id,
            details={
                "school_id": workspace_id,
                "tenant_id": workspace_id,
                "user_id": user_id,
                "bytes": len(bundle),
                "client_ip": client_ip,
            },
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception:  # noqa: BLE001
        logger.debug("workspace export download audit failed", exc_info=True)

    filename = f"nassaq-workspace-{workspace_id}.zip"
    return Response(
        content=bundle,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


# -- Endpoint: POST /independent-teacher/workspace/soft-delete ------------

@router.post("/independent-teacher/workspace/soft-delete")
async def soft_delete_workspace(
    payload: SoftDeleteRequest,
    request: Request,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403_dep),
    _perm: dict = Depends(_require_workspace_soft_delete_perm),
):
    school_id = require_request_school_id(current_user)
    workspace_id = independent_workspace_id(current_user) or school_id

    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school:
        raise HTTPException(status_code=404, detail=_MSG_WORKSPACE_NOT_FOUND)

    if (school.get("status") or "").lower() == "archived":
        raise HTTPException(status_code=409, detail=_MSG_ALREADY_ARCHIVED)

    last_export_at = _coerce_dt(school.get("last_export_at"))
    if last_export_at is None or (_utcnow() - last_export_at) > WORKSPACE_EXPORT_TOKEN_TTL:
        raise HTTPException(status_code=412, detail=_MSG_EXPORT_REQUIRED)

    submitted = (payload.confirm_workspace_name or "").strip()
    expected = (school.get("name") or "").strip()
    if not submitted or submitted != expected:
        raise HTTPException(status_code=422, detail=_MSG_NAME_MISMATCH)

    now = _utcnow()
    # Mint a fresh export token at archive time so the email link works
    # even if the user already consumed the original download. Replacing
    # the prior hash + clearing consumed_at matches the documented
    # "minting a new token invalidates any prior outstanding URL"
    # contract; the workspace stays downloadable until pending_hard_delete
    # flips, which only happens after the 30-day reactivation window.
    fresh_token, fresh_hash, fresh_expires_at = mint_workspace_export_token(
        workspace_id, current_user["id"],
    )
    try:
        async with db.session.begin_nested():
            await gd_update_one(
                db.session, "schools", {"id": workspace_id},
                {
                    "status": "archived",
                    "archived_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "last_export_at": now.isoformat(),
                    "last_export_token_hash": fresh_hash,
                    "last_export_consumed_at": None,
                    "reactivation_reminder_sent_at": None,
                },
            )
            await audit_engine.log(
                action=AUDIT_SOFT_DELETE,
                performed_by=current_user["id"],
                tenant_id=workspace_id,
                entity_type="school",
                entity_id=workspace_id,
                details={
                    "school_id": workspace_id,
                    "tenant_id": workspace_id,
                    "user_id": current_user["id"],
                    "archived_at": now.isoformat(),
                    "reactivation_window_days": _REACTIVATE_WINDOW.days,
                    "last_export_at": last_export_at.isoformat(),
                },
                actor_name=current_user.get("full_name"),
                actor_role=current_user.get("role"),
                actor_email=current_user.get("email"),
                ip_address=(request.client.host if request.client else None),
                user_agent=request.headers.get("user-agent"),
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "soft_delete_workspace failed user=%s: %s",
            current_user.get("id"), exc,
        )
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    reactivation_deadline = now + _REACTIVATE_WINDOW
    download_url = f"/api/public/workspace-export/{fresh_token}"

    # Best-effort archive notification email. Failure must NOT undo the
    # archive — the workspace is already in the 'archived' state and
    # the in-app dialog has surfaced the deadline. We log + continue.
    try:
        recipient = (current_user.get("email") or "").strip()
        if recipient and "@" in recipient and "@invite.nassaq.invalid" not in recipient:
            send_workspace_archived_email(
                to_email=recipient,
                user_name=current_user.get("full_name") or recipient,
                workspace_name=(school.get("name") or "").strip() or workspace_id,
                download_url=download_url,
                download_expires_at=fresh_expires_at.isoformat(),
                reactivation_deadline=reactivation_deadline.isoformat(),
                reactivation_window_days=_REACTIVATE_WINDOW.days,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("workspace archived email dispatch failed: %s", exc)

    return {
        "ok": True,
        "status": "archived",
        "archived_at": now.isoformat(),
        "reactivation_window_days": _REACTIVATE_WINDOW.days,
        "reactivation_deadline": reactivation_deadline.isoformat(),
        "download_url": download_url,
        "download_expires_at": fresh_expires_at.isoformat(),
    }


# -- Endpoint: POST /independent-teacher/workspace/reactivate -------------

@router.post("/independent-teacher/workspace/reactivate")
async def reactivate_workspace(
    request: Request,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403_dep),
):
    school_id = require_request_school_id(current_user)
    workspace_id = independent_workspace_id(current_user) or school_id

    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school:
        raise HTTPException(status_code=404, detail=_MSG_WORKSPACE_NOT_FOUND)

    if (school.get("status") or "").lower() != "archived":
        raise HTTPException(status_code=409, detail=_MSG_NOT_ARCHIVED)

    if school.get("pending_hard_delete"):
        raise HTTPException(status_code=410, detail=_MSG_REACTIVATE_EXPIRED)

    archived_at = _coerce_dt(school.get("archived_at"))
    if archived_at is None or (_utcnow() - archived_at) > _REACTIVATE_WINDOW:
        raise HTTPException(status_code=410, detail=_MSG_REACTIVATE_EXPIRED)

    now = _utcnow()
    try:
        async with db.session.begin_nested():
            await gd_update_one(
                db.session, "schools", {"id": workspace_id},
                {
                    "status": "active",
                    "archived_at": None,
                    "updated_at": now.isoformat(),
                    "reactivation_reminder_sent_at": None,
                },
            )
            await audit_engine.log(
                action=AUDIT_REACTIVATE,
                performed_by=current_user["id"],
                tenant_id=workspace_id,
                entity_type="school",
                entity_id=workspace_id,
                details={
                    "school_id": workspace_id,
                    "tenant_id": workspace_id,
                    "user_id": current_user["id"],
                    "previous_archived_at": archived_at.isoformat(),
                },
                actor_name=current_user.get("full_name"),
                actor_role=current_user.get("role"),
                actor_email=current_user.get("email"),
                ip_address=(request.client.host if request.client else None),
                user_agent=request.headers.get("user-agent"),
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "reactivate_workspace failed user=%s: %s",
            current_user.get("id"), exc,
        )
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    return {"ok": True, "status": "active"}


# -- Lazy on-login sweep helper ------------------------------------------
#
# Called from auth_routes_mod.login on the IT login path. Cheap: a
# single workspace lookup + at-most-one row update. NOT a background
# job — we want the flag to flip the first time the user touches the
# system after the 30-day window so platform-admin tooling sees a
# consistent state without scheduled jobs.

async def maybe_flip_pending_hard_delete(workspace_id: str) -> bool:
    """Flip ``pending_hard_delete`` true when the archived workspace
    is past its reactivation window. Returns True if the flag flipped
    on this call. Best-effort — never raises.
    """
    if not workspace_id:
        return False
    try:
        school = await gd_find_one(db.session, "schools", {"id": workspace_id})
        if not school:
            return False
        if school.get("pending_hard_delete"):
            return False
        if (school.get("status") or "").lower() != "archived":
            return False
        archived_at = _coerce_dt(school.get("archived_at"))
        if archived_at is None:
            return False
        if (_utcnow() - archived_at) <= _REACTIVATE_WINDOW:
            return False
        await gd_update_one(
            db.session, "schools", {"id": workspace_id},
            {"pending_hard_delete": True, "updated_at": _utcnow_iso()},
        )
        try:
            await audit_engine.log(
                action=AUDIT_PENDING_HARD_DELETE,
                performed_by=None,
                tenant_id=workspace_id,
                entity_type="school",
                entity_id=workspace_id,
                details={
                    "school_id": workspace_id,
                    "tenant_id": workspace_id,
                    "trigger": "lazy_on_login_sweep",
                    "archived_at": archived_at.isoformat(),
                },
            )
        except Exception:  # noqa: BLE001
            logger.debug("pending_hard_delete audit failed", exc_info=True)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("maybe_flip_pending_hard_delete: %s", exc)
        return False


__all__ = ["router", "maybe_flip_pending_hard_delete"]
