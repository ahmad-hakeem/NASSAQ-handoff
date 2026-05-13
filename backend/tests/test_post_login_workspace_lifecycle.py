"""Task #236 — post-login workspace lifecycle embedding (Task #231 regression guard).

Pins the contract that ``/auth/login`` and ``/auth/mfa/verify`` embed a
populated ``workspace_lifecycle.reactivation_banner`` block for a freshly
reactivated Independent-Teacher caller, and ``workspace_lifecycle: None``
for a non-IT caller. A regression here would silently bring back the
late-pop banner that Task #231 was filed to fix.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

# Ensure the MFA crypto key is set BEFORE importing dependencies that
# transitively pull it in (mirrors test_mfa.py).
os.environ.setdefault(
    "MFA_ENCRYPTION_KEY",
    os.environ.get("MFA_ENCRYPTION_KEY", "")
    or "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
)

from dependencies import db, UserRole, hash_password  # noqa: E402
from engines.sql_utils import gd_insert, gd_update_one  # noqa: E402
from auth_scope import independent_workspace_id  # noqa: E402
from services import mfa_crypto  # noqa: E402

from tests._it_fixtures import seed_active_passkey  # noqa: E402


_PASS = "Test@1234!"


async def _mk_it_user_with_password(*, with_passkey: bool) -> dict:
    """Create a real Independent-Teacher user + workspace whose
    ``password_hash`` actually verifies, so we can drive the public
    ``/auth/login`` route end-to-end (the shared `mk_it_workspace`
    fixture stores ``password_hash="x"`` for direct-token tests)."""
    uid = str(uuid.uuid4())
    email = f"it-{uid}@nassaq-test.com"
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": email,
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": hash_password(_PASS),
        "mfa_enrolled_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    user["tenant_id"] = wsid
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-Workspace-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher_workspace",
    })
    if with_passkey:
        await seed_active_passkey(uid)
    return {"user": user, "uid": uid, "wsid": wsid, "email": email}


async def _mark_reactivated(wsid: str, *, days_archived: int = 2) -> None:
    """Stamp the workspace as if it had just been reactivated after a
    ``days_archived``-day archive cycle. Mirrors the column state the
    real archive→reactivate flow leaves behind so the banner gate
    (``last_reactivated_at > reactivation_banner_dismissed_at`` AND
    a populated ``last_archive_cycle_archived_at``) trips."""
    now = datetime.now(timezone.utc)
    archived_at = (now - timedelta(days=days_archived)).isoformat()
    await gd_update_one(db.session, "schools", {"id": wsid}, {
        "status": "active",
        "archived_at": None,
        "last_reactivated_at": now.isoformat(),
        "last_archive_cycle_archived_at": archived_at,
        "reactivation_banner_dismissed_at": None,
    })


# ---------------------------------------------------------------------------
# /auth/login
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_embeds_reactivation_banner_for_freshly_reactivated_it_user(client):
    """Direct ``/auth/login`` (no MFA factor) must surface a populated
    ``workspace_lifecycle.reactivation_banner`` so the dashboard paints
    the banner in the same frame as the rest of the page."""
    ctx = await _mk_it_user_with_password(with_passkey=False)
    await _mark_reactivated(ctx["wsid"], days_archived=2)

    resp = await client.post(
        "/auth/login",
        json={"email": ctx["email"], "password": _PASS},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Direct-token path (no MFA challenge).
    assert body.get("access_token"), body
    lifecycle = body.get("workspace_lifecycle")
    assert lifecycle is not None, "expected embedded workspace_lifecycle for IT login"
    banner = lifecycle.get("reactivation_banner")
    assert banner is not None, "expected non-null reactivation_banner for freshly reactivated IT user"
    assert banner["reactivated_at"]
    assert banner["archived_at"]
    assert banner["reactivation_window_days"] == 30
    # 30-day window minus ~2 days archived ⇒ ~28 days remaining.
    assert banner["days_remaining_at_reactivation"] in (27, 28)


@pytest.mark.asyncio
async def test_login_returns_null_workspace_lifecycle_for_non_it_user(client, tenant_a):
    """Non-IT callers (here: a school principal with no MFA factor) must
    receive ``workspace_lifecycle: None`` — the banner snapshot is an
    IT-only side-channel."""
    uid = str(uuid.uuid4())
    email = f"princ-{uid}@nassaq-test.com"
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": tenant_a,
        "email": email,
        "full_name": f"Principal-{uid[:6]}",
        "is_active": True,
        "password_hash": hash_password(_PASS),
    })
    resp = await client.post(
        "/auth/login",
        json={"email": email, "password": _PASS},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("access_token"), body
    assert body.get("workspace_lifecycle") is None, (
        "non-IT login must NOT carry a workspace_lifecycle snapshot"
    )


# ---------------------------------------------------------------------------
# /auth/mfa/verify
# ---------------------------------------------------------------------------

async def _seed_recovery_code(user_id: str) -> str:
    plaintext = mfa_crypto.generate_recovery_code()
    await gd_insert(db.session, "mfa_recovery_codes", {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "code_hash": mfa_crypto.hash_recovery_code(plaintext),
        "created_at": datetime.now(timezone.utc),
        "consumed_at": None,
    })
    return plaintext


@pytest.mark.asyncio
async def test_mfa_verify_embeds_reactivation_banner_for_freshly_reactivated_it_user(client):
    """The post-MFA token mint must also embed ``workspace_lifecycle``,
    not just the direct-token /auth/login path. We drive a real login →
    challenge → recovery_code verify cycle so any regression in the
    embed inside ``_complete_mfa_login``'s caller surfaces here."""
    ctx = await _mk_it_user_with_password(with_passkey=True)
    await _mark_reactivated(ctx["wsid"], days_archived=2)
    plaintext = await _seed_recovery_code(ctx["uid"])

    login = await client.post(
        "/auth/login",
        json={"email": ctx["email"], "password": _PASS},
    )
    assert login.status_code == 200, login.text
    challenge_token = login.json().get("challenge_token")
    assert challenge_token, "expected MFA challenge for IT user with active passkey"

    verify = await client.post(
        "/auth/mfa/verify",
        json={"factor_kind": "recovery_code", "code": plaintext},
        headers={"Authorization": f"Bearer {challenge_token}"},
    )
    assert verify.status_code == 200, verify.text
    body = verify.json()
    assert body.get("access_token"), body
    lifecycle = body.get("workspace_lifecycle")
    assert lifecycle is not None, "expected embedded workspace_lifecycle on /auth/mfa/verify"
    banner = lifecycle.get("reactivation_banner")
    assert banner is not None, (
        "expected non-null reactivation_banner on /auth/mfa/verify for freshly reactivated IT user"
    )
    assert banner["reactivated_at"]
    assert banner["archived_at"]
    assert banner["reactivation_window_days"] == 30
    assert banner["days_remaining_at_reactivation"] in (27, 28)
