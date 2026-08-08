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
    ("GET", "/search/palette?q=ab"),
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


# ------------------------------------------------------------------ (C)
# Sanitized payloads + the school-staff command palette (/search/palette).

# Any key containing one of these substrings must NEVER appear anywhere in a
# search/directory response body (raw `users` rows carry password_hash and
# MFA/reset material; raw student/parent rows carry family PII fields that
# the projections intentionally drop).
_SENSITIVE_KEY_PATTERNS = (
    "password", "mfa", "secret", "reset_token", "token_hash", "otp",
)


def _assert_no_sensitive_keys(obj, path="$"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            assert not any(p in kl for p in _SENSITIVE_KEY_PATTERNS), (
                f"sensitive key {k!r} leaked at {path}"
            )
            _assert_no_sensitive_keys(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _assert_no_sensitive_keys(v, f"{path}[{i}]")


async def _mk_role_user_headers(role: UserRole, tenant_id) -> dict:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": role.value,
        "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test",
        "full_name": f"U-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    })
    token = create_access_token({
        "sub": uid, "role": role.value, "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}, uid


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [
    UserRole.PARENT,
    # UserRole.STUDENT is denied even earlier: student login is globally
    # disabled at get_current_user (401), so the palette is unreachable.
    UserRole.INDEPENDENT_TEACHER,
    UserRole.PLATFORM_ADMIN,
])
async def test_palette_denies_non_school_staff(client, tenant_a, role):
    """/search/palette is school-staff only: parents/students must not
    enumerate school data, platform admins have no school context, and
    independent teachers use their own workspace endpoint."""
    headers, _ = await _mk_role_user_headers(role, tenant_a)
    r = await client.get("/search/palette?q=ab", headers=headers)
    assert r.status_code == 403, f"{role} -> {r.status_code} {r.text}"


@pytest.mark.asyncio
async def test_palette_unreachable_for_student_accounts(client, tenant_a):
    """Students are blocked at authentication itself (global student-login
    gate) — the palette must stay unreachable (401), never 200."""
    headers, _ = await _mk_role_user_headers(UserRole.STUDENT, tenant_a)
    r = await client.get("/search/palette?q=ab", headers=headers)
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_palette_leadership_results_scoped_and_projected(
    client, tenant_a, tenant_b
):
    """Leadership palette: sees own-tenant students/classes/teachers with
    role-aware hrefs, never tenant-B rows, and only the minimal projection
    {id, category, primary, secondary, href} — no raw rows, no PII keys."""
    a = await _seed_tenant_with_directory_rows(tenant_a, "A")
    b = await _seed_tenant_with_directory_rows(tenant_b, "B")
    headers, _ = await _mk_role_user_headers(UserRole.SCHOOL_ADMIN, tenant_a)

    r = await client.get("/search/palette?q=student", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"q", "students", "classes", "teachers"}
    _assert_no_sensitive_keys(body)

    student_ids = {s["id"] for s in body["students"]}
    assert a["student_id"] in student_ids
    assert b["student_id"] not in student_ids
    for item in body["students"]:
        assert set(item.keys()) == {"id", "category", "primary", "secondary", "href"}
        assert item["href"] == f"/principal/students/{item['id']}"
        # Least-PII: the national id must never be surfaced as display text.
        assert "national" not in str(item.get("secondary", "")).lower()

    # Teachers category is leadership-only and must be tenant-scoped too.
    r = await client.get("/search/palette?q=teacher", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    _assert_no_sensitive_keys(body)
    teacher_ids = {t["id"] for t in body["teachers"]}
    assert a["teacher_user_id"] in teacher_ids
    assert b["teacher_user_id"] not in teacher_ids
    for item in body["teachers"]:
        assert item["href"] == "/admin/users-management?filter=teachers"

    # Classes route leadership to the management page.
    r = await client.get("/search/palette?q=class", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    class_ids = {c["id"] for c in body["classes"]}
    assert a["class_id"] in class_ids
    assert b["class_id"] not in class_ids
    for item in body["classes"]:
        assert item["href"] == "/admin/users-management?filter=classes"


@pytest.mark.asyncio
async def test_palette_teacher_is_class_scoped(client, tenant_a):
    """A teacher only sees students of classes they are assigned to; the
    teachers category stays empty; hrefs use the teacher deep-link."""
    seeded = await _seed_tenant_with_directory_rows(tenant_a, "A")

    # Second student in a class the teacher is NOT assigned to.
    other_cls = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": other_cls, "school_id": tenant_a, "tenant_id": tenant_a,
        "name": "A-other-class",
    })
    other_stu = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": other_stu, "school_id": tenant_a, "tenant_id": tenant_a,
        "full_name": "A-student-other", "class_id": other_cls,
        "is_active": True,
    })

    headers, teacher_uid = await _mk_role_user_headers(UserRole.TEACHER, tenant_a)
    # Real school teachers live in BOTH `users` (login) and `teachers`
    # (authoritative row keyed by school_id). teacher_assignments.teacher_id
    # is an FK to teachers.id; get_current_user auto-links via email.
    teacher_row_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_row_id, "school_id": tenant_a,
        "full_name": "A-teacher-row", "email": f"u-{teacher_uid}@t.test",
        "is_active": True,
    })
    subj_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subj_id, "school_id": tenant_a, "tenant_id": tenant_a,
        "name": "A-subject",
    })
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()), "tenant_id": tenant_a,
        "teacher_id": teacher_row_id, "class_id": seeded["class_id"],
        "subject_id": subj_id, "is_active": True,
    })

    r = await client.get("/search/palette?q=student", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    _assert_no_sensitive_keys(body)
    student_ids = {s["id"] for s in body["students"]}
    assert seeded["student_id"] in student_ids
    assert other_stu not in student_ids, "teacher saw a student outside their classes"
    assert body["teachers"] == [], "teachers category must be leadership-only"
    for item in body["students"]:
        assert item["href"].startswith(f"/teacher/students?student_id={item['id']}")


@pytest.mark.asyncio
async def test_palette_short_query_returns_empty_payload(client, tenant_a):
    """Sub-min-length queries return an empty payload, never an error, so
    the FE can call on every keystroke."""
    headers, _ = await _mk_role_user_headers(UserRole.SCHOOL_ADMIN, tenant_a)
    r = await client.get("/search/palette?q=a", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"q": "a", "students": [], "classes": [], "teachers": []}


@pytest.mark.asyncio
async def test_search_global_and_directory_teachers_sanitized(
    client, tenant_a
):
    """Regression: /search/global and /directory/teachers used to return
    RAW users rows (password_hash + MFA fields) to any authenticated
    caller. Both must now return only projected display fields."""
    await _seed_tenant_with_directory_rows(tenant_a, "A")
    headers, _ = await _mk_role_user_headers(UserRole.SCHOOL_ADMIN, tenant_a)

    r = await client.get("/search/global?q=A-", headers=headers)
    assert r.status_code == 200, r.text
    _assert_no_sensitive_keys(r.json())

    r = await client.get("/directory/teachers", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    _assert_no_sensitive_keys(body)
    for t in body.get("teachers", []):
        assert set(t.keys()) <= {"id", "full_name", "email", "phone", "is_active"}


# ------------------------------------------------------------------ (D)
# Add-flow audit 2026-07-28: /classes/options/students must emit grade_id in
# the SAME id space as /classes/options/grades (tenant grade_levels row id
# when one matches, else the canonical grade number), or the class wizard's
# `student.grade_id === selected grade id` filter hides the whole roster.

@pytest.mark.asyncio
async def test_class_students_options_grade_id_matches_grades_options(
    client, tenant_a
):
    # Tenant grade_levels row with a UUID id for canonical grade 3.
    grade3_row_id = str(uuid.uuid4())
    await gd_insert(db.session, "grade_levels", {
        "id": grade3_row_id, "school_id": tenant_a, "grade": 3,
        "name_ar": "الصف الثالث الابتدائي",
    })

    cls_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cls_id, "school_id": tenant_a, "tenant_id": tenant_a,
        "name": "فصل ثالث", "grade_id": grade3_row_id, "is_active": True,
    })

    # s1: own canonical grade value; s2: grade only derivable via the class;
    # s3: messy legacy value -> unknown ("" — must stay visible client-side).
    s1, s2, s3 = (str(uuid.uuid4()) for _ in range(3))
    await gd_insert(db.session, "students", {
        "id": s1, "school_id": tenant_a, "tenant_id": tenant_a,
        "full_name": "طالب-أ", "grade": "3", "is_active": True,
    })
    await gd_insert(db.session, "students", {
        "id": s2, "school_id": tenant_a, "tenant_id": tenant_a,
        "full_name": "طالب-ب", "class_id": cls_id, "is_active": True,
    })
    await gd_insert(db.session, "students", {
        "id": s3, "school_id": tenant_a, "tenant_id": tenant_a,
        "full_name": "طالب-ج", "grade": "0125", "is_active": True,
    })

    headers, _ = await _mk_role_user_headers(UserRole.SCHOOL_ADMIN, tenant_a)

    r = await client.get("/classes/options/grades", headers=headers)
    assert r.status_code == 200, r.text
    grade3_option = next(g for g in r.json()["grades"] if g["grade"] == 3)
    assert grade3_option["id"] == grade3_row_id  # tenant row id preserved

    r = await client.get("/classes/options/students", headers=headers)
    assert r.status_code == 200, r.text
    by_id = {s["student_id"]: s for s in r.json()["students"]}
    # Both resolvable students must carry the SAME id the grades dropdown
    # uses, so the wizard's equality filter matches.
    assert by_id[s1]["grade_id"] == grade3_option["id"]
    assert by_id[s2]["grade_id"] == grade3_option["id"]
    # Unknown grades stay "" (frontend keeps these students visible).
    assert by_id[s3]["grade_id"] == ""
