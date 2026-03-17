"""
Student Creation Routes - Advanced Student + Parent Wizard
منظومة إنشاء الطلاب المتقدمة
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import qrcode
import io
import base64
import logging

logger = logging.getLogger("nassaq.student_creation_routes")


# ============== Pydantic Models ==============

class ParentData(BaseModel):
    full_name: str
    national_id: Optional[str] = None
    phone: str
    email: Optional[EmailStr] = None
    relationship: str  # father, mother, guardian
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
    date_of_birth: str
    education_level: str  # primary, middle, high
    grade_id: str
    class_id: Optional[str] = None
    
    # Parent Info
    parent: ParentData
    
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


def generate_qr_code(student_data: dict) -> str:
    """
    توليد QR Code للطالب
    """
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr_data = f"NASSAQ-STUDENT|{student_data.get('id')}|{student_data.get('student_id')}|{student_data.get('full_name')}"
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
        """
        existing_parent = None
        linked_students = []
        
        # Search by national_id first
        if parent_data.get("national_id"):
            existing_parent = await db.parents.find_one({
                "national_id": parent_data["national_id"],
                "school_id": school_id
            }, {"_id": 0})
        
        # Search by phone if not found
        if not existing_parent and parent_data.get("phone"):
            existing_parent = await db.parents.find_one({
                "phone": parent_data["phone"],
                "school_id": school_id
            }, {"_id": 0})
        
        # Search by email if not found
        if not existing_parent and parent_data.get("email"):
            existing_parent = await db.parents.find_one({
                "email": parent_data["email"],
                "school_id": school_id
            }, {"_id": 0})
        
        if existing_parent:
            # Get linked students (siblings)
            student_ids = existing_parent.get("student_ids", [])
            if student_ids:
                siblings = await db.students.find(
                    {"id": {"$in": student_ids}},
                    {"_id": 0, "id": 1, "full_name": 1, "class_id": 1}
                ).to_list(20)
                linked_students = siblings
            
            return {
                "parent": existing_parent,
                "is_new": False,
                "linked_students": linked_students
            }
        
        # Create new parent
        parent_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Generate temp password
        temp_password = generate_secure_password()
        
        # Create user account for parent
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
        await db.users.insert_one(user_doc)
        
        parent_doc = {
            "id": parent_id,
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
        
        await db.parents.insert_one(parent_doc)
        
        return {
            "parent": parent_doc,
            "is_new": True,
            "linked_students": [],
            "temp_password": temp_password
        }
    
    
    @router.post("/create")
    async def create_student_with_parent(
        request: StudentCreateRequest,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
    ):
        """
        إنشاء طالب جديد مع ولي أمره
        - إنشاء أو ربط ولي الأمر
        - اكتشاف الأشقاء تلقائياً
        - توليد Student ID
        - توليد QR Code
        """
        school_id = current_user.get("tenant_id")
        if not school_id:
            raise HTTPException(status_code=400, detail="لم يتم تحديد المدرسة")
        
        # Get school info for student ID generation
        school = await db.schools.find_one({"id": school_id}, {"_id": 0, "code": 1, "city_code": 1, "name_ar": 1})
        school_code = school.get("code", "SCH") if school else "SCH"
        city_code = school.get("city_code", "CIT") if school else "CIT"
        school_name = school.get("name_ar", "المدرسة") if school else "المدرسة"
        
        # Check for duplicate student
        if request.national_id:
            existing = await db.students.find_one({
                "national_id": request.national_id,
                "school_id": school_id
            })
            if existing:
                raise HTTPException(status_code=400, detail="الطالب موجود مسبقاً برقم الهوية هذا")
        
        if request.email:
            existing = await db.users.find_one({"email": request.email})
            if existing:
                raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
        
        # Check if linking to existing parent
        if request.link_to_parent_id:
            existing_parent = await db.parents.find_one({"id": request.link_to_parent_id, "school_id": school_id}, {"_id": 0})
            if existing_parent:
                student_ids = existing_parent.get("student_ids", [])
                siblings = await db.students.find({"id": {"$in": student_ids}}, {"_id": 0, "id": 1, "full_name": 1}).to_list(20)
                parent_result = {
                    "parent": existing_parent,
                    "is_new": False,
                    "linked_students": siblings
                }
            else:
                raise HTTPException(status_code=404, detail="ولي الأمر المحدد غير موجود")
        else:
            # Find or create parent
            parent_result = await find_or_create_parent(
                request.parent.model_dump(),
                school_id,
                current_user.get("id")
            )
        
        parent = parent_result["parent"]
        is_new_parent = parent_result["is_new"]
        siblings = parent_result["linked_students"]
        
        # Generate student ID
        year = datetime.now().strftime("%Y")
        student_count = await db.students.count_documents({"school_id": school_id}) + 1
        student_id_code = generate_student_id(school_code, city_code, year, student_count)
        
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
        await db.users.insert_one(user_doc)
        
        student_doc = {
            "id": student_id,
            "user_id": user_id,
            "student_id": student_id_code,
            "full_name": request.full_name,
            "email": student_email,
            "national_id": request.national_id,
            "gender": request.gender,
            "date_of_birth": request.date_of_birth,
            "education_level": request.education_level,
            "grade_id": request.grade_id,
            "class_id": request.class_id,
            "parent_id": parent.get("id"),
            "sibling_ids": [s.get("id") for s in siblings],
            "school_id": school_id,
            "is_active": True,
            "created_at": now,
            "created_by": current_user.get("id"),
        }
        
        # Add health data if provided
        if request.health:
            student_doc["health"] = request.health.model_dump()
        
        # Generate QR Code
        qr_code = generate_qr_code(student_doc)
        student_doc["qr_code"] = qr_code
        
        await db.students.insert_one(student_doc)
        
        # Link student to parent
        await db.parents.update_one(
            {"id": parent.get("id")},
            {"$addToSet": {"student_ids": student_id}}
        )
        
        # Link siblings
        if siblings:
            sibling_ids = [s.get("id") for s in siblings]
            # Update siblings to include new student
            await db.students.update_many(
                {"id": {"$in": sibling_ids}},
                {"$addToSet": {"sibling_ids": student_id}}
            )
        
        # Update class student count
        if request.class_id:
            await db.classes.update_one(
                {"id": request.class_id},
                {"$inc": {"student_count": 1}}
            )
        
        # Get class and grade info for response
        class_info = None
        grade_info = None
        if request.class_id:
            class_info = await db.classes.find_one({"id": request.class_id}, {"_id": 0, "name": 1})
        if request.grade_id:
            grade_info = await db.grades.find_one({"id": request.grade_id}, {"_id": 0, "name": 1})
        
        # Log action
        await db.audit_logs.insert_one({
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
        parent = await db.parents.find_one(query, {"_id": 0})
        
        if not parent:
            return {"found": False, "parent": None, "students": []}
        
        # Get linked students
        student_ids = parent.get("student_ids", [])
        students = []
        if student_ids:
            students = await db.students.find(
                {"id": {"$in": student_ids}},
                {"_id": 0, "id": 1, "full_name": 1, "class_id": 1, "grade_id": 1}
            ).to_list(20)
        
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
                
                # Generate student ID
                school = await db.schools.find_one({"id": school_id}, {"_id": 0, "code": 1, "city_code": 1})
                school_code = school.get("code", "SCH") if school else "SCH"
                city_code = school.get("city_code", "CIT") if school else "CIT"
                year = datetime.now().strftime("%Y")
                student_count = await db.students.count_documents({"school_id": school_id}) + results["new_students"] + 1
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
                await db.users.insert_one(user_doc)
                
                student_doc = {
                    "id": student_id,
                    "user_id": user_id,
                    "student_id": student_id_code,
                    "full_name": student_data.get("full_name"),
                    "email": student_email,
                    "national_id": student_data.get("national_id"),
                    "gender": student_data.get("gender", "male"),
                    "date_of_birth": student_data.get("date_of_birth"),
                    "education_level": student_data.get("education_level"),
                    "grade_id": student_data.get("grade_id"),
                    "class_id": student_data.get("class_id"),
                    "parent_id": parent_result["parent"].get("id"),
                    "school_id": school_id,
                    "is_active": True,
                    "created_at": now,
                    "created_by": current_user.get("id")
                }
                
                # Generate QR
                qr_code = generate_qr_code(student_doc)
                student_doc["qr_code"] = qr_code
                
                await db.students.insert_one(student_doc)
                
                # Link to parent
                await db.parents.update_one(
                    {"id": parent_result["parent"].get("id")},
                    {"$addToSet": {"student_ids": student_id}}
                )
                
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
        
        return {
            "success": results["failed"] == 0,
            "results": results,
            "created_students": created_students[:50]  # Return first 50
        }
    
    
    return router
