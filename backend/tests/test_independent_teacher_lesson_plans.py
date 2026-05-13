"""IT Phase 2 §6.4 — Light AI lesson-planning assistant (Task #209).

Coverage:
  (a) generate without AI configured → 503
  (b) generate happy path inserts row + bumps quota counter (LLM mocked)
  (c) generate respects daily quota (MAX_LESSON_PLANS_PER_DAY)
  (d) generated payload has foreign-id keys stripped from the LLM JSON
  (e) list returns only the caller's own saved plans (cross-workspace
      rows are invisible)
  (f) save-to-class flips is_saved=True; cross-workspace plan_id → 404
  (g) save-to-class with cross-workspace class_id → 404
  (h) non-IT role on every endpoint → 403
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from auth_scope import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_count, gd_find_one, gd_insert


def _headers(uid: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({"sub": uid, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


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
    user["tenant_id"] = wsid
    return user


async def _mk_principal() -> dict:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid,
        "name": f"S-{sid[:6]}",
        "code": f"S{sid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": sid,
        "email": f"p-{uid}@t.test",
        "full_name": f"P-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


def _mock_openai(monkeypatch, payload_text: str) -> None:
    """Patch get_openai_client to return a fake that echoes ``payload_text``."""
    from routes import independent_teacher_lesson_plans_routes as mod

    def _fake_client():
        choice = SimpleNamespace(message=SimpleNamespace(content=payload_text))
        completion = SimpleNamespace(choices=[choice])
        chat = SimpleNamespace(completions=SimpleNamespace(
            create=lambda **kw: completion,
        ))
        return SimpleNamespace(chat=chat)

    monkeypatch.setattr(mod, "get_openai_client", _fake_client)


# ----------------------------------------------------------------------
# (a) AI not configured → 503
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generate_without_ai_returns_503(client, monkeypatch):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"])
    from routes import independent_teacher_lesson_plans_routes as mod
    monkeypatch.setattr(mod, "get_openai_client", lambda: None)
    resp = await client.post(
        "/independent-teacher/lesson-plans/generate",
        headers=h,
        json={"topic": "الكسور"},
    )
    assert resp.status_code == 503, resp.text


# ----------------------------------------------------------------------
# (b) Happy path
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generate_inserts_row_and_bumps_counter(client, monkeypatch):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"])
    _mock_openai(monkeypatch, '{"title": "الكسور", "objectives": ["يتعرّف الطالب"]}')
    resp = await client.post(
        "/independent-teacher/lesson-plans/generate",
        headers=h,
        json={"topic": "الكسور", "subject": "رياضيات"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["lesson_plan"]["topic"] == "الكسور"
    assert body["lesson_plan"]["plan"]["title"] == "الكسور"
    assert body["lesson_plan"]["is_saved"] is False
    assert body["quota"]["used_today"] == 1

    count = await gd_count(
        db.session, "lesson_plans",
        {"workspace_school_id": user["tenant_id"]},
    )
    assert count == 1

    quota = await gd_find_one(
        db.session, "workspace_quota",
        {"workspace_school_id": user["tenant_id"]},
    )
    assert int(quota.get("lesson_plans_today") or 0) == 1


# ----------------------------------------------------------------------
# (c) Daily quota enforcement
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generate_respects_daily_quota(client, monkeypatch):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"])
    _mock_openai(monkeypatch, '{"title": "x"}')

    from quotas import independent_teacher as qmod
    monkeypatch.setattr(qmod, "MAX_LESSON_PLANS_PER_DAY", 2)
    from routes import independent_teacher_lesson_plans_routes as mod
    monkeypatch.setattr(mod, "MAX_LESSON_PLANS_PER_DAY", 2)
    # Disable the short-window burst guard so we can prove the daily
    # quota path independently (Task #221).
    monkeypatch.setattr(mod, "_BURST_SHORT_MAX", 100)
    monkeypatch.setattr(mod, "_BURST_LONG_MAX", 100)

    for _ in range(2):
        r = await client.post(
            "/independent-teacher/lesson-plans/generate",
            headers=h, json={"topic": "t"},
        )
        assert r.status_code == 200, r.text

    r = await client.post(
        "/independent-teacher/lesson-plans/generate",
        headers=h, json={"topic": "t"},
    )
    assert r.status_code == 429, r.text


# ----------------------------------------------------------------------
# (c2) Short-window burst guard (Task #221)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generate_burst_rate_limited(client, monkeypatch):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"])
    _mock_openai(monkeypatch, '{"title": "x"}')

    # First call passes the 1/10s and 3/60s windows.
    r1 = await client.post(
        "/independent-teacher/lesson-plans/generate",
        headers=h, json={"topic": "t"},
    )
    assert r1.status_code == 200, r1.text

    # Immediate second call trips the 1/10s window.
    r2 = await client.post(
        "/independent-teacher/lesson-plans/generate",
        headers=h, json={"topic": "t"},
    )
    assert r2.status_code == 429, r2.text
    body = r2.json()
    # Standard envelope is {"success": False, "error": {"code", "message"}}.
    # Must be the burst copy, NOT the daily-quota copy.
    err_msg = (body.get("error") or {}).get("message") or ""
    assert "متكررة" in err_msg, err_msg
    assert "اليومي" not in err_msg, err_msg
    assert "Retry-After" in r2.headers


@pytest.mark.asyncio
async def test_generate_burst_long_window_3_per_minute(client, monkeypatch):
    """Explicit coverage for the 3-per-60s ceiling (Task #221)."""
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"])
    _mock_openai(monkeypatch, '{"title": "x"}')

    # Disable the 1/10s window so we can isolate the 3/60s ceiling.
    from routes import independent_teacher_lesson_plans_routes as mod
    monkeypatch.setattr(mod, "_BURST_SHORT_MAX", 100)

    # Three calls within the 60s window must all succeed.
    for _ in range(3):
        r = await client.post(
            "/independent-teacher/lesson-plans/generate",
            headers=h, json={"topic": "t"},
        )
        assert r.status_code == 200, r.text

    # The fourth one in the same minute must trip the long-window guard.
    r4 = await client.post(
        "/independent-teacher/lesson-plans/generate",
        headers=h, json={"topic": "t"},
    )
    assert r4.status_code == 429, r4.text
    err_msg = (r4.json().get("error") or {}).get("message") or ""
    assert "متكررة" in err_msg, err_msg


# ----------------------------------------------------------------------
# (d) Foreign-id stripping from the LLM payload
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generate_strips_foreign_ids_from_payload(client, monkeypatch):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"])
    _mock_openai(
        monkeypatch,
        '{"title": "ok", "student_id": "s-leak", "tenant_id": "other-school", '
        '"activities": [{"name": "n", "class_id": "c-leak"}]}',
    )
    resp = await client.post(
        "/independent-teacher/lesson-plans/generate",
        headers=h, json={"topic": "t"},
    )
    assert resp.status_code == 200, resp.text
    plan = resp.json()["lesson_plan"]["plan"]
    assert "student_id" not in plan
    assert "tenant_id" not in plan
    assert "class_id" not in plan["activities"][0]


# ----------------------------------------------------------------------
# (e) List returns only the caller's saved plans (cross-ws invisible)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_returns_only_own_saved_plans(client):
    user_a = await _mk_it_workspace()
    user_b = await _mk_it_workspace()
    now = datetime.now(timezone.utc)
    # A: one saved, one draft
    await gd_insert(db.session, "lesson_plans", {
        "id": str(uuid.uuid4()),
        "workspace_school_id": user_a["tenant_id"],
        "created_by": user_a["id"],
        "topic": "saved-a",
        "language": "ar",
        "plan": {"title": "saved-a"},
        "is_saved": True,
        "created_at": now, "updated_at": now,
    })
    await gd_insert(db.session, "lesson_plans", {
        "id": str(uuid.uuid4()),
        "workspace_school_id": user_a["tenant_id"],
        "created_by": user_a["id"],
        "topic": "draft-a",
        "language": "ar",
        "plan": {"title": "draft-a"},
        "is_saved": False,
        "created_at": now, "updated_at": now,
    })
    # B: one saved (should NOT appear for A)
    await gd_insert(db.session, "lesson_plans", {
        "id": str(uuid.uuid4()),
        "workspace_school_id": user_b["tenant_id"],
        "created_by": user_b["id"],
        "topic": "saved-b",
        "language": "ar",
        "plan": {"title": "saved-b"},
        "is_saved": True,
        "created_at": now, "updated_at": now,
    })

    h = _headers(user_a["id"], user_a["role"], user_a["tenant_id"])
    resp = await client.get("/independent-teacher/lesson-plans", headers=h)
    assert resp.status_code == 200, resp.text
    plans = resp.json()["lesson_plans"]
    topics = {p["topic"] for p in plans}
    assert topics == {"saved-a"}


# ----------------------------------------------------------------------
# (f) save-to-class happy + cross-ws plan_id 404
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_save_to_class_flips_is_saved_and_blocks_cross_ws(client):
    user_a = await _mk_it_workspace()
    user_b = await _mk_it_workspace()
    now = datetime.now(timezone.utc)

    # A's plan + A's class
    plan_id = str(uuid.uuid4())
    await gd_insert(db.session, "lesson_plans", {
        "id": plan_id,
        "workspace_school_id": user_a["tenant_id"],
        "created_by": user_a["id"],
        "topic": "t", "language": "ar",
        "plan": {"title": "t"}, "is_saved": False,
        "created_at": now, "updated_at": now,
    })
    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id,
        "school_id": user_a["tenant_id"],
        "tenant_id": user_a["tenant_id"],
        "name": "C-A", "name_ar": "ص-أ",
        "is_active": True,
    })

    # B tries to save A's plan → 404 (cross-ws plan_id)
    hb = _headers(user_b["id"], user_b["role"], user_b["tenant_id"])
    r = await client.post(
        f"/independent-teacher/lesson-plans/{plan_id}/save-to-class",
        headers=hb, json={"class_id": class_id},
    )
    assert r.status_code == 404, r.text

    # A saves successfully
    ha = _headers(user_a["id"], user_a["role"], user_a["tenant_id"])
    r = await client.post(
        f"/independent-teacher/lesson-plans/{plan_id}/save-to-class",
        headers=ha, json={"class_id": class_id},
    )
    assert r.status_code == 200, r.text
    assert r.json()["lesson_plan"]["is_saved"] is True
    assert r.json()["lesson_plan"]["class_id"] == class_id


# ----------------------------------------------------------------------
# (g) save-to-class with cross-workspace class_id → 404
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_save_to_class_rejects_foreign_class(client):
    user_a = await _mk_it_workspace()
    user_b = await _mk_it_workspace()
    now = datetime.now(timezone.utc)

    plan_id = str(uuid.uuid4())
    await gd_insert(db.session, "lesson_plans", {
        "id": plan_id,
        "workspace_school_id": user_a["tenant_id"],
        "created_by": user_a["id"],
        "topic": "t", "language": "ar",
        "plan": {}, "is_saved": False,
        "created_at": now, "updated_at": now,
    })
    foreign_class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": foreign_class_id,
        "school_id": user_b["tenant_id"],
        "tenant_id": user_b["tenant_id"],
        "name": "C-B", "name_ar": "ص-ب",
        "is_active": True,
    })

    ha = _headers(user_a["id"], user_a["role"], user_a["tenant_id"])
    r = await client.post(
        f"/independent-teacher/lesson-plans/{plan_id}/save-to-class",
        headers=ha, json={"class_id": foreign_class_id},
    )
    assert r.status_code == 404, r.text


# ----------------------------------------------------------------------
# (h) non-IT roles → 403 on every endpoint
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_non_it_role_denied_403(client, monkeypatch):
    p = await _mk_principal()
    h = _headers(p["id"], p["role"], p["tenant_id"])
    _mock_openai(monkeypatch, '{"title": "x"}')

    r = await client.post(
        "/independent-teacher/lesson-plans/generate",
        headers=h, json={"topic": "t"},
    )
    assert r.status_code == 403, r.text

    r = await client.get("/independent-teacher/lesson-plans", headers=h)
    assert r.status_code == 403, r.text

    r = await client.post(
        f"/independent-teacher/lesson-plans/{uuid.uuid4()}/save-to-class",
        headers=h, json={"class_id": str(uuid.uuid4())},
    )
    assert r.status_code == 403, r.text
