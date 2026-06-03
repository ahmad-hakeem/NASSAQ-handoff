"""Regression: Independent-Teacher schedule visibility.

Root cause guarded here: the IT weekly schedule grid (جدولي /
TeacherSchedulePage) builds its rows from ``GET /time-slots`` and renders the
empty state ("لا يوجد جدول حالياً") whenever the slot list is empty. The
``GET /time-slots`` read used to live on a router gated by
``require_full_school_tenant``, which returns 403 to every IT caller — so the
IT-synthesised slots were unreachable and the saved schedule never rendered,
even though ``GET /teacher/schedule/{id}`` already returned the sessions.

The fix mounts the read-only ``GET /time-slots`` route WITHOUT the
full-tenant gate. These tests assert:
  1. an IT caller now reaches ``/time-slots`` (200, not 403) and gets
     synthesised class slots;
  2. both inputs the grid needs — time-slots AND teacher schedule — resolve
     non-empty for a workspace that has a saved session;
  3. a full-tenant (non-IT) caller still reads its real persisted slots
     (no regression from moving the route off the gated router).
"""
from __future__ import annotations

import uuid

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_update_one

from tests.test_independent_teacher_schedule import (
    _headers,
    _mk_independent_teacher_with_workspace,
)

TIME_SLOTS_PATH = "/time-slots"


async def _mk_bootstrapped_it():
    """Like ``_mk_independent_teacher_with_workspace`` but also links the
    user to its workspace (``users.tenant_id = itw_{user_id}``), mirroring a
    real account AFTER bootstrap. ``/time-slots`` resolves the school via the
    caller's tenant context, so an unlinked (tenant_id=None) account is a
    different, pre-bootstrap failure mode and not what this regression covers."""
    ctx = await _mk_independent_teacher_with_workspace()
    await gd_update_one(
        db.session, "users", {"id": ctx["user"]["id"]},
        {"tenant_id": ctx["wsid"]},
    )
    ctx["user"]["tenant_id"] = ctx["wsid"]
    return ctx


@pytest.mark.asyncio
async def test_it_caller_can_read_synthesized_time_slots(client):
    """The exact regression: an IT caller must NOT get the full-tenant 403
    on ``/time-slots`` and must receive synthesised class slots so the
    weekly grid can render."""
    ctx = await _mk_bootstrapped_it()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])

    resp = await client.get(TIME_SLOTS_PATH, headers=h)

    assert resp.status_code == 200, resp.text
    slots = resp.json()
    assert isinstance(slots, list)
    # Workspace was seeded with periods_per_day=7, so synthesis must produce
    # class slots (the frontend filters out is_break rows before rendering).
    class_slots = [s for s in slots if not s.get("is_break")]
    assert class_slots, f"expected synthesised class slots, got {slots}"
    first = class_slots[0]
    assert first.get("start_time") and first.get("end_time")
    assert first.get("school_id") == ctx["wsid"]


@pytest.mark.asyncio
async def test_it_schedule_and_time_slots_both_resolve_for_grid(client):
    """End-to-end inputs for the جدولي grid: with a saved schedule_session,
    both ``/time-slots`` (rows) and ``/teacher/schedule/{id}`` (sessions)
    return non-empty for the owning IT teacher."""
    ctx = await _mk_bootstrapped_it()
    wsid = ctx["wsid"]
    await gd_insert(db.session, "schedule_sessions", {
        "id": str(uuid.uuid4()),
        "school_id": wsid,
        "schedule_id": f"itw_schedule_{wsid}",
        "teacher_id": ctx["teacher_id"],
        "class_id": ctx["class_id"],
        "subject_id": ctx["subject_id"],
        "day_of_week": "sun",
        "slot_number": 1,
        "status": "scheduled",
        "subject_name": "الرياضيات",
        "class_name": "فصل أ",
    })
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], wsid)

    slots_resp = await client.get(TIME_SLOTS_PATH, headers=h)
    assert slots_resp.status_code == 200, slots_resp.text
    assert [s for s in slots_resp.json() if not s.get("is_break")]

    sched_resp = await client.get(
        f"/teacher/schedule/{ctx['teacher_id']}", headers=h
    )
    assert sched_resp.status_code == 200, sched_resp.text
    sessions = sched_resp.json()
    assert isinstance(sessions, list) and len(sessions) == 1
    assert sessions[0]["day_of_week"] == "sunday"
    assert sessions[0]["class_id"] == ctx["class_id"]


@pytest.mark.asyncio
async def test_full_tenant_principal_still_reads_persisted_time_slots(client):
    """No regression for non-IT: moving the route off the gated router must
    not change full-tenant behaviour — a principal still reads the real
    persisted ``time_slots`` rows for their school."""
    school_id = f"SCH-{uuid.uuid4().hex[:8]}"
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": "مدرسة كاملة",
        "code": f"FT{uuid.uuid4().hex[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "private",
        "tenant_type": "school",
    })
    slot_id = str(uuid.uuid4())
    await gd_insert(db.session, "time_slots", {
        "id": slot_id,
        "school_id": school_id,
        "name": "الحصة 1",
        "start_time": "08:00",
        "end_time": "08:45",
        "slot_number": 1,
        "period_number": 1,
        "is_break": False,
        "is_active": True,
    })
    principal_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": principal_id,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "email": f"principal-{principal_id}@t.test",
        "full_name": "مدير",
        "is_active": True,
        "password_hash": "x",
    })
    token = create_access_token({
        "sub": principal_id,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
    })
    h = {"Authorization": f"Bearer {token}"}

    resp = await client.get(TIME_SLOTS_PATH, headers=h)

    assert resp.status_code == 200, resp.text
    slots = resp.json()
    assert any(s.get("id") == slot_id for s in slots), slots


@pytest.mark.asyncio
async def test_it_caller_cannot_read_foreign_workspace_time_slots(client):
    """Security: now that /time-slots is mounted off the full-tenant gate, the
    handler must bind the tenant itself. An IT caller passing another
    workspace's school_id must be denied (403), not handed foreign slots."""
    victim = await _mk_bootstrapped_it()
    attacker = await _mk_bootstrapped_it()
    h = _headers(attacker["user"]["id"], attacker["user"]["role"], attacker["wsid"])

    resp = await client.get(
        f"{TIME_SLOTS_PATH}?school_id={victim['wsid']}", headers=h
    )

    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_principal_cannot_read_foreign_school_time_slots(client):
    """Security: a full-tenant principal must not read another school's slots
    by supplying a foreign ?school_id= (the override is validated against the
    caller's own tenant)."""
    victim_school = f"SCH-{uuid.uuid4().hex[:8]}"
    await gd_insert(db.session, "schools", {
        "id": victim_school, "name": "ضحية", "code": f"V{uuid.uuid4().hex[:8]}",
        "status": "active", "country": "SA", "language": "ar",
        "school_type": "private", "tenant_type": "school",
    })
    await gd_insert(db.session, "time_slots", {
        "id": str(uuid.uuid4()), "school_id": victim_school, "name": "الحصة 1",
        "start_time": "08:00", "end_time": "08:45", "slot_number": 1,
        "period_number": 1, "is_break": False, "is_active": True,
    })
    attacker_school = f"SCH-{uuid.uuid4().hex[:8]}"
    await gd_insert(db.session, "schools", {
        "id": attacker_school, "name": "مهاجم", "code": f"A{uuid.uuid4().hex[:8]}",
        "status": "active", "country": "SA", "language": "ar",
        "school_type": "private", "tenant_type": "school",
    })
    principal_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": principal_id,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": attacker_school,
        "email": f"attacker-{principal_id}@t.test",
        "full_name": "مهاجم",
        "is_active": True,
        "password_hash": "x",
    })
    token = create_access_token({
        "sub": principal_id,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": attacker_school,
    })
    h = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        f"{TIME_SLOTS_PATH}?school_id={victim_school}", headers=h
    )

    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_platform_admin_direct_school_id_addressing_preserved(client):
    """Guardrail: this fix must NOT change platform-admin behaviour. A
    platform admin supplying ?school_id= reads that school's slots directly
    (no impersonation token required), matching pre-fix behaviour. This test
    pins the documented route-level exception so future hardening doesn't
    silently break it."""
    target_school = f"SCH-{uuid.uuid4().hex[:8]}"
    await gd_insert(db.session, "schools", {
        "id": target_school, "name": "هدف", "code": f"T{uuid.uuid4().hex[:8]}",
        "status": "active", "country": "SA", "language": "ar",
        "school_type": "private", "tenant_type": "school",
    })
    slot_id = str(uuid.uuid4())
    await gd_insert(db.session, "time_slots", {
        "id": slot_id, "school_id": target_school, "name": "الحصة 1",
        "start_time": "08:00", "end_time": "08:45", "slot_number": 1,
        "period_number": 1, "is_break": False, "is_active": True,
    })
    admin_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": admin_id,
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": None,
        "email": f"admin-{admin_id}@t.test",
        "full_name": "مشرف المنصة",
        "is_active": True,
        "password_hash": "x",
    })
    token = create_access_token({
        "sub": admin_id,
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": None,
    })
    h = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        f"{TIME_SLOTS_PATH}?school_id={target_school}", headers=h
    )

    assert resp.status_code == 200, resp.text
    assert any(s.get("id") == slot_id for s in resp.json()), resp.text
