"""Regression coverage for the parent-edited student profile flow.

Pins the per-student `profile_settings` PUT/GET surface in
`parent_portal_routes.py` so future refactors of `_verify_parent_access`,
the catalog allowlists, or the merge logic cannot silently regress
parent-to-student isolation or accept unknown chip values.

Scenarios:
  * PUT on a linked child succeeds and persists sanitized settings.
  * PUT on a non-linked (cross-tenant) student returns 403.
  * Unknown chip values are stripped from list fields.
  * Unknown `family_situation` / `emoji` values are ignored (existing
    value retained).
  * Editing sibling A does not mutate sibling B's `profile_settings`.
  * A partial PUT (only one section) merges into the existing settings
    instead of clobbering the other sections.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find_one


async def _raw_insert_student(*, student_id: str, school_id: str,
                              parent_id: str, full_name: str = "طالب",
                              profile_settings: dict | None = None) -> None:
    await db.session.execute(
        text(
            """
            INSERT INTO students (id, school_id, full_name, parent_id, is_active, profile_settings)
            VALUES (:id, :school_id, :full_name, :parent_id, true, CAST(:ps AS JSONB))
            """
        ),
        {
            "id": student_id,
            "school_id": school_id,
            "full_name": full_name,
            "parent_id": parent_id,
            "ps": __import__("json").dumps(profile_settings or {}),
        },
    )


def _parent_headers(user_id: str, tenant_id: str) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": UserRole.PARENT.value,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _seed_parent(tenant_id: str) -> dict:
    parent_record_id = str(uuid.uuid4())
    parent_user_id = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": parent_record_id,
        "full_name": "ولي أمر",
        "email": f"p-{parent_record_id}@t.test",
        "school_id": tenant_id,
        "is_active": True,
        "student_ids": [],
    })
    await gd_insert(db.session, "users", {
        "id": parent_user_id,
        "role": UserRole.PARENT.value,
        "tenant_id": tenant_id,
        "parent_id": parent_record_id,
        "email": f"p-{parent_record_id}@t.test",
        "full_name": "ولي أمر",
        "is_active": True,
        "password_hash": "x",
    })
    return {"user_id": parent_user_id, "parent_record_id": parent_record_id}


async def _seed_child(tenant_id: str, parent_record_id: str,
                       profile_settings: dict | None = None) -> str:
    sid = str(uuid.uuid4())
    await _raw_insert_student(
        student_id=sid,
        school_id=tenant_id,
        parent_id=parent_record_id,
        profile_settings=profile_settings,
    )
    return sid


async def _read_profile_settings(student_id: str) -> dict:
    row = await gd_find_one(db.session, "students", {"id": student_id})
    return dict(row.get("profile_settings") or {})


@pytest.mark.asyncio
async def test_put_profile_succeeds_for_linked_child(client, tenant_a):
    parent = await _seed_parent(tenant_a)
    child_id = await _seed_child(tenant_a, parent["parent_record_id"])

    res = await client.put(
        f"/parent-portal/child/{child_id}/profile",
        headers=_parent_headers(parent["user_id"], tenant_a),
        json={
            "emoji": "🌟",
            "health_conditions": ["asthma", "diabetes"],
            "behavioral_aspects": ["shyness"],
            "family_situation": "both_parents",
            "family_other_situations": ["parent_traveling"],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    saved = body["profile_settings"]
    assert saved["emoji"] == "🌟"
    assert saved["health_conditions"] == ["asthma", "diabetes"]
    assert saved["behavioral_aspects"] == ["shyness"]
    assert saved["family_situation"] == "both_parents"
    assert saved["family_other_situations"] == ["parent_traveling"]

    persisted = await _read_profile_settings(child_id)
    assert persisted == saved


@pytest.mark.asyncio
async def test_put_profile_forbidden_for_non_linked_child(client, tenant_a, tenant_b):
    """A parent in tenant_a cannot edit a student that belongs to a
    different parent / different tenant — the route MUST 403."""
    parent = await _seed_parent(tenant_a)
    # Foreign student in tenant_b, owned by an unrelated parent record.
    other_parent_record = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": other_parent_record,
        "full_name": "ولي آخر",
        "email": f"p-{other_parent_record}@t.test",
        "school_id": tenant_b,
        "is_active": True,
        "student_ids": [],
    })
    foreign_child = await _seed_child(tenant_b, other_parent_record,
                                       profile_settings={"emoji": "🎯"})

    res = await client.put(
        f"/parent-portal/child/{foreign_child}/profile",
        headers=_parent_headers(parent["user_id"], tenant_a),
        json={"emoji": "🚀"},
    )
    assert res.status_code == 403

    # And the foreign child's stored settings must be untouched.
    assert (await _read_profile_settings(foreign_child)) == {"emoji": "🎯"}


@pytest.mark.asyncio
async def test_unknown_chip_values_are_rejected(client, tenant_a):
    """Values outside the per-field allowlists must be silently dropped
    so an attacker cannot persist arbitrary tag strings."""
    parent = await _seed_parent(tenant_a)
    child_id = await _seed_child(tenant_a, parent["parent_record_id"])

    res = await client.put(
        f"/parent-portal/child/{child_id}/profile",
        headers=_parent_headers(parent["user_id"], tenant_a),
        json={
            "emoji": "💀",  # not in EMOJI allowlist
            "health_conditions": ["asthma", "<script>", "made_up_tag"],
            "behavioral_aspects": ["aggression", "not_a_real_thing"],
            "family_situation": "haunted_house",  # invalid
            "family_other_situations": ["orphan", "not_real"],
        },
    )
    assert res.status_code == 200, res.text
    saved = res.json()["profile_settings"]
    # Disallowed emoji means the key is never set — default emoji remains
    # whatever it was (here: absent because the child started empty).
    assert "emoji" not in saved
    assert saved["health_conditions"] == ["asthma"]
    assert saved["behavioral_aspects"] == ["aggression"]
    # Invalid family_situation is ignored entirely (not blanked, not set).
    assert "family_situation" not in saved
    assert saved["family_other_situations"] == ["orphan"]


@pytest.mark.asyncio
async def test_editing_sibling_a_does_not_touch_sibling_b(client, tenant_a):
    """Editing one child must never mutate a sibling's `profile_settings`,
    even though both children share the same parent record."""
    parent = await _seed_parent(tenant_a)
    sibling_a = await _seed_child(tenant_a, parent["parent_record_id"])
    sibling_b_initial = {
        "emoji": "👧",
        "health_conditions": ["weak_vision"],
        "behavioral_aspects": [],
        "family_situation": "mother_only",
        "family_other_situations": [],
    }
    sibling_b = await _seed_child(tenant_a, parent["parent_record_id"],
                                   profile_settings=sibling_b_initial)

    res = await client.put(
        f"/parent-portal/child/{sibling_a}/profile",
        headers=_parent_headers(parent["user_id"], tenant_a),
        json={
            "emoji": "⚽",
            "health_conditions": ["nut_allergy"],
        },
    )
    assert res.status_code == 200, res.text

    # Sibling B's settings are exactly what they were seeded with.
    assert (await _read_profile_settings(sibling_b)) == sibling_b_initial


@pytest.mark.asyncio
async def test_partial_save_merges_instead_of_clobbering(client, tenant_a):
    """A PUT that only contains one section MUST merge into the existing
    profile_settings JSONB, preserving the untouched sections."""
    parent = await _seed_parent(tenant_a)
    initial = {
        "emoji": "📚",
        "health_conditions": ["asthma"],
        "behavioral_aspects": ["hyperactivity"],
        "family_situation": "both_parents",
        "family_other_situations": ["parent_traveling"],
    }
    child_id = await _seed_child(tenant_a, parent["parent_record_id"],
                                  profile_settings=initial)

    # Touch only `family_situation`. Every other key must remain.
    res = await client.put(
        f"/parent-portal/child/{child_id}/profile",
        headers=_parent_headers(parent["user_id"], tenant_a),
        json={"family_situation": "father_only"},
    )
    assert res.status_code == 200, res.text
    saved = res.json()["profile_settings"]
    assert saved["family_situation"] == "father_only"
    assert saved["emoji"] == "📚"
    assert saved["health_conditions"] == ["asthma"]
    assert saved["behavioral_aspects"] == ["hyperactivity"]
    assert saved["family_other_situations"] == ["parent_traveling"]

    persisted = await _read_profile_settings(child_id)
    assert persisted == saved


@pytest.mark.asyncio
async def test_get_profile_forbidden_for_non_linked_child(client, tenant_a, tenant_b):
    """GET surface must mirror PUT — a parent must not be able to read
    another family's `profile_settings`."""
    parent = await _seed_parent(tenant_a)
    other_parent_record = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": other_parent_record,
        "full_name": "ولي آخر",
        "email": f"p-{other_parent_record}@t.test",
        "school_id": tenant_b,
        "is_active": True,
        "student_ids": [],
    })
    foreign_child = await _seed_child(tenant_b, other_parent_record,
                                       profile_settings={"emoji": "🎯"})

    res = await client.get(
        f"/parent-portal/child/{foreign_child}/profile",
        headers=_parent_headers(parent["user_id"], tenant_a),
    )
    assert res.status_code == 403
