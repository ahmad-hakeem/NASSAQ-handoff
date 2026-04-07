"""
NASSAQ — Application startup and shutdown hooks.
"""
import os
import uuid
import logging
from datetime import datetime, timezone

from dependencies import db, hash_password
from db import async_session_factory, init_pg_tables, close_pg_engine
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate

logger = logging.getLogger("nassaq")


async def _run_with_session(label: str, coro_fn):
    async with async_session_factory() as s:
        db.set_session(s)
        try:
            result = await coro_fn()
            await s.commit()
            return result
        except Exception as e:
            await s.rollback()
            logger.warning(f"{label}: {e}")
            return None
        finally:
            db.set_session(None)


async def _seed_platform_admins():
    admins = [
        {
            "full_name": "Dr. Ahmad Zalat",
            "email": "zalat@nassaqapp.com",
            "password": os.environ.get("ADMIN_SEED_PASSWORD_ZALAT", ""),
            "role": "platform_admin",
        },
        {
            "full_name": "Ahmed Hakim",
            "email": "hakim@nassaqapp.com",
            "password": os.environ.get("ADMIN_SEED_PASSWORD_HAKIM", ""),
            "role": "platform_admin",
        },
    ]
    for admin in admins:
        if not admin["password"]:
            logger.warning(f"Skipping admin seed for {admin['email']}: password env var not set")
            continue
        existing = await gd_find_one(db.session, "users", {"email": admin["email"]})
        if not existing:
            user_doc = {
                "id": str(uuid.uuid4()),
                "email": admin["email"],
                "full_name": admin["full_name"],
                "password_hash": hash_password(admin["password"]),
                "role": admin["role"],
                "is_active": True,
                "tenant_id": None,
                "phone": None,
                "avatar_url": None,
                "preferred_language": "ar",
                "preferred_theme": "light",
                "must_change_password": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await gd_insert(db.session, "users", user_doc)
            logger.info(f"Seeded platform admin: {admin['email']}")
        else:
            if existing.get("role") != "platform_admin":
                await gd_update_one(db.session, "users", {"email": admin["email"]}, {"role": "platform_admin"})
                logger.info(f"Updated role to platform_admin: {admin['email']}")


async def startup_tasks():
    from config import config

    issues = config.validate()
    if issues:
        for issue in issues:
            logger.warning(f"Config issue: {issue}")
    logger.info(f"NASSAQ v{config.VERSION} starting in {config.ENVIRONMENT} mode")
    logger.info(f"Database: PostgreSQL | Seed allowed: {config.seed_allowed()} | Destructive ops: {config.destructive_ops_allowed()}")

    checklist = config.deployment_checklist()
    if config.is_production() and not checklist["all_passed"]:
        failed = {k: v for k, v in checklist.items() if v is False}
        logger.error(f"DEPLOYMENT SAFETY: Pre-flight checks FAILED: {failed}")

    try:
        await init_pg_tables()
        logger.info("PostgreSQL tables verified on startup")
    except Exception as e:
        logger.warning(f"PostgreSQL init on startup: {e}")

    try:
        from db import get_sync_engine
        from middleware.query_monitor import install_query_timing, start_pool_monitor
        sync_eng = get_sync_engine()
        install_query_timing(sync_eng)
        start_pool_monitor(sync_eng)
        logger.info("Query timing and pool monitor installed")
    except Exception as e:
        logger.warning(f"Query monitor setup: {e}")

    from engines.approval_engine import approval_engine
    from engines.approval_handlers import TeacherApprovalHandler, SchoolApprovalHandler
    approval_engine.register(TeacherApprovalHandler())
    approval_engine.register(SchoolApprovalHandler())
    logger.info(f"Approval engine initialized with {len(approval_engine.get_registered_types())} handler(s)")

    async def _product_hub_integrity():
        try:
            from routes.product_hub_routes import _ensure_issue_counter, _ensure_data_integrity
            await _ensure_issue_counter()
            integrity = await _ensure_data_integrity()
            logger.info(f"Product hub data integrity: {integrity}")
        except Exception as e:
            logger.warning(f"Product hub data integrity check: {e}")

    await _run_with_session("Product hub integrity", _product_hub_integrity)

    db_has_data = False

    async def _data_snapshot():
        nonlocal db_has_data
        user_count_result = await gd_count(db.session, "users", {})
        db_has_data = user_count_result > 0
        school_count = await gd_count(db.session, "schools", {})
        student_count = await gd_count(db.session, "students", {})
        teacher_count = await gd_count(db.session, "teachers", {})
        logger.info(f"DEPLOYMENT SAFETY: Data snapshot on startup — users={user_count_result}, schools={school_count}, students={student_count}, teachers={teacher_count}")

    await _run_with_session("Data snapshot", _data_snapshot)

    if config.seed_allowed() and not db_has_data:
        await _run_with_session("Seed admins", _seed_platform_admins)

        from seeds.timetable_hard_constraints import seed_hard_constraints
        result = await _run_with_session("Hard constraints", lambda: seed_hard_constraints(db))
        if result:
            logger.info(f"Timetable hard constraints: {result}")

        from seeds.timetable_soft_constraints import seed_soft_constraints
        result = await _run_with_session("Soft constraints", lambda: seed_soft_constraints(db))
        if result:
            logger.info(f"Timetable soft constraints: {result}")
    elif config.seed_allowed() and db_has_data:
        logger.info("DEPLOYMENT SAFETY: Seed scripts SKIPPED (database already has data)")
    else:
        logger.info(f"DEPLOYMENT SAFETY: Seed scripts SKIPPED (environment={config.ENVIRONMENT})")


async def shutdown_tasks():
    try:
        from routes.websocket_routes import get_connection_manager
        mgr = get_connection_manager()
        for user_id in list(mgr.active_connections.keys()):
            for conn in mgr.active_connections[user_id]:
                try:
                    await conn.close(code=1001, reason="Server shutting down")
                except Exception:
                    pass
        mgr.active_connections.clear()
        mgr.role_connections.clear()
        mgr.tenant_connections.clear()
    except Exception as e:
        logger.debug(f"WS cleanup on shutdown: {e}")
    await close_pg_engine()
    logger.info("NASSAQ shutdown complete")
