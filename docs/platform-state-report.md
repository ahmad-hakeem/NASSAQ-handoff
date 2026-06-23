# NASSAQ — Platform State Report

> **Generated:** 2026-06-23
> **Scope:** Whole-platform state snapshot for reuse as context by future AI models (report generation, debugging, ticketing, implementation guidance).
> **Source of truth:** Grounded in current code (`backend/`, `frontend/`), `replit.md`, `threat_model.md`, `docs/it-phase2-reference.md`, and the engineering memory in `.agents/memory/`. Statements are written from **current code reality**; where an older spec conflicts, the drift is called out explicitly.
> **How to read status labels:** `stable` = implemented and exercised; `partial` = works but with known gaps/caveats; `risky` = works but is a security/perf/tenancy hazard zone; `blocked` = intentionally denied by policy/architecture; `spec-only` = designed/backed but not user-reachable.

---

## 1. Executive Summary

NASSAQ (نَسَّق) is an **Arabic-first, multi-tenant school-management platform**. Frontend: React (CRACO/CRA + webpack-dev-server v5 shim), Tailwind, Radix, RTL-first. Backend: FastAPI (async SQLAlchemy 2.0 over PostgreSQL/asyncpg), Pydantic contracts, JWT auth with refresh-family rotation, bcrypt, AI via the OpenAI-compatible gateway. Schema is managed **exclusively by Alembic** with a production startup head-gate.

**Overall health:** The platform is feature-complete across the core school workflows (auth, scheduling, attendance, grading, behavior, communication, reporting, parent/teacher dashboards) and ships a fully separate **Independent Teacher (IT)** product line (self-serve single-teacher workspaces) layered on the same codebase via synthetic-tenant scoping.

**What is stable today:** Authentication/session/MFA, tenant isolation, the modern smart-scheduling engine + master grid, attendance, assessments/grading + the follow-up sheet (كشف المتابعة), behavior, communication + WebSockets, reporting/exports, classes/students CRUD with the canonical stage/grade system, the parent portal, and the IT Phase-2 surface.

**Main current product direction:** Hardening the **Independent Teacher** workspace line (cross-workspace co-teaching, public token redemption flows, lifecycle/export) and ongoing **security hardening** of multi-tenant/multi-role authorization (the bulk of `threat_model.md`). Most recent fix: **Parent Portal timetable grid period normalization**.

**Primary risk themes:** (1) cross-tenant / cross-role authorization on legacy and by-id surfaces; (2) public token-redemption flows in the IT line; (3) AI-endpoint abuse/cost; (4) export formula-injection. These are tracked as standing scan anchors in `threat_model.md` — treat them as caution zones, not assumed-open holes.

---

## 2. Role Matrix

Roles below are the `UserRole` values (`backend/models/enums.py`, `backend/dependencies.py`). Frontend access is enforced separately in `frontend/src/routes/appRoutes.js` + `frontend/src/components/guards/RouteGuards.js`.

| Capability | Platform Admin | Principal / School Admin | School Sub-Admin (`n`) | Teacher | Independent Teacher | Parent | Student |
|---|---|---|---|---|---|---|---|
| Login + session | ✅ | ✅ | ✅ | ✅ | ✅ (workspace perimeter gate) | ✅ | ⚠️ backend only |
| MFA / step-up | ✅ required for privileged ops | ✅ | ✅ | ✅ (enforced server-side) | ✅ 403 step-up envelope | ✅ | n/a |
| Cross-tenant traversal | ✅ via hardened impersonation | ❌ own tenant only | ❌ | ❌ | ❌ own `itw_` workspace only | ❌ | ❌ |
| Schools / users mgmt | ✅ | ⚠️ own school only | ⚠️ custom perms only | ❌ | ❌ | ❌ | ❌ |
| Smart scheduling / master grid | ✅ (view/ops) | ✅ | ⚠️ perm-gated | view own | ✅ manual editor (IT) | ❌ | ❌ |
| Attendance | ✅ | ✅ | ⚠️ | ✅ own classes | ✅ own classes | view child | view self (be) |
| Assessments / grading / follow-up | ✅ | ✅ | ⚠️ | ✅ own classes | ✅ own classes | view child | view self (be) |
| Behavior / incidents | ✅ | ✅ | ⚠️ | ✅ own classes | ✅ | view child | view self (be) |
| Communication / notifications | ✅ | ✅ broadcast | ⚠️ | ✅ scoped | ✅ scoped | ✅ recipient | n/a |
| Parent portal | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Lesson planner / AI planning | ❌ | ❌ | ❌ | ⚠️ | ✅ (IT hub) | ❌ | ❌ |
| Bulk import (students) | ✅ | ✅ | ⚠️ | ❌ | ✅ (IT) | ❌ | ❌ |
| Hakim AI assistant | ✅ exec diagnostics | ✅ | ✅ | ✅ | ✅ | ✅ (insights) | ❌ |
| Workspace export / lifecycle | ✅ purge (admin) | ❌ | ❌ | ❌ | ✅ export/soft-delete | ❌ | ❌ |
| Role switch / impersonation | ✅ (mint) | ⚠️ multi-role only | ⚠️ | ❌ | ❌ | ❌ | ❌ |

Legend: ✅ available · ⚠️ partial/conditional/perm-gated · ❌ denied · `be` = backend-implemented but frontend access disabled.

---

## 3. Architecture Overview

### 3.1 Tenancy & workspace scoping
- **`tenant_id` ⇄ `school_id` are aliases** for one logical scope. `backend/engines/sql_utils.py` defines `TENANT_ALIAS` and `_build_orm_filter_conditions` auto-remaps the key to the real ORM column; `backend/utils/tenant_scope.py:tenant_scoped_find_one` does a primary→alternate column fallback for mixed-schema legacy rows while staying pinned to the caller's tenant.
- **Resolution:** `backend/utils/tenant_scope.py:resolve_school_id` enforces that non-platform users only operate on their own tenant. `X-School-Context` / param overrides are only honored for platform admins **whose impersonation JWT claim matches** — otherwise ignored. Treat any tenant-context rewrite as equivalent to impersonation (same MFA/audit/expiry guarantees).
- **Independent Teacher workspaces are synthetic:** IT users have **no real `school_id`**; `backend/auth_scope.py:independent_workspace_id(user)` returns `itw_{user_id}`, and all `gd_find` calls scope to it, preventing IT↔IT leakage.
- **Real school vs IT discriminator:** `school_type` / `tenant_type == 'independent_teacher'`. `entity_kind` is a **computed property** on `SchoolResponse` (`backend/models/school.py`), **not a DB column** — never filter on it in SQL.
- **By-id 404 invariant (spec §8 inv. 3):** every IT-reachable by-id read must return **404 (never 403/200)** for cross-workspace lookups so the API never confirms existence of foreign rows. `tenant_scoped_assert_one` enforces this (filter returns `None` → 404).

### 3.2 RBAC & permission source of truth
- **Roles:** Platform tier (`platform_admin`, `platform_sub_admin`, `platform_operations_manager`, `platform_technical_admin`, `platform_support_specialist`, `platform_data_analyst`, `platform_security_officer`, `platform_sales`, `platform_marketing`, `platform_quality`); School tier (`ministry_rep`, `school_principal`, `school_admin`, `school_sub_admin`, `teacher`, `student`, `parent`, `driver`, `gatekeeper`); `independent_teacher`; `testing_account`.
- **Permissions:** the `Permission` enum + `ROLE_PERMISSIONS` map live in `backend/middleware/rbac.py`. **Effective permissions = base-role union + per-user `custom_permissions`** via `RBACMiddleware.get_user_permissions`.
- **Guards:** `require_permission(perm)` (fine-grained), `require_roles([...])` (`backend/dependencies.py`), `require_recent_mfa(max_age)` (checks `mfa_recent_at` JWT claim).
- **Gotcha:** `school_sub_admin` (wire value `"n"`) has **no base permission set** — its permissions are **custom-only**. A sub-admin with no custom grants sees almost nothing.

### 3.3 Auth, session & MFA
- **Login:** `POST /auth/login` (`backend/routes/auth_routes_mod.py`) verifies credentials, checks lock/deactivation, evaluates MFA policy; issues a `type=mfa_challenge` token when MFA required+enrolled, else access+refresh.
- **JWT:** `create_access_token` adds `mfa_recent_at` + `jti`; `create_refresh_token` adds `family_id` (fid). Rotation keeps `fid`, changes `jti`; replaying a used `jti` revokes the **whole family** (stolen-token defense). Session revocation must kill the access token **and** the refresh family.
- **`GET /auth/me`** returns user context and is exempt from the MFA-enrollment gate; it also carries the **`mfa_enforcement_disabled`** flag.
- **MFA kill-switch (`n`):** `mfa_policy.is_enforcement_disabled()` suppresses both the login gate and the FE enroll redirect (surfaced via `/auth/me`). If MFA "looks mandatory" unexpectedly, check this flag first, not the backend gate.
- **IT 403 step-up envelope (§5.7):** all IT write/export surfaces emit the step-up requirement as **HTTP 403** so the FE axios interceptor replays after passkey assertion. Use `require_recent_mfa_403()` (IT-only) / `require_recent_mfa_403_if_independent_teacher()` (shared). **Bare `require_recent_mfa` on shared routes is forbidden** — its 401 is treated as a hard logout by the FE.
- **Role switch / impersonation:** hardened `POST /role-switch/switch` requires fresh MFA + reason, persists to `impersonation_sessions`, mints a 15-min capped token; `POST /role-switch/restore` revokes the switched `jti`. Legacy `POST /user-roles/switch` handles same-tenant multi-role swaps + admin cross-tenant (Phase-2 hardened). The legacy `/user-roles/return-to-original` restore path is a standing scan anchor.

### 3.4 Data layer
- **GenericDocument model:** several collections (`timetables`, `timetable_sessions`, `schedules`, etc.) are stored as **GenericDocument rows, not first-class tables**. Query exclusively via `gd_find` / `gd_find_one` (`backend/engines/sql_utils.py`); `Repos`/`db` (`backend/dependencies.py`) owns the `AsyncSession`. `warn_missing_tenant_filter` logs any tenant-scoped query missing a tenant filter.
- **Schema discipline:** Alembic only; no `Base.metadata.create_all()/drop_all()`. Build phase runs `alembic upgrade head` once (`build.sh`); the app refuses to boot in production if live schema ≠ head (`backend/app/lifecycle.py`). Drift + destructive-migration guard tests exist (see `replit.md`).

### 3.5 Scheduling storage (non-obvious)
- Live schools use the **modern** `timetables` + `timetable_sessions` GenericDocument collections; legacy `schedules` is empty. Resolve teacher sessions via `_resolve_teacher_sessions` — never inline. The **old scheduling system must not be reintroduced** (hard user preference).
- Master grid: single window `MASTER_GRID_TEACHER_WINDOW = 200`, **no pagination** (workspace redesign 2026-05-06).
- Real `time_slots` use `slot_number` (no `period_number` column); breaks are interleaved (e.g. slots 4 & 8). Period labels derive from **contiguous post-break-filter index**, not `slot_number`.

### 3.6 Design invariants (UI/UX policy)
- All warnings/errors/confirms use **`NassaqAlertDialog`** — never native `alert()`/`confirm()`/`toast.error()` for critical interactions.
- Hijri conversion via `hijri-converter`; **`Intl.DateTimeFormat('ar-SA-u-ca-islamic')` is forbidden**.
- RTL via logical properties (`ps/pe/ms/me`, `text-start/end`); no raw hex in JSX (brand tokens only); no emoji icons (lucide `strokeWidth={1.5}`, `aria-hidden`); no text gradients; no `console.log` in pages/contexts.
- API errors return **safe Arabic messages** — never raw `str(e)`.
- The **landing page** intentionally overrides four `design_guidelines.json` rules for funnel conversion (turquoise as unifying accent, navy/light alternation, larger display headings, turquoise CTAs) — do not "fix" these back.

---

## 4. Account-Type Deep-Dive

### 4.1 Platform Admin
- **Login/session:** standard; privileged ops require fresh MFA. Cross-tenant traversal only through hardened impersonation (`/role-switch/switch`).
- **Nav shell (`Sidebar.jsx`):** Dashboard `/admin`, Schools `/admin/schools-table`, Users `/admin/users`, System Monitoring `/admin/monitoring`, Security Center `/admin/security`, Workspace Purge `/admin/workspace-purge`, Audit Logs `/admin/audit`.
- **Tenant scope:** global. **Denials/cautions:** credential-minting (create users, reset passwords, mint principal creds, workspace purge) are high-risk — must carry fresh-MFA posture; flagged in `threat_model.md`. Platform dashboard stats merge **two** stat endpoints client-side (keep their role sets identical or cards show 0); note ops-manager FE value `platform_n` ≠ BE `platform_operations_manager`.

### 4.2 School Principal / School Admin
- **Nav:** Command Center `/principal`, School Schedule `/school/schedule`, Users & Classes `/admin/users-management`, Staff Attendance `/admin/teacher-attendance`, School Settings `/school/settings`.
- **Scope:** strictly own tenant. Legacy `PATCH/PUT /schools/{school_id}` with a foreign id is a standing scan anchor (cross-tenant tamper) — caution.
- **Denials:** cannot traverse other schools; cannot perform platform credential minting. Same-tenant role-hierarchy break (lower-tier admin resetting/suspending a higher-privileged account) is a flagged risk.

### 4.3 School Sub-Admin (`n` / `school_sub_admin`)
- **No base permissions** — entirely custom-permission driven. With no grants, the shell is nearly empty. Default dashboard `/school`.

### 4.4 Teacher (real-school)
- **Identity is dual:** a teacher is a `users` row (login/tenant) **plus** an authoritative `teachers` row (keyed by `school_id`, drives Teachers page/academics). Admin paths must reconcile **both**. Teacher auto-linking from mutable email/phone/national_id is a flagged risk.
- **Nav:** Dashboard `/teacher`, My Classes `/teacher/classes`, My Achievements `/teacher/achievements`, AI Insights `/ai-insights`.
- **Class membership** comes from 3 overlapping sources: `teacher_assignments` (authoritative + permission), `teacher_class_assignments` (convenience), `schedule_sessions` (grid). Empty "My Classes" usually = sessions without assignments → reconcile additively.
- **Standby periods (حصص الانتظار):** empty list is usually a **config** issue (`teachers.weekly_periods` NULL/≤0), not a bug — engine excludes by design.

### 4.5 Independent Teacher (`independent_teacher`)
- **Perimeter gate:** if the `itw_` workspace isn't materialized (`tenant_id` missing), FE redirects to `/teacher/onboarding`; bootstrap routes are allowlisted through the workspace gate.
- **Nav:** teacher shell + **Time Management Hub `/teacher/planning`** (IT-only) housing lesson planner, calendar, import, schedule editor, collaborators.
- **Scope:** synthetic `itw_{user_id}`; the **only** sanctioned cross-workspace path is `workspace_collaborators` (co-teaching, single shared `class_id`, via `backend/utils/collab_access.py` — never broaden `TenantIsolation`).
- **MFA:** all write/export surfaces use the **403 step-up envelope**.
- **Tab gating:** always-entitled IT tabs (lesson-planner/import) must gate on **role**, not the lazy `/auth/me/permissions` fetch (which only false-negatives → tabs vanish on slow/failed fetch).

### 4.6 Parent
- **Nav:** Home `/parent`, Student Profile `/parent/children`, Communication Center `/parent/communication`, Settings `/parent/settings`.
- **Linkage:** real-school guardian relationship/email is canonical **only in `guardian_links`** (the `gd_*` layer drops these fields from `students`/`parents` ORM rows) — single-student GET must enrich. Stale `parents.student_ids` / inactive `guardian_links` honoring is a flagged disclosure risk; relationship endpoints must re-authorize every adjacent student.
- **Recently fixed:** Parent Portal **timetable grid** now renders from one canonical teaching-period source (see §7).

### 4.7 Student
- **Backend implemented** (`backend/routes/student_portal_routes.py`: schedule, grades, achievements, attendance) but **frontend access is intentionally disabled** — `RouteGuards.js` maps `student → "/login"` and `/student/*` is a Navigate-to-`/login` redirect. Treat the student portal as **blocked/spec-only on the frontend**, not broken.

### 4.8 Role-switching / impersonation (cross-cutting)
- Hardened mint + DB-persisted `impersonation_sessions` + 15-min cap + reason + fresh MFA. FE `AuthContext` lets platform admins preview a school as principal (swaps token/security context). Alternate self role-switch paths and the legacy return-to-original path are standing scan anchors — authorization-changing flows must promptly invalidate stale real-time + switched-session access.

---

## 5. Module Status Table

| Module | Status | What it does (current code) | Key backend | Key frontend | Tenancy / data assumptions | Known defects / hazards | Recommended next safe action |
|---|---|---|---|---|---|---|---|
| Auth & session | stable | Login, JWT access+refresh family rotation, lock/deactivation, MFA challenge | `auth_routes_mod.py`, `dependencies.py`, `engines/session_engine.py`, `utils/tokens.py` | `contexts/AuthContext.js`, `services/apiClient.js` | Tenant pinned per token; revocation must kill refresh family | Account-unlock/reactivate paths must advance `last_password_change` + revoke sessions (anchor) | Keep revocation joins consistent; no schema change needed |
| Role switch / impersonation | stable (risky surface) | Hardened switch/restore + legacy multi-role | `auth_routes_mod.py`, `user_roles_routes.py` | `AuthContext.js` role switcher | `impersonation_sessions`; 15-min cap | Alternate/legacy paths bypass hardened controls (anchors) | Funnel all switches through hardened path; audit alternates |
| Tenant isolation / scoping | stable (critical invariant) | Alias remap, fail-closed scoping, synthetic IT id, by-id 404 | `utils/tenant_scope.py`, `middleware/tenant_isolation.py`, `engines/sql_utils.py`, `auth_scope.py` | n/a | `tenant_id⇄school_id`; `itw_` synthetic; by-id must 404 | `X-School-Context`/param overrides are recurring escalation anchors | Never widen `TenantIsolation`; use callsite widening for §6.7 only |
| Smart scheduling / master grid | stable | Modern `timetables`+`timetable_sessions`, generation engine, master matrix DnD, conflict validation | `schedule_master_grid_routes.py`, `scheduling_smart_engine_routes.py`, `engines/smart_scheduling_engine.py` | `SchedulePageNew.jsx`, `components/schedule/MasterMatrixDnd.jsx` | GenericDocument collections; `slot_number` not `period_number`; window=200 no pager | Old system must NOT return; gap-filler must respect `weekly_periods` (else HC-09 PUBLISH_BLOCKED) | Touch only via `_resolve_teacher_sessions`; sign-off before standby-engine changes |
| Attendance & sessions | stable | Record, bulk mark, excuses, statistics | `attendance_routes.py`, `attendance_routes_mod.py`, `engines/attendance_engine.py` | `AttendancePage.jsx`, `TeacherModule/TeacherAttendanceManagePage.jsx`, `InlineAttendanceTable.jsx` | Class/tenant scoped; session-by-id via `_verify_session_owner` (404 cross-tenant) | Legacy `/attendance/*` read/report routes are disclosure anchors | Prefer modular routes; keep `_verify_session_owner` fail-closed |
| Assessments / grading + follow-up (كشف المتابعة) | stable | Weighted grades, report cards, serialized follow-up sheet | `assessment_routes.py`, `engines/assessment_engine.py` | `AssessmentPage.jsx`, `components/teacher/FollowupGradesTable.jsx` | All follow-up writes route through one serialized flush; per-key dirty+revision vs 30s merge poll | Hydration re-overlay bug class (manual vs derived); homework intentionally toggle-locked; participation is per-step clamp [0,max] | Don't "fix" homework toggle-lock; preserve keep-manual guard |
| Behavior / incidents | stable | Positive/negative categories, severity, auto-escalation | `behaviour_routes_mod.py`, `engines/behaviour_engine.py` | `TeacherModule/TeacherBehaviorPage.jsx`, `components/parent/panels/BehaviorPanel.jsx` | Tenant + class scoped | — | — |
| Communication & notifications + WS | stable | Multi-channel broadcast (in-app/SMS/email), audience scoping, realtime | `communication_routes.py`, `notification_routes_mod.py`, `websocket_routes.py` | `CommunicationCenterPage.jsx`, `NotificationBell.jsx`, `SendNotificationWizard.jsx` | WS auth must match HTTP (token validity/revocation) | Legacy comm read APIs + IT inbox resolution in legacy routes are anchors; parent messaging recipient-policy bypass anchor | Route IT recipient eligibility via classify-not-filter |
| Parent portal | stable (recent fix) | Multi-child dashboard: performance, attendance, behavior, schedule grid, reports | `parent_portal_routes.py`, `utils/parent_children_resolution.py` | `ParentPortal/ParentPortalDashboard.jsx`, `ChildDetailsPage.jsx`, `components/parent/panels/*` | Linkage canonical in `guardian_links`; AI insights need rate limit | Timetable grid period-normalization fixed (§7); parent-linkage fallbacks are disclosure anchors | Cap parent AI-insights endpoint; re-authorize adjacent students |
| Student portal | blocked (FE) / spec-only | Backend serves schedule/grades/achievements/attendance | `student_portal_routes.py` | `StudentPortal/*` exists but `/student/*` → `/login` | Self-scoped | FE access deliberately disabled in `RouteGuards.js` | Do not treat as a bug; re-enable is a product decision |
| Classes & students CRUD | stable | Canonical 3-stage/12-grade system, fail-closed on create+edit, capacity enforcement | `academics_class_routes.py`, `academics_student_routes.py`, `utils/canonical_grades.py` | `ClassesPage.jsx`, `StudentsPage.jsx`, `AddStudentWizard.jsx` | `grade_id` authoritative; unified for real + IT; capacity via `resolve_class_capacity` (fallback 30) | Class-index loaders MUST select `capacity` or all classes fall back to 30; cross-workspace roster serializer (`GET /classes/{id}/students`) is an IT PII anchor | Keep canonical resolver; never expose full `StudentResponse` cross-workspace |
| School & account settings | stable | Time slots, working days, MFA/security settings | `school_settings_mod.py`, `settings_routes.py`, `mfa_routes.py` | `SchoolSettingsPagePro.jsx`, `AccountSettingsPage.jsx` | Tenant scoped; MFA session revocation must revoke refresh family | MFA revocation-family-miss anchor; name-update must use AuthContext `api` | Keep `GenericNameGuard` ≥3-char real-name enforcement |
| Reporting & exports (PDF/CSV/XLSX) | stable (risky writers) | Unified report engine, multi-format, school-wide vs class | `reporting_routes_mod.py`, `engines/reporting_engine.py`, `engines/export_engine.py` | `components/parent/panels/ReportsPanel.jsx`, `TeacherModule/TeacherAnalyticsPanel.jsx` | Shared writer + IT analytics writer | **Formula-injection**: every CSV/XLSX writer must neutralize leading `=+-@` and set xlsxwriter `strings_to_formulas/urls=False`; two writers exist — keep in sync | Audit both writers on any export change |
| Calendar events | stable | Admin calendar (exams/holidays/trips), CSV import; IT personal calendar (`is_personal`) | `calendar_routes_mod.py`, `independent_teacher_calendar_routes.py` | `components/dashboard/AdminCalendar.jsx`, `TeacherModule/TeacherPersonalCalendarPage.jsx` | IT personal vs school-wide separated by `is_personal` | — | — |
| Hakim AI + AI insights | stable (cost-risk) | Multi-role assistant, exec diagnostics, product-hub prompt | `ai_routes_mod.py`, `engines/hakim_ai_engine.py`, `services/hakim_llm_service.py` | `AIInsightsPage.jsx`, `components/hakim/HakimAssistant.jsx` | gpt-5-mini reasoning contract: budget ≤1024 returns EMPTY; open-ended needs ≥2048; client MUST pass gateway base_url | General `/api/hakim/chat` lacks dedicated abuse cap (anchor); parent AI-insights uncached (anchor) | Add per-surface abuse caps; respect token-budget contract |
| IT bulk import | stable | Arabic CSV student import, name validation, quota | `independent_teacher_bulk_import_routes.py` | `TeacherModule/ImportStudentsPage.jsx` | IT workspace scoped; Noor restore semantics (soft-delete = restore) | Commit re-resolves `class_id` from live index (honor per-pair overrides) | Keep preview/commit dedupe in agreement |
| IT lifecycle / export / purge | stable (token-risk) | Export → soft-delete → reactivate (≤30d) → platform hard-delete; single-use export tokens | `independent_teacher_workspace_lifecycle_routes.py`, `platform_workspace_purge_routes.py` | `AccountSettingsPage.jsx`, admin purge route | Soft-delete requires export within 24h; hard-delete platform-admin out-of-band only | Public export-download auth (`_authenticate_export_download`) skipping `last_password_change`/`is_active` is an anchor | Re-verify token freshness on download |
| IT co-teaching / collaborators | stable (cross-tenant) | JWT invite, accept, `workspace_collaborators`, scoped to shared `class_id` | `independent_teacher_collab_routes.py`, `utils/collab_access.py` | `components/teacher/CollaboratorsTab.jsx` | Only sanctioned IT↔IT path; §8 relaxed only for named `class_id` | Accepted collaborator reading full roster PII is an anchor | Widen at callsite only; never broaden `TenantIsolation` |
| IT parent invitations | stable (flagged) | 7-day JWT, public accept landing, materializes `users` + links student | `independent_teacher_invitation_routes.py`, `public_routes.py` | `ParentInvitationAcceptPage.jsx` | Behind `IT_PARENT_INVITATIONS_ENABLED` | Public accept can rebind to another family's `parents` row via caller `national_id` (anchor) | Validate redemption against canonical identifiers |
| IT manual schedule editor | stable | Optimistic concurrency via `schedule_sessions.version`; `pg_advisory_xact_lock` on upsert | `independent_teacher_schedule_routes.py` | `TeacherModule/WorkspaceSchedulePage.jsx` (handles 409) | `version` token ignored by real-school write paths | — | Keep 409 conflict handling intact |

---

## 6. Known Risks & Blockers

### 6.1 Security (standing scan anchors — treat as caution zones)
`threat_model.md` is the authoritative list. The recurring themes:
- **Tenant-context overrides:** raw `X-School-Context` / param/body `school_id` overrides; legacy academic-structure routes trusting caller `school_id`; legacy `PATCH/PUT /schools/{school_id}` cross-tenant tamper.
- **Authorization breaks:** teacher overreach in unified reporting/export; teacher-reachable directory/relationship/consent/attendance disclosure surfaces; same-tenant role-hierarchy breaks (lower-tier admin taking over higher-privileged accounts).
- **Credential minting:** platform-admin user-create / password-reset / principal-cred routes reachable without fresh MFA → persistent-backdoor risk.
- **Parent/guardian linkage:** stale `parents.student_ids` / inactive `guardian_links`; relationship pivots to siblings; privacy-export leaking password hashes / MFA state.
- **IT public token flows (2026-05-20):** parent-invitation rebind via `national_id`; export-download accepting stale/reactivated tokens; collaborator full-roster PII; export writers without formula neutralization.
- **AI abuse/cost:** `/api/hakim/chat` and parent AI-insights lack dedicated abuse caps.
- **Session revocation joins:** unlock/reactivate paths that don't advance `last_password_change` or revoke refresh family.

### 6.2 Functional / correctness caveats (from engineering memory)
- Follow-up sheet hydration re-overlay (manual vs derived) — participation/performance fixed via keep-manual guard; **homework is intentionally toggle-locked** (not a bug).
- `homework_mode` is stored but the engine ignores it (only `homework_enabled`); 2 `didnt_submit` tests are pre-existing red, out of scope.
- Scheduling gap-filler must respect `weekly_periods` or it floods sparse classes → HC-09 PUBLISH_BLOCKED. Under-placement is separate (genuine infeasibility, policy question).
- Class-index loaders that don't SELECT `capacity` make every class fall back to 30.

### 6.3 Performance hot spots
- N+1 risk on related fetches — use bulk `gd_find` with `$in`.
- Hakim LLM token-budget contract (gpt-5-mini): too-small budgets return EMPTY; open-ended calls need ≥2048.
- Autoscale cold-start: keep only the schema head-gate blocking on boot; defer non-critical startup DB work via `create_task` (publish flakes on `GET /` racing cold start).

### 6.4 Deployment / infra
- `pg_trgm` trigram GIN indexes: Replit's publish-time schema diff strips `gin_trgm_ops` → deploy failure; drop such indexes via Alembic.
- Custom-domain TLS: `ERR_CONNECTION_CLOSED` on the custom domain while `*.replit.app` is 200 = DNS/cert verification gap, **not** an app bug.
- The editor "Backend API" workflow runs as **`ENVIRONMENT=production` on the real prod DB** with a head-gate — new Alembic heads must be applied (dry-run first) or boot fails. There is **no `--reload`** — restart after backend edits.

---

## 7. Recently Completed Work

- **Parent Portal timetable grid period normalization (2026-06-23):** the grid now derives ONE canonical teaching-period list from school `time_slots` (fallback `school_settings.periods_per_day`, then distinct session periods) instead of a per-day session-count max with array-index packing. Each session lands on its TRUE period row; break/orphan/null periods clamp out (no phantom rows); no base session is dropped; times fill from the matched slot. Gapped-slot raw-vs-contiguous encoding is disambiguated by period-value evidence, then by a structural `start_time` tie-break (manual timetables store empty times → raw; generators carry times → contiguous). One shared FE transform (`frontend/src/utils/parentScheduleGrid.js`) now feeds both `SchedulePanel.jsx` and `ChildSchedulePage.jsx`. Validated by 11 unit tests + live-DB run against the real buggy school. `today-live` left out of scope by design.
- **IT Phase-2 surface (recent line of work):** full workspace lifecycle, bulk import, parent invitations, personal calendar, lesson planner, co-teaching collaborators, manual schedule editor with optimistic concurrency, analytics/exports, platform purge. Per-route detail in `docs/it-phase2-reference.md`.
- **Ongoing security hardening:** the bulk of `threat_model.md` scan anchors (tenant-context overrides, role-switch paths, credential minting, parent linkage, IT public token flows, export injection).
- **Scheduling/grading correctness:** participation running-clamp, follow-up sheet serialized persistence, canonical stage/grade unification (real + IT), teacher timetable period labels, hard-constraint slot-period resolution.

---

## 8. Intentional Denials (by design — NOT bugs)

| Denial | Why | Where |
|---|---|---|
| Student portal frontend access | Product decision; `/student/*` redirects to `/login` | `frontend/src/components/guards/RouteGuards.js` |
| IT users cannot access another workspace | Synthetic-tenant isolation; only `workspace_collaborators` for one shared class | `auth_scope.py`, `utils/collab_access.py` |
| By-id cross-workspace reads return 404 (not 403/200) | Don't confirm existence of foreign rows | `tenant_scoped_assert_one`, §8 inv. 3 |
| Homework follow-up cell toggle-locked | Intentional grading semantics | follow-up sheet logic |
| Standby periods empty when `weekly_periods` ≤ 0 | Engine excludes by design (config, not bug) | standby engine |
| Old scheduling system | Hard user preference — must not be reintroduced | `replit.md` |
| Seed scripts in prod/staging | Blocked; skipped if DB has data | deployment guards |
| Destructive DB ops (drop/delete/rename/truncate) in non-dev | Blocked; Alembic-only schema | deployment safety |
| Native `alert()`/`confirm()`/`toast.error()` for critical UX | Must use `NassaqAlertDialog` | UI policy |
| `Intl.DateTimeFormat('ar-SA-u-ca-islamic')` for Hijri | Forbidden; use `hijri-converter` | `utils/hijriDate.js` |
| Hard-delete of IT workspace from IT API | Platform-admin out-of-band only | lifecycle routes |
| Landing-page deviations from `design_guidelines.json` | Intentional marketing-funnel overrides | `LandingPage.jsx` |

---

## 9. Architectural Invariants (must NOT break casually)

1. **Tenant scope is `tenant_id ⇄ school_id`, enforced at query level.** Never trust client-supplied tenant/role/user/relationship ids. Never widen `TenantIsolation`; widen at the callsite only for the §6.7 co-teaching `class_id`.
2. **By-id IT-reachable reads MUST 404 (never 403/200) cross-workspace.**
3. **Schema is Alembic-only**; no `create_all`/`drop_all`; prod boots only at head; destructive ops blocked outside dev.
4. **IT write/export step-up = HTTP 403 envelope.** Bare `require_recent_mfa` (401) on shared routes is forbidden (FE treats 401 as hard logout).
5. **Session revocation kills the access token AND the refresh family.** Authorization-changing flows invalidate stale real-time + switched sessions promptly.
6. **Canonical stage/grade system** is the single source for class/student create+edit (real + IT); `grade_id` authoritative; fail-closed.
7. **Scheduling resolves via `_resolve_teacher_sessions`** over modern `timetables`+`timetable_sessions`; never inline; never reintroduce the old system; gap-filler respects `weekly_periods`.
8. **Every CSV/XLSX writer neutralizes formula injection** (`=+-@` + xlsxwriter `strings_to_formulas/urls=False`); keep the shared + IT writers in sync.
9. **All follow-up sheet writes go through the one serialized flush** with per-key dirty+revision; never clobber unsaved edits on the merge poll.
10. **AI clients pass the gateway `base_url`** and respect the gpt-5-mini token-budget contract.
11. **UI policy invariants:** `NassaqAlertDialog`, `hijri-converter`, RTL logical props, brand tokens (no raw hex), lucide icons (no emoji), no text gradients, no `console.log` in pages/contexts, safe Arabic API errors.

---

## 10. Spec ↔ Code Drift Notes

- **`schedule_sessions.version`** is the IT manual-editor optimistic-concurrency token (spec 2026-05-12 §5.4); **real-school schedule write paths ignore it**.
- **`entity_kind`** appears in responses as a **computed property**, not a column — older references implying a column are stale; filter by `school_type/tenant_type == 'independent_teacher'`.
- **Legacy `schedules` collection** is empty; modern schools live in `timetables`+`timetable_sessions`. Specs referencing `schedules`/`timetable_sessions` as tables are describing GenericDocument collections.
- **`homework_mode`** is persisted by the route but ignored by the engine (only `homework_enabled` is honored) — spec intent vs current behavior diverge; out of scope until prioritized.
- **Frontend toolchain:** stays on CRA + `react-scripts` 5.0.1 with `webpack-dev-server` pinned EXACT and a v4→v5 shim (`craco.config.js`); decision and safe-upgrade procedure in `docs/frontend-toolchain.md`. Do not loosen the pin or migrate to Vite without sign-off.

---

## 11. Model Handover Notes (operational instructions for future AI agents)

When analyzing this platform or generating code/reports/tickets:

1. **Start investigations at the right anchor.** For security/authorization: read `threat_model.md` Scan Anchors first. For IT workspace code: read `docs/it-phase2-reference.md` first. For scheduling/grading/parent quirks: read `.agents/memory/` topic files first.
2. **Trust current code over older specs**, and state the drift (see §10) rather than assuming the spec is reality.
3. **Never weaken tenant isolation.** Verify by-id reads 404 cross-workspace; never broaden `TenantIsolation`; honor `resolve_school_id`.
4. **Respect the MFA envelope split:** 403 step-up on IT/shared write paths; 401 means hard logout to the FE.
5. **Schema changes are Alembic-only**, applied via build phase, gated at boot. The dev "Backend API" workflow is **production on the real prod DB** — dry-run migrations, restart after backend edits (no `--reload`), and never run destructive ops or seeds.
6. **Validate backend changes with `pytest` manually** (the `runTest` subagent is disabled). For prod-data-only flows (e.g. the parent grid bug), validate via unit tests plus a script that runs the real resolver against the live DB (`async_session_factory`; `import dependencies` FIRST to avoid the engines↔dependencies circular import).
7. **QA with `TEST_CREDENTIALS.md` only**; never paste/leak those creds anywhere (logs, code, screenshots, docs). Note: seed creds do **not** authenticate against the prod DB this workspace uses — rely on unit tests + live-DB scripts for prod-only data.
8. **Honor UI/UX invariants** (§3.6, §9.11) and the **landing-page intentional overrides** — don't "fix" them back to the in-app spec.
9. **Distinguish denial from defect** (§8). Do not file the student portal, homework toggle-lock, empty standby periods, or by-id 404s as bugs.
10. **Don't reintroduce the old scheduling system, don't loosen the webpack-dev-server pin, don't change stable scheduling/standby/grading logic without explicit sign-off**, and keep both export writers' formula-injection neutralization in sync.
11. **Ask before major/destructive/architectural changes** (user preference): iterative milestones, simple/direct language, detailed explanations for complex changes.

---

### Quick-answer index (acceptance criteria)
- **Stable today:** auth/session/MFA, tenant isolation, smart scheduling + master grid, attendance, assessments + follow-up, behavior, communication + WS, parent portal, reporting/exports, classes/students CRUD, calendar, Hakim AI, full IT Phase-2 surface.
- **Who can do what:** see §2 Role Matrix + §4 deep-dive.
- **Tenant-scoped vs global:** everything school-role is own-tenant; only platform-admin is global (via hardened impersonation); IT is `itw_` synthetic-tenant scoped.
- **Known issues needing caution:** §6 (security anchors, correctness caveats, perf, infra).
- **Intentionally blocked:** §8.
- **Latest completed work:** §7 (parent grid normalization; IT Phase-2; security hardening).
- **Where to start a new investigation:** §11.1.
- **Never change casually:** §9 invariants + §11.10.
