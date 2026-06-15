"""materialize canonical timetable hard/soft constraints

Task #907 — The canonical system constraints (HC-01..HC-17, SC-01..SC-12)
were only ever written by the seed script, which is blocked in production and
skipped whenever the DB already has data. As a result production schools see an
empty "قيود الجدول" tab. This data migration materializes the canonical lists
directly into ``generic_documents`` so every environment (including prod) gets
exactly one canonical row per constraint code, and removes the known-corrupt
``category: "test"`` / duplicated ``HC-01`` rows that polluted the collection.

Forward-only and idempotent: it rewrites the two system collections to the
canonical set keyed by a deterministic id per code, so re-running it converges
to the same state without creating duplicates.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-06-15
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from seeds.timetable_hard_constraints import TIMETABLE_HARD_CONSTRAINTS
from seeds.timetable_soft_constraints import TIMETABLE_SOFT_CONSTRAINTS

revision: str = 'd8e9f0a1b2c3'
down_revision: Union[str, Sequence[str], None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


HARD_COLLECTION = "timetable_hard_constraints"
SOFT_COLLECTION = "timetable_soft_constraints"


def _materialize(conn, collection: str, rows: list, id_prefix: str) -> None:
    for row in rows:
        code = row["code"]
        doc = dict(row)
        # `data` JSONB stores everything except the id (gd helpers keep id out
        # of the data blob); a deterministic id keeps re-runs idempotent.
        gid = f"{id_prefix}{code}"
        conn.execute(
            sa.text(
                "INSERT INTO generic_documents (id, collection, data, created_at) "
                "VALUES (:id, :c, :data, now()) "
                "ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data"
            ),
            {"id": gid, "c": collection, "data": json.dumps(doc, ensure_ascii=False)},
        )


def upgrade() -> None:
    conn = op.get_bind()
    # Remove every existing row in both collections (corrupt `category:"test"`
    # entries, duplicated HC-01 reference rows, and any stale partial-seed
    # rows). The canonical set is re-inserted immediately below, so the end
    # state is deterministic. These collections hold reference data only — no
    # school/user data — so the DELETE is safe and acknowledged in the
    # destructive-migration guard allowlist.
    conn.execute(
        sa.text("DELETE FROM generic_documents WHERE collection IN (:h, :s)"),
        {"h": HARD_COLLECTION, "s": SOFT_COLLECTION},
    )
    _materialize(conn, HARD_COLLECTION, TIMETABLE_HARD_CONSTRAINTS, "sys-hc-")
    _materialize(conn, SOFT_COLLECTION, TIMETABLE_SOFT_CONSTRAINTS, "sys-sc-")


def downgrade() -> None:
    # The canonical system constraints are reference data, not user data. A
    # downgrade simply removes the materialized rows; it intentionally does
    # not restore the previously-corrupt rows.
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM generic_documents WHERE collection IN (:h, :s)"),
        {"h": HARD_COLLECTION, "s": SOFT_COLLECTION},
    )
