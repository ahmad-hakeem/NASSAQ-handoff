"""add indexes and unique constraints

Revision ID: b7e52689a1ad
Revises: b9e08d69a15a
Create Date: 2026-04-05
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b7e52689a1ad'
down_revision: Union[str, Sequence[str], None] = 'b9e08d69a15a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize_empty_to_null(connection):
    connection.execute(sa.text(
        "UPDATE students SET student_number = NULL WHERE student_number = ''"
    ))
    connection.execute(sa.text(
        "UPDATE students SET national_id = NULL WHERE national_id = ''"
    ))
    connection.execute(sa.text(
        "UPDATE teachers SET national_id = NULL WHERE national_id = ''"
    ))


def _dedupe_students_student_number(connection):
    rows = connection.execute(sa.text(
        "SELECT school_id, student_number, array_agg(id ORDER BY created_at DESC) AS ids "
        "FROM students "
        "WHERE student_number IS NOT NULL "
        "GROUP BY school_id, student_number "
        "HAVING count(*) > 1"
    )).fetchall()
    for row in rows:
        ids_to_fix = list(row[2])[1:]
        for sid in ids_to_fix:
            suffix = uuid.uuid4().hex[:8]
            connection.execute(sa.text(
                "UPDATE students SET student_number = :new_num WHERE id = :sid"
            ), {"new_num": f"{row[1]}_dup_{suffix}", "sid": sid})


def _dedupe_students_national_id(connection):
    rows = connection.execute(sa.text(
        "SELECT school_id, national_id, array_agg(id ORDER BY created_at DESC) AS ids "
        "FROM students "
        "WHERE national_id IS NOT NULL "
        "GROUP BY school_id, national_id "
        "HAVING count(*) > 1"
    )).fetchall()
    for row in rows:
        ids_to_fix = list(row[2])[1:]
        for sid in ids_to_fix:
            suffix = uuid.uuid4().hex[:8]
            connection.execute(sa.text(
                "UPDATE students SET national_id = :new_nid WHERE id = :sid"
            ), {"new_nid": f"{row[1]}_dup_{suffix}", "sid": sid})


def _dedupe_teachers_national_id(connection):
    rows = connection.execute(sa.text(
        "SELECT school_id, national_id, array_agg(id ORDER BY created_at DESC) AS ids "
        "FROM teachers "
        "WHERE national_id IS NOT NULL "
        "GROUP BY school_id, national_id "
        "HAVING count(*) > 1"
    )).fetchall()
    for row in rows:
        ids_to_fix = list(row[2])[1:]
        for sid in ids_to_fix:
            suffix = uuid.uuid4().hex[:8]
            connection.execute(sa.text(
                "UPDATE teachers SET national_id = :new_nid WHERE id = :sid"
            ), {"new_nid": f"{row[1]}_dup_{suffix}", "sid": sid})


def _fix_subjects_nulls(connection):
    connection.execute(sa.text(
        "UPDATE subjects SET name = COALESCE(name_ar, name_en, 'Unnamed') WHERE name IS NULL"
    ))
    connection.execute(sa.text(
        "DELETE FROM subjects WHERE school_id IS NULL"
    ))


def upgrade() -> None:
    conn = op.get_bind()

    _normalize_empty_to_null(conn)

    op.create_index('ix_users_phone', 'users', ['phone'], unique=False)
    op.create_index('ix_users_national_id', 'users', ['national_id'], unique=False)

    op.create_index('ix_teachers_national_id', 'teachers', ['national_id'], unique=False)

    op.create_index('ix_students_national_id', 'students', ['national_id'], unique=False)
    op.create_index('ix_students_parent_id', 'students', ['parent_id'], unique=False)

    op.create_index('ix_schedule_sessions_schedule_id', 'schedule_sessions', ['schedule_id'], unique=False)

    op.create_index('ix_attendance_session_id', 'attendance', ['session_id'], unique=False)

    op.create_index('ix_audit_logs_target_id', 'audit_logs', ['target_id'], unique=False)

    _dedupe_students_student_number(conn)
    _dedupe_students_national_id(conn)
    _dedupe_teachers_national_id(conn)

    op.create_unique_constraint('uq_students_number_school', 'students', ['student_number', 'school_id'])
    op.create_unique_constraint('uq_students_national_id_school', 'students', ['national_id', 'school_id'])
    op.create_unique_constraint('uq_teachers_national_id_school', 'teachers', ['national_id', 'school_id'])

    _fix_subjects_nulls(conn)
    op.alter_column('subjects', 'name', existing_type=sa.String(), nullable=False)
    op.alter_column('subjects', 'school_id', existing_type=sa.String(), nullable=False)


def downgrade() -> None:
    op.alter_column('subjects', 'school_id', existing_type=sa.String(), nullable=True)
    op.alter_column('subjects', 'name', existing_type=sa.String(), nullable=True)

    op.drop_constraint('uq_teachers_national_id_school', 'teachers', type_='unique')
    op.drop_constraint('uq_students_national_id_school', 'students', type_='unique')
    op.drop_constraint('uq_students_number_school', 'students', type_='unique')

    op.drop_index('ix_audit_logs_target_id', table_name='audit_logs')
    op.drop_index('ix_attendance_session_id', table_name='attendance')
    op.drop_index('ix_schedule_sessions_schedule_id', table_name='schedule_sessions')
    op.drop_index('ix_students_parent_id', table_name='students')
    op.drop_index('ix_students_national_id', table_name='students')
    op.drop_index('ix_teachers_national_id', table_name='teachers')
    op.drop_index('ix_users_national_id', table_name='users')
    op.drop_index('ix_users_phone', table_name='users')
