"""In-session student health visibility (health + behavioral, NO family).

Spec: docs/superpowers/specs/2026-07-20-in-session-student-health-visibility-design.md

Two authoritative JSONB sources on the students row are merged for the
teacher-facing in-session view:
  - students.health_info        (admin/wizard-written medical record)
  - students.profile_settings   (parent-portal "ملف الطالب" chips + free text)

Surfaces under test:
  1. utils/student_health.py helpers (merge + coercion + privacy exclusions)
  2. GET /session/{sid}/students — roster now carries compact health flags
  3. GET /session/{sid}/students/{stid}/health — fresh read-only detail,
     guarded by _verify_session_owner + student-in-session-class check.
"""
import json
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_insert


# ────────────────────────── fixtures / builders ──────────────────────────

async def _mk_teacher(tenant_id: str, role: str = "teacher"):
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": role, "tenant_id": tenant_id if role == "teacher" else None,
        "email": f"u-{uid}@t.test", "full_name": "معلم اختبار", "is_active": True,
        "password_hash": "x",
    })
    claims = {"sub": uid, "role": role}
    if role == "teacher":
        claims["tenant_id"] = tenant_id
    elif role == "independent_teacher":
        # The workspace gate (auth_scope.require_workspace_materialised) 409s
        # any IT access token without the materialised-workspace claim.
        claims["tenant_id"] = f"itw_{uid}"
    return uid, {"Authorization": f"Bearer {create_access_token(claims)}"}


async def _mk_class(tenant_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": tenant_id, "tenant_id": tenant_id, "name": "1A",
    })
    return cid


async def _mk_student(tenant_id: str, class_id: str, *, health_info=None,
                      profile_settings=None, is_active=True) -> str:
    sid = str(uuid.uuid4())
    row = {
        "id": sid, "tenant_id": tenant_id, "school_id": tenant_id,
        "class_id": class_id, "full_name": "طالب اختبار", "is_active": is_active,
    }
    if health_info is not None:
        row["health_info"] = health_info
    if profile_settings is not None:
        row["profile_settings"] = profile_settings
    await gd_insert(db.session, "students", row)
    return sid


async def _mk_session(tenant_id: str, class_id: str, teacher_id: str) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id, "school_id": tenant_id, "tenant_id": tenant_id,
        "class_id": class_id, "date": "2026-07-20", "status": "in_progress",
        "start_time": now, "teacher_id": teacher_id, "created_at": now,
    })
    return session_id


FULL_PROFILE = {
    "emoji": "👦",
    "health_conditions": ["nut_allergy", "asthma"],
    "other_health_details": "يستخدم بخاخ عند الحاجة",
    "behavioral_aspects": ["hyperactivity", "speech_difficulty"],
    "other_behavior_details": "يحتاج جلوس أمامي",
    "family_situation": "other",
    "family_other_situations": ["parents_separation"],
}

FULL_HEALTH_INFO = {
    "blood_type": "O+",
    "has_chronic_conditions": True, "chronic_conditions": "سكري النوع الأول",
    "has_allergies": True, "allergies": "حساسية بنسلين",
    "has_disabilities": False, "disabilities": "قديم يجب ألا يظهر",
    "current_medications": "أنسولين",
    "requires_special_care": True, "special_care_notes": "مراقبة سكر الدم",
    "emergency_medical_notes": "اتصال فوري بالعيادة عند الهبوط",
}


# ───────────────────────────── helper units ─────────────────────────────

def test_summarize_merges_both_sources_and_sets_flags():
    from src.common.utils.student_health import summarize_student_health
    s = summarize_student_health({
        "profile_settings": FULL_PROFILE, "health_info": FULL_HEALTH_INFO,
    })
    assert s["health_conditions"] == ["nut_allergy", "asthma"]
    assert s["behavioral_aspects"] == ["hyperactivity", "speech_difficulty"]
    assert s["has_health_alert"] is True
    assert s["has_behavior_alert"] is True


def test_summarize_healthy_student_has_no_alerts():
    from src.common.utils.student_health import summarize_student_health
    for row in ({}, {"profile_settings": None, "health_info": None},
                {"profile_settings": {"emoji": "👧", "family_situation": "both_parents"}}):
        s = summarize_student_health(row)
        assert s["health_conditions"] == []
        assert s["behavioral_aspects"] == []
        assert s["has_health_alert"] is False
        assert s["has_behavior_alert"] is False


def test_summarize_medical_record_only_still_alerts():
    """A student whose data was entered only by an admin (health_info, no
    parent chips) must still get the roster alert flag."""
    from src.common.utils.student_health import summarize_student_health
    s = summarize_student_health({"health_info": {"has_allergies": True, "allergies": "لقاح"}})
    assert s["health_conditions"] == []
    assert s["has_health_alert"] is True
    assert s["has_behavior_alert"] is False


def test_summarize_coerces_malformed_values():
    from src.common.utils.student_health import summarize_student_health
    s = summarize_student_health({
        "profile_settings": {
            "health_conditions": "asthma",          # str, not list
            "behavioral_aspects": [1, None, "anger", ""],
            "other_health_details": 42,              # not a str
        },
        "health_info": "not-a-dict",
    })
    assert s["health_conditions"] == []
    assert s["behavioral_aspects"] == ["anger"]
    assert s["has_behavior_alert"] is True


def test_detail_gates_flagged_pairs_and_excludes_family():
    from src.common.utils.student_health import build_student_health_detail
    d = build_student_health_detail({
        "profile_settings": FULL_PROFILE, "health_info": FULL_HEALTH_INFO,
    })
    assert d["has_any"] is True
    h = d["health"]
    assert h["conditions"] == ["nut_allergy", "asthma"]
    assert h["other_details"] == "يستخدم بخاخ عند الحاجة"
    assert h["blood_type"] == "O+"
    assert h["chronic_conditions"] == "سكري النوع الأول"
    assert h["allergies"] == "حساسية بنسلين"
    # flag is False -> stale text must NOT appear
    assert h.get("disabilities") in (None, "")
    assert h["current_medications"] == "أنسولين"
    assert h["special_care_notes"] == "مراقبة سكر الدم"
    assert h["emergency_medical_notes"] == "اتصال فوري بالعيادة عند الهبوط"
    b = d["behavior"]
    assert b["aspects"] == ["hyperactivity", "speech_difficulty"]
    assert b["other_details"] == "يحتاج جلوس أمامي"
    # privacy: family/emoji never leave the helper
    blob = json.dumps(d, ensure_ascii=False)
    assert "family" not in blob
    assert "emoji" not in blob
    assert "👦" not in blob


def test_detail_empty_for_healthy_student():
    from src.common.utils.student_health import build_student_health_detail
    d = build_student_health_detail({})
    assert d["has_any"] is False
    assert d["health"]["conditions"] == []
    assert d["behavior"]["aspects"] == []


# ───────────────────────────── roster flags ─────────────────────────────

@pytest.mark.asyncio
async def test_roster_includes_health_flags(client, tenant_a):
    teacher_id, headers = await _mk_teacher(tenant_a)
    class_id = await _mk_class(tenant_a)
    flagged = await _mk_student(tenant_a, class_id, profile_settings=FULL_PROFILE)
    healthy = await _mk_student(tenant_a, class_id)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)

    res = await client.get(f"/session/{session_id}/students", headers=headers)
    assert res.status_code == 200
    by_id = {s["id"]: s for s in res.json()["students"]}

    fs = by_id[flagged]
    assert fs["has_health_alert"] is True
    assert fs["has_behavior_alert"] is True
    assert fs["health_conditions"] == ["nut_allergy", "asthma"]
    assert fs["behavioral_aspects"] == ["hyperactivity", "speech_difficulty"]

    hs = by_id[healthy]
    assert hs["has_health_alert"] is False
    assert hs["has_behavior_alert"] is False
    assert hs["health_conditions"] == []

    # roster stays compact + private: no free text, no family data
    blob = json.dumps(res.json(), ensure_ascii=False)
    assert "family" not in blob
    assert "بخاخ" not in blob  # other_health_details free text


# ─────────────────────────── detail endpoint ────────────────────────────

@pytest.mark.asyncio
async def test_detail_endpoint_owner_gets_merged_fresh_detail(client, tenant_a):
    teacher_id, headers = await _mk_teacher(tenant_a)
    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(
        tenant_a, class_id,
        profile_settings=FULL_PROFILE, health_info=FULL_HEALTH_INFO,
    )
    session_id = await _mk_session(tenant_a, class_id, teacher_id)

    res = await client.get(
        f"/session/{session_id}/students/{student_id}/health", headers=headers)
    assert res.status_code == 200
    d = res.json()
    assert d["student_id"] == student_id
    assert d["has_any"] is True
    assert d["health"]["conditions"] == ["nut_allergy", "asthma"]
    assert d["health"]["allergies"] == "حساسية بنسلين"
    assert d["behavior"]["aspects"] == ["hyperactivity", "speech_difficulty"]
    blob = json.dumps(d, ensure_ascii=False)
    assert "family" not in blob


@pytest.mark.asyncio
async def test_detail_endpoint_cross_tenant_is_404(client, tenant_a, tenant_b):
    teacher_id, _ = await _mk_teacher(tenant_a)
    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(tenant_a, class_id, profile_settings=FULL_PROFILE)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)

    _, foreign_headers = await _mk_teacher(tenant_b)
    res = await client.get(
        f"/session/{session_id}/students/{student_id}/health", headers=foreign_headers)
    assert res.status_code == 404  # §8 invariant 3: never confirm foreign rows


@pytest.mark.asyncio
async def test_detail_endpoint_same_tenant_non_owner_is_403(client, tenant_a):
    teacher_id, _ = await _mk_teacher(tenant_a)
    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(tenant_a, class_id, profile_settings=FULL_PROFILE)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)

    _, other_headers = await _mk_teacher(tenant_a)
    res = await client.get(
        f"/session/{session_id}/students/{student_id}/health", headers=other_headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_detail_endpoint_student_outside_session_class_is_404(client, tenant_a):
    """The session must not become a pivot to read other classes' students."""
    teacher_id, headers = await _mk_teacher(tenant_a)
    class_id = await _mk_class(tenant_a)
    other_class = await _mk_class(tenant_a)
    outsider = await _mk_student(tenant_a, other_class, profile_settings=FULL_PROFILE)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)

    res = await client.get(
        f"/session/{session_id}/students/{outsider}/health", headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_detail_endpoint_inactive_student_is_404(client, tenant_a):
    teacher_id, headers = await _mk_teacher(tenant_a)
    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(
        tenant_a, class_id, profile_settings=FULL_PROFILE, is_active=False)
    session_id = await _mk_session(tenant_a, class_id, teacher_id)

    res = await client.get(
        f"/session/{session_id}/students/{student_id}/health", headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_detail_endpoint_independent_teacher_owner_works(client):
    """IT sessions live in the synthetic itw_<uid> workspace; the same
    endpoint must serve the IT owner."""
    uid, headers = await _mk_teacher("__unused__", role="independent_teacher")
    workspace = f"itw_{uid}"
    await gd_insert(db.session, "schools", {
        "id": workspace, "name": "مساحة معلم مستقل", "code": f"IT{uid[:6]}",
        "status": "active", "school_type": "independent_teacher",
    })
    class_id = await _mk_class(workspace)
    student_id = await _mk_student(
        workspace, class_id,
        health_info={"has_allergies": True, "allergies": "حساسية قمح"},
    )
    session_id = await _mk_session(workspace, class_id, uid)

    res = await client.get(
        f"/session/{session_id}/students/{student_id}/health", headers=headers)
    assert res.status_code == 200
    d = res.json()
    assert d["has_any"] is True
    assert d["health"]["allergies"] == "حساسية قمح"


@pytest.mark.asyncio
async def test_detail_endpoint_malformed_jsonb_does_not_500(client, tenant_a):
    teacher_id, headers = await _mk_teacher(tenant_a)
    class_id = await _mk_class(tenant_a)
    student_id = await _mk_student(
        tenant_a, class_id,
        profile_settings={"health_conditions": "asthma", "other_health_details": 7},
        health_info={"has_allergies": "yes", "allergies": ["a", "b"]},
    )
    session_id = await _mk_session(tenant_a, class_id, teacher_id)

    res = await client.get(
        f"/session/{session_id}/students/{student_id}/health", headers=headers)
    assert res.status_code == 200
