"""
NASSAQ - School Routes
School/Tenant management endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import bcrypt

from models import (
    SchoolCreate, SchoolResponse, SchoolStatus, UserRole
)
import logging

logger = logging.getLogger("nassaq.school_routes")
from services.audit_service import log_action


def create_school_routes(db, get_current_user, require_roles):
    """Create school management router"""
    router = APIRouter(prefix="/schools", tags=["Schools"])
    
    @router.post("", response_model=SchoolResponse)
    async def create_school(
        school_data: SchoolCreate,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """Create a new school"""
        # Auto-generate code if not provided
        if not school_data.code:
            year_suffix = datetime.now().strftime("%y")
            country_code = school_data.country[:2].upper() if school_data.country else "SA"
            last_school = await db.schools.find_one(
                {"code": {"$regex": f"^NSS-{country_code}-{year_suffix}-"}},
                sort=[("code", -1)]
            )
            if last_school and last_school.get("code"):
                try:
                    last_num = int(last_school["code"].split("-")[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            school_code = f"NSS-{country_code}-{year_suffix}-{str(next_num).zfill(4)}"
        else:
            school_code = school_data.code
        
        # Check if code exists
        existing = await db.schools.find_one({"code": school_code})
        if existing:
            raise HTTPException(status_code=400, detail="رمز المدرسة مستخدم مسبقاً")
        
        # Validate principal email
        if school_data.principal_email:
            existing_email = await db.users.find_one({"email": school_data.principal_email})
            if existing_email:
                raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
        
        school_email = school_data.email or school_data.principal_email or f"school-{school_code.lower()}@nassaq.com"
        school_phone = school_data.phone or school_data.principal_phone
        
        school_id = str(uuid.uuid4())
        school_doc = {
            "id": school_id,
            "name": school_data.name,
            "name_en": school_data.name_en,
            "code": school_code,
            "email": school_email,
            "phone": school_phone,
            "address": school_data.address,
            "city": school_data.city,
            "region": school_data.region,
            "country": school_data.country or "SA",
            "logo_url": None,
            "status": SchoolStatus.ACTIVE.value,
            "student_capacity": school_data.student_capacity,
            "current_students": 0,
            "current_teachers": 0,
            "language": school_data.language or "ar",
            "calendar_system": school_data.calendar_system or "hijri_gregorian",
            "school_type": school_data.school_type or "public",
            "stage": school_data.stage or "primary",
            "principal_name": school_data.principal_name,
            "principal_email": school_data.principal_email,
            "principal_phone": school_data.principal_phone,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("user_id")
        }
        
        await db.schools.insert_one(school_doc)
        
        # Create principal account if email provided
        if school_data.principal_email and school_data.principal_name:
            import secrets
            import string
            chars = string.ascii_letters + string.digits + "@#$"
            temp_password = ''.join(secrets.choice(chars) for _ in range(12))
            
            hashed_password = bcrypt.hashpw(temp_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            principal_id = str(uuid.uuid4())
            principal_doc = {
                "id": principal_id,
                "email": school_data.principal_email,
                "password_hash": hashed_password,
                "full_name": school_data.principal_name,
                "role": UserRole.SCHOOL_PRINCIPAL.value,
                "tenant_id": school_id,
                "phone": school_data.principal_phone,
                "is_active": True,
                "must_change_password": True,
                "preferred_language": school_data.language or "ar",
                "preferred_theme": "light",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            await db.users.insert_one(principal_doc)
            
            await log_action(
                db=db,
                action="CREATE_SCHOOL_WITH_PRINCIPAL",
                action_by=current_user.get("id", ""),
                target_type="school",
                target_id=school_id,
                details={
                    "school_code": school_code,
                    "school_name": school_data.name,
                    "principal_email": school_data.principal_email
                }
            )
        
        return SchoolResponse(
            id=school_id,
            name=school_data.name,
            name_en=school_data.name_en,
            code=school_code,
            email=school_email,
            phone=school_phone,
            address=school_data.address,
            city=school_data.city,
            region=school_data.region,
            country=school_data.country or "SA",
            logo_url=None,
            status=SchoolStatus.ACTIVE,
            student_capacity=school_data.student_capacity,
            current_students=0,
            current_teachers=0,
            created_at=school_doc["created_at"]
        )
    
    @router.get("", response_model=List[SchoolResponse])
    async def get_schools(
        status: Optional[str] = None,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.MINISTRY_REP]))
    ):
        """Get all schools"""
        query = {}
        if status:
            query["status"] = status
        
        schools = await db.schools.find(query, {"_id": 0}).to_list(1000)
        return [SchoolResponse(**s) for s in schools]
    
    @router.get("/{school_id}", response_model=SchoolResponse)
    async def get_school(school_id: str, current_user: dict = Depends(get_current_user)):
        """Get single school"""
        school = await db.schools.find_one({"id": school_id}, {"_id": 0})
        if not school:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")
        return SchoolResponse(**school)
    
    @router.put("/{school_id}/status")
    async def update_school_status(
        school_id: str,
        status: SchoolStatus,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """Update school status"""
        result = await db.schools.update_one(
            {"id": school_id},
            {"$set": {"status": status.value, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")
        return {"message": "تم تحديث حالة المدرسة"}
    
    return router
