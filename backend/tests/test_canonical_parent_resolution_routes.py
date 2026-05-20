"""Task #465 — canonical parent resolution at every "notify parent" call-site.

Verifies that the three migrated routes (bulk-attendance, bulk-grades, and
AI-insights intervention) all resolve the parent user through
``guardian_links`` (not mutable parent_phone / parent_email / parents.email).

Sections:
  A. Helper unit tests (resolve_student_parent_user_id / bulk variant)
  B. POST /ai/insights/intervention  action_type=notify_parent
  C. POST /grades/bulk  — parent notification via guardian_links
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from dependencies import db as _db, UserRole, create_access_token
from engines.sql_utils import gd_find, gd_insert
from utils.parent_resolution import (
    PARENT_NOT_FOUND_AR,
    resolve_student_parent_user_id,
    resolve_students_parent_user_ids,
)


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tok(user: dict) -> dict:
    token = create_access_token(
        {"sub": user["id"], "role": user["role"], "tenant_id": user["tenant_id"]}
    )
    return {"Authorization": f"Bearer {token}"}


async def _mk_school() -> str:
    sid = str(uuid.uuid4())
    await gd_insert(_db.session, "schools", {
        "id": sid,
        "name": f"School-{sid[:6]}",
        "code": f"S{sid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    return sid


async def _mk_user(role_val: str, tenant_id: str) -> dict:
    uid = str(uuid.uuid4())
    u = {
        "id": uid,
        "role": role_val,
        "tenant_id": tenant_id,
        "email": f"{uid}@t.test",
        "full_name": f"User-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(_db.session, "users", u)
    return u


async def _mk_parent_user(tenant_id: str) -> dict:
    """Create a parent *user* row only — no students.parent_id link."""
    return await _mk_user("parent", tenant_id)


async def _mk_parent_with_row(tenant_id: str) -> dict:
    """Create both a parents row and a matching users row (same id).

    Required for tests that use ``students.parent_id``, which has a FK
    into the ``parents`` table.
    """
    pid = str(uuid.uuid4())
    await gd_insert(_db.session, "parents", {
        "id": pid,
        "full_name": f"Parent-{pid[:6]}",
        "email": f"p-{pid}@t.test",
        "school_id": tenant_id,
        "is_active": True,
    })
    u = {
        "id": pid,
        "role": "parent",
        "tenant_id": tenant_id,
        "email": f"p-{pid}@t.test",
        "full_name": f"Parent-{pid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(_db.session, "users", u)
    return u


async def _mk_student(
    school_id: str,
    *,
    parent_id: str | None = None,
    class_id: str | None = None,
) -> dict:
    sid = str(uuid.uuid4())
    await gd_insert(_db.session, "students", {
        "id": sid,
        "school_id": school_id,
        "full_name": f"ST-{sid[:6]}",
        "parent_id": parent_id,
        "class_id": class_id,
        "is_active": True,
    })
    return {"id": sid, "school_id": school_id, "parent_id": parent_id}


async def _link_guardian(
    student_id: str, parent_user_id: str, tenant_id: str
) -> None:
    """Insert an active guardian_links row (no parent_id on the student)."""
    await gd_insert(_db.session, "guardian_links", {
        "id": str(uuid.uuid4()),
        "student_id": student_id,
        "parent_ref": parent_user_id,
        "tenant_id": tenant_id,
        "is_active": True,
        "relationship_type": "father",
    })


async def _mk_realistic_parent(tenant_id: str) -> tuple[dict, dict]:
    """Create a separate parents row + users row bridged via the shared email.

    Mirrors what ``find_or_create_parent`` actually persists in production:
    a ``parents`` row scoped to the school (no persisted ``user_id``
    column) and a separate ``users`` row with ``role='parent'``. The
    only stable link between them is ``parents.email == users.email``.
    Returns ``(parent_row, user_row)``.
    """
    user_id = str(uuid.uuid4())
    parent_id = str(uuid.uuid4())
    email = f"p-{parent_id}@t.test"
    await gd_insert(_db.session, "users", {
        "id": user_id,
        "role": "parent",
        "tenant_id": tenant_id,
        "email": email,
        "full_name": f"Parent-{user_id[:6]}",
        "is_active": True,
        "password_hash": "x",
    })
    await gd_insert(_db.session, "parents", {
        "id": parent_id,
        "full_name": f"Parent-{user_id[:6]}",
        "email": email,
        "school_id": tenant_id,
        "is_active": True,
    })
    return ({"id": parent_id, "email": email},
            {"id": user_id, "email": email})


@pytest.mark.asyncio
async def test_resolver_bridges_students_parent_id_through_parents_email():
    """Production case: students.parent_id -> parents.id -> parents.email -> users.id.

    Regression for the false-positive "لا يوجد ولي أمر مرتبط بهذا الطالب"
    error in the Teacher Communication module — the previous resolver
    treated students.parent_id as a users.id directly and returned None
    for every student created through the principal flow (where
    students.parent_id is a parents.id, not a users.id).
    """
    school_id = await _mk_school()
    parent_row, user_row = await _mk_realistic_parent(school_id)
    student = await _mk_student(school_id, parent_id=parent_row["id"])
    result = await resolve_student_parent_user_id(student["id"], school_id)
    assert result == user_row["id"]


@pytest.mark.asyncio
async def test_resolver_bridges_guardian_links_parent_ref_as_parents_id():
    """relationship_routes_mod.py writes parent_ref = parents.id; bridge it."""
    school_id = await _mk_school()
    parent_row, user_row = await _mk_realistic_parent(school_id)
    student = await _mk_student(school_id)  # no students.parent_id
    # parent_ref holds parents.id (principal-managed linkage flow).
    await gd_insert(_db.session, "guardian_links", {
        "id": str(uuid.uuid4()),
        "student_id": student["id"],
        "parent_ref": parent_row["id"],
        "tenant_id": school_id,
        "is_active": True,
        "relationship_type": "mother",
    })
    result = await resolve_student_parent_user_id(student["id"], school_id)
    assert result == user_row["id"]


@pytest.mark.asyncio
async def test_resolver_prefers_guardian_links_parent_user_id_column():
    """The canonical parent_user_id column wins over any other source."""
    school_id = await _mk_school()
    parent_row, user_row = await _mk_realistic_parent(school_id)
    student = await _mk_student(school_id)
    await gd_insert(_db.session, "guardian_links", {
        "id": str(uuid.uuid4()),
        "student_id": student["id"],
        "parent_user_id": user_row["id"],
        # parent_ref intentionally points elsewhere — parent_user_id wins.
        "parent_ref": parent_row["id"],
        "tenant_id": school_id,
        "is_active": True,
        "relationship_type": "father",
    })
    result = await resolve_student_parent_user_id(student["id"], school_id)
    assert result == user_row["id"]


@pytest.mark.asyncio
async def test_bulk_resolver_bridges_realistic_parents_rows():
    """Bulk variant must also bridge parents.id -> parents.user_id -> users.id."""
    school_id = await _mk_school()
    p1_row, u1 = await _mk_realistic_parent(school_id)
    p2_row, u2 = await _mk_realistic_parent(school_id)
    s1 = await _mk_student(school_id, parent_id=p1_row["id"])
    s2 = await _mk_student(school_id)
    # s2 linked via guardian_links with parent_ref = parents.id.
    await gd_insert(_db.session, "guardian_links", {
        "id": str(uuid.uuid4()),
        "student_id": s2["id"],
        "parent_ref": p2_row["id"],
        "tenant_id": school_id,
        "is_active": True,
        "relationship_type": "mother",
    })
    result = await resolve_students_parent_user_ids(
        [s1["id"], s2["id"]], school_id,
    )
    assert result[s1["id"]] == u1["id"]
    assert result[s2["id"]] == u2["id"]


@pytest.mark.asyncio
async def test_resolver_rejects_cross_tenant_parents_row():
    """parents row in tenant B must not resolve a student in tenant A even
    when students.parent_id happens to match the foreign parents.id."""
    school_a = await _mk_school()
    school_b = await _mk_school()
    foreign_parent, foreign_user = await _mk_realistic_parent(school_b)
    student = await _mk_student(school_a, parent_id=foreign_parent["id"])
    result = await resolve_student_parent_user_id(student["id"], school_a)
    assert result is None


# ===========================================================================
# A. Helper unit tests
# ===========================================================================


@pytest.mark.asyncio
async def test_resolver_returns_none_for_orphan():
    school_id = await _mk_school()
    student = await _mk_student(school_id)
    result = await resolve_student_parent_user_id(student["id"], school_id)
    assert result is None


@pytest.mark.asyncio
async def test_resolver_resolves_via_parent_id_fallback():
    school_id = await _mk_school()
    parent = await _mk_parent_with_row(school_id)
    student = await _mk_student(school_id, parent_id=parent["id"])
    result = await resolve_student_parent_user_id(student["id"], school_id)
    assert result == parent["id"]


@pytest.mark.asyncio
async def test_resolver_prefers_guardian_links_over_parent_id():
    """guardian_links.parent_ref wins even when students.parent_id is set."""
    school_id = await _mk_school()
    old_parent = await _mk_parent_with_row(school_id)
    new_parent = await _mk_parent_user(school_id)
    student = await _mk_student(school_id, parent_id=old_parent["id"])
    await _link_guardian(student["id"], new_parent["id"], school_id)
    result = await resolve_student_parent_user_id(student["id"], school_id)
    assert result == new_parent["id"]


@pytest.mark.asyncio
async def test_resolver_guardian_links_only_no_parent_id():
    """Works when student has no parent_id but has an active guardian_link."""
    school_id = await _mk_school()
    parent = await _mk_parent_user(school_id)
    student = await _mk_student(school_id)  # no parent_id
    await _link_guardian(student["id"], parent["id"], school_id)
    result = await resolve_student_parent_user_id(student["id"], school_id)
    assert result == parent["id"]


@pytest.mark.asyncio
async def test_resolver_cross_tenant_isolation():
    """A guardian_links row in tenant B must not resolve for tenant A."""
    school_a = await _mk_school()
    school_b = await _mk_school()
    parent_b = await _mk_parent_user(school_b)
    student = await _mk_student(school_a)
    # Link exists only in tenant B's namespace
    await gd_insert(_db.session, "guardian_links", {
        "id": str(uuid.uuid4()),
        "student_id": student["id"],
        "parent_ref": parent_b["id"],
        "tenant_id": school_b,
        "is_active": True,
        "relationship_type": "mother",
    })
    result = await resolve_student_parent_user_id(student["id"], school_a)
    assert result is None


@pytest.mark.asyncio
async def test_bulk_resolver_guardian_links_only():
    school_id = await _mk_school()
    p1 = await _mk_parent_user(school_id)
    p2 = await _mk_parent_user(school_id)
    s1 = await _mk_student(school_id)
    s2 = await _mk_student(school_id)
    await _link_guardian(s1["id"], p1["id"], school_id)
    await _link_guardian(s2["id"], p2["id"], school_id)
    result = await resolve_students_parent_user_ids([s1["id"], s2["id"]], school_id)
    assert result[s1["id"]] == p1["id"]
    assert result[s2["id"]] == p2["id"]


@pytest.mark.asyncio
async def test_bulk_resolver_skips_orphans():
    school_id = await _mk_school()
    parent = await _mk_parent_user(school_id)
    linked = await _mk_student(school_id)
    orphan = await _mk_student(school_id)
    await _link_guardian(linked["id"], parent["id"], school_id)
    result = await resolve_students_parent_user_ids(
        [linked["id"], orphan["id"]], school_id
    )
    assert linked["id"] in result
    assert orphan["id"] not in result


# ===========================================================================
# B. POST /ai/insights/intervention — action_type=notify_parent
# ===========================================================================


@pytest_asyncio.fixture
async def _school_and_admin():
    school_id = await _mk_school()
    admin = await _mk_user(UserRole.SCHOOL_ADMIN.value, school_id)
    return school_id, admin


@pytest.mark.asyncio
async def test_intervention_notify_guardian_links_only(client, _school_and_admin):
    """notify_parent succeeds when parent is linked via guardian_links only."""
    school_id, admin = _school_and_admin
    parent = await _mk_parent_user(school_id)
    student = await _mk_student(school_id)  # no parent_id
    await _link_guardian(student["id"], parent["id"], school_id)

    body = {
        "student_id": student["id"],
        "action_type": "notify_parent",
        "data": {"message": "يرجى مراجعة المدرسة", "issue_type": "attendance"},
    }
    r = await client.post("/ai/insights/intervention", json=body, headers=_tok(admin))
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True

    notifs = await gd_find(
        _db.session, "notifications",
        {"user_id": parent["id"], "tenant_id": school_id},
    )
    assert any("يرجى مراجعة المدرسة" in (n.get("message") or "") for n in notifs), \
        "Expected parent notification via guardian_links; none found"


@pytest.mark.asyncio
async def test_intervention_notify_orphan_returns_arabic_404(client, _school_and_admin):
    """notify_parent on a student with no guardian link returns 404 + Arabic."""
    school_id, admin = _school_and_admin
    student = await _mk_student(school_id)  # no parent at all

    body = {
        "student_id": student["id"],
        "action_type": "notify_parent",
        "data": {"message": "رسالة", "issue_type": "attendance"},
    }
    r = await client.post("/ai/insights/intervention", json=body, headers=_tok(admin))
    assert r.status_code == 404
    assert PARENT_NOT_FOUND_AR in r.text


# ===========================================================================
# C. POST /grades/bulk — parent notification via guardian_links
# ===========================================================================


@pytest_asyncio.fixture
async def _assessment_fixtures():
    """Seed school, teacher, class, subject, and assessment for grade tests."""
    school_id = await _mk_school()
    teacher = await _mk_user(UserRole.TEACHER.value, school_id)

    cls_id = str(uuid.uuid4())
    subj_id = str(uuid.uuid4())
    await gd_insert(_db.session, "classes", {
        "id": cls_id, "school_id": school_id, "name": "4A",
    })
    await gd_insert(_db.session, "subjects", {
        "id": subj_id, "school_id": school_id, "name": "رياضيات",
    })
    assessment_id = str(uuid.uuid4())
    now = _now()
    await gd_insert(_db.session, "assessments", {
        "id": assessment_id,
        "school_id": school_id,
        "tenant_id": school_id,
        "class_id": cls_id,
        "subject_id": subj_id,
        "name": "اختبار",
        "type": "quiz",
        "max_score": 100,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })
    return {
        "school_id": school_id,
        "teacher": teacher,
        "cls_id": cls_id,
        "subj_id": subj_id,
        "assessment_id": assessment_id,
    }


@pytest.mark.asyncio
async def test_bulk_grades_notifies_guardian_links_parent(client, _assessment_fixtures):
    """Bulk grade entry sends parent notification when linked via guardian_links."""
    f = _assessment_fixtures
    parent = await _mk_parent_user(f["school_id"])
    student = await _mk_student(f["school_id"], class_id=f["cls_id"])  # no parent_id
    await _link_guardian(student["id"], parent["id"], f["school_id"])

    body = {
        "assessment_id": f["assessment_id"],
        "grades": [{"student_id": student["id"], "score": 85, "notes": ""}],
    }
    r = await client.post("/grades/bulk", json=body, headers=_tok(f["teacher"]))
    assert r.status_code == 200, r.text

    notifs = await gd_find(
        _db.session, "notifications",
        {"user_id": parent["id"], "tenant_id": f["school_id"]},
    )
    assert notifs, "Expected parent notification via guardian_links; got none"


@pytest.mark.asyncio
async def test_bulk_grades_no_notification_for_orphan(client, _assessment_fixtures):
    """No parent notification created when student has no parent link."""
    f = _assessment_fixtures
    student = await _mk_student(f["school_id"], class_id=f["cls_id"])

    body = {
        "assessment_id": f["assessment_id"],
        "grades": [{"student_id": student["id"], "score": 70, "notes": ""}],
    }
    r = await client.post("/grades/bulk", json=body, headers=_tok(f["teacher"]))
    assert r.status_code == 200, r.text

    notifs = await gd_find(
        _db.session, "notifications",
        {"user_id": student["id"], "tenant_id": f["school_id"],
         "action_url": "/parent/grades"},
    )
    assert not notifs, "Unexpected parent notification for orphan student"
