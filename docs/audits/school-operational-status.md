# School Operational Status Audit

## Scope

This report records the Task #1164 lifecycle audit run against the **workspace
database only**. It is not evidence of a production-database audit.

Command:

```text
cd backend && python scripts/audit_school_lifecycle.py --report /tmp/school-lifecycle-audit-1164.json
```

The command ran inside a PostgreSQL read-only transaction and selected only
`id`, `status`, `tenant_type`, `archived_at`, and `pending_hard_delete`. The
audit was bounded at 10,000 rows. It does not query school names, contact
details, users, or credentials.

## Aggregate Results

- Rows inspected: 1,228
- Bound reached: no
- `active`: 1,227
- `setup`: 1
- Null statuses: 0
- Unknown statuses: 0
- Noncanonical supported statuses (for example `ACTIVE` or ` active `): 0
- Archived-state timestamp contradictions: 0
- Pending-hard-delete contradictions: 0
- Ambiguous rows: 0

No school identifiers are included in this committed report.

## Mutation Decision

No data was mutated. The audit found no null, unknown, noncanonical, or
contradictory lifecycle values, so there was no deterministic correction to
apply. Promoting or otherwise changing a school without such evidence would
alter authorization-sensitive lifecycle state and was therefore explicitly
out of scope.