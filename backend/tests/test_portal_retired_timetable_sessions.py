"""HTTP regressions for operational timetable reads in both portals."""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from dependencies import create_access_token, db
from engines.sql_utils import gd_insert


def _headers(user_id: str, role: str, school_id: str) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": school_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _school() -> str:
    school_id = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": f"Portal lifecycle {school_id[:6]}",
        "code": f"PL{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    return school_id


async def _class(school_id: str) -> str:
    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id,
        "school_id": school_id,
        "name": "Portal lifecycle class",
        "is_active": True,
    })
    return class_id


async def _teacher(school_id: str, name: str) -> str:
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "school_id": school_id,
        "full_name": name,
        "is_active": True,
    })
    return teacher_id


async def _subject(school_id: str, name: str) -> str:
    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id,
        "school_id": school_id,
        "name": name,
        "is_active": True,
    })
    return subject_id


async def _timetable(school_id: str) -> str:
    timetable_id = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": timetable_id,
        "school_id": school_id,
        "name": "Portal lifecycle timetable",
        "status": "published",
        "is_published": True,
    })
    return timetable_id


async def _session(
    school_id: str,
    timetable_id: str,
    class_id: str,
    *,
    session_id: str | None = None,
    day: str = "monday",
    period: int = 1,
    teacher_id: str | None = None,
    subject_id: str | None = None,
    **fields,
) -> str:
    session_id = session_id or str(uuid.uuid4())
    row = {
        "id": session_id,
        "school_id": school_id,
        "timetable_id": timetable_id,
        "class_id": class_id,
        "day_of_week": day,
        "period_number": period,
        "teacher_id": teacher_id,
        "subject_id": subject_id,
        "start_time": f"{period:02d}:00",
        "end_time": f"{period:02d}:45",
    }
    row.update(fields)
    await gd_insert(db.session, "timetable_sessions", row)
    return session_id


async def _parent_child(school_id: str, class_id: str):
    parent_id = str(uuid.uuid4())
    child_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": parent_id,
        "role": "parent",
        "tenant_id": school_id,
        "email": f"{parent_id}@portal.test",
        "full_name": "Portal parent",
        "is_active": True,
        "password_hash": "x",
    })
    await gd_insert(db.session, "students", {
        "id": child_id,
        "school_id": school_id,
        "full_name": "Portal child",
        "class_id": class_id,
        "is_active": True,
    })
    await gd_insert(db.session, "guardian_links", {
        "id": str(uuid.uuid4()),
        "tenant_id": school_id,
        "student_id": child_id,
        "parent_ref": parent_id,
        "is_active": True,
    })
    return parent_id, child_id


async def _student(school_id: str, class_id: str):
    student_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": student_id,
        "role": "student",
        "tenant_id": school_id,
        "email": f"{student_id}@portal.test",
        "full_name": "Portal student",
        "is_active": True,
        "password_hash": "x",
        "student_id": student_id,
    })
    await gd_insert(db.session, "students", {
        "id": student_id,
        "user_id": student_id,
        "school_id": school_id,
        "full_name": "Portal student",
        "class_id": class_id,
        "is_active": True,
    })
    return student_id


async def test_parent_schedule_and_today_only_expose_live_tenant_rows(client):
    school_id = await _school()
    foreign_school_id = await _school()
    class_id = await _class(school_id)
    parent_id, child_id = await _parent_child(school_id, class_id)
    timetable_id = await _timetable(school_id)
    teacher_id = await _teacher(school_id, "Live teacher")
    subject_id = await _subject(school_id, "Live subject")
    # Production resolves "today" in the school's Saudi timezone. UTC crosses
    # into the next school day at 21:00 and made this regression intermittently
    # seed the wrong weekday.
    today = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%A").lower()

    await _session(
        school_id, timetable_id, class_id, day=today, period=1,
        teacher_id=teacher_id, subject_id=subject_id,
    )
    await _session(
        school_id, timetable_id, class_id, day=today, period=2,
        teacher_id=teacher_id, subject_id=subject_id,
        is_active=None, status=None,
    )
    await _session(
        school_id, timetable_id, class_id, day=today, period=3,
        teacher_id=teacher_id, subject_id=subject_id,
        is_active=False, subject_name="RETIRED_TEACHER_PLACEMENT",
    )
    await _session(
        school_id, timetable_id, class_id, day=today, period=4,
        teacher_id=teacher_id, subject_id=subject_id,
        status="cancelled", subject_name="RETIRED_CLASS_PLACEMENT",
    )
    # A live dangling teacher reference remains visible through its denormalised
    # name; lifecycle filtering must not turn into referential filtering.
    await _session(
        school_id, timetable_id, class_id, day=today, period=5,
        teacher_id=str(uuid.uuid4()), subject_id=subject_id,
        teacher_name="Active orphan teacher",
    )
    # Same timetable/class keys but a different tenant must never leak.
    await _session(
        foreign_school_id, timetable_id, class_id, day=today, period=6,
        teacher_id=teacher_id, subject_id=subject_id,
        subject_name="FOREIGN_TENANT",
    )

    headers = _headers(parent_id, "parent", school_id)
    schedule = await client.get(
        f"/parent-portal/child/{child_id}/schedule", headers=headers
    )
    today_live = await client.get(
        f"/parent-portal/child/{child_id}/today-live", headers=headers
    )

    assert schedule.status_code == 200, schedule.text
    assert today_live.status_code == 200, today_live.text
    schedule_text = schedule.text
    today_text = today_live.text
    for excluded in (
        "RETIRED_TEACHER_PLACEMENT",
        "RETIRED_CLASS_PLACEMENT",
        "FOREIGN_TENANT",
    ):
        assert excluded not in schedule_text
        assert excluded not in today_text
    today_rows = today_live.json()["school_day"]["all_sessions"]
    # With no configured period model the parent view reindexes the three
    # surviving distinct raw periods to canonical rows 1..3.
    assert {row["period"] for row in today_rows} == {1, 2, 3}
    assert any(row["teacher"] == "Active orphan teacher" for row in today_rows)


async def test_student_schedule_dashboard_and_teachers_only_use_live_rows(
    client, monkeypatch
):
    # Student bearer access is temporarily product-disabled. Exercise the real
    # HTTP dependency stack while narrowly lifting that unrelated feature flag.
    monkeypatch.setattr("dependencies.STUDENT_LOGIN_DISABLED", False)
    school_id = await _school()
    foreign_school_id = await _school()
    class_id = await _class(school_id)
    student_id = await _student(school_id, class_id)
    timetable_id = await _timetable(school_id)
    live_teacher = await _teacher(school_id, "Student live teacher")
    retired_teacher = await _teacher(school_id, "RETIRED PORTAL TEACHER")
    foreign_teacher = await _teacher(school_id, "FOREIGN PORTAL TEACHER")
    subject_id = await _subject(school_id, "Student live subject")
    today = datetime.now().strftime("%A").lower()

    await _session(
        school_id, timetable_id, class_id, day=today, period=1,
        teacher_id=live_teacher, subject_id=subject_id,
    )
    await _session(
        school_id, timetable_id, class_id, day=today, period=2,
        teacher_id=live_teacher, subject_id=subject_id,
        is_active=None, status=None,
    )
    await _session(
        school_id, timetable_id, class_id, day=today, period=3,
        teacher_id=retired_teacher, subject_id=subject_id, is_active=False,
    )
    await _session(
        school_id, timetable_id, class_id, day=today, period=4,
        teacher_id=retired_teacher, subject_id=subject_id, status="cancelled",
    )
    await _session(
        school_id, timetable_id, class_id, day=today, period=5,
        teacher_id=str(uuid.uuid4()), subject_id=subject_id,
        teacher_name="Student active orphan",
    )
    await _session(
        foreign_school_id, timetable_id, class_id, day=today, period=6,
        teacher_id=foreign_teacher, subject_id=subject_id,
    )

    headers = _headers(student_id, "student", school_id)
    schedule = await client.get("/student-portal/schedule", headers=headers)
    dashboard = await client.get("/student-portal/dashboard", headers=headers)
    teachers = await client.get("/student-portal/teachers", headers=headers)

    assert schedule.status_code == 200, schedule.text
    assert dashboard.status_code == 200, dashboard.text
    assert teachers.status_code == 200, teachers.text
    for response in (schedule, dashboard, teachers):
        assert "RETIRED PORTAL TEACHER" not in response.text
        assert "FOREIGN PORTAL TEACHER" not in response.text
    assert {row["period"] for row in dashboard.json()["today_schedule"]} == {
        1, 2, 5
    }
    assert any(
        row["teacher"] == "Student active orphan"
        for row in dashboard.json()["today_schedule"]
    )
    assert [row["name"] for row in teachers.json()["teachers"]] == [
        "Student live teacher"
    ]


async def test_student_dashboard_filters_retired_rows_before_limit(
    client, monkeypatch
):
    monkeypatch.setattr("dependencies.STUDENT_LOGIN_DISABLED", False)
    school_id = await _school()
    class_id = await _class(school_id)
    student_id = await _student(school_id, class_id)
    timetable_id = await _timetable(school_id)
    teacher_id = await _teacher(school_id, "After-limit teacher")
    subject_id = await _subject(school_id, "After-limit subject")
    today = datetime.now().strftime("%A").lower()

    for index in range(20):
        await _session(
            school_id, timetable_id, class_id,
            session_id=f"000-retired-{index:02d}-{uuid.uuid4()}",
            day=today, period=index + 1, teacher_id=teacher_id,
            subject_id=subject_id, is_active=False,
        )
    await _session(
        school_id, timetable_id, class_id,
        session_id=f"zzz-live-{uuid.uuid4()}",
        day=today, period=21, teacher_id=teacher_id, subject_id=subject_id,
    )

    response = await client.get(
        "/student-portal/dashboard",
        headers=_headers(student_id, "student", school_id),
    )

    assert response.status_code == 200, response.text
    assert [row["period"] for row in response.json()["today_schedule"]] == [21]