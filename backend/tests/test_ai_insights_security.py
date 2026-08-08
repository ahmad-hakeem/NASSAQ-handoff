"""
Regression tests for Task #154 — AI Insights authorization hardening (H1).

Three test groups:
  (a) Independent teacher with no resolvable workspace -> 403 + safe Arabic
      message on every affected endpoint; never empty 200, never global counts.
  (b) Independent teacher with a workspace but zero owned records -> documented
      empty-shape payload (schema parity with populated response, not equal to
      platform-wide aggregates).
  (c) Cross-isolation: two independent teachers each with their own student see
      only their own; a school teacher with one assigned class never sees
      another teacher's class in the same school.
"""
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


async def _seed_teacher(school_id: str) -> str:
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid, "school_id": school_id, "full_name": f"T-{tid[:6]}",
    })
    return tid


async def _seed_grade(school_id: str, student_id: str, percentage: float) -> None:
    """Insert a `student_grades` row keyed by tenant_id (the column the
    Hakim risk engine reads). Used to seed deterministic academic
    signals for the principal/admin populated-payload tests."""
    await gd_insert(db.session, "student_grades", {
        "id": str(uuid.uuid4()),
        "tenant_id": school_id,
        "student_id": student_id,
        "percentage": percentage,
        "graded_at": datetime.now(timezone.utc).isoformat(),
    })


async def _seed_low_attendance(school_id: str, student_id: str, days: int = 5) -> None:
    """Seed `days` consecutive absences for a student so the Hakim risk
    engine yields a low attendance score and the student lands in the
    intervention/at-risk list."""
    today = datetime.now(timezone.utc)
    for i in range(days):
        d = (today - timedelta(days=i + 1)).strftime("%Y-%m-%d")
        await gd_insert(db.session, "attendance", {
            "id": str(uuid.uuid4()),
            "school_id": school_id,
            "student_id": student_id,
            "date": d,
            "status": "absent",
        })


AI_INSIGHTS_ENDPOINTS = (
    "/ai/insights/overview",
    "/ai/insights/predictions",
    "/ai/insights/recommendations",
    "/ai/insights/alerts",
    "/ai/insights/at-risk-students",
)

OVERVIEW_TOP_KEYS = {
    "overall_score", "trend", "trend_value", "has_data", "score_available",
    "scope_level", "last_updated", "metrics",
}
OVERVIEW_METRIC_KEYS = {
    "attendance_rate", "engagement_rate", "has_engagement_data",
    "student_teacher_ratio", "total_students", "total_teachers",
    "has_attendance_data", "previous_month_score",
}


def _headers(user_id: str, role: str, tenant_id):
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_independent_teacher(*, with_workspace: bool):
    """Insert an independent_teacher user. Optionally also create the
    workspace school row that resolve_ai_insights_scope looks up.

    The minted bearer always carries ``tenant_id=itw_{uid}`` — the
    post-bootstrap token shape. Since Task #183 the global
    ``require_workspace_materialised`` gate 409s any IT bearer whose
    ``tenant_id`` is NULL before the route runs, so a pre-bootstrap token
    can no longer reach the AI Insights resolver at all. With
    ``with_workspace=False`` the token is materialised but the workspace
    row is absent — exercising the resolver's own fail-closed 403."""
    uid = str(uuid.uuid4())
    workspace_id = f"itw_{uid}"
    if with_workspace:
        # Schools row FIRST: users.tenant_id has an FK to schools.id.
        await gd_insert(db.session, "schools", {
            "id": workspace_id,
            "name": f"Workspace-{uid[:6]}",
            "code": workspace_id,
            "status": "active",
            "country": "SA",
            "language": "ar",
        })
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        # DB tenant_id only when the schools row exists (FK); the JWT below
        # always carries it — the #183 gate is a JWT-only check.
        "tenant_id": workspace_id if with_workspace else None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    })
    return {
        "id": uid,
        "workspace_id": workspace_id,
        "headers": _headers(uid, UserRole.INDEPENDENT_TEACHER.value, workspace_id),
    }


async def _seed_workspace_class_and_student(workspace_id: str):
    """Add one class + one active student to a workspace so the resolver
    returns a populated VALID_SCOPE."""
    cid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": workspace_id,
        "name": f"WC-{cid[:6]}",
    })
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": workspace_id,
        "full_name": f"WS-{sid[:6]}",
        "class_id": cid,
        "is_active": True,
    })
    return {"class_id": cid, "student_id": sid}


# ------------------------------------------------------------------ (a)
SAFE_AR_DENIED = "تعذّر التحقق من صلاحياتك للوصول إلى هذه البيانات"


@pytest.mark.asyncio
async def test_independent_teacher_no_workspace_returns_403_safe_arabic(
    client, seeded_school
):
    """An independent teacher whose workspace cannot be resolved must
    receive a controlled 403 with the safe Arabic denial message on EVERY
    AI Insights endpoint — never silently fall through to the global
    payload, never silently return an empty 200 that masks the real ACL/
    resolution failure."""
    it = await _mk_independent_teacher(with_workspace=False)

    for path in AI_INSIGHTS_ENDPOINTS:
        r = await client.get(path, headers=it["headers"])
        assert r.status_code == 403, (
            f"{path} -> {r.status_code} {r.text} (expected 403 fail-closed)"
        )
        body = r.json()
        # NASSAQ uses a custom error envelope:
        #   { success: false, error: { code: "HTTP_403", message: "..." } }
        # Accept either that envelope or the default FastAPI {"detail": "..."}.
        message = None
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                message = err.get("message")
            if message is None:
                message = body.get("detail")
        assert message == SAFE_AR_DENIED, (
            f"{path} returned wrong error body: {body!r}"
        )
        # Defence-in-depth: response body must NOT leak raw exception text
        # or English stack traces.
        assert "Traceback" not in r.text
        assert "Exception" not in r.text


@pytest.mark.asyncio
async def test_school_teacher_missing_identity_fields_returns_403(
    client, tenant_a
):
    """A school-teacher token whose `teacher_id` or `tenant_id` cannot be
    resolved must fail closed with safe Arabic 403 — never silently
    degrade into the empty-payload path, so that real ACL/provisioning
    failures stay visible in monitoring."""
    # Case 1: teacher_id missing from token entirely.
    uid_no_tid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid_no_tid, "role": UserRole.TEACHER.value,
        "tenant_id": tenant_a, "email": f"u-{uid_no_tid}@t.test",
        "full_name": "NoTeacherId", "is_active": True, "password_hash": "x",
    })
    headers_no_tid = {"Authorization": "Bearer " + create_access_token({
        "sub": uid_no_tid, "role": UserRole.TEACHER.value,
        "tenant_id": tenant_a,
        # teacher_id intentionally omitted
    })}

    # NOTE: missing `tenant_id` on the JWT alone is NOT a resolution failure
    # — `get_current_user` backfills it from the persisted user record. The
    # only resolver-level identity failure for school teachers is a missing
    # `teacher_id`, which the user table does not silently backfill.

    for label, headers in (("missing-teacher-id", headers_no_tid),):
        for path in AI_INSIGHTS_ENDPOINTS:
            r = await client.get(path, headers=headers)
            assert r.status_code == 403, (
                f"{label} {path} -> {r.status_code} {r.text} "
                f"(expected fail-closed 403)"
            )
            body = r.json() if r.headers.get("content-type", "").startswith(
                "application/json") else {}
            message = None
            if isinstance(body, dict):
                err = body.get("error")
                if isinstance(err, dict):
                    message = err.get("message")
                if message is None:
                    message = body.get("detail")
            assert message == SAFE_AR_DENIED, (
                f"{label} {path} returned wrong error body: {body!r}"
            )


# ------------------------------------------------------------------ (b)
@pytest.mark.asyncio
async def test_independent_teacher_empty_workspace_schema_parity(
    client, seeded_school
):
    """Workspace exists but has no records -> empty-shape payload with full
    schema parity, and counts are not equal to the platform aggregate."""
    it = await _mk_independent_teacher(with_workspace=True)

    overview = await client.get("/ai/insights/overview", headers=it["headers"])
    assert overview.status_code == 200
    body = overview.json()

    # Schema parity: every key the populated response would return must be
    # present (zeroed), so the frontend contract does not silently break.
    assert set(body.keys()) == OVERVIEW_TOP_KEYS
    assert set(body["metrics"].keys()) == OVERVIEW_METRIC_KEYS
    assert body["metrics"]["total_students"] == 0
    assert body["metrics"]["total_teachers"] == 0
    assert body["has_data"] is False
    # Isolation: must NOT equal the seeded other-tenant total (10).
    assert body["metrics"]["total_students"] != len(seeded_school.students)

    for path in ("/ai/insights/predictions", "/ai/insights/recommendations",
                 "/ai/insights/alerts", "/ai/insights/at-risk-students"):
        r = await client.get(path, headers=it["headers"])
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text}"
        assert isinstance(r.json(), list)
        assert r.json() == [], f"{path} should be empty for IT with no records"


# ------------------------------------------------------------------ (c)
@pytest.mark.asyncio
async def test_two_independent_teachers_are_isolated(client):
    """Each independent teacher's overview must reflect only their own
    workspace's students, never the other's."""
    a = await _mk_independent_teacher(with_workspace=True)
    b = await _mk_independent_teacher(with_workspace=True)

    a_seed = await _seed_workspace_class_and_student(a["workspace_id"])
    # Teacher B gets two students so the totals are clearly distinguishable.
    await _seed_workspace_class_and_student(b["workspace_id"])
    await _seed_workspace_class_and_student(b["workspace_id"])

    res_a = await client.get("/ai/insights/overview", headers=a["headers"])
    res_b = await client.get("/ai/insights/overview", headers=b["headers"])
    assert res_a.status_code == 200 and res_b.status_code == 200
    body_a, body_b = res_a.json(), res_b.json()

    # Schema parity for the populated path too.
    assert set(body_a.keys()) == OVERVIEW_TOP_KEYS
    assert set(body_a["metrics"].keys()) == OVERVIEW_METRIC_KEYS

    assert body_a["metrics"]["total_students"] == 1, body_a["metrics"]
    assert body_b["metrics"]["total_students"] == 2, body_b["metrics"]

    # Cross-listing endpoints must not leak the other teacher's students.
    risks_a = await client.get("/ai/insights/at-risk-students", headers=a["headers"])
    risks_b = await client.get("/ai/insights/at-risk-students", headers=b["headers"])
    assert risks_a.status_code == 200 and risks_b.status_code == 200
    a_ids = {r["id"] for r in risks_a.json()}
    b_ids = {r["id"] for r in risks_b.json()}
    # No overlap between the two teachers' student id sets.
    assert a_ids.isdisjoint(b_ids)


@pytest.mark.asyncio
async def test_school_teachers_in_same_school_are_isolated(
    client, tenant_a
):
    """Two school teachers in the SAME school, each assigned to a different
    class, must each see only their own class's students."""
    # Teacher A
    ta_user_id = str(uuid.uuid4())
    ta_teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": ta_user_id, "role": UserRole.TEACHER.value, "tenant_id": tenant_a,
        "teacher_id": ta_teacher_id, "email": f"ta-{ta_user_id}@t.test",
        "full_name": "TA", "is_active": True, "password_hash": "x",
    })
    await gd_insert(db.session, "teachers", {
        "id": ta_teacher_id, "school_id": tenant_a, "user_id": ta_user_id,
        "full_name": "TA",
    })
    cls_a = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cls_a, "school_id": tenant_a, "name": "TA-class",
    })
    await gd_insert(db.session, "teacher_class_assignments", {
        "id": str(uuid.uuid4()), "teacher_id": ta_teacher_id,
        "school_id": tenant_a, "class_id": cls_a,
    })
    sa_id = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sa_id, "school_id": tenant_a, "full_name": "Student-A",
        "class_id": cls_a, "is_active": True,
    })

    # Teacher B
    tb_user_id = str(uuid.uuid4())
    tb_teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": tb_user_id, "role": UserRole.TEACHER.value, "tenant_id": tenant_a,
        "teacher_id": tb_teacher_id, "email": f"tb-{tb_user_id}@t.test",
        "full_name": "TB", "is_active": True, "password_hash": "x",
    })
    await gd_insert(db.session, "teachers", {
        "id": tb_teacher_id, "school_id": tenant_a, "user_id": tb_user_id,
        "full_name": "TB",
    })
    cls_b = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cls_b, "school_id": tenant_a, "name": "TB-class",
    })
    await gd_insert(db.session, "teacher_class_assignments", {
        "id": str(uuid.uuid4()), "teacher_id": tb_teacher_id,
        "school_id": tenant_a, "class_id": cls_b,
    })
    sb_id = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sb_id, "school_id": tenant_a, "full_name": "Student-B",
        "class_id": cls_b, "is_active": True,
    })

    headers_a = {"Authorization": f"Bearer " + create_access_token({
        "sub": ta_user_id, "role": UserRole.TEACHER.value,
        "tenant_id": tenant_a, "teacher_id": ta_teacher_id,
    })}
    headers_b = {"Authorization": f"Bearer " + create_access_token({
        "sub": tb_user_id, "role": UserRole.TEACHER.value,
        "tenant_id": tenant_a, "teacher_id": tb_teacher_id,
    })}

    ov_a = (await client.get("/ai/insights/overview", headers=headers_a)).json()
    ov_b = (await client.get("/ai/insights/overview", headers=headers_b)).json()

    assert set(ov_a.keys()) == OVERVIEW_TOP_KEYS
    assert set(ov_b.keys()) == OVERVIEW_TOP_KEYS
    assert ov_a["metrics"]["total_students"] == 1
    assert ov_b["metrics"]["total_students"] == 1


# ------------------------------------------------------------------ (d)
# Task #156 — confirm principals / school admins still see their own
# tenant's populated, school-scoped data on the same five endpoints
# the IT/teacher hardening tests cover. Without this, a future tweak to
# `resolve_ai_insights_scope` could silently drop the admin/principal
# view (e.g. if the `None` branch were accidentally folded into the
# fail-closed branch) and the H1 tests would still all pass.

async def _mk_admin_user(role: UserRole, tenant_id: str) -> dict:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": role.value, "tenant_id": tenant_id,
        "email": f"{role.value}-{uid}@t.test",
        "full_name": f"{role.value}-{uid[:6]}",
        "is_active": True, "password_hash": "x",
    })
    return {
        "id": uid,
        "headers": _headers(uid, role.value, tenant_id),
    }


@pytest.mark.asyncio
async def test_principal_sees_populated_school_scoped_overview(
    client, seeded_school
):
    """A principal in the seeded tenant must see the school's real
    student/teacher counts on /ai/insights/overview — never the empty
    payload (which is reserved for IT/teachers with no resolvable scope)
    and never the default-zero shape masking a dropped principal path."""
    # Add a couple of teachers so total_teachers is also populated.
    await _seed_teacher(seeded_school.id)
    await _seed_teacher(seeded_school.id)
    # Seed a grade so the academic signal path is exercised end-to-end
    # (the task explicitly asks for students/teachers/grades in scope).
    await _seed_grade(seeded_school.id, seeded_school.students[0]["id"], 88.0)

    principal = await _mk_admin_user(UserRole.SCHOOL_PRINCIPAL, seeded_school.id)
    r = await client.get("/ai/insights/overview", headers=principal["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == OVERVIEW_TOP_KEYS
    assert set(body["metrics"].keys()) == OVERVIEW_METRIC_KEYS
    assert body["metrics"]["total_students"] == len(seeded_school.students)
    assert body["metrics"]["total_teachers"] == 2
    assert body["has_data"] is True


@pytest.mark.asyncio
async def test_school_admin_sees_populated_school_scoped_overview(
    client, seeded_school
):
    """Same contract as the principal: a school_admin must receive the
    populated, school-scoped overview, not the empty/zeroed payload."""
    await _seed_teacher(seeded_school.id)
    await _seed_grade(seeded_school.id, seeded_school.students[0]["id"], 92.0)

    admin = await _mk_admin_user(UserRole.SCHOOL_ADMIN, seeded_school.id)
    r = await client.get("/ai/insights/overview", headers=admin["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["metrics"]["total_students"] == len(seeded_school.students)
    assert body["metrics"]["total_teachers"] == 1
    assert body["has_data"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [
    UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN,
])
async def test_admin_predictions_recommendations_alerts_populated(
    client, seeded_school, role
):
    """Predictions / recommendations / alerts are list-shaped endpoints.
    For an admin/principal in a tenant that has data, they must respond
    200 with a list — and recommendations + alerts always include at
    least the default fallback entry (so an empty list would indicate
    the principal path was silently dropped)."""
    await _seed_teacher(seeded_school.id)
    await _seed_grade(seeded_school.id, seeded_school.students[0]["id"], 78.0)
    # Predictions only emit an attendance card when there IS attendance data
    # (A1: zero-data weeks emit nothing rather than a fake 0% trend). Seed a
    # full two-week signal (>= 5 records in each week) so one of the three
    # attendance branches deterministically fires.
    await _seed_low_attendance(
        seeded_school.id, seeded_school.students[0]["id"], days=14,
    )
    admin = await _mk_admin_user(role, seeded_school.id)

    # All three list endpoints have at least one guaranteed entry once
    # the resolver hands the admin/principal the school scope:
    #   - predictions: appends one of three attendance branches (or the
    #     "insufficient data" card) whenever attendance data exists.
    #   - recommendations: always appends a default fallback if no rule
    #     fires.
    #   - alerts: always appends a default "no urgent alerts" entry if
    #     no rule fires.
    # If any returned `[]`, that would mean the admin path was
    # accidentally routed through the IT empty-scope branch.
    for path in ("/ai/insights/predictions",
                 "/ai/insights/recommendations",
                 "/ai/insights/alerts"):
        r = await client.get(path, headers=admin["headers"])
        assert r.status_code == 200, (
            f"{role.value} {path} -> {r.status_code} {r.text}"
        )
        body = r.json()
        assert isinstance(body, list), (
            f"{role.value} {path} body not a list: {body!r}"
        )
        assert len(body) >= 1, (
            f"{role.value} {path} unexpectedly empty: {body!r}"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [
    UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN,
])
async def test_admin_at_risk_students_returns_school_scoped_list(
    client, seeded_school, role
):
    """At-risk students for an admin/principal must respond 200 with a
    school-scoped list AND must surface the seeded at-risk signal — a
    student with chronic absences and a low grade. This guarantees the
    populated path is exercised, not just the empty-but-200 shape."""
    target = seeded_school.students[0]
    await _seed_low_attendance(seeded_school.id, target["id"], days=10)
    await _seed_grade(seeded_school.id, target["id"], 35.0)

    admin = await _mk_admin_user(role, seeded_school.id)
    r = await client.get(
        "/ai/insights/at-risk-students", headers=admin["headers"])
    assert r.status_code == 200, f"{role.value} -> {r.status_code} {r.text}"
    body = r.json()
    assert isinstance(body, list)
    own_ids = {s["id"] for s in seeded_school.students}
    for row in body:
        # Every returned student must belong to the admin's school.
        assert row["id"] in own_ids, (
            f"{role.value} saw foreign student id {row['id']!r}; "
            f"own school student ids = {own_ids}"
        )
    # The seeded at-risk student must appear — proves admin/principal
    # actually receive a populated at-risk payload, not just an empty
    # 200 that would mask a regression to the no-scope path.
    assert any(row["id"] == target["id"] for row in body), (
        f"{role.value} at-risk-students missing seeded at-risk student "
        f"{target['id']!r}; got {[r['id'] for r in body]}"
    )


@pytest.mark.asyncio
async def test_principal_in_tenant_a_does_not_see_tenant_b_data(
    client, seeded_school, tenant_b, tenant_b_students
):
    """Cross-tenant isolation for the admin/principal path: a principal
    in tenant A must see tenant A counts only — never the sum of A+B,
    and never tenant B's students on at-risk-students."""
    # Make tenant B distinguishable: add one teacher to B so its counts
    # are clearly different from A.
    await _seed_teacher(tenant_b)

    principal_a = await _mk_admin_user(
        UserRole.SCHOOL_PRINCIPAL, seeded_school.id)

    overview = await client.get(
        "/ai/insights/overview", headers=principal_a["headers"])
    assert overview.status_code == 200, overview.text
    body = overview.json()
    # Tenant A has 10 seeded students; tenant B has 3. The principal in A
    # must see exactly A's count, never the global 13.
    assert body["metrics"]["total_students"] == len(seeded_school.students)
    assert body["metrics"]["total_students"] != (
        len(seeded_school.students) + len(tenant_b_students)
    )
    # Tenant A has 0 teachers seeded; tenant B has 1. Must NOT leak.
    assert body["metrics"]["total_teachers"] == 0

    # at-risk-students cross-isolation: no tenant B student id may appear.
    risks = await client.get(
        "/ai/insights/at-risk-students", headers=principal_a["headers"])
    assert risks.status_code == 200
    b_ids = {s["id"] for s in tenant_b_students}
    a_returned_ids = {row["id"] for row in risks.json()}
    assert a_returned_ids.isdisjoint(b_ids), (
        f"Principal in tenant A leaked tenant B students: "
        f"{a_returned_ids & b_ids}"
    )


@pytest.mark.asyncio
async def test_school_admin_in_tenant_a_does_not_see_tenant_b_data(
    client, seeded_school, tenant_b, tenant_b_students
):
    """Same cross-tenant isolation contract for school_admin."""
    admin_a = await _mk_admin_user(UserRole.SCHOOL_ADMIN, seeded_school.id)

    overview = await client.get(
        "/ai/insights/overview", headers=admin_a["headers"])
    assert overview.status_code == 200, overview.text
    assert overview.json()["metrics"]["total_students"] == len(
        seeded_school.students)

    risks = await client.get(
        "/ai/insights/at-risk-students", headers=admin_a["headers"])
    assert risks.status_code == 200
    b_ids = {s["id"] for s in tenant_b_students}
    assert {row["id"] for row in risks.json()}.isdisjoint(b_ids)
