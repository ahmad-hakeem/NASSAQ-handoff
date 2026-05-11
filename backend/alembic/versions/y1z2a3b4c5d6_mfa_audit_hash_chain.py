"""mfa phase 2 — populate per-tenant hash chain on insert (mfa.* scope)

Revision ID: y1z2a3b4c5d6
Revises: x1y2z3a4b5c6
Create Date: 2026-05-11

Phase 1 (revision ``x1y2z3a4b5c6``) already added the
``audit_logs.prev_hash`` and ``audit_logs.row_hash`` columns plus the
``audit_logs_mfa_immutable_trg`` trigger that refuses UPDATE/DELETE on any
row whose ``action`` starts with ``mfa.``.

What was missing — and what this migration adds — is the BEFORE INSERT
trigger that actually fills those two columns for new ``mfa.*`` rows so
the chain is verifiable end-to-end.

Design
------
* Chain is **per-tenant** (scoped by ``school_id`` — the column the app
  uses for tenant scoping; the alias ``tenant_id`` is column-mapped at
  the ORM layer). NULL ``school_id`` (platform-scoped events) forms its
  own chain via ``IS NOT DISTINCT FROM``.
* Genesis row of a chain has ``prev_hash = '0' * 64``.
* ``row_hash = sha256(prev_hash || canonical_payload)`` where the
  canonical payload is a pipe-joined string of the immutable identifying
  fields (id, action, performed_by, school_id, entity_type, entity_id,
  ip_address, user_agent, details::text, timestamp, prev_hash). We use
  ``concat_ws('|', ...)`` with ``coalesce`` defaults so NULL columns hash
  to a deterministic empty slot rather than collapsing the chain.
* We require ``pgcrypto`` for ``digest()``; ``CREATE EXTENSION IF NOT
  EXISTS`` is idempotent and safe in shared/managed Postgres.
* Non-``mfa.*`` rows are untouched (the trigger short-circuits) so the
  rest of the audit surface keeps its existing semantics.
* This trigger is BEFORE INSERT so ``NEW.prev_hash`` and ``NEW.row_hash``
  end up persisted on the same row that committed the action.

Verification (used by ``GET /api/audit/mfa-verify-chain``):
    walk rows ordered by (timestamp ASC, id ASC) per ``school_id``;
    recompute the same payload; compare to stored ``row_hash``; the chain
    is intact iff every recomputation matches and each row's ``prev_hash``
    equals the previous row's ``row_hash``.

Backfill: existing ``mfa.*`` rows that pre-date the trigger keep
``prev_hash = NULL`` / ``row_hash = NULL``. The verification endpoint
treats the first non-NULL row as the genesis of the verifiable chain
(documented in the route). We intentionally do NOT retro-hash old rows
because the goal is *forward* tamper-evidence; back-dated hashes would
be no more trustworthy than the underlying rows.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "y1z2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "x1y2z3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_logs_mfa_hash_chain_fn()
        RETURNS trigger AS $$
        DECLARE
          v_prev TEXT;
          v_payload TEXT;
          v_lock_key BIGINT;
        BEGIN
          IF NEW.action IS NULL OR NEW.action NOT LIKE 'mfa.%' THEN
            RETURN NEW;
          END IF;

          -- Per-tenant transactional advisory lock to serialise the
          -- "find latest predecessor + insert new head" critical section.
          -- Without this, two concurrent INSERTs for the same tenant can
          -- both read the same predecessor row_hash and produce a forked
          -- chain that the verifier reports as broken even though the
          -- application did nothing wrong. The lock is released
          -- automatically at COMMIT/ROLLBACK and is keyed off
          -- school_id (NULL → 0) so platform-scoped rows form their own
          -- serialised chain.
          v_lock_key := hashtextextended('mfa_audit_chain:' || coalesce(NEW.school_id, ''), 0);
          PERFORM pg_advisory_xact_lock(v_lock_key);

          -- Most recent prior hash in this tenant's chain.
          SELECT row_hash INTO v_prev
          FROM audit_logs
          WHERE action LIKE 'mfa.%'
            AND row_hash IS NOT NULL
            AND school_id IS NOT DISTINCT FROM NEW.school_id
          ORDER BY timestamp DESC, id DESC
          LIMIT 1;

          IF v_prev IS NULL THEN
            v_prev := repeat('0', 64);
          END IF;

          NEW.prev_hash := v_prev;

          v_payload := concat_ws('|',
            NEW.id,
            NEW.action,
            coalesce(NEW.performed_by, ''),
            coalesce(NEW.school_id, ''),
            coalesce(NEW.entity_type, ''),
            coalesce(NEW.entity_id, ''),
            coalesce(NEW.ip_address, ''),
            coalesce(NEW.user_agent, ''),
            coalesce(NEW.details::text, '{}'),
            coalesce(NEW.timestamp::text, ''),
            v_prev
          );

          NEW.row_hash := encode(digest(v_payload, 'sha256'), 'hex');
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS audit_logs_mfa_hash_chain_trg ON audit_logs;")
    op.execute(
        """
        CREATE TRIGGER audit_logs_mfa_hash_chain_trg
        BEFORE INSERT ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_logs_mfa_hash_chain_fn();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_mfa_hash_chain_trg ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_mfa_hash_chain_fn();")
    # pgcrypto extension intentionally NOT dropped — other tooling may rely on it.
