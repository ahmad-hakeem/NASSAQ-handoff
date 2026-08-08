"""Memory-safety contract for the shared data-access helpers.

Root cause these tests pin down: ``gd_find`` had no default and no maximum
row limit, so "load the whole table into RAM" was the *default* behaviour of
the helper every route in this codebase uses (412 of 1061 call sites pass no
limit at all). Measured cost on this deployment: ~4.1 KB of process RSS per
materialised row, i.e. ~200 MB for a 50,000-row read.

The contract:
  * an unbounded ``gd_find`` is capped and the truncation is logged (never
    silent),
  * an explicit ``limit`` is still honoured (reports must not lose rows),
  * anything that legitimately needs every row streams it in bounded batches
    via ``gd_iter_batches`` instead of materialising one giant list,
  * caller-supplied page sizes cannot exceed a server-side maximum.
"""

import json
import uuid

import pytest

from dependencies import db
from engines import sql_utils
from engines.sql_utils import gd_find, gd_insert, gd_iter_batches, gd_update_many

pytestmark = pytest.mark.asyncio

PROBE = "mem_probe_docs"


async def _seed_probe(tenant_id: str, n: int) -> list:
    ids = []
    for i in range(n):
        doc_id = str(uuid.uuid4())
        await gd_insert(db.session, PROBE, {
            "id": doc_id,
            "tenant_id": tenant_id,
            "seq": i,
            "state": "initial",
        })
        ids.append(doc_id)
    await db.session.flush()
    return ids


# --------------------------------------------------------------------------
# gd_find ceiling
# --------------------------------------------------------------------------

async def test_unbounded_gd_find_is_capped_at_the_ceiling(monkeypatch):
    tenant = str(uuid.uuid4())
    await _seed_probe(tenant, 7)
    monkeypatch.setattr(sql_utils, "GD_FIND_MAX_ROWS", 3)

    rows = await gd_find(db.session, PROBE, {"tenant_id": tenant})

    assert len(rows) == 3, "a gd_find with no limit must not materialise the whole table"


async def test_explicit_limit_above_the_ceiling_is_honoured(monkeypatch):
    """Reports deliberately pass large limits; the cap must not silently
    shrink them, or report output starts losing rows."""
    tenant = str(uuid.uuid4())
    await _seed_probe(tenant, 7)
    monkeypatch.setattr(sql_utils, "GD_FIND_MAX_ROWS", 3)

    rows = await gd_find(db.session, PROBE, {"tenant_id": tenant}, limit=50)

    assert len(rows) == 7


async def test_truncation_is_logged_with_the_collection_name(monkeypatch, caplog):
    tenant = str(uuid.uuid4())
    await _seed_probe(tenant, 7)
    monkeypatch.setattr(sql_utils, "GD_FIND_MAX_ROWS", 3)

    with caplog.at_level("WARNING"):
        await gd_find(db.session, PROBE, {"tenant_id": tenant})

    assert any(PROBE in r.message for r in caplog.records), \
        "a truncated read must be observable, not silent"


async def test_short_reads_do_not_warn(monkeypatch, caplog):
    tenant = str(uuid.uuid4())
    await _seed_probe(tenant, 2)
    monkeypatch.setattr(sql_utils, "GD_FIND_MAX_ROWS", 3)

    with caplog.at_level("WARNING"):
        rows = await gd_find(db.session, PROBE, {"tenant_id": tenant})

    assert len(rows) == 2
    assert not [r for r in caplog.records if PROBE in r.message]


# --------------------------------------------------------------------------
# gd_iter_batches streaming
# --------------------------------------------------------------------------

async def test_iter_batches_covers_every_row_exactly_once():
    tenant = str(uuid.uuid4())
    seeded = set(await _seed_probe(tenant, 7))

    batches = []
    async for batch in gd_iter_batches(db.session, PROBE, {"tenant_id": tenant}, batch_size=3):
        batches.append([r["id"] for r in batch])

    flat = [i for b in batches for i in b]
    assert [len(b) for b in batches] == [3, 3, 1]
    assert set(flat) == seeded
    assert len(flat) == len(set(flat)), "keyset paging must not repeat rows"


async def test_iter_batches_never_holds_more_than_one_batch(monkeypatch):
    """Bounded memory means bounded round-trip size: N rows at batch_size B
    must cost ceil(N/B) queries, not one giant SELECT."""
    tenant = str(uuid.uuid4())
    await _seed_probe(tenant, 7)

    executed = []
    original = db.session.execute

    async def counting_execute(stmt, *a, **kw):
        executed.append(stmt)
        return await original(stmt, *a, **kw)

    monkeypatch.setattr(db.session, "execute", counting_execute)

    seen = 0
    async for batch in gd_iter_batches(db.session, PROBE, {"tenant_id": tenant}, batch_size=3):
        seen += len(batch)
        assert len(batch) <= 3

    assert seen == 7
    assert len(executed) >= 3


async def test_iter_rows_streams_single_rows_up_to_max_rows():
    """Row-level streaming: report aggregations keep their `for row in ...`
    loop body and stop materialising the whole result set."""
    from engines.sql_utils import gd_iter_rows

    tenant = str(uuid.uuid4())
    seeded = set(await _seed_probe(tenant, 7))

    seen = []
    async for row in gd_iter_rows(db.session, PROBE, {"tenant_id": tenant}, batch_size=2):
        seen.append(row["id"])
    assert set(seen) == seeded

    capped = [r async for r in gd_iter_rows(db.session, PROBE, {"tenant_id": tenant},
                                            batch_size=2, max_rows=3)]
    assert len(capped) == 3


async def test_iter_batches_supports_models_without_an_id_column(tenant_a):
    """Keyset paging must page on the model's primary key, not on a column
    called ``id``: some tables (e.g. workspace_quota) have neither."""
    await gd_insert(db.session, "workspace_quota", {
        "workspace_school_id": tenant_a,
        "auto_export_enabled": True,
    })
    await db.session.flush()

    seen = []
    async for batch in gd_iter_batches(db.session, "workspace_quota",
                                       {"auto_export_enabled": True}, batch_size=2):
        seen.extend(batch)

    assert any(r.get("workspace_school_id") == tenant_a for r in seen)


async def test_update_many_does_not_skip_rows_when_it_mutates_its_own_filter(tenant_a):
    """Keyset paging walks ids ascending, so flipping the very field the
    filter matches on (the class-delete / mark-all-read pattern) must still
    reach every row rather than skipping whole pages."""
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(sql_utils, "GD_BATCH_SIZE", 2)
        for _ in range(7):
            await gd_insert(db.session, PROBE, {"tenant_id": tenant_a, "is_active": True})
        await db.session.flush()

        updated = await gd_update_many(db.session, PROBE,
                                       {"tenant_id": tenant_a, "is_active": True},
                                       {"is_active": False})
        assert updated == 7
        left = await gd_find(db.session, PROBE,
                             {"tenant_id": tenant_a, "is_active": True}, limit=100)
        assert left == []
    finally:
        monkeypatch.undo()


async def test_bulk_notifications_survive_one_bad_recipient(tenant_a):
    """A chunk is written inside a SAVEPOINT: one invalid recipient must be
    counted as failed without dropping its chunk-mates or poisoning the
    caller's transaction."""
    from engines.notification_engine import NotificationEngine
    from dependencies import UserRole
    from tests.conftest import _mk_user

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(sql_utils, "GD_BATCH_SIZE", 5)
        good = [(await _mk_user(UserRole.PARENT, tenant_a))["id"] for _ in range(3)]
        await db.session.flush()
        bad = str(uuid.uuid4())  # no such user -> FK violation

        engine = NotificationEngine(db)
        res = await engine.create_bulk_notifications(
            tenant_id=tenant_a, recipient_ids=good[:2] + [bad] + good[2:],
            title="t", message="m",
        )
        assert res["created"] == 3, res
        assert res["failed"] == 1, res

        # the good ones are really persisted, exactly once each
        for uid in good:
            rows = await gd_find(db.session, "notifications", {"user_id": uid}, limit=10)
            assert len(rows) == 1
        # and the caller's transaction is still usable
        assert await gd_find(db.session, "notifications", {"user_id": bad}, limit=5) == []
    finally:
        monkeypatch.undo()


async def test_iter_batches_respects_max_rows():
    tenant = str(uuid.uuid4())
    await _seed_probe(tenant, 7)

    seen = 0
    async for batch in gd_iter_batches(db.session, PROBE, {"tenant_id": tenant},
                                       batch_size=2, max_rows=5):
        seen += len(batch)

    assert seen == 5


async def test_iter_batches_works_for_orm_backed_collections(tenant_a):
    from tests.conftest import _seed_student

    ids = {(await _seed_student(tenant_a, with_parent=False))["id"] for _ in range(5)}
    await db.session.flush()

    seen = []
    async for batch in gd_iter_batches(db.session, "students",
                                       {"school_id": tenant_a}, batch_size=2):
        assert len(batch) <= 2
        seen.extend(r["id"] for r in batch)

    assert set(seen) == ids


# --------------------------------------------------------------------------
# gd_update_many batching
# --------------------------------------------------------------------------

async def test_gd_update_many_updates_every_row_across_batches(monkeypatch):
    tenant = str(uuid.uuid4())
    await _seed_probe(tenant, 7)
    monkeypatch.setattr(sql_utils, "GD_BATCH_SIZE", 3)

    count = await gd_update_many(db.session, PROBE, {"tenant_id": tenant},
                                 {"$set": {"state": "updated"}})
    await db.session.flush()

    assert count == 7
    rows = await gd_find(db.session, PROBE, {"tenant_id": tenant}, limit=50)
    assert {r["state"] for r in rows} == {"updated"}


async def test_gd_update_many_does_not_load_every_row_at_once(monkeypatch):
    tenant = str(uuid.uuid4())
    await _seed_probe(tenant, 7)
    monkeypatch.setattr(sql_utils, "GD_BATCH_SIZE", 3)

    executed = []
    original = db.session.execute

    async def counting_execute(stmt, *a, **kw):
        executed.append(stmt)
        return await original(stmt, *a, **kw)

    monkeypatch.setattr(db.session, "execute", counting_execute)
    await gd_update_many(db.session, PROBE, {"tenant_id": tenant},
                         {"$set": {"state": "updated"}})

    assert len(executed) >= 3, "a bulk update must page through its rows"


# --------------------------------------------------------------------------
# Callers: page-size ceiling and streaming exports
# --------------------------------------------------------------------------

async def test_bulk_notifications_are_written_in_chunks(monkeypatch, tenant_a):
    """``create_bulk_notifications`` used to flush once per recipient, keeping
    every ORM object in the identity map for the whole fan-out."""
    from engines.notification_engine import NotificationEngine
    from dependencies import UserRole
    from tests.conftest import _mk_user

    monkeypatch.setattr(sql_utils, "GD_BATCH_SIZE", 3)
    recipients = [(await _mk_user(UserRole.PARENT, tenant_a))["id"] for _ in range(7)]
    await db.session.flush()

    flushes = 0
    original_flush = db.session.flush

    async def counting_flush(*a, **kw):
        nonlocal flushes
        flushes += 1
        return await original_flush(*a, **kw)

    monkeypatch.setattr(db.session, "flush", counting_flush)

    result = await NotificationEngine(db).create_bulk_notifications(
        tenant_id=tenant_a, recipient_ids=recipients,
        title="t", message="m",
    )

    assert result["created"] == 7
    assert flushes <= 3, f"expected one flush per chunk, got {flushes}"


async def test_notifications_page_size_has_a_server_side_maximum(client, teacher_headers):
    resp = await client.get("/notifications", params={"limit": 100000},
                            headers=teacher_headers)

    assert resp.status_code == 422, \
        "a caller must not be able to ask for an unbounded page"


async def test_student_export_streams_and_is_never_silently_capped(monkeypatch, tenant_a):
    """The export must return every student even when the gd_find ceiling is
    tiny - it streams instead of doing one capped read."""
    from tests.conftest import _seed_student
    from engines.export_engine import ExportEngine

    for _ in range(5):
        await _seed_student(tenant_a, with_parent=False)
    await db.session.flush()

    monkeypatch.setattr(sql_utils, "GD_FIND_MAX_ROWS", 2)
    monkeypatch.setattr(sql_utils, "GD_BATCH_SIZE", 2)

    out = await ExportEngine(db).export_students(tenant_a, fmt="json")
    payload = json.loads(out["content"].decode("utf-8"))

    assert len(payload) == 5
