"""
NASSAQ - Dashboard Routes
Dashboard and statistics endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from datetime import datetime, timezone, timedelta

from models import DashboardStats, UserRole
import logging

logger = logging.getLogger("nassaq.dashboard_routes")


def create_dashboard_routes(db, get_current_user, require_roles):
    """Create dashboard router"""
    router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
    
    @router.get("/stats", response_model=DashboardStats)
    async def get_dashboard_stats(
        current_user: dict = Depends(get_current_user),
        scope: Optional[str] = None,
        school_id: Optional[str] = None,
        school_ids: Optional[str] = None,
        city: Optional[str] = None,
        region: Optional[str] = None,
        school_type: Optional[str] = None,
        time_window: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None
    ):
        """Get dashboard statistics with optional filtering"""
        
        if current_user["role"] == UserRole.PLATFORM_ADMIN.value:
            # Build filters
            school_filter = {}
            student_filter = {}
            teacher_filter = {}
            
            if scope == 'single' and school_id:
                school_filter["id"] = school_id
                student_filter["school_id"] = school_id
                teacher_filter["school_id"] = school_id
            elif scope == 'multi' and school_ids:
                school_id_list = [s.strip() for s in school_ids.split(',') if s.strip()]
                if school_id_list:
                    school_filter["id"] = {"$in": school_id_list}
                    student_filter["school_id"] = {"$in": school_id_list}
                    teacher_filter["school_id"] = {"$in": school_id_list}
            
            if city:
                school_filter["city"] = city
            if region:
                school_filter["region"] = region
            if school_type:
                school_filter["school_type"] = school_type
            if status and status != 'all':
                school_filter["status"] = status
            
            # Count stats
            total_schools = await db.schools.count_documents(school_filter)
            active_filter = {**school_filter, "status": "active"}
            active_schools = await db.schools.count_documents(active_filter)
            pending_filter = {**school_filter, "status": "pending"}
            pending_schools = await db.schools.count_documents(pending_filter)
            suspended_filter = {**school_filter, "status": "suspended"}
            suspended_schools = await db.schools.count_documents(suspended_filter)
            setup_filter = {**school_filter, "status": "setup"}
            setup_schools = await db.schools.count_documents(setup_filter)
            
            # Students and Teachers
            total_students = await db.students.count_documents(student_filter if student_filter else {})
            total_teachers = await db.teachers.count_documents(teacher_filter if teacher_filter else {})
            
            # Users
            total_users = await db.users.count_documents({})
            active_users = await db.users.count_documents({"is_active": True})
            
            # Classes and subjects
            total_classes = await db.classes.count_documents({})
            total_subjects = await db.subjects.count_documents({})
            
            # Pending requests
            pending_requests = await db.registration_requests.count_documents({"status": "pending"})
            
            return DashboardStats(
                total_schools=total_schools,
                total_students=total_students,
                total_teachers=total_teachers,
                active_schools=active_schools,
                pending_schools=pending_schools,
                suspended_schools=suspended_schools,
                setup_schools=setup_schools,
                total_users=total_users,
                pending_requests=pending_requests,
                active_users=active_users,
                total_classes=total_classes,
                total_subjects=total_subjects
            )
        
        # School-level stats
        elif current_user["role"] in [UserRole.SCHOOL_PRINCIPAL.value, UserRole.SCHOOL_ADMIN.value]:
            tenant_id = current_user.get("tenant_id")
            if not tenant_id:
                return DashboardStats()
            
            total_students = await db.students.count_documents({"school_id": tenant_id})
            total_teachers = await db.teachers.count_documents({"school_id": tenant_id})
            total_classes = await db.classes.count_documents({"school_id": tenant_id})
            
            return DashboardStats(
                total_schools=1,
                active_schools=1,
                total_students=total_students,
                total_teachers=total_teachers,
                total_classes=total_classes
            )
        
        return DashboardStats()
    
    @router.get("/school/{school_id}")
    async def get_school_dashboard(
        school_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get school-specific dashboard data"""
        # Verify access
        if current_user["role"] not in [UserRole.PLATFORM_ADMIN.value]:
            if current_user.get("tenant_id") != school_id:
                raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Get school info
        school = await db.schools.find_one({"id": school_id}, {"_id": 0})
        if not school:
            raise HTTPException(status_code=404, detail="School not found")
        
        # Get counts
        total_students = await db.students.count_documents({"school_id": school_id, "is_active": True})
        total_teachers = await db.teachers.count_documents({"school_id": school_id, "is_active": True})
        total_classes = await db.classes.count_documents({"school_id": school_id, "is_active": True})
        
        # Today's attendance
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        attendance_today = await db.attendance.count_documents({
            "school_id": school_id,
            "date": today
        })
        
        present_today = await db.attendance.count_documents({
            "school_id": school_id,
            "date": today,
            "status": "present"
        })
        
        return {
            "school": school,
            "metrics": {
                "total_students": total_students,
                "total_teachers": total_teachers,
                "total_classes": total_classes,
                "attendance_today": attendance_today,
                "present_today": present_today
            }
        }
    
    return router
