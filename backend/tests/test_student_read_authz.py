"""
Regression tests for Task #344 — Student Read Authorization Issues.

Verifies that the four previously unguarded student-by-ID read endpoints
now enforce per-student relationship checks, rejecting callers who are not
the student, a guardian, an assigned teacher, or a school admin.

Endpoints under test:
  GET /reports/student/{student_id}
  GET /attendance/summary/student/{student_id}
  GET /attendance/excuses/student/{student_id}
  GET /student/{student_id}/score
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


async def _mk_student(school_id: str) -> dict:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": sid,
        "full_name": f"ST-{sid[:6]}",
        "school_id": school_id,
        "is_active": True,
    })
    return {"id": sid, "school_id": school_id}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def school_a() -> str:
    return await _mk_school()


@pytest_asyncio.fixture
async def school_b() -> str:
    return await _mk_school()


@pytest_asyncio.fixture
async def student_a(school_a) -> dict:
    return await _mk_student(school_a)


@pytest_asyncio.fixture
async def principal_a_headers(school_a):
    user = await _mk_user(UserRole.SCHOOL_PRINCIPAL, school_a)
    return _tok(user)


@pytest_asyncio.fixture
async def unrelated_teacher_a_headers(school_a):
    """Teacher in school A but with NO assignment to the student's class."""
    user = await _mk_user(UserRole.TEACHER, school_a)
    return _tok(user)


@pytest_asyncio.fixture
async def unrelated_parent_a_headers(school_a):
    """Parent in school A but NOT linked to the target student."""
    user = await _mk_user(UserRole.PARENT, school_a)
    return _tok(user)


@pytest_asyncio.fixture
async def cross_tenant_teacher_headers(school_b):
    """Teacher from school B — cross-tenant IDOR attempt."""
    user = await _mk_user(UserRole.TEACHER, school_b)
    return _tok(user)


# ---------------------------------------------------------------------------
# Tests — GET /reports/student/{student_id}
# ---------------------------------------------------------------------------

REPORT_ROUTE = "/reports/student/{sid}"


@pytest.mark.asyncio
async def test_report_unrelated_teacher_same_tenant_403(
    client, unrelated_teacher_a_headers, student_a
):
    r = await client.get(
        REPORT_ROUTE.format(sid=student_a["id"]),
        headers=unrelated_teacher_a_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_report_unrelated_parent_same_tenant_403(
    client, unrelated_parent_a_headers, student_a
):
    r = await client.get(
        REPORT_ROUTE.format(sid=student_a["id"]),
        headers=unrelated_parent_a_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_report_cross_tenant_403(
    client, cross_tenant_teacher_headers, student_a
):
    r = await client.get(
        REPORT_ROUTE.format(sid=student_a["id"]),
        headers=cross_tenant_teacher_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_report_principal_same_tenant_allowed(
    client, principal_a_headers, student_a
):
    r = await client.get(
        REPORT_ROUTE.format(sid=student_a["id"]),
        headers=principal_a_headers,
    )
    assert r.status_code not in (403, 401), r.text


# ---------------------------------------------------------------------------
# Tests — GET /attendance/summary/student/{student_id}
# ---------------------------------------------------------------------------

SUMMARY_ROUTE = "/attendance/summary/student/{sid}"


@pytest.mark.asyncio
async def test_attendance_summary_unrelated_teacher_same_tenant_403(
    client, unrelated_teacher_a_headers, student_a
):
    r = await client.get(
        SUMMARY_ROUTE.format(sid=student_a["id"]),
        headers=unrelated_teacher_a_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_attendance_summary_unrelated_parent_same_tenant_403(
    client, unrelated_parent_a_headers, student_a
):
    r = await client.get(
        SUMMARY_ROUTE.format(sid=student_a["id"]),
        headers=unrelated_parent_a_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_attendance_summary_cross_tenant_403(
    client, cross_tenant_teacher_headers, student_a
):
    r = await client.get(
        SUMMARY_ROUTE.format(sid=student_a["id"]),
        headers=cross_tenant_teacher_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_attendance_summary_principal_same_tenant_allowed(
    client, principal_a_headers, student_a
):
    r = await client.get(
        SUMMARY_ROUTE.format(sid=student_a["id"]),
        headers=principal_a_headers,
    )
    assert r.status_code not in (403, 401), r.text


# ---------------------------------------------------------------------------
# Tests — GET /attendance/excuses/student/{student_id}
# ---------------------------------------------------------------------------

EXCUSES_ROUTE = "/attendance/excuses/student/{sid}"


@pytest.mark.asyncio
async def test_excuses_unrelated_teacher_same_tenant_403(
    client, unrelated_teacher_a_headers, student_a
):
    r = await client.get(
        EXCUSES_ROUTE.format(sid=student_a["id"]),
        headers=unrelated_teacher_a_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_excuses_unrelated_parent_same_tenant_403(
    client, unrelated_parent_a_headers, student_a
):
    r = await client.get(
        EXCUSES_ROUTE.format(sid=student_a["id"]),
        headers=unrelated_parent_a_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_excuses_cross_tenant_403(
    client, cross_tenant_teacher_headers, student_a
):
    r = await client.get(
        EXCUSES_ROUTE.format(sid=student_a["id"]),
        headers=cross_tenant_teacher_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_excuses_principal_same_tenant_allowed(
    client, principal_a_headers, student_a
):
    r = await client.get(
        EXCUSES_ROUTE.format(sid=student_a["id"]),
        headers=principal_a_headers,
    )
    assert r.status_code not in (403, 401), r.text


# ---------------------------------------------------------------------------
# Tests — GET /student/{student_id}/score  (cross-tenant IDOR)
# ---------------------------------------------------------------------------

SCORE_ROUTE = "/student/{sid}/score"


@pytest.mark.asyncio
async def test_score_unrelated_teacher_same_tenant_403(
    client, unrelated_teacher_a_headers, student_a
):
    r = await client.get(
        SCORE_ROUTE.format(sid=student_a["id"]),
        headers=unrelated_teacher_a_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_score_unrelated_parent_same_tenant_403(
    client, unrelated_parent_a_headers, student_a
):
    r = await client.get(
        SCORE_ROUTE.format(sid=student_a["id"]),
        headers=unrelated_parent_a_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_score_cross_tenant_idor_403(
    client, cross_tenant_teacher_headers, student_a
):
    """Cross-tenant IDOR: teacher from school B must not read school A student score."""
    r = await client.get(
        SCORE_ROUTE.format(sid=student_a["id"]),
        headers=cross_tenant_teacher_headers,
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_score_principal_same_tenant_allowed(
    client, principal_a_headers, student_a
):
    r = await client.get(
        SCORE_ROUTE.format(sid=student_a["id"]),
        headers=principal_a_headers,
    )
    assert r.status_code not in (403, 401), r.text


@pytest.mark.asyncio
async def test_score_unauthenticated_401(client, student_a):
    r = await client.get(SCORE_ROUTE.format(sid=student_a["id"]))
    assert r.status_code == 401, r.text
