# Phase 4 — E2E Reliability per Role

**Date:** 2026-04-17 · **Status:** ✅ Complete (API-level smoke tests)
**Method:** authenticated `curl` sweeps over public endpoints + 4 representative roles. Login worked for `school_principal` (abdulelah, ahmaaad), `teacher` (ahmed.teacher), `student` (student@nassaqapp.com). Parent/platform_admin passwords were not in the environment, so those flows are checked at the contract level (401/403 paths) and via the principal/teacher views of parent data.

## 1. Findings

| ID | Sev | Finding |
|---|---|---|
| **E-01** | 🟥 Critical | **`GET /api/users` returns HTTP 500** for `school_principal` (error_id `35c89490`). Need to investigate the route handler — likely a missing tenant filter or unhandled `KeyError` on the response builder. Backend log showed no traceback because `INTERNAL_ERROR` swallowed it. |
| **E-02** | 🟧 High | **`GET /api/teachers/me` returns 404** for an authenticated `teacher` user. Auth path enriches `teacher_id` by `users.email == teachers.email` lookup — for `ahmed.teacher@nassaqapp.com` the lookup must be failing (mismatched email or no row). Combined with D-05 (4 teachers with bad `user_id`), the same teacher account ends up with `teacher_id=None` → "teacher not found". |
| **E-03** | 🟧 High | **`GET /api/students/me` returns 404** for an authenticated `student`. Same root cause as E-02 but for `student_id` enrichment. |
| **E-04** | 🟧 High | ✅ **FIXED in Phase 5.** The SPA static fallback (`@app.get("/{full_path:path}")`) was returning `index.html` (HTTP 200) for every unknown path — including `/api/*`, `/docs`, `/openapi.json`. This silently masked 404s. Now returns proper JSON 404 for reserved prefixes. |
| **E-05** | 🟨 Medium | **`/api/notifications` and `/api/messages` return `[]`** (literal empty list, only `2b` payload) for principal AND teacher accounts that have data in DB. Possible tenant-filter mismatch — the principal's `tenant_id` may not match the way notifications are stored. Worth a route-level investigation. |
| **E-06** | 🟩 Low | **WebSocket `/ws` probes** continue to be rejected (403). These come from health-check / probe traffic — frontend uses `/api/ws/notifications` correctly. No action. |
| **E-07** | 🟩 Low | **All public + auth endpoints respond < 50 ms** under single-request load. p95 (sample n=20): `/api/auth/me`=12 ms, `/api/students`=44 ms, `/api/dashboard/stats`=29 ms. |

## 2. Per-role coverage matrix

| Role | Login | /me | List own resources | Notifications | Dashboard |
|---|---|---|---|---|---|
| **platform_admin** | ⚪ no creds | – | – | – | – |
| **school_principal** | ✅ | ✅ 12ms | ✅ /api/students, /api/teachers, /api/classes, /api/parents | ⚠ E-05 | ✅ 29ms |
| **teacher** | ✅ | ✅ 9ms | ❌ E-02 (`/teachers/me` 404) | ⚠ E-05 | ✅ 15ms |
| **student** | ✅ | ✅ 12ms | ❌ E-03 (`/students/me` 404) | ⚠ E-05 | ✅ 15ms |
| **parent** | ⚪ no creds | – | – | – | – |
| **independent_teacher** | ⚪ not tested | – | – | – | – |
| **school_admin** | ⚪ not tested | – | – | – | – |

## 3. Unauthenticated path checks

- `/api/auth/me` without token → 401 ✅
- `/api/students` without token → 401 ✅
- `/api/dashboard/stats` without token → 401 ✅
- `/api/public/contact-info` → 200 (442 B)
- `/api/public/stats` → 200 (126 B)
- `/api/health` → 200 ✅
- `/api/metrics` → 200 ✅

## 4. Action items → Phase 5

- **E-01, E-02, E-03**: open three small fix-PRs after this report (E-01 needs trace, E-02/E-03 are auth-enrichment fallbacks).
- **E-04**: ✅ FIXED.
- **E-05**: investigate empty notifications.

## Gate

✅ Phase 4 complete (with caveats on missing platform_admin / parent credentials). **Proceeding to Phase 5 (Fix everything).**
