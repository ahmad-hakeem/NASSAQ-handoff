"""Task #520 — grade-levels round-trip smoke test.

Regression: `GET /api/grade-levels` used to 500 with a Pydantic
ValidationError immediately after a row was created via
`POST /api/grade-levels`, because the response model required `name` and
`created_at` fields that do not exist on the `grade_levels` ORM/table.

Task #579 — None-tenant guard test added below.
"""
import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from server import app
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert
from tests.conftest import _mk_user, _headers


@pytest.mark.asyncio
async def test_create_then_list_grade_levels_round_trip():
    tenant = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": tenant,
        "name": f"School-{tenant[:6]}",
        "code": f"S{tenant[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant)
    headers = _headers(principal)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create = await ac.post(
            "/api/grade-levels",
            headers=headers,
            json={
                "name": "الصف الأول",
                "name_en": "Grade 1",
                "order": 1,
                "is_active": True,
                "school_id": tenant,
            },
        )
        assert create.status_code == 200, create.text
        created = create.json()
        assert created["id"]
        assert created["name"] == "الصف الأول"
        assert created["name_ar"] == "الصف الأول"
        assert created["name_en"] == "Grade 1"
        assert created["school_id"] == tenant

        listed = await ac.get("/api/grade-levels", headers=headers)
        assert listed.status_code == 200, listed.text
        rows = listed.json()
        match = next((r for r in rows if r["id"] == created["id"]), None)
        assert match is not None, rows
        assert match["name"] == "الصف الأول"
        assert match["name_ar"] == "الصف الأول"

        single = await ac.get(f"/api/grade-levels/{created['id']}", headers=headers)
        assert single.status_code == 200, single.text
        assert single.json()["name"] == "الصف الأول"


@pytest.mark.asyncio
async def test_get_grade_levels_none_tenant_returns_empty_list():
    """Task #579: a caller whose JWT carries no tenant_id (and is not an
    independent teacher) must receive 200 [] instead of crashing with 500."""
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.TEACHER.value,
        "email": f"{uid}@notenant.test",
        "full_name": "No Tenant Teacher",
        "is_active": True,
        "password_hash": "x",
    })
    token = create_access_token({
        "sub": uid,
        "role": UserRole.TEACHER.value,
    })
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/grade-levels", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
