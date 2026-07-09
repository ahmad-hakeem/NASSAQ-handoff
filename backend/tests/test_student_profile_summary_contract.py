"""Student-profile summary contract regression tests.

Guards the two field/shape contracts the admin/principal Student Profile page
(`frontend/src/components/student-profile/StudentTabsContent.jsx` via
`frontend/src/hooks/useStudentProfile.js`) depends on:

  1. GET /api/grades/student/{id} must NOT 500 when the student only has
     "live session" grade documents. Those docs either lack the
     `assessment_id` key entirely, or carry a synthetic id
     ("session:<id>:homework") that has no matching `assessments` row. The
     endpoint must surface them (they are self-contained: subject/score/
     percentage are stored inline) instead of crashing or silently skipping.
     It must also return the `subjects` and `statistics` keys the frontend
     reads.

  2. GET /api/attendance/summary/student/{id} must return the
     `present_days` / `absent_days` / `excused_days` keys the frontend maps
     onto the حاضر / غائب / بعذر cards.
"""
import uuid
from datetime import datetime

import pytest
from sqlalchemy import text

from dependencies import db, UserRole
from engines.sql_utils import gd_insert
from tests.conftest import _mk_user, _mk_school, _headers


async def _seed_student(tenant: str, class_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": tenant,
        "full_name": "طالب اختبار",
        "class_id": class_id,
        "is_active": True,
    })
    return sid


# ---------------------------------------------------------------------------
# Bug 2 — grades endpoint must surface live-session grades, not 500 / skip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_grades_endpoint_surfaces_live_session_grades(client):
    tenant = str(uuid.uuid4())
    await _mk_school(tenant)
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant)
    hdrs = _headers(principal)

    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {"id": class_id, "school_id": tenant, "name": "1A"})
    student_id = await _seed_student(tenant, class_id)

    subject_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    # Doc A: no `assessment_id` key at all (production 500 trigger).
    await gd_insert(db.session, "grades", {
        "id": str(uuid.uuid4()),
        "student_id": student_id,
        "school_id": tenant,
        "tenant_id": tenant,
        "class_id": class_id,
        "subject_id": subject_id,
        "subject_name": "الرياضيات",
        "subject": "الرياضيات",
        "score": 3.0,
        "max_score": 5.0,
        "percentage": 60.0,
        "assessment_type": "coursework",
        "date": "2026-06-22",
        "source": "live_session",
        "session_id": session_id,
    })

    # Doc B: synthetic assessment_id with no matching assessments row (skip trigger).
    await gd_insert(db.session, "grades", {
        "id": str(uuid.uuid4()),
        "student_id": student_id,
        "school_id": tenant,
        "tenant_id": tenant,
        "class_id": class_id,
        "subject_id": subject_id,
        "subject_name": "الرياضيات",
        "subject": "الرياضيات",
        "score": 5.0,
        "max_score": 5.0,
        "percentage": 100.0,
        "assessment_type": "coursework",
        "date": "2026-06-22",
        "source": "live_session",
        "session_id": session_id,
        "assessment_id": f"session:{session_id}:homework",
    })

    resp = await client.get(f"/grades/student/{student_id}", headers=hdrs)
    assert resp.status_code == 200, (
        f"grades endpoint must not 500 on live-session grades: {resp.status_code} {resp.text}"
    )
    body = resp.json()

    # Both grades counted (neither dropped).
    assert body["total_assessments"] == 2, body
    assert body["statistics"]["total_assessments"] == 2, body
    assert body["statistics"]["overall_average"] == 80.0, body

    # Per-subject summary the frontend table consumes.
    subjects = body["subjects"]
    assert isinstance(subjects, list) and len(subjects) == 1, body
    assert subjects[0]["subject_name"] == "الرياضيات", body
    assert subjects[0]["percentage"] == 80.0, body
    assert subjects[0]["count"] == 2, body


# ---------------------------------------------------------------------------
# Bug 1 — attendance summary must expose *_days keys the frontend reads
# ---------------------------------------------------------------------------

async def _add_att(school_id: str, student_id: str, class_id: str, date_str: str, status: str) -> None:
    await db.session.execute(
        text(
            "INSERT INTO attendance"
            " (id, school_id, class_id, student_id, date, status, created_at, updated_at)"
            " VALUES (:id, :school_id, :class_id, :student_id, :date, :status, now(), now())"
        ),
        {
            "id": str(uuid.uuid4()),
            "school_id": school_id,
            "class_id": class_id,
            "student_id": student_id,
            "date": datetime.fromisoformat(f"{date_str}T08:00:00+00:00"),
            "status": status,
        },
    )


@pytest.mark.asyncio
async def test_attendance_summary_returns_days_keys(client):
    tenant = str(uuid.uuid4())
    await _mk_school(tenant)
    principal = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant)
    hdrs = _headers(principal)

    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {"id": class_id, "school_id": tenant, "name": "1A"})
    student_id = await _seed_student(tenant, class_id)

    await _add_att(tenant, student_id, class_id, "2026-05-01", "present")
    await _add_att(tenant, student_id, class_id, "2026-05-02", "present")
    await _add_att(tenant, student_id, class_id, "2026-05-03", "absent")

    resp = await client.get(f"/attendance/summary/student/{student_id}", headers=hdrs)
    assert resp.status_code == 200, f"{resp.status_code} {resp.text}"
    body = resp.json()
    assert body["present_days"] == 2, body
    assert body["absent_days"] == 1, body
    assert "excused_days" in body, body
