"""
Regression tests for editing a skill type's score weight (وزن الدرجة) via
PUT /skills-types/{skill_id}.

Invariants covered:
- A school-scoped caller (teacher/principal) editing a *global* predefined
  skill does NOT mutate the global row — instead their school gets its own copy
  carrying the new weight, and GET /skills-types shadows the global with that
  copy so the UI shows a single chip.
- Editing the same global skill again updates the existing school copy (matched
  by name) rather than inserting a second copy.
- A skill already owned by the caller's school is updated in place.
- A PLATFORM_ADMIN may edit a global row in place (they own global scope).
- Editing a skill owned by another tenant returns 404 (never 403/200) so the
  API does not confirm the existence of a foreign-tenant row.
- An Independent-Teacher caller without fresh MFA gets the step-up envelope as
  HTTP 403 (§5.7 durable write).
- Invalid weights (non-numeric, <=0, >100) are rejected with a safe 400.
- A school copy carrying an edited weight can be recorded in a live session.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_find, gd_find_one, gd_insert


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

async def _mk_user(role: str, tenant_id: str) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": role, "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test", "full_name": "مستخدم", "is_active": True,
        "password_hash": "x",
    })
    return uid


def _headers(user_id: str, role: str, tenant_id: str) -> dict:
    token = create_access_token({
        "sub": user_id, "role": role, "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_global_skill() -> dict:
    """Insert a *global* predefined skill (school_id NULL, no weight) and
    return it. Names are uuid-tagged so runs against a shared DB never
    collide with real seed rows or each other."""
    tag = str(uuid.uuid4())[:8]
    skill = {
        "id": f"skill-{tag}",
        "name_ar": f"مهارة عامة {tag}",
        "name_en": f"Global Skill {tag}",
        "category": "general",
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "skills_types", skill)
    return skill


async def _mk_class(tenant_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": tenant_id, "tenant_id": tenant_id, "name": "1A",
    })
    return cid


async def _mk_student(tenant_id: str, class_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "tenant_id": tenant_id, "school_id": tenant_id,
        "class_id": class_id, "full_name": "طالب", "is_active": True,
    })
    return sid


async def _mk_session(tenant_id: str, class_id: str, teacher_id: str) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "school_id": tenant_id,
        "tenant_id": tenant_id,
        "class_id": class_id,
        "date": "2026-06-16",
        "status": "in_progress",
        "start_time": now,
        "teacher_id": teacher_id,
        "attendance_approved": True,
        "created_at": now,
    })
    return session_id


# ─────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_teacher_edit_global_skill_creates_school_copy(client, tenant_a):
    """A teacher editing a global skill's weight gets a school-scoped copy;
    the global row is left untouched and GET shadows it with the copy."""
    teacher_id = await _mk_user("teacher", tenant_a)
    hdrs = _headers(teacher_id, "teacher", tenant_a)
    g = await _mk_global_skill()

    resp = await client.put(f"/skills-types/{g['id']}", json={"points": 7}, headers=hdrs)
    assert resp.status_code == 200, resp.text
    skill = resp.json()["skill"]
    assert skill["points"] == 7
    assert skill["school_id"] == tenant_a
    assert skill["id"] != g["id"], "a school copy must be created, not the global row"

    # Global row is unchanged (still no weight).
    global_row = await gd_find_one(db.session, "skills_types", {"id": g["id"]})
    assert global_row is not None
    assert not global_row.get("school_id")
    assert global_row.get("points") in (None, 0)

    # GET shadows the global with the school copy: exactly one entry with that
    # name, carrying the edited weight, and the raw global id is not present.
    listing = await client.get("/skills-types", headers=hdrs)
    assert listing.status_code == 200, listing.text
    rows = listing.json()
    assert g["id"] not in {s["id"] for s in rows}
    same_name = [s for s in rows if (s.get("name_ar") or "").strip() == g["name_ar"]]
    assert len(same_name) == 1, same_name
    assert same_name[0]["points"] == 7
    assert same_name[0]["school_id"] == tenant_a


@pytest.mark.asyncio
async def test_second_edit_updates_same_copy(client, tenant_a):
    """Editing the same global skill twice updates the one school copy rather
    than inserting a second copy."""
    teacher_id = await _mk_user("teacher", tenant_a)
    hdrs = _headers(teacher_id, "teacher", tenant_a)
    g = await _mk_global_skill()

    r1 = await client.put(f"/skills-types/{g['id']}", json={"points": 7}, headers=hdrs)
    assert r1.status_code == 200, r1.text
    r2 = await client.put(f"/skills-types/{g['id']}", json={"points": 9}, headers=hdrs)
    assert r2.status_code == 200, r2.text
    assert r2.json()["skill"]["points"] == 9

    copies = [
        s for s in await gd_find(db.session, "skills_types", {"school_id": tenant_a})
        if (s.get("name_ar") or "").strip() == g["name_ar"]
    ]
    assert len(copies) == 1, f"expected exactly one school copy, got {copies}"
    assert copies[0]["points"] == 9


@pytest.mark.asyncio
async def test_school_owned_skill_updated_in_place(client, tenant_a):
    """A skill already owned by the caller's school is updated in place."""
    teacher_id = await _mk_user("teacher", tenant_a)
    hdrs = _headers(teacher_id, "teacher", tenant_a)

    created = await client.post(
        "/skills-types",
        json={"name": "Owned", "name_ar": "مملوكة", "points": 4},
        headers=hdrs,
    )
    assert created.status_code == 200, created.text
    sid = created.json()["skill"]["id"]

    resp = await client.put(f"/skills-types/{sid}", json={"points": 6}, headers=hdrs)
    assert resp.status_code == 200, resp.text
    assert resp.json()["skill"]["id"] == sid, "must update in place, not clone"
    assert resp.json()["skill"]["points"] == 6

    row = await gd_find_one(db.session, "skills_types", {"id": sid})
    assert row["points"] == 6


@pytest.mark.asyncio
async def test_platform_admin_edits_global_in_place(client, tenant_a):
    """A PLATFORM_ADMIN owns the global scope and edits a global row in place."""
    admin_id = await _mk_user("platform_admin", tenant_a)
    hdrs = _headers(admin_id, "platform_admin", tenant_a)
    g = await _mk_global_skill()

    resp = await client.put(f"/skills-types/{g['id']}", json={"points": 5}, headers=hdrs)
    assert resp.status_code == 200, resp.text
    assert resp.json()["skill"]["id"] == g["id"], "platform admin edits the global row itself"

    row = await gd_find_one(db.session, "skills_types", {"id": g["id"]})
    assert row["points"] == 5
    assert not row.get("school_id"), "the row must stay global"


@pytest.mark.asyncio
async def test_cross_tenant_put_by_id_returns_404(client, tenant_a, tenant_b):
    """Editing a skill owned by another tenant returns 404 (not 403/200)."""
    teacher_a = await _mk_user("teacher", tenant_a)
    hdrs_a = _headers(teacher_a, "teacher", tenant_a)
    created = await client.post(
        "/skills-types",
        json={"name": "A only", "name_ar": "خاصة بأ", "points": 3},
        headers=hdrs_a,
    )
    assert created.status_code == 200, created.text
    sid = created.json()["skill"]["id"]

    teacher_b = await _mk_user("teacher", tenant_b)
    hdrs_b = _headers(teacher_b, "teacher", tenant_b)
    resp = await client.put(f"/skills-types/{sid}", json={"points": 8}, headers=hdrs_b)
    assert resp.status_code == 404, (
        f"Expected 404 for cross-tenant edit; got {resp.status_code}: {resp.text}"
    )
    # The victim's row must be untouched.
    row = await gd_find_one(db.session, "skills_types", {"id": sid})
    assert row["points"] == 3


@pytest.mark.asyncio
async def test_independent_teacher_step_up_and_copy_scoping(client):
    """An Independent-Teacher edit is gated by the §5.7 step-up envelope (HTTP
    403) so the FE axios interceptor replays after passkey assertion. When the
    ``MFA_ENFORCEMENT_DISABLED`` kill-switch is active the gate is bypassed —
    in that case the edit must still produce a copy scoped to the IT workspace
    (never mutating the shared global row)."""
    from services.mfa_policy import is_enforcement_disabled

    uid = str(uuid.uuid4())
    itw = f"itw_{uid}"
    # The IT workspace is backed by a schools row (school_type=independent_teacher)
    # so the users.tenant_id FK resolves.
    await gd_insert(db.session, "schools", {
        "id": itw, "name": "IT Workspace", "code": f"IT{uid[:8]}",
        "status": "active", "country": "SA", "language": "ar",
        "school_type": "independent_teacher",
    })
    await gd_insert(db.session, "users", {
        "id": uid, "role": "independent_teacher", "tenant_id": itw,
        "email": f"it-{uid}@t.test", "full_name": "معلم مستقل", "is_active": True,
        "password_hash": "x",
    })
    hdrs = _headers(uid, "independent_teacher", itw)
    g = await _mk_global_skill()

    resp = await client.put(f"/skills-types/{g['id']}", json={"points": 5}, headers=hdrs)
    if is_enforcement_disabled():
        # Kill-switch active: gate bypassed, but the IT copy-on-edit path must
        # still scope the new copy to the IT workspace and leave the global row
        # untouched.
        assert resp.status_code == 200, resp.text
        skill = resp.json()["skill"]
        assert skill["school_id"] == itw
        assert skill["id"] != g["id"]
        global_row = await gd_find_one(db.session, "skills_types", {"id": g["id"]})
        assert not global_row.get("school_id")
        assert global_row.get("points") in (None, 0)
    else:
        assert resp.status_code == 403, (
            f"Expected 403 step-up for IT; got {resp.status_code}: {resp.text}"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [0, -3, 101, "abc", None])
async def test_invalid_weight_rejected(client, tenant_a, bad):
    """Non-numeric / non-positive / out-of-range weights are rejected (400)."""
    teacher_id = await _mk_user("teacher", tenant_a)
    hdrs = _headers(teacher_id, "teacher", tenant_a)
    g = await _mk_global_skill()

    resp = await client.put(f"/skills-types/{g['id']}", json={"points": bad}, headers=hdrs)
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_recorded_copy_uses_edited_weight(client, tenant_a):
    """A school copy carrying an edited weight can be recorded in a live
    session using the copy's id (the value the refreshed FE sends)."""
    teacher_id = await _mk_user("teacher", tenant_a)
    hdrs = _headers(teacher_id, "teacher", tenant_a)
    g = await _mk_global_skill()

    edit = await client.put(f"/skills-types/{g['id']}", json={"points": 8}, headers=hdrs)
    assert edit.status_code == 200, edit.text
    copy_id = edit.json()["skill"]["id"]

    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(tenant_a, class_id)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)

    rec = await client.post(
        f"/session/{session_id}/skill",
        json={"student_id": student_id, "skill_type_id": copy_id},
        headers=hdrs,
    )
    assert rec.status_code == 200, rec.text

    copy_row = await gd_find_one(db.session, "skills_types", {"id": copy_id})
    assert copy_row["points"] == 8
