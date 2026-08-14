"""Parent/student schedule surfaces must never say "غير محدد" for a subject
that actually has a name.

Root cause covered (audit 2026-08-04): the subject-name maps behind the parent
home widget (``GET /parent-portal/child/{id}/today-live``), the parent weekly
schedule (``/child/{id}/schedule``) and the student portal were built with

    {s["id"]: s.get("name_ar", s.get("name", ""))}

``subjects`` is a real table: ``name`` is NOT NULL, ``name_ar`` is nullable. A
row created by a path that only fills ``name`` therefore arrives as
``{"name": "علوم", "name_ar": None}`` — the key EXISTS, so ``dict.get`` never
reaches its default and the map value is ``None``. The caller's
``sub_map.get(id) or ... or "غير محدد"`` then rendered the placeholder (and the
weekly grid, which used ``sub_map.get(id, "غير محدد")``, leaked a literal
``null``) even though the subject was perfectly nameable.

Pins:
1. ``name_ar``-less subjects render their ``name`` on the home widget.
2. The weekly schedule uses the same chain and never returns ``null``.
3. A dangling ``subject_id`` falls back to the row's denormalised
   ``subject_name`` before the placeholder.
4. "غير محدد" survives only when the session truly has no resolvable name.
"""
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_insert
from src.common.utils.subject_display import build_subject_name_map, subject_display_name

SAUDI_TZ = ZoneInfo("Asia/Riyadh")
_DAY_MAP = {6: "sunday", 0: "monday", 1: "tuesday", 2: "wednesday",
            3: "thursday", 4: "friday", 5: "saturday"}
_DAY_AR = {"sunday": "الأحد", "monday": "الاثنين", "tuesday": "الثلاثاء",
           "wednesday": "الأربعاء", "thursday": "الخميس"}


def _headers(user_id: str, role: str, tenant_id):
    token = create_access_token({"sub": user_id, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


def _today_en() -> str:
    return _DAY_MAP.get(datetime.now(SAUDI_TZ).weekday(), "sunday")


async def _mk_real_school():
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid, "name": "مدرسة الاختبار", "code": f"SC{sid[:8]}",
        "status": "active", "country": "SA", "language": "ar",
        "school_type": "public", "tenant_type": "production",
    })
    return sid


async def _mk_parent_and_child(school_id):
    parent_uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": parent_uid, "role": "parent", "tenant_id": school_id,
        "email": f"p-{parent_uid}@t.test", "full_name": "ولي الأمر",
        "is_active": True, "password_hash": "x",
    })
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": school_id, "tenant_id": school_id,
        "name": "أول/1",
    })
    student_id = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": student_id, "school_id": school_id, "tenant_id": school_id,
        "full_name": "طالب اختبار", "class_id": cid, "is_active": True,
    })
    await gd_insert(db.session, "guardian_links", {
        "id": str(uuid.uuid4()), "tenant_id": school_id,
        "student_id": student_id, "parent_ref": parent_uid, "is_active": True,
    })
    return parent_uid, student_id, cid


async def _mk_teacher(school_id, name="أحمد المعلم"):
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid, "school_id": school_id, "full_name": name, "is_active": True,
    })
    return tid


async def _mk_subject(school_id, name, name_ar=None):
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid, "school_id": school_id, "name": name, "name_ar": name_ar,
        "is_active": True,
    })
    return sid


async def _mk_timetable(school_id):
    tt_id = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": tt_id, "school_id": school_id, "name": "الجدول المعتمد",
        "status": "published",
    })
    return tt_id


async def _mk_session(tt_id, school_id, class_id, day, period, *,
                      subject_id=None, teacher_id=None, subject_name=None):
    doc = {
        "id": str(uuid.uuid4()), "timetable_id": tt_id, "school_id": school_id,
        "class_id": class_id, "day_of_week": day, "period_number": period,
        "subject_id": subject_id, "teacher_id": teacher_id,
    }
    if subject_name is not None:
        doc["subject_name"] = subject_name
    await gd_insert(db.session, "timetable_sessions", doc)


# --------------------------------------------------------------------------
# Pure resolver
# --------------------------------------------------------------------------

def test_display_name_falls_back_through_null_columns():
    assert subject_display_name({"name_ar": "العلوم", "name": "Science"}) == "العلوم"
    # The real-table shape: key present, value NULL → must fall through.
    assert subject_display_name({"name_ar": None, "name": "علوم"}) == "علوم"
    assert subject_display_name({"name_ar": "  ", "name": None,
                                 "name_en": "Science"}) == "Science"
    assert subject_display_name({"name_ar": None, "name": None}) == ""
    assert subject_display_name(None) == ""


def test_name_map_omits_nameless_rows_so_or_chains_still_fall_through():
    rows = [
        {"id": "a", "name_ar": None, "name": "علوم"},
        {"id": "b", "name_ar": None, "name": None, "name_en": None},
        {"name_ar": "بلا معرف"},
    ]
    assert build_subject_name_map(rows) == {"a": "علوم"}
    assert build_subject_name_map(None) == {}


# --------------------------------------------------------------------------
# Parent home widget (today-live)
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_today_live_renders_subject_without_arabic_name(client):
    school_id = await _mk_real_school()
    parent_uid, student_id, class_id = await _mk_parent_and_child(school_id)
    teacher_id = await _mk_teacher(school_id)
    tt_id = await _mk_timetable(school_id)
    today = _today_en()

    localized = await _mk_subject(school_id, "Science", name_ar="العلوم")
    name_only = await _mk_subject(school_id, "التربية الفنية")  # name_ar NULL

    await _mk_session(tt_id, school_id, class_id, today, 1,
                      subject_id=localized, teacher_id=teacher_id)
    await _mk_session(tt_id, school_id, class_id, today, 2,
                      subject_id=name_only, teacher_id=teacher_id)

    resp = await client.get(f"/parent-portal/child/{student_id}/today-live",
                            headers=_headers(parent_uid, "parent", school_id))
    assert resp.status_code == 200, resp.text
    by_period = {s["period"]: s for s in resp.json()["school_day"]["all_sessions"]}
    assert by_period[1]["subject"] == "العلوم"
    # Regression: this used to be "غير محدد" because name_ar was NULL.
    assert by_period[2]["subject"] == "التربية الفنية"
    assert by_period[2]["teacher"] == "أحمد المعلم"


@pytest.mark.asyncio
async def test_today_live_falls_back_to_row_name_then_placeholder(client):
    school_id = await _mk_real_school()
    parent_uid, student_id, class_id = await _mk_parent_and_child(school_id)
    teacher_id = await _mk_teacher(school_id)
    tt_id = await _mk_timetable(school_id)
    today = _today_en()

    # Subject deleted after the timetable was built → dangling id, but the row
    # still remembers what the lesson was.
    await _mk_session(tt_id, school_id, class_id, today, 1,
                      subject_id=str(uuid.uuid4()), teacher_id=teacher_id,
                      subject_name="الرياضيات")
    # Nothing resolvable at all → the placeholder is the honest answer.
    await _mk_session(tt_id, school_id, class_id, today, 2,
                      subject_id=None, teacher_id=teacher_id)

    resp = await client.get(f"/parent-portal/child/{student_id}/today-live",
                            headers=_headers(parent_uid, "parent", school_id))
    assert resp.status_code == 200, resp.text
    by_period = {s["period"]: s for s in resp.json()["school_day"]["all_sessions"]}
    assert by_period[1]["subject"] == "الرياضيات"
    assert by_period[2]["subject"] == "غير محدد"


# --------------------------------------------------------------------------
# Parent weekly schedule
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weekly_schedule_never_returns_null_subject(client):
    school_id = await _mk_real_school()
    parent_uid, student_id, class_id = await _mk_parent_and_child(school_id)
    teacher_id = await _mk_teacher(school_id)
    tt_id = await _mk_timetable(school_id)

    name_only = await _mk_subject(school_id, "التربية الفنية")  # name_ar NULL
    await _mk_session(tt_id, school_id, class_id, "monday", 1,
                      subject_id=name_only, teacher_id=teacher_id)
    await _mk_session(tt_id, school_id, class_id, "monday", 2,
                      subject_id=str(uuid.uuid4()), teacher_id=teacher_id,
                      subject_name="الرياضيات")

    resp = await client.get(f"/parent-portal/child/{student_id}/schedule",
                            headers=_headers(parent_uid, "parent", school_id))
    assert resp.status_code == 200, resp.text
    monday = resp.json()["schedule"].get("الاثنين") or []
    assert len(monday) == 2, monday
    subjects = [row["subject"] for row in monday]
    assert None not in subjects, monday
    assert set(subjects) == {"التربية الفنية", "الرياضيات"}
    assert all(row["teacher"] == "أحمد المعلم" for row in monday)


# --------------------------------------------------------------------------
# Parent "child teachers" list
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_child_teachers_list_keeps_subject_without_arabic_name(client):
    """The teachers list filters out subjects whose name resolves empty, so the
    NULL ``name_ar`` map silently dropped every such subject from the card.

    The student portal renders the same three maps (today schedule, weekly
    schedule, my-teachers) through the same helper; it has no HTTP coverage
    because student logins are disabled platform-wide
    (``dependencies.STUDENT_LOGIN_DISABLED``) — see
    test_session_management_assignments.py."""
    school_id = await _mk_real_school()
    parent_uid, student_id, class_id = await _mk_parent_and_child(school_id)
    teacher_id = await _mk_teacher(school_id)
    tt_id = await _mk_timetable(school_id)

    name_only = await _mk_subject(school_id, "التربية الفنية")  # name_ar NULL
    await _mk_session(tt_id, school_id, class_id, "monday", 1,
                      subject_id=name_only, teacher_id=teacher_id)

    resp = await client.get(f"/parent-portal/child/{student_id}/teachers",
                            headers=_headers(parent_uid, "parent", school_id))
    assert resp.status_code == 200, resp.text
    rows = resp.json()["teachers"]
    assert len(rows) == 1, rows
    assert rows[0]["subjects"] == ["التربية الفنية"]
