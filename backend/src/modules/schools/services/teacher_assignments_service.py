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

from engines.sql_utils import (
    gd_find, gd_find_one, gd_insert, gd_update_one, gd_update_many, gd_delete_many,
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
)

logger = logging.getLogger("nassaq")


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
