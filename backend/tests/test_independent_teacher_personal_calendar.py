"""Tests for IT personal calendar events (Task #208 §6.3).

Covers:
- POST tags rows is_personal=True and pins tenant_id=itw_{user_id} +
  created_by=current_user.id (request-body overrides ignored).
- GET only returns the caller's own personal events in their workspace.
- Cross-workspace ids return 404 (§8 inv. 3) on GET single (via
  PUT/DELETE), PUT, and DELETE — never 200/403.
- Another IT in another workspace cannot see or mutate the events.
- Legacy principal /v1/calendar/events surface is untouched: a
  principal in their own school still gets their school-wide rows back.
- A non-IT caller (school principal) is denied (403) on the new IT
  surface.
- The role's permission set exposes events.author_own.
"""
from __future__ import annotations

import uuid

import pytest

from src.core.guards.tenant_guard import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
)
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find_one, gd_insert
from src.core.middleware.rbac import Permission, ROLE_PERMISSIONS


PATH = "/independent-teacher/calendar/events"

# Dynamic future dates: the calendar API rejects past dates, so hardcoded
# literals become time-bombs once the wall clock passes them.
from datetime import date as _date, timedelta as _timedelta
_FUTURE_D1 = (_date.today() + _timedelta(days=30)).isoformat()
_FUTURE_D2 = (_date.today() + _timedelta(days=31)).isoformat()
LEGACY_PATH = "/v1/calendar/events"


def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_it() -> dict:
    """Create an Independent-Teacher user and matching workspace school."""
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-cal-{uid}@t.test",
        "full_name": f"IT-Cal-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher",
        "tenant_type": "independent_teacher",
    })
    return {"user": user, "wsid": wsid}


async def _mk_principal_school() -> dict:
    """Create a real school + principal user for legacy regression."""
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid,
        "name": f"Sch-{sid[:6]}",
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
        "email": f"prin-cal-{uid}@t.test",
        "full_name": f"Prin-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return {"user": user, "school_id": sid}


# -- Permission slice -----------------------------------------------------

def test_permission_exposed_in_independent_teacher_role():
    perms = ROLE_PERMISSIONS["independent_teacher"]
    assert Permission.EVENTS_AUTHOR_OWN.value in perms
    # Principal must NOT silently inherit it.
    assert Permission.EVENTS_AUTHOR_OWN.value not in ROLE_PERMISSIONS["school_principal"]
    assert Permission.EVENTS_AUTHOR_OWN.value not in ROLE_PERMISSIONS["teacher"]


# -- Create / List --------------------------------------------------------

@pytest.mark.asyncio
async def test_create_personal_event_pins_tenant_and_author(client):
    ctx = await _mk_it()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    payload = {
        "title_ar": "اجتماع شخصي",
        "type": "meeting",
        "date": _FUTURE_D1,
        "details_ar": "تحضير الدرس",
    }
    resp = await client.post(PATH, json=payload, headers=h)
    assert resp.status_code == 201, resp.text
    body = resp.json()["event"]
    assert body["title_ar"] == "اجتماع شخصي"
    assert body["is_personal"] is True
    assert body["created_by"] == ctx["user"]["id"]
    assert body["tenant_id"] == ctx["wsid"]

    # DB-level verification — column persisted, tenant pinned.
    row = await gd_find_one(db.session, "calendar_events", {"id": body["id"]})
    assert row is not None
    assert row["tenant_id"] == ctx["wsid"]
    assert row["created_by"] == ctx["user"]["id"]
    assert row["is_personal"] is True


@pytest.mark.asyncio
async def test_create_rejects_missing_title(client):
    ctx = await _mk_it()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    resp = await client.post(PATH, json={"date": _FUTURE_D1}, headers=h)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_rejects_bad_date(client):
    ctx = await _mk_it()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    resp = await client.post(
        PATH, json={"title_ar": "اختبار", "date": "bad"}, headers=h,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_returns_only_callers_personal_events(client):
    a = await _mk_it()
    b = await _mk_it()
    ha = _headers(a["user"]["id"], a["user"]["role"], a["wsid"])
    hb = _headers(b["user"]["id"], b["user"]["role"], b["wsid"])
    await client.post(PATH, json={"title_ar": "A", "date": _FUTURE_D1}, headers=ha)
    await client.post(PATH, json={"title_ar": "B", "date": _FUTURE_D2}, headers=hb)

    resp_a = await client.get(PATH, headers=ha)
    assert resp_a.status_code == 200
    titles_a = [e["title_ar"] for e in resp_a.json()["events"]]
    assert titles_a == ["A"]

    resp_b = await client.get(PATH, headers=hb)
    titles_b = [e["title_ar"] for e in resp_b.json()["events"]]
    assert titles_b == ["B"]


# -- Cross-workspace 404 invariant (§8 inv. 3) ----------------------------

@pytest.mark.asyncio
async def test_cross_workspace_get_via_update_returns_404(client):
    a = await _mk_it()
    b = await _mk_it()
    ha = _headers(a["user"]["id"], a["user"]["role"], a["wsid"])
    hb = _headers(b["user"]["id"], b["user"]["role"], b["wsid"])
    created = (await client.post(
        PATH, json={"title_ar": "A-event", "date": _FUTURE_D1}, headers=ha,
    )).json()["event"]
    eid = created["id"]

    # B tries to read A's event by-id via PUT — must 404, never 403/200.
    r_put = await client.put(
        f"{PATH}/{eid}", json={"title_ar": "hijack"}, headers=hb,
    )
    assert r_put.status_code == 404, r_put.text

    r_del = await client.delete(f"{PATH}/{eid}", headers=hb)
    assert r_del.status_code == 404, r_del.text

    # A's event must still exist and be unchanged.
    row = await gd_find_one(db.session, "calendar_events", {"id": eid})
    assert row is not None
    assert row["title_ar"] == "A-event"


# -- Update / Delete ------------------------------------------------------

@pytest.mark.asyncio
async def test_update_own_event_persists(client):
    ctx = await _mk_it()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    created = (await client.post(
        PATH, json={"title_ar": "old", "date": _FUTURE_D1}, headers=h,
    )).json()["event"]

    resp = await client.put(
        f"{PATH}/{created['id']}",
        json={"title_ar": "new", "type": "exam"},
        headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()["event"]
    assert body["title_ar"] == "new"
    assert body["type"] == "exam"
    assert body["is_personal"] is True
    assert body["tenant_id"] == ctx["wsid"]


@pytest.mark.asyncio
async def test_delete_own_event(client):
    ctx = await _mk_it()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["wsid"])
    created = (await client.post(
        PATH, json={"title_ar": "x", "date": _FUTURE_D1}, headers=h,
    )).json()["event"]

    resp = await client.delete(f"{PATH}/{created['id']}", headers=h)
    assert resp.status_code == 200
    row = await gd_find_one(db.session, "calendar_events", {"id": created["id"]})
    assert row is None


# -- Non-IT denial --------------------------------------------------------

@pytest.mark.asyncio
async def test_principal_denied_on_it_surface(client):
    ctx = await _mk_principal_school()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["school_id"])
    resp = await client.get(PATH, headers=h)
    assert resp.status_code == 403
    body = resp.json()
    msg = body.get("detail") or body.get("error", {}).get("message", "")
    assert INDEPENDENT_TEACHER_DENIED_AR in str(msg)

    resp_post = await client.post(
        PATH, json={"title_ar": "x", "date": _FUTURE_D1}, headers=h,
    )
    assert resp_post.status_code == 403


# -- Legacy principal calendar regression --------------------------------

@pytest.mark.asyncio
async def test_principal_legacy_calendar_unchanged(client):
    ctx = await _mk_principal_school()
    h = _headers(ctx["user"]["id"], ctx["user"]["role"], ctx["school_id"])
    # Create via legacy route — no is_personal flag passed.
    resp = await client.post(
        LEGACY_PATH,
        json={"title_ar": "اجتماع المدرسة", "date": _FUTURE_D1, "type": "meeting"},
        headers=h,
    )
    assert resp.status_code == 201, resp.text
    eid = resp.json()["event"]["id"]

    # Row tagged with the school tenant; is_personal must NOT be true.
    row = await gd_find_one(db.session, "calendar_events", {"id": eid})
    assert row is not None
    assert row["tenant_id"] == ctx["school_id"]
    assert not bool(row.get("is_personal"))

    # Legacy listing still returns it.
    listing = (await client.get(LEGACY_PATH, headers=h)).json()
    assert any(e["id"] == eid for e in listing["events"])
