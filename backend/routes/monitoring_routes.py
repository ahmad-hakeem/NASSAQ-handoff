"""
NASSAQ Monitoring & Health Endpoints
Provides /system/health, /system/status, /system/metrics
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
import time
import os
import platform

from dependencies import db, get_current_user, require_roles, UserRole
import logging

logger = logging.getLogger("nassaq.monitoring_routes")

router = APIRouter(prefix="/system", tags=["Monitoring"])

_start_time = time.time()


@router.get("/health")
async def health_check():
    db_ok = False
    db_latency_ms = 0
    try:
        start = time.time()
        await db.command("ping")
        db_latency_ms = round((time.time() - start) * 1000, 2)
        db_ok = True
    except Exception:
        pass

    uptime_seconds = round(time.time() - _start_time)
    status = "healthy" if db_ok else "degraded"

    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": uptime_seconds,
        "database": {
            "connected": db_ok,
            "latency_ms": db_latency_ms,
        },
        "version": "3.0.0",
    }


@router.get("/status")
async def system_status(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    db_ok = False
    collections = []
    total_users = 0
    total_schools = 0
    active_users_24h = 0

    try:
        await db.command("ping")
        db_ok = True
        names = await db.list_collection_names()
        collections = sorted(names)
        total_users = await db.users.count_documents({})
        total_schools = await db.schools.count_documents({})
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        active_users_24h = await db.users.count_documents({"last_login": {"$gte": cutoff.isoformat()}})
    except Exception:
        pass

    uptime_seconds = round(time.time() - _start_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60

    return {
        "status": "operational" if db_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime": f"{hours}h {minutes}m",
        "uptime_seconds": uptime_seconds,
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "python_version": platform.python_version(),
        "database": {
            "connected": db_ok,
            "name": os.environ.get("DB_NAME", "unknown"),
            "collections_count": len(collections),
        },
        "stats": {
            "total_users": total_users,
            "total_schools": total_schools,
            "active_users_24h": active_users_24h,
        },
    }


@router.get("/deployment-safety")
async def deployment_safety_check(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    from config import config
    checklist = config.deployment_checklist()

    db_ok = False
    collection_counts = {}
    try:
        await db.command("ping")
        db_ok = True
        for coll_name in ["users", "schools", "teachers", "students", "product_issues"]:
            collection_counts[coll_name] = await db[coll_name].count_documents({})
    except Exception:
        pass

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": config.ENVIRONMENT,
        "database_name": config.DB_NAME,
        "database_connected": db_ok,
        "seed_scripts_blocked": not config.seed_allowed(),
        "destructive_ops_blocked": not config.destructive_ops_allowed(),
        "pre_flight_checklist": checklist,
        "data_snapshot": collection_counts,
        "policy": {
            "rule": "Production data must NEVER be lost, overwritten, or replaced",
            "seed_blocked_in": ["production", "staging"],
            "safe_to_deploy": checklist.get("all_passed", False) and db_ok,
        }
    }


@router.get("/metrics")
async def system_metrics(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    process_info = {}
    try:
        import psutil
        process = psutil.Process()
        mem = process.memory_info()
        process_info = {
            "memory_rss_mb": round(mem.rss / 1024 / 1024, 2),
            "memory_vms_mb": round(mem.vms / 1024 / 1024, 2),
            "cpu_percent": process.cpu_percent(),
            "threads": process.num_threads(),
        }
    except ImportError:
        process_info = {"error": "psutil not installed"}

    db_counts = {}
    try:
        db_counts = {
            "users": await db.users.count_documents({}),
            "schools": await db.schools.count_documents({}),
            "teachers": await db.teachers.count_documents({}),
            "students": await db.students.count_documents({}),
            "classes": await db.classes.count_documents({}),
            "sessions": await db.teacher_sessions.count_documents({}),
            "audit_logs": await db.audit_logs.count_documents({}),
        }
    except Exception:
        db_counts = {"error": "database unavailable"}

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - _start_time),
        "process": process_info,
        "database_counts": db_counts,
    }
