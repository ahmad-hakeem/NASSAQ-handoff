# Bug Fix Design — High / Medium / Low Priority Issues

**Date:** 2026-04-16
**Scope:** Fixes for all High, Medium, and Low priority bugs found in the April 2026 audit. Critical items (token storage, hardcoded secrets, XSS, insecure WS, Stripe key) are intentionally excluded per user instruction.

---

## Group 1 — Backend Security (High)

### 1a. Tenant Isolation in `get_students`
`academics_student_routes.py` line 117 accepts a caller-supplied `school_id` query param and uses it directly without checking whether the current non-admin user actually belongs to that school. Fix: ignore the param for non-platform-admins and always enforce `current_user.tenant_id`.

### 1b. Missing School Isolation in `get_student`
`academics_student_routes.py` line 276 looks up a student by ID alone, without checking the student's `school_id` against the requesting user's tenant. Fix: add a tenant check after the lookup and raise 403 if mismatch.

### 1c. Missing Role Checks on Options Endpoints
`/classes/options/grades`, `/classes/options/teachers`, `/students/options/classes` only require `get_current_user`. Students or parents could call these. Fix: require at minimum TEACHER role via a role-check helper.

### 1d. Dynamic `sqlalchemy.text()` in Alembic Migrations
Two migration files build SQL strings dynamically and pass them to `sqlalchemy.text()`. These are one-time migration scripts and the dynamic parts are internal column-name lists (not user input), so the risk is low in practice. Fix: replace dynamic string concatenation with static parameterized queries or pre-built safe strings.

### 1e. JWT Logout Deny-list
Logout currently only logs an audit event; the token stays valid until expiry. Fix: add a `revoked_tokens` table in PostgreSQL (id, jti, expires_at) and check it in `get_current_user`. Tokens get a `jti` (UUID) claim at creation; on logout the jti is inserted into the table.

---

## Group 2 — Backend Performance & Reliability (Low)

### 2a. N+1 Query in `analyze_teacher_sessions`
`hakim_ai_engine.py` lines 422–433 runs `gd_find_one` per class inside a loop. Fix: collect all class IDs first, then run a single `gd_find` with `{"id": {"$in": class_ids}}`, and build a lookup dict.

### 2b. In-Memory Average in `analyze_class_health`
Fetches up to 10,000 `student_daily_scores` records to sum in Python. Fix: use `gd_aggregate` (or `gd_count` + a weighted query) to compute totals on the DB side, avoiding the large in-memory load.

### 2c. Missing `try/except` in Hakim AI
`analyze_teacher_sessions` and `analyze_class_health` have no top-level error handling. Fix: wrap each public method body in `try/except Exception` and return a graceful error dict instead of propagating a 500.

### 2d. Atomic Student Count
`academics_student_routes.py` updates `student_count` with a read-then-write. Fix: use `gd_update_one` with `{"$inc": {"student_count": 1}}` (or `-1`) instead.

---

## Group 3 — React Stale Closures & Race Conditions (Medium)

### 3a. Auto-save Stale Closure in `SessionTeachPage`
The `setInterval` effect at line 275 is missing `customPositiveBehaviours`, `customNegativeBehaviours`, `customSkills` from its dependency array. Fix: add them. Also, since the interval resets on every dep change, store the latest values in a `useRef` to read inside the interval callback without making the interval itself re-create constantly.

### 3b. Unmount Guard in Session Initialization
`loadStudents().then(loadSessionInfo)` has no unmount check. Fix: use an `isMounted` ref; inside the `.then()` check `if (!isMounted.current) return` before calling `loadSessionInfo`.

### 3c. `loadHomeworkStatuses` Called Before Students Loaded
Called on line 165 inside `loadSessionInfo(studentList)` — this is fine since `studentList` is passed. The second call at line 463 in `handleSetMode` uses stale `students` state if not yet populated. Fix: guard with `if (students.length > 0)` or pass the list explicitly.

### 3d. `fetchProfile` Missing `api` Dependency
`StudentProfilePage.jsx`: `fetchProfile` captures `api` but the effect only depends on `childId`. Fix: move `fetchProfile` inside the `useEffect` or wrap it in `useCallback([api, childId])`.

### 3e. `startSession` Not Memoized in `SessionStartPage`
`startSession` changes on every render but is used in a `useEffect` without being in deps. Fix: wrap in `useCallback` with correct dependencies, then add it to the effect's dep array.

---

## Group 4 — Parent Portal Data Consistency (Medium)

### 4a. Optimistic Prepend After Form Submission
`ParentAbsenceExcusePage` and `ParentMeetingRequestPage` manually prepend to state after a POST. If the server response shape differs, the list entry is stale. Fix: after a successful submission, call `fetchData()` / `fetchMeetings()` to re-fetch the authoritative list from the server.

### 4b. ESLint `react-hooks/exhaustive-deps` Warnings
All Parent Portal pages have `fetchData`/`fetchMeetings`/`fetchProfile` defined outside `useEffect` and called inside without being in the dep array. Fix: define fetch functions inside the effect body or wrap in `useCallback` and add to dep array. This eliminates all ESLint warnings for these files.

---

## Architecture Notes

- No new dependencies introduced.
- The `revoked_tokens` table requires a new Alembic migration.
- All changes are backward-compatible.
- No frontend routing or state management structure changes.
