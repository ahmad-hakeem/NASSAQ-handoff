"""
Student Management Engine - محرك إدارة الطلاب
Handles student creation, parent linking, and related operations
"""
import logging
from datetime import datetime, timezone
from bson import ObjectId
from typing import Optional, Dict, Any, List
import re
import secrets
import string
import qrcode
import io
import base64
from pydantic import BaseModel, Field, EmailStr
from enum import Enum

logger = logging.getLogger(__name__)

# ==================== Enums ====================

class Gender(str, Enum):
    male = "male"
    female = "female"

class BloodType(str, Enum):
    A_positive = "A+"
    A_negative = "A-"
    B_positive = "B+"
    B_negative = "B-"
    AB_positive = "AB+"
    AB_negative = "AB-"
    O_positive = "O+"
    O_negative = "O-"

class ParentRelation(str, Enum):
    father = "father"
    mother = "mother"
    guardian = "guardian"
    other = "other"

# ==================== Pydantic Models ====================

class StudentBasicInfo(BaseModel):
    """Step 1: Basic student information"""
    full_name_ar: str = Field(..., min_length=3, max_length=100)
    full_name_en: Optional[str] = Field(None, max_length=100)
    national_id: str = Field(..., min_length=10, max_length=10, pattern=r'^\d{10}$')
    date_of_birth: str = Field(...)  # YYYY-MM-DD format
    gender: Gender
    nationality: str = Field(default="SA")
    grade_id: str = Field(...)  # Reference to grade
    section_id: str = Field(...)  # Reference to section

class ParentContactInfo(BaseModel):
    """Step 2: Parent/Guardian information"""
    parent_name_ar: str = Field(..., min_length=3, max_length=100)
    parent_name_en: Optional[str] = Field(None, max_length=100)
    parent_national_id: Optional[str] = Field(None, min_length=10, max_length=10, pattern=r'^\d{10}$')
    parent_phone: str = Field(..., pattern=r'^[\d+\-\s]{9,15}$')
    parent_email: Optional[EmailStr] = None
    parent_relation: ParentRelation
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    address: Optional[str] = None

class StudentHealthInfo(BaseModel):
    """Step 3: Health information"""
    blood_type: Optional[BloodType] = None
    has_chronic_conditions: bool = False
    chronic_conditions: Optional[str] = None
    has_allergies: bool = False
    allergies: Optional[str] = None
    has_disabilities: bool = False
    disabilities: Optional[str] = None
    current_medications: Optional[str] = None
    requires_special_care: bool = False
    special_care_notes: Optional[str] = None
    emergency_medical_notes: Optional[str] = None

class CreateStudentRequest(BaseModel):
    """Full student creation request"""
    basic_info: StudentBasicInfo
    parent_info: ParentContactInfo
    health_info: Optional[StudentHealthInfo] = None
    save_as_draft: bool = False

class StudentDraft(BaseModel):
    """Draft student data for incomplete submissions"""
    basic_info: Optional[Dict[str, Any]] = None
    parent_info: Optional[Dict[str, Any]] = None
    health_info: Optional[Dict[str, Any]] = None
    current_step: int = 1

# ==================== Engine Class ====================

class StudentManagementEngine:
    """Engine for managing student operations"""
    
    def __init__(self, db):
        self.db = db
        self.students_collection = db.students
        self.parents_collection = db.parents
        self.drafts_collection = db.student_drafts
        self.users_collection = db.users
        self.schools_collection = db.schools
        self.grades_collection = db.grades
        self.sections_collection = db.sections
    
    # ==================== ID Generation ====================
    
    async def _generate_student_id(self, tenant_id: str) -> str:
        """
        Generate unique student ID in format: NSS-SCH-CIT-YY-XXXX
        NSS = Platform prefix
        SCH = School code (first 3 chars)
        CIT = City code (first 3 chars)
        YY = Year (2 digits)
        XXXX = Sequential number
        """
        try:
            # Get school info
            school = await self.schools_collection.find_one({"_id": ObjectId(tenant_id)})
            if not school:
                school = await self.schools_collection.find_one({"tenant_id": tenant_id})
            
            school_code = "SCH"
            city_code = "CTY"
            
            if school:
                # Extract school code from name (first 3 chars uppercase)
                school_name = school.get("name_ar", school.get("name", "SCH"))
                school_code = ''.join(c for c in school_name[:3] if c.isalnum()).upper() or "SCH"
                
                # Extract city code
                city = school.get("city", "CTY")
                city_code = ''.join(c for c in city[:3] if c.isalnum()).upper() or "CTY"
            
            # Year (2 digits)
            year = datetime.now().strftime("%y")
            
            # Get next sequential number for this school/year
            prefix = f"NSS-{school_code}-{city_code}-{year}-"
            
            # Count existing students with this prefix
            count = await self.students_collection.count_documents({
                "student_id": {"$regex": f"^{re.escape(prefix)}"}
            })
            
            # Generate 4-digit sequential number
            seq_num = str(count + 1).zfill(4)
            
            return f"{prefix}{seq_num}"
        except Exception as e:
            logger.error(f"Error generating student ID: {e}")
            # Fallback to simple format
            timestamp = datetime.now().strftime("%y%m%d%H%M")
            random_suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
            return f"NSS-STD-{timestamp}-{random_suffix}"
    
    async def _generate_parent_id(self, tenant_id: str) -> str:
        """
        Generate unique parent ID in format: NSS-SCH-CIT-YY-PXXXX
        Similar to student ID but with P prefix for parent
        """
        try:
            # Get school info
            school = await self.schools_collection.find_one({"_id": ObjectId(tenant_id)})
            if not school:
                school = await self.schools_collection.find_one({"tenant_id": tenant_id})
            
            school_code = "SCH"
            city_code = "CTY"
            
            if school:
                school_name = school.get("name_ar", school.get("name", "SCH"))
                school_code = ''.join(c for c in school_name[:3] if c.isalnum()).upper() or "SCH"
                city = school.get("city", "CTY")
                city_code = ''.join(c for c in city[:3] if c.isalnum()).upper() or "CTY"
            
            year = datetime.now().strftime("%y")
            prefix = f"NSS-{school_code}-{city_code}-{year}-P"
            
            count = await self.parents_collection.count_documents({
                "parent_id": {"$regex": f"^{re.escape(prefix)}"}
            })
            
            seq_num = str(count + 1).zfill(4)
            
            return f"{prefix}{seq_num}"
        except Exception as e:
            logger.error(f"Error generating parent ID: {e}")
            timestamp = datetime.now().strftime("%y%m%d%H%M")
            random_suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
            return f"NSS-PRT-{timestamp}-{random_suffix}"
    
    def _generate_qr_code(self, data: str) -> str:
        """Generate QR code as base64 string"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error generating QR code: {e}")
            return ""
    
    def _generate_temp_password(self, length: int = 12) -> str:
        """Generate a secure temporary password"""
        chars = string.ascii_letters + string.digits + "!@#$%"
        password = ''.join(secrets.choice(chars) for _ in range(length))
        return password
    
    # ==================== Validation ====================
    
    async def validate_national_id(self, national_id: str, tenant_id: str) -> Dict[str, Any]:
        """Check if national ID already exists in the system"""
        # Check students
        existing_student = await self.students_collection.find_one({
            "national_id": national_id,
            "tenant_id": tenant_id,
            "is_deleted": {"$ne": True}
        })
        
        if existing_student:
            return {
                "valid": False,
                "message": "رقم الهوية مسجل مسبقاً لطالب آخر",
                "message_en": "National ID already registered for another student",
                "existing_type": "student",
                "existing_id": str(existing_student.get("student_id", ""))
            }
        
        return {"valid": True}
    
    async def validate_parent_phone(self, phone: str, tenant_id: str) -> Dict[str, Any]:
        """Check if parent phone exists and return parent info if found"""
        existing_parent = await self.parents_collection.find_one({
            "phone": phone,
            "tenant_id": tenant_id,
            "is_deleted": {"$ne": True}
        })
        
        if existing_parent:
            return {
                "exists": True,
                "parent_id": existing_parent.get("parent_id"),
                "parent_name_ar": existing_parent.get("name_ar"),
                "parent_name_en": existing_parent.get("name_en"),
                "can_link": True,
                "message": "تم العثور على ولي الأمر، يمكن ربط الطالب به",
                "message_en": "Parent found, student can be linked"
            }
        
        return {"exists": False}
    
    # ==================== CRUD Operations ====================
    
    async def create_student(
        self,
        request: CreateStudentRequest,
        tenant_id: str,
        created_by: str
    ) -> Dict[str, Any]:
        """Create a new student with all information"""
        try:
            # Validate national ID
            validation = await self.validate_national_id(request.basic_info.national_id, tenant_id)
            if not validation["valid"]:
                return {"success": False, "error": validation["message"], "error_en": validation["message_en"]}
            
            # Generate student ID
            student_id = await self._generate_student_id(tenant_id)
            
            # Generate QR code with student ID
            qr_code = self._generate_qr_code(student_id)
            
            # Create or link parent
            parent_result = await self._create_or_link_parent(
                request.parent_info,
                tenant_id,
                created_by
            )
            
            # Prepare student document
            now = datetime.now(timezone.utc)
            student_doc = {
                "student_id": student_id,
                "tenant_id": tenant_id,
                "qr_code": qr_code,
                
                # Basic info
                "full_name_ar": request.basic_info.full_name_ar,
                "full_name_en": request.basic_info.full_name_en,
                "national_id": request.basic_info.national_id,
                "date_of_birth": request.basic_info.date_of_birth,
                "gender": request.basic_info.gender.value,
                "nationality": request.basic_info.nationality,
                "grade_id": request.basic_info.grade_id,
                "section_id": request.basic_info.section_id,
                
                # Parent link
                "parent_id": parent_result.get("parent_id"),
                
                # Health info
                "health_info": request.health_info.dict() if request.health_info else None,
                
                # Status
                "status": "active",
                "enrollment_date": now.isoformat(),
                "is_deleted": False,
                
                # Audit
                "created_at": now,
                "created_by": created_by,
                "updated_at": now,
                "updated_by": created_by,
            }
            
            # Insert student
            result = await self.students_collection.insert_one(student_doc)
            
            # Create user account for student (for login)
            user_result = await self._create_student_user_account(
                student_doc,
                tenant_id,
                created_by
            )
            
            # Update parent's children list
            if parent_result.get("parent_id"):
                await self.parents_collection.update_one(
                    {"parent_id": parent_result["parent_id"]},
                    {"$addToSet": {"children": student_id}}
                )
            
            return {
                "success": True,
                "student_id": student_id,
                "qr_code": qr_code,
                "parent_id": parent_result.get("parent_id"),
                "is_new_parent": parent_result.get("is_new"),
                "user_account": user_result,
                "message": "تم إضافة الطالب بنجاح",
                "message_en": "Student added successfully"
            }
            
        except Exception as e:
            logger.error(f"Error creating student: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "حدث خطأ أثناء إضافة الطالب",
                "message_en": "Error occurred while adding student"
            }
    
    async def _create_or_link_parent(
        self,
        parent_info: ParentContactInfo,
        tenant_id: str,
        created_by: str
    ) -> Dict[str, Any]:
        """Create new parent or link to existing one"""
        # Check if parent exists by phone
        existing = await self.validate_parent_phone(parent_info.parent_phone, tenant_id)
        
        if existing.get("exists"):
            return {
                "parent_id": existing["parent_id"],
                "is_new": False
            }
        
        # Create new parent
        parent_id = await self._generate_parent_id(tenant_id)
        now = datetime.now(timezone.utc)
        
        parent_doc = {
            "parent_id": parent_id,
            "tenant_id": tenant_id,
            "name_ar": parent_info.parent_name_ar,
            "name_en": parent_info.parent_name_en,
            "national_id": parent_info.parent_national_id,
            "phone": parent_info.parent_phone,
            "email": parent_info.parent_email,
            "relation": parent_info.parent_relation.value,
            "emergency_contact": parent_info.emergency_contact,
            "emergency_phone": parent_info.emergency_phone,
            "address": parent_info.address,
            "children": [],
            "status": "active",
            "is_deleted": False,
            "created_at": now,
            "created_by": created_by,
            "updated_at": now,
        }
        
        await self.parents_collection.insert_one(parent_doc)
        
        # Create user account for parent
        await self._create_parent_user_account(parent_doc, tenant_id, created_by)
        
        return {
            "parent_id": parent_id,
            "is_new": True
        }
    
    async def _create_student_user_account(
        self,
        student_doc: Dict,
        tenant_id: str,
        created_by: str
    ) -> Dict[str, Any]:
        """Create a user account for the student"""
        try:
            temp_password = self._generate_temp_password()
            now = datetime.now(timezone.utc)
            
            # Username based on student ID
            username = student_doc["student_id"].lower().replace("-", "")
            
            # Check if user already exists
            existing = await self.users_collection.find_one({"username": username})
            if existing:
                username = f"{username}_{secrets.token_hex(2)}"
            
            user_doc = {
                "username": username,
                "email": f"{username}@nassaq.student.local",
                "password_hash": temp_password,  # Should be hashed in production
                "role": "student",
                "tenant_id": tenant_id,
                "full_name": student_doc["full_name_ar"],
                "full_name_en": student_doc.get("full_name_en"),
                "linked_entity_id": student_doc["student_id"],
                "must_change_password": True,
                "is_active": True,
                "created_at": now,
                "created_by": created_by,
            }
            
            await self.users_collection.insert_one(user_doc)
            
            return {
                "username": username,
                "temp_password": temp_password,
                "created": True
            }
        except Exception as e:
            logger.error(f"Error creating student user account: {e}")
            return {"created": False, "error": str(e)}
    
    async def _create_parent_user_account(
        self,
        parent_doc: Dict,
        tenant_id: str,
        created_by: str
    ) -> Dict[str, Any]:
        """Create a user account for the parent"""
        try:
            temp_password = self._generate_temp_password()
            now = datetime.now(timezone.utc)
            
            # Username based on parent ID or phone
            username = parent_doc["parent_id"].lower().replace("-", "")
            
            existing = await self.users_collection.find_one({"username": username})
            if existing:
                username = f"{username}_{secrets.token_hex(2)}"
            
            email = parent_doc.get("email") or f"{username}@nassaq.parent.local"
            
            user_doc = {
                "username": username,
                "email": email,
                "password_hash": temp_password,
                "role": "parent",
                "tenant_id": tenant_id,
                "full_name": parent_doc["name_ar"],
                "full_name_en": parent_doc.get("name_en"),
                "linked_entity_id": parent_doc["parent_id"],
                "phone": parent_doc["phone"],
                "must_change_password": True,
                "is_active": True,
                "created_at": now,
                "created_by": created_by,
            }
            
            await self.users_collection.insert_one(user_doc)
            
            return {
                "username": username,
                "temp_password": temp_password,
                "created": True
            }
        except Exception as e:
            logger.error(f"Error creating parent user account: {e}")
            return {"created": False, "error": str(e)}
    
    # ==================== Draft Operations ====================
    
    async def save_draft(
        self,
        draft: StudentDraft,
        tenant_id: str,
        created_by: str,
        draft_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Save student creation draft"""
        now = datetime.now(timezone.utc)
        
        draft_doc = {
            "tenant_id": tenant_id,
            "basic_info": draft.basic_info,
            "parent_info": draft.parent_info,
            "health_info": draft.health_info,
            "current_step": draft.current_step,
            "updated_at": now,
            "updated_by": created_by,
        }
        
        if draft_id:
            # Update existing draft
            result = await self.drafts_collection.update_one(
                {"_id": ObjectId(draft_id), "tenant_id": tenant_id},
                {"$set": draft_doc}
            )
            return {"draft_id": draft_id, "updated": True}
        else:
            # Create new draft
            draft_doc["created_at"] = now
            draft_doc["created_by"] = created_by
            result = await self.drafts_collection.insert_one(draft_doc)
            return {"draft_id": str(result.inserted_id), "created": True}
    
    async def get_draft(self, draft_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific draft"""
        draft = await self.drafts_collection.find_one({
            "_id": ObjectId(draft_id),
            "tenant_id": tenant_id
        })
        
        if draft:
            draft["_id"] = str(draft["_id"])
            return draft
        return None
    
    async def list_drafts(self, tenant_id: str, created_by: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all drafts for a tenant"""
        query = {"tenant_id": tenant_id}
        if created_by:
            query["created_by"] = created_by
        
        cursor = self.drafts_collection.find(query).sort("updated_at", -1).limit(50)
        drafts = await cursor.to_list(length=50)
        
        for draft in drafts:
            draft["_id"] = str(draft["_id"])
        
        return drafts
    
    async def delete_draft(self, draft_id: str, tenant_id: str) -> bool:
        """Delete a draft"""
        result = await self.drafts_collection.delete_one({
            "_id": ObjectId(draft_id),
            "tenant_id": tenant_id
        })
        return result.deleted_count > 0
    
    # ==================== Query Operations ====================
    
    async def get_student(self, student_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get student by ID"""
        student = await self.students_collection.find_one({
            "student_id": student_id,
            "tenant_id": tenant_id,
            "is_deleted": {"$ne": True}
        }, {"_id": 0})
        
        return student
    
    async def list_students(
        self,
        tenant_id: str,
        grade_id: Optional[str] = None,
        section_id: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        """List students with filters"""
        query = {
            "tenant_id": tenant_id,
            "is_deleted": {"$ne": True}
        }
        
        if grade_id:
            query["grade_id"] = grade_id
        if section_id:
            query["section_id"] = section_id
        if search:
            query["$or"] = [
                {"full_name_ar": {"$regex": search, "$options": "i"}},
                {"full_name_en": {"$regex": search, "$options": "i"}},
                {"student_id": {"$regex": search, "$options": "i"}},
                {"national_id": {"$regex": search, "$options": "i"}},
            ]
        
        total = await self.students_collection.count_documents(query)
        cursor = self.students_collection.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
        students = await cursor.to_list(length=limit)
        
        return {
            "students": students,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    
    # ==================== Options/Lookups ====================
    
    async def get_grades(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get available grades for a school"""
        cursor = self.grades_collection.find(
            {"tenant_id": tenant_id, "is_active": {"$ne": False}},
            {"_id": 0}
        )
        grades = await cursor.to_list(length=100)
        
        # If no grades found, return default grades
        if not grades:
            grades = [
                {"id": "grade_1", "name_ar": "الصف الأول", "name_en": "Grade 1", "level": 1},
                {"id": "grade_2", "name_ar": "الصف الثاني", "name_en": "Grade 2", "level": 2},
                {"id": "grade_3", "name_ar": "الصف الثالث", "name_en": "Grade 3", "level": 3},
                {"id": "grade_4", "name_ar": "الصف الرابع", "name_en": "Grade 4", "level": 4},
                {"id": "grade_5", "name_ar": "الصف الخامس", "name_en": "Grade 5", "level": 5},
                {"id": "grade_6", "name_ar": "الصف السادس", "name_en": "Grade 6", "level": 6},
            ]
        
        return grades
    
    async def get_sections(self, tenant_id: str, grade_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get available sections for a school/grade"""
        query = {"tenant_id": tenant_id, "is_active": {"$ne": False}}
        if grade_id:
            query["grade_id"] = grade_id
        
        cursor = self.sections_collection.find(query, {"_id": 0})
        sections = await cursor.to_list(length=100)
        
        # If no sections found, return default sections
        if not sections:
            sections = [
                {"id": "section_a", "name_ar": "أ", "name_en": "A", "capacity": 30},
                {"id": "section_b", "name_ar": "ب", "name_en": "B", "capacity": 30},
                {"id": "section_c", "name_ar": "ج", "name_en": "C", "capacity": 30},
            ]
        
        return sections
    
    async def get_nationalities(self) -> List[Dict[str, str]]:
        """Get list of nationalities"""
        return [
            {"code": "SA", "name_ar": "سعودي", "name_en": "Saudi"},
            {"code": "AE", "name_ar": "إماراتي", "name_en": "Emirati"},
            {"code": "KW", "name_ar": "كويتي", "name_en": "Kuwaiti"},
            {"code": "BH", "name_ar": "بحريني", "name_en": "Bahraini"},
            {"code": "OM", "name_ar": "عماني", "name_en": "Omani"},
            {"code": "QA", "name_ar": "قطري", "name_en": "Qatari"},
            {"code": "EG", "name_ar": "مصري", "name_en": "Egyptian"},
            {"code": "JO", "name_ar": "أردني", "name_en": "Jordanian"},
            {"code": "SY", "name_ar": "سوري", "name_en": "Syrian"},
            {"code": "LB", "name_ar": "لبناني", "name_en": "Lebanese"},
            {"code": "PS", "name_ar": "فلسطيني", "name_en": "Palestinian"},
            {"code": "YE", "name_ar": "يمني", "name_en": "Yemeni"},
            {"code": "IQ", "name_ar": "عراقي", "name_en": "Iraqi"},
            {"code": "SD", "name_ar": "سوداني", "name_en": "Sudanese"},
            {"code": "PK", "name_ar": "باكستاني", "name_en": "Pakistani"},
            {"code": "IN", "name_ar": "هندي", "name_en": "Indian"},
            {"code": "BD", "name_ar": "بنغالي", "name_en": "Bangladeshi"},
            {"code": "PH", "name_ar": "فلبيني", "name_en": "Filipino"},
            {"code": "ID", "name_ar": "إندونيسي", "name_en": "Indonesian"},
            {"code": "OTHER", "name_ar": "أخرى", "name_en": "Other"},
        ]
    
    async def get_blood_types(self) -> List[Dict[str, str]]:
        """Get list of blood types"""
        return [
            {"code": "A+", "name_ar": "A موجب", "name_en": "A Positive"},
            {"code": "A-", "name_ar": "A سالب", "name_en": "A Negative"},
            {"code": "B+", "name_ar": "B موجب", "name_en": "B Positive"},
            {"code": "B-", "name_ar": "B سالب", "name_en": "B Negative"},
            {"code": "AB+", "name_ar": "AB موجب", "name_en": "AB Positive"},
            {"code": "AB-", "name_ar": "AB سالب", "name_en": "AB Negative"},
            {"code": "O+", "name_ar": "O موجب", "name_en": "O Positive"},
            {"code": "O-", "name_ar": "O سالب", "name_en": "O Negative"},
        ]
    
    async def get_parent_relations(self) -> List[Dict[str, str]]:
        """Get list of parent relations"""
        return [
            {"code": "father", "name_ar": "الأب", "name_en": "Father"},
            {"code": "mother", "name_ar": "الأم", "name_en": "Mother"},
            {"code": "guardian", "name_ar": "ولي الأمر", "name_en": "Guardian"},
            {"code": "other", "name_ar": "أخرى", "name_en": "Other"},
        ]
