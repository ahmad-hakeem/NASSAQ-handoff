"""Both teacher creation APIs must enforce the same identity lifecycle."""
import uuid

import pytest

from dependencies import db
from engines.sql_utils import gd_find_one, gd_update_one
from tests.test_teacher_restore_create_contract import _principal, _deleted_teacher, _headers


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/teachers", "/teachers/create"])
async def test_deleted_identity_requires_explicit_restore(client, tenant_a, path):
    actor = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_a)
    email = f"{user['id']}@example.com"
    for collection, row in (("users", user), ("teachers", teacher)):
        await gd_update_one(db.session, collection, {"id": row["id"]}, {"email": email})
        row["email"] = email
    response = await client.post(path, headers=_headers(actor["id"], tenant_a), json={
        "full_name": "Replacement Teacher", "email": user["email"], "phone": user["phone"],
    })
    assert response.status_code == 409, response.text
    assert response.json()["error"]["detail"]["code"] == "TEACHER_RESTORE_AVAILABLE"
    assert response.json()["error"]["detail"]["teacher_id"] == teacher["id"]
    assert (await gd_find_one(db.session, "users", {"id": user["id"]}))["is_active"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/teachers", "/teachers/create"])
@pytest.mark.parametrize("international", [False, True])
async def test_active_phone_cannot_be_reused_with_different_email(client, tenant_a, path, international):
    actor = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_a)
    await gd_update_one(db.session, "users", {"id": user["id"]}, {"is_active": True})
    await gd_update_one(db.session, "teachers", {"id": teacher["id"]},
                        {"is_active": True, "deleted_at": None})
    email = f"{uuid.uuid4()}@example.com"
    response = await client.post(path, headers=_headers(actor["id"], tenant_a), json={
        "full_name": "Different Teacher", "email": email,
        "phone": "+966 " + user["phone"][1:] if international else user["phone"],
    })
    assert response.status_code in (400, 409), response.text
    assert await gd_find_one(db.session, "users", {"email": email}) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("with_phone", [False, True])
async def test_legacy_create_delete_readd(client, tenant_a, with_phone):
    actor = await _principal(tenant_a)
    email = f"{uuid.uuid4()}@example.com"
    payload = {
        "full_name": "Teacher Without Phone", "email": email,
    }
    if with_phone:
        payload["phone"] = f"05{uuid.uuid4().int % 100_000_000:08d}"
    headers = _headers(actor["id"], tenant_a)
    response = await client.post("/teachers", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    teacher_id = response.json()["id"]
    assert response.json()["phone"] == payload.get("phone")
    user = await gd_find_one(db.session, "users", {"email": email})
    assert user["teacher_id"] == teacher_id
    deleted = await client.delete(f"/teachers/{teacher_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["permanent"] is True
    recreated = await client.post("/teachers", headers=headers, json=payload)
    assert recreated.status_code == 200, recreated.text
    assert recreated.json()["id"] != teacher_id
    assert (await gd_find_one(db.session, "users", {"email": email}))["id"] != user["id"]