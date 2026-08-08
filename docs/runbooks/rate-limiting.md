# Rate limiting & brute-force protection

**Status:** distributed (Postgres-backed) since 2026-07-31.
**Code:** `backend/middleware/rate_limiter.py` · **Table:** `rate_limit_counters`
**Runbook owner:** backend / security

---

## 1. The bug this replaced (read this before "simplifying" it)

The limiter used to keep its sliding window in **process memory**. Replit
autoscale runs one uvicorn process per machine and scales out to N machines,
so a single attacker's requests were spread across N independent counters:

| Instances | Attempts allowed against a 10/60s login limit |
|-----------|-----------------------------------------------|
| 1         | 10 (intended)                                 |
| 2         | 20                                            |
| 4         | 40                                            |
| 8         | 80                                            |

(Measured with `backend/scripts/evidence_rate_limit_multiworker.py`.)

Scale-to-zero made it worse: every counter was wiped when the instance shut
down, so an attacker could reset the budget by pausing.

The same store backs every *inner* limit in the auth routes (per-email login,
per-user refresh/me, per-email password recovery, per-token/per-identity reset,
MFA per-user/per-IP), so all of them multiplied identically.

**Rule: never add process-memory rate limiting.** Any new limit must go through
`rate_store` (which is the shared store) or it is a limit in name only.

## 2. How it works now

* `SharedRateLimitStore` stores counters in the Postgres table
  `rate_limit_counters` (`key` PK / `count` / `expires_at`), so every worker
  and every instance consults **one** budget.
* **Algorithm:** weighted two-bucket sliding window. Each check reads the
  current and previous bucket, weighting the previous by its remaining
  overlap: `estimate = prev * (1 - elapsed/window) + current`. A plain fixed
  window would let 2x the limit through across a boundary.
* **Atomicity:** the read, the decision and the increment happen in **one
  transaction** — `SELECT pg_advisory_xact_lock(classid, key_hash)` followed by
  one statement that decides and conditionally inserts. Two workers can never
  both read "9 of 10" and both be admitted, and the decision is not exposed to
  the statement-snapshot race that a plain upsert-then-read has around a bucket
  boundary. The lock uses the *two-argument* advisory form so it shares no lock
  space with the `pg_try_advisory_xact_lock(bigint)` callers elsewhere in the
  codebase (session finalise sweep, draft-timetable ensure).
* **Only admitted requests are counted.** A rejected attempt does not increment
  the counter, so a client in a retry loop cannot keep pushing out its own
  unblock time. `Retry-After` is *solved* from the decay curve (across the
  bucket roll when needed), so a client that waits exactly that long is
  admitted — pinned by
  `test_client_that_waits_the_advertised_retry_after_is_admitted`.
* **Keys:** `<namespace>:<sha256(logical key)[:32]>:<window>:<bucket>`. Logical
  keys are per-IP (`<ip>:<path prefix>`, from the middleware), per-account
  (`login_account:<email>`), per-user (`refresh_user:`, `auth_me_user:`,
  `mfa_email_otp:user:`), per-email (`forgot_password_email:`) and per-token
  (`reset_password_token:`).
* **Contract:** `await rate_store.is_rate_limited(key, max_requests, window_seconds)`
  → `(limited, remaining, retry_after)`. Unchanged from the old store, so all
  call sites got the fix without edits.
* **Cleanup:** expired rows are swept opportunistically (1% of checks) and by
  `await rate_store.cleanup(force=True)`.

## 3. Response contract

429 responses carry:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1785524126   # unix seconds when the budget frees up
Retry-After: 43
```

Allowed responses on a throttled path carry `Limit` / `Remaining` / `Reset`
(no `Retry-After`). The middleware body is
`{"success": false, "error": {"code": "RATE_LIMITED", ...}}`; handler-level
limits raise `HTTPException(429, ...)` with the same headers via
`rate_limit_headers()`.

Inner (per-account / per-user) limits are stricter than the outer per-IP one,
so when a handler answers 429 the middleware **leaves its headers alone** — the
client is told about the limit it actually tripped, not the outer IP budget.

`POST /auth/forgot-password` deliberately answers **200 with the generic
message** when throttled — a 429 there would be an account-enumeration oracle.

## 4. Failure policy: fail-degraded (not fail-open, not fail-closed)

If the shared store errors or exceeds `RATE_LIMIT_DB_TIMEOUT_MS`, the check
falls back to the in-process window with the **same limits** and logs:

```
WARNING nassaq.ratelimit rate_limiter degraded to in-process fallback ...
```

Rationale: fail-open removes brute-force protection exactly when the system is
already unhealthy; fail-closed turns a database blip into a total login outage
(the limiter sits on `/auth/login`). Degrading restores the *old* behaviour —
per-instance limits — which is strictly better than nothing and never an
availability risk.

A key that was just denied is cached locally until its `retry_after` passes, so
hammering a blocked key costs **zero** DB round-trips; the limiter cannot be
turned into a DB amplifier by the attack it is blocking.

The limiter also borrows a pooled connection *while* `pg_session_middleware`
already holds the request-scoped one (handler-level limits are a nested
checkout). `RATE_LIMIT_MAX_INFLIGHT` caps how many it may hold at once, so a
flood of **unique** keys — the one shape the deny cache cannot absorb — cannot
drain the application pool; excess checks wait, then degrade.

## 5. Configuration

| Env var | Default | Meaning |
|---|---|---|
| `RATE_LIMIT_STORE` | `shared` | `shared` = Postgres (correct); `memory` = legacy per-process, for isolated local runs only. Logs a warning at boot. |
| `RATE_LIMIT_DB_TIMEOUT_MS` | `250` (`3000` under `TESTING=1`) | Ceiling on the limiter's DB round-trip before degrading. Measured cost: p50 5 ms, p95 9 ms. |
| `RATE_LIMIT_MAX_INFLIGHT` | `8` | Max pooled connections the limiter may hold at once, per process. Protects the app pool from limiter checks under a unique-key flood. |
| `RATE_LIMIT_NAMESPACE` | `rl1` | Key prefix. Change it to give two deployments sharing a database separate budgets, or to flush every counter instantly. |
| `RATE_LIMIT_LOGIN` / `RATE_LIMIT_WINDOW` | `10` / `60` | The `/api/auth/login` per-IP bucket. |

Per-path limits live in `RATE_LIMITS` in `backend/middleware/rate_limiter.py`.
It is **prefix + first match**, so a singular write path must be listed before
(or scoped with `"methods": {"POST"}` against) a plural GET path that shares its
prefix.

## 6. Operations

**Is someone being blocked right now?**

```sql
SELECT key, count, expires_at FROM rate_limit_counters
WHERE expires_at > now() ORDER BY count DESC LIMIT 20;
```

Keys are hashed, so you cannot read the account out of the table — use the logs:

```
rate_limit_denied ip=… method=POST path=/api/auth/login pattern=… limit=10 window=60s retry_after=43s scope=ip
rate_limit_denied scope=account path=/api/auth/login ip=… account_tag=… limit=10 window=60s retry_after=43s
```

`account_tag` is `sha256(email)[:12]`, not the address: these lines are emitted
on every blocked attempt and a security log full of raw victim emails is its own
disclosure risk. Correlate with `identity_tag("someone@example.com")` from
`middleware.rate_limiter` when you need to trace one account.

`scope=ip` is the IP axis, `scope=account` / `scope=mfa_otp_user` /
`scope=reset_identity` are the identity axes. One IP across many accounts =
credential stuffing; many IPs against one account = targeted brute force.

**Unblock a specific key** (e.g. a locked-out principal):

```python
from middleware.rate_limiter import rate_store
await rate_store.forget("login_account:someone@example.com", 60)
```

**Counters for a health/metrics probe:** `rate_store.metrics` →
`{"checks", "denied", "degraded", "short_circuited"}` (process-local since boot;
`degraded > 0` means the shared store was unreachable).

These are exposed on the monitoring surface (platform-admin only):

* `GET /api/system/metrics` → `rate_limiter` block:
  `{store, distributed, checks, denied, degraded, short_circuited,
  degraded_rate, last_degraded_log_epoch, db_timeout_ms, scope}` (via
  `middleware.rate_limiter.get_rate_limiter_health()`).
* `GET /api/system/alerts` raises a **warning** alert when `degraded > 0`
  (shared store was unreachable → limits fell back to per-instance) or when
  the store is the legacy in-memory one (`RATE_LIMIT_STORE=memory`).

**Caveat:** counters are process-local since boot. On autoscale each instance
reports its own sample — read them as per-instance indicators (`scope:
"per-instance-since-boot"`), never sum them into a global total. `distributed:
true` with `degraded: 0` means the limiter on *that* instance is actually
distributed right now.

**Raising a limit** for a legitimate burst: prefer the env vars over editing
`RATE_LIMITS`; the E2E gate signs in dozens of times a minute from one IP and is
the usual reason.

## 7. Tests

`backend/tests/test_distributed_rate_limit.py` — proves the multi-worker bypass
is gone (N simulated workers share one budget for N = 1/2/4/8), covers the
window boundary, the degraded fallback, the timeout guard, the deny cache, the
sweep and the 429 header contract.
