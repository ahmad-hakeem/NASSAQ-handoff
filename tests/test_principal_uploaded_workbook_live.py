"""Live development-DB regression for the supplied principal workbook.

The workbook is deliberately read from the repository by default so the
regression uses the exact uploaded artifact.  A different copy may be used
only by explicitly setting ``PRINCIPAL_IMPORT_WORKBOOK``:

    RUN_PRINCIPAL_IMPORT_LIVE=1 \
    PRINCIPAL_IMPORT_DATABASE=development \
    pytest -q tests/test_principal_uploaded_workbook_live.py

This test is opt-in and writes only inside one manually-owned outer
transaction.  The transaction is rolled back in ``finally``; no import route
or helper is permitted to commit it.  Assertions and failure messages contain
aggregate counts/schema facts only, never workbook PII or row identifiers.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import text
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


_WORKBOOK = Path(
    os.environ.get(
        "PRINCIPAL_IMPORT_WORKBOOK",
        Path(__file__).resolve().parents[1]
        / "attached_assets/0_template_NEW_with_10_students_1789490500064.xlsx",
    )
)
if not _WORKBOOK.is_file():
    pytest.skip(
        "uploaded workbook not found; set PRINCIPAL_IMPORT_WORKBOOK explicitly",
        allow_module_level=True,
    )


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
from src.common.utils.canonical_grades import normalize_canonical_grade  # noqa: E402
from src.core.database.db import _get_async_url  # noqa: E402
from src.core.database.repository import Repos  # noqa: E402
from src.modules.bulk_import.controllers.bulk_import_export_routes import (  # noqa: E402
    _import_students,
)


pytestmark = pytest.mark.asyncio


_GRADE_LABELS = (
    "الصف الأول الابتدائي",
    "الصف الثاني الابتدائي",
    "الصف الثالث الابتدائي",
    "الصف الرابع الابتدائي",
    "الصف الخامس الابتدائي",
    "الصف السادس الابتدائي",
    "الصف الأول المتوسط",
    "الصف الثاني المتوسط",
    "الصف الثالث المتوسط",
    "الصف الأول الثانوي",
)


def _id() -> str:
    return str(uuid.uuid4())


def _route_value(row, field: str):
    """Read a route dict or Pydantic response without logging row values."""
    if isinstance(row, dict):
        return row.get(field)
    return getattr(row, field, None)


def _school_doc(school_id: str, principal_id: str) -> dict:
    return {
        "id": school_id,
        "name": f"Uploaded workbook regression {school_id[:8]}",
        "code": f"UWR-{school_id[:8]}",
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
        "password_hash": "uploaded-workbook-regression-not-used",
        "role": role,
        "tenant_id": school_id,
        "is_active": True,
        "must_change_password": False,
    }


def _grade_doc(school_id: str, grade_id: str, label: str) -> dict:
    canonical = normalize_canonical_grade(label)
    assert canonical is not None
    number = int(canonical["grade"])
    return {
        "id": grade_id,
        "school_id": school_id,
        "name": label,
        "name_ar": label,
        "name_en": canonical["label_en"],
        "code": f"uploaded-g{number}",
        "stage": canonical["stage"],
        "order": number,
        "is_active": True,
    }


async def _snapshot(
    session: AsyncSession,
    school_id: str,
    parent_user_ids: set[str] | None = None,
) -> dict:
    """Return aggregate counts only; never include row values."""
    parent_user_filter = (
        {"id": {"$in": list(parent_user_ids)}}
        if parent_user_ids
        else {"tenant_id": school_id, "role": "parent"}
    )
    return {
        "students": await gd_count(session, "students", {"school_id": school_id}),
        "classes": await gd_count(session, "classes", {"school_id": school_id}),
        "parents": await gd_count(session, "parents", {"school_id": school_id}),
        "parent_users": await gd_count(
            session,
            "users",
            parent_user_filter,
        ),
        "guardian_links": await gd_count(
            session,
            "guardian_links",
            {"tenant_id": school_id, "is_active": True},
        ),
        "batches": await gd_count(
            session,
            "bulk_import_batches",
            {"school_id": school_id},
        ),
    }


async def _columns(session: AsyncSession, table_name: str) -> set[str]:
    """Read live mapped-schema columns without relying on ORM metadata."""
    result = await session.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = :table_name
            """
        ),
        {"table_name": table_name},
    )
    return {str(value) for value in result.scalars().all()}


async def _assert_transaction_cleanup(
    engine,
    school_id: str,
) -> None:
    """Verify that the manually-owned outer rollback removed every fixture row."""
    async with engine.connect() as connection:
        async with AsyncSession(
            bind=connection,
            expire_on_commit=False,
        ) as verification_session:
            assert await gd_count(
                verification_session,
                "schools",
                {"id": school_id},
            ) == 0
            assert await gd_count(
                verification_session,
                "users",
                {"tenant_id": school_id},
            ) == 0
            assert await gd_count(
                verification_session,
                "students",
                {"school_id": school_id},
            ) == 0
            assert await gd_count(
                verification_session,
                "classes",
                {"school_id": school_id},
            ) == 0
            assert await gd_count(
                verification_session,
                "grade_levels",
                {"school_id": school_id},
            ) == 0
            assert await gd_count(
                verification_session,
                "parents",
                {"school_id": school_id},
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


async def test_actual_uploaded_workbook_import_and_live_routes():
    """Import all ten workbook rows and inspect the actual mapped schema."""
    engine = create_async_engine(_get_async_url(), poolclass=NullPool)
    school_id = _id()
    principal_id = _id()
    grade_ids = {label: _id() for label in _GRADE_LABELS}
    principal = {
        "id": principal_id,
        "full_name": "Uploaded workbook regression principal",
        "role": "school_principal",
        "tenant_id": school_id,
    }
    db = None
    connection = None
    outer_transaction = None
    session = None

    try:
        workbook_df = pd.read_excel(
            _WORKBOOK,
            sheet_name="البيانات",
            dtype=str,
        ).dropna(how="all")
        assert len(workbook_df) == 10, {
            "expected_rows": 10,
            "actual_rows": len(workbook_df),
        }

        # Keep this assertion intentionally about structure.  It protects
        # against accidentally replacing the supplied ten-grade workbook with
        # a fixture that has six classes (one per section label).
        grade_column = next(
            column for column in workbook_df.columns if "الصف" in str(column)
        )
        section_column = next(
            column for column in workbook_df.columns if "الفصل" in str(column)
        )
        parent_email_column = next(
            column
            for column in workbook_df.columns
            if "بريد" in str(column) and "ولي" in str(column)
        )
        grade_count = int(workbook_df[grade_column].nunique(dropna=True))
        section_count = int(workbook_df[section_column].nunique(dropna=True))
        pair_count = int(
            workbook_df.groupby(
                [grade_column, section_column],
                dropna=False,
            ).ngroups
        )
        expected_section_labels = {
            str(value).strip()
            for value in workbook_df[section_column].dropna()
        }
        expected_grade_section_pairs = {
            (
                str(normalize_canonical_grade(row[grade_column])["grade"]),
                str(row[section_column]).strip(),
            )
            for _, row in workbook_df.iterrows()
        }
        assert {
            "grade_count": grade_count,
            "section_count": section_count,
            "grade_section_pairs": pair_count,
        } == {
            "grade_count": 10,
            "section_count": 6,
            "grade_section_pairs": 10,
        }

        connection = await engine.connect()
        outer_transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        db = Repos(session)

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
                email=f"uploaded-workbook-principal-{school_id[:8]}@example.test",
                full_name=principal["full_name"],
            ),
        )
        for label in _GRADE_LABELS:
            await gd_insert(
                session,
                "grade_levels",
                _grade_doc(school_id, grade_ids[label], label),
            )

        # The development database already contains some global parent users
        # for the workbook's supplied email values.  Missing-email rows receive
        # new generated users; supplied emails must reuse their existing
        # accounts.  Keep the snapshots in memory only and report counts.
        supplied_parent_emails = {
            str(value).strip().casefold()
            for value in workbook_df[parent_email_column].dropna()
            if str(value).strip()
        }
        preexisting_import_users = {}
        preexisting_import_user_snapshots = {}
        for email in supplied_parent_emails:
            existing_user = await gd_find_one(
                session,
                "users",
                {"email": email},
            )
            if existing_user and existing_user.get("role") == "parent":
                user_id = existing_user.get("id")
                if user_id:
                    preexisting_import_users[user_id] = existing_user
                    preexisting_import_user_snapshots[user_id] = dict(existing_user)

        first_errors: list[dict] = []
        first_warnings: list[dict] = []
        first_result = await _import_students(
            db,
            workbook_df,
            school_id,
            principal,
            first_errors,
            first_warnings,
            filename=_WORKBOOK.name,
        )
        await session.flush()

        assert first_result["imported"] == 10, {
            "imported": first_result["imported"],
            "failed": first_result["failed"],
            "error_count": len(first_errors),
        }
        assert first_result["failed"] == 0
        assert not first_errors
        assert first_result["classes_created"] == 10
        assert first_result["parents_created"] == 10
        assert len(first_result["created_class_ids"]) == 10
        assert len(first_result["created_parent_ids"]) == 10
        expected_new_parent_users = 10 - len(preexisting_import_users)
        assert len(first_result["created_parent_user_ids"]) == (
            expected_new_parent_users
        )
        created_parent_user_ids = set(first_result["created_parent_user_ids"])
        assert not created_parent_user_ids.intersection(preexisting_import_users)
        imported_parent_user_ids = (
            set(preexisting_import_users) | created_parent_user_ids
        )
        assert len(imported_parent_user_ids) == 10
        assert await _snapshot(
            session,
            school_id,
            imported_parent_user_ids,
        ) == {
            "students": 10,
            "classes": 10,
            "parents": 10,
            "parent_users": 10,
            "guardian_links": 10,
            "batches": 1,
        }

        students = await gd_find(
            session,
            "students",
            {"school_id": school_id},
            limit=20,
        )
        classes = await gd_find(
            session,
            "classes",
            {"school_id": school_id},
            limit=20,
        )
        parents = await gd_find(
            session,
            "parents",
            {"school_id": school_id},
            limit=20,
        )
        parent_users = await gd_find(
            session,
            "users",
            {
                "id": {"$in": list(imported_parent_user_ids)},
                "role": "parent",
            },
            limit=20,
        )
        links = await gd_find(
            session,
            "guardian_links",
            {"tenant_id": school_id, "is_active": True},
            limit=20,
        )

        assert len(students) == 10
        assert len(classes) == 10
        assert len(parents) == 10
        assert len(parent_users) == 10
        assert len(links) == 10
        parent_users_by_id = {
            user.get("id"): user
            for user in parent_users
        }
        assert sum(
            user.get("id") in imported_parent_user_ids
            for user in parent_users
        ) == 10
        assert sum(
            parent_users_by_id.get(user_id) == snapshot
            for user_id, snapshot in preexisting_import_user_snapshots.items()
        ) == len(preexisting_import_user_snapshots)
        assert len({student.get("class_id") for student in students}) == 10
        assert len({student.get("parent_id") for student in students}) == 10
        assert len({link.get("student_id") for link in links}) == 10
        assert len({link.get("parent_ref") for link in links}) == 10
        parent_ids = {parent.get("id") for parent in parents}
        student_ids = {student.get("id") for student in students}
        parent_user_ids = {user.get("id") for user in parent_users}
        assert sum(
            link.get("student_id") in student_ids
            and link.get("parent_ref") in parent_user_ids
            for link in links
        ) == 10
        assert sum(
            student.get("parent_id") in parent_ids
            for student in students
        ) == 10
        user_emails = {user.get("email") for user in parent_users}
        assert sum(
            parent.get("email") in user_emails
            for parent in parents
            if parent.get("email")
        ) == 10

        classes_by_id = {row.get("id"): row for row in classes}
        imported_grade_numbers = {
            str(normalize_canonical_grade(label)["grade"]): label
            for label in _GRADE_LABELS
        }
        grade_class_pairs = {
            (
                student.get("grade"),
                classes_by_id[student.get("class_id")].get("section"),
            )
            for student in students
        }
        assert grade_class_pairs == expected_grade_section_pairs
        assert {
            classes_by_id[student.get("class_id")].get("section")
            for student in students
        } == expected_section_labels
        assert {
            student.get("grade") for student in students
        } == set(imported_grade_numbers)
        assert all(
            classes_by_id[student.get("class_id")].get("grade_level")
            == imported_grade_numbers[student.get("grade")]
            for student in students
        )

        # Call both admin parent surfaces directly while their module-level
        # Repos objects point at this same session.  This is the route-level
        # response without opening a second request transaction.
        from src.modules.academics.controllers import (  # noqa: PLC0415
            academics_student_routes,
        )
        from src.modules.search_directory.controllers import (  # noqa: PLC0415
            search_directory_routes_mod,
        )
        from dependencies import (  # noqa: PLC0415
            UserRole,
            get_current_user,
            require_roles,
        )
        from src.common.utils import (  # noqa: PLC0415
            parent_children_resolution,
        )
        from src.modules.portals.controllers.parent_portal_routes import (  # noqa: PLC0415
            setup_parent_portal_routes,
        )
        from fastapi import Response  # noqa: PLC0415

        academic_db = academics_student_routes.db
        directory_db = search_directory_routes_mod.db
        parent_resolution_db = parent_children_resolution.db
        same_db = db
        academics_student_routes.db = same_db
        search_directory_routes_mod.db = same_db
        parent_children_resolution.db = same_db
        try:
            parents_response = await academics_student_routes.get_parents(
                x_school_context=None,
                current_user=principal,
            )
            directory_response = await search_directory_routes_mod.directory_parents(
                page=1,
                per_page=50,
                current_user=principal,
            )

            # Build the actual parent-portal router with this same Repos
            # object, then invoke its registered /parent-portal/children
            # endpoint.  Use the persisted user-shaped claims for each
            # guardian_links.parent_ref.  In particular, an email-reused
            # global user may carry an older tenant_id; the target child must
            # still be resolved through the current-school guardian link.
            parent_router = setup_parent_portal_routes(
                same_db,
                get_current_user,
                require_roles,
                UserRole,
            )
            parent_children_endpoint = next(
                route.endpoint
                for route in parent_router.routes
                if getattr(route, "path", "").endswith("/children")
                and "GET" in (getattr(route, "methods", None) or set())
            )
            students_by_id = {
                student.get("id"): student
                for student in students
            }
            parent_children_target_count = 0
            parent_children_target_class_count = 0
            for link in links:
                parent_user = parent_users_by_id.get(link.get("parent_ref"))
                expected_student = students_by_id.get(link.get("student_id"))
                assert parent_user is not None
                assert expected_student is not None
                parent_claims = dict(parent_user)
                parent_claims["role"] = "parent"
                children_response = await parent_children_endpoint(
                    current_user=parent_claims,
                )
                portal_children = children_response.get("children") or []
                target_children = [
                    child
                    for child in portal_children
                    if _route_value(child, "id") == expected_student.get("id")
                ]
                parent_children_target_count += bool(target_children)
                parent_children_target_class_count += any(
                    _route_value(child, "class_id")
                    == expected_student.get("class_id")
                    for child in target_children
                )

            # Exercise the principal class-roster endpoint for each imported
            # class in this same transaction.  Each class has one imported
            # student in this workbook; assert the expected class/student
            # relationship without exposing row values on failure.
            class_roster_target_count = 0
            for expected_student in students:
                class_response = await academics_student_routes.get_class_students(
                    class_id=expected_student.get("class_id"),
                    response=Response(),
                    current_user=principal,
                )
                class_roster_target_count += any(
                    _route_value(row, "id") == expected_student.get("id")
                    and _route_value(row, "class_id")
                    == expected_student.get("class_id")
                    for row in class_response
                )
        finally:
            academics_student_routes.db = academic_db
            search_directory_routes_mod.db = directory_db
            parent_children_resolution.db = parent_resolution_db

        assert len(parents_response) == 10
        assert sum(
            int(parent.get("children_count") or 0)
            for parent in parents_response
        ) == 10
        assert sum(
            int(parent.get("children_count") or 0) > 0
            for parent in parents_response
        ) == 10
        assert len(directory_response["parents"]) == 10
        assert directory_response["total"] == 10
        assert sum(
            int(parent.get("children_count") or 0)
            for parent in directory_response["parents"]
        ) == 10
        assert sum(
            int(parent.get("children_count") or 0) > 0
            for parent in directory_response["parents"]
        ) == 10
        assert class_roster_target_count == 10
        assert parent_children_target_count == 10
        assert parent_children_target_class_count == 10

        before_retry = await _snapshot(
            session,
            school_id,
            imported_parent_user_ids,
        )
        retry_errors: list[dict] = []
        retry_result = await _import_students(
            db,
            workbook_df,
            school_id,
            principal,
            retry_errors,
            [],
            filename=_WORKBOOK.name,
        )
        await session.flush()
        after_retry = await _snapshot(
            session,
            school_id,
            imported_parent_user_ids,
        )
        assert retry_result["imported"] == 10
        assert retry_result["updated"] == 10
        assert retry_result["created"] == 0
        assert retry_result["parents_created"] == 0
        assert retry_result["classes_created"] == 0
        assert retry_result["created_parent_user_ids"] == []
        assert retry_result["failed"] == 0
        assert not retry_errors
        assert after_retry == {
            **before_retry,
            "batches": before_retry["batches"] + 1,
        }

        # Verify ownership fields against information_schema, not only ORM
        # metadata.  Current development DBs have historically lacked both
        # columns; gd_insert then silently drops these service fields.
        parent_columns = await _columns(session, "parents")
        batch_columns = await _columns(session, "bulk_import_batches")
        batch = await gd_find_one(
            session,
            "bulk_import_batches",
            {"school_id": school_id},
        )
        assert batch is not None
        ownership_findings = {
            "parents_user_id_column": "user_id" in parent_columns,
            "parent_rows_with_user_id": sum(
                1 for parent in parents if parent.get("user_id")
            ),
            "bulk_import_batches_ownership_version_column": (
                "ownership_version" in batch_columns
            ),
            "persisted_ownership_version": batch.get("ownership_version") is not None,
            "persisted_created_parent_ids": len(
                batch.get("created_parent_ids") or []
            ),
            "persisted_created_parent_user_ids": len(
                batch.get("created_parent_user_ids") or []
            ),
        }
        assert ownership_findings["parents_user_id_column"] is False
        assert ownership_findings["parent_rows_with_user_id"] == 0
        # The physical marker is historical and may remain on an older
        # development database, but current ORM inserts must never depend on
        # or persist it.
        assert ownership_findings["persisted_ownership_version"] is False
        assert ownership_findings["persisted_created_parent_ids"] == 10
        assert (
            ownership_findings["persisted_created_parent_user_ids"]
            == expected_new_parent_users
        ), (
            "live ownership/schema mismatch (aggregate only): "
            f"{ownership_findings}"
        )
    finally:
        # This is intentionally the only transaction lifecycle in the test.
        # No route/helper call is allowed to commit temporary development rows.
        if session is not None:
            await session.rollback()
            await session.close()
        if outer_transaction is not None and outer_transaction.is_active:
            await outer_transaction.rollback()
        if connection is not None:
            await connection.close()
        try:
            await _assert_transaction_cleanup(engine, school_id)
        finally:
            await engine.dispose()