"""Tenant-isolation regression tests for the timetable subsystem.

Covers F-CN-06 (engine constraint loader cross-tenant fallback) and
related cross-tenant denial scenarios.
"""

import pytest
from fastapi import HTTPException

from dependencies import db
from engines.smart_scheduling_engine import SmartSchedulingEngine


async def test_engine_does_not_fall_back_to_global_constraints(
    school_a_id,
    school_b_id,
    seed_global_admin_constraint,
    seed_school_b_constraint,
):
    """If school A has no school_constraints, the engine must NOT pull
    administrative_constraints scoped to another school (cross-tenant leak).
    """
    engine = SmartSchedulingEngine(db)
    constraints = await engine._load_school_constraints(school_a_id)
    for c in constraints:
        assert c.get("school_id") == school_a_id, (
            f"Cross-tenant leak: constraint {c.get('id')} belongs to "
            f"{c.get('school_id')}, not {school_a_id}"
        )


async def test_engine_refuses_cross_tenant_generation(school_a_id, school_b_id):
    """The engine entry must reject generation requests where the caller's
    tenant does not match the target school_id (defence in depth — F-EN-06).
    """
    engine = SmartSchedulingEngine(db)
    principal_a_user = {
        "role": "school_principal",
        "tenant_id": school_a_id,
        "school_id": school_a_id,
    }
    with pytest.raises(HTTPException) as exc:
        await engine.generate_timetable(
            school_id=school_b_id,
            calling_user=principal_a_user,
        )
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# F-API-04: scheduling_core_routes list/get cross-tenant denial
# ---------------------------------------------------------------------------


async def test_get_time_slots_rejects_other_school(
    client, school_principal_headers, school_b_id
):
    r = await client.get(
        f"/time-slots?school_id={school_b_id}",
        headers=school_principal_headers,
    )
    assert r.status_code == 403


async def test_get_teacher_assignments_rejects_other_school(
    client, school_principal_headers, school_b_id
):
    r = await client.get(
        f"/teacher-assignments?school_id={school_b_id}",
        headers=school_principal_headers,
    )
    assert r.status_code == 403


async def test_get_schedules_rejects_other_school(
    client, school_principal_headers, school_b_id
):
    r = await client.get(
        f"/schedules?school_id={school_b_id}",
        headers=school_principal_headers,
    )
    assert r.status_code == 403


async def test_get_schedule_sessions_rejects_other_school_schedule(
    client, school_principal_headers, school_b_schedule_id
):
    """schedule-sessions takes a `schedule_id` (not `school_id`); the
    cross-tenant attack vector is passing another school's schedule_id
    (IDOR). Resource-based check required.
    """
    r = await client.get(
        f"/schedule-sessions?schedule_id={school_b_schedule_id}",
        headers=school_principal_headers,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# F-API-01 / F-API-16: scheduling_smart_engine_routes cross-tenant denial
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method,path_template", [
    ("GET", "/smart-scheduling/validate/{school_id}"),
    ("POST", "/smart-scheduling/generate/{school_id}"),
    ("GET", "/smart-scheduling/timetables/{school_id}"),
    ("GET", "/smart-scheduling/timetable/{timetable_id}"),
    ("GET", "/smart-scheduling/timetable/{timetable_id}/sessions"),
    ("GET", "/smart-scheduling/timetable/{timetable_id}/conflicts"),
    ("POST", "/smart-scheduling/timetable/{timetable_id}/publish"),
    ("POST", "/smart-scheduling/timetable/{timetable_id}/archive"),
    ("GET", "/smart-scheduling/pre-check/{school_id}"),
    ("GET", "/smart-scheduling/demand-matrix/{school_id}"),
    ("GET", "/smart-scheduling/resource-matrix/{school_id}"),
    ("DELETE", "/smart-scheduling/timetable/{timetable_id}"),
])
async def test_smart_engine_endpoints_reject_other_school(
    client, school_principal_headers,
    school_b_id, school_b_timetable_id,
    method, path_template,
):
    path = path_template.format(school_id=school_b_id, timetable_id=school_b_timetable_id)
    r = await client.request(method, path, headers=school_principal_headers)
    assert r.status_code == 403, (
        f"{method} {path} should deny cross-tenant; got {r.status_code} {r.text}"
    )


@pytest.mark.parametrize("path", [
    "/smart-scheduling/timetable/versions",
    "/smart-scheduling/timetable/active/sessions",
])
async def test_smart_engine_header_endpoints_reject_other_school(
    client, school_principal_headers, school_b_id, path,
):
    headers = {**school_principal_headers, "X-School-Context": school_b_id}
    r = await client.get(path, headers=headers)
    assert r.status_code == 403


async def test_generate_smart_rejects_other_school_in_body(
    client, school_principal_headers, school_b_id,
):
    r = await client.post(
        "/timetable/generate-smart",
        headers=school_principal_headers,
        json={"school_id": school_b_id},
    )
    assert r.status_code == 403


async def test_generate_smart_rejects_other_school_in_header(
    client, school_principal_headers, school_b_id,
):
    headers = {**school_principal_headers, "X-School-Context": school_b_id}
    r = await client.post(
        "/timetable/generate-smart",
        headers=headers,
        json={},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# F-API-02: principal_timetable_routes — RBAC + tenant denial
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method,path,body", [
    ("GET",    "/principal/timetable/summary", None),
    ("GET",    "/principal/timetable/readiness", None),
    ("GET",    "/principal/timetable/versions", None),
    ("GET",    "/principal/timetable/grid", None),
    ("POST",   "/principal/timetable/generate", {}),
    ("POST",   "/principal/timetable/version/{vid}/publish", {}),
    ("POST",   "/principal/timetable/version/{vid}/fill-gaps", {}),
    ("POST",   "/principal/timetable/sessions/swap", {"session_a_id": "x", "session_b_id": "y"}),
    ("POST",   "/principal/timetable/sessions/move", {"session_id": "x", "target_slot_id": "y"}),
    ("GET",    "/principal/timetable/session/{sid}", None),
])
async def test_principal_timetable_rejects_teacher(
    client, teacher_a_token, school_a_id, school_a_version_id, school_a_session_id,
    method, path, body,
):
    """A teacher must NOT be able to call principal-only endpoints
    even for their own school."""
    path = path.format(vid=school_a_version_id, sid=school_a_session_id)
    r = await client.request(
        method, path,
        headers={
            "Authorization": f"Bearer {teacher_a_token}",
            "X-School-Context": school_a_id,
        },
        json=body,
    )
    assert r.status_code in (401, 403), (
        f"{method} {path} accepted a teacher token; got {r.status_code} {r.text}"
    )


async def test_principal_timetable_rejects_other_school_header(
    client, principal_a_token, school_b_id,
):
    """Principal of school A passing X-School-Context: school-B must be 403."""
    r = await client.get(
        "/principal/timetable/summary",
        headers={
            "Authorization": f"Bearer {principal_a_token}",
            "X-School-Context": school_b_id,
        },
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# F-API-03: timetable_readiness_routes — tenant + auth denial
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", [
    "/timetable-readiness/check",
    "/timetable-readiness/summary",
])
async def test_readiness_rejects_other_school_header(
    client, principal_a_token, school_b_id, path,
):
    r = await client.get(
        path,
        headers={
            "Authorization": f"Bearer {principal_a_token}",
            "X-School-Context": school_b_id,
        },
    )
    assert r.status_code == 403


async def test_readiness_rejects_unauthenticated(client):
    r = await client.get("/timetable-readiness/check")
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# F-EN-06 (Gap 1): scheduling_generation_routes — POST /schedules/{id}/generate
# must reject cross-tenant schedule_id (IDOR via path param).
# ---------------------------------------------------------------------------


async def test_generate_schedule_rejects_other_school_schedule(
    client, school_principal_headers, school_b_schedule_id,
):
    r = await client.post(
        f"/schedules/{school_b_schedule_id}/generate",
        headers=school_principal_headers,
    )
    assert r.status_code == 403, (
        f"POST /schedules/{school_b_schedule_id}/generate accepted cross-tenant; "
        f"got {r.status_code} {r.text}"
    )


# ---------------------------------------------------------------------------
# Gap 2: scheduling_core_routes create handlers must reject body.school_id
# pointing at another tenant.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path,body_extra", [
    ("/time-slots", {"period_number": 1, "start_time": "08:00", "end_time": "09:00"}),
    ("/teacher-assignments", {
        "teacher_id": "00000000-0000-0000-0000-000000000001",
        "subject_id": "00000000-0000-0000-0000-000000000002",
    }),
    ("/schedules", {"name": "X", "academic_year": "2025-2026", "semester": "1"}),
])
async def test_create_handlers_reject_other_school_in_body(
    client, school_principal_headers, school_b_id, path, body_extra,
):
    body = {"school_id": school_b_id, **body_extra}
    r = await client.post(path, headers=school_principal_headers, json=body)
    assert r.status_code == 403, (
        f"POST {path} accepted cross-tenant body school_id; got {r.status_code} {r.text}"
    )


async def test_create_schedule_session_rejects_other_school_schedule(
    client, school_principal_headers, school_b_schedule_id,
):
    r = await client.post(
        "/schedule-sessions",
        headers=school_principal_headers,
        json={
            "schedule_id": school_b_schedule_id,
            "day": "sunday",
            "period_number": 1,
        },
    )
    assert r.status_code == 403, (
        f"POST /schedule-sessions accepted cross-tenant schedule_id; "
        f"got {r.status_code} {r.text}"
    )


# ---------------------------------------------------------------------------
# Gap 4: positive control tests — legitimate principal access must work.
# ---------------------------------------------------------------------------


async def test_principal_own_school_summary_allowed(
    client, principal_a_token,
):
    r = await client.get(
        "/principal/timetable/summary",
        headers={"Authorization": f"Bearer {principal_a_token}"},
    )
    assert r.status_code not in (401, 403), (
        f"Principal denied access to own-school summary; got {r.status_code} {r.text}"
    )


async def test_principal_own_school_with_matching_header(
    client, principal_a_token, school_a_id,
):
    r = await client.get(
        "/principal/timetable/summary",
        headers={
            "Authorization": f"Bearer {principal_a_token}",
            "X-School-Context": school_a_id,
        },
    )
    assert r.status_code not in (401, 403), (
        f"Principal denied with matching X-School-Context; got {r.status_code} {r.text}"
    )


async def test_readiness_own_school_allowed(
    client, principal_a_token, school_a_id,
):
    r = await client.get(
        "/timetable-readiness/check",
        headers={
            "Authorization": f"Bearer {principal_a_token}",
            "X-School-Context": school_a_id,
        },
    )
    assert r.status_code not in (401, 403), (
        f"Principal denied readiness for own school; got {r.status_code} {r.text}"
    )
