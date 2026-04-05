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
from sqlalchemy import text as sa_text
import logging

logger = logging.getLogger("nassaq.monitoring_routes")

router = APIRouter(prefix="/system", tags=["Monitoring"])

_start_time = time.time()


async def _pg_ping(db_ref):
    session = db_ref._get_session()
    if not session:
        return False, 0
    start = time.time()
    result = await session.execute(sa_text("SELECT 1"))
    result.scalar()
    latency = round((time.time() - start) * 1000, 2)
    return True, latency


async def _pg_table_count(db_ref):
    session = db_ref._get_session()
    if not session:
        return 0
    result = await session.execute(sa_text(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
    ))
    return result.scalar() or 0


@router.get("/health")
async def health_check():
    db_ok = False
    db_latency_ms = 0
    try:
        db_ok, db_latency_ms = await _pg_ping(db)
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
    table_count = 0
    total_users = 0
    total_schools = 0
    active_users_24h = 0

    try:
        db_ok, _ = await _pg_ping(db)
        if db_ok:
            table_count = await _pg_table_count(db)
            total_users = await db.users.count_documents({})
            total_schools = await db.schools.count_documents({})
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            active_users_24h = await db.users.count_documents({"last_login": {"$gte": cutoff.isoformat()}})
    except Exception as e:
        logger.warning(f"System status query error: {e}")

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
            "name": "nassaq_postgres",
            "collections_count": table_count,
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
        db_ok, _ = await _pg_ping(db)
        if db_ok:
            for coll_name in ["users", "schools", "teachers", "students", "product_issues"]:
                collection_counts[coll_name] = await db[coll_name].count_documents({})
    except Exception:
        pass

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": config.ENVIRONMENT,
        "database_name": "nassaq_postgres",
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


@router.get("/errors")
async def system_errors(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    try:
        session = db._get_session()
        if session:
            result = await session.execute(sa_text(
                "SELECT id, data->>'level' as level, data->>'message' as message, "
                "data->>'source' as source, data->>'timestamp' as timestamp "
                "FROM generic_documents WHERE collection='system_errors' "
                "ORDER BY created_at DESC LIMIT 50"
            ))
            rows = result.mappings().all()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"Error fetching system errors: {e}")
    return []


@router.get("/jobs")
async def system_jobs(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    return []


@router.get("/alerts")
async def system_alerts(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    alerts = []
    try:
        db_ok, latency = await _pg_ping(db)
        if not db_ok:
            alerts.append({
                "id": "db-health",
                "type": "critical",
                "message": "Database connection failed",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        elif latency > 500:
            alerts.append({
                "id": "db-slow",
                "type": "warning",
                "message": f"Database latency high: {latency}ms",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    except Exception:
        pass
    return alerts


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
