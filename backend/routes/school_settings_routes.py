"""
School Settings Routes - مسارات إعدادات المدرسة
Single source of truth for school configuration and official curriculum
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
import logging
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate

logger = logging.getLogger("nassaq.school_settings")


class SchoolSettingsUpdate(BaseModel):
    academic_year: Optional[str] = None
    current_semester: Optional[str] = None
    working_days: Optional[Dict[str, bool]] = None
    periods_per_day: Optional[int] = None
    period_duration: Optional[int] = None
    school_day_start: Optional[str] = None
    school_day_end: Optional[str] = None
    break_duration: Optional[int] = None
    prayer_time: Optional[str] = None
    break_after_period: Optional[int] = None
    prayer_after_period: Optional[int] = None
    preferred_subjects_morning: Optional[List[str]] = None
    avoid_same_subject_consecutive: Optional[bool] = None
    distribute_subjects_evenly: Optional[bool] = None


class ConstraintCreate(BaseModel):
    constraint_type: str
    name_ar: str
    description_ar: Optional[str] = None
    applies_to: str  # "school" | "teacher" | "class"
    applies_to_id: Optional[str] = None
    rule: Dict[str, Any]
    is_active: bool = True


class ConstraintUpdate(BaseModel):
    name_ar: Optional[str] = None
    description_ar: Optional[str] = None
    rule: Optional[Dict[str, Any]] = None


class ConstraintStatusPatch(BaseModel):
    is_active: bool


def setup_school_settings_routes(db, get_current_user, require_roles, UserRole):
    router = APIRouter(prefix="/school", tags=["School Settings"])

    async def get_school_id_from_user(current_user: dict) -> str:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        if not school_id:
            raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")
        return school_id

    async def log_audit(school_id: str, user: dict, action: str, entity: str, entity_id: str, changes: dict = None):
        try:
            await gd_insert(db.session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "school_id": school_id,
                "user_id": user.get("id"),
                "user_email": user.get("email"),
                "user_role": user.get("role"),
                "action": action,
                "entity_type": entity,
                "entity_id": entity_id,
                "changes": changes or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ip_address": "",
            })
        except Exception as e:
            logger.warning(f"Failed to write audit log for {action} on {entity}/{entity_id}: {e}")

    # ============ SCHOOL SETTINGS ============

    @router.get("/settings")
    async def get_school_settings(
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL,
            UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_OPERATIONS_MANAGER
        ]))
    ):
        school_id = await get_school_id_from_user(current_user)
        
        # Get school info
        school = await gd_find_one(db.session, "schools", {"id": school_id})
        if not school:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")
        
        # Get settings
        settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
        if not settings:
            settings = {
                "school_id": school_id,
                "academic_year": "2024-2025",
                "current_semester": "first",
                "working_days": {"sunday": True, "monday": True, "tuesday": True, "wednesday": True, "thursday": True, "friday": False, "saturday": False},
                "periods_per_day": 7,
                "period_duration": 45,
                "school_day_start": "07:00",
                "school_day_end": "13:15",
                "break_duration": 15,
                "prayer_time": "12:00",
                "break_after_period": 4,
                "prayer_after_period": 6,
            }
        
        # Get academic years
        academic_years = await gd_find(db.session, "academic_years", {"school_id": school_id}, limit=20)
        academic_terms = await gd_find(db.session, "academic_terms", {"school_id": school_id}, limit=20)
        
        # Get stages/grades/classes
        stages = await gd_find(db.session, "academic_stages", {"school_id": school_id}, limit=20)
        grades = await gd_find(db.session, "grades", {"school_id": school_id}, limit=50)
        classes = await gd_find(db.session, "classes", {"school_id": school_id, "is_active": {"$ne": False}}, limit=200)
        
        # Get teachers
        teachers = await gd_find(db.session, "teachers", {"school_id": school_id}, limit=100)
        
        # Get subjects
        subjects = await gd_find(db.session, "subjects", {"school_id": school_id}, limit=50)
        
        # Get teacher assignments
        teacher_assignments = await gd_find(db.session, "teacher_assignments", {"school_id": school_id}, limit=500)
        
        return {
            "school": school,
            "settings": settings,
            "academic_years": academic_years,
            "academic_terms": academic_terms,
            "stages": stages,
            "grades": grades,
            "classes": classes,
            "teachers": teachers,
            "subjects": subjects,
            "teacher_assignments": teacher_assignments,
        }

    @router.put("/settings")
    async def update_school_settings(
        update: SchoolSettingsUpdate,
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
        ]))
    ):
        school_id = await get_school_id_from_user(current_user)
        now = datetime.now(timezone.utc).isoformat()
        
        update_data = {k: v for k, v in update.dict().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="لا توجد بيانات للتحديث")
        
        update_data["updated_at"] = now
        update_data["updated_by"] = current_user.get("email")
        
        existing = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
        if existing:
            await gd_update_one(db.session, "school_settings", {"school_id": school_id}, update_data)
        else:
            await gd_insert(db.session, "school_settings", {
                "school_id": school_id,
                "created_at": now,
                **update_data
            })
        
        await log_audit(school_id, current_user, "UPDATE", "school_settings", school_id, update_data)
        
        # Return fresh data
        updated = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
        return {"success": True, "settings": updated, "message": "تم حفظ الإعدادات بنجاح"}

    @router.put("/settings/basic")
    async def update_school_basic_info(
        data: dict,
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
        ]))
    ):
        school_id = await get_school_id_from_user(current_user)
        now = datetime.now(timezone.utc).isoformat()
        
        # Only allowed fields (school_code is read-only)
        allowed = ["name_ar", "name_en", "city", "address", "phone", "email", "type"]
        update_data = {k: v for k, v in data.items() if k in allowed}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="لا توجد بيانات صالحة للتحديث")
        
        update_data["updated_at"] = now
        await gd_update_one(db.session, "schools", {"id": school_id}, update_data)
        await log_audit(school_id, current_user, "UPDATE", "school_basic_info", school_id, update_data)
        
        school = await gd_find_one(db.session, "schools", {"id": school_id})
        return {"success": True, "school": school, "message": "تم تحديث بيانات المدرسة بنجاح"}

    # ============ HARD CONSTRAINTS (SYSTEM RULES) ============

    @router.get("/settings/hard-constraints")
    async def get_hard_constraints(
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL,
            UserRole.PLATFORM_ADMIN, UserRole.TEACHER
        ]))
    ):
        constraints = await gd_find(db.session, "timetable_hard_constraints", {"is_system": True}, order_by="order", desc_order=False, limit=50)

        categories = {}
        for c in constraints:
            cat = c.get("category", "other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(c)

        return {
            "success": True,
            "hard_constraints": constraints,
            "total": len(constraints),
            "categories": {
                "resource_conflict": "تعارض الموارد",
                "time_boundary": "حدود الوقت",
                "capacity": "السعة",
                "workload": "نصاب العمل",
                "curriculum": "المنهج الدراسي",
                "distribution": "توزيع الحصص",
                "assignment": "الإسناد",
                "completeness": "اكتمال الجدول",
                "data_integrity": "صحة البيانات",
                "publishing": "النشر"
            },
            "by_category": categories
        }

    # ============ CONSTRAINTS (SCHOOL-LEVEL) ============

    @router.get("/settings/constraints")
    async def get_constraints(
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL,
            UserRole.PLATFORM_ADMIN
        ]))
    ):
        school_id = await get_school_id_from_user(current_user)
        constraints = await gd_find(db.session, "school_constraints", {"school_id": school_id}, limit=100)
        return {"constraints": constraints, "total": len(constraints)}

    @router.post("/settings/constraints")
    async def create_constraint(
        constraint: ConstraintCreate,
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
        ]))
    ):
        school_id = await get_school_id_from_user(current_user)
        now = datetime.now(timezone.utc).isoformat()
        
        cid = str(uuid.uuid4())
        doc = {
            "id": cid,
            "school_id": school_id,
            **constraint.dict(),
            "created_at": now,
            "updated_at": now,
            "created_by": current_user.get("email"),
        }
        await gd_insert(db.session, "school_constraints", doc)
        await log_audit(school_id, current_user, "CREATE", "school_constraint", cid, constraint.dict())
        
        created = await gd_find_one(db.session, "school_constraints", {"id": cid})
        return {"success": True, "constraint": created, "message": "تم إضافة القيد بنجاح"}

    @router.put("/settings/constraints/{constraint_id}")
    async def update_constraint(
        constraint_id: str,
        update: ConstraintUpdate,
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
        ]))
    ):
        school_id = await get_school_id_from_user(current_user)
        
        existing = await gd_find_one(db.session, "school_constraints", {"id": constraint_id, "school_id": school_id})
        if not existing:
            raise HTTPException(status_code=404, detail="القيد غير موجود")
        
        update_data = {k: v for k, v in update.dict().items() if v is not None}
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        await gd_update_one(db.session, "school_constraints", {"id": constraint_id}, update_data)
        await log_audit(school_id, current_user, "UPDATE", "school_constraint", constraint_id, update_data)
        
        updated = await gd_find_one(db.session, "school_constraints", {"id": constraint_id})
        return {"success": True, "constraint": updated, "message": "تم تحديث القيد بنجاح"}

    @router.patch("/settings/constraints/{constraint_id}/status")
    async def toggle_constraint_status(
        constraint_id: str,
        status: ConstraintStatusPatch,
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
        ]))
    ):
        school_id = await get_school_id_from_user(current_user)
        
        existing = await gd_find_one(db.session, "school_constraints", {"id": constraint_id, "school_id": school_id})
        if not existing:
            raise HTTPException(status_code=404, detail="القيد غير موجود")
        
        await gd_update_one(db.session, "school_constraints", {"id": constraint_id}, {"is_active": status.is_active, "updated_at": datetime.now(timezone.utc).isoformat()})
        await log_audit(school_id, current_user, "TOGGLE_STATUS", "school_constraint", constraint_id, {"is_active": status.is_active})
        
        action = "تفعيل" if status.is_active else "إيقاف"
        return {"success": True, "message": f"تم {action} القيد بنجاح"}

    @router.delete("/settings/constraints/{constraint_id}")
    async def delete_constraint(
        constraint_id: str,
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
        ]))
    ):
        school_id = await get_school_id_from_user(current_user)
        
        existing = await gd_find_one(db.session, "school_constraints", {"id": constraint_id, "school_id": school_id})
        if not existing:
            raise HTTPException(status_code=404, detail="القيد غير موجود")
        
        await gd_delete_one(db.session, "school_constraints", {"id": constraint_id})
        await log_audit(school_id, current_user, "DELETE", "school_constraint", constraint_id, {})
        
        return {"success": True, "message": "تم حذف القيد بنجاح"}

    # ============ OFFICIAL CURRICULUM ============

    @router.get("/official-curriculum")
    async def get_official_curriculum(
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL,
            UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_OPERATIONS_MANAGER
        ]))
    ):
        stages = await gd_find(db.session, "official_curriculum_stages", {}, order_by="order", desc_order=False, limit=10)
        tracks = await gd_find(db.session, "official_curriculum_tracks", {}, order_by="order", desc_order=False, limit=20)
        grades = await gd_find(db.session, "official_curriculum_grades", {}, limit=50)
        subjects = await gd_find(db.session, "official_curriculum_subjects", {}, limit=200)
        grade_subjects = await gd_find(db.session, "official_curriculum_grade_subjects", {}, order_by="display_order", desc_order=False, limit=1000)
        rank_loads = await gd_find(db.session, "official_teacher_rank_loads", {}, limit=20)
        optional_pools = await gd_find(db.session, "official_optional_subject_pools", {}, limit=10)
        pool_items = await gd_find(db.session, "official_optional_subject_pool_items", {}, limit=50)
        
        return {
            "stages": stages,
            "tracks": tracks,
            "grades": grades,
            "subjects": subjects,
            "grade_subjects": grade_subjects,
            "rank_loads": rank_loads,
            "optional_pools": optional_pools,
            "pool_items": pool_items,
            "is_read_only": True,
            "metadata": {
                "total_stages": len(stages),
                "total_tracks": len(tracks),
                "total_grades": len(grades),
                "total_subjects": len(subjects),
                "total_mappings": len(grade_subjects),
            }
        }

    @router.get("/official-curriculum/stages/{stage_id}/tracks/{track_id}/grades")
    async def get_curriculum_by_stage_track(
        stage_id: str,
        track_id: str,
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL,
            UserRole.PLATFORM_ADMIN
        ]))
    ):
        grades = await gd_find(db.session, "official_curriculum_grades", {"stage_id": stage_id, "track_id": track_id}, limit=20)
        
        result = []
        for grade in grades:
            grade_subjects = await gd_find(db.session, "official_curriculum_grade_subjects", {"grade_id": grade["id"]}, order_by="display_order", desc_order=False, limit=30)
            result.append({**grade, "subjects": grade_subjects})
        
        return {"grades": result}

    # ============ TEACHER-SUBJECT ASSIGNMENTS ============

    @router.get("/settings/teacher-assignments")
    async def get_teacher_assignments(
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
        ]))
    ):
        school_id = await get_school_id_from_user(current_user)
        assignments = await gd_find(db.session, "teacher_assignments", {"school_id": school_id}, limit=500)
        return {"assignments": assignments, "total": len(assignments)}

    @router.post("/settings/teacher-assignments")
    async def create_teacher_assignment(
        data: dict,
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
        ]))
    ):
        school_id = await get_school_id_from_user(current_user)
        now = datetime.now(timezone.utc).isoformat()
        
        teacher_id = data.get("teacher_id")
        subject_id = data.get("subject_id")
        class_id = data.get("class_id")
        
        if not teacher_id or not subject_id:
            raise HTTPException(status_code=400, detail="teacher_id و subject_id مطلوبان")
        
        # Check teacher exists in this school
        teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id, "school_id": school_id})
        if not teacher:
            raise HTTPException(status_code=404, detail="المعلم غير موجود")
        
        # Check duplicate
        existing = await gd_find_one(db.session, "teacher_assignments", {
            "school_id": school_id, "teacher_id": teacher_id,
            "subject_id": subject_id, "class_id": class_id
        })
        if existing:
            raise HTTPException(status_code=409, detail="هذا التكليف موجود بالفعل")
        
        aid = str(uuid.uuid4())
        doc = {
            "id": aid,
            "school_id": school_id,
            "teacher_id": teacher_id,
            "subject_id": subject_id,
            "class_id": class_id,
            "periods_per_week": data.get("periods_per_week", 4),
            "is_active": True,
            "created_at": now,
        }
        await gd_insert(db.session, "teacher_assignments", doc)
        await log_audit(school_id, current_user, "CREATE", "teacher_assignment", aid, doc)
        
        created = await gd_find_one(db.session, "teacher_assignments", {"id": aid})
        return {"success": True, "assignment": created, "message": "تم إضافة تكليف المعلم بنجاح"}

    @router.delete("/settings/teacher-assignments/{assignment_id}")
    async def delete_teacher_assignment(
        assignment_id: str,
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
        ]))
    ):
        school_id = await get_school_id_from_user(current_user)
        
        existing = await gd_find_one(db.session, "teacher_assignments", {"id": assignment_id, "school_id": school_id})
        if not existing:
            raise HTTPException(status_code=404, detail="التكليف غير موجود")
        
        await gd_delete_one(db.session, "teacher_assignments", {"id": assignment_id})
        await log_audit(school_id, current_user, "DELETE", "teacher_assignment", assignment_id, {})
        
        return {"success": True, "message": "تم حذف التكليف بنجاح"}

    # ============ CLASSES MANAGEMENT ============

    @router.post("/settings/classes")
    async def create_class(
        data: dict,
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
        ]))
    ):
        school_id = await get_school_id_from_user(current_user)
        now = datetime.now(timezone.utc).isoformat()
        
        grade_id = data.get("grade_id")
        section = data.get("section")
        if not grade_id or not section:
            raise HTTPException(status_code=400, detail="grade_id و section مطلوبان")
        
        # Get grade info
        grade = await gd_find_one(db.session, "grades", {"id": grade_id, "school_id": school_id})
        if not grade:
            raise HTTPException(status_code=404, detail="الصف غير موجود")
        
        class_id = f"cls-{school_id}-g{grade.get('grade_number', '?')}-{section}-{str(uuid.uuid4())[:8]}"
        class_doc = {
            "id": class_id,
            "school_id": school_id,
            "name": f"{grade.get('name_ar', '')} ({section})",
            "name_ar": f"{grade.get('name_ar', '')} ({section})",
            "grade_level": str(grade.get("grade_number", "")),
            "grade_id": grade_id,
            "section": section,
            "student_count": 0,
            "homeroom_teacher_id": data.get("homeroom_teacher_id"),
            "is_active": True,
            "created_at": now,
        }
        await gd_insert(db.session, "classes", class_doc)
        await log_audit(school_id, current_user, "CREATE", "class", class_id, class_doc)

        try:
            from routes.school_settings_mod import _ensure_class_linked_to_all_teachers
            await _ensure_class_linked_to_all_teachers(school_id, class_id)
        except Exception as e:
            logger.warning(f"Auto-assign class {class_id} to teachers failed: {e}")
        
        created = await gd_find_one(db.session, "classes", {"id": class_id})
        return {"success": True, "class": created, "message": "تم إنشاء الفصل بنجاح"}

    @router.delete("/settings/classes/{class_id}")
    async def delete_class(
        class_id: str,
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
        ]))
    ):
        school_id = await get_school_id_from_user(current_user)
        
        existing = await gd_find_one(db.session, "classes", {"id": class_id, "school_id": school_id})
        if not existing:
            raise HTTPException(status_code=404, detail="الفصل غير موجود")
        
        student_count = existing.get("student_count", 0)
        if student_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"لا يمكن حذف الفصل لوجود {student_count} طالب مرتبط به. يرجى نقل الطلاب أولاً."
            )
        
        cleanup = {}
        await gd_delete_one(db.session, "classes", {"id": class_id})
        r = await gd_delete_many(db.session, "teacher_assignments", {"class_id": class_id, "school_id": school_id})
        cleanup["teacher_assignments"] = r
        r = await gd_delete_many(db.session, "teacher_class_assignments", {"class_id": class_id})
        cleanup["teacher_class_assignments"] = r
        r = await gd_delete_many(db.session, "class_subjects", {"class_id": class_id})
        cleanup["class_subjects"] = r
        r = await gd_delete_many(db.session, "timetable_sessions", {"class_id": class_id})
        cleanup["timetable_sessions"] = r
        r = await gd_delete_many(db.session, "class_sessions", {"class_id": class_id})
        cleanup["class_sessions"] = r
        r = await gd_delete_many(db.session, "attendance", {"class_id": class_id})
        cleanup["attendance"] = r
        r = await gd_delete_many(db.session, "session_attendance", {"class_id": class_id})
        cleanup["session_attendance"] = r
        r = await gd_delete_many(db.session, "assessments", {"class_id": class_id})
        cleanup["assessments"] = r
        r = await gd_delete_many(db.session, "grades", {"class_id": class_id})
        cleanup["grades"] = r
        r = await gd_delete_many(db.session, "behaviour_records", {"class_id": class_id})
        cleanup["behaviour_records"] = r

        await log_audit(school_id, current_user, "DELETE", "class", class_id, {"cleanup": cleanup})
        
        return {"success": True, "message": "تم حذف الفصل وجميع البيانات المرتبطة به بنجاح", "cleanup": cleanup}

    return router
