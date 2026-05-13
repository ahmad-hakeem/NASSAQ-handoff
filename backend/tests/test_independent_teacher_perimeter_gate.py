"""Task #186 — pin the IT perimeter-gate FE/BE contract.

The frontend axios interceptor (`AuthContext.js`) handles the
"workspace not yet materialised" guidance dialog by matching on the
exact tuple `(status == 409, detail == WORKSPACE_NOT_MATERIALISED_AR)`.

This test locks that contract so a future backend refactor cannot
silently break the FE handler — if either the status or the safe
Arabic detail string drifts, this test will fail and the FE/BE
constants must be re-aligned together.
"""
import time
import uuid

import pytest
from datetime import datetime, timezone

from auth_scope import WORKSPACE_NOT_MATERIALISED_AR
from dependencies import UserRole, create_access_token, db
from engines.sql_utils import gd_insert


def _headers(user_id: str, role: str, mfa_recent_at=None) -> dict:
    token = create_access_token(
        {"sub": user_id, "role": role, "tenant_id": None},
        mfa_recent_at=mfa_recent_at,
        mfa_kind="totp" if mfa_recent_at else None,
    )
    return {"Authorization": f"Bearer {token}"}


async def _mk_pre_bootstrap_it() -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-perimeter-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "users", user)
    return user


def _extract_detail(body: dict) -> str:
    """Mirror the FE interceptor's `detailMessage` extraction shape."""
    detail = body.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        msg = detail.get("message")
        if isinstance(msg, str):
            return msg
    err = body.get("error") or {}
    if isinstance(err, dict):
        msg = err.get("message")
        if isinstance(msg, str):
            return msg
    return ""


@pytest.mark.asyncio
async def test_perimeter_gate_emits_canonical_409_and_safe_arabic_detail(client):
    """Pre-bootstrap IT hitting any non-allowlisted route → 409 + safe AR."""
    user = await _mk_pre_bootstrap_it()
    h = _headers(user["id"], user["role"], mfa_recent_at=int(time.time()))

    resp = await client.get("/students", headers=h)

    assert resp.status_code == 409, resp.text
    detail = _extract_detail(resp.json())
    assert detail == WORKSPACE_NOT_MATERIALISED_AR, (
        f"FE/BE contract drift: detail={detail!r} expected={WORKSPACE_NOT_MATERIALISED_AR!r}"
    )


@pytest.mark.asyncio
async def test_perimeter_gate_emits_same_contract_on_post_routes(client):
    """The contract holds for mutating routes too (axios interceptor is
    method-agnostic)."""
    user = await _mk_pre_bootstrap_it()
    h = _headers(user["id"], user["role"], mfa_recent_at=int(time.time()))

    resp = await client.post("/students", headers=h, json={"full_name": "x"})

    assert resp.status_code == 409, resp.text
    assert _extract_detail(resp.json()) == WORKSPACE_NOT_MATERIALISED_AR
