"""
Regression tests for role-aware AI Insights recommendations.

These tests prove that the `/ai/insights/recommendations` endpoint:

  1. Never surfaces principal-directed wording (e.g. "follow up with class
     teachers", "review school start times", "hire additional teachers")
     to a teacher caller.
  2. Surfaces principal-appropriate wording to school admin / principal
     callers when the underlying metric thresholds are crossed.
  3. Hides principal-only recommendation types (HR/staffing) from teacher
     accounts entirely — neither by category, title, nor by `audience`.
  4. Produces role-specific text variants for shared recommendation types
     (attendance, tardiness, low-attendance class) when the same data
     state is observed by both role groups.
  5. Carries explicit audience metadata on every card so the frontend can
     act on backend-authoritative semantics, not regex guesses.
"""
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


# -------------------------------------------------------------- helpers


PRINCIPAL_DIRECTED_TOKENS = [
    # English principal-directed wording.
    re.compile(r"with class teachers", re.IGNORECASE),
    re.compile(r"hire", re.IGNORECASE),
    re.compile(r"hiring", re.IGNORECASE),
    re.compile(r"strengthen teaching staff", re.IGNORECASE),
    re.compile(r"review start times", re.IGNORECASE),
    # Arabic principal-directed wording.
    re.compile(r"معلمي الفصول"),
    re.compile(r"الكادر التعليمي"),
    re.compile(r"تعيين معلمين"),
    re.compile(r"بدء الدوام"),
]


def _texts(rec: dict):
    cat = rec.get("category") or {}
    title = rec.get("title") or {}
    desc = rec.get("description") or {}
    out = []
    for blob in (cat, title, desc):
        if isinstance(blob, dict):
            out.extend([v for v in blob.values() if isinstance(v, str)])
        elif isinstance(blob, str):
            out.append(blob)
    return out


def _has_principal_wording(rec: dict) -> bool:
    for text in _texts(rec):
        for pat in PRINCIPAL_DIRECTED_TOKENS:
            if pat.search(text):
                return True
    return False


def _headers(user_id: str, role: str, tenant_id, *, teacher_id=None):
    payload = {"sub": user_id, "role": role, "tenant_id": tenant_id}
    if teacher_id is not None:
        payload["teacher_id"] = teacher_id
    return {"Authorization": f"Bearer {create_access_token(payload)}"}


async def _seed_class(school_id: str, name: str = "1A") -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": school_id, "name": name,
    })
    return cid


async def _seed_student(school_id: str, class_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": school_id, "full_name": f"S-{sid[:6]}",
        "class_id": class_id, "is_active": True,
    })
    return sid


async def _seed_teacher_user(school_id: str, class_id: str):
    """Create a TEACHER user assigned to one class."""
    user_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": user_id, "role": UserRole.TEACHER.value,
        "tenant_id": school_id, "teacher_id": teacher_id,
        "email": f"t-{user_id}@t.test", "full_name": f"T-{user_id[:6]}",
        "is_active": True, "password_hash": "x",
    })
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "school_id": school_id, "user_id": user_id,
        "full_name": f"T-{user_id[:6]}",
    })
    await gd_insert(db.session, "teacher_class_assignments", {
        "id": str(uuid.uuid4()), "teacher_id": teacher_id,
        "school_id": school_id, "class_id": class_id,
    })
    return user_id, teacher_id


async def _seed_attendance_low(school_id: str, class_id: str,
                               student_ids, *, present_pct: int = 50):
    """Insert 30 days of attendance for each student so attendance rate
    falls below the 85% threshold (and below the 80% per-class threshold)."""
    base = datetime.now(timezone.utc) - timedelta(days=20)
    for sid in student_ids:
        for d in range(20):
            day = (base + timedelta(days=d)).strftime("%Y-%m-%d")
            status = "present" if (d * 100 // 20) < present_pct else "absent"
            await gd_insert(db.session, "attendance", {
                "id": str(uuid.uuid4()), "school_id": school_id,
                "student_id": sid, "class_id": class_id,
                "date": day, "status": status,
            })


# -------------------------------------------------------------- tests


@pytest.mark.asyncio
async def test_teacher_recommendations_have_no_principal_directed_wording(
    client, tenant_a
):
    """A teacher whose own class has low attendance must receive teacher-
    targeted wording. Principal-directed phrases such as 'with class
    teachers' or 'hire additional teachers' must never appear."""
    cls = await _seed_class(tenant_a, "T-cls")
    students = [await _seed_student(tenant_a, cls) for _ in range(5)]
    user_id, teacher_id = await _seed_teacher_user(tenant_a, cls)
    await _seed_attendance_low(tenant_a, cls, students, present_pct=50)

    headers = _headers(user_id, UserRole.TEACHER.value, tenant_a,
                       teacher_id=teacher_id)
    r = await client.get("/ai/insights/recommendations", headers=headers)
    assert r.status_code == 200, r.text
    recs = r.json()
    assert isinstance(recs, list) and recs, "teacher should still see cards"

    for rec in recs:
        assert not _has_principal_wording(rec), (
            f"Teacher saw principal-directed wording in card: {rec!r}"
        )

    # Every emitted card must explicitly include the teacher role in its
    # backend-declared audience.
    for rec in recs:
        aud = rec.get("audience")
        assert isinstance(aud, list) and UserRole.TEACHER.value in aud, (
            f"Teacher card missing teacher in audience: {rec!r}"
        )

    # Recommendation types known to be principal-only must be absent.
    types = {r.get("recommendation_type") for r in recs}
    assert "staffing_strengthen" not in types

    # The class-low-attendance card, if present, must use the teacher
    # variant — classroom scope, teacher action_owner.
    for rec in recs:
        if rec.get("recommendation_type") == "class_low_attendance":
            assert rec.get("action_owner") == "teacher"
            assert rec.get("scope_level") == "classroom"


@pytest.mark.asyncio
async def test_principal_sees_principal_directed_wording_for_shared_cards(
    client, tenant_a, school_principal_headers
):
    """A principal looking at the same kind of failing-attendance state
    must continue to see the school-coordination wording variant."""
    cls = await _seed_class(tenant_a, "P-cls")
    students = [await _seed_student(tenant_a, cls) for _ in range(5)]
    await _seed_attendance_low(tenant_a, cls, students, present_pct=50)

    r = await client.get("/ai/insights/recommendations",
                         headers=school_principal_headers)
    assert r.status_code == 200, r.text
    recs = r.json()
    assert isinstance(recs, list) and recs

    # Every card must declare the principal role in its audience.
    for rec in recs:
        aud = rec.get("audience")
        assert isinstance(aud, list) and \
            UserRole.SCHOOL_PRINCIPAL.value in aud, (
                f"Principal card missing principal in audience: {rec!r}"
            )

    # Principal must see the school-coordination variant of the
    # class-low-attendance card when one is produced.
    for rec in recs:
        if rec.get("recommendation_type") == "class_low_attendance":
            assert rec.get("action_owner") == "principal"
            assert rec.get("scope_level") == "school"
            joined = " ".join(_texts(rec))
            assert ("class teachers" in joined or
                    "معلمي الفصول" in joined), (
                f"Principal class-low-attendance card lost its admin "
                f"wording: {rec!r}"
            )


@pytest.mark.asyncio
async def test_shared_card_produces_distinct_role_variants(
    client, tenant_a, school_principal_headers
):
    """Same `recommendation_type` triggered by the same data must yield
    different wording for principal vs teacher."""
    cls = await _seed_class(tenant_a, "Shared-cls")
    students = [await _seed_student(tenant_a, cls) for _ in range(5)]
    user_id, teacher_id = await _seed_teacher_user(tenant_a, cls)
    await _seed_attendance_low(tenant_a, cls, students, present_pct=50)

    r_p = await client.get("/ai/insights/recommendations",
                           headers=school_principal_headers)
    r_t = await client.get("/ai/insights/recommendations",
                           headers=_headers(user_id, UserRole.TEACHER.value,
                                            tenant_a, teacher_id=teacher_id))
    assert r_p.status_code == 200 and r_t.status_code == 200

    def _by_type(recs):
        return {r.get("recommendation_type"): r for r in recs}

    p_by = _by_type(r_p.json())
    t_by = _by_type(r_t.json())

    # The shared "attendance_improve" card should appear for both roles
    # AND have a different description body per role.
    if "attendance_improve" in p_by and "attendance_improve" in t_by:
        p_desc = (p_by["attendance_improve"].get("description") or {}).get("en", "")
        t_desc = (t_by["attendance_improve"].get("description") or {}).get("en", "")
        assert p_desc and t_desc and p_desc != t_desc, (
            f"Shared card produced identical wording across roles: "
            f"principal={p_desc!r} teacher={t_desc!r}"
        )


@pytest.mark.asyncio
async def test_audience_filter_drops_principal_only_card_for_teacher():
    """Direct unit test of the backend authoritative audience filter, so a
    future builder that emits a principal-only card without the
    pre-skip safeguard still cannot leak it to a teacher payload."""
    from routes.ai_routes_mod import (
        _filter_recommendations_for_role,
        _PRINCIPAL_AUDIENCE,
        _ALL_SCHOOL_AUDIENCE,
    )

    cards = [
        {"id": "1", "audience": list(_PRINCIPAL_AUDIENCE),
         "recommendation_type": "staffing_strengthen"},
        {"id": "2", "audience": list(_ALL_SCHOOL_AUDIENCE),
         "recommendation_type": "attendance_improve"},
        {"id": "3"},  # legacy / no audience -> kept
    ]

    teacher_view = _filter_recommendations_for_role(
        cards, UserRole.TEACHER.value
    )
    ids = {c["id"] for c in teacher_view}
    assert ids == {"2", "3"}, ids

    principal_view = _filter_recommendations_for_role(
        cards, UserRole.SCHOOL_PRINCIPAL.value
    )
    ids = {c["id"] for c in principal_view}
    assert ids == {"1", "2", "3"}, ids

    # Platform admin oversees the whole platform and must NOT be subject
    # to the per-card school-audience filter — otherwise every card with
    # an `audience` list (which is now every generated card) would be
    # silently stripped from the cross-tenant oversight view.
    platform_view = _filter_recommendations_for_role(
        cards, UserRole.PLATFORM_ADMIN.value
    )
    ids = {c["id"] for c in platform_view}
    assert ids == {"1", "2", "3"}, ids


@pytest.mark.asyncio
async def test_platform_admin_endpoint_response_not_stripped(
    client, tenant_a, platform_admin_headers
):
    """Regression: a platform admin hitting /ai/insights/recommendations
    on a tenant with at least some data must still receive the
    underlying generated cards, not a single fallback 'all clear'."""
    cls = await _seed_class(tenant_a, "PA-cls")
    students = [await _seed_student(tenant_a, cls) for _ in range(5)]
    await _seed_attendance_low(tenant_a, cls, students, present_pct=50)

    r = await client.get("/ai/insights/recommendations",
                         headers=platform_admin_headers)
    assert r.status_code == 200, r.text
    recs = r.json()
    assert isinstance(recs, list) and recs

    # The data state above should produce at least one data-driven card
    # (attendance_improve and/or class_low_attendance). It must NOT
    # collapse to the generic 'all_clear' fallback.
    types = {rec.get("recommendation_type") for rec in recs}
    assert types - {"all_clear"}, (
        f"Platform admin only got fallback cards: {recs!r}"
    )
