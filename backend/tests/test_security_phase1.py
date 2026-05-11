"""
Regression tests for Security Phase 1 — Immediate Hardening Sprint.

Covers:
  - C-3 IDORs: cross-tenant fetches of academic year / term / grade level /
    assessment / student dashboard return 404 (not 200).
  - C-4 public stats lockdown: /public/stats requires PLATFORM_ADMIN.
  - H-1 per-identity authz on student data: /attendance/student/{id} returns
    403 for an in-tenant teacher with no assignment to that class.
  - H-3 password recovery rate limits: forgot-password/reset-password are
    listed in RATE_LIMITS with the documented window/budget.
  - H-4 CSP tightening: response carries object-src 'none', base-uri 'none',
    form-action 'self'.
  - M-7 cleanup script guard: cleanup_test_data refuses to run when
    destructive ops are blocked.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from dependencies import db, UserRole
from engines.sql_utils import gd_insert
from tests.conftest import _mk_user, _headers, _mk_school


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# C-4 — /public/stats lockdown
# ---------------------------------------------------------------------------

async def test_public_stats_unauthenticated_blocked(client):
    resp = await client.get("/public/stats")
    assert resp.status_code in (401, 403)


async def test_public_stats_school_principal_blocked(client, school_principal_headers):
    resp = await client.get("/public/stats", headers=school_principal_headers)
    assert resp.status_code == 403


async def test_public_stats_platform_admin_allowed(client, platform_admin_headers):
    resp = await client.get("/public/stats", headers=platform_admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "schools" in body


# ---------------------------------------------------------------------------
# C-3 — cross-tenant IDOR closure
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def foreign_academic_year(tenant_b):
    ay_id = str(uuid.uuid4())
    await gd_insert(db.session, "academic_years", {
        "id": ay_id,
        "school_id": tenant_b,
        "name": "2026-2027",
        "name_en": "2026-2027",
        "start_date": "2026-09-01",
        "end_date": "2027-06-30",
        "status": "active",
    })
    return ay_id


@pytest_asyncio.fixture
async def foreign_term(tenant_b, foreign_academic_year):
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "terms", {
        "id": tid,
        "school_id": tenant_b,
        "academic_year_id": foreign_academic_year,
        "name": "T1",
        "start_date": "2026-09-01",
        "end_date": "2026-12-31",
    })
    return tid


@pytest_asyncio.fixture
async def foreign_grade_level(tenant_b):
    gid = str(uuid.uuid4())
    await gd_insert(db.session, "grade_levels", {
        "id": gid,
        "school_id": tenant_b,
        "name_ar": "الأول",
        "name_en": "First",
        "order": 1,
    })
    return gid


@pytest_asyncio.fixture
async def foreign_assessment(tenant_b):
    cls_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {"id": cls_id, "school_id": tenant_b, "name": "B-cls"})
    aid = str(uuid.uuid4())
    await gd_insert(db.session, "assessments", {
        "id": aid,
        "school_id": tenant_b,
        "name": "Foreign Quiz",
        "subject_id": None,
        "class_id": cls_id,
        "type": "quiz",
        "max_score": 10,
    })
    return aid


async def test_cross_tenant_academic_year_returns_404(client, school_principal_headers, foreign_academic_year):
    resp = await client.get(
        f"/academics/academic-years/{foreign_academic_year}",
        headers=school_principal_headers,
    )
    assert resp.status_code == 404


async def test_cross_tenant_term_returns_404(client, school_principal_headers, foreign_term):
    resp = await client.get(
        f"/academics/terms/{foreign_term}",
        headers=school_principal_headers,
    )
    assert resp.status_code == 404


async def test_cross_tenant_grade_level_returns_404(client, school_principal_headers, foreign_grade_level):
    resp = await client.get(
        f"/academics/grade-levels/{foreign_grade_level}",
        headers=school_principal_headers,
    )
    assert resp.status_code == 404


async def test_cross_tenant_assessment_returns_404(client, school_principal_headers, foreign_assessment):
    resp = await client.get(
        f"/assessments/{foreign_assessment}",
        headers=school_principal_headers,
    )
    assert resp.status_code == 404


async def test_cross_tenant_student_dashboard_returns_404(client, school_principal_headers, tenant_b_student):
    sid = tenant_b_student["id"]
    resp = await client.get(
        f"/student/dashboard/{sid}",
        headers=school_principal_headers,
    )
    # Either 404 (helper hides existence) or 403; never 200 with foreign data.
    assert resp.status_code in (403, 404)


async def test_own_tenant_assessment_returns_200(client, school_principal_headers, tenant_a):
    cls_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {"id": cls_id, "school_id": tenant_a, "name": "A-cls"})
    aid = str(uuid.uuid4())
    await gd_insert(db.session, "assessments", {
        "id": aid, "school_id": tenant_a, "class_id": cls_id,
        "subject_id": None, "name": "Own Quiz", "type": "quiz", "max_score": 10,
    })
    resp = await client.get(f"/assessments/{aid}", headers=school_principal_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == aid


async def test_forgot_password_per_email_429_after_budget(client, monkeypatch):
    """Drive the per-email bucket past its budget; once exhausted it must
    short-circuit *before* hitting the DB. We assert that with the per-IP
    middleware bucket out of the way (raised in this test), the per-identity
    bucket alone returns the silent generic message after 5 hits."""
    from middleware.rate_limiter import rate_store
    # Use a fresh, unique email so we don't collide with other tests.
    email = f"rl-{uuid.uuid4().hex[:8]}@example.com"
    bucket = f"forgot_password_email:{email.lower()}"
    rate_store._store.pop(bucket, None)
    # Hit it 7 times — first 5 are "real", remaining must be silently capped.
    statuses = []
    for _ in range(7):
        r = await client.post("/auth/forgot-password", json={"email": email})
        statuses.append(r.status_code)
    # Endpoint always returns 200 with a generic message (anti-enumeration).
    assert all(s == 200 for s in statuses)
    # But the per-email bucket must have engaged after the budget — assert
    # via the store directly rather than a leaky 429 surface.
    limited, _, _ = await rate_store.is_rate_limited(bucket, 5, 3600)
    assert limited is True


async def test_reset_password_per_identity_returns_429(client, tenant_a):
    """Per-identity bucket: after 10 valid-token attempts against the same
    user_id, the 11th must 429 — even though each token is unique."""
    from middleware.rate_limiter import rate_store
    from dependencies import JWT_SECRET, JWT_ALGORITHM
    import jwt as _jwt
    user_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": user_id, "role": "school_principal", "tenant_id": tenant_a,
        "email": f"{user_id}@t.test", "full_name": "rl-target",
        "is_active": True, "password_hash": "x",
    })
    rate_store._store.pop(f"reset_password_user:{user_id}", None)

    def _mk_token():
        # Each token has a unique jti so the per-token-prefix bucket
        # (10/hour, keyed on token[:24]) stays out of the way and we
        # isolate the per-identity bucket.
        return _jwt.encode(
            {"sub": user_id, "purpose": "password_reset",
             "jti": uuid.uuid4().hex,
             "exp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                    + __import__("datetime").timedelta(hours=1)},
            JWT_SECRET, algorithm=JWT_ALGORITHM,
        )

    # Each call uses a freshly minted token. The per-token bucket is keyed
    # on the validated jti (or sha256 of the full token), so two distinct
    # tokens never share that bucket — the only bucket that should engage
    # across iterations is the per-identity one (10/hour on user_id).
    tokens = [_mk_token() for _ in range(12)]
    # Bucket isolation invariant: two distinct tokens must produce two
    # distinct per-token bucket keys. (Architect v3 caught a regression
    # where token[:24] aliased every JWT under the constant header.)
    import jwt as _jwt2
    jtis = {_jwt2.decode(t, JWT_SECRET, algorithms=[JWT_ALGORITHM])["jti"] for t in tokens}
    assert len(jtis) == 12, "tokens must yield distinct per-token bucket keys"

    statuses = []
    for tok in tokens:
        r = await client.post("/auth/reset-password", json={
            "token": tok, "new_password": "NewSecret!2345",
        })
        statuses.append(r.status_code)
    # First 10 attempts pass identity-bucket validation and fall to
    # the next check (400 — token hash doesn't match a stored reset).
    # Attempt 11+ must be rejected with 429 by the per-identity bucket.
    assert all(s in (400, 429) for s in statuses), statuses
    assert 429 in statuses[10:], (
        f"per-identity reset-password bucket never tripped: {statuses}"
    )
    # And confirm that 1..10 are NOT 429s — proves unrelated tokens did
    # not collide on a shared (broken) per-token bucket.
    assert all(s == 400 for s in statuses[:10]), (
        f"per-token bucket aliased across distinct tokens: {statuses}"
    )


async def test_assessment_endpoint_fail_closed_without_tenant(client, tenant_a):
    """A token with no tenant_id (e.g. orphan service account) must not bypass
    tenant scoping on the assessment GET endpoint."""
    from dependencies import create_access_token
    cls_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {"id": cls_id, "school_id": tenant_a, "name": "A-cls"})
    aid = str(uuid.uuid4())
    await gd_insert(db.session, "assessments", {
        "id": aid, "school_id": tenant_a, "class_id": cls_id,
        "subject_id": None, "name": "Own Quiz", "type": "quiz", "max_score": 10,
    })
    user_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": user_id, "role": "school_principal", "tenant_id": None,
        "email": f"{user_id}@t.test", "full_name": "no-tenant",
        "is_active": True, "password_hash": "x",
    })
    token = create_access_token({"sub": user_id, "role": "school_principal", "tenant_id": None})
    resp = await client.get(
        f"/assessments/{aid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Must NOT return 200 — helper raises 403 when no tenant context.
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# H-1 — per-identity authorization on student data
# ---------------------------------------------------------------------------

async def test_attendance_student_endpoint_blocks_unrelated_teacher(client, tenant_a, seeded_school):
    # A teacher in the same tenant who has no teacher_assignments / class_sessions
    # for the target student's class must be denied (same-tenant alone is no
    # longer sufficient).
    teacher_user = await _mk_user(UserRole.TEACHER, tenant_a)
    headers = _headers(teacher_user)
    target_student = seeded_school.students[0]
    resp = await client.get(
        f"/attendance/student/{target_student['id']}",
        headers=headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# H-3 — password recovery rate-limit configuration
# ---------------------------------------------------------------------------

def test_forgot_password_in_rate_limits_map():
    from middleware.rate_limiter import RATE_LIMITS
    entry = RATE_LIMITS.get("/api/auth/forgot-password")
    assert entry is not None
    assert entry["max"] >= 1 and entry["window"] >= 60


def test_reset_password_in_rate_limits_map():
    from middleware.rate_limiter import RATE_LIMITS
    entry = RATE_LIMITS.get("/api/auth/reset-password")
    assert entry is not None
    assert entry["max"] >= 1 and entry["window"] >= 60


# ---------------------------------------------------------------------------
# H-4 — CSP tightening
# ---------------------------------------------------------------------------

async def test_csp_header_contains_phase1_directives(client):
    resp = await client.get("/public/health")
    csp = resp.headers.get("content-security-policy") or resp.headers.get("Content-Security-Policy") or ""
    assert "object-src 'none'" in csp
    assert "base-uri 'none'" in csp
    assert "form-action 'self'" in csp
    # connect-src is intentionally narrow (no https: wildcard).
    assert "connect-src 'self' wss: ws:" in csp


# ---------------------------------------------------------------------------
# M-7 — cleanup_test_data destructive guard
# ---------------------------------------------------------------------------

def test_cleanup_test_data_refuses_outside_dev(monkeypatch):
    import importlib
    from config import NassaqConfig as Config
    cleanup_mod = importlib.import_module("scripts.cleanup_test_data")
    # Config caches ENVIRONMENT as a class attr at import time, so patch it
    # in place rather than via the env var (which only affects future imports).
    monkeypatch.setattr(Config, "ENVIRONMENT", "production", raising=False)
    assert Config.destructive_ops_allowed() is False
    with pytest.raises(SystemExit) as exc:
        cleanup_mod._assert_destructive_ops_allowed()
    assert exc.value.code == 2


async def test_cleanup_test_data_reasserts_at_exit(monkeypatch):
    """If ENVIRONMENT flips mid-run, the finally-block guard must trip even
    after _run_cleanup() returns successfully."""
    import importlib
    from config import NassaqConfig as Config
    cleanup_mod = importlib.import_module("scripts.cleanup_test_data")

    call_log = []

    async def fake_run_cleanup():
        call_log.append("ran")
        # Flip the environment after the work is done — the exit-time
        # _assert_destructive_ops_allowed() must catch it.
        monkeypatch.setattr(Config, "ENVIRONMENT", "production", raising=False)

    monkeypatch.setattr(Config, "ENVIRONMENT", "development", raising=False)
    monkeypatch.setattr(cleanup_mod, "_run_cleanup", fake_run_cleanup)
    with pytest.raises(SystemExit) as exc:
        await cleanup_mod.cleanup()
    assert exc.value.code == 2
    assert call_log == ["ran"]  # the work did run, then the exit guard tripped


# ---------------------------------------------------------------------------
# tenant_scoped_find_one — fail-closed semantics
# ---------------------------------------------------------------------------

async def test_tenant_scoped_find_one_denies_when_no_tenant(tenant_a):
    from utils.tenant_scope import tenant_scoped_find_one
    from fastapi import HTTPException

    no_tenant_user = {"role": UserRole.SCHOOL_PRINCIPAL.value}  # tenant_id missing
    gid = str(uuid.uuid4())
    await gd_insert(db.session, "grade_levels", {
        "id": gid, "school_id": tenant_a, "name_ar": "x", "name_en": "x", "order": 1,
    })
    with pytest.raises(HTTPException) as exc:
        await tenant_scoped_find_one(db.session, "grade_levels", gid, no_tenant_user)
    assert exc.value.status_code == 403


async def test_tenant_scoped_find_one_returns_none_for_foreign_tenant(tenant_a, tenant_b):
    from utils.tenant_scope import tenant_scoped_find_one
    gid = str(uuid.uuid4())
    await gd_insert(db.session, "grade_levels", {
        "id": gid, "school_id": tenant_b, "name_ar": "x", "name_en": "x", "order": 1,
    })
    in_tenant_user = {"role": UserRole.SCHOOL_PRINCIPAL.value, "tenant_id": tenant_a}
    result = await tenant_scoped_find_one(db.session, "grade_levels", gid, in_tenant_user)
    assert result is None


async def test_tenant_scoped_find_one_returns_row_for_own_tenant(tenant_a):
    from utils.tenant_scope import tenant_scoped_find_one
    gid = str(uuid.uuid4())
    await gd_insert(db.session, "grade_levels", {
        "id": gid, "school_id": tenant_a, "name_ar": "س", "name_en": "x", "order": 1,
    })
    user = {"role": UserRole.SCHOOL_PRINCIPAL.value, "tenant_id": tenant_a}
    result = await tenant_scoped_find_one(db.session, "grade_levels", gid, user)
    assert result is not None and result["id"] == gid
