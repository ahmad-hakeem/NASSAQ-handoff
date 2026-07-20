"""Curriculum-plan tab ↔ Smart Lesson Plan Assistant bridge.

Bug: plans generated in the assistant and "saved to class" live in the
``lesson_plans`` GenericDocument collection, while the class خطة المنهج
tab reads ONLY ``curriculum_lessons`` — so saved plans never appeared in
the class view. Fix: ``GET /class/{class_id}/curriculum-plan`` now also
returns ``assistant_plans`` = the CALLER'S OWN saved assistant plans
pinned to that class.

Coverage:
  (a) IT — own saved plan for the class appears in ``assistant_plans``.
  (b) IT — unsaved plans and plans saved to a DIFFERENT class excluded.
  (c) School teacher — own saved plan appears (same route, real tenant).
  (d) Privacy — another teacher's plan for the same class is invisible.
  (e) Serialization — the raw ``prompt`` / ``created_by`` fields never leak.
  (f) Leadership — ``assistant_plans`` is [] (assistant plans stay
      creator-private; leadership visibility is a separate product call).
  (g) Subject filter — assistant plans are NOT hidden by ``subject_id``
      (fail-visible: they carry free-text subject, not a subject_id).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from auth_scope import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


def _headers(uid: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({"sub": uid, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


async def _mk_it_user() -> dict:
    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": now,
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-WS-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher_workspace",
    })
    user["tenant_id"] = wsid
    return user


async def _mk_class(school_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "tenant_id": school_id,
        "name": f"C-{cid[:6]}",
        "capacity": 20,
        "current_students": 0,
        "is_active": True,
    })
    return cid


async def _mk_school_teacher() -> dict:
    """Regular school teacher with a real tenant + authoritative teachers
    row + one ACTIVE teacher_assignments class (mirrors the Task #1089
    fixtures in test_independent_teacher_lesson_plans.py)."""
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid,
        "name": f"S-{sid[:6]}",
        "code": f"S{sid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.TEACHER.value,
        "tenant_id": sid,
        "email": f"t-{uid}@t.test",
        "full_name": f"T-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "user_id": uid,
        "school_id": sid,
        "tenant_id": sid,
        "full_name": user["full_name"],
        "is_active": True,
    })
    user["teacher_id"] = teacher_id
    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id,
        "school_id": sid,
        "tenant_id": sid,
        "name": "C-own",
        "name_ar": "ص-خ",
        "is_active": True,
    })
    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id,
        "school_id": sid,
        "name": "رياضيات",
        "is_active": True,
    })
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()),
        "teacher_id": teacher_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "school_id": sid,
        "is_active": True,
    })
    user["class_id"] = class_id
    user["subject_id"] = subject_id
    return user


async def _mk_principal(sid: str) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": "school_admin",
        "tenant_id": sid,
        "email": f"p-{uid}@t.test",
        "full_name": f"P-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


async def _mk_assistant_plan(
    *,
    workspace_id: str,
    created_by: str,
    class_id=None,
    is_saved: bool = False,
    topic: str = "مقدمة في الكسور",
    subject: str = "رياضيات",
) -> str:
    now = datetime.now(timezone.utc)
    plan_id = str(uuid.uuid4())
    await gd_insert(db.session, "lesson_plans", {
        "id": plan_id,
        "workspace_school_id": workspace_id,
        "created_by": created_by,
        "subject": subject,
        "grade_level": "الخامس",
        "topic": topic,
        "duration_minutes": 45,
        "language": "ar",
        "prompt": "SECRET-PROMPT-MUST-NOT-LEAK",
        "plan": {"title": topic, "objectives": ["هدف 1"]},
        "class_id": class_id,
        "is_saved": is_saved,
        "created_at": now,
        "updated_at": now,
    })
    return plan_id


# ---------------------------------------------------------------------------
# (a)+(b) IT — own saved plan appears; unsaved / other-class excluded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_it_saved_plan_appears_in_class_curriculum(client):
    user = await _mk_it_user()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    cid = await _mk_class(wsid)
    other_cid = await _mk_class(wsid)

    saved = await _mk_assistant_plan(
        workspace_id=wsid, created_by=user["id"], class_id=cid, is_saved=True,
    )
    # noise: unsaved draft + plan saved to a different class
    await _mk_assistant_plan(
        workspace_id=wsid, created_by=user["id"], class_id=None, is_saved=False,
    )
    await _mk_assistant_plan(
        workspace_id=wsid, created_by=user["id"], class_id=other_cid, is_saved=True,
    )

    resp = await client.get(f"/class/{cid}/curriculum-plan", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "assistant_plans" in body, "assistant_plans key missing from curriculum payload"
    ids = {p["id"] for p in body["assistant_plans"]}
    assert ids == {saved}
    plan = body["assistant_plans"][0]
    assert plan["topic"] == "مقدمة في الكسور"
    assert plan["class_id"] == cid
    assert plan["is_saved"] is True
    assert plan["plan"]["title"] == "مقدمة في الكسور"


# ---------------------------------------------------------------------------
# (c) School teacher — own saved plan appears on the same route
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_school_teacher_saved_plan_appears(client):
    user = await _mk_school_teacher()
    h = _headers(user["id"], user["role"], user["tenant_id"])
    saved = await _mk_assistant_plan(
        workspace_id=user["tenant_id"],
        created_by=user["id"],
        class_id=user["class_id"],
        is_saved=True,
    )

    resp = await client.get(f"/class/{user['class_id']}/curriculum-plan", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ids = {p["id"] for p in body.get("assistant_plans", [])}
    assert saved in ids


# ---------------------------------------------------------------------------
# (d) Privacy — a colleague's plan for the same class stays invisible
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_other_teachers_plan_is_invisible(client):
    user = await _mk_school_teacher()
    other_uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": other_uid,
        "role": UserRole.TEACHER.value,
        "tenant_id": user["tenant_id"],
        "email": f"t2-{other_uid}@t.test",
        "full_name": "T2",
        "is_active": True,
        "password_hash": "x",
    })
    await _mk_assistant_plan(
        workspace_id=user["tenant_id"],
        created_by=other_uid,
        class_id=user["class_id"],
        is_saved=True,
    )

    h = _headers(user["id"], user["role"], user["tenant_id"])
    resp = await client.get(f"/class/{user['class_id']}/curriculum-plan", headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json().get("assistant_plans", []) == []


# ---------------------------------------------------------------------------
# (e) Serialization — prompt / created_by never leak
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assistant_plan_serialization_whitelist(client):
    user = await _mk_it_user()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    cid = await _mk_class(wsid)
    await _mk_assistant_plan(
        workspace_id=wsid, created_by=user["id"], class_id=cid, is_saved=True,
    )

    resp = await client.get(f"/class/{cid}/curriculum-plan", headers=h)
    assert resp.status_code == 200, resp.text
    plans = resp.json().get("assistant_plans", [])
    assert len(plans) == 1
    for forbidden in ("prompt", "created_by", "workspace_school_id"):
        assert forbidden not in plans[0], f"{forbidden} leaked in assistant plan payload"


# ---------------------------------------------------------------------------
# (f) Leadership — assistant plans stay creator-private
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_leadership_gets_empty_assistant_plans(client):
    teacher = await _mk_school_teacher()
    await _mk_assistant_plan(
        workspace_id=teacher["tenant_id"],
        created_by=teacher["id"],
        class_id=teacher["class_id"],
        is_saved=True,
    )
    principal = await _mk_principal(teacher["tenant_id"])
    h = _headers(principal["id"], principal["role"], principal["tenant_id"])

    resp = await client.get(f"/class/{teacher['class_id']}/curriculum-plan", headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json().get("assistant_plans", []) == []


# ---------------------------------------------------------------------------
# (g) Subject filter must not hide assistant plans (fail-visible)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subject_filter_does_not_hide_assistant_plans(client):
    user = await _mk_school_teacher()
    saved = await _mk_assistant_plan(
        workspace_id=user["tenant_id"],
        created_by=user["id"],
        class_id=user["class_id"],
        is_saved=True,
        subject="التاريخ",
    )
    h = _headers(user["id"], user["role"], user["tenant_id"])
    resp = await client.get(
        f"/class/{user['class_id']}/curriculum-plan",
        params={"subject_id": user["subject_id"]},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    ids = {p["id"] for p in resp.json().get("assistant_plans", [])}
    assert saved in ids
