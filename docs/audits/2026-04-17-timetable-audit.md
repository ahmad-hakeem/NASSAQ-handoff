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

The timetable subsystem was audited end-to-end on 2026-04-17. Core CRUD and the smart-engine happy path work, but the subsystem has critical multi-tenant and authorization holes, advertises 17 hard constraints while enforcing only 3, and uses three divergent generators with non-atomic persistence — it is not production-safe in its current state.

| Layer                  | Critical | High | Medium | Low | Total |
| ---------------------- | -------: | ---: | -----: | --: | ----: |
| Data model             |        1 |    5 |      5 |   1 |    12 |
| Seed data              |        0 |    5 |      3 |   1 |     9 |
| Constraints            |        2 |    4 |      5 |   1 |    12 |
| Generation engine      |        1 |    7 |      8 |   1 |    17 |
| API                    |        3 |    5 |      9 |   2 |    19 |
| Frontend               |        0 |    2 |      6 |   2 |    10 |
| End-to-end flow        |        0 |    4 |      3 |   1 |     8 |
| Cross-cutting          |        0 |    4 |      1 |   2 |     7 |
| **Total**              |    **7** | **36** |  **40** | **11** | **94** |

## 2. Top 10 critical / high findings

- **F-API-02 — Principal-timetable router authenticates by raw JWT decode and skips role enforcement** (Critical, `backend/routes/principal_timetable_routes.py:171-190`) — every generate/publish/swap/move handler in the 1,962-line router is callable by any authenticated user (including teachers, students, parents, and revoked tokens) for any school whose UUID they know.
- **F-API-01 — Generation, publish, validate, conflicts, and version endpoints accept any `school_id` / `timetable_id` from any authenticated user** (Critical, `backend/routes/scheduling_smart_engine_routes.py:83-625`) — direct cross-tenant read, generate, publish, archive, and delete; a school A principal can overwrite school B's published timetable.
- **F-API-04 — Tenant scoping on list/get endpoints uses `current_user["tenant_id"]` only when `school_id` query param is missing** (Critical, `backend/routes/scheduling_core_routes.py:59-512`) — passing `?school_id=<other-school>` returns that school's time slots, teacher assignments, schedules, and sessions.
- **F-EN-06 — Cross-tenant safety not enforced inside the engine** (Critical, `backend/engines/smart_scheduling_engine.py:1927-1936`) — the engine itself trusts the `school_id` it is handed and loads constraint tables without a tenant filter, compounding any route-level scope hole into actual data mutation.
- **F-CN-06 — Cross-tenant constraint leak: empty `school_constraints` falls back to global `administrative_constraints`** (Critical, `backend/engines/smart_scheduling_engine.py:1934-1938`) — another school's rules silently shape this school's generation, and the readiness summary at `:442-444` repeats the bug, so counts and enforcement disagree per tenant.
- **F-CN-01 — Hard constraints are loaded but never dispatched: `validation_key` is dead metadata in the engine** (Critical, `backend/engines/smart_scheduling_engine.py:1926-1946`) — 14 of the 17 hard rules advertised in the Settings UI are never actually enforced; toggling `is_active` has zero effect.
- **F-DM-01 — No uniqueness constraint preventing teacher / class / room double-booking** (Critical, `backend/pg_models.py:362-395`) — the DB silently accepts double-bookings; conflict detection is purely advisory and any concurrent generation, drag-and-drop, or manual edit can corrupt the timetable.
- **F-CN-02 — Publish-gate validator enforces only 3 of 17 hard constraints** (High, `backend/engines/smart_scheduling_engine.py`) — a draft riddled with HC-04…HC-17 violations passes the publish gate, so the "validation" before publish is largely cosmetic.
- **F-CN-03 — Room overlap (HC-03) is never detected anywhere in the engine or publish-gate** (High, `backend/engines/smart_scheduling_engine.py`) — two classes can be placed in the same room in the same slot with no warning at generate, validate, or publish time.
- **F-EN-04 — Re-running generation silently overwrites prior sessions** (High, `backend/engines/smart_scheduling_engine.py`) — there is no draft-vs-published separation; an accidental re-run from any user with route access wipes the previous result with no recovery path.

## 3. Layer findings

### 3.1 Data model & migrations
_Files inspected:_
- `backend/models/scheduling.py`
- `backend/pg_models.py`
- `backend/shared_models.py`
- `backend/models/enums.py`
- `backend/alembic/versions/6ba4c4afaf24_initial_schema_with_fk_relationships.py`
- `backend/alembic/versions/0ddc122c827a_add_generic_documents_table.py`
- `backend/alembic/versions/e052f4eb5993_timetable_constraint_type_nullable.py`
- `backend/alembic/versions/b7e52689a1ad_add_indexes_unique_constraints.py`
- `backend/alembic/versions/c8d9e0f1a2b3_migrate_string_timestamps_to_datetime.py`
- `backend/alembic/versions/e2f3a4b5c6d7_migrate_remaining_string_timestamps.py`
- `backend/alembic/versions/g1h2i3j4k5l6_add_missing_indexes_performance.py`
- `backend/alembic/versions/h1i2j3k4l5m6_promote_generic_doc_collections.py`
- `backend/alembic/versions/i1j2k3l4m5n6_add_missing_fk_indexes.py`
- `backend/alembic/versions/l1m2n3o4p5q6_fix_approval_events_fk.py`

_Findings:_

#### F-DM-01 — No uniqueness constraint preventing teacher / class / room double-booking
- **Severity:** Critical
- **Location:** `backend/pg_models.py:362-395` (`ScheduleSession.__table_args__`)
- **Description:** `schedule_sessions` has no `UniqueConstraint` on `(school_id, teacher_id, day_of_week, time_slot_id)`, `(school_id, class_id, day_of_week, time_slot_id)`, or `(school_id, room_id, day_of_week, time_slot_id)`. The initial migration (`6ba4c4afaf24_initial_schema_with_fk_relationships.py:999-1027`) likewise creates only non-unique indexes. The only protection is whatever the engine remembers to check at write time.
- **Why it matters:** Any code path or manual `INSERT` (drag-and-drop, manual edit, generation re-run, concurrent generation jobs) can place the same teacher in two classrooms in the same slot, the same class with two teachers, or the same room with two classes. The DB silently accepts it; conflict detection becomes purely advisory and cannot be relied on.
- **Recommended fix:** Add partial unique indexes (`WHERE teacher_id IS NOT NULL`, etc.) on the three tuples above, scoped per `schedule_id` (or per published timetable version) so drafts don't collide with published rows.
- **Effort:** M

#### F-DM-02 — `schedule_sessions.schedule_id` has no foreign key to `timetables`
- **Severity:** High
- **Location:** `backend/pg_models.py:367`; initial migration `backend/alembic/versions/6ba4c4afaf24_initial_schema_with_fk_relationships.py:1002,1020-1026`
- **Description:** `ScheduleSession.schedule_id` is a plain indexed `String` with no `ForeignKey("timetables.id", ...)`. The same is true of `TimetableRun.schedule_id` (`backend/pg_models.py:350`, no FK and no index). Deleting a `Timetable` row leaves orphaned sessions and runs.
- **Why it matters:** Orphan rows leak across tenants once IDs are reused, break the principal "delete draft" flow (sessions remain queryable from teacher / parent views), and corrupt aggregate counts (`Timetable.total_sessions`).
- **Recommended fix:** Add `ForeignKey("timetables.id", ondelete="CASCADE")` on `schedule_sessions.schedule_id` and `timetable_runs.schedule_id`, and add an index on `timetable_runs.schedule_id`.
- **Effort:** S

#### F-DM-03 — `ScheduleSession.room_id` has no FK and no `Room` entity link
- **Severity:** High
- **Location:** `backend/pg_models.py:376`; `physical_classrooms` table at `backend/pg_models.py:~1080`
- **Description:** `ScheduleSession.room_id` is a free-form `String` with no `ForeignKey`. There is a `physical_classrooms` table but the scheduling layer is not linked to it. The Pydantic `ScheduleSessionCreate` even comments "للتطوير المستقبلي" (`backend/models/scheduling.py:187`).
- **Why it matters:** Room conflicts cannot be enforced at the DB level (compounds F-DM-01); deleting / renaming a classroom leaves stale references; the principal cannot trust the room column on the timetable grid.
- **Recommended fix:** Define an FK `ForeignKey("physical_classrooms.id", ondelete="SET NULL")` on `schedule_sessions.room_id`, add a composite index `(school_id, room_id, day_of_week, time_slot_id)`, and treat room as a first-class scheduling dimension.
- **Effort:** M

#### F-DM-04 — Timetable / sessions / assignments have no link to `AcademicTerm` (or year as FK)
- **Severity:** High
- **Location:** `backend/pg_models.py:326-342` (`Timetable`), `:279-307` (`TeacherAssignment`), `:362-395` (`ScheduleSession`); `AcademicTerm` defined at `backend/pg_models.py:846-864`
- **Description:** `Timetable`, `TeacherAssignment`, and `ScheduleSession` track the academic period only as a free-text `academic_year` string and an `Integer` `semester` column (defaults `"2026-2027"` / `1`). There is no FK to `academic_terms.id` or `academic_years.id`, even though both tables exist.
- **Why it matters:** A school cannot have multiple in-flight terms cleanly; year rollover requires string editing; reporting cannot join sessions to the canonical term; deleting a term does not cascade to its timetables. The hard-coded default `"2026-2027"` will silently misclassify rows in 2027-2028.
- **Recommended fix:** Add `academic_term_id = Column(String, ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False, index=True)` to `Timetable` (and propagate to `ScheduleSession` / `TeacherAssignment`); back-fill from the existing `academic_year` + `semester` strings; drop the hard-coded default.
- **Effort:** L

#### F-DM-05 — `TeacherAssignment` has no uniqueness on (school, teacher, class, subject, term)
- **Severity:** High
- **Location:** `backend/pg_models.py:279-307`
- **Description:** No `UniqueConstraint` exists on `teacher_assignments` covering `(school_id, teacher_id, class_id, subject_id, academic_year, semester)`. The same teacher can be assigned to the same class + subject twice with different `weekly_sessions`.
- **Why it matters:** The generation engine reads assignments to decide how many sessions to place; duplicate rows silently double the placed count, breaking the generated timetable. Bulk import is exactly the path most likely to create duplicates.
- **Recommended fix:** Add a `UniqueConstraint("school_id", "teacher_id", "class_id", "subject_id", "academic_year", "semester", name="uq_assignment_unique")` and a one-time dedupe migration.
- **Effort:** S

#### F-DM-06 — Two divergent shapes for `TimeSlot` / `ScheduleSession` / `DayOfWeek` between Pydantic modules
- **Severity:** High
- **Location:** `backend/models/scheduling.py:30-38, 105-128, 177-210` vs `backend/shared_models.py:540-545, 559-585, 637-665`
- **Description:** `scheduling.py` defines `DayOfWeek` with English lowercase values (`"sunday"`, `"monday"`, …) and a `TimeSlotCreate` with fields `name / slot_number / is_break`. `shared_models.py` defines `DayOfWeekEnum` with **Arabic** values (`"الأحد"`, `"الإثنين"`, …) and a `TimeSlotCreate` with fields `period_number / slot_type / label / day`. `ScheduleSessionCreate` likewise differs: `day_of_week` + `time_slot_id` (scheduling.py) vs `day` + `period_number` (shared_models.py). The ORM column `ScheduleSession.day_of_week` is `String` and even has a sibling `day` column (`backend/pg_models.py:372-373`) — both are written from different routes.
- **Why it matters:** Routes serialise the same row two different ways; a conflict-check that compares `"sunday"` to `"الأحد"` returns false; engine and UI cannot agree on the day axis. Direct cause of stale / mismatched timetable cells.
- **Recommended fix:** Pick one canonical enum (e.g. lowercase English, kept in `models/scheduling.py`), delete the duplicate in `shared_models.py`, drop the redundant `day` / `period_number` ORM columns once back-filled, and update routes to use the single Pydantic model.
- **Effort:** M

#### F-DM-07 — `TimeSlot.start_time` / `end_time` and `Timetable.effective_from` / `effective_to` are `String`, not `Time` / `Date`
- **Severity:** Medium
- **Location:** `backend/pg_models.py:317-318` (`TimeSlot`), `:335-336` (`Timetable`); migration `backend/alembic/versions/c8d9e0f1a2b3_migrate_string_timestamps_to_datetime.py:15-91` migrated `created_at` columns but left these
- **Description:** Time-of-day and date columns are still `String` ("HH:MM" and "YYYY-MM-DD" by convention). The big string-to-datetime migration deliberately migrated only `created_at` / `updated_at` style columns, skipping these. Mirrors the issue called out for `c8d9e0f1a2b3` and `e2f3a4b5c6d7` in the task brief.
- **Why it matters:** No DB-side ordering or arithmetic: `WHERE start_time < end_time` is lexicographic, breaks for `"9:00"` vs `"10:00"` if the convention slips; range queries for "sessions effective today" require Python parsing; constraints like "no slot crossing midnight" cannot be expressed in SQL.
- **Recommended fix:** Add a third migration converting `time_slots.start_time/end_time` to `TIME` and `timetables.effective_from/effective_to` to `DATE`, with `_safe_cast` helpers analogous to `c8d9e0f1a2b3`.
- **Effort:** M

#### F-DM-08 — `TimetableConstraint.school_id` is nullable with `ON DELETE SET NULL`; tenant-scoped rows silently become global
- **Severity:** Medium
- **Location:** `backend/pg_models.py:1124-1137`; initial migration `backend/alembic/versions/6ba4c4afaf24_initial_schema_with_fk_relationships.py:311-325`; nullable churn in `backend/alembic/versions/e052f4eb5993_timetable_constraint_type_nullable.py:21-36`
- **Description:** `school_id` is `nullable=True`, FK uses `ondelete="SET NULL"`, and `is_global` defaults `True`. When a school is deleted, every per-school constraint becomes `school_id = NULL`, which the rest of the code treats as a *platform-wide* constraint applicable to every other tenant. Additionally `type` was made nullable (migration `e052f4eb5993`) immediately after the initial schema, contradicting any "one of {hard, soft}" invariant.
- **Why it matters:** Multi-tenant leak — one school's deleted constraint can start applying to all schools. Nullable `type` removes the only discriminator the engine has between hard and soft rules.
- **Recommended fix:** Use `ondelete="CASCADE"` for school-owned constraints (or split into `timetable_constraints_global` + `timetable_constraints_school` tables). Make `type` `NOT NULL` with a CHECK constraint.
- **Effort:** S

#### F-DM-09 — Missing composite indexes for the engine's hot read paths
- **Severity:** Medium
- **Location:** `backend/pg_models.py:391-395`; migration `backend/alembic/versions/g1h2i3j4k5l6_add_missing_indexes_performance.py:30`
- **Description:** Existing composite indexes are `(school_id, schedule_id, day_of_week)`, `(teacher_id, day_of_week)`, `(class_id, day_of_week)` only. There is no `(teacher_id, day_of_week, time_slot_id)`, `(class_id, day_of_week, time_slot_id)`, `(room_id, day_of_week, time_slot_id)`, or `(school_id, academic_term_id, day_of_week, time_slot_id)` — exactly the keys a conflict check or "what's on Sunday period 3" query needs. The day-of-week-only index added in `g1h2i3j4k5l6` is too low-cardinality to help.
- **Why it matters:** Conflict checks and grid renders perform full-day scans + Python filtering; performance on a real school (40 classes × 7 days × 8 slots ≈ 2 240 rows per term) is acceptable today but degrades non-linearly with multi-term retention.
- **Recommended fix:** Add the three missing `(<actor>_id, day_of_week, time_slot_id)` composite indexes; once F-DM-04 lands, prepend `academic_term_id`.
- **Effort:** S

#### F-DM-10 — Denormalised name caches and duplicate axis columns on `schedule_sessions` are silently allowed to drift
- **Severity:** Medium
- **Location:** `backend/pg_models.py:362-395` (columns `teacher_name`, `class_name`, `subject_name`, `time_slot_name`, `start_time`, `end_time`, plus duplicate axes `day_of_week` / `day` and `time_slot_id` / `slot_number`); also `backend/pg_models.py:279-307` (`TeacherAssignment.teacher_name`, `class_name`, `subject_name`, `weekly_sessions` AND `periods_per_week`)
- **Description:** Each `schedule_sessions` row caches the names of its FK targets and re-stores time-of-day. There is no trigger or migration to refresh them. `day_of_week` and `day` coexist; `time_slot_id` and `slot_number` coexist; `weekly_sessions` and `periods_per_week` coexist. Different code paths populate different columns (see F-DM-06).
- **Why it matters:** Renaming a teacher / subject / class leaves stale labels on the timetable grid forever; teacher and parent views show outdated names. Two "source of truth" columns invite silent disagreement (e.g. an engine that reads `weekly_sessions` and a route that writes `periods_per_week`).
- **Recommended fix:** Drop the cached *_name columns and resolve names via JOIN at read time (the FK relationships already exist with `lazy="selectin"`). Pick one of `day_of_week` / `day`, one of `time_slot_id` / `slot_number`, one of `weekly_sessions` / `periods_per_week`; back-fill and drop the loser.
- **Effort:** M

#### F-DM-11 — `Timetable` allows multiple "published" rows per (school, term, semester)
- **Severity:** Medium
- **Location:** `backend/pg_models.py:326-342`
- **Description:** `Timetable` has no `UniqueConstraint`. Two simultaneous principal "Publish" clicks (or repeated re-publishes) can leave several rows with `status="published"` for the same school + academic_year + semester.
- **Why it matters:** Teacher / parent views that fetch "the published timetable" pick whichever row the ORM returns first; behaviour is non-deterministic; audit log of "who is currently published" is meaningless.
- **Recommended fix:** Add a partial unique index `WHERE status = 'published'` on `(school_id, academic_year, semester)` — or, after F-DM-04, on `(school_id, academic_term_id)`. Combine with a transactional "demote previous published row" in the publish path.
- **Effort:** S

#### F-DM-12 — `TimetableConstraint` has no `updated_at`
- **Severity:** Low
- **Location:** `backend/pg_models.py:1124-1137`
- **Description:** Unlike every other tenant-owned table, `timetable_constraints` only has `created_at`. The string-timestamp migrations don't add one either.
- **Why it matters:** Editing a constraint leaves no last-modified marker; cache invalidation and audit log correlation rely on guesswork.
- **Recommended fix:** Add `updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)` plus an Alembic migration.
- **Effort:** S

### 3.2 Seed & reference data
_Files inspected:_

Seed files:
- `backend/seeds/__init__.py` (empty)
- `backend/seeds/timetable_hard_constraints.py`
- `backend/seeds/timetable_soft_constraints.py`

Invocation / call sites:
- `backend/app/lifecycle.py` (startup-only invocation at lines 137–152)
- `backend/engines/smart_scheduling_engine.py` (consumer at lines 1927–1932; soft `scoring_key` dispatch at 1666–1803)
- `backend/engines/scheduling_engine.py` (related but separate `seed_default_time_slots` at lines 48–79)
- `backend/routes/scheduling_routes.py` (manual route invoking `seed_default_time_slots` at lines 139–152)
- `backend/routes/school_routes_mod.py` (tenant-creation path at lines 72–239 — does **not** invoke any timetable seed)
- `backend/routes/timetable_readiness_routes.py:328-329` (counts active hard/soft constraints for readiness UI)
- `backend/routes/principal_timetable_routes.py:977` (loads hard constraints for principal view)
- `backend/routes/school_settings_mod.py:996, 1036, 1091, 1107` (settings UI + soft-constraint per-school override path)
- `backend/routes/school_settings_routes.py:212` (settings list)

_Findings:_

#### F-SD-01 — Constraint seeds only run when the database is completely empty; subsequent additions never reach existing deployments
- **Severity:** High
- **Location:** `backend/app/lifecycle.py:137-152`
- **Description:** The hard- and soft-constraint seeds are only invoked from `_run_with_session("Hard constraints", ...)` / `_run_with_session("Soft constraints", ...)` inside the `if config.seed_allowed() and not db_has_data:` branch. `db_has_data` is `True` whenever `users` has any row, so on any production-like database (which always has at least platform-admin users) the seeds are *always* skipped. The opposite branch logs `"Seed scripts SKIPPED (database already has data)"`.
- **Why it matters:** When a new constraint is added to `TIMETABLE_HARD_CONSTRAINTS` or `TIMETABLE_SOFT_CONSTRAINTS` (e.g. HC-18), no existing deployment will ever seed it. Schools generated after the upgrade silently miss the new rule; engine reads `await gd_find(... is_active: True)` and gets the old set. The seed authors clearly intended idempotent upserts (`seed_hard_constraints` does upsert-by-`code` at lines 282–299) but the gate prevents them from running.
- **Recommended fix:** Move the constraint seeds out of the `not db_has_data` branch and run them on every startup (they are already idempotent upserts). Gate only the *user* / demo data behind the empty-DB check.
- **Effort:** S

#### F-SD-02 — `seed_soft_constraints` early-returns by count, so adding a new soft constraint to the code list never inserts it
- **Severity:** High
- **Location:** `backend/seeds/timetable_soft_constraints.py:187-189`
- **Description:** Before iterating, the function does `existing_count = await collection.count_documents({}); if existing_count >= len(TIMETABLE_SOFT_CONSTRAINTS): return {"status": "already_seeded", ...}`. If the collection contains 12 rows and a developer appends a 13th constant to `TIMETABLE_SOFT_CONSTRAINTS`, the count check passes (12 ≥ 12 → false) only on the *first* run that inserts the 13th; but if rows include any leftover school-override or stale row inflating count, the upsert loop is skipped entirely. Worse, the symmetrical hard-constraint seed at `timetable_hard_constraints.py:271-308` does *not* have this short-circuit — the two seeds disagree on idempotency semantics.
- **Why it matters:** Combined with F-SD-01 the soft seed is effectively a write-once-and-forget script. Any future "add a constraint" PR will silently no-op in production. The mismatch between the two seed files also confuses operators who assume identical behaviour.
- **Recommended fix:** Drop the count-based short-circuit; rely on the `find_one({"code": ...})` upsert loop already present at lines 193–203, mirroring the hard-constraint seed.
- **Effort:** S

#### F-SD-03 — Hard-constraint `validation_key` is dead metadata; the engine never dispatches off it
- **Severity:** High
- **Location:** `backend/seeds/timetable_hard_constraints.py:11-267` (every entry has a `validation_key`); consumer at `backend/engines/smart_scheduling_engine.py:1927-1928, 1934-1938`
- **Description:** Every hard-constraint row carries a `validation_key` (`teacher_overlap`, `class_overlap`, `room_overlap`, `school_day_boundary`, `non_teaching_period`, `daily_period_limit`, `working_days`, `teacher_weekly_load`, `subject_weekly_periods`, `no_consecutive_subject`, `teacher_subject_match`, `teacher_class_assignment`, `resource_single_booking`, `schedule_completeness`, `academic_structure_match`, `entity_integrity`, `block_publish_on_conflict`). A grep across the entire backend shows zero references to any of these strings outside the seed file itself. The smart-scheduling engine loads the rows (`hard_constraints = await gd_find(... "timetable_hard_constraints" ...)`) and then concatenates them with `school_constraints` into `all_constraints` but never inspects `validation_key`. The actual hard-rule enforcement is hand-coded inside Python (e.g. `_apply_soft_constraint_scoring` for soft, ad-hoc grid-collision checks for hard).
- **Why it matters:** The seeds give the impression that disabling a row (`is_active: False`, or `can_disable: True` + override) will turn off a system rule. It will not — the engine ignores the rows. Compounds with F-SD-06 (HC-10's `can_disable: True` is meaningless) and the principal Settings UI at `backend/routes/school_settings_mod.py:996` which exposes the rows for inspection. Worse, if a real validation_key/check pair drifts (engine bug fixed under one name, seed still labels another), no error surface tells anyone.
- **Recommended fix:** Either (a) add a registry mapping `validation_key → callable` and have the engine iterate `for hc in all_constraints: enforce(hc.validation_key)`, or (b) delete `validation_key` and document that the rows are display-only metadata. Option (a) is the long-term correct shape.
- **Effort:** L

#### F-SD-04 — Default time slots, working days, and per-school constraint customisation are never seeded on tenant creation
- **Severity:** High
- **Location:** `backend/routes/school_routes_mod.py:72-239` (`create_school`); `backend/engines/scheduling_engine.py:48-79` (`seed_default_time_slots`, only invoked from `backend/routes/scheduling_routes.py:139-152`)
- **Description:** `create_school` inserts a `schools` row, optionally a principal user, and then *optionally* copies a `default_settings` template into `school_settings` (lines 198–220) — but only if a `default_settings` row exists, and the copy excludes any per-school constraint override rows. There is no call to `SchedulingEngine.seed_default_time_slots(school_id, ...)`, no insert into `school_soft_constraint_overrides`, and no `time_slots` rows are created. The only way time slots reach a new tenant is the manual route at `scheduling_routes.py:139-152`, which a principal must trigger by hand.
- **Why it matters:** A freshly onboarded school has zero time slots, so every readiness check (`backend/routes/timetable_readiness_routes.py:328-329`) and every generation attempt (engine `pre_scheduling_check`) fails with no clear "seed me" button. The principal sees an empty TimeSlotsPage with no defaults; the timetable wizard cannot proceed. Multi-tenant onboarding is therefore broken for the timetable subsystem.
- **Recommended fix:** Inside `create_school` (or a dedicated `provision_school` lifecycle hook) call `SchedulingEngine.seed_default_time_slots(school_id, current_user["id"])` and seed a baseline `school_soft_constraint_overrides` row per global soft constraint. Guard with idempotency.
- **Effort:** M

#### F-SD-05 — Missing common hard-constraint coverage: subject-required-room, per-day teacher cap, explicit teacher-availability rule
- **Severity:** High
- **Location:** `backend/seeds/timetable_hard_constraints.py:11-267`
- **Description:** The seeded HC set covers teacher/class/room overlap (HC-01..03, HC-13), school-day boundaries (HC-04, HC-05, HC-07), weekly load (HC-08, HC-09), assignment integrity (HC-11, HC-12, HC-15, HC-16) and publishing gates (HC-14, HC-17). It does **not** cover three constraints a real school relies on:
  1. *Subject-required-room* — e.g. PE in the gym, Chemistry in the lab. No HC row references room *type*; HC-03 only blocks double-booking.
  2. *Max periods per day per teacher* — only the *weekly* quota (HC-08) is encoded; a teacher with 20 weekly periods can be given all 7 on Sunday.
  3. *Teacher availability windows* — the engine reads `teacher_availability` rows at `backend/engines/smart_scheduling_engine.py:401-402, 747-748, 961`, but no HC-row makes that rule visible to the principal Settings UI; if `teacher_availability` is empty the engine silently treats every teacher as fully available.
- **Why it matters:** Generated timetables can produce pedagogically and operationally invalid drafts: PE in a regular classroom, a teacher booked for 7 straight periods on one day while idle the rest of the week, or a part-time teacher scheduled on their off day with no readiness warning.
- **Recommended fix:** Add HC-18 `subject_required_room`, HC-19 `teacher_daily_period_limit`, HC-20 `teacher_availability_window`. Couple each with the engine enforcement (see F-SD-03 registry idea) and surface them in the readiness check.
- **Effort:** M

#### F-SD-06 — HC-10 duplicates SC-01 with conflicting semantics ("no consecutive same subject" exists as both hard and soft)
- **Severity:** Medium
- **Location:** `backend/seeds/timetable_hard_constraints.py:147-162` (HC-10) vs `backend/seeds/timetable_soft_constraints.py:12-25` (SC-01)
- **Description:** HC-10 is `"No Consecutive Same Subject"` with `severity: critical`, `can_disable: True`, `override_setting: "allow_consecutive_same_subject"`, `validation_key: "no_consecutive_subject"`. SC-01 has the same human title `"No Consecutive Same Subject"` with `weight: 8`, `scoring_key: "no_consecutive_same_subject"`. The engine actually consumes the *soft* form (`sc_map.get("no_consecutive_same_subject")` at `backend/engines/smart_scheduling_engine.py:1668`) and never enforces HC-10 (per F-SD-03). Frontend listing both rows (settings UI at `school_settings_mod.py:996, 1036`) shows a "critical, cannot be disabled" hard rule alongside a "weight 8, can be disabled" soft rule for the *same* behaviour.
- **Why it matters:** Confusing for principals — they see the rule as both blocking and merely scored; turning the soft one off has no effect on the (also unenforced) hard one. Indicates the seed designers had not decided whether the rule is mandatory or preferential.
- **Recommended fix:** Remove HC-10 (it is a soft preference, not a publishing-block rule), or alternatively remove SC-01 and wire HC-10 through the validation_key registry. Document the choice.
- **Effort:** S

#### F-SD-07 — Hard constraints are global rows with no `school_id`; the seed never accommodates per-tenant variation
- **Severity:** Medium
- **Location:** `backend/seeds/timetable_hard_constraints.py:11-267` (no `school_id` field on any row); seed insert at lines 282–299; loader at `backend/engines/smart_scheduling_engine.py:1927`
- **Description:** Every HC row is global. The engine fetches them with `gd_find(... "timetable_hard_constraints", {"is_system": True, "is_active": True} ...)` — no `school_id` filter. There is no per-school override mechanism for hard rules; a partial school override exists only for *soft* constraints (`school_soft_constraint_overrides`, see `school_settings_mod.py:1107`). Combined with `TimetableConstraint.school_id` being nullable in `pg_models.py` (see F-DM-08), tenant-scoped enforcement of any hard rule is impossible.
- **Why it matters:** A school that legitimately wants "allow consecutive same subject" (block scheduling), or wants stricter room rules, has no path. The principal Settings UI at `school_settings_routes.py:212` shows the rows as read-only.
- **Recommended fix:** Either (a) add `school_id: None` to every seeded row to make global-vs-tenant explicit and introduce a `school_hard_constraint_overrides` collection symmetric with the soft one, or (b) document that hard rules are platform-mandated and remove the appearance of configurability from the UI.
- **Effort:** M

#### F-SD-08 — `seed_default_time_slots` defaults are Saudi-specific, never reference school week, and use `String` times (compounds F-DM-07)
- **Severity:** Medium
- **Location:** `backend/engines/scheduling_engine.py:48-79`
- **Description:** The default 9 slots hard-code `07:00–13:40` with `"prayer"` at `12:10–12:55` (Dhuhr) and `"الفسحة الأولى"` (Arabic-only) for the break. There is no parallel seed of `working_days` (Sun–Thu vs Mon–Fri vs Sat–Wed); `working_days` is left for the `default_settings` template copy in `school_routes_mod.py:204-208`, which is conditional on a row existing in the `default_settings` collection. Times are stored as strings (`"07:00"`), inheriting F-DM-07's lexicographic-sort risk. Slot 4 is a 20-minute break, slot 8 is 45 minutes of prayer — both non-teaching but mixed in with teaching slots without any `is_break`/`is_prayer` boolean (only `type` string) that the readiness check at `timetable_readiness_routes.py:328-329` could discriminate.
- **Why it matters:** A non-Saudi school (Mon–Fri week, no Dhuhr slot) cannot use the defaults; an Arabic-only `name_ar` for the break breaks the en/ar parity that every constraint row otherwise enforces; and there is no programmatic way to ask "how many *teaching* slots does this school have on Sunday?" without parsing strings.
- **Recommended fix:** Make defaults country/`stage`-aware (look up from `school.country`); store slot times as `Time`; add `name_en` to the break row; expose `working_days` defaulting via the same seed.
- **Effort:** M

#### F-SD-09 — Constraint name/description localisation is hard-coded ar/en pairs with no i18n key indirection
- **Severity:** Low
- **Location:** `backend/seeds/timetable_hard_constraints.py:11-267`, `backend/seeds/timetable_soft_constraints.py:11-180`
- **Description:** Each row carries `name_ar` / `name_en` / `description_ar` / `description_en` literals. There is no `i18n_key` referencing `frontend/src/locales/{en,ar}.json`. Adding a third locale (e.g. French for an international school) requires a schema migration and a re-seed, not a JSON-file edit.
- **Why it matters:** Localisation burden grows quadratically with locales × constraints; a translation typo in production cannot be hot-fixed without a deploy.
- **Recommended fix:** Replace the four columns with a single `i18n_key: "constraints.hard.HC-01.name"` per row and move the strings to the locale JSON files.
- **Effort:** M

### 3.3 Constraints (hard + soft)
_Files inspected:_

`grep -rln -E "hard_constraint|soft_constraint|HardConstraint|SoftConstraint" backend --include='*.py'` returned:
- `backend/seeds/timetable_hard_constraints.py`
- `backend/seeds/timetable_soft_constraints.py`
- `backend/engines/smart_scheduling_engine.py`
- `backend/routes/school_settings_routes.py`
- `backend/routes/school_settings_mod.py`
- `backend/routes/principal_timetable_routes.py`
- `backend/routes/timetable_readiness_routes.py`
- `backend/app/lifecycle.py`

Additional constraint-related route / helper files inspected (per the broader `grep -rli "constraint"` plus `scheduling_*_routes.py` requirement):
- `backend/routes/scheduling_generation_routes.py`
- `backend/routes/scheduling_core_routes.py`
- `backend/routes/scheduling_routes.py`
- `backend/routes/scheduling_smart_engine_routes.py`
- `backend/routes/scheduling_smart_session_routes.py`

_Findings:_

#### F-CN-01 — Hard constraints are loaded but never dispatched: `validation_key` is dead metadata in the engine
- **Severity:** Critical
- **Location:** `backend/engines/smart_scheduling_engine.py:1926-1946` (load + concat) and `backend/seeds/timetable_hard_constraints.py:11-267` (every row carries a `validation_key`)
- **Description:** `generate_full_timetable` loads `timetable_hard_constraints` (`smart_scheduling_engine.py:1927`) and concatenates them with `school_constraints` into `all_constraints`, then passes that list to `generate_draft_timetable` and `detect_conflicts`. Neither callee inspects `validation_key`; the only hard-rule logic is hand-coded inline (class/teacher uniqueness checks at `:951-968` and `:1555-1573`, conflict scan at `:1410-1498`). Setting `is_active: False` on rows for HC-04, HC-05, HC-06, HC-07, HC-08, HC-09, HC-10, HC-11, HC-12, HC-13, HC-15, HC-16, or HC-17 has zero effect on engine behaviour because no dispatcher reads the key. A `grep` across the entire backend shows the strings `school_day_boundary`, `non_teaching_period`, `daily_period_limit`, `working_days`, `teacher_weekly_load`, `subject_weekly_periods`, `no_consecutive_subject`, `teacher_subject_match`, `teacher_class_assignment`, `resource_single_booking`, `academic_structure_match`, `entity_integrity`, `block_publish_on_conflict` appear only inside the seed file.
- **Why it matters:** 14 of the 17 "system-level rules that MUST be enforced" advertised to principals (Settings UI at `school_settings_mod.py:989-1024`) are in fact unenforced. A principal who edits HC-08's `is_active` flag in the DB to "loosen" the teacher-weekly-load gate sees no change; a principal who relies on HC-15 ("no out-of-curriculum subject") gets no protection. Audit trail and Settings UI both lie about what is actually being checked.
- **Recommended fix:** Build a `VALIDATION_REGISTRY: Dict[str, Callable]` mapping each `validation_key` to its enforcement function. In `generate_draft_timetable` and the publish-gate, iterate `for hc in active_hard_constraints: REGISTRY[hc["validation_key"]](...)`. Mirror the pattern already used for soft constraints (`scoring_key` dispatch at `:1668-1808`).
- **Effort:** L
- **Status:** ✅ Remediated 2026-04-17 (Batch 2 plan: docs/superpowers/plans/2026-04-17-timetable-remediation-batch2.md)

#### F-CN-02 — Publish-gate validator enforces only 3 of 17 hard constraints
- **Severity:** High
- **Location:** `backend/routes/principal_timetable_routes.py:960-1097` (`validate_before_publish`)
- **Description:** The pre-publish validator loads `hc_keys` (`:977-978`) and only conditionally raises errors for `teacher_overlap`, `class_overlap`, and `schedule_completeness` (`:1018-1063`). HC-03 (room_overlap), HC-04, HC-05, HC-06, HC-07, HC-08, HC-09, HC-10, HC-11, HC-12, HC-13, HC-15, HC-16, HC-17 — all marked `severity: critical, can_disable: False` in the seed — are silently ignored by the gate even when their rows are active. The function then sets `can_publish = len(validation_errors) == 0` (`:1083`).
- **Why it matters:** A draft that violates room double-booking, weekly-load quota, subject weekly periods, teacher-subject qualification, or curriculum integrity will pass `can_publish=True` and reach teacher / parent views. HC-17 ("Block publish on conflict") explicitly promises this gate exists; the gate exists in name only.
- **Recommended fix:** Once the registry from F-CN-01 lands, replace the hand-rolled if-chain with `for hc in active_hard_constraints: REGISTRY[hc["validation_key"]].validate_publish(version_id, school_id, validation_errors)`. As a stop-gap, hand-add the missing checks to `validate_before_publish`.
- **Effort:** M
- **Status:** ✅ Remediated 2026-04-17 (Batch 2 plan: docs/superpowers/plans/2026-04-17-timetable-remediation-batch2.md)

#### F-CN-03 — Room overlap (HC-03) is never detected anywhere in the engine or publish-gate
- **Severity:** High
- **Location:** `backend/engines/smart_scheduling_engine.py:1410-1498` (`detect_conflicts`), and `backend/routes/principal_timetable_routes.py:46-72` (`_count_real_conflicts`)
- **Description:** `detect_conflicts` only groups by `(day_of_week, period_number)` and checks `teacher_id` and `class_id` collisions (`:1437-1473`). It never inspects `room_id`. The aggregate at `_count_real_conflicts` likewise groups only by teacher and class. There is no `ConflictType.ROOM_OVERLAP` branch in `detect_conflicts` despite the enum entry existing in `models/scheduling.py`, and HC-03's `validation_key="room_overlap"` is not consulted (compounds F-CN-01).
- **Why it matters:** Two teachers can be scheduled in the same room at the same time and neither the generator, conflict detector, nor publish gate will surface it; principals discover it on the day the bell rings.
- **Recommended fix:** Add a third grouping in `detect_conflicts` keyed on `(room_id, day, period)` (skipping rows where `room_id` is null), emit `ConflictType.ROOM_OVERLAP` conflicts, and add a `room_conflicts` aggregate to `_count_real_conflicts`.
- **Effort:** S
- **Status:** ✅ Remediated 2026-04-17 (Batch 2 plan: docs/superpowers/plans/2026-04-17-timetable-remediation-batch2.md)

#### F-CN-04 — `minimize_teacher_travel` (SC-12) is a no-op listed as active in the Settings UI
- **Severity:** High
- **Location:** `backend/engines/smart_scheduling_engine.py:1803-1808`; seed `backend/seeds/timetable_soft_constraints.py:166-179`
- **Description:** The scoring dispatcher matches `sc_map.get("minimize_teacher_travel")` and then `logger.debug("Skipping minimize_teacher_travel constraint: room assignment data not yet available in the scheduling model")` — i.e. the function silently returns the score unchanged. SC-12 is seeded with `is_active: True, weight: 2` and exposed in the principal Settings UI at `school_settings_mod.py:1027-1078` as a togglable rule.
- **Why it matters:** Principals who turn the switch on or tune its weight believe they are influencing room-to-room teacher travel; they are not. Dead constraint.
- **Recommended fix:** Either implement the room-travel cost (requires F-DM-03's room FK), or set the seeded row to `is_active: False` and hide it from the UI until implemented.
- **Effort:** M

#### F-CN-05 — Custom soft constraints and constraint patterns are write-only — engine never loads them
- **Severity:** High
- **Location:** `backend/routes/school_settings_mod.py:1121-1310` (`/school/settings/custom-soft-constraints` and `/school/settings/constraint-patterns` CRUD); engine load at `backend/engines/smart_scheduling_engine.py:1930-1932`
- **Description:** The principal can create, update, delete rows in `custom_soft_constraints` and `custom_constraint_patterns` (full CRUD endpoints at `school_settings_mod.py:1121-1310`). The smart engine, however, only loads `timetable_soft_constraints` (line 1930) and `school_constraints` / `administrative_constraints` (lines 1934-1936). A grep for `custom_soft_constraints` and `custom_constraint_patterns` outside `school_settings_mod.py` returns zero results.
- **Why it matters:** Schools that author custom rules see them stored, listed in the UI, and silently ignored at generation time. The feature is half-built; the principal has no signal that their rule is dead.
- **Recommended fix:** Either extend `_apply_soft_constraint_scoring` to also load and apply `custom_soft_constraints` (requires a DSL or `pattern_code` dispatcher), or remove the CRUD endpoints and the corresponding UI until the engine wiring is implemented.
- **Effort:** L

#### F-CN-06 — Cross-tenant constraint leak: when a school has no `school_constraints`, the engine pulls **global** `administrative_constraints`
- **Severity:** Critical
- **Location:** `backend/engines/smart_scheduling_engine.py:1934-1938`
- **Description:** `constraints = await gd_find(self.session, "school_constraints", {"school_id": school_id, "is_active": True}, limit=50)`; `if not constraints: constraints = await gd_find(self.session, "administrative_constraints", {"is_active": True}, limit=50)`. The fallback query has **no** `school_id` filter; `administrative_constraints` is a global table. Whatever rules another school (or a platform admin) authored will be applied to this school's generation.
- **Why it matters:** Multi-tenant leak. School B's "no Math after lunch" rule (created when their `school_constraints` collection was empty) will silently distort School A's timetable. Combined with the same fallback in `engines/smart_scheduling_engine.py:442-444` for the readiness summary, the count and the enforcement disagree per tenant.
- **Recommended fix:** Drop the fallback entirely, or add a `{"school_id": school_id}` filter to the `administrative_constraints` query. Also audit `administrative_constraints` for tenant scoping at the schema level.
- **Effort:** S
- **Status:** ✅ Remediated 2026-04-17 (Batch 1 plan: docs/superpowers/plans/2026-04-17-timetable-remediation-batch1.md)

#### F-CN-07 — `hard_subjects_early` (SC-05) gives the early-period bonus to **every** subject, not just hard ones
- **Severity:** Medium
- **Location:** `backend/engines/smart_scheduling_engine.py:1699-1705`
- **Description:** ```sc = sc_map.get("hard_subjects_early"); if sc: w = sc.get("weight", 5) / 10.0; if period <= 3: score += 3 * w; elif period == teaching_period_numbers[-1]: score -= 1 * w```. The branch never inspects `subject_id` against any "is hard subject" predicate (the seed even names "Math, Science, Arabic" in the description). Consequently PE, Art, and electives also get the early-period bonus.
- **Why it matters:** Defeats the constraint's stated pedagogical purpose; principals tuning the weight see no qualitative change because the bonus applies uniformly. Generated timetables will not preferentially front-load core subjects.
- **Recommended fix:** Add a `target_subject_ids` field (already present on the per-school override at `school_settings_mod.py:1054-1055`) and gate the bonus on `if subject_id in sc.get("target_subject_ids", [])`. Default to a hard-coded set of "core" subjects via `subject.category == "core"` if no override is present.
- **Effort:** S

#### F-CN-08 — `balanced_weekly_distribution` uses a hard-coded threshold `>= 2` instead of subject's actual weekly periods
- **Severity:** Medium
- **Location:** `backend/engines/smart_scheduling_engine.py:1735-1748`
- **Description:** The check is `if today_count >= 2: score -= 10 * w`. For a subject with `weekly_periods=2` (e.g. Art on a 5-day week) the engine will penalise placing both periods on different days as soon as one of them lands. For Arabic (`weekly_periods=6` on a 5-day week, expected 1-2 per day) the threshold is far too lenient. The threshold ignores `len(working_days)` and `weekly_periods` entirely.
- **Why it matters:** The "balanced distribution" soft rule biases the optimiser toward incorrect distributions for both low-frequency and high-frequency subjects. The misbehaviour is silent because the score is never surfaced to the principal.
- **Recommended fix:** Compute `expected_per_day = ceil(weekly_periods / len(working_days))` and penalise `today_count > expected_per_day`.
- **Effort:** S

#### F-CN-09 — Soft "consecutive" / "gap" rules ignore break and prayer periods, so a session before lunch is treated as adjacent to one after lunch
- **Severity:** Medium
- **Location:** `backend/engines/smart_scheduling_engine.py:1668-1680` (no_consecutive_same_subject), `:1682-1697` (minimize_teacher_gaps), `:1707-1717` (limit_consecutive_teacher), `:1750-1765` (minimize_class_gaps), `:1788-1795` (diverse_after_break)
- **Description:** All four "adjacency" rules use `period - 1` / `period + 1` arithmetic over the integer period number, but `teaching_period_numbers` excludes break/prayer periods and is therefore non-contiguous (e.g. `[1,2,3,5,6,7]` if period 4 is a break). The check `prev_period in grid.get(day, {})` returns `False` for the break slot but the math still treats `period 5` and `period 3` as non-adjacent (gap=1) when they are in fact adjacent teaching slots, while treating `period 5` and `period 6` as adjacent across no break, which they are. Net: the rules misclassify "across-the-break" pairs as gaps and miss legitimate consecutive teaching slots when a break sits in between.
- **Why it matters:** Constraint scoring is wrong on every school day that has any non-teaching period (which is every real school). `diverse_after_break` (SC-09), whose entire purpose is to act on the slot immediately after a break, only fires when the previous *teaching* period happens to share a number with `period - 1` — i.e. essentially never on a real schedule.
- **Recommended fix:** Replace `period - 1` / `period + 1` with `prev_teaching_period(period)` / `next_teaching_period(period)` helpers that walk `teaching_period_numbers` rather than the integer line.
- **Effort:** S

#### F-CN-10 — `can_disable: True` on hard constraints (HC-10) is exposed to the UI but no endpoint exists to actually disable them
- **Severity:** Medium
- **Location:** `backend/seeds/timetable_hard_constraints.py:147-162` (HC-10's `can_disable: True`, `override_setting: "allow_consecutive_same_subject"`); GET endpoint at `backend/routes/school_settings_mod.py:989-1024`; PUT endpoint **only** exists for soft constraints (`:1081-1116`)
- **Description:** The hard-constraint listing endpoint returns rows including `can_disable` and `override_setting`. The frontend therefore renders a toggle. There is no `PUT /school/settings/hard-constraints/{code}` route, no override collection for hard rows (mirror of `school_soft_constraint_overrides`), and the engine ignores the flag anyway (F-CN-01). Combined with F-SD-06 (HC-10 vs SC-01), the UX is contradictory.
- **Why it matters:** Principals click the HC-10 toggle, get either no API call or a 405, and conclude the system is broken. The seed advertises configurability that the API and engine do not deliver.
- **Recommended fix:** Either remove `can_disable: True` from HC-10, or add a `school_hard_constraint_overrides` collection + PUT endpoint mirroring the soft path, and wire `override_setting` into the registry from F-CN-01.
- **Effort:** S

#### F-CN-11 — Conflict detector enforces only the global teacher weekly-load rule; HC-06, HC-08-daily, HC-09 are not checked
- **Severity:** Medium
- **Location:** `backend/engines/smart_scheduling_engine.py:1475-1496` (`detect_conflicts` weekly-load loop)
- **Description:** Beyond per-slot teacher/class collisions, the only quantitative check is `if load > resource.weekly_load: emit TEACHER_OVERLOAD`. There is no per-day cap (HC-06 daily_period_limit, no HC-19 daily-teacher cap), no `subject_weekly_periods` (HC-09) tally per `(class_id, subject_id)`, no enforcement that a class actually got `weekly_periods` of every subject (the publish-gate's "empty slot" warning is the only proxy). Generation skips a session silently with `unscheduled.append(...)` rather than raising.
- **Why it matters:** A class can finish generation missing 2 of 5 Math periods with no `TimetableConflict` raised; the publish gate (F-CN-02) won't catch it either unless those slots happen to be empty, but they may be filled by a different subject.
- **Recommended fix:** In `detect_conflicts`, add per-`(class_id, subject_id)` tally vs the demand's `weekly_periods` and emit `SUBJECT_QUOTA_VIOLATION`. Add a per-(teacher, day) tally vs a configurable `max_daily_periods`.
- **Effort:** M
- **Status:** ✅ Remediated 2026-04-17 (Batch 2 plan: docs/superpowers/plans/2026-04-17-timetable-remediation-batch2.md)

#### F-CN-12 — Constraint violation messages are bilingual hard-coded strings with no i18n key
- **Severity:** Low
- **Location:** `backend/routes/principal_timetable_routes.py:1011-1063` (publish-gate messages); `backend/engines/smart_scheduling_engine.py:1442-1496` (conflict messages); seed rows carry only `name_ar` / `name_en` / `description_ar` / `description_en`
- **Description:** Every error path returns Arabic + English strings inline (e.g. `"message": f"القيد الإلزامي: لا يمكن إسناد ..."`). There is no stable error code/i18n key beyond the human-readable `code` field (`HC-01`, `PERIODS_MISMATCH`, etc.) and these are not present in `frontend/src/locales/{en,ar}.json`. The frontend cannot render a localised message in a third language nor adapt copy without a backend deploy.
- **Why it matters:** Future i18n (e.g. Urdu, French for international branches) requires changing backend strings; A/B testing of error copy is impossible; QA cannot assert on stable keys.
- **Recommended fix:** Define an enum of constraint-violation codes (e.g. `TT.HC01.TEACHER_OVERLAP`) and return only the code + structured params; let the frontend do the i18n lookup via the locale files.
- **Effort:** M

### 3.4 Generation engine
_Files inspected:_
- `backend/engines/scheduling_engine.py` (688 lines — legacy schedule engine, time-slot CRUD, simple session insertion, conflict checks)
- `backend/engines/smart_scheduling_engine.py` (2166 lines — primary 8-phase smart engine: validate → load → demand → resources → pre-check → generate → detect → optimize)
- `backend/services/scheduling_service.py` (427 lines — secondary random-shuffle greedy generator over `teacher_assignments`/`schedule_sessions`)
- `backend/routes/scheduling_generation_routes.py` (1001 lines — `/schedules/{id}/generate`, conflicts, suggestions)
- `backend/routes/scheduling_smart_engine_routes.py` (~625 lines — smart engine HTTP surface)
- `backend/routes/scheduling_smart_session_routes.py` (995 lines — session update/swap/move/delete/add for the smart timetable)
- `backend/tests/test_smart_scheduling.py` (545 lines)
- `backend/tests/test_smart_timetable_page.py` (219 lines)

_Findings:_

#### F-EN-01 — Three coexisting, divergent generators
- **Severity:** High
- **Location:** `backend/engines/scheduling_engine.py:40-688`, `backend/services/scheduling_service.py:258-427`, `backend/engines/smart_scheduling_engine.py:1849-2067`
- **Description:** Three separate generation paths exist: (a) `SchedulingEngine` (per-session manual creation), (b) `SchedulingService.generate_schedule` (random-shuffle greedy over `teacher_assignments`), (c) `SmartSchedulingEngine.generate_timetable` (8-phase pipeline). They write to different tables (`schedule_sessions` vs `timetable_sessions`), use different day enums, different conflict tables, and different status lifecycles. The route `POST /schedules/{schedule_id}/generate` (`scheduling_generation_routes.py:35`) re-implements yet a fourth greedy variant inline rather than calling any of the three.
- **Why it matters:** Bug-fixes and constraint changes must be replicated four times; sessions written by one engine are invisible to readers querying the other table; conflicting "source of truth" makes the audit (and any future feature) ambiguous.
- **Recommended fix:** Pick one engine (the smart engine writes to `timetables`/`timetable_sessions`, which the frontend reads) and delete or thin-shim the others; centralise placement logic in a shared module.
- **Effort:** L

#### F-EN-02 — Generation is non-deterministic (no seeded RNG)
- **Severity:** Medium
- **Location:** `backend/services/scheduling_service.py:11,335,356`, `backend/routes/scheduling_generation_routes.py:11,53` (imports `random`), `backend/engines/smart_scheduling_engine.py:891-906` (sort by computed `difficulty` only)
- **Description:** `SchedulingService.generate_schedule` calls `random.shuffle(sessions_to_place)` and `random.shuffle(days_tried)` with no seed. The same input therefore produces different output every run. The smart engine relies on Python dict iteration order plus a single sort key (`-difficulty, -priority`); ties are resolved by insertion order, which depends on DB row ordering. Neither path accepts a `seed` parameter.
- **Why it matters:** Principals cannot reproduce a "good" generation, cannot diff two runs, cannot regression-test the engine, and support cannot reproduce user complaints. Re-running because "the previous result looked better" silently destroys the prior draft (see F-EN-04).
- **Recommended fix:** Add a `seed: Optional[int]` argument; instantiate `random.Random(seed)` and use it everywhere; persist the seed on the run record. For the smart engine, add a deterministic tiebreaker (e.g. `(class_id, subject_id)`).
- **Effort:** S

#### F-EN-03 — No iteration cap, timeout, or best-so-far recovery in the smart engine
- **Severity:** High
- **Location:** `backend/engines/smart_scheduling_engine.py:849-1225` (Phase 6 generation), `1849-2067` (`generate_timetable` orchestrator)
- **Description:** Phase 6 walks every demand × every period × every suitable teacher with no max_iterations, max_seconds, or asyncio timeout. The orchestrator has no `wait_for(...)` and no checkpoint of partial results. The legacy `SchedulingService.generate_schedule` accepts `max_iterations: int = 1000` (`scheduling_service.py:263`) but never actually reads the parameter inside the loop.
- **Why it matters:** A school with ~40 classes × 7 periods × 5 days × dozens of teachers can pin a backend worker for minutes; FastAPI default workers will block other requests. If the worker is killed or the request is cancelled, no timetable, no run record finalisation, and no partial result is persisted (state is held in the function-local `sessions` list until line 1983).
- **Recommended fix:** Wrap Phase 6 in `asyncio.wait_for`; honour `max_iterations`; flush sessions in batches per phase so the run can be resumed; on timeout, mark run as `PARTIAL` and persist whatever was placed.
- **Effort:** M

#### F-EN-04 — Re-running generation silently overwrites prior sessions
- **Severity:** High
- **Location:** `backend/services/scheduling_service.py:318` (`gd_delete_many("schedule_sessions", {"schedule_id": schedule_id})`), `backend/routes/scheduling_generation_routes.py:106` (same delete), `backend/engines/smart_scheduling_engine.py:1983` (always inserts a brand-new `timetable_id` so prior drafts accumulate)
- **Description:** Two of the three engines unconditionally `delete_many` all sessions for the schedule before regenerating, with no soft-delete, no archive, no version bump, and no confirmation. The smart engine takes the opposite extreme — every call creates a new `timetables` row, so a school accumulates dozens of draft timetables with no cleanup story; "version" is hard-coded to `1` (line 1978).
- **Why it matters:** A principal who manually adjusted a schedule (via session-update routes) and then clicks "Generate" again loses every adjustment with no undo. Conversely, the smart engine UI must somehow guess which of N drafts is current.
- **Recommended fix:** Wrap regeneration in an explicit "create new draft from current" with an incrementing `version`; require explicit user confirmation before `delete_many`; add `previous_timetable_id` linkage; provide a cleanup/retain-N-drafts policy.
- **Effort:** M

#### F-EN-05 — No concurrency lock on generation
- **Severity:** High
- **Location:** `backend/engines/smart_scheduling_engine.py:1849-2067`, `backend/routes/scheduling_smart_engine_routes.py:114-143`, `backend/routes/scheduling_generation_routes.py:35-313`
- **Description:** None of the three generators take a per-school lock (DB advisory lock, row lock, or in-process semaphore) before reading inputs and writing sessions. Two principals (or two browser tabs) hitting "Generate" simultaneously produce two parallel runs that interleave `delete_many` and `insert_many` against the same `schedule_id` / `school_id`.
- **Why it matters:** Race condition can leave the schedule with sessions from two interleaved runs (orphaned references, duplicate slots) or leave the run record stuck in `GENERATING`. No idempotency key is accepted on the route.
- **Recommended fix:** Take an advisory lock keyed by `school_id` (Postgres `pg_try_advisory_lock`) at the start of `generate_timetable`; reject overlapping requests with HTTP 409; or queue runs via a background task.
- **Effort:** M

#### F-EN-06 — Cross-tenant safety not enforced inside the engine
- **Severity:** Critical
- **Location:** `backend/engines/smart_scheduling_engine.py:1927-1936` (loads `timetable_hard_constraints` and `timetable_soft_constraints` with no `school_id` filter; falls back to `administrative_constraints` global), `backend/routes/scheduling_smart_engine_routes.py:114-143` (`generate_timetable` accepts `school_id` from the URL with no check that `current_user.school_id == school_id`), `backend/routes/scheduling_generation_routes.py:35-90` (loads `schedule` and `assignments` by `school_id` from the schedule row, not the user)
- **Description:** The route `@router.post("/smart-scheduling/generate/{school_id}")` only checks role (`PLATFORM_ADMIN, SCHOOL_PRINCIPAL, SCHOOL_ADMIN`) but not whether the caller belongs to that school. A principal of school A can call `/smart-scheduling/generate/SCHOOL_B` and trigger generation in school B's data. The engine itself trusts the `school_id` it receives.
- **Why it matters:** Multi-tenant boundary leak — a principal of one school can mutate (and overwrite) another school's draft timetable. This is a direct RBAC hole.
- **Recommended fix:** Inside the route, assert `current_user["role"] == PLATFORM_ADMIN or current_user["school_id"] == school_id` before delegating; also pass user tenant into the engine and re-assert there. Same fix needed on `generate_timetable_smart` and `pre-check`/`demand-matrix`/`resource-matrix`/`validate` routes.
- **Effort:** S
- **Status:** ✅ Remediated 2026-04-17 (Batch 1 plan: docs/superpowers/plans/2026-04-17-timetable-remediation-batch1.md)

#### F-EN-07 — Conflict detection is duplicated and inconsistent
- **Severity:** Medium
- **Location:** `backend/engines/smart_scheduling_engine.py:1180-1219` (in-process post-generation safety check) vs `1412-1498` (Phase 7 `detect_conflicts`) — both run on the same data; `backend/services/scheduling_service.py:173-256` (`detect_all_conflicts` for `schedule_sessions`); `backend/routes/scheduling_generation_routes.py:319-460` (yet another conflict-detection implementation against `schedule_sessions`); `backend/routes/scheduling_smart_session_routes.py:79-108,236-270` (per-edit conflict checks)
- **Description:** Four implementations of teacher/class collision detection coexist. The smart engine never checks **room/classroom collisions** at all (room_id is set to `None` in `services/scheduling_service.py:388` and is not even stored on `TimetableSession`). The legacy `_check_session_conflicts` checks `teacher_overlap` and `section_overlap` only. The Phase 7 detector and the in-loop "final safety check" both run, doubling work.
- **Why it matters:** Room double-booking is undetectable in the smart engine output, and duplication means a fix applied to one detector is missed by the other.
- **Recommended fix:** Extract a single `ConflictDetector.detect(sessions)` returning teacher/class/room conflicts; call it once after generation; add `room_id` to `TimetableSession` placement.
- **Effort:** M

#### F-EN-08 — Hard constraints loaded but never matched against `validation_key`
- **Severity:** Medium
- **Location:** `backend/engines/smart_scheduling_engine.py:1927-1928,995-1005` (constraint dispatch only checks `rule_key in {"no_first_period","no_last_period"}`)
- **Description:** Phase 5 loads every `timetable_hard_constraints` row (`is_system=True`) and merges with school constraints, but the placement loop only handles two literal `rule_key` values. The `validation_key` column populated by the seeder (see F-SD-03) is never read. New hard constraints added by an admin via the UI are silently ignored unless their `rule_key` is one of the two hard-coded strings.
- **Why it matters:** Admins believe they have configured a constraint; the engine ignores it; conflicts go undetected. This is the single biggest gap between "constraint configured" and "constraint enforced".
- **Recommended fix:** Replace the if-chain with a registry of `validation_key -> Callable(session, context) -> bool` and require every constraint row to map to a validator; reject seeding constraints whose key has no validator.
- **Effort:** M
- **Status:** ✅ Remediated 2026-04-17 (Batch 2 plan: docs/superpowers/plans/2026-04-17-timetable-remediation-batch2.md)

#### F-EN-09 — Engine has no awareness of the rich constraint model
- **Severity:** High
- **Location:** `backend/engines/smart_scheduling_engine.py:849-1225` (Phase 6 placement)
- **Description:** Placement only consults: teacher availability, weekly_load, teacher×slot uniqueness, class×slot uniqueness, and the two hardcoded period-bans above. It does not consult: `subject_must_use_room`, `consecutive_lessons_limit`, `daily_subject_limit`, `morning_only_subjects`, `teacher_max_consecutive`, `pinned_sessions`, `unavailable_periods` from `time_slots.is_break/is_prayer`, `room_capacity`, `multi-class lectures`, `gender_segregation`, etc. The capacity analysis (`_analyze_capacity_issues`, line 1304) computes statistics but does not feed them back into placement.
- **Why it matters:** The "smart" label is misleading — generation is single-pass greedy with two soft-constraint scoring tweaks, then conflicts are catalogued rather than resolved. For real schools this produces low-quality timetables that will be heavily edited manually.
- **Recommended fix:** Adopt a CSP / OR-Tools backbone (or at minimum backtracking with constraint propagation); accept the full constraint set as input; integrate `_analyze_capacity_issues` warnings into a pre-generation infeasibility report so users fix data before runs.
- **Effort:** L
- **Status:** 🟡 Partially Remediated 2026-04-17 (Batch 2: pre-generation infeasibility report INF-01..INF-05 with 422 gating shipped; CSP/backtracking rewrite deferred to Batch 3)

#### F-EN-10 — Quadratic / cubic scans inside the placement loop
- **Severity:** Medium
- **Location:** `backend/engines/smart_scheduling_engine.py:909-1051` (per demand × period × suitable_teacher), `979-994` (inner re-scan of `teaching_period_numbers` to compute `filled_periods` for every candidate), `1068-1167` (second full pass: every class × every day × every period × every demand × every teacher), `1095-1099` (rebuilds `subject_session_counts` per outer iteration)
- **Description:** The two placement passes are O(D · P · T) and O(C · D · P · D · T), and within each candidate evaluation the loop *recomputes* `filled_periods` (O(P)) and `subject_session_counts` (O(|sessions|)). For a typical school (40 classes, 30 demands/class, 5 days, 7 periods, 5 candidate teachers/subject) the inner work approaches 10⁷ ops, all in Python.
- **Why it matters:** Together with F-EN-03 (no timeout) this is the primary cause of slow generation and the reason the engine cannot be made deterministic-with-backtracking later.
- **Recommended fix:** Maintain incremental indexes (`class_subject_count`, `class_filled_periods_per_day`); precompute `teacher_available[(day,period)] -> set[teacher_id]`; replace the second pass with targeted gap-filling on the unscheduled list.
- **Effort:** M

#### F-EN-11 — Persistence is non-atomic across multiple tables
- **Severity:** High
- **Location:** `backend/engines/smart_scheduling_engine.py:1983-2020` (sequential `gd_insert(timetables)` → `gd_insert_many(timetable_sessions)` → `gd_insert_many(timetable_conflicts)` → `gd_insert_many(timetable_unscheduled_demands)` → `gd_update_one(timetable_runs)`)
- **Description:** The five writes are not wrapped in a single transaction. Any error between them (DB hiccup, validation rejection, worker death) leaves the timetable row without sessions, or sessions without their conflict log, or the run record stuck mid-generation. The legacy generator (`scheduling_service.py:411-415`) has the same pattern.
- **Why it matters:** Partial writes corrupt the UI ("timetable exists but has zero sessions"); manual cleanup requires DBA intervention.
- **Recommended fix:** Wrap the persistence block in `async with self.session.begin():`; on any exception, rollback and mark the run `FAILED`. Confirm the underlying `gd_*` helpers honour the surrounding transaction.
- **Effort:** S

#### F-EN-12 — `version` is hard-coded to 1; no draft-vs-published linkage
- **Severity:** Medium
- **Location:** `backend/engines/smart_scheduling_engine.py:1978` (`"version": 1`), `2117-2138` (`publish_timetable` flips status to `published` but does not bump version, copy-on-write, or supersede prior published timetable)
- **Description:** Every generated timetable starts at version 1; publishing the second timetable does not demote the first. There is no `superseded_by` / `effective_from` field. The "active timetable" lookup (`scheduling_smart_engine_routes.py:282-288`) just picks any row with `status=published` — the first one returned by the DB.
- **Why it matters:** Two published timetables can coexist for the same school; teachers/students may see either depending on query ordering. Version history exists in the schema but is unused.
- **Recommended fix:** On publish, archive the previous published timetable for the same `(school_id, academic_year, semester)`; bump version per generation in that scope; persist `effective_from`/`effective_to`.
- **Effort:** M

#### F-EN-13 — Errors are returned as free-text strings, not structured codes
- **Severity:** Medium
- **Location:** `backend/engines/smart_scheduling_engine.py:1899-1901,2065-2067` (returns `message_ar`/`message_en` strings only), `backend/routes/scheduling_smart_engine_routes.py:188-191` (`except Exception: raise HTTPException(500, "فشل في توليد الجدول")` — masks the real error), `backend/routes/scheduling_generation_routes.py:60,69,90` (`HTTPException` with Arabic-only string detail)
- **Description:** Generation failures surface as Arabic strings without an `error_code`, no machine-readable issue list, and (in `generate-smart`) the original exception is swallowed. `UnscheduledDemand.reason_ar` ("لم يتوفر وقت أو معلم مناسب") is a generic catch-all that does not tell the user *which* constraint blocked placement.
- **Why it matters:** Frontend cannot branch on error type; support cannot triage; user sees "generation failed" with no actionable next step.
- **Recommended fix:** Define an `ErrorCode` enum (`NO_TEACHERS_FOR_SUBJECT`, `INSUFFICIENT_SLOTS`, `TEACHER_AVAILABILITY_EMPTY`, ...); attach to every `UnscheduledDemand` and to `GenerationResult`; surface the original exception (sanitised) in `message_en`.
- **Effort:** M

#### F-EN-14 — `generate_timetable_smart` swallows all exceptions
- **Severity:** Medium
- **Location:** `backend/routes/scheduling_smart_engine_routes.py:188-191`
- **Description:** `except Exception as e: raise HTTPException(status_code=500, detail="فشل في توليد الجدول")` — the original traceback is not logged and not surfaced. Any TypeError, KeyError or constraint violation looks identical to a network blip.
- **Why it matters:** Production debugging is impossible; users get a meaningless 500.
- **Recommended fix:** Log `e` with `logger.exception(...)`; include `error_id` (uuid) in the response so users can quote it to support; do not catch the exception at all if the engine already returns a structured `GenerationResult` with `success=False`.
- **Effort:** S

#### F-EN-15 — `random` is imported into routes that no longer use it
- **Severity:** Low
- **Location:** `backend/routes/scheduling_smart_engine_routes.py:11`, `backend/routes/scheduling_smart_session_routes.py:11`, `backend/routes/scheduling_generation_routes.py:11`
- **Description:** Module-level `import random` (and several other unused imports: `re`, `io`, `base64`, `Header`) appear in three of the scheduling routes. Only `scheduling_generation_routes.py` actually uses `random` (re-imported inside the function at line 53). Smart-engine and session routes never call any RNG.
- **Why it matters:** Cleanup; reduces audit surface.
- **Recommended fix:** Remove unused imports.
- **Effort:** S

#### F-EN-16 — Test suite does not cover failure modes
- **Severity:** High
- **Location:** `backend/tests/test_smart_scheduling.py:413-444` (only happy-path generation), `backend/tests/test_smart_timetable_page.py:33-219` (read-only)
- **Description:** The two test files only assert that endpoints return 200 with the expected response keys. There is **no** test for: determinism (re-run produces same output), cross-tenant access (principal A calling school B), concurrent generation, timeout behaviour, room conflicts, hard-constraint enforcement (F-EN-08), partial-data cases (no teachers, no time slots), atomicity on failure (F-EN-11), publish with critical conflicts blocked, version supersession. Tests rely on a live backend (`BASE_URL`), hard-coded principal credentials, and a known `SCH-001` school.
- **Why it matters:** Every finding in this section can regress without any test failure. Coverage is essentially smoke-tests, not behavioural tests.
- **Recommended fix:** Add unit tests against an in-memory engine with mocked DB; cover each failure mode above; convert `test_smart_scheduling.py` into integration tests gated by env, and add unit tests for the engine class directly.
- **Effort:** L

#### F-EN-17 — `models/scheduling.py` vs `shared_models.py` divergence affects engine outputs
- **Severity:** Medium
- **Location:** `backend/services/scheduling_service.py:18-26` (imports `DayOfWeek` from `models.scheduling`), `backend/engines/smart_scheduling_engine.py` (uses string literals `"sunday"..."thursday"` and its own `DayOfWeek` enum at line ~50), `backend/routes/scheduling_generation_routes.py:29` (imports `SessionStatusEnum, ScheduleStatusEnum` from `shared_models`)
- **Description:** Three different day/status enums are used across the engines and the routes that talk to them. `SchedulingService` writes `day_of_week` from `DayOfWeek.value` (English lowercase), the smart engine writes the same English strings but its `working_days` default is also English lowercase, and `shared_models` declares an Arabic-day enum (already noted in F-DM-04). When the route layer instantiates models, it can silently coerce or reject sessions.
- **Why it matters:** Compounds the data-model divergence (F-DM-04) at the engine layer; sessions written by one engine may fail Pydantic validation when read by another route.
- **Recommended fix:** As part of F-DM-04 / F-EN-01 consolidation, move all enums to one module and import from there.
- **Effort:** S

### 3.5 API routes
_Files inspected:_
- `backend/routes/scheduling_core_routes.py`
- `backend/routes/scheduling_generation_routes.py`
- `backend/routes/scheduling_routes.py`
- `backend/routes/scheduling_smart_engine_routes.py`
- `backend/routes/scheduling_smart_session_routes.py`
- `backend/routes/principal_timetable_routes.py`
- `backend/routes/timetable_readiness_routes.py`
- `backend/routes/schedule_management_routes.py`
- `backend/dependencies.py` (auth wiring: `get_current_user`, `require_roles`)
- `backend/middleware/tenant_isolation.py` (defines `TenantIsolation` helpers — **not** wired as global middleware)
- `backend/middleware/rbac.py` (defines `Permission`, `require_permission` decorator — **not** wired into scheduling routes)

_Tenant middleware verdict:_ **Confirms F-EN-06.** `backend/middleware/tenant_isolation.py` exists and exports `TenantIsolation`, `tenant_scoped`, `validate_resource_tenant`, and `TenantAwareQuery`, but a grep across all eight scheduling/timetable route modules shows **zero usages** — none of them import from `middleware.tenant_isolation` or apply `tenant_scoped`/`validate_resource_tenant` decorators. The `require_roles` dependency in `backend/dependencies.py:288-293` only checks `current_user["role"]` against an allow-list and performs **no** tenant binding. Tenant scoping in scheduling routes is therefore entirely manual, per-endpoint, and inconsistent (see F-API-01, F-API-02 below).

_Findings:_

#### F-API-01 — Generation, publish, validate, conflicts, and version endpoints accept any `school_id` / `timetable_id` from any authenticated user (cross-tenant scope hole)
- **Severity:** Critical
- **Location:** `backend/routes/scheduling_smart_engine_routes.py:83-110` (`/smart-scheduling/validate/{school_id}`), `:114-143` (`/smart-scheduling/generate/{school_id}`), `:194-209` (`/smart-scheduling/timetables/{school_id}`), `:321-335` (`/smart-scheduling/timetable/{timetable_id}`), `:338-379` (`/smart-scheduling/timetable/{timetable_id}/sessions`), `:382-400` (`/smart-scheduling/timetable/{timetable_id}/conflicts`), `:422-448` (`/smart-scheduling/timetable/{timetable_id}/publish`), `:451-474` (archive), `:477-511` (pre-check), `:514-587` (demand & resource matrices), `:590-625` (delete)
- **Description:** Every one of these endpoints receives `school_id` or `timetable_id` directly from the URL path and passes it straight into the engine / database without verifying that the caller's `tenant_id`/`school_id` matches the resource's tenant. The role check (`require_roles([PLATFORM_ADMIN, SCHOOL_PRINCIPAL, SCHOOL_ADMIN])`) blocks teachers/students but **does not** prevent a `school_principal` of school A from generating, viewing, publishing, or deleting timetables for school B simply by guessing/seeing another school's UUID. There is no `current_user["tenant_id"] == school_id` guard, no use of `TenantIsolation.validate_tenant_access`, and no global tenant middleware (verified above).
- **Why it matters:** Direct multi-tenant data-leak / cross-tenant write hole. Any school principal can read another school's draft and published timetables, trigger expensive AI generation runs against them, publish them (overwriting the legitimate school's published version since publish flips status), or delete them. This is the concrete realization of the concern flagged in F-EN-06.
- **Recommended fix:** Add a tenant guard at the top of every `school_id`-bearing endpoint: `if current_user.get("role") != UserRole.PLATFORM_ADMIN.value and current_user.get("tenant_id") != school_id: raise HTTPException(403, ...)`. For `timetable_id`-bearing endpoints, fetch the timetable first and compare `timetable["school_id"]` to the user's tenant. Better: wire `middleware/tenant_isolation.py`'s `validate_resource_tenant` decorator (already implemented) onto the scheduling router, or include it in `require_roles`.
- **Effort:** M
- **Status:** ✅ Remediated 2026-04-17 (Batch 1 plan: docs/superpowers/plans/2026-04-17-timetable-remediation-batch1.md)

#### F-API-02 — Principal-timetable router authenticates by raw JWT decode and skips role enforcement
- **Severity:** Critical
- **Location:** `backend/routes/principal_timetable_routes.py:171-190` (`get_school_id` decodes JWT directly), and **every** `@router.*` handler in the file (e.g. `:220-283` summary, `:290-364` readiness, `:371-417` versions, `:541-657` grid, `:869-953` `/generate`, `:1104-1287` `/version/{id}/publish`, `:1531-1739` `/version/{id}/fill-gaps`, `:1755-1857` `/sessions/swap`, `:1859-1947` `/sessions/move`, `:1948-1962` `/session/{id}`)
- **Description:** Not a single endpoint in this 1,962-line router uses `Depends(get_current_user)` or `Depends(require_roles(...))`. Authorization is performed only by `get_school_id`, which (a) trusts a `X-School-Context` header verbatim, (b) falls back to a hand-rolled `jwt.decode(..., _JWT_SECRET, ...)` that does not check `type=="access"`, JTI revocation, account lock, `is_active`, or impersonation flags (all of which `dependencies.get_current_user` enforces), and (c) returns the school_id from the token unconditionally. There is no role check at all — a `teacher`, `student`, `parent`, or even a refresh-token-bearing client can call `POST /principal/timetable/generate`, `POST /version/{id}/publish`, `POST /sessions/swap`, etc.
- **Why it matters:** A principal-only, security-sensitive UI surface (generate/publish/delete/swap timetable) is in practice authenticated as "anyone with any valid token plus an `X-School-Context` header". Combined with the missing tenant check on `X-School-Context`, anyone holding a valid login can publish, archive, or rewrite the timetable for any school whose UUID they know, including via revoked tokens.
- **Recommended fix:** Replace the hand-rolled JWT decode with `current_user: dict = Depends(get_current_user)` on every handler, derive `school_id` from `current_user["tenant_id"]` (or validate `X-School-Context` against it for platform admins only), and gate write endpoints with `Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL]))`.
- **Effort:** M
- **Status:** ✅ Remediated 2026-04-17 (Batch 1 plan: docs/superpowers/plans/2026-04-17-timetable-remediation-batch1.md)

#### F-API-03 — `timetable_readiness_routes` uses the same trust-header / raw-JWT pattern with no role check
- **Severity:** High
- **Location:** `backend/routes/timetable_readiness_routes.py:22-23` (module-level JWT secret), `:102-118` (`_extract_school_id`), `:496-506` (`/timetable-readiness/check`), `:507-539` (`/summary`)
- **Description:** Mirror of F-API-02 on a smaller surface. No `Depends(get_current_user)` is used; `school_id` is taken from `X-School-Context` or a manually-decoded JWT. Any authenticated user (or anyone with a guessable school UUID and a valid token) can run readiness checks — these are read-only but expose internal data-quality issues, missing teachers, missing assignments, and capacity gaps for arbitrary schools.
- **Why it matters:** Information disclosure across tenants; also bypasses the centralized account-lock / token-revocation checks in `dependencies.get_current_user`.
- **Recommended fix:** Add `current_user: dict = Depends(get_current_user)` and tenant binding identical to F-API-02 fix.
- **Effort:** S
- **Status:** ✅ Remediated 2026-04-17 (Batch 1 plan: docs/superpowers/plans/2026-04-17-timetable-remediation-batch1.md)

#### F-API-04 — Tenant scoping on list/get endpoints uses `current_user["tenant_id"]` only when `school_id` query param is missing — a caller can override by passing any `school_id`
- **Severity:** Critical
- **Location:** `backend/routes/scheduling_core_routes.py:59-71` (`GET /time-slots`), `:196-215` (`GET /teacher-assignments`), `:350-367` (`GET /schedules`), `:465-512` (`GET /schedule-sessions`)
- **Description:** Pattern: `if school_id: query["school_id"] = school_id; elif current_user.role != PLATFORM_ADMIN: query["school_id"] = current_user.tenant_id`. The `if` branch trusts the URL/query param as ground truth and the user's actual tenant is never compared. A school_principal of school A can call `GET /teacher-assignments?school_id=<school-B-uuid>` and receive school B's data.
- **Why it matters:** Direct cross-tenant read of teacher assignments, schedules, schedule sessions, and time slots — i.e. who teaches what to whom in another school.
- **Recommended fix:** Always derive `school_id` from `current_user.tenant_id`; only allow override when `current_user.role == PLATFORM_ADMIN`. Or call `TenantIsolation.apply_tenant_filter(query, current_user, "school_id")`.
- **Effort:** S
- **Status:** ✅ Remediated 2026-04-17 (Batch 1 plan: docs/superpowers/plans/2026-04-17-timetable-remediation-batch1.md)

#### F-API-05 — `POST /smart-scheduling/generate` and `POST /principal/timetable/generate` are non-idempotent — every retry creates a new timetable row plus a full sessions write
- **Severity:** High
- **Location:** `backend/routes/scheduling_smart_engine_routes.py:114-143`, `:147-191`; `backend/routes/principal_timetable_routes.py:869-953`
- **Description:** The route handlers accept no idempotency key, perform no de-duplication, and the underlying `smart_scheduling_engine.generate_timetable` is invoked unconditionally. A double-click, a network retry, or a celery-style retry produces parallel timetable drafts each containing thousands of `timetable_sessions` rows.
- **Why it matters:** Heavy AI generation is run twice (cost + latency); the principal's UI ends up with multiple mostly-identical "draft" versions; later publish operations may pick the wrong one. Also creates concurrent write races on `timetable_sessions` if two runs interleave.
- **Recommended fix:** Accept an `Idempotency-Key` header or a request-scoped `request_id`; before generating, check for an in-progress run for `(school_id, academic_year, term_id)` in `timetable_runs` and either return the existing run or 409. Add an advisory DB lock (`pg_advisory_xact_lock(school_id_hash)`) for the generation transaction.
- **Effort:** M

#### F-API-06 — `POST /version/{id}/publish` is non-idempotent and side-effects (snapshot insert, archive of previous, audit log) are not transactional
- **Severity:** High
- **Location:** `backend/routes/principal_timetable_routes.py:1104-1287`
- **Description:** Handler (a) archives all currently-published timetables, (b) inserts a `published_timetables` snapshot, (c) updates `timetables.status="published"`, (d) inserts an `audit_logs` row. Each is a separate DB call without a transaction. A retry after partial failure will: archive again (idempotent), insert a *second* snapshot row with a new UUID, and then (depending on engine path) double-publish. Snapshot insert failure is swallowed (`logger.error`, `snapshot_saved=False`) yet publish proceeds anyway, leaving a published timetable with no snapshot.
- **Why it matters:** Duplicate snapshots in `published_timetables` corrupt the "official archive"; users see two snapshots for the same publish event. Loss of snapshot is silent — historical record is incomplete. Also no idempotency-key protection.
- **Recommended fix:** Wrap the sequence in a single SQL transaction; key the snapshot by `(timetable_id, published_at)` with a unique constraint to make retries safe; fail (don't fall through) if snapshot insert fails.
- **Effort:** M

#### F-API-07 — List endpoints return entire collections without pagination
- **Severity:** Medium
- **Location:** `backend/routes/scheduling_core_routes.py:71` (time_slots `limit=50`), `:215` (teacher_assignments `limit=500`), `:366` (schedules `limit=100`), `:480` (schedule_sessions `limit=1000`); `backend/routes/scheduling_smart_engine_routes.py:234` (timetables `limit=100`), `:298` (active sessions `limit=1000`); `backend/routes/principal_timetable_routes.py:1179` (`limit=50000` snapshot fetch)
- **Description:** Every "list" endpoint hard-codes a `limit=` and exposes no `skip`/`cursor` parameter. For a school with ≥7 periods × 5 days × 30 classes ≈ 1,050 sessions, the active-sessions endpoint just barely fits under its 1000 cap and silently truncates beyond that. The publish snapshot fetches up to 50,000 sessions in one round-trip and embeds them in a single `published_timetables` JSONB column.
- **Why it matters:** Quiet truncation hides data ("where did my sessions go?"), large response payloads cause 5–30 second latencies on big schools, and the 50k snapshot inflates the row to MBs. No way for a frontend to page through.
- **Recommended fix:** Add cursor pagination (`?after=<id>&limit=100`) and remove the silent truncation; for the snapshot, store sessions in a side table referenced by snapshot id rather than a JSON blob.
- **Effort:** M

#### F-API-08 — N+1 queries while enriching session lists, conflict details, and demand matrix
- **Severity:** Medium
- **Location:** `backend/routes/scheduling_smart_engine_routes.py:300-318` (active sessions enrichment loops `gd_find_one("teachers"|"classes"|"grades")` per session), `:358-379` (`/timetable/{id}/sessions` does up to 4 `gd_find_one` per session including a fallback to `reference_subjects`), `:528-547` (demand matrix loops `gd_find_one("subjects"|"reference_subjects")` per subject per class); `backend/routes/principal_timetable_routes.py:1040-1056` (validation loops `gd_find_one("timetable_sessions")` per `class × day × period`)
- **Description:** Classic N+1 pattern: instead of pre-loading all teachers/subjects/classes once and joining in memory, the routes call `gd_find_one` per row. The principal validate-publish endpoint executes ~`classes × working_days × periods` lookups (≈30×5×7 = 1,050 round-trips for a small school) just to count empty slots.
- **Why it matters:** Pages that should render in <500 ms take 5–30 s; on a school with ~30 classes the validate-publish call alone is >1 s of pure round-trip overhead and scales linearly with school size.
- **Recommended fix:** Bulk-fetch related entities once (`gd_find("teachers", {"id": {"$in": teacher_ids}})`), build dict maps, and join in memory; for the empty-slot check, replace the triple loop with a single aggregation: `SELECT (class_id, day, period) FROM timetable_sessions WHERE timetable_id=? GROUP BY ...` and subtract from the cartesian product.
- **Effort:** M

#### F-API-09 — `POST /smart-scheduling/session/add` uses query parameters instead of a Pydantic body model
- **Severity:** Medium
- **Location:** `backend/routes/scheduling_smart_engine_routes.py:403-495`
- **Description:** Mutating endpoint takes `timetable_id, class_id, subject_id, teacher_id, day_of_week, period_number` as **query parameters** (function signature with no `Body(...)` wrapper), bypassing the project's Pydantic-request convention used everywhere else in the file. No validation of `day_of_week` enum or `period_number` range.
- **Why it matters:** Invalid days/periods bypass validation, request bodies are not auditable in API docs, and the endpoint is fragile to future signature changes. Inconsistent with the rest of the file (e.g. `UpdateSmartSessionRequest`, `SwapSessionsRequest`).
- **Recommended fix:** Wrap parameters in a `BaseModel` with a `DayOfWeek` enum and `period_number: int = Field(ge=1, le=10)`.
- **Effort:** S

#### F-API-10 — Inconsistent / wrong HTTP status codes on conflict and validation errors
- **Severity:** Medium
- **Location:** `backend/routes/scheduling_smart_engine_routes.py:438-441` (publish-with-conflicts returns 400, should be 409/422), `:603-607` (delete published returns 400 instead of 409), `backend/routes/scheduling_core_routes.py:421` (duplicate session returns 400 instead of 409), `backend/routes/principal_timetable_routes.py:921` (engine `success=False` returns 422 — correct), `:1120,1131,1142` (publish blocked by conflicts returns 422 — correct)
- **Description:** Inconsistent semantics: some "resource conflict" cases return 400, others 409, others 422. The smart-engine routes never return 409 even when the failure is a true write-conflict (duplicate, publish-with-conflicts, delete-published). The principal routes correctly use 422 for "publishable invariants violated", so the codebase is internally inconsistent.
- **Why it matters:** Frontend cannot reliably distinguish "bad input" (400/422) from "state conflict" (409); makes generic error handling impossible and forces string parsing of `detail`.
- **Recommended fix:** Adopt a single convention: 400 for malformed request, 422 for semantically invalid (Pydantic-style), 404 for missing, 409 for state conflicts (already-exists / cannot-modify-published / publish-with-conflicts).
- **Effort:** S

#### F-API-11 — Most endpoints return raw `dict` instead of declared `response_model`s, hiding output schema
- **Severity:** Medium
- **Location:** `backend/routes/scheduling_smart_engine_routes.py:83-625` (all endpoints return ad-hoc dicts despite three `BaseModel`s being declared at lines 43-79), `backend/routes/scheduling_smart_session_routes.py:50-495` (all return dicts), `backend/routes/principal_timetable_routes.py:220-1962` (every handler returns ad-hoc `{"success": True, "data": {...}}`), `backend/routes/timetable_readiness_routes.py:496-539`
- **Description:** Despite `SmartTimetableResponse`, `SmartTimetableSessionResponse`, `ReadinessIssue`, and `CategoryReadiness` being defined, no handler uses `response_model=`. OpenAPI shows opaque dicts; frontend has no contract; field renames break silently.
- **Why it matters:** No contract enforcement → quiet schema drift breaks the React frontend; hides excessive fields (potential PII over-exposure); makes future Pydantic-v2 / API-versioning migration painful.
- **Recommended fix:** Define explicit response models for each endpoint and add `response_model=` to the route decorator; reject unknown fields with `model_config = ConfigDict(extra='forbid')` for inputs.
- **Effort:** M

#### F-API-12 — Audit logging is inconsistent across timetable lifecycle (generate/publish/delete/archive)
- **Severity:** Medium
- **Location:** `backend/routes/scheduling_smart_engine_routes.py:114-143` (generate — no audit insert), `:422-448` (publish — no audit insert; delegated to engine), `:451-474` (archive — no audit), `:590-625` (delete — no audit), `:381-400` (delete session — no audit); contrast with `backend/routes/scheduling_core_routes.py:167-182` and `:303-318` which **do** insert into `audit_logs` for teacher_assignment create/delete; and `backend/routes/principal_timetable_routes.py:1255-1270` which writes a publish audit row.
- **Description:** Critical security/compliance actions (timetable generation, smart-engine publish, smart-engine delete/archive, session delete/move/swap) write nothing to `audit_logs`. The principal-router publish path does, but the parallel smart-engine publish path does not. Given there are two publish endpoints (F-API-13), one publish leaves an audit trail and the other does not.
- **Why it matters:** No accountability for who generated/published/deleted a timetable when the smart-engine path is used; impossible to investigate "who published this version" or "who wiped the draft".
- **Recommended fix:** Centralize an `audit_engine.log_action(...)` call in the engine layer (so both route entry-points share the audit record), with action codes `TIMETABLE_GENERATED`, `TIMETABLE_PUBLISHED`, `TIMETABLE_DELETED`, `SESSION_MOVED`, etc.
- **Effort:** S

#### F-API-13 — Duplicate, divergent endpoints for the same concept (time-slots, schedules/publish, generate, swap/move, sessions list)
- **Severity:** Medium
- **Location:** `backend/routes/scheduling_routes.py:127-477` (factory router, prefix `/scheduling`) defines `POST /time-slots`, `POST /schedules`, `POST /schedules/{id}/generate`, `POST /sessions`, etc.; `backend/routes/scheduling_core_routes.py:35-400` redefines `POST /time-slots`, `POST /schedules`, `PUT /schedules/{id}/publish`, `POST /schedule-sessions`; `backend/routes/scheduling_generation_routes.py:35-90` defines `POST /schedules/{id}/generate` again; `backend/routes/scheduling_smart_engine_routes.py:114-191` defines two different generate endpoints (`/smart-scheduling/generate/{school_id}` and `/timetable/generate-smart`) using the same engine call; `principal_timetable_routes.py:869` defines a third `/principal/timetable/generate`; swap/move logic exists three times (smart_session_routes:193 & 304, principal_timetable_routes:1755 & 1859).
- **Description:** Multiple route modules define overlapping endpoints with divergent auth, divergent payload shapes, divergent tenant handling, and divergent audit logging. `scheduling_routes.py` reads `current_user.tenant_id` correctly but is a factory wired separately; `scheduling_core_routes.py` accepts `school_id` in body/query and trusts it; `principal_timetable_routes.py` reads it from a header.
- **Why it matters:** Confusing API surface, redundant maintenance burden, security gaps (e.g. fix to F-API-04 must be applied in 3 places), and risk of behavior divergence (e.g. one swap path checks tenant, the other doesn't — see `scheduling_smart_session_routes.py:213-216` vs principal swap at `principal_timetable_routes.py:1755-1810`).
- **Recommended fix:** Pick a canonical router per concept (time-slots → core; generate → smart engine; publish → principal); deprecate the duplicates with a clear sunset; add request-id-based metrics to confirm which paths are still in use.
- **Effort:** L

#### F-API-14 — Module-level mutable `db` / `smart_engine` globals injected via `set_db()` / `set_engine()` — dangerous for testability and multi-process safety
- **Severity:** Low
- **Location:** `backend/routes/principal_timetable_routes.py:22-31`, `backend/routes/timetable_readiness_routes.py:29-33`
- **Description:** Both routers stash a global `db = None` and `smart_engine = None` and rely on a `set_db(...)` / `set_engine(...)` call at startup. If these are not called (test harness, lazy import, hot reload), every endpoint NPEs at first DB access. No defensive `if db is None: raise HTTPException(503)` guard at the module level (only `principal_timetable_routes.py:879-880` checks `smart_engine`).
- **Why it matters:** Fragile dependency injection; tests must remember to call `set_db`. Other routers (e.g. `scheduling_core_routes.py`) import `db` from `dependencies` directly — inconsistent pattern.
- **Recommended fix:** Replace with `from dependencies import db, smart_scheduling_engine` consistent with the rest of the codebase; remove the module-level globals.
- **Effort:** S

#### F-API-15 — `schedule_management_routes.py` performs role-checking inline rather than via `require_roles`, and has no tenant ownership check
- **Severity:** Medium
- **Location:** `backend/routes/schedule_management_routes.py:84-138` (`POST /schedules/create`), `:140-177` (`GET /schedules/{id}`)
- **Description:** `create_schedule` does `if current_user.get("role") not in ["platform_admin","school_principal","school_sub_admin"]: raise 403` — a hand-rolled allow-list, bypassing `require_roles`. `get_schedule` and `get_class_schedule` only filter `engine.get_schedule(schedule_id, tenant_id)` by the caller's tenant, but the corresponding `engine` implementation isn't visible from the route — the route trusts the engine to honor tenant_id. The schedule list endpoint has no role gate at all (any user can list schedules).
- **Why it matters:** Inconsistent with project-wide RBAC pattern; fragile if engine signature changes; the inline allow-list omits `school_admin` for unclear reasons (admin can't create schedules?).
- **Recommended fix:** Replace with `current_user: dict = Depends(require_roles([...]))`; explicitly assert in the route that fetched resource's `tenant_id == current_user.tenant_id` rather than relying on engine convention.
- **Effort:** S

#### F-API-16 — `/smart-scheduling/timetable/versions` and `/active/sessions` derive `school_id` from the `X-School-Context` header without role-gating
- **Severity:** High
- **Location:** `backend/routes/scheduling_smart_engine_routes.py:213-255`, `:258-318`
- **Description:** Both endpoints accept `x_school_context` header verbatim, falling back to `current_user["school_id"]` then a scan of `current_user["roles"]`. There is no validation that the user actually belongs to the supplied `school_id`. A teacher of school A can pass `X-School-Context: <school-B-uuid>` and read school B's timetable versions or active sessions.
- **Why it matters:** Read-side multi-tenant leak of the entire active timetable for any school whose UUID is known.
- **Recommended fix:** Reject `x_school_context` unless `current_user.role == PLATFORM_ADMIN` or `x_school_context == current_user.tenant_id`.
- **Effort:** S
- **Status:** ✅ Remediated 2026-04-17 (Batch 1 plan: docs/superpowers/plans/2026-04-17-timetable-remediation-batch1.md)

#### F-API-17 — Manual session edit/move/swap and "force update" allow `source_type="hybrid_adjusted"` writes against published timetables in the smart-engine routes
- **Severity:** High
- **Location:** `backend/routes/scheduling_smart_engine_routes.py:50-155` (update, no published-check), `:158-190` (force update, no check), `:381-400` (delete session, no published-check), `:403-495` (add manual session, no published-check); contrast with `:218-220` (swap blocks published) and `principal_timetable_routes.py:1778` (swap blocks published)
- **Description:** Update, force-update, delete, and add-session endpoints in `scheduling_smart_engine_routes.py` never check whether the parent timetable is `published`. Only the `swap` and `move` endpoints in the same file and the principal-router equivalents block writes to a published timetable.
- **Why it matters:** A principal can silently mutate the official published timetable, breaking parent/teacher/student views without re-publishing or producing a new snapshot. The published `published_timetables` snapshot diverges from the live `timetable_sessions` rows (the snapshot was captured at publish time but live rows now drift).
- **Recommended fix:** At the top of each mutating handler, fetch the timetable and 409 if `status == "published"`; or only allow such edits to clone the timetable into a new draft.
- **Effort:** S

#### F-API-18 — `force_update_smart_session` exists with the same role gate as the conflict-checking variant — no second-factor / reason-required workflow
- **Severity:** Low
- **Location:** `backend/routes/scheduling_smart_engine_routes.py:158-190`
- **Description:** "Force update — ignore conflicts" is gated by the same `require_roles([PLATFORM_ADMIN, SCHOOL_PRINCIPAL, SCHOOL_ADMIN])` as the safe variant. There is no requirement for a justification field, no audit log entry recording that the conflict-check was bypassed, and no warning surfaced to other consumers.
- **Why it matters:** Silent override of conflict detection with no paper trail; teacher double-bookings created by force-update look identical in the DB to genuine generation errors.
- **Recommended fix:** Require `reason: str = Field(min_length=10)` in the request body, write an `audit_logs` row tagged `FORCE_OVERRIDE`, and mark the resulting session with `was_force_overridden=True`.
- **Effort:** S

#### F-API-19 — `dependencies.require_roles` does not bind to the requested tenant — role check is global
- **Severity:** Medium
- **Location:** `backend/dependencies.py:288-293`
- **Description:** `require_roles` only checks `current_user["role"] in allowed_roles`. It does not look at the URL `school_id`, the `X-School-Context` header, or the resource's tenant. A `school_principal` is "principal of every school" as far as this dependency is concerned, and a `platform_admin` impersonating a school via `X-School-Context` (see `dependencies.py:274-280`) drops their `original_role` into `is_impersonating` but the role checker still sees `platform_admin`. There is no companion `require_principal_of(school_id)` helper.
- **Why it matters:** Underlies F-API-01 / F-API-04 — every "tenant scoping" gap in scheduling routes traces to the fact that the auth dependency contains no tenant binding. Any future endpoint that follows the project pattern inherits the gap.
- **Recommended fix:** Add a `require_school_role(roles, school_id_param="school_id")` dependency that resolves the path/query/header `school_id`, looks up the user's tenant, and 403s on mismatch (unless platform admin). Migrate scheduling routes to it.
- **Effort:** M


### 3.6 Frontend wizards & pages
_Files inspected:_

Discovery query: `grep -rli -E "timetable|schedule" frontend/src/pages frontend/src/components | sort -u` (65 files matched). Files actually opened and reviewed:

- `frontend/src/components/wizards/CreateScheduleWizard.jsx`
- `frontend/src/pages/SchedulePageNew.jsx`
- `frontend/src/components/timetable/PrincipalTimetablePage.jsx`
- `frontend/src/components/timetable/TimetableGridSection.jsx`
- `frontend/src/pages/TimeSlotsPage.jsx`
- `frontend/src/pages/TeacherAssignmentsPage.jsx`
- `frontend/src/pages/TeacherModule/TeacherSchedulePage.jsx`
- `frontend/src/pages/ParentPortal/ChildSchedulePage.jsx`
- `frontend/src/pages/StudentPortal/StudentSchedulePage.jsx`

Other matches from the grep (e.g. `Sidebar.jsx`, `HakimAssistant.jsx`, `LandingPage.jsx`, `AdminDashboard.jsx`, `ParentDashboard.jsx`, `TeacherDashboard.jsx`, dashboard widgets, notification components, intervention components, `TenantsManagement.jsx`, `UsersClassesManagement.jsx`, `SchoolSettingsPagePro.jsx`, the rest of the `components/timetable/*` family) only reference scheduling tangentially (links, badges, navigation cards) and were not opened individually for this layer.

_Findings:_

#### F-FE-01 — School-level Arabic strings hard-coded throughout `SchedulePageNew`
- **Severity:** High
- **Location:** `frontend/src/pages/SchedulePageNew.jsx:101,134,143,144,158,267,295,301,305,310,324,337,352,357,424,428,432,450,454,459,518,540,543,547,556,557,559,571,582,594,604,640,653,673,680,694`
- **Description:** Almost every visible string on the school principal's main schedule screen is an Arabic literal embedded in JSX (`'الجدول المدرسي'`, `'لم يتم توليد جدول بعد'`, `'فشل تحميل البيانات'`, `'تم تبديل الحصتين بنجاح'`, `'انقل هنا ↓'`, toast messages, dialog titles, button labels, day names, status badges, error messages, drag-drop hints, etc.). The component imports `useTheme` but **does not** import `useTranslation`/`t` and never reads `en.json`/`ar.json`. The same is true of every Arabic literal in `SchedulePageNew`'s `DAYS` constant and the `BreakRow` / `EmptyCell` helpers.
- **Why it matters:** The English locale is broken on the most-used principal page — switching to English leaves dozens of strings in Arabic, breaking the bilingual contract advertised by the rest of the app. It also means any future copy change has to be done in JSX rather than locale files, increasing drift between `en.json` and `ar.json`.
- **Recommended fix:** Inject `const { t } = useTranslation();`, replace every literal with a `t()` key, and add the keys to both `en.json` and `ar.json`. As a regression test, add an ESLint rule (or simple grep in CI) flagging non-ASCII literals in JSX text nodes for files under `frontend/src/pages/`.
- **Effort:** M

#### F-FE-02 — `TeacherSchedulePage` renders Arabic-only strings even in English mode
- **Severity:** Medium
- **Location:** `frontend/src/pages/TeacherModule/TeacherSchedulePage.jsx:29-37,73-77,192,285,286,433,438,450,460,474`
- **Description:** Color tables and badges are keyed by Arabic subject names (`'اللغة العربية'`, `'الرياضيات'`, …) so an English-named subject always falls through to the neutral palette. Status badge labels (`'الحصة الحالية'`, `'قادمة'`, `'مكتملة'`), conflict text, the print/CSV column headers (`isRTL ? 'اليوم' : 'Day'` pattern), and the "Current Session"/"Start Session" button labels use inline ternaries on `isRTL` instead of `t()` keys. This bypasses the central locale files entirely.
- **Why it matters:** Any school whose subjects are stored in English (or in a different transliteration of Arabic) gets a colourless grid; copy edits cannot be done by translators; locale-file completeness checks miss these strings.
- **Recommended fix:** Move subject-color mapping to a normalised key (subject ID or `subject.code`), and replace the `isRTL ? 'AR' : 'EN'` ternaries with `t()` keys backed by `en.json`/`ar.json`.
- **Effort:** M

#### F-FE-03 — `CreateScheduleWizard` performs no time/range validation before POST
- **Severity:** High
- **Location:** `frontend/src/components/wizards/CreateScheduleWizard.jsx:106-179`
- **Description:** `handleSubmit` only checks that `name_ar` and `class_id` are present and that there is at least one day with periods. There is no check that:
  1. each period has a non-empty `subject_id` and `teacher_id` (currently empty selects pass through and hit the API),
  2. `start_time < end_time`,
  3. periods within a day do not overlap,
  4. the same teacher is not assigned to two simultaneous periods across days,
  5. `period_number` is unique within the day.
  `addPeriod` blindly takes `(prev[day]?.length || 0) + 1` so deleting the middle period leaves a gap; `removePeriod` does not renumber. The "wizard" is actually a single dialog (no `<Stepper>`/`<Tabs>`), so there is no review step and no preview before submit.
- **Why it matters:** Garbage payloads reach `/schedules/create` and rely on the backend for every error; inverted times and overlaps create invalid sessions that downstream timetable views render incorrectly.
- **Recommended fix:** Add a `validateSchedule()` helper that runs all of the above checks and returns a list of localized errors; render them inline next to each offending row; renumber periods after delete; introduce a final "Preview" step (read-only render of the planned grid) before the submit button.
- **Effort:** M

#### F-FE-04 — `TimeSlotsPage` accepts inverted, overlapping, or zero-duration slots
- **Severity:** Medium
- **Location:** `frontend/src/pages/TimeSlotsPage.jsx:127-156,335-356`
- **Description:** `handleCreateSlot` only checks that `name` and `selectedSchool` are present. The `start_time`/`end_time`/`duration_minutes`/`slot_number` inputs have no client-side validation: the user can submit `end_time <= start_time`, a duration that disagrees with the time range, a negative `slot_number`, or a slot that overlaps an existing one. There is no edit dialog at all (the `Edit` icon is imported on line 18 but never rendered in the row); the only mutation paths are "create" and "delete".
- **Why it matters:** Bad time slots silently corrupt every downstream grid (sessions get mismatched on `period_number`/`start_time` joins) and force the principal to delete + recreate slots whenever they make a typo. Most schools will hit this within minutes of onboarding.
- **Recommended fix:** Add a `validateSlot` helper (`start < end`, `duration === diffMinutes`, `slot_number >= 1`, no overlap with existing non-break slots) and gate the submit on it. Add an edit dialog so users can tune times without losing the slot ID.
- **Effort:** S

#### F-FE-05 — `TeacherAssignmentsPage` fetches workloads in a serial N+1 loop
- **Severity:** Medium
- **Location:** `frontend/src/pages/TeacherAssignmentsPage.jsx:155-165`
- **Description:** After loading teachers, the page calls `await api.get('/teachers/{id}/workload')` inside a `for...of` loop limited to the first 20 teachers. With 20 round-trips serialized, the page blocks for several seconds on a typical school dataset; teachers 21+ silently never get a workload card. The hard-coded `slice(0, 20)` is undocumented and not visible in the UI.
- **Why it matters:** Slow first paint and incomplete workload data for any school with >20 teachers — the workload pill on assignment cards 21+ stays blank with no explanation. Real schools (the audit target) routinely have 30–80 teachers.
- **Recommended fix:** Either add a backend `/teachers/workloads?school_id=…` bulk endpoint, or run the per-teacher requests through `Promise.all` (or `Promise.allSettled`) in chunks of ~10. Remove the magic `20` cap and surface a "loading workloads…" skeleton next to each card.
- **Effort:** S

#### F-FE-06 — Principal timetable grid has no keyboard or screen-reader support
- **Severity:** Medium
- **Location:** `frontend/src/components/timetable/TimetableGridSection.jsx:28-148` (and the cell renderers in `frontend/src/pages/SchedulePageNew.jsx:75-148`)
- **Description:** The timetable cell is a `<div>` with `onClick`/`draggable`, no `role="button"`/`role="gridcell"`, no `tabIndex`, no `aria-label`, no keyboard `onKeyDown` handler — `grep tabIndex|aria-|role=` against `TimetableGridSection.jsx` returns zero matches. There is also no live region announcing drag/swap results (`toast.success('تم النقل…')` is the only feedback). Drop targets are pure `<div>` elements without `aria-dropeffect` or focus management.
- **Why it matters:** A principal who cannot use a mouse cannot operate the timetable at all; screen-reader users cannot perceive cell contents or move sessions. Saudi public-procurement guidelines (and most modern accessibility standards) require keyboard parity for primary admin workflows.
- **Recommended fix:** Wrap the grid in a `role="grid"` table semantic (or true `<table>`), give each cell `role="gridcell"`, `tabIndex={0}`, `aria-label="<subject>, <teacher>, <period>"`, and implement arrow-key navigation + space-to-pick-up / arrow-to-move / enter-to-drop for keyboard drag-and-drop. Add an `aria-live="polite"` region for swap/move announcements.
- **Effort:** L

#### F-FE-07 — Full timetable rendered as raw DOM nodes (no virtualisation)
- **Severity:** Low
- **Location:** `frontend/src/components/timetable/PrincipalTimetablePage.jsx:62-172` (`PreviousTimetableGrid`) and `frontend/src/pages/SchedulePageNew.jsx:74-148`
- **Description:** Both grids render every class × every day × every period as a separate `<div>` (with nested icons, tooltips, and gradient backgrounds). For the audit's stress target — 40 classes × 7 days × 8 periods × ~6 nested elements per cell ≈ 13 000+ DOM nodes per render — there is no virtualisation, no memoisation around `TimetableCell`, and `getSessionForCell` does an `Array.find` linear scan over `sessions` for every cell on every render. `SchedulePageNew.jsx:472` recomputes `gridSessions` and `periodGaps` on every state change without indexing.
- **Why it matters:** On large schools the principal page becomes janky on filter switches, drags reflow the whole tree, and mobile devices stutter. Not catastrophic today (most schools <20 classes) but will bite as the product scales.
- **Recommended fix:** Index sessions once per fetch as `Map<classId, Map<dayKey, Map<periodNumber, session>>>`; memoise `TimetableCell` with `React.memo`; for very large schools either virtualise rows with `react-window`'s `FixedSizeList` or paginate by class.
- **Effort:** M

#### F-FE-08 — `school_id` resolution silently falls back to `localStorage`
- **Severity:** Medium
- **Location:** `frontend/src/components/timetable/PrincipalTimetablePage.jsx:237-246`
- **Description:** The `getEffectiveSchoolId` helper tries (in order) `schoolContext.school_id`, `user.tenant_id`, `user.school_id`, the first role's `school_id`, and finally `localStorage.getItem('school_id') || localStorage.getItem('nassaq_school_id')`. The header builder on lines 41-45 then sends that value as `X-School-Context` for every timetable request.
- **Why it matters:** Any user can edit `localStorage.school_id` in dev tools and the frontend will happily send that ID as the school context. The backend dependency tree (see F-XC-02 placeholder / F-API-04) does not always re-validate that the header school matches the user's tenant, so a localStorage tweak combined with a missing backend check is a multi-tenant leak vector. Even without exploitation, it makes browser session corruption ("I logged out and now see another school's data") possible.
- **Recommended fix:** Drop the `localStorage` fallbacks; if neither the auth context nor the user object resolves a school ID, surface an error and log out. Pair with the backend fix in F-XC-02 to reject `X-School-Context` values that don't match the JWT's tenant.
- **Effort:** S

#### F-FE-09 — `TeacherSchedulePage` trusts a client-supplied teacher ID
- **Severity:** Medium
- **Location:** `frontend/src/pages/TeacherModule/TeacherSchedulePage.jsx:98-106`
- **Description:** `teacherId = user?.teacher_id || user?.id` is computed in the browser and then interpolated into `api.get('/teacher/schedule/${teacherId}')`. There is no `/teacher/me/schedule` style endpoint. A teacher with dev tools open can substitute another teacher's UUID and the request will go through (security depends entirely on backend route filtering — see F-API-XX). The same pattern (`api.get('/parent-portal/child/${childId}/schedule')` in `ChildSchedulePage.jsx:42-44` and `api.get('/student-portal/schedule')`) at least delegates to the backend, but the teacher path explicitly shapes the URL from a client-side ID.
- **Why it matters:** It is one missing backend check away from a teacher reading any colleague's timetable. Even in the safe case it makes RBAC harder to reason about because the boundary is split between two layers.
- **Recommended fix:** Add and call a `/teacher/me/schedule` (or `/teachers/self/schedule`) endpoint that derives the teacher ID from the JWT, and stop accepting a teacher ID in the URL for self-service views.
- **Effort:** S

#### F-FE-10 — Stale timetable cache after generate / publish in `SchedulePageNew`
- **Severity:** Low
- **Location:** `frontend/src/pages/SchedulePageNew.jsx:289-361`
- **Description:** After `handleGenerate` succeeds, the code calls `setSelectedTimetableId(result.timetable_id)` then immediately `fetchSessions(result.timetable_id)` — but the `useEffect` on line 290 (`if (selectedTimetableId) fetchSessions()`) also fires, racing the explicit call and using the previous closure's `selectedTimetableId`. After `handlePublish` (line 347) the code reloads `smartTimetables` but does **not** call `fetchSessions`, so the published-status badge and the drag-drop guard (`canDragDrop` line 379) update but the underlying sessions list is not refreshed. There is no global cache invalidation across other open tabs (parent/student/teacher portals continue showing the previous version until the 5-min interval poll in `TeacherSchedulePage.jsx:139-142` fires).
- **Why it matters:** Right after generating or publishing, the principal can briefly see duplicate fetches and inconsistent counts; teachers and parents may operate on stale schedules for up to 5 minutes. Not data-loss, just confusing.
- **Recommended fix:** Replace ad-hoc state with React Query / SWR keyed by `timetable_id`, invalidate the key on generate / publish, and broadcast a "schedule updated" event over the existing notification websocket so other portals refetch immediately. Also remove the duplicate explicit call on line 335 once the effect-driven fetch is reliable.
- **Effort:** M


### 3.7 End-to-end flow walkthrough
_Files inspected:_ `frontend/src/components/wizards/CreateScheduleWizard.jsx`, `frontend/src/components/timetable/PrincipalTimetablePage.jsx`, `frontend/src/pages/TimeSlotsPage.jsx`, `frontend/src/pages/TeacherModule/TeacherSchedulePage.jsx`, `frontend/src/pages/ParentPortal/ChildSchedulePage.jsx`, `frontend/src/pages/StudentPortal/StudentSchedulePage.jsx`, `backend/routes/timetable_readiness_routes.py`, `backend/routes/scheduling_generation_routes.py`, `backend/routes/principal_timetable_routes.py`, `backend/routes/student_portal_routes.py`, `backend/routes/parent_portal_routes.py`, `backend/routes/role_dashboards_mod.py`, plus cross-references to findings already recorded in sections 3.1–3.6.

_Walkthrough:_

1. **New empty school is created (tenant onboarding).** A platform admin provisions a school via the tenant flow (`backend/engines/tenant_engine.py`, surfaced through `backend/routes/platform_routes_mod.py` / `PlatformSchoolsPage.jsx`). At this point the school has no time slots, no constraints, and no per-tenant defaults: the seeds for hard/soft constraints (Layer SD, F-SD-01, F-SD-04) only run when the global tables are empty and are never re-applied per tenant, so a fresh school inherits whatever global rows happen to exist plus an empty `school_constraints` table — which the engine then silently substitutes with the global `administrative_constraints` rows (F-CN-06).

2. **Principal sets up academic year and term.** The principal opens the academic structure screens (`frontend/src/pages/AcademicStructurePage.jsx`) which call `backend/routes/academics_year_term_routes.py`. The chosen year/semester is later quoted as plain strings (`academic_year`, `semester`) on `timetables`, `teacher_assignments`, and `schedule_sessions`; there is no FK to an `AcademicTerm` row (Layer DM, F-DM-04), so subsequent steps rely on string equality between the wizard's `'2025-2026'` default (`CreateScheduleWizard.jsx:62`) and whatever was typed into the academic-year screen.

3. **Principal creates classes (grades, sections).** Done through `frontend/src/pages/ClassesPage.jsx` + `frontend/src/components/wizards/CreateClassWizard.jsx`, backed by `backend/routes/academics_class_routes.py` and `backend/routes/class_management_routes.py`. The created classes are what the readiness Phase 2 ("Academic Entities") later counts (`backend/routes/timetable_readiness_routes.py`).

4. **Principal creates / imports subjects.** `frontend/src/pages/SubjectsPage.jsx` calls `backend/routes/academics_subject_routes.py`. Grade↔subject linkage and weekly-period counts are stored here and consumed by the engine's demand matrix; the engine, however, ignores per-subject weekly-period counts and uses a hard-coded `>= 2` threshold for "balanced distribution" (Layer CN, F-CN-08).

5. **Principal creates / imports teachers and assigns subjects to teachers.** `frontend/src/pages/TeachersPage.jsx`, `CreateUserWizard.jsx`, `AddTeacherWizard.jsx`, `BulkTeacherImport.jsx`, and `frontend/src/pages/TeacherClassAssignmentPage.jsx` write to `backend/routes/teacher_management_routes.py`, `bulk_teacher_routes.py`, and `backend/routes/academics_teacher_routes.py`. Teacher↔subject and class↔subject links land in `teacher_assignments`, which has no uniqueness constraint on (school, teacher, class, subject, term) (F-DM-05), so duplicates created by re-imports propagate forward into generation.

6. **Principal defines time slots / period structure for the school week.** `frontend/src/pages/TimeSlotsPage.jsx` posts to `backend/routes/scheduling_routes.py` / `scheduling_core_routes.py`. `start_time` / `end_time` are persisted as strings (F-DM-07) and the seeded defaults are Saudi-specific with a fixed Sun–Thu week (F-SD-08). Working days come from school settings (`_parse_working_days_from_settings` in `backend/routes/timetable_readiness_routes.py:68`) which has three fallback sources, demonstrating the lack of a single source of truth for the school week.

7. **Principal reviews / configures hard and soft constraints.** Reached through `frontend/src/pages/SchoolSettingsPagePro.jsx` → `DynamicSettingsContent` constraints tab (`backend/routes/scheduling_routes.py`, `school_settings_routes.py`). The UI shows seeded constraints with `can_disable: True` toggles (F-CN-10) and lets the principal author custom soft constraints, but neither toggling nor custom rules are dispatched in the engine (F-CN-01, F-CN-05).

8. **Principal opens the readiness check; gaps are reported.** `frontend/src/components/timetable/PrincipalTimetablePage.jsx` renders `TimetableReadinessPanel` and calls `GET /api/principal/timetable/readiness` (`principal_timetable_routes.py:290`) and `GET /api/timetable-readiness/check` (`timetable_readiness_routes.py:496`). The latter is unauthenticated/role-unchecked (F-API-03) and walks the 6 readiness phases. Issues come back with bilingual hard-coded `message_ar` / `message_en` (no i18n keys; cross-refs F-CN-12).

9. **Principal triggers generation; engine runs; result is shown as a draft.** From the same page, the principal clicks the AI generation modal (`AITimetableGenerationModal` in `TimetableModals`), which posts to `POST /api/principal/timetable/generate` (`principal_timetable_routes.py:869`) — internally delegating to `smart_scheduling_engine`. There is no concurrency lock (F-EN-05), no seeded RNG (F-EN-02), no cap/timeout (F-EN-03), and the existing draft is silently overwritten (F-EN-04). The new timetable row is created with `status="draft"` and rendered in `TimetableGridSection`. The legacy `CreateScheduleWizard.jsx` is a parallel, divergent entry point (F-EN-01) that bypasses readiness entirely and writes to a separate `schedules` collection via `POST /schedules/{id}/generate` (`scheduling_generation_routes.py:35`).

10. **Principal reviews the draft, makes manual edits if needed.** `TimetableGridSection` and `TimetableSessionDetailsDrawer` call `POST /api/principal/timetable/sessions/swap` and `.../sessions/move` (`principal_timetable_routes.py:1755`, `:1859`) plus `.../version/{id}/fill-gaps`. These mutations do not re-run the constraint validator, so an edit can re-introduce a HC-03 (room-overlap) or HC-06 violation that the engine would not have produced (F-CN-03, F-CN-11). After editing, the principal can run `GET /version/{id}/validate-publish` which only enforces 3 of 17 hard constraints (F-CN-02).

11. **Principal publishes the timetable.** `PublishTimetableVersionModal` collects an effective-from date and confirmation, then `handlePublishVersion` (`PrincipalTimetablePage.jsx:569`) posts to `POST /api/principal/timetable/version/{id}/publish` (`principal_timetable_routes.py:1104`). The endpoint is non-idempotent and not transactional across the snapshot insert, archive of the previous published row, and audit log (F-API-06); the data model also allows multiple "published" rows to coexist for the same (school, term, semester) (F-DM-11). On success the page sets a confetti overlay, locally mutates `activeVersion.status = 'published'`, and refetches the grid.

12. **Teacher logs in and sees their schedule.** `frontend/src/pages/TeacherModule/TeacherSchedulePage.jsx` mounts under the teacher portal and calls `GET /api/teacher/schedule/{teacher_id}` (`backend/routes/role_dashboards_mod.py:805`). The page reads `start_time` / `end_time` strings (F-DM-07) and parses them client-side. There is no websocket/polling refresh after the principal publishes a new version, so a teacher who is already logged in keeps seeing the old schedule until manual refresh.

13. **Student / parent logs in and sees the relevant class schedule.** `frontend/src/pages/StudentPortal/StudentSchedulePage.jsx` calls `GET /api/student-portal/schedule` (`student_portal_routes.py:302`) and `frontend/src/pages/ParentPortal/ChildSchedulePage.jsx` calls `GET /api/parent-portal/child/{child_id}/schedule` (`parent_portal_routes.py:430`). Both query `timetable_sessions` for the child's `class_id` from the most recent timetable, but the two endpoints disagree on which timetable counts as "live": the student endpoint accepts any status in `LIVE_TIMETABLE_STATUSES` while the parent endpoint hard-codes `status: "published"`. Neither does any change-detection or push notification on republish.

_Flow-level findings:_

#### F-E2E-01 — Two parallel "create timetable" entry points with incompatible data models
- **Severity:** High
- **Location:** `frontend/src/components/wizards/CreateScheduleWizard.jsx:38`, `frontend/src/components/timetable/PrincipalTimetablePage.jsx:1`, `backend/routes/scheduling_generation_routes.py:35`, `backend/routes/principal_timetable_routes.py:869`
- **Description:** A principal can reach scheduling either via the legacy `CreateScheduleWizard` (writes to `schedules` + `schedule_sessions`, hits `POST /schedules/{id}/generate`) or via `PrincipalTimetablePage` (writes to `timetables` + `timetable_sessions`, hits `POST /principal/timetable/generate`). The two paths share no readiness check, no constraint validation, and no version model, and produce disjoint rows that the teacher/student/parent endpoints (which read only `timetable_sessions`) cannot see if the legacy wizard was used.
- **Why it matters:** Real principals will pick whichever button they happen to find first; if it is the legacy wizard their result silently never reaches the consumer portals, looking like total data loss.
- **Recommended fix:** Remove the legacy `CreateScheduleWizard` mount from the navigation (or convert it into a thin redirect to `PrincipalTimetablePage`), and delete `POST /schedules/{id}/generate` after migrating its tests.
- **Effort:** M

#### F-E2E-02 — No enforced gate between readiness and generation
- **Severity:** High
- **Location:** `frontend/src/components/timetable/PrincipalTimetablePage.jsx:977`, `backend/routes/principal_timetable_routes.py:869`
- **Description:** `TimetableReadinessPanel` reports phase-by-phase gaps but the "Generate" button is independently enabled — the page does not require `FULLY_READY` before allowing `POST /principal/timetable/generate`, and the backend endpoint does not check readiness either. With no time slots, no teachers, or no assignments, generation will still run and produce an empty/partial timetable that is then publishable.
- **Why it matters:** Schools end up publishing nonsense timetables; debugging "why is the grid empty" forces them back through the readiness screen they already dismissed.
- **Recommended fix:** Disable the generate CTA whenever `readiness.status !== "FULLY_READY"` (or downgrade with a confirm-to-override for `PARTIALLY_READY`), and add a server-side guard in `principal_timetable_routes.py:869` that returns 409 with the readiness payload when critical issues exist.
- **Effort:** S

#### F-E2E-03 — Manual draft edits bypass constraint validation
- **Severity:** High
- **Location:** `backend/routes/principal_timetable_routes.py:1755`, `backend/routes/principal_timetable_routes.py:1859`, `backend/routes/principal_timetable_routes.py:1531`
- **Description:** `POST /sessions/swap`, `POST /sessions/move`, and `POST /version/{id}/fill-gaps` mutate `timetable_sessions` directly without re-evaluating the hard-constraint set. A principal can swap two cells and create a teacher double-booking, room overlap, or daily-cap violation that the engine would have refused. Since `validate-publish` only enforces 3 of 17 hard constraints (F-CN-02), the violation can survive all the way to publish.
- **Why it matters:** The "manual edit" flow is the one place principals exercise judgement, so silent constraint breakage here directly produces real, visible classroom conflicts.
- **Recommended fix:** Run the same conflict detector used in publish-gate after every swap/move/fill-gaps mutation, and either reject the mutation or return a structured warning the UI can display before persisting.
- **Effort:** M

#### F-E2E-04 — Parent and student schedule endpoints disagree on which timetable to read
- **Severity:** High
- **Location:** `backend/routes/parent_portal_routes.py:454`, `backend/routes/student_portal_routes.py:326`
- **Description:** The student endpoint reads `timetables` whose status is in `LIVE_TIMETABLE_STATUSES` (a multi-status set introduced by fix C3), while the parent endpoint hard-codes `status: "published"` and falls back to the most recent timetable regardless of status. After a principal moves a timetable through `active`/`live`/etc., a student can see the new schedule while their parent still sees the previous one (or vice-versa via the silent fallback).
- **Why it matters:** Parents and students of the same household will see contradictory schedules, and the silent fallback to "most recent any-status" can surface drafts to parents.
- **Recommended fix:** Extract a shared helper `_resolve_live_timetable(school_id)` used by both portals (and the teacher endpoint), and remove the unconditional "most recent" fallback so missing-published-timetable returns an empty schedule, not a draft.
- **Effort:** S

#### F-E2E-05 — Teacher / student / parent views do not refresh after publish
- **Severity:** Medium
- **Location:** `frontend/src/pages/TeacherModule/TeacherSchedulePage.jsx:79`, `frontend/src/pages/StudentPortal/StudentSchedulePage.jsx:50`, `frontend/src/pages/ParentPortal/ChildSchedulePage.jsx:39`
- **Description:** All three consumer pages fetch the schedule once on mount and have no websocket subscription, polling, or `react-query`-style invalidation. The `WebSocketContext` is wired for notifications but the publish flow in `PrincipalTimetablePage.jsx:569` does not emit a "timetable_published" event. Logged-in users keep seeing the previous schedule until they manually reload.
- **Why it matters:** The most common "the new schedule isn't showing" support ticket is created by exactly this gap — users believe publish failed when it actually succeeded.
- **Recommended fix:** Emit a `timetable_published` event from the publish endpoint (scoped to school_id), have the three consumer pages subscribe via `WebSocketContext` and refetch on receipt, and as a fallback add a 60s polling interval when the tab is visible.
- **Effort:** M

#### F-E2E-06 — Publish action's local state mutation hides server failures
- **Severity:** Medium
- **Location:** `frontend/src/components/timetable/PrincipalTimetablePage.jsx:569`
- **Description:** `handlePublishVersion` flips the local `activeVersion.status` to `'published'` and shows a confetti overlay before refetching server state. If the subsequent `fetchGrid` fails (network blip, server returned a non-`published` row because of the F-DM-11 multiple-published condition), the UI still shows "published" while the database may be inconsistent.
- **Why it matters:** Principals trust the confetti and walk away; the timetable is then never actually visible to teachers or families.
- **Recommended fix:** Defer the optimistic state flip and the confetti until both the publish POST and the subsequent grid + versions refetch resolve successfully; on failure, surface an error toast and keep the version in `draft` visually.
- **Effort:** S

#### F-E2E-07 — Tenant onboarding does not seed default time slots or per-school constraints
- **Severity:** Medium
- **Location:** `backend/engines/tenant_engine.py`, `backend/seeds/timetable_hard_constraints.py:1`, `backend/seeds/timetable_soft_constraints.py:1`
- **Description:** A newly provisioned school lands on `PrincipalTimetablePage` with zero time slots, zero `school_constraints`, and no defaulted working days; the readiness check immediately blocks every phase (cross-refs F-SD-04). The principal must manually open `TimeSlotsPage` and the constraints settings before anything else works, and there is no in-product nudge guiding them there.
- **Why it matters:** First-run experience for a new school is a wall of red error states with no clear "do this first" path; many tenants will abandon at this step.
- **Recommended fix:** On tenant creation, provision (a) a default Sun–Thu working-week setting, (b) a default 7-period day with two break slots from the seeds, and (c) per-school copies of the global hard/soft constraint rows; then have `PrincipalTimetablePage` deep-link to the first failing readiness phase as a guided onboarding step.
- **Effort:** M

#### F-E2E-08 — `CreateScheduleWizard` hard-codes academic year `'2025-2026'`
- **Severity:** Low
- **Location:** `frontend/src/components/wizards/CreateScheduleWizard.jsx:62`
- **Description:** The legacy wizard initialises `academic_year: '2025-2026'` and never reconciles with the current academic year configured in `AcademicStructurePage`. Combined with the lack of an `AcademicTerm` FK (F-DM-04), any timetable created here is keyed to a literal string that may not match the rest of the system.
- **Why it matters:** Even ignoring F-E2E-01, anyone who still uses this wizard in 2026-2027 will create rows that nothing else can join against.
- **Recommended fix:** Drop the wizard (preferred, see F-E2E-01) or, if kept, replace the literal default with the current term resolved from `/api/academic-structure/current`.
- **Effort:** S

### 3.8 Cross-cutting
_Files inspected:_

Middleware / shared infrastructure:
- `backend/middleware/__init__.py`
- `backend/middleware/audit_middleware.py`
- `backend/middleware/cache_metrics.py`
- `backend/middleware/error_handler.py`
- `backend/middleware/query_monitor.py`
- `backend/middleware/rate_limiter.py`
- `backend/middleware/rbac.py`
- `backend/middleware/request_tracing.py`
- `backend/middleware/tenant_isolation.py`
- `backend/dependencies.py`
- `backend/db.py`
- `backend/db_indexes.py`

Locales:
- `frontend/src/locales/en.json`
- `frontend/src/locales/ar.json`

Timetable-related backend tests (discovered via `grep -rln -E "timetable|schedul|time_slot|constraint" backend/tests --include='*.py' | sort -u`):
- `backend/tests/test_attendance_api.py`
- `backend/tests/test_bulk_import_export.py`
- `backend/tests/test_communication_reports.py`
- `backend/tests/test_conflict_resolution_api.py`
- `backend/tests/test_dashboard_apis.py`
- `backend/tests/test_drag_drop_api.py`
- `backend/tests/test_foundation_phase.py`
- `backend/tests/test_intervention_endpoint.py`
- `backend/tests/test_iteration_32.py`
- `backend/tests/test_iteration_71.py`
- `backend/tests/test_iteration_73.py`
- `backend/tests/test_language_dashboard.py`
- `backend/tests/test_management_api.py`
- `backend/tests/test_nassaq_api.py`
- `backend/tests/test_nassaq_features.py`
- `backend/tests/test_nassaq_fixes_iter67.py`
- `backend/tests/test_new_routers.py`
- `backend/tests/test_official_curriculum_api.py`
- `backend/tests/test_official_curriculum_iter79.py`
- `backend/tests/test_principal_timetable_page_iter81.py`
- `backend/tests/test_restructure_and_new_apis.py`
- `backend/tests/test_role_communication_apis.py`
- `backend/tests/test_schedule_hakim.py`
- `backend/tests/test_schedule_page_new.py`
- `backend/tests/test_scheduling_api.py`
- `backend/tests/test_scheduling_smart_engine.py`
- `backend/tests/test_school_settings.py`
- `backend/tests/test_school_settings_pro.py`
- `backend/tests/test_seed_data_verification.py`
- `backend/tests/test_session_management_assignments.py`
- `backend/tests/test_settings_edit_constraints.py`
- `backend/tests/test_smart_scheduling.py`
- `backend/tests/test_smart_timetable_page.py`
- `backend/tests/test_student_parent_portal.py`
- `backend/tests/test_student_performance_rbac.py`
- `backend/tests/test_subjects_constraints_activerole.py`
- `backend/tests/test_teacher_module_apis.py`
- `backend/tests/test_teacher_wizard_api.py`
- `backend/tests/test_timetable_readiness.py`
- `backend/tests/test_user_creation_flow.py`
- `backend/tests/test_user_integrations_analytics.py`

Frontend tests (discovered via `grep -rln -E "timetable|schedule" frontend/src --include='*.test.*' --include='*.spec.*'`):
- _none — frontend has no `*.test.*` / `*.spec.*` files for timetable._

_Findings:_

#### F-XC-01 — `TENANT_SCOPED_COLLECTIONS` whitelist omits every timetable-owned table; isolation warnings never fire for the engine
- **Severity:** High
- **Location:** `backend/middleware/tenant_isolation.py:278-282`
- **Description:** The `TENANT_SCOPED_COLLECTIONS` frozenset used by `warn_missing_tenant_filter` (and intended as a soft tripwire for missing tenant filters) lists `students, teachers, classes, subjects, attendance, teacher_attendance, schedules, grades, behaviour_records, events, notifications, registration_requests`. It does **not** include `timetables`, `schedule_sessions`, `timetable_sessions`, `time_slots`, `teacher_assignments`, `timetable_constraints`, `school_constraints`, `administrative_constraints`, or `constraint_patterns`. Every timetable read/write therefore bypasses the scoped-query log warning, leaving F-EN-06 (engine performs reads without tenant filter), F-API-01/02/04 (routes accept arbitrary `school_id`/`timetable_id`), and F-CN-06 (cross-tenant constraint fallback) without any runtime tripwire that would have surfaced them in logs.
- **Why it matters:** This is the place where the project's own tenant-isolation contract is declared. The omission both (a) reinforces the existing Critical/High API & engine isolation findings — there is no defence-in-depth at the data-access layer — and (b) means the same class of bug can be reintroduced silently. Once a school grows past one tenant, the only signal of leakage will be a customer report.
- **Recommended fix:** Add `timetables, schedule_sessions, timetable_sessions, time_slots, teacher_assignments, timetable_constraints, school_constraints, administrative_constraints, constraint_patterns` to `TENANT_SCOPED_COLLECTIONS`, then route all timetable repository calls through `gd_find` / `gd_find_one` wrappers that invoke `warn_missing_tenant_filter` (or, better, a hard `RuntimeError` in dev mode). Pair with the route-level fixes from F-API-01/02/04 and F-EN-06.
- **Effort:** S
- **Status:** ✅ Remediated 2026-04-17 (Batch 1 plan: docs/superpowers/plans/2026-04-17-timetable-remediation-batch1.md)

#### F-XC-02 — RBAC permission system declares `SCHEDULE_PUBLISH` / `SCHEDULE_DELETE` but no scheduling route uses it; gating relies on hard-coded role lists
- **Severity:** Medium
- **Location:** `backend/middleware/rbac.py:46-51` (Permission enum) and `backend/middleware/rbac.py:159-174` (principal mapping); contrast with `backend/dependencies.py:288-293` (`require_roles`).
- **Description:** `Permission.SCHEDULE_VIEW/CREATE/EDIT/PUBLISH/DELETE` are defined and mapped to `school_principal`, but `grep` across `backend/routes/scheduling_*.py`, `principal_timetable_routes.py`, `timetable_readiness_routes.py`, and `schedule_management_routes.py` shows **zero** call sites of `require_permission(...)` for any of them — every route uses `require_roles([...])` with a hand-typed list, which (a) duplicates the permission matrix, (b) has already drifted (e.g. F-API-15 inline role checks in `schedule_management_routes`, F-API-02 raw-JWT decode in `principal_timetable_routes`), and (c) ignores the per-school custom-permissions overlay (`user.permissions`) that `RBACMiddleware.has_permission` honours. School admins who could legitimately be granted `SCHEDULE_PUBLISH` cannot be, because no route checks the permission.
- **Why it matters:** Two parallel access-control systems disagree about who can publish or delete a timetable, and the one actually enforced is the weaker hand-typed one. Custom per-user grants are silently ignored. A future role refactor will look at `ROLE_PERMISSIONS` and assume those checks are real.
- **Recommended fix:** Either (a) delete the unused `Permission.SCHEDULE_*` values and the principal mapping rows that reference them, documenting that scheduling uses role-based not permission-based gating; or (b) replace the role-list `Depends(require_roles([...]))` on every scheduling endpoint with `Depends(require_permission(Permission.SCHEDULE_PUBLISH.value))` etc., and rely on `ROLE_PERMISSIONS` as the single source of truth.
- **Effort:** M

#### F-XC-03 — `db_indexes.py` is a stub; index coverage is not verifiable from one location
- **Severity:** Low
- **Location:** `backend/db_indexes.py:1-13`
- **Description:** The file contains only a comment ("Indexes are now managed via SQLAlchemy ORM models … and applied through Alembic migrations") and a no-op `create_indexes()` coroutine that logs a single line. There is no enumeration, verification, or assertion that the composite indexes the engine actually needs (per F-DM-09: `(school_id, term, day, period)`, `(teacher_id, day, period)`, `(class_id, day, period)`, `(timetable_id, day, period)`) exist on the live schema. Engine read patterns (e.g. `smart_scheduling_engine` filtering `schedule_sessions` by `timetable_id`+`day_of_week`+`period_number`, `principal_timetable_routes` listing sessions by `school_id`+`status`) cannot be cross-checked against this file.
- **Why it matters:** Centralised index registration was the obvious place for the audit to confirm performance hot-paths. Its absence means index coverage must be reconstructed by reading every Alembic version individually (e.g. `b7e52689a1ad`, `g1h2i3j4k5l6`, `i1j2k3l4m5n6`). Drift between what the engine queries and what is indexed will only surface as slow queries in production.
- **Recommended fix:** Either delete the stub and remove the lifecycle hook that calls it, or repopulate it with an enumeration of required composite indexes that runs `CREATE INDEX IF NOT EXISTS …` and asserts presence at boot. The latter is the safer choice given F-DM-09.
- **Effort:** S

#### F-XC-04 — Sensitive timetable lifecycle events (generate, publish, delete, manual edit) are not explicitly audit-logged; reliance on AuditMiddleware mis-tags most of them
- **Severity:** High
- **Location:**
  - `backend/middleware/audit_middleware.py:197-234` (`_derive_action`) and `:67-98` (`PATH_ENTITY_MAP`)
  - `backend/routes/scheduling_smart_engine_routes.py:19` and `backend/routes/scheduling_smart_session_routes.py:19` and `backend/routes/scheduling_generation_routes.py:19` (`audit_engine` imported but never invoked)
  - Only one explicit timetable audit call exists: `backend/routes/principal_timetable_routes.py:1256` (`gd_insert(... "audit_logs" ...)`)
- **Description:** Inside the routes, no `audit_engine.log(...)` call is made for any timetable lifecycle action. The codebase relies entirely on `AuditMiddleware` to capture HTTP requests after the fact, but the middleware's tagging logic only recognises `"schedule.generated"` when both `"/generate"` and `"schedule"` appear in the path, and `"schedule.published"` only when both `"/publish"` and `"schedule"` appear. This means:
  - `POST /api/principal/timetable/generate` → derives `entity="timetable"`, action falls through to `timetable.created` (no `"schedule"` token); the dedicated `schedule.generated` action is never emitted.
  - `POST /api/principal/timetable/version/{id}/publish` → derives `timetable.updated`, not `schedule.published`.
  - `DELETE /api/smart-scheduling/timetable/{id}` → tagged via generic `METHOD_ACTIONS`, severity `medium` not `high`.
  - Manual edits (`POST /smart-scheduling/session/move`, `swap`, `add`, `force_update_smart_session`) emit only the generic `session.created/updated`, with no record of *which* timetable was mutated, what the previous slot was, or whether it was a published timetable. Reinforces F-API-12 and F-API-17/18.
- **Why it matters:** Audit trails are the only post-incident artefact for "who broke the timetable?" or "who published the wrong draft?" The middleware-only approach loses the actor's intent (publish vs. plain update), the resource id (timetable_id is in the URL but is not extracted into the audit `entity_id`), and the before-state of the mutation. A school principal disputing a parent complaint about a sudden schedule change would have no usable audit row.
- **Recommended fix:** (1) Extend `_derive_action` so that any path containing `"timetable"` is treated as the schedule entity (`schedule.generated`, `schedule.published`, `schedule.deleted`, `schedule.session_moved`). (2) In each scheduling lifecycle route, call `audit_engine.log_action(...)` explicitly with the resolved `timetable_id`, `school_id`, before/after JSON for moves, and severity `high` for delete/publish. (3) Bump severity for `/timetable/.+/publish` and `/timetable/.+/delete` to `high` in `HIGH_SEVERITY_PATTERNS`.
- **Effort:** M

#### F-XC-05 — i18n key parity holds for timetable strings, but locale parity does not protect against the JSX hard-codes already flagged
- **Severity:** Low
- **Location:** `frontend/src/locales/en.json` and `frontend/src/locales/ar.json` (whole files)
- **Description:** A diff of all keys whose path contains `timetable|schedule|constraint|session|publish|generation` shows 151 keys in `en.json` and 151 keys in `ar.json` with identical key sets — locale parity is intact for translated strings. The cross-cutting risk is therefore not in the locale files but in the JSX components that bypass `t(...)` entirely (already flagged: F-FE-01 hard-coded Arabic in `SchedulePageNew`, F-FE-02 Arabic-only labels in `TeacherSchedulePage`, F-CN-12 bilingual hard-coded constraint messages in the engine, F-SD-09 hard-coded ar/en pairs in seeds). i18n correctness is therefore a code-discipline problem, not a locale-coverage problem.
- **Why it matters:** Future maintainers will read green parity numbers and conclude the timetable subsystem is fully internationalised. It is not — the violations are in the consumers, not the dictionaries.
- **Recommended fix:** Add an ESLint rule (e.g. `i18next/no-literal-string`) scoped to `frontend/src/components/timetable/**` and `frontend/src/pages/{Schedule,Timetable,Teacher}*`, then drive the existing FE/CN/SD findings to closure. Locale files themselves need no change.
- **Effort:** S

#### F-XC-06 — Timetable grid has no keyboard, screen-reader, or focus affordances at all
- **Severity:** High
- **Location:** `frontend/src/components/timetable/TimetableGridSection.jsx:1-560` (entire file)
- **Description:** A grep for `role=`, `aria-`, `tabIndex`, `onKeyDown`, or `focus:` over the 560-line `TimetableGridSection` returns **zero** matches. Cells are plain `<div>` elements with click handlers; there are no `role="grid"` / `role="gridcell"` ARIA semantics, no `aria-label` summarising what subject/teacher each cell holds, no keyboard navigation between cells, no focus ring on selection. This reinforces F-FE-06 from a cross-cutting accessibility-conformance perspective: the timetable is unusable with assistive technology and unreachable without a mouse.
- **Why it matters:** Saudi accessibility regulations (and any future ministry RFP) will require WCAG 2.1 AA on government-adjacent platforms. The principal timetable is one of the most-used screens in the product; shipping it as mouse-only is both a compliance and a usability risk for principals using touch laptops or low-vision tools.
- **Recommended fix:** Wrap the grid in `role="grid" aria-label={t('timetable.grid.aria_label')}` with `aria-rowcount` / `aria-colcount`; render each cell as `role="gridcell" tabIndex={0} aria-label={…subject, teacher, time…}`; add `onKeyDown` for arrow-key navigation, Enter to open the edit modal, Escape to close; add a visible `focus-visible:ring-2` style. Pair with F-FE-06 to avoid duplicate effort.
- **Effort:** M

#### F-XC-07 — Test suite does not cover any of the six high-risk timetable behaviours
- **Severity:** High
- **Location:** `backend/tests/test_smart_scheduling.py`, `backend/tests/test_scheduling_smart_engine.py`, `backend/tests/test_scheduling_api.py`, `backend/tests/test_principal_timetable_page_iter81.py`, `backend/tests/test_timetable_readiness.py`, `backend/tests/test_conflict_resolution_api.py`, `backend/tests/test_drag_drop_api.py`, `backend/tests/test_settings_edit_constraints.py`, `backend/tests/test_subjects_constraints_activerole.py`, `backend/tests/test_smart_timetable_page.py`
- **Description:** A full-text grep for `cross.tenant|other_school|different_school|isolation|leak|school_b|tenant_b` and for `determini|seed|random` across all 41 timetable-related test files returns essentially nothing relevant (the only matches are the literal token "seed" in `test_seed_time_slots`, which is a default-data test, not a determinism test). Mapping the discovered tests to the six behaviours called out by the plan:
  | Behaviour                       | Covered? | Where (or "missing")                                                                                                          |
  | ------------------------------- | :------: | ------------------------------------------------------------------------------------------------------------------------------ |
  | Engine determinism              |    No    | No test runs the engine twice with the same input and asserts identical output (compounds F-EN-02).                            |
  | Conflict detection (correctness)|  Partial | `test_smart_scheduling.TestSmartSchedulingConflicts` and `test_conflict_resolution_api.py` exercise the *endpoints* but assert structural shape only — no fixture forces a known double-booking and asserts it is detected. F-EN-07/F-CN-03 (room overlap never detected) is therefore not test-guarded. |
  | RBAC                            |  Partial | `TestSmartSchedulingAuth` / `TestAuthentication` classes verify "no token = 401". None test the cross-role matrix (teacher cannot publish, parent cannot generate, school_admin cannot delete). |
  | Multi-tenant isolation          |    No    | Zero tests log in as School A and attempt to read/mutate School B's `timetable_id`/`school_id`. Compounds F-API-01/02/04 and F-XC-01. |
  | End-to-end happy path           |    No    | No test drives readiness → generate → review → publish → teacher-view → parent-view as a single scenario. `test_principal_timetable_page_iter81.py` only smoke-tests individual endpoints with existing IDs. |
  | Re-generation / overwrite       |    No    | F-EN-04 (silent overwrite) and F-API-05 (non-idempotent generate) are not exercised by any test.                                |
- **Why it matters:** The most dangerous classes of bug already documented in the audit — multi-tenant leakage, non-deterministic generation, silent overwrite, undetected room conflicts — are all in the part of the test matrix that is empty. Refactors will continue to pass CI while regressing these properties.
- **Recommended fix:** Add a targeted backend test module (e.g. `tests/test_timetable_safety.py`) with fixtures that seed two schools and cover, at minimum: (a) cross-tenant 403/404 on every `school_id`/`timetable_id` parameter; (b) determinism: same fixture in → identical session set out across two runs; (c) double-booked teacher *and* double-booked room must be reported by the conflicts endpoint; (d) full happy-path scenario through the principal pipeline; (e) re-running generate does not multiply rows. Tie these to a CI gate.
- **Effort:** L

## 4. What works well

- **Rich, well-modelled constraint catalogue in seeds.** `backend/seeds/timetable_hard_constraints.py` and `timetable_soft_constraints.py` define 17 hard rules and 12 soft rules with bilingual (ar/en) names, descriptions, scoring weights, and a `validation_key` / `scoring_key` taxonomy — a strong foundation that the engine still needs to honour.
- **Soft-constraint scoring is genuinely dispatcher-driven.** `smart_scheduling_engine.py:1668-1808` cleanly maps each `scoring_key` to its scoring function, demonstrating exactly the pattern that the hard-constraint side is missing — the fix for F-CN-01 has a working template inside the same file.
- **Tenant-isolation primitives already exist.** `backend/middleware/tenant_isolation.py` provides `validate_resource_tenant` and `apply_tenant_filter` helpers and the dependency `require_roles` is established — the critical API holes can be closed by *using* infrastructure that is already written, not by inventing new patterns.
- **Two divergent migration cleanups landed cleanly.** `c8d9e0f1a2b3_migrate_string_timestamps_to_datetime.py` and `e2f3a4b5c6d7_migrate_remaining_string_timestamps.py` show the team has a pattern for safely converting string columns to typed columns — directly reusable for F-DM-07 / F-SD-08.
- **Principal timetable UX is feature-rich.** `frontend/src/components/timetable/PrincipalTimetablePage.jsx` and the `TimetableGenerationJourney`, `TimetableInsightsPanel`, `TimetableReadinessPanel`, `TimetableVersionManager` companions present a thoughtful, guided flow with readiness, generation, review, and versioning surfaces.
- **Readiness pre-check exists end-to-end.** `timetable_readiness_routes.py` plus `TimetableReadinessPanel.jsx` give the principal a structured gap report (teachers, subjects, classes, time slots, assignments) before generation — the right shape, just not yet wired as a hard gate (F-E2E-02).

## 5. Recommended next steps

1. **Close the multi-tenant / RBAC holes on every timetable route** — addresses F-API-01, F-API-02, F-API-03, F-API-04, F-API-16, F-EN-06, F-CN-06, F-XC-01. Rationale: these are the only Criticals plus the cross-cutting tenant-isolation gap; until they are fixed, every other improvement runs on data that can be read or overwritten by the wrong school.
2. **Make hard-constraint enforcement match what the UI advertises** — addresses F-CN-01, F-CN-02, F-CN-03, F-CN-11, F-EN-08, F-EN-09. Rationale: build the `validation_key → callable` registry (mirror the working soft-constraint dispatcher at `smart_scheduling_engine.py:1668-1808`), wire it into both the placement loop and the publish gate, and add the missing room-overlap detector. Single coherent change; one engine file.
3. **Add DB-level uniqueness and atomic persistence for sessions** — addresses F-DM-01, F-EN-04, F-EN-11, F-API-05, F-API-06. Rationale: partial unique indexes on `(school_id, teacher_id, day, slot)` etc. plus a transactional generate/publish wrapper; this turns conflict detection from advisory into authoritative and stops re-runs from silently destroying drafts.
4. **Unify the generation surface** — addresses F-EN-01, F-API-13, F-E2E-01, F-API-17, F-E2E-03. Rationale: pick one of the three generators, retire the duplicate routes (`/smart-scheduling/generate` vs `/principal/timetable/generate` vs `scheduling_generation_routes`), and route manual edits through the same constraint validator so drafts cannot diverge from the rules.
5. **Fix the seed/onboarding pipeline so new schools start usable** — addresses F-SD-01, F-SD-02, F-SD-04, F-SD-05, F-SD-07, F-E2E-07. Rationale: per-tenant seeding of default time slots, working days, and constraint customisation on tenant creation; idempotent re-runs that pick up new constraint rows. Unblocks every brand-new school onboarded after the fixes ship.
6. **Harden the engine against partial-data and concurrency failures** — addresses F-EN-03, F-EN-05, F-EN-13, F-EN-14, F-EN-16. Rationale: iteration cap + best-so-far recovery, advisory lock around generation, structured error codes instead of free-text, and tests covering each failure mode.
7. **Repair the data-model coherence layer** — addresses F-DM-02, F-DM-03, F-DM-04, F-DM-05, F-DM-06, F-DM-07, F-DM-11, F-EN-17, F-SD-08. Rationale: add the missing FKs (sessions→timetables, sessions→rooms, timetable→term), reconcile `pg_models.py` vs `models/scheduling.py` vs `shared_models.py`, convert string time/date columns to typed columns, and enforce single-published-per-term.
8. **Make readiness a real gate and refresh downstream views** — addresses F-E2E-02, F-E2E-04, F-E2E-05, F-E2E-06, F-FE-01, F-FE-03. Rationale: block the generate button until readiness is green, reconcile parent/student endpoints on which timetable to read, invalidate caches on publish, and stop hard-coding Arabic strings / skipping client-side validation in the wizard.
9. **Add audit logging and explicit role permissions for lifecycle events** — addresses F-XC-04, F-XC-02, F-API-12. Rationale: wire `SCHEDULE_PUBLISH` / `SCHEDULE_DELETE` permissions into the new hardened routes and emit explicit audit events for generate/publish/delete/manual-edit so AuditMiddleware tagging is correct.
10. **Repair frontend correctness on the most-used views** — addresses F-FE-02, F-FE-04, F-FE-05, F-FE-08, F-FE-09, F-XC-06. Rationale: fix Arabic-only strings in `TeacherSchedulePage`, validate time slot ranges, batch the workload N+1, stop trusting localStorage / client-supplied teacher IDs, and add keyboard / ARIA support to the timetable grid.
11. **Add the missing test coverage** — addresses F-EN-16, F-XC-07. Rationale: codify the six high-risk behaviours (engine determinism, conflict detection, tenant isolation, RBAC, publish atomicity, end-to-end happy path) so the fixes above don't regress.
