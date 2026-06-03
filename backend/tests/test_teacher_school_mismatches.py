"""
Tests for the Platform-Admin teacher cross-school mismatch report
(`GET /users/teacher-school-mismatches` -> `get_teacher_school_mismatches`
in `backend/routes/user_routes_mod.py`).

The endpoint surfaces teacher users whose intended school (``users.tenant_id``)
differs from the school where their live (non-deleted) ``teachers`` record
actually lives — the teachers ``_ensure_school_teacher_record`` intentionally
BLOCKS from being moved, who therefore never appear under their intended
school's Teachers page.

Locks in:
  * A teacher with a live record ONLY in a different school is flagged, and the
    entry exposes both the intended school and the record school.
  * A teacher with a live record in the intended school is NOT flagged.
  * Soft-deleted (``deleted_at`` set) records are ignored.
  * Matching is by ``user_id`` and falls back to ``email``.
  * Non-platform-admin callers are rejected with 403.

These tests scope each read to the seeded intended school via ``school_id`` so
the response is deterministic on the shared test database (an unscoped scan sees
every teacher user, so the absolute count and paging are not deterministic).
"""
import uuid

import pytest

from dependencies import db, UserRole
from engines.sql_utils import gd_insert


async def _mk_school(name_suffix: str = "") -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid,
        "name": f"School-{name_suffix or sid[:6]}",
        "code": f"S{sid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    return sid


async def _mk_teacher_user(intended_school_id, email=None) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.TEACHER.value,
        "tenant_id": intended_school_id,
        "email": email or f"{uid}@t.test",
        "full_name": f"Teacher {uid[:6]}",
        "phone": "0500000000",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


async def _mk_teacher_record(
    school_id,
    *,
    user_id=None,
    email=None,
    deleted_at=None,
    full_name="Record",
) -> str:
    rid = str(uuid.uuid4())
    row = {
        "id": rid,
        "full_name": full_name,
        "email": email,
        "school_id": school_id,
        "user_id": user_id,
        "is_active": True,
        "deleted_at": deleted_at,
        "preferences": {},
        "constraints": {},
    }
    await gd_insert(db.session, "teachers", row)
    return rid


def _entry_for(body: dict, user_id: str):
    for m in body["mismatches"]:
        if m["user_id"] == user_id:
            return m
    return None


# ----------------------------------------------------------------------
# (1) Live record only in a DIFFERENT school -> flagged, exposing both
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_teacher_stuck_in_other_school_is_flagged_with_both_schools(
    client, platform_admin_headers
):
    intended = await _mk_school("intended")
    other = await _mk_school("other")
    user = await _mk_teacher_user(intended)
    rec_id = await _mk_teacher_record(other, user_id=user["id"])

    resp = await client.get(
        "/users/teacher-school-mismatches",
        params={"school_id": intended},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    entry = _entry_for(resp.json(), user["id"])
    assert entry is not None, "stuck teacher must appear in the report"

    assert entry["intended_school"]["id"] == intended
    assert entry["intended_school"]["name"] == f"School-intended"
    record_ids = {s["id"] for s in entry["record_schools"]}
    assert record_ids == {other}
    record_names = {s["name"] for s in entry["record_schools"]}
    assert record_names == {"School-other"}
    assert entry["teacher_record_ids"] == [rec_id]
    assert entry["email"] == user["email"]


# ----------------------------------------------------------------------
# (2) Live record in the INTENDED school -> NOT flagged
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_teacher_with_record_in_intended_school_is_not_flagged(
    client, platform_admin_headers
):
    intended = await _mk_school("intended")
    user = await _mk_teacher_user(intended)
    await _mk_teacher_record(intended, user_id=user["id"])

    resp = await client.get(
        "/users/teacher-school-mismatches",
        params={"school_id": intended},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert _entry_for(resp.json(), user["id"]) is None


@pytest.mark.asyncio
async def test_teacher_with_records_in_both_schools_is_not_flagged(
    client, platform_admin_headers
):
    """If ANY live record sits in the intended school the teacher appears
    there normally and is not stuck — even if another record exists elsewhere."""
    intended = await _mk_school("intended")
    other = await _mk_school("other")
    user = await _mk_teacher_user(intended)
    await _mk_teacher_record(intended, user_id=user["id"])
    await _mk_teacher_record(other, user_id=user["id"])

    resp = await client.get(
        "/users/teacher-school-mismatches",
        params={"school_id": intended},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert _entry_for(resp.json(), user["id"]) is None


# ----------------------------------------------------------------------
# (3) Soft-deleted records are ignored
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_soft_deleted_record_in_other_school_is_ignored(
    client, platform_admin_headers
):
    """A teacher whose ONLY record (in another school) is soft-deleted has no
    live record, so there is nothing stuck — they must NOT be flagged."""
    intended = await _mk_school("intended")
    other = await _mk_school("other")
    user = await _mk_teacher_user(intended)
    await _mk_teacher_record(
        other, user_id=user["id"], deleted_at="2026-01-01T00:00:00+00:00"
    )

    resp = await client.get(
        "/users/teacher-school-mismatches",
        params={"school_id": intended},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert _entry_for(resp.json(), user["id"]) is None


@pytest.mark.asyncio
async def test_soft_deleted_record_does_not_count_as_intended_match(
    client, platform_admin_headers
):
    """A soft-deleted record in the intended school must not 'rescue' a teacher
    whose only LIVE record is in another school — they stay flagged."""
    intended = await _mk_school("intended")
    other = await _mk_school("other")
    user = await _mk_teacher_user(intended)
    await _mk_teacher_record(
        intended, user_id=user["id"], deleted_at="2026-01-01T00:00:00+00:00"
    )
    live_id = await _mk_teacher_record(other, user_id=user["id"])

    resp = await client.get(
        "/users/teacher-school-mismatches",
        params={"school_id": intended},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    entry = _entry_for(resp.json(), user["id"])
    assert entry is not None
    assert {s["id"] for s in entry["record_schools"]} == {other}
    assert entry["teacher_record_ids"] == [live_id]


# ----------------------------------------------------------------------
# (4) Matching by user_id and fallback to email
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_match_by_user_id(client, platform_admin_headers):
    intended = await _mk_school("intended")
    other = await _mk_school("other")
    user = await _mk_teacher_user(intended)
    # Record linked ONLY by user_id (different/empty email) — still matched.
    rec_id = await _mk_teacher_record(other, user_id=user["id"], email=None)

    resp = await client.get(
        "/users/teacher-school-mismatches",
        params={"school_id": intended},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    entry = _entry_for(resp.json(), user["id"])
    assert entry is not None
    assert entry["teacher_record_ids"] == [rec_id]


@pytest.mark.asyncio
async def test_match_falls_back_to_email(client, platform_admin_headers):
    intended = await _mk_school("intended")
    other = await _mk_school("other")
    user = await _mk_teacher_user(intended)
    # Record has NO user_id link; matches purely on the canonical email.
    rec_id = await _mk_teacher_record(other, user_id=None, email=user["email"])

    resp = await client.get(
        "/users/teacher-school-mismatches",
        params={"school_id": intended},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    entry = _entry_for(resp.json(), user["id"])
    assert entry is not None
    assert entry["teacher_record_ids"] == [rec_id]


# ----------------------------------------------------------------------
# (5) Authorization — non-platform-admin callers rejected
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_teacher_caller_is_rejected_403(client, teacher_headers):
    resp = await client.get(
        "/users/teacher-school-mismatches", headers=teacher_headers
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_school_admin_caller_is_rejected_403(client, school_admin_headers):
    resp = await client.get(
        "/users/teacher-school-mismatches", headers=school_admin_headers
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_unauthenticated_caller_is_rejected(client):
    resp = await client.get("/users/teacher-school-mismatches")
    assert resp.status_code in (401, 403), resp.text


# ----------------------------------------------------------------------
# (6) Scoping + pagination keep the report responsive at scale
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_school_id_scope_excludes_other_schools_teachers(
    client, platform_admin_headers
):
    """``school_id`` scopes the scan to one intended school: a stuck teacher in a
    DIFFERENT intended school must not appear when scoping to ours."""
    intended = await _mk_school("intended")
    other_intended = await _mk_school("other-intended")
    record_school = await _mk_school("record")

    ours = await _mk_teacher_user(intended)
    await _mk_teacher_record(record_school, user_id=ours["id"])
    theirs = await _mk_teacher_user(other_intended)
    await _mk_teacher_record(record_school, user_id=theirs["id"])

    resp = await client.get(
        "/users/teacher-school-mismatches",
        params={"school_id": intended},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert _entry_for(body, ours["id"]) is not None
    assert _entry_for(body, theirs["id"]) is None


@pytest.mark.asyncio
async def test_pagination_limit_and_offset(client, platform_admin_headers):
    """Within a scoped school, ``limit``/``offset`` page the result list while
    ``total`` keeps reporting the full count."""
    intended = await _mk_school("intended")
    other = await _mk_school("other")

    created = []
    for _ in range(3):
        u = await _mk_teacher_user(intended)
        await _mk_teacher_record(other, user_id=u["id"])
        created.append(u)

    resp_full = await client.get(
        "/users/teacher-school-mismatches",
        params={"school_id": intended, "limit": 100, "offset": 0},
        headers=platform_admin_headers,
    )
    assert resp_full.status_code == 200, resp_full.text
    full = resp_full.json()
    assert full["total"] == 3
    assert full["returned"] == 3
    all_ids = [m["user_id"] for m in full["mismatches"]]

    resp_page = await client.get(
        "/users/teacher-school-mismatches",
        params={"school_id": intended, "limit": 2, "offset": 0},
        headers=platform_admin_headers,
    )
    assert resp_page.status_code == 200, resp_page.text
    page = resp_page.json()
    assert page["total"] == 3
    assert page["returned"] == 2
    assert page["limit"] == 2
    assert [m["user_id"] for m in page["mismatches"]] == all_ids[:2]

    resp_page2 = await client.get(
        "/users/teacher-school-mismatches",
        params={"school_id": intended, "limit": 2, "offset": 2},
        headers=platform_admin_headers,
    )
    assert resp_page2.status_code == 200, resp_page2.text
    page2 = resp_page2.json()
    assert page2["total"] == 3
    assert page2["returned"] == 1
    assert page2["offset"] == 2
    assert [m["user_id"] for m in page2["mismatches"]] == all_ids[2:]
