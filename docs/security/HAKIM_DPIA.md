# Hakim AI — Data Protection Impact Assessment (Phase 3 scaffold)

> **Status:** Initial DPIA shipped with Phase 3 alongside the
> pseudonymization layer and per-tenant consent flag. Update on every
> material change to provider, prompt shape, or data fields.

## 1. Processing description

The "Hakim" assistant invokes a large language model to generate or improve
free-form Arabic/English educational text on behalf of platform users
(teachers, principals, platform admins). Use cases include drafting student
feedback, summarising weekly reports, and suggesting behaviour-plan wording.

| Field | Value |
|---|---|
| Controller | The school tenant (school_id) |
| Processor | NASSAQ platform |
| Sub-processor | OpenAI (default) — pluggable per tenant (roadmap) |
| Region | OpenAI default region (US). Sovereign deployments require an in-region or on-prem endpoint — see §6. |
| Lawful basis | Legitimate interest of the school in producing high-quality educational content, gated by an explicit per-tenant `ai_consent_enabled` flag. |

## 2. Data flow

```
User input (Arabic or English text + structured context)
        │
        ▼
Hakim service (backend/services/hakim_llm_service.py)
        │  ── pseudonymize names + drop forbidden identifiers
        │     (backend/services/hakim_pseudonymizer.py)
        ▼
LLM provider (OpenAI Chat Completions)
        │  ── response with tokens like [STUDENT_1]
        ▼
Hakim service ── rehydrate tokens to real names
        │
        ▼
User
```

## 3. Categories of data sent to the provider (post-sanitisation)

| Category | Sent? | Notes |
|---|---|---|
| Personal names (student / teacher / parent) | **No** | Replaced with stable opaque tokens (`[STUDENT_1]`, `[TEACHER_2]`, …) before the prompt is built. |
| Direct identifiers (national_id, phone, email, address, birthdate) | **Never** | Dropped entirely from context by `_FORBIDDEN_KEYS` filter. |
| Academic free-text (the user's draft text or context they've typed) | Yes | The user's own composition. Names *inside* this free text are also tokenised when the caller registers them. |
| Subject / grade / class metadata | Yes | Considered low-risk descriptive context. |
| Tenant id / user id | No | Not added to prompt; only used internally for routing. |

## 4. Storage of prompts/responses

- The provider's data-retention defaults apply (OpenAI: 30 days for abuse
  monitoring, then deleted; not used for training when the platform is on
  the standard API tier).
- Locally we do **not** persist plain-text prompts or responses. Validation
  failures log only (mode, field, generation_id, length, reason).

## 5. Per-tenant kill-switch

`schools.ai_consent_enabled` (boolean, default TRUE). When FALSE, every
`hakim_generate` call returns `{success: False, reason: "AI_DISABLED_BY_TENANT"}`
without contacting any provider. This is the operational control for tenants
that have not signed an AI-processing agreement.

## 6. Roadmap (not yet shipped)

- **Per-tenant LLM provider** — selectable in-region (e.g. Azure OpenAI in
  KSA) or on-prem (e.g. local vLLM endpoint) for sovereign tenants.
- **Per-parent consent ledger** — granular consent at the child level layered
  on top of the tenant-level flag.
- **Prompt/response audit trail** with redaction for compliance review.

## 7. Risk assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Direct identifier leakage to provider | Low | High | `_FORBIDDEN_KEYS` filter drops them before the prompt is built. |
| Re-identification from tokenised text | Low | Medium | Tokens are session-scoped; provider cannot link `[STUDENT_3]` across calls. |
| Provider outage degrading product | Medium | Low | Hakim returns the user's input untouched on failure (`AI_DISABLED`). |
| Tenant disagrees with AI processing | High | Medium | `ai_consent_enabled=FALSE` blocks all calls. |
| Provider region not acceptable to regulator | Medium | High | **Open** — sovereign roadmap (§6). |

## 8. Owners

- **DPIA owner:** Compliance officer.
- **Engineering owner:** Hakim service maintainer.
- **Review cadence:** annually, or on any change to provider / data fields.
