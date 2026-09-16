# Restored-schema development alignment

## Scope and approval

The user explicitly approved backing up and removing these development-only
columns. No production mutation, migration, or publish was performed:

- `bulk_import_batches.ownership_version`
- `schools.configuration`
- `schools.location`
- `schools.setup_completed`
- `schools.setup_steps_completed`
- `schools.principal_mobile`

Read-only inspection found all five school columns NULL across 1,228 school
rows. Four of eight import batches held ownership version 2.

## Backup and execution

The verified, permission-restricted, git-ignored workspace backup is:
`.local/private-backups/schema-alignment/development-columns.json`.
It contains the four non-NULL marker values with batch IDs, the empty set of
non-NULL school values, column types, and a fingerprint of all affected rows.
It contains no credentials. Keep this backup outside version control; it is a
workspace file, not a separately managed or guaranteed off-workspace backup.

Removal used one explicitly development-targeted transaction, short lock and
statement timeouts, and exclusive locks on both affected tables. A guard
recomputed the pre-backup fingerprint and would abort on any data change.
All drops used RESTRICT, not CASCADE. The transaction committed successfully.

Recovery, if separately authorized, must target development only: recreate
the six nullable, no-default columns using the recorded types, then restore
the four marker values by existing batch ID from the backup. The school
columns need no value restoration because all were NULL. Recreating these
columns would reintroduce the development-to-production Publish discrepancy;
do not run recovery as part of publishing.

## Verification and limitations

- Read-only queries confirm all six columns are absent in both environments.
- Catalog fingerprints match for 1,014 columns (including types, nullability,
  defaults, identity and generated attributes), 377 indexes, and two sequences
  in the public schema.
- The 214 constraints differ only in the representation of two status checks:
  `parent_invitations.ck_parent_invitations_status` and
  `workspace_collaborators.ck_workspace_collaborators_status`.
  Their allowed status lists match; the cast placement differs. Neither
  constraint was altered.
- `cd backend && ENVIRONMENT=development TESTING=1 python -m pytest -q
  tests/test_managed_schema_safety.py
  tests/test_bulk_import_rollback_ownership.py
  -k 'not removed_ownership_marker_does_not_round_trip'`
  passed: 25 tests, one database-writing test deliberately deselected.
- No-marker import undo still preserves parent accounts/users. Runtime
  compatibility code and historical migrations were not changed.

**Publish verification is pending.** The documented `explainSchemaDiff`
callback was unavailable in this task environment, including an independent
agent check. Catalog fingerprints are not a substitute for the Publish
planner. Do not claim zero pending SQL or publish until the actual Publish
review shows no schema statements. If statements remain, inspect them without
accepting or applying them.

The user requested moving this work to main before that final review.
Completion of the development alignment therefore does not certify a
migration-free publish. Recheck the actual Publish plan from main as a
separate follow-up, retaining the prohibition on production mutations.

The deployment/database guidance describes automatic schema comparison on
Publish; no supported skip-schema-comparison switch was verified. Do not add
migration commands to builds or startup, overwrite production data, or run
historical additive migrations to resolve this discrepancy.

## Main-workspace verification after merge — 2026-09-16

The task-local removal described above had not changed main's development
database: a subsequent read-only inspection found all six columns still
present, and the actual Publish planner proposed six additions.

With renewed explicit user approval, the six columns were removed from main
development only. The verified backup is
`.local/private-backups/schema-alignment/main-development-columns-2026-09-16.json`
(permission-restricted and git-ignored). A single transaction locked both
tables and compared their affected values and column metadata with the backup
before executing the six RESTRICT drops. Production was not mutated.

Final checks:
- All six columns are absent in both main development and production.
- Actual Publish comparison: `hasDiff: false`, `statementsToExecute: []`,
  no warnings or structural-data-loss flags.
- Focused schema-safety and import-undo tests: 25 passed; the database-writing
  persistence test was deliberately deselected.

This supersedes the pending main-workspace schema comparison above. It does
not certify a future preview build or publish; neither was initiated here.