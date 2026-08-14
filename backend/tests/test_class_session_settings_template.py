"""
Tests for the class-level session-settings template endpoints
(GET/POST /class/{class_id}/session-settings on class_teaching_router).

These are the فصولي → "إعدادات الحصة" dialog's endpoints. They read/write the
SAME session_settings row (keyed {class_id, subject_id, tenant_id}) that the
live lesson hydrates from, funneling every user-controlled field through
backend/utils/session_settings.py so the two surfaces can never drift.

Covered contracts:
- School-teacher roundtrip: POST full payload → GET returns exists=True and
  the sanitized custom element definitions + toggles.
- Partial-POST no-clobber: a POST without the custom element keys (and
  without streak_bonus_enabled) must NOT wipe stored definitions — the
  "absent key = don't touch" contract.
- subject_id is required on POST (422 with a safe Arabic message).
- Teacher without class linkage → 403.
- IT ownership: an independent teacher owns classes in their itw_ workspace.
- IT cross-workspace by-id → 404, never 403/200 (§8 invariant 3).
"""
import uuid

import pytest
from fastapi import HTTPException

from dependencies import db, UserRole
from engines.sql_utils import gd_insert, gd_find_one
from src.modules.scheduling.controllers.scheduling_smart_session_routes import (
    get_class_session_settings,
    save_class_session_settings,
)


# ──────────────────── helpers ────────────────────

async def _mk_school(school_id: str, *, school_type: str = None) -> None:
    doc = {
        "id": school_id,
        "name": f"School-{school_id[:6]}",
        "code": f"S{uuid.uuid4().hex[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    }
    if school_type:
        doc["school_type"] = school_type
    await gd_insert(db.session, "schools", doc)


async def _mk_tenant() -> str:
    sid = str(uuid.uuid4())
    await _mk_school(sid)
    return sid


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


async def _mk_teacher_user(
    tenant_id: str, *, link_class_id: str = None, link_subject_id: str = None,
) -> dict:
    uid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid, "school_id": tenant_id, "full_name": "معلم اختبار",
        "is_active": True,
    })
    user = {
        "id": uid, "role": "teacher", "tenant_id": tenant_id,
        "teacher_id": tid,
        "email": f"u-{uid}@t.test", "full_name": "معلم اختبار", "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    if link_class_id:
        await gd_insert(db.session, "teacher_assignments", {
            "id": str(uuid.uuid4()),
            "class_id": link_class_id,
            "teacher_id": tid,
            "subject_id": link_subject_id,
            "school_id": tenant_id,
        })
    return user


async def _mk_it_user() -> dict:
    uid = str(uuid.uuid4())
    wsid = f"itw_{uid}"
    await _mk_school(wsid, school_type="independent_teacher")
    user = {
        "id": uid, "role": UserRole.INDEPENDENT_TEACHER.value, "tenant_id": wsid,
        "email": f"it-{uid}@t.test", "full_name": "معلم مستقل", "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


_FULL_PAYLOAD_CUSTOMS = {
    "custom_positive_behaviours": [{"id": "cp_1", "name": "مبادرة رائعة", "points": 3}],
    "custom_negative_behaviours": [{"id": "cn_1", "name": "إزعاج", "points": -4}],
    "custom_skills": [{"name": "مهارة القراءة", "points": 5}],
    "custom_evaluation_items": [
        {"id": "ev_1", "name": "نشاط إثرائي", "color": "sky", "icon": "Star", "points": 2},
    ],
    "behaviour_score_overrides": {"beh_pos_participation": 7},
}


def _full_payload(subject_id: str) -> dict:
    return {
        "subject_id": subject_id,
        "participation_enabled": True,
        "homework_enabled": False,
        "homework_view_mode": "submitted",
        "recitation_enabled": True,
        "recitation_max_attempts": 2,
        "streak_bonus_enabled": False,
        "skill_enabled": True,
        "participation_scores": {"active": 2, "initiative": 3},
        **_FULL_PAYLOAD_CUSTOMS,
    }


# ──────────────────── tests ────────────────────

@pytest.mark.asyncio
async def test_school_teacher_roundtrip():
    tenant = await _mk_tenant()
    cls = await _mk_class(tenant)
    subj = await _mk_subject(tenant)
    user = await _mk_teacher_user(tenant, link_class_id=cls, link_subject_id=subj)

    res = await save_class_session_settings(cls, _full_payload(subj), user)
    assert res["success"] is True

    got = await get_class_session_settings(cls, subj, user)
    assert got["exists"] is True
    assert got["homework_enabled"] is False
    assert got["homework_view_mode"] == "submitted"
    assert got["recitation_enabled"] is True
    assert got["recitation_max_attempts"] == 2
    assert got["streak_bonus_enabled"] is False
    assert got["skill_enabled"] is True
    assert got["participation_scores"] == {"active": 2, "initiative": 3}
    assert got["custom_positive_behaviours"] == [
        {"id": "cp_1", "name": "مبادرة رائعة", "points": 3}]
    assert got["custom_negative_behaviours"] == [
        {"id": "cn_1", "name": "إزعاج", "points": -4}]
    assert got["custom_skills"] == [{"name": "مهارة القراءة", "points": 5}]
    assert got["custom_evaluation_items"][0]["name"] == "نشاط إثرائي"
    assert got["behaviour_score_overrides"] == {"beh_pos_participation": 7}

    # The stored row is keyed exactly the way the live-lesson route keys it,
    # so the next lesson hydrates from this same template.
    row = await gd_find_one(db.session, "session_settings", {
        "class_id": cls, "subject_id": subj, "tenant_id": tenant,
    })
    assert row is not None
    assert row["custom_skills"] == [{"name": "مهارة القراءة", "points": 5}]


@pytest.mark.asyncio
async def test_partial_post_does_not_clobber_customs_or_streak():
    tenant = await _mk_tenant()
    cls = await _mk_class(tenant)
    subj = await _mk_subject(tenant)
    user = await _mk_teacher_user(tenant, link_class_id=cls, link_subject_id=subj)

    await save_class_session_settings(cls, _full_payload(subj), user)

    # Partial POST: toggles only — no custom element keys, no streak key.
    await save_class_session_settings(cls, {
        "subject_id": subj,
        "participation_enabled": False,
        "homework_enabled": True,
    }, user)

    got = await get_class_session_settings(cls, subj, user)
    assert got["participation_enabled"] is False           # updated
    assert got["homework_enabled"] is True                 # updated
    assert got["streak_bonus_enabled"] is False            # untouched (absent key)
    assert got["custom_positive_behaviours"] == [
        {"id": "cp_1", "name": "مبادرة رائعة", "points": 3}]   # untouched
    assert got["custom_skills"] == [{"name": "مهارة القراءة", "points": 5}]
    assert got["behaviour_score_overrides"] == {"beh_pos_participation": 7}


@pytest.mark.asyncio
async def test_post_requires_subject_id():
    tenant = await _mk_tenant()
    cls = await _mk_class(tenant)
    subj = await _mk_subject(tenant)
    user = await _mk_teacher_user(tenant, link_class_id=cls, link_subject_id=subj)
    with pytest.raises(HTTPException) as exc:
        await save_class_session_settings(cls, {"homework_enabled": True}, user)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_unlinked_teacher_denied():
    tenant = await _mk_tenant()
    cls = await _mk_class(tenant)
    subj = await _mk_subject(tenant)
    stranger = await _mk_teacher_user(tenant)  # same tenant, NO class linkage
    with pytest.raises(HTTPException) as exc:
        await get_class_session_settings(cls, subj, stranger)
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        await save_class_session_settings(cls, {"subject_id": subj}, stranger)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_it_owner_roundtrip():
    it = await _mk_it_user()
    wsid = it["tenant_id"]
    cls = await _mk_class(wsid)
    subj = await _mk_subject(wsid)

    res = await save_class_session_settings(cls, _full_payload(subj), it)
    assert res["success"] is True
    got = await get_class_session_settings(cls, subj, it)
    assert got["exists"] is True
    assert got["custom_skills"] == [{"name": "مهارة القراءة", "points": 5}]
    # Tenant on the stored row derives from the CLASS row (= workspace id).
    row = await gd_find_one(db.session, "session_settings", {
        "class_id": cls, "subject_id": subj, "tenant_id": wsid,
    })
    assert row is not None


@pytest.mark.asyncio
async def test_it_cross_workspace_404_never_403():
    owner = await _mk_it_user()
    intruder = await _mk_it_user()
    cls = await _mk_class(owner["tenant_id"])
    subj = await _mk_subject(owner["tenant_id"])

    with pytest.raises(HTTPException) as exc:
        await get_class_session_settings(cls, subj, intruder)
    assert exc.value.status_code == 404  # §8 inv. 3 — never 403/200

    with pytest.raises(HTTPException) as exc:
        await save_class_session_settings(
            cls, {"subject_id": subj, "homework_enabled": False}, intruder)
    assert exc.value.status_code == 404
