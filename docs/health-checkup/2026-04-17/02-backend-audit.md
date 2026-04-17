# Phase 1 — Backend Audit

**Date:** 2026-04-17
**Status:** ✅ Complete (audit only; no code changes)
**Backend version:** NASSAQ v3.0.0 · FastAPI · PostgreSQL (Alembic-managed)

---

## 1. Inventory

| Layer | Item | Count |
|---|---|---|
| Routes | Route modules | 66 |
| Routes | `@router.{get,post,put,patch,delete}` declarations | **~960** (sum across modules) |
| Engines | Business engines (under `backend/engines/`) | 27 |
| Services | Service modules | 6 |
| Middleware | Custom middleware classes | 6 + 3 inline `@app.middleware` |
| Migrations | Alembic revisions | 18 |
| Approval handlers | Registered at startup | 2 (`teacher`, `school`) |

### Middleware stack (registration order, fires LIFO)

1. `ErrorHandlerMiddleware`
2. `RateLimitMiddleware`
3. `RequestTracingMiddleware`
4. `pg_session_middleware` (inline) — opens a session per request
5. `add_security_headers` (inline)
6. `audit_log_middleware` (inline) — async fire-and-forget audit insert
7. `CORSMiddleware`

Custom middleware files: `error_handler.py`, `rate_limiter.py`, `request_tracing.py`, `audit_middleware.py`, `query_monitor.py`, `cache_metrics.py`, `tenant_isolation.py`, `rbac.py`.

---

## 2. Live runtime metrics (sampled)

From `/system/health`:
- Uptime: 338 s, status: **healthy**
- DB connected, latency **14.89 ms**, pool size 15, checked-out 1
- Memory RSS: **252.6 MB**, threads: 11, fds: 11
- avg response 17.7 ms, p95/p99 = 82.6 ms (small sample), 0 errors / 18 reqs
- Cache hit-rate so far: 50% (cold)

From repeated `/api/public/stats` (cached): 4–5 ms after warm-up — cache works correctly.

`/api/public/contact-info`: ~9 ms first call.

No `ERROR/WARNING/CRITICAL` lines in current backend log.

---

## 3. Findings (Backend)

### Severity legend
🟥 Critical · 🟧 High · 🟨 Medium · 🟩 Low · ⚪ Polish/Info

| ID | Sev | Area | Finding |
|---|---|---|---|
| **B-01** | 🟥 Critical | Static-file serving / Security | `app/routes.py::serve_react_app` does `frontend_build / full_path` and serves the file if it exists, **with no path-traversal sanitisation**. URL normalisers (Starlette/Uvicorn) currently strip `..` segments, so it isn't exploitable today, but this is a one-bad-proxy-away **path-traversal vulnerability**. Must add `Path(...).resolve()` + `is_relative_to(frontend_build.resolve())` check. |
| **B-02** | 🟧 High | CSP | Content-Security-Policy includes both `'unsafe-inline'` **and** `'unsafe-eval'` for `script-src`. This neuters CSP's XSS protection. Tighten to nonces/hashes; remove `unsafe-eval` (CRA build doesn't need it). |
| **B-03** | 🟧 High | Static caching / Performance | `/static/*.js` bundle is **4.82 MB** and served by FastAPI/Uvicorn with **no `Cache-Control` header**. Even hashed assets are re-validated each visit. Add `Cache-Control: public, max-age=31536000, immutable` for hashed `static/` paths. |
| **B-04** | 🟧 High | Bundle / Performance | The single JS bundle is 4.82 MB (uncompressed). No code-splitting visible. Frontend phase will profile, but pre-tag for fix in Phase 5. |
| **B-05** | 🟧 High | Monitoring endpoint broken | `monitoring_routes.py` line 172: `db[coll_name].count_documents({})` is **MongoDB syntax** left over from the old DB. `Repos` does not implement `__getitem__` or `count_documents`. The exception is swallowed silently, so `/system/deployment-safety` returns empty `data_snapshot`. Replace with `gd_count(...)`. |
| **B-06** | 🟧 High | Monitoring endpoint broken | `monitoring_routes.py::system_status` uses `{"$gte": cutoff.isoformat()}` against `gd_count`. Need to verify `gd_count` translates `$gte`; if not, “active_users_24h” is wrong. (DB Phase will verify with explain.) |
| **B-07** | 🟨 Medium | Reliability | **No automated port cleanup** before workflow start. A leftover uvicorn or craco from a previous session crashes the workflow (P0-01). Wrap workflow command in a `prestart` that frees the port. |
| **B-08** | 🟨 Medium | Auth / Auditing | `audit_log_middleware` re-decodes the JWT inside the request path **even though** auth-protected routes already validated it via `get_current_user`. This is duplicated crypto work per request. Read `request.state.user` (set by `RequestTracingMiddleware` or auth dep) only; if absent and audit needs identity, decode once and cache on `request.state`. |
| **B-09** | 🟨 Medium | Connection-pool metric | Live pool stats show `Current Overflow: -13` and `pool_size: 15, checked_out: 1, overflow: -13`. Negative overflow likely indicates the metric is computed as `checked_out - pool_size`. Cosmetic but misleading on dashboards — fix label or formula in `query_monitor.py::get_pool_stats`. |
| **B-10** | 🟨 Medium | Rate limiting | Rate-limit store is in-memory (acknowledged in docstring). With multiple workers/instances limits multiply. List of protected endpoints is **not exhaustive** — missing: password-reset, token-refresh, OTP, file-upload, AI endpoints (only `/hakim/analyze` is covered, but other AI routes aren't). |
| **B-11** | 🟨 Medium | WebSocket | `ws/notifications` correctly uses message-based auth, but on each pong/server_ping, no idle-timeout disconnect. `_server_ping_loop` only force-closes when send fails. Dead clients with stale sockets stay in `manager.active_connections` until next send fails. Add inactivity timer to disconnect after N missed pongs. |
| **B-12** | 🟨 Medium | WebSocket | `ConnectionManager` is **process-local**; with multiple workers, a notification published from worker A won't reach a user connected to worker B. Currently single-worker — flag for future scaling. |
| **B-13** | 🟨 Medium | Auth | `get_current_user` does **3+ extra `gd_find_one` calls** to enrich `teacher_id`, `student_id`, `parent_id` on every request. For high-traffic teacher/parent dashboards this is wasted DB work. Cache these enrichments on the JWT (set at login) or on a lightweight per-process LRU. |
| **B-14** | 🟨 Medium | Auth | `revoked_tokens` lookup on every request uses `gd_find_one` — unindexed on `jti`? (DB Phase will verify.) Without a unique index on `jti`, this is a full scan per request. |
| **B-15** | 🟩 Low | Code hygiene | `app/routes.py` has an explicit `TODO` to migrate factory-pattern legacy routes (`scheduling_routes`, `attendance_routes`, `assessment_routes`, etc.) into `_mod` modules and remove the duplication. Two parallel registration patterns exist today. |
| **B-16** | 🟩 Low | Logging | Two logger configs: `dependencies.py` calls `logging.basicConfig` with a plain format, then `server.py` installs a JSON formatter. `dependencies.py` import order may briefly run with the basic format before the JSON handler is installed. Remove the basicConfig from `dependencies.py`. |
| **B-17** | 🟩 Low | Tests | `backend/tests/*` hardcode `https://school-timetable-ai.preview.emergentagent.com` as fallback — old preview URL. Should default to `http://localhost:8000` or fail loudly. |
| **B-18** | 🟩 Low | Public surface | `_register_static_fallback` mounts `/{full_path:path}` catch-all **after** API routes, but it still requires the file to exist. Hidden config files that happen to live under `frontend/build/` would be served (e.g. if anyone drops a `.env` there). Phase 5: explicit allow-list of extensions. |
| **B-19** | 🟩 Low | Health endpoint | `system/health` is **public** (no auth). It returns process memory, CPU, DB latency, pool stats, and request counts. Helpful for uptime monitors but exposes internal posture. Consider a slim public health (`{status, version}`) and a detailed one behind auth. |
| **B-20** | ⚪ Polish | Headers | `X-XSS-Protection: 1; mode=block` is **deprecated** and recommended off by modern security guides (rely on CSP). |
| **B-21** | ⚪ Polish | Config | `CORS_ORIGINS` defaults to `["*"]` and `ALLOWED_HOSTS` defaults to `["*"]` — production guard exists in `validate()` for CORS but **not for ALLOWED_HOSTS** (the latter isn't actually enforced anywhere — see B-22). |
| **B-22** | 🟨 Medium | Config | `ALLOWED_HOSTS` is read from env but never wired into Starlette's `TrustedHostMiddleware`. The config is therefore inert. Either wire it up or delete it to avoid false sense of security. |
| **B-23** | 🟩 Low | Performance | `_register_static_fallback` calls `file_path.exists()` on **every URL** that doesn't match an API route — extra filesystem stat per request. Behind a CDN / nginx in production this disappears, but in dev it's a small per-request cost. |
| **B-24** | 🟨 Medium | OpenAI integration | API key is read from `AI_INTEGRATIONS_OPENAI_API_KEY`, **but** `routes/academic_structure_routes.py` reads `OPENAI_API_KEY` directly. Two env-var conventions co-exist. Standardise. |
| **B-25** | 🟧 High | Lifecycle / data | `lifecycle.py::shutdown_tasks` clears `mgr.active_connections.clear()` etc., **but** if shutdown is killed mid-write (SIGKILL, OOM), there is no “drain in-flight requests” logic. The `pg_session_middleware` will leak open transactions. Add a graceful shutdown timeout that waits up to N seconds for active sessions. |
| **B-26** | 🟩 Low | Imports | `app/middleware.py` imports `import asyncio, time, uuid as _uuid` **inside** the audit middleware function on every request. Move to module top. |

---

## 4. Endpoint sample timings (cold/warm)

| Endpoint | Cold | Warm |
|---|---|---|
| `GET /system/health` | 7 ms | n/a |
| `GET /api/public/stats` (full agg) | ~83 ms | 4–5 ms (cached) |
| `GET /api/public/contact-info` | 35 ms | 9 ms |
| `GET /static/js/main.*.js` (4.8 MB) | depends on bandwidth | re-validated each visit (no `Cache-Control`) |
| `GET /` (SPA index) | 16 ms | n/a |

No endpoints over 1 s observed in the sample. A real slow-endpoint scan with auth requires Phase 4 (E2E with login).

---

## 5. Summary by area

| Area | Verdict |
|---|---|
| Auth & JWT | Solid; needs B-08, B-13, B-14 optimisation |
| Authorization (`require_roles`) | Pattern is clean; per-route role audit deferred to Phase 4 |
| Error handling | Good (3 exception handlers + error middleware); structured |
| Logging | Structured JSON; minor cleanup (B-16) |
| Security headers | Present but CSP weak (B-02), `ALLOWED_HOSTS` inert (B-22) |
| Static serving | Path-traversal hazard (B-01), no cache headers (B-03), big bundle (B-04) |
| WebSockets | Auth-via-message ✅, idle-timeout missing (B-11), single-worker (B-12) |
| Rate limiting | Works in-memory; coverage gaps (B-10) |
| Monitoring | Rich, but two routes broken (B-05, B-06), pool metric weird (B-09) |
| Background jobs | None active beyond audit-fire-and-forget; pool monitor task healthy |
| Integrations | OpenAI present, two env-var names (B-24) |

---

## 6. Action items

All findings → Phase 5 fix queue. Will be regrouped by area for safe batching:

- **Security batch:** B-01, B-02, B-19, B-20, B-22
- **Static & perf batch:** B-03, B-04, B-23
- **Reliability batch:** B-07, B-11, B-12, B-25
- **Monitoring fix batch:** B-05, B-06, B-09
- **Auth efficiency batch:** B-08, B-13, B-14
- **Hygiene batch:** B-15, B-16, B-17, B-21, B-24, B-26
- **Rate-limit batch:** B-10

## Gate

✅ Phase 1 complete. Ready for **Phase 2 — Database Audit** (PostgreSQL schema vs models, indexes, slow queries, orphans, migrations) on user approval.
