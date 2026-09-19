"""HTTP contract regression tests for create-after-soft-delete."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import jwt

from server import app
from dependencies import (
    JWT_ALGORITHM, JWT_SECRET, UserRole, create_access_token, db,
)
from engines.sql_utils import gd_find_one, gd_insert, gd_update_one
from src.modules.academics.controllers import academics_teacher_routes


def _headers(user_id: str, school_id: str) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _principal(school_id: str) -> dict:
    row = {
        "id": str(uuid.uuid4()),
        "email": f"principal-{uuid.uuid4()}@test.invalid",
        "full_name": "Principal",
        "password_hash": "x",
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "is_active": True,
    }
    await gd_insert(db.session, "users", row)
    return row


async def _deleted_teacher(school_id: str) -> tuple[dict, dict]:
    teacher_id, user_id = str(uuid.uuid4()), str(uuid.uuid4())
    email, phone, national_id = f"{user_id}@test.invalid", "0501234567", "1012345678"
    user = {
        "id": user_id,
        "email": email,
        "phone": phone,
        "full_name": "Retained Teacher",
        "password_hash": "retained-password-hash",
        "role": UserRole.TEACHER.value,
        "tenant_id": school_id,
        "teacher_id": teacher_id,
        "is_active": False,
        "mfa_required": True,
    }
    teacher = {
        "id": teacher_id,
        "user_id": user_id,
        "school_id": school_id,
        "email": email,
        "phone": phone,
        "national_id": national_id,
        "full_name": "Retained Teacher",
        "is_active": False,
        "deleted_at": "2025-01-01T00:00:00+00:00",
    }
    await gd_insert(db.session, "users", user)
    await gd_insert(db.session, "teachers", teacher)
    return teacher, user


async def _subject(school_id: str) -> str:
    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id,
        "school_id": school_id,
        "name": f"Subject-{subject_id[:6]}",
        "is_active": True,
    })
    return subject_id


def test_api_teacher_create_route_resolves_to_verified_handler():
    matches = [
        route for route in app.routes
        if getattr(route, "path", None) == "/api/teachers/create"
        and "POST" in getattr(route, "methods", set())
    ]
    assert matches
    assert matches[0].endpoint.__module__.endswith("academics_teacher_routes")
    assert matches[0].endpoint.__name__ == "create_teacher_wizard"


@pytest.mark.asyncio
async def test_delete_create_collision_then_explicit_restore_preserves_account(client, tenant_a):
    principal = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_a)
    await gd_update_one(db.session, "teachers", {"id": teacher["id"]}, {
        "is_active": True, "deleted_at": None,
    })
    await gd_update_one(db.session, "users", {"id": user["id"]}, {"is_active": True})
    deleted = await client.delete(
        f"/teachers/{teacher['id']}", headers=_headers(principal["id"], tenant_a)
    )
    assert deleted.status_code == 200, deleted.text

    payload = {
        "full_name": "Silently Changed Name",
        "email": user["email"].upper(),
        "phone": "+966 50 123 4567",
        "national_id": teacher["national_id"],
    }

    collision = await client.post(
        "/teachers/create", json=payload, headers=_headers(principal["id"], tenant_a)
    )
    assert collision.status_code == 409, collision.text
    assert collision.json()["error"]["detail"] == {
        "code": "TEACHER_RESTORE_AVAILABLE",
        "message": "هذا المعلم محذوف سابقاً. أكّد استعادة حسابه الحالي بدلاً من إنشاء حساب جديد.",
        "teacher_id": teacher["id"],
    }
    unchanged = await gd_find_one(db.session, "teachers", {"id": teacher["id"]})
    assert unchanged["full_name"] == "Retained Teacher"
    assert unchanged["is_active"] is False

    restored = await client.post(
        f"/teachers/{teacher['id']}/restore",
        headers=_headers(principal["id"], tenant_a),
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["restored_existing"] is True
    retained_user = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert retained_user["password_hash"] == "retained-password-hash"
    assert retained_user["mfa_required"] is True


@pytest.mark.asyncio
async def test_foreign_soft_deleted_collision_stays_generic(client, tenant_a, tenant_b):
    principal = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_b)
    response = await client.post("/teachers/create", json={
        "full_name": "Takeover",
        "email": user["email"],
        "phone": user["phone"],
        "national_id": teacher["national_id"],
    }, headers=_headers(principal["id"], tenant_a))
    assert response.status_code == 400
    assert not isinstance(response.json().get("error", {}).get("detail"), dict)
    row = await gd_find_one(db.session, "teachers", {"id": teacher["id"]})
    assert row["is_active"] is False


@pytest.mark.asyncio
async def test_active_duplicate_and_deleted_identity_mismatch_have_no_restore_hint(client, tenant_a):
    principal = await _principal(tenant_a)
    active_teacher, active_user = await _deleted_teacher(tenant_a)
    await gd_update_one(db.session, "teachers", {"id": active_teacher["id"]}, {
        "is_active": True, "deleted_at": None,
    })
    await gd_update_one(db.session, "users", {"id": active_user["id"]}, {"is_active": True})

    active = await client.post("/teachers/create", json={
        "full_name": "Duplicate",
        "email": active_user["email"],
        "phone": active_user["phone"],
        "national_id": active_teacher["national_id"],
    }, headers=_headers(principal["id"], tenant_a))
    assert active.status_code == 400
    assert active.json()["error"]["code"] != "TEACHER_RESTORE_AVAILABLE"

    # Free the fixture's deliberately stable identity values before inserting
    # a second same-school teacher (the real schema enforces national-id scope).
    await gd_update_one(db.session, "teachers", {"id": active_teacher["id"]}, {
        "national_id": "1099999999", "phone": "0500000001",
    })
    await gd_update_one(db.session, "users", {"id": active_user["id"]}, {
        "phone": "0500000001",
    })
    deleted_teacher, deleted_user = await _deleted_teacher(tenant_a)
    mismatch = await client.post("/teachers/create", json={
        "full_name": "Mismatch",
        "email": deleted_user["email"],
        "phone": "0559999999",
        "national_id": deleted_teacher["national_id"],
    }, headers=_headers(principal["id"], tenant_a))
    assert mismatch.status_code == 400
    assert mismatch.json()["error"]["code"] != "TEACHER_RESTORE_AVAILABLE"


@pytest.mark.asyncio
async def test_delete_audit_failure_rolls_back_all_lifecycle_writes(
    client, tenant_a, monkeypatch,
):
    principal = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_a)
    await gd_update_one(db.session, "teachers", {"id": teacher["id"]}, {
        "is_active": True, "deleted_at": None,
    })
    await gd_update_one(db.session, "users", {"id": user["id"]}, {
        "is_active": True, "mfa_required": False,
    })
    assignment_id = str(uuid.uuid4())
    await gd_insert(db.session, "teacher_assignments", {
        "id": assignment_id,
        "school_id": tenant_a,
        "teacher_id": teacher["id"],
        "subject_id": await _subject(tenant_a),
        "is_active": True,
    })
    session_id, jti = str(uuid.uuid4()), str(uuid.uuid4())
    await gd_insert(db.session, "user_sessions", {
        "id": session_id,
        "user_id": user["id"],
        "jti": jti,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "revoked_at": None,
    })

    real_insert = academics_teacher_routes.gd_insert

    async def fail_audit(session, collection, document):
        if collection == "audit_logs":
            raise RuntimeError("injected audit failure")
        return await real_insert(session, collection, document)

    monkeypatch.setattr(academics_teacher_routes, "gd_insert", fail_audit)
    response = await client.delete(
        f"/teachers/{teacher['id']}", headers=_headers(principal["id"], tenant_a)
    )
    assert response.status_code == 500
    assert (await gd_find_one(db.session, "teachers", {"id": teacher["id"]}))["is_active"] is True
    assert (await gd_find_one(db.session, "users", {"id": user["id"]}))["is_active"] is True
    assert (await gd_find_one(
        db.session, "teacher_assignments", {"id": assignment_id}
    ))["is_active"] is True
    assert (await gd_find_one(db.session, "user_sessions", {"id": session_id}))["revoked_at"] is None
    assert await gd_find_one(db.session, "revoked_tokens", {"jti": jti}) is None


@pytest.mark.asyncio
async def test_restore_audit_failure_rolls_back_teacher_and_user(
    client, tenant_a, monkeypatch,
):
    principal = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_a)
    assignment_id = str(uuid.uuid4())
    await gd_insert(db.session, "teacher_assignments", {
        "id": assignment_id,
        "school_id": tenant_a,
        "teacher_id": teacher["id"],
        "subject_id": await _subject(tenant_a),
        "is_active": False,
    })
    session_id = str(uuid.uuid4())
    await gd_insert(db.session, "user_sessions", {
        "id": session_id,
        "user_id": user["id"],
        "jti": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
        "revoked_at": datetime.now(timezone.utc).isoformat(),
    })
    real_insert = academics_teacher_routes.gd_insert

    async def fail_audit(session, collection, document):
        if collection == "audit_logs":
            raise RuntimeError("injected audit failure")
        return await real_insert(session, collection, document)

    monkeypatch.setattr(academics_teacher_routes, "gd_insert", fail_audit)
    response = await client.post(
        f"/teachers/{teacher['id']}/restore",
        headers=_headers(principal["id"], tenant_a),
    )
    assert response.status_code == 500
    assert (await gd_find_one(db.session, "teachers", {"id": teacher["id"]}))["is_active"] is False
    assert (await gd_find_one(db.session, "users", {"id": user["id"]}))["is_active"] is False
    assert (await gd_find_one(
        db.session, "teacher_assignments", {"id": assignment_id}
    ))["is_active"] is False
    assert (await gd_find_one(db.session, "user_sessions", {"id": session_id}))["revoked_at"] is not None


@pytest.mark.asyncio
async def test_deleted_teacher_access_token_stays_revoked_after_restore(client, tenant_a):
    principal = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_a)
    await gd_update_one(db.session, "teachers", {"id": teacher["id"]}, {
        "is_active": True, "deleted_at": None,
    })
    await gd_update_one(db.session, "users", {"id": user["id"]}, {
        "is_active": True, "mfa_required": False,
    })
    token = create_access_token({
        "sub": user["id"], "role": UserRole.TEACHER.value, "tenant_id": tenant_a,
    })
    claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    await gd_insert(db.session, "user_sessions", {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "jti": claims["jti"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": datetime.fromtimestamp(claims["exp"], timezone.utc).isoformat(),
        "revoked_at": None,
    })
    teacher_headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/teachers/options/nationalities", headers=teacher_headers)).status_code == 200

    deleted = await client.delete(
        f"/teachers/{teacher['id']}", headers=_headers(principal["id"], tenant_a)
    )
    assert deleted.status_code == 200, deleted.text
    assert (await client.get(
        "/teachers/options/nationalities", headers=teacher_headers
    )).status_code == 401

    restored = await client.post(
        f"/teachers/{teacher['id']}/restore",
        headers=_headers(principal["id"], tenant_a),
    )
    assert restored.status_code == 200, restored.text
    after_restore = await client.get(
        "/teachers/options/nationalities", headers=teacher_headers
    )
    assert after_restore.status_code == 401
    assert after_restore.json()["error"]["message"] == "Token has been revoked"