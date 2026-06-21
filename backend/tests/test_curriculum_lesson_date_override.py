"""
Integration tests for the Add-Lesson date-range validation and override flow.

Covers:
  (1) GET new-metadata — returns curriculum date range for a class that has an
      active term; falls back gracefully (no error) when no term exists.
  (2) POST add_lesson — in-range dates are accepted with no special fields.
  (3) POST add_lesson — out-of-range dates with no override flag → 409
      `curriculum_date_conflict`.
  (4) POST add_lesson — out-of-range dates with override_curriculum=True but
      blank override_reason → 422.
  (5) POST add_lesson — out-of-range dates with valid override → 200, persists
      `override_*` fields, and writes one `curriculum_lesson_audit` row.
  (6) Cross-workspace IT §8 inv. 3 — metadata endpoint returns 404 for a
      foreign class, not 403/200.
"""

import uuid
from datetime import date, timezone, datetime

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find_one, gd_count
from auth_scope import independent_workspace_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_it_user() -> dict:
    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": now,
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-Workspace-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    return user


async def _mk_class(school_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "tenant_id": school_id,
        "name": f"C-{cid[:6]}",
        "capacity": 20,
        "current_students": 0,
        "is_active": True,
    })
    return cid


async def _mk_term(school_id: str, start_date: str, end_date: str) -> str:
    """Seed an active academic year + term for `school_id`."""
    year_id = str(uuid.uuid4())
    await gd_insert(db.session, "academic_years", {
        "id": year_id,
        "school_id": school_id,
        "name": "2025-2026",
        "start_date": start_date,
        "end_date": end_date,
        "is_current": True,
    })
    term_id = str(uuid.uuid4())
    await gd_insert(db.session, "terms", {
        "id": term_id,
        "school_id": school_id,
        "academic_year_id": year_id,
        "name": "الفصل الأول",
        "start_date": start_date,
        "end_date": end_date,
        "is_current": True,
    })
    return term_id


# ---------------------------------------------------------------------------
# (1) Metadata endpoint — with and without a term
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lesson_new_metadata_with_active_term(client):
    user = await _mk_it_user()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    cid = await _mk_class(wsid)
    await _mk_term(wsid, "2025-09-01", "2026-06-30")

    resp = await client.get(f"/class/{cid}/curriculum-plan/lesson/new-metadata", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["curriculum_start_date"] == "2025-09-01"
    assert body["curriculum_end_date"] == "2026-06-30"
    assert body["allow_override"] is True
    assert body["default_start_date"] is not None
    assert body["default_end_date"] is not None


@pytest.mark.asyncio
async def test_lesson_new_metadata_no_term_returns_nulls(client):
    user = await _mk_it_user()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    cid = await _mk_class(wsid)

    resp = await client.get(f"/class/{cid}/curriculum-plan/lesson/new-metadata", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["curriculum_start_date"] is None
    assert body["curriculum_end_date"] is None


# ---------------------------------------------------------------------------
# (2) In-range dates — accepted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_lesson_in_range_dates_accepted(client):
    user = await _mk_it_user()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    cid = await _mk_class(wsid)
    await _mk_term(wsid, "2025-09-01", "2026-06-30")

    resp = await client.post(
        f"/class/{cid}/curriculum-plan/lesson",
        json={
            "title": "درس داخل النطاق",
            "week": 1,
            "order": 1,
            "start_date": "2025-10-01",
            "end_date": "2025-10-07",
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["start_date"] == "2025-10-01"
    assert body["end_date"] == "2025-10-07"
    assert body.get("override_curriculum") is None


# ---------------------------------------------------------------------------
# (3) Out-of-range without override → 409 curriculum_date_conflict
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_lesson_out_of_range_no_override_returns_409(client):
    user = await _mk_it_user()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    cid = await _mk_class(wsid)
    await _mk_term(wsid, "2025-09-01", "2026-06-30")

    resp = await client.post(
        f"/class/{cid}/curriculum-plan/lesson",
        json={
            "title": "درس خارج النطاق",
            "week": 1,
            "order": 1,
            "start_date": "2024-01-01",
            "end_date": "2024-01-07",
        },
        headers=h,
    )
    assert resp.status_code == 409, resp.text
    detail = resp.json().get("detail", {})
    assert detail.get("code") == "curriculum_date_conflict"
    assert "curriculum_start" in detail.get("details", {})


# ---------------------------------------------------------------------------
# (4) Out-of-range + override=True but blank reason → 422
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_lesson_override_without_reason_returns_422(client):
    user = await _mk_it_user()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    cid = await _mk_class(wsid)
    await _mk_term(wsid, "2025-09-01", "2026-06-30")

    resp = await client.post(
        f"/class/{cid}/curriculum-plan/lesson",
        json={
            "title": "درس خارج النطاق",
            "week": 1,
            "order": 1,
            "start_date": "2024-01-01",
            "end_date": "2024-01-07",
            "override_curriculum": True,
            "override_reason": "   ",
        },
        headers=h,
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# (5) Out-of-range + valid override → 200 + audit row persisted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_lesson_override_with_reason_persists_and_audits(client):
    user = await _mk_it_user()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)
    cid = await _mk_class(wsid)
    await _mk_term(wsid, "2025-09-01", "2026-06-30")

    resp = await client.post(
        f"/class/{cid}/curriculum-plan/lesson",
        json={
            "title": "درس خارج النطاق بمبرر",
            "week": 2,
            "order": 1,
            "start_date": "2024-01-01",
            "end_date": "2024-01-07",
            "override_curriculum": True,
            "override_reason": "تأجيل بسبب الاختبارات الفصلية",
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    lesson_id = body["id"]
    assert body["override_curriculum"] is True
    assert "override_reason" in body

    # Lesson persisted
    persisted = await gd_find_one(db.session, "curriculum_lessons", {"id": lesson_id})
    assert persisted is not None
    assert persisted["override_curriculum"] is True

    # Audit row written
    audit_count = await gd_count(db.session, "curriculum_lesson_audit", {"lesson_id": lesson_id})
    assert audit_count == 1

    audit = await gd_find_one(db.session, "curriculum_lesson_audit", {"lesson_id": lesson_id})
    assert audit["user_id"] == user["id"]
    assert audit["override_reason"] == "تأجيل بسبب الاختبارات الفصلية"
    assert audit["curriculum_start"] == "2025-09-01"


# ---------------------------------------------------------------------------
# (6) Cross-workspace metadata → 404 (§8 inv. 3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lesson_metadata_cross_workspace_returns_404(client):
    user_a = await _mk_it_user()
    user_b = await _mk_it_user()
    wsid_a = independent_workspace_id(user_a)
    wsid_b = independent_workspace_id(user_b)
    cid = await _mk_class(wsid_a)

    h_b = _headers(user_b["id"], user_b["role"], wsid_b)
    resp = await client.get(f"/class/{cid}/curriculum-plan/lesson/new-metadata", headers=h_b)
    assert resp.status_code == 404, resp.text
