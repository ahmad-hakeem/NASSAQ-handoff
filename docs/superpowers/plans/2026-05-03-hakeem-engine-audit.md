# Hakeem Engine Audit & Generation Summary — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit the Hakeem auto-generation engine for hard-constraint enforcement (A–F) and fairness (G), fix any real gaps the user approves from the audit, and add a rich, persisted `generation_summary` object to every run.

**Architecture:** Two-phase. Phase 1 is read-only — produce `docs/superpowers/specs/2026-05-03-hakeem-engine-audit-report.md` and pause for the user to pick which gaps to fix. Phase 2 applies approved fixes, then adds rejection counters to the placement loop, builds the summary at the end of `generate_timetable`, persists it to a new `timetable_runs.generation_summary` JSONB column, and returns it in the API response.

**Tech Stack:** Python (FastAPI), SQLAlchemy, Alembic, PostgreSQL (JSONB), pytest.

**Spec:** `docs/superpowers/specs/2026-05-03-hakeem-engine-audit-design.md`

---

## File Structure

**Read-only in Phase 1 (audit):**
- `backend/routes/scheduling_smart_engine_routes.py` — endpoint + payload assembly
- `backend/engines/smart_scheduling_engine.py` — `generate_timetable` (line 2791), placement loop (~1647–1720), `_log_run` (line 3351)
- `backend/engines/hard_constraints/validators/*.py` — registry validators
- `backend/pg_models.py` — `TimetableRun` (line 349)

**Created in Phase 2:**
- `docs/superpowers/specs/2026-05-03-hakeem-engine-audit-report.md` — the audit report (Task 1)
- `backend/alembic/versions/u1v2w3x4y5z6_add_generation_summary_to_timetable_runs.py` — migration
- `backend/engines/scheduling_summary.py` — small helper module that builds the `GenerationSummary` dict from accumulated counters
- `backend/tests/test_scheduling_summary.py` — unit tests for the helper

**Modified in Phase 2:**
- `backend/pg_models.py:349-363` — add `generation_summary` JSONB column to `TimetableRun`
- `backend/engines/smart_scheduling_engine.py` — initialize counter dict in `generate_timetable` (~line 2791), increment counters at existing rejection sites in the placement loop (~line 1571–1720), build summary near the success log (~line 3262), persist on the run row, return in result
- `backend/routes/scheduling_smart_engine_routes.py:118` — include `generation_summary` in the response payload returned by `smart_generate_timetable`
- `backend/tests/test_scheduling_smart_engine.py` — extend with one integration test asserting the summary shape

---

## Phase 1 — Audit (read-only)

### Task 1: Produce the audit report

**Files:**
- Create: `docs/superpowers/specs/2026-05-03-hakeem-engine-audit-report.md`

This task does not modify code. It reads the engine and registry, then writes the audit report.

- [ ] **Step 1: Read the engine entry point**

Read `backend/engines/smart_scheduling_engine.py` lines 2791–3300 (`generate_timetable` from start to success log) and lines 1540–1900 (the placement loop, `_registry_rejects`, and `_record_unscheduled_demand` if present). Note the exact line numbers of every check that rejects a placement.

- [ ] **Step 2: Read every hard-constraint validator**

Read each file in `backend/engines/hard_constraints/validators/`. For each validator, record: the constraint it enforces, the rejection condition, and whether it is wired into the registry (`backend/engines/hard_constraints/__init__.py`).

- [ ] **Step 3: Read the route's payload assembly**

Read `backend/routes/scheduling_smart_engine_routes.py` lines 100–250 (around `smart_generate_timetable`). Confirm what enters `context_payload` and whether each of these is fetched: `school_settings`, `time_slots`, `teacher_assignments`, `teacher_class_assignments`, `unavailability` (entity_type='teacher'), `timetable_hard_constraints`, `timetable_soft_constraints`. Note any fallback to defaults when a source is empty.

- [ ] **Step 4: Write the audit report**

Create `docs/superpowers/specs/2026-05-03-hakeem-engine-audit-report.md` with this exact structure:

```markdown
# Hakeem Engine Audit Report

**Date:** 2026-05-03
**Spec:** docs/superpowers/specs/2026-05-03-hakeem-engine-audit-design.md

## 1. Scope & method
[2–4 sentences: what files were read, what was not.]

## 2. Data hydration verification
| Source | Loaded? | File:Line | Silent fallback? | Notes |
|---|---|---|---|---|
| school_settings (periods, days) | ... | ... | ... | ... |
| time_slots | ... | ... | ... | ... |
| teacher_assignments | ... | ... | ... | ... |
| teacher_class_assignments | ... | ... | ... | ... |
| unavailability (teacher) | ... | ... | ... | ... |
| timetable_hard_constraints | ... | ... | ... | ... |
| timetable_soft_constraints | ... | ... | ... | ... |

## 3. Hard-constraint matrix
| ID | Constraint | File:Line of check | Observed behavior | Verdict | Recommended fix |
|---|---|---|---|---|---|
| A1 | Teacher double-booking | ... | ... | ✅/⚠/❌ | ... |
| A2 | Class double-booking | ... | ... | ... | ... |
| B  | Teacher unavailability honored | ... | ... | ... | ... |
| C  | Boundary (active_days × periods_per_day) | ... | ... | ... | ... |
| D  | Teacher weekly quota | ... | ... | ... | ... |
| E  | Max consecutive periods/teacher | ... | ... | ... | ... |
| F  | Max periods per day/teacher | ... | ... | ... | ... |

## 4. Soft-constraint / fairness (G)
| ID | Constraint | File:Line | Observed behavior | Verdict |
|---|---|---|---|---|
| G  | Distribution fairness across days | ... | ... | ... |

## 5. Logging & summary gap analysis
- Already exists: [list of fields/log records the engine produces today]
- Will be added by `generation_summary`: [delta vs. current logging]

## 6. Recommended fix list
| # | Severity | Constraint | Fix | Estimated touch |
|---|---|---|---|---|
| 1 | Critical/Important/Nice | A1/B/... | one-paragraph fix description | files + approx LOC |
```

Every cell must contain real content — no "TBD", no "see code". If a constraint is fully enforced, write "Enforced — no fix needed" in the Recommended Fix column.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-05-03-hakeem-engine-audit-report.md
git commit -m "docs: hakeem engine constraint audit report"
```

- [ ] **Step 6: Pause for user review**

Stop execution. Tell the user:

> "Audit report committed at `docs/superpowers/specs/2026-05-03-hakeem-engine-audit-report.md`. Please review §6 (Recommended fix list) and tell me which fixes to apply (e.g., 'apply 1, 3, skip 2'). I'll then proceed to Task 2 with that subset."

Do **not** start Task 2 until the user responds with an approval list.

---

## Phase 2 — Fixes + Summary

### Task 2: Apply approved gap fixes

**Files:** Determined by the user-approved fix list from Task 1, Step 6.

This task is templated — its concrete steps are written *after* the user approves the fix list. Each approved fix becomes its own sub-task following this template:

- [ ] **Step 1: Write the failing test**

Add a test in `backend/tests/test_scheduling_smart_engine.py` (or the relevant existing test file in `backend/tests/`) that constructs a minimal scenario violating the constraint and asserts the engine refuses to place the offending session (or places it correctly, depending on the gap).

```python
def test_<constraint_id>_<short_name>():
    # Arrange: minimal payload that exercises the gap
    # Act: call the placement function (or full generate_timetable in-memory)
    # Assert: rejection / correct placement
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_scheduling_smart_engine.py::test_<constraint_id>_<short_name> -v`
Expected: FAIL (engine currently does not enforce the constraint).

- [ ] **Step 3: Apply the minimal fix**

Edit the precise file:line called out in the audit report's "Recommended fix" column for that row. Show the exact edited code in the plan once it is written. Keep the fix surgical — no incidental refactors.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_scheduling_smart_engine.py::test_<constraint_id>_<short_name> -v`
Expected: PASS.

- [ ] **Step 5: Run the full scheduling test suite**

Run: `pytest backend/tests/test_scheduling_smart_engine.py backend/tests/test_smart_scheduling.py backend/tests/test_hard_constraint_validators_core.py backend/tests/test_hard_constraint_validators_extended.py backend/tests/test_hard_constraint_registry.py -v`
Expected: All previously-passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/...
git commit -m "fix(hakeem): enforce <constraint_id> <short description>"
```

If the audit report concludes that all constraints are already fully enforced, Task 2 is a no-op — record this in the commit log of Task 3 ("audit found no gaps") and skip directly to Task 3.

---

### Task 3: Add `generation_summary` JSONB column to `timetable_runs`

**Files:**
- Create: `backend/alembic/versions/u1v2w3x4y5z6_add_generation_summary_to_timetable_runs.py`
- Modify: `backend/pg_models.py:349-363`

- [ ] **Step 1: Write the migration**

Create `backend/alembic/versions/u1v2w3x4y5z6_add_generation_summary_to_timetable_runs.py`:

```python
"""add generation_summary to timetable_runs

Revision ID: u1v2w3x4y5z6
Revises: t1u2v3w4x5y6
Create Date: 2026-05-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'u1v2w3x4y5z6'
down_revision: Union[str, Sequence[str], None] = 't1u2v3w4x5y6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'timetable_runs',
        sa.Column('generation_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('timetable_runs', 'generation_summary')
```

- [ ] **Step 2: Add the column to the SQLAlchemy model**

In `backend/pg_models.py`, add inside the `TimetableRun` class (immediately after the `warnings` column on line 360):

```python
    generation_summary = Column(JSONB, nullable=True)
```

- [ ] **Step 3: Run the migration**

Run: `cd backend && alembic upgrade head`
Expected: `INFO  [alembic.runtime.migration] Running upgrade t1u2v3w4x5y6 -> u1v2w3x4y5z6, add generation_summary to timetable_runs`

- [ ] **Step 4: Verify column exists**

Run: `cd backend && python -c "from pg_models import TimetableRun; print('generation_summary' in TimetableRun.__table__.c)"`
Expected: `True`

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/u1v2w3x4y5z6_add_generation_summary_to_timetable_runs.py backend/pg_models.py
git commit -m "feat(db): add generation_summary JSONB to timetable_runs"
```

---

### Task 4: Build the summary helper module

**Files:**
- Create: `backend/engines/scheduling_summary.py`
- Create: `backend/tests/test_scheduling_summary.py`

The helper accepts the counters and per-teacher placement records that the placement loop accumulates, and returns the JSON-shaped summary defined in the spec §6.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_scheduling_summary.py`:

```python
from backend.engines.scheduling_summary import (
    RejectionCounters,
    TeacherPlacementRecord,
    build_generation_summary,
)


def test_build_generation_summary_basic_shape():
    counters = RejectionCounters()
    counters.teacher_busy = 12
    counters.class_busy = 4
    counters.teacher_unavailable = 3
    counters.max_consecutive_exceeded = 5
    counters.max_per_day_exceeded = 2
    counters.weekly_quota_exceeded = 1
    counters.constraint_registry_rejected = 7
    counters.no_eligible_teacher = 0

    teacher_records = [
        TeacherPlacementRecord(
            teacher_id="t1",
            name="Yousef",
            by_day={"sun": 4, "mon": 3, "tue": 4, "wed": 4, "thu": 3},
            max_consecutive=3,
            gaps=1,
        )
    ]

    unplaced = [
        {"class_id": "c1", "subject_id": "s1", "remaining": 2, "primary_reason": "teacher_unavailable"},
    ]

    result = build_generation_summary(
        required=240,
        placed=235,
        elapsed_ms=1842,
        fairness_score=87,
        constraints_evaluated=[
            "double_booking_teacher",
            "double_booking_class",
            "unavailability",
            "boundary",
            "weekly_quota",
            "max_consecutive_per_day",
            "max_periods_per_day",
        ],
        rejection_counters=counters,
        teacher_records=teacher_records,
        unplaced_demands=unplaced,
    )

    assert result["schema_version"] == 1
    assert result["totals"] == {
        "required": 240,
        "placed": 235,
        "failed": 5,
        "placement_rate": 0.979,
    }
    assert result["elapsed_ms"] == 1842
    assert result["fairness"]["overall_score"] == 87
    assert result["fairness"]["per_teacher"][0]["total_periods"] == 18
    assert result["rejections_by_reason"]["teacher_busy"] == 12
    assert result["rejections_by_reason"]["no_eligible_teacher"] == 0
    assert result["unplaced_demands"] == unplaced


def test_build_generation_summary_zero_required():
    result = build_generation_summary(
        required=0,
        placed=0,
        elapsed_ms=10,
        fairness_score=0,
        constraints_evaluated=[],
        rejection_counters=RejectionCounters(),
        teacher_records=[],
        unplaced_demands=[],
    )
    assert result["totals"]["placement_rate"] is None
    assert result["totals"]["failed"] == 0


def test_rejection_counters_default_to_zero_in_output():
    counters = RejectionCounters()
    result = build_generation_summary(
        required=1, placed=1, elapsed_ms=1, fairness_score=0,
        constraints_evaluated=[], rejection_counters=counters,
        teacher_records=[], unplaced_demands=[],
    )
    for key in [
        "teacher_busy", "class_busy", "teacher_unavailable",
        "max_consecutive_exceeded", "max_per_day_exceeded",
        "weekly_quota_exceeded", "constraint_registry_rejected",
        "no_eligible_teacher",
    ]:
        assert result["rejections_by_reason"][key] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_scheduling_summary.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.engines.scheduling_summary'`

- [ ] **Step 3: Implement the helper**

Create `backend/engines/scheduling_summary.py`:

```python
"""Build the generation_summary object for a Hakeem timetable run.

Schema is defined in docs/superpowers/specs/2026-05-03-hakeem-engine-audit-design.md §6.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RejectionCounters:
    teacher_busy: int = 0
    class_busy: int = 0
    teacher_unavailable: int = 0
    max_consecutive_exceeded: int = 0
    max_per_day_exceeded: int = 0
    weekly_quota_exceeded: int = 0
    constraint_registry_rejected: int = 0
    no_eligible_teacher: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "teacher_busy": self.teacher_busy,
            "class_busy": self.class_busy,
            "teacher_unavailable": self.teacher_unavailable,
            "max_consecutive_exceeded": self.max_consecutive_exceeded,
            "max_per_day_exceeded": self.max_per_day_exceeded,
            "weekly_quota_exceeded": self.weekly_quota_exceeded,
            "constraint_registry_rejected": self.constraint_registry_rejected,
            "no_eligible_teacher": self.no_eligible_teacher,
        }


@dataclass
class TeacherPlacementRecord:
    teacher_id: str
    name: str
    by_day: Dict[str, int] = field(default_factory=dict)
    max_consecutive: int = 0
    gaps: int = 0

    def total_periods(self) -> int:
        return sum(self.by_day.values())

    def as_dict(self) -> Dict[str, Any]:
        return {
            "teacher_id": self.teacher_id,
            "name": self.name,
            "total_periods": self.total_periods(),
            "by_day": dict(self.by_day),
            "max_consecutive": self.max_consecutive,
            "gaps": self.gaps,
        }


def build_generation_summary(
    *,
    required: int,
    placed: int,
    elapsed_ms: int,
    fairness_score: int,
    constraints_evaluated: List[str],
    rejection_counters: RejectionCounters,
    teacher_records: List[TeacherPlacementRecord],
    unplaced_demands: List[Dict[str, Any]],
) -> Dict[str, Any]:
    failed = max(required - placed, 0)
    placement_rate: Optional[float]
    if required == 0:
        placement_rate = None
    else:
        placement_rate = round(placed / required, 3)

    return {
        "schema_version": 1,
        "totals": {
            "required": required,
            "placed": placed,
            "failed": failed,
            "placement_rate": placement_rate,
        },
        "elapsed_ms": elapsed_ms,
        "fairness": {
            "overall_score": fairness_score,
            "per_teacher": [r.as_dict() for r in teacher_records],
        },
        "rejections_by_reason": rejection_counters.as_dict(),
        "constraints_evaluated": list(constraints_evaluated),
        "unplaced_demands": list(unplaced_demands),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_scheduling_summary.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/engines/scheduling_summary.py backend/tests/test_scheduling_summary.py
git commit -m "feat(hakeem): add scheduling_summary helper module"
```

---

### Task 5: Wire counters into the placement loop

**Files:**
- Modify: `backend/engines/smart_scheduling_engine.py` (placement loop ~line 1571–1720)

The placement loop already rejects placements at known sites (class busy ~1667, teacher busy ~1685, unavailability ~1679, registry ~1571). Increment the matching counter at each site.

- [ ] **Step 1: Read the placement loop**

Read `backend/engines/smart_scheduling_engine.py` lines 1540–1750. Identify every `continue`/`return False` site that represents a rejection and map it to a `RejectionCounters` field. Record the exact line for each in a temporary scratchpad before editing.

- [ ] **Step 2: Add counter parameter to the placement function**

Locate the function that contains the placement loop (around line 1647). Add a `rejection_counters: RejectionCounters | None = None` keyword argument. Import at top of file:

```python
from backend.engines.scheduling_summary import (
    RejectionCounters,
    TeacherPlacementRecord,
    build_generation_summary,
)
```

- [ ] **Step 3: Increment counters at each rejection site**

At each rejection site identified in Step 1, before the `continue`/`return False`, add:

```python
if rejection_counters is not None:
    rejection_counters.teacher_busy += 1   # or whichever field matches the rejection
```

The mapping must be:
- Class double-booking site → `class_busy`
- Teacher double-booking site → `teacher_busy`
- Unavailability site → `teacher_unavailable`
- `_registry_rejects` returning True → `constraint_registry_rejected`
- "No eligible teacher" branches (where the candidate list is empty) → `no_eligible_teacher`
- Any max-consecutive check → `max_consecutive_exceeded`
- Any max-per-day check → `max_per_day_exceeded`
- Any weekly-quota check → `weekly_quota_exceeded`

If a particular check does not currently exist (e.g., the audit report concluded `max_consecutive_exceeded` is not enforced and the user did not approve adding it), leave that counter at zero — do not invent a check.

- [ ] **Step 4: Run the existing test suite**

Run: `pytest backend/tests/test_scheduling_smart_engine.py backend/tests/test_smart_scheduling.py -v`
Expected: All previously-passing tests still pass (counters default to None when caller does not pass them).

- [ ] **Step 5: Commit**

```bash
git add backend/engines/smart_scheduling_engine.py
git commit -m "feat(hakeem): increment rejection counters in placement loop"
```

---

### Task 6: Build summary in `generate_timetable` and persist it

**Files:**
- Modify: `backend/engines/smart_scheduling_engine.py` (`generate_timetable`, ~line 2791 and ~line 3262)

- [ ] **Step 1: Initialize counters at the start of `generate_timetable`**

In `generate_timetable` (line 2791), immediately after capturing `start_time` / `run_id`, add:

```python
import time as _time
_summary_start_ms = int(_time.monotonic() * 1000)
rejection_counters = RejectionCounters()
```

Pass `rejection_counters=rejection_counters` to every internal call that reaches the placement loop modified in Task 5.

- [ ] **Step 2: Build per-teacher records from the final grid**

After the placement loop completes and just before the success log at line 3262, walk the produced sessions to build `teacher_records`. Add a helper inline:

```python
def _build_teacher_records(grid, teachers_by_id) -> list[TeacherPlacementRecord]:
    by_teacher: dict[str, dict[str, int]] = {}
    for day, periods in grid.items():
        for period, slot in periods.items():
            for teacher_id in slot.get("teachers", []):
                by_teacher.setdefault(teacher_id, {}).setdefault(day, 0)
                by_teacher[teacher_id][day] += 1
    records = []
    for teacher_id, by_day in by_teacher.items():
        teacher = teachers_by_id.get(teacher_id, {})
        records.append(TeacherPlacementRecord(
            teacher_id=teacher_id,
            name=teacher.get("name", ""),
            by_day=by_day,
            max_consecutive=0,  # leave at 0 for v1; populate in a follow-up if needed
            gaps=0,             # same
        ))
    return records
```

The exact shape of `grid` and the iteration keys must be adapted to the engine's actual data structures — read lines 1640–1750 to confirm names before writing this. If the grid uses different field names (e.g., `slot["teacher_id"]` instead of `slot["teachers"]`), adjust accordingly. Do not invent fields.

- [ ] **Step 3: Build the summary and persist it**

Just before the existing `_log_run("info", "اكتمل توليد الجدول", ...)` call near line 3262, add:

```python
elapsed_ms = int(_time.monotonic() * 1000) - _summary_start_ms

generation_summary = build_generation_summary(
    required=total_required_sessions,        # use the variable already computed during demand-matrix build
    placed=sessions_created_count,           # use existing counter
    elapsed_ms=elapsed_ms,
    fairness_score=fairness_score,           # use existing fairness metric if computed; else 0
    constraints_evaluated=[
        "double_booking_teacher",
        "double_booking_class",
        "unavailability",
        "boundary",
        "weekly_quota",
        "max_consecutive_per_day",
        "max_periods_per_day",
    ],
    rejection_counters=rejection_counters,
    teacher_records=_build_teacher_records(grid, teachers_by_id),
    unplaced_demands=[
        {
            "class_id": d["class_id"],
            "subject_id": d["subject_id"],
            "remaining": d["remaining"],
            "primary_reason": d.get("primary_reason", "unknown"),
        }
        for d in unscheduled_demands_summary  # use existing list of unscheduled demand records
    ],
)
```

The variable names `total_required_sessions`, `sessions_created_count`, `fairness_score`, `grid`, `teachers_by_id`, `unscheduled_demands_summary` must be replaced with the engine's actual variable names from lines 2791–3260. Read first; do not guess.

- [ ] **Step 4: Persist on the `timetable_runs` row**

Locate the existing UPDATE that sets `status='completed'` on the `timetable_runs` row near line 3262–3290. Add `generation_summary=generation_summary` to the same UPDATE statement so the column is written atomically with status. If the engine writes via `_log_run`, instead use the same SQLAlchemy session pattern already in use to update the run row.

- [ ] **Step 5: Add the summary to the returned result dict**

In the return value of `generate_timetable`, add the key `"generation_summary": generation_summary`. Do not remove existing keys.

- [ ] **Step 6: Run the scheduling test suite**

Run: `pytest backend/tests/test_scheduling_smart_engine.py backend/tests/test_smart_scheduling.py -v`
Expected: All previously-passing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add backend/engines/smart_scheduling_engine.py
git commit -m "feat(hakeem): build and persist generation_summary on each run"
```

---

### Task 7: Return `generation_summary` in the API response

**Files:**
- Modify: `backend/routes/scheduling_smart_engine_routes.py:118` (`smart_generate_timetable`)

- [ ] **Step 1: Read the current response shape**

Read `backend/routes/scheduling_smart_engine_routes.py` lines 100–250 to find where `smart_generate_timetable` builds its response from the engine's returned dict.

- [ ] **Step 2: Forward the summary**

Where the response dict is assembled, add (do not replace existing keys):

```python
"generation_summary": engine_result.get("generation_summary"),
```

`engine_result` should be replaced with the actual variable name holding the engine's return value.

- [ ] **Step 3: Add an integration test**

Append to `backend/tests/test_scheduling_smart_engine.py`:

```python
def test_generate_timetable_returns_generation_summary(seeded_school):
    """End-to-end: generation response includes a well-formed summary."""
    response = client.post(f"/api/smart-scheduling/generate/{seeded_school.id}")
    assert response.status_code == 200
    body = response.json()
    summary = body.get("generation_summary")
    assert summary is not None
    assert summary["schema_version"] == 1
    assert set(summary.keys()) >= {
        "schema_version", "totals", "elapsed_ms", "fairness",
        "rejections_by_reason", "constraints_evaluated", "unplaced_demands",
    }
    assert summary["totals"]["placed"] + summary["totals"]["failed"] == summary["totals"]["required"]
    for key in [
        "teacher_busy", "class_busy", "teacher_unavailable",
        "max_consecutive_exceeded", "max_per_day_exceeded",
        "weekly_quota_exceeded", "constraint_registry_rejected",
        "no_eligible_teacher",
    ]:
        assert key in summary["rejections_by_reason"]
```

The test name `seeded_school` and `client` must match the existing fixture and TestClient name in `backend/tests/test_scheduling_smart_engine.py`. Read the top of the file first; if a different fixture is used (e.g., `school_fixture`, `app_client`), substitute it.

- [ ] **Step 4: Run the new test**

Run: `pytest backend/tests/test_scheduling_smart_engine.py::test_generate_timetable_returns_generation_summary -v`
Expected: PASS.

- [ ] **Step 5: Run the full scheduling test suite**

Run: `pytest backend/tests/test_scheduling_smart_engine.py backend/tests/test_smart_scheduling.py backend/tests/test_hard_constraint_validators_core.py backend/tests/test_hard_constraint_validators_extended.py backend/tests/test_hard_constraint_registry.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/routes/scheduling_smart_engine_routes.py backend/tests/test_scheduling_smart_engine.py
git commit -m "feat(api): expose generation_summary in /api/smart-scheduling/generate response"
```

---

### Task 8: Manual verification + replit.md update

**Files:**
- Modify: `replit.md`

- [ ] **Step 1: Restart the Backend API workflow**

Use the `restart_workflow` tool with name `Backend API`. Confirm logs show no startup errors.

- [ ] **Step 2: Trigger one real generation**

Pick any school id present in the dev database (or use an existing test fixture's school id). Run:

```bash
curl -s -X POST "$REPLIT_DEV_DOMAIN/api/smart-scheduling/generate/<SCHOOL_ID>" \
  -H "Authorization: Bearer <DEV_TOKEN>" | python -m json.tool | grep -A 60 generation_summary
```

Expected: JSON block matching the §6 schema, with `totals.placed + totals.failed == totals.required`.

- [ ] **Step 3: Verify persistence**

Run a read-only SQL query (use the database skill, environment "development"):

```sql
SELECT id, status, generation_summary -> 'totals' AS totals
FROM timetable_runs
ORDER BY created_at DESC
LIMIT 1;
```

Expected: the most recent run shows a non-null `totals` JSON matching the response from Step 2.

- [ ] **Step 4: Update replit.md**

Append to `replit.md` under the appropriate section:

```markdown
- The Hakeem auto-generation engine emits a `generation_summary` JSON object on every run. The shape is defined in `docs/superpowers/specs/2026-05-03-hakeem-engine-audit-design.md` §6. It is returned from `POST /api/smart-scheduling/generate/{school_id}` and persisted to `timetable_runs.generation_summary`.
```

- [ ] **Step 5: Commit**

```bash
git add replit.md
git commit -m "docs: note generation_summary on Hakeem engine in replit.md"
```

---

## Self-Review

**Spec coverage:**
- §1 Goals 1–2 (audit + matrix) → Task 1.
- §1 Goal 3 (fix gaps) → Task 2 (templated; concretized after Task 1 user gate).
- §1 Goal 4 (summary returned + persisted) → Tasks 3–7.
- §6 Schema → Task 4 (helper + tests).
- §7 Persistence (nullable JSONB, no backfill) → Task 3.
- §8 API contract additive → Task 7.
- §9 Phases 1–6 → Tasks 1, 2, 5, 3+6, 7, 8 respectively.
- §11 Success criteria → Task 1 produces the audit report; Task 6 ensures `placed + failed == required`; Task 8 confirms persisted column matches response.

**Placeholder scan:**
- Task 2 is intentionally templated because its concrete fixes depend on the user-approved fix list from Task 1 — this is a deliberate user gate, not a placeholder. The template fully specifies the per-fix workflow.
- Task 6 Steps 2–3 explicitly call out variable-name lookups as a *read-then-substitute* step, not a "TBD". The exact engine variable names cannot be guessed — they must be read from the actual placement loop.

**Type consistency:**
- `RejectionCounters` and `TeacherPlacementRecord` defined in Task 4 are imported and used identically in Tasks 5 and 6.
- `build_generation_summary` keyword arguments in Task 4 match the call site in Task 6 Step 3.
- `generation_summary` column name is identical across migration (Task 3 Step 1), model (Task 3 Step 2), engine UPDATE (Task 6 Step 4), API response (Task 7 Step 2), and replit.md note (Task 8 Step 4).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-03-hakeem-engine-audit.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
