"""
Teacher Assignments Service
Handles teacher-class assignments, teacher-subject assignments, default class auto-population,
syncing, and unassigned classes checks.
"""
from fastapi import HTTPException
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
import uuid
import logging
from sqlalchemy import delete as sa_delete, select, union

from engines.sql_utils import (
    gd_find, gd_find_one, gd_insert, gd_update_one, gd_update_many, gd_delete_one, gd_delete_many,
)
from src.modules.schools.dto.assignments_dto import (
    TeacherClassAssignmentCreate, TeacherSubjectAssignmentCreate
)
from src.common.utils.teacher_assignment_sync import (
    materialize_default_class_assignments,
    resolve_class_subject,
    class_subject_candidates,
    add_tombstone,
    clear_tombstones,
    add_class_tombstones,
)

logger = logging.getLogger("nassaq")

BULK_UNASSIGN_PAIR_LIMIT = 20_000
BULK_UNASSIGN_TIMETABLE_LIMIT = 20_000
BULK_REVIEW_CHUNK_SIZE = 500


class TeacherAssignmentsService:
    """Service handling teacher-class and teacher-subject assignment mappings."""

    @staticmethod
    async def auto_populate_teacher_class_assignments(school_id: str):
        """Materialize default 'all teachers ↔ all classes' links into canonical teacher_assignments."""
        return await materialize_default_class_assignments(school_id)

    @staticmethod
    async def ensure_teacher_linked_to_all_classes(school_id: str, teacher_id: str):
        """When a new teacher is created, materialize canonical class assignments."""
        if not school_id or not teacher_id:
            return
        try:
            await materialize_default_class_assignments(school_id, teacher_ids=[teacher_id])
        except Exception as e:
            logger.warning(f"_ensure_teacher_linked failed teacher={teacher_id}: {e}")

    @staticmethod
    async def ensure_class_linked_to_all_teachers(school_id: str, class_id: str):
        """When a new class is created, materialize canonical assignments."""
        if not school_id or not class_id:
            return
        try:
            await materialize_default_class_assignments(school_id, class_ids=[class_id])
        except Exception as e:
            logger.warning(f"_ensure_class_linked failed class={class_id}: {e}")

    @staticmethod
    async def get_teacher_class_assignments(
        session,
        current_user: dict,
        x_school_context: str = None,
        page: int = 1,
        page_size: int = 200,
        teacher_id: str = None,
        class_id: str = None,
    ) -> dict:
        from src.modules.schools.services.school_settings_service import resolve_school_context
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        created = await TeacherAssignmentsService.auto_populate_teacher_class_assignments(school_id)
        if created > 0:
            logger.info(f"Materialized {created} canonical teacher-class assignments for school {school_id}")

        ta_filter = {"school_id": school_id, "is_active": True}
        if teacher_id:
            ta_filter["teacher_id"] = teacher_id
        canonical = await gd_find(session, "teacher_assignments", ta_filter, limit=50000)

        pair_map: Dict[tuple, dict] = {}
        for a in canonical:
            cid = a.get("class_id")
            tid = a.get("teacher_id")
            if not cid or not tid:
                continue
            if class_id and cid != class_id:
                continue
            key = (tid, cid)
            if key not in pair_map:
                pair_map[key] = a

        t_ids = list({tid for tid, _ in pair_map.keys()})
        c_ids = list({cid for _, cid in pair_map.keys()})
        teachers_list = await gd_find(session, "teachers", {"id": {"$in": t_ids}}, limit=len(t_ids) + 1) if t_ids else []
        classes_list = await gd_find(session, "classes", {"id": {"$in": c_ids}, "is_active": {"$ne": False}}, limit=len(c_ids) + 1) if c_ids else []
        teacher_map = {t["id"]: t for t in teachers_list}
        class_map = {c["id"]: c for c in classes_list}

        rows = []
        for (tid, cid), a in pair_map.items():
            class_doc = class_map.get(cid)
            if not class_doc:
                continue
            teacher = teacher_map.get(tid)
            rows.append({
                "id": a.get("id"),
                "teacher_id": tid,
                "class_id": cid,
                "school_id": a.get("school_id"),
                "academic_year_id": a.get("academic_year_id"),
                "teacher_name": teacher.get("full_name") if teacher else None,
                "class_name": f"{class_doc.get('name', '')} - {class_doc.get('section', '')}",
                "auto_assigned": a.get("auto_assigned", False),
                "created_at": a.get("created_at"),
            })

        rows.sort(key=lambda r: (r.get("teacher_name") or "", r.get("class_name") or ""))
        total = len(rows)
        skip = (page - 1) * page_size
        paged = rows[skip:skip + page_size]

        return {
            "data": paged,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    @staticmethod
    async def create_teacher_class_assignment(
        session,
        assignment: TeacherClassAssignmentCreate,
        current_user: dict,
        x_school_context: str = None
    ) -> dict:
        from src.modules.schools.services.school_settings_service import resolve_school_context
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        teacher = await gd_find_one(session, "teachers", {"id": assignment.teacher_id, "school_id": school_id})
        if not teacher:
            raise HTTPException(status_code=404, detail="المعلم غير موجود في هذه المدرسة")
        class_doc = await gd_find_one(session, "classes", {"id": assignment.class_id, "school_id": school_id})
        if not class_doc:
            raise HTTPException(status_code=404, detail="الفصل غير موجود في هذه المدرسة")

        if assignment.subject_id:
            chosen = await gd_find_one(session, "subjects", {
                "id": assignment.subject_id,
                "$or": [{"school_id": school_id}, {"is_global": True}],
            })
            if not chosen or chosen.get("is_active") is False:
                raise HTTPException(status_code=404, detail="المادة غير موجودة في هذه المدرسة")
            subject_id, reason = assignment.subject_id, "explicit"
        else:
            subject_id, reason = await resolve_class_subject(session, school_id, teacher, class_doc)
        if not subject_id:
            if reason == "ambiguous":
                msg = "يدرّس هذا المعلم أكثر من مادة. يرجى اختيار المادة المناسبة لهذا الفصل."
            else:
                msg = "تعذّر تحديد مادة مناسبة لهذا المعلم في هذا الفصل تلقائيًا. يرجى اختيار المادة، أو إسنادها للمعلم من تبويب إسناد المواد."
            candidates = await class_subject_candidates(session, school_id, teacher, class_doc)
            raise HTTPException(status_code=409, detail={
                "code": "subject_required",
                "reason": reason,
                "message": msg,
                "teacher_id": assignment.teacher_id,
                "teacher_name": teacher.get("full_name"),
                "class_id": assignment.class_id,
                "class_name": class_doc.get("name"),
                "candidates": candidates,
            })

        existing = await gd_find_one(session, "teacher_assignments", {
            "school_id": school_id,
            "teacher_id": assignment.teacher_id,
            "class_id": assignment.class_id,
            "subject_id": subject_id,
            "is_active": True,
        })
        if existing:
            raise HTTPException(status_code=400, detail="هذا الإسناد موجود بالفعل")

        await clear_tombstones(session, school_id, assignment.teacher_id, class_id=assignment.class_id)

        subject = await gd_find_one(session, "subjects", {"id": subject_id})
        now = datetime.now(timezone.utc).isoformat()

        deactivated = await gd_find_one(session, "teacher_assignments", {
            "school_id": school_id,
            "teacher_id": assignment.teacher_id,
            "class_id": assignment.class_id,
            "subject_id": subject_id,
            "is_active": False,
        })
        if deactivated:
            await gd_update_one(session, "teacher_assignments", {"id": deactivated.get("id")},
                                {"is_active": True, "updated_at": now})
            new_id = deactivated.get("id")
        else:
            new_id = str(uuid.uuid4())
            await gd_insert(session, "teacher_assignments", {
                "id": new_id,
                "teacher_id": assignment.teacher_id,
                "class_id": assignment.class_id,
                "subject_id": subject_id,
                "school_id": school_id,
                "teacher_name": teacher.get("full_name"),
                "subject_name": (subject.get("name_ar") or subject.get("name")) if subject else None,
                "is_active": True,
                "created_at": now,
            })

        return {
            "message": "تم إنشاء الإسناد بنجاح",
            "assignment": {
                "id": new_id,
                "teacher_id": assignment.teacher_id,
                "class_id": assignment.class_id,
                "subject_id": subject_id,
                "school_id": school_id,
                "teacher_name": teacher.get("full_name") if teacher else None,
                "subject_name": (subject.get("name_ar") or subject.get("name")) if subject else None,
                "class_name": f"{class_doc.get('name', '')} - {class_doc.get('section', '')}" if class_doc else None,
                "created_at": now,
            }
        }

    @staticmethod
    async def delete_teacher_class_assignment(
        session,
        assignment_id: str,
        current_user: dict,
        x_school_context: str = None
    ) -> dict:
        from src.modules.schools.services.school_settings_service import resolve_school_context
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        teacher_id = None
        class_id = None
        canonical_row = await gd_find_one(session, "teacher_assignments", {"id": assignment_id, "school_id": school_id})
        if canonical_row:
            teacher_id = canonical_row.get("teacher_id")
            class_id = canonical_row.get("class_id")
        else:
            legacy = await gd_find_one(session, "teacher_class_assignments", {"id": assignment_id, "school_id": school_id})
            if legacy:
                teacher_id = legacy.get("teacher_id")
                class_id = legacy.get("class_id")

        if not teacher_id or not class_id:
            raise HTTPException(status_code=404, detail="الإسناد غير موجود")

        now = datetime.now(timezone.utc).isoformat()

        await gd_update_many(session, "teacher_assignments", {
            "school_id": school_id, "teacher_id": teacher_id, "class_id": class_id, "is_active": True,
        }, {"is_active": False, "updated_at": now})

        await add_tombstone(session, school_id, teacher_id, class_id, None,
                            created_by=current_user.get("id"))

        await gd_delete_many(session, "teacher_class_assignments", {
            "school_id": school_id, "teacher_id": teacher_id, "class_id": class_id,
        })

        flagged = 0
        try:
            published_tts = await gd_find(session, "timetables", {
                "school_id": school_id, "status": "published",
            }, limit=200)
            tt_ids = [t.get("id") for t in published_tts if t.get("id")]
            if tt_ids:
                flagged = await gd_update_many(session, "timetable_sessions", {
                    "timetable_id": {"$in": tt_ids}, "teacher_id": teacher_id, "class_id": class_id,
                }, {
                    "needs_review": True,
                    "review_reason": "unassigned_pairing",
                    "review_flagged_at": now,
                })
        except Exception as e:
            logger.warning(f"flag sessions on unassign failed teacher={teacher_id} class={class_id}: {e}")

        return {"message": "تم حذف الإسناد بنجاح", "flagged_sessions": flagged}

    @staticmethod
    async def bulk_unassign_class_assignments(
        session,
        current_user: dict,
        x_school_context: str = None,
        teacher_id: str = None,
    ) -> dict:
        """Deactivate every active class assignment in the school (or for one
        teacher) without deleting teachers, classes, or timetable history.

        This intentionally has no academic-year filter: the settings screen's
        active canonical links are school-wide.  All writes live in one
        savepoint because request middleware may commit even after an HTTP
        error; a failed tombstone/cleanup/review write must therefore undo the
        entire operation before the error escapes.
        """
        from src.modules.schools.services.school_settings_service import resolve_school_context

        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        if teacher_id:
            teacher = await gd_find_one(session, "teachers", {
                "id": teacher_id,
                "school_id": school_id,
                "is_active": {"$ne": False},
            })
            if not teacher:
                # Do not reveal whether a cross-school identifier exists.
                raise HTTPException(status_code=404, detail="المعلم غير موجود في هذه المدرسة")

        assignment_filter = {
            "school_id": school_id,
            "is_active": True,
            "class_id": {"$ne": None},
        }
        if teacher_id:
            assignment_filter["teacher_id"] = teacher_id

        async with session.begin_nested():
            # Project only the two keys needed for the operation. UNION makes
            # canonical/legacy duplicates one pair and LIMIT + 1 lets us reject
            # oversized requests explicitly rather than silently truncating.
            from pg_models import TeacherAssignment, TeacherClassAssignment, Timetable

            canonical_pairs = select(
                TeacherAssignment.teacher_id.label("teacher_id"),
                TeacherAssignment.class_id.label("class_id"),
            ).where(
                TeacherAssignment.school_id == school_id,
                TeacherAssignment.is_active.is_(True),
                TeacherAssignment.class_id.is_not(None),
            )
            legacy_pairs = select(
                TeacherClassAssignment.teacher_id.label("teacher_id"),
                TeacherClassAssignment.class_id.label("class_id"),
            ).where(
                TeacherClassAssignment.school_id == school_id,
                # The real legacy model has is_active. NULL historical rows
                # are treated as active; explicit False rows are history.
                TeacherClassAssignment.is_active.is_not(False),
            )
            if teacher_id:
                canonical_pairs = canonical_pairs.where(
                    TeacherAssignment.teacher_id == teacher_id
                )
                legacy_pairs = legacy_pairs.where(
                    TeacherClassAssignment.teacher_id == teacher_id
                )
            pair_result = await session.execute(
                union(canonical_pairs, legacy_pairs).limit(
                    BULK_UNASSIGN_PAIR_LIMIT + 1
                )
            )
            pair_rows = pair_result.all()
            if len(pair_rows) > BULK_UNASSIGN_PAIR_LIMIT:
                raise HTTPException(status_code=409, detail={
                    "code": "bulk_unassign_limit_exceeded",
                    "message": "عدد الإسنادات يتجاوز الحد الآمن للعملية",
                    "limit": BULK_UNASSIGN_PAIR_LIMIT,
                })
            pairs = {(row.teacher_id, row.class_id) for row in pair_rows}

            timetable_ids = []
            if pairs:
                timetable_stmt = select(Timetable.id).where(
                    Timetable.school_id == school_id,
                    Timetable.status == "published",
                ).limit(BULK_UNASSIGN_TIMETABLE_LIMIT + 1)
                published_result = await session.execute(timetable_stmt)
                timetable_ids = list(published_result.scalars().all())
                if len(timetable_ids) > BULK_UNASSIGN_TIMETABLE_LIMIT:
                    raise HTTPException(status_code=409, detail={
                        "code": "bulk_unassign_timetable_limit_exceeded",
                        "message": "عدد الجداول المنشورة يتجاوز الحد الآمن للعملية",
                        "limit": BULK_UNASSIGN_TIMETABLE_LIMIT,
                    })

            now = datetime.now(timezone.utc).isoformat()

            deactivated_rows = 0
            legacy_deleted = 0
            tombstones_created = 0
            flagged_sessions = 0
            if pairs:
                deactivated_rows = await gd_update_many(
                    session, "teacher_assignments", assignment_filter,
                    {"is_active": False, "updated_at": now},
                )

                tombstones_created = await add_class_tombstones(
                    session,
                    school_id,
                    pairs,
                    created_by=current_user.get("id"),
                    created_at=now,
                )

                legacy_delete = sa_delete(TeacherClassAssignment).where(
                    TeacherClassAssignment.school_id == school_id,
                    TeacherClassAssignment.is_active.is_not(False),
                )
                if teacher_id:
                    legacy_delete = legacy_delete.where(
                        TeacherClassAssignment.teacher_id == teacher_id
                    )
                legacy_result = await session.execute(legacy_delete)
                legacy_deleted = legacy_result.rowcount or 0

                if timetable_ids:
                    sorted_pairs = sorted(pairs)
                    for offset in range(0, len(sorted_pairs), BULK_REVIEW_CHUNK_SIZE):
                        pair_chunk = sorted_pairs[
                            offset:offset + BULK_REVIEW_CHUNK_SIZE
                        ]
                        session_filter = {
                            "timetable_id": {"$in": timetable_ids},
                            "$or": [
                                {
                                    "teacher_id": pair_teacher,
                                    "class_id": pair_class,
                                }
                                for pair_teacher, pair_class in pair_chunk
                            ],
                        }
                        flagged_sessions += await gd_update_many(
                            session, "timetable_sessions", session_filter, {
                                "needs_review": True,
                                "review_reason": "unassigned_pairing",
                                "review_flagged_at": now,
                            },
                        )

        affected_teachers = {tid for tid, _ in pairs}
        affected_classes = {cid for _, cid in pairs}
        return {
            "success": True,
            "unassigned_count": len(pairs),
            "deactivated_rows": deactivated_rows,
            "teachers_affected": len(affected_teachers),
            "classes_affected": len(affected_classes),
            "tombstones_created": tombstones_created,
            "legacy_rows_deleted": legacy_deleted,
            "flagged_sessions": flagged_sessions,
        }

    @staticmethod
    async def get_classes_without_teachers(session, current_user: dict, x_school_context: str = None) -> dict:
        from src.modules.schools.services.school_settings_service import resolve_school_context
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        all_classes = await gd_find(session, "classes", {"school_id": school_id, "is_active": {"$ne": False}}, limit=500)
        canonical_links = await gd_find(
            session, "teacher_assignments",
            {"school_id": school_id, "is_active": True}, limit=50000,
        )
        assigned_class_ids = {a.get("class_id") for a in canonical_links if a.get("class_id")}

        unassigned = []
        for c in all_classes:
            if c.get("id") not in assigned_class_ids:
                unassigned.append({
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "section": c.get("section"),
                    "grade_id": c.get("grade_id")
                })

        return {
            "count": len(unassigned),
            "classes": unassigned
        }

    @staticmethod
    async def get_teacher_subject_assignments(
        session,
        teacher_id: Optional[str],
        subject_id: Optional[str],
        current_user: dict,
        x_school_context: str = None
    ) -> list:
        from src.modules.schools.services.school_settings_service import resolve_school_context
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        query = {"school_id": school_id, "is_active": True}
        if teacher_id:
            query["teacher_id"] = teacher_id
        if subject_id:
            query["subject_id"] = subject_id

        assignments = await gd_find(session, "teacher_assignments", query, limit=50000)
        unique_pairs: Dict[Tuple[str, str], dict] = {}
        for a in assignments:
            tid = a.get("teacher_id")
            sid = a.get("subject_id")
            if not tid or not sid:
                continue
            pair_key = (tid, sid)
            if pair_key not in unique_pairs:
                unique_pairs[pair_key] = a

        t_ids = list({tid for tid, _ in unique_pairs.keys()})
        s_ids = list({sid for _, sid in unique_pairs.keys()})
        teachers = await gd_find(session, "teachers", {"id": {"$in": t_ids}}, limit=len(t_ids) + 1) if t_ids else []
        subjects = await gd_find(session, "subjects", {"id": {"$in": s_ids}}, limit=len(s_ids) + 1) if s_ids else []
        teacher_map = {t["id"]: t for t in teachers}
        subject_map = {s["id"]: s for s in subjects}

        result = []
        for (tid, sid), a in unique_pairs.items():
            t = teacher_map.get(tid)
            s = subject_map.get(sid)
            result.append({
                "id": a.get("id"),
                "teacher_id": tid,
                "subject_id": sid,
                "school_id": a.get("school_id"),
                "teacher_name": (t.get("full_name") if t else None) or a.get("teacher_name"),
                "subject_name": ((s.get("name_ar") or s.get("name")) if s else None) or a.get("subject_name"),
                "created_at": a.get("created_at"),
            })
        return result

    @staticmethod
    async def create_teacher_subject_assignment(
        session,
        payload: TeacherSubjectAssignmentCreate,
        current_user: dict,
        x_school_context: str = None
    ) -> dict:
        from src.modules.schools.services.school_settings_service import resolve_school_context
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        teacher = await gd_find_one(session, "teachers", {"id": payload.teacher_id, "school_id": school_id})
        if not teacher:
            raise HTTPException(status_code=404, detail="المعلم غير موجود في هذه المدرسة")
        subject = await gd_find_one(session, "subjects", {
            "id": payload.subject_id,
            "$or": [{"school_id": school_id}, {"is_global": True}],
        })
        if not subject:
            raise HTTPException(status_code=404, detail="المادة غير موجودة في هذه المدرسة")

        existing = await gd_find_one(session, "teacher_assignments", {
            "school_id": school_id,
            "teacher_id": payload.teacher_id,
            "subject_id": payload.subject_id,
            "is_active": True,
        })
        if existing:
            return {
                "message": "هذا الإسناد موجود بالفعل",
                "assignment": {
                    "id": existing.get("id"),
                    "teacher_id": existing.get("teacher_id"),
                    "subject_id": existing.get("subject_id"),
                    "school_id": existing.get("school_id"),
                },
            }

        new_assignment = {
            "id": str(uuid.uuid4()),
            "teacher_id": payload.teacher_id,
            "subject_id": payload.subject_id,
            "school_id": school_id,
            "teacher_name": teacher.get("full_name") if teacher else None,
            "subject_name": (subject.get("name_ar") or subject.get("name")) if subject else None,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(session, "teacher_assignments", new_assignment)

        return {
            "message": "تم إنشاء الإسناد بنجاح",
            "assignment": new_assignment,
        }

    @staticmethod
    async def delete_teacher_subject_assignment(
        session,
        assignment_id: str,
        current_user: dict,
        x_school_context: str = None
    ) -> dict:
        from src.modules.schools.services.school_settings_service import resolve_school_context
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        result = await gd_delete_one(session, "teacher_assignments", {
            "id": assignment_id,
            "school_id": school_id,
        })
        if result == 0:
            raise HTTPException(status_code=404, detail="الإسناد غير موجود")
        return {"message": "تم حذف الإسناد بنجاح"}

    @staticmethod
    async def get_teacher_assigned_classes(
        session,
        teacher_id: str,
        current_user: dict,
        x_school_context: str = None
    ) -> list:
        from src.modules.schools.services.school_settings_service import resolve_school_context
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        assignments = await gd_find(session, "teacher_assignments", {
            "school_id": school_id,
            "teacher_id": teacher_id,
            "is_active": True,
        }, limit=2000)

        per_class: Dict[str, dict] = {}
        for a in assignments:
            cid = a.get("class_id")
            if cid and cid not in per_class:
                per_class[cid] = a

        class_ids = list(per_class.keys())
        classes_docs = await gd_find(session, "classes", {"id": {"$in": class_ids}, "is_active": {"$ne": False}}, limit=500) if class_ids else []
        class_map = {c["id"]: c for c in classes_docs}

        result = []
        for cid, assignment in per_class.items():
            class_doc = class_map.get(cid)
            if class_doc:
                result.append({
                    "id": assignment.get("id"),
                    "class_id": cid,
                    "class_name": class_doc.get("name"),
                    "section": class_doc.get("section"),
                    "grade_id": class_doc.get("grade_id")
                })
        return result
