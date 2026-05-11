# Phase 3 Security Hardening — Implementation Report

**Task:** #168 — Phase 3 of `docs/security/SECURITY_AUDIT_2026-05-11.md`
**Tier targeted:** Level 4 — auditable for regulated children's data
**Status:** Tractable subset shipped. Multi-week items explicitly drifted to Phase 4.

## Shipped in this task

### 1. Refresh-token family tracking (stolen-token containment)
- New table `revoked_token_families` (Alembic migration `w1x2y3z4a5b6_phase3_security_hardening`).
- `create_refresh_token` now stamps a `fid` (family id) claim, preserved across rotation.
- `/auth/refresh` checks `revoked_token_families` on entry. If the lineage is revoked → 401 immediately.
- On replay (duplicate jti IntegrityError, wrapped in a savepoint so the outer
  txn stays alive) the entire lineage is inserted into `revoked_token_families`,
  killing every sibling token spawned from that ancestor.

### 2. WebSocket in-flight revocation
- `websocket_routes.py` ping loop now revalidates the connection's jti against
  `revoked_tokens` every 30s and closes with code 4001 if revoked. Previously a
  long-lived socket survived logout/admin-revoke until reconnect.

### 3. Hakim AI — pseudonymization + per-tenant kill-switch
- `services/hakim_pseudonymizer.py`: deterministic per-call substitution of
  student / teacher / parent names with opaque tokens (`STUDENT_001`, etc.) and
  unconditional removal of forbidden direct identifiers (`national_id`, `phone`,
  `email`). Round-trip restore for LLM responses.
- `services/hakim_llm_service.py`: added `tenant_id` kwarg. Reads typed column
  `schools.ai_consent_enabled` directly (JSON view does not expose it). When
  False → returns `AI_DISABLED_BY_TENANT` and never calls the LLM.
- New schema column `schools.ai_consent_enabled` with `server_default=true` so
  existing tenants are unaffected; principals can opt out per-school.

### 4. CI / governance scaffolding
- `scripts/ci_security_scan.sh` — runs `pip-audit` + `safety check` + `bandit`
  with non-zero exit on high-severity findings (suitable for CI gating).
- `docs/security/COMPLIANCE_PROGRAM.md` — documents the security program,
  vendor review cadence, training requirements, incident-response RACI.
- `docs/security/HAKIM_DPIA.md` — Data Protection Impact Assessment for the
  AI pipeline (lawful basis, data minimisation, retention, subject rights).

### 5. Tests
- `backend/tests/test_security_phase3.py` — 12 tests, all passing:
  - pseudonymizer round-trip (basic, no-leak of national_id/phone/email,
    longest-match ordering, unknown-token passthrough).
  - refresh tokens carry `fid`; rotation preserves family across multiple hops.
  - replay → entire family revoked; subsequent refresh in same family → 401.
  - AI consent flag False → `hakim_generate` short-circuits and never calls LLM.
  - Route-level integration: `/teacher/portfolio/generate-evidence-text`
    with `ai_consent_enabled=False` proves `tenant_id` is propagated end-to-end
    and the LLM client is never invoked.
  - Fail-closed consent: simulated DB read failure → `AI_CONSENT_UNVERIFIED`,
    no LLM call. Unknown tenant_id → `AI_CONSENT_UNVERIFIED`, no LLM call.

**Fail-closed posture:** consent enforcement is authoritative. If `tenant_id`
is provided but consent cannot be conclusively read (DB error, missing row,
schema drift), `hakim_generate` returns `AI_CONSENT_UNVERIFIED` and the LLM
is never called. Only an explicit `True` consent value allows outbound calls.
- All four production call sites updated to forward `tenant_id`:
  `portfolio_routes_mod.py` (3 sites + helper) and `parent_portal_routes.py`
  (2 sites — story + tip).
- Full security suite: **47 passed** (Phase 1 + Phase 2 + Phase 3, no regressions).

## Drift — explicitly NOT shipped (deferred to Phase 4)

These items in the audit report require >1 week of focused work or coordinated
infra changes and were intentionally excluded from this task. They should be
broken out as their own tasks rather than rolled into one super-task:

| Item | Why deferred |
|---|---|
| Nonce-based CSP + Vite/CRACO migration off `unsafe-inline` | Requires SSR/template changes across every HTML entry point and a Vite migration; high-risk for ongoing UI work. |
| Staff MFA (TOTP/WebAuthn enrolment + step-up) | New tables, new flows, recovery codes, admin UI, audit log integration. |
| RS256/ES256 + JWKS rotation | Requires KMS or filesystem key store, dual-signing window, frontend JWKS fetch, and ops runbook. |
| Per-tenant LLM provider abstraction | Vendor-pluggable provider registry, per-tenant config UI, billing isolation. (Pseudonymization + consent kill-switch shipped instead as a meaningful subset.) |
| Envelope encryption for sensitive columns (national_id, phone, address) | Requires KMS, key rotation, search/index strategy migration; touches dozens of tables. |
| Full per-parent consent ledger | New `consent_records` table + ingestion/UX for parents to grant/withdraw per-child per-purpose. |
| Automated retention sweep job | Scheduler + per-collection retention policy; needs legal sign-off on durations. |
| GDPR Art. 17 erasure script | Cross-cutting; touches every PII table, requires anonymization vs hard-delete decisions per artifact. |

### Items confirmed N/A or already done in earlier phases

- **`/system/health` minimisation** — already slim (`status` + `timestamp` only). Verified in Phase 2.
- **SRI for CDN assets** — only `frontend/src/index.css` `@import` of Google Fonts CSS, which is dynamically served by user-agent. SRI on a User-Agent-keyed response would break for many browsers. Documented as N/A.

## Verification

```bash
cd backend && TESTING=1 python -m pytest tests/test_security_phase1.py tests/test_security_phase2.py tests/test_security_phase3.py
# 47 passed
alembic upgrade head  # w1x2y3z4a5b6 applied cleanly
```

## Recommended next task

Open a Phase 4 task pointing at the drift table above. Highest impact next steps
in priority order: **(1) staff MFA**, **(2) RS256+JWKS**, **(3) erasure +
retention job**, **(4) nonce CSP**.
