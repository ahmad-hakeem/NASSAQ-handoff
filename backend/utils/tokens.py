"""Shared single-use token helpers.

This module owns the canonical hash scheme used by every NASSAQ
single-use token (password reset, parent invitation, …) so the
algorithm lives in exactly one place. Callers MUST go through these
helpers — never re-implement ``hashlib.sha256`` inline.

Currently exposed:

* ``token_hash(raw_token)`` — sha256 hex digest. Reused by
  ``backend/routes/auth_routes_mod.py`` for ``users.reset_token_hash``
  and by this module for ``parent_invitations.token_hash``.

* ``mint_invitation_token(workspace_school_id, student_id)`` /
  ``verify_invitation_token(raw_token, stored_hash, *, workspace_school_id, student_id)``
  — the IT Phase-2 §6.2 parent-invitation token contract.

Design notes
------------
* The token is a JWT signed with ``JWT_SECRET`` (alias of the
  platform ``SECRET_KEY``) carrying ``ws`` (workspace school id) and
  ``stu`` (student id) claims. A token minted for student A in
  workspace W cannot be replayed against student B or workspace W2 —
  ``verify_invitation_token`` rejects any mismatch BEFORE comparing
  the stored hash, so a leaked token is bound to its target row.

* Hash equality is the single-use guard: once §6.2b's accept route
  flips ``parent_invitations.status`` to ``accepted`` and clears
  ``token_hash`` (or rotates the row to a terminal state), the next
  ``verify_invitation_token`` call returns False because the stored
  hash no longer matches. This mirrors the password-reset pattern.

* Expiry is 7 days, computed at mint time and embedded both as the
  JWT ``exp`` claim AND returned as a ``datetime`` so the caller can
  persist it in ``parent_invitations.expires_at``. The JWT ``exp``
  alone is enforced by ``jwt.decode``; the DB column is a defensive
  belt-and-suspenders for the cancel/expire sweep §6.2b will run.
"""
from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from typing import Tuple

import jwt

from dependencies import JWT_SECRET, JWT_ALGORITHM


INVITATION_TOKEN_TTL = timedelta(days=7)
_INVITATION_PURPOSE = "parent_invitation"
_COLLAB_INVITATION_PURPOSE = "workspace_collab_invitation"
COLLAB_INVITATION_TOKEN_TTL = timedelta(days=7)


def token_hash(raw_token: str) -> str:
    """Return the canonical sha256 hex digest of a single-use token.

    Reused by password-reset and parent-invitation flows so the hash
    scheme lives in one place. Callers MUST NOT re-implement.
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()


def mint_invitation_token(
    workspace_school_id: str,
    student_id: str,
) -> Tuple[str, str, datetime]:
    """Mint a one-shot signed parent-invitation token.

    Returns ``(raw_token, token_hash, expires_at)``:

    * ``raw_token``    — the JWT to embed in the deep link / email.
                         Treat as a secret; never log.
    * ``token_hash``   — sha256 hex digest to persist in
                         ``parent_invitations.token_hash``. Equality
                         against this is the single-use guard.
    * ``expires_at``   — 7-day expiry, timezone-aware UTC, suitable
                         for ``parent_invitations.expires_at``.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + INVITATION_TOKEN_TTL
    payload = {
        "purpose": _INVITATION_PURPOSE,
        "ws": workspace_school_id,
        "stu": student_id,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expires_at,
    }
    raw = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return raw, token_hash(raw), expires_at


def verify_invitation_token(
    raw_token: str,
    stored_hash: str,
    *,
    workspace_school_id: str,
    student_id: str,
) -> bool:
    """Verify a parent-invitation token in constant time.

    Returns True only when ALL of the following hold:

    * ``raw_token`` is a well-formed JWT signed by ``JWT_SECRET``.
    * The JWT has not expired and carries ``purpose=parent_invitation``.
    * The JWT's ``ws`` / ``stu`` claims match the row the caller is
      attempting to accept (prevents cross-student / cross-workspace
      replay of a leaked token).
    * ``token_hash(raw_token) == stored_hash`` (constant-time compare).

    Returns False on any failure — never raises.
    """
    if not raw_token or not stored_hash:
        return False
    try:
        payload = jwt.decode(raw_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return False
    if payload.get("purpose") != _INVITATION_PURPOSE:
        return False
    if payload.get("ws") != workspace_school_id:
        return False
    if payload.get("stu") != student_id:
        return False
    return hmac.compare_digest(token_hash(raw_token), stored_hash)


def mint_collab_invitation_token(
    host_school_id: str,
    class_id: str,
    collaborator_email: str,
) -> Tuple[str, str, datetime]:
    """Mint a one-shot signed workspace-collaborator invitation token (§6.7).

    Bound to the ``(host_school_id, class_id, collaborator_email)`` triple
    so a leaked token cannot be replayed against a different class, host,
    or invitee.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + COLLAB_INVITATION_TOKEN_TTL
    payload = {
        "purpose": _COLLAB_INVITATION_PURPOSE,
        "host": host_school_id,
        "cls": class_id,
        "email": collaborator_email.lower(),
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expires_at,
    }
    raw = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return raw, token_hash(raw), expires_at


def verify_collab_invitation_token(
    raw_token: str,
    stored_hash: str,
    *,
    host_school_id: str,
    class_id: str,
    collaborator_email: str,
) -> bool:
    """Verify a collab-invitation token in constant time."""
    if not raw_token or not stored_hash:
        return False
    try:
        payload = jwt.decode(raw_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return False
    if payload.get("purpose") != _COLLAB_INVITATION_PURPOSE:
        return False
    if payload.get("host") != host_school_id:
        return False
    if payload.get("cls") != class_id:
        return False
    if (payload.get("email") or "").lower() != (collaborator_email or "").lower():
        return False
    return hmac.compare_digest(token_hash(raw_token), stored_hash)
