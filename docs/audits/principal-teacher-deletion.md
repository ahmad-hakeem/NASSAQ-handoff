# Principal teacher permanent deletion

## Root cause and evidence

The school DELETE route was already authorized for school leadership. The false
blocker was in ownership validation: school deletion required both scalar links
between a teacher profile and its user account, while platform deletion accepted
one unique, non-conflicting link. Legacy one-sided accounts therefore produced an
ownership-review error unnecessarily.

HTTP regressions reproduced the school failure for both one-sided variants before
the fix. The screenshot does not identify the target account, and retained
production logs did not contain the blocked request; its exact historical reason
has not been independently confirmed.

## Role and scope matrix

| Actor | Target | Policy |
| --- | --- | --- |
| School Principal / School Admin | Exclusive same-school teacher | Direct permanent deletion after ownership/dependency checks |
| School leadership | Foreign-school teacher | Denied by tenant authorization |
| School leadership | Administrator or shared-role identity linked to teacher | Denied by teacher-only ownership checks |
| Platform Admin | Eligible exclusive school teacher | Direct deletion across school scope |
| Any permitted actor | Missing, conflicting, multiple or cross-school ownership | Blocked; resolve the reported ownership/dependency problem |

One valid scalar link is sufficient only when all other checks pass. No account is
matched for deletion merely by name, phone, or email. No permission bypass or
automatic repair of ambiguous identity links was added.

## Cleanup, history, and interface

Existing active school relationship cleanup, identity release, school-count
reconciliation and retained/anonymized educational history remain unchanged.
Historical attendance, assessments, timetables, messages and audit records do not
become new blockers. Existing genuine shared/unknown dependency restrictions remain.

Deletion remains inside the existing locked transaction and savepoint, with
failure auditing after cleanup rollback. Deleted accounts fail subsequent
database-backed authentication.

The school confirmation now uses the existing structured deletion-error display.
Authorization failures, blockers and internal failures remain visible in the
dialog with available resolution details. It no longer presents platform approval
as a prerequisite for ordinary school deletion. Success refreshes the parent list
before closing; duplicate submissions remain disabled.

## Verification

- Backend: 52 tests passed across teacher permanent deletion and platform teacher
  account deletion, including real school DELETE requests for both one-sided
  variants, cross-school denial, protected/shared accounts, active cleanup,
  historical retention, identity reuse, rollback and failure audits.
- Frontend: 27 tests passed across three focused suites, covering success,
  duplicate submission, 403/409/500 diagnostics, sensitive-field exclusion and reset.
- No production account was deleted for verification. Publication and an authorized
  production deletion are still required before claiming production confirmation.