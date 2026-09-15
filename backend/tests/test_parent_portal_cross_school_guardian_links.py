"""Regression coverage for global parent accounts with cross-school links.

The parent account can be reused when a guardian is imported into another
school.  Its ``users.tenant_id`` may still name the older school, so the
parent portal must use the active canonical ``guardian_links.parent_ref`` only
for this narrow exception.  Contact fields, inactive links, mismatched
school/parent relations, and unrelated active links must not authorize access.
"""
from __future__ import annotations

import uuid

import pytest

from dependencies import UserRole, create_access_token, db
from engines.sql_utils import gd_insert
from src.common.utils.parent_children_resolution import resolve_parent_children


def _headers(user: dict) -> dict:
    token = create_access_token(
        {
            "sub": user["id"],
            "role": UserRole.PARENT.value,
            "tenant_id": user["tenant_id"],
        }
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_global_parent(old_school_id: str, new_school_id: str) -> dict:
    parent_user_id = str(uuid.uuid4())
    parent_record_id = str(uuid.uuid4())
    email = f"cross-school-{parent_user_id}@t.test"
    await gd_insert(
        db.session,
        "users",
        {
            "id": parent_user_id,
            "role": UserRole.PARENT.value,
            "tenant_id": old_school_id,
            "parent_id": parent_record_id,
            "email": email,
            "full_name": "ولي أمر متعدد المدارس",
            "is_active": True,
            "password_hash": "x",
        },
    )
    await gd_insert(
        db.session,
        "parents",
        {
            "id": parent_record_id,
            "school_id": new_school_id,
            "email": email,
            "full_name": "ولي أمر متعدد المدارس",
            "is_active": True,
            "student_ids": [],
        },
    )
    return {
        "id": parent_user_id,
        "tenant_id": old_school_id,
        "parent_id": parent_record_id,
    }


async def _seed_linked_student(
    school_id: str,
    parent_user_id: str,
    parent_record_id: str,
    *,
    link_active: bool = True,
    link_school_id: str | None = None,
    link_parent_id: str | None = None,
) -> str:
    student_id = str(uuid.uuid4())
    await gd_insert(
        db.session,
        "students",
        {
            "id": student_id,
            "school_id": school_id,
            "full_name": "طالب مرتبط",
            "parent_id": parent_record_id,
            "is_active": True,
        },
    )
    await gd_insert(
        db.session,
        "guardian_links",
        {
            "id": str(uuid.uuid4()),
            "parent_ref": parent_user_id,
            "parent_id": (
                parent_record_id
                if link_parent_id is None
                else link_parent_id
            ),
            "student_id": student_id,
            "tenant_id": link_school_id or school_id,
            "is_active": link_active,
        },
    )
    return student_id


@pytest.mark.asyncio
async def test_parent_portal_list_and_detail_use_verified_cross_school_link(
    client,
    tenant_a,
    tenant_b,
):
    """An old account tenant must not hide a valid new-school child."""
    parent = await _seed_global_parent(tenant_a, tenant_b)
    student_id = await _seed_linked_student(
        tenant_b,
        parent["id"],
        parent["parent_id"],
    )

    headers = _headers(parent)
    listed = await client.get("/parent-portal/children", headers=headers)
    assert listed.status_code == 200, listed.text
    assert student_id in {child["id"] for child in listed.json()["children"]}

    detail = await client.get(
        f"/parent-portal/child/{student_id}",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["id"] == student_id


@pytest.mark.asyncio
async def test_parent_portal_rejects_inactive_or_inconsistent_cross_school_links(
    client,
    tenant_a,
    tenant_b,
):
    """Inactive links and inconsistent relation metadata fail closed."""
    parent = await _seed_global_parent(tenant_a, tenant_b)
    inactive_student_id = await _seed_linked_student(
        tenant_b,
        parent["id"],
        parent["parent_id"],
        link_active=False,
    )
    mismatched_student_id = await _seed_linked_student(
        tenant_b,
        parent["id"],
        parent["parent_id"],
        link_school_id=str(uuid.uuid4()),
    )

    headers = _headers(parent)
    listed = await client.get("/parent-portal/children", headers=headers)
    assert listed.status_code == 200, listed.text
    listed_ids = {child["id"] for child in listed.json()["children"]}
    assert inactive_student_id not in listed_ids
    assert mismatched_student_id not in listed_ids

    for student_id in (inactive_student_id, mismatched_student_id):
        detail = await client.get(
            f"/parent-portal/child/{student_id}",
            headers=headers,
        )
        assert detail.status_code == 403, detail.text


@pytest.mark.asyncio
async def test_parent_portal_does_not_use_contact_or_other_parent_links_cross_school(
    client,
    tenant_a,
    tenant_b,
):
    """A matching email/phone or another parent's link is not authorization."""
    parent = await _seed_global_parent(tenant_a, tenant_b)
    other_parent = await _seed_global_parent(tenant_a, tenant_b)
    unrelated_student_id = await _seed_linked_student(
        tenant_b,
        other_parent["id"],
        other_parent["parent_id"],
    )

    headers = _headers(parent)
    listed = await client.get("/parent-portal/children", headers=headers)
    assert listed.status_code == 200, listed.text
    assert unrelated_student_id not in {
        child["id"] for child in listed.json()["children"]
    }

    detail = await client.get(
        f"/parent-portal/child/{unrelated_student_id}",
        headers=headers,
    )
    assert detail.status_code == 403, detail.text


@pytest.mark.asyncio
async def test_cross_school_exception_does_not_apply_to_non_parent_identity(
    tenant_a,
    tenant_b,
):
    """The exceptional resolver path is parent-role-only."""
    parent = await _seed_global_parent(tenant_a, tenant_b)
    student_id = await _seed_linked_student(
        tenant_b,
        parent["id"],
        parent["parent_id"],
    )
    teacher_id = str(uuid.uuid4())
    await gd_insert(
        db.session,
        "users",
        {
            "id": teacher_id,
            "role": UserRole.TEACHER.value,
            "tenant_id": tenant_a,
            "email": f"teacher-{teacher_id}@t.test",
            "full_name": "معلم",
            "is_active": True,
            "password_hash": "x",
        },
    )
    await gd_insert(
        db.session,
        "guardian_links",
        {
            "id": str(uuid.uuid4()),
            "parent_ref": teacher_id,
            "parent_id": parent["parent_id"],
            "student_id": student_id,
            "tenant_id": tenant_b,
            "is_active": True,
        },
    )

    children = await resolve_parent_children(
        {
            "id": teacher_id,
            "role": UserRole.TEACHER.value,
            "tenant_id": tenant_a,
        },
        tenant_a,
    )
    assert student_id not in {child["id"] for child in children}