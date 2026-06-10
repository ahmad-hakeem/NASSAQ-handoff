"""
Independent-Teacher Parents directory — children-aggregation correctness
regression tests (router: ``independent_teacher_parents_routes``).

Task #850 locked the *security* contract (tenant isolation, credential
leakage, rotation atomicity). This suite locks the orthogonal
*per-parent children-aggregation* rules so a future change cannot:

  * attach one family's children to another parent's row, or
  * count children that no longer exist / were removed.

Specifically it asserts that ``list_workspace_parents`` and
``get_workspace_parent`` agree on:

  * Each parent sees EXACTLY its own active, linked children — never a
    sibling/child from a different parent's guardian_links.
  * guardian_links pointing at inactive or removed students are
    excluded from both the children list and ``children_count``.
  * Duplicate ``(parent_id, student_id)`` link pairs are de-duplicated.
  * ``portal_state`` resolves correctly (active / pending / none) across
    all three users-row resolution paths: ``parent_ref``,
    ``users.parent_id``, and the legacy ``users.email`` fallback.

Helpers mirror ``test_independent_teacher_parents_security.py``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from auth_scope import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


# ----------------------------------------------------------------------
# Fixtures / helpers (mirror test_independent_teacher_parents_security.py)
# ----------------------------------------------------------------------

# A non-sentinel, non-placeholder password hash so _portal_state reads as
# a real credential. The value never needs to verify — only its presence
# and "not the sentinel" matter for portal-state resolution.
_REAL_HASH = "$2b$12$abcdefghijklmnopqrstuvAbCdEfGhIjKlMnOpQrStUvWxYz0123"

_USER_PASSWORD_SENTINEL = "!invite-pending"
_INVALID_EMAIL_DOMAIN = "@invite.nassaq.invalid"


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


async def _mk_it() -> dict:
    """Bootstrap an IT user + workspace school."""
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
        "name": f"IT-Workspace-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher",
    })
    return user


def _it_headers(user: dict) -> dict:
    claims = {
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": independent_workspace_id(user),
    }
    token = create_access_token(claims, mfa_recent_at=_now_ts(), mfa_kind="webauthn")
    return {"Authorization": f"Bearer {token}"}


async def _mk_student(
    wsid: str,
    *,
    name: str = "طالب",
    is_active: bool = True,
    parent_id: str | None = None,
) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": wsid,
        "tenant_id": wsid,
        "full_name": name,
        "is_active": is_active,
        "parent_id": parent_id,
    })
    return sid


async def _mk_parent(
    wsid: str,
    *,
    email: str | None = None,
    name: str = "ولي أمر",
) -> tuple[str, str]:
    pid = str(uuid.uuid4())
    email = email or f"parent-{pid}@example.com"
    await gd_insert(db.session, "parents", {
        "id": pid,
        "school_id": wsid,
        "full_name": name,
        "phone": "+966500111000",
        "email": email,
        "national_id": "1029384756",
        "is_active": True,
    })
    return pid, email


async def _mk_parent_user(
    wsid: str,
    *,
    email: str,
    parent_id: str | None = None,
    is_active: bool = True,
    password_hash: str = _REAL_HASH,
) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": "parent",
        "tenant_id": wsid,
        "parent_id": parent_id,
        "email": email,
        "full_name": "ولي أمر",
        "password_hash": password_hash,
        "is_active": is_active,
        "preferred_language": "ar",
        "preferred_theme": "light",
    })
    return uid


async def _mk_link(
    wsid: str,
    *,
    parent_id: str,
    student_id: str,
    parent_ref: str | None = None,
    is_active: bool = True,
) -> str:
    lid = str(uuid.uuid4())
    await gd_insert(db.session, "guardian_links", {
        "id": lid,
        "parent_ref": parent_ref,
        "parent_id": parent_id,
        "student_id": student_id,
        "relationship": "guardian",
        "tenant_id": wsid,
        "is_active": is_active,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return lid


def _find_parent(payload: dict, parent_id: str) -> dict | None:
    for p in payload.get("parents", []):
        if p["id"] == parent_id:
            return p
    return None


# ----------------------------------------------------------------------
# (a) Each parent sees ONLY its own children — no cross-family bleed.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_children_are_scoped_per_parent_in_list(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)

    pa, _ = await _mk_parent(wsid, name="أ")
    sa = await _mk_student(wsid, name="ابن أ", parent_id=pa)
    await _mk_link(wsid, parent_id=pa, student_id=sa)

    pb, _ = await _mk_parent(wsid, name="ب")
    sb = await _mk_student(wsid, name="ابن ب", parent_id=pb)
    await _mk_link(wsid, parent_id=pb, student_id=sb)

    resp = await client.get("/independent-teacher/parents", headers=h)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    row_a = _find_parent(data, pa)
    row_b = _find_parent(data, pb)
    assert row_a is not None and row_b is not None

    assert row_a["children_count"] == 1
    assert [c["id"] for c in row_a["children"]] == [sa]
    assert sb not in [c["id"] for c in row_a["children"]]

    assert row_b["children_count"] == 1
    assert [c["id"] for c in row_b["children"]] == [sb]
    assert sa not in [c["id"] for c in row_b["children"]]


@pytest.mark.asyncio
async def test_children_are_scoped_per_parent_in_detail(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)

    pa, _ = await _mk_parent(wsid, name="أ")
    sa = await _mk_student(wsid, name="ابن أ", parent_id=pa)
    await _mk_link(wsid, parent_id=pa, student_id=sa)

    pb, _ = await _mk_parent(wsid, name="ب")
    sb = await _mk_student(wsid, name="ابن ب", parent_id=pb)
    await _mk_link(wsid, parent_id=pb, student_id=sb)

    resp = await client.get(f"/independent-teacher/parents/{pa}", headers=h)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == pa
    assert data["children_count"] == 1
    assert [c["id"] for c in data["children"]] == [sa]
    assert sb not in [c["id"] for c in data["children"]]


# ----------------------------------------------------------------------
# (b) Inactive / removed students are excluded from list + count.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_inactive_and_removed_students_excluded_in_list(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)

    pid, _ = await _mk_parent(wsid)
    live = await _mk_student(wsid, name="حي", parent_id=pid)
    inactive = await _mk_student(wsid, name="موقوف", is_active=False, parent_id=pid)
    removed = str(uuid.uuid4())  # link points at a student row that never exists

    await _mk_link(wsid, parent_id=pid, student_id=live)
    await _mk_link(wsid, parent_id=pid, student_id=inactive)
    await _mk_link(wsid, parent_id=pid, student_id=removed)

    resp = await client.get("/independent-teacher/parents", headers=h)
    assert resp.status_code == 200, resp.text
    row = _find_parent(resp.json(), pid)
    assert row is not None
    assert row["children_count"] == 1
    child_ids = [c["id"] for c in row["children"]]
    assert child_ids == [live]
    assert inactive not in child_ids
    assert removed not in child_ids


@pytest.mark.asyncio
async def test_inactive_and_removed_students_excluded_in_detail(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)

    pid, _ = await _mk_parent(wsid)
    live = await _mk_student(wsid, name="حي", parent_id=pid)
    inactive = await _mk_student(wsid, name="موقوف", is_active=False, parent_id=pid)
    removed = str(uuid.uuid4())

    await _mk_link(wsid, parent_id=pid, student_id=live)
    await _mk_link(wsid, parent_id=pid, student_id=inactive)
    await _mk_link(wsid, parent_id=pid, student_id=removed)

    resp = await client.get(f"/independent-teacher/parents/{pid}", headers=h)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["children_count"] == 1
    child_ids = [c["id"] for c in data["children"]]
    assert child_ids == [live]
    assert inactive not in child_ids
    assert removed not in child_ids


# ----------------------------------------------------------------------
# (c) Duplicate (parent_id, student_id) link pairs are de-duplicated.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_duplicate_link_pairs_deduped_in_list(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)

    pid, _ = await _mk_parent(wsid)
    sid = await _mk_student(wsid, parent_id=pid)
    # Two active links for the same (parent, student) pair.
    await _mk_link(wsid, parent_id=pid, student_id=sid)
    await _mk_link(wsid, parent_id=pid, student_id=sid)

    resp = await client.get("/independent-teacher/parents", headers=h)
    assert resp.status_code == 200, resp.text
    row = _find_parent(resp.json(), pid)
    assert row is not None
    assert row["children_count"] == 1
    assert [c["id"] for c in row["children"]] == [sid]


@pytest.mark.asyncio
async def test_duplicate_link_pairs_deduped_in_detail(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)

    pid, _ = await _mk_parent(wsid)
    sid = await _mk_student(wsid, parent_id=pid)
    await _mk_link(wsid, parent_id=pid, student_id=sid)
    await _mk_link(wsid, parent_id=pid, student_id=sid)

    resp = await client.get(f"/independent-teacher/parents/{pid}", headers=h)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["children_count"] == 1
    assert [c["id"] for c in data["children"]] == [sid]


# ----------------------------------------------------------------------
# (d) portal_state resolution across the three users-row lookup paths.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_portal_state_none_when_no_users_row(client):
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)

    pid, _ = await _mk_parent(wsid)
    sid = await _mk_student(wsid, parent_id=pid)
    await _mk_link(wsid, parent_id=pid, student_id=sid)
    # No portal users row at all.

    resp = await client.get("/independent-teacher/parents", headers=h)
    row = _find_parent(resp.json(), pid)
    assert row is not None
    assert row["has_login_account"] is False
    assert row["portal_state"] == "none"
    assert row["user_id"] is None

    detail = await client.get(f"/independent-teacher/parents/{pid}", headers=h)
    acct = detail.json()["user_account"]
    assert acct["has_login_account"] is False
    assert acct["portal_state"] == "none"


@pytest.mark.asyncio
async def test_portal_state_active_via_parent_ref_path(client):
    """Resolvable ONLY by guardian_links.parent_ref (users row has a
    different email and no parent_id back-pointer)."""
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)

    pid, parent_email = await _mk_parent(wsid)
    sid = await _mk_student(wsid, parent_id=pid)
    # users row reachable only via parent_ref: parent_id=None, email differs.
    portal_uid = await _mk_parent_user(
        wsid, email="distinct-login@example.com", parent_id=None, is_active=True,
    )
    await _mk_link(wsid, parent_id=pid, student_id=sid, parent_ref=portal_uid)

    row = _find_parent(
        (await client.get("/independent-teacher/parents", headers=h)).json(), pid
    )
    assert row is not None
    assert row["user_id"] == portal_uid
    assert row["has_login_account"] is True
    assert row["portal_state"] == "active"

    detail = (await client.get(f"/independent-teacher/parents/{pid}", headers=h)).json()
    acct = detail["user_account"]
    assert acct["user_id"] == portal_uid
    assert acct["portal_state"] == "active"


@pytest.mark.asyncio
async def test_portal_state_active_via_parent_id_path(client):
    """Resolvable via users.parent_id (no parent_ref on link, email
    differs from the parent profile email)."""
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)

    pid, _ = await _mk_parent(wsid)
    sid = await _mk_student(wsid, parent_id=pid)
    portal_uid = await _mk_parent_user(
        wsid, email="other-login@example.com", parent_id=pid, is_active=True,
    )
    await _mk_link(wsid, parent_id=pid, student_id=sid, parent_ref=None)

    row = _find_parent(
        (await client.get("/independent-teacher/parents", headers=h)).json(), pid
    )
    assert row is not None
    assert row["user_id"] == portal_uid
    assert row["portal_state"] == "active"

    detail = (await client.get(f"/independent-teacher/parents/{pid}", headers=h)).json()
    assert detail["user_account"]["user_id"] == portal_uid
    assert detail["user_account"]["portal_state"] == "active"


@pytest.mark.asyncio
async def test_portal_state_pending_via_email_fallback_path(client):
    """Resolvable ONLY by the legacy users.email == parent.email fallback
    (no parent_ref, users.parent_id mismatched). Inactive account → the
    state must read as 'pending'."""
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)

    pid, parent_email = await _mk_parent(wsid)
    sid = await _mk_student(wsid, parent_id=pid)
    # parent_id=None so only the email fallback can reach it; inactive →
    # pending.
    portal_uid = await _mk_parent_user(
        wsid, email=parent_email, parent_id=None, is_active=False,
    )
    await _mk_link(wsid, parent_id=pid, student_id=sid, parent_ref=None)

    row = _find_parent(
        (await client.get("/independent-teacher/parents", headers=h)).json(), pid
    )
    assert row is not None
    assert row["user_id"] == portal_uid
    assert row["has_login_account"] is True
    assert row["portal_state"] == "pending"

    detail = (await client.get(f"/independent-teacher/parents/{pid}", headers=h)).json()
    acct = detail["user_account"]
    assert acct["user_id"] == portal_uid
    assert acct["portal_state"] == "pending"


@pytest.mark.asyncio
async def test_portal_state_pending_when_password_is_sentinel(client):
    """An active row whose password is still the invite sentinel must read
    as 'pending', not 'active'."""
    user = await _mk_it()
    wsid = independent_workspace_id(user)
    h = _it_headers(user)

    pid, _ = await _mk_parent(wsid)
    sid = await _mk_student(wsid, parent_id=pid)
    portal_uid = await _mk_parent_user(
        wsid, email="sentinel-login@example.com", parent_id=pid,
        is_active=True, password_hash=_USER_PASSWORD_SENTINEL,
    )
    await _mk_link(wsid, parent_id=pid, student_id=sid, parent_ref=None)

    row = _find_parent(
        (await client.get("/independent-teacher/parents", headers=h)).json(), pid
    )
    assert row is not None
    assert row["user_id"] == portal_uid
    assert row["portal_state"] == "pending"
