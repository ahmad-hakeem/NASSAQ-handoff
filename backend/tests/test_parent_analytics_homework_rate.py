"""Parent cumulative-analytics homework_rate regression tests.

Root cause addressed:
  GET /parent-portal/child/{id}/analytics (the "عرض التفاصيل التراكمية" /
  "مؤشر المتابعة المنزلية" panel) computed homework_rate from ONLY the
  digital model (assignment_submissions / student_assignments), while the
  الواجبات tab merges lesson-recorded homework (`session_homework`,
  status done/not_done marked by the teacher during a live lesson).
  For lesson-only schools the summary showed 0% while the tab showed real
  submissions — a contradiction.

  The endpoint now uses the shared `_merged_homework_counts` helper (both
  models merged, tenant fail-closed on session resolution). When NO homework
  is tracked anywhere, homework_rate is None: the "واجبات غير مكتملة"
  weakness is suppressed and the composite follow-up score renormalizes
  its weights instead of treating "untracked" as 0%.

Scenarios covered (GET /parent-portal/child/{id}/analytics):
  1. Lesson-only homework (2 done / 1 not_done) → homework_rate 66.7,
     not 0 (the reported bug).
  2. No homework anywhere → homework_rate None, no homework weakness,
     composite score renormalized (not dragged down by a 0% component).
  3. Digital + lesson merged → 1 submitted digital + 1 not_done lesson = 50%
     → homework weakness present with the merged rate.
  4. Cross-tenant / orphan session_homework rows excluded (fail closed).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


def _parent_token(user_id: str, tenant_id: str) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": UserRole.PARENT.value,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _seed_parent_with_child(tenant_id: str, class_id: str | None = None):
    parent_record_id = str(uuid.uuid4())
    parent_user_id = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": parent_record_id,
        "full_name": "ولي أمر تجريبي",
        "email": f"p-{parent_record_id}@t.test",
        "school_id": tenant_id,
        "is_active": True,
        "student_ids": [],
    })
    await gd_insert(db.session, "users", {
        "id": parent_user_id,
        "role": UserRole.PARENT.value,
        "tenant_id": tenant_id,
        "parent_id": parent_record_id,
        "email": f"p-{parent_record_id}@t.test",
        "full_name": "ولي أمر تجريبي",
        "is_active": True,
        "password_hash": "x",
    })
    student_id = str(uuid.uuid4())
    await db.session.execute(
        text(
            "INSERT INTO students (id, school_id, full_name, parent_id, class_id, is_active)"
            " VALUES (:id, :school_id, :full_name, :parent_id, :class_id, true)"
        ),
        {
            "id": student_id,
            "school_id": tenant_id,
            "full_name": f"ST-{student_id[:6]}",
            "parent_id": parent_record_id,
            "class_id": class_id,
        },
    )
    return {
        "user_id": parent_user_id,
        "parent_record_id": parent_record_id,
        "student_id": student_id,
    }


async def _seed_session(school_id: str, *, class_id: str | None = None,
                        date: str = "2026-06-10") -> str:
    session_id = str(uuid.uuid4())
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "school_id": school_id,
        "class_id": class_id,
        "subject_id": str(uuid.uuid4()),
        "subject_name": "الرياضيات",
        "date": date,
    })
    return session_id


async def _seed_lesson_hw(session_id: str, student_id: str, status: str) -> None:
    await gd_insert(db.session, "session_homework", {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "student_id": student_id,
        "status": status,
        "recorded_at": "2026-06-10T09:00:00+00:00",
    })


async def _get_analytics(client, seeded, tenant_id):
    res = await client.get(
        f"/parent-portal/child/{seeded['student_id']}/analytics",
        headers=_parent_token(seeded["user_id"], tenant_id),
    )
    assert res.status_code == 200, res.text
    return res.json()


def _homework_weakness(body):
    return [w for w in body.get("weaknesses", [])
            if w.get("area") == "واجبات غير مكتملة"]


@pytest.mark.asyncio
async def test_lesson_only_homework_reflected_in_rate(client, tenant_a):
    """The reported bug: lesson-recorded submissions must move the summary
    metric off 0%."""
    seeded = await _seed_parent_with_child(tenant_a)
    student_id = seeded["student_id"]

    for status in ("done", "done", "not_done"):
        sid = await _seed_session(tenant_a)
        await _seed_lesson_hw(sid, student_id, status)
    await db.session.flush()

    body = await _get_analytics(client, seeded, tenant_a)
    rate = body["follow_up"]["breakdown"]["homework_rate"]
    assert rate == pytest.approx(66.7, abs=0.1)
    # 66.7 >= 60 → no homework weakness.
    assert _homework_weakness(body) == []


@pytest.mark.asyncio
async def test_no_homework_tracked_is_none_not_zero(client, tenant_a):
    """No homework in either model → None (untracked), no fake 0% weakness,
    and the composite score renormalizes instead of losing 30% weight."""
    seeded = await _seed_parent_with_child(tenant_a)
    await db.session.flush()

    body = await _get_analytics(client, seeded, tenant_a)
    assert body["follow_up"]["breakdown"]["homework_rate"] is None
    assert _homework_weakness(body) == []
    # All other components are 0 here, so the renormalized score is 0 —
    # the key assertion is that the response is well-formed with hw=None.
    assert body["follow_up"]["score"] == 0


@pytest.mark.asyncio
async def test_digital_and_lesson_merged(client, tenant_a):
    """1 submitted digital assignment + 1 not_done lesson record → 50%,
    and the <60% weakness carries the merged rate."""
    class_id = str(uuid.uuid4())
    await db.session.execute(
        text(
            "INSERT INTO classes (id, school_id, name, is_active)"
            " VALUES (:id, :school_id, :name, true)"
        ),
        {"id": class_id, "school_id": tenant_a, "name": f"CL-{class_id[:6]}"},
    )
    seeded = await _seed_parent_with_child(tenant_a, class_id=class_id)
    student_id = seeded["student_id"]

    assignment_id = str(uuid.uuid4())
    await gd_insert(db.session, "student_assignments", {
        "id": assignment_id,
        "school_id": tenant_a,
        "class_id": class_id,
        "title": "واجب رقمي",
        "due_date": "2026-06-15",
        "is_active": True,
    })
    await gd_insert(db.session, "assignment_submissions", {
        "id": str(uuid.uuid4()),
        "assignment_id": assignment_id,
        "student_id": student_id,
        "school_id": tenant_a,
        "submitted_at": "2026-06-14T10:00:00+00:00",
    })

    sid = await _seed_session(tenant_a, class_id=class_id)
    await _seed_lesson_hw(sid, student_id, "not_done")
    await db.session.flush()

    body = await _get_analytics(client, seeded, tenant_a)
    rate = body["follow_up"]["breakdown"]["homework_rate"]
    assert rate == pytest.approx(50.0, abs=0.1)
    weaknesses = _homework_weakness(body)
    assert len(weaknesses) == 1
    assert "50.0" in weaknesses[0]["detail"]


@pytest.mark.asyncio
async def test_cross_tenant_and_orphan_lesson_rows_excluded(client, tenant_a, tenant_b):
    """Forged tenant_b session homework and orphan rows must not count:
    with only those present, homework stays untracked (None)."""
    seeded = await _seed_parent_with_child(tenant_a)
    student_id = seeded["student_id"]

    # Forged: session lives in tenant_b but references the tenant_a student.
    s_b = await _seed_session(tenant_b)
    await _seed_lesson_hw(s_b, student_id, "done")
    # Orphan: no class_sessions row at all (tenant unprovable).
    await _seed_lesson_hw(str(uuid.uuid4()), student_id, "done")
    await db.session.flush()

    body = await _get_analytics(client, seeded, tenant_a)
    assert body["follow_up"]["breakdown"]["homework_rate"] is None
    assert _homework_weakness(body) == []
