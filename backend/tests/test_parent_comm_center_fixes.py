"""
Parent Communication Center fixes:

1. Teacher-recipient resolution must ALSO cover classes whose live schedule
   exists only in the modern ``timetable_sessions`` store (anchored to the
   latest PUBLISHED ``timetables`` row). Classes scheduled by the smart
   engine have no ``schedule_sessions`` rows, so the old resolver returned
   an empty list ("لا يوجد معلمون متاحون للمراسلة حالياً") even though the
   child's class had a full published timetable.
   Anchoring to the published timetable only (never the historical pile)
   preserves the anti-over-disclosure decision from
   docs/qa/2026-05-31-parent-dropdowns-audit.md (Finding 1).

2. The hard 3-open-request cap is removed from quick-message,
   absence-excuse, and meeting-request. ``/open-requests-count`` keeps
   returning counts for display but must always report ``can_submit: true``.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_insert


def _headers(user_id: str, role: str, tenant_id):
    token = create_access_token({"sub": user_id, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


async def _mk_user(role: str, tenant_id, name=None) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": role, "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test", "full_name": name or f"{role}-{uid[:6]}",
        "is_active": True, "password_hash": "x",
    })
    return uid


async def _mk_class(tenant_id) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": tenant_id, "tenant_id": tenant_id, "name": "1A",
    })
    return cid


async def _mk_student(tenant_id, class_id, *, parent_user_id, name="S") -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": tenant_id, "tenant_id": tenant_id,
        "full_name": name, "class_id": class_id, "is_active": True,
    })
    await gd_insert(db.session, "guardian_links", {
        "id": str(uuid.uuid4()), "tenant_id": tenant_id,
        "student_id": sid, "parent_user_id": parent_user_id,
        "is_active": True,
    })
    return sid


async def _mk_teacher(tenant_id, name) -> tuple:
    """teachers row + linked teacher user. Returns (teacher_id, user_id)."""
    user_id = await _mk_user("teacher", tenant_id, name=name)
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "school_id": tenant_id, "user_id": user_id,
        "full_name": name, "is_active": True,
    })
    return teacher_id, user_id


async def _mk_published_timetable(tenant_id, *, status="published",
                                  published_at=None) -> str:
    tt_id = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": tt_id, "school_id": tenant_id, "name": "جدول",
        "status": status,
        "is_published": status == "published",
        "published_at": published_at or datetime.now(timezone.utc).isoformat(),
    })
    return tt_id


async def _mk_timetable_session(tt_id, class_id, teacher_id):
    await gd_insert(db.session, "timetable_sessions", {
        "id": str(uuid.uuid4()), "timetable_id": tt_id,
        "class_id": class_id, "teacher_id": teacher_id,
        "day_of_week": "sunday", "period_number": 1,
    })


async def _mk_schedule_session(tenant_id, class_id, teacher_id):
    await gd_insert(db.session, "schedule_sessions", {
        "id": str(uuid.uuid4()), "school_id": tenant_id,
        "schedule_id": str(uuid.uuid4()),
        "class_id": class_id, "teacher_id": teacher_id,
        "day_of_week": "sunday", "slot_number": 1, "status": "scheduled",
    })


async def _mk_open_excuse(tenant_id, parent_id):
    await gd_insert(db.session, "absence_excuses", {
        "id": str(uuid.uuid4()), "school_id": tenant_id,
        "parent_id": parent_id, "child_id": str(uuid.uuid4()),
        "absence_date": "2026-07-01", "reason": "r", "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


# ---------- 1) teacher recipient resolution ----------

@pytest.mark.asyncio
async def test_teachers_resolve_via_published_timetable_sessions(client, tenant_a):
    """Class scheduled ONLY by the modern engine (timetable_sessions under a
    published timetable, zero schedule_sessions rows) must still surface its
    teachers to the parent."""
    parent = await _mk_user("parent", tenant_a)
    class_id = await _mk_class(tenant_a)
    await _mk_student(tenant_a, class_id, parent_user_id=parent, name="ولد")
    teacher_id, teacher_user = await _mk_teacher(tenant_a, "معلم الرياضيات")
    tt_id = await _mk_published_timetable(tenant_a)
    await _mk_timetable_session(tt_id, class_id, teacher_id)

    resp = await client.get("/parent-portal/message-recipients/teachers",
                            headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, resp.text
    teachers = resp.json().get("teachers", [])
    ids = {t["recipient_user_id"] for t in teachers}
    assert teacher_user in ids, f"expected teacher from published timetable, got {teachers}"
    row = next(t for t in teachers if t["recipient_user_id"] == teacher_user)
    assert "ولد" in row.get("child_labels", [])


@pytest.mark.asyncio
async def test_teachers_still_resolve_via_schedule_sessions(client, tenant_a):
    """Regression guard: legacy schedule_sessions path keeps working."""
    parent = await _mk_user("parent", tenant_a)
    class_id = await _mk_class(tenant_a)
    await _mk_student(tenant_a, class_id, parent_user_id=parent)
    teacher_id, teacher_user = await _mk_teacher(tenant_a, "معلم العلوم")
    await _mk_schedule_session(tenant_a, class_id, teacher_id)

    resp = await client.get("/parent-portal/message-recipients/teachers",
                            headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, resp.text
    ids = {t["recipient_user_id"] for t in resp.json().get("teachers", [])}
    assert teacher_user in ids


@pytest.mark.asyncio
async def test_union_of_both_schedule_sources(client, tenant_a):
    """A parent with two children — one class in schedule_sessions, one in
    the published timetable — sees the union of both teacher sets."""
    parent = await _mk_user("parent", tenant_a)
    class_legacy = await _mk_class(tenant_a)
    class_modern = await _mk_class(tenant_a)
    await _mk_student(tenant_a, class_legacy, parent_user_id=parent, name="أ")
    await _mk_student(tenant_a, class_modern, parent_user_id=parent, name="ب")
    t1_id, t1_user = await _mk_teacher(tenant_a, "معلم أ")
    t2_id, t2_user = await _mk_teacher(tenant_a, "معلم ب")
    await _mk_schedule_session(tenant_a, class_legacy, t1_id)
    tt_id = await _mk_published_timetable(tenant_a)
    await _mk_timetable_session(tt_id, class_modern, t2_id)

    resp = await client.get("/parent-portal/message-recipients/teachers",
                            headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, resp.text
    ids = {t["recipient_user_id"] for t in resp.json().get("teachers", [])}
    assert {t1_user, t2_user} <= ids


@pytest.mark.asyncio
async def test_archived_timetable_teachers_not_disclosed(client, tenant_a):
    """Over-disclosure guard (audit Finding 1): teachers appearing ONLY in an
    archived/older timetable must NOT be offered as recipients."""
    parent = await _mk_user("parent", tenant_a)
    class_id = await _mk_class(tenant_a)
    await _mk_student(tenant_a, class_id, parent_user_id=parent)
    current_id, current_user = await _mk_teacher(tenant_a, "الحالي")
    old_id, old_user = await _mk_teacher(tenant_a, "القديم")
    tt_old = await _mk_published_timetable(
        tenant_a, status="archived", published_at="2026-01-01T00:00:00+00:00")
    await _mk_timetable_session(tt_old, class_id, old_id)
    tt_new = await _mk_published_timetable(tenant_a)
    await _mk_timetable_session(tt_new, class_id, current_id)

    resp = await client.get("/parent-portal/message-recipients/teachers",
                            headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, resp.text
    ids = {t["recipient_user_id"] for t in resp.json().get("teachers", [])}
    assert current_user in ids
    assert old_user not in ids


@pytest.mark.asyncio
async def test_cross_tenant_timetable_not_disclosed(client, tenant_a, tenant_b):
    """A published timetable in ANOTHER tenant must never leak teachers."""
    parent = await _mk_user("parent", tenant_a)
    class_id = await _mk_class(tenant_a)
    await _mk_student(tenant_a, class_id, parent_user_id=parent)
    foreign_teacher, foreign_user = await _mk_teacher(tenant_b, "أجنبي")
    tt_foreign = await _mk_published_timetable(tenant_b)
    # Foreign timetable referencing the SAME class id (hostile/stale data).
    await _mk_timetable_session(tt_foreign, class_id, foreign_teacher)

    resp = await client.get("/parent-portal/message-recipients/teachers",
                            headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, resp.text
    ids = {t["recipient_user_id"] for t in resp.json().get("teachers", [])}
    assert foreign_user not in ids


# ---------- 2) open-request limit removal ----------

@pytest.mark.asyncio
async def test_quick_message_not_blocked_after_three_open(client, tenant_a):
    parent = await _mk_user("parent", tenant_a)
    await _mk_user("school_admin", tenant_a)  # receiver for admin messages
    class_id = await _mk_class(tenant_a)
    child = await _mk_student(tenant_a, class_id, parent_user_id=parent)
    for _ in range(3):
        await _mk_open_excuse(tenant_a, parent)

    resp = await client.post("/parent-portal/quick-message",
                             json={"content": "رسالة رابعة", "recipient_type": "admin",
                                   "student_id": child},
                             headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, f"limit must be removed, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_open_requests_count_always_can_submit(client, tenant_a):
    parent = await _mk_user("parent", tenant_a)
    for _ in range(4):
        await _mk_open_excuse(tenant_a, parent)

    resp = await client.get("/parent-portal/open-requests-count",
                            headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["can_submit"] is True
    assert body["breakdown"]["excuses"] == 4  # counts still reported for display


@pytest.mark.asyncio
async def test_absence_excuse_not_blocked_after_three_open(client, tenant_a):
    parent = await _mk_user("parent", tenant_a)
    class_id = await _mk_class(tenant_a)
    child = await _mk_student(tenant_a, class_id, parent_user_id=parent)
    for _ in range(3):
        await _mk_open_excuse(tenant_a, parent)

    resp = await client.post("/parent-portal/absence-excuse",
                             json={"child_id": child, "absence_date": "2026-07-08",
                                   "reason": "مرض"},
                             headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, f"limit must be removed, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_meeting_request_not_blocked_after_three_open(client, tenant_a):
    parent = await _mk_user("parent", tenant_a)
    for _ in range(3):
        await _mk_open_excuse(tenant_a, parent)

    resp = await client.post("/parent-portal/meeting-request",
                             json={"preferred_date": "2026-07-15", "topic": "اجتماع"},
                             headers=_headers(parent, "parent", tenant_a))
    assert resp.status_code == 200, f"limit must be removed, got {resp.status_code}: {resp.text}"


# ---------- 3) per-IP burst limits replace the removed cap ----------

from src.core.middleware.rate_limiter import RATE_LIMITS, rate_store  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_store():
    rate_store._store.clear()
    yield
    rate_store._store.clear()


def test_parent_write_surfaces_have_burst_limits():
    """The removed 3-open cap is replaced by POST-only per-IP burst limits."""
    for path in ("/api/parent-portal/quick-message",
                 "/api/parent-portal/absence-excuse",
                 "/api/parent-portal/meeting-request"):
        entry = RATE_LIMITS.get(path)
        assert entry is not None, f"{path} missing from RATE_LIMITS"
        assert entry["max"] >= 1 and entry["window"] >= 1
        assert entry.get("methods") == {"POST"}, f"{path} must be POST-only"


@pytest.mark.asyncio
async def test_excuse_post_burst_429_but_get_list_unthrottled(client, tenant_a, monkeypatch):
    parent = await _mk_user("parent", tenant_a)
    class_id = await _mk_class(tenant_a)
    child = await _mk_student(tenant_a, class_id, parent_user_id=parent)
    headers = _headers(parent, "parent", tenant_a)
    monkeypatch.setitem(RATE_LIMITS["/api/parent-portal/absence-excuse"], "max", 2)

    payload = {"child_id": child, "absence_date": "2026-07-08", "reason": "مرض"}
    for _ in range(2):
        r = await client.post("/parent-portal/absence-excuse", json=payload, headers=headers)
        assert r.status_code == 200, r.text

    r = await client.post("/parent-portal/absence-excuse", json=payload, headers=headers)
    assert r.status_code == 429
    assert r.headers.get("Retry-After") is not None

    # Sibling GET list shares the path prefix but must NOT be throttled.
    r = await client.get("/parent-portal/absence-excuses", headers=headers)
    assert r.status_code == 200, r.text
