"""Platform account deletion must use the school-teacher lifecycle."""
import logging

import pytest

from dependencies import db
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one
from src.core.middleware.rbac import ROLE_PERMISSIONS
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
@pytest.mark.parametrize("kind", ["shared", "wrong_profile", "custom_permissions"])
async def test_platform_delete_ambiguous_teacher_never_suspends(
    client, tenant_a, platform_admin_headers, kind, caplog,
):
    teacher, user = await _deleted_teacher(tenant_a)
    patch = {"is_active": True, "deleted_at": None}
    if kind == "shared":
        patch["linked_roles"] = [{"role": "parent", "tenant_id": tenant_a}]
    elif kind == "wrong_profile":
        other_teacher, other_user = await _deleted_teacher(tenant_a)
        patch["teacher_id"] = other_teacher["id"]
    else:
        patch["permissions"] = [*ROLE_PERMISSIONS["teacher"], "users.delete"]
    await gd_update_one(db.session, "users", {"id": user["id"]}, patch)
    with caplog.at_level(logging.WARNING, logger="services.teacher_permanent_deletion"):
        response = await client.delete(f"/users/{user['id']}", headers=platform_admin_headers)
    assert response.status_code == 409, response.text
    blocker_logs = [
        record.getMessage() for record in caplog.records
        if record.name == "services.teacher_permanent_deletion"
    ]
    assert blocker_logs
    assert "reason=" in blocker_logs[-1]
    assert "table=" in blocker_logs[-1]
    assert "count=" in blocker_logs[-1]
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


@pytest.mark.asyncio
async def test_actual_platform_create_then_immediate_delete(client, tenant_a, platform_admin_headers):
    """Exercise the real Platform Admin create payload, including role defaults."""
    import uuid

    email = f"platform-created-{uuid.uuid4().hex}@example.com"
    payload = {
        "email": email,
        "phone": str(uuid.uuid4().int)[:11],
        "password": "Str0ng!Passw0rd",
        "full_name": "معلم دورة حياة",
        "role": "teacher",
        "tenant_id": tenant_a,
        "permissions": ROLE_PERMISSIONS["teacher"],
    }
    created = await client.post("/users/create", headers=platform_admin_headers, json=payload)
    assert created.status_code == 200, created.text
    user_id = created.json()["id"]
    user = await gd_find_one(db.session, "users", {"id": user_id})
    profiles = await gd_find(db.session, "teachers", {"user_id": user_id})
    assert len(profiles) == 1
    assert user["teacher_id"] == profiles[0]["id"]

    deleted = await client.delete(f"/users/{user_id}", headers=platform_admin_headers)
    assert deleted.status_code == 200, deleted.text
    assert await gd_find_one(db.session, "users", {"id": user_id}) is None
    assert await gd_find_one(db.session, "teachers", {"id": profiles[0]["id"]}) is None
    recreated = await client.post("/users/create", headers=platform_admin_headers, json=payload)
    assert recreated.status_code == 200, recreated.text
    assert recreated.json()["id"] != user_id


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_side", ["user", "profile"])
async def test_platform_delete_resolves_unique_legacy_one_sided_link(
    client, tenant_a, platform_admin_headers, missing_side,
):
    teacher, user = await _deleted_teacher(tenant_a)
    await gd_update_one(db.session, "users", {"id": user["id"]}, {
        "is_active": True,
        **({"teacher_id": None} if missing_side == "user" else {}),
    })
    await gd_update_one(db.session, "teachers", {"id": teacher["id"]}, {
        "is_active": True,
        "deleted_at": None,
        **({"user_id": None} if missing_side == "profile" else {}),
    })

    response = await client.delete(f"/users/{user['id']}", headers=platform_admin_headers)
    assert response.status_code == 200, response.text
    assert await gd_find_one(db.session, "users", {"id": user["id"]}) is None
    assert await gd_find_one(db.session, "teachers", {"id": teacher["id"]}) is None


@pytest.mark.asyncio
async def test_platform_delete_missing_profile_stays_review_required(
    client, tenant_a, platform_admin_headers,
):
    import uuid

    user_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": user_id,
        "email": f"{user_id}@example.com",
        "password_hash": "x",
        "full_name": "Legacy profile-less teacher",
        "role": "teacher",
        "tenant_id": tenant_a,
        "is_active": True,
    })
    response = await client.delete(f"/users/{user_id}", headers=platform_admin_headers)
    assert response.status_code == 409, response.text
    assert await gd_find_one(db.session, "users", {"id": user_id}) is not None


@pytest.mark.asyncio
async def test_platform_delete_ambiguous_legacy_profiles_stay_blocked(
    client, tenant_a, platform_admin_headers,
):
    import uuid

    teacher, user = await _deleted_teacher(tenant_a)
    await gd_update_one(db.session, "users", {"id": user["id"]}, {
        "teacher_id": None, "is_active": True,
    })
    await gd_update_one(db.session, "teachers", {"id": teacher["id"]}, {
        "is_active": True, "deleted_at": None,
    })
    second_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": second_id,
        "teacher_id": second_id,
        "user_id": user["id"],
        "full_name": "Ambiguous legacy profile",
        "school_id": tenant_a,
        "is_active": True,
    })

    response = await client.delete(f"/users/{user['id']}", headers=platform_admin_headers)
    assert response.status_code == 409, response.text
    assert await gd_find_one(db.session, "users", {"id": user["id"]}) is not None
    assert await gd_find_one(db.session, "teachers", {"id": teacher["id"]}) is not None
    assert await gd_find_one(db.session, "teachers", {"id": second_id}) is not None