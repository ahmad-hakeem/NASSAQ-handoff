"""
Regression tests for Task #155 — fail-closed school-id resolution across the
attendance, search and directory endpoints (audit rows #1-#11).

Tests are organised by **authorization pattern**, not by route module:

  (A) Caller with no resolvable school/workspace id (orphaned-tenant token,
      neither `tenant_id` nor an `independent_teacher` workspace) -> every
      affected endpoint must return 403 with the exact safe Arabic denial
      message used by the AI Insights resolver (Task #154 parity).

  (B) Cross-tenant isolation: a caller from tenant A querying any
      directory/search/attendance endpoint must never see tenant B rows,
      even though both tenants have data.

These tests intentionally cover ALL migrated endpoints in a single
parametrisation so the contract is enforced uniformly; adding a new
endpoint with the same pattern only requires extending the parametrize
list.
"""
import uuid

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


SAFE_AR_DENIED = "تعذّر التحقق من صلاحياتك للوصول إلى هذه البيانات"


# Endpoints migrated to require_request_school_id (Task #155 audit rows
# #1-#11 from the original matrix + #14-#17 added in the post-review re-scan).
# Each entry: (method, path).
SCOPED_ENDPOINTS = [
    ("GET", "/attendance/alerts"),
    ("GET", "/attendance/statistics"),
    ("GET", "/attendance/report/summary"),
    ("GET", "/attendance/excuses"),
    ("GET", "/search/global?q=a"),
    ("GET", "/search/autocomplete?q=a"),
    ("GET", "/directory/students"),
    ("GET", "/directory/teachers"),
    ("GET", "/directory/parents"),
    ("GET", "/directory/classes"),
    ("GET", "/directory/statistics"),
    ("GET", "/classes/options/grades"),
    ("GET", "/classes/options/teachers"),
    ("GET", "/classes/options/students"),
    ("GET", "/teachers/options/grades"),
]


def _extract_error_message(body) -> str | None:
    """NASSAQ wraps errors as `{success, error: {code, message}}` but some
    paths still emit FastAPI's default `{detail: ...}`. Accept both."""
    if not isinstance(body, dict):
        return None
    err = body.get("error")
    if isinstance(err, dict) and err.get("message"):
        return err["message"]
    return body.get("detail")


async def _mk_orphan_user_headers() -> dict:
    """Insert a school-affiliated user whose `tenant_id` is NULL in the
    database — neither the JWT nor `get_current_user`'s backfill can recover
    a tenant. Role is SCHOOL_ADMIN so RBAC gates do not block before our
    resolver runs."""
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.SCHOOL_ADMIN.value,
        "tenant_id": None,
        "email": f"orphan-{uid}@t.test",
        "full_name": f"Orphan-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    })
    token = create_access_token({
        "sub": uid,
        "role": UserRole.SCHOOL_ADMIN.value,
        "tenant_id": None,
    })
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ (A)
@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", SCOPED_ENDPOINTS)
async def test_unresolvable_school_id_returns_403_safe_arabic(
    client, method, path
):
    """Pattern A: a caller with no resolvable school/workspace id must
    receive a controlled 403 with the safe Arabic denial message — never a
    silent empty 200, never cross-tenant data. This is the same fail-closed
    contract Task #154 introduced for AI Insights, now enforced for every
    endpoint migrated in Task #155."""
    headers = await _mk_orphan_user_headers()

    r = await client.request(method, path, headers=headers)
    assert r.status_code == 403, (
        f"{method} {path} -> {r.status_code} {r.text} (expected 403 fail-closed)"
    )
    body = r.json() if r.headers.get("content-type", "").startswith(
        "application/json") else {}
    message = _extract_error_message(body)
    assert message == SAFE_AR_DENIED, (
        f"{method} {path} returned wrong error body: {body!r}"
    )
    # Defence-in-depth: never leak raw exception text.
    assert "Traceback" not in r.text
    assert "Exception" not in r.text


# ------------------------------------------------------------------ (B)
async def _seed_tenant_with_directory_rows(school_id: str, label: str) -> dict:
    """Add one class, one student, one teacher user, and one parent row to
    a tenant so directory/search endpoints have something to find."""
    cls_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cls_id, "school_id": school_id, "tenant_id": school_id,
        "name": f"{label}-class",
    })
    stu_id = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": stu_id, "school_id": school_id, "tenant_id": school_id,
        "full_name": f"{label}-student", "class_id": cls_id, "is_active": True,
    })
    tch_user_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": tch_user_id, "role": UserRole.TEACHER.value,
        "tenant_id": school_id, "email": f"t-{tch_user_id}@t.test",
        "full_name": f"{label}-teacher", "is_active": True, "password_hash": "x",
    })
    par_id = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": par_id, "school_id": school_id,
        "full_name": f"{label}-parent", "is_active": True,
    })
    return {
        "class_id": cls_id, "student_id": stu_id,
        "teacher_user_id": tch_user_id, "parent_id": par_id,
        "label": label,
    }


@pytest.mark.asyncio
async def test_directory_search_cross_tenant_isolation(
    client, tenant_a, tenant_b
):
    """Pattern B: with directory rows in BOTH tenants, a tenant-A admin must
    only see tenant-A rows on every directory/search endpoint. This catches
    any reintroduction of the broad-fallback foot-gun (`{} if not school_id`)
    that the audit doc enumerated as Task #155 confirmed-vulnerable rows."""
    a = await _seed_tenant_with_directory_rows(tenant_a, "A")
    b = await _seed_tenant_with_directory_rows(tenant_b, "B")

    a_user_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": a_user_id, "role": UserRole.SCHOOL_ADMIN.value,
        "tenant_id": tenant_a, "email": f"adm-{a_user_id}@t.test",
        "full_name": "A-admin", "is_active": True, "password_hash": "x",
    })
    headers = {"Authorization": "Bearer " + create_access_token({
        "sub": a_user_id, "role": UserRole.SCHOOL_ADMIN.value,
        "tenant_id": tenant_a,
    })}

    # /directory/students -- must list A's student, not B's.
    r = await client.get("/directory/students", headers=headers)
    assert r.status_code == 200, r.text
    student_ids = {s["id"] for s in r.json().get("students", [])}
    assert a["student_id"] in student_ids
    assert b["student_id"] not in student_ids

    # /directory/teachers -- A-teacher present, B-teacher absent.
    r = await client.get("/directory/teachers", headers=headers)
    assert r.status_code == 200, r.text
    teacher_ids = {t["id"] for t in r.json().get("teachers", [])}
    assert a["teacher_user_id"] in teacher_ids
    assert b["teacher_user_id"] not in teacher_ids

    # /directory/parents -- A-parent present, B-parent absent.
    r = await client.get("/directory/parents", headers=headers)
    assert r.status_code == 200, r.text
    parent_ids = {p["id"] for p in r.json().get("parents", [])}
    assert a["parent_id"] in parent_ids
    assert b["parent_id"] not in parent_ids

    # /directory/classes -- A-class present, B-class absent.
    r = await client.get("/directory/classes", headers=headers)
    assert r.status_code == 200, r.text
    class_ids = {c["id"] for c in r.json().get("classes", [])}
    assert a["class_id"] in class_ids
    assert b["class_id"] not in class_ids

    # /directory/statistics -- counts must reflect only tenant A.
    r = await client.get("/directory/statistics", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    # The endpoint shape is { students_total, teachers_total, ... } -- locate
    # whichever student-count key it uses defensively.
    students_total = (
        body.get("students_total")
        or body.get("students", {}).get("total")
        or body.get("totals", {}).get("students")
    )
    assert students_total is not None, body
    # Tenant A has exactly one student we seeded; tenant B has its own. The
    # count for A must NOT include B's student.
    assert students_total == 1, body

    # /search/global -- looking for the shared substring 'student' must not
    # surface tenant B's student row.
    r = await client.get("/search/global?q=student", headers=headers)
    assert r.status_code == 200, r.text
    found_student_ids = {s["id"] for s in r.json().get("students", [])}
    assert a["student_id"] in found_student_ids
    assert b["student_id"] not in found_student_ids
