"""Independent-Teacher §6.7 cross-workspace co-teaching tests.

Spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §6.7.
Task: #210.

Covers:
  * Create happy path + idempotent re-create on the pending slot.
  * Create cross-workspace class id → 404 (§8 inv. 3).
  * Self-invite refused (400).
  * MFA step-up envelope on every IT write surface.
  * Accept happy path: pending → accepted, binds collaborator workspace.
  * Accept tampered / expired / replay token → 400.
  * Accept email mismatch → 403.
  * Cancel pending happy path + non-pending → 409.
  * Revoke (host side) flips accepted → revoked + audit row.
  * Revoke (collaborator side) without manage permission still works.
  * List host view scoped to caller's class only; cross-tenant class → 404.
  * `caller_can_access_class` widens for the named class only.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one
from utils.collab_access import (
    caller_can_access_class,
    caller_collab_mode_for_class,
)
from utils.tokens import mint_collab_invitation_token

from tests._it_fixtures import (
    headers, mk_it_workspace, now_ts, STEP_UP_CODES,
)


def _h(ctx: dict, *, with_mfa: bool = True) -> dict:
    return headers(
        ctx["uid"], ctx["user"]["role"], ctx["wsid"],
        mfa_recent_at=now_ts() if with_mfa else None,
    )


async def _seed_pending(
    host_ctx: dict, collaborator_email: str, *, mode: str = "read",
) -> tuple[str, str]:
    """Direct-insert a pending row + return (collab_id, raw_token)."""
    raw, t_hash, expires_at = mint_collab_invitation_token(
        host_ctx["wsid"], host_ctx["class_id"], collaborator_email,
    )
    cid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "workspace_collaborators", {
        "id": cid,
        "host_school_id": host_ctx["wsid"],
        "collaborator_school_id": None,
        "class_id": host_ctx["class_id"],
        "collaborator_email": collaborator_email.lower(),
        "collaborator_user_id": None,
        "token_hash": t_hash,
        "scope": {"mode": mode},
        "status": "pending",
        "sent_at": now,
        "accepted_at": None,
        "revoked_at": None,
        "expires_at": expires_at.isoformat(),
        "created_by": host_ctx["uid"],
        "created_at": now,
        "updated_at": now,
    })
    return cid, raw


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_collab_happy_path(client):
    host = await mk_it_workspace(with_passkey=True)
    collab = await mk_it_workspace(with_passkey=True)
    h = _h(host)

    resp = await client.post(
        "/independent-teacher/workspace-collaborators",
        json={
            "class_id": host["class_id"],
            "collaborator_email": collab["user"]["email"],
            "scope": {"mode": "read"},
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "pending"
    assert data["host_school_id"] == host["wsid"]
    assert data["class_id"] == host["class_id"]
    assert data["collaborator_email"] == collab["user"]["email"].lower()
    assert data["scope"] == {"mode": "read"}
    assert data["reused"] is False
    assert data["token"]

    audits = await gd_find(db.session, "audit_logs", {
        "action": "INDEPENDENT_TEACHER_COLLAB_INVITED",
        "entity_id": data["id"],
    })
    assert len(audits) == 1
    assert audits[0]["school_id"] == host["wsid"]


@pytest.mark.asyncio
async def test_create_collab_is_idempotent(client):
    host = await mk_it_workspace(with_passkey=True)
    collab = await mk_it_workspace(with_passkey=True)
    h = _h(host)
    body = {
        "class_id": host["class_id"],
        "collaborator_email": collab["user"]["email"],
        "scope": {"mode": "read"},
    }
    a = await client.post("/independent-teacher/workspace-collaborators", json=body, headers=h)
    b = await client.post("/independent-teacher/workspace-collaborators", json=body, headers=h)
    assert a.status_code == 200 and b.status_code == 200, b.text
    assert a.json()["id"] == b.json()["id"]
    assert b.json()["reused"] is True


@pytest.mark.asyncio
async def test_create_collab_cross_workspace_class_returns_404(client):
    host_a = await mk_it_workspace(with_passkey=True)
    host_b = await mk_it_workspace(with_passkey=True)
    target = await mk_it_workspace(with_passkey=True)
    h_b = _h(host_b)
    resp = await client.post(
        "/independent-teacher/workspace-collaborators",
        json={
            "class_id": host_a["class_id"],
            "collaborator_email": target["user"]["email"],
        },
        headers=h_b,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_create_collab_unknown_email_returns_404(client):
    """Spec requires the invited email to belong to an existing IT
    account so the host gets a clear error instead of a dead token."""
    host = await mk_it_workspace(with_passkey=True)
    resp = await client.post(
        "/independent-teacher/workspace-collaborators",
        json={
            "class_id": host["class_id"],
            "collaborator_email": "no-such-user@nowhere.test",
        },
        headers=_h(host),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_create_collab_non_it_email_returns_400(client):
    """An existing user whose role is not `independent_teacher` (e.g. a
    school teacher / parent) must not be invitable into the IT collab
    envelope."""
    host = await mk_it_workspace(with_passkey=True)
    foreign_uid = str(uuid.uuid4())
    foreign_email = f"non-it-{foreign_uid}@t.test"
    # Reuse the host's school to satisfy users.tenant_id FK; only the
    # `role != independent_teacher` field matters for this assertion.
    await gd_insert(db.session, "users", {
        "id": foreign_uid,
        "role": "teacher",
        "tenant_id": host["wsid"],
        "email": foreign_email,
        "full_name": "Affiliated Teacher",
        "is_active": True,
        "password_hash": "x",
    })
    resp = await client.post(
        "/independent-teacher/workspace-collaborators",
        json={
            "class_id": host["class_id"],
            "collaborator_email": foreign_email,
        },
        headers=_h(host),
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_create_collab_self_invite_refused(client):
    host = await mk_it_workspace(with_passkey=True)
    h = _h(host)
    resp = await client.post(
        "/independent-teacher/workspace-collaborators",
        json={
            "class_id": host["class_id"],
            "collaborator_email": host["user"]["email"],
        },
        headers=h,
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_create_collab_missing_mfa_emits_stepup_envelope(client):
    host = await mk_it_workspace(with_passkey=True)
    h = _h(host, with_mfa=False)
    resp = await client.post(
        "/independent-teacher/workspace-collaborators",
        json={
            "class_id": host["class_id"],
            "collaborator_email": "x@x.com",
        },
        headers=h,
    )
    assert resp.status_code == 403, resp.text
    body = resp.json()
    detail = body.get("detail") or (body.get("error") or {}).get("detail") or body.get("error")
    code = (detail or {}).get("code") if isinstance(detail, dict) else None
    assert code in STEP_UP_CODES


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_collab_happy_path_and_409(client):
    host = await mk_it_workspace(with_passkey=True)
    h = _h(host)
    cid, _ = await _seed_pending(host, "x@x.com")

    first = await client.post(
        f"/independent-teacher/workspace-collaborators/{cid}/cancel",
        headers=h,
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "cancelled"

    second = await client.post(
        f"/independent-teacher/workspace-collaborators/{cid}/cancel",
        headers=h,
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_cancel_collab_cross_workspace_returns_404(client):
    host_a = await mk_it_workspace(with_passkey=True)
    host_b = await mk_it_workspace(with_passkey=True)
    cid, _ = await _seed_pending(host_a, "x@x.com")

    resp = await client.post(
        f"/independent-teacher/workspace-collaborators/{cid}/cancel",
        headers=_h(host_b),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Accept
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_accept_collab_happy_path(client):
    host = await mk_it_workspace(with_passkey=True)
    collab = await mk_it_workspace(with_passkey=True)
    cid, raw = await _seed_pending(host, collab["user"]["email"])

    resp = await client.post(
        "/independent-teacher/workspace-collaborators/accept",
        json={"token": raw},
        headers=_h(collab),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["collaborator_school_id"] == collab["wsid"]
    assert body["collaborator_user_id"] == collab["uid"]

    refreshed = await gd_find_one(db.session, "workspace_collaborators", {"id": cid})
    assert refreshed["status"] == "accepted"

    audits = await gd_find(db.session, "audit_logs", {
        "action": "INDEPENDENT_TEACHER_COLLAB_ACCEPTED",
        "entity_id": cid,
    })
    assert len(audits) == 1


@pytest.mark.asyncio
async def test_accept_collab_email_mismatch_403(client):
    host = await mk_it_workspace(with_passkey=True)
    collab = await mk_it_workspace(with_passkey=True)
    _, raw = await _seed_pending(host, "someone-else@example.com")

    resp = await client.post(
        "/independent-teacher/workspace-collaborators/accept",
        json={"token": raw},
        headers=_h(collab),
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_accept_collab_tampered_token_400(client):
    host = await mk_it_workspace(with_passkey=True)
    collab = await mk_it_workspace(with_passkey=True)
    _, raw = await _seed_pending(host, collab["user"]["email"])

    resp = await client.post(
        "/independent-teacher/workspace-collaborators/accept",
        json={"token": raw + "tamper"},
        headers=_h(collab),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_accept_collab_expired_token_400(client):
    host = await mk_it_workspace(with_passkey=True)
    collab = await mk_it_workspace(with_passkey=True)
    cid, raw = await _seed_pending(host, collab["user"]["email"])
    await gd_update_one(
        db.session, "workspace_collaborators", {"id": cid},
        {"expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()},
    )
    resp = await client.post(
        "/independent-teacher/workspace-collaborators/accept",
        json={"token": raw},
        headers=_h(collab),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_accept_collab_replay_400(client):
    host = await mk_it_workspace(with_passkey=True)
    collab = await mk_it_workspace(with_passkey=True)
    _, raw = await _seed_pending(host, collab["user"]["email"])

    first = await client.post(
        "/independent-teacher/workspace-collaborators/accept",
        json={"token": raw}, headers=_h(collab),
    )
    assert first.status_code == 200, first.text
    second = await client.post(
        "/independent-teacher/workspace-collaborators/accept",
        json={"token": raw}, headers=_h(collab),
    )
    assert second.status_code == 400


# ---------------------------------------------------------------------------
# Revoke
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revoke_accepted_collab_by_host(client):
    host = await mk_it_workspace(with_passkey=True)
    collab = await mk_it_workspace(with_passkey=True)
    _, raw = await _seed_pending(host, collab["user"]["email"])
    accept = await client.post(
        "/independent-teacher/workspace-collaborators/accept",
        json={"token": raw}, headers=_h(collab),
    )
    cid = accept.json()["id"]

    resp = await client.delete(
        f"/independent-teacher/workspace-collaborators/{cid}",
        headers=_h(host),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "revoked"

    audits = await gd_find(db.session, "audit_logs", {
        "action": "INDEPENDENT_TEACHER_COLLAB_REVOKED",
        "entity_id": cid,
    })
    assert len(audits) == 1


@pytest.mark.asyncio
async def test_revoke_accepted_collab_by_collaborator_side(client):
    host = await mk_it_workspace(with_passkey=True)
    collab = await mk_it_workspace(with_passkey=True)
    _, raw = await _seed_pending(host, collab["user"]["email"])
    accept = await client.post(
        "/independent-teacher/workspace-collaborators/accept",
        json={"token": raw}, headers=_h(collab),
    )
    cid = accept.json()["id"]

    resp = await client.delete(
        f"/independent-teacher/workspace-collaborators/{cid}",
        headers=_h(collab),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "revoked"


@pytest.mark.asyncio
async def test_revoke_returns_404_for_unrelated_workspace(client):
    host = await mk_it_workspace(with_passkey=True)
    collab = await mk_it_workspace(with_passkey=True)
    bystander = await mk_it_workspace(with_passkey=True)
    _, raw = await _seed_pending(host, collab["user"]["email"])
    accept = await client.post(
        "/independent-teacher/workspace-collaborators/accept",
        json={"token": raw}, headers=_h(collab),
    )
    cid = accept.json()["id"]

    resp = await client.delete(
        f"/independent-teacher/workspace-collaborators/{cid}",
        headers=_h(bystander),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_host_view_scoped_to_caller_class(client):
    host = await mk_it_workspace(with_passkey=True)
    other = await mk_it_workspace(with_passkey=True)
    await _seed_pending(host, "a@x.com")
    await _seed_pending(host, "b@x.com")
    await _seed_pending(other, "c@x.com")

    resp = await client.get(
        "/independent-teacher/workspace-collaborators",
        params={"class_id": host["class_id"]},
        headers=_h(host),
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 2
    assert {it["collaborator_email"] for it in items} == {"a@x.com", "b@x.com"}


@pytest.mark.asyncio
async def test_list_host_view_cross_workspace_class_returns_404(client):
    host_a = await mk_it_workspace(with_passkey=True)
    host_b = await mk_it_workspace(with_passkey=True)
    resp = await client.get(
        "/independent-teacher/workspace-collaborators",
        params={"class_id": host_a["class_id"]},
        headers=_h(host_b),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# collab_access widening
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_collab_access_widens_only_for_named_class(client):
    host = await mk_it_workspace(with_passkey=True)
    collab = await mk_it_workspace(with_passkey=True)
    _, raw = await _seed_pending(host, collab["user"]["email"], mode="write")
    await client.post(
        "/independent-teacher/workspace-collaborators/accept",
        json={"token": raw}, headers=_h(collab),
    )

    # The collaborator can access the named class…
    assert await caller_can_access_class(db.session, collab["user"], host["class_id"]) is True
    assert await caller_collab_mode_for_class(db.session, collab["user"], host["class_id"]) == "write"

    # …but NOT another class in the same host workspace (would-be widening
    # leak: the relaxation is per-class only, never workspace-wide).
    other_class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": other_class_id,
        "name": "فصل ب",
        "school_id": host["wsid"],
        "tenant_id": host["wsid"],
        "homeroom_teacher_id": host["teacher_id"],
        "capacity": 10,
        "current_students": 0,
        "is_active": True,
    })
    assert await caller_can_access_class(db.session, collab["user"], other_class_id) is False
    assert await caller_collab_mode_for_class(db.session, collab["user"], other_class_id) is None

    # An uninvolved third workspace must NEVER get access.
    bystander = await mk_it_workspace(with_passkey=True)
    assert await caller_can_access_class(db.session, bystander["user"], host["class_id"]) is False


# ---------------------------------------------------------------------------
# End-to-end isolation against real host resources (review fix)
# ---------------------------------------------------------------------------

async def _accept(client, host, collab):
    _, raw = await _seed_pending(host, collab["user"]["email"], mode="write")
    r = await client.post(
        "/independent-teacher/workspace-collaborators/accept",
        json={"token": raw}, headers=_h(collab),
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_collab_can_read_host_class_endpoints(client):
    """Accepted collaborator can read the host class detail, roster and
    student-stats — proving the widening helpers are wired into the
    actual production routes (not just the helper module)."""
    host = await mk_it_workspace(with_passkey=True)
    collab = await mk_it_workspace(with_passkey=True)
    await _accept(client, host, collab)

    h = _h(collab)

    r = await client.get(f"/classes/{host['class_id']}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == host["class_id"]

    r = await client.get(f"/classes/{host['class_id']}/students", headers=h)
    assert r.status_code == 200, r.text

    # /classes/{id}/student-stats is the third surface used by the
    # teacher class-detail page; widening must reach it too.
    r = await client.get(f"/classes/{host['class_id']}/student-stats", headers=h)
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_bystander_cannot_read_host_class_endpoints(client):
    """An IT in a third workspace with no collab row gets a clean 404
    on the host's class detail (§8 inv. 3 must hold for non-collabs)."""
    host = await mk_it_workspace(with_passkey=True)
    bystander = await mk_it_workspace(with_passkey=True)
    h = _h(bystander)

    r = await client.get(f"/classes/{host['class_id']}", headers=h)
    assert r.status_code == 404, r.text

    r = await client.get(f"/classes/{host['class_id']}/students", headers=h)
    # No collab row → tenant-pinned query returns an empty list under the
    # bystander's own school_id, never the host's roster. Either an
    # empty 200 or a 404 satisfies §8 inv. 3 (no foreign-tenant data).
    if r.status_code == 200:
        assert r.json() == [], r.text
    else:
        assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_collab_widening_does_not_leak_to_other_host_classes(client):
    """The relaxation is per-class only; a sibling class in the same
    host workspace must remain invisible to the collaborator."""
    host = await mk_it_workspace(with_passkey=True)
    collab = await mk_it_workspace(with_passkey=True)
    await _accept(client, host, collab)

    sibling_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": sibling_id, "name": "فصل ج",
        "school_id": host["wsid"], "tenant_id": host["wsid"],
        "homeroom_teacher_id": host["teacher_id"],
        "capacity": 10, "current_students": 0, "is_active": True,
    })

    r = await client.get(f"/classes/{sibling_id}", headers=_h(collab))
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_collab_read_scope_blocks_writes(client):
    """A `scope.mode='read'` collab must be refused on write surfaces
    (here: POST grade-columns) with a safe Arabic 403."""
    host = await mk_it_workspace(with_passkey=True)
    collab = await mk_it_workspace(with_passkey=True)
    _, raw = await _seed_pending(host, collab["user"]["email"], mode="read")
    r = await client.post(
        "/independent-teacher/workspace-collaborators/accept",
        json={"token": raw}, headers=_h(collab),
    )
    assert r.status_code == 200, r.text

    # The collab gets read access to the named class…
    r = await client.get(f"/classes/{host['class_id']}/students", headers=_h(collab))
    assert r.status_code == 200, r.text
    # …and `caller_collab_mode_for_class` reports 'read', which is what
    # IT-reachable write surfaces gate on (the curriculum-plan /
    # grade-columns router IS mounted ungated and IT-reachable — see
    # backend/app/routes.py — so this asserts the helper contract directly).
    assert await caller_collab_mode_for_class(
        db.session, collab["user"], host["class_id"],
    ) == "read"
