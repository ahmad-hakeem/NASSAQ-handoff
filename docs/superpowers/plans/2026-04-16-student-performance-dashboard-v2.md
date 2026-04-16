# Student Performance Analytics Dashboard v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the "تحليل أداء الطلاب" tab inside `AIInsightsPage` — executive KPIs, risk scatter map, intervention list with 3 real actions, root-cause pie chart aligned with Hakim's 4 factors, and OpenAI-backed Arabic recommendations — by extending existing AI endpoints and unifying on `HakimAIEngine`.

**Architecture:** Backend adds `analyze_students_risk_batch` to `HakimAIEngine` and three new endpoints (`students-overview`, `recommendations-ai`, `intervention`) in `ai_routes_mod.py`. Legacy `at-risk-students` becomes a thin wrapper over the new overview and gains an RBAC gate. Frontend adds a Radix Tabs wrapper to `AIInsightsPage.jsx` and seven new components under `frontend/src/components/student-performance/`, lazy-loaded behind a role check.

**Tech Stack:** FastAPI + SQLAlchemy-backed GenericDocument (`gd_*` helpers) · React 18 + Radix UI + Recharts · i18next (ar/en) · OpenAI (via existing Hakim chat client) · pytest + React Testing Library.

**Spec:** `docs/superpowers/specs/2026-04-16-student-performance-dashboard-v2-design.md`

---

## File Map

**Modified:**
- `backend/engines/hakim_ai_engine.py` — add batch helper; refactor private calc helpers to accept pre-fetched data.
- `backend/routes/ai_routes_mod.py` — 3 new endpoints; refactor existing `at-risk-students` into wrapper + add RBAC gate.
- `frontend/src/pages/AIInsightsPage.jsx` — add Radix Tabs; role gate; lazy-load the new tab content.
- `frontend/src/locales/ar.json`, `frontend/src/locales/en.json` — new i18n keys.

**New:**
- `backend/tests/conftest.py` (if absent) — async httpx client + role/tenant fixtures used by every test in this plan
- `backend/tests/test_student_performance_rbac.py`
- `backend/tests/test_students_overview.py`
- `backend/tests/test_intervention_endpoint.py`
- `backend/tests/test_hakim_batch_risk.py`
- `frontend/src/components/student-performance/StudentPerformanceDashboard.jsx`
- `frontend/src/components/student-performance/ExecutiveSummaryCards.jsx`
- `frontend/src/components/student-performance/StudentRiskMap.jsx`
- `frontend/src/components/student-performance/InterventionList.jsx`
- `frontend/src/components/student-performance/InterventionActionModal.jsx`
- `frontend/src/components/student-performance/RootCauseChart.jsx`
- `frontend/src/components/student-performance/HakimRecommendations.jsx`

**Conventions reused:**
- RBAC: `from dependencies import require_roles, UserRole` and use `Depends(require_roles([...]))`.
- DB helpers: `gd_find`, `gd_find_one`, `gd_insert`, `gd_count`, `_gd_aggregate` from the `ai_routes_mod` top imports.
- Notifications: `create_notification_internal` from `routes.notification_routes_mod`.
- Tenant isolation: `school_id = current_user["tenant_id"]` on every query.

---

## Task 0 — Test fixtures bootstrap

No repo-level `conftest.py` exists today; every later task assumes these fixtures. Create once, reuse everywhere. Keep this task small and orthogonal — it is a prerequisite, not a feature.

**Files:**
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Implement fixtures**

```python
# backend/tests/conftest.py
import os, uuid, pytest, pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("TESTING", "1")

from app.main import app
from db import db
from engines.sql_utils import gd_insert
from dependencies import UserRole, create_access_token  # adjust import if token helper lives elsewhere

async def _mk_user(role: UserRole, tenant_id: str):
    uid = str(uuid.uuid4())
    user = {"id": uid, "role": role.value, "tenant_id": tenant_id,
            "email": f"{uid}@t.test", "full_name": f"{role.value} user", "is_active": True}
    await gd_insert(db.session, "users", user)
    return user

def _headers(user: dict) -> dict:
    token = create_access_token({"sub": user["id"], "role": user["role"],
                                 "tenant_id": user["tenant_id"]})
    return {"Authorization": f"Bearer {token}"}

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest_asyncio.fixture
async def tenant_a():
    return str(uuid.uuid4())

@pytest_asyncio.fixture
async def tenant_b():
    return str(uuid.uuid4())

@pytest_asyncio.fixture
async def school_admin_headers(tenant_a):
    return _headers(await _mk_user(UserRole.SCHOOL_ADMIN, tenant_a))

@pytest_asyncio.fixture
async def school_sub_admin_headers(tenant_a):
    return _headers(await _mk_user(UserRole.SCHOOL_SUB_ADMIN, tenant_a))

@pytest_asyncio.fixture
async def school_principal_headers(tenant_a):
    return _headers(await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a))

@pytest_asyncio.fixture
async def teacher_headers(tenant_a):
    return _headers(await _mk_user(UserRole.TEACHER, tenant_a))

@pytest_asyncio.fixture
async def parent_headers(tenant_a):
    return _headers(await _mk_user(UserRole.PARENT, tenant_a))

@pytest_asyncio.fixture
async def student_headers(tenant_a):
    return _headers(await _mk_user(UserRole.STUDENT, tenant_a))

@pytest_asyncio.fixture
async def platform_admin_headers():
    return _headers(await _mk_user(UserRole.PLATFORM_ADMIN, str(uuid.uuid4())))

@pytest_asyncio.fixture
async def tenant_a_admin(school_admin_headers):
    return school_admin_headers

async def _seed_student(school_id: str, with_parent: bool = True, class_id: str | None = None):
    parent_id = str(uuid.uuid4()) if with_parent else None
    if parent_id:
        await gd_insert(db.session, "users",
                        {"id": parent_id, "role": "parent", "tenant_id": school_id,
                         "email": f"p-{parent_id}@t.test", "is_active": True})
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students",
                    {"id": sid, "school_id": school_id, "full_name": f"ST-{sid[:6]}",
                     "class_id": class_id, "parent_id": parent_id, "is_active": True})
    return {"id": sid, "school_id": school_id, "parent_id": parent_id}

@pytest_asyncio.fixture
async def seeded_school(tenant_a):
    students = []
    cls = str(uuid.uuid4())
    await gd_insert(db.session, "classes",
                    {"id": cls, "school_id": tenant_a, "name": "1A"})
    for _ in range(10):
        students.append(await _seed_student(tenant_a, True, cls))
    class _S:
        id = tenant_a
        db = db
        students = students
    return _S()

@pytest_asyncio.fixture
async def many_students_school(tenant_a):
    cls = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {"id": cls, "school_id": tenant_a, "name": "Big"})
    students = [await _seed_student(tenant_a, True, cls) for _ in range(120)]
    class _S: id = tenant_a; students = students
    return _S()

@pytest_asyncio.fixture
async def tenant_b_students(tenant_b):
    return [await _seed_student(tenant_b, True) for _ in range(3)]

@pytest_asyncio.fixture
async def tenant_b_student(tenant_b_students):
    return tenant_b_students[0]

@pytest_asyncio.fixture
async def a_student(tenant_a):
    return await _seed_student(tenant_a, True)

@pytest_asyncio.fixture
async def student_with_parent(tenant_a):
    return await _seed_student(tenant_a, True)

@pytest_asyncio.fixture
async def orphan_student(tenant_a):
    return await _seed_student(tenant_a, with_parent=False)
```

- [ ] **Step 2: Verify collection and token helpers match the codebase**

Before running tests, confirm `create_access_token` exists in `backend/dependencies.py` (or adjust import to the real module, e.g. `app.auth`). Confirm `db.session` is the shared async session used by `gd_*` helpers elsewhere.

```bash
grep -n "def create_access_token" backend/dependencies.py backend/app/**/*.py 2>/dev/null | head
```

If the token helper is elsewhere, fix the import and re-run.

- [ ] **Step 3: Smoke-run an empty test**

```bash
pytest backend/tests/conftest.py -v --collect-only
```
Expected: no collection errors.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: async client + role/tenant fixtures for student-performance plan"
```

---

## Task 1 — Hakim batch risk scoring (engine)

**Files:**
- Modify: `backend/engines/hakim_ai_engine.py`
- Test: `backend/tests/test_hakim_batch_risk.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_hakim_batch_risk.py
import pytest
from engines.hakim_ai_engine import HakimAIEngine

@pytest.mark.asyncio
async def test_batch_returns_one_entry_per_student(seeded_school):
    engine = HakimAIEngine(seeded_school.db)
    ids = [s["id"] for s in seeded_school.students[:5]]
    results = await engine.analyze_students_risk_batch(
        seeded_school.id, ids, days_back=30
    )
    assert len(results) == 5
    by_id = {r["student_id"]: r for r in results}
    for sid in ids:
        assert sid in by_id
        r = by_id[sid]
        assert 0 <= r["risk_score"] <= 100
        assert r["risk_category"] in {"low", "medium", "high", "critical"}
        assert set(r["breakdown"].keys()) == {"attendance", "participation", "behaviour", "academic"}

@pytest.mark.asyncio
async def test_batch_matches_single_call(seeded_school):
    engine = HakimAIEngine(seeded_school.db)
    sid = seeded_school.students[0]["id"]
    single = await engine.analyze_student_risk(sid, seeded_school.id, days_back=30)
    batch = (await engine.analyze_students_risk_batch(
        seeded_school.id, [sid], days_back=30
    ))[0]
    assert batch["risk_score"] == single["risk_score"]
    assert batch["breakdown"] == single["breakdown"]
```

- [ ] **Step 2: Run — expect FAIL (`analyze_students_risk_batch` not defined).**
  `pytest backend/tests/test_hakim_batch_risk.py -v`

- [ ] **Step 3: Implement with strict parity**

The batch must produce **identical** scores to `analyze_student_risk` (§11 of spec requires unification). Approach: factor the single-student path's inputs (attendance counts, session_attendance counts, interactions list, daily_scores, grades) into pre-fetchable lookups, then share scoring logic between batch and the existing helpers.

Add a second parity test first (in addition to Step 1):

```python
@pytest.mark.asyncio
async def test_batch_identical_to_single_for_all(seeded_school):
    engine = HakimAIEngine(seeded_school.db)
    ids = [s["id"] for s in seeded_school.students]
    batch = {r["student_id"]: r for r in
             await engine.analyze_students_risk_batch(seeded_school.id, ids, days_back=30)}
    for sid in ids:
        single = await engine.analyze_student_risk(sid, seeded_school.id, days_back=30)
        assert batch[sid]["risk_score"] == single["risk_score"], sid
        assert batch[sid]["breakdown"] == single["breakdown"], sid
        assert batch[sid]["risk_category"] == single["risk_category"], sid
```

Now append to `HakimAIEngine`, keeping the same data sources and defaults as `_calc_attendance_score`, `_calc_participation_score`, `_calc_behaviour_score`, `_calc_academic_score`:

```python
async def analyze_students_risk_batch(
    self, school_id: str, student_ids: list[str], days_back: int = 30
) -> list[dict]:
    if not student_ids:
        return []
    cutoff = (datetime.now(timezone.utc)
              - timedelta(days=days_back)).strftime("%Y-%m-%d")

    # ---- pre-fetch: attendance totals + present/late per student ----
    att_rows = await gd_find(self.session, "attendance",
        {"school_id": school_id, "student_id": {"$in": student_ids},
         "date": {"$gte": cutoff}}, limit=50000)
    att_map = {sid: {"total": 0, "present": 0} for sid in student_ids}
    for r in att_rows:
        sid = r["student_id"]
        if sid not in att_map: continue
        att_map[sid]["total"] += 1
        if r.get("status") in ("present", "late"):
            att_map[sid]["present"] += 1

    # ---- school-level session ids (reuse existing helper) ----
    session_ids = await self._get_school_session_ids(school_id, cutoff)

    # ---- pre-fetch: session_attendance present + all session_interactions ----
    sa_map = {sid: 0 for sid in student_ids}
    inter_map: dict[str, list[dict]] = {sid: [] for sid in student_ids}
    if session_ids:
        sa_rows = await gd_find(self.session, "session_attendance",
            {"student_id": {"$in": student_ids}, "status": "present",
             "session_id": {"$in": session_ids}}, limit=50000)
        for r in sa_rows:
            if r["student_id"] in sa_map:
                sa_map[r["student_id"]] += 1
        inter_rows = await gd_find(self.session, "session_interactions",
            {"student_id": {"$in": student_ids},
             "session_id": {"$in": session_ids}}, limit=50000)
        for r in inter_rows:
            if r["student_id"] in inter_map:
                inter_map[r["student_id"]].append(r)

    # ---- pre-fetch: daily scores + grades (same collections as single path) ----
    ds_rows = await gd_find(self.session, "student_daily_scores",
        {"school_id": school_id, "student_id": {"$in": student_ids},
         "date": {"$gte": cutoff}}, limit=50000)
    ds_map: dict[str, list[dict]] = {sid: [] for sid in student_ids}
    for r in ds_rows:
        ds_map.setdefault(r["student_id"], []).append(r)

    gr_rows = await gd_find(self.session, "student_grades",
        {"tenant_id": school_id, "student_id": {"$in": student_ids}}, limit=50000)
    gr_map: dict[str, list[dict]] = {sid: [] for sid in student_ids}
    for r in gr_rows:
        gr_map.setdefault(r["student_id"], []).append(r)

    # ---- students meta ----
    students_docs = await gd_find(self.session, "students",
        {"id": {"$in": student_ids}, "school_id": school_id}, limit=len(student_ids))
    students_map = {s["id"]: s for s in students_docs}

    # ---- pure scorers that mirror _calc_* defaults exactly ----
    def score_attendance(a):
        if a["total"] == 0: return 100.0
        return (a["present"] / a["total"]) * 100

    def score_participation(sessions_present, interactions_list):
        if not session_ids: return 50.0
        if sessions_present == 0: return 50.0
        ratio = len(interactions_list) / max(sessions_present, 1)
        return min(100.0, ratio * 100)

    def score_behaviour(interactions_list):
        if not session_ids: return 75.0
        beh = [i for i in interactions_list if i.get("interaction_type") == "behaviour"]
        if not beh: return 75.0
        pos = sum(1 for i in beh
                  if (i.get("behaviour_type") == "positive")
                  or (i.get("behaviour_category") in ("positive", "respect", "teamwork")))
        return min(100.0, (pos / len(beh)) * 100 + 25)

    def score_academic(daily_scores, grades):
        if daily_scores:
            total = sum(s.get("score", 0) for s in daily_scores)
            max_possible = len(daily_scores) * 5
            if max_possible <= 0: return 60.0
            return min(100.0, (total / max_possible) * 100)
        if grades:
            avg = sum(g.get("percentage", 0) for g in grades) / len(grades)
            return min(100.0, avg)
        return 60.0

    results = []
    for sid in student_ids:
        att_s  = score_attendance(att_map[sid])
        part_s = score_participation(sa_map[sid], inter_map[sid])
        beh_s  = score_behaviour(inter_map[sid])
        acad_s = score_academic(ds_map.get(sid, []), gr_map.get(sid, []))

        risk_score = round(
            att_s * RISK_WEIGHTS["attendance"] + part_s * RISK_WEIGHTS["participation"]
            + beh_s * RISK_WEIGHTS["behaviour"] + acad_s * RISK_WEIGHTS["academic"], 1
        )
        category, label_ar = RISK_CATEGORIES[0][2], RISK_CATEGORIES[0][3]
        for lo, hi, cat, label in RISK_CATEGORIES:
            if lo <= risk_score < hi:
                category, label_ar = cat, label; break

        factors = []
        if att_s  < 50: factors.append("انخفاض الحضور")
        if part_s < 50: factors.append("انخفاض المشاركة")
        if beh_s  < 50: factors.append("مشاكل سلوكية")
        if acad_s < 50: factors.append("تدني الأداء الأكاديمي")

        s = students_map.get(sid, {})
        results.append({
            "student_id": sid,
            "student_name": s.get("full_name"),
            "class_id": s.get("class_id"),
            "parent_id": s.get("parent_id"),
            "risk_score": risk_score,
            "risk_category": category,
            "risk_label_ar": label_ar,
            "factors": factors,
            "breakdown": {
                "attendance": round(att_s, 1), "participation": round(part_s, 1),
                "behaviour": round(beh_s, 1), "academic": round(acad_s, 1),
            },
            "period_days": days_back,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        })
    return results
```

> **Parity rule:** do not change any default (`100/50/75/60`) or threshold — copy them verbatim from `_calc_*`. If `test_batch_identical_to_single_for_all` fails even with this code, the cause is almost always a default mismatch or collection-name drift (e.g. `grades` vs `student_grades`, `school_id` vs `tenant_id`). Fix by re-reading the corresponding `_calc_*` method and mirroring its inputs exactly.

- [ ] **Step 4: Re-run tests — expect PASS for all three cases including the strict parity test.**

- [ ] **Step 5: Commit**

```bash
git add backend/engines/hakim_ai_engine.py backend/tests/test_hakim_batch_risk.py
git commit -m "feat(hakim): analyze_students_risk_batch with strict single-path parity"
```

---

## Task 2 — `GET /ai/insights/students-overview` endpoint

**Files:**
- Modify: `backend/routes/ai_routes_mod.py`
- Test: `backend/tests/test_students_overview.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_students_overview.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_overview_happy_path(client: AsyncClient, school_admin_headers, seeded_school):
    r = await client.get("/ai/insights/students-overview", headers=school_admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert set(data["summary"].keys()) >= {"total_students", "stable", "needs_followup", "at_risk", "excelling"}
    s = data["summary"]
    assert s["stable"]["count"] + s["needs_followup"]["count"] + s["at_risk"]["count"] + s["excelling"]["count"] <= s["total_students"]
    assert all(k in data["root_causes"] for k in ("attendance", "participation", "behaviour", "academic"))
    for row in data["risk_map"]:
        assert 0 <= row["x_academic"] <= 100
        assert 0 <= row["y_engagement"] <= 100
        assert row["category"] in {"stable", "needs_followup", "at_risk", "excelling"}
    for row in data["intervention_list"]:
        assert row["category"] in {"needs_followup", "at_risk"}

@pytest.mark.asyncio
async def test_overview_sorted_and_capped(client, school_admin_headers, many_students_school):
    r = await client.get("/ai/insights/students-overview", headers=school_admin_headers)
    items = r.json()["intervention_list"]
    assert len(items) <= 50
    scores = [x["risk_score"] for x in items]
    assert scores == sorted(scores)

@pytest.mark.asyncio
async def test_overview_tenant_isolation(client, tenant_a_admin, tenant_b_students):
    r = await client.get("/ai/insights/students-overview", headers=tenant_a_admin)
    ids_returned = {x["student_id"] for x in r.json()["risk_map"]}
    ids_b = {s["id"] for s in tenant_b_students}
    assert ids_returned.isdisjoint(ids_b)

@pytest.mark.asyncio
async def test_overview_refresh_busts_cache(client, school_admin_headers):
    r1 = await client.get("/ai/insights/students-overview", headers=school_admin_headers)
    ts1 = r1.json()["last_updated"]
    r2 = await client.get("/ai/insights/students-overview?refresh=1", headers=school_admin_headers)
    assert r2.json()["last_updated"] >= ts1
```

- [ ] **Step 2: Run — expect FAIL (route not defined).**

- [ ] **Step 3: Implement endpoint**

Add to `backend/routes/ai_routes_mod.py` just above the existing `get_at_risk_students` handler:

```python
_OVERVIEW_CACHE: dict[str, tuple[float, dict]] = {}
_OVERVIEW_TTL_SEC = 300

@router.get("/ai/insights/students-overview")
async def get_students_overview(
    refresh: int = 0,
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")

    now = datetime.now(timezone.utc).timestamp()
    cached = _OVERVIEW_CACHE.get(school_id)
    if not refresh and cached and now - cached[0] < _OVERVIEW_TTL_SEC:
        return cached[1]

    students = await gd_find(db.session, "students", {"school_id": school_id}, limit=500)
    if not students:
        empty = {"summary": {"total_students": 0, "stable": {"count":0,"percentage":0},
                             "needs_followup": {"count":0,"percentage":0},
                             "at_risk": {"count":0,"percentage":0},
                             "excelling": {"count":0,"percentage":0}},
                 "risk_map": [], "intervention_list": [], "root_causes": {
                     "attendance":{"count":0,"percentage":0},
                     "participation":{"count":0,"percentage":0},
                     "behaviour":{"count":0,"percentage":0},
                     "academic":{"count":0,"percentage":0}},
                 "last_updated": datetime.now(timezone.utc).isoformat()}
        _OVERVIEW_CACHE[school_id] = (now, empty)
        return empty

    ids = [s["id"] for s in students]
    risks = await hakim_engine.analyze_students_risk_batch(school_id, ids, days_back=30)

    class_docs = await gd_find(db.session, "classes",
                               {"id": {"$in": list({r["class_id"] for r in risks if r.get("class_id")})}}, limit=500)
    class_name = {c["id"]: c.get("name", "") for c in class_docs}

    academic_scores = sorted([r["breakdown"]["academic"] for r in risks], reverse=True)
    top_q = academic_scores[max(len(academic_scores)//4 - 1, 0)] if academic_scores else 0

    buckets = {"stable": [], "needs_followup": [], "at_risk": [], "excelling": []}
    enriched = []
    for r in risks:
        cat_raw = r["risk_category"]
        if cat_raw == "low":
            ui_cat = "stable"
        elif cat_raw == "medium":
            ui_cat = "needs_followup"
        else:
            ui_cat = "at_risk"
        if r["risk_score"] >= 90 and r["breakdown"]["academic"] >= top_q:
            ui_cat = "excelling"
        buckets[ui_cat].append(r)

        weakest = min(r["breakdown"].items(), key=lambda kv: kv[1])
        weakest_key, _ = weakest
        enriched.append({**r, "ui_category": ui_cat, "weakest": weakest_key,
                         "class_name": class_name.get(r.get("class_id"), "")})

    total = len(risks)
    def _pct(n): return round((n / total) * 100, 1) if total else 0
    summary = {
        "total_students": total,
        "stable":         {"count": len(buckets["stable"]),         "percentage": _pct(len(buckets["stable"]))},
        "needs_followup": {"count": len(buckets["needs_followup"]), "percentage": _pct(len(buckets["needs_followup"]))},
        "at_risk":        {"count": len(buckets["at_risk"]),        "percentage": _pct(len(buckets["at_risk"]))},
        "excelling":      {"count": len(buckets["excelling"]),      "percentage": _pct(len(buckets["excelling"]))},
    }

    risk_map = [
        {
            "student_id": e["student_id"], "name": e["student_name"],
            "class_name": e["class_name"],
            "x_academic": e["breakdown"]["academic"],
            "y_engagement": round((e["breakdown"]["attendance"] + e["breakdown"]["participation"]) / 2, 1),
            "risk_score": e["risk_score"], "category": e["ui_category"],
            "factors": e["factors"],
        } for e in enriched
    ]

    intervention_items = [e for e in enriched if e["ui_category"] in ("at_risk", "needs_followup")]
    intervention_items.sort(key=lambda x: x["risk_score"])
    intervention_items = intervention_items[:50]
    LABELS = {"attendance":"انخفاض الحضور", "participation":"انخفاض المشاركة",
              "behaviour":"مشاكل سلوكية", "academic":"تدني الأداء الأكاديمي"}
    intervention_list = [{
        "student_id": e["student_id"], "name": e["student_name"],
        "class_name": e["class_name"], "category": e["ui_category"],
        "issue_type": e["weakest"], "issue_label_ar": LABELS[e["weakest"]],
        "risk_score": e["risk_score"], "parent_id": e.get("parent_id"),
    } for e in intervention_items]

    cause_counts = {"attendance":0, "participation":0, "behaviour":0, "academic":0}
    at_risk_like = [e for e in enriched if e["risk_score"] < 75]
    for e in at_risk_like:
        cause_counts[e["weakest"]] += 1
    causes_total = sum(cause_counts.values()) or 1
    root_causes = {k: {"count": v, "percentage": round((v/causes_total)*100, 1)}
                   for k, v in cause_counts.items()}

    payload = {
        "summary": summary, "risk_map": risk_map, "intervention_list": intervention_list,
        "root_causes": root_causes,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    _OVERVIEW_CACHE[school_id] = (now, payload)
    return payload

def _invalidate_overview_cache(school_id: str) -> None:
    _OVERVIEW_CACHE.pop(school_id, None)
```

- [ ] **Step 4: Run tests — expect PASS.**

- [ ] **Step 5: Commit**

```bash
git add backend/routes/ai_routes_mod.py backend/tests/test_students_overview.py
git commit -m "feat(ai-insights): add students-overview endpoint with 5-min cache"
```

---

## Task 3 — Refactor `at-risk-students` into wrapper + add RBAC

**Files:**
- Modify: `backend/routes/ai_routes_mod.py` (replace existing `get_at_risk_students`)
- Test: `backend/tests/test_students_overview.py` (add wrapper regression cases)

- [ ] **Step 1: Add regression test**

```python
@pytest.mark.asyncio
async def test_at_risk_legacy_shape_preserved(client, school_admin_headers, seeded_school):
    r = await client.get("/ai/insights/at-risk-students", headers=school_admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) <= 20
    if data:
        item = data[0]
        assert {"id", "name", "grade", "risk_level", "risk_type", "factors"} <= set(item.keys())

@pytest.mark.asyncio
async def test_at_risk_requires_admin_role(client, teacher_headers):
    r = await client.get("/ai/insights/at-risk-students", headers=teacher_headers)
    assert r.status_code == 403
```

- [ ] **Step 2: Run — one passes (backwards shape), one fails (no gate).**

- [ ] **Step 3: Replace handler body**

```python
@router.get("/ai/insights/at-risk-students")
async def get_at_risk_students(
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    overview = await get_students_overview(refresh=0, current_user=current_user)
    result = []
    for row in overview["intervention_list"][:20]:
        result.append({
            "id": row["student_id"],
            "name": row["name"],
            "grade": row["class_name"],
            "risk_level": row["risk_score"],
            "risk_type": row["issue_type"],
            "factors": [row["issue_label_ar"]],
        })
    return result
```

- [ ] **Step 4: Run tests — expect PASS.**

- [ ] **Step 5: Commit**

```bash
git add backend/routes/ai_routes_mod.py backend/tests/test_students_overview.py
git commit -m "refactor(ai-insights): at-risk-students now wraps students-overview + RBAC gate"
```

---

## Task 4 — `POST /ai/insights/intervention`

**Files:**
- Modify: `backend/routes/ai_routes_mod.py`
- Test: `backend/tests/test_intervention_endpoint.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_intervention_endpoint.py
import pytest

@pytest.mark.asyncio
async def test_notify_parent_creates_notification(client, school_admin_headers, student_with_parent, db):
    body = {"student_id": student_with_parent["id"], "action_type": "notify_parent",
            "data": {"message": "يرجى مراجعة المدرسة", "issue_type": "attendance"}}
    r = await client.post("/ai/insights/intervention", json=body, headers=school_admin_headers)
    assert r.status_code == 200 and r.json()["success"]
    notifs = await db.gd_find("notifications",
        {"user_id": student_with_parent["parent_id"], "tenant_id": student_with_parent["school_id"]})
    assert any("يرجى مراجعة المدرسة" in (n.get("message") or "") for n in notifs)

@pytest.mark.asyncio
async def test_remedial_plan_persisted(client, school_admin_headers, a_student):
    body = {"student_id": a_student["id"], "action_type": "remedial_plan",
            "data": {"issue_type": "academic", "description": "خطة دعم",
                     "target_date": "2026-05-01", "milestones": ["مراجعة", "اختبار"]}}
    r = await client.post("/ai/insights/intervention", json=body, headers=school_admin_headers)
    assert r.status_code == 200
    inv_id = r.json()["intervention_id"]
    assert inv_id

@pytest.mark.asyncio
async def test_cross_tenant_student_404(client, tenant_a_admin, tenant_b_student):
    body = {"student_id": tenant_b_student["id"], "action_type": "schedule_followup",
            "data": {"follow_up_date": "2026-04-30", "notes": ""}}
    r = await client.post("/ai/insights/intervention", json=body, headers=tenant_a_admin)
    assert r.status_code == 404

@pytest.mark.asyncio
async def test_intervention_role_denied_for_teacher(client, teacher_headers, a_student):
    body = {"student_id": a_student["id"], "action_type": "schedule_followup",
            "data": {"follow_up_date": "2026-04-30"}}
    r = await client.post("/ai/insights/intervention", json=body, headers=teacher_headers)
    assert r.status_code == 403

@pytest.mark.asyncio
async def test_intervention_writes_audit_log(client, school_admin_headers, a_student, db):
    body = {"student_id": a_student["id"], "action_type": "schedule_followup",
            "data": {"follow_up_date": "2026-04-30"}}
    r = await client.post("/ai/insights/intervention", json=body, headers=school_admin_headers)
    assert r.status_code == 200
    from engines.sql_utils import gd_find
    from dependencies import db as _db
    logs = await gd_find(_db.session, "audit_logs",
        {"entity_id": a_student["id"], "action": "intervention.schedule_followup"})
    assert logs, "audit row missing"

@pytest.mark.asyncio
async def test_notify_parent_without_parent_400(client, school_admin_headers, orphan_student):
    body = {"student_id": orphan_student["id"], "action_type": "notify_parent",
            "data": {"message": "x", "issue_type": "attendance"}}
    r = await client.post("/ai/insights/intervention", json=body, headers=school_admin_headers)
    assert r.status_code == 400
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

Near the top of `ai_routes_mod.py` add import if missing: `from routes.notification_routes_mod import create_notification_internal`.

Then:

```python
class InterventionRequest(BaseModel):
    student_id: str
    action_type: Literal["notify_parent", "remedial_plan", "schedule_followup"]
    data: dict

@router.post("/ai/insights/intervention")
async def post_intervention(
    body: InterventionRequest,
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")

    student = await gd_find_one(db.session, "students",
                                {"id": body.student_id, "school_id": school_id})
    if not student:
        raise HTTPException(404, "الطالب غير موجود")

    now = datetime.now(timezone.utc)
    intervention_id = str(uuid.uuid4())
    d = body.data or {}

    if body.action_type == "notify_parent":
        parent_id = student.get("parent_id")
        if not parent_id:
            raise HTTPException(400, "لا يوجد ولي أمر مسجل للطالب")
        message = (d.get("message") or "").strip()
        if not message:
            raise HTTPException(400, "نص الرسالة مطلوب")
        await create_notification_internal(
            title="متابعة أداء الطالب",
            message=message,
            recipient_id=parent_id,
            notification_type=d.get("issue_type", "general"),
            priority="high",
            sender_id=current_user.get("id"),
            related_entity="student",
            related_entity_id=body.student_id,
            school_id=school_id,
        )
        msg_ar = "تم إرسال الرسالة لولي الأمر بنجاح"

    elif body.action_type == "remedial_plan":
        doc = {
            "id": intervention_id,
            "school_id": school_id,
            "student_id": body.student_id,
            "type": "plan",
            "status": "active",
            "title": d.get("title", "خطة علاجية"),
            "description": d.get("description", ""),
            "data": {
                "issue_type": d.get("issue_type", "academic"),
                "start_date": now.strftime("%Y-%m-%d"),
                "target_date": d.get("target_date"),
                "milestones": [{"text": m, "completed": False} for m in (d.get("milestones") or [])],
            },
            "created_by": current_user.get("id"),
            "created_at": now, "updated_at": now,
        }
        await gd_insert(db.session, "ai_interventions", doc)
        msg_ar = "تم إنشاء الخطة العلاجية بنجاح"

    elif body.action_type == "schedule_followup":
        doc = {
            "id": intervention_id,
            "school_id": school_id,
            "student_id": body.student_id,
            "type": "followup",
            "status": "active",
            "title": "متابعة",
            "description": d.get("notes", ""),
            "data": {
                "issue_type": d.get("issue_type", "attendance"),
                "follow_up_date": d.get("follow_up_date"),
                "notes": d.get("notes", ""),
            },
            "created_by": current_user.get("id"),
            "created_at": now, "updated_at": now,
        }
        await gd_insert(db.session, "ai_interventions", doc)
        msg_ar = "تمت جدولة المتابعة بنجاح"

    # --- audit-log write (spec §10.4) — column names match pg_models.AuditLog ---
    await gd_insert(db.session, "audit_logs", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "performed_by": current_user.get("id"),
        "actor_role": current_user.get("role"),
        "action": f"intervention.{body.action_type}",
        "entity_type": "student",
        "entity_id": body.student_id,
        "target_id": body.student_id,
        "target_type": "student",
        "details": {"intervention_id": intervention_id, "issue_type": d.get("issue_type")},
        "created_at": now,
    })

    _invalidate_overview_cache(school_id)
    return {"success": True, "intervention_id": intervention_id, "message_ar": msg_ar}
```

- [ ] **Step 4: Run tests — PASS.**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(ai-insights): POST /intervention with notify/plan/followup dispatch"
```

---

## Task 5 — `GET /ai/insights/recommendations-ai`

**Files:**
- Modify: `backend/routes/ai_routes_mod.py`
- Test: `backend/tests/test_students_overview.py` (append)

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_recommendations_ai_happy(client, school_admin_headers, monkeypatch):
    from routes import ai_routes_mod
    async def fake_openai(prompt: str):
        return '[{"type":"quantitative","text":"5 طلاب"},{"type":"positive","text":"تحسن"}]'
    monkeypatch.setattr(ai_routes_mod, "_call_openai_for_recommendations", fake_openai)
    r = await client.get("/ai/insights/recommendations-ai", headers=school_admin_headers)
    assert r.status_code == 200
    j = r.json()
    assert j["source"] == "openai"
    assert 1 <= len(j["recommendations"]) <= 6
    for x in j["recommendations"]:
        assert x["type"] in {"quantitative","academic","statistical_alert","positive","administrative"}
        assert x["text"] and x["icon"]

@pytest.mark.asyncio
async def test_recommendations_ai_fallback(client, school_admin_headers, monkeypatch):
    from routes import ai_routes_mod
    async def boom(prompt: str): raise RuntimeError("openai down")
    monkeypatch.setattr(ai_routes_mod, "_call_openai_for_recommendations", boom)
    r = await client.get("/ai/insights/recommendations-ai", headers=school_admin_headers)
    assert r.status_code == 200
    assert r.json()["source"] == "fallback"
    assert len(r.json()["recommendations"]) == 1

@pytest.mark.asyncio
async def test_recommendations_ai_role(client, teacher_headers):
    r = await client.get("/ai/insights/recommendations-ai", headers=teacher_headers)
    assert r.status_code == 403
```

- [ ] **Step 2: Run — FAIL.**

- [ ] **Step 3: Implement**

```python
_REC_CACHE: dict[str, tuple[float, dict]] = {}
_REC_TTL_SEC = 900
_ICONS = {"quantitative":"📊","academic":"🎯","statistical_alert":"⚠️",
          "positive":"✅","administrative":"📋"}

async def _call_openai_for_recommendations(prompt: str) -> str:
    """Thin wrapper — explicit seam for monkeypatching in tests.
    Uses the same client as the rest of this module (`get_openai_client`)."""
    client = get_openai_client()
    if client is None:
        raise RuntimeError("openai_unavailable")
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content":
             "أنت مستشار تعليمي. أجب حصراً بمصفوفة JSON دون نص إضافي."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "[]"
    # Model may return {"recommendations":[...]} or bare list — normalize downstream.
    return content

def _build_recs_prompt(overview: dict) -> str:
    s = overview["summary"]; rc = overview["root_causes"]
    top_causes = ", ".join(
        f"{k}({v['count']})" for k, v in sorted(rc.items(), key=lambda kv: -kv[1]["count"])[:2]
    )
    return (
        "أنت مستشار تعليمي ذكي. بناءً على بيانات مدرسة:\n"
        f"- إجمالي الطلاب: {s['total_students']}\n"
        f"- في فئة الخطر: {s['at_risk']['count']}\n"
        f"- يحتاجون متابعة: {s['needs_followup']['count']}\n"
        f"- أسباب التعثر الشائعة: {top_causes}\n"
        "قدّم ما بين 4 إلى 6 توصيات كقائمة JSON حصراً بالصيغة:\n"
        '[{"type":"quantitative|academic|statistical_alert|positive|administrative","text":"..."}]'
    )

def _fallback_recommendation(overview: dict) -> list[dict]:
    at_risk = overview["summary"]["at_risk"]["count"]
    total = overview["summary"]["total_students"] or 1
    pct = round((at_risk/total)*100)
    return [{"type":"statistical_alert",
             "text": f"{at_risk} طالب في فئة الخطر حالياً ({pct}%). يُنصح بمراجعة قائمة التدخل.",
             "icon": _ICONS["statistical_alert"]}]

@router.get("/ai/insights/recommendations-ai")
async def get_recommendations_ai(
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    school_id = current_user["tenant_id"]
    now = datetime.now(timezone.utc).timestamp()
    cached = _REC_CACHE.get(school_id)
    if cached and now - cached[0] < _REC_TTL_SEC:
        return cached[1]

    overview = await get_students_overview(refresh=0, current_user=current_user)
    prompt = _build_recs_prompt(overview)
    try:
        raw = await _call_openai_for_recommendations(prompt)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = parsed.get("recommendations") or parsed.get("items") or []
        if not (isinstance(parsed, list) and parsed):
            raise ValueError("invalid model output")
        clean = []
        for item in parsed[:6]:
            t = item.get("type"); text = (item.get("text") or "").strip()
            if t in _ICONS and text:
                clean.append({"type": t, "text": text, "icon": _ICONS[t]})
        if not clean:
            raise ValueError("empty after validation")
        payload = {"recommendations": clean,
                   "generated_at": datetime.now(timezone.utc).isoformat(),
                   "source": "openai"}
    except Exception:
        payload = {"recommendations": _fallback_recommendation(overview),
                   "generated_at": datetime.now(timezone.utc).isoformat(),
                   "source": "fallback"}

    _REC_CACHE[school_id] = (now, payload)
    return payload
```

- [ ] **Step 4: Run — PASS.**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(ai-insights): recommendations-ai with OpenAI + graceful fallback"
```

---

## Task 6 — i18n keys

**Files:** `frontend/src/locales/ar.json`, `frontend/src/locales/en.json`

- [ ] **Step 1: Add keys (ar.json — append inside root object)**

Use exactly the block from §5.5 of the spec. English mirror uses sensible equivalents, e.g. `"studentPerformance": "Student Performance"`, `"attendance": "Attendance"`, `"behaviour": "Behaviour"`, `"academic": "Academic"`, etc. Include every key from the Arabic block — missing keys crash the tab.

- [ ] **Step 2: Verify no duplicates**

```bash
node -e "const f=require('./frontend/src/locales/ar.json'); console.log(Object.keys(f).length);"
node -e "const a=require('./frontend/src/locales/ar.json'), e=require('./frontend/src/locales/en.json'); const miss=Object.keys(a).filter(k=>!(k in e)); console.log('missing', miss);"
```

- [ ] **Step 3: Commit**

```bash
git commit -am "i18n: student-performance dashboard keys (ar + en)"
```

---

## Task 7 — Frontend scaffolding: dashboard container + Tabs wiring

**Files:**
- Create: `frontend/src/components/student-performance/StudentPerformanceDashboard.jsx`
- Modify: `frontend/src/pages/AIInsightsPage.jsx`

- [ ] **Step 1: Create container**

**Import conventions for this codebase (used in every new frontend file):**
- `useTranslation` comes from `../../contexts/ThemeContext` (not `react-i18next`).
- `api` comes from `useAuth()` in `../../contexts/AuthContext` (there is no `@/lib/api`).
- UI primitives live under `../ui/...` and follow shadcn conventions.

```jsx
// frontend/src/components/student-performance/StudentPerformanceDashboard.jsx
import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import { RefreshCw } from 'lucide-react';
import { Button } from '../ui/button';
import ExecutiveSummaryCards from './ExecutiveSummaryCards';
import StudentRiskMap from './StudentRiskMap';
import InterventionList from './InterventionList';
import RootCauseChart from './RootCauseChart';
import HakimRecommendations from './HakimRecommendations';
import InterventionActionModal from './InterventionActionModal';

export default function StudentPerformanceDashboard() {
  const { t } = useTranslation();
  const { api } = useAuth();
  const [data, setData] = useState(null);
  const [recs, setRecs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [modal, setModal] = useState(null); // { student, actionType }

  const load = useCallback(async (force=false) => {
    const qs = force ? '?refresh=1' : '';
    setRefreshing(force);
    try {
      const [ov, rc] = await Promise.all([
        api.get(`/ai/insights/students-overview${qs}`),
        api.get('/ai/insights/recommendations-ai'),
      ]);
      setData(ov.data); setRecs(rc.data);
    } finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(false); }, [load]);

  if (loading) return <div className="p-6 text-center">{t('loading')}</div>;

  return (
    <div dir="rtl" className="space-y-6 font-tajawal">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-cairo text-[#1C3D74]">{t('studentPerformance')}</h2>
        <Button variant="outline" onClick={() => load(true)} disabled={refreshing}>
          <RefreshCw className={`ms-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          {t('refreshData')}
        </Button>
      </div>

      <ExecutiveSummaryCards summary={data.summary} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <StudentRiskMap points={data.risk_map} />
        <InterventionList items={data.intervention_list}
                          onAction={(student, actionType) => setModal({ student, actionType })} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RootCauseChart causes={data.root_causes} />
        <HakimRecommendations recommendations={recs?.recommendations || []}
                              source={recs?.source} />
      </div>

      {modal && (
        <InterventionActionModal
          student={modal.student}
          actionType={modal.actionType}
          onClose={() => setModal(null)}
          onSuccess={() => { setModal(null); load(true); }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire Tabs into `AIInsightsPage.jsx`**

Wrap the existing render tree (lines 594–951 content) in Tabs. Add at top of file:

```jsx
import { lazy, Suspense } from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
const StudentPerformanceDashboard = lazy(() =>
  import('../components/student-performance/StudentPerformanceDashboard'));

const ADMIN_ROLES = ['school_admin', 'school_sub_admin', 'school_principal'];
```

Inside the component, wrap existing JSX:

```jsx
const canSeeStudentPerformance = ADMIN_ROLES.includes(user?.role);

return (
  <Tabs defaultValue="insights" dir="rtl">
    <TabsList>
      <TabsTrigger value="insights">{t('aiInsights')}</TabsTrigger>
      {canSeeStudentPerformance && (
        <TabsTrigger value="student-performance">{t('studentPerformance')}</TabsTrigger>
      )}
    </TabsList>
    <TabsContent value="insights">
      {/* ← move existing return(...) JSX here verbatim */}
    </TabsContent>
    {canSeeStudentPerformance && (
      <TabsContent value="student-performance">
        <Suspense fallback={<div className="p-6">{t('loading')}</div>}>
          <StudentPerformanceDashboard />
        </Suspense>
      </TabsContent>
    )}
  </Tabs>
);
```

Active-tab underline color is overridden in the Radix Tabs CSS token already in the design system; no CSS change needed beyond passing `data-state=active` style (`#46C1BE`) — verify visually in Task 12.

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(ai-insights): Tabs wrapper + lazy StudentPerformanceDashboard"
```

---

## Task 8 — ExecutiveSummaryCards

**File:** `frontend/src/components/student-performance/ExecutiveSummaryCards.jsx`

- [ ] **Step 1: Implement**

```jsx
import { useTranslation } from '../../contexts/ThemeContext';
import { CheckCircle2, AlertTriangle, TrendingDown, Star } from 'lucide-react';

const CARDS = [
  { key: 'stable',         color: '#22c55e', Icon: CheckCircle2, labelKey: 'stable' },
  { key: 'needs_followup', color: '#eab308', Icon: AlertTriangle, labelKey: 'needsFollowup' },
  { key: 'at_risk',        color: '#ef4444', Icon: TrendingDown, labelKey: 'educationalRisk' },
  { key: 'excelling',      color: '#615090', Icon: Star,         labelKey: 'excelling' },
];

export default function ExecutiveSummaryCards({ summary }) {
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {CARDS.map(({ key, color, Icon, labelKey }) => {
        const v = summary[key] || { count: 0, percentage: 0 };
        return (
          <div key={key}
               className="rounded-xl bg-white p-5 shadow-[0_4px_20px_-4px_rgba(15,44,89,0.1)] border-e-4"
               style={{ borderInlineEndColor: color }}>
            <div className="flex items-start justify-between">
              <div>
                <div className="text-3xl font-cairo font-bold" style={{ color }}>
                  {v.percentage}%
                </div>
                <div className="text-sm text-[#312E2F] mt-1">{t(labelKey)}</div>
                <div className="text-xs text-neutral-500 mt-1">{v.count}</div>
              </div>
              <Icon className="h-6 w-6" style={{ color }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git commit -am "feat(student-perf): ExecutiveSummaryCards KPI grid"
```

---

## Task 9 — StudentRiskMap (Recharts scatter)

**File:** `frontend/src/components/student-performance/StudentRiskMap.jsx`

- [ ] **Step 1: Implement**

```jsx
import { useTranslation } from '../../contexts/ThemeContext';
import { ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

const COLORS = { stable:'#22c55e', needs_followup:'#eab308', at_risk:'#ef4444', excelling:'#615090' };

function Dot(props) {
  const { cx, cy, payload } = props;
  return <circle cx={cx} cy={cy} r={6} fill={COLORS[payload.category] || '#888'} />;
}

function TipBox({ active, payload }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-lg bg-white p-3 shadow text-sm" dir="rtl">
      <div className="font-bold text-[#1C3D74]">{p.name}</div>
      <div className="text-neutral-600">{p.class_name}</div>
      <div className="mt-1">Risk: {p.risk_score}</div>
      <div className="text-xs text-neutral-500">{(p.factors || []).join('، ')}</div>
    </div>
  );
}

export default function StudentRiskMap({ points }) {
  const { t } = useTranslation();
  return (
    <div className="rounded-xl bg-white p-5 shadow-[0_4px_20px_-4px_rgba(15,44,89,0.1)]">
      <h3 className="text-lg font-cairo text-[#1C3D74] mb-3">{t('riskMap')}</h3>
      <ResponsiveContainer width="100%" height={340}>
        <ScatterChart margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
          <CartesianGrid stroke="#EAECED" />
          <XAxis type="number" dataKey="x_academic" domain={[0,100]}
                 label={{ value: t('academicAxis'), position: 'insideBottom', offset: -5 }} />
          <YAxis type="number" dataKey="y_engagement" domain={[0,100]}
                 label={{ value: t('engagementAxis'), angle: -90, position: 'insideLeft' }} />
          <Tooltip content={<TipBox />} />
          <Scatter data={points} shape={<Dot />} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: Commit** — `git commit -am "feat(student-perf): StudentRiskMap scatter plot"`

---

## Task 10 — InterventionList + InterventionActionModal

**Files:**
- `frontend/src/components/student-performance/InterventionList.jsx`
- `frontend/src/components/student-performance/InterventionActionModal.jsx`

- [ ] **Step 1: InterventionList**

```jsx
import { useTranslation } from '../../contexts/ThemeContext';
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem }
  from '../ui/dropdown-menu';
import { Button } from '../ui/button';

const BADGE = { at_risk: {bg:'#fee2e2', fg:'#ef4444'},
                needs_followup: {bg:'#fef3c7', fg:'#eab308'} };

export default function InterventionList({ items, onAction }) {
  const { t } = useTranslation();
  if (!items?.length) {
    return <div className="rounded-xl bg-white p-5 text-center text-neutral-500">
             {t('noStudentsAtRisk')}</div>;
  }
  return (
    <div className="rounded-xl bg-white p-5 shadow-[0_4px_20px_-4px_rgba(15,44,89,0.1)]">
      <h3 className="text-lg font-cairo text-[#1C3D74] mb-3">{t('studentsNeedIntervention')}</h3>
      <ul className="divide-y divide-[#EAECED]">
        {items.map(s => {
          const b = BADGE[s.category] || BADGE.needs_followup;
          return (
            <li key={s.student_id} className="py-3 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="font-bold text-[#312E2F] truncate">{s.name}</div>
                <div className="text-xs text-neutral-500">{s.class_name} · {s.issue_label_ar}</div>
              </div>
              <span className="text-xs rounded-full px-2 py-1"
                    style={{ background: b.bg, color: b.fg }}>
                {t(s.category === 'at_risk' ? 'educationalRisk' : 'needsFollowup')}
              </span>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button size="sm" style={{ background:'#46C1BE', color:'white' }}>
                    {t('takeAction')}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem disabled={!s.parent_id}
                    onSelect={() => onAction(s, 'notify_parent')}>
                    {t('sendParentMessage')}
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => onAction(s, 'remedial_plan')}>
                    {t('createRemedialPlan')}
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => onAction(s, 'schedule_followup')}>
                    {t('scheduleFollowup')}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: InterventionActionModal**

```jsx
import { useState } from 'react';
import { useTranslation } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter }
  from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { toast } from '../../hooks/use-toast';

const DEFAULT_MESSAGE = (name, issue) =>
  `ولي أمر ${name} الكريم، نود إبلاغكم بأن ابنكم/ابنتكم بحاجة لمتابعة بخصوص ${issue}. نرجو التواصل مع المدرسة.`;

function plusDays(n) {
  const d = new Date(); d.setDate(d.getDate()+n);
  return d.toISOString().slice(0,10);
}

export default function InterventionActionModal({ student, actionType, onClose, onSuccess }) {
  const { t } = useTranslation();
  const { api } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(
    DEFAULT_MESSAGE(student.name, student.issue_label_ar));
  const [description, setDescription] = useState('');
  const [targetDate, setTargetDate] = useState(plusDays(14));
  const [milestones, setMilestones] = useState(['']);
  const [followUpDate, setFollowUpDate] = useState(plusDays(7));
  const [notes, setNotes] = useState('');

  const successKey = { notify_parent:'messageSentToParent',
                       remedial_plan:'remedialPlanCreated',
                       schedule_followup:'followupScheduled' }[actionType];

  async function submit() {
    setSubmitting(true);
    try {
      const data = actionType === 'notify_parent'
        ? { message, issue_type: student.issue_type }
        : actionType === 'remedial_plan'
          ? { issue_type: student.issue_type, description, target_date: targetDate,
              milestones: milestones.map(m => m.trim()).filter(Boolean) }
          : { follow_up_date: followUpDate, notes, issue_type: student.issue_type };
      await api.post('/ai/insights/intervention',
        { student_id: student.student_id, action_type: actionType, data });
      toast({ title: t(successKey) });
      onSuccess();
    } catch (e) {
      toast({ title: e?.response?.data?.detail || 'Error', variant: 'destructive' });
    } finally { setSubmitting(false); }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent dir="rtl" className="font-tajawal">
        <DialogHeader><DialogTitle>{t({
          notify_parent: 'sendParentMessage',
          remedial_plan: 'createRemedialPlan',
          schedule_followup: 'scheduleFollowup' }[actionType])}</DialogTitle></DialogHeader>

        {actionType === 'notify_parent' && (
          <Textarea value={message} onChange={e=>setMessage(e.target.value)} rows={5} />
        )}

        {actionType === 'remedial_plan' && (
          <div className="space-y-3">
            <Textarea value={description} onChange={e=>setDescription(e.target.value)}
                      placeholder={t('planDescription')} rows={4} />
            <div>
              <label className="text-sm">{t('targetDate')}</label>
              <Input type="date" value={targetDate} onChange={e=>setTargetDate(e.target.value)} />
            </div>
            <div>
              <label className="text-sm">{t('milestones')}</label>
              {milestones.map((m,i)=>(
                <Input key={i} value={m} className="mt-2"
                  onChange={e => {
                    const cp=[...milestones]; cp[i]=e.target.value; setMilestones(cp);
                  }} />
              ))}
              <Button type="button" variant="outline" size="sm" className="mt-2"
                onClick={()=>setMilestones([...milestones, ''])}>+</Button>
            </div>
          </div>
        )}

        {actionType === 'schedule_followup' && (
          <div className="space-y-3">
            <div>
              <label className="text-sm">{t('followupDate')}</label>
              <Input type="date" value={followUpDate}
                     onChange={e=>setFollowUpDate(e.target.value)} />
            </div>
            <Textarea value={notes} onChange={e=>setNotes(e.target.value)}
                      placeholder={t('followupNotes')} rows={3} />
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} disabled={submitting}
                  style={{ background:'#1C3D74', color:'white' }}>OK</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 3: Commit** — `git commit -am "feat(student-perf): InterventionList + 3-variant modal"`

---

## Task 11 — RootCauseChart + HakimRecommendations

**Files:**
- `frontend/src/components/student-performance/RootCauseChart.jsx`
- `frontend/src/components/student-performance/HakimRecommendations.jsx`

- [ ] **Step 1: RootCauseChart**

```jsx
import { useTranslation } from '../../contexts/ThemeContext';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const SLICE_COLORS = { attendance:'#eab308', participation:'#22c55e',
                       behaviour:'#ef4444', academic:'#615090' };

export default function RootCauseChart({ causes }) {
  const { t } = useTranslation();
  const data = Object.entries(causes || {}).map(([k, v]) => ({
    name: t(k), key: k, value: v.count, pct: v.percentage,
  })).filter(d => d.value > 0);

  return (
    <div className="rounded-xl bg-white p-5 shadow-[0_4px_20px_-4px_rgba(15,44,89,0.1)]">
      <h3 className="text-lg font-cairo text-[#1C3D74] mb-3">{t('rootCauseAnalysis')}</h3>
      {data.length === 0 ? (
        <div className="text-center text-neutral-500 py-12">—</div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" outerRadius={100} label>
              {data.map(d => <Cell key={d.key} fill={SLICE_COLORS[d.key]} />)}
            </Pie>
            <Tooltip formatter={(v, n, p)=>[`${v} (${p.payload.pct}%)`, n]} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
```

- [ ] **Step 2: HakimRecommendations**

```jsx
import { useTranslation } from '../../contexts/ThemeContext';

const BORDER = { quantitative:'#46C1BE', academic:'#46C1BE',
                 statistical_alert:'#ef4444', positive:'#22c55e', administrative:'#615090' };

export default function HakimRecommendations({ recommendations, source }) {
  const { t } = useTranslation();
  return (
    <div className="rounded-xl bg-white p-5 shadow-[0_4px_20px_-4px_rgba(15,44,89,0.1)]">
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="text-lg font-cairo text-[#1C3D74]">{t('nassaqSuggestions')}</h3>
        {source === 'fallback' && (
          <span className="text-xs text-neutral-500">offline</span>
        )}
      </div>
      <ul className="space-y-3">
        {recommendations.map((r, i) => (
          <li key={i} className="rounded-lg p-3 border-e-4"
              style={{ borderInlineEndColor: BORDER[r.type], background:'#f8fafc' }}>
            <span className="text-lg ms-2">{r.icon}</span>
            <span className="text-[#312E2F]">{r.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 3: Commit** — `git commit -am "feat(student-perf): RootCauseChart + HakimRecommendations"`

---

## Task 12 — RBAC & tenant-isolation test suite

**File:** `backend/tests/test_student_performance_rbac.py`

- [ ] **Step 1: Implement the matrix from spec §10.5**

```python
import pytest
from itertools import product

ROUTES_GET  = ["/ai/insights/students-overview",
               "/ai/insights/recommendations-ai",
               "/ai/insights/at-risk-students"]
ROUTE_POST  = "/ai/insights/intervention"
ROLES_ALLOWED = ["school_admin_headers", "school_sub_admin_headers", "school_principal_headers"]
ROLES_DENIED  = ["teacher_headers", "parent_headers", "student_headers", "platform_admin_headers"]

@pytest.mark.asyncio
@pytest.mark.parametrize("route,headers_fixture", list(product(ROUTES_GET, ROLES_ALLOWED)))
async def test_get_allowed_roles_200(client, request, route, headers_fixture):
    headers = request.getfixturevalue(headers_fixture)
    r = await client.get(route, headers=headers)
    assert r.status_code == 200, (route, headers_fixture, r.text)

@pytest.mark.asyncio
@pytest.mark.parametrize("route,headers_fixture", list(product(ROUTES_GET, ROLES_DENIED)))
async def test_get_denied_roles_403(client, request, route, headers_fixture):
    headers = request.getfixturevalue(headers_fixture)
    r = await client.get(route, headers=headers)
    assert r.status_code == 403

@pytest.mark.asyncio
@pytest.mark.parametrize("headers_fixture", ROLES_ALLOWED)
async def test_post_intervention_allowed_roles_200(client, request, a_student, headers_fixture):
    headers = request.getfixturevalue(headers_fixture)
    body = {"student_id": a_student["id"], "action_type": "schedule_followup",
            "data": {"follow_up_date": "2026-04-30"}}
    r = await client.post(ROUTE_POST, json=body, headers=headers)
    assert r.status_code == 200, (headers_fixture, r.text)

@pytest.mark.asyncio
@pytest.mark.parametrize("headers_fixture", ROLES_DENIED)
async def test_post_intervention_denied_roles_403(client, request, a_student, headers_fixture):
    headers = request.getfixturevalue(headers_fixture)
    body = {"student_id": a_student["id"], "action_type": "schedule_followup",
            "data": {"follow_up_date": "2026-04-30"}}
    r = await client.post(ROUTE_POST, json=body, headers=headers)
    assert r.status_code == 403

@pytest.mark.asyncio
async def test_unauthenticated_401(client, a_student):
    for route in ROUTES_GET:
        r = await client.get(route)
        assert r.status_code == 401
    r = await client.post(ROUTE_POST, json={"student_id": a_student["id"],
        "action_type": "schedule_followup", "data": {"follow_up_date": "2026-04-30"}})
    assert r.status_code == 401

@pytest.mark.asyncio
async def test_intervention_cross_tenant_404(client, tenant_a_admin, tenant_b_student):
    r = await client.post("/ai/insights/intervention",
        json={"student_id": tenant_b_student["id"], "action_type": "schedule_followup",
              "data": {"follow_up_date": "2026-04-30"}}, headers=tenant_a_admin)
    assert r.status_code == 404

@pytest.mark.asyncio
async def test_overview_data_isolation(client, tenant_a_admin, tenant_b_students):
    r = await client.get("/ai/insights/students-overview", headers=tenant_a_admin)
    ids_returned = {x["student_id"] for x in r.json()["risk_map"]} \
                  | {x["student_id"] for x in r.json()["intervention_list"]}
    ids_b = {s["id"] for s in tenant_b_students}
    assert ids_returned.isdisjoint(ids_b)
```

- [ ] **Step 2: Run — expect all PASS.**

- [ ] **Step 3: Commit** — `git commit -am "test(rbac): student-performance endpoints role + tenant isolation"`

---

## Task 13 — Manual verification + perf smoke

- [ ] **Step 1: Seed a large school**

```bash
python backend/scripts/seed_test_data.py --school-size 500
```

- [ ] **Step 2: Curl perf check**

```bash
time curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$REPLIT_DEV_DOMAIN/ai/insights/students-overview?refresh=1" > /tmp/ov.json
```
Expected: total time ≤ 2 s.

- [ ] **Step 3: Visual check**

Open the app, sign in as a `school_admin`, navigate to AI Insights, click the new tab. Confirm:
- 4 KPI cards render with correct colors (see spec §2).
- Scatter shows colored points; hover shows tooltip.
- Intervention list has "اتخاذ إجراء" dropdown with 3 items; parent option disabled for students without parent.
- Pie chart labels are Arabic and match `attendance / participation / behaviour / academic`.
- Recommendations card shows 4–6 items; kill OpenAI env var, refresh → fallback copy displayed.
- Sign in as a `teacher`: tab NOT visible; hitting `/ai/insights/students-overview` directly returns 403.

- [ ] **Step 4: Commit any visual tweaks** — `git commit -am "chore: visual polish after manual QA"`

---

## Self-Review

**Spec coverage check:**
- Spec §4.1 students-overview → Task 2 ✓
- Spec §4.2 at-risk-students wrapper → Task 3 ✓
- Spec §4.3 recommendations-ai → Task 5 ✓
- Spec §4.4 intervention POST → Task 4 (+ audit-log write per §10.4) ✓
- Spec §4.5 Hakim batch → Task 1 (with strict parity test) ✓
- Spec §4.6 remedial_plans collection → used in Task 4 ✓
- Spec §5 frontend (7 files) → Tasks 7–11 ✓
- Spec §5.5 i18n → Task 6 ✓
- Spec §10.2 RBAC matrix (GET + POST) → Task 12 ✓
- Spec §10.4 audit log on intervention → Task 4 (impl + test) ✓
- Spec §10.5 tenant isolation → Task 2, 4, 12 ✓
- Spec §11 acceptance criteria → covered across Tasks 7–13 (visual items in 13)
- Test fixtures prerequisite → Task 0 ✓

**Placeholder scan:** none.

**Type consistency & primitives:**
- Backend: `_invalidate_overview_cache`, `_call_openai_for_recommendations`, `_build_recs_prompt`, `_fallback_recommendation`, `analyze_students_risk_batch` names match across tasks.
- Backend: OpenAI path uses `get_openai_client()` already in `ai_routes_mod.py` — no new dependency.
- Backend: `create_notification_internal` call uses the real kwargs (`recipient_id`, `notification_type`, `priority`, `sender_id`, `related_entity`, `related_entity_id`, `school_id`).
- Backend: `audit_logs` collection name matches existing `gd_insert(db.session, "audit_logs", ...)` usage in `settings_routes.py` / `platform_routes_mod.py`.
- Backend: Hakim batch reads from the **same** collections and defaults as `_calc_*` (`student_daily_scores` with `school_id`, `student_grades` with `tenant_id`, `session_interactions`, default 60/75/50/100).
- Frontend: all components import `useTranslation` from `contexts/ThemeContext`, `api` from `useAuth()`; no `@/…` alias is used because the project relies on relative imports.
- Frontend prop shapes match backend response keys (`x_academic`, `y_engagement`, `category`, `issue_label_ar`, `risk_score`). Intervention request body shape matches between Task 4 backend and Task 10 modal.

**Known follow-ups / risks:**
- If `test_batch_identical_to_single_for_all` fails, it will almost always be a collection-field mismatch (`school_id` vs `tenant_id` on `student_grades`, or a default constant drift). Fix by mirroring the single-path code, not by softening the assertion.
- `create_access_token` in the fixtures assumes the helper lives in `backend/dependencies.py`; Task 0 Step 2 verifies and adjusts if not.

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-16-student-performance-dashboard-v2.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
