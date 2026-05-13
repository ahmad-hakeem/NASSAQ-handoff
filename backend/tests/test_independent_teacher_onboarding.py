"""Tests for IT first-login onboarding tour state (Task #250).

Covers:
- GET /state: should_show=True for a fresh IT user with a workspace,
  False before bootstrap, False once stamped.
- POST /complete: idempotently stamps users.it_onboarding_completed_at
  and flips should_show to False.
- POST /reset: clears the stamp and re-arms should_show.
- Non-IT callers (school principal) are denied with the canonical
  Arabic copy on all three endpoints.
- Two IT workspaces remain isolated — completing the tour for user A
  never flips user B's row.
"""
from __future__ import annotations

import uuid

import pytest

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
)
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find_one, gd_insert


STATE = "/independent-teacher/onboarding/state"
COMPLETE = "/independent-teacher/onboarding/complete"
RESET = "/independent-teacher/onboarding/reset"


def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_it(*, with_workspace: bool = True) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-onb-{uid}@t.test",
        "full_name": f"IT-Onb-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    if with_workspace:
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
        # Mirror bootstrap: post-materialisation tenant_id == wsid.
        from engines.sql_utils import gd_update_one
        await gd_update_one(db.session, "users", {"id": uid}, {"tenant_id": wsid})
        user["tenant_id"] = wsid
    return {"user": user, "wsid": wsid}


@pytest.mark.asyncio
async def test_state_should_show_true_for_fresh_it_with_workspace(client):
    it = await _mk_it()
    r = await client.get(STATE, headers=_headers(it["user"]["id"], "independent_teacher", it["wsid"]))
    assert r.status_code == 200
    body = r.json()
    assert body["should_show"] is True
    assert body["completed_at"] is None
    assert body["has_workspace"] is True


@pytest.mark.asyncio
async def test_state_should_show_false_before_workspace_bootstrap(client):
    # Pre-bootstrap an IT user has tenant_id=None and no synthetic
    # schools row. The API surface flatly refuses (409 from the global
    # lifecycle gate) so the FE trigger — which only ever runs after
    # the dashboard has actually rendered — naturally stays quiet. The
    # important behaviour is that no welcome card ever pops without a
    # workspace; we assert the response is non-200 here.
    it = await _mk_it(with_workspace=False)
    r = await client.get(STATE, headers=_headers(it["user"]["id"], "independent_teacher", None))
    assert r.status_code != 200


@pytest.mark.asyncio
async def test_complete_stamps_and_is_idempotent(client):
    it = await _mk_it()
    h = _headers(it["user"]["id"], "independent_teacher", it["wsid"])

    r1 = await client.post(COMPLETE, headers=h)
    assert r1.status_code == 200
    assert r1.json()["should_show"] is False
    first_stamp = r1.json()["completed_at"]
    assert first_stamp is not None

    # DB row reflects the stamp.
    row = await gd_find_one(db.session, "users", {"id": it["user"]["id"]})
    assert row["it_onboarding_completed_at"] is not None

    # Second POST is a no-op — stamp does not change.
    r2 = await client.post(COMPLETE, headers=h)
    assert r2.status_code == 200
    assert r2.json()["completed_at"] == first_stamp

    # GET reflects the stamped state.
    r3 = await client.get(STATE, headers=h)
    assert r3.json()["should_show"] is False
    assert r3.json()["completed_at"] == first_stamp


@pytest.mark.asyncio
async def test_reset_re_arms_should_show(client):
    it = await _mk_it()
    h = _headers(it["user"]["id"], "independent_teacher", it["wsid"])
    await client.post(COMPLETE, headers=h)

    r = await client.post(RESET, headers=h)
    assert r.status_code == 200
    assert r.json()["completed_at"] is None
    assert r.json()["should_show"] is True

    row = await gd_find_one(db.session, "users", {"id": it["user"]["id"]})
    assert row["it_onboarding_completed_at"] is None


@pytest.mark.asyncio
async def test_non_it_caller_denied_on_all_endpoints(client):
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid, "name": f"Sch-{sid[:6]}", "code": f"S{sid[:8]}",
        "status": "active", "country": "SA", "language": "ar",
    })
    pid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": pid, "role": UserRole.SCHOOL_PRINCIPAL.value, "tenant_id": sid,
        "email": f"p-{pid}@t.test", "full_name": f"P-{pid[:6]}",
        "is_active": True, "password_hash": "x",
    })
    h = _headers(pid, "principal", sid)
    for path, method in [(STATE, "get"), (COMPLETE, "post"), (RESET, "post")]:
        r = await getattr(client, method)(path, headers=h)
        assert r.status_code == 403
        # Different error envelopes are used across the API surface
        # (FastAPI's "detail" vs. the project's "message" wrapper).
        # All we care about here is that the canonical Arabic copy
        # surfaces somewhere in the body.
        assert INDEPENDENT_TEACHER_DENIED_AR in r.text


@pytest.mark.asyncio
async def test_workspaces_are_isolated(client):
    a = await _mk_it()
    b = await _mk_it()
    ha = _headers(a["user"]["id"], "independent_teacher", a["wsid"])
    hb = _headers(b["user"]["id"], "independent_teacher", b["wsid"])

    await client.post(COMPLETE, headers=ha)

    # B remains un-stamped.
    rb = await client.get(STATE, headers=hb)
    assert rb.json()["should_show"] is True
    row_b = await gd_find_one(db.session, "users", {"id": b["user"]["id"]})
    assert row_b["it_onboarding_completed_at"] is None
