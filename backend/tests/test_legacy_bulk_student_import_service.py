"""Focused contracts for the principal legacy student importer.

These tests keep the row-atomicity contract independent from the live
PostgreSQL fixture.  The route itself is covered by the existing API suite;
the fake session here makes it possible to prove that a class created for a
failed row is rolled back while a prior successful row remains committed.
"""

from copy import deepcopy
from types import SimpleNamespace

import pandas as pd
import pytest

from src.modules.bulk_import.services import student_import_service as importer


class _Savepoint:
    def __init__(self, session):
        self.session = session
        self.snapshot = None

    async def __aenter__(self):
        self.snapshot = deepcopy(self.session.rows)
        return self

    async def __aexit__(self, exc_type, _exc, _tb):
        if exc_type:
            self.session.rows = self.snapshot
        return False


class _Session:
    def __init__(self):
        self.rows = {
            "grade_levels": [],
            "classes": [],
            "students": [],
            "parents": [],
            "users": [],
            "guardian_links": [],
            "bulk_import_batches": [],
        }

    async def execute(self, *_args, **_kwargs):
        return SimpleNamespace()

    def begin_nested(self):
        return _Savepoint(self)


def _fake_db(session):
    return SimpleNamespace(session=session)


@pytest.mark.asyncio
async def test_import_normalises_aliases_arabic_digits_and_canonical_grade(monkeypatch):
    session = _Session()
    monkeypatch.setattr(importer, "acquire_school_import_lock", _noop_lock)
    monkeypatch.setattr(importer, "gd_find", _find)
    monkeypatch.setattr(importer, "gd_insert", _insert)
    monkeypatch.setattr(importer, "gd_update_one", _update)
    monkeypatch.setattr(importer, "gd_find_one", _find_one)
    monkeypatch.setattr(importer, "_fake_unused", None, raising=False)
    monkeypatch.setattr(
        "services.parent_linking.link_or_update_real_school_guardian",
        _guardian,
    )
    monkeypatch.setattr("engines.entity_counts.reconcile_school_counts", _reconcile_school)
    monkeypatch.setattr("engines.entity_counts.reconcile_class_counts", _reconcile_class)
    monkeypatch.setattr("dependencies.generate_secure_password", lambda: "temp")
    monkeypatch.setattr("dependencies.hash_password", lambda _value: "hash")

    errors, warnings = [], []
    frame = pd.DataFrame([{
        " FIRST_NAME (REQUIRED) ": "سارة",
        "LAST NAME": "الشمري",
        "NATIONAL ID": "١٢٣٤٥٦٧٨٩",
        "GRADE LEVEL": "١",
        "SECTION": "أ",
        "GUARDIAN PHONE": "٠٥٠١٢٣٤٥٦٧",
    }])
    result = await importer.import_students(
        _fake_db(session), frame, "school-1", {"id": "principal-1"}, errors, warnings
    )

    assert result["imported"] == 1
    assert result["failed"] == 0
    assert result["assigned"] == 1
    assert result["classes_created"] == 1
    assert session.rows["students"][0]["national_id"] == "0123456789"
    assert session.rows["students"][0]["grade"] == "1"
    assert session.rows["classes"][0]["grade_level"] == "الصف الأول الابتدائي"


@pytest.mark.asyncio
async def test_failed_row_rolls_back_its_class_but_not_prior_success(monkeypatch):
    session = _Session()
    monkeypatch.setattr(importer, "acquire_school_import_lock", _noop_lock)
    monkeypatch.setattr(importer, "gd_find", _find)
    monkeypatch.setattr(importer, "gd_insert", _insert)
    monkeypatch.setattr(importer, "gd_update_one", _update)
    monkeypatch.setattr(importer, "gd_find_one", _find_one)
    monkeypatch.setattr(
        "services.parent_linking.link_or_update_real_school_guardian",
        _guardian_fails_for_second_row,
    )
    monkeypatch.setattr("engines.entity_counts.reconcile_school_counts", _reconcile_school)
    monkeypatch.setattr("engines.entity_counts.reconcile_class_counts", _reconcile_class)
    monkeypatch.setattr("dependencies.generate_secure_password", lambda: "temp")
    monkeypatch.setattr("dependencies.hash_password", lambda _value: "hash")

    errors, warnings = [], []
    frame = pd.DataFrame([
        {
            "First Name": "أحمد", "Last Name": "الأول",
            "National ID": "1234567890", "Grade": "1", "Class": "أ",
            "Parent Phone": "0501234567",
        },
        {
            "First Name": "محمد", "Last Name": "الثاني",
            "National ID": "1234567891", "Grade": "2", "Class": "ب",
            "Parent Phone": "0501234568",
        },
    ])
    result = await importer.import_students(
        _fake_db(session), frame, "school-1", {"id": "principal-1"}, errors, warnings
    )

    assert result["imported"] == 1
    assert result["failed"] == 1
    assert result["classes_created"] == 1
    assert len(session.rows["students"]) == 1
    assert len(session.rows["classes"]) == 1
    assert session.rows["classes"][0]["grade_level"] == "الصف الأول الابتدائي"


@pytest.mark.asyncio
async def test_missing_grade_and_class_are_row_errors(monkeypatch):
    session = _Session()
    monkeypatch.setattr(importer, "acquire_school_import_lock", _noop_lock)
    errors, warnings = [], []
    frame = pd.DataFrame([{
        "First Name": "أحمد",
        "Last Name": "الأول",
        "National ID": "1234567890",
        "Parent Phone": "0501234567",
    }])
    result = await importer.import_students(
        _fake_db(session), frame, "school-1", {"id": "principal-1"}, errors, warnings
    )

    assert result["imported"] == 0
    assert result["failed"] == 1
    assert {entry["field"] for entry in errors} == {"grade", "class_name"}


@pytest.mark.asyncio
async def test_blank_merged_grade_class_cells_fail_that_row_explicitly(monkeypatch):
    session = _Session()
    _patch_fake_dependencies(monkeypatch, _guardian)
    errors, warnings = [], []
    # Pandas represents all but the first row of an Excel merged range as NaN.
    # The importer must reject those rows rather than silently creating an
    # unassigned student.
    frame = pd.DataFrame([
        {
            "First Name": "أحمد", "Last Name": "الأول",
            "National ID": "1234567890", "Grade": "1", "Class": "أ",
            "Parent Phone": "0501234567",
        },
        {
            "First Name": "محمد", "Last Name": "الثاني",
            "National ID": "1234567891", "Grade": None, "Class": None,
            "Parent Phone": "0501234568",
        },
    ])

    result = await importer.import_students(
        _fake_db(session), frame, "school-1", {"id": "principal-1"}, errors, warnings
    )

    assert result["imported"] == 1
    assert result["failed"] == 1
    row_errors = [error for error in errors if error["row"] == 3]
    assert {error["field"] for error in row_errors} == {"الصف", "الفصل"}


@pytest.mark.asyncio
async def test_manifest_distinguishes_new_parent_row_from_reused_global_user(monkeypatch):
    session = _Session()
    _patch_fake_dependencies(monkeypatch, _guardian_new_parent_reused_user)
    errors, warnings = [], []
    frame = pd.DataFrame([{
        "First Name": "أحمد", "Last Name": "الأول",
        "National ID": "3234567890", "Grade": "1", "Class": "أ",
        "Parent Phone": "0501234567",
    }])

    result = await importer.import_students(
        _fake_db(session), frame, "school-1", {"id": "principal-1"}, errors, warnings
    )

    assert result["created_parent_ids"] == ["parent-row"]
    assert result["created_parent_user_ids"] == []
    manifest = session.rows["bulk_import_batches"][0]
    assert manifest["ownership_version"] == 2
    assert manifest["created_parent_ids"] == ["parent-row"]
    assert manifest["created_parent_user_ids"] == []


@pytest.mark.asyncio
async def test_matching_is_grade_scoped_and_reimport_updates_or_restores(monkeypatch):
    session = _Session()
    school_id = "school-1"
    session.rows["classes"] = [
        {
            "id": "grade-1-a", "school_id": school_id,
            "name": "الصف الأول الابتدائي - أ",
            "grade_level": "الصف الأول الابتدائي", "section": "أ",
            "capacity": 1, "current_students": 1, "is_active": True,
        },
        {
            "id": "grade-2-a", "school_id": school_id,
            "name": "الصف الثاني الابتدائي - أ",
            "grade_level": "الصف الثاني الابتدائي", "section": "أ",
            "capacity": 1, "current_students": 0, "is_active": False,
        },
    ]
    session.rows["students"] = [
        {
            "id": "active-student", "school_id": school_id,
            "national_id": "1234567890", "full_name": "قديم نشط",
            "grade": "1", "class_id": "grade-1-a", "is_active": True,
        },
        {
            "id": "deleted-student", "school_id": school_id,
            "national_id": "2234567891", "full_name": "قديم محذوف",
            "grade": "2", "class_id": None, "is_active": False,
        },
    ]
    _patch_fake_dependencies(monkeypatch, _guardian)

    errors, warnings = [], []
    frame = pd.DataFrame([
        {
            "First Name": "نشط", "Last Name": "محدث",
            "National ID": "1234567890", "Grade": "١", "Class": "أ",
            "Parent Phone": "0501234567",
        },
        {
            "First Name": "محذوف", "Last Name": "مستعاد",
            "National ID": "٢٢٣٤٥٦٧٨٩١", "Grade": "٢", "Class": "أ",
            "Parent Phone": "0501234568",
        },
    ])
    result = await importer.import_students(
        _fake_db(session), frame, school_id, {"id": "principal-1"}, errors, warnings
    )

    assert result["imported"] == 2
    assert result["updated"] == 1
    assert result["restored"] == 1
    assert result["classes_created"] == 0
    assert result["assigned"] == 2
    assert result["updated_student_ids"] == ["active-student"]
    assert result["restored_student_ids"] == ["deleted-student"]
    active = next(row for row in session.rows["students"] if row["id"] == "active-student")
    restored = next(row for row in session.rows["students"] if row["id"] == "deleted-student")
    assert active["class_id"] == "grade-1-a"
    assert restored["class_id"] == "grade-2-a"
    assert restored["is_active"] is True
    assert next(row for row in session.rows["classes"] if row["id"] == "grade-1-a")["is_active"] is True
    assert next(row for row in session.rows["classes"] if row["id"] == "grade-2-a")["is_active"] is True


@pytest.mark.asyncio
async def test_full_class_is_a_failed_row_not_an_unassigned_success(monkeypatch):
    session = _Session()
    session.rows["classes"] = [{
        "id": "full-class", "school_id": "school-1",
        "name": "الصف الأول الابتدائي - أ",
        "grade_level": "الصف الأول الابتدائي", "section": "أ",
        "capacity": 1, "current_students": 1, "is_active": True,
    }]
    session.rows["students"] = [{
        "id": "occupant", "school_id": "school-1",
        "national_id": "1234567890", "class_id": "full-class",
        "is_active": True,
    }]
    _patch_fake_dependencies(monkeypatch, _guardian)
    errors, warnings = [], []
    frame = pd.DataFrame([{
        "First Name": "جديد", "Last Name": "مرفوض",
        "National ID": "1234567891", "Grade": "1", "Class": "أ",
        "Parent Phone": "0501234567",
    }])

    result = await importer.import_students(
        _fake_db(session), frame, "school-1", {"id": "principal-1"}, errors, warnings
    )

    assert result["imported"] == 0
    assert result["failed"] == 1
    assert result["assigned"] == 0
    assert len(session.rows["students"]) == 1
    assert session.rows["students"][0]["class_id"] == "full-class"
    assert "ممتلئ" in errors[0]["message"]


def _patch_fake_dependencies(monkeypatch, guardian):
    monkeypatch.setattr(importer, "acquire_school_import_lock", _noop_lock)
    monkeypatch.setattr(importer, "gd_find", _find)
    monkeypatch.setattr(importer, "gd_insert", _insert)
    monkeypatch.setattr(importer, "gd_update_one", _update)
    monkeypatch.setattr(importer, "gd_find_one", _find_one)
    monkeypatch.setattr("services.parent_linking.link_or_update_real_school_guardian", guardian)
    monkeypatch.setattr("engines.entity_counts.reconcile_school_counts", _reconcile_school)
    monkeypatch.setattr("engines.entity_counts.reconcile_class_counts", _reconcile_class)
    monkeypatch.setattr("dependencies.generate_secure_password", lambda: "temp")
    monkeypatch.setattr("dependencies.hash_password", lambda _value: "hash")


async def _noop_lock(_session, _school_id):
    return None


async def _find(session, collection, filters, limit=None, **_kwargs):
    rows = session.rows.get(collection, [])
    out = []
    for row in rows:
        if all(
            (row.get(key) in value.get("$in", [])) if isinstance(value, dict) and "$in" in value
            else row.get(key) == value
            for key, value in filters.items()
        ):
            out.append(deepcopy(row))
    return out[:limit] if limit else out


async def _find_one(session, collection, filters, **_kwargs):
    rows = await _find(session, collection, filters)
    return rows[0] if rows else None


async def _insert(session, collection, document):
    session.rows.setdefault(collection, []).append(deepcopy(document))


async def _update(session, collection, filters, updates):
    rows = session.rows.get(collection, [])
    for row in rows:
        if all(row.get(key) == value for key, value in filters.items()):
            for key, value in updates.get("$set", updates).items():
                row[key] = value
            return 1
    return 0


async def _guardian(_session, student, **_kwargs):
    if student["national_id"] == "1234567891":
        raise ValueError("guardian provisioning failed")
    return {
        "parent_id": "parent-1",
        "parent_name": student.get("parent_name"),
        "parent_phone": student.get("parent_phone"),
        "parent_email": None,
        "is_new": False,
    }


async def _guardian_fails_for_second_row(_session, student, **_kwargs):
    if student["national_id"] == "1234567891":
        raise ValueError("guardian provisioning failed")
    return {
        "parent_id": "parent-1",
        "parent_name": student.get("parent_name"),
        "parent_phone": student.get("parent_phone"),
        "parent_email": None,
        "is_new": False,
    }


async def _guardian_new_parent_reused_user(_session, student, **_kwargs):
    return {
        "parent_id": "parent-row",
        "parent_user_id": "shared-user",
        "parent_name": student.get("parent_name"),
        "parent_phone": student.get("parent_phone"),
        "parent_email": None,
        "is_new": True,
        "is_new_user": False,
    }


async def _reconcile_school(*_args, **_kwargs):
    return (0, 0)


async def _reconcile_class(*_args, **_kwargs):
    return 0