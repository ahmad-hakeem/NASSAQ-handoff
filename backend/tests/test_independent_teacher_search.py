"""IT workspace-wide command-palette search (Task #251).

Coverage:
  * empty / sub-min-length q returns empty payload
  * results pinned to itw_{user_id} — cross-workspace rows excluded
  * limit honoured per category
  * non-IT role → 403
  * lesson plans / calendar events restricted to created_by == user.id
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from auth_scope import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


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


async def _mk_student(school_id: str, name: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": school_id,
        "full_name": name,
        "is_active": True,
    })
    return sid


async def _mk_class(school_id: str, name: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "name": name,
        "is_active": True,
    })
    return cid


async def _mk_subject(school_id: str, name_ar: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid,
        "school_id": school_id,
        "name": name_ar,
        "name_ar": name_ar,
        "is_active": True,
    })
    return sid


async def _mk_lesson_plan(workspace_id: str, user_id: str, topic: str) -> str:
    pid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await gd_insert(db.session, "lesson_plans", {
        "id": pid,
        "workspace_school_id": workspace_id,
        "created_by": user_id,
        "topic": topic,
        "language": "ar",
        "plan": {"title": topic},
        "is_saved": True,
        "created_at": now,
        "updated_at": now,
    })
    return pid


async def _mk_calendar_event(tenant_id: str, user_id: str, title: str, date: str) -> str:
    eid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await gd_insert(db.session, "calendar_events", {
        "id": eid,
        "tenant_id": tenant_id,
        "title_ar": title,
        "type": "meeting",
        "date": date,
        "is_personal": True,
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    })
    return eid


# ----------------------------------------------------------------------
# (a) Empty / sub-min-length q → empty payload
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_q_returns_empty_payload(client):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"])
    await _mk_student(user["tenant_id"], "أحمد محمد")

    for q in ("", " ", "a"):
        r = await client.get(
            "/independent-teacher/search",
            headers=h,
            params={"q": q},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        for cat in ("students", "classes", "subjects", "lesson_plans", "calendar_events"):
            assert body[cat] == [], f"{cat} should be empty for q={q!r}"


# ----------------------------------------------------------------------
# (b) Workspace pinning — cross-workspace rows excluded
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workspace_pinning_excludes_foreign_rows(client):
    me = await _mk_it_workspace()
    other = await _mk_it_workspace()
    h = _headers(me["id"], me["role"], me["tenant_id"])

    await _mk_student(me["tenant_id"], "نور الهدى")
    await _mk_student(other["tenant_id"], "نور البعيد")
    await _mk_class(me["tenant_id"], "صف نور")
    await _mk_class(other["tenant_id"], "صف نور البعيد")
    await _mk_subject(me["tenant_id"], "نور الرياضيات")
    await _mk_subject(other["tenant_id"], "نور الفيزياء")
    await _mk_lesson_plan(me["tenant_id"], me["id"], "نور الكسور")
    await _mk_lesson_plan(other["tenant_id"], other["id"], "نور الجبر")
    await _mk_calendar_event(me["tenant_id"], me["id"], "نور اجتماع", "2026-05-20")
    await _mk_calendar_event(other["tenant_id"], other["id"], "نور رحلة", "2026-05-21")

    r = await client.get(
        "/independent-teacher/search",
        headers=h,
        params={"q": "نور"},
    )
    assert r.status_code == 200, r.text
    body = r.json()

    for cat in ("students", "classes", "subjects", "lesson_plans", "calendar_events"):
        assert len(body[cat]) == 1, f"{cat}: {body[cat]}"
        assert "البعيد" not in body[cat][0]["primary"]
        assert "الجبر" not in body[cat][0]["primary"]
        assert "رحلة" not in body[cat][0]["primary"]


# ----------------------------------------------------------------------
# (c) Limit enforcement
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_limit_enforced_per_category(client):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"])
    for i in range(15):
        await _mk_student(user["tenant_id"], f"طالب رقم {i}")

    r = await client.get(
        "/independent-teacher/search",
        headers=h,
        params={"q": "طالب", "limit": 5},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["students"]) == 5


# ----------------------------------------------------------------------
# (d) Non-IT role → 403
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_non_it_role_forbidden(client):
    p = await _mk_principal()
    h = _headers(p["id"], p["role"], p["tenant_id"])
    r = await client.get(
        "/independent-teacher/search",
        headers=h,
        params={"q": "test"},
    )
    assert r.status_code == 403, r.text


# ----------------------------------------------------------------------
# (e) Lesson plans / events restricted to created_by == user.id
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lesson_plans_and_events_restricted_to_author(client):
    me = await _mk_it_workspace()
    h = _headers(me["id"], me["role"], me["tenant_id"])

    # Plan and event authored by ME — visible.
    await _mk_lesson_plan(me["tenant_id"], me["id"], "زاوية المثلث")
    await _mk_calendar_event(me["tenant_id"], me["id"], "زاوية اللقاء", "2026-06-01")

    # Plan and event physically in MY workspace but authored by another
    # user_id — must NOT appear (defense-in-depth: workspace tenants are
    # sealed to one IT, but we double-check on created_by anyway).
    other_uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": other_uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": me["tenant_id"],
        "email": f"other-{other_uid}@t.test",
        "full_name": f"Other-{other_uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    })
    await _mk_lesson_plan(me["tenant_id"], other_uid, "زاوية الجبر")
    await _mk_calendar_event(me["tenant_id"], other_uid, "زاوية رحلة", "2026-06-02")

    r = await client.get(
        "/independent-teacher/search",
        headers=h,
        params={"q": "زاوية"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    plan_topics = [p["primary"] for p in body["lesson_plans"]]
    event_titles = [e["primary"] for e in body["calendar_events"]]
    assert "زاوية المثلث" in plan_topics
    assert "زاوية الجبر" not in plan_topics
    assert "زاوية اللقاء" in event_titles
    assert "زاوية رحلة" not in event_titles


# ----------------------------------------------------------------------
# (f) Ranking — exact match comes before substring match
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_exact_match_ranked_first(client):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"])
    await _mk_class(user["tenant_id"], "صف الرياضيات المتقدم")
    await _mk_class(user["tenant_id"], "صف رياضيات")  # closer prefix-ish
    await _mk_class(user["tenant_id"], "رياضيات")  # exact

    r = await client.get(
        "/independent-teacher/search",
        headers=h,
        params={"q": "رياضيات"},
    )
    body = r.json()
    names = [c["primary"] for c in body["classes"]]
    assert names[0] == "رياضيات"


# ----------------------------------------------------------------------
# (g) Per-user rate limit — burst → 429 with safe Arabic message
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_per_user_rate_limit_returns_429_on_burst(client):
    from routes import independent_teacher_search_routes as search_mod
    from middleware.rate_limiter import rate_store

    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"])

    # Wipe any prior counter for this user so the test is deterministic.
    async with rate_store._lock:
        rate_store._store.pop(f"it_search:{user['id']}", None)

    max_req = search_mod._SEARCH_RATE_MAX
    last_status = None
    for _ in range(max_req):
        r = await client.get(
            "/independent-teacher/search",
            headers=h,
            params={"q": "x"},
        )
        last_status = r.status_code
    assert last_status == 200

    r = await client.get(
        "/independent-teacher/search",
        headers=h,
        params={"q": "x"},
    )
    assert r.status_code == 429, r.text
    assert "Retry-After" in r.headers
    body = r.json()
    # The global StarletteHTTPException handler wraps string detail under
    # ``error.message``; the safe Arabic message must round-trip verbatim
    # so the FE NassaqAlertDialog renders it unchanged.
    assert body["error"]["message"] == search_mod._MSG_RATE_LIMITED_AR

    # Independent across users — sibling IT account is unaffected.
    other = await _mk_it_workspace()
    h2 = _headers(other["id"], other["role"], other["tenant_id"])
    r2 = await client.get(
        "/independent-teacher/search",
        headers=h2,
        params={"q": "x"},
    )
    assert r2.status_code == 200, r2.text
