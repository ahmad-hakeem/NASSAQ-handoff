"""Regression: the waiting-lesson assignment notification ("إسناد حصة انتظار")
sent by the /substitutions (single) and /substitutions/bulk (batch) endpoints
must carry the same essential lesson data as the coverage notification
("تكليف بتغطية حصة"): day, period, time, and class name.

The modern schedule store resolves class/subject display names from the
`classes`/`subjects` collections at render time, so `timetable_sessions` rows
often carry only `class_id`/`subject_id`. The pre-fix `assign_substitute`
notification builders read `orig.get("class_name")` directly and fell back to
"—", so the assigned teacher received an incomplete notice with no class name.

These tests lock in:

  1. /substitutions: when the session has `class_id`/`subject_id` but no baked
     name, the notification's `message` and `metadata.class_name` resolve the
     real class name from the same-tenant `classes` collection.
  2. /substitutions: a `class_id` pointing to a foreign tenant's class is NOT
     disclosed — it falls back to "—" (tenant-isolation guarantee).
  3. /substitutions/bulk (single slot): the grouped notification likewise
     resolves and includes the class name.
"""
from __future__ import annotations

import uuid

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find_one, gd_insert


pytestmark = pytest.mark.asyncio


def _headers(user: dict) -> dict:
    token = create_access_token({
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_principal(tenant_id: str) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": tenant_id,
        "email": f"{uid}@t.test",
        "full_name": "Principal user",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


async def _mk_substitute_teacher(tenant_id: str) -> dict:
    """A teacher needs both a users row (recipient) and a teachers row."""
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.TEACHER.value,
        "tenant_id": tenant_id,
        "email": f"{uid}@t.test",
        "full_name": "Sub Teacher",
        "is_active": True,
        "password_hash": "x",
    })
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid,
        "school_id": tenant_id,
        "user_id": uid,
        "full_name": "Sub Teacher",
        "is_active": True,
    })
    return {"teacher_id": tid, "user_id": uid}


async def _mk_session(tenant_id: str, *, class_id, subject_id=None) -> str:
    sess_id = str(uuid.uuid4())
    await gd_insert(db.session, "timetable_sessions", {
        "id": sess_id,
        "school_id": tenant_id,
        "day_of_week": "wednesday",
        "period_number": 1,
        "class_id": class_id,
        "subject_id": subject_id,
        # NOTE: deliberately no class_name / subject_name baked in.
    })
    return sess_id


async def test_substitution_notification_includes_resolved_class_name(
    client, tenant_a
):
    principal = await _mk_principal(tenant_a)
    sub = await _mk_substitute_teacher(tenant_a)

    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id, "school_id": tenant_a, "name": "الصف السابع", "is_active": True,
    })
    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id, "school_id": tenant_a, "name": "Math",
        "name_ar": "الرياضيات", "is_active": True,
    })
    # A teaching time-slot so the period time resolves and is carried too.
    await gd_insert(db.session, "time_slots", {
        "id": str(uuid.uuid4()), "school_id": tenant_a, "name": "الحصة الأولى",
        "slot_number": 1, "start_time": "08:00", "end_time": "08:45",
        "is_break": False, "is_active": True,
    })
    sess_id = await _mk_session(tenant_a, class_id=class_id, subject_id=subject_id)

    resp = await client.post(
        "/substitutions",
        headers=_headers(principal),
        json={
            "original_session_id": sess_id,
            "substitute_teacher_id": sub["teacher_id"],
        },
    )
    assert resp.status_code == 201, resp.text
    notif_id = (resp.json().get("substitution") or {}).get("notification_id")
    assert notif_id

    notif = await gd_find_one(db.session, "notifications", {"id": notif_id})
    assert notif is not None
    assert notif["title"] == "إسناد حصة انتظار جديدة"
    # Class name + time are embedded in the human-readable message...
    assert "الصف السابع" in notif["message"]
    assert "08:00 - 08:45" in notif["message"]
    # ...and persisted in metadata at creation time.
    meta = notif.get("metadata") or {}
    assert meta.get("class_name") == "الصف السابع"
    assert meta.get("class_id") == class_id
    assert meta.get("subject_name") == "الرياضيات"
    assert meta.get("period_time") == "08:00 - 08:45"


async def test_substitution_notification_does_not_disclose_foreign_class(
    client, tenant_a, tenant_b
):
    principal = await _mk_principal(tenant_a)
    sub = await _mk_substitute_teacher(tenant_a)

    # Class + subject belong to ANOTHER tenant — the session references them by
    # id but neither name must leak into school A's notification.
    foreign_class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": foreign_class_id, "school_id": tenant_b, "name": "فصل مدرسة أخرى",
        "is_active": True,
    })
    foreign_subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": foreign_subject_id, "school_id": tenant_b, "name": "Secret",
        "name_ar": "مادة مدرسة أخرى", "is_active": True,
    })
    sess_id = await _mk_session(
        tenant_a, class_id=foreign_class_id, subject_id=foreign_subject_id
    )

    resp = await client.post(
        "/substitutions",
        headers=_headers(principal),
        json={
            "original_session_id": sess_id,
            "substitute_teacher_id": sub["teacher_id"],
        },
    )
    assert resp.status_code == 201, resp.text
    notif_id = (resp.json().get("substitution") or {}).get("notification_id")
    assert notif_id

    notif = await gd_find_one(db.session, "notifications", {"id": notif_id})
    assert "فصل مدرسة أخرى" not in notif["message"]
    assert "مادة مدرسة أخرى" not in notif["message"]
    meta = notif.get("metadata") or {}
    assert meta.get("class_name") == "—"
    assert not meta.get("subject_name")


async def test_bulk_substitution_notification_includes_resolved_class_name(
    client, tenant_a
):
    principal = await _mk_principal(tenant_a)
    sub = await _mk_substitute_teacher(tenant_a)

    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id, "school_id": tenant_a, "name": "الصف الثامن", "is_active": True,
    })
    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id, "school_id": tenant_a, "name": "Science",
        "name_ar": "العلوم", "is_active": True,
    })
    sess_id = await _mk_session(tenant_a, class_id=class_id, subject_id=subject_id)

    resp = await client.post(
        "/substitutions/bulk",
        headers=_headers(principal),
        json={
            "items": [{
                "original_session_id": sess_id,
                "substitute_teacher_id": sub["teacher_id"],
            }],
        },
    )
    assert resp.status_code == 201, resp.text
    results = resp.json().get("results") or []
    assert len(results) == 1 and results[0].get("success")
    notif_id = (results[0].get("substitution") or {}).get("notification_id")
    assert notif_id

    notif = await gd_find_one(db.session, "notifications", {"id": notif_id})
    assert notif is not None
    assert notif["title"] == "إسناد حصة انتظار جديدة"
    assert "الصف الثامن" in notif["message"]
    meta = notif.get("metadata") or {}
    assert meta.get("class_name") == "الصف الثامن"
    assert meta.get("class_id") == class_id
    assert meta.get("subject_name") == "العلوم"
