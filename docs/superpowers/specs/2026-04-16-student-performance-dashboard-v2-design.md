# Student Performance Analytics Dashboard — v2 Design Spec

**Date:** 2026-04-16
**Status:** Design approved — awaiting spec review
**Supersedes:** `attached_assets/2026-04-13-student-performance-dashboard-design_1776372609260.md`
**Revision driver:** Codebase drift — the v1 spec predates several endpoints and the production shape of Hakim AI engine.

---

## 0. Why this revision

The v1 spec (2026-04-13) assumed a greenfield build. Code audit on 2026-04-16 found:

1. `GET /ai/insights/at-risk-students`, `GET /ai/insights/recommendations`, and `GET /ai/insights/alerts` **already exist** in `backend/routes/ai_routes_mod.py`.
2. The existing at-risk endpoint uses its own ad-hoc risk formula that **does not** call `HakimAIEngine.analyze_student_risk`. Shipping v1 would create a third parallel risk-scoring path.
3. The v1 root-cause taxonomy (`homework / attendance / participation / exams`) does not match Hakim's real 4-factor breakdown (`attendance / participation / behaviour / academic`).
4. The v1 spec names `student_grades`; the collection in use is `grades`. Notification writes standardized on `create_notification_internal`, not the raw `NotificationEngine`.

v2 resolves the drift by **reusing and extending** existing endpoints, **unifying** risk scoring on Hakim, and **aligning** the taxonomy with the real engine.

---

## 1. Scope

### In scope
- New tab "تحليل أداء الطلاب" inside `AIInsightsPage.jsx` using Radix Tabs.
- Five visible sections: Executive Summary KPIs, Student Risk Map (scatter), Intervention List, Root-Cause Pie Chart, Hakim AI Recommendations.
- Three intervention actions: notify parent, create remedial plan, schedule follow-up.
- OpenAI-backed recommendation generation (Arabic).
- Manual refresh button; fetch on tab open.

### Out of scope
PDF/Excel export · WebSocket live updates · Parent/teacher views · Intervention history tracking · Cross-class comparisons · Push notifications on status change.

### Target roles
`school_admin`, `school_sub_admin`, `school_principal`. Platform admin excluded (not their workflow — they have separate platform-level AI endpoints).

See §10 for the full RBAC matrix and enforcement rules.

---

## 2. Brand compliance

Unchanged from v1. Brand Navy `#1C3D74`, Turquoise `#46C1BE`, Purple `#615090`, Black `#312E2F`, Gray `#EAECED`. Status colors: stable `#22c55e`, watch `#eab308`, risk `#ef4444`, excelling `#615090`. Fonts Cairo/Tajawal/IBM Plex Mono. Radius `12px`. Shadow `0 4px 20px -4px rgba(15,44,89,0.1)`. Full RTL.

---

## 3. Architecture overview

```
┌──────────────────────┐     ┌─────────────────────────────┐     ┌────────────────────┐
│   Frontend           │     │   Backend (ai_routes_mod)   │     │   Data layer       │
│                      │     │                             │     │                    │
│ AIInsightsPage       │     │ GET /ai/insights/           │     │ students           │
│  └─ Tabs             │─GET▸│     students-overview  ←NEW │─────│ attendance         │
│     └─ Student       │     │                             │     │ grades             │
│        Performance   │     │ GET /ai/insights/           │     │ behaviour_records  │
│        Dashboard     │─GET▸│     recommendations-ai ←NEW │─────│ session_attendance │
│                      │     │                             │     │ session_           │
│                      │     │ GET /ai/insights/           │     │   interactions     │
│                      │     │     at-risk-students        │     │                    │
│                      │     │     (refactored wrapper)    │     │                    │
│                      │     │                             │     │                    │
│                      │POST▸│ POST /ai/insights/          │     │ remedial_plans ←NEW│
│                      │     │      intervention ←NEW      │─────│ notifications      │
│                      │     │                             │     │                    │
│                      │     │ ┌─────────────────────────┐ │     │                    │
│                      │     │ │ HakimAIEngine           │ │     │                    │
│                      │     │ │  analyze_students_risk_ │ │     │                    │
│                      │     │ │  batch() ←NEW           │ │     │                    │
│                      │     │ └─────────────────────────┘ │     │                    │
│                      │     │                             │     │                    │
│                      │     │ ┌─────────────────────────┐ │     │                    │
│                      │     │ │ OpenAI (via existing    │ │     │                    │
│                      │     │ │ Hakim chat path)        │ │     │                    │
│                      │     │ └─────────────────────────┘ │     │                    │
└──────────────────────┘     └─────────────────────────────┘     └────────────────────┘
```

---

## 4. Backend

### 4.1 `GET /ai/insights/students-overview` (NEW, primary)

Single payload powering KPIs, scatter map, intervention list, and root-cause chart.

**Auth:** admin roles (`school_admin`, `school_sub_admin`, `school_principal`).
**Scope:** strictly `tenant_id` from current user.
**Cache:** in-memory TTL 5 min, keyed by `school_id`.
**Cap:** 500 students. If a school has more, select the 500 with the lowest risk_score (most at-risk first) using a cheap pre-pass.

**Response:**
```json
{
  "summary": {
    "total_students": 200,
    "stable":        {"count": 124, "percentage": 62},
    "needs_followup":{"count": 46,  "percentage": 23},
    "at_risk":       {"count": 20,  "percentage": 10},
    "excelling":     {"count": 10,  "percentage": 5}
  },
  "risk_map": [
    {
      "student_id": "uuid",
      "name": "سارة الأحمدي",
      "class_name": "5A",
      "x_academic": 35,
      "y_engagement": 40,
      "risk_score": 38,
      "category": "at_risk",
      "factors": ["انخفاض الحضور", "تدني الأداء الأكاديمي"]
    }
  ],
  "intervention_list": [
    {
      "student_id": "uuid",
      "name": "سارة الأحمدي",
      "class_name": "5A",
      "category": "at_risk",
      "issue_type": "attendance",
      "issue_label_ar": "انخفاض الحضور",
      "risk_score": 38,
      "parent_id": "uuid"
    }
  ],
  "root_causes": {
    "attendance":    {"count": 18, "percentage": 40},
    "participation": {"count": 9,  "percentage": 20},
    "behaviour":     {"count": 7,  "percentage": 15},
    "academic":      {"count": 11, "percentage": 25}
  },
  "last_updated": "2026-04-16T10:30:00Z"
}
```

**Category mapping** — read directly from Hakim's `RISK_CATEGORIES` constant; do not invent thresholds in this endpoint.
- `stable` = `risk_category in {"low"}`
- `needs_followup` = `risk_category == "medium"`
- `at_risk` = `risk_category in {"high", "critical"}`
- `excelling` = `risk_score >= 90` AND `breakdown.academic` is in the school's top academic quartile.

**Risk-map coordinates:**
- `x_academic` = `breakdown.academic` (0–100).
- `y_engagement` = `round((breakdown.attendance + breakdown.participation) / 2, 1)`.

**Intervention list:**
- Include only `needs_followup` + `at_risk`.
- Sort by `risk_score` ascending.
- Cap at 50.
- `issue_type` = key of the lowest value in `breakdown` for that student. `issue_label_ar` = the Arabic label from Hakim's factors list.

**Root causes:**
- For every student with `risk_score < 75`, identify their single weakest breakdown factor.
- Aggregate counts across those factors; compute percentages.
- Four keys fixed: `attendance`, `participation`, `behaviour`, `academic`.

### 4.2 `GET /ai/insights/at-risk-students` (refactored, backwards compatible)

Re-implemented as a thin wrapper:
1. Call `students_overview(school_id)` (benefits from cache).
2. Return `intervention_list[:20]` reshaped to the legacy response schema used today:
   ```json
   [{ "id": "...", "name": "...", "grade": "5A", "risk_level": 38, "risk_type": "attendance", "factors": [...] }]
   ```
3. `risk_level` = `risk_score`, `risk_type` = `issue_type`, `grade` = `class_name`.

No breaking changes for existing callers.

### 4.3 `GET /ai/insights/recommendations-ai` (NEW)

OpenAI-backed Arabic recommendations, additive to the existing rule-based `/ai/insights/recommendations` (which stays untouched for its current consumers).

**Flow:**
1. Read cached `students_overview` for this school (compute if absent).
2. Build stats bag: counts per category, weekly delta (compare against a one-week-old snapshot stored in a lightweight `ai_insight_snapshots` doc; missing snapshot ⇒ omit delta), successful intervention count (count of `remedial_plans` with `status=completed` in last 30d), top classes by at-risk ratio.
3. Build Arabic prompt (template below) and call OpenAI via the same client used by Hakim chat (`backend/services/` existing path). Request JSON response.
4. Validate: must be a JSON array of `{type, text}`, max 6, types restricted to `quantitative | academic | statistical_alert | positive | administrative`. Attach default icons server-side.
5. On any failure (timeout, parse error, invalid types): return a single `statistical_alert` item derived from the stats bag ("ارتفاع نسبة الطلاب المتعثرين إلى X%" or similar). Do not 500 the page.

**Cache:** 15 min per school.
**Prompt template (Arabic):**
```
أنت مستشار تعليمي ذكي. بناءً على بيانات مدرسة:
- إجمالي الطلاب: {total}
- في فئة الخطر: {at_risk}
- يحتاجون متابعة: {needs_followup}
- أسباب التعثر الشائعة: {top_causes}
- التغير عن الأسبوع الماضي: {weekly_delta}
- تدخلات ناجحة في آخر 30 يوم: {successful_interventions}
- فصول تحتاج اهتمام: {top_classes}

قدّم ما بين 4 إلى 6 توصيات مهيكلة كقائمة JSON حصراً، بالصيغة:
[{"type":"quantitative|academic|statistical_alert|positive|administrative","text":"نص التوصية"}]
```

**Response:**
```json
{
  "recommendations": [
    {"type":"quantitative","text":"...","icon":"📊"}
  ],
  "generated_at": "2026-04-16T10:30:00Z",
  "source": "openai" // or "fallback"
}
```

### 4.4 `POST /ai/insights/intervention` (NEW)

**Request:**
```json
{
  "student_id": "uuid",
  "action_type": "notify_parent | remedial_plan | schedule_followup",
  "data": {
    "message": "...",              // notify_parent
    "issue_type": "attendance|participation|behaviour|academic",
    "description": "...",          // remedial_plan
    "target_date": "YYYY-MM-DD",   // remedial_plan
    "milestones": ["...", "..."],  // remedial_plan
    "follow_up_date": "YYYY-MM-DD",// schedule_followup
    "notes": "..."                 // schedule_followup
  }
}
```

**Dispatch:**
- `notify_parent` → resolve `parent_id` from the student record; call `create_notification_internal(recipient_id=parent_id, category=issue_type, priority="high" if student.category=="at_risk" else "medium", title_ar="متابعة أداء الطالب", body_ar=message)`. Reject if the student has no `parent_id`.
- `remedial_plan` → insert into `remedial_plans` collection (see §4.6) with `status="active"` and `start_date=today`.
- `schedule_followup` → insert into `remedial_plans` with `type="followup"`, `status="active"`, `start_date=today`, `follow_up_date` from payload. Unified collection — simpler than splitting into `behaviour_records`.

All three invalidate the `students_overview` cache for the school so the UI reflects the action on next refresh.

**Response:**
```json
{ "success": true, "intervention_id": "uuid", "message_ar": "تم تنفيذ الإجراء بنجاح" }
```

### 4.5 Hakim engine additions

**`analyze_students_risk_batch(school_id, student_ids, days_back=30) -> List[Dict]`**

Returns one entry per student matching the existing `analyze_student_risk` shape (`student_id`, `student_name`, `class_id`, `risk_score`, `risk_category`, `risk_label_ar`, `recommendation`, `factors`, `breakdown`, `period_days`, `analyzed_at`).

Implementation:
1. Resolve `cutoff` date once.
2. Five batched queries (all scoped by `school_id` and `student_ids`):
   - attendance totals + present/late per student
   - session_attendance present per student (with session_ids pre-fetched once for the school)
   - session_interactions per student, split by `interaction_type in {behaviour, participation}`
   - grades aggregate per student (avg percentage, count)
   - student class_id lookup
3. Refactor existing `_calc_*` helpers to accept pre-fetched per-student dicts (backwards-compatible overloads kept for the single-student path).
4. Combine with `RISK_WEIGHTS` — no new scoring logic.

Single-student `analyze_student_risk` keeps its current signature and now just delegates to `analyze_students_risk_batch([student_id])[0]` internally (optional optimization, not required for shipping).

### 4.6 New collection — `remedial_plans`

Generic document with this shape:
```json
{
  "collection": "remedial_plans",
  "data": {
    "student_id": "uuid",
    "school_id": "uuid",
    "created_by": "uuid",
    "type": "plan | followup",
    "issue_type": "attendance|participation|behaviour|academic",
    "description": "string",
    "start_date": "YYYY-MM-DD",
    "target_date": "YYYY-MM-DD",
    "follow_up_date": "YYYY-MM-DD | null",
    "follow_up_notes": "string",
    "milestones": [{"text":"...", "completed": false}],
    "status": "active | completed | cancelled",
    "created_at": "ISO",
    "updated_at": "ISO"
  }
}
```
Tenant isolation: every read/write includes `school_id`. No Alembic migration needed (generic doc).

---

## 5. Frontend

### 5.1 Files

Modified:
- `frontend/src/pages/AIInsightsPage.jsx` — add Radix Tabs, role gate, lazy-load new tab.
- `frontend/src/locales/ar.json`, `en.json` — new keys.

New under `frontend/src/components/student-performance/`:
- `StudentPerformanceDashboard.jsx` — container, state, data fetching, refresh button.
- `ExecutiveSummaryCards.jsx` — 4 KPI cards.
- `StudentRiskMap.jsx` — Recharts `ScatterChart`, tooltip, click-to-details.
- `InterventionList.jsx` — ranked list + "اتخاذ إجراء" dropdown.
- `InterventionActionModal.jsx` — unified modal with 3 form variants.
- `RootCauseChart.jsx` — Recharts `PieChart`, 4 slices aligned with Hakim.
- `HakimRecommendations.jsx` — typed cards with colored right-border.

### 5.2 Tabs and role gate

```jsx
const canSeeStudentPerformance =
  ['school_admin', 'school_sub_admin', 'school_principal'].includes(user.role);

<Tabs defaultValue="insights">
  <TabsList>
    <TabsTrigger value="insights">{t('aiInsights')}</TabsTrigger>
    {canSeeStudentPerformance && (
      <TabsTrigger value="student-performance">{t('studentPerformance')}</TabsTrigger>
    )}
  </TabsList>
  <TabsContent value="insights">{/* existing 594-951 content unchanged */}</TabsContent>
  {canSeeStudentPerformance && (
    <TabsContent value="student-performance">
      <Suspense fallback={<DashboardSkeleton/>}>
        <StudentPerformanceDashboard />
      </Suspense>
    </TabsContent>
  )}
</Tabs>
```

Active tab underline: `#46C1BE`.

### 5.3 Data fetching

On tab mount:
- `GET /ai/insights/students-overview` → feeds KPIs, scatter, intervention list, pie chart.
- `GET /ai/insights/recommendations-ai` → feeds Hakim recommendations card.

Manual refresh button re-runs both with `?refresh=1` query (backend busts cache when present).

### 5.4 Intervention action modal

Single modal, three rendered variants keyed by `actionType`:
- `notify_parent`: preview the default template (editable), send button.
- `remedial_plan`: issue_type (prefilled), description textarea, start/target date pickers, dynamic milestones list.
- `schedule_followup`: follow_up_date picker (default +7 days), notes textarea.

On success: toast with appropriate `t('messageSentToParent' | 'remedialPlanCreated' | 'followupScheduled')` and trigger dashboard refresh.

### 5.5 i18n keys (aligned with v2 taxonomy)

```json
{
  "studentPerformance": "تحليل أداء الطلاب",
  "executiveSummary": "ملخص تنفيذي",
  "stable": "مستقر",
  "needsFollowup": "يحتاج متابعة",
  "educationalRisk": "خطر تعليمي",
  "excelling": "متفوقون",
  "riskMap": "خريطة المخاطر",
  "studentsNeedIntervention": "طلاب يحتاجون تدخلاً",
  "takeAction": "اتخاذ إجراء",
  "sendParentMessage": "رسالة لولي الأمر",
  "createRemedialPlan": "خطة علاجية",
  "scheduleFollowup": "متابعة الأسبوع القادم",
  "rootCauseAnalysis": "أسباب التعثر",
  "attendance": "الحضور",
  "participation": "المشاركة",
  "behaviour": "السلوك",
  "academic": "الأداء الأكاديمي",
  "nassaqSuggestions": "اقتراحات نسق",
  "refreshData": "تحديث البيانات",
  "lastUpdated": "آخر تحديث",
  "interventionSuccess": "تم تنفيذ الإجراء بنجاح",
  "messageSentToParent": "تم إرسال الرسالة لولي الأمر بنجاح",
  "remedialPlanCreated": "تم إنشاء الخطة العلاجية بنجاح",
  "followupScheduled": "تمت جدولة المتابعة بنجاح",
  "planDescription": "وصف الخطة",
  "targetDate": "تاريخ الهدف",
  "milestones": "خطوات المتابعة",
  "followupDate": "تاريخ المتابعة",
  "followupNotes": "ملاحظات المتابعة",
  "noStudentsAtRisk": "لا يوجد طلاب في فئة الخطر حالياً",
  "academicAxis": "الأداء الأكاديمي",
  "engagementAxis": "الحضور والمشاركة"
}
```

`homework` and `exams` keys removed vs v1.

---

## 6. Data flow — intervention action example

```
User clicks "إرسال رسالة لولي الأمر"
 └─▸ InterventionActionModal renders notify_parent variant
     └─▸ POST /ai/insights/intervention { action_type: "notify_parent", ... }
         └─▸ route resolves parent_id from students
             └─▸ create_notification_internal(...)
                 └─▸ inserts into notifications
             └─▸ invalidate students_overview cache for school_id
         └─▸ { success: true, intervention_id, message_ar }
     └─▸ toast success, close modal, trigger dashboard refresh
```

---

## 7. Implementation phases

**Phase 1 — Hakim batch + overview endpoint**
1. Refactor `_calc_*` helpers in `hakim_ai_engine.py` to accept pre-fetched data.
2. Add `analyze_students_risk_batch`.
3. Add `GET /ai/insights/students-overview` with in-memory TTL cache and 500-student cap.
4. Refactor `GET /ai/insights/at-risk-students` into wrapper — preserve existing response schema, verify no consumer breakage.

**Phase 2 — Intervention + OpenAI recommendations**
5. Register `remedial_plans` usage (no migration; generic doc).
6. Add `POST /ai/insights/intervention` with three dispatch paths + cache invalidation.
7. Add `GET /ai/insights/recommendations-ai` with OpenAI call, validation, fallback, 15-min cache.

**Phase 3 — Frontend**
8. Add Tabs to `AIInsightsPage.jsx`, role gate, lazy-load.
9. Build 7 components under `student-performance/`.
10. Wire data fetching + manual refresh.
11. Wire intervention modal + toast + refresh.
12. Add i18n keys (ar + en).

**Phase 4 — Verification**
13. Role gate test (tab hidden for teacher/parent/platform admin).
14. Intervention side-effect tests (notification row, remedial_plans row).
15. Perf check: overview endpoint ≤ 2 s for 500 students.
16. OpenAI fallback test (force error → fallback item returned, page renders).

---

## 8. Files affected

**Modified**
- `backend/engines/hakim_ai_engine.py` — batch helper, refactor private calcs.
- `backend/routes/ai_routes_mod.py` — new endpoints, refactor existing `at-risk-students`.
- `frontend/src/pages/AIInsightsPage.jsx` — Tabs.
- `frontend/src/locales/ar.json`, `en.json` — new keys.

**New**
- `frontend/src/components/student-performance/StudentPerformanceDashboard.jsx`
- `frontend/src/components/student-performance/ExecutiveSummaryCards.jsx`
- `frontend/src/components/student-performance/StudentRiskMap.jsx`
- `frontend/src/components/student-performance/InterventionList.jsx`
- `frontend/src/components/student-performance/InterventionActionModal.jsx`
- `frontend/src/components/student-performance/RootCauseChart.jsx`
- `frontend/src/components/student-performance/HakimRecommendations.jsx`

No new backend route file — all endpoints live in `ai_routes_mod.py` to stay consistent with the existing module layout.

---

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Batch scoring slower than ad-hoc formula | 5 pre-fetched queries; benchmark on seeded data; target ≤ 2 s / 500 students; fall back to cached snapshot on timeout. |
| Old `at-risk-students` consumers break | Endpoint kept, response schema preserved; targeted tests on the wrapper. |
| OpenAI latency / cost | 15-min cache, 6-item cap, JSON-only validation, deterministic fallback. |
| Risk thresholds drift between UI and engine | UI never recomputes `risk_category`; always reads from backend response. |
| Cache staleness after intervention | Intervention POST invalidates the overview cache for the school. |
| Students with no parent | `notify_parent` returns 400 with explicit Arabic error; UI disables the option when `parent_id` is missing. |

---

## 10. RBAC compliance

This feature **must** use the project's existing RBAC primitives. No custom role checks, no inline role lists scattered across handlers.

### 10.1 Enforcement primitives

- **Enum:** `UserRole` from `backend/dependencies.py` (values: `school_admin`, `school_sub_admin`, `school_principal`, `platform_admin`, `teacher`, `independent_teacher`, `student`, `parent`, …).
- **Decorator:** `require_roles([...])` from `backend/dependencies.py`. FastAPI dependency; returns `current_user` dict on success, raises `403` on role mismatch.
- **Tenant isolation:** Every read/write includes `school_id = current_user["tenant_id"]`. Documents without a matching `school_id` are invisible. This is enforced in every query — not optional, not batched into a trust boundary elsewhere.

### 10.2 Endpoint role matrix

| Endpoint | Method | Allowed roles | Notes |
|---|---|---|---|
| `/ai/insights/students-overview` | GET | `SCHOOL_ADMIN`, `SCHOOL_SUB_ADMIN`, `SCHOOL_PRINCIPAL` | New. `require_roles` gate. Platform admin excluded. |
| `/ai/insights/recommendations-ai` | GET | `SCHOOL_ADMIN`, `SCHOOL_SUB_ADMIN`, `SCHOOL_PRINCIPAL` | New. Same gate. |
| `/ai/insights/intervention` | POST | `SCHOOL_ADMIN`, `SCHOOL_SUB_ADMIN`, `SCHOOL_PRINCIPAL` | New. Same gate. Mutating. |
| `/ai/insights/at-risk-students` | GET | `SCHOOL_ADMIN`, `SCHOOL_SUB_ADMIN`, `SCHOOL_PRINCIPAL` | **Existing — currently ungated.** This revision adds `require_roles`. Considered a security fix, not a breaking change (no non-admin callers in code audit). |

### 10.3 Frontend tab gate

The new tab is shown only when `user.role` ∈ `{school_admin, school_sub_admin, school_principal}`. This is a UX convenience, not a security boundary — the real gate is §10.2. Never rely on the tab being hidden to protect data.

### 10.4 Intervention-specific authorization

- `notify_parent`: requires the student's `school_id` to equal `current_user["tenant_id"]`. Parent must belong to the same school. Reject with 404 if the student isn't in the caller's tenant (never 403, to avoid leaking existence).
- `remedial_plan` and `schedule_followup`: same tenant check. `created_by` = `current_user["id"]`. Audit-write only; no edits in this release.
- All three intervention branches write an `audit_log` row via the existing audit middleware pattern (`action=intervention.<action_type>`, `resource_type=student`, `resource_id=student_id`).

### 10.5 Test matrix (to be encoded in plan)

| Scenario | Expected |
|---|---|
| `school_admin` calls any new endpoint in own tenant | 200 |
| `school_sub_admin` calls any new endpoint in own tenant | 200 |
| `school_principal` calls any new endpoint in own tenant | 200 |
| `teacher` calls any new endpoint | 403 |
| `parent` calls any new endpoint | 403 |
| `student` calls any new endpoint | 403 |
| `platform_admin` calls any new endpoint | 403 |
| `school_admin` intervenes on a student from a different `school_id` | 404 |
| Unauthenticated request | 401 |
| `school_admin` of tenant A never sees a single row from tenant B in `students-overview` | data-isolation test with seeded two-tenant fixture |

### 10.6 Non-goals for RBAC

- No row-level sub-delegation (e.g., sub-admin restricted to a subset of classes). Out of scope.
- No PII redaction beyond existing field policies. Student names and parent ids are already visible to the allowed roles elsewhere.

---

## 11. Acceptance criteria

- [ ] Tab visible only for `school_admin`, `school_sub_admin`, `school_principal`.
- [ ] KPI cards show live counts from `students-overview` that sum to `total_students`.
- [ ] Risk map renders every returned student as a colored point; click reveals tooltip with name, class, risk_score, factors.
- [ ] Intervention list ordered by risk ascending, capped at 50.
- [ ] "إرسال رسالة" creates a real row in `notifications` for the student's parent.
- [ ] "خطة علاجية" creates a real `remedial_plans` document (`type=plan`).
- [ ] "جدولة متابعة" creates a real `remedial_plans` document (`type=followup`, `follow_up_date` set).
- [ ] Pie chart slices are exactly `attendance / participation / behaviour / academic` with Arabic labels.
- [ ] `recommendations-ai` returns 4–6 typed items in Arabic; on OpenAI error returns exactly one fallback item with `source="fallback"`.
- [ ] `at-risk-students` response schema unchanged (regression-tested).
- [ ] Manual refresh button bypasses cache (`?refresh=1`).
- [ ] Overview endpoint returns in ≤ 2 s for 500 students (dev seed data).
- [ ] Full RTL; brand colors/fonts applied; all visible strings translated (ar+en).
