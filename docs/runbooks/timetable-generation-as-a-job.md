# Timetable generation runs off the loop, as a job

**Applies to:** the smart scheduling engine — draft construction, conflict
detection, optimization — and anything else that searches, solves, or optimizes.

This is the scheduling-specific companion to
[`cpu-bound-work-off-the-loop.md`](./cpu-bound-work-off-the-loop.md). Read that
one first for the general rule and the `run_cpu_bound` API.

## The rule

> **No heavy algorithm may run inside an `async def` route handler or inside an
> awaited engine method.** Timetable generation, optimization passes and
> constraint solving belong in a sync core handed to
> `run_cpu_bound(..., pool=TIMETABLE_POOL)`, and anything that can exceed a few
> seconds must be exposed as a *job*, not as one long request.

## Why — measured, not assumed

`POST /smart-scheduling/generate/{school_id}` used to `await
generate_timetable(...)` inline. The three heavy phases inside it never await,
so the loop was owned by the placement search for its entire duration.

`backend/scripts/evidence_event_loop_timetable.py` runs the real engine phases
against synthetic schools with a 10 ms heartbeat measuring loop lateness:

| Scenario | Total | Worst loop stall (inline) | Worst loop stall (offloaded) |
|---|---:|---:|---:|
| 12 classes / 30 teachers | 1.3 s | **1332 ms** | 1105 ms¹ |
| 24 classes / 45 teachers | 6.2 s | **6266 ms** | 188 ms |
| 40 classes / 70 teachers | 26.9 s | **26868 ms** | **96 ms** |
| 3 principals × 24 classes | 19.6 s | **19625 ms** | 331 ms |
| idle baseline | — | 0.4 ms | 0.4 ms |

¹ first offloaded call in the process pays a one-time module-import cost; in the
server `services` is already imported at boot.

Breakdown of a 40-class run: draft construction 26.5 s, conflict detection
12 ms, optimization 391 ms. **The draft search is essentially the whole cost.**

During those 27 seconds nothing else on the instance was served — not parents
opening the app, not teachers taking attendance, not `/healthz`. One principal
pressing "إنشاء الجدول تلقائياً" was a full outage for that instance.

Re-run it any time you doubt the numbers:

```bash
cd backend && ENVIRONMENT=development python3 scripts/evidence_event_loop_timetable.py
```

## How it is structured now

Each phase is an **async wrapper** + a **sync core**:

| Public (async, awaited by callers) | Sync core (runs in the pool) |
|---|---|
| `generate_draft_timetable` | `_generate_draft_timetable_sync` |
| `detect_conflicts` | `_detect_conflicts_sync` |
| `optimize_timetable` | `_optimize_timetable_sync` |
| `_build_constraint_context` | `_build_constraint_context_sync` |

The wrappers keep their original signatures and return values, so every existing
caller and test is unchanged.

**The cores must never await, and never touch the database.** They run on a
worker thread where the request-scoped `AsyncSession` is not safe to use. The
draft core therefore returns `log_intents` — a list of `(level, message,
context)` tuples — which the async wrapper flushes through `_log_run` after the
search returns.

Why offload the three phases individually instead of the whole
`generate_timetable` orchestrator: the orchestrator interleaves awaited DB reads
between phases. Offloading it wholesale would drag that I/O into the thread.

## Two pools, deliberately

`services/cpu_offload.py` runs **named pools**:

* `render` — PDF/XLSX/CSV documents. Sub-second, high frequency.
* `timetable` — the scheduling search. 1–27 s, rare.

They are separate executors on purpose. A 27 s generation admitted into the
2-worker render pool would starve every export queued behind it for half a
minute.

| Setting | Default | Reasoning |
|---|---:|---|
| `TIMETABLE_OFFLOAD_MAX_WORKERS` | 2 | The search is GIL-bound; more threads do not solve faster, they only add jitter. |
| `TIMETABLE_OFFLOAD_MAX_INFLIGHT` | 4 | Admitted jobs (running + waiting). Beyond this, principals are told to retry rather than queued invisibly. |
| `TIMETABLE_OFFLOAD_ADMISSION_TIMEOUT_S` | 60 | How long a job waits for a worker. |
| `TIMETABLE_OFFLOAD_TIMEOUT_S` | 180 | Wall-clock budget per phase. Deliberately more generous than a typical 30–60 s API budget: with the loop freed, a slow-but-succeeding large-school run costs only that one principal time, and a 60 s cap would make the feature unusable for a 40-class school. |
| `TIMETABLE_JOB_STALE_AFTER_S` | 600 | A non-terminal run older than this is reaped as failed. |

Saturation → `CpuOffloadBusy` → 503; over budget → `CpuOffloadTimeout` → 504.
Both are handled centrally in `server.py`.

## The job API

Offloading fixes the *server*. It does not fix the *request*: a 27 s response is
still long enough for a proxy or browser to abort (the dev proxy in
`frontend/src/setupProxy.js` cuts at 30 s), and it pins the principal to the
page. So generation is also exposed as a job.

```
POST /api/smart-scheduling/generate/{school_id}/job   → 202 {job_id, status, poll_url}
GET  /api/smart-scheduling/job/{job_id}               → {status, progress, is_done, result}
GET  /api/schedule/master-grid?view=draft             → the finished timetable
```

The **job record is the `timetable_runs` row**. The engine already created one
and walked it through `validating → generating → optimizing → completed` with a
`completion_percentage`; the job endpoints just expose it. Because that state
lives in Postgres rather than in process memory, a poll that lands on a
different autoscale instance than the one doing the work still gets the truth.

The synchronous `POST /smart-scheduling/generate/{school_id}` still exists for
scripts and tests. The principal UI uses the job pair.

### Guarantees

* **Fail fast.** `build_infeasibility_report` runs *before* queueing; an
  unsolvable school gets `422 GENERATION_BLOCKED` with the reasons, and no
  worker is burned.
* **One run per school, claimed atomically.** A second request while one is in
  flight returns the running job (`already_running: true`) instead of starting a
  competing search that would overwrite the first one's draft. The check and the
  INSERT are separated by two awaited round-trips (context assembly, then the
  infeasibility report), which is ample room for two principals — or one
  double-click — to both pass a read-then-insert guard. So the claim is made
  under `pg_advisory_xact_lock(hashtextextended('timetable_gen:<school>', 0))`:
  lock, re-check, insert, commit. Transaction-scoped, released by that commit,
  no schema change. The cheap pre-check before the lock is just a fast path and
  may be raced past harmlessly.
* **Liveness is a heartbeat, not elapsed time.** A running job refreshes
  `heartbeat_at` every 20 s on its own session — affordable only because the CPU
  phases no longer hold the loop. Reaping on age alone would kill a healthy
  large-school run at the threshold and then let a second generation start
  beside it, both writing the same draft.
* **Stale reaping is compare-and-set.** If the instance running a job dies
  (deploy, scale-down, crash) the row would sit "generating" forever — lying to
  the principal *and* permanently blocking the guard above. A run silent for
  more than `TIMETABLE_JOB_STALE_AFTER_S` is flipped to `failed` / `JOB_STALE` on
  the next poll or generate attempt, but only `WHERE status` is still active, so
  concurrent pollers cannot rewrite a run that finished in the meantime.
* **Own session, and the ContextVar is put back.** The background task opens its
  own `async_session_factory` session; the request-scoped one is closed by the
  time it runs. The job row is committed *before* the task is scheduled, because
  under `BaseHTTPMiddleware` a background task can start before
  `pg_session_middleware` commits. `db.session` is a ContextVar shared with the
  rest of the request context, so the job restores the previous value in a
  `finally` — otherwise anything scheduled after it inherits a closed session.
* **A crashed job always ends terminal.** If the job's *own session* is what
  broke, the failure is written on a fresh session (`_terminalize_run`) rather
  than left for the reaper, so the school is not blocked in the interim.
* **Run state is keyed by run_id.** `smart_scheduling_engine` is a process-wide
  singleton. Anything stashed on `self` during a run (rejection counters, the
  RNG seed) is shared by every concurrent generation — one school's counters
  used to be readable in another school's `generation_summary`. Run-scoped
  values live in `self._run_scratch[run_id]` and are popped in a `finally`.

### Frontend

`SchedulePageNew.jsx` starts the job, then polls every 2 s (10 min ceiling,
tolerating 5 consecutive transient network errors — a dropped poll does not mean
a failed generation). The Hakim overlay's progress bar is driven by the server's
real `completion_percentage` and never moves backwards. Polling stops on unmount.

## A trap this exposed: `timetable_runs` silently dropped its own progress

`timetable_runs` is a real table, and `dict_to_model` discards any key that is
not a column when the table has no `data` JSONB. The engine had been writing
`started_at`, `finished_at`, `completion_percentage`, `timetable_id`,
`created_by`, `conflicts_count`, `optimization_score` and more — **all silently
thrown away** (the visible symptom: rows with `status = 'completed'` and
`sessions_created = 0`).

Migration `tj01runs02data` adds a `data` JSONB overflow column, which makes
`dict_to_model` route extras into it and `model_to_dict` merge them back on
read. No engine code changed; the writes simply became durable.

**Generalize this:** before relying on a field written through `gd_insert` /
`gd_update_one`, confirm the target is either a GenericDocument collection or a
real table that has the column (or a `data` column). Silent drops do not raise.

## Monitoring

`GET /system/metrics` (platform admin):

* `cpu_pools.timetable.p95_ms` — generation cost trend. Rising means schools are
  outgrowing the engine.
* `cpu_pools.timetable.rejected` — principals were turned away with a 503.
  Non-zero repeatedly means raise `TIMETABLE_OFFLOAD_MAX_INFLIGHT` or the
  instance size.
* `cpu_pools.timetable.queued` / `in_flight` — queue depth right now.
* `cpu_pools.render.*` — unchanged by scheduling load, which is the point of
  separating the pools. If render p95 tracks timetable p95, the pools have been
  merged by mistake.

Counters are process-local since boot; on autoscale each instance reports its own.

## Regression guards

`backend/tests/test_timetable_offload.py` fails CI if:

* a sync core becomes `async def` (a thread pool cannot run a coroutine),
* an `await` appears inside a sync core (DB I/O crept back into the thread),
* a wrapper stops delegating through `_run_off_loop` (the search is back on the
  loop while every other test still passes),
* route code calls a sync core directly,
* the loop stalls more than 300 ms during a 1 s phase,
* timetable work lands in the render pool,
* either pool stops reading its own `*_OFFLOAD_*` limits (a `_spec()` mis-mapping
  would silently give timetable jobs the render pool's 90 s cap),
* the job API loses fail-fast, one-run-per-school, stale reaping or tenant
  scoping,
* the claim stops being taken under the advisory lock, or re-checks before
  taking it,
* a run with a fresh heartbeat is reaped, or the reaper overwrites a finished
  run,
* the job leaks its background session into the request ContextVar,
* run-scoped engine state stops being keyed by `run_id`.
