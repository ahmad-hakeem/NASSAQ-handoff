"""
Parent Communication Center — child-first messaging
(spec: docs/superpowers/specs/2026-07-10-parent-comm-child-context.md)

1. `GET /parent-portal/message-recipients/teachers` returns the parent's
   children plus, per teacher, the `child_ids` that teacher actually teaches.
2. `POST /parent-portal/quick-message` requires `student_id`, validates it is
   the caller's own child, and (for teacher recipients) that the chosen
   teacher teaches THAT child. The stored message carries the student context
   and is delivered to the recipient's `/communication/received` inbox
   (audience="custom"), and the notification carries the full body.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_find, gd_find_one, gd_insert


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


async def _mk_class(tenant_id, name="1A") -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": tenant_id, "tenant_id": tenant_id, "name": name,
    })
    return cid


async def _mk_student(tenant_id, class_id, *, parent_user_id, name="S") -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": tenant_id, "tenant_id": tenant_id,
        "full_name": name, "class_id": class_id, "is_active": True,
    })
    await gd_insert(db.session, "guardian_links", {
        "id": str(uuid.uuid4()), "tenant_id": tenant_id,
        "student_id": sid, "parent_user_id": parent_user_id,
        "is_active": True,
    })
    return sid


async def _mk_teacher(tenant_id, name) -> tuple:
    user_id = await _mk_user("teacher", tenant_id, name=name)
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "school_id": tenant_id, "user_id": user_id,
        "full_name": name, "is_active": True,
    })
    return teacher_id, user_id


async def _mk_schedule_session(tenant_id, class_id, teacher_id):
    await gd_insert(db.session, "schedule_sessions", {
        "id": str(uuid.uuid4()), "school_id": tenant_id,
        "schedule_id": str(uuid.uuid4()),
        "class_id": class_id, "teacher_id": teacher_id,
        "day_of_week": "sunday", "slot_number": 1, "status": "scheduled",
    })


async def _two_children_two_teachers(tenant):
    """Parent with two children in two classes, each class taught by its own
    teacher. Returns (parent, child_a, child_b, teacher_a_user, teacher_b_user)."""
    parent = await _mk_user("parent", tenant, name="ولي الأمر")
    class_a = await _mk_class(tenant, "أول-أ")
    class_b = await _mk_class(tenant, "ثاني-ب")
    child_a = await _mk_student(tenant, class_a, parent_user_id=parent, name="أحمد")
    child_b = await _mk_student(tenant, class_b, parent_user_id=parent, name="بدر")
    ta_id, ta_user = await _mk_teacher(tenant, "معلم أ")
    tb_id, tb_user = await _mk_teacher(tenant, "معلم ب")
    await _mk_schedule_session(tenant, class_a, ta_id)
    await _mk_schedule_session(tenant, class_b, tb_id)
    return parent, child_a, child_b, ta_user, tb_user


# ---------- 1) recipients endpoint: children + child_ids ----------

@pytest.mark.asyncio
async def test_recipients_endpoint_returns_children_and_child_ids(client, tenant_a):
    parent, child_a, child_b, ta_user, tb_user = await _two_children_two_teachers(tenant_a)

    resp = await client.get("/parent-portal/message-recipients/teachers",
                            headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    children = {c["student_id"]: c["name"] for c in body.get("children", [])}
    assert children.get(child_a) == "أحمد"
    assert children.get(child_b) == "بدر"

    teachers = {t["recipient_user_id"]: t for t in body.get("teachers", [])}
    assert teachers[ta_user].get("child_ids") == [child_a]
    assert teachers[tb_user].get("child_ids") == [child_b]


@pytest.mark.asyncio
async def test_children_include_child_without_class(client, tenant_a):
    """A child with no class (no teachers) must still be selectable for the
    admin flow."""
    parent = await _mk_user("parent", tenant_a)
    unassigned = await _mk_student(tenant_a, None, parent_user_id=parent, name="بلا فصل")

    resp = await client.get("/parent-portal/message-recipients/teachers",
                            headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, resp.text
    ids = {c["student_id"] for c in resp.json().get("children", [])}
    assert unassigned in ids


# ---------- 2) quick-message validation ----------

@pytest.mark.asyncio
async def test_quick_message_requires_student_id(client, tenant_a):
    parent = await _mk_user("parent", tenant_a)
    await _mk_user("school_admin", tenant_a)

    resp = await client.post("/parent-portal/quick-message",
                             json={"content": "بدون طالب", "recipient_type": "admin"},
                             headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_quick_message_rejects_foreign_student(client, tenant_a, tenant_b):
    parent = await _mk_user("parent", tenant_a)
    await _mk_user("school_admin", tenant_a)
    other_parent = await _mk_user("parent", tenant_b)
    class_b = await _mk_class(tenant_b)
    foreign_child = await _mk_student(tenant_b, class_b, parent_user_id=other_parent)

    resp = await client.post("/parent-portal/quick-message",
                             json={"content": "x", "recipient_type": "admin",
                                   "student_id": foreign_child},
                             headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_quick_message_rejects_teacher_not_teaching_that_child(client, tenant_a):
    """Teacher B teaches child B only — sending about child A must fail."""
    parent, child_a, child_b, ta_user, tb_user = await _two_children_two_teachers(tenant_a)

    resp = await client.post("/parent-portal/quick-message",
                             json={"content": "x", "recipient_type": "teacher",
                                   "recipient_user_id": tb_user,
                                   "student_id": child_a},
                             headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 400, resp.text


# ---------- 3) persistence + delivery ----------

@pytest.mark.asyncio
async def test_quick_message_stores_student_context_and_custom_audience(client, tenant_a):
    parent, child_a, child_b, ta_user, tb_user = await _two_children_two_teachers(tenant_a)

    resp = await client.post("/parent-portal/quick-message",
                             json={"content": "ابني يحتاج متابعة", "message_type": "note",
                                   "recipient_type": "teacher",
                                   "recipient_user_id": ta_user,
                                   "student_id": child_a},
                             headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, resp.text

    msg = await gd_find_one(db.session, "messages",
                            {"sender_id": parent, "receiver_id": ta_user})
    assert msg is not None
    assert msg.get("student_id") == child_a
    assert msg.get("student_name") == "أحمد"
    assert "أحمد" in (msg.get("subject") or "")
    assert msg.get("title") == msg.get("subject")
    assert msg.get("audience") == "custom"
    assert msg.get("audience_ids") == [ta_user]
    assert msg.get("sent_at")

    notif = await gd_find_one(db.session, "notifications", {"user_id": ta_user})
    assert notif is not None
    assert "أحمد" in (notif.get("title") or "")
    assert "ابني يحتاج متابعة" in (notif.get("message") or "")


@pytest.mark.asyncio
async def test_quick_message_visible_in_receiver_inbox_only(client, tenant_a):
    parent, child_a, child_b, ta_user, tb_user = await _two_children_two_teachers(tenant_a)

    resp = await client.post("/parent-portal/quick-message",
                             json={"content": "رسالة للمعلم أ", "message_type": "inquiry",
                                   "recipient_type": "teacher",
                                   "recipient_user_id": ta_user,
                                   "student_id": child_a},
                             headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, resp.text

    inbox_a = await client.get("/communication/received",
                               headers=_headers(ta_user, "teacher", tenant_a))
    assert inbox_a.status_code == 200, inbox_a.text
    contents_a = [m.get("content") for m in inbox_a.json().get("messages", [])]
    assert "رسالة للمعلم أ" in contents_a

    inbox_b = await client.get("/communication/received",
                               headers=_headers(tb_user, "teacher", tenant_a))
    assert inbox_b.status_code == 200, inbox_b.text
    contents_b = [m.get("content") for m in inbox_b.json().get("messages", [])]
    assert "رسالة للمعلم أ" not in contents_b


@pytest.mark.asyncio
async def test_quick_message_to_admin_with_student_context(client, tenant_a):
    parent = await _mk_user("parent", tenant_a)
    admin = await _mk_user("school_principal", tenant_a)
    class_id = await _mk_class(tenant_a)
    child = await _mk_student(tenant_a, class_id, parent_user_id=parent, name="سارة")

    resp = await client.post("/parent-portal/quick-message",
                             json={"content": "استفسار عن الرسوم", "message_type": "inquiry",
                                   "recipient_type": "admin",
                                   "student_id": child},
                             headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, resp.text

    msg = await gd_find_one(db.session, "messages",
                            {"sender_id": parent, "receiver_id": admin})
    assert msg is not None
    assert msg.get("student_name") == "سارة"
    assert msg.get("audience_ids") == [admin]

    inbox = await client.get("/communication/received",
                             headers=_headers(admin, "school_principal", tenant_a))
    assert inbox.status_code == 200, inbox.text
    contents = [m.get("content") for m in inbox.json().get("messages", [])]
    assert "استفسار عن الرسوم" in contents


@pytest.mark.asyncio
async def test_parent_inbox_read_model_surfaces_student_name(client, tenant_a):
    parent, child_a, child_b, ta_user, tb_user = await _two_children_two_teachers(tenant_a)

    await client.post("/parent-portal/quick-message",
                      json={"content": "متابعة", "message_type": "note",
                            "recipient_type": "teacher",
                            "recipient_user_id": ta_user,
                            "student_id": child_a},
                      headers=_headers(parent, "parent", tenant_a))

    resp = await client.get("/parent-portal/messages",
                            headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, resp.text
    names = [m.get("student_name") for m in resp.json().get("messages", [])]
    assert "أحمد" in names
