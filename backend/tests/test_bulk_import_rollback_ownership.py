"""Rollback ownership regressions for the principal student import."""

from copy import deepcopy
import os
from types import SimpleNamespace
import uuid

import pytest

from engines.sql_utils import gd_find_one, gd_insert
from src.modules.bulk_import.controllers import bulk_import_export_routes as routes


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
    def __init__(self, rows):
        self.rows = rows

    def begin_nested(self):
        return _Savepoint(self)


def _db(rows):
    return SimpleNamespace(session=_Session(rows))


async def _find(session, collection, filters, limit=None, **_kwargs):
    result = []
    for row in session.rows.get(collection, []):
        matches = True
        for key, expected in filters.items():
            actual = row.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                matches = matches and actual in expected["$in"]
            elif isinstance(expected, dict) and "$nin" in expected:
                matches = matches and actual not in expected["$nin"]
            else:
                matches = matches and actual == expected
        if matches:
            result.append(deepcopy(row))
    return result[:limit] if limit else result


async def _count(session, collection, filters, **_kwargs):
    return len(await _find(session, collection, filters))


async def _update(session, collection, filters, updates, **_kwargs):
    changed = 0
    for row in session.rows.get(collection, []):
        if all(row.get(key) == value for key, value in filters.items()):
            values = updates.get("$set", updates)
            row.update(values)
            changed += 1
    return changed


async def _delete_many(session, collection, filters, **_kwargs):
    rows = session.rows.get(collection, [])
    kept = []
    deleted = 0
    for row in rows:
        matches = True
        for key, expected in filters.items():
            actual = row.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                matches = matches and actual in expected["$in"]
            elif isinstance(expected, dict) and "$nin" in expected:
                matches = matches and actual not in expected["$nin"]
            else:
                matches = matches and actual == expected
        if matches:
            deleted += 1
        else:
            kept.append(row)
    session.rows[collection] = kept
    return deleted


async def _delete_one(session, collection, filters, **_kwargs):
    return await _delete_many(session, collection, filters)


async def _insert(session, collection, document, **_kwargs):
    session.rows.setdefault(collection, []).append(deepcopy(document))


async def _noop_reconcile(*_args, **_kwargs):
    return None


def _patch_db(monkeypatch):
    monkeypatch.setattr(routes, "gd_find", _find)
    monkeypatch.setattr(routes, "gd_count", _count)
    monkeypatch.setattr(routes, "gd_update_one", _update)
    monkeypatch.setattr(routes, "gd_delete_many", _delete_many)
    monkeypatch.setattr(routes, "gd_delete_one", _delete_one)
    monkeypatch.setattr(routes, "gd_insert", _insert)
    monkeypatch.setattr(
        "engines.entity_counts.reconcile_school_counts", _noop_reconcile
    )
    monkeypatch.setattr(
        "engines.entity_counts.reconcile_class_counts", _noop_reconcile
    )


@pytest.mark.asyncio
async def test_reused_parent_and_shared_user_survive_rollback(monkeypatch):
    rows = {
        "students": [
            {
                "id": "new-student",
                "school_id": "school-a",
                "parent_id": "existing-parent",
                "class_id": "class-a",
            },
            {
                "id": "old-student",
                "school_id": "school-a",
                "parent_id": "existing-parent",
                "class_id": "class-a",
            },
        ],
        "parents": [{
            "id": "existing-parent",
            "school_id": "school-a",
            "email": "shared@example.test",
            "student_ids": ["new-student", "old-student"],
        }],
        "users": [{
            "id": "shared-user",
            "email": "shared@example.test",
            "role": "parent",
            "tenant_id": "school-a",
        }],
        "guardian_links": [{
            "id": "link-new",
            "student_id": "new-student",
            "parent_ref": "shared-user",
            "tenant_id": "school-a",
        }],
        "bulk_import_batches": [],
        "audit_logs": [],
        "classes": [],
        "parent_invitations": [],
    }
    _patch_db(monkeypatch)
    database = _db(rows)
    async with database.session.begin_nested():
        result = await routes._rollback_import_batch_mutations(
            database,
            "batch-1",
            {
                "student_ids": ["new-student"],
                "created_parent_ids": [],
                "created_parent_user_ids": [],
                "ownership_version": 2,
            },
            "school-a",
            {"id": "principal"},
        )

    assert result["rolled_back_students"] == 1
    assert rows["parents"][0]["id"] == "existing-parent"
    assert rows["users"][0]["id"] == "shared-user"
    assert rows["parents"][0]["student_ids"] == ["old-student"]
    assert not rows["guardian_links"]


@pytest.mark.asyncio
async def test_created_user_is_preserved_when_shared_by_another_school(monkeypatch):
    rows = {
        "students": [
            {"id": "school-a-student", "school_id": "school-a",
             "parent_id": "created-parent", "class_id": "class-a"},
            {"id": "school-b-student", "school_id": "school-b",
             "parent_id": "other-parent", "class_id": "class-b"},
        ],
        "parents": [
            {"id": "created-parent", "school_id": "school-a",
             "email": "shared@example.test",
             "student_ids": ["school-a-student"]},
            {"id": "other-parent", "school_id": "school-b",
             "email": "shared@example.test",
             "student_ids": ["school-b-student"]},
        ],
        "users": [{
            "id": "shared-user", "email": "shared@example.test",
            "role": "parent", "tenant_id": "school-a",
        }],
        "guardian_links": [
            {"id": "link-a", "student_id": "school-a-student",
             "parent_ref": "shared-user", "tenant_id": "school-a"},
            {"id": "link-b", "student_id": "school-b-student",
             "parent_ref": "shared-user", "tenant_id": "school-b"},
        ],
        "bulk_import_batches": [],
        "audit_logs": [],
        "classes": [],
        "parent_invitations": [],
    }
    _patch_db(monkeypatch)
    database = _db(rows)
    async with database.session.begin_nested():
        result = await routes._rollback_import_batch_mutations(
            database,
            "batch-2",
            {
                "student_ids": ["school-a-student"],
                "created_parent_ids": ["created-parent"],
                "created_parent_user_ids": ["shared-user"],
                "ownership_version": 2,
            },
            "school-a",
            {"id": "principal"},
        )

    assert result["rolled_back_students"] == 1
    assert result["rolled_back_parents"] == 1
    assert result["rolled_back_users"] == 0
    assert not any(row["id"] == "created-parent" for row in rows["parents"])
    assert any(row["id"] == "other-parent" for row in rows["parents"])
    assert rows["users"][0]["id"] == "shared-user"
    assert [row["id"] for row in rows["guardian_links"]] == ["link-b"]


@pytest.mark.asyncio
async def test_created_user_without_email_is_preserved_fail_closed(monkeypatch):
    """A missing parent email cannot authorize account deletion."""
    rows = {
        "students": [{
            "id": "student-with-parent", "school_id": "school-a",
            "parent_id": "created-parent",
        }],
        "parents": [{
            "id": "created-parent", "school_id": "school-a",
            "student_ids": ["student-with-parent"],
        }],
        "users": [{
            "id": "created-user", "role": "parent",
            "tenant_id": "school-a",
        }],
        "guardian_links": [{
            "id": "link-created", "student_id": "student-with-parent",
            "parent_ref": "created-user", "tenant_id": "school-a",
        }],
        "bulk_import_batches": [],
        "audit_logs": [],
        "classes": [],
        "parent_invitations": [],
    }
    _patch_db(monkeypatch)
    database = _db(rows)

    async with database.session.begin_nested():
        result = await routes._rollback_import_batch_mutations(
            database,
            "batch-without-email",
            {
                "student_ids": ["student-with-parent"],
                "created_parent_ids": ["created-parent"],
                "created_parent_user_ids": ["created-user"],
                "ownership_version": 2,
            },
            "school-a",
            {"id": "principal"},
        )

    assert result["rolled_back_parents"] == 1
    assert result["rolled_back_users"] == 0
    assert rows["users"][0]["id"] == "created-user"


@pytest.mark.asyncio
async def test_legacy_manifest_never_grants_parent_or_user_deletion(monkeypatch):
    rows = {
        "students": [{
            "id": "legacy-student", "school_id": "school-a",
            "parent_id": "legacy-parent",
        }],
        "parents": [{
            "id": "legacy-parent", "school_id": "school-a",
            "email": "legacy@example.test", "student_ids": ["legacy-student"],
        }],
        "users": [{
            "id": "legacy-user", "email": "legacy@example.test",
            "role": "parent", "tenant_id": "school-a",
        }],
        "guardian_links": [{
            "id": "legacy-link", "student_id": "legacy-student",
            "parent_ref": "legacy-user", "tenant_id": "school-a",
        }],
        "bulk_import_batches": [],
        "audit_logs": [],
        "classes": [],
        "parent_invitations": [],
    }
    _patch_db(monkeypatch)
    database = _db(rows)
    async with database.session.begin_nested():
        result = await routes._rollback_import_batch_mutations(
            database,
            "legacy-batch",
            {
                "student_ids": ["legacy-student"],
                "created_parent_ids": ["legacy-parent"],
                "created_parent_user_ids": ["legacy-user"],
            },
            "school-a",
            {"id": "principal"},
        )

    assert result["rolled_back_students"] == 1
    assert result["rolled_back_parents"] == 0
    assert result["rolled_back_users"] == 0
    assert rows["parents"][0]["id"] == "legacy-parent"
    assert rows["users"][0]["id"] == "legacy-user"


@pytest.mark.asyncio
async def test_rollback_savepoint_restores_rows_when_finalization_fails(monkeypatch):
    rows = {
        "students": [{"id": "new-student", "school_id": "school-a"}],
        "parents": [], "users": [], "guardian_links": [],
        "bulk_import_batches": [], "audit_logs": [],
        "classes": [], "parent_invitations": [],
    }
    _patch_db(monkeypatch)

    async def fail_batch_update(*_args, **_kwargs):
        raise RuntimeError("batch update failed")

    monkeypatch.setattr(routes, "gd_update_one", fail_batch_update)
    database = _db(rows)
    with pytest.raises(RuntimeError):
        async with database.session.begin_nested():
            await routes._rollback_import_batch_mutations(
                database,
                "batch-3",
                {"student_ids": ["new-student"], "ownership_version": 2},
                "school-a",
                {"id": "principal"},
            )

    assert database.session.rows["students"] == [
        {"id": "new-student", "school_id": "school-a"}
    ]


@pytest.mark.asyncio
async def test_removed_ownership_marker_does_not_round_trip_through_batch_model(
    _db_session, tenant_a
):
    """The removed marker is not selected or inserted by the current ORM.

    This intentionally writes only one temporary batch row.  The shared test
    fixture rolls the transaction back, and the explicit TESTING gate keeps a
    developer from accidentally pointing this persistence check at production.
    """
    if os.environ.get("TESTING") != "1":
        pytest.skip("refusing real DB persistence check outside TESTING")

    batch_id = str(uuid.uuid4())
    await gd_insert(
        _db_session,
        "bulk_import_batches",
        {
            "id": batch_id,
            "school_id": tenant_a,
            "import_type": "students",
            "imported_count": 0,
            "student_ids": [],
            "created_class_ids": [],
            "created_parent_ids": [],
            "created_parent_user_ids": [],
            "status": "active",
        },
    )
    await _db_session.flush()

    reread = await gd_find_one(
        _db_session,
        "bulk_import_batches",
        {"id": batch_id, "school_id": tenant_a},
    )
    assert reread is not None
    assert "ownership_version" not in reread