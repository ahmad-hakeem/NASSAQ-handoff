# Batch 2 Remediation Plan — Hard-Constraint Enforcement Match UI

**Created:** 2026-04-17
**Audit source:** `docs/audits/2026-04-17-timetable-audit.md`
**Targets (6 findings):** F-CN-01, F-CN-02, F-CN-03, F-CN-11, F-EN-08, F-EN-09 (scoped subset)
**Style:** TDD — every task ships with a failing test first, then the production change, then a green test.

---

## 0. Problem Statement (in plain language)

The principal Settings UI lists **17 hard constraints** (HC-01 … HC-17) and tells the principal "these MUST be enforced." In reality only **3** of them are actually checked anywhere in the system (teacher overlap, class overlap, schedule completeness):

* The engine loads every active hard-constraint row, then **never reads `validation_key`** — it relies on hand-coded inline checks for two of them and ignores the rest. (F-CN-01, F-EN-08)
* The publish-gate validator (`validate_before_publish`) has a hand-rolled `if`-chain that only knows about the same three. (F-CN-02)
* Two teachers (or classes) can be put in the **same room at the same time** and nothing detects it — neither at generation, nor in conflict detection, nor at publish. (F-CN-03)
* A class can finish generation **missing 2 of 5 weekly Math periods** and no `TimetableConflict` is raised — the engine `unscheduled.append(...)` swallows it. (F-CN-11)
* The "smart" engine has no awareness of subject-must-use-room, daily limits, morning-only, pinned sessions, etc. (F-EN-09 — partial scope only in this batch.)

**Outcome of Batch 2:** the 17 hard constraints become real. Every active `validation_key` is dispatched to a registered validator at generation time AND at publish time. Room overlap, subject quota, and daily period cap become first-class conflicts. The publish-gate becomes the single authoritative gate.

---

## 1. Scope & Out-of-Scope

### In scope (this batch)

| Finding | Severity | What this batch delivers |
|---|---|---|
| F-CN-01 | Critical | `HardConstraintRegistry`: one validator per `validation_key`, dispatched in both engine and publish-gate. |
| F-EN-08 | Medium | Same registry — replaces the two-key `if`-chain in the placement loop. |
| F-CN-02 | High | `validate_before_publish` uses the registry; all 17 keys produce structured `validation_errors` when violated. |
| F-CN-03 | High | `ROOM_OVERLAP` added to `ConflictType`; `detect_conflicts` and `_count_real_conflicts` group by `(room_id, day, period)`. |
| F-CN-11 | Medium | `detect_conflicts` adds `SUBJECT_QUOTA_VIOLATION` per `(class_id, subject_id)` and `DAILY_PERIOD_LIMIT_EXCEEDED` per `(teacher_id, day)`. |
| F-EN-09 | High | **Scoped to the recommendation tail only**: `_analyze_capacity_issues` results are surfaced as a structured `infeasibility_report` returned by the validate / pre-check endpoints **before** generation runs. The full CSP/OR-Tools rewrite is deferred to a later batch. |

### Explicitly out of scope (defer to later batches)

* Full CSP/OR-Tools backbone for F-EN-09 (effort L; needs its own design doc).
* F-CN-04 / F-CN-05 / F-CN-07–10 / F-CN-12 (soft-constraint correctness, custom-soft-constraint wiring, i18n keys) — separate batch.
* HC-11 (`teacher_subject_match`) and HC-15 (`academic_structure_match`) rely on data that is sparsely populated today (`teacher.qualifications`, `class.curriculum.subjects`). We register the validators but emit `MEDIUM` severity (warnings, not blockers) so absent data does not break legitimate publish flows. HC-12 (`teacher_class_assignment`) is **NOT** in this demotion — it stays HIGH because `teacher_assignments` is the source-of-truth table populated by Phase 4 of the Batch-1 onboarding flow, so absent rows there genuinely indicate a misconfiguration.

### Non-targets (do not touch in this batch)

* `backend/services/scheduling_service.py` (the legacy random-shuffle generator) — separate batch.
* `backend/engines/scheduling_engine.py` legacy time-slot engine — separate batch.
* Frontend wiring of the new error codes (Batch 9: i18n).

---

## 2. Architecture: the `HardConstraintRegistry`

A single module — `backend/engines/hard_constraints/__init__.py` — exposes:

```python
ValidationFn = Callable[[ConstraintContext], List[ConstraintViolation]]

@dataclass(frozen=True)
class ConstraintViolation:
    code: str                      # e.g. "HC-03"
    validation_key: str            # e.g. "room_overlap"
    severity: ConflictSeverity     # CRITICAL / HIGH / MEDIUM / LOW
    message_en: str
    message_ar: str
    refs: Dict[str, Any]           # {"session_ids": [...], "room_id": ..., "day": ..., "period": ...}

@dataclass
class ConstraintContext:
    school_id: str
    sessions: List[dict]           # candidate or placed sessions
    demands: List[dict]            # weekly_periods per (class_id, subject_id)
    resources: Dict[str, dict]     # teacher / class / room / subject lookups
    time_slots: List[dict]
    settings: Dict[str, Any]       # school_constraints overrides (max_daily_periods, etc.)

VALIDATION_REGISTRY: Dict[str, ValidationFn] = { ... }   # 17 entries
```

The registry is **closed** (every seeded `validation_key` MUST map to an entry; CI fails otherwise). Each validator is a pure function over `ConstraintContext` — no DB access, no I/O — so it can run inside both:

1. The engine's placement loop (per candidate placement, fast subset).
2. The publish-gate (whole-timetable scan).

A small façade splits validators into two tiers:

```python
def validate_placement(ctx, candidate) -> List[Violation]:  # incremental, called per candidate
def validate_full(ctx) -> List[Violation]:                  # whole-grid, called by publish-gate & detect_conflicts
```

This keeps engine performance reasonable while reusing the same logic.

---

## 3. Tasks

Tasks are TDD. Each task is a single dedicated subagent.

**Execution DAG (corrected after pre-plan architect review):**

```
Task 1 (registry skeleton)
   │
   ├──> Task 2 (5 must-be-real validators)  ──┐
   │                                           │
   └──> Task 4 (12 remaining validators incl. HC-14) ──┐
                                                       │
                                              Task 6 (engine wiring + literal-rule_key migration)
                                                       │
                                              ├──> Task 3 (detect_conflicts + new ConflictType)
                                              │
                                              └──> Task 5 (publish-gate + publish-action enforcement)
                                                       │
                                              Task 7 (infeasibility report + 422 gating)
                                                       │
                                              Task 8 (annotation + sweep)
```

Tasks 2 and 4 may run in parallel. Tasks 3 and 5 may run in parallel after Task 6. Everything else is strictly sequential.

### Task 1 — Build the registry skeleton + tier-split harness

**Goal:** Land `backend/engines/hard_constraints/` with the `VALIDATION_REGISTRY`, `ConstraintContext`, `ConstraintViolation`, `validate_placement`, `validate_full` — all 17 validators present but most still raise `NotImplementedError`. Wire a CI guard that fails if any seeded `validation_key` has no registry entry.

**Files created:**
- `backend/engines/hard_constraints/__init__.py` — registry + façade
- `backend/engines/hard_constraints/types.py` — `ConstraintContext`, `ConstraintViolation`
- `backend/engines/hard_constraints/validators/teacher_overlap.py` (HC-01)
- `backend/engines/hard_constraints/validators/class_overlap.py` (HC-02)
- `backend/engines/hard_constraints/validators/room_overlap.py` (HC-03)  ← new
- `backend/engines/hard_constraints/validators/school_day_boundary.py` (HC-04)
- … 13 more, one per `validation_key` listed in `seeds/timetable_hard_constraints.py`
- `backend/tests/test_hard_constraint_registry.py`

**Failing tests (write first):**
1. `test_every_seeded_validation_key_has_registry_entry` — load `timetable_hard_constraints` seed rows, assert `set(seed_keys) == set(REGISTRY.keys())`.
2. `test_no_orphan_validators` — every key in `REGISTRY` is also in the seed.
3. `test_validate_placement_returns_list` — passes empty context, expects `[]`.
4. `test_validate_full_collects_violations_from_all_active_validators` — stub validators that always emit one violation; assert all stub violations appear.
5. `test_inactive_constraint_is_not_dispatched` — set seed row's `is_active=False` in fixture; assert that key's validator is not called.

**Acceptance:**
- All 5 tests pass.
- The 17 validator files exist; the 14 not yet implemented raise `NotImplementedError("HC-XX validator not yet implemented")` and are skipped (with a `logger.warning`) by `validate_full` — they do NOT cause crashes.

---

### Task 2 — Implement the 5 "must-be-real-now" validators

**Goal:** Replace `NotImplementedError` for the validators whose absence is a Critical/High audit finding:

| HC | validation_key | Severity | What it checks |
|---|---|---|---|
| HC-01 | `teacher_overlap` | CRITICAL | one teacher per (day, period) |
| HC-02 | `class_overlap` | CRITICAL | one class per (day, period) |
| HC-03 | `room_overlap` | CRITICAL | one room per (day, period) when `room_id` is set |
| HC-09 | `subject_weekly_periods` | HIGH | `count(class_id, subject_id) == demand.weekly_periods` |
| HC-06 | `daily_period_limit` | HIGH | per-(teacher, day) ≤ `settings.max_daily_periods` (default 6, configurable) |

**Files modified:** the 5 validator files from Task 1.

**Failing tests (write first):**
- `test_teacher_overlap_detects_collision` — 2 sessions, same teacher, same slot → 1 violation.
- `test_class_overlap_detects_collision` — same.
- `test_room_overlap_detects_collision` — 2 sessions, same room, same slot → 1 violation; null room_id → no violation.
- `test_subject_weekly_periods_under_target` — class needs 5 Math/wk, only 3 placed → 1 violation `delta=-2`.
- `test_subject_weekly_periods_over_target` — 6 placed instead of 5 → 1 violation `delta=+1`.
- `test_daily_period_limit_default_six` — teacher with 7 sessions on Sunday → 1 violation; teacher with 6 → 0.
- `test_daily_period_limit_respects_school_setting` — `settings={"max_daily_periods": 4}`, teacher with 5 → 1 violation.
- `test_room_overlap_skips_null_room` — null room_id pairs do NOT produce a violation.

**Acceptance:** 8 new tests pass. The 5 validator files are implemented as pure functions (no DB calls).

---

### Task 3 — Add `ROOM_OVERLAP`, `SUBJECT_QUOTA_VIOLATION`, `DAILY_PERIOD_LIMIT_EXCEEDED` to `ConflictType` and wire into `detect_conflicts`

**Goal:** Close F-CN-03 + F-CN-11 in the engine's existing conflict detector by delegating to the registry.

**Files modified:**
- `backend/engines/smart_scheduling_engine.py`
  - Extend `ConflictType` enum (line ~77): add `ROOM_OVERLAP`, `SUBJECT_QUOTA_VIOLATION`, `DAILY_PERIOD_LIMIT_EXCEEDED`.
  - Refactor `detect_conflicts` (lines 1410-1498) to: build a `ConstraintContext`, call `validate_full(ctx)`, map each `ConstraintViolation` → `TimetableConflict` row using a `validation_key → ConflictType` map.
  - **Delete** the inline weekly-load (`TEACHER_OVERLOAD`) check at lines 1475-1496. HC-08 (`teacher_weekly_load`, implemented in Task 4 as a full-tier validator) is the single source of truth. The `TEACHER_OVERLOAD` ConflictType value is preserved and is now emitted by the registry mapping (`teacher_weekly_load → TEACHER_OVERLOAD`). Note: this means **Task 3 cannot land before Task 4** — the DAG already serializes them correctly via Task 6.
- `backend/routes/principal_timetable_routes.py:46-72`
  - Extend `_count_real_conflicts` to read the 3 new conflict types from the same conflicts collection (not recompute) — display only.

**Failing tests (write first):**
1. `test_detect_conflicts_emits_room_overlap` — generate fixtures with 2 sessions sharing a room → at least one `TimetableConflict` of type `ROOM_OVERLAP` is persisted.
2. `test_detect_conflicts_emits_subject_quota_violation` — class missing weekly periods → `SUBJECT_QUOTA_VIOLATION` row written.
3. `test_detect_conflicts_emits_daily_period_limit` — teacher with 7 sessions in one day → `DAILY_PERIOD_LIMIT_EXCEEDED` row.
4. `test_count_real_conflicts_includes_new_types` — the principal `summary` endpoint returns non-zero `room_conflicts` / `quota_violations` when present.

**Acceptance:** 4 new tests pass. The conflict-row schema gains 3 new `conflict_type` values consumed by the principal UI's count.

---

### Task 4 — Implement remaining 12 validators (incl. HC-14 schedule_completeness)

**Goal:** Implement every validator NOT covered by Task 2, so that no `NotImplementedError` remains in the registry after this task lands.

| HC | validation_key | Tier | Severity in this batch | Notes |
|---|---|---|---|---|
| HC-04 | `school_day_boundary` | placement | HIGH | session.period ∈ active period range |
| HC-05 | `non_teaching_period` | placement | HIGH | candidate slot is not `is_break` / `is_prayer` |
| HC-07 | `working_days` | placement | HIGH | session.day ∈ school working days |
| HC-08 | `teacher_weekly_load` | full | HIGH | per-teacher weekly count ≤ resource.weekly_load. **Replaces** the inline `TEACHER_OVERLOAD` loop in `detect_conflicts` (single source of truth). |
| HC-10 | `no_consecutive_subject` | placement | MEDIUM | same (class, subject) not in consecutive teaching periods on same day; respects HC-10 `can_disable` override flag (see F-CN-10 — out of batch scope, but the validator MUST honour the flag if present in `ctx.settings.hard_constraint_overrides[hc_code]`) |
| HC-11 | `teacher_subject_match` | placement | MEDIUM (warning) | teacher qualified for subject. Demoted to warning because data is sparsely populated; upgrade in future batch. |
| HC-12 | `teacher_class_assignment` | placement | HIGH | teacher is in `teacher_assignments` for that (class, subject) |
| HC-13 | `resource_single_booking` | placement | HIGH | non-room resources (lab equipment, projector, etc.) booked at most once per slot |
| HC-14 | `schedule_completeness` | full | CRITICAL | every (class, subject) has all `weekly_periods` placed AND no empty slot between first and last placed period of that day for that class. **Replaces** the existing publish-gate completeness check (single source of truth — Task 5 deletes the inline version). |
| HC-15 | `academic_structure_match` | full | MEDIUM (warning) | placed subject ∈ class.curriculum.subjects; demoted to warning, same data-quality reason as HC-11. |
| HC-16 | `entity_integrity` | placement | CRITICAL | every FK in the session row resolves in `ctx.resources` (no orphan teacher_id / class_id / subject_id / room_id). |
| HC-17 | `block_publish_on_conflict` | full | meta | NOT a normal validator — implemented as the publish-gate decision rule (`can_publish = no CRITICAL/HIGH violations`). The registry entry is a documented marker that maps to the publish-gate logic in Task 5; the validator function itself returns `[]`. |

**Important quality bar:** every validator MUST be a pure function ≤ 60 lines. If a check requires DB access (e.g. teacher.qualifications for HC-11/HC-15), the relevant data is loaded **into the `ConstraintContext.resources` lookup once**, by the engine, before the registry runs — validators never touch the DB.

**Tier-split rationale:** placement-tier validators are O(1) per candidate. `teacher_weekly_load` (HC-08), `subject_weekly_periods` (HC-09 from Task 2), and `schedule_completeness` (HC-14) are inherently whole-grid (need final counts) and run only in `validate_full`. `academic_structure_match` (HC-15) is whole-grid because it cross-checks against the class's full curriculum manifest. Everything else is per-candidate-checkable and should fail fast at placement.

**Failing tests (write first):** one happy-path + one violation case per validator = **24 tests minimum** (12 validators × 2 cases; HC-17 marker validator gets 1 test asserting it returns `[]`). Use realistic fixtures.

**Acceptance:** 24+ new tests pass. No `NotImplementedError` remains in the registry. The Task 1 guard test `test_every_seeded_validation_key_has_registry_entry` continues to pass.

---

### Task 5 — Replace publish-gate hand-rolled chain AND enforce on the publish action itself

**Goal:** Close F-CN-02 robustly. The audit explicitly calls out HC-17 ("block publish on conflict") — meaning the *publish endpoint*, not just the *validate-before-publish endpoint*, must reject violating timetables. Today a client can call publish directly and bypass `validate_before_publish` entirely.

**Two changes, not one:**

**5a. Rewire `validate_before_publish`** (`backend/routes/principal_timetable_routes.py:960-1097`) to use the registry:

```python
ctx = await _build_constraint_context(school_id, version_id, db)
violations = validate_full(ctx)
validation_errors = [
    {
        "code": v.code,
        "validation_key": v.validation_key,
        "severity": v.severity.value,
        "message_en": v.message_en,
        "message_ar": v.message_ar,
        "refs": v.refs,
    }
    for v in violations if v.severity in (ConflictSeverity.CRITICAL, ConflictSeverity.HIGH)
]
warnings = [... for v if v.severity == ConflictSeverity.MEDIUM]
can_publish = len(validation_errors) == 0
```

The hand-rolled `if teacher_overlap / class_overlap / schedule_completeness` chain is **deleted**. (HC-14 from Task 4 now provides the schedule_completeness check; HC-01/HC-02 from Task 2 provide the overlap checks.)

**5b. Enforce on the publish action itself.** `POST /principal/timetable/version/{version_id}/publish` (search `principal_timetable_routes.py` for the `publish_version` handler) MUST run the **same** `validate_full(ctx)` and **abort with HTTP 409** if any CRITICAL/HIGH violation is present, regardless of whether the client called `validate_before_publish` first. The legacy `POST /smart-scheduling/timetable/{timetable_id}/publish` endpoint (`scheduling_smart_engine_routes.py`) gets the same guard. This implements HC-17 in code, not just in the seed text.

A shared helper `await assert_publishable(version_id, school_id, db)` lives in a new module `backend/engines/hard_constraints/publish_guard.py` and is called by both publish endpoints.

**Files modified:**
- `backend/routes/principal_timetable_routes.py:960-1097` (validate_before_publish refactor)
- `backend/routes/principal_timetable_routes.py` (publish_version handler — add guard call)
- `backend/routes/scheduling_smart_engine_routes.py` (smart-engine publish — add guard call)
- `backend/engines/hard_constraints/publish_guard.py` (new shared helper)

**Failing tests (write first):**
1. `test_publish_gate_blocks_on_room_overlap` — fixture with 1 room conflict → `can_publish=False`, `validation_errors[].validation_key=="room_overlap"`.
2. `test_publish_gate_blocks_on_subject_quota_shortfall` — class missing 2 Math/wk → blocked.
3. `test_publish_gate_blocks_on_daily_limit_exceeded` — teacher with 7 sessions/day → blocked.
4. `test_publish_gate_blocks_on_schedule_incomplete` — class missing whole subject (HC-14) → blocked.
5. `test_publish_gate_passes_clean_timetable` — handcrafted clean fixture → `can_publish=True`, `validation_errors==[]`.
6. `test_publish_gate_existing_teacher_overlap_still_blocks` — regression: prior behaviour preserved.
7. `test_publish_gate_response_carries_validation_keys` — every error carries `validation_key` (Batch 9 i18n foundation).
8. **`test_publish_endpoint_rejects_violating_version_without_pre_validate`** — call `POST /principal/timetable/version/{vid}/publish` directly on a version that has a room conflict → expect `409`, body lists the violating `validation_key`s. Asserts the publish action is independently guarded.
9. **`test_smart_engine_publish_endpoint_rejects_violating_timetable`** — same for `POST /smart-scheduling/timetable/{tid}/publish`.

**Acceptance:** 9 new tests pass. The function body of `validate_before_publish` shrinks by ~80 lines. Both publish endpoints share `assert_publishable`.

---

### Task 6 — Wire registry into the engine's placement loop

**Goal:** Close F-CN-01 + F-EN-08 in the generator. The two-key `if rule_key in {"no_first_period","no_last_period"}` chain (smart_scheduling_engine.py:995-1005) is replaced with `validate_placement(ctx, candidate)`. If any returned violation is `CRITICAL`, the candidate is rejected.

**Files modified:** `backend/engines/smart_scheduling_engine.py` — the placement loop (lines 849-1225) and the constraint-load section (lines 1926-1946).

**Performance guard:** `validate_placement` is called O(D · P · T) times, so each placement-tier validator must be O(1) per call (no scans of the whole sessions list). The tier split is the one defined in Task 4's table — placement tier covers HC-01/02/03/04/05/06/07/10/11/12/13/16; full tier covers HC-08/09/14/15/17. The split is encoded by a `tier: Literal["placement","full"]` attribute on each validator's metadata. Placement-tier validators receive a `candidate` argument (the single session about to be placed) plus the partial grid as fast lookup indexes; they MUST NOT iterate the whole grid.

**Migration of the existing `no_first_period` / `no_last_period` literal-rule_key checks (regression-prevention):** these are not in the seed `validation_key` list — they are *school-level* rule_keys stored on `school_constraints` rows. Today they are honoured only by the inline check. Before deleting the inline check, this task adds:

1. A new placement-tier validator file `backend/engines/hard_constraints/validators/school_period_bans.py` that reads `ctx.settings.school_period_bans` (a list of `{rule_key, subject_id?, period_number}` records derived from `school_constraints`) and emits violations when a candidate places a banned subject in a banned period.
2. A pure-data adapter `_school_constraints_to_period_bans(rows)` that converts `school_constraints` rows with `rule_key in {"no_first_period","no_last_period","no_period_n"}` into the structured `school_period_bans` list, populated into `ctx.settings` by `_build_constraint_context`.
3. A regression test (item 3 below) proving an active "no Math first period" school constraint still blocks Math-in-period-1 placement after the inline chain is removed.

**Failing tests (write first):**
1. `test_engine_rejects_candidate_violating_active_hard_constraint` — active HC with `validation_key="some_key"` whose validator returns a violation → engine moves to next candidate.
2. `test_engine_skips_inactive_hard_constraint` — same fixture but `is_active=False` → candidate accepted.
3. **`test_engine_still_honours_school_no_first_period_constraint`** — regression. School has `school_constraints` row `{rule_key: "no_first_period", subject_id: math_id, is_active: True}` → engine never places Math in period 1.
4. `test_engine_no_longer_uses_inline_no_first_period_chain` — grep guard: the literal string comparisons `rule_key == "no_first_period"` and `rule_key == "no_last_period"` no longer appear in `smart_scheduling_engine.py` (the strings still appear as data keys in the adapter, which is fine).
5. `test_full_generation_still_succeeds_on_clean_fixture` — end-to-end: small school, generate, expect a non-empty timetable and zero CRITICAL conflicts.

**Performance baseline:** before changing any code, this task records `time` for `generate_full_timetable` against the clean fixture (3 runs, median). After changes, the same fixture must complete within **+25%** of the baseline (looser than my earlier ±10% — registry dispatch has overhead that's worth absorbing for correctness).

**Acceptance:** 5 new tests pass. The placement loop is shorter, not longer. End-to-end generation time on the clean fixture stays within +25% of the pre-change baseline.

---

### Task 7 — Pre-generation infeasibility report (scoped F-EN-09)

**Goal:** Surface `_analyze_capacity_issues` output **before** generation, so users fix data first.

**Deterministic gating criteria (so `blocks_generation` cannot drift into a no-op):** the report blocks generation iff ANY of these conditions hold (all computed from data already analysed by `_analyze_capacity_issues`):

| Code | Condition | Why it blocks |
|---|---|---|
| `INF-01` | `total_demand_periods > total_available_teaching_slots` (sum across all classes) | Mathematically impossible to fit. |
| `INF-02` | Any class has `class_demand_periods > class_available_slots` (per-class capacity) | That class cannot be fully scheduled. |
| `INF-03` | Any subject has `weekly_periods_demanded > sum(weekly_load of qualified teachers)` | No teacher capacity to cover it. |
| `INF-04` | Any required resource (room marked `subject_must_use_room`) has fewer slots than demanded | Hard infeasibility. |
| `INF-05` | School has zero `time_slots` rows OR zero teaching periods configured | Generation has nothing to fill. |

Anything else (warnings, "tight but feasible", soft-constraint risks) is reported as an `advisory` issue and does NOT block.

**Schema:**
```python
class InfeasibilityIssue(BaseModel):
    code: str                       # "INF-01" .. "INF-05" or "ADV-XX"
    severity: Literal["blocker","advisory"]
    message_en: str
    message_ar: str
    refs: Dict[str, Any]            # offending class_id / subject_id / numeric counts

class InfeasibilityReport(BaseModel):
    blocks_generation: bool          # True iff any issue.severity == "blocker"
    issues: List[InfeasibilityIssue]
    computed_at: datetime
```

**Files modified:**
- `backend/engines/smart_scheduling_engine.py` — promote `_analyze_capacity_issues` (line 1304) to a public method `build_infeasibility_report(school_id) -> InfeasibilityReport`. The method MUST classify each issue into INF-01..INF-05 (blockers) or ADV-* (advisories).
- `backend/routes/scheduling_smart_engine_routes.py` — extend `GET /smart-scheduling/validate/{school_id}` and `GET /smart-scheduling/pre-check/{school_id}` to include `infeasibility_report` in the response.
- `backend/routes/scheduling_smart_engine_routes.py` — `POST /smart-scheduling/generate/{school_id}` and `POST /smart-scheduling/generate-smart` MUST return HTTP 422 with the report when `report.blocks_generation == True`, instead of starting a doomed run.

**Failing tests (write first):**
1. `test_pre_check_returns_infeasibility_report_when_total_demand_exceeds_slots` — INF-01 fixture → blocker present, `blocks_generation=True`.
2. `test_pre_check_returns_blocker_for_per_class_capacity_overrun` — INF-02 fixture.
3. `test_pre_check_returns_blocker_for_no_time_slots` — INF-05 fixture.
4. `test_generate_returns_422_when_blocker_present` — INF-01 fixture → POST generate returns 422 with the report body and never invokes `generate_full_timetable`.
5. `test_pre_check_clean_when_capacity_ok` — clean fixture → `infeasibility_report.issues == []`, `blocks_generation=False`.
6. `test_advisory_issue_does_not_block_generation` — fixture with a tight-but-feasible class (advisory) → `blocks_generation=False`, generation proceeds.

**Acceptance:** 6 new tests pass. The blocker classification is deterministic and covered by tests; "partial remediation" of F-EN-09 means infeasibility is now caught BEFORE generation even though the placement algorithm itself is unchanged.

---

### Task 8 — Audit annotation + final sweep

**Goal:** Annotate the 6 audit findings as remediated; run the full Batch-1 + Batch-2 test suites; restart the Backend API workflow and verify clean startup.

**Steps:**
1. Append `- **Status:** ✅ Remediated 2026-04-17 (Batch 2 plan: docs/superpowers/plans/2026-04-17-timetable-remediation-batch2.md)` after the `Effort:` line of:
   - F-CN-01 (line 282)
   - F-CN-02 (line 290)
   - F-CN-03 (line 298)
   - F-CN-11 (line 363)
   - F-EN-08 (line 449)
   - F-EN-09 (line 457) — annotate as **Partially Remediated** (infeasibility report only; CSP rewrite deferred).
2. Run `python -m pytest backend/tests/test_tenant_scope_helper.py backend/tests/test_timetable_tenant_isolation.py backend/tests/test_hard_constraint_registry.py backend/tests/test_publish_gate_registry.py backend/tests/test_engine_registry_dispatch.py backend/tests/test_pre_check_infeasibility.py` from project root → expect all green.
3. Restart `Backend API` workflow; confirm no import errors in logs.
4. Architect review of the full Batch 2 diff using the same prompt template as Batch 1 (verify no critical gaps remain open, no regressions in Batch 1 coverage).

---

## 4. Test summary

| Task | New tests | Cumulative |
|---|---|---|
| 1 | 5  | 5 |
| 2 | 8  | 13 |
| 3 | 4  | 17 |
| 4 | 25 | 42 |
| 5 | 9  | 51 |
| 6 | 5  | 56 |
| 7 | 6  | 62 |
| **Batch 2 total** | **62** | **62** |

Combined with Batch 1's 56 tests → **118 timetable tests** post-Batch 2.

---

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Performance regression in `validate_placement` (called per candidate) | Medium | Tier-split (placement vs full); benchmark in Task 6; abort & redesign if > 1.5× baseline. |
| Validators silently disagree with the inline checks they replace | Medium | Task 6 keeps the regression test `test_publish_gate_existing_teacher_overlap_still_blocks`; Task 5 includes a clean-timetable positive control. |
| `_build_constraint_context` requires DB roundtrips that hurt publish-gate latency | Low | Cache resources in a single batched fetch per call; same pattern already used in `_count_real_conflicts`. |
| HC-11 / HC-15 false-positives because `teacher.qualifications` is sparsely populated | High | This batch demotes HC-11/HC-15 violations to `MEDIUM` (warnings, not blockers). Data-quality cleanup is a future batch. |
| Frontend doesn't yet know `room_overlap` / `quota_violation` keys | Low | Task 3 adds them as new conflict types — frontend will display them under a generic "Other conflict" until Batch 9 i18n lands. Acceptable. |
| Publish endpoint bypassed validate_before_publish (architect-flagged) | Closed | Task 5b adds `assert_publishable` directly in both publish handlers; tests 5.8 and 5.9 prove direct publish calls are guarded. |
| HC-14 schedule_completeness regression (architect-flagged) | Closed | HC-14 is now an explicit row in Task 4's matrix and the inline publish-gate check is only deleted AFTER HC-14 validator + tests are green. |
| Existing `no_first_period`/`no_last_period` school constraints silently dropped (architect-flagged) | Closed | Task 6 adds the `school_period_bans` adapter + validator + regression test BEFORE removing the inline literal-key chain. |
| `blocks_generation` drifts into a no-op (architect-flagged) | Closed | Task 7 defines INF-01..INF-05 as the closed set of blockers, each with its own failing test. |
| Architect review uncovers gaps (as in Batch 1) | Medium | Run a pre-implementation architect review of THIS plan (already done) and a post-implementation review after Task 8. |

---

## 6. Definition of Done for Batch 2

- All 52 new tests + all 56 Batch 1 tests pass from project root.
- `validate_before_publish` no longer contains the 3-key inline `if`-chain.
- `smart_scheduling_engine.py` placement loop no longer contains the literal `"no_first_period"` / `"no_last_period"` string comparisons.
- `ConflictType` enum has `ROOM_OVERLAP`, `SUBJECT_QUOTA_VIOLATION`, `DAILY_PERIOD_LIMIT_EXCEEDED`.
- `_count_real_conflicts` sums all 6 conflict types; principal summary endpoint reflects them.
- `GET /smart-scheduling/pre-check/{school_id}` returns an `infeasibility_report` field.
- `POST /smart-scheduling/generate*` returns 422 instead of starting a doomed run when `infeasibility_report.blocks_generation == True`.
- Audit findings F-CN-01, F-CN-02, F-CN-03, F-CN-11, F-EN-08 annotated **Remediated**; F-EN-09 annotated **Partially Remediated** with the deferred CSP scope cross-referenced to a future plan stub.
- Backend API workflow restarts cleanly; architect review reports no Critical / High gaps remaining in the targeted findings.
