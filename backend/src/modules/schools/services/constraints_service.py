"""
Constraints Service
Handles timetable hard constraints, soft constraints, custom constraints, constraint patterns,
teacher non-teaching other duties, and teacher workload summary/overrides.
"""
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import logging

from dependencies import (
    UserRole,
)
from engines.sql_utils import (
    gd_find, gd_find_one, gd_insert, gd_update_one, gd_delete_one,
)
from engines.timetable_session_lifecycle import find_live_timetable_sessions
from src.modules.schools.dto.constraints_dto import (
    CustomSoftConstraintCreate, CustomSoftConstraintUpdate,
    ConstraintPatternCreate, OtherDutyCreate, OtherDutyUpdate
)

logger = logging.getLogger("nassaq")

RANK_TOTAL_PERIODS = {
    "expert": 24,
    "advanced": 22,
    "practitioner": 20,
    "assistant": 18,
    "معلم خبير": 24,
    "معلم متقدم": 22,
    "معلم ممارس": 20,
    "معلم مساعد": 18,
}


class ConstraintsService:
    """Service handling timetable constraints, patterns, duties, and workload."""

    @staticmethod
    async def get_hard_constraints(session, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        global_constraints = await gd_find(session, "timetable_hard_constraints", {"is_system": True}, order_by="order", desc_order=False, limit=50)

        school_overrides: Dict[str, dict] = {}
        if school_id:
            overrides = await gd_find(session, "school_hard_constraint_overrides", {"school_id": school_id}, limit=200)
            school_overrides = {ov["code"]: ov for ov in overrides if ov.get("code")}

        constraints = []
        for c in global_constraints:
            merged = dict(c)
            merged["origin"] = "system"
            can_disable = bool(c.get("can_disable", False))
            merged["can_disable"] = can_disable
            ov = school_overrides.get(c.get("code"))
            if ov and "is_active" in ov and can_disable:
                merged["is_active"] = ov["is_active"]
            constraints.append(merged)

        categories = {}
        for c in constraints:
            cat = c.get("category", "other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(c)

        category_labels = {
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
        }

        return {
            "success": True,
            "hard_constraints": constraints,
            "total": len(constraints),
            "categories": category_labels,
            "by_category": categories
        }

    @staticmethod
    async def get_soft_constraints(session, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        global_constraints = await gd_find(session, "timetable_soft_constraints", {}, order_by="order", desc_order=False, limit=50)

        school_overrides: Dict[str, dict] = {}
        if school_id:
            overrides = await gd_find(session, "school_soft_constraint_overrides", {"school_id": school_id}, limit=200)
            school_overrides = {ov["code"]: ov for ov in overrides if ov.get("code")}

        constraints = []
        for c in global_constraints:
            merged = dict(c)
            ov = school_overrides.get(c.get("code"))
            if ov:
                if "is_active" in ov:
                    merged["is_active"] = ov["is_active"]
                if "weight" in ov:
                    merged["weight"] = ov["weight"]
                if "target_subject_ids" in ov:
                    merged["target_subject_ids"] = ov["target_subject_ids"]
            constraints.append(merged)

        categories = {}
        for c in constraints:
            cat = c.get("category", "other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(c)

        category_labels = {
            "distribution": "توزيع الحصص",
            "teacher_comfort": "راحة المعلم",
            "pedagogy": "الجانب التربوي",
            "fairness": "العدالة والتوازن"
        }

        return {
            "success": True,
            "soft_constraints": constraints,
            "total": len(constraints),
            "categories": category_labels,
            "by_category": categories
        }

    @staticmethod
    async def toggle_soft_constraint(session, code: str, data: dict, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        if not school_id:
            raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")

        constraint = await gd_find_one(session, "timetable_soft_constraints", {"code": code})
        if not constraint:
            raise HTTPException(status_code=404, detail="القيد غير موجود")

        now = datetime.now(timezone.utc).isoformat()
        update: dict = {"code": code, "school_id": school_id, "updated_at": now}
        if "is_active" in data:
            update["is_active"] = data["is_active"]
        if "weight" in data:
            w = data["weight"]
            if isinstance(w, int) and 1 <= w <= 10:
                update["weight"] = w
        if "target_subject_ids" in data:
            val = data["target_subject_ids"]
            update["target_subject_ids"] = val if isinstance(val, list) else []

        existing_ov = await gd_find_one(session, "school_soft_constraint_overrides", {"school_id": school_id, "code": code})
        if existing_ov:
            await gd_update_one(session, "school_soft_constraint_overrides", {"school_id": school_id, "code": code}, update)
        else:
            update["id"] = str(uuid.uuid4())
            update["created_at"] = now
            await gd_insert(session, "school_soft_constraint_overrides", update)

        return {"success": True, "message": "تم تحديث القيد التفضيلي بنجاح"}

    @staticmethod
    async def toggle_hard_constraint(session, code: str, data: dict, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        if not school_id:
            raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")

        constraint = await gd_find_one(session, "timetable_hard_constraints", {"code": code})
        if not constraint:
            raise HTTPException(status_code=404, detail="القيد غير موجود")

        if "is_active" not in data:
            raise HTTPException(status_code=400, detail="الحقل is_active مطلوب")
        is_active = bool(data["is_active"])

        if not is_active and not bool(constraint.get("can_disable", False)):
            raise HTTPException(status_code=400, detail="هذا القيد إلزامي ولا يمكن تعطيله")

        now = datetime.now(timezone.utc).isoformat()
        update = {"code": code, "school_id": school_id, "is_active": is_active, "updated_at": now}

        existing_ov = await gd_find_one(session, "school_hard_constraint_overrides", {"school_id": school_id, "code": code})
        if existing_ov:
            await gd_update_one(session, "school_hard_constraint_overrides", {"school_id": school_id, "code": code}, update)
        else:
            update["id"] = str(uuid.uuid4())
            update["created_at"] = now
            await gd_insert(session, "school_hard_constraint_overrides", update)

        return {"success": True, "message": "تم تحديث القيد الإلزامي بنجاح"}

    @staticmethod
    async def get_custom_soft_constraints(session, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        if not school_id:
            raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")
        constraints = await gd_find(session, "custom_soft_constraints", {"school_id": school_id}, order_by="created_at", desc_order=False, limit=100)
        return {"success": True, "constraints": constraints, "total": len(constraints)}

    @staticmethod
    async def create_custom_soft_constraint(session, data: dict, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        if not school_id:
            raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")

        name_ar = data.get("name_ar", "").strip()
        if not name_ar:
            raise HTTPException(status_code=400, detail="اسم القيد مطلوب")

        now = datetime.now(timezone.utc).isoformat()
        cid = str(uuid.uuid4())
        try:
            weight_val = max(1, min(10, int(data.get("weight", 5))))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="قيمة الوزن غير صالحة — يجب أن تكون رقماً بين 1 و10")
        doc = {
            "id": cid,
            "school_id": school_id,
            "name_ar": name_ar,
            "description_ar": data.get("description_ar", ""),
            "pattern": data.get("pattern", ""),
            "pattern_code": data.get("pattern_code", "custom"),
            "weight": weight_val,
            "target_subject_ids": data.get("target_subject_ids", []),
            "applies_to": data.get("applies_to", "school"),
            "is_active": True,
            "created_by": current_user.get("email"),
            "created_at": now,
            "updated_at": now,
        }
        await gd_insert(session, "custom_soft_constraints", doc)
        created = await gd_find_one(session, "custom_soft_constraints", {"id": cid})
        return {"success": True, "constraint": created, "message": "تم إضافة القيد المخصص بنجاح"}

    @staticmethod
    async def update_custom_soft_constraint(session, constraint_id: str, data: dict, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        existing = await gd_find_one(session, "custom_soft_constraints", {"id": constraint_id, "school_id": school_id})
        if not existing:
            raise HTTPException(status_code=404, detail="القيد غير موجود")

        update = {"updated_at": datetime.now(timezone.utc).isoformat()}
        for field in ["name_ar", "description_ar", "pattern", "pattern_code", "applies_to", "is_active", "target_subject_ids"]:
            if field in data:
                update[field] = data[field]
        if "weight" in data:
            try:
                update["weight"] = max(1, min(10, int(data["weight"])))
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="قيمة الوزن غير صالحة — يجب أن تكون رقماً بين 1 و10")

        await gd_update_one(session, "custom_soft_constraints", {"id": constraint_id, "school_id": school_id}, update)
        updated = await gd_find_one(session, "custom_soft_constraints", {"id": constraint_id})
        return {"success": True, "constraint": updated, "message": "تم تحديث القيد بنجاح"}

    @staticmethod
    async def delete_custom_soft_constraint(session, constraint_id: str, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        existing = await gd_find_one(session, "custom_soft_constraints", {"id": constraint_id, "school_id": school_id})
        if not existing:
            raise HTTPException(status_code=404, detail="القيد غير موجود")
        await gd_delete_one(session, "custom_soft_constraints", {"id": constraint_id, "school_id": school_id})
        return {"success": True, "message": "تم حذف القيد المخصص بنجاح"}

    @staticmethod
    async def get_constraint_patterns(session, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        builtin = await gd_find(session, "constraint_patterns", {"is_builtin": True}, order_by="order", desc_order=False, limit=50)
        custom = []
        if school_id:
            custom = await gd_find(session, "constraint_patterns", {"school_id": school_id, "is_builtin": False}, order_by="created_at", desc_order=False, limit=50)
        return {"success": True, "builtin_patterns": builtin, "custom_patterns": custom}

    @staticmethod
    async def create_constraint_pattern(session, data: dict, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        if not school_id:
            raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")

        name_ar = data.get("name_ar", "").strip()
        if not name_ar:
            raise HTTPException(status_code=400, detail="اسم القالب مطلوب")

        now = datetime.now(timezone.utc).isoformat()
        pid = str(uuid.uuid4())
        doc = {
            "id": pid,
            "school_id": school_id,
            "name_ar": name_ar,
            "name_en": data.get("name_en", ""),
            "description_ar": data.get("description_ar", ""),
            "category": data.get("category", "distribution"),
            "template": data.get("template", {}),
            "is_builtin": False,
            "created_by": current_user.get("email"),
            "created_at": now,
            "updated_at": now,
        }
        await gd_insert(session, "constraint_patterns", doc)
        created = await gd_find_one(session, "constraint_patterns", {"id": pid})
        return {"success": True, "pattern": created, "message": "تم إنشاء قالب القيد بنجاح"}

    @staticmethod
    async def update_constraint_pattern(session, pattern_id: str, data: dict, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        existing = await gd_find_one(session, "constraint_patterns", {"id": pattern_id, "school_id": school_id, "is_builtin": False})
        if not existing:
            raise HTTPException(status_code=404, detail="القالب غير موجود أو أنه قالب نظامي لا يمكن تعديله")

        update = {"updated_at": datetime.now(timezone.utc).isoformat()}
        for field in ["name_ar", "name_en", "description_ar", "category", "template"]:
            if field in data:
                update[field] = data[field]

        await gd_update_one(session, "constraint_patterns", {"id": pattern_id, "school_id": school_id}, update)
        updated = await gd_find_one(session, "constraint_patterns", {"id": pattern_id})
        return {"success": True, "pattern": updated, "message": "تم تحديث القالب بنجاح"}

    @staticmethod
    async def delete_constraint_pattern(session, pattern_id: str, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        existing = await gd_find_one(session, "constraint_patterns", {"id": pattern_id, "school_id": school_id, "is_builtin": False})
        if not existing:
            raise HTTPException(status_code=404, detail="القالب غير موجود أو أنه قالب نظامي لا يمكن حذفه")
        await gd_delete_one(session, "constraint_patterns", {"id": pattern_id, "school_id": school_id})
        return {"success": True, "message": "تم حذف القالب بنجاح"}

    @staticmethod
    async def get_other_duties(session, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        if not school_id:
            raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")
        duties = await gd_find(session, "teacher_other_duties", {"school_id": school_id}, order_by="created_at", desc_order=False, limit=200)
        return {"success": True, "duties": duties, "total": len(duties)}

    @staticmethod
    async def create_other_duty(session, data: dict, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        if not school_id:
            raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")

        teacher_id = data.get("teacher_id", "").strip()
        duty_name = data.get("duty_name", "").strip()
        if not teacher_id or not duty_name:
            raise HTTPException(status_code=400, detail="teacher_id و duty_name مطلوبان")

        teacher = await gd_find_one(session, "teachers", {"id": teacher_id, "school_id": school_id})
        if not teacher:
            raise HTTPException(status_code=400, detail="المعلم غير موجود أو لا ينتمي إلى هذه المدرسة")

        try:
            equivalent_periods = max(0, int(data.get("equivalent_periods", 1)))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="قيمة الحصص المعادلة غير صالحة — يجب أن تكون رقماً صحيحاً موجباً")
        now = datetime.now(timezone.utc).isoformat()
        did = str(uuid.uuid4())
        doc = {
            "id": did,
            "school_id": school_id,
            "teacher_id": teacher_id,
            "teacher_name": data.get("teacher_name", ""),
            "duty_name": duty_name,
            "equivalent_periods": equivalent_periods,
            "notes": data.get("notes", ""),
            "created_by": current_user.get("email"),
            "created_at": now,
            "updated_at": now,
        }
        await gd_insert(session, "teacher_other_duties", doc)
        created = await gd_find_one(session, "teacher_other_duties", {"id": did})
        return {"success": True, "duty": created, "message": "تم إضافة التكليف بنجاح"}

    @staticmethod
    async def update_other_duty(session, duty_id: str, data: dict, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        existing = await gd_find_one(session, "teacher_other_duties", {"id": duty_id, "school_id": school_id})
        if not existing:
            raise HTTPException(status_code=404, detail="التكليف غير موجود")

        update = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if "duty_name" in data:
            update["duty_name"] = data["duty_name"]
        if "equivalent_periods" in data:
            try:
                update["equivalent_periods"] = max(0, int(data["equivalent_periods"]))
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="قيمة الحصص المعادلة غير صالحة — يجب أن تكون رقماً صحيحاً موجباً")
        if "notes" in data:
            update["notes"] = data["notes"]

        await gd_update_one(session, "teacher_other_duties", {"id": duty_id, "school_id": school_id}, update)
        updated = await gd_find_one(session, "teacher_other_duties", {"id": duty_id})
        return {"success": True, "duty": updated, "message": "تم تحديث التكليف بنجاح"}

    @staticmethod
    async def delete_other_duty(session, duty_id: str, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        existing = await gd_find_one(session, "teacher_other_duties", {"id": duty_id, "school_id": school_id})
        if not existing:
            raise HTTPException(status_code=404, detail="التكليف غير موجود")
        await gd_delete_one(session, "teacher_other_duties", {"id": duty_id, "school_id": school_id})
        return {"success": True, "message": "تم حذف التكليف بنجاح"}

    @staticmethod
    async def get_workload_summary(session, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        if not school_id:
            raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")

        teachers = await gd_find(session, "teachers", {"school_id": school_id, "is_active": True}, limit=200)
        duties = await gd_find(session, "teacher_other_duties", {"school_id": school_id}, limit=500)

        timetables = await gd_find(
            session, "timetables", {"school_id": school_id},
            order_by="updated_at", desc_order=True, limit=10
        )
        active_timetable = (
            next((t for t in timetables if t.get("status") == "draft"), None)
            or next((t for t in timetables if t.get("is_published")), None)
            or (timetables[0] if timetables else None)
        )
        session_counts_by_teacher: Dict[str, int] = {}
        if active_timetable:
            placed_sessions = await find_live_timetable_sessions(
                session,
                {
                    "school_id": school_id,
                    "timetable_id": active_timetable.get("id"),
                },
                limit=10000
            )
            for s in placed_sessions:
                tid = s.get("teacher_id")
                if tid:
                    session_counts_by_teacher[tid] = session_counts_by_teacher.get(tid, 0) + 1

        duties_by_teacher: Dict[str, list] = {}
        for d in duties:
            tid = d.get("teacher_id")
            if tid:
                if tid not in duties_by_teacher:
                    duties_by_teacher[tid] = []
                duties_by_teacher[tid].append(d)

        overrides = await gd_find(session, "teacher_workload_overrides", {"school_id": school_id}, limit=200)
        overrides_by_teacher: Dict[str, dict] = {o["teacher_id"]: o for o in overrides if o.get("teacher_id")}

        summary = []
        for teacher in teachers:
            tid = teacher.get("id")
            rank = teacher.get("rank", "")
            total_periods = RANK_TOTAL_PERIODS.get(rank, 20)
            teaching_periods = session_counts_by_teacher.get(tid, 0)
            teacher_duties = duties_by_teacher.get(tid, [])
            other_duty_periods = sum(int(d.get("equivalent_periods", 0)) for d in teacher_duties)
            used_periods = teaching_periods + other_duty_periods
            override = overrides_by_teacher.get(tid, {})
            manual_override = override.get("standby_override")
            standby_periods = manual_override if manual_override is not None else max(0, total_periods - used_periods)

            summary.append({
                "teacher_id": tid,
                "teacher_name": teacher.get("full_name", ""),
                "rank": rank,
                "total_periods": total_periods,
                "teaching_periods": teaching_periods,
                "other_duty_periods": other_duty_periods,
                "other_duties": teacher_duties,
                "used_periods": used_periods,
                "standby_periods": standby_periods,
                "manual_override": manual_override is not None,
                "overload": used_periods > total_periods,
            })

        return {"success": True, "summary": summary, "total_teachers": len(summary)}

    @staticmethod
    async def set_workload_override(session, teacher_id: str, data: dict, current_user: dict) -> dict:
        school_id = current_user.get("school_id") or current_user.get("tenant_id")
        if not school_id:
            raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")

        teacher = await gd_find_one(session, "teachers", {"id": teacher_id, "school_id": school_id})
        if not teacher:
            raise HTTPException(status_code=404, detail="المعلم غير موجود")

        now = datetime.now(timezone.utc).isoformat()
        standby_override = data.get("standby_override")
        if standby_override is None:
            await gd_delete_one(session, "teacher_workload_overrides", {"teacher_id": teacher_id, "school_id": school_id})
            return {"success": True, "message": "تم إزالة التعديل اليدوي"}

        try:
            standby_override = int(standby_override)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="قيمة حصص الانتظار غير صالحة — يجب أن تكون رقماً صحيحاً")

        rank = teacher.get("rank", "")
        max_periods = RANK_TOTAL_PERIODS.get(rank, 24)
        if standby_override < 0 or standby_override > max_periods:
            raise HTTPException(
                status_code=400,
                detail=f"قيمة حصص الانتظار يجب أن تكون بين 0 و{max_periods}"
            )

        override_doc = {
            "teacher_id": teacher_id,
            "school_id": school_id,
            "standby_override": standby_override,
            "updated_by": current_user.get("email"),
            "updated_at": now,
        }
        existing = await gd_find_one(session, "teacher_workload_overrides", {"teacher_id": teacher_id, "school_id": school_id})
        if existing:
            await gd_update_one(session, "teacher_workload_overrides", {"teacher_id": teacher_id, "school_id": school_id}, override_doc)
        else:
            override_doc["id"] = str(uuid.uuid4())
            override_doc["created_at"] = now
            await gd_insert(session, "teacher_workload_overrides", override_doc)

        return {"success": True, "message": "تم تحديث حصص الانتظار اليدوية"}

    @staticmethod
    async def update_school_constraint(session, constraint_id: str, data: dict, current_user: dict, x_school_context: str = None) -> dict:
        from src.modules.schools.services.school_settings_service import resolve_school_context
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="School context required")

        update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if "is_active" in data:
            update_data["is_active"] = data["is_active"]

        result = await gd_update_one(session, "reference_admin_constraints", {"id": constraint_id}, update_data)
        if result == 0:
            result = await gd_update_one(session, "admin_constraints", {"id": constraint_id}, update_data)
        if result == 0:
            raise HTTPException(status_code=404, detail="Constraint not found")

        return {"message": "تم تحديث القيد بنجاح", "is_active": data.get("is_active")}
