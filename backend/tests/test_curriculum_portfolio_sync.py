"""
Integration tests for the Curriculum-Plan → Portfolio (Planning Evidence) sync.

When a teacher adds / edits / deletes lessons in their curriculum plan, an auto
"خطة توزيع المنهج" portfolio card (evidence_type=curriculum_distribution_plan)
must stay in sync — one card per (class, subject), showing the live lesson count.

Covers:
  (1) Add lesson → auto card created with lesson_count=1; a second add upserts
      the SAME card to lesson_count=2 (never a duplicate).
  (2) Marking a lesson complete bumps completed_count; deleting lessons drops the
      count and removes the card once the plan is empty.
  (3) A teacher's own manually-added planning card (source=manual, no
      source_entity_id) is never touched by the auto-sync.
"""

import uuid
from datetime import timezone, datetime

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find_one, gd_count
from auth_scope import independent_workspace_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({"sub": user_id, "role": role, "tenant_id": tenant_id})
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
        "name": f"IT-Workspace-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    return user


async def _mk_subject(school_id: str, name: str = "الرياضيات") -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid,
        "school_id": school_id,
        "tenant_id": school_id,
        "name": name,
        "is_active": True,
    })
    return sid


async def _mk_class(school_id: str, subject_id: str = None) -> str:
    cid = str(uuid.uuid4())
    doc = {
        "id": cid,
        "school_id": school_id,
        "tenant_id": school_id,
        "name": f"C-{cid[:6]}",
        "capacity": 20,
        "current_students": 0,
        "is_active": True,
    }
    if subject_id:
        doc["subject_id"] = subject_id
    await gd_insert(db.session, "classes", doc)
    return cid


async def _add_lesson(client, cid: str, h: dict, title: str, subject_id: str = None) -> dict:
    url = f"/class/{cid}/curriculum-plan/lesson"
    if subject_id:
        url += f"?subject_id={subject_id}"
    resp = await client.post(url, json={"title": title, "week": 1, "order": 1}, headers=h)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _plan_filter(teacher_id: str, class_id: str, subject_id: str) -> dict:
    return {
        "teacher_id": teacher_id,
        "evidence_type": "curriculum_distribution_plan",
        "source_entity_id": f"curriculum_plan:{class_id}:{subject_id or ''}",
    }


# ---------------------------------------------------------------------------
# (1) Add → create + upsert (no duplicates)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_lesson_creates_then_upserts_plan_evidence(client):
    user = await _mk_it_user()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    subject_id = await _mk_subject(wsid)
    cid = await _mk_class(wsid, subject_id)

    flt = _plan_filter(user["id"], cid, subject_id)
    assert await gd_count(db.session, "portfolio_evidence", flt) == 0

    await _add_lesson(client, cid, h, "الدرس الأول", subject_id)
    ev = await gd_find_one(db.session, "portfolio_evidence", flt)
    assert ev is not None
    assert ev["source"] == "auto"
    assert ev["evidence_type"] == "curriculum_distribution_plan"
    assert ev["metadata"]["lesson_count"] == 1
    assert ev["metadata"]["completed_count"] == 0
    assert "عدد الدروس: 1" in ev["description_ar"]

    await _add_lesson(client, cid, h, "الدرس الثاني", subject_id)
    ev2 = await gd_find_one(db.session, "portfolio_evidence", flt)
    assert ev2["id"] == ev["id"]  # same card upserted, not a duplicate
    assert ev2["metadata"]["lesson_count"] == 2
    assert await gd_count(db.session, "portfolio_evidence", flt) == 1


# ---------------------------------------------------------------------------
# (2) Complete bumps completed_count; delete drops count then removes card
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_and_delete_keep_plan_evidence_in_sync(client):
    user = await _mk_it_user()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    subject_id = await _mk_subject(wsid)
    cid = await _mk_class(wsid, subject_id)
    flt = _plan_filter(user["id"], cid, subject_id)

    l1 = await _add_lesson(client, cid, h, "الدرس الأول", subject_id)
    l2 = await _add_lesson(client, cid, h, "الدرس الثاني", subject_id)

    r = await client.put(f"/curriculum-lesson/{l1['id']}", json={"is_completed": True}, headers=h)
    assert r.status_code == 200, r.text
    ev = await gd_find_one(db.session, "portfolio_evidence", flt)
    assert ev["metadata"]["lesson_count"] == 2
    assert ev["metadata"]["completed_count"] == 1
    assert "الدروس المكتملة: 1" in ev["description_ar"]

    assert (await client.delete(f"/curriculum-lesson/{l1['id']}", headers=h)).status_code == 200
    ev = await gd_find_one(db.session, "portfolio_evidence", flt)
    assert ev["metadata"]["lesson_count"] == 1
    assert ev["metadata"]["completed_count"] == 0

    assert (await client.delete(f"/curriculum-lesson/{l2['id']}", headers=h)).status_code == 200
    assert await gd_count(db.session, "portfolio_evidence", flt) == 0


# ---------------------------------------------------------------------------
# (3) Manual planning card is never touched by the auto-sync
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manual_planning_card_is_preserved(client):
    user = await _mk_it_user()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    subject_id = await _mk_subject(wsid)
    cid = await _mk_class(wsid, subject_id)

    manual_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "portfolio_evidence", {
        "id": manual_id,
        "teacher_id": user["id"],
        "school_id": wsid,
        "evidence_type": "curriculum_distribution_plan",
        "title_ar": "خطة توزيع المنهج للمعلم",
        "source": "manual",
        "source_entity_id": None,
        "created_at": now,
        "updated_at": now,
    })

    l1 = await _add_lesson(client, cid, h, "الدرس الأول", subject_id)
    # Auto card added; manual card untouched.
    assert await gd_find_one(db.session, "portfolio_evidence", {"id": manual_id}) is not None
    assert await gd_count(db.session, "portfolio_evidence", _plan_filter(user["id"], cid, subject_id)) == 1

    # Emptying the plan removes the AUTO card but leaves the manual one.
    assert (await client.delete(f"/curriculum-lesson/{l1['id']}", headers=h)).status_code == 200
    assert await gd_find_one(db.session, "portfolio_evidence", {"id": manual_id}) is not None
    assert await gd_count(db.session, "portfolio_evidence", _plan_filter(user["id"], cid, subject_id)) == 0
