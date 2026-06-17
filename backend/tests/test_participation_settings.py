"""
Task #964 — Backend unit tests for participation settings tenant scoping
and server-side max enforcement.

Invariants covered:
(a) Settings saved with the correct tenant_id are returned on GET for that
    tenant — the stored record contains tenant_id and the GET lookup is scoped.
(b) A second tenant's GET returns that tenant's own settings (not the first
    tenant's) — cross-tenant isolation.
(c) An out-of-range participation_scores value (exceeds tenant_participation_max)
    returns HTTP 422 with an Arabic error message.
(d) An in-range value is accepted and stored.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_find_one, gd_insert


async def _mk_user(tenant_id: str, role: str = "teacher") -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": role,
        "tenant_id": tenant_id,
        "email": f"u-{uid}@test.test",
        "full_name": "معلم",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


def _auth_headers(user: dict) -> dict:
    token = create_access_token({
        "sub": user["id"],
        "role": user["role"],
        "tenant_id": user["tenant_id"],
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_class(tenant_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": tenant_id, "tenant_id": tenant_id, "name": "1A",
    })
    return cid


async def _mk_subject(tenant_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid, "school_id": tenant_id, "tenant_id": tenant_id,
        "name": "الرياضيات", "name_ar": "الرياضيات",
    })
    return sid


async def _mk_session(tenant_id: str, class_id: str, subject_id: str,
                      teacher_id: str) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "school_id": tenant_id,
        "tenant_id": tenant_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "teacher_id": teacher_id,
        "date": "2026-06-15",
        "status": "in_progress",
        "start_time": now,
        "created_at": now,
    })
    return session_id


@pytest.mark.asyncio
async def test_settings_saved_with_tenant_id_returned_on_get(client, tenant_a):
    """(a) Settings saved under tenant A are returned correctly on GET."""
    user = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, user["id"])
    headers = _auth_headers(user)

    payload = {
        "subject_id": subject_id,
        "participation_enabled": True,
        "participation_scores": {"active": 3, "initiative": 5},
    }
    post_res = await client.post(f"/session/{session_id}/settings", json=payload, headers=headers)
    assert post_res.status_code == 200, post_res.text
    data = post_res.json()
    assert data["participation_scores"].get("active") == 3
    assert data.get("tenant_id") == tenant_a

    get_res = await client.get(f"/session/{session_id}/settings", headers=headers)
    assert get_res.status_code == 200, get_res.text
    get_data = get_res.json()
    assert get_data["participation_scores"].get("active") == 3
    assert get_data["participation_scores"].get("initiative") == 5

    stored = await gd_find_one(db.session, "session_settings",
                               {"class_id": class_id, "subject_id": subject_id, "tenant_id": tenant_a})
    assert stored is not None, "stored record must have tenant_id scoped"
    assert stored.get("tenant_id") == tenant_a


@pytest.mark.asyncio
async def test_cross_tenant_get_returns_own_settings(client, tenant_a, tenant_b):
    """(b) Tenant B's GET returns its own settings, not tenant A's."""
    user_a = await _mk_user(tenant_a)
    class_a = await _mk_class(tenant_a)
    subject_a = await _mk_subject(tenant_a)
    session_a = await _mk_session(tenant_a, class_a, subject_a, user_a["id"])
    headers_a = _auth_headers(user_a)

    user_b = await _mk_user(tenant_b)
    class_b = await _mk_class(tenant_b)
    subject_b = await _mk_subject(tenant_b)
    session_b = await _mk_session(tenant_b, class_b, subject_b, user_b["id"])
    headers_b = _auth_headers(user_b)

    await client.post(f"/session/{session_a}/settings", headers=headers_a, json={
        "subject_id": subject_a,
        "participation_scores": {"active": 7},
    })
    await client.post(f"/session/{session_b}/settings", headers=headers_b, json={
        "subject_id": subject_b,
        "participation_scores": {"active": 2},
    })

    res_b = await client.get(f"/session/{session_b}/settings", headers=headers_b)
    assert res_b.status_code == 200, res_b.text
    assert res_b.json()["participation_scores"].get("active") == 2, (
        "Tenant B must see its own score (2), not tenant A's (7)"
    )

    res_a = await client.get(f"/session/{session_a}/settings", headers=headers_a)
    assert res_a.status_code == 200, res_a.text
    assert res_a.json()["participation_scores"].get("active") == 7, (
        "Tenant A must see its own score (7)"
    )


@pytest.mark.asyncio
async def test_cross_tenant_same_class_and_subject_isolated(client, tenant_a, tenant_b):
    """
    (b-regression) Two tenants share the same class_id and subject_id strings.
    Without tenant_id scoping, tenant B's GET would return tenant A's settings.
    This test proves the specific regression scenario that motivated tenant scoping.
    """
    # Create ONE class record (FK anchor) and ONE subject record — both under
    # tenant_a — then have BOTH tenants' sessions reference the same IDs.
    # This is the exact scenario where a lookup keyed only by (class_id, subject_id)
    # would silently return the wrong tenant's data.
    shared_class = await _mk_class(tenant_a)
    shared_subject = await _mk_subject(tenant_a)

    user_a = await _mk_user(tenant_a)
    user_b = await _mk_user(tenant_b)
    headers_a = _auth_headers(user_a)
    headers_b = _auth_headers(user_b)

    # Both sessions reference the SAME class_id + subject_id strings.
    session_a = await _mk_session(tenant_a, shared_class, shared_subject, user_a["id"])
    session_b = await _mk_session(tenant_b, shared_class, shared_subject, user_b["id"])

    # Tenant A saves score 7, tenant B saves score 2 — for the same identifiers.
    await client.post(f"/session/{session_a}/settings", headers=headers_a, json={
        "subject_id": shared_subject,
        "participation_scores": {"active": 7},
    })
    await client.post(f"/session/{session_b}/settings", headers=headers_b, json={
        "subject_id": shared_subject,
        "participation_scores": {"active": 2},
    })

    # Without tenant_id scoping: tenant B would wrongly see score=7 (tenant A's data).
    # With correct scoping: tenant B sees its own score=2.
    res_b = await client.get(f"/session/{session_b}/settings", headers=headers_b)
    assert res_b.status_code == 200, res_b.text
    assert res_b.json()["participation_scores"].get("active") == 2, (
        "Tenant B must see its own score (2) even though class_id and subject_id match tenant A's"
    )

    # Tenant A must still see its own score=7 (not corrupted by tenant B's write).
    res_a = await client.get(f"/session/{session_a}/settings", headers=headers_a)
    assert res_a.status_code == 200, res_a.text
    assert res_a.json()["participation_scores"].get("active") == 7, (
        "Tenant A must still see its own score (7)"
    )


@pytest.mark.asyncio
async def test_out_of_range_value_rejected_with_422(client, tenant_a):
    """(c) A participation_scores value exceeding the tenant max is rejected with 422."""
    user = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, user["id"])
    headers = _auth_headers(user)

    await gd_insert(db.session, "tenant_settings", {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_a,
        "setting_key": "participation_max",
        "value": 4,
    })

    res = await client.post(f"/session/{session_id}/settings", headers=headers, json={
        "subject_id": subject_id,
        "participation_scores": {"active": 5},
    })
    assert res.status_code == 422, res.text
    body = res.json()
    msg = body.get("error", {}).get("message", "") or body.get("detail", "") or ""
    assert "5" in msg or "4" in msg, f"Arabic error should mention values; got body: {body}"
    assert any(c > "\u0600" for c in msg), "Error message must contain Arabic text"


@pytest.mark.asyncio
async def test_in_range_value_accepted(client, tenant_a):
    """(d) A participation_scores value within the tenant max is accepted."""
    user = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, user["id"])
    headers = _auth_headers(user)

    await gd_insert(db.session, "tenant_settings", {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_a,
        "setting_key": "participation_max",
        "value": 10,
    })

    res = await client.post(f"/session/{session_id}/settings", headers=headers, json={
        "subject_id": subject_id,
        "participation_scores": {"active": 8, "initiative": 10},
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["participation_scores"]["active"] == 8
    assert data["participation_scores"]["initiative"] == 10


@pytest.mark.asyncio
async def test_in_range_value_at_exact_max_accepted(client, tenant_a):
    """Edge: value exactly equal to tenant max is accepted (boundary inclusive)."""
    user = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, user["id"])
    headers = _auth_headers(user)

    await gd_insert(db.session, "tenant_settings", {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_a,
        "setting_key": "participation_max",
        "value": 6,
    })

    res = await client.post(f"/session/{session_id}/settings", headers=headers, json={
        "subject_id": subject_id,
        "participation_scores": {"active": 6},
    })
    assert res.status_code == 200, res.text
    assert res.json()["participation_scores"]["active"] == 6


@pytest.mark.asyncio
async def test_value_exceeds_default_max_rejected(client, tenant_a):
    """When no tenant max is configured, the default 100 cap is enforced (> 100 → rejected)."""
    user = await _mk_user(tenant_a)
    class_id = await _mk_class(tenant_a)
    subject_id = await _mk_subject(tenant_a)
    session_id = await _mk_session(tenant_a, class_id, subject_id, user["id"])
    headers = _auth_headers(user)

    res = await client.post(f"/session/{session_id}/settings", headers=headers, json={
        "subject_id": subject_id,
        "participation_scores": {"active": 101},
    })
    assert res.status_code == 422, res.text
