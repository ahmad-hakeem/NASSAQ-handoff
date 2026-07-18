"""
Parent Communication Center — Independent-Teacher workspace routing.

Root causes covered (systematic-debugging session 2026-07-18):

1. `GET /parent-portal/message-recipients/teachers` resolved the recipient
   user with a hard ``role == "teacher"`` filter, so the workspace owner
   (role ``independent_teacher``) never appeared → the parent UI showed
   "لا يوجد معلمون متاحون للمراسلة حالياً" even though the IT teaches the child.
2. `POST /parent-portal/quick-message` with ``recipient_type="admin"``
   resolved administration via ``school_principal``/``school_admin`` only —
   roles that never exist inside an IT workspace → 503 and a generic
   "حدث خطأ أثناء الإرسال" popup. In an IT workspace the workspace owner IS
   the administration.

Also pins the fail-closed behaviour: a REAL school with no active
principal/admin still gets 503 (no silent fallback to arbitrary users).
"""
import uuid

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_find, gd_insert


def _headers(user_id: str, role: str, tenant_id):
    token = create_access_token({"sub": user_id, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


async def _mk_user(role: str, tenant_id, name=None) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": role, "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test", "full_name": name or f"{role}-{uid[:6]}",
        "is_active": True, "password_hash": "x",
    })
    return uid


async def _mk_it_workspace() -> tuple:
    """IT workspace: schools row flagged independent_teacher + owner user +
    authoritative teachers row (mirrors real IT bootstrap)."""
    owner_uid = str(uuid.uuid4())
    tenant = f"itw_{owner_uid}"
    await gd_insert(db.session, "schools", {
        "id": tenant,
        "name": "مساحة معلم مستقل",
        "code": f"IT{owner_uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher",
        "tenant_type": "independent_teacher",
    })
    await gd_insert(db.session, "users", {
        "id": owner_uid, "role": "independent_teacher", "tenant_id": tenant,
        "email": f"it-{owner_uid}@t.test", "full_name": "المعلم المستقل",
        "is_active": True, "password_hash": "x",
    })
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "school_id": tenant, "user_id": owner_uid,
        "full_name": "المعلم المستقل", "is_active": True,
    })
    return tenant, owner_uid, teacher_id


async def _mk_classed_child(tenant, teacher_id, parent_user_id, name="طالب"):
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": tenant, "tenant_id": tenant, "name": "فصل-أ",
    })
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": tenant, "tenant_id": tenant,
        "full_name": name, "class_id": cid, "is_active": True,
    })
    await gd_insert(db.session, "guardian_links", {
        "id": str(uuid.uuid4()), "tenant_id": tenant,
        "student_id": sid, "parent_user_id": parent_user_id,
        "is_active": True,
    })
    await gd_insert(db.session, "schedule_sessions", {
        "id": str(uuid.uuid4()), "school_id": tenant,
        "schedule_id": str(uuid.uuid4()),
        "class_id": cid, "teacher_id": teacher_id,
        "day_of_week": "sunday", "slot_number": 1, "status": "scheduled",
    })
    return sid


# ---------- 1) IT appears in the parent's teacher recipient list ----------

@pytest.mark.asyncio
async def test_it_owner_listed_as_teacher_recipient(client):
    tenant, owner_uid, teacher_id = await _mk_it_workspace()
    parent = await _mk_user("parent", tenant, name="ولي الأمر")
    child = await _mk_classed_child(tenant, teacher_id, parent)

    resp = await client.get("/parent-portal/message-recipients/teachers",
                            headers=_headers(parent, "parent", tenant))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    teachers = {t["recipient_user_id"]: t for t in body.get("teachers", [])}
    assert owner_uid in teachers, "IT workspace owner must be a messageable teacher"
    assert child in (teachers[owner_uid].get("child_ids") or [])


# ---------- 2) quick-message → teacher (the IT) succeeds ----------

@pytest.mark.asyncio
async def test_quick_message_to_it_teacher_succeeds(client):
    tenant, owner_uid, teacher_id = await _mk_it_workspace()
    parent = await _mk_user("parent", tenant, name="ولي الأمر")
    child = await _mk_classed_child(tenant, teacher_id, parent)

    resp = await client.post("/parent-portal/quick-message",
                             headers=_headers(parent, "parent", tenant),
                             json={
                                 "recipient_type": "teacher",
                                 "recipient_user_id": owner_uid,
                                 "student_id": child,
                                 "message_type": "note",
                                 "content": "رسالة إلى المعلم المستقل",
                             })
    assert resp.status_code == 200, resp.text

    msgs = await gd_find(db.session, "messages",
                         {"school_id": tenant, "sender_id": parent})
    assert len(msgs) == 1
    assert msgs[0].get("receiver_id") == owner_uid
    assert msgs[0].get("audience") == "custom"
    assert owner_uid in (msgs[0].get("audience_ids") or [])


# ---------- 3) quick-message → administration routes to the IT owner ----------

@pytest.mark.asyncio
async def test_quick_message_to_admin_routes_to_it_owner(client):
    tenant, owner_uid, teacher_id = await _mk_it_workspace()
    parent = await _mk_user("parent", tenant, name="ولي الأمر")
    child = await _mk_classed_child(tenant, teacher_id, parent)

    resp = await client.post("/parent-portal/quick-message",
                             headers=_headers(parent, "parent", tenant),
                             json={
                                 "recipient_type": "admin",
                                 "student_id": child,
                                 "message_type": "inquiry",
                                 "content": "رسالة إلى الإدارة",
                             })
    assert resp.status_code == 200, resp.text

    msgs = await gd_find(db.session, "messages",
                         {"school_id": tenant, "sender_id": parent})
    assert len(msgs) == 1
    assert msgs[0].get("receiver_id") == owner_uid, \
        "admin path in an IT workspace must resolve to the workspace owner"


# ---------- 4) real school without principal/admin stays fail-closed ----------

@pytest.mark.asyncio
async def test_real_school_without_admin_still_503(client, tenant_a):
    parent = await _mk_user("parent", tenant_a, name="ولي الأمر")
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": tenant_a, "tenant_id": tenant_a,
        "full_name": "طالب", "is_active": True,
    })
    await gd_insert(db.session, "guardian_links", {
        "id": str(uuid.uuid4()), "tenant_id": tenant_a,
        "student_id": sid, "parent_user_id": parent,
        "is_active": True,
    })

    resp = await client.post("/parent-portal/quick-message",
                             headers=_headers(parent, "parent", tenant_a),
                             json={
                                 "recipient_type": "admin",
                                 "student_id": sid,
                                 "message_type": "note",
                                 "content": "رسالة",
                             })
    assert resp.status_code == 503, resp.text


@pytest.mark.asyncio
async def test_real_school_with_stray_it_user_still_503(client, tenant_a):
    """The IT-owner admin fallback is gated on the SCHOOLS-row discriminator,
    not on user roles: a real school containing a stray active
    ``independent_teacher`` user must still fail closed (503)."""
    await _mk_user("independent_teacher", tenant_a, name="دخيل")
    parent = await _mk_user("parent", tenant_a, name="ولي الأمر")
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": tenant_a, "tenant_id": tenant_a,
        "full_name": "طالب", "is_active": True,
    })
    await gd_insert(db.session, "guardian_links", {
        "id": str(uuid.uuid4()), "tenant_id": tenant_a,
        "student_id": sid, "parent_user_id": parent,
        "is_active": True,
    })

    resp = await client.post("/parent-portal/quick-message",
                             headers=_headers(parent, "parent", tenant_a),
                             json={
                                 "recipient_type": "admin",
                                 "student_id": sid,
                                 "message_type": "note",
                                 "content": "رسالة",
                             })
    assert resp.status_code == 503, resp.text
