"""Regression for the assign → unassign → reassign lifecycle of the
drag-and-drop teacher↔class assignment (School Schedule Settings → إسناد
الفصول).

Production bug: after unassigning a (teacher, class) pairing, re-dragging the
same class onto the same teacher returned the 409 "subject_required" error
("تعذّر تحديد مادة مناسبة...") even though the pairing had a valid subject
before. Cause: the grade curriculum was empty and the subject pool was
polluted by unrelated subjects harvested from the teacher's OTHER active
assignment rows, so the single-subject fallback never fired — and the
deactivated row that still held the previously valid subject was ignored.

This exercises the real route handlers end-to-end:
    POST   /teacher-class-assignments   (create_teacher_class_assignment)
    DELETE /teacher-class-assignments/{id} (delete_teacher_class_assignment)
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from dependencies import db
from engines.sql_utils import gd_find, gd_find_one, gd_insert
from src.modules.schools.controllers.school_settings_mod import (
    TeacherClassAssignmentCreate,
    create_teacher_class_assignment,
    delete_teacher_class_assignment,
    TeacherSubjectAssignmentCreate,
    create_teacher_subject_assignment,
    delete_teacher_subject_assignment,
)
from src.common.utils.teacher_assignment_sync import load_tombstones


def _principal(school_id: str) -> dict:
    return {"id": "principal", "tenant_id": school_id, "role": "school_principal"}


async def _mk_subject(school_id: str, name: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid, "school_id": school_id, "name": name, "name_ar": name,
        "is_active": True,
    })
    return sid


async def _mk_teacher(school_id: str, subject_name: str) -> str:
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid, "school_id": school_id, "full_name": f"T-{tid[:6]}",
        "subject": subject_name, "specialization": subject_name,
        "is_active": True,
    })
    return tid


async def _mk_class(school_id: str, name: str = "1A") -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": school_id, "name": name, "is_active": True,
    })
    return cid


async def _mk_ta(school_id: str, teacher_id: str, class_id: str, subject_id: str):
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()), "school_id": school_id,
        "teacher_id": teacher_id, "class_id": class_id,
        "subject_id": subject_id, "is_active": True,
    })


async def _assign(school_id: str, teacher_id: str, class_id: str) -> dict:
    return await create_teacher_class_assignment(
        assignment=TeacherClassAssignmentCreate(teacher_id=teacher_id, class_id=class_id),
        current_user=_principal(school_id),
        x_school_context=None,
    )


async def _unassign(school_id: str, assignment_id: str) -> dict:
    return await delete_teacher_class_assignment(
        assignment_id=assignment_id,
        current_user=_principal(school_id),
        x_school_context=None,
    )


async def _active_pair_rows(school_id: str, teacher_id: str, class_id: str):
    rows = await gd_find(db.session, "teacher_assignments", {
        "school_id": school_id, "teacher_id": teacher_id, "class_id": class_id,
    }, limit=50)
    return [r for r in rows if r.get("is_active") is not False]


@pytest.mark.asyncio
async def test_assign_unassign_reassign_lifecycle(tenant_a):
    """The exact production scenario: empty curriculum, teacher whose active
    rows span several subjects. Reassigning the same class must succeed and
    restore the previously valid subject."""
    s_hist = await _mk_subject(tenant_a, "التاريخ")
    s_math = await _mk_subject(tenant_a, "الرياضيات")
    s_sci = await _mk_subject(tenant_a, "العلوم")
    teacher = await _mk_teacher(tenant_a, "التاريخ")
    c_target = await _mk_class(tenant_a, "10A")
    c_o1, c_o2 = await _mk_class(tenant_a, "11A"), await _mk_class(tenant_a, "12A")
    # Polluted pool: unrelated subjects on the teacher's other active rows
    # (mirrors auto-materialized / imported links in production).
    await _mk_ta(tenant_a, teacher, c_o1, s_math)
    await _mk_ta(tenant_a, teacher, c_o2, s_sci)

    # 1) Assign — resolves the teacher's own subject despite the polluted pool.
    resp = await _assign(tenant_a, teacher, c_target)
    assignment = resp["assignment"]
    assert assignment["subject_id"] == s_hist

    # 2) Unassign — deactivates the pair and records a tombstone.
    await _unassign(tenant_a, assignment["id"])
    assert await _active_pair_rows(tenant_a, teacher, c_target) == []
    tombs = await load_tombstones(db.session, tenant_a, teacher)
    assert any(t.get("class_id") == c_target for t in tombs)

    # 3) Reassign the SAME pair — must NOT raise 409 subject_required; must
    #    restore the same subject and clear the tombstone.
    resp2 = await _assign(tenant_a, teacher, c_target)
    assert resp2["assignment"]["subject_id"] == s_hist
    active = await _active_pair_rows(tenant_a, teacher, c_target)
    assert len(active) == 1
    tombs_after = await load_tombstones(db.session, tenant_a, teacher)
    assert not any(t.get("class_id") == c_target for t in tombs_after)


@pytest.mark.asyncio
async def test_reassign_reuses_prior_subject_even_without_doc_subject(tenant_a):
    """Teacher record carries NO resolvable subject of its own — the prior
    deactivated row is the only evidence, and it must be enough."""
    s1 = await _mk_subject(tenant_a, "الجغرافيا")
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid, "school_id": tenant_a, "full_name": "بدون تخصص", "is_active": True,
    })
    cid = await _mk_class(tenant_a)
    # Prior (now deactivated) canonical row for the pair.
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()), "school_id": tenant_a,
        "teacher_id": tid, "class_id": cid, "subject_id": s1, "is_active": False,
    })

    resp = await _assign(tenant_a, tid, cid)
    assert resp["assignment"]["subject_id"] == s1
    active = await _active_pair_rows(tenant_a, tid, cid)
    assert len(active) == 1


@pytest.mark.asyncio
async def test_assign_still_409s_when_truly_unresolvable(tenant_a):
    """Validation stays accurate: a teacher with no subject evidence at all
    must still get the structured subject_required 409."""
    await _mk_subject(tenant_a, "الفيزياء")
    await _mk_subject(tenant_a, "الكيمياء")
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid, "school_id": tenant_a, "full_name": "بدون مواد", "is_active": True,
    })
    cid = await _mk_class(tenant_a)

    with pytest.raises(HTTPException) as exc:
        await _assign(tenant_a, tid, cid)
    assert exc.value.status_code == 409
    assert exc.value.detail.get("code") == "subject_required"


@pytest.mark.asyncio
async def test_assign_matches_specialization_without_definite_article(tenant_a):
    """Reported production bug: the teacher's specialization is "رياضيات" while
    the school's subject is named "الرياضيات" and the grade has no curriculum.
    Exact-name matching found nothing → false 409. Normalized matching must
    resolve it and assign the class."""
    s_math = await _mk_subject(tenant_a, "الرياضيات")
    await _mk_subject(tenant_a, "رياضيات اختبار")  # near-miss must not collide
    teacher = await _mk_teacher(tenant_a, "رياضيات")
    cid = await _mk_class(tenant_a, "صف اختبار ٢")

    resp = await _assign(tenant_a, teacher, cid)
    assert resp["assignment"]["subject_id"] == s_math
    assert len(await _active_pair_rows(tenant_a, teacher, cid)) == 1


@pytest.mark.asyncio
async def test_assign_offers_candidates_then_accepts_explicit_subject(tenant_a):
    """Teacher teaches two subjects and the grade has no curriculum: the 409
    must carry the candidate subjects (so the UI can ask) and the retry with an
    explicit subject_id must persist exactly that subject."""
    s_math = await _mk_subject(tenant_a, "الرياضيات")
    s_sci = await _mk_subject(tenant_a, "العلوم")
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid, "school_id": tenant_a, "full_name": "معلم متعدد المواد", "is_active": True,
    })
    c_other = await _mk_class(tenant_a, "9A")
    c_target = await _mk_class(tenant_a, "9B")
    # Principal assigned BOTH subjects to the teacher (إسناد المواد).
    await _mk_ta(tenant_a, tid, c_other, s_math)
    await _mk_ta(tenant_a, tid, c_other, s_sci)

    with pytest.raises(HTTPException) as exc:
        await _assign(tenant_a, tid, c_target)
    detail = exc.value.detail
    assert exc.value.status_code == 409
    assert detail["code"] == "subject_required"
    assert detail["reason"] == "ambiguous"
    assert {c["id"] for c in detail["candidates"]} == {s_math, s_sci}

    resp = await create_teacher_class_assignment(
        assignment=TeacherClassAssignmentCreate(
            teacher_id=tid, class_id=c_target, subject_id=s_sci),
        current_user=_principal(tenant_a),
        x_school_context=None,
    )
    assert resp["assignment"]["subject_id"] == s_sci
    rows = await _active_pair_rows(tenant_a, tid, c_target)
    assert [r["subject_id"] for r in rows] == [s_sci]


@pytest.mark.asyncio
async def test_explicit_subject_from_another_school_rejected(tenant_a, tenant_b):
    """The explicit choice is still validated against the caller's school."""
    foreign_subject = await _mk_subject(tenant_b, "مادة خارجية")
    teacher = await _mk_teacher(tenant_a, "التاريخ")
    await _mk_subject(tenant_a, "التاريخ")
    cid = await _mk_class(tenant_a)

    with pytest.raises(HTTPException) as exc:
        await create_teacher_class_assignment(
            assignment=TeacherClassAssignmentCreate(
                teacher_id=teacher, class_id=cid, subject_id=foreign_subject),
            current_user=_principal(tenant_a),
            x_school_context=None,
        )
    assert exc.value.status_code == 404
    assert await _active_pair_rows(tenant_a, teacher, cid) == []


@pytest.mark.asyncio
async def test_unresolvable_409_still_lists_school_subjects(tenant_a):
    """No subject evidence at all: still a 409, but never a dead end — the
    principal gets the school catalogue to choose from."""
    s1 = await _mk_subject(tenant_a, "الفيزياء")
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid, "school_id": tenant_a, "full_name": "بدون مواد", "is_active": True,
    })
    cid = await _mk_class(tenant_a)

    with pytest.raises(HTTPException) as exc:
        await _assign(tenant_a, tid, cid)
    assert exc.value.status_code == 409
    assert s1 in {c["id"] for c in exc.value.detail["candidates"]}


@pytest.mark.asyncio
async def test_duplicate_assign_rejected(tenant_a):
    s1 = await _mk_subject(tenant_a, "الأحياء")
    teacher = await _mk_teacher(tenant_a, "الأحياء")
    cid = await _mk_class(tenant_a)
    resp = await _assign(tenant_a, teacher, cid)
    assert resp["assignment"]["subject_id"] == s1

    with pytest.raises(HTTPException) as exc:
        await _assign(tenant_a, teacher, cid)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_delete_teacher_subject_assignment_success_and_not_found(tenant_a):
    sid = await _mk_subject(tenant_a, "الكيمياء")
    tid = await _mk_teacher(tenant_a, "الكيمياء")

    create_resp = await create_teacher_subject_assignment(
        payload=TeacherSubjectAssignmentCreate(teacher_id=tid, subject_id=sid),
        current_user=_principal(tenant_a),
        x_school_context=None,
    )
    assignment_id = create_resp["assignment"]["id"]

    del_resp = await delete_teacher_subject_assignment(
        assignment_id=assignment_id,
        current_user=_principal(tenant_a),
        x_school_context=None,
    )
    assert del_resp["message"] == "تم حذف الإسناد بنجاح"

    # Confirm row is deleted
    found = await gd_find_one(db.session, "teacher_assignments", {"id": assignment_id})
    assert found is None

    # Deleting again should raise 404
    with pytest.raises(HTTPException) as exc:
        await delete_teacher_subject_assignment(
            assignment_id=assignment_id,
            current_user=_principal(tenant_a),
            x_school_context=None,
        )
    assert exc.value.status_code == 404

