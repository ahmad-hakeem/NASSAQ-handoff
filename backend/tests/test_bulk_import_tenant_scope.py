"""Focused tenant-binding regressions for the bulk import/export routes."""

import uuid

import pytest
from fastapi import HTTPException

from dependencies import UserRole, create_access_token, db
from engines.sql_utils import gd_find_one, gd_insert
from src.modules.bulk_import.controllers.bulk_import_export_routes import (
    _resolve_bulk_school_id,
)


PRINCIPAL = {
    "role": "school_principal",
    "tenant_id": "school-a",
    "school_id": "school-a",
}
PLATFORM_ADMIN = {
    "role": "platform_admin",
    "tenant_id": None,
    "school_id": None,
}


def test_principal_cannot_spoof_school_with_query_parameter():
    with pytest.raises(HTTPException) as exc:
        _resolve_bulk_school_id(PRINCIPAL, None, "school-b")
    assert exc.value.status_code == 403


def test_principal_cannot_spoof_school_with_context_header():
    with pytest.raises(HTTPException) as exc:
        _resolve_bulk_school_id(PRINCIPAL, "school-b")
    assert exc.value.status_code == 403


def test_platform_admin_without_context_fails_closed():
    with pytest.raises(HTTPException) as exc:
        _resolve_bulk_school_id(PLATFORM_ADMIN, None)
    assert exc.value.status_code == 400


def test_plain_platform_admin_cannot_use_school_query_as_context():
    with pytest.raises(HTTPException) as exc:
        _resolve_bulk_school_id(PLATFORM_ADMIN, None, "school-b")
    assert exc.value.status_code == 403


def test_platform_admin_with_active_switch_must_use_pinned_context():
    switched_admin = {
        **PLATFORM_ADMIN,
        "tenant_id": "school-b",
        "is_impersonating": True,
    }
    assert _resolve_bulk_school_id(switched_admin, "school-b") == "school-b"


def test_platform_admin_with_inactive_switch_cannot_use_context():
    inactive_switch = {
        **PLATFORM_ADMIN,
        "tenant_id": "school-b",
        "is_impersonating": False,
    }
    with pytest.raises(HTTPException) as exc:
        _resolve_bulk_school_id(inactive_switch, "school-b")
    assert exc.value.status_code == 403


async def _platform_admin_impersonation_headers(school_id: str) -> dict:
    user_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": user_id,
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": None,
        "email": f"{user_id}@bulk-scope.test",
        "full_name": "Bulk Scope Platform Admin",
        "is_active": True,
        "password_hash": "x",
    })
    token = create_access_token({
        "sub": user_id,
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": school_id,
        "is_impersonating": True,
    })
    return {
        "Authorization": f"Bearer {token}",
        "X-School-Context": school_id,
    }


async def _seed_active_batch(school_id: str) -> str:
    batch_id = str(uuid.uuid4())
    await gd_insert(db.session, "bulk_import_batches", {
        "id": batch_id,
        "school_id": school_id,
        "actor_id": "bulk-scope-test",
        "actor_name": "Bulk Scope Test",
        "import_type": "students",
        "file_name": "scope-test.xlsx",
        "imported_count": 0,
        "student_ids": [],
        "created_class_ids": [],
        "created_parent_ids": [],
        "created_parent_user_ids": [],
        "status": "active",
    })
    return batch_id


@pytest.mark.asyncio
async def test_switched_admin_rollback_is_tenant_bound_at_route_level(
    client, tenant_a, tenant_b,
):
    """A pinned A preview cannot mutate B, while its A batch still rolls back."""
    batch_b = await _seed_active_batch(tenant_b)
    batch_a = await _seed_active_batch(tenant_a)
    headers = await _platform_admin_impersonation_headers(tenant_a)

    foreign_response = await client.post(
        f"/bulk/batches/{batch_b}/rollback",
        headers=headers,
    )
    assert foreign_response.status_code == 404, foreign_response.text
    untouched_foreign_batch = await gd_find_one(
        db.session,
        "bulk_import_batches",
        {"id": batch_b, "school_id": tenant_b},
    )
    assert untouched_foreign_batch["status"] == "active"

    own_response = await client.post(
        f"/bulk/batches/{batch_a}/rollback",
        headers=headers,
    )
    assert own_response.status_code == 200, own_response.text
    rolled_back_batch = await gd_find_one(
        db.session,
        "bulk_import_batches",
        {"id": batch_a, "school_id": tenant_a},
    )
    assert rolled_back_batch["status"] == "rolled_back"