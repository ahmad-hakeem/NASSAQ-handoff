# NASSAQ — Platform Status Report

**Date:** 2026-05-12
**Mode:** Investigation only — no production code changed during this audit.
**Sources of truth:** Live codebase under `backend/` and `frontend/`, plus `replit.md`, `threat_model.md`, `docs/specs/2026-05-12-independent-teacher-phased-spec.md`, `docs/audits/2026-05-11-independent-teacher-architecture-audit.md`, `docs/superpowers/specs/2026-05-03-hakeem-engine-audit-report.md`.
**Convention used in this report:** Every claim cites `file:line`. Status legend: **Stable** = production-grade and verified, **Partial** = working with known scope gaps, **Risky** = working but with concrete defect/risk, **Spec-only** = documented but not in code, **Blocked** = depends on other work.

---

## 1. Executive Status Snapshot

**Healthy and safe to build on:**
- Auth / session / refresh-rotation / family revocation (`auth_routes_mod.py:154,513`).
- MFA factor stack (passkey, TOTP, email-OTP, recovery codes) plus the canonical step-up envelope and the frontend axios interceptor that auto-replays (`mfa_routes.py`, `dependencies.py:420`, `frontend/src/contexts/AuthContext.js:188`).
- Role-switch / impersonation with 15-minute hard TTL and DB-anchored restore (`auth_routes_mod.py:1390,1524`).
- Backend-sourced permission catalog (`GET /auth/me/permissions`) consumed by the frontend after Task #178 (`AuthContext.js:739`).
- Canonical tenant resolver `auth_scope.require_request_school_id` (`auth_scope.py:69-82`) used consistently; tenant isolation supports synthetic `itw_{user_id}` (`middleware/tenant_isolation.py:41-52`).
- Independent Teacher Phase 1 §5.1–§5.8 — bootstrap, classes, students, schedule editor, settings, communication cohort, Invite Parent, account settings — all merged with focused tests.
- Login state-machine / success-error race fix (`pages/LoginPage.jsx:45,122,197`).
- Alembic-only schema discipline (35 linear migrations, latest `z1a2b3c4d5e6`); no `Base.metadata.create_all()` anywhere; destructive ops blocked outside dev (`config.py:91`).

**Actively in-flight:**
- Tasks **#201** (MFA step-up backfill on remaining §5.7 surfaces) and **#202** (§5.9 exit-criteria suite) — proposed today.
- Active Drafts: #152, #153, #155, #158, #159, #169, #170, #171, #175, #179, #180, #184, #185, #186, #187, #190, #191, #196, #197.

**Unstable / known risky:**
- **N+1 on `GET /assessments`** — 4 lookups per row in a loop (`assessment_routes_mod.py:257-293`). At 100 assessments this is ~400 round-trips. Highest-impact perf hotspot found.
- **Optimistic concurrency gap on principal manual schedule edits** — IT path uses `schedule_sessions.version`, principal path does not (`scheduling_smart_session_routes.py`).
- **Smart-engine progress UX** is timer-simulated (`HAKIM_STAGES`) rather than reading the real `TimetableRunStatus` rows the engine already writes (`SchedulePageNew.jsx:308`, `smart_scheduling_engine.py:138`).
- **`PUT /users/me/profile`, `GET /export/report`, `GET /export/attendance`, `GET /independent-teacher/schedule/export.pdf`, `PUT /students/{id}`, `DELETE /parents/{id}`** still lack `require_recent_mfa` for IT callers — addressed by Task #201.
- **Frontend Arabic-warnings discipline drift** — `window.confirm()` / `toast.error()` for important warnings remain in `SystemMonitoringPage.jsx`, `UsersManagement.jsx`, `ProductHubSubmitPage.jsx`, `SchedulePageNew.jsx`, `AccountSettingsPage.jsx`. `NassaqAlertDialog` is the standard per `replit.md` and is under-adopted.
- **`students` ↔ `users` link via email** is fragile when guardians share a household email — flagged as a known design risk for the parent/student portal.
- **Stray tracked file `sed8mSlHn`** at the repo root is a duplicate of `.replit` (no real secrets, but should not be in git — repository hygiene only).

**Product priority alignment.** Principal Grid Matrix improvements remain the active product track; Independent Teacher is a parallel track that has now reached a defensible Phase-1 close. This report does **not** recommend reverting to the old timetable page.

---

## 2. Architecture Overview (verified)

| Layer | Reality | Source |
|---|---|---|
| Backend | FastAPI + SQLAlchemy 2.0 (`AsyncSession`) on PostgreSQL. Pydantic schemas in `backend/shared_models.py`. | `backend/server.py`, `backend/app/routes.py` |
| ORM / migrations | Alembic-only (`backend/alembic/versions/` — 35 files, linear). No `metadata.create_all()` in `server.py`. Latest `z1a2b3c4d5e6_students_pending_parent_columns.py`. | verified |
| Frontend | React (CRACO) + Tailwind + Radix UI + `@dnd-kit` + `react-router-dom` + `recharts` + `framer-motion`. Centralized API client at `frontend/src/services/apiClient.js`. | `frontend/package.json`, `replit.md` |
| Auth | Pure JWT (access + refresh) with server-side `revoked_tokens` JTI checks and `revoked_token_families` for rotation reuse. `user_sessions` is a best-effort registry. | `auth_routes_mod.py:154,513`, `dependencies.py:250` |
| Tenancy | `tenant_id` resolved via canonical `auth_scope.require_request_school_id`; synthetic `itw_{user_id}` is a first-class tenant. | `auth_scope.py:69-82`, `middleware/tenant_isolation.py:37-52` |
| RBAC | Backend-sourced permission catalog served from `GET /auth/me/permissions`; route guards via `require_roles(...)`. | `dependencies.py:91-112`, `AuthContext.js:739` |
| AI | OpenAI SDK via `python_openai_ai_integrations` integration. Model `gpt-4o-mini` hardcoded in `ai_routes_mod.py:361` and `services/hakim_llm_service.py:49`. Prompt sanitiser via `_sanitize_literal` / `_quote`. | `ai_routes_mod.py:35`, `services/hakim_llm_service.py:423,487` |
| Localisation | `frontend/src/i18n/{ar,en}.json`. Hijri conversion via `frontend/src/utils/hijriDate.js` (NOT `Intl.DateTimeFormat('ar-SA-u-ca-islamic')`, per `replit.md` rule). | verified |

Required env vars per `replit.md` are honored: `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `MFA_ENCRYPTION_KEY` — all read via `os.environ.get` in `backend/config.py` and `backend/dependencies.py`.

---

## 3. Major Product Areas — Status Table

| Area | Status | Backend Touchpoints | Frontend Touchpoints | Tenancy / RBAC | Main Risks | Next Safe Action |
|---|---|---|---|---|---|---|
| Auth / login / session | **Stable** | `auth_routes_mod.py:154,513`, `dependencies.py:229,250`, `settings_routes.py` | `pages/LoginPage.jsx`, `contexts/AuthContext.js:360` | JWT + JTI revocation; family revocation on rotation reuse | Best-effort `_record_session_from_token`; background-task audit-log loss on abrupt shutdown | Add E2E test for post-login redirect (Drafts #196/#197) |
| MFA + step-up | **Stable** | `mfa_routes.py`, `services/mfa_policy.py`, `dependencies.py:420` | `AuthContext.js:165,188`, `components/mfa/MfaStepUpDialog.jsx` | Per-tier policy (A/B/C); 5-min freshness | Three §5.7 surfaces still missing `require_recent_mfa` (Task #201) | Land #201, then #202 |
| Role switching / impersonation | **Stable** | `auth_routes_mod.py:1390,1524`; `impersonation_sessions` table | `AuthContext.js:87`, `Sidebar.jsx` | 15-min TTL; restore from DB row, not token claim | Window of theft = 15 min (acceptable) | None |
| Frontend route guards | **Stable** | `dependencies.py:91-112` (catalog source) | `routes/appRoutes.js:160`, `components/guards/RouteGuards.js:22`, `AuthContext.js:739` | Backend remains authority | Some hardcoded role checks (`isSchoolPrincipal`) still in `AuthContext.js` — cosmetic, backend enforces | Optional: replace bool helpers with capability lookups |
| Tenancy resolution | **Stable** | `auth_scope.py:69-82`, `middleware/tenant_isolation.py:37-52` | n/a | `itw_*` first-class everywhere | WebSocket route inherits `require_workspace_materialised` and the previously-noted TypeError (see §5) | Land the WS TypeError fix as part of #202 sweep or a 1-line ticket |
| Principal Grid Matrix (timetable) | **Partial** | `schedule_master_grid_routes.py:398`, `scheduling_smart_engine_routes.py:121`, `scheduling_smart_session_routes.py:148,538`, `engines/smart_scheduling_engine.py:138` | `pages/SchedulePageNew.jsx:1,205,308,446,482,1134,1142`, `components/schedule/{FilledCell,MasterMatrixDnd,SessionEditDrawer}.jsx`, `config/scheduleConfig.js:18` | `_full_tenant_dep` on writes | (a) No `expected_version` on principal manual edits; (b) timer-simulated progress; (c) `limit=10000` payload at 200 teachers; (d) N+1 in `get_active_timetable_sessions:509` | Wire structured progress + version concurrency in a focused ticket |
| Independent Teacher schedule editor | **Stable** | `independent_teacher_schedule_routes.py:207,341,374,517` | `pages/TeacherModule/WorkspaceSchedulePage.jsx` | `itw_{user_id}`; uses `schedule_sessions.version` | None known | None |
| Hakim assistant | **Stable** | `ai_routes_mod.py` (`/hakim/chat`, `/hakim/contextual-message:296`), `services/hakim_llm_service.py:49,423,487` | `components/hakim/HakimAssistant.jsx:233,451`, `HakeemPlan.jsx:359` | Per-route `school_id` scoping | No streaming; rate-limit is process-local (`middleware/rate_limiter.py:75`) | Plan tenant-aware per-user quota when ready |
| AI Insights | **Stable** | `ai_routes_mod.py:410-436` (`_resolve_parent_linked_children`), `tests/test_ai_insights_security.py` | `pages/AIInsightsPage.jsx` | `school_id` + `guardian_links` filter | Page still uses full-page spinner | Skeleton swap |
| Hakeem Plans | **Stable, IT-denied** | `hakeem_plan_routes_mod.py` mounted with `_full_tenant_dep` (`app/routes.py:154`) | `components/hakeem/HakeemPlan.jsx:195,359` | 403 for IT (tested) | None | None |
| Communication / notifications | **Stable** | `notification_routes_mod.py:213-250,252,356,397,429`, `communication_routes.py:438,153-264`, `independent_teacher_communication_routes.py:112,151,256`, `routes/websocket_routes.py:139,73,225` | `pages/TeacherModule/{TeacherCommunicationPage,IndependentTeacherCommunicationPage}.jsx`, `pages/ParentPortal/*` | Cohort enforcement for IT (Task #198); broadcast IT-denied | None critical | Audit Drafts #152/#153/#179/#180 for closure |
| Parent portal | **Stable** | `parent_portal_routes.py:244,247,256,269,287,326,387,445` | `pages/ParentPortal/ParentPortalDashboard.jsx` | `_verify_parent_access` (`guardian_links` preferred, `parents.student_ids` then `students.parent_id` fallback) | Triple-fallback link path is hard to reason about; legacy `parent_id` still load-bearing | Plan eventual sunset of `students.parent_id` fallback |
| Student portal | **Risky** | `student_portal_routes.py:41` | `pages/StudentPortal/StudentPortalDashboard.jsx:84` | Email-based student↔user link | Email collisions: students sharing a household email could resolve wrong record | Track as Phase-2 work; safe today only because email uniqueness happens to hold per tenant |
| Classes (CRUD) | **Stable** | `academics_class_routes.py:51,160,202,278,341,377` | `pages/UsersClassesManagement.jsx`, `pages/ClassDetailPage.jsx` | `tenant_id` / `itw_*` | Mass delete cascades across 12 tables (`academics_class_routes.py:397-417`) — UI warning likely understates blast radius | Add typed-name confirm token on class delete |
| Students (CRUD) | **Stable** | `academics_student_routes.py:52,120,342,373,493`, `student_creation_routes.py:700`, `pg_models.py:212-213`, migration `z1a2b3c4d5e6` | `pages/StudentsPage.jsx`, `pages/StudentProfilePage.jsx` | Cross-tenant by-id returns 404 | `PUT /students/{id}` lacks IT MFA (Task #201) | #201 |
| Attendance | **Stable** | `attendance_routes_mod.py:122,261,286-340,391,421,459,471,579` | `pages/Attendance*.jsx` | `tenant_id` / `itw_*`; `require_can_view_student_sync_check` on by-student | `limit=10000` on date-range list (payload bloat); bulk path sends notifications in a Python loop | Page the date-range query when periods exceed N |
| Assessments + grades | **Risky (perf)** | `assessment_routes_mod.py:150,225,257-293,297,400` | `pages/Assessments*.jsx` | Role gating includes `independent_teacher` (Task #194) | **Severe N+1 on `GET /assessments`** | Bulk-fetch the per-row enrichments (single `WHERE id IN`) |
| Behaviour records | **Partial** | `behaviour_routes_mod.py:205,269,297,337,424,436` | `pages/Behaviour*.jsx` | `tenant_id` / `itw_*` | Hardcoded 48-hour edit window blocks legitimate corrections | Make window configurable per school |
| Teacher portfolio | **Stable** | `portfolio_routes_mod.py:67` | `pages/TeacherModule/TeacherAchievementsPage.jsx` | `tenant_id` | None known | None |
| Subjects | **Stable** | `academics_subject_routes.py:217,230-272` | (inline within class wizard) | `tenant_id` / system reference fallback | None | Optional Draft #190 (IT-managed subjects) — defer |
| Reporting / exports | **Risky** | `reporting_routes_mod.py:42,87,137,546,621,639`, `engines/export_engine.py:184`, `independent_teacher_schedule_routes.py:341` | (download triggers in many pages) | Mostly principal/admin; some IT-reachable | Synchronous file generation + `limit=100000` on raw queries → DoS pressure under load; no IT MFA on the IT-reachable subset | #201 covers MFA; queue exports as later perf work |
| School settings (full) | **Stable** | `school_settings_routes.py`, `school_settings_mod.py` | `pages/SchoolSettingsPagePro.jsx` | Principal/admin only | `replit.md` historical notes (`PRINCIPAL_AUDIT_APRIL_2026.md`) suggest legacy clutter | None pressing |
| IT workspace settings | **Stable** | `independent_teacher_workspace_settings_routes.py` | `pages/TeacherModule/WorkspaceSettingsPage.jsx` | `itw_{user_id}` only | None | None |
| Account settings (personal) | **Stable** | `user_routes_mod.py:621,933` (canonical `PUT /users/me/profile`); `auth_routes_mod.py:1124` (`change-password` — has MFA); `settings_routes.py` (sessions — has MFA); plus Task #200 IT sections | `pages/AccountSettingsPage.jsx:218,553` | own-user only | `PUT /users/me/profile` lacks `require_recent_mfa`; `window.location.reload()` after role switch (acceptable trade-off) | #201 |
| Onboarding (IT) | **Stable** | `independent_teacher_bootstrap_routes.py:241,269` | `pages/IndependentTeacherOnboardingWizard.jsx` | bootstrap is atomic + idempotent | Drafts #186/#187 (recovery screen + failure-mode tests) still meaningful | Pull #186/#187 into the next IT slice |
| Onboarding (Principal) | **Partial** | `school_routes_mod.py:post_create_school` | `CreateSchoolWizard.jsx` | `tenant_id` | No formal "finish setup" recovery if wizard interrupted | Mirror the IT recovery screen pattern when revisiting |
| Calendar / events | **Stable** | `calendar_routes_mod.py:127,218` (`/v1/calendar`) | `components/dashboard/AdminCalendar.jsx` | `_resolve_tenant`; CRUD has no extra role gating beyond `get_current_user` | Activities/calendar routes lean on `get_current_user`+tenant alone; consider explicit role guards for write paths | Small RBAC tightening ticket |

---

## 4. Timetable Deep Dive (priority track)

**Old path.** A legacy manual-edit page existed (`TeacherScheduleGrid.jsx` and friends) but is no longer mounted in `appRoutes.js`. Backend routes such as `scheduling_smart_session_routes.py` were repurposed to serve the new edit drawer rather than removed. **No revert recommended.**

**New Grid Matrix.**
- Page: `frontend/src/pages/SchedulePageNew.jsx:1,205,308,446,482` (sticky band, `HakimInsightsBanner` chip-collapsed alerts/insights, no pager UI — matches the 2026-05-06 redesign).
- Cells: `frontend/src/components/schedule/FilledCell.jsx`.
- Drag/drop: `frontend/src/components/schedule/MasterMatrixDnd.jsx` (`DraggableSession`, `DroppableSlot`).
- Edit drawer: `frontend/src/components/schedule/SessionEditDrawer.jsx:333` (conflict surface + "Save Anyway" via `/force` at `scheduling_smart_session_routes.py:268`).
- Window size: `MASTER_GRID_TEACHER_WINDOW = 200` in `frontend/src/config/scheduleConfig.js:18`.
- Backend grid feed: `schedule_master_grid_routes.py:398,486` (`limit=10000`).
- Backend writes (move/swap/edit/delete): `scheduling_smart_session_routes.py:148,538`.
- Smart engine entrypoint: `scheduling_smart_engine_routes.py:121` → `engines/smart_scheduling_engine.py:138` (`TimetableRunStatus` with `VALIDATING / GENERATING / OPTIMIZING`).

**Manual editing.** Present and usable on **draft** timetables (drag-drop + click-to-edit + force-save). Soft conflict resolution shows server conflicts and lets the user override. **What is missing on the principal path:** optimistic concurrency (the IT path already uses `schedule_sessions.version`; principal does not).

**Generation progress UX is vague.** Frontend simulates `HAKIM_STAGES` with `minMs` (`SchedulePageNew.jsx:308`) instead of subscribing to the real `TimetableRunStatus` rows. Long jobs can appear stuck.

**Independent Teacher schedule.** Entirely separate path — different page, different routes, different model rows; do not conflate.

**Top concrete risks (in priority order):**
1. Last-write-wins on principal manual edits (no `expected_version`).
2. Vague generation progress (timer-simulated rather than DB-truth).
3. N+1 in `scheduling_smart_session_routes.py:509` (`get_active_timetable_sessions` looks up teacher/class names per row).
4. Master-grid response can be 10,000+ rows for a 200-teacher week.

---

## 5. Security / Tenancy / Authorization Audit

**Canonical resolver.** `auth_scope.require_request_school_id` (`auth_scope.py:69-82`) is the single source of truth. `middleware/tenant_isolation.py:37-52` delegates to `auth_scope.independent_workspace_id` to avoid duplicate naming logic. Resolution order: explicit `tenant_id` → synthetic `itw_{user_id}` for ITs.

**Synthetic tenant first-class.** `itw_*` is enumerated in `TENANT_SCOPED_COLLECTIONS` (`middleware/tenant_isolation.py:291`); no UUID-only assertions in the hot path were found.

**Backend authorization is the boundary.** Frontend guards (`appRoutes.js:160`, `RouteGuards.js:22`) never extend permission; backend `require_roles` and `require_full_school_tenant` always re-check.

**Cross-tenant leak hotspots — current posture:**
- Communication — **enforced** via `_resolve_caller_workspace` (`communication_routes.py:17-31`); IT cohorts re-validated at send (`notification_routes_mod.py:213-250`).
- AI Insights — **enforced** (`ai_routes_mod.py:410-436`); `tests/test_ai_insights_security.py` is the canonical pattern.
- Schedule — **enforced** for IT; principal path scoped by `_full_tenant_dep`.
- Parent Portal — **enforced** via `_verify_parent_access:244` with the legacy fallback chain noted above.
- Reporting / export — **mixed**: most routes pull `tenant_id` from `current_user`; a few fall back to `independent_workspace_id` (`reporting_routes_mod.py:95`). No leak found, but coverage tests are thin.
- Monitoring — `monitoring_routes.py` intentionally bypasses tenant scoping for health checks; verify no per-tenant data is exposed.

**Deny-by-default gaps.** Routes in `backend/routes/activities_routes_mod.py` and `backend/routes/consent_privacy_routes_mod.py` use `Depends(get_current_user)` only — no `require_role` and no `require_full_school_tenant`. Risk is contained today by tenant-aware queries downstream, but explicit role guards on writes are advisable.

**WebSocket auth.** `routes/websocket_routes.py:139,178` decodes the JWT and registers the connection by `tenant_id` (lines 186, 204) and JTI (revocation re-check every 30s at line 225). The previously-observed `require_workspace_materialised() missing 1 required positional argument: 'request'` originates from the `api_router` global dependency at `app/routes.py:297` (designed for HTTP `Request`) being inherited into the WS route — a one-line decorator-scope fix.

**Step-up gaps (input to Task #201):**
- `PUT /users/me/profile` — `user_routes_mod.py:933`.
- `GET /export/report/{report_type}` — `reporting_routes_mod.py:546`.
- `GET /export/attendance` (IT-reachable via `teacher` allow-list) — `reporting_routes_mod.py:639`.
- `GET /independent-teacher/schedule/export.pdf` — `independent_teacher_schedule_routes.py:341`.
- `PUT /students/{student_id}` (when caller is IT) — `academics_student_routes.py:373`.
- `DELETE /parents/{parent_id}` (when caller is IT) — `academics_teacher_routes.py:897`.

**Already enforced (correct):** `POST /auth/change-password`, `POST /independent-teacher/students/{id}/invite-parent`, `PATCH /independent-teacher/students/{id}/pending-parent`, session revocation under `settings_routes.py`.

---

## 6. Independent Teacher — Reality vs Spec (Phase 1 Appendix A)

| Ticket | Spec § | Reality | Evidence |
|---|---|---|---|
| IT-P0-1..6 | §4 groundwork | **Working** | Tasks #176–#178 merged |
| IT-P1-1/2 Bootstrap | §5.1 | **Working** | `independent_teacher_bootstrap_routes.py:241`, `test_independent_teacher_bootstrap.py:108` |
| IT-P1-3 Workspace Settings | §5.2 | **Working** | `independent_teacher_workspace_settings_routes.py`, `WorkspaceSettingsPage.jsx` |
| IT-P1-4 Classes create | §5.3 | **Working** | `academics_class_routes.py:51`, `enforce_class_quota` |
| IT-P1-5 Students create | §5.3 | **Working** | `academics_student_routes.py:52`, `pg_models.py:212-213`, trigger in `z1a2b3c4d5e6` |
| IT-P1-6 Schedule editor | §5.4 | **Working** | `independent_teacher_schedule_routes.py:207,374,517` (uses `schedule_sessions.version`) |
| IT-P1-7 Assessments smoke | §5.5 | **Working** | `test_independent_teacher_phase1_smoke.py`, `Permission.ASSESSMENTS_EDIT` granted |
| IT-P1-8 Notifications cohort | §5.6 | **Working** | `notification_routes_mod.py:213-250`, `independent_teacher_communication_routes.py:112,151` |
| IT-P1-9 Invite Parent | §5.6 | **Working** | `independent_teacher_invite_parent_routes.py:240,400`, atomic + step-up + 403 envelope |
| **IT-P1-10 MFA on §5.7** | §5.7 | **Partial** — gaps listed above | Task **#201** addresses |
| IT-P1-11 Account Settings | §5.8 | **Working** | Task #200 merged; `AccountSettingsPage.jsx` IT sections + sub-brand |
| **IT-P1-12 Exit-criteria suite** | §5.9 | **Spec-only** | Task **#202** addresses |

**Architecture choice confirmed.** Synthetic `itw_{user_id}` self-tenant model is what is in code (`auth_scope.py:53-66`). There is no separate `workspaces` table.

**Phase 1 remaining work:** Tasks #201 then #202. Phase 2 (§6.1–§6.8 — bulk import, calendar authoring, AI lesson planner, plans/quotas, public profile, co-teaching, export & soft-delete) is not yet started and remains a later track per current product priority.

---

## 7. Frontend UX / State Quality

**Full-page spinners that should be skeletons.** `RouteGuards.js:25,45` (acceptable for the auth boot), `AIInsightsPage`, `ProductHubIssuePage`, `ParentDashboard`, `ClassDetailPage`, `AdminDashboard`, `AcademicStructurePage`. `StudentProfilePage` and `TeacherClassAssignmentPage` already do skeletons — use as the reference pattern.

**Unnecessary refreshes / shell remounts.**
- `AccountSettingsPage.jsx:553` — `window.location.reload()` after role switch (necessary for state reset; acceptable).
- `ErrorBoundary.jsx:23` — `window.location.reload()` recovery (acceptable).
- `StudentPortal/StudentPortalDashboard.jsx:84` — manual refresh button (review).

**Login orchestration.** Task #195 fix is intact: `AuthContext.js:242` suppresses global 429/500 toasts on `/auth/login` and `/auth/me` to prevent double-firing with the inline banner; `AuthContext.js:417` maps backend codes to translated Arabic. `LoginPage.jsx:45,122,183,197` runs a formal state machine and clears local state on bootstrap failure. **Remaining gap:** post-bootstrap navigation state isn't persisted (Drafts #196/#197 — real outstanding work).

**`NassaqAlertDialog` violations.** `window.confirm()` in `SystemMonitoringPage.jsx`, `UsersManagement.jsx`. `toast.error()` for important warnings in `ProductHubSubmitPage.jsx`, `SchedulePageNew.jsx:1134,1142`, `SystemMonitoringPage.jsx`, `UserDetailsPage.jsx`, `AccountSettingsPage.jsx:218`.

**Optimistic-success without rollback.** `SchedulePageNew.jsx:1134,1142` fires `toast.success` before refresh confirms; if refresh fails the user sees inconsistent state.

---

## 8. Operational / Code Health

| Check | Status | Evidence |
|---|---|---|
| Alembic-only schema | ✓ | No `Base.metadata.create_all()` in `backend/`; 35 linear migrations |
| Destructive-op block in non-dev | ✓ | `config.py:91 destructive_ops_allowed()` returns `False` if `is_production()` |
| Secrets via env | ✓ | `MFA_ENCRYPTION_KEY`, `DATABASE_URL`, `SECRET_KEY` all `os.environ.get` |
| `console.log` in pages/contexts | ✓ clean | grep returns zero matches under `frontend/src/pages/` |
| `detail=str(e)` exception leakage | ✓ scrubbed | None found in user-facing handlers |
| Bare `except:` / silent `except Exception: pass` | One offender | `schedule_master_grid_routes.py:792` |
| Forbidden Hijri API | ✓ | `Intl.DateTimeFormat('ar-SA-u-ca-islamic')` not used; `frontend/src/utils/hijriDate.js` is the only path |
| Repository hygiene | ✗ | Stray tracked file `sed8mSlHn` at repo root is a duplicate of `.replit`; remove from git |

**Test coverage by domain (depth):**
| Domain | Files | Depth |
|---|---|---|
| Auth / MFA | `test_mfa.py`, `test_security_phase3.py` | Negative + integration |
| IT Workspace | `test_independent_teacher_{bootstrap,classes,schedule,students,workspace_settings,phase0,phase1_smoke,communication,invite_parent}.py` | Smoke + cross-tenant per-feature |
| Schedule | `test_master_grid_dynamic_periods.py`, `test_drag_drop_api.py` | Integration |
| AI / Hakim | `test_ai_insights_security.py`, `test_schedule_hakim.py` | Role-aware + negative |
| Tenancy | `test_communication_isolation.py`, `test_tenant_scope_helper.py` | Cross-tenant |

**N+1 / payload-bloat hotspots (top 5):**
1. `assessment_routes_mod.py:257-293` — 4 lookups per assessment (severe).
2. `scheduling_smart_session_routes.py:509` — name lookups inside the active-sessions loop.
3. `attendance_routes_mod.py:286-340` — bulk-record sends notifications in a Python loop (IO, not DB, but blocks the request).
4. `attendance_routes_mod.py:421` — `limit=10000` for date-range class attendance.
5. `schedule_master_grid_routes.py:486` — `limit=10000` master-grid payload at 200 teachers.

---

## 9. Top 20 Issues / Opportunities

| # | Title | Severity | Area | Files | Why it matters | Next action | Stack |
|---|---|---|---|---|---|---|---|
| 1 | MFA step-up missing on §5.7 surfaces (profile, exports, IT student/parent edits) | High | Auth / IT | `user_routes_mod.py:933`, `reporting_routes_mod.py:546,639`, `independent_teacher_schedule_routes.py:341`, `academics_student_routes.py:373`, `academics_teacher_routes.py:897` | Closes the only known §5.7 gap before declaring Phase-1 done | Land Task **#201** | Backend |
| 2 | Phase-1 §5.9 exit-criteria test suite | High | IT / Tests | `backend/tests/test_independent_teacher_*` (new module) | Single signal that Phase 1 is complete and stable | Land Task **#202** after #201 | Backend |
| 3 | Severe N+1 on `GET /assessments` | High | Academics / Perf | `assessment_routes_mod.py:257-293` | 100 rows ⇒ ~400 round-trips | Bulk-fetch enrichments via single `WHERE id IN` | Backend |
| 4 | Optimistic concurrency missing on principal manual schedule edits | High | Timetable | `scheduling_smart_session_routes.py:148,268,538` | Last-write-wins with multiple admins | Add `expected_version` (mirror IT path) | Backend + small FE wiring |
| 5 | Smart-engine progress is timer-simulated, not DB-truth | Medium | Timetable / UX | `SchedulePageNew.jsx:308`, `engines/smart_scheduling_engine.py:138` | UI appears stuck on long jobs | Surface `TimetableRunStatus` via polling or WS | Full-stack |
| 6 | `NassaqAlertDialog` discipline drift (`window.confirm`, `toast.error`) | Medium | UX / Brand | `SystemMonitoringPage.jsx`, `UsersManagement.jsx`, `SchedulePageNew.jsx:1134,1142`, `AccountSettingsPage.jsx:218`, `ProductHubSubmitPage.jsx`, `UserDetailsPage.jsx` | Brand and a11y consistency required by `replit.md` | Replace per page | Frontend |
| 7 | Mass class delete cascades 12 tables without typed-name confirm | Medium | Academics | `academics_class_routes.py:377,397-417` | High blast radius | Add typed-name confirm token + clearer dialog | Full-stack |
| 8 | Reporting/export endpoints generate files synchronously with `limit=100000` queries | Medium | Reporting / Perf | `reporting_routes_mod.py:42,87,137,546`, `engines/export_engine.py:184` | DoS pressure under load; long requests | Move to background job + paginate | Backend |
| 9 | WebSocket dependency TypeError from `require_workspace_materialised` | Medium | Tenancy | `routes/websocket_routes.py:139`, `app/routes.py:297` | Spam in logs; risk if a WS route silently 500s | Scope the dep to HTTP routes only | Backend (1-line) |
| 10 | Behaviour 48-hour edit window hardcoded | Medium | Behaviour / UX | `behaviour_routes_mod.py:205` | Locks teachers out of legitimate corrections | Per-school setting | Backend + small UI |
| 11 | Bare `except Exception: pass` swallows errors | Medium | Reliability | `schedule_master_grid_routes.py:792` | Hides real failures | Log with context + narrow exception type | Backend |
| 12 | Optimistic-success toasts before refresh in Grid Matrix | Medium | UX | `SchedulePageNew.jsx:1134,1142` | Inconsistent state on partial failure | Defer toast to post-refresh | Frontend |
| 13 | Activities/consent routes lack explicit role guards on writes | Medium | RBAC | `routes/activities_routes_mod.py`, `routes/consent_privacy_routes_mod.py` | Today contained by tenant scoping; defence-in-depth missing | Add `require_roles` on write paths | Backend |
| 14 | Student↔User link via email is collision-fragile | Medium (latent) | Portal | `routes/student_portal_routes.py:41`, `routes/independent_teacher_communication_routes.py:121` | Shared family emails could resolve wrong record | Plan `students.user_id` migration as Phase-2 work | Backend (later) |
| 15 | Parent portal triple-fallback link path (guardian_links → parents.student_ids → students.parent_id) | Medium | Portal | `parent_portal_routes.py:244,247,256,269` | Hard to reason about, blocks `students.parent_id` sunset | Plan migration to `guardian_links` only | Backend (later) |
| 16 | Hardcoded role helpers still in `AuthContext` | Low | RBAC / FE | `frontend/src/contexts/AuthContext.js` (`isSchoolPrincipal` etc.) | Cosmetic; backend re-checks. Easy to drift. | Replace with capability lookups | Frontend |
| 17 | Full-page spinners on data-heavy pages | Low | UX | `pages/AIInsightsPage.jsx`, `pages/ParentPortal/...`, `pages/ClassDetailPage.jsx` | Perceived performance | Adopt `StudentProfilePage` skeleton pattern | Frontend |
| 18 | Hakim rate limit is process-local | Low (cost) | AI / Infra | `middleware/rate_limiter.py:75` | Multi-worker deployment ⇒ effective limit × workers | Per-tenant counter in DB or Redis | Backend |
| 19 | Stray repo file `sed8mSlHn` (duplicate of `.replit`) tracked in git | Low | Hygiene | repo root | Repo cleanliness | Remove from git in a small chore | Repo |
| 20 | Stale Drafts cluttering the queue | Low | Project mgmt | Tasks #155, #169, #179, #184, #185 (and #190/#191 questionable) | Wastes scoping cycles | Retire or rewrite (see §11) | Project mgmt |

---

## 10. In-flight / Partial / Deprecated / Blocked

| Item | State | Notes |
|---|---|---|
| Task #201 — IT MFA step-up backfill | Active (just started) | Closes §5.7 gap |
| Task #202 — IT §5.9 exit-criteria suite | Queued, blocked by #201 | Phase-1 capstone |
| Drafts #196/#197 — post-login redirect persistence + E2E | Real, outstanding | Plan when login UX returns to top of stack |
| Drafts #186/#187 — IT bootstrap recovery screen + failure-mode tests | Real, outstanding | Pull into next IT slice |
| Drafts #152/#153 — parent-portal "new info" nudges + real-time push | Real, outstanding | Phase-2 communication track |
| Drafts #158/#159 — standby roster PDF + lock tests | Real, outstanding | Owned by standby work, separate from IT |
| Drafts #169/#170/#171 — security maturity (passkeys/JWKS/GDPR erasure) | Real, outstanding | Future security sprint |
| Drafts #175 — old account endpoints deprecation watch | Real, low | Telemetry-only |
| Draft #155 — AI Insights audit-first extension | **Likely obsolete** | Superseded by `auth_scope.py` consolidation + #154; recommend cancel |
| Draft #179 — IT safe messaging | **Obsolete** | Superseded by Tasks #198 + #177; recommend cancel |
| Draft #180 — IT scoping mistakes auto-detection tests | Folds into #202 | Recommend cancel + fold into #202 |
| Draft #184 — IT manual schedule editor | **Obsolete** | Superseded by Task #193; recommend cancel |
| Draft #185 — IT classes/students/subjects management | Mostly obsolete | Superseded by #188/#192; subjects piece overlaps #190 |
| Draft #190 — IT subject management | Real but defer | Out of Phase-1 spec; revisit in Phase-2 |
| Draft #191 — class-list empty state | Real, low | Polish ticket |
| Old `TeacherScheduleGrid.jsx`-style components | Deprecated | Not mounted; do not revert |

---

## 11. Recommended Work Order

**Immediate priority (1-2 weeks):**
1. Land Task **#201** (IT MFA step-up backfill).
2. Land Task **#202** (§5.9 exit-criteria suite); fold Draft #180 in here.
3. Retire stale Drafts: cancel #155, #179, #184; rewrite or cancel #185; defer #190/#191.

**Safe short-term work (this and next sprint), in order of value:**
4. Wire `expected_version` on the principal manual schedule edit path (mirror IT pattern).
5. Surface real `TimetableRunStatus` in the Grid Matrix progress UI.
6. Fix the assessments N+1 (`assessment_routes_mod.py:257-293`).
7. Lock down `NassaqAlertDialog` discipline on the six identified pages.
8. Fix the WebSocket `require_workspace_materialised` dependency-scope TypeError.
9. Add typed-name confirm token on class delete.
10. Skeleton swap on the four heaviest pages.

**Blocked / dependency-gated:**
- Phase-1 close (#202) is blocked by #201.
- Bootstrap recovery polish (Drafts #186/#187) blocks any further hardening of IT first-login UX.

**Later track:**
- Reporting/export → background-jobs migration.
- `students.user_id` link migration (sunset email-based linkage).
- `students.parent_id` sunset in favour of `guardian_links` only.
- Hakim per-tenant quota in Redis or DB.
- IT Phase 2 (§6.1–§6.8): bulk import, calendar authoring, AI lesson planner, plans/quotas, public profile, co-teaching, export & soft-delete — confirmed not in current product priority.
- Old security maturity track (Drafts #169/#170/#171).

---

## 12. Exact Files to Revisit First

Prioritised reading list for the next engineer or for any hand-off:

1. `backend/auth_scope.py` — canonical tenant resolver (§5.A).
2. `backend/middleware/tenant_isolation.py` — synthetic `itw_*` support and TENANT_SCOPED_COLLECTIONS.
3. `backend/dependencies.py` — `get_current_user`, `require_roles`, `require_recent_mfa`.
4. `backend/routes/auth_routes_mod.py` — login, refresh-rotation/family revocation, role switch/restore.
5. `backend/routes/independent_teacher_invite_parent_routes.py` — canonical 403 step-up envelope shape (model for #201).
6. `backend/routes/independent_teacher_bootstrap_routes.py` — atomic bootstrap pattern.
7. `backend/routes/independent_teacher_schedule_routes.py` — model for optimistic concurrency on the principal path.
8. `backend/routes/notification_routes_mod.py` and `backend/routes/independent_teacher_communication_routes.py` — cohort scoping for IT.
9. `backend/routes/scheduling_smart_session_routes.py` and `backend/engines/smart_scheduling_engine.py` — manual-edit and generation flow.
10. `backend/routes/assessment_routes_mod.py:225-300` — N+1 hotspot.
11. `backend/routes/reporting_routes_mod.py` and `backend/engines/export_engine.py` — synchronous export risks.
12. `backend/routes/websocket_routes.py` and `backend/app/routes.py:297` — WS dependency-scope TypeError.
13. `frontend/src/contexts/AuthContext.js` — login state, MFA bridge, post-login redirect.
14. `frontend/src/pages/LoginPage.jsx` — login state-machine.
15. `frontend/src/pages/SchedulePageNew.jsx` and `frontend/src/components/schedule/*` — Grid Matrix surface.
16. `frontend/src/pages/IndependentTeacherOnboardingWizard.jsx` and `frontend/src/pages/TeacherModule/*` — IT first-login + workspace pages.
17. `docs/specs/2026-05-12-independent-teacher-phased-spec.md` and `docs/audits/2026-05-11-independent-teacher-architecture-audit.md` — IT track ground truth.
18. `docs/superpowers/specs/2026-05-03-hakeem-engine-audit-report.md` — Hakim/Hakeem engine ground truth.
19. `replit.md` and `threat_model.md` — repo guardrails and security boundaries.

---

*End of report. No code was modified during this audit.*
