"""
Independent-Teacher Parents directory — security-rule regression tests
(Task #850; router: ``independent_teacher_parents_routes``).

Locks in the security contract of the IT Parents tab so a future change
cannot silently break tenant isolation or leak credentials:

  * Cross-workspace by-id reads/writes 404 (never 403/200) — spec §8
    invariant 3 — for both ``GET /independent-teacher/parents/{id}``
    and ``PUT .../{id}/credentials``.
  * The credential-rotation endpoint emits the canonical 403 MFA
    step-up envelope when recent MFA is missing.
  * List + detail responses never include password-hash material, and
    rotation returns the one-time plaintext exactly once (the stored
    hash is never returned and never equals the plaintext).
  * A failure during the rotation write rolls back via the nested
    transaction — no half-created portal account (mirrors the
    invite-parent atomicity test).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch as mock_patch

import pytest

from auth_scope import independent_workspace_id
from dependencies import db, UserRole, create_access_token, verify_password
from engines.sql_utils import gd_count, gd_find, gd_find_one, gd_insert


# ----------------------------------------------------------------------
# Fixtures / helpers (mirror test_independent_teacher_invite_parent.py)
# ----------------------------------------------------------------------

def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


async def _seed_active_passkey(user_id: str) -> None:
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


async def _seed_parent_with_portal(
    wsid: str,
    *,
    student_name: str = "طالب",
    password_hash: str = "$2b$12$abcdefghijklmnopqrstuvAbCdEfGhIjKlMnOpQrStUvWxYz0123",
    with_user: bool = True,
) -> dict:
    """Seed a workspace parent with a linked student + (optional) portal
    ``users`` row carrying a real password hash. Returns key ids."""
    parent_id = str(uuid.uuid4())
    student_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4()) if with_user else None

    await gd_insert(db.session, "parents", {
        "id": parent_id,
        "school_id": wsid,
        "full_name": "ولي أمر",
        "phone": "+966500111000",
        "email": f"parent-{parent_id}@example.com",
        "national_id": "1029384756",
        "user_id": user_id,
        "is_active": True,
    })
    await gd_insert(db.session, "students", {
        "id": student_id,
        "school_id": wsid,
        "tenant_id": wsid,
        "full_name": student_name,
        "is_active": True,
        "parent_id": parent_id,
    })
    if with_user:
        await gd_insert(db.session, "users", {
            "id": user_id,
            "role": "parent",
            "tenant_id": wsid,
            "parent_id": parent_id,
            "email": f"parent-{parent_id}@example.com",
            "full_name": "ولي أمر",
            "password_hash": password_hash,
            "is_active": True,
            "preferred_language": "ar",
            "preferred_theme": "light",
        })
    await gd_insert(db.session, "guardian_links", {
        "id": str(uuid.uuid4()),
        "parent_ref": user_id,
        "parent_id": parent_id,
        "student_id": student_id,
        "relationship": "guardian",
        "tenant_id": wsid,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {
        "parent_id": parent_id,
        "student_id": student_id,
        "user_id": user_id,
        "password_hash": password_hash,
    }


# ----------------------------------------------------------------------
# (a) Cross-workspace by-id GET → 404 (never 403/200) — §8 inv. 3
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_parent_cross_workspace_returns_404(client):
    owner = await _mk_it()
    owner_wsid = independent_workspace_id(owner)
    seed = await _seed_parent_with_portal(owner_wsid)

    intruder = await _mk_it()
    h = _it_headers(intruder)

    resp = await client.get(
        f"/independent-teacher/parents/{seed['parent_id']}",
        headers=h,
    )
    assert resp.status_code == 404, resp.text


# ----------------------------------------------------------------------
# (b) Cross-workspace by-id credential rotation → 404 (never 403/200)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rotate_credentials_cross_workspace_returns_404(client):
    owner = await _mk_it()
    owner_wsid = independent_workspace_id(owner)
    seed = await _seed_parent_with_portal(owner_wsid)

    intruder = await _mk_it()
    h = _it_headers(intruder)

    resp = await client.put(
        f"/independent-teacher/parents/{seed['parent_id']}/credentials",
        json={"new_password": "BrandNewPass9"},
        headers=h,
    )
    # Must 404 — never confirm the foreign parent's existence, and never
    # mutate it.
    assert resp.status_code == 404, resp.text

    # The foreign parent's portal password hash is untouched.
    foreign_user = await gd_find_one(db.session, "users", {"id": seed["user_id"]})
    assert foreign_user["password_hash"] == seed["password_hash"]


# ----------------------------------------------------------------------
# (c) Credential rotation without recent MFA → 403 step-up envelope
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rotate_credentials_requires_recent_mfa(client, monkeypatch):
    # Env runs with the demo kill switch on; the step-up gate only fires
    # when enforcement is enabled. is_enforcement_disabled() reads the env
    # fresh per call, so flipping it here takes effect immediately.
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "false")
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    seed = await _seed_parent_with_portal(wsid)
    h = _it_headers(user, with_mfa=False)

    resp = await client.put(
        f"/independent-teacher/parents/{seed['parent_id']}/credentials",
        json={"new_password": "BrandNewPass9"},
        headers=h,
    )
    assert resp.status_code == 403, resp.text
    body = resp.json()
    detail = body.get("detail") or (body.get("error") or {})
    code = None
    if isinstance(detail, dict):
        code = detail.get("code") or (detail.get("error") or {}).get("code")
    s = str(detail)
    assert code in {"MFA_STEPUP_REQUIRED", "MFA_PASSKEY_REQUIRED"} \
        or "MFA_STEPUP_REQUIRED" in s or "MFA_PASSKEY_REQUIRED" in s

    # No write happened — the hash is unchanged.
    portal_user = await gd_find_one(db.session, "users", {"id": seed["user_id"]})
    assert portal_user["password_hash"] == seed["password_hash"]


# ----------------------------------------------------------------------
# (d) List response never leaks password-hash material
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_parents_never_returns_password_hash(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    seed = await _seed_parent_with_portal(wsid)
    h = _it_headers(user)

    resp = await client.get("/independent-teacher/parents", headers=h)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Our seeded parent is present...
    ids = [p["id"] for p in data["parents"]]
    assert seed["parent_id"] in ids

    # ...and nowhere in the serialized payload does the hash or the
    # hash field appear. (``must_change_password`` is a legitimate
    # boolean state flag, so we match the hash key specifically rather
    # than the bare "password" substring.)
    blob = json.dumps(data)
    assert seed["password_hash"] not in blob
    assert "password_hash" not in blob


# ----------------------------------------------------------------------
# (e) Detail response never leaks password-hash material
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_parent_detail_never_returns_password_hash(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    seed = await _seed_parent_with_portal(wsid)
    h = _it_headers(user)

    resp = await client.get(
        f"/independent-teacher/parents/{seed['parent_id']}",
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == seed["parent_id"]
    assert data["user_account"]["has_login_account"] is True

    blob = json.dumps(data)
    assert seed["password_hash"] not in blob
    assert "password_hash" not in blob


# ----------------------------------------------------------------------
# (f) Rotation returns the one-time plaintext exactly once; the stored
#     hash is never returned and never equals the plaintext.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rotate_credentials_returns_plaintext_once(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    seed = await _seed_parent_with_portal(wsid)
    h = _it_headers(user)

    resp = await client.put(
        f"/independent-teacher/parents/{seed['parent_id']}/credentials",
        json={"new_password": "BrandNewPass9"},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # One-time plaintext echoed back exactly once...
    assert data["password"] == "BrandNewPass9"
    assert data["must_change_password"] is True
    # ...but the stored hash is never part of the response.
    assert "password_hash" not in json.dumps(data)

    # The persisted hash is a real bcrypt of the plaintext — not the
    # plaintext itself, and different from the previous hash.
    portal_user = await gd_find_one(db.session, "users", {"id": seed["user_id"]})
    assert portal_user["password_hash"] != "BrandNewPass9"
    assert portal_user["password_hash"] != seed["password_hash"]
    assert verify_password("BrandNewPass9", portal_user["password_hash"]) is True
    assert portal_user["must_change_password"] is True


@pytest.mark.asyncio
async def test_rotate_credentials_autogenerates_password_when_omitted(client):
    """When no password is supplied a strong one is generated and returned
    once; it must still be a hashed-at-rest, verifiable credential."""
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    seed = await _seed_parent_with_portal(wsid)
    h = _it_headers(user)

    resp = await client.put(
        f"/independent-teacher/parents/{seed['parent_id']}/credentials",
        json={},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    generated = data["password"]
    assert isinstance(generated, str) and len(generated) >= 8

    portal_user = await gd_find_one(db.session, "users", {"id": seed["user_id"]})
    assert portal_user["password_hash"] != generated
    assert verify_password(generated, portal_user["password_hash"]) is True


# ----------------------------------------------------------------------
# (g) Rollback on forced inner failure — no half-created portal account
#     (mirrors test_invite_parent_rolls_back_on_audit_failure).
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rotate_credentials_rolls_back_on_audit_failure(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    # Parent with NO portal users row yet → rotation takes the
    # account-creation path, so a rollback must leave zero portal users.
    seed = await _seed_parent_with_portal(wsid, with_user=False)
    h = _it_headers(user)

    users_before = await gd_count(
        db.session, "users", {"role": "parent", "tenant_id": wsid},
    )

    # Force the audit insert to blow up inside the SAVEPOINT.
    with mock_patch(
        "routes.independent_teacher_parents_routes.audit_engine.log",
        side_effect=RuntimeError("boom"),
    ):
        resp = await client.put(
            f"/independent-teacher/parents/{seed['parent_id']}/credentials",
            json={"new_password": "BrandNewPass9"},
            headers=h,
        )
    assert resp.status_code == 500, resp.text

    # Nothing persisted: no portal users row was created.
    users_after = await gd_count(
        db.session, "users", {"role": "parent", "tenant_id": wsid},
    )
    assert users_after == users_before
    created = await gd_find(
        db.session, "users",
        {"parent_id": seed["parent_id"], "tenant_id": wsid},
    )
    assert created == []
