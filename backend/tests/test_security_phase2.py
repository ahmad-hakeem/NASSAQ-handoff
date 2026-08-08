"""
Phase 2 security tests (audit C-1, H-2, M-4, M-6).

Covers:
  * trusted-proxy IP extraction (XFF only honoured for allow-listed peers)
  * impersonation persistence + JTI-bound restore (the H-2 IDOR fix)
  * audit-sink emit and drop-on-overflow + redaction
"""
from __future__ import annotations

import asyncio
import importlib
import os
import uuid

import pytest
import pytest_asyncio

from sqlalchemy import text as _sa_text

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find_one


# ───────────────────────────── trusted_proxy ──────────────────────────────


def _make_request(peer: str, headers: dict | None = None):
    """Build the smallest object that quacks like a Starlette Request for
    extract_client_ip (it only touches `.client.host` and `.headers.get`)."""
    class _Client:
        host = peer

    class _Headers(dict):
        def get(self, key, default=None):  # noqa: D401
            return super().get(key.lower(), default)

    class _Req:
        client = _Client()

        def __init__(self, hdrs):
            self.headers = _Headers({k.lower(): v for k, v in (hdrs or {}).items()})

    return _Req(headers or {})


def _reload_trusted_proxy():
    import utils.trusted_proxy as tp
    importlib.reload(tp)
    return tp


def test_untrusted_peer_ignores_xff(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_CIDRS", raising=False)
    tp = _reload_trusted_proxy()
    req = _make_request("203.0.113.7", {"X-Forwarded-For": "1.2.3.4"})
    assert tp.extract_client_ip(req) == "203.0.113.7"


def test_trusted_peer_honours_xff(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "10.0.0.0/8")
    tp = _reload_trusted_proxy()
    req = _make_request("10.5.5.5", {"X-Forwarded-For": "203.0.113.99, 10.5.5.5"})
    assert tp.extract_client_ip(req) == "203.0.113.99"


def test_trusted_peer_falls_back_to_real_ip(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "10.0.0.0/8")
    tp = _reload_trusted_proxy()
    req = _make_request("10.5.5.5", {"X-Real-IP": "198.51.100.4"})
    assert tp.extract_client_ip(req) == "198.51.100.4"


def test_invalid_cidr_is_ignored_safely(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "not-a-cidr,10.0.0.0/8")
    tp = _reload_trusted_proxy()
    req = _make_request("10.0.0.1", {"X-Forwarded-For": "9.9.9.9"})
    assert tp.extract_client_ip(req) == "9.9.9.9"


# ───────────────────────────── impersonation ──────────────────────────────


@pytest_asyncio.fixture
async def platform_admin():
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.PLATFORM_ADMIN.value,
        "email": f"{uid}@t.test",
        "full_name": "Platform Admin",
        "is_active": True,
        "password_hash": "x",
    })
    return uid


@pytest_asyncio.fixture
async def target_school():
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid,
        "name": "Target School",
        "code": f"S{sid[:6]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    # Preview eligibility requires an ACTIVE school principal in the target
    # school (no_active_principal guard) — seed one so /role-switch/switch
    # to school_principal is permitted.
    pid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": pid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": sid,
        "email": f"principal-{pid[:8]}@t.test",
        "full_name": "Seed Principal",
        "is_active": True,
        "password_hash": "x",
    })
    return sid


def _bearer(uid: str, role: str, tenant_id: str | None = None) -> dict:
    tok = create_access_token({"sub": uid, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {tok}"}


@pytest.mark.asyncio
async def test_role_switch_requires_reason(client, platform_admin, target_school):
    headers = _bearer(platform_admin, UserRole.PLATFORM_ADMIN.value)
    res = await client.post(
        "/role-switch/switch",
        json={"target_role": UserRole.SCHOOL_PRINCIPAL.value, "school_id": target_school},
        headers=headers,
    )
    # No reason → 400
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_role_switch_persists_session_and_caps_ttl(client, platform_admin, target_school):
    import jwt as _jwt
    from dependencies import JWT_SECRET, JWT_ALGORITHM

    headers = _bearer(platform_admin, UserRole.PLATFORM_ADMIN.value)
    res = await client.post(
        "/role-switch/switch",
        json={
            "target_role": UserRole.SCHOOL_PRINCIPAL.value,
            "school_id": target_school,
            "reason": "QA review session",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    tok = res.json()["token"]
    payload = _jwt.decode(tok, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    # 15-minute cap (allow 1-min jitter)
    import time
    now = time.time()
    assert payload["exp"] - now < 16 * 60
    assert payload["exp"] - now > 14 * 60

    row = (await db.session.execute(
        _sa_text("SELECT original_user_id, target_role, ended_at, reason FROM impersonation_sessions WHERE jti=:j"),
        {"j": payload["jti"]},
    )).mappings().first()
    assert row is not None
    assert row["original_user_id"] == platform_admin
    assert row["target_role"] == UserRole.SCHOOL_PRINCIPAL.value
    assert row["ended_at"] is None
    assert row["reason"] == "QA review session"


@pytest.mark.asyncio
async def test_restore_ignores_forged_original_user_id(client, platform_admin, target_school):
    """A switched-token holder cannot restore as a *different* user even if
    they forge `original_user_id` in the JWT — restore must only consult
    the server-side `impersonation_sessions` row keyed by JTI."""
    # 1. Legit switch.
    headers = _bearer(platform_admin, UserRole.PLATFORM_ADMIN.value)
    res = await client.post(
        "/role-switch/switch",
        json={
            "target_role": UserRole.SCHOOL_PRINCIPAL.value,
            "school_id": target_school,
            "reason": "QA review session",
        },
        headers=headers,
    )
    assert res.status_code == 200
    switched = res.json()["token"]

    # 2. Mint a *forged* switched token: same JTI as legit, but
    #    `original_user_id` claims a victim user. The endpoint must
    #    ignore that claim and resolve the row's persisted owner.
    import jwt as _jwt
    from dependencies import JWT_SECRET, JWT_ALGORITHM

    legit = _jwt.decode(switched, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    victim_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": victim_id,
        "role": UserRole.PLATFORM_ADMIN.value,
        "email": f"{victim_id}@t.test",
        "full_name": "Victim",
        "is_active": True,
        "password_hash": "x",
    })

    forged_payload = dict(legit)
    forged_payload["original_user_id"] = victim_id
    forged = _jwt.encode(forged_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    res2 = await client.post(
        "/role-switch/restore",
        headers={"Authorization": f"Bearer {forged}"},
    )
    assert res2.status_code == 200, res2.text
    body = res2.json()
    assert body["restored"] is True
    # Restored token must be issued for the platform admin (the row owner),
    # NOT the victim id from the forged claim.
    new_tok = body["token"]
    new_payload = _jwt.decode(new_tok, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert new_payload["sub"] == platform_admin
    assert new_payload["sub"] != victim_id


@pytest.mark.asyncio
async def test_restore_rejects_unknown_jti(client, platform_admin):
    """A switched-style token whose JTI has no server-side row must 401."""
    import jwt as _jwt
    from dependencies import JWT_SECRET, JWT_ALGORITHM

    tok = create_access_token({
        "sub": platform_admin,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "original_role": UserRole.PLATFORM_ADMIN.value,
        "original_user_id": platform_admin,
        "tenant_id": None,
        "is_impersonating": True,
    })
    res = await client.post(
        "/role-switch/restore",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert res.status_code == 401


# ───────────────────────────── audit_sink ─────────────────────────────────


@pytest.mark.asyncio
async def test_audit_sink_writes_to_file(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_SINK_BACKEND", "file")
    target = tmp_path / "audit.log"
    monkeypatch.setenv("AUDIT_SINK_PATH", str(target))
    monkeypatch.setenv("AUDIT_SINK_QUEUE_MAX", "100")

    import services.audit_sink as sink_mod
    importlib.reload(sink_mod)

    sink_mod.emit_audit({
        "action": "role_switch.start",
        "original_user_id": "u-1",
        # Sensitive keys must be redacted in the on-disk payload.
        "password": "supersecret",
        "access_token": "eyJxxx",
    })

    # Drain the worker.
    for _ in range(50):
        await asyncio.sleep(0.02)
        if target.exists() and target.stat().st_size > 0:
            break

    assert target.exists()
    contents = target.read_text(encoding="utf-8")
    assert "role_switch.start" in contents
    assert "supersecret" not in contents
    assert "eyJxxx" not in contents
    assert "***REDACTED***" in contents


@pytest.mark.asyncio
async def test_audit_sink_drops_on_overflow(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDIT_SINK_BACKEND", "file")
    monkeypatch.setenv("AUDIT_SINK_PATH", str(tmp_path / "overflow.log"))
    monkeypatch.setenv("AUDIT_SINK_QUEUE_MAX", "2")

    import services.audit_sink as sink_mod
    importlib.reload(sink_mod)

    # Block the worker by monkeypatching the backend write to a long sleep.
    async def _slow(_payload):  # noqa: D401
        await asyncio.sleep(5)

    sink_mod.audit_sink._backend.write = _slow  # type: ignore[attr-defined]

    # Prime the worker so the queue exists.
    sink_mod.audit_sink.emit({"action": "x"})
    await asyncio.sleep(0)  # let the worker pick up the first item

    # Now flood; max=2 means a few of these MUST be dropped.
    for i in range(50):
        sink_mod.audit_sink.emit({"action": "flood", "i": i})

    # Give the loop a tick.
    await asyncio.sleep(0.05)
    assert sink_mod.audit_sink.dropped > 0
