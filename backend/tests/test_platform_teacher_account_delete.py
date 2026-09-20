"""Platform account deletion must use the school-teacher lifecycle."""
import pytest

from dependencies import db
from engines.sql_utils import gd_find_one, gd_update_one
from tests.test_teacher_restore_create_contract import _deleted_teacher


@pytest.mark.asyncio
@pytest.mark.parametrize("previously_deleted", [False, True])
async def test_platform_delete_removes_teacher_and_releases_identity(
    client, tenant_a, platform_admin_headers, previously_deleted,
):
    teacher, user = await _deleted_teacher(tenant_a)
    search_name = user["id"].replace("-", "")
    await gd_update_one(db.session, "users", {"id": user["id"]}, {"full_name": search_name})
    before = await client.get("/users/platform-users", headers=platform_admin_headers,
                              params={"search": search_name})
    assert before.status_code == 200, before.text
    assert {row["id"] for row in before.json()["users"]} == {user["id"]}
    if not previously_deleted:
        await gd_update_one(db.session, "users", {"id": user["id"]}, {"is_active": True})
        await gd_update_one(db.session, "teachers", {"id": teacher["id"]},
                            {"is_active": True, "deleted_at": None})
    response = await client.delete(f"/users/{user['id']}", headers=platform_admin_headers)
    assert response.status_code == 200, response.text
    assert response.json()["permanent"] is True
    assert await gd_find_one(db.session, "users", {"id": user["id"]}) is None
    assert await gd_find_one(db.session, "teachers", {"id": teacher["id"]}) is None
    for status in ("all", "active", "suspended"):
        listing = await client.get("/users/platform-users", headers=platform_admin_headers,
                                   params={"search": search_name, "status": status})
        assert listing.status_code == 200, listing.text
        assert not any(row["id"] == user["id"] for row in listing.json()["users"])
    assert (await client.get(f"/users/{user['id']}", headers=platform_admin_headers)).status_code == 404
    assert (await client.delete(f"/users/{user['id']}", headers=platform_admin_headers)).status_code == 404
    # Creation with a real school context proves both identifiers were released.
    from tests.test_teacher_restore_create_contract import _principal, _headers
    actor = await _principal(tenant_a)
    created = await client.post("/teachers/create", headers=_headers(actor["id"], tenant_a),
                                json={key: teacher[key] for key in
                                      ("full_name", "email", "phone", "national_id")})
    assert created.status_code == 200, created.text
    assert (await gd_find_one(db.session, "users", {"email": user["email"]}))["id"] != user["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["unlinked", "shared", "wrong_profile"])
async def test_platform_delete_ambiguous_teacher_never_suspends(
    client, tenant_a, platform_admin_headers, kind,
):
    teacher, user = await _deleted_teacher(tenant_a)
    patch = {"is_active": True, "deleted_at": None}
    if kind == "unlinked":
        patch["teacher_id"] = None
    elif kind == "shared":
        patch["linked_roles"] = [{"role": "parent", "tenant_id": tenant_a}]
    else:
        other_teacher, other_user = await _deleted_teacher(tenant_a)
        patch["teacher_id"] = other_teacher["id"]
    await gd_update_one(db.session, "users", {"id": user["id"]}, patch)
    response = await client.delete(f"/users/{user['id']}", headers=platform_admin_headers)
    assert response.status_code == 409, response.text
    retained = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert retained["is_active"] is True
    assert not retained.get("deleted_at")
    assert await gd_find_one(db.session, "teachers", {"id": teacher["id"]}) is not None
    if kind == "wrong_profile":
        assert await gd_find_one(db.session, "users", {"id": other_user["id"]}) is not None


@pytest.mark.asyncio
async def test_platform_suspend_remains_reversible(client, tenant_a, platform_admin_headers):
    teacher, user = await _deleted_teacher(tenant_a)
    await gd_update_one(db.session, "users", {"id": user["id"]}, {"is_active": True})
    response = await client.put(f"/users/{user['id']}/status",
                                headers=platform_admin_headers, json={"is_active": False})
    assert response.status_code == 200, response.text
    assert (await gd_find_one(db.session, "users", {"id": user["id"]}))["is_active"] is False
    assert await gd_find_one(db.session, "teachers", {"id": teacher["id"]}) is not None
    restored = await client.put(f"/users/{user['id']}/status",
                                headers=platform_admin_headers, json={"is_active": True})
    assert restored.status_code == 200, restored.text
    assert (await gd_find_one(db.session, "users", {"id": user["id"]}))["is_active"] is True