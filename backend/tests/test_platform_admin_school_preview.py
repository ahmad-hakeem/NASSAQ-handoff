"""Platform-admin principal preview eligibility and schools list metadata."""
from __future__ import annotations

import time
import uuid

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert
from utils.platform_admin_preview import (
    MSG_ARCHIVED,
    MSG_INDEPENDENT_TEACHER_WORKSPACE,
    REASON_ARCHIVED,
    REASON_INDEPENDENT_TEACHER_WORKSPACE,
    assess_principal_preview_eligibility,
    is_independent_teacher_workspace,
)


async def _mk_platform_admin() -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": None,
        "email": f"pa-{uid}@t.test",
        "full_name": "Platform Admin",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


async def _mk_school(*, school_id: str | None = None, status: str = "active", school_type: str | None = None) -> str:
    sid = school_id or str(uuid.uuid4())
    row = {
        "id": sid,
        "name": f"School {sid[:6]}",
        "code": f"S{sid[:8]}",
        "status": status,
        "country": "SA",
        "language": "ar",
    }
    if school_type:
        row["school_type"] = school_type
    await gd_insert(db.session, "schools", row)
    return sid


async def _seed_principal(school_id: str) -> None:
    uid = str(uuid.uuid4())
    await gd_insert(
        db.session,
        "users",
        {
            "id": uid,
            "role": UserRole.SCHOOL_PRINCIPAL.value,
            "tenant_id": school_id,
            "email": f"p-{uid}@t.test",
            "full_name": "Principal",
            "is_active": True,
            "password_hash": "x",
        },
    )


def _admin_headers(user: dict, *, fresh_mfa: bool = False) -> dict:
    data = {
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": user.get("tenant_id"),
    }
    if fresh_mfa:
        data["mfa_recent_at"] = int(time.time())
    token = create_access_token(data)
    return {"Authorization": f"Bearer {token}"}


def test_is_independent_teacher_workspace_by_id_prefix():
    assert is_independent_teacher_workspace({"id": "itw_abc", "status": "active"})
    assert not is_independent_teacher_workspace({"id": str(uuid.uuid4()), "status": "active"})


def test_is_independent_teacher_workspace_by_school_type():
    assert is_independent_teacher_workspace(
        {"id": str(uuid.uuid4()), "school_type": "independent_teacher_workspace", "status": "active"}
    )


def test_assess_archived_standard_school():
    meta = assess_principal_preview_eligibility({"id": str(uuid.uuid4()), "status": "archived"})
    assert meta["can_preview_as_principal"] is False
    assert meta["preview_block_reason"] == REASON_ARCHIVED
    assert meta["preview_block_message_ar"] == MSG_ARCHIVED


def test_assess_it_workspace_archived_name_like_real_school():
    """Regression: archived IT row named like a school must not be previewable."""
    meta = assess_principal_preview_eligibility(
        {"id": f"itw_{uuid.uuid4()}", "name": "الملك فيصل", "status": "archived"},
    )
    assert meta["can_preview_as_principal"] is False
    assert meta["preview_block_reason"] == REASON_INDEPENDENT_TEACHER_WORKSPACE
    assert meta["preview_block_message_ar"] == MSG_INDEPENDENT_TEACHER_WORKSPACE


@pytest.mark.asyncio
async def test_get_schools_includes_preview_metadata(client):
    admin = await _mk_platform_admin()
    headers = _admin_headers(admin)

    real_id = await _mk_school(status="active")
    await _seed_principal(real_id)
    itw_id = await _mk_school(school_id=f"itw_{uuid.uuid4()}", status="archived")
    archived_id = await _mk_school(status="archived")

    res = await client.get("/schools", headers=headers)
    assert res.status_code == 200, res.text

    by_id = {row["id"]: row for row in res.json()}

    assert by_id[real_id]["can_preview_as_principal"] is True
    assert by_id[real_id]["entity_kind"] == "standard_school"

    assert by_id[itw_id]["can_preview_as_principal"] is False
    assert by_id[itw_id]["entity_kind"] == "independent_teacher_workspace"
    assert by_id[itw_id]["preview_block_reason"] == REASON_INDEPENDENT_TEACHER_WORKSPACE

    assert by_id[archived_id]["can_preview_as_principal"] is False
    assert by_id[archived_id]["preview_block_reason"] == REASON_ARCHIVED


@pytest.mark.asyncio
async def test_role_switch_archived_returns_clear_message(client, monkeypatch):
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")
    admin = await _mk_platform_admin()
    headers = _admin_headers(admin, fresh_mfa=True)

    archived_id = await _mk_school(status="archived")

    res = await client.post(
        "/role-switch/switch",
        json={
            "target_role": "school_principal",
            "school_id": archived_id,
            "reason": "QA archived school message",
        },
        headers=headers,
    )
    assert res.status_code == 403
    assert MSG_ARCHIVED in res.text


@pytest.mark.asyncio
async def test_role_switch_itw_returns_it_workspace_message(client, monkeypatch):
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "1")
    admin = await _mk_platform_admin()
    headers = _admin_headers(admin, fresh_mfa=True)

    itw_id = await _mk_school(school_id=f"itw_{uuid.uuid4()}", status="active")

    res = await client.post(
        "/role-switch/switch",
        json={
            "target_role": "school_principal",
            "school_id": itw_id,
            "reason": "QA IT workspace guard",
        },
        headers=headers,
    )
    assert res.status_code == 403
    assert MSG_INDEPENDENT_TEACHER_WORKSPACE in res.text
