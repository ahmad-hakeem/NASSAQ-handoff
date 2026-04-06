"""cleanup redundant schema fields

Revision ID: d1e2f3a4b5c6
Revises: c8d9e0f1a2b3
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa

revision = "d1e2f3a4b5c6"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
        ),
        {"t": table, "c": column}
    )
    return result.scalar() is not None


def upgrade():
    conn = op.get_bind()

    if _column_exists(conn, "schools", "current_student_count"):
        op.execute(
            sa.text(
                'UPDATE "schools" SET "current_students" = COALESCE("current_student_count", "current_students") '
                'WHERE "current_student_count" IS NOT NULL AND "current_student_count" > "current_students"'
            )
        )
        op.drop_column("schools", "current_student_count")

    if _column_exists(conn, "schools", "current_teacher_count"):
        op.execute(
            sa.text(
                'UPDATE "schools" SET "current_teachers" = COALESCE("current_teacher_count", "current_teachers") '
                'WHERE "current_teacher_count" IS NOT NULL AND "current_teacher_count" > "current_teachers"'
            )
        )
        op.drop_column("schools", "current_teacher_count")

    if _column_exists(conn, "classes", "current_count"):
        op.execute(
            sa.text(
                'UPDATE "classes" SET "current_students" = COALESCE("current_count", "current_students") '
                'WHERE "current_count" IS NOT NULL AND "current_count" > "current_students"'
            )
        )
        op.drop_column("classes", "current_count")

    if _column_exists(conn, "subjects", "tenant_id"):
        op.execute(
            sa.text(
                'UPDATE "subjects" SET "school_id" = COALESCE("school_id", "tenant_id") '
                'WHERE "school_id" IS NULL AND "tenant_id" IS NOT NULL'
            )
        )
        op.drop_column("subjects", "tenant_id")

    if _column_exists(conn, "audit_logs", "tenant_id"):
        op.execute(
            sa.text(
                'UPDATE "audit_logs" SET "school_id" = "tenant_id" '
                'FROM "schools" WHERE "audit_logs"."school_id" IS NULL '
                'AND "audit_logs"."tenant_id" IS NOT NULL '
                'AND "schools"."id" = "audit_logs"."tenant_id"'
            )
        )
        op.drop_column("audit_logs", "tenant_id")


def downgrade():
    conn = op.get_bind()

    if not _column_exists(conn, "audit_logs", "tenant_id"):
        op.add_column("audit_logs", sa.Column("tenant_id", sa.String(), nullable=True))
        op.execute(sa.text('UPDATE "audit_logs" SET "tenant_id" = "school_id"'))

    if not _column_exists(conn, "subjects", "tenant_id"):
        op.add_column("subjects", sa.Column("tenant_id", sa.String(), nullable=True))
        op.execute(sa.text('UPDATE "subjects" SET "tenant_id" = "school_id"'))

    if not _column_exists(conn, "classes", "current_count"):
        op.add_column("classes", sa.Column("current_count", sa.Integer(), nullable=True, server_default="0"))
        op.execute(sa.text('UPDATE "classes" SET "current_count" = "current_students"'))

    if not _column_exists(conn, "schools", "current_teacher_count"):
        op.add_column("schools", sa.Column("current_teacher_count", sa.Integer(), nullable=True, server_default="0"))
        op.execute(sa.text('UPDATE "schools" SET "current_teacher_count" = "current_teachers"'))

    if not _column_exists(conn, "schools", "current_student_count"):
        op.add_column("schools", sa.Column("current_student_count", sa.Integer(), nullable=True, server_default="0"))
        op.execute(sa.text('UPDATE "schools" SET "current_student_count" = "current_students"'))
