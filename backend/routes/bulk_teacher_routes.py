"""
NASSAQ - Bulk Teacher Import Routes
API endpoints for bulk importing teachers
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid
import csv
import io
import logging

logger = logging.getLogger("nassaq.bulk_teacher")


class TeacherBulkData(BaseModel):
    full_name: str
    gender: Optional[str] = None
    national_id: Optional[str] = None
    phone: Optional[str] = None
    email: str
    subject: Optional[str] = None
    education_level: Optional[str] = None
    grades: Optional[str] = None
    rank: Optional[str] = None
    address: Optional[str] = None


class ParseResult(BaseModel):
    success: bool
    data: List[dict]
    errors: List[dict]
    total_rows: int


def create_bulk_teacher_routes(db, get_current_user, require_roles, UserRole, hash_password, generate_temp_password):
    """Create bulk teacher import router"""
    router = APIRouter(prefix="/teachers/bulk", tags=["Bulk Teacher Import"])
    
    @router.post("/parse", response_model=ParseResult)
    async def parse_teacher_file(
        file: UploadFile = File(...),
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Parse uploaded file and return validated data"""
        school_id = current_user.get("tenant_id")
        
        try:
            content = await file.read()
            decoded = content.decode('utf-8-sig')  # Handle BOM
            
            reader = csv.DictReader(io.StringIO(decoded))
            
            data = []
            errors = []
            row_num = 0
            
            # Get existing emails and national IDs for duplicate check
            existing_emails = set()
            existing_ids = set()
            async for doc in db.teachers.find({"school_id": school_id}, {"email": 1, "national_id": 1}):
                if doc.get("email"):
                    existing_emails.add(doc["email"].lower())
                if doc.get("national_id"):
                    existing_ids.add(doc["national_id"])
            
            for row in reader:
                row_data = {}
                row_errors = []
                
                # Map columns (support Arabic and English headers)
                name_keys = ['full_name', 'اسم المعلم الكامل', 'الاسم', 'Name', 'Teacher Name']
                email_keys = ['email', 'البريد الإلكتروني', 'البريد', 'Email']
                phone_keys = ['phone', 'رقم الهاتف', 'الهاتف', 'Phone']
                id_keys = ['national_id', 'رقم الهوية', 'الهوية', 'National ID', 'ID']
                gender_keys = ['gender', 'الجنس', 'Gender']
                subject_keys = ['subject', 'المادة', 'المادة الدراسية', 'Subject']
                level_keys = ['education_level', 'المرحلة التعليمية', 'المرحلة', 'Level', 'Education Level']
                grades_keys = ['grades', 'الصفوف', 'الصفوف التي يدرسها', 'Grades', 'Teaching Grades']
                rank_keys = ['rank', 'الرتبة', 'الرتبة المهنية', 'Rank', 'Teacher Rank']
                address_keys = ['address', 'العنوان', 'Address']
                
                def get_value(keys):
                    for key in keys:
                        if key in row and row[key].strip():
                            return row[key].strip()
                    return None
                
                # Extract values
                row_data['full_name'] = get_value(name_keys)
                row_data['email'] = get_value(email_keys)
                row_data['phone'] = get_value(phone_keys)
                row_data['national_id'] = get_value(id_keys)
                row_data['gender'] = get_value(gender_keys)
                row_data['subject'] = get_value(subject_keys)
                row_data['education_level'] = get_value(level_keys)
                row_data['grades'] = get_value(grades_keys)
                row_data['rank'] = get_value(rank_keys)
                row_data['address'] = get_value(address_keys)
                
                # Validate required fields
                if not row_data['full_name']:
                    row_errors.append("الاسم مطلوب / Name required")
                if not row_data['email']:
                    row_errors.append("البريد الإلكتروني مطلوب / Email required")
                elif row_data['email'].lower() in existing_emails:
                    row_errors.append("البريد الإلكتروني مستخدم مسبقاً / Email already exists")
                
                if row_data['national_id'] and row_data['national_id'] in existing_ids:
                    row_errors.append("رقم الهوية مستخدم مسبقاً / National ID already exists")
                
                if row_errors:
                    errors.append({"row": row_num, "message": "; ".join(row_errors)})
                else:
                    existing_emails.add(row_data['email'].lower())
                    if row_data['national_id']:
                        existing_ids.add(row_data['national_id'])
                
                data.append(row_data)
                row_num += 1
            
            return ParseResult(
                success=True,
                data=data,
                errors=errors,
                total_rows=row_num
            )
            
        except Exception as e:
            logger.error(f"File parse error: {e}")
            raise HTTPException(status_code=400, detail="فشل تحليل الملف — تأكد من صيغة الملف")
    
    @router.post("/create-single")
    async def create_single_teacher_bulk(
        teacher_data: TeacherBulkData,
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Create a single teacher from bulk import data"""
        school_id = current_user.get("tenant_id")
        
        # Check duplicate email
        existing = await db.teachers.find_one({"email": teacher_data.email, "school_id": school_id})
        if existing:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
        
        # Generate teacher ID
        year = datetime.now().strftime("%y")
        count = await db.teachers.count_documents({"school_id": school_id})
        teacher_id = f"TCH-{year}-{str(count + 1).zfill(4)}"
        
        # Generate temp password
        temp_password = generate_temp_password()
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Create teacher record
        teacher_doc = {
            "id": str(uuid.uuid4()),
            "teacher_id": teacher_id,
            "full_name": teacher_data.full_name,
            "email": teacher_data.email,
            "phone": teacher_data.phone,
            "national_id": teacher_data.national_id,
            "gender": teacher_data.gender,
            "specialization": teacher_data.subject,
            "education_level": teacher_data.education_level,
            "grades": teacher_data.grades,
            "rank": teacher_data.rank,
            "address": teacher_data.address,
            "school_id": school_id,
            "is_active": True,
            "created_at": now,
            "created_by": current_user["id"]
        }
        
        await db.teachers.insert_one(teacher_doc)
        
        # Create user account
        user_doc = {
            "id": str(uuid.uuid4()),
            "email": teacher_data.email,
            "password_hash": hash_password(temp_password),
            "full_name": teacher_data.full_name,
            "role": "teacher",
            "tenant_id": school_id,
            "phone": teacher_data.phone,
            "is_active": True,
            "must_change_password": True,
            "preferred_language": "ar",
            "preferred_theme": "light",
            "created_at": now
        }
        
        await db.users.insert_one(user_doc)
        
        return {
            "success": True,
            "teacher_id": teacher_id,
            "email": teacher_data.email,
            "temp_password": temp_password
        }
    
    @router.post("/import")
    async def bulk_import_teachers(
        teachers: List[TeacherBulkData],
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Import multiple teachers at once"""
        school_id = current_user.get("tenant_id")
        
        created = 0
        failed = 0
        results = []
        
        for teacher_data in teachers:
            try:
                # Check duplicate
                existing = await db.teachers.find_one({"email": teacher_data.email, "school_id": school_id})
                if existing:
                    results.append({"email": teacher_data.email, "success": False, "error": "Email exists"})
                    failed += 1
                    continue
                
                # Generate IDs
                year = datetime.now().strftime("%y")
                count = await db.teachers.count_documents({"school_id": school_id})
                teacher_id = f"TCH-{year}-{str(count + 1).zfill(4)}"
                temp_password = generate_temp_password()
                now = datetime.now(timezone.utc).isoformat()
                
                # Create teacher
                teacher_doc = {
                    "id": str(uuid.uuid4()),
                    "teacher_id": teacher_id,
                    "full_name": teacher_data.full_name,
                    "email": teacher_data.email,
                    "phone": teacher_data.phone,
                    "national_id": teacher_data.national_id,
                    "gender": teacher_data.gender,
                    "specialization": teacher_data.subject,
                    "school_id": school_id,
                    "is_active": True,
                    "created_at": now,
                    "created_by": current_user["id"]
                }
                await db.teachers.insert_one(teacher_doc)
                
                # Create user account
                user_doc = {
                    "id": str(uuid.uuid4()),
                    "email": teacher_data.email,
                    "password_hash": hash_password(temp_password),
                    "full_name": teacher_data.full_name,
                    "role": "teacher",
                    "tenant_id": school_id,
                    "is_active": True,
                    "must_change_password": True,
                    "preferred_language": "ar",
                    "created_at": now
                }
                await db.users.insert_one(user_doc)
                
                results.append({
                    "email": teacher_data.email,
                    "success": True,
                    "teacher_id": teacher_id,
                    "temp_password": temp_password
                })
                created += 1
                
            except Exception as e:
                results.append({"email": teacher_data.email, "success": False, "error": str(e)})
                failed += 1
        
        return {
            "success": True,
            "total": len(teachers),
            "created": created,
            "failed": failed,
            "results": results
        }
    
    return router
