"""Real-route regression coverage for the principal publish policy.

The publish gate must treat an HC-09 subject overage as a review warning,
not as a reason to discard an otherwise usable timetable.  This file keeps
the proof at the HTTP boundary:

* a principal publishes a real draft containing one excess subject session;
* the exact timetable-session rows remain intact;
* the published master grid, teacher timetable, and parent timetable all
  resolve those rows from the published parent;
* newly authenticated and refreshed principal sessions see the same rows;
* a real teacher/class conflict returns 409 without archiving the current
  published timetable; and
* cross-school teacher and parent reads fail closed.

All rows are synthetic and use the existing per-test database session, which
is rolled back by ``backend/tests/conftest.py``.
"""
from __future__ import annotations

import inspect
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import UserRole, create_access_token, db, hash_password
from engines.smart_scheduling_engine import SmartSchedulingEngine
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one, gd_update_many


_LOGIN_PASSWORD = "Regression@1234!"


def _headers(user: dict) -> dict[str, str]:
    token = create_access_token(
        {
            "sub": user["id"],
            "role": user["role"],
            "tenant_id": user.get("tenant_id"),
        }
    )
    return {"Authorization": f"Bearer {token}"}


async def _mk_user(
    school_id: str,
    role: UserRole,
    *,
    with_password: bool = False,
) -> dict:
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "role": role.value,
        "tenant_id": school_id,
        "email": f"publish-{user_id}@example.com",
        "full_name": f"Regression {role.value}",
        "is_active": True,
        "password_hash": hash_password(_LOGIN_PASSWORD) if with_password else "x",
    }
    await gd_insert(db.session, "users", user)
    return user


async def _mk_teacher(school_id: str, *, user: dict | None = None) -> tuple[dict, dict]:
    user = user or await _mk_user(school_id, UserRole.TEACHER)
    teacher = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "user_id": user["id"],
        "full_name": f"Teacher-{user['id'][:8]}",
        "is_active": True,
        "weekly_periods": 20,
    }
    await gd_insert(db.session, "teachers", teacher)
    return user, teacher


async def _mk_class(school_id: str, *, grade_id: str | None = None) -> dict:
    row = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "name": f"Class-{uuid.uuid4().hex[:8]}",
        "is_active": True,
    }
    if grade_id:
        row["grade_id"] = grade_id
    await gd_insert(db.session, "classes", row)
    return row


async def _mk_subject(school_id: str) -> dict:
    row = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "name": f"Subject-{uuid.uuid4().hex[:8]}",
        "name_ar": "مادة اختبار النشر",
        "is_active": True,
    }
    await gd_insert(db.session, "subjects", row)
    return row


async def _mk_timetable(school_id: str, *, status: str, name: str) -> dict:
    row = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "name": name,
        "academic_year": "2026-2027",
        "semester": 1,
        "status": status,
        "is_published": status == "published",
        "version": 1,
        "total_sessions": 0,
    }
    if status == "published":
        row["published_at"] = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "timetables", row)
    return row


async def _mk_session(
    school_id: str,
    timetable_id: str,
    *,
    teacher_id: str,
    class_id: str,
    subject_id: str,
    day: str,
    period: int,
) -> dict:
    row = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "timetable_id": timetable_id,
        "teacher_id": teacher_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "day_of_week": day,
        "period_number": period,
        "start_time": "",
        "end_time": "",
        "status": "scheduled",
        "source_type": "manual",
    }
    await gd_insert(db.session, "timetable_sessions", row)
    return row


async def _mk_parent_child(school_id: str, class_id: str) -> tuple[dict, dict]:
    parent = await _mk_user(school_id, UserRole.PARENT)
    child = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "full_name": f"Student-{uuid.uuid4().hex[:8]}",
        "is_active": True,
    }
    if class_id:
        child["class_id"] = class_id
    await gd_insert(db.session, "students", child)
    # This is the same real linkage used by the parent-IT endpoint tests.  It
    # exercises the canonical parent resolver rather than bypassing it.
    await gd_insert(
        db.session,
        "guardian_links",
        {
            "id": str(uuid.uuid4()),
            "tenant_id": school_id,
            "student_id": child["id"],
            "parent_ref": parent["id"],
            "is_active": True,
        },
    )
    return parent, child


async def _isolate_hard_constraints() -> None:
    await gd_update_many(
        db.session,
        "timetable_hard_constraints",
        {},
        {"is_active": False},
    )


async def _enable_hard_constraint(
    validation_key: str,
    code: str,
    *,
    severity: str = "high",
) -> None:
    existing = await gd_find_one(
        db.session,
        "timetable_hard_constraints",
        {"validation_key": validation_key},
    )
    if existing:
        await gd_update_one(
            db.session,
            "timetable_hard_constraints",
            {"id": existing["id"]},
            {"is_active": True, "severity": severity},
        )
        return
    await gd_insert(
        db.session,
        "timetable_hard_constraints",
        {
            "id": str(uuid.uuid4()),
            "code": code,
            "name_ar": code,
            "name_en": code,
            "description_ar": "",
            "description_en": "",
            "category": "regression",
            "severity": severity,
            "is_system": True,
            "is_active": True,
            "can_disable": False,
            "validation_key": validation_key,
        },
    )


def _grid_signatures(body: dict) -> set[tuple]:
    signatures = set()
    for teacher_id, days in (body.get("cells") or {}).items():
        for day, periods in days.items():
            for period, cell in periods.items():
                signatures.add(
                    (
                        cell.get("session_id"),
                        teacher_id,
                        cell.get("class_id"),
                        cell.get("subject_id"),
                        day,
                        int(period),
                    )
                )
    return signatures


def _teacher_signatures(rows: list[dict]) -> set[tuple]:
    return {
        (
            row.get("schedule_session_id") or row.get("id"),
            row.get("class_id"),
            row.get("subject_id"),
            row.get("day_of_week"),
            row.get("period_number"),
        )
        for row in rows
    }


def _session_core(row: dict) -> tuple:
    return (
        row["id"],
        row["timetable_id"],
        row["teacher_id"],
        row["class_id"],
        row["subject_id"],
        row["day_of_week"],
        row["period_number"],
    )


async def _login(client, user: dict) -> dict:
    response = await client.post(
        "/auth/login",
        json={"email": user["email"], "password": _LOGIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_principal_publish_hc09_warning_preserves_sessions_across_real_reads(
    client,
    tenant_a,
):
    """HC-09 overage is a warning while published session identity survives.

    The curriculum says one weekly period, while the candidate draft contains
    two.  After the policy fix this publishes successfully and all three
    published timetable readers expose the same two real sessions.
    """
    principal = await _mk_user(
        tenant_a,
        UserRole.SCHOOL_PRINCIPAL,
        with_password=True,
    )
    teacher_user, teacher = await _mk_teacher(tenant_a)

    grade_id = str(uuid.uuid4())
    classroom = await _mk_class(tenant_a, grade_id=grade_id)
    parent, child = await _mk_parent_child(tenant_a, classroom["id"])
    subject = await _mk_subject(tenant_a)
    await gd_insert(
        db.session,
        "grade_subjects",
        {
            "id": str(uuid.uuid4()),
            "school_id": tenant_a,
            "grade_id": grade_id,
            "subject_id": subject["id"],
            "weekly_periods": 1,
            "is_active": True,
        },
    )
    await gd_insert(
        db.session,
        "teacher_assignments",
        {
            "id": str(uuid.uuid4()),
            "school_id": tenant_a,
            "teacher_id": teacher["id"],
            "class_id": classroom["id"],
            "subject_id": subject["id"],
            "weekly_sessions": 1,
            "periods_per_week": 1,
            "academic_year": "2026-2027",
            "semester": 1,
            "is_active": True,
        },
    )

    draft = await _mk_timetable(tenant_a, status="draft", name="Excess-subject draft")
    sessions = [
        await _mk_session(
            tenant_a,
            draft["id"],
            teacher_id=teacher["id"],
            class_id=classroom["id"],
            subject_id=subject["id"],
            day="sunday",
            period=1,
        ),
        await _mk_session(
            tenant_a,
            draft["id"],
            teacher_id=teacher["id"],
            class_id=classroom["id"],
            subject_id=subject["id"],
            day="monday",
            period=2,
        ),
    ]
    before = {_session_core(row) for row in sessions}

    await _isolate_hard_constraints()
    # The test is intentionally red while HC-09 over-placement still emits
    # HIGH.  The policy fix changes this overage to MEDIUM.
    await _enable_hard_constraint(
        "subject_weekly_periods",
        "HC-09",
        severity="medium",
    )

    published = await client.post(
        "/schedule/publish",
        json={"school_id": tenant_a, "timetable_id": draft["id"]},
        headers=_headers(principal),
    )
    assert published.status_code == 200, published.text
    assert published.json()["timetable_id"] == draft["id"]

    persisted = await gd_find(
        db.session,
        "timetable_sessions",
        {"timetable_id": draft["id"]},
        limit=20,
    )
    assert {_session_core(row) for row in persisted} == before

    # The gate's structured result must retain HC-09 as a warning rather than
    # silently dropping evidence of the overage.
    validation = await SmartSchedulingEngine(db).validate_before_publish(
        school_id=tenant_a,
        timetable_id=draft["id"],
    )
    assert validation["is_publishable"] is True
    assert any(
        warning["validation_key"] == "subject_weekly_periods"
        and warning["refs"].get("expected") == 1
        and warning["refs"].get("actual") == 2
        for warning in validation["warnings"]
    )
    assert not any(
        violation["validation_key"] == "subject_weekly_periods"
        for violation in validation["violations"]
    )

    principal_headers = _headers(principal)
    grid_response = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}&view=published",
        headers=principal_headers,
    )
    assert grid_response.status_code == 200, grid_response.text
    grid = grid_response.json()
    expected_grid = {
        (
            row["id"],
            teacher["id"],
            classroom["id"],
            subject["id"],
            row["day_of_week"],
            row["period_number"],
        )
        for row in sessions
    }
    assert _grid_signatures(grid) == expected_grid

    teacher_response = await client.get(
        f"/teacher/schedule/{teacher['id']}",
        headers=_headers(teacher_user),
    )
    assert teacher_response.status_code == 200, teacher_response.text
    assert _teacher_signatures(teacher_response.json()) == {
        (
            row["id"],
            classroom["id"],
            subject["id"],
            row["day_of_week"],
            row["period_number"],
        )
        for row in sessions
    }

    parent_response = await client.get(
        f"/parent-portal/child/{child['id']}/schedule",
        headers=_headers(parent),
    )
    assert parent_response.status_code == 200, parent_response.text
    parent_body = parent_response.json()
    parent_sessions = {
        (entry["period"], entry["subject"], entry["teacher"])
        for day_entries in parent_body["schedule"].values()
        for entry in day_entries
    }
    assert parent_sessions == {
        (row["period_number"], subject["name_ar"], teacher["full_name"])
        for row in sessions
    }

    # A newly authenticated principal and a rotated refresh token must resolve
    # the same published cell signatures; no in-memory auth state may be the
    # source of schedule visibility.
    fresh_login = await _login(client, principal)
    fresh_grid_response = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}&view=published",
        headers={"Authorization": f"Bearer {fresh_login['access_token']}"},
    )
    assert fresh_grid_response.status_code == 200, fresh_grid_response.text
    assert _grid_signatures(fresh_grid_response.json()) == expected_grid

    refreshed = await client.post(
        "/auth/refresh",
        json={"refresh_token": fresh_login["refresh_token"]},
    )
    assert refreshed.status_code == 200, refreshed.text
    rotated_grid_response = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}&view=published",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert rotated_grid_response.status_code == 200, rotated_grid_response.text
    assert _grid_signatures(rotated_grid_response.json()) == expected_grid


@pytest.mark.asyncio
async def test_conflicting_publish_returns_409_and_keeps_current_published_timetable(
    client,
    tenant_a,
):
    """A real teacher/class overlap cannot archive the currently published set."""
    principal = await _mk_user(tenant_a, UserRole.SCHOOL_PRINCIPAL)
    teacher_user, teacher = await _mk_teacher(tenant_a)
    classroom = await _mk_class(tenant_a)
    subject = await _mk_subject(tenant_a)

    published = await _mk_timetable(tenant_a, status="published", name="Current")
    old_session = await _mk_session(
        tenant_a,
        published["id"],
        teacher_id=teacher["id"],
        class_id=classroom["id"],
        subject_id=subject["id"],
        day="sunday",
        period=1,
    )
    draft = await _mk_timetable(tenant_a, status="draft", name="Conflicting draft")
    await _mk_session(
        tenant_a,
        draft["id"],
        teacher_id=teacher["id"],
        class_id=classroom["id"],
        subject_id=subject["id"],
        day="monday",
        period=1,
    )
    await _mk_session(
        tenant_a,
        draft["id"],
        teacher_id=teacher["id"],
        class_id=classroom["id"],
        subject_id=subject["id"],
        day="monday",
        period=1,
    )

    await _isolate_hard_constraints()
    await _enable_hard_constraint("teacher_overlap", "HC-01")
    await _enable_hard_constraint("class_overlap", "HC-02")

    response = await client.post(
        "/schedule/publish",
        json={"school_id": tenant_a, "timetable_id": draft["id"]},
        headers=_headers(principal),
    )
    assert response.status_code == 409, response.text

    current = await gd_find_one(db.session, "timetables", {"id": published["id"]})
    attempted = await gd_find_one(db.session, "timetables", {"id": draft["id"]})
    assert current["status"] == "published"
    assert attempted["status"] == "draft"

    grid_response = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}&view=published",
        headers=_headers(principal),
    )
    assert grid_response.status_code == 200, grid_response.text
    assert _grid_signatures(grid_response.json()) == {
        (
            old_session["id"],
            teacher["id"],
            classroom["id"],
            subject["id"],
            "sunday",
            1,
        )
    }

    teacher_response = await client.get(
        f"/teacher/schedule/{teacher['id']}",
        headers=_headers(teacher_user),
    )
    assert teacher_response.status_code == 200, teacher_response.text
    assert [row["schedule_session_id"] for row in teacher_response.json()] == [
        old_session["id"]
    ]


@pytest.mark.asyncio
async def test_unpublish_can_keep_existing_editable_draft_without_discarding_data(
    client,
    tenant_a,
):
    """Explicit keep mode archives the live version and preserves the draft."""
    principal = await _mk_user(tenant_a, UserRole.SCHOOL_PRINCIPAL)
    teacher_user, teacher = await _mk_teacher(tenant_a)
    classroom = await _mk_class(tenant_a)
    subject = await _mk_subject(tenant_a)
    published = await _mk_timetable(tenant_a, status="published", name="Live")
    draft = await _mk_timetable(tenant_a, status="draft", name="My edits")
    live_session = await _mk_session(
        tenant_a,
        published["id"],
        teacher_id=teacher["id"],
        class_id=classroom["id"],
        subject_id=subject["id"],
        day="sunday",
        period=1,
    )
    draft_session = await _mk_session(
        tenant_a,
        draft["id"],
        teacher_id=teacher["id"],
        class_id=classroom["id"],
        subject_id=subject["id"],
        day="monday",
        period=2,
    )

    blocked = await client.post(
        f"/smart-scheduling/timetable/{published['id']}/unpublish",
        headers=_headers(principal),
        json={},
    )
    assert blocked.status_code == 409, blocked.text
    assert "DRAFT_ALREADY_EXISTS" in blocked.text

    response = await client.post(
        f"/smart-scheduling/timetable/{published['id']}/unpublish",
        headers=_headers(principal),
        json={"keep_existing_draft": True},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "archived"
    assert response.json()["editable_draft_id"] == draft["id"]
    archived = await gd_find_one(
        db.session, "timetables", {"id": published["id"]}
    )
    retained_draft = await gd_find_one(
        db.session, "timetables", {"id": draft["id"]}
    )
    assert archived["status"] == "archived"
    assert archived["is_published"] is False
    assert retained_draft["status"] == "draft"
    assert retained_draft["name"] == "My edits"
    assert await gd_find_one(
        db.session, "timetable_sessions", {"id": live_session["id"]}
    )
    assert await gd_find_one(
        db.session, "timetable_sessions", {"id": draft_session["id"]}
    )


def test_all_draft_lifecycle_routes_take_the_shared_school_lock():
    """Publish, unpublish and ensure-draft must use one serialization lock."""
    from src.modules.scheduling.controllers import scheduling_smart_engine_routes

    expected_call = "await _acquire_draft_lifecycle_lock(school_id)"
    route_functions = (
        scheduling_smart_engine_routes.smart_publish_timetable,
        scheduling_smart_engine_routes.publish_schedule,
        scheduling_smart_engine_routes.ensure_editable_draft_route,
        scheduling_smart_engine_routes.unpublish_timetable,
    )
    for route_function in route_functions:
        source = inspect.getsource(route_function)
        assert expected_call in source, route_function.__name__

    helper_source = inspect.getsource(
        scheduling_smart_engine_routes._acquire_draft_lifecycle_lock
    )
    assert "pg_advisory_xact_lock(hashtext(:k))" in helper_source
    assert "sched_draft_ensure:{school_id}" in helper_source


@pytest.mark.asyncio
async def test_foreign_teacher_and_parent_cannot_read_school_schedule(
    client,
    tenant_a,
    tenant_b,
):
    """Role-scoped timetable reads reject IDs belonging to another school."""
    teacher_user_a, teacher_a = await _mk_teacher(tenant_a)
    _, teacher_b = await _mk_teacher(tenant_b)
    foreign_teacher_response = await client.get(
        f"/teacher/schedule/{teacher_b['id']}",
        headers=_headers(teacher_user_a),
    )
    assert foreign_teacher_response.status_code == 403, foreign_teacher_response.text

    class_a = await _mk_class(tenant_a)
    parent_a, child_a = await _mk_parent_child(tenant_a, class_a["id"])
    parent_b, _ = await _mk_parent_child(tenant_b, "")
    foreign_parent_response = await client.get(
        f"/parent-portal/child/{child_a['id']}/schedule",
        headers=_headers(parent_b),
    )
    assert foreign_parent_response.status_code == 403, foreign_parent_response.text

    # Keep the valid same-school linkage exercised too: this guards against a
    # blanket parent denial being mistaken for tenant isolation.
    own_parent_response = await client.get(
        f"/parent-portal/child/{child_a['id']}/schedule",
        headers=_headers(parent_a),
    )
    assert own_parent_response.status_code == 200, own_parent_response.text