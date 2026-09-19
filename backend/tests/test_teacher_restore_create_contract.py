"""HTTP contract regression tests for create-after-soft-delete."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import jwt
from fastapi import HTTPException
from sqlalchemy import text

from server import app
from dependencies import (
    JWT_ALGORITHM, JWT_SECRET, UserRole, create_access_token, db,
)
from engines.sql_utils import gd_find_one, gd_insert, gd_update_one
from src.modules.academics.controllers import academics_teacher_routes
from src.modules.teacher_management.controllers.principal_management_routes import (
    UpdateCredentialsRequest,
    update_teacher_credentials,
)
from src.modules.users.controllers.user_routes_mod import (
    UserStatusRequest,
    update_user_status,
)
from src.core.database.db import async_session_factory


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
    suffix = f"{int(uuid.UUID(user_id)) % 100_000_000:08d}"
    email = f"{user_id}@test.invalid"
    phone = f"05{suffix}"
    national_id = f"1{int(uuid.UUID(teacher_id)) % 1_000_000_000:09d}"
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
        "phone": f"+966 {teacher['phone'][1:]}",
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
async def test_foreign_soft_deleted_collision_is_blocked_without_owner_details(client, tenant_a, tenant_b):
    principal = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_b)
    response = await client.post("/teachers/create", json={
        "full_name": "Takeover",
        "email": user["email"],
        "phone": user["phone"],
        "national_id": teacher["national_id"],
    }, headers=_headers(principal["id"], tenant_a))
    assert response.status_code == 409
    detail = response.json()["error"]["detail"]
    assert detail["code"] == "TEACHER_MOBILE_CONFLICT"
    assert "teacher_id" not in detail
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
    assert active.status_code == 409
    assert active.json()["error"]["detail"]["code"] == "TEACHER_ACTIVE_DUPLICATE"

    deleted_teacher, deleted_user = await _deleted_teacher(tenant_a)
    mismatch_phone = (
        "05"
        + f"{(int(deleted_teacher['phone'][2:]) + 7) % 100_000_000:08d}"
    )
    mismatch = await client.post("/teachers/create", json={
        "full_name": "Mismatch",
        "email": deleted_user["email"],
        "phone": mismatch_phone,
        "national_id": deleted_teacher["national_id"],
    }, headers=_headers(principal["id"], tenant_a))
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["detail"]["code"] == "TEACHER_NATIONAL_ID_CONFLICT"


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


@pytest.mark.asyncio
async def test_legacy_null_user_phone_is_still_a_verified_restore_candidate(client, tenant_a):
    """The teacher profile owns mobile; a missing duplicate on users is not a conflict."""
    principal = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_a)
    await gd_update_one(db.session, "users", {"id": user["id"]}, {"phone": None})

    response = await client.post("/teachers/create", json={
        "full_name": "Must not overwrite retained profile",
        "email": user["email"],
        "phone": teacher["phone"],
        "national_id": teacher["national_id"],
    }, headers=_headers(principal["id"], tenant_a))

    assert response.status_code == 409, response.text
    assert response.json()["error"]["detail"]["code"] == "TEACHER_RESTORE_AVAILABLE"
    assert response.json()["error"]["detail"]["teacher_id"] == teacher["id"]

    restored = await client.post(
        f"/teachers/{teacher['id']}/restore",
        headers=_headers(principal["id"], tenant_a),
    )
    assert restored.status_code == 200, restored.text
    healed_user = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert healed_user["phone"] == teacher["phone"]
    assert healed_user["password_hash"] == user["password_hash"]


@pytest.mark.asyncio
async def test_nonempty_user_phone_conflict_is_structured_and_not_restorable(client, tenant_a):
    principal = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_a)
    conflict_phone = "05" + f"{(int(teacher['phone'][2:]) + 1) % 100_000_000:08d}"
    await gd_update_one(db.session, "users", {"id": user["id"]}, {"phone": conflict_phone})

    response = await client.post("/teachers/create", json={
        "full_name": "Conflict",
        "email": user["email"],
        "phone": teacher["phone"],
        "national_id": teacher["national_id"],
    }, headers=_headers(principal["id"], tenant_a))

    assert response.status_code == 409, response.text
    detail = response.json()["error"]["detail"]
    assert detail["code"] == "TEACHER_MOBILE_CONFLICT"
    assert "teacher_id" not in detail


@pytest.mark.asyncio
async def test_single_missing_reciprocal_link_can_be_repaired_only_by_explicit_restore(
    client, tenant_a,
):
    principal = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_a)
    await gd_update_one(db.session, "users", {"id": user["id"]}, {"teacher_id": None})

    create = await client.post("/teachers/create", json={
        "full_name": "No wizard overwrite",
        "email": user["email"],
        "phone": teacher["phone"],
        "national_id": teacher["national_id"],
    }, headers=_headers(principal["id"], tenant_a))
    assert create.status_code == 409, create.text
    assert create.json()["error"]["detail"]["code"] == "TEACHER_RESTORE_AVAILABLE"

    restore = await client.post(
        f"/teachers/{teacher['id']}/restore",
        headers=_headers(principal["id"], tenant_a),
    )
    assert restore.status_code == 200, restore.text
    repaired = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert repaired["teacher_id"] == teacher["id"]
    retained = await gd_find_one(db.session, "teachers", {"id": teacher["id"]})
    assert retained["full_name"] == teacher["full_name"]


@pytest.mark.asyncio
async def test_reverse_missing_reciprocal_link_is_repaired_by_explicit_restore(
    client, tenant_a,
):
    principal = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_a)
    await gd_update_one(db.session, "teachers", {"id": teacher["id"]}, {"user_id": None})

    create = await client.post("/teachers/create", json={
        "full_name": "Retained",
        "email": user["email"],
        "phone": teacher["phone"],
        "national_id": teacher["national_id"],
    }, headers=_headers(principal["id"], tenant_a))
    assert create.status_code == 409, create.text
    assert create.json()["error"]["detail"]["code"] == "TEACHER_RESTORE_AVAILABLE"

    restore = await client.post(
        f"/teachers/{teacher['id']}/restore",
        headers=_headers(principal["id"], tenant_a),
    )
    assert restore.status_code == 200, restore.text
    assert (await gd_find_one(
        db.session, "teachers", {"id": teacher["id"]}
    ))["user_id"] == user["id"]


@pytest.mark.asyncio
async def test_shared_user_referenced_by_another_teacher_fails_closed(client, tenant_a):
    principal = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_a)
    other_teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": other_teacher_id,
        "school_id": tenant_a,
        "user_id": user["id"],
        "full_name": "Conflicting Link",
        "email": f"{other_teacher_id}@test.invalid",
        "phone": f"05{int(uuid.UUID(other_teacher_id)) % 100_000_000:08d}",
        "national_id": f"1{int(uuid.UUID(other_teacher_id)) % 1_000_000_000:09d}",
        "is_active": False,
        "deleted_at": "2025-01-01T00:00:00+00:00",
    })

    response = await client.post("/teachers/create", json={
        "full_name": "Ambiguous",
        "email": user["email"],
        "phone": teacher["phone"],
        "national_id": teacher["national_id"],
    }, headers=_headers(principal["id"], tenant_a))
    assert response.status_code == 409, response.text
    assert response.json()["error"]["detail"]["code"] == "TEACHER_ACCOUNT_REVIEW_REQUIRED"

    restore = await client.post(
        f"/teachers/{teacher['id']}/restore",
        headers=_headers(principal["id"], tenant_a),
    )
    assert restore.status_code == 409
    assert (await gd_find_one(
        db.session, "teachers", {"id": teacher["id"]}
    ))["is_active"] is False


@pytest.mark.asyncio
async def test_direct_restore_rechecks_new_global_contact_collision(client, tenant_a, tenant_b):
    principal = await _principal(tenant_a)
    teacher, _ = await _deleted_teacher(tenant_a)
    foreign_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": foreign_id,
        "email": f"{foreign_id}@test.invalid",
        "phone": teacher["phone"],
        "full_name": "Foreign Collision",
        "password_hash": "x",
        "role": UserRole.TEACHER.value,
        "tenant_id": tenant_b,
        "is_active": True,
    })

    restore = await client.post(
        f"/teachers/{teacher['id']}/restore",
        headers=_headers(principal["id"], tenant_a),
    )
    assert restore.status_code == 409, restore.text
    detail = restore.json()["error"]["detail"]
    assert detail["code"] == "TEACHER_MOBILE_CONFLICT"
    assert "teacher_id" not in detail
    assert (await gd_find_one(
        db.session, "teachers", {"id": teacher["id"]}
    ))["is_active"] is False


@pytest.mark.asyncio
async def test_actual_user_status_suspension_survives_teacher_delete_restore(
    client, tenant_a,
):
    principal = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_a)
    await gd_update_one(db.session, "teachers", {"id": teacher["id"]}, {
        "is_active": True, "deleted_at": None,
    })
    await gd_update_one(db.session, "users", {"id": user["id"]}, {
        "is_active": True, "status": "active",
    })

    await update_user_status(
        user["id"],
        UserStatusRequest(is_active=False),
        principal,
    )
    suspended = await gd_find_one(db.session, "users", {"id": user["id"]})
    assert suspended["is_active"] is False
    assert suspended["status"] == "suspended"

    deleted = await client.delete(
        f"/teachers/{teacher['id']}",
        headers=_headers(principal["id"], tenant_a),
    )
    assert deleted.status_code == 200, deleted.text
    deletion_audit = await gd_find_one(db.session, "audit_logs", {
        "entity_type": "teacher",
        "entity_id": teacher["id"],
        "action": "delete",
    })
    assert deletion_audit["previous_state"]["user_was_active"] is False
    restore = await client.post(
        f"/teachers/{teacher['id']}/restore",
        headers=_headers(principal["id"], tenant_a),
    )
    assert restore.status_code == 409, restore.text
    assert restore.json()["error"]["detail"]["code"] == "TEACHER_ACCOUNT_REVIEW_REQUIRED"
    assert (await gd_find_one(
        db.session, "users", {"id": user["id"]}
    ))["is_active"] is False


@pytest.mark.asyncio
async def test_user_only_normalized_email_and_phone_collisions_are_blocked(client, tenant_a):
    principal = await _principal(tenant_a)
    marker = uuid.uuid4()
    email = f"orphan-{marker}@test.invalid"
    phone = f"05{int(marker) % 100_000_000:08d}"
    await gd_insert(db.session, "users", {
        "id": str(uuid.uuid4()),
        "email": email.upper(),
        "phone": f"+966 {phone[1:]}",
        "full_name": "Orphan Identity",
        "password_hash": "x",
        "role": UserRole.TEACHER.value,
        "tenant_id": tenant_a,
        "is_active": False,
    })

    by_email = await client.post("/teachers/create", json={
        "full_name": "No takeover",
        "email": email,
        "phone": f"05{(int(phone[2:]) + 3) % 100_000_000:08d}",
    }, headers=_headers(principal["id"], tenant_a))
    assert by_email.status_code == 409, by_email.text
    assert by_email.json()["error"]["detail"]["code"] == "TEACHER_ACCOUNT_REVIEW_REQUIRED"

    by_phone = await client.post("/teachers/create", json={
        "full_name": "No phone relink",
        "email": f"different-{marker}@test.invalid",
        "phone": phone,
    }, headers=_headers(principal["id"], tenant_a))
    assert by_phone.status_code == 409, by_phone.text
    assert by_phone.json()["error"]["detail"]["code"] == "TEACHER_MOBILE_CONFLICT"


@pytest.mark.asyncio
@pytest.mark.parametrize(("email", "phone"), [
    ("   ", "0501234567"),
    ("not-an-email", "0501234567"),
    ("valid@test.invalid", "abc"),
    ("valid@test.invalid", "   "),
])
async def test_invalid_normalized_identity_is_structured_400(
    client, tenant_a, email, phone,
):
    principal = await _principal(tenant_a)
    response = await client.post("/teachers/create", json={
        "full_name": "Invalid",
        "email": email,
        "phone": phone,
    }, headers=_headers(principal["id"], tenant_a))
    assert response.status_code == 400, response.text
    assert response.json()["error"]["detail"]["code"] == "TEACHER_IDENTITY_INVALID"


@pytest.mark.asyncio
async def test_profile_only_restore_is_explicit_but_linked_missing_identity_requires_review(
    client, tenant_a,
):
    principal = await _principal(tenant_a)
    profile_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": profile_id,
        "school_id": tenant_a,
        "full_name": "Profile Only",
        "email": None,
        "phone": None,
        "is_active": False,
        "deleted_at": "2025-01-01T00:00:00+00:00",
    })
    profile_restore = await client.post(
        f"/teachers/{profile_id}/restore",
        headers=_headers(principal["id"], tenant_a),
    )
    assert profile_restore.status_code == 200, profile_restore.text
    assert profile_restore.json()["profile_only"] is True
    assert profile_restore.json()["account_restored"] is False

    teacher, user = await _deleted_teacher(tenant_a)
    await gd_update_one(db.session, "teachers", {"id": teacher["id"]}, {"phone": None})
    linked_restore = await client.post(
        f"/teachers/{teacher['id']}/restore",
        headers=_headers(principal["id"], tenant_a),
    )
    assert linked_restore.status_code == 409, linked_restore.text
    assert linked_restore.json()["error"]["detail"]["code"] == "TEACHER_ACCOUNT_REVIEW_REQUIRED"
    assert (await gd_find_one(
        db.session, "users", {"id": user["id"]}
    ))["is_active"] is False


@pytest.mark.asyncio
async def test_complete_profile_only_restore_requires_zero_global_account_candidates(
    client, tenant_a,
):
    principal = await _principal(tenant_a)
    profile_id = str(uuid.uuid4())
    phone = f"05{int(uuid.UUID(profile_id)) % 100_000_000:08d}"
    email = f"profile-only-{profile_id}@test.invalid"
    await gd_insert(db.session, "teachers", {
        "id": profile_id,
        "school_id": tenant_a,
        "full_name": "Complete Profile Only",
        "email": email,
        "phone": phone,
        "national_id": f"1{int(uuid.UUID(profile_id)) % 1_000_000_000:09d}",
        "user_id": None,
        "is_active": False,
        "deleted_at": "2025-01-01T00:00:00+00:00",
    })

    restored = await client.post(
        f"/teachers/{profile_id}/restore",
        headers=_headers(principal["id"], tenant_a),
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["profile_only"] is True
    assert restored.json()["account_restored"] is False
    assert (await gd_find_one(
        db.session, "teachers", {"id": profile_id}
    ))["user_id"] is None

    conflict_profile_id = str(uuid.uuid4())
    conflict_phone = f"05{int(uuid.UUID(conflict_profile_id)) % 100_000_000:08d}"
    conflict_email = f"profile-only-{conflict_profile_id}@test.invalid"
    await gd_insert(db.session, "teachers", {
        "id": conflict_profile_id,
        "school_id": tenant_a,
        "full_name": "Conflicting Complete Profile",
        "email": conflict_email,
        "phone": conflict_phone,
        "national_id": f"1{int(uuid.UUID(conflict_profile_id)) % 1_000_000_000:09d}",
        "user_id": None,
        "is_active": False,
        "deleted_at": "2025-01-01T00:00:00+00:00",
    })
    await gd_insert(db.session, "users", {
        "id": str(uuid.uuid4()),
        "email": conflict_email.upper(),
        "phone": None,
        "full_name": "Contact Collision",
        "password_hash": "x",
        "role": UserRole.TEACHER.value,
        "tenant_id": tenant_a,
        "is_active": False,
    })
    blocked = await client.post(
        f"/teachers/{conflict_profile_id}/restore",
        headers=_headers(principal["id"], tenant_a),
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["detail"]["code"] == "TEACHER_ACCOUNT_REVIEW_REQUIRED"
    assert (await gd_find_one(
        db.session, "teachers", {"id": conflict_profile_id}
    ))["is_active"] is False


@pytest.mark.asyncio
async def test_unlinked_incomplete_profile_with_matching_account_requires_review(client, tenant_a):
    principal = await _principal(tenant_a)
    profile_id = str(uuid.uuid4())
    email = f"legacy-{profile_id}@test.invalid"
    await gd_insert(db.session, "teachers", {
        "id": profile_id,
        "school_id": tenant_a,
        "full_name": "Unlinked Legacy",
        "email": email,
        "phone": None,
        "is_active": False,
        "deleted_at": "2025-01-01T00:00:00+00:00",
    })
    await gd_insert(db.session, "users", {
        "id": str(uuid.uuid4()),
        "email": email.upper(),
        "full_name": "Possible Owner",
        "password_hash": "x",
        "role": UserRole.TEACHER.value,
        "tenant_id": tenant_a,
        "is_active": False,
    })
    restore = await client.post(
        f"/teachers/{profile_id}/restore",
        headers=_headers(principal["id"], tenant_a),
    )
    assert restore.status_code == 409, restore.text
    assert restore.json()["error"]["detail"]["code"] == "TEACHER_ACCOUNT_REVIEW_REQUIRED"


@pytest.mark.asyncio
async def test_suspended_retained_account_requires_review_and_is_not_revived(client, tenant_a):
    principal = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_a)
    await gd_update_one(db.session, "users", {"id": user["id"]}, {"status": "suspended"})

    response = await client.post("/teachers/create", json={
        "full_name": "Suspended",
        "email": user["email"],
        "phone": teacher["phone"],
        "national_id": teacher["national_id"],
    }, headers=_headers(principal["id"], tenant_a))
    assert response.status_code == 409, response.text
    assert response.json()["error"]["detail"]["code"] == "TEACHER_ACCOUNT_REVIEW_REQUIRED"

    restore = await client.post(
        f"/teachers/{teacher['id']}/restore",
        headers=_headers(principal["id"], tenant_a),
    )
    assert restore.status_code == 409
    assert (await gd_find_one(db.session, "users", {"id": user["id"]}))["is_active"] is False


@pytest.mark.asyncio
async def test_active_duplicate_has_structured_code(client, tenant_a):
    principal = await _principal(tenant_a)
    teacher, user = await _deleted_teacher(tenant_a)
    await gd_update_one(db.session, "teachers", {"id": teacher["id"]}, {
        "is_active": True, "deleted_at": None,
    })
    await gd_update_one(db.session, "users", {"id": user["id"]}, {"is_active": True})

    response = await client.post("/teachers/create", json={
        "full_name": "Duplicate",
        "email": user["email"],
        "phone": teacher["phone"],
        "national_id": teacher["national_id"],
    }, headers=_headers(principal["id"], tenant_a))
    assert response.status_code == 409, response.text
    assert response.json()["error"]["detail"]["code"] == "TEACHER_ACTIVE_DUPLICATE"


@pytest.mark.asyncio
async def test_credential_recovery_copies_authoritative_teacher_phone(tenant_a):
    """Healing an old profile without a User must not create another NULL phone."""
    principal = await _principal(tenant_a)
    teacher_id = str(uuid.uuid4())
    phone = f"05{int(uuid.UUID(teacher_id)) % 100_000_000:08d}"
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "school_id": tenant_a,
        "full_name": "Legacy Teacher",
        "email": f"legacy-{teacher_id}@test.invalid",
        "phone": phone,
        "national_id": f"1{teacher_id.replace('-', '')[:9]}",
        "is_active": True,
    })

    result = await update_teacher_credentials(
        teacher_id,
        UpdateCredentialsRequest(new_password="new-password"),
        {
            **principal,
            "role": UserRole.SCHOOL_PRINCIPAL.value,
            "tenant_id": tenant_a,
        },
        {},
    )

    assert result["account_created"] is True
    healed_teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    healed_user = await gd_find_one(db.session, "users", {"id": healed_teacher["user_id"]})
    assert healed_user["phone"] == phone


@pytest.mark.asyncio
async def test_create_user_write_failure_does_not_leave_orphan_teacher(
    client, tenant_a, monkeypatch,
):
    principal = await _principal(tenant_a)
    marker = uuid.uuid4()
    email = f"atomic-{marker}@test.invalid"
    phone = f"05{int(marker) % 100_000_000:08d}"
    national_id = f"1{int(marker) % 1_000_000_000:09d}"
    real_insert = academics_teacher_routes.gd_insert

    async def fail_user(session, collection, document):
        if collection == "users" and document.get("email") == email:
            raise RuntimeError("injected user write failure")
        return await real_insert(session, collection, document)

    monkeypatch.setattr(academics_teacher_routes, "gd_insert", fail_user)
    response = await client.post("/teachers/create", json={
        "full_name": "Atomic Teacher",
        "email": email,
        "phone": phone,
        "national_id": national_id,
    }, headers=_headers(principal["id"], tenant_a))

    assert response.status_code == 500
    assert await gd_find_one(db.session, "teachers", {"email": email}) is None
    assert await gd_find_one(db.session, "users", {"email": email}) is None


@pytest.mark.asyncio
async def test_concurrent_create_in_independent_sessions_provisions_only_one_account():
    """Exercise the advisory identity lock with two real committed sessions."""
    school_id = str(uuid.uuid4())
    marker = uuid.uuid4().hex
    email = f"concurrent-{marker}@test.invalid"
    phone = f"05{int(marker[:12], 16) % 100_000_000:08d}"
    national_id = f"1{int(marker[12:24], 16) % 1_000_000_000:09d}"
    principal = {
        "id": str(uuid.uuid4()),
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "full_name": "Concurrent Test Principal",
    }
    payload = academics_teacher_routes.TeacherWizardCreate(
        full_name="Concurrent Teacher",
        email=email,
        phone=phone,
        national_id=national_id,
    )

    async with async_session_factory() as seed:
        await gd_insert(seed, "schools", {
            "id": school_id,
            "name": f"Concurrent-{marker[:8]}",
            "code": f"C{marker[:10]}",
            "status": "active",
            "country": "SA",
            "language": "ar",
        })
        await seed.commit()

    async def attempt():
        async with async_session_factory() as session:
            db.set_session(session)
            try:
                result = await academics_teacher_routes.create_teacher_wizard(
                    payload, principal,
                )
                await session.commit()
                return result
            except HTTPException as exc:
                await session.rollback()
                return exc
            finally:
                db.set_session(None)

    try:
        outcomes = await asyncio.gather(attempt(), attempt())
        successes = [value for value in outcomes if isinstance(value, dict)]
        conflicts = [value for value in outcomes if isinstance(value, HTTPException)]
        assert len(successes) == 1, outcomes
        assert len(conflicts) == 1, outcomes
        assert conflicts[0].status_code == 409
        assert conflicts[0].detail["code"] == "TEACHER_ACTIVE_DUPLICATE"

        async with async_session_factory() as verify:
            users = (await verify.execute(
                text("SELECT count(*) FROM users WHERE email = :email"),
                {"email": email},
            )).scalar_one()
            teachers = (await verify.execute(
                text("SELECT count(*) FROM teachers WHERE email = :email"),
                {"email": email},
            )).scalar_one()
            assert users == teachers == 1
    finally:
        # This test commits solely to make rows visible across independent
        # sessions, so it owns deterministic cleanup even on assertion failure.
        async with async_session_factory() as cleanup:
            await cleanup.execute(
                text("DELETE FROM teachers WHERE school_id = :school_id"),
                {"school_id": school_id},
            )
            await cleanup.execute(
                text("DELETE FROM users WHERE tenant_id = :school_id OR email = :email"),
                {"school_id": school_id, "email": email},
            )
            await cleanup.execute(
                text("DELETE FROM schools WHERE id = :school_id"),
                {"school_id": school_id},
            )
            await cleanup.commit()