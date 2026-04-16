import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from engines.hakim_ai_engine import HakimAIEngine
from engines.sql_utils import gd_insert
from dependencies import db
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


async def _seed_student_local(school_id, class_id):
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": school_id, "full_name": f"ST-{sid[:6]}",
        "class_id": class_id, "is_active": True,
    })
    return {"id": sid, "school_id": school_id, "parent_id": None}


@pytest_asyncio.fixture
async def seeded_school():
    school_id = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": "Test School",
        "code": f"TS-{school_id[:8]}",
        "status": "active",
    })
    cls = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {"id": cls, "school_id": school_id, "name": "1A"})
    students = []
    for _ in range(10):
        students.append(await _seed_student_local(school_id, cls))

    class _S:
        id = school_id
        students = None

    s = _S()
    s.db = db
    s.students = students
    return s


@pytest.mark.asyncio
async def test_batch_returns_one_entry_per_student(seeded_school):
    engine = HakimAIEngine(seeded_school.db)
    ids = [s["id"] for s in seeded_school.students[:5]]
    results = await engine.analyze_students_risk_batch(seeded_school.id, ids, days_back=30)
    assert len(results) == 5
    by_id = {r["student_id"]: r for r in results}
    for sid in ids:
        assert sid in by_id
        r = by_id[sid]
        assert 0 <= r["risk_score"] <= 100
        assert r["risk_category"] in {"low", "medium", "high", "critical"}
        assert set(r["breakdown"].keys()) == {"attendance", "participation", "behaviour", "academic"}


@pytest.mark.asyncio
async def test_batch_matches_single_call(seeded_school):
    engine = HakimAIEngine(seeded_school.db)
    sid = seeded_school.students[0]["id"]
    single = await engine.analyze_student_risk(sid, seeded_school.id, days_back=30)
    batch = (await engine.analyze_students_risk_batch(seeded_school.id, [sid], days_back=30))[0]
    assert batch["risk_score"] == single["risk_score"]
    assert batch["breakdown"] == single["breakdown"]


@pytest.mark.asyncio
async def test_batch_identical_to_single_for_all(seeded_school):
    engine = HakimAIEngine(seeded_school.db)
    ids = [s["id"] for s in seeded_school.students]
    batch = {r["student_id"]: r for r in
             await engine.analyze_students_risk_batch(seeded_school.id, ids, days_back=30)}
    for sid in ids:
        single = await engine.analyze_student_risk(sid, seeded_school.id, days_back=30)
        assert batch[sid]["risk_score"] == single["risk_score"], sid
        assert batch[sid]["breakdown"] == single["breakdown"], sid
        assert batch[sid]["risk_category"] == single["risk_category"], sid


@pytest.mark.asyncio
async def test_batch_empty_list(seeded_school):
    engine = HakimAIEngine(seeded_school.db)
    assert await engine.analyze_students_risk_batch(seeded_school.id, [], days_back=30) == []
