"""Smoke test for the IT §6.2c parent-invitation FE read surface.

Spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §6.2c.
Task: #206.

Covers the tiny GET surface that backs the IT student-card chip:

  * Returns ``{"invitation": null}`` when no invitation exists yet.
  * Round-trips the latest pending invitation after create.
  * Returns ``status: "cancelled"`` after the cancel endpoint runs.
  * Cross-workspace student id 404s (§8 inv. 3) before disclosing
    whether a row exists.
"""
from __future__ import annotations

import uuid

import pytest

from tests._it_fixtures import headers, mk_it_workspace, now_ts
from tests.test_independent_teacher_phase2_invitations import (
    _it_headers, _mk_pending_student,
)


@pytest.mark.asyncio
async def test_get_invitation_returns_null_when_none(client):
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    sid = await _mk_pending_student(ctx["wsid"])
    h = _it_headers(ctx)

    resp = await client.get(
        f"/independent-teacher/students/{sid}/parent-invitation", headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"invitation": None}


@pytest.mark.asyncio
async def test_get_invitation_round_trips_pending(client):
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    sid = await _mk_pending_student(ctx["wsid"])
    h = _it_headers(ctx)

    create = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent-invitation",
        json={"parent_email": "dad@example.com"}, headers=h,
    )
    assert create.status_code == 200, create.text
    inv_id = create.json()["id"]

    resp = await client.get(
        f"/independent-teacher/students/{sid}/parent-invitation", headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["invitation"]
    assert body is not None
    assert body["id"] == inv_id
    assert body["status"] == "pending"
    assert body["student_id"] == sid
    assert body["channels"] == {"email": True, "sms": False}
    # The raw token must NEVER be returned by the read endpoint — it is
    # one-shot at create-time only.
    assert "token" not in body


@pytest.mark.asyncio
async def test_get_invitation_reflects_cancellation(client):
    ctx = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    sid = await _mk_pending_student(ctx["wsid"])
    h = _it_headers(ctx)

    create = await client.post(
        f"/independent-teacher/students/{sid}/invite-parent-invitation",
        json={"parent_email": "dad@example.com"}, headers=h,
    )
    inv_id = create.json()["id"]

    cancel = await client.post(
        f"/independent-teacher/parent-invitations/{inv_id}/cancel", headers=h,
    )
    assert cancel.status_code == 200

    resp = await client.get(
        f"/independent-teacher/students/{sid}/parent-invitation", headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()["invitation"]
    assert body["id"] == inv_id
    assert body["status"] == "cancelled"


@pytest.mark.asyncio
async def test_get_invitation_cross_workspace_returns_404(client):
    ctx_a = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    ctx_b = await mk_it_workspace(with_student=False, with_parent=False, with_passkey=True)
    sid_in_a = await _mk_pending_student(ctx_a["wsid"])

    # Create the invitation under ctx_a so a row exists — the cross-
    # workspace caller must NOT learn it exists.
    await client.post(
        f"/independent-teacher/students/{sid_in_a}/invite-parent-invitation",
        json={"parent_email": "dad@example.com"}, headers=_it_headers(ctx_a),
    )

    resp = await client.get(
        f"/independent-teacher/students/{sid_in_a}/parent-invitation",
        headers=_it_headers(ctx_b),
    )
    assert resp.status_code == 404, resp.text
