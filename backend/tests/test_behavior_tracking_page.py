"""Behaviour tracking page (المتابعة السلوكية) — GET/POST /behavior.

Root cause of "all students show 0 points": the page's endpoints read and
wrote an orphan ``behavior`` generic collection that nothing else in the
system used (0 rows in production), while real behaviours live in the
canonical ``behaviour_records`` table (written by the live-lesson engine
and the behaviour-incident routes). Additionally the role gates allowed
"teacher" but not "independent_teacher", so IT callers got a 403 the
frontend silently swallowed into an empty list.

These tests pin:
1. GET reads canonical behaviour_records with the legacy response shape
   the page renders (note ← description, date ← date/created_at fallback,
   type normalized to positive/negative).
2. POST persists into behaviour_records with only real columns.
3. Both school teacher AND independent_teacher work.
4. Tenant scoping: no cross-tenant reads even with a foreign class_id.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find, gd_insert
from tests.conftest import _mk_user, _headers


async def _seed_class(school_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": school_id, "name": f"C-{cid[:6]}",
        "is_active": True,
    })
    return cid


async def _seed_student(school_id: str, class_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": school_id, "full_name": f"S-{sid[:6]}",
        "class_id": class_id, "is_active": True,
    })
    return sid


async def _seed_behaviour(school_id: str, class_id: str, student_id: str,
                          *, rec_type="positive", points=2,
                          description="مشاركة فعالة", date=None):
    """Seed the way the live-lesson engine effectively does: real columns
    only, ``date`` typically NULL (the engine writes ``incident_date``
    which is not a column and gets dropped)."""
    rid = str(uuid.uuid4())
    doc = {
        "id": rid, "school_id": school_id, "student_id": student_id,
        "class_id": class_id, "type": rec_type, "category": rec_type,
        "points": points, "description": description,
    }
    if date is not None:
        doc["date"] = date
    await gd_insert(db.session, "behaviour_records", doc)
    return rid


async def _mk_assigned_teacher(school_id: str, class_id: str):
    """School teacher WITH an active teacher_assignments row — the profile
    endpoints authorize a teacher against that table (or a class session)."""
    user = await _mk_user(UserRole.TEACHER, school_id)
    await gd_insert(db.session, "teachers", {
        "id": user["id"], "school_id": school_id, "user_id": user["id"],
        "full_name": f"T-{user['id'][:6]}", "email": user.get("email"),
        "is_active": True,
    })
    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id, "school_id": school_id, "name": "مادة",
        "name_ar": "مادة", "name_en": "Subject", "is_active": True,
    })
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()), "school_id": school_id,
        "teacher_id": user["id"], "class_id": class_id,
        "subject_id": subject_id, "is_active": True,
    })
    return user


# ------------------------------------------------------------------ GET


@pytest.mark.asyncio
async def test_teacher_sees_live_session_behaviours(client, tenant_a, teacher_headers):
    cls = await _seed_class(tenant_a)
    sid = await _seed_student(tenant_a, cls)
    await _seed_behaviour(tenant_a, cls, sid, rec_type="positive", points=5,
                          description="مساعدة زملائه")
    await _seed_behaviour(tenant_a, cls, sid, rec_type="negative", points=-2,
                          description="عدم الانتباه")

    r = await client.get(f"/behavior?class_id={cls}", headers=teacher_headers)
    assert r.status_code == 200, r.text
    records = r.json()
    assert len(records) == 2
    by_type = {rec["type"]: rec for rec in records}
    assert by_type["positive"]["points"] == 5
    assert by_type["positive"]["note"] == "مساعدة زملائه"
    assert by_type["negative"]["points"] == -2
    # live-session rows have NULL date → must fall back to created_at,
    # never null (the page renders new Date(record.date))
    for rec in records:
        assert rec["date"], rec
        assert rec["student_id"] == sid


@pytest.mark.asyncio
async def test_independent_teacher_not_403(client, tenant_a):
    """IT runs the same /teacher/behavior page; the old gate 403'd them and
    the page silently showed 'no behaviours'."""
    it_user = await _mk_user(UserRole.INDEPENDENT_TEACHER, tenant_a)
    cls = await _seed_class(tenant_a)
    sid = await _seed_student(tenant_a, cls)
    await _seed_behaviour(tenant_a, cls, sid)

    r = await client.get(f"/behavior?class_id={cls}", headers=_headers(it_user))
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_legacy_type_normalized_from_points_sign(client, tenant_a, teacher_headers):
    """Rows written by the incident routes may carry legacy `type` values
    (e.g. 'incident'); the page styles/counts strictly on positive/negative."""
    cls = await _seed_class(tenant_a)
    sid = await _seed_student(tenant_a, cls)
    rid = str(uuid.uuid4())
    await gd_insert(db.session, "behaviour_records", {
        "id": rid, "school_id": tenant_a, "student_id": sid, "class_id": cls,
        "type": "incident", "points": -3, "description": "x",
    })

    r = await client.get(f"/behavior?class_id={cls}", headers=teacher_headers)
    assert r.status_code == 200
    assert r.json()[0]["type"] == "negative"


@pytest.mark.asyncio
async def test_cross_tenant_records_invisible(client, tenant_a, tenant_b):
    cls_a = await _seed_class(tenant_a)
    sid_a = await _seed_student(tenant_a, cls_a)
    await _seed_behaviour(tenant_a, cls_a, sid_a)

    teacher_b = await _mk_user(UserRole.TEACHER, tenant_b)
    r = await client.get(f"/behavior?class_id={cls_a}", headers=_headers(teacher_b))
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_parent_role_still_403(client, tenant_a, parent_headers):
    # (student tokens are 401 platform-wide — STUDENT_LOGIN_DISABLED —
    # so the non-teaching-role guard is asserted with a parent token)
    r = await client.get("/behavior", headers=parent_headers)
    assert r.status_code == 403


# ------------------------------------------------------------------ POST


@pytest.mark.asyncio
async def test_teacher_quick_registration_persists_and_reads_back(
    client, tenant_a, teacher_headers
):
    """Exact frontend quick-add payload: note (not description), points,
    type, date as YYYY-MM-DD."""
    cls = await _seed_class(tenant_a)
    sid = await _seed_student(tenant_a, cls)

    payload = {
        "student_id": sid, "class_id": cls, "teacher_id": "ignored-client-value",
        "type": "positive", "note": "مشاركة فعالة", "points": 5,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    r = await client.post("/behavior", json=payload, headers=teacher_headers)
    assert r.status_code == 200, r.text
    rec = r.json()["record"]
    assert rec["note"] == "مشاركة فعالة"
    assert rec["points"] == 5

    # persisted in the CANONICAL table with real columns
    rows = await gd_find(db.session, "behaviour_records", {
        "school_id": tenant_a, "student_id": sid,
    })
    assert len(rows) == 1
    assert rows[0]["description"] == "مشاركة فعالة"
    assert rows[0]["points"] == 5
    assert rows[0]["type"] == "positive"
    assert rows[0]["created_by"], "created_by must be pinned server-side"

    # visible on the tracking read path (reopen page scenario)
    r2 = await client.get(f"/behavior?class_id={cls}", headers=teacher_headers)
    assert r2.status_code == 200
    assert [x["note"] for x in r2.json()] == ["مشاركة فعالة"]


@pytest.mark.asyncio
async def test_independent_teacher_can_record(client, tenant_a):
    it_user = await _mk_user(UserRole.INDEPENDENT_TEACHER, tenant_a)
    cls = await _seed_class(tenant_a)
    sid = await _seed_student(tenant_a, cls)

    r = await client.post("/behavior", json={
        "student_id": sid, "class_id": cls, "type": "negative",
        "note": "إزعاج الآخرين", "points": -2,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }, headers=_headers(it_user))
    assert r.status_code == 200, r.text

    r2 = await client.get(f"/behavior?class_id={cls}", headers=_headers(it_user))
    assert r2.status_code == 200
    recs = r2.json()
    assert len(recs) == 1 and recs[0]["type"] == "negative"


@pytest.mark.asyncio
async def test_post_without_date_still_persists(client, tenant_a, teacher_headers):
    """Defensive: a payload with no date must not crash the timestamptz
    coercion; the read path falls back to created_at so the page still
    renders a date."""
    cls = await _seed_class(tenant_a)
    sid = await _seed_student(tenant_a, cls)

    r = await client.post("/behavior", json={
        "student_id": sid, "class_id": cls, "type": "positive",
        "note": "التزام بالقواعد", "points": 3,
    }, headers=teacher_headers)
    assert r.status_code == 200, r.text

    r2 = await client.get(f"/behavior?class_id={cls}", headers=teacher_headers)
    assert r2.status_code == 200
    recs = r2.json()
    assert len(recs) == 1
    assert recs[0]["date"], "date must fall back to created_at, never null"


@pytest.mark.asyncio
async def test_post_rejects_foreign_student(client, tenant_a, tenant_b):
    cls_b = await _seed_class(tenant_b)
    sid_b = await _seed_student(tenant_b, cls_b)
    teacher_a = await _mk_user(UserRole.TEACHER, tenant_a)

    r = await client.post("/behavior", json={
        "student_id": sid_b, "class_id": cls_b, "type": "positive",
        "note": "x", "points": 1,
    }, headers=_headers(teacher_a))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_post_rejects_mismatched_class(client, tenant_a, teacher_headers):
    cls1 = await _seed_class(tenant_a)
    cls2 = await _seed_class(tenant_a)
    sid = await _seed_student(tenant_a, cls1)

    r = await client.post("/behavior", json={
        "student_id": sid, "class_id": cls2, "type": "positive",
        "note": "x", "points": 1,
    }, headers=teacher_headers)
    assert r.status_code == 422


# ------------------------------- class dropdown (Task: IT sees no classes)


@pytest.mark.asyncio
async def test_independent_teacher_class_dropdown_populated(client, tenant_a):
    """IT has no teachers/teacher_assignments rows — they own every class in
    their own workspace. The endpoint used to 404 them and the page's
    .catch() rendered an EMPTY class dropdown."""
    it_user = await _mk_user(UserRole.INDEPENDENT_TEACHER, tenant_a)
    c1 = await _seed_class(tenant_a)
    c2 = await _seed_class(tenant_a)
    await _seed_student(tenant_a, c1)

    r = await client.get(f"/teacher/classes/{it_user['id']}", headers=_headers(it_user))
    assert r.status_code == 200, r.text
    returned = {c["id"] for c in r.json()}
    assert {c1, c2} <= returned
    by_id = {c["id"]: c for c in r.json()}
    assert by_id[c1]["student_count"] == 1


@pytest.mark.asyncio
async def test_independent_teacher_dropdown_excludes_other_workspaces(
    client, tenant_a, tenant_b
):
    it_user = await _mk_user(UserRole.INDEPENDENT_TEACHER, tenant_a)
    mine = await _seed_class(tenant_a)
    foreign = await _seed_class(tenant_b)

    r = await client.get(f"/teacher/classes/{it_user['id']}", headers=_headers(it_user))
    assert r.status_code == 200, r.text
    ids = {c["id"] for c in r.json()}
    assert mine in ids
    assert foreign not in ids


@pytest.mark.asyncio
async def test_independent_teacher_cannot_read_another_teachers_classes(
    client, tenant_a
):
    it_user = await _mk_user(UserRole.INDEPENDENT_TEACHER, tenant_a)
    other = await _mk_user(UserRole.INDEPENDENT_TEACHER, tenant_a)
    await _seed_class(tenant_a)

    r = await client.get(f"/teacher/classes/{other['id']}", headers=_headers(it_user))
    assert r.status_code == 403


# ---------------- student profile (opened from فصولي) reads the same store


@pytest.mark.asyncio
async def test_recorded_behaviour_visible_in_student_profile(client, tenant_a):
    """The class-list student profile reads /students/{id}/analytics, which
    used to read the orphan `behavior` collection — so behaviours recorded on
    المتابعة السلوكية never showed up there."""
    cls = await _seed_class(tenant_a)
    sid = await _seed_student(tenant_a, cls)
    teacher_headers = _headers(await _mk_assigned_teacher(tenant_a, cls))

    r = await client.post("/behavior", json={
        "student_id": sid, "class_id": cls, "type": "positive",
        "note": "مشاركة فعالة", "points": 5,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }, headers=teacher_headers)
    assert r.status_code == 200, r.text
    r = await client.post("/behavior", json={
        "student_id": sid, "class_id": cls, "type": "negative",
        "note": "عدم الانتباه", "points": -2,
    }, headers=teacher_headers)
    assert r.status_code == 200, r.text

    prof = await client.get(f"/students/{sid}/analytics", headers=teacher_headers)
    assert prof.status_code == 200, prof.text
    beh = prof.json()["behavior"]
    notes = {rec["note"] for rec in beh["records"]}
    assert notes == {"مشاركة فعالة", "عدم الانتباه"}
    # the teacher-written label survives (not collapsed to a category name)
    assert {rec["name_ar"] for rec in beh["records"]} == notes
    assert beh["total_points"] == 3


@pytest.mark.asyncio
async def test_student_profile_shows_both_polarities(client, tenant_a):
    cls = await _seed_class(tenant_a)
    teacher_headers = _headers(await _mk_assigned_teacher(tenant_a, cls))
    pos_only = await _seed_student(tenant_a, cls)
    neg_only = await _seed_student(tenant_a, cls)
    none_at_all = await _seed_student(tenant_a, cls)
    await _seed_behaviour(tenant_a, cls, pos_only, rec_type="positive", points=5)
    await _seed_behaviour(tenant_a, cls, neg_only, rec_type="negative", points=-3,
                          description="إزعاج الآخرين")

    for sid, expected in ((pos_only, 5), (neg_only, -3), (none_at_all, 0)):
        r = await client.get(f"/students/{sid}/analytics", headers=teacher_headers)
        assert r.status_code == 200, r.text
        assert r.json()["behavior"]["total_points"] == expected


@pytest.mark.asyncio
async def test_live_session_mirror_not_double_counted(client, tenant_a):
    """commit_session_scores mirrors each live-session behaviour interaction
    into behaviour_records as ``si:<interaction_id>:br``. Analytics already
    sums the interaction itself, so the mirror must be skipped."""
    cls = await _seed_class(tenant_a)
    sid = await _seed_student(tenant_a, cls)
    teacher_headers = _headers(await _mk_assigned_teacher(tenant_a, cls))
    await gd_insert(db.session, "behaviour_records", {
        "id": f"si:{uuid.uuid4()}:br", "school_id": tenant_a, "student_id": sid,
        "class_id": cls, "type": "positive", "category": "positive",
        "points": 4, "description": "احترام",
    })

    r = await client.get(f"/students/{sid}/analytics", headers=teacher_headers)
    assert r.status_code == 200, r.text
    beh = r.json()["behavior"]
    assert beh["records"] == []
    assert beh["total_points"] == 0

    # but the tracking page (which does NOT read interactions) still shows it
    page = await client.get(f"/behavior?class_id={cls}", headers=teacher_headers)
    assert page.status_code == 200
    assert len(page.json()) == 1


@pytest.mark.asyncio
async def test_class_student_stats_include_recorded_behaviour(
    client, tenant_a, teacher_headers
):
    """سجل الطلاب list cards read /classes/{id}/student-stats — same orphan
    collection bug."""
    cls = await _seed_class(tenant_a)
    sid = await _seed_student(tenant_a, cls)
    await _seed_behaviour(tenant_a, cls, sid, rec_type="positive", points=5)
    await _seed_behaviour(tenant_a, cls, sid, rec_type="negative", points=-2)

    r = await client.get(f"/classes/{cls}/student-stats", headers=teacher_headers)
    assert r.status_code == 200, r.text
    assert r.json()[sid]["behavior_points"] == 3


@pytest.mark.asyncio
async def test_independent_teacher_sees_own_student_profile(client, tenant_a):
    """IT has no teacher_assignments rows — the school-teacher authz path
    403'd them out of their own students' profiles."""
    it_user = await _mk_user(UserRole.INDEPENDENT_TEACHER, tenant_a)
    cls = await _seed_class(tenant_a)
    sid = await _seed_student(tenant_a, cls)
    await _seed_behaviour(tenant_a, cls, sid, rec_type="positive", points=5,
                          description="إبداع وتميز")

    r = await client.get(f"/students/{sid}/analytics", headers=_headers(it_user))
    assert r.status_code == 200, r.text
    beh = r.json()["behavior"]
    assert beh["total_points"] == 5
    assert [rec["note"] for rec in beh["records"]] == ["إبداع وتميز"]


@pytest.mark.asyncio
async def test_independent_teacher_cannot_read_foreign_student_profile(
    client, tenant_a, tenant_b
):
    it_user = await _mk_user(UserRole.INDEPENDENT_TEACHER, tenant_a)
    cls_b = await _seed_class(tenant_b)
    sid_b = await _seed_student(tenant_b, cls_b)

    r = await client.get(f"/students/{sid_b}/analytics", headers=_headers(it_user))
    assert r.status_code == 403
