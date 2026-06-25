"""Regression: the teacher coverage-assignment notification ("تكليف بتغطية حصة")
must include the class name (اسم الفصل) even when the source timetable_sessions
record does not bake `class_name` in.

The modern schedule store resolves class/subject display names from the
`classes`/`subjects` collections at render time, so `timetable_sessions` rows
often carry only `class_id`/`subject_id`. The pre-fix
`/standby/notify-coverage` handler read `orig.get("class_name")` directly and
fell back to "—", so teachers received an incomplete assignment notice with no
destination class.

These tests lock in:

  1. When the session has `class_id` (and `subject_id`) but no baked name, the
     created notification's `message` and `metadata.class_name` resolve the real
     class name from the same-tenant `classes` collection.
  2. A `class_id` that points to a foreign tenant's class is NOT disclosed —
     it falls back to "—" (tenant-isolation guarantee).
"""
from __future__ import annotations

import uuid

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find_one, gd_insert
import routes.standby_routes as standby_routes


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


def _patch_eligibility(monkeypatch, teacher_id: str) -> None:
    """The route validates availability via score_candidates_for_slot; stub it
    to mark our substitute eligible without standing up the full roster."""
    async def _fake_score(*_args, **_kwargs):
        return {"candidates": [{"teacher_id": teacher_id}]}

    monkeypatch.setattr(standby_routes, "score_candidates_for_slot", _fake_score)


async def test_coverage_notification_includes_resolved_class_name(
    client, tenant_a, monkeypatch
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
    sess_id = await _mk_session(tenant_a, class_id=class_id, subject_id=subject_id)

    _patch_eligibility(monkeypatch, sub["teacher_id"])

    resp = await client.post(
        "/standby/notify-coverage",
        headers=_headers(principal),
        json={
            "original_session_id": sess_id,
            "substitute_teacher_id": sub["teacher_id"],
        },
    )
    assert resp.status_code == 201, resp.text
    notif_id = resp.json()["notification_id"]
    assert notif_id

    notif = await gd_find_one(db.session, "notifications", {"id": notif_id})
    assert notif is not None
    assert notif["title"] == "تكليف بتغطية حصة"
    # Class name is embedded in the human-readable message...
    assert "الصف السابع" in notif["message"]
    # ...and persisted in metadata at creation time (preferred over late joins).
    meta = notif.get("metadata") or {}
    assert meta.get("class_name") == "الصف السابع"
    assert meta.get("class_id") == class_id
    assert meta.get("subject_name") == "الرياضيات"


async def test_coverage_notification_does_not_disclose_foreign_class(
    client, tenant_a, tenant_b, monkeypatch
):
    principal = await _mk_principal(tenant_a)
    sub = await _mk_substitute_teacher(tenant_a)

    # Class belongs to ANOTHER tenant — the session references it by id but the
    # name must NOT leak into school A's notification.
    foreign_class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": foreign_class_id, "school_id": tenant_b, "name": "فصل مدرسة أخرى",
        "is_active": True,
    })
    sess_id = await _mk_session(tenant_a, class_id=foreign_class_id)

    _patch_eligibility(monkeypatch, sub["teacher_id"])

    resp = await client.post(
        "/standby/notify-coverage",
        headers=_headers(principal),
        json={
            "original_session_id": sess_id,
            "substitute_teacher_id": sub["teacher_id"],
        },
    )
    assert resp.status_code == 201, resp.text
    notif = await gd_find_one(
        db.session, "notifications", {"id": resp.json()["notification_id"]}
    )
    assert "فصل مدرسة أخرى" not in notif["message"]
    meta = notif.get("metadata") or {}
    assert meta.get("class_name") == "—"
