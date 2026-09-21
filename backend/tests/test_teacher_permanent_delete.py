"""Permanent school deletion: isolated transactions, including explicit commit."""
import asyncio
import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from db import _get_async_url
from dependencies import db, create_access_token, create_refresh_token
from engines.sql_utils import gd_insert, gd_find_one, gd_update_one
from pg_models import Base, Teacher
from tests.test_teacher_restore_create_contract import _principal, _deleted_teacher, _headers


@pytest_asyncio.fixture(autouse=True)
async def _db_session():
    # A handler commit releases a savepoint, never commits fixture data.
    engine = create_async_engine(_get_async_url(), poolclass=NullPool)
    async with engine.connect() as connection:
        outer = await connection.begin()
        async with AsyncSession(bind=connection, join_transaction_mode="create_savepoint",
                                expire_on_commit=False) as session:
            db.set_session(session)
            yield session
            await session.close()
            db.set_session(None)
        await outer.rollback()
    await engine.dispose()


async def setup(school):
    actor = await _principal(school)
    teacher, user = await _deleted_teacher(school)
    await gd_update_one(db.session, "teachers", {"id": teacher["id"]},
                        {"is_active": True, "deleted_at": None})
    await gd_update_one(db.session, "users", {"id": user["id"]}, {"is_active": True})
    return actor, teacher, user


@pytest.mark.asyncio
@pytest.mark.parametrize("create_path", ["/teachers/create", "/teachers"])
async def test_permanent_delete_readd_duplicate_and_token(client, tenant_a, create_path):
    actor, teacher, user = await setup(tenant_a)
    email = f"{user['id']}@example.com"
    for collection, row in (("users", user), ("teachers", teacher)):
        await gd_update_one(db.session, collection, {"id": row["id"]}, {"email": email})
        row["email"] = email
    claims = {"sub": user["id"], "role": "teacher", "tenant_id": tenant_a}
    old_headers = {"Authorization": f"Bearer {create_access_token(claims)}"}
    refresh_token = create_refresh_token(claims)
    session_id = str(uuid.uuid4())
    await gd_insert(db.session, "user_sessions", {
        "id": session_id, "user_id": user["id"], "jti": str(uuid.uuid4()),
        "refresh_jti": str(uuid.uuid4()), "refresh_family_id": str(uuid.uuid4()),
    })
    await gd_insert(db.session, "mfa_factors", {
        "id": str(uuid.uuid4()), "user_id": user["id"], "kind": "totp",
    })
    response = await client.delete(f"/teachers/{teacher['id']}", headers=_headers(actor["id"], tenant_a))
    assert response.status_code == 200, response.text
    assert response.json()["permanent"] is True
    assert await gd_find_one(db.session, "teachers", {"id": teacher["id"]}) is None
    assert await gd_find_one(db.session, "users", {"id": user["id"]}) is None
    assert await gd_find_one(db.session, "user_sessions", {"id": session_id}) is None
    assert await gd_find_one(db.session, "mfa_factors", {"user_id": user["id"]}) is None
    from src.modules.auth.controllers.auth_routes_mod import _record_session_from_token
    await _record_session_from_token(db.session, old_headers["Authorization"][7:], user["id"], None, None)
    assert await gd_find_one(db.session, "user_sessions", {"user_id": user["id"]}) is None
    assert (await gd_find_one(db.session, "schools", {"id": tenant_a}))["current_teachers"] == 0
    assert (await client.get("/teachers?include_deleted=true",
                            headers=_headers(actor["id"], tenant_a))).json() == []
    missing = await client.delete(
        f"/teachers/{teacher['id']}", headers=_headers(actor["id"], tenant_a),
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "HTTP_404"
    assert missing.json()["error"]["message"] == "المعلم غير موجود"
    assert (await client.get("/auth/me", headers=old_headers)).status_code in (401, 403)
    assert (await client.post("/auth/refresh", json={"refresh_token": refresh_token})).status_code == 401
    response = await client.post(create_path, headers=_headers(actor["id"], tenant_a),
                                 json={k: teacher[k] for k in ("full_name", "email", "phone", "national_id")})
    assert response.status_code == 200, response.text
    assert (await gd_find_one(db.session, "teachers", {"email": teacher["email"]}))["id"] != teacher["id"]
    assert (await client.post("/auth/refresh", json={"refresh_token": refresh_token})).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("ambiguity", [
    "linked_roles", "other_profile", "missing_link", "generic_role",
    "unknown_document", "other_identity", "nested_claim",
])
async def test_shared_accounts_fail_closed(client, tenant_a, tenant_b, ambiguity):
    actor, teacher, user = await setup(tenant_a)
    if ambiguity == "linked_roles":
        await gd_update_one(db.session, "users", {"id": user["id"]},
                            {"linked_roles": [{"role": "parent", "tenant_id": tenant_a}]})
    elif ambiguity == "other_profile":
        await gd_insert(db.session, "teachers", {"id": str(uuid.uuid4()), "user_id": user["id"],
                        "school_id": tenant_b, "full_name": "Other school"})
    elif ambiguity == "missing_link":
        await gd_update_one(db.session, "teachers", {"id": teacher["id"]}, {"user_id": None})
    elif ambiguity == "generic_role":
        await gd_insert(db.session, "user_roles", {"id": str(uuid.uuid4()), "user_id": user["id"],
                        "role": "parent", "tenant_id": tenant_a})
    elif ambiguity == "unknown_document":
        await gd_insert(db.session, "unreviewed_identity_extension", {
            "id": str(uuid.uuid4()), "nested": [{"user_id": user["id"]}]})
    else:
        other = await _principal(tenant_b)
        await gd_update_one(db.session, "users", {"id": other["id"]}, (
            {"phone": user["phone"]} if ambiguity == "other_identity" else
            {"linked_roles": [{"role": "teacher", "teacher_id": teacher["id"], "tenant_id": tenant_a}]}
        ))
    result = await client.delete(f"/teachers/{teacher['id']}", headers=_headers(actor["id"], tenant_a))
    assert result.status_code == 409, result.text
    detail = result.json()["error"]["detail"]
    assert detail["code"] == (
        "DELETE_CONFIGURATION_ERROR"
        if ambiguity == "unknown_document"
        else "DELETE_DEPENDENCY_BLOCKED"
    )
    assert detail["message"]
    assert detail["dependencies"] == [{
        "reason": {
            "linked_roles": "account_ownership_mismatch",
            "other_profile": "additional_profile_claims",
            "missing_link": "account_ownership_mismatch",
            "generic_role": "invalid_membership_document",
            "unknown_document": "unknown_linked_document_collection",
            "other_identity": "duplicate_identity_owner",
            "nested_claim": "linked_role_profile_claim",
        }[ambiguity],
        "category": "configuration" if ambiguity == "unknown_document" else "dependency",
        "table": {
            "other_profile": "teachers",
            "missing_link": "users",
            "generic_role": "user_roles",
            "unknown_document": "unreviewed_identity_extension",
            "other_identity": "users",
            "nested_claim": "users",
        }.get(ambiguity, "users"),
        "count": 1 if ambiguity != "other_profile" else 2,
        "resolution": detail["dependencies"][0]["resolution"],
    }]
    assert (await gd_find_one(db.session, "teachers", {"id": teacher["id"]}))["is_active"]
    assert await gd_find_one(db.session, "users", {"id": user["id"]})


@pytest.mark.asyncio
async def test_platform_delete_uses_current_db_role_and_accepts_legacy_defaults(
    client, tenant_a,
):
    actor, teacher, user = await setup(tenant_a)
    standard_six = [
        "view_students",
        "manage_attendance",
        "manage_grades",
        "view_schedule",
        "manage_behavior",
        "view_reports",
    ]
    await gd_update_one(db.session, "users", {"id": user["id"]}, {
        "permissions": standard_six,
    })
    # The JWT deliberately contains the actor's old school role. Authentication
    # must authorize from the freshly loaded users row, not this stale claim.
    await gd_update_one(db.session, "users", {"id": actor["id"]}, {
        "role": "platform_admin", "permissions": [],
    })
    stale_headers = _headers(actor["id"], tenant_a)
    result = await client.delete(
        f"/users/{user['id']}",
        headers=stale_headers,
    )

    assert result.status_code == 200, result.text
    assert result.json()["permanent"] is True
    assert await gd_find_one(db.session, "teachers", {"id": teacher["id"]}) is None
    assert await gd_find_one(db.session, "users", {"id": user["id"]}) is None


@pytest.mark.asyncio
async def test_legacy_teacher_defaults_delete_but_extra_grant_blocks(
    client, tenant_a,
):
    actor, teacher, user = await setup(tenant_a)
    legacy_defaults = [
        "view_students", "manage_attendance", "manage_grades",
        "view_schedule", "manage_behavior", "view_reports",
    ]
    await gd_update_one(db.session, "users", {"id": user["id"]}, {
        "permissions": legacy_defaults + ["users.delete"],
    })
    blocked = await client.delete(
        f"/teachers/{teacher['id']}", headers=_headers(actor["id"], tenant_a),
    )
    assert blocked.status_code == 409
    dependency = blocked.json()["error"]["detail"]["dependencies"][0]
    assert dependency["reason"] == "custom_teacher_permissions"
    assert await gd_find_one(db.session, "users", {"id": user["id"]})

    await gd_update_one(db.session, "users", {"id": user["id"]}, {
        "permissions": legacy_defaults,
    })
    deleted = await client.delete(
        f"/teachers/{teacher['id']}", headers=_headers(actor["id"], tenant_a),
    )
    assert deleted.status_code == 200, deleted.text
    assert await gd_find_one(db.session, "users", {"id": user["id"]}) is None


@pytest.mark.asyncio
async def test_platform_delete_self_and_platform_admin_have_specific_protection_errors(
    client, tenant_a,
):
    actor = await _principal(tenant_a)
    await gd_update_one(db.session, "users", {"id": actor["id"]}, {
        "role": "platform_admin", "permissions": [],
    })
    headers = _headers(actor["id"], tenant_a)
    self_result = await client.delete(f"/users/{actor['id']}", headers=headers)
    assert self_result.status_code == 409
    assert self_result.json()["error"]["detail"]["code"] == "SELF_DELETE_PROTECTED"

    other = await _principal(tenant_a)
    await gd_update_one(db.session, "users", {"id": other["id"]}, {
        "role": "platform_admin", "permissions": [],
    })
    protected_result = await client.delete(f"/users/{other['id']}", headers=headers)
    assert protected_result.status_code == 409
    assert protected_result.json()["error"]["detail"]["code"] == "PLATFORM_ADMIN_PROTECTED"


@pytest.mark.asyncio
async def test_dependency_failure_is_audited_after_cleanup_rollback(
    client, tenant_a,
):
    actor, teacher, user = await setup(tenant_a)
    await gd_update_one(db.session, "users", {"id": user["id"]}, {
        "linked_roles": [{"role": "parent", "tenant_id": tenant_a}],
    })

    result = await client.delete(
        f"/teachers/{teacher['id']}", headers=_headers(actor["id"], tenant_a),
    )

    assert result.status_code == 409
    assert await gd_find_one(db.session, "users", {"id": user["id"]})
    audit = await gd_find_one(db.session, "audit_logs", {
        "entity_id": teacher["id"], "action": "permanent_delete_failed",
    })
    assert audit["new_state"] == {
        "outcome": "blocked",
        "code": "DELETE_DEPENDENCY_BLOCKED",
        "category": "dependency",
        "table": "users",
        "count": 1,
    }
    assert not any(value in str(audit) for value in (
        teacher["email"], teacher["phone"], teacher["national_id"], teacher["full_name"],
    ))


@pytest.mark.asyncio
async def test_failed_delete_does_not_commit_unrelated_pending_work(
    tenant_a, monkeypatch,
):
    from services import teacher_permanent_deletion as service

    actor, teacher, user = await setup(tenant_a)
    await gd_update_one(db.session, "users", {"id": user["id"]}, {
        "linked_roles": [{"role": "parent", "tenant_id": tenant_a}],
    })
    # Establish the test baseline, then add unrelated request work which must
    # remain pending when the deletion guard fails.
    await db.session.commit()
    unrelated_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": unrelated_id, "school_id": tenant_a, "name": "Pending unrelated work",
    })

    async def forbidden_commit():
        raise AssertionError("failure path must not explicitly commit")

    monkeypatch.setattr(db.session, "commit", forbidden_commit)
    with pytest.raises(HTTPException) as blocked:
        await service.permanently_delete_teacher(
            db.session, teacher["id"], actor,
        )
    assert blocked.value.status_code == 409
    assert await gd_find_one(db.session, "subjects", {"id": unrelated_id})

    await db.session.rollback()
    assert await gd_find_one(db.session, "subjects", {"id": unrelated_id}) is None


@pytest.mark.asyncio
async def test_commit_failure_has_no_success_and_rolls_back_all_cleanup(tenant_a, monkeypatch):
    from services import teacher_permanent_deletion as service
    actor, teacher, user = await setup(tenant_a)
    # Save the fixture into the outer rollback-only transaction, so service
    # rollback affects its changes only.
    await db.session.commit()

    async def failed_commit():
        raise RuntimeError("injected durability failure")
    monkeypatch.setattr(db.session, "commit", failed_commit)
    with pytest.raises(RuntimeError, match="durability failure"):
        await service.permanently_delete_teacher(db.session, teacher["id"], actor)
    assert await gd_find_one(db.session, "users", {"id": user["id"]})
    assert await gd_find_one(db.session, "teachers", {"id": teacher["id"]})
    assert await gd_find_one(db.session, "audit_logs", {
        "entity_id": teacher["id"], "action": "permanent_delete"}) is None


@pytest.mark.asyncio
async def test_regular_teacher_cannot_permanently_delete(client, tenant_a):
    actor, teacher, user = await setup(tenant_a)
    await gd_update_one(db.session, "users", {"id": user["id"]}, {"mfa_required": False})
    token = create_access_token({"sub": user["id"], "role": "teacher", "tenant_id": tenant_a})
    result = await client.delete(f"/teachers/{teacher['id']}",
                                 headers={"Authorization": f"Bearer {token}"})
    assert result.status_code == 403
    assert await gd_find_one(db.session, "users", {"id": user["id"]})


@pytest.mark.asyncio
@pytest.mark.parametrize("column", ["result", "config", "data"])
@pytest.mark.parametrize("foreign_scope", ["row", "nested"])
async def test_typed_json_foreign_scope_blocks_before_any_cleanup(
    client, tenant_a, tenant_b, column, foreign_scope,
):
    actor, teacher, user = await setup(tenant_a)
    run_id = str(uuid.uuid4())
    snapshot = {"teacher_id": teacher["id"], "teacher_name": teacher["full_name"]}
    if foreign_scope == "nested":
        snapshot = {"nested": [{"tenant_id": tenant_b, **snapshot}]}
    await gd_insert(db.session, "timetable_runs", {
        "id": run_id, "school_id": tenant_b if foreign_scope == "row" else tenant_a,
        column: snapshot,
    })
    result = await client.delete(f"/teachers/{teacher['id']}", headers=_headers(actor["id"], tenant_a))
    assert result.status_code == 409, result.text
    assert (await gd_find_one(db.session, "timetable_runs", {"id": run_id}))[column] == snapshot
    assert await gd_find_one(db.session, "users", {"id": user["id"]})
    assert (await gd_find_one(db.session, "teachers", {"id": teacher["id"]}))["is_active"]
    assert await gd_find_one(db.session, "teachers", {"id": f"deleted-teacher:{tenant_a}"}) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("schema,kind", [
    ("graph", "parent_of"), ("graph", "guardian_of"), ("graph", "manages_school"),
    ("graph", "unclassified"), ("identity", "parent_child"), ("identity", "guardian"),
    ("identity", "principal_school"), ("identity", "unclassified"),
    ("identity", "teacher_class"),
])
async def test_non_teacher_relationships_in_both_real_schemas_block(
    client, tenant_a, schema, kind,
):
    actor, teacher, user = await setup(tenant_a)
    relation_id = str(uuid.uuid4())
    if schema == "graph":
        relation = {
            "id": relation_id, "relationship_type": kind, "tenant_id": tenant_a,
            "from_entity_type": "parent" if kind in {"parent_of", "guardian_of"} else "principal",
            "from_entity_id": user["id"], "to_entity_type": "student",
            "to_entity_id": str(uuid.uuid4()), "metadata": {}, "status": "active",
        }
    else:
        # IdentityEngine's actual format has user endpoints, not typed class/
        # subject endpoints. Even a teacher_class string cannot prove ownership.
        relation = {
            "id": relation_id, "relationship_type": kind, "user_id_1": user["id"],
            "user_id_2": actor["id"], "is_active": True, "is_verified": True,
            "detected_automatically": False, "created_by": actor["id"],
        }
    await gd_insert(db.session, "user_relationships", relation)
    result = await client.delete(f"/teachers/{teacher['id']}", headers=_headers(actor["id"], tenant_a))
    assert result.status_code == 409, result.text
    retained = await gd_find_one(db.session, "user_relationships", {"id": relation_id})
    assert all(retained[k] == v for k, v in relation.items())
    assert await gd_find_one(db.session, "users", {"id": user["id"]})
    assert (await gd_find_one(db.session, "teachers", {"id": teacher["id"]}))["is_active"]


@pytest.mark.asyncio
@pytest.mark.parametrize("variant", ["valid", "wrong_source", "foreign_endpoint", "mixed_schema", "missing_endpoint"])
async def test_teacher_graph_relationship_requires_proven_endpoints(
    client, tenant_a, tenant_b, variant,
):
    actor, teacher, user = await setup(tenant_a)
    subject_id, relation_id = str(uuid.uuid4()), str(uuid.uuid4())
    if variant != "missing_endpoint":
        await gd_insert(db.session, "subjects", {
            "id": subject_id, "school_id": tenant_b if variant == "foreign_endpoint" else tenant_a,
            "name": "Relationship subject"})
    relation = {
        "id": relation_id, "relationship_type": "teaches_subject", "tenant_id": tenant_a,
        "from_entity_type": "teacher", "from_entity_id": teacher["id"],
        "to_entity_type": "subject", "to_entity_id": subject_id, "status": "active", "metadata": {},
    }
    if variant == "wrong_source":
        relation["from_entity_type"] = "principal"
    if variant == "mixed_schema":
        relation.update(user_id_1=user["id"], user_id_2=actor["id"])
    await gd_insert(db.session, "user_relationships", relation)
    result = await client.delete(f"/teachers/{teacher['id']}", headers=_headers(actor["id"], tenant_a))
    assert result.status_code == (200 if variant == "valid" else 409), result.text
    assert bool(await gd_find_one(db.session, "user_relationships", {"id": relation_id})) == (variant != "valid")


@pytest.mark.asyncio
async def test_history_cascade_and_nested_json_preserved(client, tenant_a):
    actor, teacher, user = await setup(tenant_a)
    session_id, assessment_id, document_id = (str(uuid.uuid4()) for _ in range(3))
    subject_id, assignment_id, schedule_id = (str(uuid.uuid4()) for _ in range(3))
    await gd_insert(db.session, "subjects", {"id": subject_id, "school_id": tenant_a, "name": "Subject"})
    await gd_insert(db.session, "teacher_assignments", {
        "id": assignment_id, "school_id": tenant_a, "teacher_id": teacher["id"], "subject_id": subject_id})
    await gd_insert(db.session, "schedule_sessions", {
        "id": schedule_id, "school_id": tenant_a, "schedule_id": str(uuid.uuid4()),
        "assignment_id": assignment_id, "teacher_id": teacher["id"], "day_of_week": "Sunday",
        "teacher_name": teacher["full_name"]})
    await gd_insert(db.session, "user_roles", {
        "id": str(uuid.uuid4()), "user_id": user["id"], "school_id": tenant_a, "role": "teacher"})
    await gd_insert(db.session, "teacher_sessions", {
        "id": session_id, "teacher_id": teacher["id"], "school_id": tenant_a,
        "date": "2025-01-01T00:00:00+00:00", "status": "completed"})
    await gd_insert(db.session, "assessments", {
        "id": assessment_id, "teacher_id": teacher["id"], "school_id": tenant_a,
        "name": "Retained assessment"})
    student_id, attendance_id, submission_id, message_id = (str(uuid.uuid4()) for _ in range(4))
    await gd_insert(db.session, "students", {
        "id": student_id, "school_id": tenant_a, "full_name": "Student history"})
    await gd_insert(db.session, "attendance", {
        "id": attendance_id, "student_id": student_id, "school_id": tenant_a,
        "recorded_by": user["id"], "date": "2025-01-01T00:00:00+00:00", "status": "present"})
    await gd_insert(db.session, "assessment_submissions", {
        "id": submission_id, "student_id": student_id, "assessment_id": assessment_id,
        "graded_by": user["id"], "score": 88})
    await gd_insert(db.session, "messages", {
        "id": message_id, "school_id": tenant_a, "sender_id": user["id"],
        "recipient_id": actor["id"], "body": "Retained educational correspondence"})
    await gd_insert(db.session, "timetable_sessions", {
        "id": document_id, "school_id": tenant_a, "teacher_id": teacher["id"],
        "teacher_name": teacher["full_name"], "is_active": True,
        "history": [{"teacher_id": teacher["id"], "teacher_email": teacher["email"]}]})
    result = await client.delete(f"/teachers/{teacher['id']}", headers=_headers(actor["id"], tenant_a))
    assert result.status_code == 200, result.text
    history = await gd_find_one(db.session, "teacher_sessions", {"id": session_id})
    assert history and history["teacher_id"] != teacher["id"]
    marker = (await db.session.execute(select(Teacher).where(Teacher.id == history["teacher_id"]))).scalar_one()
    assert marker.user_id is None and marker.is_active is False and marker.email is None
    assert await gd_find_one(db.session, "assessments", {"id": assessment_id})
    assert await gd_find_one(db.session, "teacher_assignments", {"id": assignment_id}) is None
    assert await gd_find_one(db.session, "user_roles", {"user_id": user["id"]}) is None
    schedule = await gd_find_one(db.session, "schedule_sessions", {"id": schedule_id})
    assert schedule["teacher_id"] is None and schedule["assignment_id"] is None
    assert schedule["status"] == "cancelled" and schedule["teacher_name"] == "معلم محذوف"
    assert (await gd_find_one(db.session, "attendance", {"id": attendance_id}))["recorded_by"] is None
    submission = await gd_find_one(db.session, "assessment_submissions", {"id": submission_id})
    assert submission["graded_by"] is None and submission["score"] == 88
    assert (await gd_find_one(db.session, "messages", {"id": message_id}))["sender_id"] is None
    doc = await gd_find_one(db.session, "timetable_sessions", {"id": document_id})
    assert doc and doc["is_active"] is False
    assert teacher["id"] not in str(doc) and teacher["email"] not in str(doc)
    audit = await gd_find_one(db.session, "audit_logs", {"entity_id": teacher["id"], "action": "permanent_delete"})
    assert audit["new_state"]["permanent"] is True
    assert not any(value in str(audit) for value in (teacher["email"], teacher["phone"], teacher["national_id"], teacher["full_name"]))


@pytest.mark.asyncio
async def test_cross_tenant_and_audit_rollback(client, tenant_a, tenant_b, monkeypatch):
    from services import teacher_permanent_deletion as service
    actor, teacher, user = await setup(tenant_a)
    foreign = await _principal(tenant_b)
    result = await client.delete(f"/teachers/{teacher['id']}", headers=_headers(foreign["id"], tenant_b))
    assert result.status_code in (403, 404)

    async def broken_audit(*args, **kwargs):
        raise RuntimeError("injected audit failure")
    monkeypatch.setattr(service, "write_deletion_audit", broken_audit)
    with pytest.raises(Exception):
        await service.permanently_delete_teacher(db.session, teacher["id"], actor)
    assert await gd_find_one(db.session, "users", {"id": user["id"]})
    assert (await gd_find_one(db.session, "teachers", {"id": teacher["id"]}))["is_active"]


@pytest.mark.asyncio
async def test_concurrent_deletions_and_unreviewed_cascade_guard(monkeypatch):
    """Real concurrent commits in a disposable test schema, never real rows."""
    from services import teacher_permanent_deletion as service
    schema = f"test_teacher_delete_{uuid.uuid4().hex}"
    control = create_async_engine(_get_async_url(), poolclass=NullPool)
    engine = create_async_engine(_get_async_url(), poolclass=NullPool,
                                 connect_args={"server_settings": {"search_path": schema}})
    tasks = []
    try:
        async with control.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        school, teacher_id, user_id, actor_id = (str(uuid.uuid4()) for _ in range(4))
        actor = {"id": actor_id, "role": "school_principal", "tenant_id": school}
        async with factory() as session:
            await gd_insert(session, "schools", {"id": school, "name": "Isolated concurrency school", "code": schema})
            await gd_insert(session, "users", {
                **actor, "email": f"{actor_id}@test.invalid", "full_name": "Principal", "password_hash": "x"})
            await gd_insert(session, "users", {
                "id": user_id, "email": f"{user_id}@test.invalid", "full_name": "Teacher",
                "password_hash": "x", "role": "teacher", "tenant_id": school, "teacher_id": teacher_id})
            await gd_insert(session, "teachers", {
                "id": teacher_id, "user_id": user_id, "school_id": school, "full_name": "Teacher"})
            await session.commit()
        # Verify live schema drift cannot silently cascade away new history.
        async with engine.begin() as connection:
            await connection.execute(text(
                "CREATE TABLE unreviewed_history (id text PRIMARY KEY, "
                "teacher_id text REFERENCES teachers(id) ON DELETE CASCADE)"
            ))
            await connection.execute(text(
                "INSERT INTO unreviewed_history VALUES ('history', :teacher)"
            ), {"teacher": teacher_id})
        async with factory() as session:
            with pytest.raises(HTTPException) as denied:
                await service.permanently_delete_teacher(session, teacher_id, actor)
            assert denied.value.status_code == 409
            assert (await session.execute(text("SELECT id FROM unreviewed_history"))).scalar() == "history"
        async with engine.begin() as connection:
            await connection.execute(text("DROP TABLE unreviewed_history"))
        reached, release = asyncio.Event(), asyncio.Event()
        original = service.write_deletion_audit

        async def pause(*args, **kwargs):
            reached.set()
            await release.wait()
            return await original(*args, **kwargs)
        monkeypatch.setattr(service, "write_deletion_audit", pause)

        async def run_delete():
            async with factory() as session:
                try:
                    return await service.permanently_delete_teacher(session, teacher_id, actor)
                except HTTPException as exc:
                    return exc.status_code
        tasks.append(asyncio.create_task(run_delete()))
        await asyncio.wait_for(reached.wait(), 15)
        tasks.append(asyncio.create_task(run_delete()))
        await asyncio.sleep(0.1)
        assert not tasks[1].done(), "second deletion must wait for the first transaction"
        release.set()
        results = await asyncio.wait_for(asyncio.gather(*tasks), 15)
        assert results[0]["permanent"] is True and results[1] == 404
        async with factory() as session:
            assert await gd_find_one(session, "users", {"id": user_id}) is None
            assert await gd_find_one(session, "teachers", {"id": teacher_id}) is None
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await engine.dispose()
        async with control.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await control.dispose()