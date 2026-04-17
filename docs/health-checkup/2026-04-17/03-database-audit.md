# Phase 2 — Database Audit

**Date:** 2026-04-17 · **Status:** ✅ Complete (audit only)
**DB:** PostgreSQL · Alembic head `m1n2o3p4q5r6` · 18 revisions, all applied.

## 1. Inventory

- **53 tables** in `public` schema · **99 FK constraints** (strong referential integrity)
- **Real row counts** (via `SELECT COUNT(*)`):
  - users 734 · schools 7 · students 511 · teachers 215 · parents 503
  - classes 45 · attendance **10 604** · behaviour_records 2 020
  - schedule_sessions 1 260 · audit_logs 1 280
  - generic_documents 1 676 (mostly `timetable_sessions`=1548)
- **Users by role:** parent 504, teacher 215, school_admin 5, platform_admin 5, school_principal 2, student 2, independent_teacher 1.
- **Index coverage:** every FK has at least one covering index (heuristic check passed).

## 2. Findings

### Severity: 🟥 Critical · 🟧 High · 🟨 Medium · 🟩 Low · ⚪ Polish

| ID | Sev | Finding |
|---|---|---|
| **D-01** | 🟧 High | **`revoked_tokens` typed table is dead code.** `engines/sql_utils.py::_ORM_REGISTRY` does **not** include `"revoked_tokens"`, so `gd_insert("revoked_tokens", …)` and `gd_find_one("revoked_tokens", …)` fall through to the JSONB `generic_documents` store. The properly-indexed `revoked_tokens(jti PK, expires_at idx)` table is never read or written. Auth path (`dependencies.py:168`) does `data->>'jti'` filter scan over generic_documents per request. Currently OK (9 rows) — at scale will be linear-scan per auth check. |
| **D-02** | 🟧 High | **No cleanup of expired revoked tokens.** All 9 rows in `generic_documents.revoked_tokens` are past their `expires_at`. There is no scheduled job or startup hook to purge them. Will grow forever. |
| **D-03** | 🟧 High | **Auth enrichment path (B-13) confirmed:** `get_current_user` runs up to **4 sequential `gd_find_one` queries** per parent request (email → phone → national_id → guardian_links) just to populate `parent_id`. With 504 parent users this is ~4× DB-roundtrip multiplier on every parent dashboard request. |
| **D-04** | 🟨 Medium | **`parents` table has no `user_id` FK** (unlike `teachers.user_id`). Linkage to `users` is only by `email` (works today; 0 mismatches), but is fragile under email changes. Add `parents.user_id` (nullable, indexed, FK→users.id) and backfill from email match. |
| **D-05** | 🟨 Medium | **4 teachers have invalid `user_id`** (point to non-existent users). Likely soft-deleted users. Either delete the orphan teacher rows or null out `user_id`. |
| **D-06** | 🟨 Medium | **1 parent user with no parents row.** Likely test/admin account. Cosmetic. |
| **D-07** | 🟨 Medium | **30 tables never analyzed** (`last_analyze IS NULL` and `last_autoanalyze IS NULL`). Query planner has stale row estimates → can pick suboptimal plans. Need `ANALYZE` (cheap) and tune autovacuum thresholds. |
| **D-08** | 🟨 Medium | **No JSONB GIN indexes.** Any filter against `generic_documents.data->>'X'` requires a sequential scan within the collection partition. Low cost while collections are small (≤1.5K rows), but will grow with timetable history. Add `CREATE INDEX … USING GIN (data jsonb_path_ops)` once a JSONB filter becomes hot. |
| **D-09** | 🟩 Low | **20 hot indexes with `idx_scan = 0`** (attendance, behaviour_records, audit_logs, parents, students, schedule_sessions). Stats may simply be cold (no traffic since restart), so this is a "monitor over a longer window" item, not a delete-now action. Re-check after 24 h of real traffic. |
| **D-10** | 🟩 Low | **Two redundant indexes on `generic_documents.collection`:** `idx_generic_docs_collection` AND `ix_generic_documents_collection`. Both btree on the same column — drop one. |
| **D-11** | 🟩 Low | **`schedule_sessions.day_of_week` is `varchar`** (stores `'monday'` etc.) — costs a string compare on a 1260-row hot path. Consider `smallint` (1–7) with a small-int → name map in code. |
| **D-12** | 🟩 Low | **`generic_documents.data` rows of inconsistent shape** in `revoked_tokens` collection (some rows have data as a non-dict). Defensive parsing OK; documents the looseness of the JSONB store. |
| **D-13** | ⚪ Polish | **`alembic_version`** has only 1 head (`m1n2o3p4q5r6`) — clean, no branches. |
| **D-14** | ⚪ Polish | **Connection pool is healthy:** size 15 + overflow 25, currently 1 checked out, lifo enabled, pre-ping on. |

## 3. Query plans (after `ANALYZE`)

| Query | Plan | Time |
|---|---|---|
| `users WHERE email='…'` (login) | Index Scan `ix_users_email` | 0.04 ms |
| `revoked_tokens WHERE data->>'jti'=…'` (actual auth path) | Index Scan `ix_generic_documents_collection` + JSONB filter | 0.02 ms (9 rows) |
| `notifications WHERE user_id='…' ORDER BY created_at DESC` | Index Scan `idx_pg_notifications_user_read_date` + sort | 0.02 ms |
| `schedule_sessions WHERE class_id=… AND day_of_week=…` | Index Scan `idx_pg_sessions_class_day` | 0.97 ms |

All hot-path queries hit the right index after `ANALYZE`.

## 4. Data integrity sweep

- 0 orphan students (bad class_id)
- 0 orphan attendance (bad student_id)
- 0 students with bad parent_id or school_id
- 0 users with bad tenant_id
- 0 duplicate emails in users
- 0 users without email
- 4 teachers with invalid user_id (D-05)
- 1 parent user with no parents-row (D-06)

## 5. Migrations

`backend/alembic/versions/`: 18 files, sequential, single head `m1n2o3p4q5r6`. Most-recent migration adds `data` JSONB to messages/notifications. Migration history is clean and applied.

## 6. Action items → Phase 5 batch routing

- **DB integrity batch:** D-04 (add parents.user_id), D-05 (clean teachers), D-06
- **Maintenance/jobs batch:** D-02 (expired token cleanup), D-07 (`ANALYZE` + autovacuum tuning)
- **Auth efficiency batch:** D-01 (route revoked_tokens to typed table), D-03 (cache enrichments on JWT)
- **Index hygiene batch:** D-09 (re-check after 24 h), D-10 (drop dup index), D-11 (day_of_week type)
- **Polish:** D-08 (GIN deferred), D-12, D-13, D-14

## Gate

✅ Phase 2 complete. **Proceeding to Phase 3 (Frontend Audit) without waiting per user instruction.**
