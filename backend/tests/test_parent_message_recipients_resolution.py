"""
Parent Communication Center — teacher recipient RESOLUTION rules.

`GET /parent-portal/message-recipients/teachers` must return exactly the
teachers who currently teach the parent's child — no more, no less:

1. The displayed name comes from the authoritative ``teachers`` row (the row
   every other academic surface renders), not from a divergent ``users``
   row — otherwise the parent sees an unrecognisable stranger in the list.
2. A teacher whose ``users`` row was provisioned without ``tenant_id``
   (legacy accounts) must still be reachable: the tenant proof is the
   school-pinned ``teachers`` row, not the nullable user column.
3. A ``users`` row belonging to a DIFFERENT tenant stays excluded (fail
   closed) even if a local teachers row points at it.
4. A cancelled period is not teaching, so it grants nothing — but several
   legitimate ``schedule_sessions`` generations (independent-teacher weekly
   schedules) all count; picking a single "newest" one would hide a real
   teacher.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_insert


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


async def _mk_child(tenant_id, class_id, *, parent_user_id, name="طالب") -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": tenant_id, "tenant_id": tenant_id,
        "full_name": name, "class_id": class_id, "is_active": True,
    })
    await gd_insert(db.session, "guardian_links", {
        "id": str(uuid.uuid4()), "tenant_id": tenant_id,
        "student_id": sid, "parent_user_id": parent_user_id, "is_active": True,
    })
    return sid


async def _mk_teacher(school_id, *, teachers_name, user_id=None,
                      user_tenant="__same__", user_name=None) -> tuple:
    """Create a teachers row (pinned to ``school_id``) + its users row.

    ``user_tenant`` defaults to the school; pass ``None`` for the legacy
    provisioning gap or another tenant id for the cross-tenant guard.
    """
    if user_id is None:
        tenant = school_id if user_tenant == "__same__" else user_tenant
        user_id = await _mk_user("teacher", tenant, name=user_name or teachers_name)
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "school_id": school_id, "user_id": user_id,
        "full_name": teachers_name, "is_active": True,
    })
    return teacher_id, user_id


async def _mk_schedule_session(school_id, class_id, teacher_id, *,
                               schedule_id=None, created_at=None, status="scheduled"):
    await gd_insert(db.session, "schedule_sessions", {
        "id": str(uuid.uuid4()), "school_id": school_id,
        "schedule_id": schedule_id or str(uuid.uuid4()),
        "class_id": class_id, "teacher_id": teacher_id,
        "day_of_week": "sunday", "slot_number": 1, "status": status,
        "created_at": created_at or datetime.now(timezone.utc),
    })


async def _recipients(client, parent, tenant):
    resp = await client.get("/parent-portal/message-recipients/teachers",
                            headers=_headers(parent, "parent", tenant))
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------- 1) display name comes from the authoritative teachers row ----------

@pytest.mark.asyncio
async def test_recipient_name_uses_authoritative_teacher_row(client, tenant_a):
    """The users row may carry a stale/divergent name ("Aisha") while the
    teachers row is the name shown on every other academic screen."""
    parent = await _mk_user("parent", tenant_a, name="ولي الأمر")
    class_id = await _mk_class(tenant_a, "أول-أ")
    child = await _mk_child(tenant_a, class_id, parent_user_id=parent, name="رائد")
    teacher_id, teacher_user = await _mk_teacher(
        tenant_a, teachers_name="أحمد المعلم", user_name="Aisha")
    await _mk_schedule_session(tenant_a, class_id, teacher_id)

    body = await _recipients(client, parent, tenant_a)
    rows = {t["recipient_user_id"]: t for t in body["teachers"]}
    assert teacher_user in rows
    assert rows[teacher_user]["teacher_name"] == "أحمد المعلم"
    assert rows[teacher_user]["child_ids"] == [child]


# ---------- 2) legacy teacher user without tenant_id stays reachable ----------

@pytest.mark.asyncio
async def test_teacher_user_without_tenant_is_still_a_recipient(client, tenant_a):
    """The school-pinned teachers row is the tenant proof; a legacy users row
    provisioned without tenant_id must not silently vanish from the list."""
    parent = await _mk_user("parent", tenant_a, name="ولي الأمر")
    class_id = await _mk_class(tenant_a, "أول-أ")
    child = await _mk_child(tenant_a, class_id, parent_user_id=parent, name="رائد")
    teacher_id, teacher_user = await _mk_teacher(
        tenant_a, teachers_name="سعد", user_tenant=None)
    await _mk_schedule_session(tenant_a, class_id, teacher_id)

    body = await _recipients(client, parent, tenant_a)
    rows = {t["recipient_user_id"]: t for t in body["teachers"]}
    assert teacher_user in rows, "teacher of the child's class dropped from recipients"
    assert rows[teacher_user]["child_ids"] == [child]

    # ...and the parent can actually send to them.
    resp = await client.post("/parent-portal/quick-message",
                             json={"content": "سؤال عن الرياضيات",
                                   "recipient_type": "teacher",
                                   "recipient_user_id": teacher_user,
                                   "student_id": child},
                             headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, resp.text


# ---------- 3) cross-tenant user stays excluded ----------

@pytest.mark.asyncio
async def test_teacher_user_from_other_tenant_excluded(client, tenant_a, tenant_b):
    parent = await _mk_user("parent", tenant_a, name="ولي الأمر")
    class_id = await _mk_class(tenant_a, "أول-أ")
    await _mk_child(tenant_a, class_id, parent_user_id=parent, name="رائد")
    _, foreign_user = await _mk_teacher(
        tenant_a, teachers_name="معلم مدرسة أخرى", user_tenant=tenant_b)
    foreign_teacher_id, _ = await _mk_teacher(
        tenant_a, teachers_name="معلم مدرسة أخرى", user_id=foreign_user)
    await _mk_schedule_session(tenant_a, class_id, foreign_teacher_id)

    body = await _recipients(client, parent, tenant_a)
    assert foreign_user not in {t["recipient_user_id"] for t in body["teachers"]}

    # ...and hand-crafting the id into the send call is rejected too.
    resp = await client.post("/parent-portal/quick-message",
                             json={"content": "محاولة مراسلة",
                                   "recipient_type": "teacher",
                                   "recipient_user_id": foreign_user},
                             headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 400, resp.text


# ---------- 4) cancelled grants nothing, parallel generations all count ----------

@pytest.mark.asyncio
async def test_parallel_schedule_generations_all_count(client, tenant_a):
    """Independent-teacher workspaces store one schedule generation per week,
    so a teacher present only in another generation of the SAME class is a
    genuine teacher of the child — never filtered out as "stale"."""
    parent = await _mk_user("parent", tenant_a, name="ولي الأمر")
    class_id = await _mk_class(tenant_a, "أول-أ")
    await _mk_child(tenant_a, class_id, parent_user_id=parent, name="رائد")
    week1_teacher, week1_user = await _mk_teacher(tenant_a, teachers_name="معلم الأسبوع الأول")
    week2_teacher, week2_user = await _mk_teacher(tenant_a, teachers_name="معلم الأسبوع الثاني")
    now = datetime.now(timezone.utc)
    await _mk_schedule_session(tenant_a, class_id, week1_teacher,
                               schedule_id=str(uuid.uuid4()),
                               created_at=now - timedelta(days=7))
    await _mk_schedule_session(tenant_a, class_id, week2_teacher,
                               schedule_id=str(uuid.uuid4()), created_at=now)

    body = await _recipients(client, parent, tenant_a)
    user_ids = {t["recipient_user_id"] for t in body["teachers"]}
    assert week1_user in user_ids
    assert week2_user in user_ids


@pytest.mark.asyncio
async def test_cancelled_session_alone_does_not_grant_recipient(client, tenant_a):
    parent = await _mk_user("parent", tenant_a, name="ولي الأمر")
    class_id = await _mk_class(tenant_a, "أول-أ")
    await _mk_child(tenant_a, class_id, parent_user_id=parent, name="رائد")
    teacher_id, teacher_user = await _mk_teacher(tenant_a, teachers_name="معلم ملغى")
    schedule_id = str(uuid.uuid4())
    await _mk_schedule_session(tenant_a, class_id, teacher_id,
                               schedule_id=schedule_id, status="cancelled")

    body = await _recipients(client, parent, tenant_a)
    assert teacher_user not in {t["recipient_user_id"] for t in body["teachers"]}


@pytest.mark.asyncio
async def test_teacher_of_another_class_not_disclosed(client, tenant_a):
    """Core rule: same school, different class → never a recipient."""
    parent = await _mk_user("parent", tenant_a, name="ولي الأمر")
    my_class = await _mk_class(tenant_a, "أول-أ")
    other_class = await _mk_class(tenant_a, "ثاني-ب")
    await _mk_child(tenant_a, my_class, parent_user_id=parent, name="رائد")
    mine, mine_user = await _mk_teacher(tenant_a, teachers_name="معلم ابني")
    theirs, theirs_user = await _mk_teacher(tenant_a, teachers_name="معلم فصل آخر")
    await _mk_schedule_session(tenant_a, my_class, mine)
    await _mk_schedule_session(tenant_a, other_class, theirs)

    body = await _recipients(client, parent, tenant_a)
    user_ids = {t["recipient_user_id"] for t in body["teachers"]}
    assert mine_user in user_ids
    assert theirs_user not in user_ids
