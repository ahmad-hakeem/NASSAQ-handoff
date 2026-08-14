"""
Independent-Teacher Invite-Parent endpoint tests
(spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §5.6, §5.7,
Task #199).

Covers POST /independent-teacher/students/{id}/invite-parent and
PATCH /independent-teacher/students/{id}/pending-parent:

  * All four dedupe paths (national_id / phone+email / phone / email)
    plus the new-parent path.
  * Cross-tenant student_id → 404 (never 403).
  * Edit-conflict 409 on PATCH pending-parent when parent_id IS NOT NULL.
  * Trigger-based clear of pending_parent_* on parent_id NULL → non-NULL.
  * guardian_links.tenant_id == itw_{user_id}.
  * INDEPENDENT_TEACHER_PARENT_LINK audit row with correct matched_by.
  * Rollback on forced inner failure (no half-linked state).
  * MFA step-up gate (no recent MFA → 401 MFA_STEPUP_REQUIRED).
  * Conservative parents update — established fields are never overwritten.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch as mock_patch

import pytest

from src.core.guards.tenant_guard import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_count, gd_find, gd_find_one, gd_insert


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


async def _seed_active_passkey(user_id: str) -> None:
    """Tier-A users need at least one active webauthn factor for
    require_recent_mfa to clear the passkey gate."""
    await gd_insert(db.session, "mfa_factors", {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "kind": "webauthn",
        "is_active": True,
        "is_primary": True,
        "webauthn_credential_id": uuid.uuid4().bytes,
        "webauthn_public_key": b"\x00",
        "webauthn_sign_count": 0,
    })


async def _mk_it() -> dict:
    """Bootstrap an IT user + workspace school + active passkey."""
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-Workspace-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher",
    })
    await _seed_active_passkey(uid)
    return user


def _it_headers(user: dict, *, with_mfa: bool = True) -> dict:
    claims = {
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": independent_workspace_id(user),
    }
    if with_mfa:
        token = create_access_token(claims, mfa_recent_at=_now_ts(), mfa_kind="webauthn")
    else:
        token = create_access_token(claims)
    return {"Authorization": f"Bearer {token}"}


async def _mk_pending_student(wsid: str, **pending) -> str:
    sid = str(uuid.uuid4())
    doc = {
        "id": sid,
        "school_id": wsid,
        "tenant_id": wsid,
        "full_name": "طالب",
        "is_active": True,
    }
    doc.update(pending)
    await gd_insert(db.session, "students", doc)
    return sid


# ----------------------------------------------------------------------
# (a) New-parent dedupe path
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invite_parent_new_creates_atomic_link(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)
    sid = await _mk_pending_student(
        wsid,
        pending_parent_name="ولي مؤقت",
        pending_parent_phone="+966500111000",
    )

    body = {
        "full_name": "أحمد المعلم",
        "phone": "+966500111111",
        "email": "newdad@example.com",
        "relationship": "father",
    }
    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent",
        json=body, headers=h,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["matched_by"] == "new"
    parent_id = data["parent"]["id"]

    # students.parent_id flipped + trigger cleared pending_*.
    student = await gd_find_one(db.session, "students", {"id": sid})
    assert student["parent_id"] == parent_id
    assert student.get("pending_parent_name") is None
    assert student.get("pending_parent_phone") is None
    assert student.get("pending_parent_email") is None

    # guardian_links row tenant_id == workspace id, is_primary on first link.
    links = await gd_find(db.session, "guardian_links",
                          {"student_id": sid, "is_active": True})
    assert len(links) == 1
    assert links[0]["tenant_id"] == wsid
    assert links[0]["is_primary"] is True
    assert links[0]["parent_id"] == parent_id

    # parents.school_id set to workspace on first creation.
    parent_row = await gd_find_one(db.session, "parents", {"id": parent_id})
    assert parent_row["school_id"] == wsid
    assert parent_row["phone"] == "+966500111111"

    # Audit row exists with the correct matched_by.
    audits = await gd_find(db.session, "audit_logs", {
        "action": "INDEPENDENT_TEACHER_PARENT_LINK",
        "entity_id": sid,
    })
    assert len(audits) == 1
    assert audits[0]["school_id"] == wsid
    assert audits[0]["details"]["matched_by"] == "new"
    assert audits[0]["details"]["parent_id"] == parent_id
    # Spec §"Done looks like": audit row carries the workspace
    # tenant_id verbatim in details so cross-workspace queries can
    # filter on it without a join.
    assert audits[0]["details"]["tenant_id"] == wsid


# ----------------------------------------------------------------------
# (a.1) New-parent path with phone only (no email) — Task #203 regression
# `users.email` is NOT NULL globally, so phone-only invites synthesise a
# deterministic non-deliverable placeholder address (.invalid TLD) so
# the workspace `users` row is always materialised and cohort resolution
# in `/notifications/bulk` works on every successful new-parent path.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invite_parent_new_phone_only_materialises_workspace_user(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)
    sid = await _mk_pending_student(wsid)

    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent",
        json={
            "full_name": "ولي بدون بريد",
            "phone": "+966500202020",
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["matched_by"] == "new"
    parent_id = data["parent"]["id"]

    # Workspace `users` row must exist for the new parent and be
    # tenant-pinned; placeholder email lives on the .invalid TLD.
    links = await gd_find(db.session, "guardian_links",
                          {"student_id": sid, "is_active": True})
    assert len(links) == 1
    assert links[0]["parent_id"] == parent_id
    parent_user_id = links[0]["parent_ref"]
    assert parent_user_id != parent_id  # synthetic users.id, not parents.id
    parent_user = await gd_find_one(db.session, "users", {"id": parent_user_id})
    assert parent_user is not None
    assert parent_user["role"] == "parent"
    assert parent_user["tenant_id"] == wsid
    assert parent_user["password_hash"] == "!invite-pending"
    assert parent_user["email"].endswith("@invite.nassaq.invalid")
    assert parent_id in parent_user["email"]

    # Audit row carries the materialisation flag.
    audits = await gd_find(db.session, "audit_logs", {
        "action": "INDEPENDENT_TEACHER_PARENT_LINK",
        "entity_id": sid,
    })
    assert len(audits) == 1
    assert audits[0]["details"]["parent_user_materialised"] is True
    assert audits[0]["details"]["parent_user_id"] == parent_user_id


# ----------------------------------------------------------------------
# (a.2) New-parent path with national_id only — Task #203 regression
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invite_parent_new_national_id_only_materialises_workspace_user(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)
    sid = await _mk_pending_student(wsid)

    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent",
        json={
            "full_name": "ولي بهوية",
            "national_id": "9876543210",
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["matched_by"] == "new"
    parent_id = data["parent"]["id"]

    links = await gd_find(db.session, "guardian_links",
                          {"student_id": sid, "is_active": True})
    assert len(links) == 1
    assert links[0]["parent_id"] == parent_id
    parent_user_id = links[0]["parent_ref"]
    assert parent_user_id != parent_id
    parent_user = await gd_find_one(db.session, "users", {"id": parent_user_id})
    assert parent_user is not None
    assert parent_user["tenant_id"] == wsid
    assert parent_user["email"].endswith("@invite.nassaq.invalid")

    audits = await gd_find(db.session, "audit_logs", {
        "action": "INDEPENDENT_TEACHER_PARENT_LINK",
        "entity_id": sid,
    })
    assert len(audits) == 1
    assert audits[0]["details"]["parent_user_materialised"] is True


# ----------------------------------------------------------------------
# (a.3) New-parent path with email that collides with another global
# `users` row — Task #203 review follow-up. Materialisation must still
# succeed by falling back to the deterministic .invalid placeholder
# instead of failing the whole link with a unique-index violation.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invite_parent_new_email_collision_falls_back_to_placeholder(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)
    sid = await _mk_pending_student(wsid)

    # Stand up a SECOND, real IT workspace and seed a `users` row in it
    # whose email will collide with the invite payload below. The
    # collision is on `users.email` (globally unique) but the email is
    # NOT in this caller's workspace `parents` table, so the parent
    # dedupe stays on the new-parent path and must hit the collision
    # fallback to the .invalid placeholder.
    other = await _mk_it()
    other_wsid = independent_workspace_id(other)
    colliding_email = f"collide-{uuid.uuid4()}@example.com"
    from engines.sql_utils import gd_insert
    await gd_insert(db.session, "users", {
        "id": str(uuid.uuid4()),
        "role": "parent",
        "tenant_id": other_wsid,
        "email": colliding_email,
        "full_name": "آخر",
        "password_hash": "!seed",
        "is_active": True,
        "preferred_language": "ar",
        "preferred_theme": "light",
    })
    await db.session.flush()

    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent",
        json={
            "full_name": "ولي بإيميل متعارض",
            "email": colliding_email,
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["matched_by"] == "new"
    parent_id = data["parent"]["id"]

    links = await gd_find(db.session, "guardian_links",
                          {"student_id": sid, "is_active": True})
    parent_user_id = links[0]["parent_ref"]
    parent_user = await gd_find_one(db.session, "users", {"id": parent_user_id})
    assert parent_user is not None
    assert parent_user["tenant_id"] == wsid
    assert parent_user["email"].endswith("@invite.nassaq.invalid")
    assert parent_user["email"] != colliding_email


# ----------------------------------------------------------------------
# (b) Dedupe by national_id — same workspace matches, cross-tenant is ignored
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invite_parent_dedupes_by_national_id_same_workspace(client):
    """A parents row with a matching national_id in the SAME workspace is
    reused (correct dedupe behaviour)."""
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)
    sid = await _mk_pending_student(wsid)

    existing_id = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": existing_id,
        "full_name": "أب موجود",
        "national_id": "1234567890",
        "phone": "+966500999999",
        "email": "existing@example.com",
        "school_id": wsid,
        "is_active": True,
    })

    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent",
        json={"national_id": "1234567890", "phone": "+966500000000"},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["matched_by"] == "national_id"
    assert resp.json()["parent"]["id"] == existing_id

    # Established fields preserved (conservative update).
    p = await gd_find_one(db.session, "parents", {"id": existing_id})
    assert p["phone"] == "+966500999999"


@pytest.mark.asyncio
async def test_invite_parent_does_not_dedupe_cross_tenant_national_id(client):
    """A parents row with a matching national_id in a DIFFERENT workspace must
    NOT be reused — a fresh parents row must be created in the requesting
    teacher's workspace instead. This prevents cross-tenant family merges."""
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)
    sid = await _mk_pending_student(wsid)

    other_user = await _mk_it()
    other_wsid = independent_workspace_id(other_user)
    other_parent_id = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": other_parent_id,
        "full_name": "أب في مدرسة أخرى",
        "national_id": "9999988888",
        "phone": "+966500111111",
        "email": "other@example.com",
        "school_id": other_wsid,
        "is_active": True,
    })

    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent",
        json={"national_id": "9999988888", "phone": "+966500222222"},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Cross-tenant row must NOT have been reused.
    assert body["parent"]["id"] != other_parent_id
    # A brand-new parent record was created in the requesting workspace.
    assert body["matched_by"] == "new"
    new_parent = await gd_find_one(db.session, "parents", {"id": body["parent"]["id"]})
    assert new_parent is not None
    assert new_parent["school_id"] == wsid
    # The cross-tenant record is untouched.
    other_p = await gd_find_one(db.session, "parents", {"id": other_parent_id})
    assert other_p["school_id"] == other_wsid


# ----------------------------------------------------------------------
# (c) Dedupe by (phone, email) exact pair
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invite_parent_dedupes_by_phone_email_pair(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)
    sid = await _mk_pending_student(wsid)

    existing_id = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": existing_id,
        "full_name": "أم",
        "phone": "+966500222222",
        "email": "mom@example.com",
        "school_id": wsid,
        "is_active": True,
    })

    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent",
        json={"phone": "+966500222222", "email": "mom@example.com"},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["matched_by"] == "phone_email"
    assert resp.json()["parent"]["id"] == existing_id


# ----------------------------------------------------------------------
# (d) Dedupe by phone alone (when email absent)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invite_parent_dedupes_by_phone_alone(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)
    sid = await _mk_pending_student(wsid)

    existing_id = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": existing_id,
        "full_name": "والد",
        "phone": "+966500333333",
        "school_id": wsid,
        "is_active": True,
    })

    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent",
        json={"phone": "+966500333333"},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["matched_by"] == "phone"
    assert resp.json()["parent"]["id"] == existing_id


# ----------------------------------------------------------------------
# (e) Dedupe by email alone (when phone absent)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invite_parent_dedupes_by_email_alone(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)
    sid = await _mk_pending_student(wsid)

    existing_id = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": existing_id,
        "full_name": "ولي",
        "email": "guardian@example.com",
        "school_id": wsid,
        "is_active": True,
    })

    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent",
        json={"email": "guardian@example.com"},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["matched_by"] == "email"
    assert resp.json()["parent"]["id"] == existing_id


# ----------------------------------------------------------------------
# (f) Cross-tenant student_id → 404 (never 403)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invite_parent_cross_tenant_returns_404(client):
    user_a = await _mk_it()
    user_b = await _mk_it()
    wsid_a = independent_workspace_id(user_a)
    h_b = _it_headers(user_b)

    sid = await _mk_pending_student(wsid_a)

    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent",
        json={"phone": "+966500444444"},
        headers=h_b,
    )
    assert resp.status_code == 404, resp.text


# ----------------------------------------------------------------------
# (g) Missing identifier → 422
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invite_parent_requires_at_least_one_identifier(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)
    sid = await _mk_pending_student(wsid)

    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent",
        json={"full_name": "بلا هوية"},
        headers=h,
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    msg = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert "الجوال" in str(msg) or "البريد" in str(msg) or "الهوية" in str(msg)


# ----------------------------------------------------------------------
# (h) MFA step-up gate — token without mfa_recent_at → 401
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invite_parent_requires_recent_mfa(client, monkeypatch):
    # This env runs with the demo kill switch (MFA_ENFORCEMENT_DISABLED=true);
    # the step-up gate only fires when enforcement is on. is_enforcement_disabled()
    # reads the env fresh per call, so forcing it off here takes effect immediately.
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "false")
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user, with_mfa=False)
    sid = await _mk_pending_student(wsid)

    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent",
        json={"phone": "+966500555555"},
        headers=h,
    )
    # Task §"Done looks like": no recent MFA → 403 with the canonical
    # step-up payload (code / challenge_endpoint / max_age_seconds).
    assert resp.status_code == 403, resp.text
    body = resp.json()
    detail = body.get("detail") or (body.get("error") or {})
    code = None
    if isinstance(detail, dict):
        code = detail.get("code") or (detail.get("error") or {}).get("code")
    s = str(detail)
    assert code in {"MFA_STEPUP_REQUIRED", "MFA_PASSKEY_REQUIRED"} \
        or "MFA_STEPUP_REQUIRED" in s or "MFA_PASSKEY_REQUIRED" in s


# ----------------------------------------------------------------------
# (i) Re-invite when already linked → 409
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invite_parent_when_already_linked_returns_409(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)

    parent_id = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": parent_id, "full_name": "أب", "school_id": wsid, "is_active": True,
    })
    sid = await _mk_pending_student(wsid, parent_id=parent_id)

    resp = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent",
        json={"phone": "+966500666666"},
        headers=h,
    )
    assert resp.status_code == 409, resp.text


# ----------------------------------------------------------------------
# (j) PATCH pending-parent — edits while still Pending
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_patch_pending_parent_edits_when_unlinked(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)
    sid = await _mk_pending_student(
        wsid, pending_parent_phone="+966500777777",
    )

    resp = await client.patch(
        f"/independent-teacher/students/{sid}/pending-parent",
        json={"full_name": "اسم محدث", "phone": "+966500888888"},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    row = await gd_find_one(db.session, "students", {"id": sid})
    assert row["pending_parent_name"] == "اسم محدث"
    assert row["pending_parent_phone"] == "+966500888888"


# ----------------------------------------------------------------------
# (k) PATCH pending-parent on linked row → 409 with §5.6 verbatim string
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_patch_pending_parent_on_linked_returns_409(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)

    parent_id = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": parent_id, "full_name": "أب", "school_id": wsid, "is_active": True,
    })
    sid = await _mk_pending_student(wsid, parent_id=parent_id)

    resp = await client.patch(
        f"/independent-teacher/students/{sid}/pending-parent",
        json={"phone": "+966500999000"},
        headers=h,
    )
    assert resp.status_code == 409, resp.text
    body = resp.json()
    msg = body.get("detail") or (body.get("error") or {}).get("message") or ""
    assert "بيانات ولي الأمر مرتبطة بحساب" in str(msg)


# ----------------------------------------------------------------------
# (l) Rollback on forced inner failure — no half-linked state
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invite_parent_rolls_back_on_audit_failure(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)
    sid = await _mk_pending_student(
        wsid, pending_parent_phone="+966500111222",
    )

    parents_before = await gd_count(db.session, "parents", {"school_id": wsid})
    links_before = await gd_count(db.session, "guardian_links",
                                  {"student_id": sid})

    # Force the audit insert to blow up inside the SAVEPOINT. The audit
    # write now lives in the shared canonical writer (utils.it_parent_link).
    with mock_patch(
        "utils.it_parent_link.audit_engine.log",
        side_effect=RuntimeError("boom"),
    ):
        resp = await client.post(
            f"/independent-teacher/students/{sid}/invite-parent",
            json={"phone": "+966500111222"},
            headers=h,
        )
    assert resp.status_code == 500, resp.text

    # Nothing must have been persisted.
    parents_after = await gd_count(db.session, "parents", {"school_id": wsid})
    links_after = await gd_count(db.session, "guardian_links",
                                 {"student_id": sid})
    assert parents_after == parents_before
    assert links_after == links_before
    student = await gd_find_one(db.session, "students", {"id": sid})
    assert student.get("parent_id") is None
    # pending_parent_* preserved (trigger never fired).
    assert student.get("pending_parent_phone") == "+966500111222"
