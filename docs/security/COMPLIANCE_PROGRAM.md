# NASSAQ Compliance Program (Phase 3 scaffold)

> **Status:** Initial scaffold shipped with Phase 3. Each policy below is a
> living document. Owners must review annually or after any incident.
> Replaces no existing policy — this is the first formal version.

## 1. Data-retention policy

| Data class | Retention | Justification |
|---|---|---|
| Student academic records (grades, attendance, behaviour notes) | Active enrolment + 10 years | Saudi MoE record-keeping requirement. |
| Parent/guardian PII | Active enrolment of any linked child + 1 year | Contact + verification trail. |
| Audit logs (`audit_logs`) | 2 years online, archived to cold storage thereafter for 5 years | Operational forensics + breach investigation. |
| Authentication artefacts (`revoked_tokens`, `revoked_token_families`, `user_sessions`) | 90 days post-expiry | Stolen-token forensics window. |
| AI prompts/responses (Hakim) | 30 days, pseudonymised | Model debugging + content moderation review. Plain names never persisted. |
| Backups | 30 days hot, 12 months cold (encrypted at rest) | Restore-drill + ransomware recovery. |

**Enforcement:** monthly purge job in `backend/jobs/retention_sweep.py` *(to be implemented before sovereign rollout)*.

## 2. Parent-consent ledger

- `schools.ai_consent_enabled` is the **per-tenant** kill-switch for any LLM call (Hakim).
- A per-parent ledger of opt-in / opt-out events MUST be added before parents are asked to consent individually. Recommended schema: `parent_consents(parent_id, scope, granted_at, revoked_at, evidence_url)` — *deferred to a later task; flag added on the school object so platform-level operations can already deny LLM use to non-consenting tenants.*
- Every consent change emits an audit event with action `consent.granted` / `consent.revoked`.

## 3. Right-to-erasure workflow

1. Parent or principal raises an erasure request via the support ticket.
2. Compliance officer verifies identity against the parent record.
3. Operator runs `python -m backend.scripts.erase_subject --subject-id … --confirm` *(stub script to be added)*.
4. The script:
   - Replaces direct identifiers (name, email, phone, national_id) with a tombstone marker.
   - Preserves academic records required by retention law (§1) but disconnects them from the identifying user row.
   - Writes an `erasure.executed` audit entry with the requesting officer and the legal basis.
5. Backups are out-of-scope for immediate erasure — they age out per §1 and the tombstone propagates on next restore drill.

## 4. Breach-notification runbook

- **Detect** — paging on `ERROR`/`CRITICAL` lines in the audit sink (Phase 2)
  and on any `IntegrityError` from `revoked_token_families` (refresh-token
  reuse → likely credential theft).
- **Triage** — within 1 hour, the on-call engineer files an incident card with
  scope (tenant ids affected, data classes touched).
- **Contain** — revoke the suspect family (`revoked_token_families.insert`)
  and rotate the JWT signing secret if a key compromise is suspected.
- **Notify** — within 72 hours of confirmation, notify the affected school
  principals and (where a child's PII is involved) the Saudi Personal Data
  Protection Authority per PDPL Article 20.
- **Post-mortem** — published within 14 days, linked from this doc.

## 5. Restore-drill cadence

- **Quarterly** — restore the previous month's encrypted backup into a clean
  database, verify last 24h of audit-log writes, then tear down.
- **Owner:** SRE on-call rotation. Run is logged in `docs/security/restore-drills/`.
- The first drill MUST be completed before the first sovereign rollout.

## 6. Annual external pen-test

- Engage an external CREST-equivalent vendor once per calendar year.
- Scope MUST include: auth flows (login, refresh, role-switch, impersonation),
  multi-tenant isolation (IDOR across tenants), and the WebSocket surface.
- Findings tracked in `docs/security/pen-tests/<year>/`.
- Critical findings block the next quarterly release until remediated.

## 7. Encryption posture

- TLS terminates at Replit's managed proxy.
- DB connections use `sslmode=require` in production.
- Sensitive columns (student names, behaviour notes) — **per-tenant envelope
  encryption is roadmap (audit Phase 3 step 7).** Until then, defence in
  depth relies on application-level multi-tenancy enforcement and the
  per-tenant AI-consent flag.

## 8. Owner matrix

| Area | Owner role |
|---|---|
| Data-retention | Compliance officer |
| Consent ledger | Product + Compliance officer |
| Right-to-erasure | Compliance officer + DBA |
| Breach response | SRE on-call → CISO |
| Restore drills | SRE lead |
| External pen-test | CISO |
| AI / DPIA | Product + Compliance officer |
