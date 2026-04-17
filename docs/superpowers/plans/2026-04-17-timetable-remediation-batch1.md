# Timetable Remediation — Batch 1: Multi-Tenant / RBAC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every Critical multi-tenant / RBAC hole in the timetable subsystem so that no school can read, generate, publish, archive, delete, or otherwise mutate another school's timetable, constraints, or related data.

**Architecture:** Centralise the tenant/role check in one helper (`assert_school_access`) used by every timetable route. Replace the hand-rolled JWT decode in `principal_timetable_routes` with the standard `get_current_user` dependency. Drop the cross-tenant constraint fallback inside the engine. Extend `TENANT_SCOPED_COLLECTIONS` to cover every timetable-owned table so missing filters log a warning. Add an integration test suite that proves school A cannot touch school B for every fixed endpoint.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy / Motor, pytest. Existing helpers reused: `dependencies.get_current_user`, `dependencies.require_roles`, `middleware.tenant_isolation.TENANT_SCOPED_COLLECTIONS`, `middleware.tenant_isolation.warn_missing_tenant_filter`.

**Source audit:** `docs/audits/2026-04-17-timetable-audit.md` — Batch 1 in §5.

**Findings addressed:** F-API-01 (Critical), F-API-02 (Critical), F-API-03 (High), F-API-04 (Critical), F-API-16 (High), F-EN-06 (Critical), F-CN-06 (Critical), F-XC-01 (High).

---

## File structure

**Create:**
- `backend/utils/tenant_scope.py` — `assert_school_access(current_user, school_id)` and `resolve_school_id(current_user, override)` helpers used by every timetable route.
- `backend/tests/test_tenant_scope_helper.py` — unit tests for the helpers.
- `backend/tests/test_timetable_tenant_isolation.py` — end-to-end cross-tenant denial tests (one test per fixed endpoint).

**Modify:**
- `backend/middleware/tenant_isolation.py` — extend `TENANT_SCOPED_COLLECTIONS`.
- `backend/engines/smart_scheduling_engine.py` — fix constraint loader (F-CN-06) and engine entry (F-EN-06).
- `backend/routes/scheduling_core_routes.py` — fix list/get endpoints (F-API-04).
- `backend/routes/scheduling_smart_engine_routes.py` — fix all `school_id` / `timetable_id` / `X-School-Context` endpoints (F-API-01, F-API-16).
- `backend/routes/principal_timetable_routes.py` — replace hand-rolled JWT decode with standard auth (F-API-02).
- `backend/routes/timetable_readiness_routes.py` — same as above on readiness routes (F-API-03).

**Conventions used by every task:**
- After each implementation step, run the relevant pytest target and paste the result.
- All test code in this plan uses `pytest` + `httpx.AsyncClient` against the existing FastAPI app fixture (see `backend/tests/conftest.py` for the existing pattern).
- **Import root convention:** the existing route files import as `from dependencies import ...` and `from middleware.tenant_isolation import ...` (no `backend.` prefix — verified at `backend/routes/scheduling_core_routes.py:15`, `backend/routes/scheduling_smart_engine_routes.py:15`). All new helper imports added by this plan **must use the same root** to avoid creating duplicate module singletons. Test files, however, follow the existing test convention (`from backend.utils.tenant_scope import ...`) — verify against neighbouring tests in `backend/tests/` and match.
- Skip explicit `git commit` commands — the platform auto-commits per task. Each task is one logical commit.

---

## Task 1: Shared tenant-scope helper (TDD)

**Files:**
- Create: `backend/utils/tenant_scope.py`
- Create: `backend/tests/test_tenant_scope_helper.py`

- [ ] **Step 1: Write the failing tests**

Write `backend/tests/test_tenant_scope_helper.py`:

```python
import pytest
from fastapi import HTTPException
from backend.utils.tenant_scope import assert_school_access, resolve_school_id
from backend.models.enums import UserRole

PRINCIPAL_A = {"role": UserRole.SCHOOL_PRINCIPAL.value, "tenant_id": "school-A", "school_id": "school-A"}
PRINCIPAL_B = {"role": UserRole.SCHOOL_PRINCIPAL.value, "tenant_id": "school-B", "school_id": "school-B"}
PLATFORM_ADMIN = {"role": UserRole.PLATFORM_ADMIN.value, "tenant_id": None, "school_id": None}
TEACHER_A = {"role": UserRole.TEACHER.value, "tenant_id": "school-A", "school_id": "school-A"}


class TestAssertSchoolAccess:
    def test_principal_same_school_allowed(self):
        assert_school_access(PRINCIPAL_A, "school-A")  # no raise

    def test_principal_other_school_denied(self):
        with pytest.raises(HTTPException) as exc:
            assert_school_access(PRINCIPAL_A, "school-B")
        assert exc.value.status_code == 403

    def test_platform_admin_any_school_allowed(self):
        assert_school_access(PLATFORM_ADMIN, "school-A")
        assert_school_access(PLATFORM_ADMIN, "school-B")

    def test_teacher_same_school_allowed_by_default(self):
        assert_school_access(TEACHER_A, "school-A")

    def test_teacher_other_school_denied(self):
        with pytest.raises(HTTPException) as exc:
            assert_school_access(TEACHER_A, "school-B")
        assert exc.value.status_code == 403

    def test_missing_tenant_id_denied(self):
        with pytest.raises(HTTPException) as exc:
            assert_school_access({"role": UserRole.SCHOOL_PRINCIPAL.value}, "school-A")
        assert exc.value.status_code == 403


class TestResolveSchoolId:
    def test_principal_no_override_uses_tenant(self):
        assert resolve_school_id(PRINCIPAL_A, None) == "school-A"

    def test_principal_override_with_own_tenant_allowed(self):
        assert resolve_school_id(PRINCIPAL_A, "school-A") == "school-A"

    def test_principal_override_with_other_tenant_denied(self):
        with pytest.raises(HTTPException) as exc:
            resolve_school_id(PRINCIPAL_A, "school-B")
        assert exc.value.status_code == 403

    def test_platform_admin_override_allowed(self):
        assert resolve_school_id(PLATFORM_ADMIN, "school-X") == "school-X"

    def test_platform_admin_no_override_returns_none(self):
        assert resolve_school_id(PLATFORM_ADMIN, None) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_tenant_scope_helper.py -v`
Expected: FAIL with `ModuleNotFoundError: backend.utils.tenant_scope`.

- [ ] **Step 3: Implement the helper**

Write `backend/utils/tenant_scope.py` (note the import root — `backend/` is already on `sys.path` per existing convention; do **not** prefix with `backend.`):

```python
from typing import Optional

from fastapi import HTTPException, status

from models.enums import UserRole  # backend/ is on sys.path; matches existing convention


def _is_platform_admin(current_user: dict) -> bool:
    return current_user.get("role") == UserRole.PLATFORM_ADMIN.value


def assert_school_access(current_user: dict, school_id: str) -> None:
    """Raise 403 unless the caller belongs to school_id (or is platform admin).

    The single authoritative tenant guard for every timetable route.
    """
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="school_id is required",
        )
    if _is_platform_admin(current_user):
        return
    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    if not user_tenant or str(user_tenant) != str(school_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: school does not match caller's tenant",
        )


def resolve_school_id(current_user: dict, override: Optional[str]) -> Optional[str]:
    """Decide which school_id a request should operate on.

    Non-admins always operate on their own tenant; an override that
    matches their tenant is OK, an override that doesn't match is 403.
    Platform admins may override freely; with no override they get None
    (caller decides whether to require one).
    """
    if _is_platform_admin(current_user):
        return override  # may be None — caller decides
    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    if override is not None and str(override) != str(user_tenant):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: school does not match caller's tenant",
        )
    if not user_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: caller has no tenant",
        )
    return str(user_tenant)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_tenant_scope_helper.py -v`
Expected: 11 tests pass.

---

## Task 2: Extend TENANT_SCOPED_COLLECTIONS (F-XC-01)

**Files:**
- Modify: `backend/middleware/tenant_isolation.py:278-282`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_tenant_scope_helper.py`:

```python
def test_tenant_scoped_collections_includes_timetable_tables():
    from backend.middleware.tenant_isolation import TENANT_SCOPED_COLLECTIONS
    required = {
        "timetables",
        "schedule_sessions",
        "timetable_sessions",
        "time_slots",
        "teacher_assignments",
        "timetable_constraints",
        "school_constraints",
        "administrative_constraints",
        "constraint_patterns",
    }
    missing = required - TENANT_SCOPED_COLLECTIONS
    assert not missing, f"Missing timetable tables in tripwire: {missing}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_tenant_scope_helper.py::test_tenant_scoped_collections_includes_timetable_tables -v`
Expected: FAIL with `Missing timetable tables in tripwire: {...all nine...}`.

- [ ] **Step 3: Extend the frozenset**

Open `backend/middleware/tenant_isolation.py:278-282` and replace the `TENANT_SCOPED_COLLECTIONS` frozenset definition with the existing entries plus:

```python
TENANT_SCOPED_COLLECTIONS = frozenset({
    # ... keep the existing entries (students, teachers, classes, subjects,
    #     attendance, teacher_attendance, schedules, grades, behaviour_records,
    #     events, notifications, registration_requests) ...
    "timetables",
    "schedule_sessions",
    "timetable_sessions",
    "time_slots",
    "teacher_assignments",
    "timetable_constraints",
    "school_constraints",
    "administrative_constraints",
    "admin_constraints",
    "constraint_patterns",
})
```

Add the ten new entries to the existing set; do not remove any existing entries. (`admin_constraints` and `administrative_constraints` are two distinct collections in the codebase — verified at `smart_scheduling_engine.py:444` vs `:1936` — both must be listed.) Update the test in Step 1 to include `"admin_constraints"` in the `required` set.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_tenant_scope_helper.py::test_tenant_scoped_collections_includes_timetable_tables -v`
Expected: PASS.

---

## Task 3: Fix engine constraint loader cross-tenant fallback (F-CN-06)

**Files:**
- Modify: `backend/engines/smart_scheduling_engine.py:1934-1938` (constraint loader inside `_load_constraints` or its caller around line 1927-1946)
- Modify: `backend/engines/smart_scheduling_engine.py:442-444` (readiness summary fallback — same bug)

- [ ] **Step 1: Read current code at both locations**

Run:
```bash
sed -n '1920,1950p' backend/engines/smart_scheduling_engine.py
sed -n '435,455p'   backend/engines/smart_scheduling_engine.py
```
Confirm both blocks contain the pattern `if not constraints: constraints = await gd_find(self.session, "administrative_constraints", {"is_active": True}, ...)`.

- [ ] **Step 2: Write the failing test**

Append to `backend/tests/test_timetable_tenant_isolation.py` (create file if it does not exist with the standard pytest async setup found in `backend/tests/test_smart_scheduling.py`):

```python
import pytest
from backend.engines.smart_scheduling_engine import SmartSchedulingEngine

@pytest.mark.asyncio
async def test_engine_does_not_fall_back_to_global_constraints(
    db_session, school_a_id, school_b_id, seed_global_admin_constraint, seed_school_b_constraint
):
    """If school A has no school_constraints, engine must NOT pull global
    administrative_constraints (which would leak school B's rule)."""
    engine = SmartSchedulingEngine(session=db_session)
    constraints = await engine._load_constraints_for_school(school_a_id)
    # Either empty or only school A's own rows — never global, never school B's.
    for c in constraints:
        assert c.get("school_id") == school_a_id, (
            f"Cross-tenant leak: constraint {c.get('id')} belongs to "
            f"{c.get('school_id')}, not {school_a_id}"
        )
```

(The fixtures `db_session`, `school_a_id`, `school_b_id`, `seed_global_admin_constraint`, `seed_school_b_constraint` should be added to `backend/tests/conftest.py` following the pattern of the existing `test_smart_scheduling.py` fixtures. If any fixture is missing, copy the closest existing fixture and adapt.)

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest backend/tests/test_timetable_tenant_isolation.py::test_engine_does_not_fall_back_to_global_constraints -v`
Expected: FAIL — the leaked constraint surfaces.

- [ ] **Step 4: Patch the constraint loader at line 1934-1938**

Replace the fallback block. Original pattern:

```python
constraints = await gd_find(self.session, "school_constraints", {"school_id": school_id, "is_active": True}, limit=50)
if not constraints:
    constraints = await gd_find(self.session, "administrative_constraints", {"is_active": True}, limit=50)
```

Change to:

```python
constraints = await gd_find(
    self.session,
    "school_constraints",
    {"school_id": school_id, "is_active": True},
    limit=50,
)
if not constraints:
    constraints = await gd_find(
        self.session,
        "administrative_constraints",
        {"school_id": school_id, "is_active": True},
        limit=50,
    )
```

- [ ] **Step 5: Patch the readiness summary fallback at line 442-444**

**Note:** the readiness path uses a *different* collection name than the generation path. Verified at `backend/engines/smart_scheduling_engine.py:444`: the readiness fallback queries `admin_constraints` (singular `admin_`), not `administrative_constraints`. Patch the existing block exactly:

```python
constraints_count = await gd_count(
    self.session,
    "school_constraints",
    {"school_id": school_id, "is_active": True},
)
if constraints_count == 0:
    constraints_count = await gd_count(
        self.session,
        "admin_constraints",
        {"school_id": school_id, "is_active": True},
    )
```

(Add the `school_id` filter; preserve the `admin_constraints` collection name. Also add `admin_constraints` to the `TENANT_SCOPED_COLLECTIONS` set in Task 2 if it's not already covered by `administrative_constraints` — these are two different tables according to the codebase usage. Re-run Task 2's test after adding it.)

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest backend/tests/test_timetable_tenant_isolation.py::test_engine_does_not_fall_back_to_global_constraints -v`
Expected: PASS.

- [ ] **Step 7: Run the existing scheduling tests to verify no regression**

Run: `pytest backend/tests/test_smart_scheduling.py backend/tests/test_smart_timetable_page.py -v`
Expected: all previously-passing tests still pass. If a test relied on the global fallback, update it to seed a school-scoped constraint instead.

---

## Task 4: Engine entry asserts tenant (F-EN-06)

**Files:**
- Modify: `backend/engines/smart_scheduling_engine.py:1927-1936` (engine entry — add tenant assertion against caller-provided context)

- [ ] **Step 1: Add an assertion at the engine entry**

Locate the public engine entry that accepts `school_id` (around line 1927-1946 — the method that loads constraints and starts a generation). Add at the top:

```python
def _assert_tenant(self, school_id: str, calling_user: Optional[dict]) -> None:
    """Defence in depth — engine refuses to operate on a school the
    caller does not belong to. Routes also enforce this; this is the
    second wall."""
    if calling_user is None:
        return  # internal callers (background jobs, tests) pass None
    from backend.utils.tenant_scope import assert_school_access
    assert_school_access(calling_user, school_id)
```

Add a `calling_user: Optional[dict] = None` keyword argument to the public generation entry method (whichever of `generate_timetable`, `generate_smart_timetable`, etc. is exposed to routes) and call `self._assert_tenant(school_id, calling_user)` as the first statement.

- [ ] **Step 2: Update routes that call the engine to pass `current_user`**

In `backend/routes/scheduling_smart_engine_routes.py` and `backend/routes/scheduling_generation_routes.py`, every place that instantiates `SmartSchedulingEngine(...)` and calls its generation entry must pass `calling_user=current_user`. (Routes themselves are fixed in Task 6 — this step only updates the call signatures so the engine assertion has data to check.)

- [ ] **Step 3: Add a unit test**

Append to `backend/tests/test_timetable_tenant_isolation.py`:

```python
@pytest.mark.asyncio
async def test_engine_refuses_cross_tenant_generation(
    db_session, school_a_id, school_b_id, principal_a_user
):
    engine = SmartSchedulingEngine(session=db_session)
    with pytest.raises(HTTPException) as exc:
        await engine.generate_timetable(
            school_id=school_b_id,
            calling_user=principal_a_user,
        )
    assert exc.value.status_code == 403
```

(Replace `engine.generate_timetable` with whatever the actual public entry name is.)

- [ ] **Step 4: Run the new test**

Run: `pytest backend/tests/test_timetable_tenant_isolation.py::test_engine_refuses_cross_tenant_generation -v`
Expected: PASS.

---

## Task 5: Fix scheduling_core_routes list/get endpoints (F-API-04)

**Files:**
- Modify: `backend/routes/scheduling_core_routes.py:59-71`, `:196-215`, `:350-367`, `:465-512`

- [ ] **Step 1: Write integration tests for cross-tenant denial**

Append to `backend/tests/test_timetable_tenant_isolation.py`:

```python
@pytest.mark.asyncio
async def test_get_time_slots_rejects_other_school(
    async_client, principal_a_token, school_b_id
):
    r = await async_client.get(
        f"/api/scheduling/time-slots?school_id={school_b_id}",
        headers={"Authorization": f"Bearer {principal_a_token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_teacher_assignments_rejects_other_school(
    async_client, principal_a_token, school_b_id
):
    r = await async_client.get(
        f"/api/scheduling/teacher-assignments?school_id={school_b_id}",
        headers={"Authorization": f"Bearer {principal_a_token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_schedules_rejects_other_school(
    async_client, principal_a_token, school_b_id
):
    r = await async_client.get(
        f"/api/scheduling/schedules?school_id={school_b_id}",
        headers={"Authorization": f"Bearer {principal_a_token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_schedule_sessions_rejects_other_school_schedule(
    async_client, principal_a_token, school_b_schedule_id
):
    """schedule-sessions takes a `schedule_id` (not `school_id`); the
    cross-tenant attack vector is passing another school's schedule_id
    (IDOR). Resource-based check required."""
    r = await async_client.get(
        f"/api/scheduling/schedule-sessions?schedule_id={school_b_schedule_id}",
        headers={"Authorization": f"Bearer {principal_a_token}"},
    )
    assert r.status_code == 403
```

(Adjust path prefix to match the actual router prefix used in `backend/routes/scheduling_core_routes.py`. Inspect the file's `APIRouter(prefix="...")` line.)

Add a `school_b_schedule_id` fixture in `conftest.py` that inserts a `schedules` row with `school_id=school_b_id` and returns its `id`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_timetable_tenant_isolation.py -k "rejects_other_school" -v`
Expected: 4 FAIL — endpoints currently return 200 with leaked data.

- [ ] **Step 3: Patch each endpoint**

**Two patches required, depending on the endpoint signature:**

**(a) `/time-slots`, `/teacher-assignments`, `/schedules` — these accept `school_id` as a query param.** Replace the unsafe pattern:

```python
if school_id:
    query["school_id"] = school_id
elif current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
    query["school_id"] = current_user.get("tenant_id")
```

with:

```python
from utils.tenant_scope import resolve_school_id  # match existing import root (no `backend.` prefix)
resolved = resolve_school_id(current_user, school_id)
if resolved is not None:
    query["school_id"] = resolved
```

**(b) `/schedule-sessions` — verified at `backend/routes/scheduling_core_routes.py:465+`, this handler takes `schedule_id` (required) and has *no* `school_id` parameter at all.** This is an IDOR: any authenticated user passing another school's `schedule_id` gets that school's sessions. Patch with a resource-based check:

```python
from utils.tenant_scope import assert_school_access

@router.get("/schedule-sessions", response_model=List[ScheduleSessionResponse])
async def get_schedule_sessions(
    schedule_id: str,
    day_of_week: Optional[str] = None,
    teacher_id: Optional[str] = None,
    class_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    schedule = await gd_find_one(db.session, "schedules", {"id": schedule_id})
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    assert_school_access(current_user, str(schedule.get("school_id")))
    query = {"schedule_id": schedule_id}
    # ... rest unchanged ...
```

(Insert the fetch + assert as the first two statements of the handler — before any other DB work.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_timetable_tenant_isolation.py -k "rejects_other_school" -v`
Expected: 4 PASS.

- [ ] **Step 5: Run the broader scheduling tests for regressions**

Run: `pytest backend/tests/test_scheduling_api.py -v`
Expected: all previously-passing tests still pass. If a test was passing because of the bug (sending `school_id` of another tenant), update it to send the principal's own `school_id`.

---

## Task 6: Fix scheduling_smart_engine_routes (F-API-01, F-API-16)

**Files:**
- Modify: `backend/routes/scheduling_smart_engine_routes.py` — every endpoint listed in F-API-01 and F-API-16.

  Endpoints to fix (lines from F-API-01 + the body/header-based generator at `:147+`):
  - `:83-110` `/smart-scheduling/validate/{school_id}`
  - `:114-143` `/smart-scheduling/generate/{school_id}`
  - `:147+` `/timetable/generate-smart` — **body/header-based, missed by audit's F-API-01 line list**; verified at `backend/routes/scheduling_smart_engine_routes.py:147` to read `school_id` from body or `X-School-Context` then call `smart_scheduling_engine.generate_timetable` with no tenant check. Same vulnerability class as F-API-01; treat as part of this batch.
  - `:194-209` `/smart-scheduling/timetables/{school_id}`
  - `:213-255` `/smart-scheduling/timetable/versions` (header-based — F-API-16)
  - `:258-318` `/active/sessions` (header-based — F-API-16; verify the actual route path — file uses `APIRouter(prefix="/smart-scheduling")` so the path may be `/smart-scheduling/active/sessions` or similar — match exactly when writing the test)
  - `:321-335` `/smart-scheduling/timetable/{timetable_id}`
  - `:338-379` `/smart-scheduling/timetable/{timetable_id}/sessions`
  - `:382-400` `/smart-scheduling/timetable/{timetable_id}/conflicts`
  - `:422-448` `/smart-scheduling/timetable/{timetable_id}/publish`
  - `:451-474` archive
  - `:477-511` pre-check
  - `:514-587` demand & resource matrices
  - `:590-625` delete

- [ ] **Step 1: Write failing integration tests (one per endpoint pattern)**

Append to `backend/tests/test_timetable_tenant_isolation.py`. For brevity, use a parameterised test where the path is the only variable.

```python
import pytest

@pytest.mark.parametrize("method,path_template", [
    ("GET",  "/api/smart-scheduling/validate/{school_id}"),
    ("POST", "/api/smart-scheduling/generate/{school_id}"),
    ("GET",  "/api/smart-scheduling/timetables/{school_id}"),
    ("GET",  "/api/smart-scheduling/timetable/{timetable_id}"),
    ("GET",  "/api/smart-scheduling/timetable/{timetable_id}/sessions"),
    ("GET",  "/api/smart-scheduling/timetable/{timetable_id}/conflicts"),
    ("POST", "/api/smart-scheduling/timetable/{timetable_id}/publish"),
    ("POST", "/api/smart-scheduling/timetable/{timetable_id}/archive"),
    ("POST", "/api/smart-scheduling/pre-check/{school_id}"),
    ("GET",  "/api/smart-scheduling/demand-matrix/{school_id}"),
    ("GET",  "/api/smart-scheduling/resource-matrix/{school_id}"),
    ("DELETE", "/api/smart-scheduling/timetable/{timetable_id}"),
])
# Note: /timetable/generate-smart is body-based, tested separately below.
@pytest.mark.asyncio
async def test_smart_engine_endpoints_reject_other_school(
    async_client, principal_a_token,
    school_b_id, school_b_timetable_id,
    method, path_template,
):
    path = path_template.format(school_id=school_b_id, timetable_id=school_b_timetable_id)
    r = await async_client.request(
        method, path,
        headers={"Authorization": f"Bearer {principal_a_token}"},
    )
    assert r.status_code == 403, (
        f"{method} {path} should deny cross-tenant; got {r.status_code} {r.text}"
    )


@pytest.mark.parametrize("path", [
    "/api/smart-scheduling/timetable/versions",
    "/api/smart-scheduling/active/sessions",
])
@pytest.mark.asyncio
async def test_smart_engine_header_endpoints_reject_other_school(
    async_client, principal_a_token, school_b_id, path,
):
    r = await async_client.get(
        path,
        headers={
            "Authorization": f"Bearer {principal_a_token}",
            "X-School-Context": school_b_id,
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_generate_smart_rejects_other_school_in_body(
    async_client, principal_a_token, school_b_id,
):
    """`POST /timetable/generate-smart` reads school_id from body — verify
    a principal of A cannot pass school B's id and trigger generation."""
    r = await async_client.post(
        "/api/smart-scheduling/timetable/generate-smart",
        headers={"Authorization": f"Bearer {principal_a_token}"},
        json={"school_id": school_b_id},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_generate_smart_rejects_other_school_in_header(
    async_client, principal_a_token, school_b_id,
):
    r = await async_client.post(
        "/api/smart-scheduling/timetable/generate-smart",
        headers={
            "Authorization": f"Bearer {principal_a_token}",
            "X-School-Context": school_b_id,
        },
        json={},
    )
    assert r.status_code == 403
```

(Adjust paths to match the actual `APIRouter(prefix=...)` in the file. Add a `school_b_timetable_id` fixture in `conftest.py` that creates a timetable belonging to school B.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_timetable_tenant_isolation.py -k smart_engine -v`
Expected: all FAIL.

- [ ] **Step 3: Patch each `school_id`-bearing endpoint**

At the top of every handler that has `school_id: UUID = Path(...)` or `school_id: str = Path(...)`, add:

```python
from backend.utils.tenant_scope import assert_school_access
# ...
assert_school_access(current_user, str(school_id))
```

Ensure `current_user: dict = Depends(get_current_user)` is in the signature (it already should be — verify).

- [ ] **Step 4: Patch each `timetable_id`-bearing endpoint**

Pattern (insert near the top of each handler, after fetching the timetable):

```python
timetable = await get_timetable_or_404(session, timetable_id)
assert_school_access(current_user, str(timetable["school_id"]))
```

Use whatever fetch function the file already uses; if it does the fetch later, hoist it to the top so the tenant check runs before any work.

- [ ] **Step 5: Patch the header-based endpoints (F-API-16)**

For `/smart-scheduling/timetable/versions` and `/active/sessions`, replace the `x_school_context` resolution block with:

```python
from utils.tenant_scope import resolve_school_id
resolved = resolve_school_id(current_user, x_school_context)
if resolved is None:
    raise HTTPException(400, "school_id is required")
school_id = resolved
```

- [ ] **Step 5b: Patch `/timetable/generate-smart` (body + header-based)**

In `backend/routes/scheduling_smart_engine_routes.py:147+` (`generate_timetable_smart`), the current code does:

```python
school_id = body.get("school_id")
if not school_id:
    school_id = request.headers.get("X-School-Context") or current_user.get("tenant_id")
```

Replace with:

```python
from utils.tenant_scope import resolve_school_id
override = body.get("school_id") or request.headers.get("X-School-Context")
school_id = resolve_school_id(current_user, override)
if not school_id:
    raise HTTPException(status_code=400, detail="school_id مطلوب")
```

Also pass `calling_user=current_user` to `smart_scheduling_engine.generate_timetable(...)` (defence-in-depth from Task 4).

Note: this endpoint currently has **no role gate** — also add `Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))` to its dependencies, matching the role policy of the path-based `/smart-scheduling/generate/{school_id}` endpoint.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest backend/tests/test_timetable_tenant_isolation.py -k smart_engine -v`
Expected: all PASS.

- [ ] **Step 7: Regression check**

Run: `pytest backend/tests/test_smart_scheduling.py backend/tests/test_smart_timetable_page.py backend/tests/test_scheduling_smart_engine.py -v`
Expected: all previously-passing tests still pass.

---

## Task 7: Fix principal_timetable_routes — replace hand-rolled JWT (F-API-02)

**Files:**
- Modify: `backend/routes/principal_timetable_routes.py:171-190` (replace `get_school_id`)
- Modify: every `@router.*` handler in the file (signatures + tenant assertion)

- [ ] **Step 1: Write failing integration tests**

Append to `backend/tests/test_timetable_tenant_isolation.py`:

```python
@pytest.mark.parametrize("method,path,body", [
    # Reads
    ("GET",  "/api/principal/timetable/summary", None),
    ("GET",  "/api/principal/timetable/readiness", None),
    ("GET",  "/api/principal/timetable/versions", None),
    ("GET",  "/api/principal/timetable/grid", None),
    # High-risk mutations (audit F-API-02 — these MUST be teacher-denied)
    ("POST", "/api/principal/timetable/generate", {}),
    ("POST", "/api/principal/timetable/version/{vid}/publish", {}),
    ("POST", "/api/principal/timetable/version/{vid}/fill-gaps", {}),
    ("POST", "/api/principal/timetable/sessions/swap", {"session_a_id": "x", "session_b_id": "y"}),
    ("POST", "/api/principal/timetable/sessions/move", {"session_id": "x", "target_slot_id": "y"}),
    ("DELETE", "/api/principal/timetable/session/{sid}", None),
])
@pytest.mark.asyncio
async def test_principal_timetable_rejects_teacher(
    async_client, teacher_a_token, school_a_id, school_a_version_id, school_a_session_id,
    method, path, body,
):
    """A teacher must NOT be able to call principal-only endpoints
    even for their own school."""
    path = path.format(vid=school_a_version_id, sid=school_a_session_id)
    r = await async_client.request(
        method, path,
        headers={
            "Authorization": f"Bearer {teacher_a_token}",
            "X-School-Context": school_a_id,
        },
        json=body,
    )
    assert r.status_code in (401, 403), (
        f"{method} {path} accepted a teacher token; got {r.status_code}"
    )


@pytest.mark.asyncio
async def test_principal_timetable_rejects_other_school_header(
    async_client, principal_a_token, school_b_id,
):
    """Principal of school A passing X-School-Context: school-B must be 403."""
    r = await async_client.get(
        "/api/principal/timetable/summary",
        headers={
            "Authorization": f"Bearer {principal_a_token}",
            "X-School-Context": school_b_id,
        },
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_timetable_tenant_isolation.py -k principal_timetable -v`
Expected: all FAIL.

- [ ] **Step 3: Replace `get_school_id` with the standard auth pattern**

At lines 171-190, delete the hand-rolled `get_school_id` function and the module-level `_JWT_SECRET`. Replace with:

```python
from backend.dependencies import get_current_user, require_roles
from backend.models.enums import UserRole
from backend.utils.tenant_scope import resolve_school_id

PRINCIPAL_ROLES = [UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL]

async def principal_school_id(
    x_school_context: Optional[str] = Header(None, alias="X-School-Context"),
    current_user: dict = Depends(require_roles(PRINCIPAL_ROLES)),
) -> str:
    """Resolve the school_id this request operates on, with full RBAC.

    - PLATFORM_ADMIN: must pass X-School-Context (any school).
    - SCHOOL_PRINCIPAL: ignores X-School-Context unless it matches their tenant.
    """
    resolved = resolve_school_id(current_user, x_school_context)
    if resolved is None:
        raise HTTPException(400, "X-School-Context header is required for platform admin")
    return resolved
```

- [ ] **Step 4: Update every handler signature**

For every `@router.get/post/put/delete/patch` decorator in the file, change the signature from whatever it was (typically `school_id: str = Depends(get_school_id)`) to:

```python
school_id: str = Depends(principal_school_id),
current_user: dict = Depends(get_current_user),
```

If a handler also performs writes (generate, publish, archive, swap, move, fill-gaps, delete, session manipulation), the existing `Depends(principal_school_id)` already enforces the role; no extra `require_roles` is needed.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest backend/tests/test_timetable_tenant_isolation.py -k principal_timetable -v`
Expected: all PASS.

- [ ] **Step 6: Regression check**

Run: `pytest backend/tests/test_principal_timetable_page_iter81.py backend/tests/test_smart_timetable_page.py -v`
Expected: all previously-passing tests still pass. If existing tests were passing because they bypassed auth, update them to use the standard token fixtures.

---

## Task 8: Fix timetable_readiness_routes (F-API-03)

**Files:**
- Modify: `backend/routes/timetable_readiness_routes.py:22-23` (drop `_JWT_SECRET`)
- Modify: `backend/routes/timetable_readiness_routes.py:102-118` (replace `_extract_school_id`)
- Modify: `backend/routes/timetable_readiness_routes.py:496-506` and `:507-539` (handler signatures)

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_timetable_tenant_isolation.py`:

```python
@pytest.mark.parametrize("path", [
    "/api/timetable-readiness/check",
    "/api/timetable-readiness/summary",
])
@pytest.mark.asyncio
async def test_readiness_rejects_other_school_header(
    async_client, principal_a_token, school_b_id, path,
):
    r = await async_client.get(
        path,
        headers={
            "Authorization": f"Bearer {principal_a_token}",
            "X-School-Context": school_b_id,
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_readiness_rejects_unauthenticated(async_client):
    r = await async_client.get("/api/timetable-readiness/check")
    assert r.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_timetable_tenant_isolation.py -k readiness -v`
Expected: 3 FAIL.

- [ ] **Step 3: Patch the file**

Delete `_JWT_SECRET` at lines 22-23. Delete `_extract_school_id` at lines 102-118. Add at the top:

```python
from backend.dependencies import get_current_user
from backend.utils.tenant_scope import resolve_school_id

async def readiness_school_id(
    x_school_context: Optional[str] = Header(None, alias="X-School-Context"),
    current_user: dict = Depends(get_current_user),
) -> str:
    resolved = resolve_school_id(current_user, x_school_context)
    if resolved is None:
        raise HTTPException(400, "X-School-Context header is required for platform admin")
    return resolved
```

Update the two handler signatures (`:496-506` and `:507-539`) to take `school_id: str = Depends(readiness_school_id)` instead of calling the deleted helper.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_timetable_tenant_isolation.py -k readiness -v`
Expected: 3 PASS.

- [ ] **Step 5: Regression check**

Run: `pytest backend/tests/test_timetable_readiness.py -v`
Expected: all previously-passing tests still pass.

---

## Task 9: Final integration sweep

**Files:**
- No code changes; verification only.

- [ ] **Step 1: Run the full tenant-isolation suite**

Run: `pytest backend/tests/test_timetable_tenant_isolation.py -v`
Expected: every test passes (helpers + per-endpoint denials + engine assertion + constraint loader).

- [ ] **Step 2: Run the broader timetable test suite**

Run:
```bash
pytest \
  backend/tests/test_smart_scheduling.py \
  backend/tests/test_smart_timetable_page.py \
  backend/tests/test_scheduling_api.py \
  backend/tests/test_scheduling_smart_engine.py \
  backend/tests/test_principal_timetable_page_iter81.py \
  backend/tests/test_timetable_readiness.py \
  backend/tests/test_settings_edit_constraints.py \
  -v
```
Expected: no regressions versus baseline (note: baseline test pass-count should be captured before starting Task 1; if a previously-passing test now fails, decide whether the test was passing because of the bug — in which case update the test — or whether the fix is wrong — in which case fix the code).

- [ ] **Step 3: Smoke-test the running app**

Restart the `Backend API` workflow. Manually exercise as a principal of one school: log in, view timetable, generate a draft, publish. Then attempt to access another school's timetable by changing the `X-School-Context` header (use browser devtools or curl). Confirm a 403 response.

- [ ] **Step 4: Mark the audit findings as remediated**

Append a "Status: Remediated 2026-04-17 (Batch 1 plan)" line to each addressed finding in `docs/audits/2026-04-17-timetable-audit.md` (F-API-01, F-API-02, F-API-03, F-API-04, F-API-16, F-EN-06, F-CN-06, F-XC-01) — single-line annotation under the existing `**Effort:**` line. Do not delete or rewrite the original finding text.

---

## Self-review

- [x] **Spec coverage:** Every Batch 1 finding in audit §5 has a task. F-API-01 → Task 6. F-API-02 → Task 7. F-API-03 → Task 8. F-API-04 → Task 5. F-API-16 → Task 6. F-EN-06 → Task 4. F-CN-06 → Task 3. F-XC-01 → Task 2. Helpers in Task 1 unblock everything.
- [x] **No placeholders:** Every step has either concrete code, a concrete command, or a concrete file:line patch description. Test fixture details defer to existing `conftest.py` patterns — explicit in the plan.
- [x] **Type/name consistency:** `assert_school_access(current_user, school_id)` and `resolve_school_id(current_user, override)` are defined in Task 1 and used unchanged in Tasks 4–8. `principal_school_id` and `readiness_school_id` are local to their respective route files. `TENANT_SCOPED_COLLECTIONS` extension list in Task 2 matches the names referenced in F-XC-01.
- [x] **Out-of-scope respected:** No findings outside Batch 1 are touched. Engine algorithm, frontend, seeds, data model uniqueness, etc. are deliberately deferred to later batch plans.
