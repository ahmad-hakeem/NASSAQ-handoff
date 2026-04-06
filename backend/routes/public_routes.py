"""
NASSAQ - Public Routes
Public endpoints that don't require authentication
"""
from fastapi import APIRouter
from datetime import datetime, timezone
import logging
import time

logger = logging.getLogger("nassaq.public_routes")

_stats_cache = {"data": None, "expires": 0}
_STATS_TTL = 60


def create_public_routes(db):
    """Create public router"""
    router = APIRouter(prefix="/public", tags=["Public"])
    
    @router.get("/stats")
    async def get_public_stats():
        """Get public platform statistics for Landing Page"""
        try:
            now = time.monotonic()
            if _stats_cache["data"] and now < _stats_cache["expires"]:
                return _stats_cache["data"]

            cached_stats = await db.platform_stats.find_one({"id": "platform_stats"})
            
            if cached_stats:
                result = {
                    "schools": cached_stats.get("total_schools", 0),
                    "students": cached_stats.get("total_students", 0),
                    "teachers": cached_stats.get("total_teachers", 0),
                    "parents": cached_stats.get("total_parents", 0),
                    "active_schools": cached_stats.get("active_schools", 0),
                    "last_updated": cached_stats.get("last_updated", "")
                }
                _stats_cache["data"] = result
                _stats_cache["expires"] = now + _STATS_TTL
                return result
            
            total_schools = await db.schools.count_documents({})
            active_schools = await db.schools.count_documents({"status": "active"})
            students_from_users = await db.users.count_documents({"role": "student"})
            students_from_col = await db.students.count_documents({})
            teachers_from_users = await db.users.count_documents({"role": "teacher"})
            teachers_from_col = await db.teachers.count_documents({})
            parents_from_users = await db.users.count_documents({"role": "parent"})
            parents_from_col = await db.parents.count_documents({})

            total_students = max(students_from_users, students_from_col)
            total_teachers = max(teachers_from_users, teachers_from_col)
            total_parents = max(parents_from_users, parents_from_col)
            
            result = {
                "schools": total_schools,
                "students": total_students,
                "teachers": total_teachers,
                "parents": total_parents,
                "active_schools": active_schools,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            _stats_cache["data"] = result
            _stats_cache["expires"] = now + _STATS_TTL
            return result
        except Exception as e:
            logger.error(f"Error fetching platform stats: {e}")
            return {
                "schools": 0,
                "students": 0,
                "teachers": 0,
                "parents": 0,
                "active_schools": 0,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
    
    @router.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "NASSAQ API"
        }
    
    return router
