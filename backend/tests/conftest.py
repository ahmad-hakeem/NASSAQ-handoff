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
async def platform_admin_headers():
    return _headers(await _mk_user(UserRole.PLATFORM_ADMIN, str(uuid.uuid4())))


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
