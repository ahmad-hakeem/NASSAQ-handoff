# Hakeem Engine Audit Report

**Date:** 2026-05-03
**Spec:** `docs/superpowers/specs/2026-05-03-hakeem-engine-audit-design.md`

## 1. Scope & method

Read `backend/engines/smart_scheduling_engine.py` (`generate_timetable` at line 2791, placement loop ~1540–1900, `_log_run` at 3351), `backend/routes/scheduling_smart_engine_routes.py` (`smart_generate_timetable` at line 118, `_assemble_hakim_context_payload` at lines 164–349), and every validator file in `backend/engines/hard_constraints/validators/` plus the registry wiring in `backend/engines/hard_constraints/__init__.py`. Did not read frontend code or the soft-scoring tuning history — out of scope.

## 2. Data hydration verification

| Source | Loaded? | File:Line | Silent fallback? | Notes |
|---|---|---|---|---|
| `school_settings` (periods_per_day, working_days) | ✅ | `scheduling_smart_engine_routes.py:182` | Warning at `:328` if missing; engine then falls back to defaults | Acceptable — warning is logged, not silent. |
| `time_slots` | ✅ | `scheduling_smart_engine_routes.py:183` | If empty, `has_timing` check at `:321` fails and generation is blocked by INF-05 | Hard-fails, not silent. |
| `teacher_assignments` (subject + weekly quota) | ✅ | `scheduling_smart_engine_routes.py:185` | If empty, engine refuses to generate at `smart_scheduling_engine.py:2846` | Hard-fails, not silent. |
| `teacher_class_assignments` | ✅ | Auto-populated via `_auto_populate_teacher_class_assignments` at `smart_scheduling_engine.py:2831` before payload use | None — always populated | OK |
| `unavailability` (entity_type='teacher') | ✅ | `scheduling_smart_engine_routes.py:192` | Defaults to `[]` if no records | OK — empty list correctly means "no unavailability". |
| `timetable_hard_constraints` | ✅ | `scheduling_smart_engine_routes.py:206` | Registry falls back to direct DB query at `smart_scheduling_engine.py:2992` if payload missing | OK |
| `timetable_soft_constraints` | ✅ | `scheduling_smart_engine_routes.py:211–237` | System defaults are merged with per-school overrides | OK — merge is intentional. |

**Verdict:** Hydration is complete. No silent fallback masks missing required data.

## 3. Hard-constraint matrix

| ID | Constraint | File:Line of check | Observed behavior | Verdict | Recommended fix |
|---|---|---|---|---|---|
| A1 | Teacher double-booking | `smart_scheduling_engine.py:1685` | `if teacher_id in teacher_grid[day][period]: continue` | ✅ Enforced | Enforced — no fix needed |
| A2 | Class double-booking | `smart_scheduling_engine.py:1667` | `if class_id in grid[day][period]: continue` | ✅ Enforced | Enforced — no fix needed |
| B  | Teacher unavailability honored | `smart_scheduling_engine.py:1679` | `if period not in resource.availability.get(day, []): continue` | ✅ Enforced | Enforced — no fix needed |
| C  | Boundary (active_days × periods_per_day) | `validators/school_day_boundary.py:22`, invoked via `_registry_rejects` at `smart_scheduling_engine.py:1729` | `if period not in allowed: reject` | ✅ Enforced | Enforced — no fix needed |
| D  | Teacher weekly quota | `smart_scheduling_engine.py:1690` | `if usage >= resource.weekly_load: continue` | ✅ Enforced | Enforced — no fix needed |
| E  | Max consecutive periods/teacher | `smart_scheduling_engine.py:1698` | `if self._would_exceed_max_consecutive(...): continue` | ✅ Enforced | Enforced — no fix needed |
| F  | Max periods per day/teacher | `validators/daily_period_limit.py:55`, invoked via `_registry_rejects` | `if count > limit: reject` (default 6) | ✅ Enforced | Enforced — no fix needed |

## 4. Soft-constraint / fairness (G)

| ID | Constraint | File:Line | Observed behavior | Verdict |
|---|---|---|---|---|
| G  | Distribution fairness across days | `smart_scheduling_engine.py:2593` (`_apply_soft_constraint_scoring`); fairness deduction at `:2668` | Starts at `score = 100`. Deducts `10 * (weight / 10.0)` if a subject appears ≥ 2 times on the same day. Other soft penalties: minimize_teacher_gaps, balanced_daily_teacher_load, hard_subjects_early, no_consecutive_same_subject. | ✅ Enforced (best-effort by design) |

## 5. Logging & summary gap analysis

**Already produced today:**
- `timetable_runs` row per generation: `id`, `school_id`, `academic_year_id`, `term_id`, `run_type`, `target_class_ids`, `status`, `started_at`, `finished_at`, `created_by`, `completion_percentage`, `conflicts_count`, `unscheduled_count`, `notes` (refs `smart_scheduling_engine.py:2910, 3116`).
- `timetable_run_logs` rows via `_log_run` at `:3351`: `id`, `run_id`, `log_level`, `message`, `context` JSONB, `created_at`.
- `timetable_unscheduled_demands` rows at `:1862`: `id`, `run_id`, `school_id`, `class_id`, `grade_id`, `subject_id`, `required_periods`, `scheduled_periods`, `remaining_periods`, `reason_ar`, `reason_en`, `reason_code`.

**Delta added by `generation_summary`:**
1. **Aggregate rejection counters** in one place — today these are scattered across `timetable_unscheduled_demands.reason_code` rows; the summary collapses them into a single `rejections_by_reason` dict so principals/engineers don't have to GROUP BY.
2. **Per-teacher distribution** (`fairness.per_teacher` with `by_day`) — today this is implicit in `schedule_sessions`; the summary surfaces it on the run row directly.
3. **`constraints_evaluated`** explicit list — proves to consumers which constraints were actually checked during this run.
4. **`elapsed_ms`** — already derivable from `finished_at - started_at` but inconvenient.
5. **`placement_rate`** — already derivable from `completion_percentage` but with explicit semantics (`null` when `required == 0`).

The summary is additive instrumentation, not a replacement for any existing log.

## 6. Recommended fix list

| # | Severity | Constraint | Fix | Estimated touch |
|---|---|---|---|---|
| — | — | — | **No gaps found.** All hard constraints A–F are enforced and fairness (G) is computed. No code fixes are required from the audit itself. | 0 LOC |

**Conclusion:** The Hakeem engine already enforces every hard constraint listed in the brief. Implementation can skip Task 2 (gap fixes) and proceed directly to Tasks 3–8 (migration → helper → counter wiring → summary build → API wiring → verification).

The single remaining value to deliver is the `generation_summary` itself — and it is purely additive instrumentation, not a fix.

## Appendix: Placement-loop rejection sites (for counter wiring in Task 5)

| # | File:Line | Trigger | Maps to `RejectionCounters` field |
|---|---|---|---|
| 1 | `smart_scheduling_engine.py:1619` | `continue` if `not working_days` | (no field — pre-loop guard, skip) |
| 2 | `smart_scheduling_engine.py:1638` | `continue` if `not suitable_teachers` | `no_eligible_teacher` |
| 3 | `smart_scheduling_engine.py:1658` | `break` if `remaining <= 0` | (success exit, skip) |
| 4 | `smart_scheduling_engine.py:1671` | `continue` if class busy | `class_busy` |
| 5 | `smart_scheduling_engine.py:1681` | `continue` if teacher unavailable | `teacher_unavailable` |
| 6 | `smart_scheduling_engine.py:1687` | `continue` if teacher busy | `teacher_busy` |
| 7 | `smart_scheduling_engine.py:1692` | `continue` if `usage >= weekly_load` | `weekly_quota_exceeded` |
| 8 | `smart_scheduling_engine.py:1702` | `continue` if `_would_exceed_max_consecutive` | `max_consecutive_exceeded` |
| 9 | `smart_scheduling_engine.py:1737` | `continue` if `_registry_rejects` (covers boundary, daily_period_limit, etc.) | `constraint_registry_rejected` (and `max_per_day_exceeded` is a subset of these — see note below) |

**Note on `max_per_day_exceeded`:** Constraint F is enforced via the registry at site #9 above (`validators/daily_period_limit.py`). To populate the dedicated `max_per_day_exceeded` counter separately from the generic `constraint_registry_rejected` bucket, Task 5 will need `_registry_rejects` to return *which* validator rejected the placement, not just a boolean. This is a small, contained change inside `_registry_rejects` and is part of Task 5 scope, not a hard-constraint fix.
