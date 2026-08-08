"""CPU-bound work must not run on the event loop.

Root cause these tests pin down
-------------------------------
Every PDF/XLSX/CSV export built its document inline inside an ``async def``
handler. ReportLab + arabic_reshaper + python-bidi never await, so the loop was
owned by the render for its whole duration: measured with
``scripts/evidence_event_loop_pdf.py``, a 200-row Arabic attendance report
froze the loop for 1.46 s and a 500-row one for 3.44 s — every other user's
request (including healthchecks) waited that long. Four concurrent reports =
5.7 s of total freeze.

The fix is ``services.cpu_offload.run_cpu_bound``: a small dedicated thread
pool with an admission cap and a per-job timeout. These tests assert the
guarantees that matter — the loop keeps ticking, saturation degrades to a
retryable 503 instead of an unbounded queue, and the render paths actually go
through it (a static check, so a future inline ``doc.build`` fails CI rather
than production).
"""
from __future__ import annotations

import ast
import asyncio
import os
import time

import pytest

from config import config as settings
from services import cpu_offload
from services.cpu_offload import (
    CpuOffloadBusy,
    CpuOffloadTimeout,
    run_cpu_bound,
)

pytestmark = pytest.mark.asyncio

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def _clean_metrics():
    cpu_offload.reset_metrics()
    yield
    cpu_offload.reset_metrics()


def _burn(seconds: float) -> str:
    """Blocking, GIL-holding busy work — the shape of a ReportLab build."""
    end = time.perf_counter() + seconds
    total = 0
    while time.perf_counter() < end:
        total += sum(range(500))
    return f"done:{total > 0}"


class _Heartbeat:
    """Records how late each 10 ms tick is; lateness == loop blockage."""

    def __init__(self):
        self.max_lateness_ms = 0.0
        self.ticks = 0
        self._stop = False
        self._task = None

    async def _run(self):
        interval = 0.01
        expected = time.perf_counter() + interval
        while not self._stop:
            await asyncio.sleep(interval)
            now = time.perf_counter()
            self.max_lateness_ms = max(self.max_lateness_ms, (now - expected) * 1000)
            self.ticks += 1
            expected = now + interval

    def __enter__(self):
        self._task = asyncio.get_event_loop().create_task(self._run())
        return self

    def __exit__(self, *exc):
        self._stop = True
        if self._task:
            self._task.cancel()


# --------------------------------------------------------------------------
# The core guarantee
# --------------------------------------------------------------------------
async def test_offloaded_work_leaves_the_loop_responsive():
    hb = _Heartbeat()
    with hb:
        await asyncio.sleep(0.05)
        result = await run_cpu_bound(_burn, 0.6, kind="test")
        await asyncio.sleep(0.05)

    assert result.startswith("done:")
    # 600 ms of CPU work; the loop must have kept ticking throughout.
    assert hb.ticks > 20, f"loop starved: only {hb.ticks} ticks"
    assert hb.max_lateness_ms < 200, (
        f"loop stalled {hb.max_lateness_ms:.0f}ms — work is not off the loop"
    )


async def test_inline_equivalent_does_block_the_loop():
    """Control: the same work run inline is exactly what we are fixing."""
    hb = _Heartbeat()
    with hb:
        await asyncio.sleep(0.05)
        _burn(0.6)
        await asyncio.sleep(0.05)

    assert hb.max_lateness_ms > 300, (
        "expected the inline control to stall the loop; if this fails the "
        "heartbeat instrument itself is broken"
    )


async def test_other_requests_progress_during_a_render():
    """A second 'request' completes while a long render is in flight."""
    ticks = []

    async def other_work():
        for _ in range(10):
            await asyncio.sleep(0.02)
            ticks.append(time.perf_counter())

    render = asyncio.create_task(run_cpu_bound(_burn, 0.5, kind="test"))
    await other_work()
    assert len(ticks) == 10, "concurrent coroutine did not get to run"
    assert not render.done(), "render finished too early to prove anything"
    await render


# --------------------------------------------------------------------------
# Result / error propagation
# --------------------------------------------------------------------------
async def test_returns_value_and_passes_arguments():
    def add(a, b, c=0):
        return a + b + c

    assert await run_cpu_bound(add, 2, 3, c=4, kind="test") == 9


async def test_callable_exception_propagates_unchanged():
    def boom():
        raise ValueError("render failed")

    with pytest.raises(ValueError, match="render failed"):
        await run_cpu_bound(boom, kind="test")

    assert cpu_offload.metrics()["failed"] == 1


async def test_timeout_raises_and_frees_the_caller(monkeypatch):
    monkeypatch.setattr(settings, "CPU_OFFLOAD_TIMEOUT_S", 0.2, raising=False)
    started = time.perf_counter()
    with pytest.raises(CpuOffloadTimeout):
        await run_cpu_bound(_burn, 1.5, kind="test")
    elapsed = time.perf_counter() - started
    # The caller is released at the budget, not when the thread finishes.
    assert elapsed < 1.0, f"caller waited {elapsed:.2f}s past its budget"


async def test_timeout_slot_is_returned_only_when_the_thread_finishes(monkeypatch):
    """A runaway job must keep occupying its admission slot.

    Releasing on timeout would over-admit: the thread is still burning CPU.
    """
    monkeypatch.setattr(settings, "CPU_OFFLOAD_TIMEOUT_S", 0.15, raising=False)
    with pytest.raises(CpuOffloadTimeout):
        await run_cpu_bound(_burn, 0.8, kind="test")

    assert cpu_offload.metrics()["in_flight"] == 1
    await asyncio.sleep(1.0)  # let the thread finish
    m = cpu_offload.metrics()
    assert m["in_flight"] == 0
    assert m["timeouts"] == 1


# --------------------------------------------------------------------------
# Admission control
# --------------------------------------------------------------------------
async def test_saturation_rejects_instead_of_queueing_forever(monkeypatch):
    monkeypatch.setattr(settings, "CPU_OFFLOAD_MAX_INFLIGHT", 2, raising=False)
    monkeypatch.setattr(settings, "CPU_OFFLOAD_ADMISSION_TIMEOUT_S", 0.1, raising=False)
    cpu_offload._semaphore = None  # rebuild with the patched cap

    busy = [asyncio.create_task(run_cpu_bound(_burn, 0.8, kind="test")) for _ in range(2)]
    await asyncio.sleep(0.15)

    started = time.perf_counter()
    with pytest.raises(CpuOffloadBusy):
        await run_cpu_bound(_burn, 0.1, kind="test")
    waited = time.perf_counter() - started

    assert waited < 1.0, "rejected caller waited far past the admission timeout"
    assert cpu_offload.metrics()["rejected"] == 1
    await asyncio.gather(*busy)
    cpu_offload._semaphore = None


async def test_busy_error_carries_a_retryable_contract():
    exc = CpuOffloadBusy()
    assert exc.status_code == 503
    assert exc.code == "RENDER_BUSY"
    assert exc.message_ar  # Arabic message is what the user actually sees
    assert CpuOffloadTimeout().status_code == 504


async def test_slot_is_released_after_success_so_the_pool_does_not_leak():
    for _ in range(3):
        await run_cpu_bound(_burn, 0.05, kind="test")
    m = cpu_offload.metrics()
    assert m["in_flight"] == 0
    assert m["completed"] == 3


# --------------------------------------------------------------------------
# Monitoring
# --------------------------------------------------------------------------
async def test_metrics_track_volume_and_duration_per_kind():
    await run_cpu_bound(_burn, 0.05, kind="pdf")
    await run_cpu_bound(_burn, 0.05, kind="xlsx")
    m = cpu_offload.metrics()

    assert m["submitted"] == 2 and m["completed"] == 2
    assert m["slowest_ms"] >= 40
    assert set(m["by_kind"]) == {"pdf", "xlsx"}
    assert m["by_kind"]["pdf"]["count"] == 1
    assert m["by_kind"]["pdf"]["avg_ms"] >= 40
    # Configuration is surfaced so an operator can see the ceiling they hit.
    assert m["max_workers"] >= 1 and m["max_inflight"] >= 1


async def test_peak_in_flight_is_recorded():
    await asyncio.gather(*[run_cpu_bound(_burn, 0.15, kind="test") for _ in range(2)])
    assert cpu_offload.metrics()["peak_in_flight"] >= 2


# --------------------------------------------------------------------------
# Guardrail: no future regression back onto the loop
# --------------------------------------------------------------------------
_PDF_DOC_NAMES = {"doc", "pdf_doc", "document", "pdf"}


def _inline_pdf_builds(path: str):
    """Report ``doc.build(...)`` calls sitting directly in a coroutine body.

    Nested plain ``def``s are skipped: those are the closures handed to
    ``run_cpu_bound``, which is exactly the pattern we want.
    """
    tree = ast.parse(open(path, encoding="utf-8").read())
    offences = []

    def walk_async_body(node, fn_name):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.Lambda)):
                continue  # offloaded closure — fine
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "build"
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id in _PDF_DOC_NAMES
            ):
                offences.append(f"{os.path.relpath(path, BACKEND_DIR)}:{child.lineno} in {fn_name}()")
            walk_async_body(child, fn_name)

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            walk_async_body(node, node.name)
    return offences


async def test_no_route_builds_a_pdf_on_the_event_loop():
    offences = []
    for folder in ("routes", "engines"):
        base = os.path.join(BACKEND_DIR, folder)
        for name in sorted(os.listdir(base)):
            if name.endswith(".py"):
                offences += _inline_pdf_builds(os.path.join(base, name))

    assert not offences, (
        "PDF built directly inside an async handler — this freezes the event "
        "loop for every other user. Move the build into a sync function and "
        "await services.cpu_offload.run_cpu_bound(...):\n  "
        + "\n  ".join(offences)
    )


async def test_export_engine_offloads_every_format():
    """The shared export engine is the hot path for 3 of the 8 export routes."""
    src = open(os.path.join(BACKEND_DIR, "engines", "export_engine.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    export_fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "export"
    )
    offloaded = {
        arg.attr
        for call in ast.walk(export_fn)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "run_cpu_bound"
        for arg in call.args[:1]
        if isinstance(arg, ast.Attribute)
    }
    assert {"_to_pdf", "_to_csv", "_to_xlsx"} <= offloaded, (
        f"export() still renders inline; offloaded={offloaded}"
    )
