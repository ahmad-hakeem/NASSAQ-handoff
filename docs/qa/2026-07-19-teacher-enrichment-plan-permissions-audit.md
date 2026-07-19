# Teacher Permissions Audit — Risk Radar → Student Profile → Enrichment Plan (الخطة الثرائية)

**Date:** 2026-07-19
**Scope:** School Teacher (معلم) permissions across the AI Insights Risk Radar,
the student profile it deep-links to, and the enrichment/remedial plan surfaces
(generation, status updates, exports).
**Spec:** `attached_assets/Pasted-Perform-a-full-permissions-audit-for-the-School-Teacher_1784498174599.txt`

---

## 1. Documented permission model (after fixes)

| Surface | Route | Gate (after audit) | Teacher (معلم) |
|---|---|---|---|
| Risk Radar data | `GET /ai/insights/students-overview`, `at-risk-students`, `recommendations-ai` | `require_roles` — leadership trio (+ `platform_admin` on `recommendations-ai`); teacher radar scope resolved server-side via `resolve_ai_insights_scope` (assigned classes only) | Sees only own-class students |
| Student profile deep-link | `GET /students/{id}` + hakim per-student GETs (`risk`, `behaviour`, `grade-trend`, `longitudinal`, `improvement-plan`, `plan-history`) | `get_current_user` + tenant 404 + `can_view_student` object check | Read-only, relationship-gated |
| **Plan generation** | `POST /hakim/student/{id}/ai-plans` | `require_roles(school_admin, school_sub_admin, school_principal, independent_teacher)` + tenant 404 + `can_view_student` + audit log `ai_plans.generate` + rate limit 5/60s | **403 (fixed — was open to any related viewer incl. the student themself)** |
| Intervention creation | `POST /ai/insights/intervention` | leadership trio, audited (pre-existing, verified) | 403 |
| **Intervention status** | `PUT /hakim/interventions/{id}/status` | leadership trio **incl. `school_sub_admin` (fixed)** + audit log `intervention.status_change` **(added)** | 403 |
| **Plan exports** | `POST /export/student-plans/{id}` and `/pdf` | `require_roles` (same 4-role set) + `can_view_student` **(both added — was `get_current_user` only)** | **403 (fixed)** |
| Full-profile exports | `POST /export/student-full-profile/{id}` docx/pdf | `get_current_user` + tenant 404 + `can_view_student` **(added — same missing-object-check class)** | Allowed only for own students |
| Teacher plan dialog (FE) | `StudentProfileDialog` (teacher surfaces) | Read-only; generation button only on leadership `StudentProfilePage` (route-gated to the SCHOOL_ROLES trio in `frontend/src/routes/appRoutes.js`) | Read-only |

**Design rationale**
- Plan **generation** is a leadership action: it issues a live LLM call, persists
  a `plan_history` row attributed to the generator, and is exposed in the UI only
  on the leadership student profile page. `independent_teacher` is included as
  the sole admin of their workspace.
- `platform_admin` is deliberately **excluded** from generation/intervention
  writes — a previewing platform admin carries a switched school-role token
  (mirrors the tested `POST /ai/insights/intervention` contract).
- Reads (`improvement-plan`, `plan-history`, per-student hakim GETs) stay
  relationship-gated (`can_view_student`) — deterministic engine output, no LLM
  cost, and teachers legitimately need them for the read-only dialog.

## 2. Mismatches found and fixed

1. **`POST /hakim/student/{id}/ai-plans` had no role gate** — any authenticated
   user passing `can_view_student` (teachers, parents, even the student) could
   trigger paid LLM generation and persist plans. → 4-role gate + audit row +
   `POST`-only rate limit (`/api/hakim/student/` 5/60s in
   `backend/middleware/rate_limiter.py`).
2. **`plan_history.generated_by` was always NULL** — the route read
   `current_user["user_id"]`; the auth layer returns the key `id`. Attribution
   now works.
3. **`PUT /hakim/interventions/{id}/status` excluded `school_sub_admin`**
   although that role can create and list interventions → inconsistent
   leadership set. Also had **no audit logging** → `intervention.status_change`
   audit row added.
4. **Plan export routes (`/export/student-plans/{id}` docx+pdf) were
   tenant-only** — any same-tenant account could render a school-stamped
   official document for any student with caller-supplied content. → 4-role
   gate + `can_view_student`.
5. **Full-profile export routes (docx+pdf) lacked `can_view_student`** — same
   missing-object-check class (they render server-fetched student PII). →
   `can_view_student` added; role gate intentionally NOT added because the
   content is server-derived (no forgery vector) and related teachers/parents
   already read this data through existing per-student GETs.

## 3. Verified as already correct

- Risk Radar teacher scoping (`resolve_ai_insights_scope`) — teachers only see
  students of their assigned classes; leadership sees the whole tenant.
- Cross-tenant lookups on every audited by-id route return **404** (never
  403/200).
- `POST /ai/insights/intervention` — leadership-only and audited (locked by
  `tests/test_student_performance_rbac.py` and `tests/test_intervention_endpoint.py`).
- Teacher plan dialog is read-only; `management/StudentProfileDialog.jsx` is
  dead code (not routed).

## 4. Documented latent issues (NOT changed — out of scope)

- **Radar scope ⊋ `can_view_student` for `teacher_class_assignments`-only
  teachers**: the radar scope resolver unions `teacher_assignments` ∪
  `teacher_class_assignments`, while `can_view_student` recognises a narrower
  relationship set. A teacher linked *only* via `teacher_class_assignments`
  could see a student on the radar but 403 on the profile. Does not bite the
  currently seeded data; fixing it means widening `can_view_student`, which
  affects many routes — needs its own review. Do **not** widen
  `resolve_ai_insights_scope` as a "fix".
- **Pre-existing test failures in `tests/test_student_performance_rbac.py`**
  (reproduced in isolation, unrelated to this audit's diff):
  - `test_get_denied_student` / `test_post_denied_student` expect 403 but get
    **401** — the platform-wide `STUDENT_LOGIN_DISABLED` auth-boundary gate
    (`backend/dependencies.py`) now rejects student bearer tokens before any
    role gate. The newer contract is locked by
    `tests/test_session_management_assignments.py`; these two older asserts
    were never updated.
  - `test_get_denied_platform_admin` expects 403 on all three radar GETs but
    `GET /ai/insights/recommendations-ai` explicitly includes
    `UserRole.PLATFORM_ADMIN` in its gate (route comment says this is
    intentional, "L4") → 200. Route and test contradict each other; needs a
    product decision, not a drive-by fix.

## 5. Verification

- `backend/tests/test_enrichment_plan_permissions.py` — **18 passed** (role
  matrix for generation/exports/status incl. `independent_teacher`
  positive paths, cross-tenant 404s for both export formats, `generated_by`
  attribution, audit rows for `ai_plans.generate` and
  `intervention.status_change`).
- Sibling suites `test_student_performance_rbac.py`,
  `test_intervention_endpoint.py`, `test_hakim_longitudinal_route.py`:
  22 passed, 3 failed — all 3 failures reproduce on the pre-audit code
  (see §4).
