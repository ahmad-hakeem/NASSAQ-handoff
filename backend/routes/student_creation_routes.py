"""
Student Creation Routes - Advanced Student + Parent Wizard
منظومة إنشاء الطلاب المتقدمة
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime, timezone
import uuid
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, _gd_inc, _gd_addtoset
from sqlalchemy.exc import IntegrityError
from app.integrity_messages import describe_integrity_error
import re as _re

import qrcode
import io
import base64
import logging

logger = logging.getLogger("nassaq.student_creation_routes")


# ============== Pydantic Models ==============

class ParentData(BaseModel):
    # Phase 1 IT workspace mode (#192, spec §5.6) — every parent field is
    # optional so the IT inline-create flow can submit a student with zero
    # or partial parent contact info. The school-admin school-mode path
    # still validates that a phone is present at the route level so the
    # legacy contract is preserved.
    full_name: Optional[str] = None
    national_id: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    relationship: Optional[str] = "guardian"  # father, mother, guardian
    address: Optional[str] = None


class HealthData(BaseModel):
    health_status: Optional[str] = None
    allergies: Optional[List[str]] = []
    medications: Optional[List[str]] = []
    special_needs: Optional[str] = None
    notes: Optional[str] = None


class StudentCreateRequest(BaseModel):
    # Student Basic Info
    full_name: str
    email: Optional[EmailStr] = None
    national_id: Optional[str] = None
    gender: str  # male, female

    # FIX (C6): Use the shared Saudi national ID validator (Optional here).
    @field_validator("national_id")
    @classmethod
    def _check_national_id(cls, v):
        from shared_models import validate_saudi_national_id
        return validate_saudi_national_id(v, required=False)
    date_of_birth: str
    education_level: str  # primary, middle, high
    grade_id: str
    class_id: Optional[str] = None
    
    # Parent Info — Optional in IT workspace mode (#192, spec §5.6).
    # The route handler enforces presence for school-admin callers so the
    # legacy contract is unchanged.
    parent: Optional[ParentData] = None

    # Health Info (Optional)
    health: Optional[HealthData] = None
    
    # Link to existing parent
    link_to_parent_id: Optional[str] = None


class StudentBulkImportRequest(BaseModel):
    students: List[dict]


# ============== Helper Functions ==============

def generate_student_id(school_code: str, city_code: str, year: str, sequence: int) -> str:
    """
    توليد معرّف الطالب الموحد
    Format: NSS-SCH-CIT-YY-XXXX
    """
    return f"NSS-{school_code[:3].upper()}-{city_code[:3].upper()}-{year[-2:]}-{sequence:04d}"


async def _next_student_sequence(session, school_id: str, prefix: str) -> int:
    """
    Compute next student_number sequence based on the MAX existing sequence
    for the school under the given prefix (NSS-SCH-CIT-YY-). This avoids
    collisions when prior students were deleted (count-based approach was
    buggy and tripped the uq_students_number_school unique constraint).

    NOTE: We don't use gd_find's $regex filter — its sanitizer re-escapes
    the pattern, breaking anchors. We fetch all students for the school and
    filter the suffix in Python (school student counts are bounded).
    """
    rows = await gd_find(
        session,
        "students",
        {"school_id": school_id},
        limit=100000,
    )
    max_seq = 0
    suffix_re = _re.compile(rf"^{_re.escape(prefix)}(\d+)$")
    for r in rows:
        sn = (r or {}).get("student_number") or ""
        m = suffix_re.match(sn)
        if m:
            try:
                v = int(m.group(1))
                if v > max_seq:
                    max_seq = v
            except (TypeError, ValueError):
                continue
    return max_seq + 1


def generate_qr_code(student_data: dict) -> str:
    """
    توليد QR Code للطالب
    """
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr_data = f"NASSAQ-STUDENT|{student_data.get('id')}|{student_data.get('student_number', student_data.get('student_id', ''))}|{student_data.get('full_name')}"
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def create_student_creation_routes(db, get_current_user, require_roles, UserRole, hash_password, generate_secure_password):
    """Factory function to create student creation router"""
    
    router = APIRouter(prefix="/student-wizard", tags=["Student Wizard"])
    
    async def find_or_create_parent(parent_data: dict, school_id: str, created_by: str):
        """
        البحث عن ولي أمر موجود أو إنشاء جديد
        يدعم ربط الأشقاء تلقائياً

        Tenant rules (important):
          • The parents row is ALWAYS scoped to the current school. We never
            reuse a parents row from another school — that would break tenant
            isolation and let a student in School A get linked to a parent
            record owned by School B.
          • The users row is global (users.email is globally unique). When a
            user account already exists for the same email, we reuse the
            existing user_id and create a fresh per-school parents row that
            references it. This avoids `users_email_key` IntegrityErrors
            without leaking data across tenants.
        """
        existing_parent = None
        linked_students = []

        # parents lookup is per-school only.
        if parent_data.get("national_id"):
            existing_parent = await gd_find_one(db.session, "parents", {
                "national_id": parent_data["national_id"],
                "school_id": school_id
            })
        if not existing_parent and parent_data.get("phone"):
            existing_parent = await gd_find_one(db.session, "parents", {
                "phone": parent_data["phone"],
                "school_id": school_id
            })
        if not existing_parent and parent_data.get("email"):
            existing_parent = await gd_find_one(db.session, "parents", {
                "email": parent_data["email"],
                "school_id": school_id
            })

        if existing_parent:
            # Get linked students (siblings) — restrict to this school so we
            # don't leak siblings from other tenants.
            student_ids = existing_parent.get("student_ids", [])
            if student_ids:
                siblings = await gd_find(
                    db.session, "students",
                    {"id": {"$in": student_ids}, "school_id": school_id},
                    limit=20,
                )
                linked_students = siblings

            # Enrich with linked user_id (parents table has no user_id column;
            # link is by email) so downstream code can write guardian_links
            if not existing_parent.get("user_id") and existing_parent.get("email"):
                linked_user = await gd_find_one(db.session, "users", {
                    "email": existing_parent["email"],
                    "role": UserRole.PARENT.value
                })
                if linked_user:
                    existing_parent["user_id"] = linked_user.get("id")

            return {
                "parent": existing_parent,
                "is_new": False,
                "linked_students": linked_students
            }

        # 3) Reuse a global users row when only the user account exists
        #    (e.g. a parent whose previous parents row was archived). This
        #    avoids tripping the users_email_key UNIQUE constraint below.
        existing_user = None
        if parent_data.get("email"):
            existing_user = await gd_find_one(db.session, "users", {
                "email": parent_data["email"],
            })
            if existing_user and existing_user.get("role") != UserRole.PARENT.value:
                # Email belongs to a non-parent account — refuse with a
                # specific, actionable message instead of a 500.
                raise HTTPException(
                    status_code=409,
                    detail="البريد الإلكتروني مستخدم مسبقاً لحساب آخر",
                )

        # Create new parent
        parent_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        if existing_user:
            user_id = existing_user.get("id")
            parent_email = existing_user.get("email")
            temp_password = None  # account already exists
        else:
            # Generate temp password and a fresh user account
            temp_password = generate_secure_password()
            user_id = str(uuid.uuid4())
            parent_email = parent_data.get("email") or f"parent_{parent_id[:8]}@nassaq.local"

            user_doc = {
                "id": user_id,
                "email": parent_email,
                "password_hash": hash_password(temp_password),
                "full_name": parent_data["full_name"],
                "role": UserRole.PARENT.value,
                "phone": parent_data.get("phone"),
                "is_active": True,
                "must_change_password": True,
                "tenant_id": school_id,
                "created_at": now,
                "created_by": created_by
            }
            await gd_insert(db.session, "users", user_doc)

        parent_doc = {
            "id": parent_id,
            # parents table has no user_id column; keep this field for
            # downstream code (e.g. guardian_links) while harmless for the ORM
            "user_id": user_id,
            "full_name": parent_data["full_name"],
            "national_id": parent_data.get("national_id"),
            "phone": parent_data.get("phone"),
            "email": parent_email,
            "relationship": parent_data.get("relationship", "guardian"),
            "address": parent_data.get("address"),
            "student_ids": [],
            "school_id": school_id,
            "is_active": True,
            "created_at": now,
            "created_by": created_by,
        }

        await gd_insert(db.session, "parents", parent_doc)

        return {
            "parent": parent_doc,
            "is_new": True,
            "linked_students": [],
            "temp_password": temp_password
        }
    
    
    @router.post("/create")
    async def create_student_with_parent(
        request: StudentCreateRequest,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER]))
    ):
        """
        إنشاء طالب جديد مع ولي أمره
        - إنشاء أو ربط ولي الأمر
        - اكتشاف الأشقاء تلقائياً
        - توليد Student ID
        - توليد QR Code
        """
        # Phase 0 §4.B-1 — canonical workspace-id resolution; IT accounts
        # land in the synthetic `itw_{user_id}` workspace.
        from auth_scope import (
            require_request_school_id,
            is_independent_teacher,
            independent_workspace_id,
        )
        from quotas.independent_teacher import enforce_student_quota
        school_id = require_request_school_id(current_user)
        # Defensive tenant pin (#192 spec §5.3 step 6 / §5.6) — even though
        # the resolver above already returns the IT workspace id from JWT,
        # double-check here so any future regression that lets the client
        # supply `school_id` cannot smuggle an IT account into another tenant.
        is_it = is_independent_teacher(current_user)
        if is_it:
            expected = independent_workspace_id(current_user)
            if school_id != expected:
                raise HTTPException(
                    status_code=403,
                    detail="غير مصرح لك بإنشاء طالب خارج مساحة عملك",
                )
            school_id = expected
        # Phase 0 §4.B-5 — IT v1 student quota.
        await enforce_student_quota(db.session, current_user)

        # Stage/grade hierarchy enforcement — fail-closed validation that
        # the submitted grade_id belongs to the submitted education_level
        # under the resolved tenant. The frontend cascades the dropdown
        # for UX, but the real boundary lives here.
        from utils.stage_grade import validate_stage_grade_pair
        await validate_stage_grade_pair(
            db.session, school_id,
            request.education_level, request.grade_id,
            require_stage=True,
        )

        # Workspace-mode (IT) accepts a fully-optional parent payload
        # (spec §5.6). For school-admin callers the pre-existing contract
        # still requires a parent record (with at least a phone) so the
        # downstream materialisation path stays intact.
        if not is_it:
            if request.parent is None or not (request.parent.phone and request.parent.full_name):
                raise HTTPException(
                    status_code=422,
                    detail="بيانات ولي الأمر مطلوبة (الاسم والهاتف)",
                )

        # Defense-in-depth: normalize blank/whitespace-only optional
        # identifier fields to None so they reach the DB as NULL instead
        # of "". Empty strings collide on the (national_id, school_id)
        # UNIQUE constraint and surface as a misleading "ID already
        # registered" error. PostgreSQL treats NULLs as distinct, so
        # multiple students with no national ID are allowed.
        def _blank_to_none(v):
            if v is None:
                return None
            if isinstance(v, str):
                s = v.strip()
                return s or None
            return v

        request.national_id = _blank_to_none(request.national_id)
        # Defensive: never persist class_id="" (orphan-class state).
        # The wizard now ships the parent class id when launched from a
        # class detail page; older callers may still send "".
        request.class_id = _blank_to_none(getattr(request, "class_id", None))
        # Pin the class to the caller's tenant — a foreign-tenant class id
        # MUST resolve to "no class" rather than crossing the boundary.
        if request.class_id:
            cls_owner = await gd_find_one(
                db.session, "classes",
                {"id": request.class_id, "school_id": school_id},
            )
            if not cls_owner:
                raise HTTPException(status_code=404, detail="الفصل غير موجود")
        if request.parent is not None:
            request.parent.full_name = _blank_to_none(request.parent.full_name)
            request.parent.national_id = _blank_to_none(request.parent.national_id)
            request.parent.phone = _blank_to_none(request.parent.phone)
            request.parent.address = _blank_to_none(request.parent.address)
            # Pydantic EmailStr rejects blank, but defensively coerce.
            if isinstance(request.parent.email, str) and not request.parent.email.strip():
                request.parent.email = None

        # Workspace-mode (IT) parent materialisation gate (spec §5.6).
        # If the caller provided no usable parent identifier (no phone),
        # we DO NOT create an empty parents row — instead we record
        # whatever fragments were supplied in the canonical
        # `students.pending_parent_{name,phone,email}` columns so a real
        # parent can be linked later via the IT inline-link flow. The
        # `students_clear_pending_parent_on_link_trg` trigger clears the
        # pending fields on parent_id NULL→non-NULL transitions.
        # Workspace-mode (#192 spec §5.6): in IT workspace mode the
        # parent payload is FULLY OPTIONAL — any parent fragments
        # supplied through the inline-create flow land in
        # `pending_parent_*` and never materialise a `parents` row.
        # Only an explicit `link_to_parent_id` opts into linking.
        skip_parent_materialise = is_it and request.link_to_parent_id is None
        pending_parent_payload = None
        if skip_parent_materialise and request.parent is not None:
            pending_parent_payload = {
                "name": request.parent.full_name,
                "phone": request.parent.phone,
                "email": request.parent.email,
            }
        elif skip_parent_materialise:
            pending_parent_payload = {"name": None, "phone": None, "email": None}

        # Backfill any previously-poisoned rows where national_id was
        # written as "" so the unique constraint stops matching them.
        # Scoped to this tenant to avoid touching unrelated data.
        try:
            from sqlalchemy import text as _sa_text
            await db.session.execute(
                _sa_text(
                    "UPDATE students SET national_id = NULL "
                    "WHERE school_id = :sid AND national_id IS NOT NULL "
                    "AND btrim(national_id) = ''"
                ),
                {"sid": school_id},
            )
        except Exception as _bf_err:
            logger.warning(f"Failed to backfill empty national_id rows: {_bf_err}")

        # Get school info for student ID generation
        school = await gd_find_one(db.session, "schools", {"id": school_id})
        school_code = school.get("code", "SCH") if school else "SCH"
        city_code = school.get("city_code", "CIT") if school else "CIT"
        school_name = school.get("name_ar", "المدرسة") if school else "المدرسة"
        
        # Pre-flight duplicate checks for student fields. These produce
        # specific, field-aware messages BEFORE we touch the DB so the user
        # sees an actionable error instead of a generic "record exists".
        if request.national_id:
            existing = await gd_find_one(db.session, "students", {
                "national_id": request.national_id,
                "school_id": school_id
            })
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail="رقم هوية الطالب مسجل مسبقاً في هذه المدرسة",
                )

        if request.email:
            existing = await gd_find_one(db.session, "users", {"email": request.email})
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail="البريد الإلكتروني للطالب مستخدم مسبقاً",
                )

        # Workspace-mode short-circuit: skip parent materialisation entirely
        # and surface a synthetic parent_result so the downstream code path
        # (audit log, response shape) stays unified. The actual pending_*
        # columns are written when we build student_doc below.
        if skip_parent_materialise:
            parent_result = {
                "parent": {},
                "is_new": False,
                "linked_students": [],
            }
        # Check if linking to existing parent
        elif request.link_to_parent_id:
            existing_parent = await gd_find_one(db.session, "parents", {"id": request.link_to_parent_id, "school_id": school_id})
            if existing_parent:
                student_ids = existing_parent.get("student_ids", [])
                siblings = await gd_find(db.session, "students", {"id": {"$in": student_ids}}, limit=20)
                if not existing_parent.get("user_id") and existing_parent.get("email"):
                    linked_user = await gd_find_one(db.session, "users", {
                        "email": existing_parent["email"],
                        "role": UserRole.PARENT.value
                    })
                    if linked_user:
                        existing_parent["user_id"] = linked_user.get("id")
                parent_result = {
                    "parent": existing_parent,
                    "is_new": False,
                    "linked_students": siblings
                }
            else:
                raise HTTPException(status_code=404, detail="ولي الأمر المحدد غير موجود")
        else:
            # Find or create parent. Convert any constraint violation that
            # leaks out of the helper into a specific, actionable message.
            try:
                parent_result = await find_or_create_parent(
                    request.parent.model_dump(),
                    school_id,
                    current_user.get("id")
                )
            except IntegrityError as ie:
                _, user_msg = describe_integrity_error(str(getattr(ie, "orig", ie)))
                # Most parent-side conflicts are about the parent's user
                # account email — clarify that explicitly when relevant.
                lower = str(getattr(ie, "orig", ie)).lower()
                if "users_email_key" in lower or "email" in lower:
                    user_msg = "بريد ولي الأمر مستخدم مسبقاً لحساب آخر"
                raise HTTPException(status_code=409, detail=user_msg)
        
        parent = parent_result["parent"]
        is_new_parent = parent_result["is_new"]
        siblings = parent_result["linked_students"]
        
        # Generate student ID — use MAX existing sequence (not count) so prior
        # deletions don't cause uq_students_number_school collisions.
        year = datetime.now().strftime("%Y")
        sc3 = (school_code or "SCH")[:3].upper()
        cc3 = (city_code or "CIT")[:3].upper()
        prefix = f"NSS-{sc3}-{cc3}-{year[-2:]}-"
        next_seq = await _next_student_sequence(db.session, school_id, prefix)
        student_id_code = generate_student_id(school_code, city_code, year, next_seq)

        # Create student
        student_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Generate temp password for student
        student_temp_password = generate_secure_password()
        student_email = request.email or f"student_{student_id[:8]}@nassaq.local"
        
        # Create user account for student
        user_id = str(uuid.uuid4())
        user_doc = {
            "id": user_id,
            "email": student_email,
            "password_hash": hash_password(student_temp_password),
            "full_name": request.full_name,
            "role": UserRole.STUDENT.value,
            "is_active": True,
            "must_change_password": True,
            "tenant_id": school_id,
            "created_at": now,
            "created_by": current_user.get("id")
        }
        try:
            await gd_insert(db.session, "users", user_doc)
        except IntegrityError as ie:
            msg = str(getattr(ie, "orig", ie))
            lower = msg.lower()
            if "users_email_key" in lower or ("email" in lower and "unique" in lower):
                raise HTTPException(
                    status_code=409,
                    detail="البريد الإلكتروني للطالب مستخدم مسبقاً",
                )
            _, user_msg = describe_integrity_error(msg)
            raise HTTPException(status_code=409, detail=user_msg)

        student_doc = {
            "id": student_id,
            "user_id": user_id,
            "student_number": student_id_code,
            "full_name": request.full_name,
            "email": student_email,
            "national_id": request.national_id,
            "gender": request.gender,
            "date_of_birth": request.date_of_birth,
            "grade": request.grade_id,
            "class_id": request.class_id,
            "parent_id": parent.get("id"),
            "parent_user_id": parent.get("user_id"),
            "parent_name": parent.get("full_name"),
            "parent_phone": parent.get("phone"),
            "parent_email": parent.get("email"),
            "school_id": school_id,
            "is_active": True,
            "created_at": now,
            "created_by": current_user.get("id"),
        }
        # Workspace-mode (#192 spec §5.6): write the partial parent payload
        # into the canonical pending_parent_* columns and leave parent_id
        # / parent_user_id NULL. The clear-on-link DB trigger wipes these
        # when a real parent is later attached.
        if skip_parent_materialise:
            student_doc["parent_id"] = None
            student_doc["parent_user_id"] = None
            student_doc["parent_name"] = None
            student_doc["parent_phone"] = None
            student_doc["parent_email"] = None
            if pending_parent_payload:
                student_doc["pending_parent_name"] = pending_parent_payload.get("name")
                student_doc["pending_parent_phone"] = pending_parent_payload.get("phone")
                student_doc["pending_parent_email"] = pending_parent_payload.get("email")

        # Generate QR Code
        qr_code = generate_qr_code(student_doc)
        student_doc["qr_code"] = qr_code

        # Retry on race-time student_number collision. Use a SAVEPOINT
        # (begin_nested) so rolling back a failed student insert does NOT
        # wipe the user/parent rows already written in this request's
        # transaction. Only student_number conflicts are retried; everything
        # else is converted to a specific, actionable HTTPException.
        _attempts = 0
        while True:
            try:
                async with db.session.begin_nested():
                    await gd_insert(db.session, "students", student_doc)
                break
            except IntegrityError as ie:
                msg = str(getattr(ie, "orig", ie))
                lower = msg.lower()
                if _attempts < 5 and ("student_number" in lower or "uq_students_number_school" in lower):
                    _attempts += 1
                    next_seq = await _next_student_sequence(db.session, school_id, prefix) + _attempts
                    student_id_code = generate_student_id(school_code, city_code, year, next_seq)
                    student_doc["student_number"] = student_id_code
                    student_doc["qr_code"] = generate_qr_code(student_doc)
                    qr_code = student_doc["qr_code"]
                    continue
                # Map the constraint name → actionable Arabic message.
                _, user_msg = describe_integrity_error(msg)
                raise HTTPException(status_code=409, detail=user_msg)

        # Recompute the school's stored counts from live rows (Task #826) so the
        # denormalized columns stay accurate instead of drifting.
        from engines.entity_counts import reconcile_school_counts
        await reconcile_school_counts(db.session, school_id)

        # Workspace-mode (#192): no parents row was materialised, so we
        # skip both the parent.student_ids backfill and the guardian_link
        # write. The student row carries the partial contact in the
        # pending_parent_* columns until the IT operator links a real parent.
        if not skip_parent_materialise and parent.get("id"):
            # Link student to parent. Scope by both id AND school_id so we can
            # never accidentally mutate a parent record owned by another tenant.
            await _gd_addtoset(
                db.session, "parents",
                {"id": parent.get("id"), "school_id": school_id},
                {"student_ids": student_id},
            )

        # Create canonical guardian_link record so downstream queries work (idempotent)
        parent_user_id = parent.get("user_id") if not skip_parent_materialise else None
        if parent_user_id:
            existing_link = await gd_find_one(db.session, "guardian_links", {
                "parent_ref": parent_user_id,
                "student_id": student_id,
            })
            if not existing_link:
                await gd_insert(db.session, "guardian_links", {
                    "id": str(uuid.uuid4()),
                    "parent_ref": parent_user_id,
                    "parent_id": parent.get("id"),
                    "student_id": student_id,
                    "relationship": parent.get("relationship", "guardian"),
                    "tenant_id": school_id,
                    "is_active": True,
                    "created_at": now,
                    "created_by": current_user.get("id"),
                })
        
        # Link siblings
        if siblings:
            sibling_ids = [s.get("id") for s in siblings]
            # Update siblings to include new student
            for sib_id in sibling_ids:
                await _gd_addtoset(db.session, "students", {"id": sib_id}, {"sibling_ids": student_id})
        
        # Update class student count. Scope by school_id so a stray
        # cross-tenant class id can never be incremented.
        if request.class_id:
            await _gd_inc(
                db.session, "classes",
                {"id": request.class_id, "school_id": school_id},
                {"current_students": 1},
            )
        
        # Get class and grade info for response
        class_info = None
        grade_info = None
        if request.class_id:
            class_info = await gd_find_one(db.session, "classes", {"id": request.class_id})
        if request.grade_id:
            grade_info = await gd_find_one(db.session, "grades", {"id": request.grade_id})
        
        # Log action
        await gd_insert(db.session, "audit_logs", {
            "id": str(uuid.uuid4()),
            "action": "student_created_with_parent",
            "action_by": current_user.get("id"),
            "action_by_name": current_user.get("full_name", ""),
            "target_type": "student",
            "target_id": student_id,
            "target_name": request.full_name,
            "details": {
                "student_id_code": student_id_code,
                "parent_id": parent.get("id"),
                "parent_name": parent.get("full_name"),
                "is_new_parent": is_new_parent,
                "siblings_count": len(siblings)
            },
            "school_id": school_id,
            "timestamp": now
        })
        
        return {
            "success": True,
            "student": {
                "id": student_id,
                "student_id": student_id_code,
                "full_name": request.full_name,
                "email": student_email,
                "temp_password": student_temp_password,
                "class_name": class_info.get("name") if class_info else None,
                "grade_name": grade_info.get("name") if grade_info else None,
                "qr_code": qr_code
            },
            "parent": {
                "id": parent.get("id"),
                "full_name": parent.get("full_name"),
                "email": parent.get("email"),
                "phone": parent.get("phone"),
                "relationship": parent.get("relationship"),
                "is_new": is_new_parent,
                "temp_password": parent_result.get("temp_password") if is_new_parent else None
            },
            "siblings": {
                "count": len(siblings),
                "detected": len(siblings) > 0,
                "list": [{"id": s.get("id"), "name": s.get("full_name")} for s in siblings]
            },
            "school": {
                "id": school_id,
                "name": school_name
            }
        }
    
    
    @router.post("/check-parent")
    async def check_parent_exists(
        national_id: Optional[str] = Query(None),
        phone: Optional[str] = Query(None),
        email: Optional[str] = Query(None),
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
    ):
        """
        التحقق من وجود ولي أمر
        يستخدم للكشف المبكر عن الأشقاء
        """
        school_id = current_user.get("tenant_id")
        if not school_id:
            raise HTTPException(status_code=400, detail="لم يتم تحديد المدرسة")
        
        or_conditions = []
        if national_id:
            or_conditions.append({"national_id": national_id})
        if phone:
            or_conditions.append({"phone": phone})
        if email:
            or_conditions.append({"email": email})
        
        if not or_conditions:
            return {"found": False, "parent": None, "students": []}
        
        query = {"school_id": school_id, "$or": or_conditions}
        parent = await gd_find_one(db.session, "parents", query)
        
        if not parent:
            return {"found": False, "parent": None, "students": []}
        
        # Get linked students
        student_ids = parent.get("student_ids", [])
        students = []
        if student_ids:
            students = await gd_find(db.session, "students", {"id": {"$in": student_ids}}, limit=20)
        
        return {
            "found": True,
            "parent": {
                "id": parent.get("id"),
                "full_name": parent.get("full_name"),
                "phone": parent.get("phone"),
                "email": parent.get("email"),
                "relationship": parent.get("relationship")
            },
            "students": [{"id": s.get("id"), "name": s.get("full_name")} for s in students],
            "siblings_count": len(students)
        }
    
    
    @router.post("/bulk-import")
    async def bulk_import_students_with_parents(
        request: StudentBulkImportRequest,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
    ):
        """
        استيراد جماعي للطلاب مع أولياء أمورهم
        """
        school_id = current_user.get("tenant_id")
        if not school_id:
            raise HTTPException(status_code=400, detail="لم يتم تحديد المدرسة")
        
        results = {
            "total": len(request.students),
            "success": 0,
            "failed": 0,
            "new_students": 0,
            "new_parents": 0,
            "linked_to_existing_parents": 0,
            "sibling_groups_detected": 0,
            "errors": []
        }
        
        created_students = []
        parent_cache = {}  # Cache parents to detect siblings within batch
        
        for idx, student_data in enumerate(request.students):
            try:
                # Validate required fields
                if not student_data.get("full_name"):
                    results["errors"].append({
                        "row": idx + 1,
                        "error": "اسم الطالب مطلوب"
                    })
                    results["failed"] += 1
                    continue
                
                if not student_data.get("parent_phone") and not student_data.get("parent_email"):
                    results["errors"].append({
                        "row": idx + 1,
                        "student_name": student_data.get("full_name"),
                        "error": "بيانات ولي الأمر مطلوبة (هاتف أو بريد)"
                    })
                    results["failed"] += 1
                    continue
                
                # Create parent data
                parent_data = {
                    "full_name": student_data.get("parent_name", f"ولي أمر {student_data.get('full_name')}"),
                    "national_id": student_data.get("parent_national_id"),
                    "phone": student_data.get("parent_phone"),
                    "email": student_data.get("parent_email"),
                    "relationship": student_data.get("parent_relationship", "guardian")
                }
                
                # Check cache for parent (sibling detection within batch)
                parent_key = parent_data.get("phone") or parent_data.get("email") or parent_data.get("national_id")
                
                if parent_key and parent_key in parent_cache:
                    parent_result = parent_cache[parent_key]
                    results["sibling_groups_detected"] += 1
                else:
                    parent_result = await find_or_create_parent(
                        parent_data,
                        school_id,
                        current_user.get("id")
                    )
                    if parent_key:
                        parent_cache[parent_key] = parent_result
                    
                    if parent_result["is_new"]:
                        results["new_parents"] += 1
                    else:
                        results["linked_to_existing_parents"] += 1
                
                # Generate student ID — use MAX existing sequence (not count)
                # to avoid uq_students_number_school collisions when prior
                # students were deleted.
                school = await gd_find_one(db.session, "schools", {"id": school_id})
                school_code = school.get("code", "SCH") if school else "SCH"
                city_code = school.get("city_code", "CIT") if school else "CIT"
                year = datetime.now().strftime("%Y")
                _bsc3 = (school_code or "SCH")[:3].upper()
                _bcc3 = (city_code or "CIT")[:3].upper()
                _bprefix = f"NSS-{_bsc3}-{_bcc3}-{year[-2:]}-"
                student_count = await _next_student_sequence(db.session, school_id, _bprefix)
                student_id_code = generate_student_id(school_code, city_code, year, student_count)
                
                # Create student
                student_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()
                student_temp_password = generate_secure_password()
                student_email = student_data.get("email") or f"student_{student_id[:8]}@nassaq.local"
                
                user_id = str(uuid.uuid4())
                user_doc = {
                    "id": user_id,
                    "email": student_email,
                    "password_hash": hash_password(student_temp_password),
                    "full_name": student_data.get("full_name"),
                    "role": UserRole.STUDENT.value,
                    "is_active": True,
                    "must_change_password": True,
                    "tenant_id": school_id,
                    "created_at": now,
                    "created_by": current_user.get("id")
                }
                # Wrap user insert in a savepoint so a later student-insert
                # failure within this row can roll back BOTH the user and the
                # student without poisoning prior successful rows in the batch.
                async with db.session.begin_nested() as _row_sp:
                    await gd_insert(db.session, "users", user_doc)

                    student_doc = {
                        "id": student_id,
                        "user_id": user_id,
                        "student_number": student_id_code,
                        "full_name": student_data.get("full_name"),
                        "email": student_email,
                        "national_id": student_data.get("national_id"),
                        "gender": student_data.get("gender", "male"),
                        "date_of_birth": student_data.get("date_of_birth"),
                        "grade": student_data.get("grade_id") or student_data.get("grade") or student_data.get("education_level"),
                        "class_id": student_data.get("class_id"),
                        "parent_id": parent_result["parent"].get("id"),
                        "parent_user_id": parent_result["parent"].get("user_id"),
                        "parent_name": parent_result["parent"].get("full_name"),
                        "parent_phone": parent_result["parent"].get("phone"),
                        "parent_email": parent_result["parent"].get("email"),
                        "school_id": school_id,
                        "is_active": True,
                        "created_at": now,
                        "created_by": current_user.get("id")
                    }

                    # Generate QR
                    qr_code = generate_qr_code(student_doc)
                    student_doc["qr_code"] = qr_code

                    # Bounded retry on student_number collision (concurrent inserter)
                    _b_attempts = 0
                    while True:
                        try:
                            async with db.session.begin_nested():
                                await gd_insert(db.session, "students", student_doc)
                            break
                        except IntegrityError as ie:
                            _b_attempts += 1
                            msg = str(getattr(ie, "orig", ie)).lower()
                            if _b_attempts < 5 and ("student_number" in msg or "uq_students_number_school" in msg):
                                next_seq = await _next_student_sequence(db.session, school_id, _bprefix) + _b_attempts
                                student_id_code = generate_student_id(school_code, city_code, year, next_seq)
                                student_doc["student_number"] = student_id_code
                                student_doc["qr_code"] = generate_qr_code(student_doc)
                                qr_code = student_doc["qr_code"]
                                continue
                            raise
                
                # Link to parent. Scope by school_id to keep tenant
                # isolation — see the same guard in the single-create flow.
                await _gd_addtoset(
                    db.session, "parents",
                    {"id": parent_result["parent"].get("id"), "school_id": school_id},
                    {"student_ids": student_id},
                )

                # Canonical guardian_link (idempotent)
                parent_user_id = parent_result["parent"].get("user_id")
                if parent_user_id:
                    existing_link = await gd_find_one(db.session, "guardian_links", {
                        "parent_ref": parent_user_id,
                        "student_id": student_id,
                    })
                    if not existing_link:
                        await gd_insert(db.session, "guardian_links", {
                            "id": str(uuid.uuid4()),
                            "parent_ref": parent_user_id,
                            "parent_id": parent_result["parent"].get("id"),
                            "student_id": student_id,
                            "relationship": parent_result["parent"].get("relationship", "guardian"),
                            "tenant_id": school_id,
                            "is_active": True,
                            "created_at": now,
                            "created_by": current_user.get("id"),
                        })
                
                results["success"] += 1
                results["new_students"] += 1
                created_students.append({
                    "id": student_id,
                    "student_id": student_id_code,
                    "name": student_data.get("full_name"),
                    "parent_name": parent_result["parent"].get("full_name")
                })
                
            except Exception as e:
                results["errors"].append({
                    "row": idx + 1,
                    "student_name": student_data.get("full_name"),
                    "error": str(e)
                })
                results["failed"] += 1

        # Recompute the school's stored counts from live rows (Task #826) once
        # after the bulk loop so the denormalized columns stay accurate.
        from engines.entity_counts import reconcile_school_counts
        await reconcile_school_counts(db.session, school_id)

        return {
            "success": results["failed"] == 0,
            "results": results,
            "created_students": created_students[:50]  # Return first 50
        }
    
    
    return router
