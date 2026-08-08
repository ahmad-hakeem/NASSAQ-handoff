"""Evidence: does Arabic PDF generation block the asyncio event loop?

Phase-1 measurement for the "PDF generation freezes the server" investigation.
Run from the backend directory:

    cd backend && ENVIRONMENT=development python3 scripts/evidence_event_loop_pdf.py

It does three things, with no database and no HTTP server involved:

1. Times the real ``ExportEngine._to_pdf`` (ReportLab + arabic_reshaper +
   python-bidi, the exact code the export routes call) at several report sizes.
2. Runs a heartbeat coroutine that should tick every 10 ms and records how
   late each tick actually is. That lateness *is* event-loop blocking: while
   the loop is stuck inside ReportLab it cannot accept, read, route or answer
   any other request.
3. Repeats the same build off the loop (``run_in_executor``) so the two
   numbers can be compared directly.

The heartbeat is the honest instrument here: a stopwatch around the build only
tells you the build is slow, not that everyone else is frozen.
"""

import asyncio
import os
import statistics
import sys
import time
import types

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

# ``engines/__init__.py`` eagerly imports the whole engine graph (and trips a
# circular import outside the app). Register ``engines`` as a bare package so
# only the export engine itself is loaded.
_pkg = types.ModuleType("engines")
_pkg.__path__ = [os.path.join(BACKEND_DIR, "engines")]
sys.modules.setdefault("engines", _pkg)

from engines.export_engine import ExportEngine  # noqa: E402

TICK = 0.01  # heartbeat interval: 10 ms


class Heartbeat:
    """Ticks every TICK seconds and records how late each tick was."""

    def __init__(self):
        self.lateness_ms = []
        self._task = None
        self._stop = False

    async def _run(self):
        expected = time.perf_counter() + TICK
        while not self._stop:
            await asyncio.sleep(TICK)
            now = time.perf_counter()
            self.lateness_ms.append(max(0.0, (now - expected) * 1000))
            expected = now + TICK

    def start(self):
        self.lateness_ms = []
        self._stop = False
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._stop = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def report(self):
        if not self.lateness_ms:
            return "no ticks recorded"
        data = sorted(self.lateness_ms)
        p95 = data[int(len(data) * 0.95) - 1] if len(data) >= 20 else data[-1]
        return (
            f"ticks={len(data)} "
            f"median={statistics.median(data):.1f}ms "
            f"p95={p95:.1f}ms "
            f"worst={data[-1]:.1f}ms"
        )


ARABIC_CLASS_NAMES = [
    "الصف الأول الابتدائي - أ", "الصف الثاني الابتدائي - ب",
    "الصف الثالث المتوسط - ج", "الصف السادس الابتدائي - د",
    "الصف الأول الثانوي - هـ", "الصف الثاني الثانوي - و",
]


def make_report(rows: int) -> dict:
    """A school-attendance report body with ``rows`` class rows."""
    return {
        "summary": {
            "total_records": rows * 30,
            "overall_rate": 93.4,
            "present": rows * 27,
            "absent": rows * 2,
            "late": rows * 1,
        },
        "by_class": [
            {
                "class_name": f"{ARABIC_CLASS_NAMES[i % len(ARABIC_CLASS_NAMES)]} ({i + 1})",
                "present": 27,
                "absent": 2,
                "late": 1,
            }
            for i in range(rows)
        ],
    }


def build_pdf(rows: int) -> int:
    """Exactly what the export routes run today, synchronously."""
    engine = ExportEngine(db=None)
    buf = engine._to_pdf(
        "school_attendance",
        make_report(rows),
        {"start_date": "2026-01-01", "end_date": "2026-06-30"},
        "2026-07-31T12:00:00Z",
        "school-evidence",
    )
    return len(buf.getvalue())


async def scenario(label: str, rows: int, offload: bool):
    hb = Heartbeat()
    hb.start()
    await asyncio.sleep(0.2)  # baseline ticks before the work starts

    started = time.perf_counter()
    if offload:
        loop = asyncio.get_running_loop()
        size = await loop.run_in_executor(None, build_pdf, rows)
    else:
        size = build_pdf(rows)
    elapsed = (time.perf_counter() - started) * 1000

    await asyncio.sleep(0.2)
    await hb.stop()
    print(
        f"{label:<44} build={elapsed:8.0f}ms  pdf={size / 1024:6.1f}KB  "
        f"loop-lag: {hb.report()}"
    )
    return elapsed


async def concurrent_scenario(label: str, rows: int, n: int, offload: bool):
    """n users ask for a report at the same instant."""
    hb = Heartbeat()
    hb.start()
    await asyncio.sleep(0.2)

    started = time.perf_counter()
    if offload:
        loop = asyncio.get_running_loop()
        await asyncio.gather(*[
            loop.run_in_executor(None, build_pdf, rows) for _ in range(n)
        ])
    else:
        for _ in range(n):  # inline: the loop can only do them one after another
            build_pdf(rows)
    elapsed = (time.perf_counter() - started) * 1000

    await asyncio.sleep(0.2)
    await hb.stop()
    print(f"{label:<44} total={elapsed:8.0f}ms  loop-lag: {hb.report()}")


async def main():
    print("\n=== Idle baseline (no PDF work) ===")
    hb = Heartbeat()
    hb.start()
    await asyncio.sleep(1.0)
    await hb.stop()
    print(f"{'idle loop':<44} {'':>28}loop-lag: {hb.report()}")

    print("\n=== A. PDF built inline on the event loop (today's behaviour) ===")
    for rows in (5, 50, 200, 500):
        await scenario(f"inline build, {rows} table rows", rows, offload=False)

    print("\n=== B. Same builds off the loop (run_in_executor) ===")
    for rows in (5, 50, 200, 500):
        await scenario(f"offloaded build, {rows} table rows", rows, offload=True)

    print("\n=== C. 4 users request a 200-row report at once ===")
    await concurrent_scenario("inline (serialized on the loop)", 200, 4, offload=False)
    await concurrent_scenario("offloaded (thread pool)", 200, 4, offload=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())
