# Timetable settings persistence

## Root cause

The form submitted camelCase keys such as `breakDuration`, but they were stored in
custom JSON while settings reads and slot generation preferred other snake_case
fields or defaults. The form also expected different response names and used
truthy fallbacks, losing valid zero values. Slot generation separately ignored
custom JSON breaks and clamped zero durations.

## Canonical contract

`GET /api/school/settings` reads the current school's canonical settings row.
Canonical ORM timing columns take precedence, with legacy alias compatibility.
Break definitions and a settings version live in custom JSON; no migration is
required. A null break duration means inherit BASE, including on subsequent saves;
an explicit empty break list means no breaks.

The current form sends `PUT /api/school/settings`, including `breakDuration: 25`
and `expected_version` from GET. The response includes `settings` containing the
saved canonical values and compatible aliases, plus `time_slots_regenerated`.
Tests compare the submitted value, response, database column, subsequent GET,
and generated break duration. Sequential 20 → 25 → 30 saves retain inheritance.

Validation covers integer/range constraints, ordered HH:MM times, weekdays,
break placement and total day duration. Required minutes are exactly lesson
minutes plus configured break minutes, with no implicit passing-time gaps.
The UI exposes the day end and a live Arabic/English time budget.
Invalid writes and slot
regeneration failures roll back. Successful writes commit before success.

## Published and draft policy

Timing changes are rejected while a published timetable exists. The UI offers
explicit confirmation to unpublish while preserving any current draft. It never
unpublishes automatically on save.

After unpublishing, saving regenerates slots and retargets compatible active
draft session timings. If periods or working days are removed, incompatible
draft versions are archived and a new editable draft retains only compatible
placements. An entirely incompatible draft produces a clean empty successor.
Archived placements are retained, but retired from operational queries.
Review the updated draft, fill any missing placements, then publish it again.

Unpublishing now always archives the formerly published version and either
retains an existing editable draft or clones one. Explicit history reads retain
archived placements. Teacher and parent operational reads require publication;
they do not show the unpublished editable copy.

Settings updates and publish/unpublish/ensure-draft share a school-scoped
transaction lock. The settings tab echoes a version to reject stale writes;
older API clients may omit that version for backward compatibility and therefore
do not receive optimistic concurrency protection.

## Caches and frontend state

No backend settings cache was found in this path. GET reads the committed row.
The form applies the canonical save response, refreshes readiness/slot count,
retains unsaved edits on errors, and rejects stale asynchronous responses.
Loading errors do not silently initialize a saveable default form.
Version conflicts offer an explicit reload that replaces the local draft.
Successful structural saves refresh the schedule grid and version list and clear
stale cell/session selections. No persistent backend timetable cache was found
on the investigated paths.

## Draft reconciliation and generation

Affected entities are school_settings, time_slots, timetables,
timetable_sessions, timetable_runs and audit_logs. Settings/time slots are
school-scoped; timetable/session history is retained under archived versions.
Teacher/class/subject assignment entities are not deleted by reconciliation.

Settings, slot regeneration, archival, compatible placement cloning, audit and
active-run cancellation commit together. Injected failures verify rollback.
The response includes draft_reconciliation counts (remapped_sessions,
archived_drafts, excluded_sessions, editable_draft_id) and
cancelled_generation_runs. Arabic/English success messages explain the result.

Active pending/validating/loading/generating/optimizing runs are invalidated on
timing changes. A captured settings version is checked under the school lifecycle
lock immediately before generation output writes, rejecting stale results.

Focused reconciliation verification: 69 backend tests passed together,
including settings/master-grid, unpublish/republish, teacher/parent visibility,
generation fencing and rollback. Fourteen focused frontend tests passed and the
production frontend build compiled. These do not establish production behavior
before the changes are published.

## Verification limits

Real database/API/slot-generation tests cover persistence, successive inherited
break updates, zero/no-break values, aliases, partial legacy updates, school
isolation, invalid rollback, stale versions, published rejection and draft timing.
Lifecycle tests cover explicit unpublish with draft preservation and locking.
Frontend tests cover reload, failures, conflict handling and stale responses;
the production frontend build succeeds.

The nearby static test's retired frontend path has been corrected. Boundary,
structured validation and master-grid fallback tests cover the removal of hidden
passing time as well as zero-duration and explicitly absent breaks.

Shared time slots are not weekday-aware. A selected weekday on a break was
previously ignored; such inputs now receive a clear validation error instead of
silently applying the break to every day. True weekday-specific timing is not
implemented by this correction.

Production logs establish endpoint traffic but do not capture the screenshot's
request body. No production settings were changed during verification. Publication
and production verification remain outstanding.