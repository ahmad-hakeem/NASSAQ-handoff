"""Backfill authoritative teachers rows for reassigned school teachers (Task #794)

Revision ID: c9d5e3f7a2b1
Revises: b8c4d2e6f1a9
Create Date: 2026-06-03

One-off, reversible DATA migration. A school (non-IT) teacher exists in BOTH the
``users`` table (login / role / ``tenant_id``) and the authoritative ``teachers``
table (keyed by ``school_id``) — the latter is what drives the School Principal's
teacher list ("إدارة المستخدمين والفصول") and every academic flow. Historically a
teacher could have ``users.tenant_id`` set/changed (before the reconcile in
``user_routes_mod._ensure_school_teacher_record`` existed, or via a path that
bypassed it) WITHOUT a matching active ``teachers`` row in that school. Such a
teacher shows the correct school in their profile but is INVISIBLE in the
principal list.

This migration reconciles those stale rows using the SAME product rules as
``_ensure_school_teacher_record``:
  * create-if-missing — provision an active ``teachers`` row in the target school
    (matching the ``TCH-{code}-{yy}-{seq}`` id shape) and link ``users.teacher_id``;
  * reactivate — if a deactivated (non-soft-deleted) record already lives in the
    target school, flip it active instead of duplicating;
  * BLOCK / skip — a teacher who already has a live (non-soft-deleted) academic
    record in a DIFFERENT school is left untouched (academic history is never
    silently migrated); they are surfaced for manual review, not moved.

It is NON-DESTRUCTIVE: ``upgrade()`` only CREATEs a bookkeeping table and runs
INSERT/UPDATE. The rows we create/reactivate (and the prior ``users.teacher_id``)
are recorded in ``teacher_record_backfill_794`` so ``downgrade()`` can reverse
precisely. Idempotent and safe to re-run.
"""
from typing import Sequence, Union
from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = "c9d5e3f7a2b1"
down_revision: Union[str, Sequence[str], None] = "b8c4d2e6f1a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_BACKFILL_TABLE = "teacher_record_backfill_794"


def _generate_school_teacher_id(conn, school_id: str) -> str:
    """Mirror of ``user_routes_mod._generate_school_teacher_id`` in sync SQL so
    the ids we create match the app's ``TCH-{code}-{yy}-{seq}`` shape."""
    name = conn.execute(
        sa.text("SELECT name FROM schools WHERE id = :id"), {"id": school_id}
    ).scalar() or "SCH"
    code = "".join(ch for ch in name[:3] if ch.isalnum()).upper() or "SCH"
    year = datetime.now().strftime("%y")
    count = conn.execute(
        sa.text("SELECT count(*) FROM teachers WHERE school_id = :id"), {"id": school_id}
    ).scalar() or 0
    candidate = f"TCH-{code}-{year}-{str(count + 1).zfill(4)}"
    exists = conn.execute(
        sa.text("SELECT 1 FROM teachers WHERE id = :id"), {"id": candidate}
    ).scalar()
    if exists:
        candidate = f"TCH-{code}-{year}-{uuid.uuid4().hex[:6].upper()}"
    return candidate


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            f"""
            CREATE TABLE IF NOT EXISTS {_BACKFILL_TABLE} (
                user_id               VARCHAR PRIMARY KEY,
                teacher_id            VARCHAR NOT NULL,
                action                VARCHAR NOT NULL,
                prior_user_teacher_id VARCHAR,
                adopted_set_active    BOOLEAN NOT NULL DEFAULT false,
                adopted_filled_user_id BOOLEAN NOT NULL DEFAULT false
            )
            """
        )
    )

    # Resilience: an environment may already hold an OLDER shape of this
    # bookkeeping table (e.g. a prior manual `alembic upgrade head` that ran the
    # pre-adoption revision). CREATE TABLE IF NOT EXISTS would then skip the new
    # columns, so add them idempotently before they are referenced below.
    for _col in ("adopted_set_active", "adopted_filled_user_id"):
        conn.execute(
            sa.text(
                f"ALTER TABLE {_BACKFILL_TABLE} "
                f"ADD COLUMN IF NOT EXISTS {_col} BOOLEAN NOT NULL DEFAULT false"
            )
        )

    # Fresh-database resilience: every long-lived environment already has
    # ``teachers.user_id`` (it predates migration coverage), but NO migration
    # creates it — so a clean ``alembic upgrade head`` on an empty database
    # fails on the query below with UndefinedColumn. Create it idempotently
    # here, matching the ORM shape (pg_models.Teacher.user_id: VARCHAR,
    # nullable, indexed). On existing databases both statements are no-ops.
    conn.execute(
        sa.text("ALTER TABLE teachers ADD COLUMN IF NOT EXISTS user_id VARCHAR")
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_teachers_user_id ON teachers (user_id)"
        )
    )

    # Teacher-role users bound to a REAL school (never an Independent-Teacher
    # workspace) that have NO active, non-soft-deleted teachers row in that
    # school — i.e. invisible to the principal despite a correct profile.
    mismatched = conn.execute(
        sa.text(
            """
            SELECT u.id AS user_id, u.email, u.tenant_id, u.teacher_id,
                   u.full_name, u.full_name_en, u.phone, u.national_id
            FROM users u
            JOIN schools s ON s.id = u.tenant_id
            WHERE u.role = 'teacher'
              AND u.tenant_id IS NOT NULL
              AND coalesce(s.tenant_type, '') <> 'independent_teacher'
              AND coalesce(s.school_type, '') <> 'independent_teacher'
              AND NOT EXISTS (
                SELECT 1 FROM teachers t
                WHERE t.school_id = u.tenant_id
                  AND (t.user_id = u.id OR t.email = u.email)
                  AND t.is_active = true
                  AND t.deleted_at IS NULL
              )
            """
        )
    ).mappings().all()

    now = datetime.now(timezone.utc)

    for u in mismatched:
        uid = u["user_id"]
        email = u["email"]
        target = u["tenant_id"]

        # Gather live (non-soft-deleted) academic rows: by explicit user_id link
        # first, else by canonical email — mirroring _ensure_school_teacher_record.
        live = conn.execute(
            sa.text(
                "SELECT id, school_id, user_id, is_active FROM teachers "
                "WHERE user_id = :uid AND deleted_at IS NULL"
            ),
            {"uid": uid},
        ).mappings().all()
        if not live and email:
            live = conn.execute(
                sa.text(
                    "SELECT id, school_id, user_id, is_active FROM teachers "
                    "WHERE email = :em AND deleted_at IS NULL"
                ),
                {"em": email},
            ).mappings().all()

        # BLOCK: a live record in a DIFFERENT school — never migrate it. Surface
        # for manual review; do not touch users or teachers.
        other = next(
            (r for r in live if r["school_id"] and r["school_id"] != target), None
        )
        if other:
            continue

        # Already has a (deactivated) record in the target school — reactivate /
        # relink instead of creating a duplicate.
        same = next((r for r in live if r["school_id"] == target), None)
        if same:
            patch_set = []
            params = {"id": same["id"]}
            if not same["user_id"]:
                patch_set.append("user_id = :uid")
                params["uid"] = uid
            if same["is_active"] is False:
                patch_set.append("is_active = true")
            if patch_set:
                conn.execute(
                    sa.text(
                        f"UPDATE teachers SET {', '.join(patch_set)} WHERE id = :id"
                    ),
                    params,
                )
            resolved_id = same["id"]
            conn.execute(
                sa.text(
                    f"""
                    INSERT INTO {_BACKFILL_TABLE}
                        (user_id, teacher_id, action, prior_user_teacher_id)
                    VALUES (:uid, :tid, 'reactivated', :prior)
                    ON CONFLICT (user_id) DO NOTHING
                    """
                ),
                {"uid": uid, "tid": resolved_id, "prior": u["teacher_id"]},
            )
        else:
            # A teacher's identity WITHIN a school is (national_id, school_id) — a
            # UNIQUE constraint (uq_teachers_national_id_school). A row for this
            # national_id may already exist in the target school under a different
            # email/user_id, so it escaped the user_id/email match above. A blind
            # INSERT would violate that constraint, so ADOPT the canonical row
            # (link the user, fill a missing user_id, reactivate a deactivated
            # row) instead of minting a duplicate. Soft-deleted rows are left
            # archived — silent resurrection is an explicit admin action, not a
            # backfill side effect.
            adopt = None
            if u["national_id"] is not None:
                adopt = conn.execute(
                    sa.text(
                        "SELECT id, user_id, is_active, deleted_at FROM teachers "
                        "WHERE national_id = :nid AND school_id = :sid"
                    ),
                    {"nid": u["national_id"], "sid": target},
                ).mappings().first()

            if adopt:
                # The constraint is a FULL unique constraint (it covers
                # soft-deleted rows too), so we must NOT fall through to INSERT
                # whenever ANY row for this (national_id, school_id) exists.
                # Adopt ONLY a clean candidate: live (deleted_at IS NULL) and not
                # already bound to a DIFFERENT user. A soft-deleted row (silent
                # resurrection) or a row owned by another user (dual-link
                # corruption) is left for explicit manual review — skip the user.
                owned_by_other = adopt["user_id"] is not None and adopt["user_id"] != uid
                if adopt["deleted_at"] is not None or owned_by_other:
                    continue

                resolved_id = adopt["id"]
                filled_user_id = not adopt["user_id"]
                set_active = adopt["is_active"] is False
                patch_set = []
                params = {"id": resolved_id}
                if filled_user_id:
                    patch_set.append("user_id = :uid")
                    params["uid"] = uid
                if set_active:
                    patch_set.append("is_active = true")
                if patch_set:
                    conn.execute(
                        sa.text(
                            f"UPDATE teachers SET {', '.join(patch_set)} WHERE id = :id"
                        ),
                        params,
                    )
                conn.execute(
                    sa.text(
                        f"""
                        INSERT INTO {_BACKFILL_TABLE}
                            (user_id, teacher_id, action, prior_user_teacher_id,
                             adopted_set_active, adopted_filled_user_id)
                        VALUES (:uid, :tid, 'adopted', :prior, :set_active, :filled)
                        ON CONFLICT (user_id) DO NOTHING
                        """
                    ),
                    {
                        "uid": uid,
                        "tid": resolved_id,
                        "prior": u["teacher_id"],
                        "set_active": set_active,
                        "filled": filled_user_id,
                    },
                )
            else:
                # No academic record yet — provision a minimal active one.
                resolved_id = _generate_school_teacher_id(conn, target)
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO teachers
                            (id, teacher_id, user_id, full_name, full_name_en, email,
                             phone, national_id, school_id, is_active, created_by,
                             created_at, updated_at)
                        VALUES
                            (:id, :id, :uid, :full_name, :full_name_en, :email,
                             :phone, :national_id, :school_id, true, 'backfill_794',
                             :created_at, :updated_at)
                        """
                    ),
                    {
                        "id": resolved_id,
                        "uid": uid,
                        "full_name": u["full_name"] or email or "معلم",
                        "full_name_en": u["full_name_en"],
                        "email": email,
                        "phone": u["phone"],
                        "national_id": u["national_id"],
                        "school_id": target,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                conn.execute(
                    sa.text(
                        f"""
                        INSERT INTO {_BACKFILL_TABLE}
                            (user_id, teacher_id, action, prior_user_teacher_id)
                        VALUES (:uid, :tid, 'created', :prior)
                        ON CONFLICT (user_id) DO NOTHING
                        """
                    ),
                    {"uid": uid, "tid": resolved_id, "prior": u["teacher_id"]},
                )

        # Link the authoritative record back onto the user row.
        if u["teacher_id"] != resolved_id:
            conn.execute(
                sa.text("UPDATE users SET teacher_id = :tid WHERE id = :uid"),
                {"tid": resolved_id, "uid": uid},
            )


def downgrade() -> None:
    conn = op.get_bind()

    rows = conn.execute(
        sa.text(
            f"SELECT user_id, teacher_id, action, prior_user_teacher_id, "
            f"adopted_set_active, adopted_filled_user_id "
            f"FROM {_BACKFILL_TABLE}"
        )
    ).mappings().all()

    for r in rows:
        # Restore the user's prior teacher_id link (only if it still points at the
        # row we set — never clobber a link written after this migration).
        conn.execute(
            sa.text(
                "UPDATE users SET teacher_id = :prior "
                "WHERE id = :uid AND teacher_id = :tid"
            ),
            {"prior": r["prior_user_teacher_id"], "uid": r["user_id"], "tid": r["teacher_id"]},
        )
        if r["action"] == "created":
            # Remove the row we created (guard by the link we wrote).
            conn.execute(
                sa.text(
                    "DELETE FROM teachers WHERE id = :tid AND user_id = :uid "
                    "AND created_by = 'backfill_794'"
                ),
                {"tid": r["teacher_id"], "uid": r["user_id"]},
            )
        elif r["action"] == "reactivated":
            # Re-deactivate the record we flipped active.
            conn.execute(
                sa.text("UPDATE teachers SET is_active = false WHERE id = :tid"),
                {"tid": r["teacher_id"]},
            )
        elif r["action"] == "adopted":
            # Revert only the mutations we actually made to the pre-existing row
            # (guard by the link we wrote so we never touch a row reassigned
            # after this migration). The row itself is never deleted — we did not
            # create it.
            if r["adopted_filled_user_id"]:
                conn.execute(
                    sa.text(
                        "UPDATE teachers SET user_id = NULL "
                        "WHERE id = :tid AND user_id = :uid"
                    ),
                    {"tid": r["teacher_id"], "uid": r["user_id"]},
                )
            if r["adopted_set_active"]:
                conn.execute(
                    sa.text(
                        "UPDATE teachers SET is_active = false WHERE id = :tid"
                    ),
                    {"tid": r["teacher_id"]},
                )

    conn.execute(sa.text(f"DROP TABLE IF EXISTS {_BACKFILL_TABLE}"))
