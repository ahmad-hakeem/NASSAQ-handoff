# CPU-bound work must not run on the event loop

**Applies to:** report/PDF generation, XLSX & CSV writers, archive (zip) building,
image processing, password hashing, encryption — anything that burns CPU without
awaiting.

## The rule

> If a piece of code takes more than a few milliseconds and never `await`s,
> it does not belong in an `async def` handler. Run it through
> `services.cpu_offload.run_cpu_bound(...)`.

## Why

The backend is a **single asyncio process per instance** (`uvicorn server:app`,
no `--workers`; see `.replit`). The event loop only switches tasks at an
`await`. Synchronous work therefore owns the process from its first line to its
last: no other request is read, routed, or answered while it runs — including
`/healthz`.

Measured on this codebase with `backend/scripts/evidence_event_loop_pdf.py`
(Arabic attendance report, ReportLab + `arabic_reshaper` + `python-bidi`):

| Report size | Build time | Worst event-loop stall (inline) | Offloaded |
|-------------|-----------:|--------------------------------:|----------:|
| 5 rows      |    85 ms   |                           80 ms |      8 ms |
| 50 rows     |   388 ms   |                          385 ms |     13 ms |
| 200 rows    |  1469 ms   |                         1463 ms |      8 ms |
| 500 rows    |  3448 ms   |                         3444 ms |     10 ms |
| 4 × 200 rows concurrently | 5.7 s | 5700 ms | 309 ms |

Offloading does **not** make a report faster — same CPU, and ReportLab is pure
Python so the GIL still serializes it. What changes is that CPython yields the
GIL every few milliseconds, so the loop keeps getting slices and everyone else's
requests keep flowing. Throughput is unchanged; *availability* is restored.

Re-run the evidence script any time you doubt it:

```bash
cd backend && ENVIRONMENT=development python3 scripts/evidence_event_loop_pdf.py
```

## How

```python
from services.cpu_offload import run_cpu_bound

# a) the work is already a sync function
pdf_bytes = await run_cpu_bound(_render_schedule_pdf, kind="pdf", **kwargs)

# b) the work is inline in the handler — wrap it in a closure, which keeps
#    every local variable it already reads
def _build():
    ...                      # no awaits allowed in here
    doc.build(story)
    return buf

buf = await run_cpu_bound(_build, kind="pdf")
```

`kind` is a free-text label ("pdf", "xlsx", "csv", "zip") used for metrics and
logs.

**The closure must not touch the database.** It runs on a worker thread; the
request-scoped `AsyncSession` is not thread-safe. Gather all data with `await`
first, then render.

## Limits and failure modes

Configured in `config.py` (all env-overridable):

| Setting | Default | Meaning |
|---|---:|---|
| `CPU_OFFLOAD_MAX_WORKERS` | 2 | Render threads. More does **not** mean faster (GIL) — it only adds jitter. |
| `CPU_OFFLOAD_MAX_INFLIGHT` | 8 | Jobs admitted (running + waiting). |
| `CPU_OFFLOAD_ADMISSION_TIMEOUT_S` | 20 | Wait for a slot before giving up. |
| `CPU_OFFLOAD_TIMEOUT_S` | 90 | Wall-clock budget per job. |
| `CPU_OFFLOAD_SLOW_MS` | 5000 | Renders slower than this log at WARNING. |

* Saturated pool → `CpuOffloadBusy` → **503 `RENDER_BUSY`** with `Retry-After: 30`
  and an Arabic message. This is deliberate back-pressure; the alternative is an
  unbounded queue where users wait minutes for a file they have abandoned.
* Over budget → `CpuOffloadTimeout` → **504 `RENDER_TIMEOUT`**.
* A Python thread cannot be killed. On timeout the *caller* is freed, but the
  runaway job keeps its worker (and its admission slot) until it finishes. The
  admission cap, not the timeout, is what protects the instance.

Both are handled centrally in `server.py`, so a route does not need to catch
them.

**Trap:** if your route wraps the render in a broad `except Exception -> 500`,
that catch swallows `CpuOffloadBusy`/`CpuOffloadTimeout` (they are plain
exceptions) and the user gets an opaque 500 with no retry signal. Re-raise them
first:

```python
except HTTPException:
    raise
except (CpuOffloadBusy, CpuOffloadTimeout):
    raise  # central handlers → 503 RENDER_BUSY / 504 RENDER_TIMEOUT
except Exception as exc:
    ...
```

## Monitoring

`GET /system/metrics` (platform admin) → `render_pool`:

* `rejected > 0` — users were turned away; reports are queueing. Consider a
  higher `CPU_OFFLOAD_MAX_INFLIGHT`, a bigger instance, or narrower reports.
* `slowest_ms` / `by_kind.*.avg_ms` — reports getting heavier over time.
* `in_flight` pinned at `max_inflight` — the render pool is the bottleneck, not
  the database.

Numbers are **process-local since boot**; on autoscale each instance reports its
own.

## Regression guard

`backend/tests/test_cpu_offload.py::test_no_route_builds_a_pdf_on_the_event_loop`
parses every module under `routes/` and `engines/` and fails if a `doc.build(...)`
sits directly inside an `async def`. A closure passed to `run_cpu_bound` is
accepted; an inline build is not.

## Still on the loop (known, not yet migrated)

These are lower-volume or smaller, and are candidates for the same treatment:

* XLSX writers in `routes/independent_teacher_workspace_excel_export_routes.py`
  and `routes/bulk_import_export_routes.py`
* the analytics **CSV** writer (pure string building, no pandas — cheap enough
  that a slot costs more than it saves; revisit if reports grow)
* XLSX **reads** in `routes/academic_structure_routes.py` and
  `engines/noor_import/parser.py` (a large Noor file blocks for seconds)
* `zipfile` archive build in
  `routes/independent_teacher_workspace_lifecycle_routes.py`
* bcrypt hashing (`services/auth_service.py`, `dependencies.py`) — ~100 ms per
  login by design

Route them through `run_cpu_bound` when you next touch them.
