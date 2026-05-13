"""IT workspace-aware bulk student import (Task #207, spec §6.1).

Covers:
  (a) parse 422s on missing required header
  (b) parse returns per-row diagnostics (valid + invalid mixed)
  (c) commit without recent MFA → 403 step-up envelope
  (d) commit happy-path inserts students + bumps imports_today
  (e) commit cross-workspace school_id smuggle attempt → 403
  (f) commit rejects when current_students + rows > MAX_STUDENTS (409)
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

import pytest

from auth_scope import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_count, gd_find_one, gd_insert, gd_update_one


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _headers(uid: str, role: str, tenant_id=None, *, mfa_recent_at=None) -> dict:
    token = create_access_token(
        {"sub": uid, "role": role, "tenant_id": tenant_id},
        mfa_recent_at=mfa_recent_at,
        mfa_kind="webauthn" if mfa_recent_at else None,
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_passkey(user_id: str) -> None:
    await gd_insert(db.session, "mfa_factors", {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "kind": "webauthn",
        "is_active": True,
        "is_primary": True,
        "webauthn_credential_id": uuid.uuid4().bytes,
        "webauthn_public_key": b"\x00",
        "webauthn_sign_count": 0,
    })


async def _mk_it_workspace() -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-WS-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher_workspace",
    })
    await _seed_passkey(uid)
    user["tenant_id"] = wsid
    return user


def _csv_bytes(*rows: tuple[str, ...]) -> bytes:
    header = "الاسم الكامل,رقم الهوية,الجنس,تاريخ الميلاد,الصف\n"
    body = "\n".join(",".join(r) for r in rows)
    return ("\ufeff" + header + body).encode("utf-8")


# ----------------------------------------------------------------------
# (a) header validation
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_parse_missing_header_422(client):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"], mfa_recent_at=_now_ts())
    bad = "العمر,الفصل\n10,1-أ".encode("utf-8")
    resp = await client.post(
        "/independent-teacher/students/bulk/parse",
        headers=h,
        files={"file": ("bad.csv", io.BytesIO(bad), "text/csv")},
    )
    assert resp.status_code == 422, resp.text


# ----------------------------------------------------------------------
# (b) parse returns per-row diagnostics
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_parse_returns_row_diagnostics(client):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"], mfa_recent_at=_now_ts())
    csv = _csv_bytes(
        ("أحمد محمد العتيبي", "1098765432", "ذكر", "2014-03-12", "الثالث الابتدائي"),
        ("", "", "", "", ""),  # blank-line skipped by parser
        ("ا", "", "", "", ""),  # too-short name → invalid
        ("سارة عبدالله القحطاني", "", "أنثى", "", "الرابع الابتدائي"),
    )
    resp = await client.post(
        "/independent-teacher/students/bulk/parse",
        headers=h,
        files={"file": ("ok.csv", io.BytesIO(csv), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_rows"] == 3
    assert body["valid_count"] == 2
    assert body["invalid_count"] == 1
    assert body["quota"]["max_students"] == 200
    # No DB writes from parse.
    assert await gd_count(db.session, "students", {"school_id": user["tenant_id"]}) == 0


# ----------------------------------------------------------------------
# (c) commit without recent MFA → 403 step-up envelope
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_commit_requires_recent_mfa_403(client):
    user = await _mk_it_workspace()
    # No mfa_recent_at on the token.
    h = _headers(user["id"], user["role"], user["tenant_id"])
    payload = {
        "rows": [{
            "row_number": 1,
            "full_name": "أحمد محمد العتيبي",
            "is_valid": True,
            "errors": [],
        }],
    }
    resp = await client.post(
        "/independent-teacher/students/bulk/commit",
        headers=h,
        json=payload,
    )
    assert resp.status_code == 403, resp.text
    body = resp.json()
    detail = body.get("detail") or (body.get("error") or {}).get("detail") or {}
    code = detail.get("code") if isinstance(detail, dict) else None
    assert code in {"MFA_STEPUP_REQUIRED", "MFA_PASSKEY_REQUIRED", "MFA_RESTORE_REQUIRED"}, body


# ----------------------------------------------------------------------
# (d) commit happy path
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_commit_inserts_and_bumps_quota_counter(client):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"], mfa_recent_at=_now_ts())
    payload = {
        "rows": [
            {
                "row_number": 1,
                "full_name": "أحمد محمد العتيبي",
                "national_id": "1098765432",
                "gender": "male",
                "date_of_birth": "2014-03-12",
                "grade_level": "الثالث الابتدائي",
                "is_valid": True,
                "errors": [],
            },
            {
                "row_number": 2,
                "full_name": "سارة عبدالله القحطاني",
                "gender": "female",
                "is_valid": True,
                "errors": [],
            },
        ],
    }
    resp = await client.post(
        "/independent-teacher/students/bulk/commit",
        headers=h,
        json=payload,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["inserted"] == 2
    assert body["quota"]["imports_today"] == 1
    assert body["quota"]["current_students"] == 2

    count = await gd_count(
        db.session, "students",
        {"school_id": user["tenant_id"], "is_active": {"$ne": False}},
    )
    assert count == 2

    quota = await gd_find_one(
        db.session, "workspace_quota",
        {"workspace_school_id": user["tenant_id"]},
    )
    assert quota is not None
    assert int(quota.get("imports_today") or 0) == 1


# ----------------------------------------------------------------------
# (f) student-cap enforcement
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_commit_refuses_when_total_exceeds_max_students(client):
    user = await _mk_it_workspace()
    # Pre-seed 199 active students so a 2-row import would push past 200.
    for _ in range(199):
        sid = str(uuid.uuid4())
        await gd_insert(db.session, "students", {
            "id": sid,
            "school_id": user["tenant_id"],
            "tenant_id": user["tenant_id"],
            "full_name": f"طالب-{sid[:6]}",
            "is_active": True,
        })
    h = _headers(user["id"], user["role"], user["tenant_id"], mfa_recent_at=_now_ts())
    payload = {
        "rows": [
            {"row_number": 1, "full_name": "طالب الإسناد الأول", "is_valid": True, "errors": []},
            {"row_number": 2, "full_name": "طالب الإسناد الثاني", "is_valid": True, "errors": []},
        ],
    }
    resp = await client.post(
        "/independent-teacher/students/bulk/commit",
        headers=h,
        json=payload,
    )
    assert resp.status_code == 409, resp.text


# ----------------------------------------------------------------------
# (g) daily import-count cap → 429
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_commit_refuses_when_daily_import_cap_reached(client):
    from datetime import date as _date
    user = await _mk_it_workspace()
    # Saturate today's import counter at the workspace cap (5/day default).
    await gd_insert(db.session, "workspace_quota", {
        "workspace_school_id": user["tenant_id"],
        "max_students": 200, "max_classes": 5,
        "max_imports_per_day": 5, "max_rows_per_import": 200,
        "imports_today": 5,
        "imports_today_date": _date.today().isoformat(),
    })
    h = _headers(user["id"], user["role"], user["tenant_id"], mfa_recent_at=_now_ts())
    payload = {"rows": [{
        "row_number": 1,
        "full_name": "أحمد محمد العتيبي",
        "is_valid": True, "errors": [],
    }]}
    resp = await client.post(
        "/independent-teacher/students/bulk/commit",
        headers=h, json=payload,
    )
    assert resp.status_code == 429, resp.text


# ----------------------------------------------------------------------
# (h) cross-tenant header in the CSV itself → 422 (parse refuses,
#     never silently dropped). Spec §6.1 IT writes pin to itw_{user}.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_parse_refuses_csv_with_school_id_column(client):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"], mfa_recent_at=_now_ts())
    bad_header = (
        "\ufeffالاسم الكامل,school_id\n"
        "أحمد محمد العتيبي,evil-tenant-id\n"
    ).encode("utf-8")
    resp = await client.post(
        "/independent-teacher/students/bulk/parse",
        headers=h,
        files={"file": ("evil.csv", io.BytesIO(bad_header), "text/csv")},
    )
    assert resp.status_code == 422, resp.text


# ----------------------------------------------------------------------
# (i) UTC midnight rollover — yesterday's saturated counter must reset
#     to 1 on a fresh day's import.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_commit_resets_daily_counter_on_new_utc_day(client):
    from datetime import date as _date, timedelta
    user = await _mk_it_workspace()
    yesterday = (_date.today() - timedelta(days=1)).isoformat()
    await gd_insert(db.session, "workspace_quota", {
        "workspace_school_id": user["tenant_id"],
        "max_students": 200, "max_classes": 5,
        "max_imports_per_day": 5, "max_rows_per_import": 200,
        "imports_today": 5,
        "imports_today_date": yesterday,
    })
    h = _headers(user["id"], user["role"], user["tenant_id"], mfa_recent_at=_now_ts())
    payload = {"rows": [{
        "row_number": 1,
        "full_name": "أحمد محمد العتيبي",
        "is_valid": True, "errors": [],
    }]}
    resp = await client.post(
        "/independent-teacher/students/bulk/commit",
        headers=h, json=payload,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["quota"]["imports_today"] == 1
    quota = await gd_find_one(
        db.session, "workspace_quota",
        {"workspace_school_id": user["tenant_id"]},
    )
    assert int(quota.get("imports_today") or 0) == 1


# ----------------------------------------------------------------------
# (j) commit ignores extra/unexpected keys (school_id smuggle attempt) —
#     ParsedRow uses the default Pydantic config which silently drops
#     unknown fields, and the workspace pin is enforced server-side.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_commit_ignores_extra_school_id_key_in_payload(client):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"], mfa_recent_at=_now_ts())
    payload = {"rows": [{
        "row_number": 1,
        "full_name": "أحمد محمد العتيبي",
        "school_id": "evil-tenant-id",
        "tenant_id": "evil-tenant-id",
        "is_valid": True,
        "errors": [],
    }]}
    resp = await client.post(
        "/independent-teacher/students/bulk/commit",
        headers=h, json=payload,
    )
    assert resp.status_code == 200, resp.text
    # Inserted row must be pinned to the IT workspace, never to the
    # smuggled tenant id.
    rows = await __import__("engines.sql_utils", fromlist=["gd_find"]).gd_find(
        db.session, "students",
        {"school_id": user["tenant_id"], "is_active": {"$ne": False}},
    )
    assert len(rows) == 1
    evil = await gd_find_one(
        db.session, "students", {"school_id": "evil-tenant-id"},
    )
    assert evil is None
