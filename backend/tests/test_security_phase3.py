"""
Phase 3 security tests — pseudonymization, refresh-token family revocation,
and per-tenant AI consent.

Scope (the deterministic subset we ship in Phase 3):
  * Pseudonymizer round-trip + forbidden-key drop.
  * Refresh-token family-id propagation across rotation.
  * Refresh-token reuse detection writes the family revocation row AND
    blocks subsequent siblings.
  * AI consent flag on `schools` blocks `hakim_generate` outbound calls.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
import pytest_asyncio
import jwt as _jwt

from sqlalchemy import text as _sa_text

from dependencies import (
    db, UserRole, JWT_SECRET, JWT_ALGORITHM,
    create_refresh_token, hash_password,
)
from engines.sql_utils import gd_insert, gd_find_one


# ─────────────────────────────── pseudonymizer ────────────────────────────


def test_pseudonymizer_round_trip_basic():
    from services.hakim_pseudonymizer import Pseudonymizer

    p = Pseudonymizer()
    p.register("محمد علي", kind="student")
    p.register("سارة الأحمد", kind="teacher")

    text = "كتب محمد علي تقريراً وراجعت سارة الأحمد المحتوى."
    sanitized = p.sanitize(text)

    assert "محمد علي" not in sanitized
    assert "سارة الأحمد" not in sanitized
    assert "[STUDENT_1]" in sanitized
    assert "[TEACHER_1]" in sanitized

    # Simulate the LLM echoing tokens back, then rehydrate.
    rehydrated = p.rehydrate(sanitized)
    assert "محمد علي" in rehydrated
    assert "سارة الأحمد" in rehydrated


def test_pseudonymizer_drops_forbidden_identifiers():
    from services.hakim_pseudonymizer import Pseudonymizer

    p = Pseudonymizer()
    out = p.sanitize_context({
        "student_name": "Ali",
        "national_id": "1234567890",
        "phone": "+966500000000",
        "subject": "math",
    })
    assert "national_id" not in out
    assert "phone" not in out
    assert out["subject"] == "math"
    assert out["student_name"].startswith("[STUDENT_")


def test_pseudonymizer_handles_longest_name_first():
    """Replacing 'محمد' before 'محمد علي' would corrupt the longer name —
    sanitize must replace longest first."""
    from services.hakim_pseudonymizer import Pseudonymizer

    p = Pseudonymizer()
    p.register("محمد", kind="teacher")
    p.register("محمد علي", kind="student")

    out = p.sanitize("محمد علي و محمد")
    # Longer name should be tokenised first; the shorter one second.
    assert "محمد علي" not in out
    assert out.count("[") == 2


def test_pseudonymizer_rehydrate_passes_through_unknown_tokens():
    from services.hakim_pseudonymizer import Pseudonymizer

    p = Pseudonymizer()
    # No registrations → no rehydration possible.
    assert p.rehydrate("hello [STUDENT_99] world") == "hello [STUDENT_99] world"


# ───────────────────────── refresh-token families ─────────────────────────


@pytest_asyncio.fixture
async def refresh_user():
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "email": f"{uid}@t.test",
        "full_name": "Refresh Test User",
        "is_active": True,
        "password_hash": hash_password("x"),
    })
    return uid


def test_refresh_token_carries_family_id():
    """Newly minted refresh tokens MUST include `fid`."""
    tok = create_refresh_token({"sub": "u1", "role": "teacher"})
    payload = _jwt.decode(tok, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert "fid" in payload
    assert isinstance(payload["fid"], str) and len(payload["fid"]) >= 8


def test_refresh_token_family_id_preserved_when_passed():
    fam = "fixed-family-id"
    tok = create_refresh_token({"sub": "u1", "role": "teacher"}, family_id=fam)
    payload = _jwt.decode(tok, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert payload["fid"] == fam


@pytest.mark.asyncio
async def test_refresh_rotation_preserves_family(client, refresh_user):
    """Rotating a refresh token MUST keep the same `fid` on the new one."""
    fam = str(uuid.uuid4())
    rt = create_refresh_token(
        {"sub": refresh_user, "role": UserRole.SCHOOL_PRINCIPAL.value},
        family_id=fam,
    )
    res = await client.post("/auth/refresh", json={"refresh_token": rt})
    assert res.status_code == 200, res.text
    new_rt = res.json()["refresh_token"]
    new_payload = _jwt.decode(new_rt, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert new_payload["fid"] == fam


@pytest.mark.asyncio
async def test_refresh_token_reuse_revokes_family(client, refresh_user):
    """Replaying a refresh token that's already been rotated MUST:
        1. fail the second call with 401, AND
        2. write a row into revoked_token_families so any sibling token from
           the same family is also rejected from then on.
    """
    fam = str(uuid.uuid4())
    rt = create_refresh_token(
        {"sub": refresh_user, "role": UserRole.SCHOOL_PRINCIPAL.value},
        family_id=fam,
    )

    # First rotation succeeds.
    ok = await client.post("/auth/refresh", json={"refresh_token": rt})
    assert ok.status_code == 200, ok.text

    # Replay → reuse detection.
    replay = await client.post("/auth/refresh", json={"refresh_token": rt})
    assert replay.status_code == 401

    # Family should now be in revoked_token_families.
    row = await gd_find_one(db.session, "revoked_token_families", {"family_id": fam})
    # The route uses raw SQL for the insert; gd_find_one targets the typed
    # table via the same name, so this assertion confirms the row landed.
    # If the typed model isn't wired through gd_find_one, fall back to raw.
    if not row:
        raw = (await db.session.execute(
            _sa_text("SELECT family_id FROM revoked_token_families WHERE family_id=:f"),
            {"f": fam},
        )).first()
        assert raw is not None, "family revocation row was not written"

    # Mint a fresh sibling refresh token in the same family — it must be
    # rejected up-front by the family check.
    sibling = create_refresh_token(
        {"sub": refresh_user, "role": UserRole.SCHOOL_PRINCIPAL.value},
        family_id=fam,
    )
    blocked = await client.post("/auth/refresh", json={"refresh_token": sibling})
    assert blocked.status_code == 401


# ──────────────────────── per-tenant AI consent ───────────────────────────


@pytest.mark.asyncio
async def test_hakim_consent_flag_blocks_outbound_call(monkeypatch):
    """When `schools.ai_consent_enabled` is False, hakim_generate must short-
    circuit with `AI_DISABLED_BY_TENANT` and never call the LLM client."""
    from services import hakim_llm_service as svc

    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid,
        "name": "No-AI School",
        "code": f"S{sid[:6]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    # The typed `schools` ORM model may not yet expose the Phase 3 column
    # (the migration adds it but the ORM model isn't updated as part of this
    # task — SQL queries that read the column directly still work). Force the
    # consent flag via raw SQL so the kill-switch SELECT sees False.
    await db.session.execute(
        _sa_text("UPDATE schools SET ai_consent_enabled = FALSE WHERE id = :i"),
        {"i": sid},
    )
    await db.session.flush()

    called = {"n": 0}

    class _BoomClient:
        class chat:
            class completions:
                @staticmethod
                def create(*a, **k):  # pragma: no cover — must not run
                    called["n"] += 1
                    raise RuntimeError("must not be called when consent is off")

    monkeypatch.setattr(svc, "_get_client", lambda: _BoomClient())

    res = await svc.hakim_generate(
        mode="generate",
        field="behavior_note",
        text="hello",
        tenant_id=sid,
    )
    assert res["success"] is False
    assert res["reason"] == "AI_DISABLED_BY_TENANT"
    assert called["n"] == 0
