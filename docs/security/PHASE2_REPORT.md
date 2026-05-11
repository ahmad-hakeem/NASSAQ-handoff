# Phase 2 Security Hardening — Report

Companion to `docs/security/PHASE1_REPORT.md` and the audit at
`docs/security/SECURITY_AUDIT_2026-05-11.md`.

This phase delivers the highest-impact subset of the audit's Top-10 follow-up
work and **explicitly defers** the most expensive multi-week items into a
Phase 2.5 / Phase 3 follow-up. The intent was to leave the platform
measurably more defensible without a half-finished cookie cutover that
would break production for every authenticated client.

## Implemented

### 1. Trusted-proxy IP handling — audit C-1
- New helper `backend/utils/trusted_proxy.py` reads `TRUSTED_PROXY_CIDRS`
  (comma-separated CIDR allow-list, default empty).
- `X-Forwarded-For` is honoured **only** when `request.client.host` is in
  that list. Outside it, the un-spoofable peer address is used.
- Wired into `middleware/rate_limiter.py` (replacing the previous
  XFF-refuses-everything stance, which made per-IP limits useless behind
  Replit's edge) and `middleware/audit_middleware._extract_real_ip`.

### 2. Server-persisted impersonation — audit H-2 / M-6
- New table `impersonation_sessions` (Alembic revision
  `v1w2x3y4z5a6`) — stores `jti`, `original_user_id`, `original_role`,
  `target_role`, `target_tenant_id`, `reason`, `started_at`, `expires_at`,
  `ended_at`, `end_reason`, `ip_address`.
- `POST /auth/role-switch/switch` now:
  - requires a non-empty `reason` (4–500 chars),
  - rejects nested impersonation,
  - mints the switched token with a hard **15-minute TTL**, regardless of
    the platform-default access-token TTL,
  - persists a row keyed by the new token's JTI.
- `POST /auth/role-switch/restore` now resolves `original_user_id` from
  the server-side row keyed by the **current switched token's JTI** —
  it deliberately ignores the JWT body claim. This closes the H-2 IDOR
  where a switched-token holder could restore as any user_id of their
  choice. Negative test
  (`test_restore_ignores_forged_original_user_id`) covers it.
- A row whose `ended_at` is non-null cannot be re-used.

### 3. External audit sink — audit M-4
- `backend/services/audit_sink.py`: bounded asyncio queue + single
  background worker.
- Backend selectable via `AUDIT_SINK_BACKEND`:
  - `file` (default) — append + fsync newline-delimited JSON to
    `AUDIT_SINK_PATH` (default `/tmp/nassaq_audit.log`). Should sit on
    an append-only / object-locked volume in production.
  - `s3` — `boto3` is loaded lazily, only if configured. Each event is
    a separate object under `AUDIT_SINK_S3_PREFIX` so an S3 Object
    Lock policy on the bucket gives tamper-evidence.
  - `noop` — testing escape hatch.
- Drop-with-alert overflow policy: `put_nowait` rejects when the queue
  is full; the count is logged at `WARNING` (rate-limited).
- Sensitive keys (`password`, `*token*`, `secret`, `api_key`,
  `authorization`, `session*`, `otp`) are stripped before serialisation.
- Wired into the role-switch start/restore handlers.

### 4. CI guard for token storage
- `scripts/check_token_storage.sh` fails on any new
  `localStorage.setItem('nassaq_token'|'nassaq_refresh_token', …)` outside
  the single legitimate writer at
  `frontend/src/contexts/AuthContext.js`.
- Caught one pre-existing violation in `AccountSettingsPage.jsx`'s
  role-switch handler — fixed to route through `AuthContext.updateToken`.

### 5. Architect-review follow-ups (landed in this same task)
- **Legacy `/user-roles/switch` parity** — the architect flagged that
  the legacy endpoint at `routes/user_roles_routes.py` was untouched.
  The H-2 *identity* IDOR doesn't actually apply there (the legacy
  return-to-original handler reads `sub` from the validated current_user
  and the original role from the DB, never trusting a JWT-body
  user-id claim), but the cross-tenant platform-admin → school-role
  switch did still mint impersonation-style tokens with no TTL cap and
  no JTI persistence. That specific path now applies the same 15-min
  TTL and persists an `impersonation_sessions` row. Same-user
  multi-role swaps (principal ↔ teacher on the same tenant) are
  legitimately not impersonation and keep the default TTL — forcing a
  reason there would break working flows.
- **Audit-sink shutdown drain** — `audit_sink.drain(timeout=3.0)` is
  now wired into `app/lifecycle.shutdown_tasks` so events queued in
  the last few hundred ms before SIGTERM aren't silently lost.

### 6. Tests
- `backend/tests/test_security_phase2.py` covers:
  - trusted-proxy parsing (untrusted, trusted, X-Real-IP fallback,
    invalid CIDR safety),
  - impersonation reason enforcement,
  - persistence + 15-minute TTL cap,
  - the H-2 restore IDOR negative test,
  - audit-sink file emission with redaction,
  - audit-sink drop-on-overflow.

## Explicitly deferred (drift)

### 7. Full cookie/CSRF migration — DEFERRED to Phase 2.5
The original Phase 2 plan moved JWTs from `localStorage` to HttpOnly
cookies and added CSRF middleware. That refactor:
- touches every authenticated HTTP and WebSocket handler,
- requires a coordinated SPA-side migration (`AuthContext`, `apiClient`,
  every direct `axios` call in pages), and
- cannot be partially landed without breaking either old or new clients
  during deploy.
Phase 1 + the new CI guard already chokepoint all token mutations through
`AuthContext`, so the migration can land as one self-contained Phase 2.5
task without redoing the prep work. Token reads still live in
`localStorage` until then — flagged in the audit follow-up file.

### 8. Tenant-key (`tenant_id` → `school_id`) rename — DEFERRED
A coordinated Alembic rename across ~60 tables is high-risk. Phase 1
shipped `utils/tenant_scope.tenant_scoped_find_one`, which already
absorbs the `school_id` / `tenant_id` schema split safely via dual-key
fallback. Renaming is a cleanup, not a defence — it's deferred to a
dedicated task with a backfill window.

### 9. Shared rate-limit store (Postgres or Redis) — DEFERRED
The audit's M-3 item asks for a process-shared limiter. The current
in-process store is documented as a known limitation and the
trusted-proxy keying work above was deliberately wired through a single
helper so a future store swap doesn't have to re-touch the keying logic.
A naive Postgres implementation (an INSERT-per-request sliding-window
table) would do real damage under load — better to land it later with a
Redis-or-equivalent backend.

## Operational notes

- Set `TRUSTED_PROXY_CIDRS` in the production environment to the actual
  Replit edge CIDR(s) before relying on per-IP rate limits.
- Set `AUDIT_SINK_PATH` to a path on an append-only / object-locked
  volume in production. The default `/tmp` location is for dev only.
- A daily integrity-check job that diffs `audit_logs` rows against the
  external sink is **not yet wired**; the data shapes line up so this
  can be a small follow-up cron task.
