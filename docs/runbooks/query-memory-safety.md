# Query memory safety — bounded reads and bulk writes

> Runbook + engineering guideline. Applies to every backend read that can
> return more than a handful of rows.

## Why this exists

Measured on this deployment (backend process, asyncpg + SQLAlchemy ORM, rows
converted to dicts by `models_to_dicts`):

| Read | Rows | Process RSS |
|------|------|-------------|
| `gd_find(session, "timetable_sessions", {})` — no limit | 33,974 | **+136 MB** |

That is **~4.1 KB of RSS per materialised row**. Extrapolated:

| Result size | Peak cost (1 request) | 4 concurrent requests |
|-------------|----------------------|-----------------------|
| 5,000 rows | ~20 MB | ~80 MB |
| 50,000 rows | ~200 MB | ~800 MB |

The audit that produced this runbook found that the shared helper
`gd_find` had **no default and no maximum limit** — 412 of its 1,061 call
sites passed no limit at all, so "SELECT the entire collection into RAM" was
the *default* behaviour of the codebase's most-used data-access function.

## The rules

1. **Never call `gd_find` without a `limit`.** A read that forgot to say how
   much it wants is now capped at `GD_FIND_MAX_ROWS` (default 5,000) and logs
   a `WARNING` naming the collection when the cap truncates it. The cap is a
   seatbelt, not a design: if you see that warning in the logs, the call site
   is wrong.
2. **An explicit `limit` is always honoured.** Reports that deliberately ask
   for a lot still get it. The ceiling only applies to `limit=None`.
3. **If the operation legitimately has to touch every row, stream it.**
   Use `gd_iter_rows` (row at a time) or `gd_iter_batches` (page at a time)
   from `engines/sql_utils.py`. Both keyset-page by `id` and detach each page
   from the session, so memory stays flat regardless of table size.
4. **Never build an `IN (...)` list out of an unbounded result.** Chunk id
   lists (see `_chunked` in `engines/export_engine.py`, 500 per statement).
5. **Caller-supplied page sizes need a server-side maximum.** Use
   `Query(default=50, ge=1, le=200)`; a bare `limit: int = 50` lets a client
   ask for `limit=100000`.
6. **Count in the database.** If only `len(rows)` is used, call `gd_count`.
7. **Bulk writes go in chunks with one flush per chunk**, and the chunk is
   detached afterwards. `gd_update_many` already does this; new fan-out code
   should follow `NotificationEngine.create_bulk_notifications` (chunk inside
   a `SAVEPOINT`, retry the chunk row-by-row on failure so one bad row does
   not drop its neighbours or poison the caller's transaction).

## The helpers

```python
from engines.sql_utils import gd_find, gd_iter_rows, gd_iter_batches, gd_count

# bounded read - you know the page you want
rows = await gd_find(session, "attendance", {"class_id": cid}, limit=200)

# streaming aggregation - loop body unchanged, memory flat
totals = {}
async for row in gd_iter_rows(session, "attendance", {"school_id": sid}, max_rows=50000):
    totals[row["status"]] = totals.get(row["status"], 0) + 1

# streaming export - one page at a time into the writer
async for batch in gd_iter_batches(session, "students", {"school_id": sid}):
    for student in batch:
        writer.writerow(student)

# just a count
n = await gd_count(session, "session_interactions", {"session_id": {"$in": ids}})
```

Both iterators use **keyset paging** (`WHERE id > cursor ORDER BY id LIMIT n`)
rather than `OFFSET`: OFFSET re-scans the skipped prefix on every page and can
skip or repeat rows when the set is written to while it is being walked.

Rows come back ordered by `id`. If you need a sorted top-N, that is a bounded
read — pass an explicit `limit` to `gd_find` with `order_by`.

## Knobs

| Env var | Default | Range | Meaning |
|---------|---------|-------|---------|
| `GD_FIND_MAX_ROWS` | 5000 | 100–200,000 | Ceiling for a `gd_find` with no `limit` |
| `GD_BATCH_SIZE` | 500 | 50–10,000 | Page size for the streaming helpers and chunked writes |

## Diagnosing a memory spike

1. Grep the logs for `hit the .* -row safety ceiling` — that names the
   collection and the filter keys of an unbounded read.
2. Correlate with `/system/metrics` (process RSS) and the request id in the
   access log.
3. Reproduce the read in isolation and measure:

```bash
cd backend && ENVIRONMENT=development python3 -c "
import asyncio, sys, resource, gc; sys.path.insert(0,'.')
import server
from db import async_session_factory
from engines.sql_utils import gd_find
rss = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
async def main():
    gc.collect(); base = rss()
    async with async_session_factory() as s:
        rows = await gd_find(s, 'timetable_sessions', {}, limit=200000)
        gc.collect(); print(len(rows), 'rows', round(rss()-base), 'MB')
asyncio.run(main())"
```

## Known remaining hot spots

These are bounded (explicit `limit=50000`) but still materialise their result
because the report shape needs the rows grouped, not just counted. Converting
them means changing what the report computes, so they were left alone and are
listed here on purpose:

- `engines/reporting_engine.py` — school interaction report (`by_type` +
  `student_agg` + per-session counts share three passes over one list).
- `engines/reporting_engine.py` — subject performance report
  (`session_inter_map` groups whole interaction rows per session).
- `engines/reporting_engine.py` — score aggregation report (`all_scores`
  is walked four times).

Anything that reads a *table* rather than a tenant-scoped slice should be
treated as a bug: every read in a multi-tenant path must carry its tenant
filter, which is what keeps these result sets small in practice.

## Tests

`backend/tests/test_query_memory_safety.py` pins the contract: the ceiling,
the "explicit limit wins" rule, the truncation warning, keyset paging
coverage, per-page round-trips for both the iterator and `gd_update_many`,
chunked notification fan-out, the notification page-size maximum, and that
exports stream (an export must stay complete even when the ceiling is tiny).
