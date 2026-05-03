# Hakeem Auto-Generation Engine — Constraint Audit & Generation Summary

**Date:** 2026-05-03
**Owner:** Backend / AI Engine
**Scope:** Audit the Hakeem auto-generation engine (`/api/smart-scheduling/generate/{school_id}`) for hard-constraint enforcement, fix any real gaps found, and add a rich, persisted `generation_summary` object to every run.

---

## 1. Goals

1. Systematically verify that every hard constraint listed in the brief is actually enforced before a class is placed in the matrix.
2. Document the verification in a per-constraint matrix that maps brief → code → verdict → recommended fix.
3. Fix real gaps that the audit reveals (not cosmetic refactors).
4. Add a `generation_summary` JSON object to the generation response and persist it on `timetable_runs` so principals and engineers can review what happened during a run.

## 2. Non-Goals

- No frontend UI to display the new summary. That is a separate task if requested.
- No changes to the soft-constraint scoring weights. Fairness (G) is verified, not re-tuned.
- No new constraint types beyond what the brief lists.
- No refactor of the placement loop's overall architecture. Targeted fixes only.

## 3. Method

The audit reads the existing engine, not a blank page. Specifically:

- `backend/routes/scheduling_smart_engine_routes.py` — endpoint, payload assembly.
- `backend/engines/smart_scheduling_engine.py` — `generate_timetable` and the placement loop.
- `backend/engines/hard_constraints/` — registry-based hard-constraint validators.
- Database tables touched during a run: `school_settings`, `time_slots`, `teacher_assignments`, `teacher_class_assignments`, `unavailability`, `timetable_hard_constraints`, `timetable_soft_constraints`, `timetable_runs`, `timetable_unscheduled_demands`, `timetable_run_logs`.

For each constraint the audit records: **file:line** of the check, **observed behavior** (including any silent fallback to defaults), a **verdict** (✅ enforced / ⚠ weak / ❌ missing), and a **recommended fix** if the verdict is not ✅.

## 4. Audit Report Structure

The audit report itself is a separate document produced as the first deliverable of the implementation phase. Its structure is fixed here so the implementation plan can reference it:

1. **Scope & method** — what was read, what was not.
2. **Data hydration verification** — confirm `context_payload` actually loads timing, teacher workload, unavailability, and constraints. Flag any silent fallbacks (defaults masking missing data).
3. **Hard-constraint matrix** — one row per constraint A–F (see §5).
4. **Soft-constraint / fairness matrix** — constraint G, best-effort verdicts.
5. **Logging & summary gap analysis** — what `timetable_runs` / `timetable_unscheduled_demands` already give us vs. what the new `generation_summary` adds.
6. **Recommended fix list** — ordered Critical / Important / Nice-to-have.

## 5. Constraints In Scope

Must-verify-and-fix (hard):

- **A.** Double-booking — teacher in two classes same period; class with two teachers same period.
- **B.** Unavailability — teacher unavailability records honored (`unavailability` table, entity_type='teacher').
- **C.** Boundary — no assignments outside `active_days × periods_per_day` defined in `school_settings` / `time_slots`.
- **D.** Teacher weekly quota — teacher never exceeds the weekly periods implied by their `teacher_assignments`.
- **E.** Max consecutive periods per teacher.
- **F.** Max periods per day per teacher.

Best-effort (soft):

- **G.** Fairness / load distribution across days. Verified via the existing `_apply_soft_constraint_scoring` path; no weight changes.

## 6. `generation_summary` Schema

Returned in the `/api/smart-scheduling/generate/{school_id}` response and persisted in a new nullable `timetable_runs.generation_summary` JSONB column.

```json
{
  "schema_version": 1,
  "totals": {
    "required": 240,
    "placed": 235,
    "failed": 5,
    "placement_rate": 0.979
  },
  "elapsed_ms": 1842,
  "fairness": {
    "overall_score": 87,
    "per_teacher": [
      {
        "teacher_id": "...",
        "name": "...",
        "total_periods": 18,
        "by_day": { "sun": 4, "mon": 3, "tue": 4, "wed": 4, "thu": 3 },
        "max_consecutive": 3,
        "gaps": 1
      }
    ]
  },
  "rejections_by_reason": {
    "teacher_busy": 12,
    "class_busy": 4,
    "teacher_unavailable": 3,
    "max_consecutive_exceeded": 5,
    "max_per_day_exceeded": 2,
    "weekly_quota_exceeded": 1,
    "constraint_registry_rejected": 7,
    "no_eligible_teacher": 0
  },
  "constraints_evaluated": [
    "double_booking_teacher",
    "double_booking_class",
    "unavailability",
    "boundary",
    "weekly_quota",
    "max_consecutive_per_day",
    "max_periods_per_day"
  ],
  "unplaced_demands": [
    {
      "class_id": "...",
      "subject_id": "...",
      "remaining": 2,
      "primary_reason": "teacher_unavailable"
    }
  ]
}
```

### Rules for the schema

- `schema_version` is required so future changes are non-breaking for consumers.
- All counters in `rejections_by_reason` default to `0`, never absent. This makes the shape stable for the frontend and for analytics queries.
- `fairness.per_teacher` includes only teachers who received at least one placement attempt during this run (not the entire roster).
- `unplaced_demands` is summarized (one row per `class_id × subject_id`), not one row per failed slot, to keep the payload bounded.
- `placement_rate` is `placed / required`, rounded to three decimals; defined as `null` when `required == 0`.
- The summary is built from counters maintained during the existing placement loop. No second pass over the matrix.

## 7. Persistence

- New Alembic migration adds a nullable `generation_summary JSONB` column to `timetable_runs`.
- Old rows return `null` for the column; the API response simply omits the field for runs that predate this change, or returns `null` — frontend treats both as "no summary available".
- No backfill. Historical runs do not get retroactive summaries.

## 8. API Contract Change

`POST /api/smart-scheduling/generate/{school_id}` response gains one top-level field:

```json
{
  "...existing fields...": "...",
  "generation_summary": { /* schema from §6, or null */ }
}
```

This is additive. Existing consumers are not affected.

## 9. Implementation Phases

The implementation plan (produced by the writing-plans skill) will sequence roughly as:

1. **Audit pass** — produce the audit report document. No code changes. User reviews and approves the fix list.
2. **Gap fixes** — apply only the fixes the user approved from the audit report. Each fix is its own commit with a short rationale.
3. **Summary instrumentation** — add counters in the placement loop (cheap; piggybacks on existing rejection logging).
4. **Migration + persistence** — add the JSONB column, write the summary to it on every run.
5. **Response wiring** — return the summary in the API response.
6. **Manual verification** — run a generation against a real school's data, eyeball the summary, confirm counters add up to the placement deltas in `timetable_unscheduled_demands`.

## 10. Risks

- **False-positive gaps.** A "missing" constraint check may actually be enforced elsewhere (e.g., the `HardConstraintRegistry`). Mitigation: the audit report goes to the user *before* any fix is written; the user picks which gaps to fix.
- **Counter drift.** New counters could disagree with `timetable_unscheduled_demands` if they're updated in different code paths. Mitigation: counters are incremented at the same call sites that write to `timetable_unscheduled_demands`, not in parallel paths.
- **Payload size.** `fairness.per_teacher` and `unplaced_demands` could grow large for big schools. Mitigation: `per_teacher` is bounded by teachers active in the run, `unplaced_demands` is aggregated by `class_id × subject_id`.

## 11. Success Criteria

- Audit report exists at `docs/superpowers/specs/2026-05-03-hakeem-engine-audit-report.md` and covers every constraint A–G with a verdict and (where needed) a recommended fix.
- Every fix the user approved from the audit is applied and accompanied by a one-line rationale in the commit message.
- A live generation run returns a `generation_summary` matching the schema in §6, with `totals.placed + totals.failed == totals.required`, and the persisted column on `timetable_runs` matches the response.
- No regression in existing `timetable_runs` / `timetable_unscheduled_demands` behavior; old API consumers continue to work.
