# Teacher delete/re-add production consistency audit

Audit date: 2026-09-19. Scope was read-only: public `GET` requests, deployment
metadata/log reads, and `SELECT` queries against the development and production
catalogs. No publish, API mutation, database write, or lifecycle test was
performed.

## Deployment and build evidence

- `getDeploymentInfo` reports a public, successful **autoscale** deployment:
  primary `https://nassaqapp.com`, additional
  `https://nassaqapp.replit.app`.
- Both `/` URLs returned HTTP 200 and the same fingerprints:
  HTML ETag `e90f9e3ff0823817ffa58f90deada5b2`;
  `/static/js/main.b3bc3d96.js` (2,101,282 bytes, ETag
  `9e9060ea8f665e233f9d788d2dcc429c`); and
  `/static/css/main.91a87e71.css` (366,186 bytes, ETag
  `e4a38ffaf2b9b66131bc1782ee5bec03`). The responses report
  `Last-Modified: Wed, 16 Sep 2026 23:39:14 GMT`.
- The deployed JS contains the older generic text `Restore teacher`, but does
  **not** contain `TEACHER_RESTORE_AVAILABLE`, `Restore prior teacher account`,
  `Restore the prior teacher account?`, `The prior account and history will be
  reused unchanged`, `can be restored`, or `Recently deleted`.
- The current workspace source does contain the new
  `TEACHER_RESTORE_AVAILABLE` wizard branch and explicit prior-account
  confirmation text. Its local Git HEAD at audit time was
  `f2351f9bf6a446ef2aabd0a36ebdf94617722dfb`.
- Public OpenAPI probes at `/openapi.json`, `/api/openapi.json`, `/api/docs`,
  and `/docs` all returned 404, so they provide no independent backend route
  inventory. Deployment logs show successful schema-gate/startup events on
  September 19 but expose no trustworthy source commit/build ID.

**Conclusion:** the two public hostnames serve the same frontend build, and
that build does not include the new create-conflict/explicit-restore UI. This
proves feature absence in the public frontend asset; it does not identify the
exact deployed commit, nor prove whether an unadvertised backend handler is
present. The asset hash and workspace HEAD must not be treated as equivalent.

## Database comparison

Catalog reads show the relevant `teachers` and `users` schemas are identical
between environments (system-generated check-constraint names differ only by
catalog object IDs):

- `teachers` has scalar `email`, `phone`, `national_id`, `user_id`,
  `teacher_id`, `is_active`, `deleted_at`, and `deleted_by`; JSONB columns are
  only `preferences` and `constraints`.
- `users` has scalar `email`, `phone`, `national_id`, `teacher_id`,
  `tenant_id`, `is_active`, and `status`. Its JSONB columns include
  `linked_roles`, `permissions`, and `notification_settings`.
- Both have the same primary/foreign keys and indexes, including the
  non-partial unique constraint/index
  `uq_teachers_national_id_school (national_id, school_id)`, teacher
  school/active indexes, unique `users.email`, and `users.phone` (non-unique).
  Neither table has a database trigger.
- Alembic heads differ: production is `b2c3d4e5f6a7`; development is two
  revisions ahead at `d4e5f6a7b8c9` via `c3d4e5f6a7b8`. Those revisions concern
  bulk-import ownership metadata and legacy school columns, not teacher/user
  lifecycle columns. Relevant schema parity is therefore proven despite the
  global migration-head difference.

### Deleted-row aggregates (no identities returned)

| Measure | Development | Production |
|---|---:|---:|
| Deleted teachers | 6 | 11 |
| Date range | 2026-08-03–2026-09-19 | 2026-05-31–2026-09-13 |
| Latest-date rows | 5 | 1 |
| Inactive / deleted-but-active | 6 / 0 | 11 / 0 |
| Teacher scalar phone present | 3 | 9 |
| Direct linked user exists | 5 | 4 |
| Direct user phone null / present | 5 / 0 | 2 / 2 |
| Teacher phone present while direct user phone null | 3 | 0 |
| Teacher JSON `phone` key | 0 | 0 |
| Orphan non-null `teachers.user_id` | 0 | 0 |

Development's five September 19 rows all have direct users; three have a
teacher phone, while all five `users.phone` values are null. Production's
single September 13 row has a teacher phone but no directly or reversely linked
user. Production's one August row has a direct/reverse user whose phone is
null. Production link-shape counts are: three bidirectionally consistent, one
direct-link/reverse-link conflict, one reverse-only, and six unlinked deleted
teachers. Development has three bidirectionally consistent, two direct-only,
and one unlinked.

The phone is not shadowed by a `data` JSON column: neither table has such a
column, and no deleted teacher has a `phone` key in `preferences` or
`constraints`. The meaningful aliases are reciprocal relationship columns,
`teachers.user_id -> users.id` and `users.teacher_id -> teachers.id`, not phone
aliases. Current source deliberately treats `teachers.phone` as authoritative
for candidate discovery and permits `users.phone` to be null; a non-null,
different user phone is a conflict. Therefore null user phones are compatible
with the intended restore policy, but missing/conflicting account links require
manual review.

## Safe administrator procedure

No broad cleanup is indicated, and no cleanup is required merely because
`users.phone` is null. Prefer the application's explicit restore operation once
the matching build is published. For a row that instead returns
`TEACHER_ACCOUNT_REVIEW_REQUIRED`:

1. Identify one teacher only, confirm the school/tenant and authoritative
   identity with an authorized administrator, and stop if ownership is
   ambiguous.
2. Take a timestamped backup/export of that teacher, every candidate user, both
   reciprocal IDs, status fields, and relevant audit/history rows. Verify the
   backup can be read before changing anything.
3. In a single transaction, lock only the verified teacher and candidate user
   rows. Re-check that no active or cross-tenant teacher/user now owns the
   email, national ID, phone, or reciprocal IDs.
4. Repair only a proven missing reciprocal link. Never choose an account by
   phone alone, bulk-copy `teachers.phone` into `users.phone`, clear the
   national-ID uniqueness constraint, delete history, or bulk-activate rows.
   A conflicting reciprocal link must be investigated rather than overwritten.
5. Restore through the supported endpoint so token revocation, audit entry,
   dependent-row policy, and school counts follow application rules. Keep old
   assignments inactive for explicit review.
6. Validate teacher/user status, tenant ownership, reciprocal IDs, sign-in
   policy, audit record, counts, and inactive dependents; then commit. Roll back
   on any mismatch and retain the backup and review record.

This procedure is intentionally per-record and requires a fresh read-only
inventory immediately before any separately authorized production change.