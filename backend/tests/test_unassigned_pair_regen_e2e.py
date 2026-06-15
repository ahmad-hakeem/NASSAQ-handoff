"""End-to-end regression for the Task #919 "unassigned pairing stays
unassigned after regeneration" guarantee.

The unit tests in ``test_teacher_assignment_sync.py`` cover the tombstone util,
subject resolution, and the reconciler in isolation. This module exercises the
FULL loop with the real scheduling engine and the real unassign route:

    seed a real (non-itw_) school
      -> materialize default (teacher, class, subject) assignments
      -> generate_timetable + publish it
      -> unassign one (teacher, class) pairing (the production DELETE route:
         tombstone + deactivate canonical row + flag published sessions)
      -> generate_timetable again

and asserts the two halves of the guarantee:

  1. The scheduler does NOT re-place the tombstoned (teacher, class, subject)
     in the new draft — even though the teacher's ``primary_subject_id`` still
     matches the subject (the suitable-teachers fallback would otherwise pull
     them back in; the tombstone filter must win).
  2. The previously-published sessions for that pairing are kept and remain
     flagged ``needs_review=True`` / ``review_reason="unassigned_pairing"``.

The seed deliberately makes the tombstoned teacher the ONLY teacher able to
teach the subject, so an empty ``suitable_teachers`` is the unambiguous signal
that the tombstone took effect (the subject simply cannot be scheduled).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from dependencies import db
from engines.smart_scheduling_engine import SmartSchedulingEngine
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one
from routes.school_settings_mod import delete_teacher_class_assignment
from utils.teacher_assignment_sync import materialize_default_class_assignments


async def _mk_time_slot(school_id: str, period_number: int) -> None:
    await gd_insert(db.session, "time_slots", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "name": f"Period {period_number}",
        "slot_number": period_number,
        "period_number": period_number,
        "start_time": f"{6 + period_number:02d}:00",
        "end_time": f"{7 + period_number:02d}:00",
        "duration_minutes": 45,
        "is_break": False,
        "is_active": True,
    })


async def _seed_two_subject_school(school_id: str) -> dict:
    """Seed the minimum data set ``generate_timetable`` needs, with one class
    and two single-subject teachers (Math/Arabic). Each teacher is the ONLY
    teacher of their subject, so tombstoning one pairing leaves that subject
    with no suitable teacher.
    """
    now = datetime.now(timezone.utc).isoformat()

    await gd_insert(db.session, "school_settings", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "working_days": ["sunday", "monday", "tuesday", "wednesday", "thursday"],
        "periods_per_day": 5,
    })
    for n in range(1, 6):
        await _mk_time_slot(school_id, n)

    ay_id = str(uuid.uuid4())
    await gd_insert(db.session, "academic_years", {
        "id": ay_id,
        "school_id": school_id,
        "name": "2026-2027",
        "name_ar": "2026-2027",
        "start_date": "2026-09-01",
        "end_date": "2027-06-30",
        "is_current": True,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })
    await gd_insert(db.session, "academic_terms", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "academic_year_id": ay_id,
        "name": "Term 1",
        "is_active": True,
        "is_current": True,
    })

    grade_id = str(uuid.uuid4())
    await gd_insert(db.session, "grade_levels", {
        "id": grade_id,
        "school_id": school_id,
        "name": "G1",
        "code": "1",
        "is_active": True,
    })
    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id,
        "school_id": school_id,
        "name": "1A",
        "grade_id": grade_id,
        "is_active": True,
    })

    subj_math = str(uuid.uuid4())
    subj_arabic = str(uuid.uuid4())
    teach_math = str(uuid.uuid4())
    teach_arabic = str(uuid.uuid4())
    for sid, name, tid in (
        (subj_math, "Math", teach_math),
        (subj_arabic, "Arabic", teach_arabic),
    ):
        await gd_insert(db.session, "subjects", {
            "id": sid, "school_id": school_id, "name": name, "name_ar": name,
            "is_active": True,
        })
        await gd_insert(db.session, "grade_subjects", {
            "id": str(uuid.uuid4()),
            "school_id": school_id,
            "grade_id": grade_id,
            "subject_id": sid,
            "weekly_periods": 5,
            "is_active": True,
        })
        # Each teacher teaches exactly one subject (single overlap → resolves
        # cleanly during default materialization). The subject is bound via the
        # ``subject`` text column (the only persisted teacher→subject hint on the
        # teachers table — ``primary_subject_id`` is not a column), which the
        # name index resolves back to the subject id.
        await gd_insert(db.session, "teachers", {
            "id": tid,
            "school_id": school_id,
            "full_name": f"T-{tid[:6]}",
            "weekly_periods": 10,
            "subject": name,
            "is_active": True,
        })

    return {
        "class_id": class_id,
        "grade_id": grade_id,
        "subj_math": subj_math,
        "subj_arabic": subj_arabic,
        "teach_math": teach_math,
        "teach_arabic": teach_arabic,
    }


async def _generate(school_id: str) -> object:
    engine = SmartSchedulingEngine(db)
    return await engine.generate_timetable(
        school_id=school_id,
        created_by="test",
        calling_user={"id": "test", "tenant_id": school_id, "role": "school_principal"},
    )


async def test_unassigned_pair_stays_unassigned_after_regeneration(tenant_a):
    ids = await _seed_two_subject_school(tenant_a)
    class_id = ids["class_id"]
    subj_math, teach_math = ids["subj_math"], ids["teach_math"]
    subj_arabic, teach_arabic = ids["subj_arabic"], ids["teach_arabic"]
    await db.session.commit()

    # 1) Materialize the default (teacher, class, subject) assignments.
    created = await materialize_default_class_assignments(tenant_a)
    assert created == 2, f"expected 2 default assignments, got {created}"
    canonical = await gd_find(
        db.session, "teacher_assignments",
        {"school_id": tenant_a, "is_active": True}, limit=100,
    )
    pairs = {(a.get("teacher_id"), a.get("class_id"), a.get("subject_id")) for a in canonical}
    assert (teach_math, class_id, subj_math) in pairs
    assert (teach_arabic, class_id, subj_arabic) in pairs

    # 2) Generate the first timetable and publish it.
    result1 = await _generate(tenant_a)
    assert result1.success, f"first generation failed: {result1.message_en}"
    await db.session.commit()

    published_tt = await gd_find_one(
        db.session, "timetables", {"school_id": tenant_a, "status": "draft"},
    )
    assert published_tt, "first generation produced no draft timetable"
    published_tt_id = published_tt["id"]

    math_sessions_v1 = await gd_find(
        db.session, "timetable_sessions",
        {"timetable_id": published_tt_id, "class_id": class_id, "subject_id": subj_math},
        limit=500,
    )
    assert math_sessions_v1, "the Math pairing must be scheduled before it is unassigned"

    await gd_update_one(
        db.session, "timetables", {"id": published_tt_id},
        {"status": "published"},
    )
    await db.session.commit()

    # 3) Unassign (teach_math, class) via the production DELETE route. This
    #    tombstones the pairing, deactivates the canonical row, and flags the
    #    already-published sessions for review.
    math_assignment = await gd_find_one(
        db.session, "teacher_assignments",
        {"school_id": tenant_a, "teacher_id": teach_math, "class_id": class_id, "is_active": True},
    )
    assert math_assignment, "Math canonical assignment not found"
    resp = await delete_teacher_class_assignment(
        assignment_id=math_assignment["id"],
        current_user={"id": "principal", "tenant_id": tenant_a, "role": "school_principal"},
        x_school_context=None,
    )
    assert resp.get("flagged_sessions", 0) == len(math_sessions_v1), (
        f"unassign must flag the {len(math_sessions_v1)} published Math sessions; "
        f"got {resp.get('flagged_sessions')}"
    )
    await db.session.commit()

    # 4) Regenerate. The scheduler must NOT re-place the tombstoned pairing.
    result2 = await _generate(tenant_a)
    assert result2.success, f"second generation failed: {result2.message_en}"
    await db.session.commit()

    new_draft = await gd_find_one(
        db.session, "timetables", {"school_id": tenant_a, "status": "draft"},
    )
    assert new_draft, "second generation produced no draft timetable"
    new_draft_id = new_draft["id"]
    assert new_draft_id != published_tt_id, "regeneration must build a fresh draft"

    new_sessions = await gd_find(
        db.session, "timetable_sessions", {"timetable_id": new_draft_id}, limit=1000,
    )
    # (1) No new session for the tombstoned (teacher, class, subject).
    assert not any(
        s.get("class_id") == class_id and s.get("subject_id") == subj_math
        for s in new_sessions
    ), "tombstoned Math pairing was re-scheduled in the regenerated draft"
    assert not any(
        s.get("teacher_id") == teach_math for s in new_sessions
    ), "tombstoned teacher was re-scheduled despite the removal"
    # The untombstoned Arabic pairing must still schedule normally.
    assert any(
        s.get("class_id") == class_id and s.get("subject_id") == subj_arabic
        and s.get("teacher_id") == teach_arabic
        for s in new_sessions
    ), "the un-removed Arabic pairing must still be scheduled after regeneration"

    # (2) The previously-published sessions are kept and remain flagged.
    kept = await gd_find(
        db.session, "timetable_sessions",
        {"timetable_id": published_tt_id, "class_id": class_id, "subject_id": subj_math},
        limit=500,
    )
    assert len(kept) == len(math_sessions_v1), (
        "published Math sessions must be kept (not deleted) after unassign+regen"
    )
    assert kept, "published Math sessions disappeared"
    for s in kept:
        assert s.get("needs_review") is True, (
            f"published session {s.get('id')} lost its needs_review flag"
        )
        assert s.get("review_reason") == "unassigned_pairing", (
            f"published session {s.get('id')} has wrong review_reason: {s.get('review_reason')}"
        )
