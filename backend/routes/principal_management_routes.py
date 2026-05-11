"""
NASSAQ Principal Management Routes
صلاحيات مدير المدرسة الكاملة على حسابات المعلمين والطلاب وأولياء الأمور
Full CRUD + profile management for school principal on teacher/student/parent accounts
"""
from fastapi import APIRouter, HTTPException, Depends, Body, Query
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict
from datetime import datetime, timezone
import uuid
import secrets
import string

from dependencies import (
    db, get_current_user, require_roles, UserRole, logger, hash_password
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, _gd_unset


router = APIRouter(prefix="/principal", tags=["Principal Management"])

ADMIN_ROLES = [UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]


def _entity_tenant_filter(tenant_id: str) -> dict:
    return {"$or": [{"tenant_id": tenant_id}, {"school_id": tenant_id}]}


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    full_name_en: Optional[str] = None
    national_id: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    marital_status: Optional[str] = None
    phone: Optional[str] = None
    alt_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None


class UpdateCredentialsRequest(BaseModel):
    new_email: Optional[str] = None
    new_password: Optional[str] = None


class UpdateAccountStatusRequest(BaseModel):
    status: str
    reason: Optional[str] = None
    duration: Optional[str] = None


class UpdateTeacherProfessionalRequest(BaseModel):
    specialization: Optional[str] = None
    academic_degree: Optional[str] = None
    teacher_rank: Optional[str] = None
    years_of_experience: Optional[int] = None
    contract_type: Optional[str] = None
    employee_number: Optional[str] = None
    department: Optional[str] = None
    education_stage: Optional[str] = None
    hire_date: Optional[str] = None


class TransferClassRequest(BaseModel):
    new_class_id: str
    new_grade_id: Optional[str] = None


async def _write_audit(tenant_id, action, entity_type, entity_id, changes, performed_by):
    await gd_insert(db.session, "audit_logs", {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "changes": changes,
        "performed_by": performed_by,
        "performed_at": datetime.now(timezone.utc).isoformat()
    })


# ==================== USER ACCOUNT RESOLVER ====================
# Map a profile entity (parents / teachers / students row) to the matching
# `users` row. The `users` table is the single source of truth for whether a
# login account exists, so we MUST check it by every reasonable identifier
# before concluding "no account exists" — otherwise the UI shows a stale
# "create account" button that then trips the global users.email UNIQUE
# constraint when admin clicks it.
#
# Lookup order (first match wins):
#   1) users.<role>_id == entity_id          (the real FK column)
#   2) users.linked_entity_id == entity_id   (legacy column on some DBs)
#   3) users.id == entity_id                 (when the profile row IS a user)
#   4) users.id == entity.user_id            (when the profile carries user_id)
#   5) users.email == entity.email           (last-resort email fallback —
#                                             this is what catches the bug
#                                             where prior link columns were
#                                             never populated)
#
# Auto-heal: if a user is found via fallbacks (4) or (5) and the canonical
# users.<role>_id link is missing/wrong, we silently update users.<role>_id
# to point at entity_id. This restores DB integrity so subsequent loads find
# the account on the first try, without requiring a migration.
ROLE_FK_COLUMN = {
    "parent": "parent_id",
    "teacher": "teacher_id",
    "student": "student_id",
}


async def _resolve_user_account_with_heal(role: str, entity: dict, entity_id: str, tenant_id: str) -> Optional[dict]:
    """Find the users row that backs a profile entity, healing the FK link
    when the lookup falls back to email matching. See module-level docstring
    above for rationale."""
    fk_col = ROLE_FK_COLUMN.get(role)
    base_filter = {"role": role, "tenant_id": tenant_id}

    # Build OR conditions — only include columns we know the schema supports.
    or_conditions = []
    if fk_col:
        or_conditions.append({fk_col: entity_id})
    or_conditions.append({"linked_entity_id": entity_id})
    or_conditions.append({"id": entity_id})
    if entity.get("user_id"):
        or_conditions.append({"id": entity.get("user_id")})

    user = None
    try:
        user = await gd_find_one(db.session, "users", {"$or": or_conditions, **base_filter})
    except Exception as e:  # pragma: no cover - defensive: e.g. column missing
        logger.warning(f"_resolve_user_account_with_heal initial lookup failed for {role}/{entity_id}: {e}")

    # Email fallback — by far the most common reason the FK lookup misses
    # is that older flows inserted users without populating <role>_id.
    if not user and entity.get("email"):
        try:
            user = await gd_find_one(db.session, "users", {
                "email": entity["email"],
                **base_filter,
            })
        except Exception as e:  # pragma: no cover
            logger.warning(f"_resolve_user_account_with_heal email fallback failed for {role}/{entity_id}: {e}")

    # Auto-heal: ensure the canonical FK column points at this entity so
    # subsequent loads don't have to fall through to the email path.
    if user and fk_col and user.get(fk_col) != entity_id:
        try:
            await gd_update_one(
                db.session, "users",
                {"id": user["id"]},
                {fk_col: entity_id, "updated_at": datetime.now(timezone.utc).isoformat()},
            )
            user[fk_col] = entity_id
            logger.info(f"Healed users.{fk_col}={entity_id} for user {user['id']} ({role})")
        except Exception as e:  # pragma: no cover
            logger.warning(f"_resolve_user_account_with_heal heal failed for {role}/{entity_id}: {e}")

    return user


# ==================== TEACHER MANAGEMENT ====================

@router.get("/teacher/{teacher_id}/full-profile")
async def get_teacher_full_profile(
    teacher_id: str,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id, **_entity_tenant_filter(tenant_id)})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")

    user_account = await _resolve_user_account_with_heal("teacher", teacher, teacher_id, tenant_id)

    assignments = await gd_find(db.session, "teacher_assignments", {**_entity_tenant_filter(tenant_id), "teacher_id": teacher_id, "is_active": True}, limit=30)

    session_count = await gd_count(db.session, "teacher_sessions", {**_entity_tenant_filter(tenant_id), "teacher_id": teacher_id})

    attendance_stats = {}
    total_sessions = await gd_count(db.session, "teacher_sessions", {**_entity_tenant_filter(tenant_id), "teacher_id": teacher_id})
    if total_sessions > 0:
        attendance_stats["total_sessions"] = total_sessions

    recent_activity = await gd_find(db.session, "audit_logs", {"tenant_id": tenant_id, "entity_id": teacher_id}, order_by="performed_at", desc_order=True, limit=10)

    return {
        "success": True,
        "profile": {
            "basic_info": {
                "full_name": teacher.get("full_name"),
                "full_name_en": teacher.get("full_name_en"),
                "national_id": teacher.get("national_id"),
                "gender": teacher.get("gender"),
                "nationality": teacher.get("nationality"),
                "date_of_birth": teacher.get("date_of_birth"),
                "marital_status": teacher.get("marital_status"),
                "photo": teacher.get("photo")
            },
            "contact_info": {
                "phone": teacher.get("phone"),
                "alt_phone": teacher.get("alt_phone"),
                "email": teacher.get("email"),
                "address": teacher.get("address"),
                "city": teacher.get("city"),
                "country": teacher.get("country")
            },
            "professional_info": {
                "specialization": teacher.get("specialization"),
                "academic_degree": teacher.get("academic_degree"),
                "teacher_rank": teacher.get("teacher_rank"),
                "years_of_experience": teacher.get("years_of_experience"),
                "contract_type": teacher.get("contract_type"),
                "employee_number": teacher.get("employee_number"),
                "department": teacher.get("department"),
                "education_stage": teacher.get("education_stage"),
                "hire_date": teacher.get("hire_date")
            },
            "operational_info": {
                "school_id": teacher.get("tenant_id"),
                "subjects": teacher.get("subject_ids", []),
                "primary_subject": teacher.get("primary_subject_id"),
                "max_periods_per_week": teacher.get("max_periods_per_week"),
                "status": teacher.get("status", "active"),
                "last_login": user_account.get("last_login") if user_account else None,
                "total_sessions": session_count
            },
            "assignments": assignments,
            "user_account": {
                "id": user_account.get("id") if user_account else None,
                "email": user_account.get("email") if user_account else teacher.get("email"),
                "status": user_account.get("status", "active") if user_account else None,
                "created_at": user_account.get("created_at") if user_account else None,
                "has_login_account": user_account is not None,
            },
            "attendance_stats": attendance_stats,
            "recent_activity": recent_activity
        }
    }


@router.put("/teacher/{teacher_id}/basic-info")
async def update_teacher_basic_info(
    teacher_id: str,
    data: UpdateProfileRequest,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id, **_entity_tenant_filter(tenant_id)})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")

    updates = {}
    changes = {}
    for field in ["full_name", "full_name_en", "national_id", "gender", "nationality",
                  "date_of_birth", "marital_status", "phone", "alt_phone", "email",
                  "address", "city", "country"]:
        val = getattr(data, field, None)
        if val is not None and val != teacher.get(field):
            updates[field] = val
            changes[field] = {"old": teacher.get(field), "new": val}

    if not updates:
        return {"success": True, "message": "لا توجد تغييرات"}

    user_row = await _resolve_user_account_with_heal("teacher", teacher, teacher_id, tenant_id)

    if "email" in updates:
        dup = await gd_find_one(db.session, "teachers", {
            "email": updates["email"], **_entity_tenant_filter(tenant_id), "id": {"$ne": teacher_id}
        })
        if dup:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم بالفعل")
        if user_row:
            user_dup = await gd_find_one(db.session, "users", {"email": updates["email"], "id": {"$ne": user_row["id"]}})
            if user_dup:
                raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم بالفعل")
            await gd_update_one(db.session, "users", {"id": user_row["id"]}, {"email": updates["email"], "updated_at": datetime.now(timezone.utc).isoformat()})

    if "full_name" in updates:
        if user_row:
            await gd_update_one(db.session, "users", {"id": user_row["id"]}, {"full_name": updates["full_name"], "updated_at": datetime.now(timezone.utc).isoformat()})
        await gd_update_many(db.session, "teacher_assignments", {**_entity_tenant_filter(tenant_id), "teacher_id": teacher_id}, {"teacher_name": updates["full_name"]})
        await gd_update_many(db.session, "schedule_sessions", {**_entity_tenant_filter(tenant_id), "teacher_id": teacher_id}, {"teacher_name": updates["full_name"]})

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "teachers", {"id": teacher_id, **_entity_tenant_filter(tenant_id)}, updates)
    await _write_audit(tenant_id, "update_teacher_profile", "teacher", teacher_id, changes, current_user["id"])

    return {"success": True, "message": "تم تحديث بيانات المعلم بنجاح", "changes": changes}


@router.put("/teacher/{teacher_id}/professional-info")
async def update_teacher_professional_info(
    teacher_id: str,
    data: UpdateTeacherProfessionalRequest,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id, **_entity_tenant_filter(tenant_id)})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")

    updates = {}
    changes = {}
    for field in ["specialization", "academic_degree", "teacher_rank", "years_of_experience",
                  "contract_type", "employee_number", "department", "education_stage", "hire_date"]:
        val = getattr(data, field, None)
        if val is not None and val != teacher.get(field):
            updates[field] = val
            changes[field] = {"old": teacher.get(field), "new": val}

    if not updates:
        return {"success": True, "message": "لا توجد تغييرات"}

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "teachers", {"id": teacher_id, **_entity_tenant_filter(tenant_id)}, updates)
    await _write_audit(tenant_id, "update_teacher_professional", "teacher", teacher_id, changes, current_user["id"])

    return {"success": True, "message": "تم تحديث البيانات المهنية بنجاح", "changes": changes}


@router.put("/teacher/{teacher_id}/credentials")
async def update_teacher_credentials(
    teacher_id: str,
    data: UpdateCredentialsRequest,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")

    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id, **_entity_tenant_filter(tenant_id)})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")

    user = await _resolve_user_account_with_heal("teacher", teacher, teacher_id, tenant_id)
    if data.new_email:
        dup = await gd_find_one(db.session, "users", {"email": data.new_email, "id": {"$ne": (user or {}).get("id", "")}})
        if dup:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم بالفعل")
    if data.new_password and len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن تكون 6 أحرف على الأقل")

    if not user:
        new_user_id = str(uuid.uuid4())
        email = data.new_email or teacher.get("email", f"{teacher_id}@nassaq.local")
        pwd = data.new_password or str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()
        user = {
            "id": new_user_id, "email": email, "password_hash": hash_password(pwd),
            "full_name": teacher.get("full_name", ""), "full_name_en": teacher.get("full_name_en", ""),
            "role": "teacher", "tenant_id": tenant_id, "teacher_id": teacher_id,
            "is_active": True, "must_change_password": True, "created_at": now, "updated_at": now
        }
        await gd_insert(db.session, "users", {**user, "_id": None})
        await _gd_unset(db.session, "users", {"id": new_user_id}, {"_id": ""})
        await gd_update_one(db.session, "teachers", {"id": teacher_id, **_entity_tenant_filter(tenant_id)}, {"user_id": new_user_id})
        await _write_audit(tenant_id, "create_teacher_account", "teacher", teacher_id, {"user_id": new_user_id, "email": email}, current_user["id"])
        return {"success": True, "message": "تم إنشاء حساب دخول للمعلم بنجاح", "account_created": True, "email": email}

    updates = {}
    changes = {}

    if data.new_email:
        updates["email"] = data.new_email
        changes["email"] = {"old": user.get("email"), "new": data.new_email}
        await gd_update_one(db.session, "teachers", {"id": teacher_id, **_entity_tenant_filter(tenant_id)}, {"email": data.new_email})

    if data.new_password:
        updates["password_hash"] = hash_password(data.new_password)
        changes["password"] = {"changed": True}

    if not updates:
        return {"success": True, "message": "لا توجد تغييرات"}

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "users", {"id": user["id"]}, updates)
    await _write_audit(tenant_id, "update_teacher_credentials", "teacher", teacher_id, changes, current_user["id"])

    return {"success": True, "message": "تم تحديث بيانات الدخول بنجاح"}


@router.put("/teacher/{teacher_id}/status")
async def update_teacher_account_status(
    teacher_id: str,
    data: UpdateAccountStatusRequest,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")

    valid_statuses = ["active", "suspended", "inactive", "closed"]
    if data.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"الحالة غير صالحة. الحالات المتاحة: {', '.join(valid_statuses)}")

    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id, **_entity_tenant_filter(tenant_id)})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")

    old_status = teacher.get("status", "active")
    now = datetime.now(timezone.utc).isoformat()

    await gd_update_one(db.session, "teachers", {"id": teacher_id, **_entity_tenant_filter(tenant_id)}, {"status": data.status, "is_active": data.status == "active", "status_reason": data.reason, "status_updated_at": now, "updated_at": now})
    user_row = await _resolve_user_account_with_heal("teacher", teacher, teacher_id, tenant_id)
    if user_row:
        await gd_update_one(db.session, "users", {"id": user_row["id"]}, {"status": data.status, "is_active": data.status == "active", "updated_at": now})
    else:
        logger.warning(f"teacher_status_change: no users row for teacher_id={teacher_id} (tenant={tenant_id}); auth row not updated")

    await _write_audit(tenant_id, f"teacher_status_{data.status}", "teacher", teacher_id,
                       {"old_status": old_status, "new_status": data.status, "reason": data.reason},
                       current_user["id"])

    status_labels = {"active": "نشط", "suspended": "معلق", "inactive": "غير نشط", "closed": "مغلق"}
    return {"success": True, "message": f"تم تغيير حالة الحساب إلى: {status_labels.get(data.status, data.status)}"}


@router.get("/teacher/{teacher_id}/activity-log")
async def get_teacher_activity_log(
    teacher_id: str,
    limit: int = Query(20, le=100),
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    logs = await gd_find(db.session, "audit_logs", {"tenant_id": tenant_id, "$or": [{"entity_id": teacher_id}, {"performed_by": teacher_id}]}, order_by="performed_at", desc_order=True, limit=limit)

    teacher_row = await gd_find_one(db.session, "teachers", {"id": teacher_id, **_entity_tenant_filter(tenant_id)})
    login_history = await _resolve_user_account_with_heal("teacher", teacher_row or {}, teacher_id, tenant_id) if teacher_row else None

    return {
        "success": True,
        "activity_log": logs,
        "last_login": login_history.get("last_login") if login_history else None,
        "login_count": login_history.get("login_count", 0) if login_history else 0
    }


# ==================== STUDENT MANAGEMENT ====================

@router.get("/student/{student_id}/full-profile")
async def get_student_full_profile(
    student_id: str,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    student = await gd_find_one(db.session, "students", {"id": student_id, **_entity_tenant_filter(tenant_id)})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    user_account = await _resolve_user_account_with_heal("student", student, student_id, tenant_id)

    guardians = await gd_find(db.session, "guardian_links", {**_entity_tenant_filter(tenant_id), "student_id": student_id, "is_active": True}, limit=10)

    if not guardians and student.get("parent_id"):
        parent = await gd_find_one(db.session, "parents", {"id": student["parent_id"], **_entity_tenant_filter(tenant_id)})
        if parent:
            guardians = [{
                "parent_ref": parent.get("id"),
                "parent_name": parent.get("full_name"),
                "relationship": student.get("parent_relationship", "parent"),
                "is_primary": True,
                "permissions": {"can_pickup": True, "can_view_grades": True, "can_view_attendance": True, "can_communicate": True}
            }]

    _PARENT_SAFE_FIELDS = {
        "id", "full_name", "full_name_en", "email", "phone", "alt_phone",
        "national_id", "gender", "nationality", "date_of_birth", "marital_status",
        "address", "city", "country", "avatar_url", "status", "is_active",
        "role", "preferred_language", "preferred_theme", "tenant_id", "school_id",
        "parent_id", "student_ids", "relationship_type", "occupation",
        "created_at", "updated_at",
    }

    parent_details = []
    for g in guardians:
        pref = g.get("parent_ref") or g.get("parent_id")
        if pref:
            p = await gd_find_one(db.session, "parents", {"id": pref, **_entity_tenant_filter(tenant_id)})
            if not p:
                p = await gd_find_one(db.session, "users", {"id": pref, "tenant_id": tenant_id, "role": "parent"})
            if p:
                safe_p = {k: v for k, v in p.items() if k in _PARENT_SAFE_FIELDS}
                parent_details.append({
                    **safe_p,
                    "relationship": g.get("relationship"),
                    "is_primary": g.get("is_primary", False),
                    "link_id": g.get("id"),
                    "permissions": g.get("permissions", {})
                })

    behaviour_records = await gd_find(db.session, "behaviour_records", {**_entity_tenant_filter(tenant_id), "student_id": student_id}, order_by="created_at", desc_order=True, limit=10)

    attendance_stats = {}
    total_attendance = await gd_count(db.session, "attendance", {**_entity_tenant_filter(tenant_id), "student_id": student_id})
    if total_attendance > 0:
        present = await gd_count(db.session, "attendance", {**_entity_tenant_filter(tenant_id), "student_id": student_id, "status": "present"})
        absent = await gd_count(db.session, "attendance", {**_entity_tenant_filter(tenant_id), "student_id": student_id, "status": "absent"})
        attendance_stats = {
            "total_days": total_attendance,
            "present": present,
            "absent": absent,
            "rate": round((present / total_attendance) * 100, 1) if total_attendance > 0 else 0
        }

    interactions = await gd_find(db.session, "session_interactions", {**_entity_tenant_filter(tenant_id), "student_id": student_id}, order_by="recorded_at", desc_order=True, limit=20)

    interaction_stats = {}
    if interactions:
        total_int = len(interactions)
        correct = sum(1 for i in interactions if i.get("interaction_type") == "correct_answer")
        wrong = sum(1 for i in interactions if i.get("interaction_type") == "wrong_answer")
        participation = sum(1 for i in interactions if i.get("interaction_type") == "participation")
        interaction_stats = {
            "total": total_int,
            "correct_answers": correct,
            "wrong_answers": wrong,
            "participation": participation
        }

    assessments = await gd_find(db.session, "assessment_submissions", {"student_id": student_id}, order_by="submitted_at", desc_order=True, limit=10)

    recent_activity = await gd_find(db.session, "audit_logs", {"tenant_id": tenant_id, "entity_id": student_id}, order_by="performed_at", desc_order=True, limit=10)

    siblings = []
    parent_refs = [g.get("parent_ref") or g.get("parent_id") for g in guardians if g.get("parent_ref") or g.get("parent_id")]
    if parent_refs:
        sibling_links = await gd_find(db.session, "guardian_links", {**_entity_tenant_filter(tenant_id), "parent_ref": {"$in": parent_refs}, "is_active": True, "student_id": {"$ne": student_id}}, limit=20)
        sib_ids = list({s["student_id"] for s in sibling_links})
        for sid in sib_ids[:10]:
            sib = await gd_find_one(db.session, "students", {"id": sid, **_entity_tenant_filter(tenant_id)})
            if sib:
                siblings.append(sib)

    return {
        "success": True,
        "profile": {
            "basic_info": {
                "id": student.get("id"),
                "full_name": student.get("full_name"),
                "full_name_en": student.get("full_name_en"),
                "national_id": student.get("national_id"),
                "student_number": student.get("student_number"),
                "date_of_birth": student.get("date_of_birth"),
                "gender": student.get("gender"),
                "nationality": student.get("nationality"),
                "grade_level": student.get("grade_level"),
                "grade_id": student.get("grade_id"),
                "class_id": student.get("class_id"),
                "class_name": student.get("class_name"),
                "education_level": student.get("education_level"),
                "photo": student.get("photo"),
                "status": student.get("status", "active")
            },
            "contact_info": {
                "phone": student.get("phone"),
                "email": student.get("email"),
                "address": student.get("address"),
                "city": student.get("city"),
                "country": student.get("country")
            },
            "parents": parent_details,
            "siblings": siblings,
            "user_account": {
                "id": user_account.get("id") if user_account else None,
                "email": user_account.get("email") if user_account else student.get("email"),
                "status": user_account.get("status", "active") if user_account else None,
                "last_login": user_account.get("last_login") if user_account else None,
                "created_at": user_account.get("created_at") if user_account else None,
                "has_login_account": user_account is not None,
            },
            "behaviour": behaviour_records,
            "attendance_stats": attendance_stats,
            "interaction_stats": interaction_stats,
            "assessments": assessments,
            "recent_activity": recent_activity
        }
    }


@router.put("/student/{student_id}/basic-info")
async def update_student_basic_info(
    student_id: str,
    data: UpdateProfileRequest,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    student = await gd_find_one(db.session, "students", {"id": student_id, **_entity_tenant_filter(tenant_id)})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    updates = {}
    changes = {}
    for field in ["full_name", "full_name_en", "national_id", "gender", "nationality",
                  "date_of_birth", "phone", "email", "address", "city", "country"]:
        val = getattr(data, field, None)
        if val is not None and val != student.get(field):
            updates[field] = val
            changes[field] = {"old": student.get(field), "new": val}

    if not updates:
        return {"success": True, "message": "لا توجد تغييرات"}

    user_row = await _resolve_user_account_with_heal("student", student, student_id, tenant_id)

    if "email" in updates:
        dup = await gd_find_one(db.session, "students", {
            "email": updates["email"], **_entity_tenant_filter(tenant_id), "id": {"$ne": student_id}
        })
        if dup:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم بالفعل")
        if user_row:
            user_dup = await gd_find_one(db.session, "users", {"email": updates["email"], "id": {"$ne": user_row["id"]}})
            if user_dup:
                raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم بالفعل")
            await gd_update_one(db.session, "users", {"id": user_row["id"]}, {"email": updates["email"], "updated_at": datetime.now(timezone.utc).isoformat()})

    if "full_name" in updates and user_row:
        await gd_update_one(db.session, "users", {"id": user_row["id"]}, {"full_name": updates["full_name"], "updated_at": datetime.now(timezone.utc).isoformat()})

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "students", {"id": student_id, **_entity_tenant_filter(tenant_id)}, updates)
    await _write_audit(tenant_id, "update_student_profile", "student", student_id, changes, current_user["id"])

    return {"success": True, "message": "تم تحديث بيانات الطالب بنجاح", "changes": changes}


@router.put("/student/{student_id}/credentials")
async def update_student_credentials(
    student_id: str,
    data: UpdateCredentialsRequest,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")

    student = await gd_find_one(db.session, "students", {"id": student_id, **_entity_tenant_filter(tenant_id)})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    user = await _resolve_user_account_with_heal("student", student, student_id, tenant_id)
    if data.new_email:
        dup = await gd_find_one(db.session, "users", {"email": data.new_email, "id": {"$ne": (user or {}).get("id", "")}})
        if dup:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم بالفعل")
    if data.new_password and len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن تكون 6 أحرف على الأقل")

    if not user:
        new_user_id = str(uuid.uuid4())
        email = data.new_email or student.get("email", f"{student_id}@nassaq.local")
        pwd = data.new_password or str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()
        user = {
            "id": new_user_id, "email": email, "password_hash": hash_password(pwd),
            "full_name": student.get("full_name", ""), "full_name_en": student.get("full_name_en", ""),
            "role": "student", "tenant_id": tenant_id, "student_id": student_id,
            "is_active": True, "must_change_password": True, "created_at": now, "updated_at": now
        }
        await gd_insert(db.session, "users", {**user, "_id": None})
        await _gd_unset(db.session, "users", {"id": new_user_id}, {"_id": ""})
        await gd_update_one(db.session, "students", {"id": student_id, **_entity_tenant_filter(tenant_id)}, {"user_id": new_user_id})
        await _write_audit(tenant_id, "create_student_account", "student", student_id, {"user_id": new_user_id, "email": email}, current_user["id"])
        return {"success": True, "message": "تم إنشاء حساب دخول للطالب بنجاح", "account_created": True, "email": email}

    updates = {}
    changes = {}

    if data.new_email:
        updates["email"] = data.new_email
        changes["email"] = {"old": user.get("email"), "new": data.new_email}
        await gd_update_one(db.session, "students", {"id": student_id, **_entity_tenant_filter(tenant_id)}, {"email": data.new_email})

    if data.new_password:
        updates["password_hash"] = hash_password(data.new_password)
        changes["password"] = {"changed": True}

    if not updates:
        return {"success": True, "message": "لا توجد تغييرات"}

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "users", {"id": user["id"]}, updates)
    await _write_audit(tenant_id, "update_student_credentials", "student", student_id, changes, current_user["id"])

    return {"success": True, "message": "تم تحديث بيانات الدخول بنجاح"}


@router.put("/student/{student_id}/status")
async def update_student_account_status(
    student_id: str,
    data: UpdateAccountStatusRequest,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    valid_statuses = ["active", "suspended", "inactive", "closed"]
    if data.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"الحالة غير صالحة")

    student = await gd_find_one(db.session, "students", {"id": student_id, **_entity_tenant_filter(tenant_id)})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    old_status = student.get("status", "active")
    now = datetime.now(timezone.utc).isoformat()

    await gd_update_one(db.session, "students", {"id": student_id, **_entity_tenant_filter(tenant_id)}, {"status": data.status, "is_active": data.status == "active", "status_reason": data.reason, "status_updated_at": now, "updated_at": now})
    user_row = await _resolve_user_account_with_heal("student", student, student_id, tenant_id)
    if user_row:
        await gd_update_one(db.session, "users", {"id": user_row["id"]}, {"status": data.status, "is_active": data.status == "active", "updated_at": now})
    else:
        logger.warning(f"student_status_change: no users row for student_id={student_id} (tenant={tenant_id}); auth row not updated")

    await _write_audit(tenant_id, f"student_status_{data.status}", "student", student_id,
                       {"old_status": old_status, "new_status": data.status, "reason": data.reason},
                       current_user["id"])

    status_labels = {"active": "نشط", "suspended": "معلق", "inactive": "غير نشط", "closed": "مغلق"}
    return {"success": True, "message": f"تم تغيير حالة الحساب إلى: {status_labels.get(data.status, data.status)}"}


@router.put("/student/{student_id}/transfer-class")
async def transfer_student_class(
    student_id: str,
    data: TransferClassRequest,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    student = await gd_find_one(db.session, "students", {"id": student_id, **_entity_tenant_filter(tenant_id)})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    new_class = await gd_find_one(db.session, "classes", {"id": data.new_class_id, "tenant_id": tenant_id})
    if not new_class:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")

    current_count = await gd_count(db.session, "students", {"class_id": data.new_class_id, **_entity_tenant_filter(tenant_id), "status": {"$ne": "deleted"}})
    capacity = new_class.get("capacity", 30)
    if current_count >= capacity:
        raise HTTPException(status_code=400, detail=f"الفصل ممتلئ ({current_count}/{capacity})")

    old_class_id = student.get("class_id")
    old_class_name = student.get("class_name")
    now = datetime.now(timezone.utc).isoformat()

    update_fields = {
        "class_id": data.new_class_id,
        "class_name": new_class.get("name"),
        "updated_at": now
    }
    if data.new_grade_id:
        update_fields["grade_id"] = data.new_grade_id
        grade = await gd_find_one(db.session, "classes", {"id": data.new_class_id})
        if grade:
            update_fields["grade_level"] = grade.get("grade_level")

    await gd_update_one(db.session, "students", {"id": student_id, **_entity_tenant_filter(tenant_id)}, update_fields)

    await _write_audit(tenant_id, "transfer_student_class", "student", student_id,
                       {"old_class": old_class_name, "old_class_id": old_class_id,
                        "new_class": new_class.get("name"), "new_class_id": data.new_class_id},
                       current_user["id"])

    return {
        "success": True,
        "message": f"تم نقل الطالب من {old_class_name} إلى {new_class.get('name')} بنجاح"
    }


@router.post("/student/{student_id}/behaviour")
async def add_student_behaviour(
    student_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    student = await gd_find_one(db.session, "students", {"id": student_id, **_entity_tenant_filter(tenant_id)})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "student_id": student_id,
        "student_name": student.get("full_name"),
        "type": data.get("type", "note"),
        "category": data.get("category", "general"),
        "description": data.get("description", ""),
        "is_positive": data.get("is_positive", True),
        "points": data.get("points", 0),
        "recorded_by": current_user["id"],
        "recorded_by_name": current_user.get("full_name"),
        "created_at": now,
        "updated_at": now
    }
    await gd_insert(db.session, "behaviour_records", record)

    return {"success": True, "message": "تم إضافة السجل السلوكي بنجاح", "record_id": record["id"]}


@router.get("/student/{student_id}/activity-log")
async def get_student_activity_log(
    student_id: str,
    limit: int = Query(20, le=100),
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    logs = await gd_find(db.session, "audit_logs", {"tenant_id": tenant_id, "$or": [{"entity_id": student_id}, {"performed_by": student_id}]}, order_by="performed_at", desc_order=True, limit=limit)

    return {"success": True, "activity_log": logs}


# ==================== PARENT MANAGEMENT ====================

@router.get("/parent/{parent_id}/full-profile")
async def get_parent_full_profile(
    parent_id: str,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")

    parent = await gd_find_one(db.session, "parents", {"id": parent_id, **_entity_tenant_filter(tenant_id)})
    if not parent:
        parent = await gd_find_one(db.session, "users", {"id": parent_id, "role": "parent", "tenant_id": tenant_id})
    if not parent:
        raise HTTPException(status_code=404, detail="ولي الأمر غير موجود")

    user_account = await _resolve_user_account_with_heal("parent", parent, parent_id, tenant_id)

    children_links = await gd_find(db.session, "guardian_links", {**_entity_tenant_filter(tenant_id), "parent_ref": parent_id, "is_active": True}, limit=20)

    children = []
    if children_links:
        link_student_ids = [link["student_id"] for link in children_links if link.get("student_id")]
        if link_student_ids:
            children_docs = await gd_find(db.session, "students", {"id": {"$in": link_student_ids}, **_entity_tenant_filter(tenant_id)}, limit=100)
            child_map = {c["id"]: c for c in children_docs}
            for link in children_links:
                child = child_map.get(link["student_id"])
                if child:
                    children.append({
                        **child,
                        "relationship": link.get("relationship"),
                        "is_primary": link.get("is_primary", False),
                        "link_id": link.get("id"),
                        "permissions": link.get("permissions", {})
                    })

    if not children and parent.get("children"):
        child_ids = parent.get("children", [])
        if child_ids:
            fallback_docs = await gd_find(db.session, "students", {"id": {"$in": child_ids}, **_entity_tenant_filter(tenant_id)}, limit=100)
            children = fallback_docs

    if not children:
        linked_students = await gd_find(db.session, "students", {"$and": [_entity_tenant_filter(tenant_id), {"$or": [{"parent_id": parent_id}, {"parent_user_id": parent_id}]}]}, limit=20)
        children = linked_students

    notifications = await gd_find(db.session, "notifications", {**_entity_tenant_filter(tenant_id), "user_id": parent_id}, order_by="created_at", desc_order=True, limit=10)

    recent_activity = await gd_find(db.session, "audit_logs", {"tenant_id": tenant_id, "$or": [{"entity_id": parent_id}, {"performed_by": parent_id}]}, order_by="performed_at", desc_order=True, limit=10)

    return {
        "success": True,
        "profile": {
            "basic_info": {
                "id": parent.get("id"),
                "full_name": parent.get("full_name"),
                "full_name_en": parent.get("full_name_en"),
                "national_id": parent.get("national_id"),
                "gender": parent.get("gender"),
                "nationality": parent.get("nationality"),
                "date_of_birth": parent.get("date_of_birth"),
                "photo": parent.get("photo")
            },
            "contact_info": {
                "phone": parent.get("phone"),
                "alt_phone": parent.get("alt_phone"),
                "email": parent.get("email"),
                "address": parent.get("address"),
                "city": parent.get("city"),
                "country": parent.get("country")
            },
            "children": children,
            "user_account": {
                "id": user_account.get("id") if user_account else None,
                "email": user_account.get("email") if user_account else parent.get("email"),
                "status": user_account.get("status", "active") if user_account else parent.get("status", "active"),
                "last_login": user_account.get("last_login") if user_account else None,
                "created_at": user_account.get("created_at") if user_account else parent.get("created_at"),
                "has_login_account": user_account is not None
            },
            "notifications": notifications,
            "recent_activity": recent_activity
        }
    }


@router.put("/parent/{parent_id}/basic-info")
async def update_parent_basic_info(
    parent_id: str,
    data: UpdateProfileRequest,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    parent = await gd_find_one(db.session, "parents", {"id": parent_id, **_entity_tenant_filter(tenant_id)})
    if not parent:
        raise HTTPException(status_code=404, detail="ولي الأمر غير موجود")

    updates = {}
    changes = {}
    for field in ["full_name", "full_name_en", "national_id", "gender", "nationality",
                  "date_of_birth", "phone", "alt_phone", "email", "address", "city", "country"]:
        val = getattr(data, field, None)
        if val is not None and val != parent.get(field):
            updates[field] = val
            changes[field] = {"old": parent.get(field), "new": val}

    if not updates:
        return {"success": True, "message": "لا توجد تغييرات"}

    user_row = await _resolve_user_account_with_heal("parent", parent, parent_id, tenant_id)

    if "email" in updates:
        dup = await gd_find_one(db.session, "parents", {"email": updates["email"], "id": {"$ne": parent_id}, **_entity_tenant_filter(tenant_id)})
        if dup:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم بالفعل")
        if user_row:
            user_dup = await gd_find_one(db.session, "users", {"email": updates["email"], "id": {"$ne": user_row["id"]}})
            if user_dup:
                raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم بالفعل")
            await gd_update_one(db.session, "users", {"id": user_row["id"]}, {"email": updates["email"], "updated_at": datetime.now(timezone.utc).isoformat()})

    if "phone" in updates:
        dup = await gd_find_one(db.session, "parents", {"phone": updates["phone"], "id": {"$ne": parent_id}, **_entity_tenant_filter(tenant_id)})
        if dup:
            raise HTTPException(status_code=400, detail="رقم الجوال مستخدم بالفعل")

    if "full_name" in updates:
        if user_row:
            await gd_update_one(db.session, "users", {"id": user_row["id"]}, {"full_name": updates["full_name"], "updated_at": datetime.now(timezone.utc).isoformat()})
        await gd_update_many(db.session, "guardian_links", {"parent_ref": parent_id, **_entity_tenant_filter(tenant_id)}, {"parent_name": updates["full_name"]})

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "parents", {"id": parent_id, **_entity_tenant_filter(tenant_id)}, updates)
    await _write_audit(tenant_id, "update_parent_profile", "parent", parent_id, changes, current_user["id"])

    return {"success": True, "message": "تم تحديث بيانات ولي الأمر بنجاح", "changes": changes}


@router.put("/parent/{parent_id}/credentials")
async def update_parent_credentials(
    parent_id: str,
    data: UpdateCredentialsRequest,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")

    parent = await gd_find_one(db.session, "parents", {"id": parent_id, **_entity_tenant_filter(tenant_id)})
    if not parent:
        raise HTTPException(status_code=404, detail="ولي الأمر غير موجود")

    user = await _resolve_user_account_with_heal("parent", parent, parent_id, tenant_id)
    if data.new_email:
        dup = await gd_find_one(db.session, "users", {"email": data.new_email, "id": {"$ne": (user or {}).get("id", "")}})
        if dup:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم بالفعل")
    if data.new_password and len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن تكون 6 أحرف على الأقل")

    if not user:
        new_user_id = str(uuid.uuid4())
        email = data.new_email or parent.get("email", f"{parent_id}@nassaq.local")
        pwd = data.new_password or str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()
        user = {
            "id": new_user_id, "email": email, "password_hash": hash_password(pwd),
            "full_name": parent.get("full_name", ""), "full_name_en": parent.get("full_name_en", ""),
            "role": "parent", "tenant_id": tenant_id, "parent_id": parent_id,
            "is_active": True, "must_change_password": True, "created_at": now, "updated_at": now
        }
        await gd_insert(db.session, "users", {**user, "_id": None})
        await _gd_unset(db.session, "users", {"id": new_user_id}, {"_id": ""})
        await gd_update_one(db.session, "parents", {"id": parent_id, **_entity_tenant_filter(tenant_id)}, {"user_id": new_user_id})
        await _write_audit(tenant_id, "create_parent_account", "parent", parent_id, {"user_id": new_user_id, "email": email}, current_user["id"])
        return {"success": True, "message": "تم إنشاء حساب دخول لولي الأمر بنجاح", "account_created": True, "email": email}

    updates = {}
    changes = {}

    if data.new_email:
        updates["email"] = data.new_email
        changes["email"] = {"old": user.get("email"), "new": data.new_email}
        await gd_update_one(db.session, "parents", {"id": parent_id, **_entity_tenant_filter(tenant_id)}, {"email": data.new_email})

    if data.new_password:
        updates["password_hash"] = hash_password(data.new_password)
        changes["password"] = {"changed": True}

    if not updates:
        return {"success": True, "message": "لا توجد تغييرات"}

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "users", {"id": user["id"]}, updates)
    await _write_audit(tenant_id, "update_parent_credentials", "parent", parent_id, changes, current_user["id"])

    return {"success": True, "message": "تم تحديث بيانات الدخول بنجاح"}


@router.put("/parent/{parent_id}/status")
async def update_parent_account_status(
    parent_id: str,
    data: UpdateAccountStatusRequest,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    valid_statuses = ["active", "suspended", "inactive", "closed"]
    if data.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="الحالة غير صالحة")

    parent = await gd_find_one(db.session, "parents", {"id": parent_id, **_entity_tenant_filter(tenant_id)})
    if not parent:
        raise HTTPException(status_code=404, detail="ولي الأمر غير موجود")

    old_status = parent.get("status", "active")
    now = datetime.now(timezone.utc).isoformat()

    await gd_update_one(db.session, "parents", {"id": parent_id, **_entity_tenant_filter(tenant_id)}, {"status": data.status, "is_active": data.status == "active", "status_reason": data.reason, "status_updated_at": now, "updated_at": now})
    user_row = await _resolve_user_account_with_heal("parent", parent, parent_id, tenant_id)
    if user_row:
        await gd_update_one(db.session, "users", {"id": user_row["id"]}, {"status": data.status, "is_active": data.status == "active", "updated_at": now})
    else:
        logger.warning(f"parent_status_change: no users row for parent_id={parent_id} (tenant={tenant_id}); auth row not updated")

    await _write_audit(tenant_id, f"parent_status_{data.status}", "parent", parent_id,
                       {"old_status": old_status, "new_status": data.status, "reason": data.reason},
                       current_user["id"])

    status_labels = {"active": "نشط", "suspended": "معلق", "inactive": "غير نشط", "closed": "مغلق"}
    return {"success": True, "message": f"تم تغيير حالة الحساب إلى: {status_labels.get(data.status, data.status)}"}


@router.get("/parent/{parent_id}/activity-log")
async def get_parent_activity_log(
    parent_id: str,
    limit: int = Query(20, le=100),
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    logs = await gd_find(db.session, "audit_logs", {"tenant_id": tenant_id, "$or": [{"entity_id": parent_id}, {"performed_by": parent_id}]}, order_by="performed_at", desc_order=True, limit=limit)

    return {"success": True, "activity_log": logs}


@router.post("/parent/{parent_id}/send-message")
async def send_message_to_parent(
    parent_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    parent = await gd_find_one(db.session, "parents", {"id": parent_id, **_entity_tenant_filter(tenant_id)})
    if not parent:
        raise HTTPException(status_code=404, detail="ولي الأمر غير موجود")

    now = datetime.now(timezone.utc).isoformat()
    message = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "from_user_id": current_user["id"],
        "from_user_name": current_user.get("full_name"),
        "to_user_id": parent_id,
        "to_user_name": parent.get("full_name"),
        "subject": data.get("subject", ""),
        "body": data.get("body", ""),
        "message_type": data.get("message_type", "general"),
        "is_read": False,
        "created_at": now
    }
    await gd_insert(db.session, "notifications", message)

    return {"success": True, "message": "تم إرسال الرسالة بنجاح", "message_id": message["id"]}


# ==================== GENERATE PASSWORD ====================

@router.post("/generate-password")
async def generate_secure_password(
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    chars = string.ascii_letters + string.digits + "!@#$%"
    password = ''.join(secrets.choice(chars) for _ in range(12))
    while not (any(c.isupper() for c in password) and any(c.islower() for c in password)
               and any(c.isdigit() for c in password) and any(c in "!@#$%" for c in password)):
        password = ''.join(secrets.choice(chars) for _ in range(12))

    return {"success": True, "password": password}


# ==================== SEARCH USERS ====================

@router.get("/search-users")
async def search_users_for_linking(
    q: str = Query(..., min_length=2),
    user_type: str = Query("student"),
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    coll_name = "students" if user_type == "student" else "parents" if user_type == "parent" else "teachers"

    import re as _re
    safe_q = _re.escape(q)
    query = {
        "$and": [
            _entity_tenant_filter(tenant_id),
            {"$or": [
                {"full_name": {"$regex": safe_q, "$options": "i"}},
                {"national_id": {"$regex": safe_q, "$options": "i"}},
                {"email": {"$regex": safe_q, "$options": "i"}},
                {"student_number": {"$regex": safe_q, "$options": "i"}} if user_type == "student" else {"phone": {"$regex": safe_q, "$options": "i"}}
            ]}
        ]
    }

    results = await gd_find(db.session, coll_name, query, limit=20)

    return {"success": True, "results": results, "total": len(results)}
