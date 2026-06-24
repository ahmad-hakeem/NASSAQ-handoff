"""Reconciliation tests for the principal/admin AI Insights overview.

The AI Insights Center (مركز الرؤى الاصطناعي) overview cards MUST report the
same roster and attendance numbers as the operational attendance board
(لوحة الحضور / ``/school/dashboard``):

* ``total_students`` / ``total_teachers`` count only ``is_active`` rows
  (archived / deactivated entities are excluded), exactly like the board.
* ``attendance_rate`` (the card is labelled "اليوم" / today) is computed from
  *today's* attendance records, not an all-time cumulative figure.

These tests pin the canonical definitions so the two surfaces never drift.
"""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from httpx import AsyncClient

from dependencies import db
from engines.sql_utils import gd_insert


async def _mk_student(school_id, active=True, class_id=None):
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": school_id,
        "full_name": f"ST-{sid[:6]}",
        "class_id": class_id,
        "is_active": active,
    })
    return sid


async def _mk_teacher(school_id, active=True):
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid,
        "school_id": school_id,
        "full_name": f"T-{tid[:6]}",
        "is_active": active,
    })
    return tid


async def _mk_attendance(school_id, student_id, date_str, status):
    await gd_insert(db.session, "attendance", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "student_id": student_id,
        "date": date_str,
        "status": status,
    })


@pytest.mark.asyncio
async def test_overview_counts_exclude_inactive(client: AsyncClient, school_admin_headers, tenant_a):
    """total_students / total_teachers must exclude inactive (archived) rows."""
    for _ in range(6):
        await _mk_student(tenant_a, active=True)
    for _ in range(4):
        await _mk_student(tenant_a, active=False)
    for _ in range(3):
        await _mk_teacher(tenant_a, active=True)
    for _ in range(2):
        await _mk_teacher(tenant_a, active=False)

    r = await client.get("/ai/insights/overview", headers=school_admin_headers)
    assert r.status_code == 200, r.text
    m = r.json()["metrics"]
    assert m["total_students"] == 6, m
    assert m["total_teachers"] == 3, m


@pytest.mark.asyncio
async def test_overview_attendance_rate_is_today(client: AsyncClient, school_admin_headers, tenant_a):
    """The 'اليوم' attendance card reflects TODAY's records, not all-time."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    old = (datetime.now(timezone.utc) - timedelta(days=40)).strftime("%Y-%m-%d")

    students = [await _mk_student(tenant_a, active=True) for _ in range(5)]

    # Today: 4 present / 1 absent => 80%
    for sid in students[:4]:
        await _mk_attendance(tenant_a, sid, today, "present")
    await _mk_attendance(tenant_a, students[4], today, "absent")

    # Old history (40 days ago): all present => would inflate an all-time rate.
    for sid in students:
        for _ in range(4):
            await _mk_attendance(tenant_a, sid, old, "present")

    r = await client.get("/ai/insights/overview", headers=school_admin_headers)
    assert r.status_code == 200, r.text
    m = r.json()["metrics"]
    assert m["attendance_rate"] == 80.0, m


@pytest.mark.asyncio
async def test_overview_reconciles_with_attendance_board(client: AsyncClient, school_admin_headers, tenant_a):
    """AI overview roster counts AND today's attendance rate must equal the
    /school/dashboard board values (the exact bug that was reported)."""
    active_students = [await _mk_student(tenant_a, active=True) for _ in range(7)]
    for _ in range(3):
        await _mk_student(tenant_a, active=False)
    for _ in range(4):
        await _mk_teacher(tenant_a, active=True)
    for _ in range(2):
        await _mk_teacher(tenant_a, active=False)

    # Today's student attendance: 4 present / 1 absent => 80% on both surfaces.
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for sid in active_students[:4]:
        await _mk_attendance(tenant_a, sid, today, "present")
    await _mk_attendance(tenant_a, active_students[4], today, "absent")

    ai = await client.get("/ai/insights/overview", headers=school_admin_headers)
    board = await client.get("/school/dashboard", headers=school_admin_headers)
    assert ai.status_code == 200, ai.text
    assert board.status_code == 200, board.text

    ai_m = ai.json()["metrics"]
    board_m = board.json()["metrics"]
    assert ai_m["total_students"] == board_m["totalStudents"]["value"]
    assert ai_m["total_teachers"] == board_m["totalTeachers"]["value"]

    # Displayed attendance-rate parity. The board value is a string like "80.0%".
    board_rate = float(str(board_m["attendanceRate"]["value"]).rstrip("%"))
    assert ai_m["attendance_rate"] == board_rate == 80.0
