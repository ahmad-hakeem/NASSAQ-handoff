"""Timetable generation must not run on the event loop, and must be pollable.

Root cause these tests pin down
-------------------------------
``POST /smart-scheduling/generate/{school_id}`` awaited
``smart_scheduling_engine.generate_timetable`` inline. The three heavy phases
inside it — draft construction, conflict detection, optimization — are pure
CPU with no awaits, so the loop was owned by the search for its entire
duration. Measured with ``scripts/evidence_event_loop_timetable.py``:

    12 classes / 30 teachers →  1.3 s frozen
    24 classes / 45 teachers →  6.2 s frozen
    40 classes / 70 teachers → 27.4 s frozen
    3 principals × 24 classes → 18.7 s of total freeze

Every other user of that instance — parents opening the app, teachers taking
attendance, the platform healthcheck — waited that long.

Two things are asserted here:

1. The phases run in the dedicated timetable pool, and the sync cores stay
   await-free. Both are checked statically as well as at runtime, so a future
   edit that re-inlines the search or sneaks an ``await`` into a core fails in
   CI rather than in production.
2. Generation is reachable as a background job with a pollable status, so a
   27 s run is not held open as a single request (proxies and browsers time
   those out) and the principal is not pinned to the page.
"""
from __future__ import annotations

import ast
import asyncio
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from dependencies import db
from engines.sql_utils import gd_insert, gd_find_one
from services import cpu_offload

pytestmark = pytest.mark.asyncio

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_PATH = os.path.join(BACKEND_DIR, "engines", "smart_scheduling_engine.py")

# Public async wrapper → the sync core it must delegate to.
PHASES = {
    "generate_draft_timetable": "_generate_draft_timetable_sync",
    "detect_conflicts": "_detect_conflicts_sync",
    "optimize_timetable": "_optimize_timetable_sync",
}


def _engine_functions():
    tree = ast.parse(open(ENGINE_PATH, encoding="utf-8").read())
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.setdefault(node.name, node)
    return out


# ---------------------------------------------------------------------------
# Static guards — these are the ones that keep the fix from rotting
# ---------------------------------------------------------------------------

def test_sync_cores_are_plain_functions():
    """The CPU cores must be ``def``, not ``async def``.

    A thread pool cannot run a coroutine: if someone converts a core back to
    ``async def`` the offload silently degrades to returning an un-awaited
    coroutine object instead of a timetable.
    """
    fns = _engine_functions()
    for wrapper, core in PHASES.items():
        assert core in fns, f"missing CPU core {core}"
        assert isinstance(fns[core], ast.FunctionDef), (
            f"{core} must be a plain def so it can run in the timetable pool"
        )
        assert isinstance(fns[wrapper], ast.AsyncFunctionDef), (
            f"{wrapper} must stay async — it is the awaited public entry point"
        )


def test_sync_cores_contain_no_await():
    """An ``await`` inside a core means DB I/O crept back into the thread.

    The cores run off the loop, where there is no request-scoped session and
    no loop to await on. Anything needing I/O belongs in the async wrapper —
    which is why the draft core returns ``log_intents`` for the wrapper to
    flush instead of writing run logs itself.
    """
    fns = _engine_functions()
    for core in PHASES.values():
        node = fns[core]
        awaits = [
            n for n in ast.walk(node)
            if isinstance(n, (ast.Await, ast.AsyncFor, ast.AsyncWith))
        ]
        assert not awaits, (
            f"{core} runs in a worker thread and must not await "
            f"(found {len(awaits)}); move the I/O into its async wrapper"
        )


def test_wrappers_delegate_to_the_timetable_pool():
    """Each wrapper must hand its core to ``_run_off_loop``.

    Guards against the regression this whole change exists to prevent:
    someone calling the core directly from the async wrapper, which puts the
    search straight back on the event loop while every test still passes.
    """
    fns = _engine_functions()
    for wrapper, core in PHASES.items():
        calls = [
            n for n in ast.walk(fns[wrapper])
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "_run_off_loop"
        ]
        assert calls, f"{wrapper} must offload via _run_off_loop"
        assert any(
            any(
                isinstance(a, ast.Attribute) and a.attr == core
                for a in call.args
            )
            for call in calls
        ), f"{wrapper} must offload {core}"


def test_generation_route_does_not_call_sync_cores():
    """Route code must never reach past the wrappers into a core."""
    routes_path = os.path.join(
        BACKEND_DIR, "routes", "scheduling_smart_engine_routes.py"
    )
    src = open(routes_path, encoding="utf-8").read()
    for core in PHASES.values():
        assert core not in src, (
            f"{core} is a CPU core — routes must call the async wrapper instead"
        )


# ---------------------------------------------------------------------------
# Runtime — the loop actually keeps ticking
# ---------------------------------------------------------------------------

class _Heartbeat:
    """Records how late each 10 ms tick is; lateness == loop blockage."""

    def __init__(self):
        self.worst_ms = 0.0
        self._task = None
        self._stop = False

    async def _run(self):
        interval = 0.01
        nxt = time.perf_counter() + interval
        while not self._stop:
            await asyncio.sleep(max(0, nxt - time.perf_counter()))
            late = (time.perf_counter() - nxt) * 1000
            self.worst_ms = max(self.worst_ms, late)
            nxt += interval

    def start(self):
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._stop = True
        if self._task:
            await asyncio.gather(self._task, return_exceptions=True)


def _burn(seconds: float):
    """Blocking, GIL-holding busy work — the shape of the scheduling search."""
    end = time.perf_counter() + seconds
    total = 0
    while time.perf_counter() < end:
        total += sum(range(500))
    return total


async def test_draft_phase_keeps_the_loop_responsive(monkeypatch):
    """A ~1 s phase must not cost the loop more than a fraction of that.

    Before the fix the loop lag equalled the whole phase duration; the
    evidence script measured 27 s for a 40-class school.
    """
    from engines.smart_scheduling_engine import SmartSchedulingEngine

    engine = SmartSchedulingEngine.__new__(SmartSchedulingEngine)

    def fake_core(*a, **kw):
        _burn(1.0)
        return ("tt", [], [], [], [], [])

    monkeypatch.setattr(
        engine, "_generate_draft_timetable_sync", fake_core, raising=False
    )

    hb = _Heartbeat()
    hb.start()
    await asyncio.sleep(0.05)
    started = time.perf_counter()
    await engine.generate_draft_timetable("s", "r", [], {}, {}, [])
    elapsed = time.perf_counter() - started
    await asyncio.sleep(0.05)
    await hb.stop()

    assert elapsed >= 0.9, "the fake phase should really have burned ~1 s"
    assert hb.worst_ms < 300, (
        f"loop blocked {hb.worst_ms:.0f}ms during a {elapsed:.1f}s phase — "
        "the work is running on the event loop again"
    )


async def test_draft_phase_uses_the_timetable_pool(monkeypatch):
    """Timetable work must not share the render pool.

    A 27 s generation in the 2-worker render pool would starve sub-second PDF
    exports behind it, so the pools are deliberately separate.
    """
    from engines.smart_scheduling_engine import SmartSchedulingEngine

    engine = SmartSchedulingEngine.__new__(SmartSchedulingEngine)
    monkeypatch.setattr(
        engine, "_generate_draft_timetable_sync",
        lambda *a, **kw: ("tt", [], [], [], [], []),
        raising=False,
    )

    cpu_offload.reset_metrics()
    await engine.generate_draft_timetable("s", "r", [], {}, {}, [])
    by_pool = cpu_offload.metrics().get("by_pool", {})

    assert by_pool.get(cpu_offload.TIMETABLE_POOL, {}).get("completed", 0) >= 1
    assert by_pool.get(cpu_offload.RENDER_POOL, {}).get("completed", 0) == 0


async def test_each_pool_reads_its_own_limits(monkeypatch):
    """The timetable pool must be sized by ``TIMETABLE_OFFLOAD_*``.

    If the spec lookup fell through to the render defaults, the timetable pool
    would silently inherit a 90 s cap — killing large-school generations that
    legitimately need three minutes — and the separation would exist in name
    only.
    """
    from config import config as settings

    monkeypatch.setattr(settings, "CPU_OFFLOAD_TIMEOUT_S", 11, raising=False)
    monkeypatch.setattr(settings, "CPU_OFFLOAD_MAX_INFLIGHT", 12, raising=False)
    monkeypatch.setattr(settings, "TIMETABLE_OFFLOAD_TIMEOUT_S", 21, raising=False)
    monkeypatch.setattr(settings, "TIMETABLE_OFFLOAD_MAX_INFLIGHT", 22, raising=False)

    render = cpu_offload._spec(cpu_offload.RENDER_POOL)
    timetable = cpu_offload._spec(cpu_offload.TIMETABLE_POOL)

    assert (render.timeout_s, render.max_inflight) == (11, 12)
    assert (timetable.timeout_s, timetable.max_inflight) == (21, 22)


async def test_timetable_defaults_outlive_a_large_generation():
    """A 40-class school measured 27 s; the cap must leave real headroom."""
    from config import config as settings

    assert settings.TIMETABLE_OFFLOAD_TIMEOUT_S >= 120, (
        "a cap near the measured worst case would fail exactly the large "
        "schools that need generation most"
    )
    assert settings.TIMETABLE_OFFLOAD_MAX_WORKERS <= 4, (
        "the search is GIL-bound — extra threads add jitter, not speed"
    )


async def test_draft_wrapper_flushes_log_intents(monkeypatch):
    """The core cannot write to the DB, so the wrapper must flush for it.

    Without this the run-log entries the engine produces during the search
    would be silently dropped when the phase moved off the loop.
    """
    from engines.smart_scheduling_engine import SmartSchedulingEngine

    engine = SmartSchedulingEngine.__new__(SmartSchedulingEngine)
    intents = [("info", "phase done", {"n": 1})]
    monkeypatch.setattr(
        engine, "_generate_draft_timetable_sync",
        lambda *a, **kw: ("tt", [], [], [], [], intents),
        raising=False,
    )

    logged = []

    async def fake_log(run_id, level, message, meta=None):
        logged.append((run_id, level, message, meta))

    monkeypatch.setattr(engine, "_log_run", fake_log, raising=False)

    result = await engine.generate_draft_timetable("s", "run1", [], {}, {}, [])

    assert len(result) == 5, "callers still expect the original 5-tuple"
    assert logged == [("run1", "info", "phase done", {"n": 1})]


# ---------------------------------------------------------------------------
# Job API
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def stub_generation(monkeypatch):
    """Neutralize the pre-flight checks and the worker.

    These tests cover the job layer — queueing, the one-run-per-school guard,
    stale reaping and tenant scoping — not the scheduling engine, and seeding
    a fully solvable school would drown that in fixture noise.
    """
    import src.modules.scheduling.controllers.scheduling_smart_engine_routes as mod
    from engines.infeasibility import InfeasibilityReport

    async def no_context(school_id):
        return {}

    async def clean_report(school_id, **kw):
        return InfeasibilityReport(
            blocks_generation=False, issues=[],
            computed_at=datetime.now(timezone.utc),
        )

    started = []

    async def fake_job(*args, **kwargs):
        started.append(args)

    monkeypatch.setattr(mod, "_assemble_hakim_context_payload", no_context)
    monkeypatch.setattr(
        mod.smart_scheduling_engine, "build_infeasibility_report", clean_report
    )
    monkeypatch.setattr(mod, "_run_generation_job", fake_job)
    return started


async def gd_update_one_(run_id, patch):
    """Patch a run row and flush, so the next read sees it."""
    from engines.sql_utils import gd_update_one

    await gd_update_one(db.session, "timetable_runs", {"id": run_id}, patch)
    await db.session.commit()


async def _mk_run(school_id, *, status="generating", age_s=5, run_id=None):
    run_id = run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc) - timedelta(seconds=age_s)
    await gd_insert(db.session, "timetable_runs", {
        "id": run_id,
        "school_id": school_id,
        "status": status,
        "started_at": started_at.isoformat(),
        "completion_percentage": 55,
    })
    return run_id


async def test_generate_job_returns_immediately(
    client, school_principal_headers, school_a_id, stub_generation
):
    """The principal gets a job id, not a 27 s held-open request."""
    res = await client.post(
        f"/smart-scheduling/generate/{school_a_id}/job",
        json={}, headers=school_principal_headers,
    )
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["job_id"]
    assert body["status"] == "pending"
    assert body["poll_url"].endswith(body["job_id"])

    # The run row must exist before the response, otherwise the very first
    # poll a client makes would 404.
    row = await gd_find_one(db.session, "timetable_runs", {"id": body["job_id"]})
    assert row is not None
    assert row["school_id"] == school_a_id


async def test_second_generate_returns_the_running_job(
    client, school_principal_headers, school_a_id, stub_generation
):
    """One generation per school — a double click must not start two searches.

    Two concurrent runs race to write the same draft and burn two of the very
    few CPU workers producing a result one of them overwrites.
    """
    existing = await _mk_run(school_a_id, status="generating", age_s=5)
    await db.session.commit()

    res = await client.post(
        f"/smart-scheduling/generate/{school_a_id}/job",
        json={}, headers=school_principal_headers,
    )
    assert res.status_code == 202
    body = res.json()
    assert body["already_running"] is True
    assert body["job_id"] == existing


async def test_stale_run_is_reaped_and_does_not_block(
    client, school_principal_headers, school_a_id, stub_generation, monkeypatch
):
    """A run whose worker vanished must not block the school forever.

    An instance restart mid-generation leaves the row "generating"; without
    reaping, the guard above would refuse every future generation.
    """
    from config import config as cfg

    monkeypatch.setattr(cfg, "TIMETABLE_JOB_STALE_AFTER_S", 30, raising=False)
    stale = await _mk_run(school_a_id, status="generating", age_s=600)
    await db.session.commit()

    res = await client.post(
        f"/smart-scheduling/generate/{school_a_id}/job",
        json={}, headers=school_principal_headers,
    )
    assert res.status_code == 202
    body = res.json()
    assert body.get("already_running") is not True
    assert body["job_id"] != stale

    reaped = await gd_find_one(db.session, "timetable_runs", {"id": stale})
    assert reaped["status"] == "failed"
    assert reaped["error_code"] == "JOB_STALE"


async def test_job_status_reports_progress(
    client, school_principal_headers, school_a_id
):
    run_id = await _mk_run(school_a_id, status="generating", age_s=5)
    await db.session.commit()

    res = await client.get(
        f"/smart-scheduling/job/{run_id}", headers=school_principal_headers
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "generating"
    assert body["is_done"] is False
    assert body["progress"] == 55


async def test_job_status_is_tenant_scoped(
    client, school_admin_headers, school_b_id
):
    """A principal must not be able to read another school's run."""
    run_id = await _mk_run(school_b_id, status="generating", age_s=5)
    await db.session.commit()

    res = await client.get(
        f"/smart-scheduling/job/{run_id}", headers=school_admin_headers
    )
    assert res.status_code in (403, 404), res.text


async def test_job_status_unknown_id_404(client, school_principal_headers):
    res = await client.get(
        f"/smart-scheduling/job/{uuid.uuid4()}", headers=school_principal_headers
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Concurrency — two generations must never overlap on one school
# ---------------------------------------------------------------------------

def test_claim_is_serialized_by_an_advisory_lock():
    """The claim must be atomic, not read-then-insert.

    The "is one already running?" check and the INSERT are separated by two
    awaited round-trips (context assembly + infeasibility report). Without a
    lock, two principals — or one double-click — can both pass the check and
    start competing searches that overwrite each other's draft. Asserted
    statically because reproducing the interleaving in-process is flaky.
    """
    routes_path = os.path.join(
        BACKEND_DIR, "routes", "scheduling_smart_engine_routes.py"
    )
    src = open(routes_path, encoding="utf-8").read()
    tree = ast.parse(src)
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef)
        and n.name == "smart_generate_timetable_job"
    )
    body_src = ast.get_source_segment(src, fn) or ""
    assert "pg_advisory_xact_lock" in body_src, (
        "the claim must take a transaction-scoped advisory lock keyed on the "
        "school before inserting the run row"
    )
    lock_at = body_src.index("pg_advisory_xact_lock")
    insert_at = body_src.index('gd_insert(db.session, "timetable_runs"')
    assert lock_at < insert_at, "the lock must be held across the insert"
    # The re-check has to happen after the lock, otherwise the lock protects
    # nothing: both racers would insert on the strength of a stale read.
    recheck_at = body_src.rindex("_find_active_run")
    assert lock_at < recheck_at < insert_at, (
        "re-check for an active run after taking the lock, before inserting"
    )


async def test_live_run_with_fresh_heartbeat_is_not_reaped(school_a_id, monkeypatch):
    """A slow-but-alive worker must not be declared dead.

    Reaping on elapsed time alone kills healthy large-school runs and then
    lets a second generation start beside the first, both writing the same
    draft. Liveness is the heartbeat, not the start time.
    """
    from routes import scheduling_smart_engine_routes as mod
    from config import config as cfg

    monkeypatch.setattr(cfg, "TIMETABLE_JOB_STALE_AFTER_S", 60, raising=False)
    run_id = await _mk_run(school_a_id, status="generating", age_s=3600)
    await gd_update_one_(run_id, {
        "heartbeat_at": datetime.now(timezone.utc).isoformat(),
    })

    row = await gd_find_one(db.session, "timetable_runs", {"id": run_id})
    out = await mod._reap_if_stale(row)
    assert out["status"] == "generating", "a beating worker was reaped"

    # …and once the beats stop, it is reaped.
    await gd_update_one_(run_id, {
        "heartbeat_at": (
            datetime.now(timezone.utc) - timedelta(seconds=600)
        ).isoformat(),
    })
    row = await gd_find_one(db.session, "timetable_runs", {"id": run_id})
    out = await mod._reap_if_stale(row)
    assert out["status"] == "failed"
    assert out["error_code"] == "JOB_STALE"


async def test_reap_does_not_overwrite_a_finished_run(school_a_id, monkeypatch):
    """Reaping is compare-and-set on status.

    A worker that finishes in the same window as a reaping poll must keep its
    real result; a blind UPDATE would rewrite a completed run as failed.
    """
    from routes import scheduling_smart_engine_routes as mod
    from config import config as cfg

    monkeypatch.setattr(cfg, "TIMETABLE_JOB_STALE_AFTER_S", 1, raising=False)
    run_id = await _mk_run(school_a_id, status="generating", age_s=600)
    stale_view = await gd_find_one(db.session, "timetable_runs", {"id": run_id})

    # The worker completes after the poller read the row but before it writes.
    await gd_update_one_(run_id, {"status": "completed"})

    await mod._reap_if_stale(stale_view)

    row = await gd_find_one(db.session, "timetable_runs", {"id": run_id})
    assert row["status"] == "completed", (
        "the reaper clobbered a run that had already finished"
    )


async def test_engine_run_state_is_not_shared_between_runs():
    """Run-scoped counters must be keyed by run_id, not stashed on the engine.

    The engine is a process-wide singleton. Now that generations can overlap,
    instance attributes let one school's rejection counters be reported in
    another school's generation_summary.
    """
    from dependencies import smart_scheduling_engine as engine

    engine._scratch("run-a")["rejection_counts"] = {"teacher_busy": 7}
    engine._scratch("run-b")["rejection_counts"] = {"teacher_busy": 0}

    assert engine._scratch("run-a")["rejection_counts"]["teacher_busy"] == 7
    assert engine._scratch("run-b")["rejection_counts"]["teacher_busy"] == 0

    engine._clear_scratch("run-a")
    engine._clear_scratch("run-b")
    assert engine._scratch("run-a") == {}, "scratch must not outlive the run"
    engine._clear_scratch("run-a")


async def test_job_restores_the_request_session(school_a_id, monkeypatch):
    """``db.session`` is a ContextVar shared with the rest of the request.

    The job rebinds it to its own session; leaving it rebound hands a closed
    session to anything scheduled after us in the same context.
    """
    from routes import scheduling_smart_engine_routes as mod

    before = db.session

    async def boom(*a, **k):
        raise RuntimeError("generation exploded")

    monkeypatch.setattr(mod.smart_scheduling_engine, "generate_timetable", boom)
    run_id = await _mk_run(school_a_id, status="pending", age_s=1)
    await db.session.commit()

    await mod._run_generation_job(
        run_id, school_a_id, None, None, "u1",
        {"id": "u1", "role": "school_principal", "tenant_id": school_a_id},
        {},
    )

    assert db.session is before, "the job leaked its background session"


async def test_run_progress_fields_are_durable(school_a_id):
    """``timetable_runs`` used to silently drop every non-column key.

    It is a real table with no ``data`` column, so ``dict_to_model`` discarded
    ``completion_percentage``, ``started_at``, ``timetable_id`` and friends —
    which is why completed runs had ``sessions_created = 0``. Polling depends
    on those fields surviving a write/read round-trip.
    """
    from engines.sql_utils import gd_update_one

    run_id = await _mk_run(school_a_id, status="pending", age_s=1)
    await gd_update_one(db.session, "timetable_runs", {"id": run_id}, {
        "completion_percentage": 85,
        "timetable_id": "tt-xyz",
        "notes": "جارٍ التحسين",
    })
    row = await gd_find_one(db.session, "timetable_runs", {"id": run_id})

    assert row["completion_percentage"] == 85
    assert row["timetable_id"] == "tt-xyz"
    assert row["notes"] == "جارٍ التحسين"
    assert row["started_at"], "started_at must survive the round-trip"
