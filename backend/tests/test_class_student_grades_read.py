"""Class-level student grades read endpoint (سجل الطلاب).

GET /api/class/{class_id}/student-grades

The teacher "Student Record" tab must show real accumulated grades from
committed live sessions (student_grades collection) instead of zeros.

Contract:
  * Aggregation = AVERAGE of the per-session committed values per
    (student, column), rounded to 1 decimal. Denominator = sessions where
    THAT student has a row for THAT column (absent/no-data sessions never
    wrote rows, so they don't count).
  * Tenant filter derives from the CLASS row's school_id — never the
    caller's tenant — so §6.7 collaborators (foreign workspace tenant)
    still read the host class's grades.
  * Optional ?subject_id= narrows to one subject's sessions.
  * School teacher auth via linkage tables; IT owner via workspace;
    cross-workspace IT without a collab row → 404 (§8 inv. 3).
"""
import uuid

import pytest

from dependencies import db, UserRole
from engines.sql_utils import gd_insert

from conftest import _mk_user, _headers, _mk_school
from tests._it_fixtures import headers as it_headers, mk_it_workspace, now_ts


async def _seed_class(school_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "name": f"C-{cid[:6]}",
        "is_active": True,
    })
    return cid


async def _seed_teacher_with_class(tenant: str, class_id: str) -> dict:
    """School teacher user + teachers row + teacher_assignments linkage."""
    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id,
        "school_id": tenant,
        "name": "مادة",
        "is_active": True,
    })
    teacher_row_id = str(uuid.uuid4())
    user = await _mk_user(UserRole.TEACHER, tenant)
    from engines.sql_utils import gd_update_one
    await gd_update_one(db.session, "users", {"id": user["id"]}, {"teacher_id": teacher_row_id})
    user["teacher_id"] = teacher_row_id
    await gd_insert(db.session, "teachers", {
        "id": teacher_row_id,
        "school_id": tenant,
        "user_id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "is_active": True,
    })
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()),
        "school_id": tenant,
        "teacher_id": teacher_row_id,
        "class_id": class_id,
        "subject_id": subject_id,
    })
    return user


async def _seed_grade_row(
    *, school_id: str, class_id: str, student_id: str, column_id: str,
    score: float, max_score: float = 5.0, session_id: str = None,
    subject_id: str = "subj-1",
) -> None:
    sess = session_id or str(uuid.uuid4())
    await gd_insert(db.session, "student_grades", {
        "id": f"sess:{sess}:{student_id}:participation:sg",
        "tenant_id": school_id,
        "school_id": school_id,
        "student_id": student_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "column_id": column_id,
        "assessment_type": "coursework",
        "score": score,
        "max_score": max_score,
        "session_id": sess,
        "source": "live_session",
    })


def _grade_map(payload: dict) -> dict:
    """{(student_id, column_id): (score, sessions)}"""
    return {
        (g["student_id"], g["column_id"]): (g["score"], g["sessions"])
        for g in payload["grades"]
    }


@pytest.mark.asyncio
async def test_school_teacher_reads_averaged_grades(client, tenant_a):
    class_id = await _seed_class(tenant_a)
    teacher = await _seed_teacher_with_class(tenant_a, class_id)
    s1, s2 = str(uuid.uuid4()), str(uuid.uuid4())
    col = str(uuid.uuid4())

    # s1: two sessions 3 + 4 -> avg 3.5 ; s2: one session 5 -> 5.0
    await _seed_grade_row(school_id=tenant_a, class_id=class_id, student_id=s1, column_id=col, score=3)
    await _seed_grade_row(school_id=tenant_a, class_id=class_id, student_id=s1, column_id=col, score=4)
    await _seed_grade_row(school_id=tenant_a, class_id=class_id, student_id=s2, column_id=col, score=5)

    r = await client.get(f"/class/{class_id}/student-grades", headers=_headers(teacher))
    assert r.status_code == 200, r.text
    gm = _grade_map(r.json())
    assert gm[(s1, col)] == (3.5, 2)
    assert gm[(s2, col)] == (5.0, 1)


@pytest.mark.asyncio
async def test_subject_filter_narrows_aggregation(client, tenant_a):
    class_id = await _seed_class(tenant_a)
    teacher = await _seed_teacher_with_class(tenant_a, class_id)
    sid = str(uuid.uuid4())
    col = str(uuid.uuid4())

    await _seed_grade_row(school_id=tenant_a, class_id=class_id, student_id=sid,
                          column_id=col, score=2, subject_id="subj-A")
    await _seed_grade_row(school_id=tenant_a, class_id=class_id, student_id=sid,
                          column_id=col, score=4, subject_id="subj-B")

    r_all = await client.get(f"/class/{class_id}/student-grades", headers=_headers(teacher))
    assert _grade_map(r_all.json())[(sid, col)] == (3.0, 2)

    r_a = await client.get(
        f"/class/{class_id}/student-grades", params={"subject_id": "subj-A"},
        headers=_headers(teacher),
    )
    assert _grade_map(r_a.json())[(sid, col)] == (2.0, 1)


@pytest.mark.asyncio
async def test_unassigned_school_teacher_403(client, tenant_a):
    class_id = await _seed_class(tenant_a)
    outsider = await _mk_user(UserRole.TEACHER, tenant_a)
    r = await client.get(f"/class/{class_id}/student-grades", headers=_headers(outsider))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_it_owner_reads_own_class_grades(client):
    ctx = await mk_it_workspace()
    sid = str(uuid.uuid4())
    col = str(uuid.uuid4())
    await _seed_grade_row(school_id=ctx["wsid"], class_id=ctx["class_id"],
                          student_id=sid, column_id=col, score=4)
    r = await client.get(
        f"/class/{ctx['class_id']}/student-grades",
        headers=it_headers(ctx["uid"], ctx["user"]["role"], ctx["wsid"]),
    )
    assert r.status_code == 200, r.text
    assert _grade_map(r.json())[(sid, col)] == (4.0, 1)


@pytest.mark.asyncio
async def test_collaborator_reads_host_class_grades_nonempty(client):
    """§6.7: collaborator's own tenant differs from the host class's —
    the tenant filter MUST derive from the class row or this returns []."""
    host = await mk_it_workspace()
    collab = await mk_it_workspace(with_class=False, with_student=False, with_parent=False)
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc).isoformat()
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    await gd_insert(db.session, "workspace_collaborators", {
        "id": str(uuid.uuid4()),
        "host_school_id": host["wsid"],
        "collaborator_school_id": collab["wsid"],
        "class_id": host["class_id"],
        "collaborator_email": collab["user"]["email"],
        "collaborator_user_id": collab["uid"],
        "token_hash": "x",
        "scope": {"mode": "read"},
        "status": "accepted",
        "sent_at": now,
        "accepted_at": now,
        "expires_at": expires,
        "created_at": now,
        "updated_at": now,
    })
    sid = str(uuid.uuid4())
    col = str(uuid.uuid4())
    await _seed_grade_row(school_id=host["wsid"], class_id=host["class_id"],
                          student_id=sid, column_id=col, score=3)
    r = await client.get(
        f"/class/{host['class_id']}/student-grades",
        headers=it_headers(collab["uid"], collab["user"]["role"], collab["wsid"]),
    )
    assert r.status_code == 200, r.text
    assert _grade_map(r.json())[(sid, col)] == (3.0, 1)


@pytest.mark.asyncio
async def test_cross_workspace_it_404(client):
    host = await mk_it_workspace()
    stranger = await mk_it_workspace(with_class=False, with_student=False, with_parent=False)
    r = await client.get(
        f"/class/{host['class_id']}/student-grades",
        headers=it_headers(stranger["uid"], stranger["user"]["role"], stranger["wsid"]),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /class/{class_id}/subjects — subject context for the record tab
# ---------------------------------------------------------------------------

async def _seed_subject(tenant: str, name: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid, "school_id": tenant, "name": name, "is_active": True,
    })
    return sid


@pytest.mark.asyncio
async def test_class_subjects_class_wide_with_caller_default(client, tenant_a):
    """The record subject list is CLASS-WIDE (spec: switch between all
    subjects attached to the class) — another teacher's subject appears —
    but the DEFAULT lands on the caller's own subject."""
    class_id = await _seed_class(tenant_a)
    teacher = await _seed_teacher_with_class(tenant_a, class_id)   # caller
    other = await _seed_teacher_with_class(tenant_a, class_id)     # colleague
    assert other["teacher_id"] != teacher["teacher_id"]

    # The caller's own subject id (from their assignment row).
    from engines.sql_utils import gd_find as _gd_find
    tas = await _gd_find(db.session, "teacher_assignments",
                         {"class_id": class_id, "teacher_id": teacher["teacher_id"]})
    my_subject = tas[0]["subject_id"]

    r = await client.get(f"/class/{class_id}/subjects", headers=_headers(teacher))
    assert r.status_code == 200, r.text
    body = r.json()
    ids = {s["id"] for s in body["subjects"]}
    assert len(ids) == 2  # caller's + colleague's subjects, class-wide
    assert my_subject in ids
    assert body["default_subject_id"] == my_subject
    assert all(s["has_grades"] is False for s in body["subjects"])


@pytest.mark.asyncio
async def test_class_subjects_includes_graded_orphan_subject(client, tenant_a):
    """A subject that only exists in stored grade docs (assignment later
    removed) must still appear — otherwise its grades become unreachable."""
    class_id = await _seed_class(tenant_a)
    teacher = await _seed_teacher_with_class(tenant_a, class_id)
    orphan = await _seed_subject(tenant_a, "مادة محذوفة التكليف")
    await _seed_grade_row(school_id=tenant_a, class_id=class_id,
                          student_id=str(uuid.uuid4()), column_id=str(uuid.uuid4()),
                          score=4, subject_id=orphan)

    r = await client.get(f"/class/{class_id}/subjects", headers=_headers(teacher))
    assert r.status_code == 200, r.text
    by_id = {s["id"]: s for s in r.json()["subjects"]}
    assert orphan in by_id
    assert by_id[orphan]["has_grades"] is True
    assert by_id[orphan]["name"] == "مادة محذوفة التكليف"
    # graded subjects sort first
    assert r.json()["subjects"][0]["id"] == orphan


@pytest.mark.asyncio
async def test_class_subjects_it_owner_single_subject(client):
    """IT single-subject class resolves exactly one subject via the
    teacher_assignments path (the classes table has no subject_id column,
    so the class-row fallback never fires for real rows)."""
    ctx = await mk_it_workspace()
    subj = await _seed_subject(ctx["wsid"], "مادة مستقلة")
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()),
        "school_id": ctx["wsid"],
        "teacher_id": ctx["teacher_id"],
        "class_id": ctx["class_id"],
        "subject_id": subj,
    })
    r = await client.get(
        f"/class/{ctx['class_id']}/subjects",
        headers=it_headers(ctx["uid"], ctx["user"]["role"], ctx["wsid"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    subs = body["subjects"]
    assert [s["id"] for s in subs] == [subj]
    assert subs[0]["name"] == "مادة مستقلة"
    assert body["default_subject_id"] == subj


@pytest.mark.asyncio
async def test_class_subjects_cross_workspace_404(client):
    host = await mk_it_workspace()
    stranger = await mk_it_workspace(with_class=False, with_student=False, with_parent=False)
    r = await client.get(
        f"/class/{host['class_id']}/subjects",
        headers=it_headers(stranger["uid"], stranger["user"]["role"], stranger["wsid"]),
    )
    assert r.status_code == 404
