"""
Task #952 — regression tests for the skill-type create-then-record flow.

Invariants covered:
- A principal who creates a skill type via POST /skills-types can immediately
  use that skill_id in POST /session/{id}/skill — HTTP 200 (no stale state).
- A teacher who creates a skill type can immediately record it in their own
  session — HTTP 200.
- A skill created under tenant A is rejected (404) when recorded in a session
  that belongs to tenant B (cross-tenant isolation).
- GET /skills-types returns global (seed) skills plus school-specific ones for
  the caller's school, and does NOT leak another school's skills.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_find, gd_find_one, gd_insert


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

async def _mk_user(role: str, tenant_id: str) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": role, "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test", "full_name": "مستخدم", "is_active": True,
        "password_hash": "x",
    })
    return uid


def _headers(user_id: str, role: str, tenant_id: str) -> dict:
    token = create_access_token({
        "sub": user_id, "role": role, "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_class(tenant_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": tenant_id, "tenant_id": tenant_id, "name": "1A",
    })
    return cid


async def _mk_student(tenant_id: str, class_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "tenant_id": tenant_id, "school_id": tenant_id,
        "class_id": class_id, "full_name": "طالب", "is_active": True,
    })
    return sid


async def _mk_session(tenant_id: str, class_id: str, teacher_id: str) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "school_id": tenant_id,
        "tenant_id": tenant_id,
        "class_id": class_id,
        "date": "2026-06-16",
        "status": "in_progress",
        "start_time": now,
        "teacher_id": teacher_id,
        "attendance_approved": True,
        "created_at": now,
    })
    return session_id


# ─────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_principal_create_skill_then_record_success(client, tenant_a):
    """
    Principal creates a skill type → teacher immediately records it in a live
    session → HTTP 200. Simulates the exact sequence that was failing.
    """
    principal_id = await _mk_user("school_principal", tenant_a)
    teacher_id = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(tenant_a, class_id)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)

    principal_hdrs = _headers(principal_id, "school_principal", tenant_a)
    teacher_hdrs = _headers(teacher_id, "teacher", tenant_a)

    # Step 1 — principal creates the skill type
    create_resp = await client.post(
        "/skills-types",
        json={"name": "Critical Thinking", "name_ar": "التفكير النقدي"},
        headers=principal_hdrs,
    )
    assert create_resp.status_code == 200, create_resp.text
    skill_id = create_resp.json()["skill"]["id"]
    assert skill_id.startswith("skill-")
    # school_id must be stored so the skill is tenant-scoped
    skill_doc = await gd_find_one(db.session, "skills_types", {"id": skill_id})
    assert skill_doc is not None
    assert skill_doc.get("school_id") == tenant_a

    # Step 2 — teacher records that skill in an active session immediately
    record_resp = await client.post(
        f"/session/{session_id}/skill",
        json={"student_id": student_id, "skill_type_id": skill_id},
        headers=teacher_hdrs,
    )
    assert record_resp.status_code == 200, record_resp.text


@pytest.mark.asyncio
async def test_teacher_create_skill_then_record_success(client, tenant_a):
    """
    Teachers are now allowed to call POST /skills-types and can immediately
    use the created skill in their own session.
    """
    teacher_id = await _mk_user("teacher", tenant_a)
    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(tenant_a, class_id)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)

    teacher_hdrs = _headers(teacher_id, "teacher", tenant_a)

    create_resp = await client.post(
        "/skills-types",
        json={"name": "Collaboration", "name_ar": "التعاون"},
        headers=teacher_hdrs,
    )
    assert create_resp.status_code == 200, create_resp.text
    skill_id = create_resp.json()["skill"]["id"]

    record_resp = await client.post(
        f"/session/{session_id}/skill",
        json={"student_id": student_id, "skill_type_id": skill_id},
        headers=teacher_hdrs,
    )
    assert record_resp.status_code == 200, record_resp.text


@pytest.mark.asyncio
async def test_cross_tenant_skill_rejected_in_foreign_session(client, tenant_a, tenant_b):
    """
    A skill created by tenant A must NOT be usable in a session belonging to
    tenant B. The backend must return 404, not 200.
    """
    # Tenant A sets up a skill
    principal_a = await _mk_user("school_principal", tenant_a)
    principal_a_hdrs = _headers(principal_a, "school_principal", tenant_a)
    create_resp = await client.post(
        "/skills-types",
        json={"name": "Skill A", "name_ar": "مهارة-أ"},
        headers=principal_a_hdrs,
    )
    assert create_resp.status_code == 200, create_resp.text
    skill_a_id = create_resp.json()["skill"]["id"]

    # Tenant B sets up a session
    teacher_b = await _mk_user("teacher", tenant_b)
    class_b = await _mk_class(tenant_b)
    student_b = await _mk_student(tenant_b, class_b)
    session_b = await _mk_session(tenant_b, class_b, teacher_b)

    teacher_b_hdrs = _headers(teacher_b, "teacher", tenant_b)

    # Tenant B teacher tries to record tenant A's skill → must be rejected
    record_resp = await client.post(
        f"/session/{session_b}/skill",
        json={"student_id": student_b, "skill_type_id": skill_a_id},
        headers=teacher_b_hdrs,
    )
    assert record_resp.status_code == 404, (
        f"Expected 404 for cross-tenant skill; got {record_resp.status_code}: {record_resp.text}"
    )


@pytest.mark.asyncio
async def test_get_skills_types_filters_by_school(client, tenant_a, tenant_b):
    """
    GET /skills-types returns global skills + school-scoped skills for the
    caller, but must NOT include skills from a different school.
    """
    principal_a = await _mk_user("school_principal", tenant_a)
    principal_b = await _mk_user("school_principal", tenant_b)
    principal_a_hdrs = _headers(principal_a, "school_principal", tenant_a)
    principal_b_hdrs = _headers(principal_b, "school_principal", tenant_b)

    # Tenant A creates a school-scoped skill
    resp_a = await client.post(
        "/skills-types",
        json={"name": "Skill A Only", "name_ar": "مهارة خاصة بأ"},
        headers=principal_a_hdrs,
    )
    assert resp_a.status_code == 200, resp_a.text
    skill_a_id = resp_a.json()["skill"]["id"]

    # Tenant B fetches their list — must NOT see tenant A's skill
    list_b = await client.get("/skills-types", headers=principal_b_hdrs)
    assert list_b.status_code == 200, list_b.text
    skill_ids_seen_by_b = {s["id"] for s in list_b.json()}
    assert skill_a_id not in skill_ids_seen_by_b, (
        "Tenant B should not see a skill that belongs to tenant A"
    )

    # Tenant A fetches their list — must see their own skill
    list_a = await client.get("/skills-types", headers=principal_a_hdrs)
    assert list_a.status_code == 200, list_a.text
    skill_ids_seen_by_a = {s["id"] for s in list_a.json()}
    assert skill_a_id in skill_ids_seen_by_a, (
        "Tenant A should see their own school-scoped skill"
    )
