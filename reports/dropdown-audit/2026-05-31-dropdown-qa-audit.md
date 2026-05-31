# NASSAQ — System-Wide Dropdown / Select QA Audit (First Pass)

**Date:** 2026-05-31
**Scope:** All dropdowns / select menus / comboboxes / autocomplete / filter lists that are
backed by server data, across roles. Verifying: real data, tenant/role scoping (no cross-tenant
leak), localization (ar/en), empty states, role gating.
**Method:** Read-only first pass. API-level probing of every dropdown data-source endpoint with
real authenticated tokens across 6 role/tenant combinations + cross-tenant attack probes +
frontend wiring verification. **No code was changed.**

> Credentials referenced by role only (see `TEST_CREDENTIALS.md`); all accounts use the shared
> test password. No usernames/emails/passwords appear in this report.

---

## 1. Roles / tenants exercised

| Role label | Backend role | Tenant |
|---|---|---|
| platform_admin | `platform_admin` | none (cross-tenant) |
| farabi_admin | `school_admin` | Farabi (`cfe73b06…`) |
| ibnsina_admin | `school_admin` | Ibn Sina (`e99d639a…`) |
| farabi_teacher | `teacher` | Farabi |
| ibnsina_teacher | `teacher` | Ibn Sina |
| farabi_parent | `parent` | Farabi |

**Not testable this pass:** `independent_teacher` and standalone `school_principal` test logins
returned 401 (stale/blocked test accounts). IT-workspace dropdowns (`independent_teacher_*`
routers) are therefore **untested** and must be covered once a working IT account is available.

---

## 2. Headline results

✅ **Tenant isolation on the core dropdown data sources is solid.** `/classes`, `/subjects`,
`/teachers`, `/students`, `/directory/*` all return only the caller's tenant rows, and the
classic override vectors are all neutralized:

| Attack | Result |
|---|---|
| `farabi_admin` token + `/classes?school_id=<ibnsina>` | Returns Farabi only — param ignored ✅ |
| `…?tenant_id=<ibnsina>` (classes/students/teachers/subjects) | Returns Farabi only ✅ |
| `farabi_admin` + `X-School-Context: <ibnsina>` header | `403` ✅ |
| `ibnsina_teacher` → `/directory/students` | Zero Farabi rows ✅ |

✅ **Role gating on directory/list sources is correct:** parent → `/students` `403`,
`/parents` `403`, `/directory/students` `403`; teacher → `/parents` `403`,
`/directory/parents` `403`. Parents/teachers cannot enumerate restricted lists.

✅ **Option/reference dropdowns return real, bilingual data** (`name_ar` + `name_en`): teacher
ranks, contract types, nationalities, teacher grades, `/classes/options/grades` (12),
`/classes/options/teachers` (104), `/classes/options/students` (265), `/reference/grades` (12–13).

---

## 3. Findings (prioritized)

### 🔴 HIGH-1 — `/reference/subjects` leaks foreign-tenant subjects to any authenticated user
- **Evidence:** Called with `farabi_admin`, `ibnsina_admin`, both teachers, and the parent — every
  role receives the **same 100 rows** containing subjects whose `school_id` belongs to *other*
  schools and IT workspaces (`itw_*`, `bcf1d58d…`, `2c2ade88…`), with `is_global: false`
  (e.g. "رياضيات اختبار / Test Math", `school_id` ≠ caller tenant).
- **Why it matters:** Cross-tenant information disclosure — exactly the top risk in
  `threat_model.md` (Information Disclosure / tenant scoping). A school-created (non-global)
  subject from tenant A is visible to tenant B.
- **Live blast radius:** **Latent.** Grep shows **no frontend dropdown currently calls
  `/reference/subjects`** — live subject dropdowns use `/subjects` (correctly tenant-scoped) and
  `/classes/options/grades`. So this is an exposed API leak, not a visible broken dropdown today,
  but it should be scoped (return only `is_global=true` + caller-tenant rows) before any dropdown
  is wired to it.

### 🟠 MED-1 — `/academic-years` returns HTTP 500 for platform admin
- **Evidence:** `platform_admin` (tenant = none) → `500 INTERNAL_ERROR`. School roles work
  (Farabi n=1). Root cause: for a platform admin **without** an `X-School-Context` override the
  query is left unscoped (`query={}`), fans out across all tenants, and at least one cross-tenant
  row fails `AcademicYearResponse` serialization (`backend/routes/academics_year_term_routes.py`
  ~L148–160).
- **Impact:** Any platform-admin surface that loads the academic-year selector/list without first
  selecting a school context errors out. (`/terms` on the same router did not 500 but should be
  re-checked once years is fixed.)

### 🟡 LOW-1 — Inconsistent grade data sources; `/grade-levels` is empty for school roles
- **Evidence:** `/grade-levels` returns `[]` for school_admin/teacher/parent (only `platform_admin`
  gets 19). Three different grade sources are in use: `/grade-levels` (empty), `/reference/grades`
  (12–13), `/classes/options/grades` (12).
- **Live impact:** Mostly masked — `CreateClassWizard` uses `/classes/options/grades` (populated);
  `AddStudentWizard` receives a populated `grades` prop from `StudentsPage` (`/reference/grades`),
  so its direct `/grade-levels` fetch is only an unused fallback. **`TeacherStudentsPage`**
  (`src/pages/TeacherModule/TeacherStudentsPage.jsx` ~L150) fetches `/grade-levels` directly with a
  `catch → []`, so `workspaceGrades` is empty for teachers — verify nothing user-visible depends on
  it. Recommend consolidating on one grade source to avoid future empty-dropdown regressions.

### 🟡 LOW-2 — Empty year/term dropdowns for under-configured tenants (data, not code)
- **Evidence:** Ibn Sina returns `/academic-years` n=0 and `/terms` n=0 (Farabi has 1 and 8).
- **Impact:** Year/term selectors render empty for Ibn Sina. Behaves correctly given the data, but
  confirms these dropdowns need a clear localized empty state ("no academic years configured")
  rather than an empty popover. Flag for the interactive pass.

### 🟡 LOW-3 — Teacher can enumerate the full school roster via `/students` and `/teachers`
- **Evidence:** `farabi_teacher` → `/students` n=265 (entire school), `/teachers` n=104; parent →
  `/teachers` n=104, `/classes` n=20, `/subjects` n=14.
- **Assessment:** Same-tenant only (no cross-tenant leak), and these likely back legitimate
  selectors. But full-roster student PII to every teacher is broad per `threat_model.md`
  ("teacher-reachable directory surfaces"). **Review item**, not a confirmed vuln — confirm whether
  teacher student-selectors should be limited to assigned classes.

---

## 4. Coverage matrix (data sources verified this pass)

| Dropdown source endpoint | Real data | Tenant-scoped | Role-gated | Notes |
|---|---|---|---|---|
| `/schools` | ✅ (326, platform) | n/a | ✅ school roles `403` | platform-only selector |
| `/classes` | ✅ | ✅ | open to all in-tenant | |
| `/subjects` | ✅ | ✅ | open | |
| `/teachers` | ✅ | ✅ | open | breadth flagged LOW-3 |
| `/students` | ✅ | ✅ | ✅ parent `403` | breadth flagged LOW-3 |
| `/classes/options/grades` | ✅ (12) | ✅ | ✅ | CreateClassWizard |
| `/classes/options/teachers` `/…/students` | ✅ | ✅ | ✅ | |
| `/reference/grades` | ✅ bilingual | ✅ | ✅ | |
| `/reference/subjects` | ⚠️ | ❌ **leak** | ❌ | **HIGH-1**, not wired to UI |
| `/grade-levels` | ⚠️ empty (school roles) | — | — | **LOW-1** |
| `/academic-years` | ⚠️ | ✅ school | platform **500** | **MED-1** |
| `/terms` | ✅/empty | ✅ | | LOW-2 |
| `/teachers/options/{ranks,grades,contract-types,nationalities}` | ✅ bilingual | ✅ | ✅ | clean |
| `/directory/{teachers,students,parents,classes}` | ✅ (cap 50) | ✅ | ✅ correct gating | pagination cap |
| `/search/autocomplete` | ✅ 200 | (shape) | open | needs interactive check |

---

## 5. Not yet covered — required for a complete audit (interactive pass)

1. **Visual / UX rendering** of each dropdown (open state, placeholder, RTL alignment, long-list
   scroll, search-within-select) — needs an authenticated Playwright pass.
2. **Persistence after mutation & refresh consistency** (create a subject/class → confirm it
   appears in dependent dropdowns without hard refresh) — needs UI interaction.
3. **Localized empty states** for the empty cases found (LOW-2, LOW-1) — confirm a branded message,
   not a blank popover.
4. **Independent-teacher workspace dropdowns** — blocked this pass (no working IT login).
5. **`school_principal`-specific** surfaces — blocked (401).
6. Confirm no dropdown uses native `alert()`/`window.confirm()` on selection errors (must use
   `NassaqAlertDialog` per project rules).

---

## 6. Recommended fixes (when the build phase is authorized)

| Pri | Fix |
|---|---|
| HIGH-1 | Scope `/reference/subjects` to `is_global=true` OR caller-tenant rows (mirror `/subjects`). |
| MED-1 | In `/academic-years`, when platform admin has no school context, either require context or guard serialization so a malformed cross-tenant row can't 500 the list. |
| LOW-1 | Consolidate grade dropdowns on a single source; remove the empty `/grade-levels` fallbacks. |
| LOW-2 | Add localized empty state to year/term selectors. |
| LOW-3 | Decide intended breadth of teacher student/teacher selectors; scope to assigned classes if appropriate. |

---

*First pass complete (data + scoping layer). Interactive UI pass and IT/principal coverage pending.*

---

## 7. Resolution log (2026-05-31)

| Finding | Status | Action |
|---|---|---|
| **HIGH-1** `/reference/subjects` cross-tenant leak | ✅ Fixed & verified | Fallback to the tenant-owned `subjects` table is now scoped to the caller's school (platform admin gets the global catalog only, no cross-tenant fan-out). Re-probe: every role now sees only its own 14 subjects, zero foreign tenants. |
| **MED-1** `/academic-years` 500 for platform admin | ✅ Fixed & verified | Per-row serialization is now guarded so one malformed/legacy cross-tenant row can't 500 the list. Same guard applied to `/terms`. Re-probe: platform admin now `200` (n=47), school admin `200` (n=1). |
| **LOW-1** inconsistent grade sources / empty `/grade-levels` | ✅ No change needed | The only direct `/grade-levels` consumer (`TeacherStudentsPage`) is gated to **independent teachers**, whose workspaces *do* populate `grade_levels` — so the source is correct there. No regular-school dropdown depends on the empty result; changing it would break IT. Left as-is intentionally. |
| **LOW-2** empty year/term dropdowns | ✅ No change needed | The term `<Select>`s already render a localized placeholder item (`noTermSelected` / `selectTermPlaceholder`) when empty, and the year/term management views have explicit empty-state cards. No bare/broken popover exists. |
| **LOW-3** teacher can enumerate full school roster | ✅ Fixed (`/students`) & verified | `GET /students` now applies least-privilege for the regular `teacher` role: results are scoped to students in classes actually assigned to the teacher (union of `teacher_assignments` ∪ `teacher_class_assignments` ∪ `class_sessions`, keyed by the auto-linked `teachers.id`); a `class_id` param is intersected with that set; a teacher with no assignments gets `[]`. IT/principal/admin/platform roles are untouched. Regression coverage in `backend/tests/test_students_teacher_class_scope.py` (3 tests: partial-coverage teacher limited, no-assignment teacher empty, school_admin full roster). Both real QA test teachers happen to cover **all** their school's classes, so their live result is unchanged — correct, not a leak. `/teachers` left as-is intentionally: many legitimate teacher-facing consumers, same-tenant only, lower sensitivity. |

