"""Tests for IT workspace settings (Task #189 §5.2)."""
import uuid

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find_one, gd_insert
from src.core.guards.tenant_guard import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
)


PATH = "/independent-teacher/workspace/settings"


def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_independent_teacher_with_workspace() -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-{uid[:6]}",
        "name_en": "IT-EN",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher",
        "tenant_type": "independent_teacher",
    })
    await gd_insert(db.session, "school_settings", {
        "id": str(uuid.uuid4()),
        "school_id": wsid,
        "working_days": ["sun", "mon", "tue", "wed", "thu"],
        "periods_per_day": 7,
        "period_duration": 45,
        "language": "ar",
    })
    year_id = str(uuid.uuid4())
    await gd_insert(db.session, "academic_years", {
        "id": year_id,
        "school_id": wsid,
        "name": "1446",
        "is_current": True,
        "status": "active",
    })
    await gd_insert(db.session, "academic_terms", {
        "id": str(uuid.uuid4()),
        "school_id": wsid,
        "academic_year_id": year_id,
        "name": "الفصل الأول",
        "term_number": 1,
        "is_current": True,
        "status": "active",
    })
    return {"user": user, "wsid": wsid}


@pytest.mark.asyncio
async def test_get_workspace_settings_returns_it_fields(client):
    ctx = await _mk_independent_teacher_with_workspace()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    resp = await client.get(PATH, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["workspace_id"] == ctx["wsid"]
    assert body["name_en"] == "IT-EN"
    assert body["periods_per_day"] == 7
    assert body["period_minutes"] == 45
    assert body["school_day_start"] == "07:00"
    assert body["academic_year_label"] == "1446"
    assert body["academic_term_label"] == "الفصل الأول"
    assert "sun" in body["working_days"]


@pytest.mark.asyncio
async def test_put_allow_listed_fields_persists(client):
    ctx = await _mk_independent_teacher_with_workspace()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    payload = {
        "name_ar": "مساحة سعد المُحدَّثة",
        "name_en": "Saad Updated",
        "logo_url": "https://example.com/logo.png",
        "working_days": ["sun", "mon", "wed"],
        "periods_per_day": 5,
        "period_minutes": 50,
        "school_day_start": "8:5",
        "timezone": "Asia/Dubai",
        "academic_year_label": "1447 - 1448 هـ",
        "academic_term_label": "الفصل الثاني",
    }
    resp = await client.put(PATH, headers=h, json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name_ar"] == "مساحة سعد المُحدَّثة"
    assert body["periods_per_day"] == 5
    assert body["period_minutes"] == 50
    assert body["school_day_start"] == "08:05"
    assert body["timezone"] == "Asia/Dubai"
    assert body["academic_year_label"] == "1447 - 1448 هـ"
    assert body["academic_term_label"] == "الفصل الثاني"
    assert sorted(body["working_days"]) == ["mon", "sun", "wed"]

    # Cross-table persistence checks.
    school = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert school["name"] == "مساحة سعد المُحدَّثة"
    assert school["name_en"] == "Saad Updated"
    assert school["logo_url"] == "https://example.com/logo.png"
    settings = await gd_find_one(
        db.session, "school_settings", {"school_id": ctx["wsid"]}
    )
    assert settings["periods_per_day"] == 5
    assert settings["period_duration"] == 50
    assert (settings.get("custom_settings") or {}).get("timezone") == "Asia/Dubai"
    assert (settings.get("custom_settings") or {}).get("school_day_start") == "08:05"
    year = await gd_find_one(
        db.session, "academic_years",
        {"school_id": ctx["wsid"], "is_current": True},
    )
    assert year["name"] == "1447 - 1448 هـ"
    term = await gd_find_one(
        db.session, "academic_terms",
        {"school_id": ctx["wsid"], "is_current": True},
    )
    assert term["name"] == "الفصل الثاني"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_key,bad_value", [
    ("school_type", "public"),
    ("tenant_type", "production"),
    ("principal_name", "غير مسموح"),
    ("ministry_id", "MIN-1"),
    ("license_number", "LIC-1"),
    ("stage", "secondary"),
    ("id", "evil"),
    ("code", "EVIL"),
    ("sections", []),
    ("classes", []),
    ("classrooms", []),
])
async def test_put_disallowed_key_is_rejected_with_arabic_403(
    client, bad_key, bad_value,
):
    ctx = await _mk_independent_teacher_with_workspace()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])

    payload = {"name_ar": "اسم جديد", bad_key: bad_value}
    resp = await client.put(PATH, headers=h, json=payload)
    assert resp.status_code == 403, (bad_key, resp.status_code, resp.text)
    body = resp.json()
    msg = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert "صلاحية" in msg, (bad_key, body)

    school = await gd_find_one(db.session, "schools", {"id": ctx["wsid"]})
    assert school["name"] != "اسم جديد"


@pytest.mark.asyncio
async def test_put_accepts_period_duration_alias(client):
    ctx = await _mk_independent_teacher_with_workspace()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    resp = await client.put(PATH, headers=h, json={"period_duration": 55})
    assert resp.status_code == 200, resp.text
    assert resp.json()["period_minutes"] == 55
    settings = await gd_find_one(
        db.session, "school_settings", {"school_id": ctx["wsid"]}
    )
    assert settings["period_duration"] == 55


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_value", ["25:00", "07:99", "noon", "7", "", 700])
async def test_put_invalid_day_start_rejected(client, bad_value):
    ctx = await _mk_independent_teacher_with_workspace()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    resp = await client.put(PATH, headers=h, json={"school_day_start": bad_value})
    assert resp.status_code == 400, (bad_value, resp.text)


@pytest.mark.asyncio
async def test_independent_teacher_cannot_modify_other_workspace(client):
    a = await _mk_independent_teacher_with_workspace()
    b = await _mk_independent_teacher_with_workspace()
    h_b = _headers(b["user"]["id"], b["user"]["role"], b["wsid"])

    original_a = await gd_find_one(db.session, "schools", {"id": a["wsid"]})
    resp = await client.put(
        PATH, headers=h_b,
        json={"name_ar": "اختراق-A"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # The write landed on B's workspace, not A's.
    assert body["workspace_id"] == b["wsid"]
    after_a = await gd_find_one(db.session, "schools", {"id": a["wsid"]})
    assert after_a["name"] == original_a["name"]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [
    UserRole.TEACHER.value,
    UserRole.SCHOOL_PRINCIPAL.value,
    UserRole.SCHOOL_ADMIN.value,
])
async def test_non_independent_teacher_roles_denied(client, role):
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid, "name": "S", "code": f"S{sid[:6]}",
        "status": "active", "country": "SA", "language": "ar",
    })
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": role, "tenant_id": sid,
        "email": f"u-{uid}@t.test", "full_name": "U",
        "is_active": True, "password_hash": "x",
    })
    h = _headers(uid, role, sid)
    resp = await client.get(PATH, headers=h)
    assert resp.status_code == 403, (role, resp.text)
    body = resp.json()
    msg = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert INDEPENDENT_TEACHER_DENIED_AR in msg

    resp_put = await client.put(PATH, headers=h, json={"name_ar": "x"})
    assert resp_put.status_code == 403, (role, resp_put.text)
