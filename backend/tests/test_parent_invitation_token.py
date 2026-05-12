"""Unit tests for the IT Phase-2 §6.2a parent-invitation token helper.

Covers (per task #204 "Done looks like"):
  * mint → verify happy path.
  * single-use guard: a re-used token fails verification once the
    stored hash is cleared (status=accepted lifecycle).
  * expired tokens fail verification.
  * tampered signatures fail verification.
  * cross-student / cross-workspace replay rejection.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt

from dependencies import JWT_SECRET, JWT_ALGORITHM
from utils.tokens import (
    INVITATION_TOKEN_TTL,
    mint_invitation_token,
    token_hash,
    verify_invitation_token,
)


WS = "itw_test-workspace-1"
WS2 = "itw_test-workspace-2"
STU = "stu-aaaa"
STU2 = "stu-bbbb"


def test_mint_returns_seven_day_expiry_and_correct_hash():
    raw, h, exp = mint_invitation_token(WS, STU)
    assert isinstance(raw, str) and raw
    assert h == token_hash(raw)
    delta = exp - datetime.now(timezone.utc)
    # Allow a small clock-skew window; must be ~7 days.
    assert INVITATION_TOKEN_TTL - timedelta(seconds=5) <= delta <= INVITATION_TOKEN_TTL


def test_verify_happy_path_then_single_use_after_hash_cleared():
    raw, h, _ = mint_invitation_token(WS, STU)
    assert verify_invitation_token(
        raw, h, workspace_school_id=WS, student_id=STU,
    ) is True
    # Lifecycle: §6.2b's accept route flips status=accepted and clears
    # token_hash. A replay against the cleared row must fail.
    cleared = ""
    assert verify_invitation_token(
        raw, cleared, workspace_school_id=WS, student_id=STU,
    ) is False


def test_verify_rejects_expired_token():
    past = datetime.now(timezone.utc) - timedelta(days=8)
    with patch("utils.tokens.datetime") as dt:
        dt.now.return_value = past
        # mint_invitation_token uses datetime.now() AND timedelta math;
        # patch only `datetime.now` so timedelta arithmetic still works.
        dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        raw, h, _ = mint_invitation_token(WS, STU)
    assert verify_invitation_token(
        raw, h, workspace_school_id=WS, student_id=STU,
    ) is False


def test_verify_rejects_tampered_signature():
    raw, h, _ = mint_invitation_token(WS, STU)
    # Flip the last char of the signature segment.
    head, body, sig = raw.split(".")
    bad_sig = sig[:-1] + ("A" if sig[-1] != "A" else "B")
    tampered = f"{head}.{body}.{bad_sig}"
    assert verify_invitation_token(
        tampered, h, workspace_school_id=WS, student_id=STU,
    ) is False


def test_verify_rejects_cross_student_replay():
    raw, h, _ = mint_invitation_token(WS, STU)
    assert verify_invitation_token(
        raw, h, workspace_school_id=WS, student_id=STU2,
    ) is False


def test_verify_rejects_cross_workspace_replay():
    raw, h, _ = mint_invitation_token(WS, STU)
    assert verify_invitation_token(
        raw, h, workspace_school_id=WS2, student_id=STU,
    ) is False


def test_verify_rejects_wrong_purpose_jwt():
    # A JWT signed by the same secret but for a different purpose
    # (e.g. password reset) must NEVER verify as an invitation token.
    now = datetime.now(timezone.utc)
    other = jwt.encode(
        {
            "purpose": "password_reset",
            "ws": WS, "stu": STU,
            "iat": now, "exp": now + timedelta(hours=1),
        },
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )
    assert verify_invitation_token(
        other, token_hash(other),
        workspace_school_id=WS, student_id=STU,
    ) is False


def test_verify_rejects_empty_inputs():
    assert verify_invitation_token("", "x", workspace_school_id=WS, student_id=STU) is False
    assert verify_invitation_token("x", "", workspace_school_id=WS, student_id=STU) is False
