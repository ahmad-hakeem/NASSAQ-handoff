"""
Tests for the Platform-Admin one-click teacher-transfer resolution endpoint
(`POST /users/{user_id}/resolve-teacher-mismatch` ->
`resolve_teacher_school_mismatch` in `backend/routes/user_routes_mod.py`).

The endpoint resolves a stuck teacher transfer surfaced by
`GET /users/teacher-school-mismatches`: a teacher whose ``users.tenant_id``
(intended school) differs from the school where their live ``teachers`` record
is stuck. Resolving:

  1. Soft-deletes (``deleted_at`` + ``is_active=False``) every live academic
     record living in a school OTHER than the intended one (retired in place —
     never migrated).
  2. Provisions / reactivates the record in the intended school via
     ``_ensure_school_teacher_record`` and folds the resolved ``teachers.id``
     back into ``users.teacher_id``.
  3. Writes an ``audit_logs`` row (``teacher_school_mismatch_resolved``).

Locks in:
  * Happy path — the foreign record is retired, a fresh record is provisioned in
    the intended school, ``users.teacher_id`` is relinked, and exactly one audit
    row is written.
  * Reactivation — ``_ensure_school_teacher_record`` flips a deactivated
    (non-deleted, ``is_active=False``) record in the target school back on in
    place rather than minting a new id. (Endpoint step 2 delegates to this
    helper; the helper is exercised directly because the endpoint's
    "already-in-intended" guard fail-closes before a non-deleted intended record
    can reach step 2 — see ``test_resolve_*already_in_intended*`` below.)
  * Archived-record restore — when the intended school already holds a
    SOFT-DELETED (``deleted_at`` set) record for the teacher, resolving RESTORES
    that old record in place (reactivated, ``deleted_at`` cleared, re-linked)
    instead of minting a fresh, disconnected id. The response carries
    ``restored_existing_record=True`` and the listing carries
    ``will_restore_existing_record=True`` so the admin is warned beforehand.
  * Every fail-closed branch: non-teacher (400), no intended school (400), no
    live record (400), already-in-intended (400), missing user (404). On each
    rejection nothing is mutated and no audit row is written.
  * Authorization — platform-admin only (teacher / school-admin / anonymous are
    rejected) and the action passes through the ``require_recent_mfa()`` gate
    (stale token -> 401 step-up envelope; fresh token -> 200).

MFA enforcement is disabled by default in this environment
(``MFA_ENFORCEMENT_DISABLED=true``), so the happy-path / branch tests reach the
business logic with the platform-admin fixture. The dedicated gate test
re-enables enforcement via monkeypatch.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find, gd_find_one, gd_count


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


async def _mk_school(name_suffix: str = "") -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid,
        "name": f"School-{name_suffix or sid[:6]}",
        "code": f"S{sid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    return sid


async def _mk_teacher_user(intended_school_id, email=None, role=UserRole.TEACHER) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": role.value,
        "tenant_id": intended_school_id,
        "email": email or f"{uid}@t.test",
        "full_name": f"Teacher {uid[:6]}",
        "phone": "0500000000",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


async def _mk_teacher_record(
    school_id,
    *,
    user_id=None,
    email=None,
    is_active=True,
    deleted_at=None,
    full_name="Record",
) -> str:
    rid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": rid,
        "teacher_id": rid,
        "full_name": full_name,
        "email": email,
        "school_id": school_id,
        "user_id": user_id,
        "is_active": is_active,
        "deleted_at": deleted_at,
        "preferences": {},
        "constraints": {},
    })
    return rid


async def _count_resolve_audits(user_id: str) -> int:
    """Audit rows for THIS user's resolution. The endpoint stores the user id
    in ``details.user_id`` (entity_id is the resolved teacher record id), so we
    scan by action and filter in-process — the shared DB makes a global count
    non-deterministic."""
    rows = await gd_find(db.session, "audit_logs", {
        "action": "teacher_school_mismatch_resolved",
    }) or []
    return sum(1 for r in rows if (r.get("details") or {}).get("user_id") == user_id)


def _resolve_url(user_id: str) -> str:
    return f"/users/{user_id}/resolve-teacher-mismatch"


# ----------------------------------------------------------------------
# (1) Happy path
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_resolve_retires_foreign_record_provisions_and_relinks(
    client, platform_admin_headers, monkeypatch
):
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")
    intended = await _mk_school("intended")
    other = await _mk_school("other")
    user = await _mk_teacher_user(intended)
    stuck_id = await _mk_teacher_record(other, user_id=user["id"])

    resp = await client.post(_resolve_url(user["id"]), headers=platform_admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    resolved_id = body["resolved_teacher_id"]
    assert resolved_id
    # A brand-new record was provisioned (not the stuck one).
    assert resolved_id != stuck_id
    assert body["retired_records"] == [
        {"teacher_record_id": stuck_id, "school_id": other}
    ]

    # Old record retired in place: soft-deleted + deactivated, still in `other`.
    stuck = await gd_find_one(db.session, "teachers", {"id": stuck_id})
    assert stuck["is_active"] is False
    assert stuck["deleted_at"] is not None
    assert stuck["school_id"] == other

    # New record is live in the intended school and linked to the user.
    provisioned = await gd_find_one(db.session, "teachers", {"id": resolved_id})
    assert provisioned["school_id"] == intended
    assert provisioned["is_active"] is True
    assert provisioned.get("deleted_at") is None
    assert provisioned["user_id"] == user["id"]

    # users.teacher_id was relinked to the resolved record.
    refreshed_user = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert refreshed_user["teacher_id"] == resolved_id

    # Exactly one audit row, with the expected shape.
    rows = await gd_find(db.session, "audit_logs", {
        "action": "teacher_school_mismatch_resolved",
    }) or []
    mine = [r for r in rows if (r.get("details") or {}).get("user_id") == user["id"]]
    assert len(mine) == 1, mine
    row = mine[0]
    assert row["entity_type"] == "teacher"
    assert row["entity_id"] == resolved_id
    assert row["school_id"] == intended
    assert row["performed_by"]  # the acting platform admin
    details = row["details"]
    assert details["intended_school_id"] == intended
    assert details["resolved_teacher_id"] == resolved_id
    assert details["retired_records"] == [
        {"teacher_record_id": stuck_id, "school_id": other}
    ]


@pytest.mark.asyncio
async def test_resolve_matches_record_by_email_fallback(
    client, platform_admin_headers, monkeypatch
):
    """The stuck record is linked only by canonical email (no user_id) — it must
    still be discovered, retired, and the user relinked to a fresh record."""
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")
    intended = await _mk_school("intended")
    other = await _mk_school("other")
    user = await _mk_teacher_user(intended)
    stuck_id = await _mk_teacher_record(other, user_id=None, email=user["email"])

    resp = await client.post(_resolve_url(user["id"]), headers=platform_admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["retired_records"] == [
        {"teacher_record_id": stuck_id, "school_id": other}
    ]

    stuck = await gd_find_one(db.session, "teachers", {"id": stuck_id})
    assert stuck["deleted_at"] is not None
    assert stuck["is_active"] is False


# ----------------------------------------------------------------------
# (2) Reactivation of a deactivated record in the target school
#     (exercised on the helper the endpoint delegates to — see module docstring)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ensure_record_reactivates_deactivated_record_in_place(monkeypatch):
    from src.modules.users.controllers.user_routes_mod import _ensure_school_teacher_record

    intended = await _mk_school("intended")
    user = await _mk_teacher_user(intended)
    admin_id = str(uuid.uuid4())
    # Deactivated (NOT soft-deleted) record already living in the target school.
    deact_id = await _mk_teacher_record(
        intended, user_id=user["id"], is_active=False
    )

    resolved_id = await _ensure_school_teacher_record(user, intended, admin_id)

    # Same record reactivated in place — no new id minted.
    assert resolved_id == deact_id
    rec = await gd_find_one(db.session, "teachers", {"id": deact_id})
    assert rec["is_active"] is True
    assert rec.get("deleted_at") is None

    # No duplicate record was provisioned in the target school.
    same_school = await gd_count(
        db.session, "teachers", {"user_id": user["id"], "school_id": intended}
    )
    assert same_school == 1


# ----------------------------------------------------------------------
# (2b) Archived-record restore in the intended school
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_resolve_restores_archived_record_in_intended_school(
    client, platform_admin_headers, monkeypatch
):
    """The intended school already holds a SOFT-DELETED record for the teacher.
    Resolving must restore THAT old record in place (same id) rather than mint a
    brand-new one, and the response must flag ``restored_existing_record``."""
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")
    intended = await _mk_school("intended")
    other = await _mk_school("other")
    user = await _mk_teacher_user(intended)
    stuck_id = await _mk_teacher_record(other, user_id=user["id"])
    archived_id = await _mk_teacher_record(
        intended,
        user_id=user["id"],
        is_active=False,
        deleted_at="2026-01-01T00:00:00+00:00",
    )

    resp = await client.post(_resolve_url(user["id"]), headers=platform_admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # The OLD archived record was restored — not a fresh id.
    assert body["resolved_teacher_id"] == archived_id
    assert body["restored_existing_record"] is True
    assert body["retired_records"] == [
        {"teacher_record_id": stuck_id, "school_id": other}
    ]

    # Archived record reactivated in place in the intended school.
    restored = await gd_find_one(db.session, "teachers", {"id": archived_id})
    assert restored["school_id"] == intended
    assert restored["is_active"] is True
    assert restored.get("deleted_at") is None
    assert restored["user_id"] == user["id"]

    # No duplicate minted in the intended school.
    in_intended = await gd_count(
        db.session, "teachers", {"school_id": intended, "deleted_at": None}
    )
    assert in_intended == 1

    # Foreign record retired in place.
    stuck = await gd_find_one(db.session, "teachers", {"id": stuck_id})
    assert stuck["is_active"] is False
    assert stuck["deleted_at"] is not None

    # users.teacher_id relinked to the restored record.
    refreshed_user = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert refreshed_user["teacher_id"] == archived_id


@pytest.mark.asyncio
async def test_resolve_mints_new_record_when_no_archive_and_flags_false(
    client, platform_admin_headers, monkeypatch
):
    """No archived record in the intended school → a fresh record is minted and
    ``restored_existing_record`` is False (the admin-facing distinction)."""
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")
    intended = await _mk_school("intended")
    other = await _mk_school("other")
    user = await _mk_teacher_user(intended)
    stuck_id = await _mk_teacher_record(other, user_id=user["id"])

    resp = await client.post(_resolve_url(user["id"]), headers=platform_admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["restored_existing_record"] is False
    assert body["resolved_teacher_id"] != stuck_id


@pytest.mark.asyncio
async def test_mismatch_listing_flags_archived_record_in_intended(
    client, platform_admin_headers, monkeypatch
):
    """The listing warns the admin (``will_restore_existing_record``) when an
    archived record already sits in the intended school for a stuck teacher."""
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")
    intended = await _mk_school("intended")
    other = await _mk_school("other")
    user = await _mk_teacher_user(intended)
    await _mk_teacher_record(other, user_id=user["id"])
    archived_id = await _mk_teacher_record(
        intended,
        user_id=user["id"],
        is_active=False,
        deleted_at="2026-01-01T00:00:00+00:00",
    )

    resp = await client.get(
        "/users/teacher-school-mismatches", headers=platform_admin_headers
    )
    assert resp.status_code == 200, resp.text
    mine = next(
        (m for m in resp.json()["mismatches"] if m["user_id"] == user["id"]), None
    )
    assert mine is not None
    assert mine["will_restore_existing_record"] is True
    assert archived_id in mine["archived_record_ids_in_intended"]


# ----------------------------------------------------------------------
# (3) Fail-closed branches
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_resolve_non_teacher_user_returns_400(
    client, platform_admin_headers, monkeypatch
):
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")
    intended = await _mk_school("intended")
    # A parent account (role != teacher).
    user = await _mk_teacher_user(intended, role=UserRole.PARENT)

    resp = await client.post(_resolve_url(user["id"]), headers=platform_admin_headers)
    assert resp.status_code == 400, resp.text
    assert await _count_resolve_audits(user["id"]) == 0


@pytest.mark.asyncio
async def test_resolve_no_intended_school_returns_400(
    client, platform_admin_headers, monkeypatch
):
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")
    other = await _mk_school("other")
    # Teacher with NO tenant_id (no intended school).
    user = await _mk_teacher_user(None)
    await _mk_teacher_record(other, user_id=user["id"])

    resp = await client.post(_resolve_url(user["id"]), headers=platform_admin_headers)
    assert resp.status_code == 400, resp.text
    assert await _count_resolve_audits(user["id"]) == 0


@pytest.mark.asyncio
async def test_resolve_no_live_record_returns_400(
    client, platform_admin_headers, monkeypatch
):
    """A teacher whose only record is soft-deleted has no live record to move."""
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")
    intended = await _mk_school("intended")
    other = await _mk_school("other")
    user = await _mk_teacher_user(intended)
    await _mk_teacher_record(
        other, user_id=user["id"], deleted_at="2026-01-01T00:00:00+00:00"
    )

    resp = await client.post(_resolve_url(user["id"]), headers=platform_admin_headers)
    assert resp.status_code == 400, resp.text
    assert await _count_resolve_audits(user["id"]) == 0


@pytest.mark.asyncio
async def test_resolve_already_in_intended_returns_400_and_no_mutation(
    client, platform_admin_headers, monkeypatch
):
    """A live record already in the intended school = no conflict -> 400, and the
    foreign record must NOT be retired."""
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")
    intended = await _mk_school("intended")
    other = await _mk_school("other")
    user = await _mk_teacher_user(intended)
    intended_rec = await _mk_teacher_record(intended, user_id=user["id"])
    other_rec = await _mk_teacher_record(other, user_id=user["id"])

    resp = await client.post(_resolve_url(user["id"]), headers=platform_admin_headers)
    assert resp.status_code == 400, resp.text

    # Nothing was retired — both records remain live.
    a = await gd_find_one(db.session, "teachers", {"id": intended_rec})
    b = await gd_find_one(db.session, "teachers", {"id": other_rec})
    assert a.get("deleted_at") is None and a["is_active"] is True
    assert b.get("deleted_at") is None and b["is_active"] is True
    assert await _count_resolve_audits(user["id"]) == 0


@pytest.mark.asyncio
async def test_resolve_missing_user_returns_404(
    client, platform_admin_headers, monkeypatch
):
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")
    resp = await client.post(
        _resolve_url(str(uuid.uuid4())), headers=platform_admin_headers
    )
    assert resp.status_code == 404, resp.text


# ----------------------------------------------------------------------
# (4) Authorization — platform-admin only
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_resolve_teacher_caller_rejected_403(
    client, teacher_headers, monkeypatch
):
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")
    resp = await client.post(_resolve_url(str(uuid.uuid4())), headers=teacher_headers)
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_resolve_school_admin_caller_rejected_403(
    client, school_admin_headers, monkeypatch
):
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")
    resp = await client.post(
        _resolve_url(str(uuid.uuid4())), headers=school_admin_headers
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_resolve_unauthenticated_rejected(client, monkeypatch):
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")
    resp = await client.post(_resolve_url(str(uuid.uuid4())))
    assert resp.status_code in (401, 403), resp.text


# ----------------------------------------------------------------------
# (5) require_recent_mfa() gate — enforcement ON
# ----------------------------------------------------------------------
async def _mk_platform_admin_with_passkey() -> dict:
    uid = str(uuid.uuid4())
    school_id = await _mk_school("admin-home")
    user = {
        "id": uid,
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": school_id,
        "email": f"admin-{uid}@t.test",
        "full_name": f"Admin {uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        # Enrollment gate in get_current_user needs this set so we reach the
        # require_recent_mfa() step-up gate (not the enrollment gate).
        "mfa_enrolled_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "users", user)
    # Tier-A passkey requirement — an active webauthn factor must exist, else the
    # gate stops at MFA_PASSKEY_REQUIRED before the freshness check.
    await gd_insert(db.session, "mfa_factors", {
        "id": str(uuid.uuid4()),
        "user_id": uid,
        "kind": "webauthn",
        "is_active": True,
        "is_primary": True,
        "webauthn_credential_id": uuid.uuid4().bytes,
        "webauthn_public_key": b"\x00",
        "webauthn_sign_count": 0,
    })
    return user


def _admin_headers(user: dict, *, fresh_mfa: bool) -> dict:
    claims = {"sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"]}
    if fresh_mfa:
        token = create_access_token(claims, mfa_recent_at=_now_ts(), mfa_kind="webauthn")
    else:
        token = create_access_token(claims)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_resolve_stale_mfa_token_is_blocked_by_stepup_gate(client, monkeypatch):
    """With enforcement ON, a platform-admin token lacking a fresh MFA proof is
    rejected by require_recent_mfa() with the canonical 401 step-up envelope —
    the business logic is never reached."""
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "false")
    admin = await _mk_platform_admin_with_passkey()
    intended = await _mk_school("intended")
    other = await _mk_school("other")
    user = await _mk_teacher_user(intended)
    stuck_id = await _mk_teacher_record(other, user_id=user["id"])

    resp = await client.post(
        _resolve_url(user["id"]), headers=_admin_headers(admin, fresh_mfa=False)
    )
    assert resp.status_code == 401, resp.text
    body = resp.json()
    detail = body.get("detail") or (body.get("error") or {})
    code = detail.get("code") if isinstance(detail, dict) else None
    assert code in {"MFA_STEPUP_REQUIRED", "MFA_PASSKEY_REQUIRED", "MFA_RESTORE_REQUIRED"}, body

    # The gate blocked the write — the stuck record was NOT retired.
    stuck = await gd_find_one(db.session, "teachers", {"id": stuck_id})
    assert stuck.get("deleted_at") is None
    assert stuck["is_active"] is True
    assert await _count_resolve_audits(user["id"]) == 0


@pytest.mark.asyncio
async def test_resolve_fresh_mfa_token_passes_the_gate(client, monkeypatch):
    """Positive control: same enforcement-ON setup, but a token carrying a fresh
    mfa_recent_at clears require_recent_mfa() and the resolution succeeds."""
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "false")
    admin = await _mk_platform_admin_with_passkey()
    intended = await _mk_school("intended")
    other = await _mk_school("other")
    user = await _mk_teacher_user(intended)
    stuck_id = await _mk_teacher_record(other, user_id=user["id"])

    resp = await client.post(
        _resolve_url(user["id"]), headers=_admin_headers(admin, fresh_mfa=True)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["retired_records"] == [
        {"teacher_record_id": stuck_id, "school_id": other}
    ]
    assert await _count_resolve_audits(user["id"]) == 1
