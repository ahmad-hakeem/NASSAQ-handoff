"""Run CPU-bound work off the asyncio event loop.

Why this exists
---------------
The API is a single-process asyncio server (one uvicorn worker per instance).
The event loop is cooperative: it can only switch tasks at an ``await``. Work
that never awaits — building a PDF, shaping Arabic text, writing an XLSX,
zipping a bundle — owns the loop from start to finish. While it runs, the
process cannot read a socket, answer a healthcheck, or serve any other user.

Measured with ``scripts/evidence_event_loop_pdf.py`` (Arabic attendance report
via ReportLab + arabic_reshaper + python-bidi), the loop stalled for the *whole*
build:

    rows   build     worst event-loop stall (inline)   offloaded
    5       85 ms     80 ms                              8 ms
    50     388 ms    385 ms                             13 ms
    200   1469 ms   1463 ms                              8 ms
    500   3448 ms   3444 ms                             10 ms

    4 concurrent 200-row reports: 5.7 s of total freeze inline, 0.3 s worst
    stall when offloaded.

Handing the work to a worker thread does not make it faster — it is the same
CPU either way, and ReportLab is pure Python so the GIL is still held. What it
buys is *preemption*: CPython releases the GIL every few milliseconds
(``sys.getswitchinterval``), so the loop keeps getting slices and everyone
else's requests keep flowing. That is the entire point.

Contract
--------
``await run_cpu_bound(fn, *args, kind="pdf", pool="render", **kwargs)``

* runs ``fn`` on a small dedicated pool (not the default executor, which
  ``audit_sink`` and others share — a burst of report traffic must not starve
  audit writes);
* admits a bounded number of jobs; past that, callers wait briefly and then get
  :class:`CpuOffloadBusy` (503) instead of queueing without limit;
* bounds each job with a timeout and raises :class:`CpuOffloadTimeout` (504);
* records timings for the monitoring endpoint.

Pools
-----
``pool`` selects an isolated executor + admission gate. Jobs of wildly
different duration must not share one: timetable generation runs for tens of
seconds (measured 27 s for a 40-class school in
``scripts/evidence_event_loop_timetable.py``), and if it sat in the render pool
two principals could occupy every worker and stall a 300 ms PDF export behind
them. Each pool is sized and bounded independently:

    render     — PDF/XLSX/CSV/zip renders, short (sub-second to a few seconds)
    timetable  — combinatorial schedule generation, tens of seconds

Known limit: a Python thread cannot be killed. On timeout the awaiting request
is released, but the runaway job keeps its worker until it finishes on its own.
The admission cap is therefore the real protection, not the timeout.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

from config import config as settings

logger = logging.getLogger("nassaq.cpu_offload")


class CpuOffloadBusy(Exception):
    """Every render slot is taken and the queue is full."""

    code = "RENDER_BUSY"
    status_code = 503
    message_ar = "الخادم مشغول بإنشاء التقارير حالياً. يرجى المحاولة بعد قليل."
    message_en = "Report generation is at capacity. Please try again shortly."


class CpuOffloadTimeout(Exception):
    """A single job exceeded its wall-clock budget."""

    code = "RENDER_TIMEOUT"
    status_code = 504
    message_ar = "استغرق إنشاء الملف وقتاً أطول من المسموح. جرّب تضييق نطاق التقرير."
    message_en = "Generating the file took too long. Try narrowing the report range."


# --------------------------------------------------------------------------
# Pools
# --------------------------------------------------------------------------
RENDER_POOL = "render"
TIMETABLE_POOL = "timetable"


class _PoolSpec:
    """Sizing and bounds for one isolated pool, read fresh from config."""

    __slots__ = ("name", "workers", "max_inflight", "admission_timeout_s", "timeout_s")

    def __init__(self, name: str, workers: int, max_inflight: int,
                 admission_timeout_s: float, timeout_s: float):
        self.name = name
        self.workers = workers
        self.max_inflight = max_inflight
        self.admission_timeout_s = admission_timeout_s
        self.timeout_s = timeout_s


def _spec(pool: str) -> _PoolSpec:
    """Config is read on every call so tests can monkeypatch limits."""
    if pool == TIMETABLE_POOL:
        return _PoolSpec(
            TIMETABLE_POOL,
            settings.TIMETABLE_OFFLOAD_MAX_WORKERS,
            settings.TIMETABLE_OFFLOAD_MAX_INFLIGHT,
            settings.TIMETABLE_OFFLOAD_ADMISSION_TIMEOUT_S,
            settings.TIMETABLE_OFFLOAD_TIMEOUT_S,
        )
    return _PoolSpec(
        RENDER_POOL,
        settings.CPU_OFFLOAD_MAX_WORKERS,
        settings.CPU_OFFLOAD_MAX_INFLIGHT,
        settings.CPU_OFFLOAD_ADMISSION_TIMEOUT_S,
        settings.CPU_OFFLOAD_TIMEOUT_S,
    )


_executor_lock = threading.Lock()
_executors: Dict[str, ThreadPoolExecutor] = {}
_semaphores: Dict[str, asyncio.Semaphore] = {}
_semaphore_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_executor(spec: _PoolSpec) -> ThreadPoolExecutor:
    with _executor_lock:
        existing = _executors.get(spec.name)
        if existing is None:
            existing = ThreadPoolExecutor(
                max_workers=spec.workers,
                thread_name_prefix=f"cpu-{spec.name}",
            )
            _executors[spec.name] = existing
            logger.info(
                "cpu_offload pool=%s started workers=%d max_inflight=%d timeout=%.0fs",
                spec.name, spec.workers, spec.max_inflight, spec.timeout_s,
            )
        return existing


def _get_semaphore(spec: _PoolSpec) -> asyncio.Semaphore:
    """Admission gate, rebuilt if the running loop changed (tests)."""
    global _semaphore_loop
    loop = asyncio.get_running_loop()
    if _semaphore_loop is not loop:
        _semaphores.clear()
        _semaphore_loop = loop
    sem = _semaphores.get(spec.name)
    if sem is None:
        sem = asyncio.Semaphore(spec.max_inflight)
        _semaphores[spec.name] = sem
    return sem


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
_metrics_lock = threading.Lock()
_metrics: Dict[str, Any] = {
    "submitted": 0,
    "completed": 0,
    "failed": 0,
    "timeouts": 0,
    "rejected": 0,
    "in_flight": 0,
    "peak_in_flight": 0,
    "total_ms": 0,
    "slowest_ms": 0,
    "by_kind": {},
    "by_pool": {},
}


def _kind_bucket(kind: str) -> Dict[str, int]:
    return _metrics["by_kind"].setdefault(
        kind, {"count": 0, "total_ms": 0, "slowest_ms": 0}
    )


def _pool_bucket(pool: str) -> Dict[str, Any]:
    return _metrics["by_pool"].setdefault(
        pool,
        {
            "submitted": 0, "completed": 0, "failed": 0, "timeouts": 0,
            "rejected": 0, "in_flight": 0, "peak_in_flight": 0,
            "total_ms": 0, "slowest_ms": 0, "durations_ms": [],
        },
    )


# Bounded ring of recent durations per pool, so p95 can be reported without
# unbounded growth (the monitoring endpoint is the only consumer).
_DURATION_SAMPLES = 200


def _mark_start(kind: str, pool: str) -> None:
    with _metrics_lock:
        _metrics["submitted"] += 1
        _metrics["in_flight"] += 1
        _metrics["peak_in_flight"] = max(
            _metrics["peak_in_flight"], _metrics["in_flight"]
        )
        p = _pool_bucket(pool)
        p["submitted"] += 1
        p["in_flight"] += 1
        p["peak_in_flight"] = max(p["peak_in_flight"], p["in_flight"])


def _mark_end(kind: str, elapsed_ms: int, outcome: str, pool: str = RENDER_POOL) -> None:
    with _metrics_lock:
        _metrics["in_flight"] = max(0, _metrics["in_flight"] - 1)
        _metrics[outcome] += 1
        p = _pool_bucket(pool)
        p["in_flight"] = max(0, p["in_flight"] - 1)
        p[outcome] += 1
        if outcome == "completed":
            _metrics["total_ms"] += elapsed_ms
            _metrics["slowest_ms"] = max(_metrics["slowest_ms"], elapsed_ms)
            bucket = _kind_bucket(kind)
            bucket["count"] += 1
            bucket["total_ms"] += elapsed_ms
            bucket["slowest_ms"] = max(bucket["slowest_ms"], elapsed_ms)
            p["total_ms"] += elapsed_ms
            p["slowest_ms"] = max(p["slowest_ms"], elapsed_ms)
            samples = p["durations_ms"]
            samples.append(elapsed_ms)
            if len(samples) > _DURATION_SAMPLES:
                del samples[: len(samples) - _DURATION_SAMPLES]


def _percentile(values, pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * len(ordered))) - 1))
    return int(ordered[idx])


def metrics() -> Dict[str, Any]:
    """Snapshot for the monitoring endpoint (process-local since boot)."""
    with _metrics_lock:
        snapshot = {
            k: v for k, v in _metrics.items() if k not in ("by_kind", "by_pool")
        }
        snapshot["by_kind"] = {
            kind: {
                **bucket,
                "avg_ms": round(bucket["total_ms"] / bucket["count"])
                if bucket["count"]
                else 0,
            }
            for kind, bucket in _metrics["by_kind"].items()
        }
        by_pool = {}
        for pool, bucket in _metrics["by_pool"].items():
            spec = _spec(pool)
            done = bucket["completed"]
            by_pool[pool] = {
                **{k: v for k, v in bucket.items() if k != "durations_ms"},
                "avg_ms": round(bucket["total_ms"] / done) if done else 0,
                "p95_ms": _percentile(bucket["durations_ms"], 95),
                "max_workers": spec.workers,
                "max_inflight": spec.max_inflight,
                "timeout_seconds": spec.timeout_s,
                # Queue depth: admitted jobs beyond the number of worker
                # threads are waiting, not running.
                "queued": max(0, bucket["in_flight"] - spec.workers),
            }
        snapshot["by_pool"] = by_pool
    completed = snapshot["completed"]
    snapshot["avg_ms"] = round(snapshot["total_ms"] / completed) if completed else 0
    snapshot["max_workers"] = settings.CPU_OFFLOAD_MAX_WORKERS
    snapshot["max_inflight"] = settings.CPU_OFFLOAD_MAX_INFLIGHT
    snapshot["timeout_seconds"] = settings.CPU_OFFLOAD_TIMEOUT_S
    return snapshot


def reset_metrics() -> None:
    """Test helper."""
    with _metrics_lock:
        _metrics.update(
            submitted=0, completed=0, failed=0, timeouts=0, rejected=0,
            in_flight=0, peak_in_flight=0, total_ms=0, slowest_ms=0,
        )
        _metrics["by_kind"] = {}
        _metrics["by_pool"] = {}


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
async def run_cpu_bound(
    fn: Callable[..., Any],
    *args,
    kind: str = "render",
    pool: str = RENDER_POOL,
    timeout: Optional[float] = None,
    **kwargs,
):
    """Execute the blocking callable ``fn`` off the event loop.

    ``kind`` is a coarse label ("pdf", "xlsx", "csv", "zip", "timetable") used
    for metrics and logs only. ``pool`` selects the isolated executor
    (:data:`RENDER_POOL` or :data:`TIMETABLE_POOL`). Raises
    :class:`CpuOffloadBusy` when the pool is saturated and
    :class:`CpuOffloadTimeout` when a job outruns its budget; anything the
    callable itself raises propagates unchanged.
    """
    spec = _spec(pool)
    budget = timeout if timeout and timeout > 0 else spec.timeout_s
    sem = _get_semaphore(spec)

    try:
        await asyncio.wait_for(sem.acquire(), timeout=spec.admission_timeout_s)
    except asyncio.TimeoutError:
        with _metrics_lock:
            _metrics["rejected"] += 1
            _pool_bucket(spec.name)["rejected"] += 1
            in_flight = _metrics["by_pool"][spec.name]["in_flight"]
        logger.warning(
            "cpu_offload rejected pool=%s kind=%s in_flight=%d max_inflight=%d",
            spec.name, kind, in_flight, spec.max_inflight,
        )
        raise CpuOffloadBusy() from None

    _mark_start(kind, spec.name)
    started = time.perf_counter()
    call = functools.partial(fn, *args, **kwargs) if (args or kwargs) else fn
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(_get_executor(spec), call)
    try:
        result = await asyncio.wait_for(asyncio.shield(future), timeout=budget)
    except asyncio.TimeoutError:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        # The worker thread cannot be interrupted; release its slot only when
        # it actually finishes, otherwise the admission cap would over-admit
        # while the runaway job still owns a thread.
        future.add_done_callback(
            lambda _f: (_release(sem), _mark_end(kind, elapsed_ms, "timeouts", spec.name))
        )
        logger.error(
            "cpu_offload timeout pool=%s kind=%s elapsed_ms=%d budget_s=%.0f",
            spec.name, kind, elapsed_ms, budget,
        )
        raise CpuOffloadTimeout() from None
    except asyncio.CancelledError:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        future.add_done_callback(
            lambda _f: (_release(sem), _mark_end(kind, elapsed_ms, "failed", spec.name))
        )
        raise
    except Exception:
        _release(sem)
        _mark_end(kind, int((time.perf_counter() - started) * 1000), "failed", spec.name)
        raise

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    _release(sem)
    _mark_end(kind, elapsed_ms, "completed", spec.name)
    if elapsed_ms >= settings.CPU_OFFLOAD_SLOW_MS:
        logger.warning(
            "cpu_offload slow job pool=%s kind=%s elapsed_ms=%d",
            spec.name, kind, elapsed_ms,
        )
    else:
        logger.debug(
            "cpu_offload ok pool=%s kind=%s elapsed_ms=%d", spec.name, kind, elapsed_ms
        )
    return result


def _release(sem: asyncio.Semaphore) -> None:
    try:
        sem.release()
    except Exception:  # pragma: no cover — defensive
        pass


def shutdown(wait: bool = False) -> None:
    """Stop every pool (called from the app shutdown hook)."""
    with _executor_lock:
        for name, executor in list(_executors.items()):
            executor.shutdown(wait=wait, cancel_futures=True)
            logger.info("cpu_offload pool=%s shut down", name)
        _executors.clear()
