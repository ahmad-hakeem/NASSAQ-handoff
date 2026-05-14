"""Independent-Teacher §6.2b parent-invitation route tests.

Spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §6.2.
Task: #205.

Covers:
  * Create happy path + idempotent re-create.
  * Create cross-workspace student → 404.
  * Cancel happy path + illegal-state rejection.
  * Accept on the new-parent path (real email, no global collision).
  * Accept on each of the four dedupe paths
    (national_id / phone+email / phone / email) — including the
    global email-collision .invalid placeholder fallback that closes
    the Task #203 carryover.
  * Accept with tampered / expired / re-used token.
  * Accept rate-limit trip after the per-IP burst.
  * MFA step-up envelope on create + cancel surfaces.
  * §5.6 feature flag delegation (IT_PARENT_INVITATIONS_ENABLED=on).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from auth_scope import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one
from utils.tokens import token_hash as _token_hash

from tests._it_fixtures import (
    headers, mk_it_workspace, now_ts, seed_active_passkey, STEP_UP_CODES,
)


def _it_headers(ctx: dict, *, with_mfa: bool = True) -> dict:
    return headers(
        ctx["uid"], ctx["user"]["role"], ctx["wsid"],
        mfa_recent_at=now_ts() if with_mfa else None,
    )


async def _mk_pending_student(wsid: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": wsid,
        "tenant_id": wsid,
        "full_name": "طالب",
        "is_active": True,
    })
    return sid


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_invitation_happy_path(client):
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    sid = await _mk_pending_student(ctx["wsid"])
    h = _it_headers(ctx)

    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent-invitation",
        json={"parent_email": "newdad@example.com", "parent_phone": "+966500111111"},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "pending"
    assert data["channels"] == {"email": True, "sms": True}
    assert data["reused"] is False
    assert data["expires_at"]
    assert data.get("token")  # raw token returned exactly once

    # Audit row pinned to the workspace.
    audits = await gd_find(db.session, "audit_logs", {
        "action": "INDEPENDENT_TEACHER_INVITATION_CREATED",
        "entity_id": data["id"],
    })
    assert len(audits) == 1
    assert audits[0]["school_id"] == ctx["wsid"]
    assert audits[0]["details"]["student_id"] == sid


@pytest.mark.asyncio
async def test_create_invitation_is_idempotent(client):
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    sid = await _mk_pending_student(ctx["wsid"])
    h = _it_headers(ctx)

    body = {"parent_email": "newdad@example.com"}
    a = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent-invitation",
        json=body, headers=h,
    )
    assert a.status_code == 200, a.text
    b = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent-invitation",
        json=body, headers=h,
    )
    assert b.status_code == 200, b.text
    assert b.json()["id"] == a.json()["id"]
    assert b.json()["reused"] is True

    # Only one row exists.
    rows = await gd_find(db.session, "parent_invitations", {
        "workspace_school_id": ctx["wsid"],
        "student_id": sid,
        "status": "pending",
    })
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_create_invitation_cross_workspace_returns_404(client):
    ctx_a = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    ctx_b = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    sid_in_a = await _mk_pending_student(ctx_a["wsid"])

    h_b = _it_headers(ctx_b)
    resp = await client.post(
        f"/independent-teacher/students/{sid_in_a}/invite-parent-invitation",
        json={"parent_email": "x@x.com"}, headers=h_b,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_create_invitation_requires_identifier(client):
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    sid = await _mk_pending_student(ctx["wsid"])
    h = _it_headers(ctx)

    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent-invitation",
        json={}, headers=h,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_invitation_missing_mfa_emits_stepup_envelope(client):
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    sid = await _mk_pending_student(ctx["wsid"])
    h = _it_headers(ctx, with_mfa=False)

    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent-invitation",
        json={"parent_email": "x@x.com"}, headers=h,
    )
    assert resp.status_code == 403, resp.text
    body = resp.json()
    detail = body.get("detail") or (body.get("error") or {}).get("detail") or body.get("error")
    code = (detail or {}).get("code") if isinstance(detail, dict) else None
    assert code in STEP_UP_CODES


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_invitation_happy_path(client):
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    sid = await _mk_pending_student(ctx["wsid"])
    h = _it_headers(ctx)

    create = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent-invitation",
        json={"parent_email": "x@x.com"}, headers=h,
    )
    assert create.status_code == 200
    inv_id = create.json()["id"]

    cancel = await client.post(
        f"/independent-teacher/parent-invitations/{inv_id}/cancel", headers=h,
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled"

    audits = await gd_find(db.session, "audit_logs", {
        "action": "INDEPENDENT_TEACHER_INVITATION_CANCELLED",
        "entity_id": inv_id,
    })
    assert len(audits) == 1


@pytest.mark.asyncio
async def test_cancel_invitation_rejects_non_pending(client):
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    sid = await _mk_pending_student(ctx["wsid"])
    h = _it_headers(ctx)

    create = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent-invitation",
        json={"parent_email": "x@x.com"}, headers=h,
    )
    inv_id = create.json()["id"]
    # First cancel succeeds.
    first = await client.post(
        f"/independent-teacher/parent-invitations/{inv_id}/cancel", headers=h,
    )
    assert first.status_code == 200
    # Second cancel must 409.
    second = await client.post(
        f"/independent-teacher/parent-invitations/{inv_id}/cancel", headers=h,
    )
    assert second.status_code == 409, second.text


@pytest.mark.asyncio
async def test_cancel_invitation_cross_workspace_returns_404(client):
    ctx_a = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    ctx_b = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    sid = await _mk_pending_student(ctx_a["wsid"])

    create = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent-invitation",
        json={"parent_email": "x@x.com"}, headers=_it_headers(ctx_a),
    )
    inv_id = create.json()["id"]

    resp = await client.post(
        f"/independent-teacher/parent-invitations/{inv_id}/cancel",
        headers=_it_headers(ctx_b),
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Accept — happy path + dedupe paths
# ---------------------------------------------------------------------------

async def _seed_invitation(
    wsid: str, sid: str, *,
    parent_email: str | None = None,
    parent_phone: str | None = None,
) -> tuple[str, str]:
    """Mint a fresh invitation row directly + return (invitation_id, raw_token)."""
    from utils.tokens import mint_invitation_token
    raw, t_hash, expires_at = mint_invitation_token(wsid, sid)
    inv_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "parent_invitations", {
        "id": inv_id,
        "workspace_school_id": wsid,
        "student_id": sid,
        "parent_email": parent_email,
        "parent_phone": parent_phone,
        "token_hash": t_hash,
        "sent_at": now_iso,
        "expires_at": expires_at.isoformat(),
        "status": "pending",
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    return inv_id, raw


@pytest.mark.asyncio
async def test_accept_invitation_new_parent_happy_path(client):
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=False)
    sid = await _mk_pending_student(ctx["wsid"])
    inv_id, token = await _seed_invitation(
        ctx["wsid"], sid,
        parent_email=f"dad-{uuid.uuid4()}@example.com",
        parent_phone="+966500999000",
    )

    resp = await client.post(
        "/public/parent-invitations/accept",
        json={"token": token, "full_name": "أحمد"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["matched_by"] == "new"
    assert body["access_token"]
    parent_id = body["parent_id"]
    parent_user_id = body["parent_user_id"]

    inv = await gd_find_one(db.session, "parent_invitations", {"id": inv_id})
    assert inv["status"] == "accepted"
    assert inv["accepted_at"] is not None

    student = await gd_find_one(db.session, "students", {"id": sid})
    assert student["parent_id"] == parent_id

    user = await gd_find_one(db.session, "users", {"id": parent_user_id})
    assert user["role"] == "parent"
    assert user["tenant_id"] == ctx["wsid"]
    assert user["password_hash"] == "!invite-pending"
    assert "@example.com" in user["email"]  # real email, no collision

    links = await gd_find(db.session, "guardian_links", {"student_id": sid, "is_active": True})
    assert len(links) == 1
    assert links[0]["tenant_id"] == ctx["wsid"]
    assert links[0]["parent_ref"] == parent_user_id

    audits = await gd_find(db.session, "audit_logs", {
        "action": "INDEPENDENT_TEACHER_INVITATION_ACCEPTED",
        "entity_id": inv_id,
    })
    assert len(audits) == 1
    assert audits[0]["details"]["matched_by"] == "new"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["national_id", "phone_email", "phone", "email"])
async def test_accept_invitation_dedupes_each_path(client, path):
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=False)
    sid = await _mk_pending_student(ctx["wsid"])

    parent_id = str(uuid.uuid4())
    parent_email = f"dedup-{uuid.uuid4()}@example.com"
    parent_phone = "+966500777777"
    parent_nid = f"NID{uuid.uuid4().hex[:10]}"

    parents_row = {
        "id": parent_id,
        "full_name": "موجود",
        "school_id": ctx["wsid"],
        "is_active": True,
    }
    inv_email = None
    inv_phone = None
    accept_payload = {}

    if path == "national_id":
        parents_row["national_id"] = parent_nid
        inv_email = parent_email  # email present but mismatched on parents
        accept_payload["national_id"] = parent_nid
    elif path == "phone_email":
        parents_row["phone"] = parent_phone
        parents_row["email"] = parent_email
        inv_email = parent_email
        inv_phone = parent_phone
    elif path == "phone":
        parents_row["phone"] = parent_phone
        inv_phone = parent_phone
    elif path == "email":
        parents_row["email"] = parent_email
        inv_email = parent_email

    await gd_insert(db.session, "parents", parents_row)
    inv_id, token = await _seed_invitation(
        ctx["wsid"], sid, parent_email=inv_email, parent_phone=inv_phone,
    )

    resp = await client.post(
        "/public/parent-invitations/accept",
        json={"token": token, **accept_payload},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["matched_by"] == path
    assert body["parent_id"] == parent_id


@pytest.mark.asyncio
async def test_accept_invitation_email_collision_falls_back_to_invalid(client):
    """Dedupe path with global users.email collision → workspace user
    materialises with .invalid placeholder, never raises."""
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=False)
    sid = await _mk_pending_student(ctx["wsid"])

    colliding_email = f"collide-{uuid.uuid4()}@example.com"
    # Existing parents row in the same workspace (matches by email).
    parent_id = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": parent_id,
        "full_name": "موجود",
        "email": colliding_email,
        "school_id": ctx["wsid"],
        "is_active": True,
    })
    # And a global users row (different tenant) owning that email.
    other = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=False)
    await gd_insert(db.session, "users", {
        "id": str(uuid.uuid4()),
        "role": "parent",
        "tenant_id": other["wsid"],
        "email": colliding_email,
        "full_name": "آخر",
        "password_hash": "!seed",
        "is_active": True,
        "preferred_language": "ar",
        "preferred_theme": "light",
    })
    await db.session.flush()

    inv_id, token = await _seed_invitation(
        ctx["wsid"], sid, parent_email=colliding_email,
    )
    resp = await client.post(
        "/public/parent-invitations/accept",
        json={"token": token},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["matched_by"] == "email"
    user = await gd_find_one(db.session, "users", {"id": body["parent_user_id"]})
    assert user["email"].endswith("@invite.nassaq.invalid")
    assert user["email"] != colliding_email


# ---------------------------------------------------------------------------
# Accept — cross-tenant dedupe isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_accept_invitation_does_not_dedupe_cross_tenant_parent(client):
    """A parents row whose phone/email/national_id matches the invitation's
    contact details but belongs to a DIFFERENT IT workspace must NOT be
    reused.  A fresh parents row must be created in the invitation's own
    workspace instead, preventing cross-tenant family merges."""
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=False)
    other = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=False)
    sid = await _mk_pending_student(ctx["wsid"])

    shared_email = f"shared-{uuid.uuid4()}@example.com"
    other_parent_id = str(uuid.uuid4())
    # Seed a parent in the OTHER workspace with the same email address.
    await gd_insert(db.session, "parents", {
        "id": other_parent_id,
        "full_name": "والد مدرسة أخرى",
        "email": shared_email,
        "school_id": other["wsid"],
        "is_active": True,
    })

    inv_id, token = await _seed_invitation(
        ctx["wsid"], sid, parent_email=shared_email,
    )
    resp = await client.post(
        "/public/parent-invitations/accept",
        json={"token": token},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # The returned parent_id must NOT be the cross-workspace record.
    assert body["parent_id"] != other_parent_id, (
        "Cross-tenant parent row must not be reused during invitation accept"
    )
    # A brand-new parents row must have been created in the invitation workspace.
    new_parent = await gd_find_one(db.session, "parents", {"id": body["parent_id"]})
    assert new_parent is not None
    assert new_parent["school_id"] == ctx["wsid"]
    # The cross-tenant record must be completely untouched.
    other_p = await gd_find_one(db.session, "parents", {"id": other_parent_id})
    assert other_p["school_id"] == other["wsid"]


# ---------------------------------------------------------------------------
# Accept — error paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_accept_invitation_rejects_tampered_token(client):
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=False)
    sid = await _mk_pending_student(ctx["wsid"])
    inv_id, token = await _seed_invitation(ctx["wsid"], sid, parent_email="x@x.com")

    resp = await client.post(
        "/public/parent-invitations/accept",
        json={"token": token + "tamper"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_accept_invitation_rejects_expired_token(client):
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=False)
    sid = await _mk_pending_student(ctx["wsid"])
    inv_id, token = await _seed_invitation(ctx["wsid"], sid, parent_email="x@x.com")
    # Force expiry.
    await gd_update_one(
        db.session, "parent_invitations", {"id": inv_id},
        {"expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()},
    )

    resp = await client.post(
        "/public/parent-invitations/accept",
        json={"token": token},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_accept_invitation_rejects_replay(client):
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=False)
    sid = await _mk_pending_student(ctx["wsid"])
    _, token = await _seed_invitation(ctx["wsid"], sid, parent_email=f"r-{uuid.uuid4()}@x.com")

    first = await client.post(
        "/public/parent-invitations/accept", json={"token": token},
    )
    assert first.status_code == 200, first.text
    second = await client.post(
        "/public/parent-invitations/accept", json={"token": token},
    )
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_accept_invitation_rate_limit_trips(client):
    """Per-IP burst beyond the configured cap returns 429."""
    from middleware.rate_limiter import rate_store
    # Reset our key by burning through with garbage tokens until 429.
    saw_429 = False
    for _ in range(15):
        r = await client.post(
            "/public/parent-invitations/accept",
            json={"token": "totallybogus" + uuid.uuid4().hex},
        )
        if r.status_code == 429:
            saw_429 = True
            break
    assert saw_429, "expected rate-limit trip after the per-IP burst"


# ---------------------------------------------------------------------------
# §5.6 feature-flag delegation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_legacy_invite_parent_delegates_when_flag_enabled(client):
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    sid = await _mk_pending_student(ctx["wsid"])
    h = _it_headers(ctx)

    with patch.dict(os.environ, {"IT_PARENT_INVITATIONS_ENABLED": "1"}):
        resp = await client.post(
            f"/independent-teacher/students/{sid}/invite-parent",
            json={
                "full_name": "ولي مدعو",
                "email": "flag-on@example.com",
                "phone": "+966500606060",
            },
            headers=h,
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # Delegation went through the §6.2b create endpoint.
    assert data["status"] == "pending"
    assert data["channels"] == {"email": True, "sms": True}

    # Student MUST NOT have been linked — the envelope is async.
    student = await gd_find_one(db.session, "students", {"id": sid})
    assert student.get("parent_id") is None


# ---------------------------------------------------------------------------
# Task #277 — accept response surfaces inviter teacher + workspace name
# (purely additive — preserves existing keys).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_accept_response_includes_inviter_and_workspace_names(client):
    """The §6.2b accept route must additively expose `inviter_teacher_name`,
    `workspace_name` and `student_name` so the parent landing can render
    a branded welcome card after a successful accept (Task #277). The
    legacy keys (`access_token`, `student_id`, `parent_user_id`, …) MUST
    keep flowing unchanged so older clients are not broken.
    """
    # Reset the per-IP accept rate-limit bucket so prior tests in the
    # same module don't push us over the burst cap.
    from middleware.rate_limiter import rate_store
    rate_store._store.clear()

    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=False)
    sid = await _mk_pending_student(ctx["wsid"])

    # Backfill `created_by` on the invitation row so the accept handler
    # can resolve the inviting teacher's display name.
    inv_id, token = await _seed_invitation(
        ctx["wsid"], sid,
        parent_email=f"polish-{uuid.uuid4()}@example.com",
        parent_phone="+966500111222",
    )
    await gd_update_one(
        db.session, "parent_invitations", {"id": inv_id},
        {"$set": {"created_by": ctx["uid"]}},
    )
    # Give the student a recognisable display name to verify the new
    # `student_name` field on the response.
    await gd_update_one(
        db.session, "students", {"id": sid},
        {"$set": {"full_name": "طالب الترحيب"}},
    )

    resp = await client.post(
        "/public/parent-invitations/accept",
        json={"token": token, "full_name": "أب جديد"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Legacy contract — unchanged.
    assert body["ok"] is True
    assert body["student_id"] == sid
    assert body["workspace_school_id"] == ctx["wsid"]
    assert body["access_token"]
    assert body["matched_by"] == "new"

    # New additive fields.
    assert body["student_name"] == "طالب الترحيب"
    assert body["inviter_teacher_name"] == ctx["user"]["full_name"]
    # mk_it_workspace seeds `schools.name = IT-Workspace-<uid prefix>`.
    assert body["workspace_name"] and body["workspace_name"].startswith("IT-Workspace-")


# ---------------------------------------------------------------------------
# Task #277 — parent-portal endpoints surface IT context
# (so the FE can swap the school chip for the inviting teacher's name and
# hide school-only surfaces). Purely additive — legacy keys must keep
# flowing unchanged.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_child_details_endpoint_includes_it_context(client):
    ctx = await mk_it_workspace(with_passkey=False)
    parent_h = headers(ctx["parent_user_id"], UserRole.PARENT.value, ctx["wsid"])

    resp = await client.get(
        f"/parent-portal/child/{ctx['student_id']}", headers=parent_h
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Legacy keys preserved.
    assert body["id"] == ctx["student_id"]
    assert body["name"] == "طالب التجربة"
    # New IT context fields.
    assert body["school_id"] == ctx["wsid"]
    assert body["is_independent_teacher_workspace"] is True
    assert body["teacher_display_name"] == ctx["user"]["full_name"]


@pytest.mark.asyncio
async def test_child_profile_endpoint_includes_it_context(client):
    ctx = await mk_it_workspace(with_passkey=False)
    parent_h = headers(ctx["parent_user_id"], UserRole.PARENT.value, ctx["wsid"])

    resp = await client.get(
        f"/parent-portal/child/{ctx['student_id']}/profile", headers=parent_h
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == ctx["student_id"]
    assert body["school_id"] == ctx["wsid"]
    assert body["is_independent_teacher_workspace"] is True
    assert body["teacher_display_name"] == ctx["user"]["full_name"]
