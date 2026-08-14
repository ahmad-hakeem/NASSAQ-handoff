import os
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

os.environ.setdefault("TESTING", "1")

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from server import app
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert
from db import _get_async_url


@pytest_asyncio.fixture(autouse=True)
async def _db_session():
    engine = create_async_engine(_get_async_url(), poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        db.set_session(s)
        try:
            yield s
        finally:
            await s.rollback()
            db.set_session(None)
    await engine.dispose()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The rate-limit store is a process-global singleton. Reset it around
    every test so create/auth-heavy suites don't bleed their request counts
    into unrelated tests (and so rate-limit tests start from a clean window).

    The shared (Postgres-backed) store also survives *between* tests, so give
    each test its own key namespace instead of deleting rows: isolation
    without a DELETE per test, and the real shared code path still runs."""
    from src.core.middleware.rate_limiter import rate_store

    def _clear():
        rate_store._store.clear()
        if hasattr(rate_store, "_deny_until"):
            rate_store._deny_until.clear()
        if hasattr(rate_store, "set_namespace"):
            rate_store.set_namespace(f"t{uuid.uuid4().hex[:12]}")

    _clear()
    yield
    _clear()


async def _mk_user(role: UserRole, tenant_id: str) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": role.value,
        "tenant_id": tenant_id,
        "email": f"{uid}@t.test",
        "full_name": f"{role.value} user",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


def _headers(user: dict) -> dict:
    token = create_access_token({
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
    })
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api") as c:
        yield c


async def _mk_school(school_id: str) -> None:
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": f"School-{school_id[:6]}",
        "code": f"S{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })


@pytest_asyncio.fixture
async def tenant_a():
    sid = str(uuid.uuid4())
    await _mk_school(sid)
    return sid


@pytest_asyncio.fixture
async def tenant_b():
    sid = str(uuid.uuid4())
    await _mk_school(sid)
    return sid


@pytest_asyncio.fixture
async def school_admin_headers(tenant_a):
    return _headers(await _mk_user(UserRole.SCHOOL_ADMIN, tenant_a))


@pytest_asyncio.fixture
async def school_sub_admin_headers(tenant_a):
    return _headers(await _mk_user(UserRole.SCHOOL_SUB_ADMIN, tenant_a))


@pytest_asyncio.fixture
async def school_principal_headers(tenant_a):
    return _headers(await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a))


@pytest_asyncio.fixture
async def teacher_headers(tenant_a):
    return _headers(await _mk_user(UserRole.TEACHER, tenant_a))


@pytest_asyncio.fixture
async def parent_headers(tenant_a):
    return _headers(await _mk_user(UserRole.PARENT, tenant_a))


@pytest_asyncio.fixture
async def student_headers(tenant_a):
    return _headers(await _mk_user(UserRole.STUDENT, tenant_a))


@pytest_asyncio.fixture
async def platform_admin_headers(tenant_a):
    return _headers(await _mk_user(UserRole.PLATFORM_ADMIN, tenant_a))


@pytest_asyncio.fixture
async def tenant_a_admin(school_admin_headers):
    return school_admin_headers


async def _seed_student(school_id: str, with_parent: bool = True, class_id=None) -> dict:
    parent_id = str(uuid.uuid4()) if with_parent else None
    if parent_id:
        await gd_insert(db.session, "parents", {
            "id": parent_id,
            "full_name": f"Parent-{parent_id[:6]}",
            "email": f"p-{parent_id}@t.test",
            "school_id": school_id,
            "is_active": True,
        })
        await gd_insert(db.session, "users", {
            "id": parent_id,
            "role": "parent",
            "tenant_id": school_id,
            "email": f"p-{parent_id}@t.test",
            "full_name": f"Parent-{parent_id[:6]}",
            "is_active": True,
            "password_hash": "x",
        })
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": school_id,
        "full_name": f"ST-{sid[:6]}",
        "class_id": class_id,
        "parent_id": parent_id,
        "is_active": True,
    })
    return {"id": sid, "school_id": school_id, "parent_id": parent_id}


class _SchoolBundle:
    def __init__(self, id_, students):
        self.id = id_
        self.students = students


@pytest_asyncio.fixture
async def seeded_school(tenant_a):
    cls = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {"id": cls, "school_id": tenant_a, "name": "1A"})
    students = []
    for _ in range(10):
        students.append(await _seed_student(tenant_a, True, cls))
    return _SchoolBundle(tenant_a, students)


@pytest_asyncio.fixture
async def many_students_school(tenant_a):
    cls = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {"id": cls, "school_id": tenant_a, "name": "Big"})
    students = [await _seed_student(tenant_a, True, cls) for _ in range(120)]
    return _SchoolBundle(tenant_a, students)


@pytest_asyncio.fixture
async def tenant_b_students(tenant_b):
    return [await _seed_student(tenant_b, True) for _ in range(3)]


@pytest_asyncio.fixture
async def tenant_b_student(tenant_b_students):
    return tenant_b_students[0]


@pytest_asyncio.fixture
async def a_student(tenant_a):
    return await _seed_student(tenant_a, True)


@pytest_asyncio.fixture
async def student_with_parent(tenant_a):
    return await _seed_student(tenant_a, True)


@pytest_asyncio.fixture
async def orphan_student(tenant_a):
    return await _seed_student(tenant_a, with_parent=False)


@pytest_asyncio.fixture
async def school_a_id(tenant_a):
    return tenant_a


@pytest_asyncio.fixture
async def school_b_id(tenant_b):
    return tenant_b


@pytest_asyncio.fixture
async def seed_global_admin_constraint(school_b_id):
    """Seed an administrative_constraints row scoped to school B.

    The pre-fix engine fallback ignores school_id, so this row will leak
    into requests for school A; the post-fix engine must skip it.
    """
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "administrative_constraints", {
        "id": cid,
        "school_id": school_b_id,
        "is_active": True,
        "name": "global-admin-constraint",
        "constraint_type": "no_friday",
    })
    return cid


@pytest_asyncio.fixture
async def school_b_schedule_id(school_b_id):
    """Insert a schedules row owned by school B and return its id.

    Used to verify cross-tenant IDOR denial on /schedule-sessions.
    """
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schedules", {
        "id": sid,
        "school_id": school_b_id,
        "name": "School B Schedule",
        "academic_year": "2025-2026",
        "semester": 1,
        "status": "draft",
        "total_sessions": 0,
    })
    return sid


@pytest_asyncio.fixture
async def school_b_timetable_id(school_b_id):
    """Insert a timetables row owned by school B and return its id."""
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": tid,
        "school_id": school_b_id,
        "name": "School B Timetable",
        "academic_year": "2026-2027",
        "semester": 1,
        "status": "draft",
        "version": 1,
        "total_sessions": 0,
    })
    return tid


@pytest_asyncio.fixture
async def teacher_a_token(tenant_a):
    user = await _mk_user(UserRole.TEACHER, tenant_a)
    return create_access_token({
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
    })


@pytest_asyncio.fixture
async def principal_a_token(tenant_a):
    user = await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a)
    return create_access_token({
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
    })


@pytest_asyncio.fixture
async def school_a_version_id(tenant_a):
    """Insert a timetables row owned by school A and return its id."""
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": tid,
        "school_id": tenant_a,
        "name": "School A Timetable",
        "academic_year": "2026-2027",
        "semester": 1,
        "status": "draft",
        "version": 1,
        "total_sessions": 0,
    })
    return tid


@pytest_asyncio.fixture
async def school_a_session_id(tenant_a, school_a_version_id):
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "timetable_sessions", {
        "id": sid,
        "timetable_id": school_a_version_id,
        "school_id": tenant_a,
        "day_of_week": "sunday",
        "period_number": 1,
    })
    return sid


@pytest_asyncio.fixture
async def seed_school_b_constraint(school_b_id):
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "school_constraints", {
        "id": cid,
        "school_id": school_b_id,
        "is_active": True,
        "name": "school-b-only",
        "constraint_type": "no_first_period",
    })
    return cid


# ---------------------------------------------------------------------------
# Live-server legacy scripts (docs/ci/quarantine.md, "Environment-gated")
#
# Dozens of legacy test modules are HTTP integration scripts: they define a
# module-level ``BASE_URL`` from ``REACT_APP_BACKEND_URL`` and drive a
# RUNNING, seeded backend via ``requests``/``websockets``. In the merge gate
# there is no live server, so every such module is skipped wholesale unless
# an absolute base URL was explicitly provided. New tests must NOT follow
# this pattern — use the in-process ``client`` fixture above instead.
# ---------------------------------------------------------------------------
_LIVE_SERVER_SKIP = pytest.mark.skip(
    reason="live-server integration script: requires REACT_APP_BACKEND_URL "
           "pointing at a running, seeded backend (docs/ci/quarantine.md)",
)


def pytest_collection_modifyitems(config, items):
    # Opt-in is keyed on the ENV VAR, not the module's BASE_URL value: some
    # legacy scripts hardcode an absolute fallback URL (e.g.
    # test_iteration_73.py points at a long-dead preview host), so their
    # BASE_URL always "looks live" even when no server was provided.
    live_env = os.environ.get("REACT_APP_BACKEND_URL", "")
    live_opt_in = live_env.startswith(("http://", "https://"))
    for item in items:
        module = getattr(item, "module", None)
        base_url = getattr(module, "BASE_URL", None)
        if isinstance(base_url, str):
            if not live_opt_in or not base_url.startswith(("http://", "https://")):
                item.add_marker(_LIVE_SERVER_SKIP)


# ---------------------------------------------------------------------------
# MFA enforcement opt-in (docs/ci/quarantine.md)
#
# The backend gate (scripts/ci/backend_tests.sh) pins
# MFA_ENFORCEMENT_DISABLED=true for the whole suite — most tests mint users
# without MFA enrollment and would otherwise be rejected by the Task #443
# enrollment gate. Tests that assert the ENFORCED contracts (step-up 403
# envelopes, enrollment gate, bootstrap MFA) request this fixture.
# services/mfa_policy.py reads the env fresh on every call, so a monkeypatch
# takes effect immediately without any reload.
# ---------------------------------------------------------------------------
@pytest.fixture
def enforce_mfa(monkeypatch):
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "false")
