"""Parent portal homework-visibility regression tests.

Root cause addressed:
  Teachers record homework status during a live lesson ("سلم"/"لم يسلم"),
  which is stored in the `session_homework` collection (status "done" /
  "not_done"). The parent Student-Profile → الواجبات tab previously read ONLY
  the digital `student_assignments` / `assignment_submissions` model, so it
  always showed 0 submitted / 0 not submitted even after the teacher recorded
  submissions in class.

  The endpoint now merges lesson-recorded homework into the same response:
  "done" → submitted, "not_done" → not_submitted.

Scenarios covered (GET /parent-portal/child/{id}/homework):
  1. No homework anywhere → empty list, zeroed statistics (regression).
  2. Teacher-recorded lesson homework (1 done, 1 not_done) → surfaced with
     correct submitted / not_submitted counts and titles.
  3. Cross-tenant session homework forged with the same student_id must not
     bleed into a tenant_a child's homework (school_id scope guard).
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


async def _seed_session(school_id: str, *, subject_id: str, subject_name: str,
                        class_id: str | None = None, date: str = "2026-06-10") -> str:
    session_id = str(uuid.uuid4())
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "school_id": school_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "subject_name": subject_name,
        "date": date,
    })
    return session_id


async def _seed_homework(session_id: str, student_id: str, status: str) -> None:
    await gd_insert(db.session, "session_homework", {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "student_id": student_id,
        "status": status,
        "recorded_at": "2026-06-10T09:00:00+00:00",
    })


@pytest.mark.asyncio
async def test_no_homework_returns_zeros(client, tenant_a):
    """No assignments and no lesson homework → empty list, zeroed stats."""
    seeded = await _seed_parent_with_child(tenant_a)
    await db.session.flush()

    res = await client.get(
        f"/parent-portal/child/{seeded['student_id']}/homework",
        headers=_parent_token(seeded["user_id"], tenant_a),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["assignments"] == []
    stats = body["statistics"]
    assert stats["submitted"] == 0
    assert stats["not_submitted"] == 0


@pytest.mark.asyncio
async def test_lesson_homework_is_surfaced(client, tenant_a):
    """Teacher-recorded lesson homework (1 done, 1 not_done) is surfaced with
    submitted / not_submitted counts and a subject-derived title."""
    seeded = await _seed_parent_with_child(tenant_a)
    student_id = seeded["student_id"]

    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {"id": subject_id, "name": "Math", "name_ar": "الرياضيات", "school_id": tenant_a})

    s1 = await _seed_session(tenant_a, subject_id=subject_id,
                             subject_name="الرياضيات", date="2026-06-10")
    s2 = await _seed_session(tenant_a, subject_id=subject_id,
                             subject_name="الرياضيات", date="2026-06-11")
    await _seed_homework(s1, student_id, "done")
    await _seed_homework(s2, student_id, "not_done")
    await db.session.flush()

    res = await client.get(
        f"/parent-portal/child/{student_id}/homework",
        headers=_parent_token(seeded["user_id"], tenant_a),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["assignments"]) == 2
    stats = body["statistics"]
    assert stats["submitted"] == 1
    assert stats["not_submitted"] == 1

    statuses = {a["status"] for a in body["assignments"]}
    assert statuses == {"submitted", "not_submitted"}
    # Subject name flows into the title.
    assert all("الرياضيات" in a["title"] for a in body["assignments"])


@pytest.mark.asyncio
async def test_cross_tenant_lesson_homework_excluded(client, tenant_a, tenant_b):
    """A forged session_homework row pointing at a tenant_a student but tied to
    a tenant_b session must NOT appear for the tenant_a parent."""
    seeded = await _seed_parent_with_child(tenant_a)
    student_id = seeded["student_id"]

    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {"id": subject_id, "name": "Science", "name_ar": "العلوم", "school_id": tenant_a})

    # Legit tenant_a lesson homework (done).
    s_a = await _seed_session(tenant_a, subject_id=subject_id, subject_name="العلوم")
    await _seed_homework(s_a, student_id, "done")

    # Forged tenant_b session referencing the same student_id (IDOR probe).
    s_b = await _seed_session(tenant_b, subject_id=subject_id, subject_name="العلوم")
    await _seed_homework(s_b, student_id, "not_done")
    await db.session.flush()

    res = await client.get(
        f"/parent-portal/child/{student_id}/homework",
        headers=_parent_token(seeded["user_id"], tenant_a),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    # Only the tenant_a "done" record is visible.
    assert len(body["assignments"]) == 1
    assert body["assignments"][0]["status"] == "submitted"
    assert body["statistics"]["submitted"] == 1
    assert body["statistics"]["not_submitted"] == 0


@pytest.mark.asyncio
async def test_orphan_and_unknown_status_rows_skipped(client, tenant_a):
    """Homework rows whose session can't be resolved, or with an unexpected
    status, must not be surfaced (tenant can't be proven / unknown state)."""
    seeded = await _seed_parent_with_child(tenant_a)
    student_id = seeded["student_id"]

    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects",
                    {"id": subject_id, "name": "Art", "name_ar": "الفنون", "school_id": tenant_a})

    # Valid resolvable session (done) — should appear.
    s_ok = await _seed_session(tenant_a, subject_id=subject_id, subject_name="الفنون")
    await _seed_homework(s_ok, student_id, "done")

    # Orphan: homework references a session that has no class_sessions row.
    await _seed_homework(str(uuid.uuid4()), student_id, "not_done")

    # Unknown status on a resolvable session.
    s_unknown = await _seed_session(tenant_a, subject_id=subject_id, subject_name="الفنون")
    await _seed_homework(s_unknown, student_id, "pending")
    await db.session.flush()

    res = await client.get(
        f"/parent-portal/child/{student_id}/homework",
        headers=_parent_token(seeded["user_id"], tenant_a),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["assignments"]) == 1
    assert body["assignments"][0]["status"] == "submitted"
    assert body["statistics"]["submitted"] == 1
    assert body["statistics"]["not_submitted"] == 0
