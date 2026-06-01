# Database Backup & Restore Runbook

This runbook covers backing up, restoring, and recovering the NASSAQ
PostgreSQL database. The database is an external, managed PostgreSQL instance
(Replit co-located Postgres) reached via `DATABASE_URL`. It lives **outside**
the autoscale container, so it survives server/process/container restarts and
redeploys. This runbook is about recovering from *logical* data loss (a bad
migration, a bad bulk operation) — not container lifecycle.

> Safety reminders (see `replit.md` and `threat_model.md`):
> production data must NEVER be lost, overwritten, or replaced. Destructive ops
> and seeding are blocked outside development. Schema changes go through Alembic
> only.

---

## 1. Backup options

There are three layers, in order of strength:

### a) Replit project checkpoints (automatic)
Replit automatically checkpoints the database alongside the codebase and chat
session. This is the first thing to reach for after an accidental data change —
roll back to a checkpoint from before the incident. No setup required.

### b) Platform-managed Postgres backups / PITR
The managed Postgres instance has platform-level backups. To recover beyond the
available checkpoints (e.g. point-in-time recovery), use the database provider's
backup/restore controls. **Verify the retention window and PITR availability for
your plan** — this is the recovery path of last resort and should be confirmed,
not assumed.

### c) Manual logical dump (`pg_dump`) — strongest, portable
A full logical dump is the only backup that is portable and restorable
independently of the platform. Take one **before any risky migration or bulk
data operation**.

```bash
# Full dump (schema + data), custom format (compressed, restorable selectively)
pg_dump "$DATABASE_URL" -Fc -f nassaq_$(date +%Y%m%d_%H%M%S).dump

# Plain SQL alternative (human-readable, larger)
pg_dump "$DATABASE_URL" -f nassaq_$(date +%Y%m%d_%H%M%S).sql
```

Store the dump off the app lifecycle (download it, or move it to object
storage) — do **not** leave it only inside the deploy image, which is rebuilt
and pruned on every release (`build.sh` deletes caches and source).

### d) Pre-deploy verification snapshot (counts only — NOT a backup)
`backend/scripts/backup_db.py` writes a JSON snapshot of **row counts and a few
sample IDs**. This is a *verification aid* to compare before/after a deploy — it
**cannot restore data**. Use it together with (a)/(b)/(c), never instead of them.

```bash
cd backend && python scripts/backup_db.py   # writes counts snapshot to JSON
```

---

## 2. Verifying persistence around a deploy/restart

1. Capture baseline: `cd backend && python scripts/backup_db.py` and note the
   Alembic revision: `psql "$DATABASE_URL" -c "SELECT version_num FROM alembic_version;"`
2. Restart / redeploy.
3. Confirm counts are unchanged (re-run the snapshot and diff), and that startup
   logs show `DEPLOYMENT SAFETY: Data snapshot on startup — users=… schools=…`
   with the expected numbers and **no** `Seeded platform admin` line.
4. Confirm the schema gate logged `PostgreSQL schema at Alembic revision: <head>`
   and did **not** log `Database schema is not at the latest Alembic head`.

---

## 3. Restore procedures

### a) Restore from a `pg_dump` custom-format dump
```bash
# Into a clean/empty target database:
pg_restore --no-owner --clean --if-exists -d "$DATABASE_URL" nassaq_YYYYMMDD_HHMMSS.dump
```
- `--clean --if-exists` drops existing objects before recreating them, so only
  run against a database you intend to overwrite (a recovery target), never
  blindly against live production.
- For a plain `.sql` dump: `psql "$DATABASE_URL" -f nassaq_YYYYMMDD_HHMMSS.sql`.

### b) Restore a single table
```bash
pg_restore --no-owner --data-only -t <table_name> -d "$DATABASE_URL" backup.dump
```

### c) Restore from a Replit checkpoint
Use the workspace rollback to a checkpoint taken before the incident. This
reverts the database (and code/chat) together — review what else changed since
that checkpoint before rolling back.

After ANY restore, restart the backend so it re-verifies the schema:
```bash
# restart the "Backend API" workflow
```

---

## 4. Rolling back a bad migration

The release applies migrations during the build phase (`build.sh` runs
`alembic upgrade head` once per deploy). The app then **refuses to boot in
production** if the live schema is not at head (startup gate in
`backend/app/lifecycle.py`). So a forgotten/partial migration surfaces as a
failed deploy, not silent drift.

If a migration shipped and is wrong:

1. **Prefer fixing forward.** Write a new migration that corrects the problem
   and deploy it. This is safest and keeps history linear.
2. **If you must downgrade** (and the migration is reversible — most define a
   `downgrade()`), do it deliberately against the target DB:
   ```bash
   cd backend
   alembic current                 # see where the DB is
   alembic downgrade -1            # or: alembic downgrade <revision>
   ```
   Then ship code compatible with the downgraded schema. Note: downgrading a
   migration that dropped a column does **not** restore that column's data —
   only a dump/checkpoint restore does. For destructive migrations, **take a
   `pg_dump` first** (see §1c). Destructive migrations are gated by
   `backend/tests/test_migration_destructive_ops_guard.py` and require an
   explicit allowlist entry as the review sign-off.
3. If data was lost by a destructive migration, restore the affected table(s)
   from the most recent dump/checkpoint (§3) and reconcile with rows written
   after the backup.

---

## 5. What to confirm periodically (not provable from code)

- Replit Postgres backup retention window and PITR availability for the plan.
- That the **deployment** `DATABASE_URL` points to the intended production
  database, distinct from any development database.
- That a recent `pg_dump` exists off the deploy lifecycle and a test restore
  into a scratch database succeeds (an untested backup is not a backup).
