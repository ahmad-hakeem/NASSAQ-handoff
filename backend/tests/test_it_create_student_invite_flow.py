"""
Independent-Teacher create-student → parent-invitation flow tests
(Task #843 / #844; spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md
§5.6, §5.7, §6.2).

Task #843 rewired `create_student_with_wizard` so that, in IT workspace mode,
a linked-parent create branches across several onboarding modes. This suite
locks that branching down:

  * Flag OFF + deliverable email/phone — legacy auto-link fallback (mode
    "linked"): a parents row is materialised and NO invitation is minted.
  * Flag ON  + deliverable email/phone — invite mode (mode "invite"): the
    student stays Pending, a parent invitation is minted, and the raw token
    is surfaced ONLY inside `parent_onboarding.invite_link`.
  * Flag ON  + national_id-only (no deliverable channel) — fallback to
    auto-link (mode "linked"): no invitation is minted.
  * Fresh MFA is required BEFORE any DB write on the invite path: without a
    recent passkey proof the create returns the 403 step-up envelope and
    persists neither the student nor an invitation.
  * The raw invitation token never appears in the API JSON response except
    embedded in the generated `parent_onboarding.invite_link`.
"""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find, gd_find_one, gd_count
from auth_scope import independent_workspace_id


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


def _mfa_headers(user_id: str, role: str, tenant_id=None) -> dict:
    """Bearer carrying a fresh passkey MFA proof — required by both the
    auto-link and the invite sub-paths (§5.7 step-up)."""
    token = create_access_token(
        {"sub": user_id, "role": role, "tenant_id": tenant_id},
        mfa_recent_at=_now_ts(),
        mfa_kind="webauthn",
    )
    return {"Authorization": f"Bearer {token}"}


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


async def _mk_independent_teacher() -> dict:
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


def _student_payload(**overrides) -> dict:
    base = {
        "full_name": "طالب اختبار",
        "gender": "male",
        "date_of_birth": "2015-01-01",
        "education_level": "primary",
        "grade_id": "الصف الأول",
    }
    base.update(overrides)
    return base


def _flag_on():
    return patch.dict("os.environ", {"IT_PARENT_INVITATIONS_ENABLED": "1"})


def _flag_off():
    return patch.dict("os.environ", {"IT_PARENT_INVITATIONS_ENABLED": "0"})


# ----------------------------------------------------------------------
# (a) Flag OFF + deliverable channel — legacy auto-link fallback.
# A parents row is materialised (mode "linked"); NO invitation is minted.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_flag_off_deliverable_auto_links_no_invitation(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _mfa_headers(user["id"], user["role"], wsid)

    payload = _student_payload(parent={
        "full_name": "ولي الأمر",
        "email": "guardian-off@example.com",
    })
    with _flag_off():
        resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Auto-link mode: student is Linked, parents row exists.
    assert body["parent_onboarding"]["mode"] == "linked"
    sid = body["student"]["id"]
    row = await gd_find_one(db.session, "students", {"id": sid})
    assert row.get("parent_id") is not None
    assert await gd_count(db.session, "parents", {"school_id": wsid}) == 1

    # The invite envelope was NOT taken — no invitation row, no invite_link.
    assert await gd_count(
        db.session, "parent_invitations", {"workspace_school_id": wsid}
    ) == 0
    assert "invite_link" not in body["parent_onboarding"]


# ----------------------------------------------------------------------
# (b) Flag ON + deliverable channel — invite mode. Student stays Pending,
# an invitation is minted, the raw token rides ONLY in the invite_link.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_flag_on_deliverable_mints_invitation_pending(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _mfa_headers(user["id"], user["role"], wsid)

    payload = _student_payload(parent={
        "full_name": "ولي مدعو",
        "email": "guardian-on@example.com",
        "phone": "+966500111000",
    })
    with _flag_on(), patch(
        "routes.academics_student_routes.send_parent_invitation_email"
    ) as mock_send:
        resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    onboarding = body["parent_onboarding"]

    # Invite mode — student remains Pending (no parent_id), no parents row.
    assert onboarding["mode"] == "invite"
    sid = body["student"]["id"]
    row = await gd_find_one(db.session, "students", {"id": sid})
    assert row.get("parent_id") is None
    assert await gd_count(db.session, "parents", {"school_id": wsid}) == 0

    # Exactly one pending invitation minted for this (workspace, student).
    invitations = await gd_find(
        db.session, "parent_invitations", {"workspace_school_id": wsid}
    )
    assert len(invitations) == 1
    assert invitations[0]["student_id"] == sid
    assert invitations[0]["status"] == "pending"

    # The success envelope carries the onboarding metadata + invite link.
    assert onboarding["invite_status"] == "pending"
    assert onboarding["invite_channels"] == {"email": True, "sms": True}
    assert onboarding["invite_link"]
    assert "token=" in onboarding["invite_link"]
    assert body["parent"] is None  # no materialised parent in invite mode

    # Email delivery was scheduled (background task ran post-response).
    assert onboarding["email_queued"] is True
    mock_send.assert_called_once()


# ----------------------------------------------------------------------
# (c) Flag ON + national_id-only (no deliverable channel) — falls back to
# auto-link. No invitation is minted; a parents row is materialised.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_flag_on_national_id_only_falls_back_to_auto_link(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _mfa_headers(user["id"], user["role"], wsid)

    payload = _student_payload(parent={
        "full_name": "والد بالهوية",
        "national_id": "1098765432",
    })
    with _flag_on():
        resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # No deliverable channel → invite envelope skipped, auto-link taken.
    assert body["parent_onboarding"]["mode"] == "linked"
    sid = body["student"]["id"]
    row = await gd_find_one(db.session, "students", {"id": sid})
    assert row.get("parent_id") is not None
    assert await gd_count(db.session, "parents", {"school_id": wsid}) == 1

    # No invitation row — national_id alone is not a deliverable channel.
    assert await gd_count(
        db.session, "parent_invitations", {"workspace_school_id": wsid}
    ) == 0


# ----------------------------------------------------------------------
# (d) Fresh MFA is required BEFORE any DB write on the invite path.
# Without a recent passkey proof the create returns the 403 step-up
# envelope and persists neither the student nor an invitation.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_flag_on_invite_path_requires_recent_mfa(client, monkeypatch):
    # The test env runs with the demo kill switch on; force enforcement so
    # the step-up gate actually fires. is_enforcement_disabled() reads the
    # env fresh on every call, so this takes effect immediately.
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "false")
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)  # no mfa_recent_at

    payload = _student_payload(parent={
        "full_name": "ولي بلا تحقق",
        "email": "no-mfa@example.com",
    })
    with _flag_on():
        resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 403, resp.text
    body = resp.json()
    code = (body.get("error") or {}).get("code") or (
        body.get("detail") if isinstance(body.get("detail"), dict) else {}
    ).get("code")
    assert code in {
        "MFA_STEPUP_REQUIRED", "MFA_PASSKEY_REQUIRED", "MFA_RESTORE_REQUIRED",
    }

    # The guard runs BEFORE any write — no student, no invitation persisted.
    assert await gd_count(db.session, "students", {"school_id": wsid}) == 0
    assert await gd_count(
        db.session, "parent_invitations", {"workspace_school_id": wsid}
    ) == 0


# ----------------------------------------------------------------------
# (e) The raw invitation token must NEVER appear in the API JSON response
# except embedded inside `parent_onboarding.invite_link`.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invite_token_only_appears_in_invite_link(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _mfa_headers(user["id"], user["role"], wsid)

    payload = _student_payload(parent={
        "full_name": "ولي مدعو",
        "email": "leak-check@example.com",
    })
    with _flag_on(), patch(
        "routes.academics_student_routes.send_parent_invitation_email"
    ):
        resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    onboarding = body["parent_onboarding"]

    invite_link = onboarding["invite_link"]
    # Pull the raw token out of the deep-link query string.
    assert "token=" in invite_link
    raw_token = invite_link.split("token=", 1)[1].split("&", 1)[0]
    assert raw_token

    # No top-level (or nested) `token` key anywhere in the envelope.
    def _no_token_key(obj):
        if isinstance(obj, dict):
            assert "token" not in obj, f"unexpected raw token key in {obj!r}"
            for v in obj.values():
                _no_token_key(v)
        elif isinstance(obj, list):
            for v in obj:
                _no_token_key(v)

    _no_token_key(body)

    # The raw token string must not appear anywhere else once invite_link
    # is removed from the serialized response.
    onboarding_wo_link = {k: v for k, v in onboarding.items() if k != "invite_link"}
    scrubbed = dict(body)
    scrubbed["parent_onboarding"] = onboarding_wo_link
    assert raw_token not in json.dumps(scrubbed, ensure_ascii=False)

    # The persisted invitation stores only the token HASH, never the raw token.
    invitations = await gd_find(
        db.session, "parent_invitations", {"workspace_school_id": wsid}
    )
    assert len(invitations) == 1
    assert invitations[0].get("token_hash")
    assert invitations[0].get("token_hash") != raw_token
