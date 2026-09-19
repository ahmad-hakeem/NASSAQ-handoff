# Teacher deletion and re-registration

## Follow-up findings — 2026-09-19

The earlier correction missed a real legacy shape: `teachers.phone` is populated
while the reciprocally linked `users.phone` is NULL. Requiring the submitted
mobile to match both rows rejected an otherwise valid retained account, then
the full national-ID uniqueness check returned the misleading duplicate error.
The credentials-recovery writer could create this shape by omitting the phone
when creating a missing login account; it now copies the teacher's phone.

The deployed frontend also lacks the explicit restore-confirmation code. Public
asset fingerprints prove the older UI is still live, but do not expose the
exact deployed commit. See `teacher-production-consistency.md`.

The corrected resolver treats a missing duplicate user phone as no contradictory
evidence, not as a matching identity by itself. It still requires proven
same-school ownership and rejects populated conflicts, foreign contacts,
ambiguous links and administrative suspension. Explicit restoration may repair
a proven one-sided link and fill only a missing duplicate phone. It never
changes credentials, MFA or submitted profile details. A legitimate profile
without any account can be explicitly restored as profile-only; matching or
ambiguous accounts require review rather than automatic merging.

Global normalized user-only collisions are checked even when no teacher profile
matches. Create uses identity locks and an atomic savepoint; invalid normalized
input returns a controlled 400. Suspension follows the actual user-status API
and retained pre-delete audit state. The UI hides internal cleanup keys and
preserves same-school lists on failed refreshes without retaining another
school's data.

### Before/after relationship map

| Record / field owner | Before deletion | After deletion | After confirmed account restore |
|---|---|---|---|
| Teacher: national ID, profile mobile, email | Active | Retained, inactive, deletion metadata | Same row, active |
| User: login email, optional duplicate mobile | Active (unless already suspended) | Retained, inactive | Same verified row; missing duplicate mobile filled |
| Reciprocal account links | Retained IDs | Retained IDs | Only proven missing side may be repaired |
| Teaching/class/subject/session assignments | Existing state | Inactive, retained | Remain inactive for review |
| Attendance, grades, messages, reports/history | Retained | Not purged | Not purged |
| Recorded authentication sessions | Usable until revoked/expired | Revoked | Not revived |
| Audit | Existing history | Delete + previous login activation state | Restore entry added |

### Final verification

- 49 backend tests passed across lifecycle and subject/delete/restore suites.
  Includes real create/delete/re-add, legacy NULL mobile, partial links,
  suspension, malformed input, normalized orphan-user conflicts, profile-only
  restoration, failed-write rollback and retained-token rejection.
- A two-independent-session database race creates exactly one teacher/user.
- 51 focused frontend tests passed, including stale-scope and failed-refresh
  handling.
- A read-only transaction checked the three recently deleted development
  teachers with a populated profile phone: all resolve to their own retained
  restore candidate. None was reactivated during that check.
- Publish schema comparison reported no pending statements or data-loss diff.
- No production write, migration or bulk cleanup was performed. Publishing and
  post-publish verification remain necessary; this is not a live-fix claim.

The following sections document the original implementation and retention
policy; the follow-up findings and verification above supersede its initial
eligibility limitations and test counts.

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