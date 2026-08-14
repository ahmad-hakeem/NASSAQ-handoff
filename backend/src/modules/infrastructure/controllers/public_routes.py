"""
NASSAQ - Public Routes
Public endpoints that don't require authentication
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
import logging
import time
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate
from dependencies import get_current_user
from src.common.utils.tenant_scope import _PLATFORM_ROLES

logger = logging.getLogger("nassaq.public_routes")

_stats_cache = {"data": None, "expires": 0}
_STATS_TTL = 60


def create_public_routes(db):
    """Create public router"""
    router = APIRouter(prefix="/public", tags=["Public"])

    @router.get("/stats")
    async def get_public_stats(current_user: dict = Depends(get_current_user)):
        # SECURITY (audit C-4): platform-wide aggregates are no longer
        # publicly readable — tenant/usage enumeration is a sovereign-grade
        # red line. Restricted to platform admins.
        if current_user.get("role") not in _PLATFORM_ROLES:
            raise HTTPException(status_code=403, detail="غير مصرح بالوصول")
        """Get public platform statistics for Landing Page"""
        try:
            now = time.monotonic()
            if _stats_cache["data"] and now < _stats_cache["expires"]:
                return _stats_cache["data"]

            cached_stats = await gd_find_one(db.session, "platform_stats", {"id": "platform_stats"})
            
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
            
            total_schools = await gd_count(db.session, "schools", {})
            active_schools = await gd_count(db.session, "schools", {"status": "active"})
            students_from_users = await gd_count(db.session, "users", {"role": "student"})
            students_from_col = await gd_count(db.session, "students", {})
            teachers_from_users = await gd_count(db.session, "users", {"role": "teacher"})
            teachers_from_col = await gd_count(db.session, "teachers", {})
            parents_from_users = await gd_count(db.session, "users", {"role": "parent"})
            parents_from_col = await gd_count(db.session, "parents", {})

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
