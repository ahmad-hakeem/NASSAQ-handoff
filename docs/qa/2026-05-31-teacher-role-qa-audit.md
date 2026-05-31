# School Teacher Role — End-to-End QA Audit

- **Date:** 2026-05-31
- **Scope:** `School Teacher` role only (NASSAQ multi-tenant school management)
- **Environment:** Dev — Frontend (CRACO) `:5000`, Backend (FastAPI) `:8000`
- **Test account:** Teacher from `TEST_CREDENTIALS.md` → `أميرة الصاعدي` (role `teacher`); tenant `faarabi` (الفارابي). Teaches Arabic across 18 classes.
- **Method:** Read-only audit. Authenticated Playwright traversal of every teacher-reachable route + direct API probes (login token) + database cross-checks. **No application code was modified.**
- **Verdict:** No cross-tenant breach and tenant/role isolation on privileged surfaces holds. However there is **one within-tenant object-level authorization gap (High)** plus a **broken default state on the three core class pages (High)**, both traced to a single root cause.

---

## Summary of findings

| # | Severity | Area | Issue |
|---|----------|------|-------|
| F1 | **High** | Access control (IDOR) | `GET /api/students?class_id=X` returns a roster for a class the teacher does **not** teach (200), while `GET /api/classes/X/students` correctly forbids it (403). The two paths use different authorization sources. |
| F2 | **High** | Broken core flow | Students / Attendance / Behavior pages default-select a non-assigned class (the junk class `rgterger`) → roster fetch 403 → error/empty state on first load. |
| F3 | **High** | Data scope / disclosure | Teacher list endpoints are not limited to assigned classes: `/api/students`→ all 265 school students (whole-school student PII), `/api/classes`→ all 20 classes, so "فصولي/My Classes", AI-Insights and Tasks all show **school-wide** counts. |
| F4 | Medium | Data scope | `GET /api/teachers` returns all 104 staff records to a regular teacher. |
| F5 | Medium | Broken flow / route | `/admin/attendance` is teacher-reachable but its data API returns 403 → `NassaqAlertDialog` "فشل تحميل الطلاب". |
| F6 | Low | Dead endpoint | Tasks page calls `GET /api/teacher/attendance/status?date=…` → 404 (route does not exist); silently swallowed by `.catch(() => null)`. |
| F7 | Low | UI / console | AI-Insights emits recharts `width(-1)/height(-1)` warnings (chart rendered before container is measured). |
| INFO | — | Env | Global "المنصة قيد التطوير" banner on every page (dev/test build). External `assets.mixkit.co` sound effect 404s on Resources/AI-Insights (non-critical third-party asset). |

### What works correctly (verified)
- **Auth/identity:** teacher JWT carries `role: teacher`; no cross-identity bug; refresh and hard-navigation keep the correct identity.
- **Dashboard** (`/teacher/home`): correct, shows the real current lesson from the schedule (`اللغة العربية / الصف السادس أ / الحصة 7`), profile %, school timeline.
- **Privileged API isolation:** teacher receives **403** on `/audit/*`, `/analytics/*`, `/platform/analytics`, `/users`, `/schools`, `/system/metrics`, `/parents`.
- **Route guards:** `/admin`, `/platform`, `/parent`, `/master-schedule` all redirect the teacher away.
- **By-id roster authorization:** `GET /api/classes/{id}/students` returns 403 for non-assigned/junk classes and 200 (14 students) for an assigned class.
- **Pages that render cleanly:** Resources, AI-Insights, Notifications, Account Settings, Product Hub.
- **Error dialogs** use `NassaqAlertDialog` (compliant), and RTL/Arabic localization renders correctly across pages.

---

## Root cause (shared by F1, F2, F3)

There are **two parallel class-authorization sources that disagree**, plus an unscoped class list feeding the UI:

- `can_view_class()` (`backend/utils/tenant_scope.py`) authorizes from **`teacher_assignments` ∪ `class_sessions`**. This guards `GET /api/classes/{id}/students`.
- The `GET /api/students` teacher scoping block (`backend/routes/academics_student_routes.py`, ~L185-205) authorizes from **`teacher_assignments` ∪ `teacher_class_assignments` ∪ `class_sessions`**.

Database for this teacher (`teacher.id = 390cc7dd…`):

| Source table | Rows for teacher | Classes covered |
|---|---|---|
| `teacher_assignments` (all `is_active=true`) | 18 | her real teaching set |
| `teacher_class_assignments` | 20 | **all** school classes (incl. junk `rgterger`) |
| `class_sessions` | table **does not exist** | — |

The breadth of `teacher_class_assignments` is **systemic, not dirty data**: `backend/routes/school_settings_mod.py` auto-links every teacher to every class (`_auto_populate_teacher_class_assignments`, `_ensure_teacher_linked_to_all_classes`, `_ensure_class_linked_to_all_teachers`) for scheduling/admin convenience. The real defect is that `/api/students` **trusts this mass-populated table as an authorization source**, while `can_view_class()` (correctly) does not. So the same class (`rgterger`, which has 0 `teacher_assignments`) is **allowed** via `/students?class_id=` but **denied** via `/classes/{id}/students`. The whole-school `/students` result (265) is the union of all 20 auto-linked classes.

Separately, `GET /api/classes` returns all 20 school classes regardless of assignment; the frontend builds the class dropdown from it and defaults to the first entry (`rgterger`), which `can_view_class()` denies → the 403 error state in F2.

**Related consistency risk:** `can_view_class()` matches `teacher_assignments` **without** filtering `is_active`, whereas the `/students` scoping block requires `is_active=True`. A soft-revoked (de-assigned) teacher could therefore still pass the by-id roster gate — a separate stale-access behavior worth reviewing when these two paths are reconciled.

---

## Detailed findings

### F1 — High — Object-level authorization bypass on `/api/students?class_id=` (within-tenant IDOR)
**Observed (same teacher token, post backend restart):**
```
GET /api/classes/5f426a13…/students   → 403  (correct)
GET /api/students?class_id=5f426a13…  → 200, 6 students   (BYPASS)
GET /api/students                      → 200, 265 students (all school)
```
`5f426a13…` ("rgterger") has zero `teacher_assignments` — the teacher does not teach it, yet she can read its roster (student records) through the query-param endpoint. This discloses student PII for non-assigned classes and contradicts the by-id gate.
**Impact:** Least-privilege / object-level authorization gap. Same-tenant only (no cross-school leak), so not Critical, but a teacher can enumerate any class roster in their school.
**Suggested direction (not applied):** make `/students` and `can_view_class()` share one authorization helper; reconcile whether `teacher_class_assignments` should grant roster access at all; treat per-class reads consistently.

### F2 — High — Core class pages land in an error/empty state by default
**Observed (UI, logged in as teacher):**
- `/teacher/students`: class selector defaults to `rgterger` → `NassaqAlertDialog`/error card "تعذر تحميل البيانات / حدث خطأ أثناء تحميل الطلاب" (the underlying `GET /api/classes/rgterger/students` is 403). Stat cards show 0/0/0%/0.
- `/teacher/attendance`: الفصل = `rgterger` → "لا يوجد طلاب في هذا الفصل".
- `/teacher/behavior`: selector = `rgterger` → "لا يوجد طلاب".
- `/teacher/tasks`: "تسجيل الحضور" list includes `rgterger` (6 طلاب) among classes to record.

A teacher opening any of these three primary pages sees a broken/empty screen until they manually switch to one of their own classes.
**Impact:** Primary daily workflows (view roster, take attendance, log behavior) are broken on first load.
**Suggested direction (not applied):** scope `/api/classes` (dropdown source) to assigned classes, and/or have the FE default-select an assigned class instead of the first item of an unscoped list; remove the junk `rgterger` class from seed data.

### F3 — High — Teacher list endpoints expose school-wide student PII
- `/api/students` → 265 (entire school active students; her assignment-scoped reach is 251).
- `/api/classes` → 20 (she teaches 18).
- Surfaces that consume these show school-wide numbers: "فصولي/My Classes" header (**265 طالب / 20 فصل**), AI-Insights ("**265 مستجلين في فصولك**" — labelled as *your* students), Tasks list (all 20 classes).
**Impact:** Over-disclosure and misleading "my classes" framing; same root cause as F1.

### F4 — Medium — Full staff directory exposed to a teacher
`GET /api/teachers` → 200 with all **104** teacher records in the tenant. May be intended as a directory, but should be reviewed for which fields a regular teacher should see.

### F5 — Medium — `/admin/attendance` reachable but unauthorized
The teacher can navigate to `/admin/attendance` (it does not redirect like `/admin`), but its data API returns **403**, producing a `NassaqAlertDialog` "خطأ / فشل تحميل الطلاب". Either the route should not be teacher-reachable or the API should serve the teacher's own scope.

### F6 — Low — Dead endpoint call on Tasks page
`frontend/src/pages/TeacherModule/TeacherTasksPage.jsx` calls `GET /api/teacher/attendance/status?date=…`, which has no backend route (404). It is wrapped in `.catch(() => null)`, so there is no user-visible impact, but it is a dead call masking a silent failure.

### F7 — Low — Recharts sizing warnings on AI-Insights
Console warnings `width(-1) and height(-1) of chart should be greater than 0` — charts render before their container is measured. Cosmetic; charts still display.

### INFO
- A global banner "المنصة قيد التطوير…" appears on every page (expected for the dev/test build).
- `https://assets.mixkit.co/.../2869-preview.mp3` fails to load on Resources and AI-Insights — a third-party sound-effect asset, non-critical.

---

## Evidence index
- Screenshots: `.local/qa/out/shots/` (Dashboard, Students, AttendanceManage, Behavior, Classes, Tasks, AIInsights, AdminAttendance, Notifications, AccountSettings, ProductHub, GUARD_* ).
- Route traversal records: `.local/qa/out/routes.jsonl`, `routes4.json`, run logs `run*.log`.
- Audit scripts: `.local/qa/audit.py`, `audit3.py`, `audit4.py`.
- API/DB probes performed inline during the audit (login token + read-only SQL counts).

## Notes / constraints honored
- Read-only first-pass audit: **no application code changed**.
- Test credentials referenced by filename only; never copied into code, logs, or this report.
