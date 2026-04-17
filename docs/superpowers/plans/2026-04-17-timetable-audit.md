# Timetable Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a single comprehensive audit report of the school timetable subsystem covering data model, seeds, constraints, generation engine, API routes, frontend, end-to-end flow, and cross-cutting concerns, with every finding ranked by severity and tied to file locations.

**Architecture:** Read-only investigative work. Each task inspects one layer of the system, records findings directly into the report file, and commits. The report is built up incrementally, layer by layer, with a final pass that produces the executive summary, top-10, and recommended next steps from the accumulated findings.

**Tech Stack:** Markdown report only. Investigation tools: file reading, grep, code search. No code, schema, or data is changed.

**Spec:** `docs/superpowers/specs/2026-04-17-timetable-audit-design.md`

---

## Conventions used by every task

**Finding format** (used in every layer section):

```markdown
#### F-<LAYER>-<NN> — <Title>
- **Severity:** Critical | High | Medium | Low
- **Location:** `path/to/file.py:LINE` (or line range)
- **Description:** What is wrong / surprising / missing.
- **Why it matters:** Concrete user / data / security impact.
- **Recommended fix:** Specific change to make.
- **Effort:** S | M | L
```

`<LAYER>` is `DM` (data model), `SD` (seed data), `CN` (constraints), `EN` (engine), `API`, `FE` (frontend), `E2E`, `XC` (cross-cutting). `<NN>` is a zero-padded sequential number per layer (01, 02, ...).

**Severity rules:**
- **Critical** — data loss, generation broken, security/RBAC hole, multi-tenant leak.
- **High** — feature broken or unusable for a real school.
- **Medium** — works but wrong, fragile, or poor UX.
- **Low** — cleanup, polish, dead code, nits.

**If a layer has no findings:** write `_No issues found._` under its findings list rather than leaving it empty.

**Commit message format:** `audit(timetable): <layer> findings` (e.g. `audit(timetable): data model findings`).

**Read-only rule:** No file outside `docs/audits/` and `docs/superpowers/{specs,plans}/` may be modified by any task in this plan.

---

## Task 1: Bootstrap report skeleton

**Files:**
- Create: `docs/audits/2026-04-17-timetable-audit.md`

- [ ] **Step 1: Create the report skeleton**

Write the following content to `docs/audits/2026-04-17-timetable-audit.md`:

```markdown
# Timetable Subsystem Audit

**Date:** 2026-04-17
**Spec:** `docs/superpowers/specs/2026-04-17-timetable-audit-design.md`
**Type:** Read-only audit. No code or data was modified.

## Severity legend
- **Critical** — data loss, generation broken, security/RBAC hole, multi-tenant leak.
- **High** — feature broken or unusable for a real school.
- **Medium** — works but wrong, fragile, or poor UX.
- **Low** — cleanup, polish, dead code, nits.

## Finding ID convention
`F-<LAYER>-<NN>` where layer is one of DM, SD, CN, EN, API, FE, E2E, XC.

---

## 1. Executive summary

_To be written in Task 10 once all findings are collected._

## 2. Top 10 critical / high findings

_To be written in Task 10._

## 3. Layer findings

### 3.1 Data model & migrations
_Files inspected:_ _filled by Task 2._

_Findings:_

### 3.2 Seed & reference data
_Files inspected:_ _filled by Task 3._

_Findings:_

### 3.3 Constraints (hard + soft)
_Files inspected:_ _filled by Task 4._

_Findings:_

### 3.4 Generation engine
_Files inspected:_ _filled by Task 5._

_Findings:_

### 3.5 API routes
_Files inspected:_ _filled by Task 6._

_Findings:_

### 3.6 Frontend wizards & pages
_Files inspected:_ _filled by Task 7._

_Findings:_

### 3.7 End-to-end flow walkthrough
_Files inspected:_ _filled by Task 8._

_Walkthrough:_

_Flow-level findings:_

### 3.8 Cross-cutting
_Files inspected:_ _filled by Task 9._

_Findings:_

## 4. What works well

_To be written in Task 10._

## 5. Recommended next steps

_To be written in Task 10._
```

- [ ] **Step 2: Commit**

```bash
git add docs/audits/2026-04-17-timetable-audit.md
git commit -m "audit(timetable): bootstrap report skeleton"
```

---

## Task 2: Data model & migrations (Layer DM)

**Files:**
- Inspect (read-only): `backend/models/scheduling.py`, `backend/pg_models.py`, `backend/shared_models.py`, `backend/models/enums.py`, all alembic versions in `backend/alembic/versions/` whose name or content references timetable / scheduling / constraint / time slot.
- Modify: `docs/audits/2026-04-17-timetable-audit.md` (section 3.1 only)

- [ ] **Step 1: Inventory the files**

Run:
```bash
ls backend/models/scheduling.py backend/pg_models.py backend/shared_models.py backend/models/enums.py
```
Then list alembic versions touching timetable concepts:
```bash
grep -rli -E "timetable|schedule|time_slot|constraint" backend/alembic/versions
```
Record the resulting file list under `_Files inspected:_` in section 3.1 of the report.

- [ ] **Step 2: Inspect each file and record findings**

For every model file and each matching alembic version, look for:
1. Entities and relationships — is there a clean `TimeSlot`, `Period`, `ScheduledSession` (or equivalent) with FKs to `Class`, `Subject`, `Teacher`, `Room`, `AcademicTerm`?
2. Multi-tenant scoping — does every timetable-owned table have a `tenant_id` / `school_id` column, indexed, and is it part of unique constraints?
3. FK integrity — `ON DELETE` behaviour, missing FKs, orphan risks.
4. Nullability — fields that should be `NOT NULL` but aren't, and vice versa.
5. Indexes — composite indexes for common queries (by tenant + term + day + slot, by teacher + day + slot, by class + day + slot, by room + day + slot).
6. Uniqueness — prevents the same teacher, class, or room being booked twice in the same slot.
7. Migration history coherence — superseded migrations, columns added then immediately altered, nullable-to-nullable churn.
8. Datetime vs string columns — any string columns that should be `DateTime` (cross-reference `c8d9e0f1a2b3` and `e2f3a4b5c6d7`).

For each issue, append a finding under `_Findings:_` in section 3.1 using the finding format from the conventions block. If nothing is wrong, write `_No issues found._`.

- [ ] **Step 3: Commit**

```bash
git add docs/audits/2026-04-17-timetable-audit.md
git commit -m "audit(timetable): data model findings"
```

---

## Task 3: Seed & reference data (Layer SD)

**Files:**
- Inspect (read-only): `backend/seeds/timetable_hard_constraints.py`, `backend/seeds/timetable_soft_constraints.py`, anything else under `backend/seeds/` referencing time slots, periods, breaks, default rooms.
- Modify: `docs/audits/2026-04-17-timetable-audit.md` (section 3.2 only)

- [ ] **Step 1: List seed files and seed call sites**

```bash
ls backend/seeds
grep -rli -E "time_slot|period|break|hard_constraint|soft_constraint" backend/seeds
```
Then locate where these seeds are invoked (tenant onboarding, seed runner, lifecycle hooks):
```bash
grep -rln -E "timetable_hard_constraints|timetable_soft_constraints|seed_timetable|seed_constraints" backend --include='*.py'
grep -rln -E "tenant.*creat|onboard|on_school_create|provision_school" backend --include='*.py'
```
Record both the seed files and the discovered invocation files under `_Files inspected:_` in section 3.2. If no invocation site is found, record that fact explicitly — it is itself a finding.

- [ ] **Step 2: Inspect each seed file and record findings**

Check for:
1. Coverage — are all hard constraints a real school needs (no double-booking teacher, no double-booking class, no double-booking room, teacher availability, max periods per day per teacher, subject-required-room) actually seeded?
2. Coverage — are common soft constraints (preferred slots, balanced distribution across the week, lunch break, no last-period for hard subjects) present?
3. Tenancy — are seeds tenant-scoped or applied globally? Does the seed run per-tenant on tenant creation?
4. Idempotency — is the seed safe to re-run? Will it create duplicates?
5. Localisation — are constraint names / descriptions translatable, or hard-coded English?
6. Defaults — default time slots / period lengths / school week (Sun–Thu vs Mon–Fri) — sensible defaults? Configurable?
7. Drift — do seed identifiers match what the engine and frontend expect (codes, slugs)?

Append findings to section 3.2 using the finding format. Write `_No issues found._` if none.

- [ ] **Step 3: Commit**

```bash
git add docs/audits/2026-04-17-timetable-audit.md
git commit -m "audit(timetable): seed data findings"
```

---

## Task 4: Constraints — hard and soft (Layer CN)

**Files:**
- Inspect (read-only): every backend file matching `grep -rli "constraint" backend --include='*.py'` that relates to scheduling, plus the constraint-related routes (`scheduling_*_routes.py`).
- Modify: `docs/audits/2026-04-17-timetable-audit.md` (section 3.3 only)

- [ ] **Step 1: Build the constraint map**

```bash
grep -rln -E "hard_constraint|soft_constraint|HardConstraint|SoftConstraint" backend --include='*.py'
```
Record the resulting file list under `_Files inspected:_` in section 3.3.

- [ ] **Step 2: Inspect and record findings**

For each hard constraint and each soft constraint, answer:
1. Where is it defined (DB row, code class, or both)?
2. Where is it evaluated (engine, API validator, DB constraint, UI)?
3. Is the evaluation correct? (Skim the code path; flag obvious bugs such as off-by-one, wrong comparison, ignoring tenant.)
4. Is the constraint configurable per school, or hard-coded?
5. Are violations surfaced clearly (codes, messages, i18n keys)?
6. Are soft-constraint weights / priorities defined, or implicit?
7. Are there constraints that are listed in the seeds but never actually enforced anywhere (dead constraints), or enforced in code but not registered in the seeds (ghost constraints)?

Append findings to section 3.3 using the finding format. Write `_No issues found._` if none.

- [ ] **Step 3: Commit**

```bash
git add docs/audits/2026-04-17-timetable-audit.md
git commit -m "audit(timetable): constraints findings"
```

---

## Task 5: Generation engine (Layer EN)

**Files:**
- Inspect (read-only): `backend/engines/` (all files), `backend/services/scheduling_service.py`, `backend/routes/scheduling_generation_routes.py`, `backend/routes/scheduling_smart_engine_routes.py`, `backend/routes/scheduling_smart_session_routes.py`, plus any helper modules they import from `backend/services/` or `backend/utils/`.
- Modify: `docs/audits/2026-04-17-timetable-audit.md` (section 3.4 only)

- [ ] **Step 1: List engine files**

```bash
ls backend/engines
ls backend/services | grep -i -E "schedul|timetable"
```
Record under `_Files inspected:_` in section 3.4.

- [ ] **Step 2: Inspect and record findings**

Check:
1. Algorithm — what is it (greedy, backtracking, CSP, ILP, OR-Tools)? Is it documented anywhere?
2. Determinism — does the same input always produce the same output (seeded RNG, stable iteration order)?
3. Conflict detection — teacher / class / room collisions all detected? Cross-tenant safety?
4. Partial-data handling — what happens with no teachers, no classes, no time slots, missing subject assignments? Are errors actionable?
5. Timeouts — is there a max runtime / iteration cap? What happens on timeout (return best-so-far vs fail)?
6. Performance — any obvious O(n²) or O(n³) loops over sessions × slots × teachers without indexing?
7. Persistence — when generation produces a result, where is it stored? Atomic? Versioned (draft vs published)?
8. Concurrency — what if two principals click "Generate" simultaneously? Locking?
9. Error surface — exceptions vs structured error objects? Are constraint-violation reasons returned to the client?
10. Test coverage — are there unit tests under `backend/tests/test_smart_scheduling.py` and `test_smart_timetable_page.py`? Do they cover the failure modes above?

Append findings to section 3.4. Write `_No issues found._` if none.

- [ ] **Step 3: Commit**

```bash
git add docs/audits/2026-04-17-timetable-audit.md
git commit -m "audit(timetable): generation engine findings"
```

---

## Task 6: API routes (Layer API)

**Files:**
- Inspect (read-only): every route module matching `backend/routes/scheduling_*.py`, `backend/routes/principal_timetable_routes.py`, `backend/routes/timetable_readiness_routes.py`, `backend/routes/schedule_management_routes.py`, plus their dependency / auth wiring (`backend/dependencies.py`, `backend/middleware/`).
- Modify: `docs/audits/2026-04-17-timetable-audit.md` (section 3.5 only)

- [ ] **Step 1: List route files**

```bash
ls backend/routes | grep -E "schedul|timetable"
```
Record under `_Files inspected:_` in section 3.5.

- [ ] **Step 2: Inspect each route file**

For each endpoint in each file:
1. Auth — is `Depends(...)` for the current user / principal / role applied? Any unprotected endpoints?
2. RBAC — are role checks correct (principal-only generation, teacher-read-only, parent-read-own-child)?
3. Tenant scoping — does every query filter by tenant / school id?
4. Input validation — Pydantic models present? Required fields enforced?
5. Output schema — explicit response models, or raw dicts?
6. Error responses — consistent shape, proper status codes (400 vs 404 vs 409 vs 422 vs 500)?
7. Idempotency — `POST /generate`, `POST /publish` — are retries safe?
8. Pagination — list endpoints return potentially huge lists?
9. N+1 — obvious eager-loading misses?
10. Versioning — draft vs published timetable separation in the API surface?
11. Audit logging — generation, publish, delete actions logged?

Append findings to section 3.5. Write `_No issues found._` if none.

- [ ] **Step 3: Commit**

```bash
git add docs/audits/2026-04-17-timetable-audit.md
git commit -m "audit(timetable): API findings"
```

---

## Task 7: Frontend wizards and pages (Layer FE)

**Files:**
- Inspect (read-only): `frontend/src/components/wizards/CreateScheduleWizard.jsx`, `frontend/src/pages/SchedulePageNew.jsx`, `frontend/src/components/timetable/PrincipalTimetablePage.jsx`, `frontend/src/pages/TimeSlotsPage.jsx`, `frontend/src/pages/TeacherModule/TeacherSchedulePage.jsx`, `frontend/src/pages/TeacherAssignmentsPage.jsx`, plus any timetable-related components found via `grep -rli -E "timetable|schedule" frontend/src/components`.
- Modify: `docs/audits/2026-04-17-timetable-audit.md` (section 3.6 only)

- [ ] **Step 1: List frontend files**

```bash
grep -rli -E "timetable|schedule" frontend/src/pages frontend/src/components | sort -u
```
Record under `_Files inspected:_` in section 3.6.

- [ ] **Step 2: Inspect and record findings**

For each page / component check:
1. Loading state — spinner / skeleton present and not blocking forever on error?
2. Empty state — useful message + call-to-action when no data?
3. Error state — surfaced from API errors? Localised? Retry possible?
4. Form validation — required fields, ranges (e.g. period count > 0), client-side feedback before submit?
5. Wizard step coherence — can the user go back without losing data? Final step previews what will be created?
6. i18n — every visible string in `frontend/src/locales/en.json` and `ar.json`? RTL layout works on the principal timetable grid?
7. Accessibility — keyboard navigation in the timetable grid, ARIA labels on cells, contrast on coloured subjects.
8. Performance — large grids (40 classes × 7 days × 8 periods) virtualised or rendering all DOM nodes?
9. State management — is the timetable cached? Stale data after generate / publish?
10. Role views — does TeacherSchedulePage only show that teacher's slots? Does the parent view filter to their child's class?

Append findings to section 3.6. Write `_No issues found._` if none.

- [ ] **Step 3: Commit**

```bash
git add docs/audits/2026-04-17-timetable-audit.md
git commit -m "audit(timetable): frontend findings"
```

---

## Task 8: End-to-end flow walkthrough (Layer E2E)

**Files:**
- Inspect (read-only): cross-references between layers already covered. No new files; this task ties the journey together.
- Modify: `docs/audits/2026-04-17-timetable-audit.md` (section 3.7 only)

- [ ] **Step 1: Write the walkthrough**

Under `_Walkthrough:_` in section 3.7, write the principal journey as a numbered narrative. For each step, name the screen / API used and reference the prior layer where it lives.

Steps to cover (each gets one short paragraph):
1. New empty school is created (tenant onboarding).
2. Principal sets up academic year and term.
3. Principal creates classes (grades, sections).
4. Principal creates / imports subjects.
5. Principal creates / imports teachers and assigns subjects to teachers.
6. Principal defines time slots / period structure for the school week.
7. Principal reviews / configures hard and soft constraints.
8. Principal opens the readiness check; gaps are reported.
9. Principal triggers generation; engine runs; result is shown as a draft.
10. Principal reviews the draft, makes manual edits if needed.
11. Principal publishes the timetable.
12. Teacher logs in and sees their schedule.
13. Student / parent logs in and sees the relevant class schedule.

- [ ] **Step 2: Record flow-only findings**

Under `_Flow-level findings:_` add findings that only emerge from the end-to-end view (e.g. "no clear handoff between readiness and generation", "publish action lacks confirmation", "teacher view does not refresh after republish"). Use the finding format. Write `_No issues found._` if none.

- [ ] **Step 3: Commit**

```bash
git add docs/audits/2026-04-17-timetable-audit.md
git commit -m "audit(timetable): end-to-end flow walkthrough"
```

---

## Task 9: Cross-cutting (Layer XC)

**Files:**
- Inspect (read-only): `backend/middleware/`, `backend/dependencies.py`, `backend/db.py`, `backend/db_indexes.py`, `frontend/src/locales/en.json`, `frontend/src/locales/ar.json`, plus **all** timetable-related tests discovered in Step 1 (do not hardcode a list — discover them).
- Modify: `docs/audits/2026-04-17-timetable-audit.md` (section 3.8 only)

- [ ] **Step 1: Discover all timetable-related tests**

```bash
grep -rln -E "timetable|schedul|time_slot|constraint" backend/tests --include='*.py' | sort -u
grep -rln -E "timetable|schedule" frontend/src --include='*.test.*' --include='*.spec.*' 2>/dev/null | sort -u
```
Record the resulting file list under `_Files inspected:_` in section 3.8 alongside the middleware / dependencies / locales files above.

- [ ] **Step 2: Inspect each concern and record findings**

Check, in this order, and record findings under section 3.8:

1. **Multi-tenant isolation** — re-confirm that timetable queries cannot leak across schools. Look for any raw SQL or ORM call missing the tenant filter.
2. **Performance** — composite index coverage from `backend/db_indexes.py` matches the engine's read patterns; no unbounded queries; pagination on list endpoints.
3. **Security / RBAC** — sensitive actions (generate, publish, delete) gated by role; no insecure direct object reference (passing arbitrary class_id without ownership check).
4. **Audit logging** — generate, publish, delete, manual-edit events recorded in audit log.
5. **i18n** — every timetable-facing string present in both `en.json` and `ar.json`; no English fallback strings hard-coded in JSX.
6. **Accessibility** — timetable grid keyboard reachable; meaningful ARIA labels; focus styles.
7. **Test coverage** — list which timetable behaviours are covered by tests and which are not (engine determinism, conflict detection, RBAC, multi-tenant isolation, end-to-end happy path).

Append findings to section 3.8. Write `_No issues found._` if none.

- [ ] **Step 3: Commit**

```bash
git add docs/audits/2026-04-17-timetable-audit.md
git commit -m "audit(timetable): cross-cutting findings"
```

---

## Task 10: Executive summary, top 10, what works, next steps

**Files:**
- Modify: `docs/audits/2026-04-17-timetable-audit.md` (sections 1, 2, 4, 5)

- [ ] **Step 1: Count findings per layer per severity**

Re-read the report top to bottom. Build a table by counting findings in each section.

Replace the placeholder under section 1 with:

```markdown
The timetable subsystem was audited end-to-end on 2026-04-17. <ONE-LINE OVERALL VERDICT>.

| Layer                  | Critical | High | Medium | Low | Total |
| ---------------------- | -------: | ---: | -----: | --: | ----: |
| Data model             |        X |    X |      X |   X |     X |
| Seed data              |        X |    X |      X |   X |     X |
| Constraints            |        X |    X |      X |   X |     X |
| Generation engine      |        X |    X |      X |   X |     X |
| API                    |        X |    X |      X |   X |     X |
| Frontend               |        X |    X |      X |   X |     X |
| End-to-end flow        |        X |    X |      X |   X |     X |
| Cross-cutting          |        X |    X |      X |   X |     X |
| **Total**              |    **X** | **X** |  **X** | **X** | **X** |
```

Replace each `X` with the actual count, and the `<ONE-LINE OVERALL VERDICT>` with one sentence summarising the state (e.g. "Core generation works but multi-tenant isolation has gaps and the principal review flow is incomplete.").

- [ ] **Step 2: Write the Top 10**

Under section 2, list the 10 highest-impact findings (all Criticals first, then Highs in impact order). For each, write one bullet:

```markdown
- **F-XX-NN — <title>** (Critical/High, `path/to/file.py:LINE`) — <one-sentence why it matters>.
```

If there are fewer than 10 Critical+High findings combined, include the worst Mediums to reach 10, or state explicitly `Only N critical/high findings were identified.` and list those.

- [ ] **Step 3: Write "What works well"**

Under section 4, write 3–6 bullets calling out the strongest parts of the subsystem identified during the audit. Be specific (file or feature names), not generic.

- [ ] **Step 4: Write "Recommended next steps"**

Under section 5, produce an ordered list of work batches:

```markdown
1. **<Batch name>** — addresses F-XX-NN, F-YY-MM. Rationale: <why first>.
2. **<Batch name>** — ...
```

Group fixes that share files or that unblock each other. Sort batches Critical → High → Medium. Stop at the point where remaining work is Low.

- [ ] **Step 5: Final consistency check**

Re-read the report once. Confirm:
- Every layer section has either findings or `_No issues found._`.
- The summary table totals match the actual finding counts.
- Every finding ID in the Top 10 and Next Steps exists in a layer section.
- No `_filled by Task N._` placeholders remain.

Fix any issue inline.

- [ ] **Step 6: Commit**

```bash
git add docs/audits/2026-04-17-timetable-audit.md
git commit -m "audit(timetable): executive summary, top 10, next steps"
```

---

## Self-review (done by plan author, not the implementer)

- [x] Spec coverage: every layer in spec §3 has its own task (Tasks 2–9). Report structure in spec §4 matches Tasks 1 + 10. Method rules from spec §2 baked into the conventions block.
- [x] No placeholders in plan steps. Every check is concrete; the only "fill in" content is the audit findings themselves, which by definition are produced during execution.
- [x] Type / name consistency: finding ID convention defined once in conventions block and used unchanged in every task. Section numbers (3.1–3.8) consistent between Task 1 skeleton and Tasks 2–9.
- [x] Out-of-scope items from spec §5 respected: every task is read-only outside `docs/audits/`, no fixes performed.
