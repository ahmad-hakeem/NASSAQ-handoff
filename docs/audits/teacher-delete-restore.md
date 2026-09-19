# Teacher deletion and re-registration

## Root cause and active route

The principal's Add Teacher wizard submits to `POST /api/teachers/create`.
The first registered handler is `academics_teacher_routes.create_teacher_wizard`;
a later teacher-management factory also registers that path but is not the
handler reached by this request. A regression test asserts this routing order.

Deletion was already a soft delete, but the wizard treated retained identities
as ordinary duplicates instead of offering the existing restore operation.
The teacher national-ID/school uniqueness constraint includes deleted records.
Removing that constraint or ignoring inactive records before inserting would
create inconsistent accounts, not solve the lifecycle mismatch.

## Retained records

- Teacher profile: inactive, with deletion timestamp/actor; identity retained.
- Login user: inactive; email, phone, password and MFA settings retained.
- Teacher/class/subject links and timetable/class-session records: retained
  but deactivated by the existing deletion operation.
- Attendance, assessments, messages, portfolio and audit history: not purged.
- Delete/restore each write an audit entry and reconcile school counts.

## Implemented policy

Restore and reuse, after explicit confirmation; never silent resurrection or
permanent deletion.

The wizard receives `409 TEACHER_RESTORE_AVAILABLE` only when the submitted
identity consistently matches a same-school soft-deleted teacher and its
unambiguously linked inactive teacher account. Active, foreign-school,
unrelated inactive and inconsistent identities do not receive a restore hint.

Confirmation calls the existing restore endpoint. The original account and
teacher IDs, password, MFA and history are reused. Wizard edits are not applied.
Old class/subject/timetable assignments remain inactive for deliberate review.
The success screen does not show or imply newly generated credentials.

Delete and restore run inside savepoints and lock affected teacher/user rows.
An audit or cleanup failure rolls back the operation. Deletion revokes recorded
active access-token JTIs and refresh chains; restoring the account does not
revive those recorded tokens. The frontend refreshes the directory and counts.

## Existing data and migration policy

No schema migration, uniqueness-constraint removal, identifier clearing or
production cleanup was performed or is required for consistent deleted records.
Those records become eligible through the explicit confirmation flow.

Ambiguous, missing or cross-school account links must be reviewed by an
authorized administrator. Do not bulk-activate them, merge identities based on
phone alone, or delete historical rows. Before any future repair, inventory the
affected links read-only, establish ownership, back up the affected records,
and repair only individually verified links in a transaction.

## Verification and limitations

- Backend: 29 passed across the lifecycle contract and existing subject
  soft-delete/restore coverage. Tests use the application's HTTP client and a
  rollback-backed test database.
- Covers delete → create conflict → explicit restore, identity preservation,
  ordinary duplicates, foreign-school denial, injected audit failure rollback
  and access-token rejection before and after restoration.
- Legacy live wizard suite: 18 skipped because its external URL/credentials were
  unavailable; these are not counted as passes.
- Frontend: 51 tests passed across four focused suites.
- Chromium: cancel sent zero restore requests; confirmation sent exactly one;
  directory refreshed and credential fields remained hidden. This exercised the
  real React app with mocked API responses, not a live end-to-end database flow.
- Row locking is implemented, but true simultaneous requests from independent
  database sessions were not stress-tested.
- Production has not been modified or verified by a destructive lifecycle test.
  Publishing is required before the changed behavior becomes live.