# Backend startup regression check

Run from the repository root with the same Python environment used by the backend:

```sh
python scripts/benchmark_backend_startup.py
python -m unittest discover -s scripts/tests -p test_backend_startup.py
```

`build.sh` runs the first command after installing backend dependencies, before
building the frontend. A nonzero exit stops publishing. It launches three fresh
interpreters **per module**, importing `dependencies` and `server` independently.
The server probe constructs the real application and registers its routes, but
does not run ASGI lifespan. Each sample must meet the default import ceilings:
5 seconds for dependencies, 15 seconds for the full app. These are intentionally
generous regression tripwires, not service-level objectives. Export-only pandas,
ReportLab, Arabic reshaper, and bidi imports fail regardless of elapsed time.

The JSON report includes individual import and whole-process wall times,
and failed probes identify the exception class, last source filename/line, and
missing module (when applicable). Raw exception messages, source lines, local
variables, and application logs are withheld to avoid exposing credentials.
The report also includes
median/max import times, Python version/executable, OS, architecture, logical CPU
count and load average. Whole-process time includes interpreter startup, probe
setup, import, optional schema probe, output and teardown; it is **not**
time-to-serve. Import time excludes interpreter/probe setup.

Filesystem and bytecode caches are uncontrolled and may be warm. No cache purge
or prewarming is performed. These numbers do **not** represent deployed cold
starts, image download, autoscale scheduling, remote database latency, TLS,
socket binding, or the complete lifespan. Compare runs on the same runner and
Python/dependency versions. For slower CI machines, use explicit reviewed
`--max-dependencies-seconds` / `--max-server-seconds` budgets; never silently
increase budgets in response to a regression. `--timeout` bounds each child
(default 60 seconds); `--samples` controls repetitions.

## Schema readiness is a separate measurement

The default/build probe is database-free: environment credentials are not
inherited, dotenv loading is disabled, the database URL is an unusable dummy,
and socket connection attempts during imports fail.

Optionally supply **a separate disposable non-production database only**, via the secret
manager as `BENCHMARK_DATABASE_URL`, then run:

```sh
python scripts/benchmark_backend_startup.py --schema-gate
```

There is deliberately no fallback to the app's `DATABASE_URL`. Managed-deployment
execution and targets with the same host/port/database as the app URL are rejected.
Internal child mode rejects direct invocation without its isolated environment.
Do not supply production credentials. This option runs the real managed physical-schema
`init_pg_tables()` gate *after* app import in each server child. It uses a fresh
engine with PostgreSQL `default_transaction_read_only=on` and a 15-second SQL
statement timeout. Schema timing includes connection establishment and catalog
validation, separately from import. A not-ready result or exception fails the
command; the normal application's readiness checks are unchanged. No lifespan,
migrations, schema repair, seeds, or maintenance jobs are invoked.

The benchmark cannot identify whether a supplied URL belongs to production;
the caller must provision a non-production target. The build never enables this
option. When not requested, schema timing is explicitly `null`, not a fabricated
zero or a mocked database timing.

The script's unit tests run without backend pytest's global app/DB fixtures.
Existing `backend/tests/test_startup_remediation.py` continues to verify that
lifespan awaits the blocking gate before scheduling deferred work.