"""
Regression tests for Task #349 — School Data Access Control.

Covers the three high-severity broken-authorization issues:
  (A) Attendance section/report endpoints: parents/students denied;
      unassigned same-tenant teachers denied on section-specific routes.
  (B) Legacy school-wide reporting endpoints: parents/students denied;
      unassigned teachers denied on class-specific reporting routes.
  (C) Student/parent directory endpoints: parents/students denied on
      bulk list routes; unrelated callers denied on per-student reads;
      parents denied on the parent directory.
  (D) POST /attendance/excuses: unrelated same-tenant callers cannot
      submit excuses for another student.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tok(user: dict) -> dict:
    token = create_access_token({
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_user(role: UserRole, tenant_id: str) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": role.value,
        "tenant_id": tenant_id,
        "email": f"{uid}@t.test",
        "full_name": f"{role.value}-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


async def _mk_school() -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid,
        "name": f"School-{sid[:6]}",
        "code": f"S{sid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    return sid


async def _mk_class(school_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "tenant_id": school_id,
        "name": f"Class-{cid[:6]}",
    })
    return cid


async def _mk_student(school_id: str, class_id: str | None = None) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": school_id,
        "full_name": f"ST-{sid[:6]}",
        "is_active": True,
        "class_id": class_id,
    })
    return sid


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def school_a() -> str:
    return await _mk_school()


@pytest_asyncio.fixture
async def class_a(school_a) -> str:
    return await _mk_class(school_a)


@pytest_asyncio.fixture
async def student_a(school_a, class_a) -> str:
    return await _mk_student(school_a, class_id=class_a)


@pytest_asyncio.fixture
async def principal_headers(school_a):
    return _tok(await _mk_user(UserRole.SCHOOL_PRINCIPAL, school_a))


@pytest_asyncio.fixture
async def unrelated_teacher_headers(school_a):
    """Teacher in school A but with NO assignment to the target class."""
    return _tok(await _mk_user(UserRole.TEACHER, school_a))


@pytest_asyncio.fixture
async def parent_headers(school_a):
    """Parent in school A but NOT linked to the target student."""
    return _tok(await _mk_user(UserRole.PARENT, school_a))


@pytest_asyncio.fixture
async def student_user_headers(school_a):
    """Student-role user in school A."""
    return _tok(await _mk_user(UserRole.STUDENT, school_a))


# ===========================================================================
# (A) Attendance section/report endpoints
# ===========================================================================

# GET /attendance/section/{section_id}

@pytest.mark.asyncio
async def test_section_attendance_parent_403(client, parent_headers, class_a):
    r = await client.get(
        f"/attendance/section/{class_a}",
        params={"attendance_date": "2025-01-01"},
        headers=parent_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_section_attendance_student_403(client, student_user_headers, class_a):
    r = await client.get(
        f"/attendance/section/{class_a}",
        params={"attendance_date": "2025-01-01"},
        headers=student_user_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_section_attendance_unassigned_teacher_403(
    client, unrelated_teacher_headers, class_a
):
    """Unassigned teacher in the same school must be denied (object-level check)."""
    r = await client.get(
        f"/attendance/section/{class_a}",
        params={"attendance_date": "2025-01-01"},
        headers=unrelated_teacher_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_section_attendance_principal_allowed(client, principal_headers, class_a):
    r = await client.get(
        f"/attendance/section/{class_a}",
        params={"attendance_date": "2025-01-01"},
        headers=principal_headers,
    )
    assert r.status_code not in (401, 403), r.text


# GET /attendance/reports/daily

@pytest.mark.asyncio
async def test_daily_report_parent_403(client, parent_headers):
    r = await client.get(
        "/attendance/reports/daily",
        params={"attendance_date": "2025-01-01"},
        headers=parent_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_daily_report_student_403(client, student_user_headers):
    r = await client.get(
        "/attendance/reports/daily",
        params={"attendance_date": "2025-01-01"},
        headers=student_user_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_daily_report_teacher_no_section_403(
    client, unrelated_teacher_headers
):
    """Teacher must supply a section_id; school-wide daily report is admin-only."""
    r = await client.get(
        "/attendance/reports/daily",
        params={"attendance_date": "2025-01-01"},
        headers=unrelated_teacher_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_daily_report_teacher_unassigned_section_403(
    client, unrelated_teacher_headers, class_a
):
    """Teacher supplies a section_id but has no assignment → denied."""
    r = await client.get(
        "/attendance/reports/daily",
        params={"attendance_date": "2025-01-01", "section_id": class_a},
        headers=unrelated_teacher_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_daily_report_principal_allowed(client, principal_headers):
    r = await client.get(
        "/attendance/reports/daily",
        params={"attendance_date": "2025-01-01"},
        headers=principal_headers,
    )
    assert r.status_code not in (401, 403), r.text


# GET /attendance/summary/section/{section_id}

@pytest.mark.asyncio
async def test_section_summary_parent_403(client, parent_headers, class_a):
    r = await client.get(
        f"/attendance/summary/section/{class_a}",
        params={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        headers=parent_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_section_summary_student_403(client, student_user_headers, class_a):
    r = await client.get(
        f"/attendance/summary/section/{class_a}",
        params={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        headers=student_user_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_section_summary_unassigned_teacher_403(
    client, unrelated_teacher_headers, class_a
):
    r = await client.get(
        f"/attendance/summary/section/{class_a}",
        params={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        headers=unrelated_teacher_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_section_summary_principal_allowed(client, principal_headers, class_a):
    r = await client.get(
        f"/attendance/summary/section/{class_a}",
        params={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        headers=principal_headers,
    )
    assert r.status_code not in (401, 403), r.text


# ===========================================================================
# (D) POST /attendance/excuses — unrelated caller blocked
# ===========================================================================

@pytest.mark.asyncio
async def test_excuse_unrelated_parent_403(client, parent_headers, student_a):
    """Unrelated parent (not a guardian of student_a) must be denied."""
    r = await client.post(
        "/attendance/excuses",
        json={
            "student_id": student_a,
            "excuse_type": "medical",
            "start_date": "2025-01-01",
            "end_date": "2025-01-02",
            "reason": "مرض",
        },
        headers=parent_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_excuse_unrelated_teacher_403(client, unrelated_teacher_headers, student_a):
    """Unassigned teacher cannot create an excuse for an unrelated student."""
    r = await client.post(
        "/attendance/excuses",
        json={
            "student_id": student_a,
            "excuse_type": "medical",
            "start_date": "2025-01-01",
            "end_date": "2025-01-02",
            "reason": "مرض",
        },
        headers=unrelated_teacher_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_excuse_student_user_403(client, student_user_headers, student_a):
    """Student-role users cannot file excuses (only guardians/admins may)."""
    r = await client.post(
        "/attendance/excuses",
        json={
            "student_id": student_a,
            "excuse_type": "medical",
            "start_date": "2025-01-01",
            "end_date": "2025-01-02",
            "reason": "مرض",
        },
        headers=student_user_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_excuse_principal_allowed(client, principal_headers, student_a):
    """School principal can create an excuse for any student in their school."""
    r = await client.post(
        "/attendance/excuses",
        json={
            "student_id": student_a,
            "excuse_type": "medical",
            "start_date": "2025-01-01",
            "end_date": "2025-01-02",
            "reason": "مرض",
        },
        headers=principal_headers,
    )
    assert r.status_code not in (401, 403), r.text


# ===========================================================================
# (B) Legacy school-wide reporting endpoints
# ===========================================================================

SCHOOL_REPORT_ENDPOINTS = [
    "/reports/school/overview",
    "/reports/school/attendance",
    "/reports/school/grades",
    "/reports/school/behavior",
    "/reports/school/top-classes",
]

ADMIN_ONLY_REPORT_ENDPOINTS = [
    "/reports/school/export",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", SCHOOL_REPORT_ENDPOINTS)
async def test_school_report_parent_403(client, parent_headers, path):
    r = await client.get(path, headers=parent_headers)
    assert r.status_code == 403, f"{path} -> {r.status_code} {r.text}"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", SCHOOL_REPORT_ENDPOINTS)
async def test_school_report_student_403(client, student_user_headers, path):
    r = await client.get(path, headers=student_user_headers)
    assert r.status_code == 403, f"{path} -> {r.status_code} {r.text}"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ADMIN_ONLY_REPORT_ENDPOINTS)
async def test_admin_only_report_parent_403(client, parent_headers, path):
    r = await client.get(path, headers=parent_headers)
    assert r.status_code == 403, f"{path} -> {r.status_code} {r.text}"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ADMIN_ONLY_REPORT_ENDPOINTS)
async def test_admin_only_report_teacher_403(client, unrelated_teacher_headers, path):
    """Export endpoints are admin-only; teachers must also be denied."""
    r = await client.get(path, headers=unrelated_teacher_headers)
    assert r.status_code == 403, f"{path} -> {r.status_code} {r.text}"


@pytest.mark.asyncio
async def test_class_report_parent_403(client, parent_headers, class_a):
    r = await client.get(f"/reports/class/{class_a}", headers=parent_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_class_report_student_403(client, student_user_headers, class_a):
    r = await client.get(f"/reports/class/{class_a}", headers=student_user_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_class_report_unassigned_teacher_403(
    client, unrelated_teacher_headers, class_a
):
    """Unassigned teacher must be denied the class-level report."""
    r = await client.get(f"/reports/class/{class_a}", headers=unrelated_teacher_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_class_report_principal_allowed(client, principal_headers, class_a):
    r = await client.get(f"/reports/class/{class_a}", headers=principal_headers)
    assert r.status_code not in (401, 403), r.text


@pytest.mark.asyncio
async def test_attendance_report_parent_403(client, parent_headers):
    r = await client.get(
        "/reports/attendance",
        params={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        headers=parent_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_attendance_report_teacher_no_class_403(client, unrelated_teacher_headers):
    """Teacher without a class_id requests school-wide attendance report → 403."""
    r = await client.get(
        "/reports/attendance",
        params={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        headers=unrelated_teacher_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_attendance_report_teacher_unassigned_class_403(
    client, unrelated_teacher_headers, class_a
):
    """Teacher specifies class_id but has no assignment → denied."""
    r = await client.get(
        "/reports/attendance",
        params={
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "class_id": class_a,
        },
        headers=unrelated_teacher_headers,
    )
    assert r.status_code == 403, r.text


# GET /reports/school/attendance (legacy) — teacher scoping

@pytest.mark.asyncio
async def test_school_attendance_report_parent_403(client, parent_headers):
    r = await client.get("/reports/school/attendance", headers=parent_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_school_attendance_report_student_403(client, student_user_headers):
    r = await client.get("/reports/school/attendance", headers=student_user_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_school_attendance_report_teacher_no_class_403(
    client, unrelated_teacher_headers
):
    """Teacher without class_id on school attendance report → 403 (admin-only school-wide)."""
    r = await client.get("/reports/school/attendance", headers=unrelated_teacher_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_school_attendance_report_teacher_unassigned_class_403(
    client, unrelated_teacher_headers, class_a
):
    """Teacher supplies class_id but has no assignment → denied."""
    r = await client.get(
        "/reports/school/attendance",
        params={"class_id": class_a},
        headers=unrelated_teacher_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_school_attendance_report_principal_allowed(client, principal_headers):
    r = await client.get("/reports/school/attendance", headers=principal_headers)
    assert r.status_code not in (401, 403), r.text


# ===========================================================================
# (C) Student / parent directory endpoints
# ===========================================================================

@pytest.mark.asyncio
async def test_students_list_parent_403(client, parent_headers):
    r = await client.get("/students", headers=parent_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_students_list_student_403(client, student_user_headers):
    r = await client.get("/students", headers=student_user_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_class_students_parent_403(client, parent_headers, class_a):
    r = await client.get(f"/classes/{class_a}/students", headers=parent_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_class_students_student_403(client, student_user_headers, class_a):
    r = await client.get(f"/classes/{class_a}/students", headers=student_user_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_class_students_unassigned_teacher_403(
    client, unrelated_teacher_headers, class_a
):
    """Unassigned teacher in the same school must be denied the class roster."""
    r = await client.get(f"/classes/{class_a}/students", headers=unrelated_teacher_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_student_by_id_unrelated_parent_403(
    client, parent_headers, student_a
):
    """Unrelated parent cannot read another student's profile."""
    r = await client.get(f"/students/{student_a}", headers=parent_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_student_by_id_unrelated_teacher_403(
    client, unrelated_teacher_headers, student_a
):
    """Unassigned teacher (same tenant) cannot read another student's profile."""
    r = await client.get(f"/students/{student_a}", headers=unrelated_teacher_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_student_by_id_principal_allowed(
    client, principal_headers, student_a
):
    r = await client.get(f"/students/{student_a}", headers=principal_headers)
    assert r.status_code not in (401, 403), r.text


@pytest.mark.asyncio
async def test_parents_list_parent_403(client, parent_headers):
    """Parent users cannot browse the parent directory."""
    r = await client.get("/parents", headers=parent_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_parents_list_teacher_403(client, unrelated_teacher_headers):
    """Teachers cannot browse the parent directory."""
    r = await client.get("/parents", headers=unrelated_teacher_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_parents_list_student_403(client, student_user_headers):
    r = await client.get("/parents", headers=student_user_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_parents_list_principal_allowed(client, principal_headers):
    r = await client.get("/parents", headers=principal_headers)
    assert r.status_code not in (401, 403), r.text
