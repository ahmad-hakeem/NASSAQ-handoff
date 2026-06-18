"""Reconcile homework grade rows for students marked not_done

Revision ID: hw0nd1zr2gr3
Revises: z7f8g9h0i1j2
Create Date: 2026-06-18

Data-only reconcile (no schema change). Historically, marking a student
"لم يُنجز الواجب" (homework status=not_done) deleted the provisional homework
grade rows or left a stale full-marks value behind, so كشف المتابعة, the
school student_grades store, and the parent grades store still showed the
homework column at max. The session engine now treats the homework toggle as
authoritative (done -> max, not_done -> 0). This migration brings already-
persisted rows in line with that contract.

Scope: session_homework, student_grades and grades all live in the
`generic_documents` table (columns: id, collection, data JSONB) — they are NOT
real tables. For every session_homework doc with status='not_done' we zero the
matching deterministic homework grade rows
(id = 'sess:{session_id}:{student_id}:homework:sg' for student_grades and
':homework:pg' for grades), but ONLY when the row was written by the live
session pipeline (source='live_session') and currently holds a positive score.

Safety:
- Pure UPDATE — no DROP / DELETE / TRUNCATE, so no destructive-migration
  allowlist entry is required and no data is removed.
- Idempotent — after a run the affected rows hold score 0, so the
  ``score > 0`` filter excludes them on any replay (no double-application).
- Conservative — rows whose session_homework doc is missing are left
  untouched (absence is ambiguous; we only act on an explicit not_done).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "hw0nd1zr2gr3"
down_revision: Union[str, Sequence[str], None] = "z7f8g9h0i1j2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RECONCILE_SQL = """
WITH target_ids AS (
    SELECT
        'sess:' || (sh.data->>'session_id') || ':'
                || (sh.data->>'student_id') || ':homework:sg' AS gid
    FROM generic_documents sh
    WHERE sh.collection = 'session_homework'
      AND sh.data->>'status' = 'not_done'
      AND COALESCE(sh.data->>'session_id', '') <> ''
      AND COALESCE(sh.data->>'student_id', '') <> ''
    UNION
    SELECT
        'sess:' || (sh.data->>'session_id') || ':'
                || (sh.data->>'student_id') || ':homework:pg' AS gid
    FROM generic_documents sh
    WHERE sh.collection = 'session_homework'
      AND sh.data->>'status' = 'not_done'
      AND COALESCE(sh.data->>'session_id', '') <> ''
      AND COALESCE(sh.data->>'student_id', '') <> ''
)
UPDATE generic_documents g
SET data = jsonb_set(
        jsonb_set(
            jsonb_set(g.data, '{score}', '0'::jsonb, true),
            '{percentage}', '0'::jsonb, true),
        '{is_passing}', 'false'::jsonb, true)
FROM target_ids t
WHERE g.id = t.gid
  AND g.collection IN ('student_grades', 'grades')
  AND g.data->>'source' = 'live_session'
  AND (g.data->>'score') ~ '^-?[0-9]+(\\.[0-9]+)?$'
  AND (g.data->>'score')::numeric > 0
"""


def upgrade() -> None:
    op.get_bind().execute(sa.text(_RECONCILE_SQL))


def downgrade() -> None:
    # No-op: the original (incorrect) full-marks/blank values cannot be
    # reconstructed, and re-introducing them would re-create the very bug this
    # migration fixes. Intentionally left empty.
    pass
