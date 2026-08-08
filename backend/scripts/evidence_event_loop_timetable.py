"""Evidence: does smart timetable generation block the asyncio event loop?

Phase-1 measurement for the "timetable generation freezes the server"
investigation. Run from the backend directory:

    cd backend && ENVIRONMENT=development python3 scripts/evidence_event_loop_timetable.py

No database and no HTTP server are involved. The script feeds the *real*
engine phases synthetic demand at three school sizes and, while they run,
ticks a heartbeat coroutine that should fire every 10 ms. How late each tick
actually is *is* event-loop blocking: while the loop is stuck inside the
placement search it cannot accept, read, route or answer any other request.

Three phases are measured separately, because they are not equally guilty and
they are not equally easy to move off the loop:

    Phase 6  generate_draft_timetable  — the combinatorial placement search
    Phase 7  detect_conflicts          — in-memory validation pass
    Phase 8  optimize_timetable        — in-memory hill climbing

All three are ``async def`` but none of them awaits anything that touches the
database once their constraint context is built, so every millisecond they
take is a millisecond the loop is frozen.
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
# only the scheduling engine itself is loaded.
_pkg = types.ModuleType("engines")
_pkg.__path__ = [os.path.join(BACKEND_DIR, "engines")]
sys.modules.setdefault("engines", _pkg)

from engines.smart_scheduling_engine import (  # noqa: E402
    AcademicDemand,
    ResourceAvailability,
    SmartSchedulingEngine,
)

TICK = 0.01  # heartbeat interval: 10 ms

WORKING_DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday"]
PERIODS_PER_DAY = 7

SUBJECT_NAMES = [
    "القرآن الكريم", "اللغة العربية", "الرياضيات", "العلوم", "الدراسات الإسلامية",
    "الدراسات الاجتماعية", "اللغة الإنجليزية", "التربية الفنية", "التربية البدنية",
    "المهارات الرقمية",
]
# Weekly load per subject, mirroring a typical Saudi primary/intermediate plan.
SUBJECT_PERIODS = [4, 6, 5, 4, 3, 2, 4, 1, 2, 2]


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


# --------------------------------------------------------------------------
# Synthetic school
# --------------------------------------------------------------------------
def make_settings() -> dict:
    slots = []
    for p in range(1, PERIODS_PER_DAY + 1):
        slots.append({
            "period": p,
            "slot_number": p,
            "start_time": f"{7 + p:02d}:00",
            "end_time": f"{7 + p:02d}:45",
            "type": "class",
            "is_break": False,
        })
    return {
        "working_days": WORKING_DAYS,
        "periods_per_day": PERIODS_PER_DAY,
        "teaching_period_numbers": list(range(1, PERIODS_PER_DAY + 1)),
        "time_slots": slots,
        "max_daily_periods": 6,
        "period_duration_minutes": 45,
    }


def make_school(classes: int, teachers: int):
    """Demands + resources for a school with ``classes`` classes."""
    subject_ids = [f"subj-{i}" for i in range(len(SUBJECT_NAMES))]

    # Every teacher covers 2 subjects; teachers are spread across subjects so
    # each subject has several eligible teachers (a realistic, solvable school).
    teacher_subjects = {}
    for t in range(teachers):
        a = subject_ids[t % len(subject_ids)]
        b = subject_ids[(t + 3) % len(subject_ids)]
        teacher_subjects[f"teacher-{t}"] = sorted({a, b})

    by_subject = {sid: [] for sid in subject_ids}
    for tid, subs in teacher_subjects.items():
        for sid in subs:
            by_subject[sid].append(tid)

    demands = []
    for c in range(classes):
        subjects = [
            {
                "subject_id": subject_ids[i],
                "subject_name": SUBJECT_NAMES[i],
                "weekly_periods": SUBJECT_PERIODS[i],
                "suitable_teachers": by_subject[subject_ids[i]],
                "priority": 1,
            }
            for i in range(len(subject_ids))
        ]
        demands.append(AcademicDemand(
            class_id=f"class-{c}",
            class_name=f"الصف {c + 1}",
            grade_id=f"grade-{(c % 6) + 1}",
            subjects=subjects,
            total_periods_required=sum(SUBJECT_PERIODS),
        ))

    resources = [
        ResourceAvailability(
            teacher_id=tid,
            teacher_name=f"معلم {tid}",
            subject_ids=subs,
            weekly_load=24,
            current_load=0,
            availability={d: list(range(1, PERIODS_PER_DAY + 1)) for d in WORKING_DAYS},
        )
        for tid, subs in teacher_subjects.items()
    ]
    return demands, resources


class _NoDB:
    """The engine only touches the DB through _log_run here, which we stub."""

    @property
    def session(self):
        raise AssertionError("evidence run must not touch the database")


def make_engine() -> SmartSchedulingEngine:
    engine = SmartSchedulingEngine(_NoDB())

    async def _no_log(*_a, **_kw):
        return None

    engine._log_run = _no_log  # type: ignore[method-assign]
    return engine


# --------------------------------------------------------------------------
# Scenarios
# --------------------------------------------------------------------------
async def run_phases(engine, demands, resources, settings, offload: bool):
    """Phases 6-8 exactly as generate_timetable chains them.

    ``offload=False`` calls the ``*_sync`` cores directly on the loop — that is
    literally what the code did before this work, so it is the honest "before"
    measurement. ``offload=True`` calls the public async methods, which hand
    the same cores to the timetable pool.
    """
    timings = {}

    t0 = time.perf_counter()
    if offload:
        _tid, sessions, _conf, _unsched, _under = await engine.generate_draft_timetable(
            "school-evidence", "run-evidence", demands, resources, settings, [], seed=7,
        )
    else:
        _tid, sessions, _conf, _unsched, _under, _logs = engine._generate_draft_timetable_sync(
            "school-evidence", "run-evidence", demands, resources, settings, [], seed=7,
        )
    timings["draft"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    if offload:
        conflicts = await engine.detect_conflicts(sessions, resources, [], "run-evidence")
    else:
        conflicts = engine._detect_conflicts_sync(sessions, resources, [], "run-evidence")
    timings["conflicts"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    if offload:
        await engine.optimize_timetable(sessions, conflicts, resources, settings)
    else:
        engine._optimize_timetable_sync(sessions, conflicts, resources, settings)
    timings["optimize"] = (time.perf_counter() - t0) * 1000

    timings["sessions"] = len(sessions)
    return timings


async def scenario(label: str, classes: int, teachers: int, offload: bool):
    demands, resources = make_school(classes, teachers)
    settings = make_settings()

    hb = Heartbeat()
    hb.start()
    await asyncio.sleep(0.2)  # baseline ticks before the work starts

    started = time.perf_counter()
    timings = await run_phases(make_engine(), demands, resources, settings, offload)
    elapsed = (time.perf_counter() - started) * 1000

    await asyncio.sleep(0.2)
    await hb.stop()
    print(
        f"{label:<40} total={elapsed:8.0f}ms  "
        f"(draft={timings['draft']:.0f} conflicts={timings['conflicts']:.0f} "
        f"optimize={timings['optimize']:.0f})  "
        f"sessions={timings['sessions']:<5} loop-lag: {hb.report()}"
    )


async def concurrent_scenario(label: str, classes: int, teachers: int, n: int, offload: bool):
    """n principals press "إنشاء الجدول تلقائياً" at the same instant."""
    payloads = [make_school(classes, teachers) for _ in range(n)]
    settings = make_settings()

    hb = Heartbeat()
    hb.start()
    await asyncio.sleep(0.2)

    started = time.perf_counter()
    if offload:
        await asyncio.gather(*[
            run_phases(make_engine(), d, r, settings, True) for d, r in payloads
        ])
    else:
        for d, r in payloads:  # inline: the loop runs them one after another
            await run_phases(make_engine(), d, r, settings, False)
    elapsed = (time.perf_counter() - started) * 1000

    await asyncio.sleep(0.2)
    await hb.stop()
    print(f"{label:<40} total={elapsed:8.0f}ms  loop-lag: {hb.report()}")


SIZES = [
    ("small school  (12 classes, 30 teachers)", 12, 30),
    ("medium school (24 classes, 45 teachers)", 24, 45),
    ("large school  (40 classes, 70 teachers)", 40, 70),
]


async def main():
    print("\n=== Idle baseline (no scheduling work) ===")
    hb = Heartbeat()
    hb.start()
    await asyncio.sleep(1.0)
    await hb.stop()
    print(f"{'idle loop':<40} {'':>54}loop-lag: {hb.report()}")

    print("\n=== A. Generation on the event loop (today's behaviour) ===")
    for label, c, t in SIZES:
        await scenario(f"inline  {label}", c, t, offload=False)

    print("\n=== B. Same generation off the loop (run_in_executor) ===")
    for label, c, t in SIZES:
        await scenario(f"offload {label}", c, t, offload=True)

    print("\n=== C. 3 principals generate a 24-class school at once ===")
    await concurrent_scenario("inline (serialized on the loop)", 24, 45, 3, offload=False)
    await concurrent_scenario("offloaded (thread pool)", 24, 45, 3, offload=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())
