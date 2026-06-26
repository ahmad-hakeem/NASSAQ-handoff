"""Regression: the principal "تكليف وإرسال إشعار" coverage action
(`POST /standby/notify-coverage`, driven by CoverageNotifyControl) must PERSIST
a real `substitute_assignments` row — not merely send a notification.

Root cause of the reported bug
------------------------------
The teacher-facing standby roster (`GET /standby/roster/me`) only marks a slot
as "assigned" (and resolves its real class name) when a matching
`substitute_assignments` row exists for the current ISO week. The pre-fix
notify-coverage handler emitted a notification but never wrote that row, so the
teacher's "حصص الانتظار" table kept showing "بانتظار الإسناد" for every slot the
principal had already assigned — even though the notification arrived.

These tests lock in:
  1. A successful notify-coverage call creates exactly one assignment row for
     the substitute, carrying the slot (day/period) and the source class_id so
     the roster's class-name fallback can resolve the destination class.
  2. The action still sends exactly ONE notification to the substitute teacher
     (the rich coverage notice), i.e. wiring in persistence did not introduce a
     duplicate notification.
"""
from __future__ import annotations

import uuid

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find
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
    await db_insert("users", user)
    return user


async def db_insert(collection: str, doc: dict) -> None:
    from engines.sql_utils import gd_insert
    await gd_insert(db.session, collection, doc)


async def _mk_substitute_teacher(tenant_id: str) -> dict:
    uid = str(uuid.uuid4())
    await db_insert("users", {
        "id": uid,
        "role": UserRole.TEACHER.value,
        "tenant_id": tenant_id,
        "email": f"{uid}@t.test",
        "full_name": "Sub Teacher",
        "is_active": True,
        "password_hash": "x",
    })
    tid = str(uuid.uuid4())
    await db_insert("teachers", {
        "id": tid,
        "school_id": tenant_id,
        "user_id": uid,
        "full_name": "Sub Teacher",
        "is_active": True,
    })
    return {"teacher_id": tid, "user_id": uid}


async def _mk_session(tenant_id: str, *, class_id, subject_id=None,
                      day="wednesday", period=1) -> str:
    sess_id = str(uuid.uuid4())
    await db_insert("timetable_sessions", {
        "id": sess_id,
        "school_id": tenant_id,
        "timetable_id": str(uuid.uuid4()),
        "day_of_week": day,
        "period_number": period,
        "class_id": class_id,
        "subject_id": subject_id,
        # NOTE: deliberately no class_name / subject_name baked in — the modern
        # store resolves display names from classes/subjects at read time.
    })
    return sess_id


def _patch_eligibility(monkeypatch, *teacher_ids: str) -> None:
    async def _fake_score(*_args, **_kwargs):
        return {"candidates": [{"teacher_id": tid} for tid in teacher_ids]}

    monkeypatch.setattr(standby_routes, "score_candidates_for_slot", _fake_score)


async def test_notify_coverage_persists_substitute_assignment(
    client, tenant_a, monkeypatch
):
    principal = await _mk_principal(tenant_a)
    sub = await _mk_substitute_teacher(tenant_a)

    class_id = str(uuid.uuid4())
    await db_insert("classes", {
        "id": class_id, "school_id": tenant_a, "name": "الصف السابع",
        "is_active": True,
    })
    sess_id = await _mk_session(tenant_a, class_id=class_id,
                                day="wednesday", period=1)

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

    # The response now exposes the persisted assignment id.
    assert resp.json().get("assignment_id"), resp.text

    rows = await gd_find(
        db.session, "substitute_assignments",
        {"school_id": tenant_a, "substitute_teacher_id": sub["teacher_id"]},
        limit=10,
    )
    assert len(rows) == 1, f"expected exactly one assignment row, got {rows}"
    row = rows[0]
    assert row["original_session_id"] == sess_id
    assert (row.get("day_of_week") or "").lower() == "wednesday"
    assert int(row.get("period_number") or 0) == 1
    # class_id must be carried so the teacher roster can resolve the class name.
    assert row.get("class_id") == class_id


async def test_notify_coverage_sends_single_notification(
    client, tenant_a, monkeypatch
):
    """Wiring persistence in must NOT double-notify the substitute teacher."""
    principal = await _mk_principal(tenant_a)
    sub = await _mk_substitute_teacher(tenant_a)

    class_id = str(uuid.uuid4())
    await db_insert("classes", {
        "id": class_id, "school_id": tenant_a, "name": "الصف الثامن",
        "is_active": True,
    })
    sess_id = await _mk_session(tenant_a, class_id=class_id,
                                day="thursday", period=2)

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

    # The substitute teacher must receive EXACTLY ONE notification (the rich
    # coverage notice). Wiring persistence in via assign_substitute(notify=False)
    # must not also trigger that path's plain notification.
    notifs = await gd_find(
        db.session, "notifications",
        {"user_id": sub["user_id"]},
        limit=20,
    )
    assert len(notifs) == 1, f"expected one notification, got {notifs}"


async def test_notify_coverage_same_teacher_is_idempotent(
    client, tenant_a, monkeypatch
):
    """Re-confirming coverage for the SAME teacher/session must be idempotent.

    The principal dialog can fire twice (double-click, retry). A repeat call for
    the same substitute on the same session/date must return success — NOT a 409
    — and must not create a second assignment row. This locks in the
    `assign_substitute` check ordering: the exact (session, date) match must be
    detected before the parallel-slot guard, otherwise a same-teacher repeat is
    misreported as `already_substituting`.
    """
    principal = await _mk_principal(tenant_a)
    sub = await _mk_substitute_teacher(tenant_a)

    class_id = str(uuid.uuid4())
    await db_insert("classes", {
        "id": class_id, "school_id": tenant_a, "name": "الصف التاسع",
        "is_active": True,
    })
    sess_id = await _mk_session(tenant_a, class_id=class_id,
                                day="monday", period=3)

    _patch_eligibility(monkeypatch, sub["teacher_id"])

    payload = {
        "original_session_id": sess_id,
        "substitute_teacher_id": sub["teacher_id"],
    }
    r1 = await client.post(
        "/standby/notify-coverage", headers=_headers(principal), json=payload,
    )
    assert r1.status_code == 201, r1.text

    r2 = await client.post(
        "/standby/notify-coverage", headers=_headers(principal), json=payload,
    )
    assert r2.status_code == 201, r2.text
    assert r2.json().get("assignment_id"), r2.text

    rows = await gd_find(
        db.session, "substitute_assignments",
        {"school_id": tenant_a, "original_session_id": sess_id},
        limit=10,
    )
    assert len(rows) == 1, f"idempotent repeat must not duplicate, got {rows}"


async def test_notify_coverage_rejects_second_teacher(
    client, tenant_a, monkeypatch
):
    """A different teacher cannot steal a session already covered.

    Once teacher A covers a session, assigning teacher B to the SAME session/date
    must 409, must not persist a second assignment, and must not notify B.
    """
    principal = await _mk_principal(tenant_a)
    sub_a = await _mk_substitute_teacher(tenant_a)
    sub_b = await _mk_substitute_teacher(tenant_a)

    class_id = str(uuid.uuid4())
    await db_insert("classes", {
        "id": class_id, "school_id": tenant_a, "name": "الصف العاشر",
        "is_active": True,
    })
    sess_id = await _mk_session(tenant_a, class_id=class_id,
                                day="tuesday", period=4)

    _patch_eligibility(monkeypatch, sub_a["teacher_id"], sub_b["teacher_id"])

    r1 = await client.post(
        "/standby/notify-coverage", headers=_headers(principal),
        json={
            "original_session_id": sess_id,
            "substitute_teacher_id": sub_a["teacher_id"],
        },
    )
    assert r1.status_code == 201, r1.text

    r2 = await client.post(
        "/standby/notify-coverage", headers=_headers(principal),
        json={
            "original_session_id": sess_id,
            "substitute_teacher_id": sub_b["teacher_id"],
        },
    )
    assert r2.status_code == 409, r2.text

    # Only teacher A holds an assignment for this session; B has none.
    rows_a = await gd_find(
        db.session, "substitute_assignments",
        {"school_id": tenant_a, "substitute_teacher_id": sub_a["teacher_id"]},
        limit=10,
    )
    rows_b = await gd_find(
        db.session, "substitute_assignments",
        {"school_id": tenant_a, "substitute_teacher_id": sub_b["teacher_id"]},
        limit=10,
    )
    assert len(rows_a) == 1, rows_a
    assert len(rows_b) == 0, rows_b

    # The rejected teacher B must NOT receive a coverage notification.
    notifs_b = await gd_find(
        db.session, "notifications",
        {"user_id": sub_b["user_id"]},
        limit=20,
    )
    assert len(notifs_b) == 0, f"rejected teacher must not be notified, got {notifs_b}"
