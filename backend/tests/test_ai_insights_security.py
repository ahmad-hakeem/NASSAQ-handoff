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
from datetime import datetime, timezone

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


AI_INSIGHTS_ENDPOINTS = (
    "/ai/insights/overview",
    "/ai/insights/predictions",
    "/ai/insights/recommendations",
    "/ai/insights/alerts",
    "/ai/insights/at-risk-students",
)

OVERVIEW_TOP_KEYS = {
    "overall_score", "trend", "trend_value", "has_data",
    "last_updated", "metrics",
}
OVERVIEW_METRIC_KEYS = {
    "attendance_rate", "engagement_rate", "student_teacher_ratio",
    "total_students", "total_teachers", "has_attendance_data",
    "previous_month_score",
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
    workspace school row that resolve_ai_insights_scope looks up."""
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    })
    workspace_id = None
    if with_workspace:
        workspace_id = f"itw_{uid}"
        await gd_insert(db.session, "schools", {
            "id": workspace_id,
            "name": f"Workspace-{uid[:6]}",
            "code": workspace_id,
            "status": "active",
            "country": "SA",
            "language": "ar",
        })
    return {
        "id": uid,
        "workspace_id": workspace_id,
        "headers": _headers(uid, UserRole.INDEPENDENT_TEACHER.value, None),
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
