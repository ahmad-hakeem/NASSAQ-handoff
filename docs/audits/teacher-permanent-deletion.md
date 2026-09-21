# School teacher permanent deletion

## Approved policy and scope

This policy supersedes the **school DELETE** policy in
`teacher-delete-restore.md`. School principals, school admins and platform admins
may permanently delete an **exclusively school-teacher** account. A platform
admin does not bypass the exclusivity/ambiguity checks. Shared, multirole,
multischool, inconsistent, missing-account or unclassified relationships require
platform-admin review; this endpoint performs no automatic account splitting.

Independent-teacher callers keep the existing workspace-scoped soft-delete
behavior. Previously soft-deleted school records remain eligible for the
existing explicit restore flow; newly permanently deleted records cannot be
restored. Re-add creates fresh account/profile IDs and credentials.

## API and transaction contract

`DELETE /api/teachers/{teacher_id}` remains the endpoint.

* Success: HTTP 200, `success: true`, `permanent: true`,
  `message: "تم حذف المعلم نهائياً"` and integer per-entity `cleanup` counters.
* Shared/ambiguous/unclassified relationship or schema drift: HTTP 409,
  Arabic detail: `لا يمكن حذف هذا الحساب نهائياً لوجود ارتباطات مشتركة أو غير مؤكدة. يلزم مراجعة مسؤول المنصة.`
  The application's normal error middleware exposes string details as
  `error.message` (`error.code = HTTP_409`).
* Missing/already deleted: 404. Unauthorized role: 403. Foreign school: 403.
* Independent-teacher success retains the prior soft-delete response.

The route delegates school deletion to
`backend/services/teacher_permanent_deletion.py`. Its savepoint covers ownership
proof, dependency inventory, history changes, account deletion, counts and audit.
Success is returned **only after explicit commit**. Guard/audit/cleanup failure
rolls back the savepoint; commit failure rolls back the transaction and cannot
return success. This is required because request middleware commits even 4xx
responses. No background cleanup job is responsible for essential deletion.

Teacher and user rows are locked. Because legacy profile/user and JSON membership
links have no FKs, writes to users, teachers, generic_documents, schools and
workspace_collaborators are serialized with table locks during the operation.
This is intentionally conservative; deletion can temporarily delay unrelated
identity/directory writes. Concurrent duplicate deletions yield one success and
one 404, not an integrity-error 500.

## Ownership proof

The teacher must have exactly one uniquely linked `users` record with primary
role `teacher`, matching school, no additional linked roles, no parent/student profile,
no foreign primary tenant, and no custom permissions requiring review.
Every other teacher profile, including inactive profiles, is checked for claims
on the account. Other users' scalar teacher links and nested linked-role claims
are checked. Conflicting or duplicate normalized email/mobile/national identity
on other accounts/profiles blocks deletion. Missing duplicate contact fields
are not contradictory evidence; populated mismatches are.

A unique one-sided scalar profile/account link can prove ownership when the
opposite link is absent, but conflicting links cannot. Only the exact scalar
`linked_roles: ["teacher"]` is treated as a redundant primary-role mirror.
Nested teacher-role objects may carry different tenant scope and remain blocked.
Ownership failures now distinguish profile/account links, tenant, primary role,
additional roles, parent/student claims and primary tenant using non-PII reasons.

## Redundant-role regression evidence

The pictured failure was a domain ownership guard, before FK cleanup—not a
database integrity exception. Read-only development inspection found reciprocal
links, matching school/primary tenant, teacher role, no parent/student profile,
empty custom permissions, and the redundant scalar teacher-role list.
The target was not deleted or modified during diagnosis. The matching named
profile was not found in the production lookup, so no production incident
reproduction or successful production deletion is claimed.

A bounded read-only dependency inventory in the development database found
19 teacher assignments, 20 teacher-class assignments, 351 timetable-session
documents, 5 teacher-attendance documents, 55 notification-log documents and
147 timetable-run-log documents. These are known cleanup/history categories;
none had an explicit foreign top-level school reference. This inventory does
not replace the deletion service's locked nested ownership and FK checks.

Both principal UI entry points send authenticated `DELETE /teachers/{id}` with
no body. Both guard in-flight duplicate submissions. Failed deletion retains
the record; success refreshes the directory and closes the profile where open.
A completed deletion retried later returns 404, not a misleading dependency 409;
this is state-idempotent, not a cached replay of the original success response.

Regression tests exercise school and platform deletion aliases, real public
creation, ordinary assignments, retained history, re-adding released identities,
shared-role rejection, authorization and rollback. The changes do not authorize
automatic repair or deletion of ambiguous real accounts.

School principal/creator links, owned independent workspaces, collaborator
claims, independent lesson plans, student/parent ownership and unknown JSON
collections block deletion. Known membership documents must describe a single
teacher role in this school. Linked JSON documents are checked for foreign
school scopes, including nested objects. Principal access is tenant checked
before any changes. Platform access does not authorize destroying a shared
account.

`user_relationships` is **not** a blanket cleanup exemption. The graph-engine
format must have a teacher-profile source, an explicitly teacher-specific type
(`teaches_class`, `homeroom_for`, `teaches_subject`, `teaches_student`, or
`employed_at`), matching typed destination, same tenant, and an actual destination
row in that tenant. Endpoints are locked and checked. Parent/guardian/principal
types, missing/foreign destinations, unknown types/fields and mixed schemas
block with 409, even if the document itself claims the right school.

The identity-engine format (`user_id_1`, `user_id_2`) resolves both endpoints as
**users**, not typed school entities. Its `teacher_class`/`teacher_subject`
labels alone cannot prove class/subject ownership. These untyped legacy edges
require platform review; parent/guardian/principal and unknown edges likewise
block. They are not silently erased to make an account appear teacher-only.

## Actual schema/dependency inventory

Inventory was read from ORM entities **and the development PostgreSQL catalog**,
including FK delete actions, nullable columns, and FK-less columns. No real
teacher account was deleted to discover dependencies. Production has not been
destructively tested. Runtime catalog validation rejects new/unmapped incoming
FKs or changed delete actions on account/profile and explicitly deleted active
tables rather than trusting an unreviewed CASCADE.

| Entity / reference | Actual dependency and deletion policy |
|---|---|
| `users` | Authentication identity, unique email, phone/national identity copies, password/reset hashes, role/linked roles, school membership and MFA flags. Actual row deleted; no disabled original account retained. |
| `teachers` | Authoritative school profile; `(national_id, school_id)` unique constraint includes inactive rows. `user_id` and legacy `teacher_id` are FK-less. Actual original profile deleted. All original reusable identifiers released from these owners. |
| `teacher_assignments`, `teacher_class_assignments` | Non-null teacher FK with **CASCADE**. Explicitly deleted, not soft-deactivated. |
| `teacher_sessions` | Non-null teacher FK with **CASCADE**: **must not cascade**. Repointed to a non-login deleted-teacher reference before original profile deletion. Completed lessons retained; scheduled lessons cancelled. |
| `assessments`, `behaviour_records`, `session_notes` | Nullable teacher FKs, **SET NULL** in schema. Repointed to deleted-teacher reference to retain recognizable attribution. |
| `classes.homeroom_teacher_id` | Nullable teacher FK, SET NULL. Cleared; the marker is not assigned an active homeroom. |
| `schedule_sessions` | Nullable teacher FK and assignment FK, both **SET NULL**. Row retained, teacher/assignment detached, status cancelled, teacher display label replaced. |
| `assessment_submissions` | `graded_by` user FK SET NULL; assessment/student links and scores retained. Assessment is not deleted. |
| `attendance` | `recorded_by` user FK SET NULL; student/session/date/status retained. |
| `session_interactions`, `session_event_log`, `student_skills` | Nullable author/assessor user FKs SET NULL; educational content retained. Session IDs remain valid because teacher_sessions are not cascaded away. |
| `lesson_plans.created_by` | **Non-null user FK CASCADE**. These are independent-workspace plans; any matching row blocks as independent/shared ownership evidence. They are never silently cascaded away. |
| `daily_tasks.user_id` | Nullable user FK **CASCADE**. Explicitly cleared before account deletion, preserving task history. `created_by` is SET NULL. |
| `messages.sender_id`, `recipient_id` | Nullable user FKs SET NULL. Communication content/history retained; deleted identity can no longer send/receive. |
| `notifications` | Non-null user FK CASCADE. Explicitly removed. |
| `notifications_preferences` | ORM declares CASCADE; inspected live table has **no user FK**. Explicit cleanup therefore does not depend on cascade. |
| `mfa_factors`, `mfa_recovery_codes`, `mfa_pending_challenges`, `mfa_email_otps`, `mfa_webauthn_challenges` | Non-null user FKs CASCADE; explicitly removed, including secrets and pending challenges. |
| `user_sessions` | **No user FK**. All rows removed without the former 500-session cap, including access/refresh JTIs and family references. |
| `revoked_tokens` | JTI-based denylist without user relation. Existing denylist entries retained until normal expiry; no credentials/PII added. |
| `revoked_token_families` | Unmapped, FK-less user reference. Revocation stays; user reference cleared. |
| `impersonation_sessions` | Unmapped, FK-less original/target IDs. Original-user match is privilege ambiguity and blocks. Target-user sessions are ended, target detached and reason replaced with a non-PII deletion reason. |
| `teacher_record_backfill_794` | Unmapped rollback ledger with user/profile IDs. Matching entries removed so a future migration rollback cannot recreate the erased identity. |
| `schools`, `workspace_collaborators` | FK-less principal/creator/collaborator ownership is checked and blocks shared account removal. |
| `parent_invitations`, typed timetable/grade creator fields | Legacy FK-less attribution is detached to a deleted reference, not left pointing at the erased account. |
| `approval_requests`, `approval_events`, `registration_requests` | Nullable reviewer/requester/actor user FKs SET NULL; administrative history retained. |
| `audit_logs`, `bulk_action_history`, `product_issues`, `issue_comments`, `issue_activity_log`, `issue_versions` | Nullable user-attribution FKs SET NULL; history retained. Newly generated deletion audit contains IDs/action/counts only—no name, email, national ID, mobile, password, token or MFA secret. |
| `events`, `calendar_events`, `ai_interventions`, `platform_settings`, `system_settings` | Nullable user-attribution FKs SET NULL. Content/settings retained. |

The deleted-teacher reference is a deterministic `deleted-teacher:<school-id>`
row labeled `معلم محذوف`. It has **no school membership** (`school_id=NULL`),
user link, email, mobile, national ID, credentials, activity or `deleted_at`.
It is a referential tombstone, not a reusable teacher identity. Educational
records retain their own original school ID. Keeping the marker outside school
membership prevents it appearing in school directory/counts, including
`include_deleted=true`. It cannot be restored; teacher detail/edit routes reject
marker IDs. This avoids a schema migration for non-null historical teacher FKs.

## GenericDocument and snapshots

The modern `timetable_sessions`/`schedules` document paths are not assumed to be
relational tables. JSON candidates are searched without a result cap for either
original identity ID. Recursive traversal handles nested objects, arrays and
ID-keyed maps; it is not limited to a root `teacher_id`.

* Explicit active-document deletion: teacher subject/class assignments,
  teacher role/membership documents, user relationships, refresh/reset token
  documents, notifications/preferences, API keys, QR codes, availability,
  teacher constraints/preferences, quotas/duties and standby overrides.
* Retained and rewritten: timetable/class session snapshots, schedules and runs,
  attendance/assessment/grade/behaviour/session history, portfolios/evidence/
  files, monitoring/follow-up, curriculum/lesson history, educational messages,
  substitute history, student activity/score history, timetable logs/conflicts.
* Referenced identity IDs and exact known identity/name copies in retained
  JSON are replaced with deleted references/labels. Nested matching schedule
  assignments are cancelled/inactivated without disabling an unrelated
  teacher's entire timetable.
* Mapped JSONB history snapshots are also traversed for identity references.
  The entire candidate inventory is locked and preflighted **before any write**.
  Both the containing relational row's tenant and nested JSON tenant scopes are
  validated; e.g. a foreign school's `timetable_runs.result`, `config` or `data`
  referencing the target teacher produces 409 without changing either school's
  rows. The mutation phase uses only this already-validated inventory.
  Unknown linked collection names or unknown live FK-less identity columns
  block deletion rather than being ignored.

Historical educational free text and attached-file bytes are **not blindly
rewritten or destroyed**. They may contain author mentions; this is educational
retention, not a claim of universal content erasure. Neither original account
nor credential/unique-identity ownership survives. No external identity
provider, external teacher cache, or asynchronous auth deletion integration was
found on this route. Authentication uses current DB account existence; both
access and refresh tokens fail after deletion and after re-add with new IDs.
Session recording now locks/rechecks a live user to prevent a stale login from
inserting a FK-less session after deletion.

## Verification and deployment

Tests were written before implementation, then exercised against rollback-only
fixtures. The common backend fixture now uses an externally owned transaction
and savepoint-joined sessions, so explicit handler commits cannot persist test
users. The real two-connection concurrency test uses a uniquely named disposable
test schema, creates only test entities, and drops that schema afterward.

Coverage includes delete/re-add with the same email/mobile/national ID; duplicate
404; genuine concurrent deletion; unauthorized/cross-tenant callers; shared
profiles, linked roles, identity collisions, nested claims and unknown document
blocking; preserved teacher lessons/attendance/assessments/submissions/messages/
JSON history; active assignment/session/MFA removal; directory/count correctness;
old access/refresh rejection; stale-session insertion prevention; injected
audit and commit rollback; and an actual unreviewed CASCADE FK rejection.
Legacy restoration and independent-teacher soft-delete suites remain covered.

Focused verification: **90 passed** across
`test_teacher_permanent_delete.py`, `test_teacher_restore_create_contract.py`,
`test_teacher_subject_soft_delete_restore.py` and
`test_session_revocation_routes.py`; Python compilation and `git diff --check`
also passed. No skipped tests are counted as passes.
Review regression coverage includes all three TimetableRun JSON columns with
foreign row and nested scopes, both actual relationship storage formats,
parent/guardian/principal/unknown edges, mixed schemas, missing/foreign
destinations and a positive verified teacher-to-subject cleanup.

No production-data cleanup, schema migration, uniqueness weakening, or git
commit is required/performed. Operational limitation: conservative inventory
and table locks favor correctness over high deletion throughput. New entity
types must receive an explicit retention/ownership classification before this
endpoint will remove an account linked to them. Publishing is required for
production behavior to change.