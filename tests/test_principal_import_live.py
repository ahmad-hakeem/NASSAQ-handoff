"""Live development-DB regression for the legacy principal student import.

This file intentionally lives outside ``backend/tests``.  It does not use the
backend test conftest, does not create an ASGI client, and never commits.  The
test is opt-in because it writes temporary rows to the configured development
database before rolling its outer transaction back:

    RUN_PRINCIPAL_IMPORT_LIVE=1 \
    PRINCIPAL_IMPORT_DATABASE=development \
    pytest -q tests/test_principal_import_live.py

The explicit database-purpose gate is a safety measure.  Do not remove it or
run this test against a production ``DATABASE_URL``.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool


if os.environ.get("RUN_PRINCIPAL_IMPORT_LIVE") != "1":
    pytest.skip(
        "opt-in live development DB regression "
        "(set RUN_PRINCIPAL_IMPORT_LIVE=1)",
        allow_module_level=True,
    )
if os.environ.get("PRINCIPAL_IMPORT_DATABASE") != "development":
    pytest.skip(
        "refusing to run unless PRINCIPAL_IMPORT_DATABASE=development",
        allow_module_level=True,
    )


# Backend modules are not installed as a package in the workspace.  Importing
# the database layer is side-effect free; this test creates its own engine and
# session below rather than borrowing backend/tests/conftest's fixture.
_BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
os.environ.setdefault("TESTING", "1")

from engines.sql_utils import (  # noqa: E402
    gd_count,
    gd_find,
    gd_find_one,
    gd_insert,
)
from src.core.database.db import _get_async_url  # noqa: E402
from src.core.database.repository import Repos  # noqa: E402
from src.modules.bulk_import.controllers.bulk_import_export_routes import (  # noqa: E402
    _import_students,
)


pytestmark = pytest.mark.asyncio

_GRADE_1 = "الصف الأول الابتدائي"
_GRADE_2 = "الصف الثاني الابتدائي"
_GRADE_3 = "الصف الثالث الابتدائي"
_GRADE_4 = "الصف الرابع الابتدائي"
_GRADE_5 = "الصف الخامس الابتدائي"


def _id() -> str:
    return str(uuid.uuid4())


def _national_id(seed: int) -> str:
    return f"910000{seed:04d}"


def _school_doc(school_id: str, principal_id: str) -> dict:
    return {
        "id": school_id,
        "name": f"Live import regression {school_id[:8]}",
        "code": f"LIR-{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "tenant_type": "development",
        "principal_id": principal_id,
        "current_students": 0,
        "current_teachers": 0,
    }


def _user_doc(
    user_id: str,
    school_id: str | None,
    *,
    role: str,
    email: str,
    full_name: str,
) -> dict:
    return {
        "id": user_id,
        "email": email,
        "full_name": full_name,
        "password_hash": "live-regression-not-used",
        "role": role,
        "tenant_id": school_id,
        "is_active": True,
        "must_change_password": False,
    }


def _grade_doc(school_id: str, grade_id: str, label: str, number: int) -> dict:
    return {
        "id": grade_id,
        "school_id": school_id,
        "name": label,
        "name_ar": label,
        "name_en": f"Grade {number}",
        "code": f"live-g{number}",
        "stage": "primary",
        "order": number,
        "is_active": True,
    }


def _class_doc(
    school_id: str,
    class_id: str,
    grade_id: str,
    grade: str,
    section: str,
    *,
    capacity: int = 30,
) -> dict:
    return {
        "id": class_id,
        "school_id": school_id,
        "name": f"{grade} - {section}",
        "grade_id": grade_id,
        "grade_level": grade,
        "section": section,
        "capacity": capacity,
        "current_students": 0,
        "is_active": True,
    }


def _import_row(
    first_name: str,
    last_name: str,
    national_id: str,
    grade: str,
    section: str,
    parent_name: str,
    parent_phone: str,
    parent_email: str | None,
) -> dict:
    return {
        "الاسم الأول (مطلوب)": first_name,
        "اسم الأب": "",
        "اسم العائلة (مطلوب)": last_name,
        "رقم الهوية (مطلوب)": national_id,
        "تاريخ الميلاد (YYYY-MM-DD)": "2016-01-15",
        "الجنس (ذكر/أنثى)": "ذكر",
        "الصف": grade,
        "الفصل": section,
        "البريد الإلكتروني": None,
        "رقم الجوال": None,
        "اسم ولي الأمر": parent_name,
        "جوال ولي الأمر (مطلوب)": parent_phone,
        "بريد ولي الأمر": parent_email,
    }


async def _snapshot(session: AsyncSession, school_id: str) -> dict:
    """Return only tenant-scoped counts used by idempotency assertions."""
    return {
        "students": await gd_count(session, "students", {"school_id": school_id}),
        "parents": await gd_count(session, "parents", {"school_id": school_id}),
        "classes": await gd_count(session, "classes", {"school_id": school_id}),
        "batches": await gd_count(
            session, "bulk_import_batches", {"school_id": school_id}
        ),
        "links": await gd_count(
            session, "guardian_links", {"tenant_id": school_id}
        ),
    }


async def _assert_transaction_cleanup(engine, school_ids: list[str]) -> None:
    """Verify the rollback removed every temporary tenant row."""
    async with engine.connect() as connection:
        async with AsyncSession(
            bind=connection, expire_on_commit=False
        ) as verification_session:
            for school_id in school_ids:
                assert await gd_count(
                    verification_session, "schools", {"id": school_id}
                ) == 0
                assert await gd_count(
                    verification_session, "users", {"tenant_id": school_id}
                ) == 0
                assert await gd_count(
                    verification_session, "students", {"school_id": school_id}
                ) == 0
                assert await gd_count(
                    verification_session, "parents", {"school_id": school_id}
                ) == 0
                assert await gd_count(
                    verification_session, "classes", {"school_id": school_id}
                ) == 0
                assert await gd_count(
                    verification_session, "grade_levels", {"school_id": school_id}
                ) == 0
                assert await gd_count(
                    verification_session, "academic_years", {"school_id": school_id}
                ) == 0
                assert await gd_count(
                    verification_session,
                    "guardian_links",
                    {"tenant_id": school_id},
                ) == 0
                assert await gd_count(
                    verification_session,
                    "bulk_import_batches",
                    {"school_id": school_id},
                ) == 0


async def test_legacy_principal_import_live_development_regression():
    """Exercise tenant, grade/section, guardian, retry, and capacity paths."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    # AcademicYear is school-scoped; only AcademicTerm has an explicit
    # academic_year_id association.  Current students/classes use their own
    # grade/class fields and have no academic_year_id column, so this fixture
    # records the real schema relationship without inventing one on students.
    engine = create_async_engine(_get_async_url(), poolclass=NullPool)
    school_id = _id()
    other_school_id = _id()
    principal_id = _id()
    existing_parent_user_id = _id()
    existing_parent_id = _id()
    conflict_user_id = _id()
    other_parent_user_id = _id()
    other_parent_id = _id()
    other_student_id = _id()
    other_class_id = _id()
    conflict_class_id = _id()
    academic_year_id = _id()
    grade_ids = {grade: _id() for grade in (_GRADE_1, _GRADE_2, _GRADE_3, _GRADE_4, _GRADE_5)}
    class_ids = {
        "grade_1_a": _id(),
        "grade_2_a": _id(),
    }

    primary_nids = [_national_id(n) for n in range(1, 5)]
    other_nid = _national_id(100)
    conflict_nid = _national_id(200)
    existing_parent_phone = "0509000001"
    existing_parent_email = f"live-existing-parent-{school_id[:8]}@example.test"
    other_parent_phone = "0509000002"
    other_parent_email = f"live-cross-tenant-parent-{other_school_id[:8]}@example.test"
    conflict_email = f"live-conflicting-account-{school_id[:8]}@example.test"

    connection = await engine.connect()
    outer_transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)
    db = Repos(session)

    try:
        await gd_insert(
            session,
            "schools",
            _school_doc(school_id, principal_id),
        )
        await gd_insert(
            session,
            "users",
            _user_doc(
                principal_id,
                school_id,
                role="school_principal",
                email=f"live-principal-{school_id[:8]}@example.test",
                full_name="Live Regression Principal",
            ),
        )
        await gd_insert(
            session,
            "academic_years",
            {
                "id": academic_year_id,
                "school_id": school_id,
                "name": "2026-2027",
                "name_en": "2026-2027",
                "is_current": True,
                "status": "active",
            },
        )
        for number, grade in enumerate(
            (_GRADE_1, _GRADE_2, _GRADE_3, _GRADE_4, _GRADE_5),
            start=1,
        ):
            await gd_insert(
                session,
                "grade_levels",
                _grade_doc(school_id, grade_ids[grade], grade, number),
            )
        await gd_insert(
            session,
            "classes",
            _class_doc(
                school_id,
                class_ids["grade_1_a"],
                grade_ids[_GRADE_1],
                _GRADE_1,
                "أ",
                capacity=4,
            ),
        )
        await gd_insert(
            session,
            "classes",
            _class_doc(
                school_id,
                class_ids["grade_2_a"],
                grade_ids[_GRADE_2],
                _GRADE_2,
                "أ",
                capacity=2,
            ),
        )

        # One existing per-school parent is reused, while the import creates
        # the remaining parent accounts.  No password or token is printed.
        await gd_insert(
            session,
            "users",
            _user_doc(
                existing_parent_user_id,
                school_id,
                role="parent",
                email=existing_parent_email,
                full_name="Existing Parent",
            ),
        )
        await gd_insert(
            session,
            "parents",
            {
                "id": existing_parent_id,
                "user_id": existing_parent_user_id,
                "full_name": "Existing Parent",
                "email": existing_parent_email,
                "phone": existing_parent_phone,
                "student_ids": [],
                "school_id": school_id,
                "is_active": True,
            },
        )

        # A same-named class, student, and parent in another tenant exercise
        # the tenant predicates.  The global parent user may be reused by the
        # new school's per-school parent row, but the parent row itself must
        # never be cross-tenant reused.
        await gd_insert(
            session,
            "schools",
            _school_doc(other_school_id, _id()),
        )
        await gd_insert(
            session,
            "users",
            _user_doc(
                other_parent_user_id,
                other_school_id,
                role="parent",
                email=other_parent_email,
                full_name="Other Tenant Parent",
            ),
        )
        await gd_insert(
            session,
            "parents",
            {
                "id": other_parent_id,
                "user_id": other_parent_user_id,
                "full_name": "Other Tenant Parent",
                "email": other_parent_email,
                "phone": other_parent_phone,
                "student_ids": [other_student_id],
                "school_id": other_school_id,
                "is_active": True,
            },
        )
        await gd_insert(
            session,
            "classes",
            _class_doc(
                other_school_id,
                other_class_id,
                _id(),
                _GRADE_4,
                "أ",
                capacity=2,
            ),
        )
        await gd_insert(
            session,
            "students",
            {
                "id": other_student_id,
                "school_id": other_school_id,
                "full_name": "Other Tenant Student",
                "national_id": other_nid,
                "grade": _GRADE_4,
                "class_id": other_class_id,
                "parent_id": other_parent_id,
                "parent_name": "Other Tenant Parent",
                "parent_phone": other_parent_phone,
                "parent_email": other_parent_email,
                "is_active": True,
            },
        )

        # This is a non-parent account.  A guardian email collision must not
        # result in a student being persisted or consuming class capacity.
        await gd_insert(
            session,
            "users",
            _user_doc(
                conflict_user_id,
                school_id,
                role="teacher",
                email=conflict_email,
                full_name="Conflicting Non-Parent Account",
            ),
        )
        await gd_insert(
            session,
            "classes",
            _class_doc(
                school_id,
                conflict_class_id,
                grade_ids[_GRADE_5],
                _GRADE_5,
                "ج",
                capacity=2,
            ),
        )

        first_import = pd.DataFrame(
            [
                _import_row(
                    "أحمد",
                    "السعيد",
                    primary_nids[0],
                    _GRADE_1,
                    "أ",
                    "Existing Parent",
                    existing_parent_phone,
                    existing_parent_email,
                ),
                _import_row(
                    "سارة",
                    "العتيبي",
                    primary_nids[1],
                    _GRADE_2,
                    "أ",
                    "New Parent One",
                    "0509000003",
                    f"live-new-parent-one-{school_id[:8]}@example.test",
                ),
                _import_row(
                    "نورة",
                    "المالكي",
                    primary_nids[2],
                    _GRADE_1,
                    "أ",
                    "Existing Parent",
                    existing_parent_phone,
                    existing_parent_email,
                ),
                _import_row(
                    "خالد",
                    "الغامدي",
                    primary_nids[3],
                    _GRADE_3,
                    "ب",
                    "New Parent Two",
                    "0509000004",
                    f"live-new-parent-two-{school_id[:8]}@example.test",
                ),
            ]
        )
        first_errors: list[dict] = []
        first_warnings: list[dict] = []
        first_result = await _import_students(
            db,
            first_import,
            school_id,
            {
                "id": principal_id,
                "full_name": "Live Regression Principal",
                "role": "school_principal",
                "tenant_id": school_id,
            },
            first_errors,
            first_warnings,
            filename="live-principal-import.xlsx",
        )
        await session.flush()

        assert first_result["imported"] == 4, (first_result, first_errors)
        assert not first_errors
        assert first_result["created_class_ids"], first_result
        assert await gd_count(
            session, "students", {"school_id": school_id}
        ) == 4
        assert await gd_count(
            session, "parents", {"school_id": school_id}
        ) == 3
        assert await gd_count(
            session, "guardian_links", {"tenant_id": school_id}
        ) == 4

        imported_students = await gd_find(
            session,
            "students",
            {"school_id": school_id},
            limit=20,
        )
        students_by_nid = {row["national_id"]: row for row in imported_students}
        classes = await gd_find(
            session, "classes", {"school_id": school_id}, limit=20
        )
        classes_by_id = {row["id"]: row for row in classes}
        parents = await gd_find(
            session, "parents", {"school_id": school_id}, limit=20
        )
        parents_by_id = {row["id"]: row for row in parents}

        # Existing grade-1/A and grade-2/A classes share a section label but
        # must remain distinct.  Grade-3/B is auto-provisioned because it was
        # intentionally absent before the import.
        grade_1_students = [
            students_by_nid[primary_nids[0]],
            students_by_nid[primary_nids[2]],
        ]
        grade_2_student = students_by_nid[primary_nids[1]]
        grade_3_student = students_by_nid[primary_nids[3]]
        assert {
            classes_by_id[row["class_id"]]["grade_level"]
            for row in grade_1_students
        } == {_GRADE_1}
        assert classes_by_id[grade_2_student["class_id"]]["grade_level"] == _GRADE_2
        assert classes_by_id[grade_3_student["class_id"]]["grade_level"] == _GRADE_3
        assert classes_by_id[grade_3_student["class_id"]]["section"] == "ب"
        assert grade_1_students[0]["class_id"] == grade_1_students[1]["class_id"]
        assert grade_1_students[0]["class_id"] != grade_2_student["class_id"]
        assert grade_3_student["class_id"] in first_result["created_class_ids"]

        # Parent and guardian_links are both relationship stores.  Each
        # imported student must point at the per-school parent row, and each
        # row must contain exactly one canonical active link.
        for student in imported_students:
            parent = parents_by_id[student["parent_id"]]
            assert parent["school_id"] == school_id
            assert student["id"] in (parent.get("student_ids") or [])
            links = await gd_find(
                session,
                "guardian_links",
                {
                    "tenant_id": school_id,
                    "student_id": student["id"],
                    "is_active": True,
                },
                limit=10,
            )
            assert len(links) == 1
            assert links[0]["parent_id"] == parent["id"]
            assert links[0]["tenant_id"] == school_id

        # The helper reconciles counters from live relationships, not from
        # stale stored values.
        class_rows_by_key = {
            (row["grade_level"], row["section"]): row for row in classes
        }
        assert class_rows_by_key[(_GRADE_1, "أ")]["current_students"] == 2
        assert class_rows_by_key[(_GRADE_2, "أ")]["current_students"] == 1
        assert class_rows_by_key[(_GRADE_3, "ب")]["current_students"] == 1
        school_row = await gd_find_one(
            session, "schools", {"id": school_id}
        )
        assert school_row["current_students"] == 4

        # Repeating the exact import is an idempotent update: it may record a
        # second audit batch, but it must not create any second student,
        # class, parent, or guardian link.
        before_retry = await _snapshot(session, school_id)
        retry_errors: list[dict] = []
        retry_warnings: list[dict] = []
        retry_result = await _import_students(
            db,
            first_import,
            school_id,
            {"id": principal_id, "full_name": "Live Regression Principal"},
            retry_errors,
            retry_warnings,
            filename="live-principal-import-retry.xlsx",
        )
        await session.flush()
        after_retry = await _snapshot(session, school_id)
        assert retry_result["imported"] == 4, retry_result
        assert retry_result["updated"] == 4, retry_result
        assert retry_result["created"] == 0, retry_result
        assert retry_result["failed"] == 0, retry_result
        assert not retry_errors
        for key in ("students", "parents", "classes", "links"):
            assert after_retry[key] == before_retry[key]
        assert after_retry["batches"] == before_retry["batches"] + 1

        # Invalid rows are reported without creating any student or class.
        invalid_nid = _national_id(300)
        invalid_import = pd.DataFrame(
            [
                _import_row(
                    "",
                    "MissingFirstName",
                    invalid_nid,
                    _GRADE_1,
                    "أ",
                    "Invalid Parent",
                    "0509000005",
                    None,
                ),
                _import_row(
                    "Invalid",
                    "BadIdentity",
                    "1234",
                    _GRADE_2,
                    "أ",
                    "Invalid Parent",
                    "123",
                    None,
                ),
            ]
        )
        invalid_before = await _snapshot(session, school_id)
        invalid_errors: list[dict] = []
        invalid_result = await _import_students(
            db,
            invalid_import,
            school_id,
            {"id": principal_id, "full_name": "Live Regression Principal"},
            invalid_errors,
            [],
            filename="live-principal-invalid.xlsx",
        )
        await session.flush()
        assert invalid_result["imported"] == 0
        assert invalid_result["failed"] == 2
        assert len(invalid_errors) >= 3
        assert await _snapshot(session, school_id) == invalid_before
        assert await gd_count(
            session, "students", {"national_id": invalid_nid}
        ) == 0

        # A same-identity student/class/parent in another tenant must not
        # block or mutate this tenant's import.
        cross_tenant_import = pd.DataFrame(
            [
                _import_row(
                    "Cross",
                    "Tenant",
                    other_nid,
                    _GRADE_4,
                    "أ",
                    "Other Tenant Parent",
                    other_parent_phone,
                    other_parent_email,
                )
            ]
        )
        other_before = {
            "students": await gd_count(
                session, "students", {"school_id": other_school_id}
            ),
            "parents": await gd_count(
                session, "parents", {"school_id": other_school_id}
            ),
            "classes": await gd_count(
                session, "classes", {"school_id": other_school_id}
            ),
        }
        cross_errors: list[dict] = []
        cross_result = await _import_students(
            db,
            cross_tenant_import,
            school_id,
            {"id": principal_id, "full_name": "Live Regression Principal"},
            cross_errors,
            [],
            filename="live-principal-cross-tenant.xlsx",
        )
        await session.flush()
        assert cross_result["imported"] == 1, (cross_result, cross_errors)
        cross_student = await gd_find_one(
            session,
            "students",
            {"school_id": school_id, "national_id": other_nid},
        )
        assert cross_student is not None
        cross_class = await gd_find_one(
            session, "classes", {"id": cross_student["class_id"]}
        )
        assert cross_class["school_id"] == school_id
        assert cross_class["grade_level"] == _GRADE_4
        assert cross_class["section"] == "أ"
        cross_parent = await gd_find_one(
            session, "parents", {"id": cross_student["parent_id"]}
        )
        assert cross_parent["school_id"] == school_id
        assert cross_parent["id"] != other_parent_id
        assert {
            "students": await gd_count(
                session, "students", {"school_id": other_school_id}
            ),
            "parents": await gd_count(
                session, "parents", {"school_id": other_school_id}
            ),
            "classes": await gd_count(
                session, "classes", {"school_id": other_school_id}
            ),
        } == other_before

        # A parent-email conflict with an existing non-parent account is a
        # row-level failure.  The row must roll back its guardian writes and
        # must not consume the target class's capacity.
        conflict_import = pd.DataFrame(
            [
                _import_row(
                    "Conflict",
                    "Guardian",
                    conflict_nid,
                    _GRADE_5,
                    "ج",
                    "Conflicting Guardian",
                    "0509000006",
                    conflict_email,
                )
            ]
        )
        conflict_errors: list[dict] = []
        conflict_result = await _import_students(
            db,
            conflict_import,
            school_id,
            {"id": principal_id, "full_name": "Live Regression Principal"},
            conflict_errors,
            [],
            filename="live-principal-parent-conflict.xlsx",
        )
        await session.flush()
        assert conflict_result["imported"] == 0, (
            conflict_result,
            conflict_errors,
        )
        assert conflict_result["failed"] >= 1
        assert conflict_errors
        assert await gd_count(
            session,
            "students",
            {"school_id": school_id, "national_id": conflict_nid},
        ) == 0
        assert await gd_count(
            session,
            "parents",
            {"school_id": school_id, "email": conflict_email},
        ) == 0
        conflict_class = await gd_find_one(
            session, "classes", {"id": conflict_class_id}
        )
        assert conflict_class["current_students"] == 0

        # Keep the academic-year shape check tied to the actual ORM schema:
        # AcademicTerm has academic_year_id; Class and Student do not.
        from pg_models import AcademicTerm, Class, Student

        assert hasattr(AcademicTerm, "academic_year_id")
        assert not hasattr(Class, "academic_year_id")
        assert not hasattr(Student, "academic_year_id")
        assert datetime.now(timezone.utc).tzinfo is not None
    finally:
        # This is deliberately the only transaction lifecycle in the test:
        # no route/helper call is allowed to commit development fixture rows.
        try:
            await session.rollback()
        finally:
            if outer_transaction.is_active:
                await outer_transaction.rollback()
            await session.close()
            await connection.close()
            try:
                await _assert_transaction_cleanup(
                    engine, [school_id, other_school_id]
                )
            finally:
                await engine.dispose()


@pytest.mark.parametrize("student_count", [31, 50, 100, 300])
async def test_legacy_principal_import_single_class_open_ended(student_count: int):
    """Every requested row stays in one class, including batches over 30.

    This route-level regression deliberately seeds a class whose legacy
    capacity is one.  It proves that import assignment, parent links, live
    counters, and exact-number re-imports remain correct at the requested
    31/50/100/300-row thresholds.
    """
    engine = create_async_engine(_get_async_url(), poolclass=NullPool)
    school_id = _id()
    principal_id = _id()
    grade_id = _id()
    class_id = _id()
    academic_year_id = _id()
    nids = [_national_id(1000 + index) for index in range(student_count)]
    rows = pd.DataFrame(
        [
            _import_row(
                f"Batch{index}",
                "Student",
                nids[index],
                _GRADE_1,
                "أ",
                f"Batch Parent {index}",
                f"050{student_count:02d}{index:05d}",
                f"live-batch-{student_count}-{index}@example.test",
            )
            for index in range(student_count)
        ]
    )

    connection = await engine.connect()
    outer_transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)
    db = Repos(session)

    try:
        await gd_insert(session, "schools", _school_doc(school_id, principal_id))
        await gd_insert(
            session,
            "users",
            _user_doc(
                principal_id,
                school_id,
                role="school_principal",
                email=f"live-batch-principal-{school_id[:8]}@example.test",
                full_name="Live Batch Principal",
            ),
        )
        await gd_insert(
            session,
            "academic_years",
            {
                "id": academic_year_id,
                "school_id": school_id,
                "name": "2026-2027",
                "name_en": "2026-2027",
                "is_current": True,
                "status": "active",
            },
        )
        await gd_insert(
            session,
            "grade_levels",
            _grade_doc(school_id, grade_id, _GRADE_1, 1),
        )
        await gd_insert(
            session,
            "classes",
            _class_doc(
                school_id,
                class_id,
                grade_id,
                _GRADE_1,
                "أ",
                capacity=1,
            ),
        )

        errors: list[dict] = []
        result = await _import_students(
            db,
            rows,
            school_id,
            {
                "id": principal_id,
                "full_name": "Live Batch Principal",
                "role": "school_principal",
                "tenant_id": school_id,
            },
            errors,
            [],
            filename=f"live-principal-{student_count}.xlsx",
        )
        await session.flush()

        assert result["imported"] == student_count, (result, errors)
        assert result["failed"] == 0, (result, errors)
        assert result["assigned"] == student_count, result
        assert not errors

        imported_students = await gd_find(
            session,
            "students",
            {"school_id": school_id},
            limit=student_count + 5,
        )
        assert len(imported_students) == student_count
        assert {student["class_id"] for student in imported_students} == {class_id}
        assert await gd_count(
            session, "parents", {"school_id": school_id}
        ) == student_count
        assert await gd_count(
            session, "guardian_links", {"tenant_id": school_id}
        ) == student_count

        class_row = await gd_find_one(session, "classes", {"id": class_id})
        school_row = await gd_find_one(session, "schools", {"id": school_id})
        assert class_row["current_students"] == student_count
        assert school_row["current_students"] == student_count

        before_retry = await _snapshot(session, school_id)
        retry_errors: list[dict] = []
        retry_result = await _import_students(
            db,
            rows,
            school_id,
            {"id": principal_id, "full_name": "Live Batch Principal"},
            retry_errors,
            [],
            filename=f"live-principal-{student_count}-retry.xlsx",
        )
        await session.flush()
        after_retry = await _snapshot(session, school_id)

        assert retry_result["imported"] == student_count, retry_result
        assert retry_result["updated"] == student_count, retry_result
        assert retry_result["created"] == 0, retry_result
        assert retry_result["failed"] == 0, retry_result
        assert not retry_errors
        for key in ("students", "parents", "classes", "links"):
            assert after_retry[key] == before_retry[key]
        assert after_retry["batches"] == before_retry["batches"] + 1
    finally:
        try:
            await session.rollback()
        finally:
            if outer_transaction.is_active:
                await outer_transaction.rollback()
            await session.close()
            await connection.close()
            try:
                await _assert_transaction_cleanup(engine, [school_id])
            finally:
                await engine.dispose()