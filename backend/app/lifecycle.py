"""
NASSAQ — Application startup and shutdown hooks.
"""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta as _td

from dependencies import db, hash_password
from src.core.database.db import async_session_factory, init_pg_tables, close_pg_engine
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, gd_iter_rows, _gd_aggregate

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
    admins = []

    # Single admin from ConfigMap / Secret / Env
    single_email = os.environ.get("ADMIN_SEED_EMAIL")
    single_pass = os.environ.get("ADMIN_SEED_PASSWORD")
    single_name = os.environ.get("ADMIN_SEED_NAME", "Platform Admin")

    if single_email and single_pass:
        admins.append({
            "full_name": single_name,
            "email": single_email,
            "password": single_pass,
            "role": "platform_admin",
        })

    zalat_pass = os.environ.get("ADMIN_SEED_PASSWORD_ZALAT", "")
    if zalat_pass:
        admins.append({
            "full_name": "Dr. Ahmad Zalat",
            "email": "zalat@nassaqapp.com",
            "password": zalat_pass,
            "role": "platform_admin",
        })

    hakim_pass = os.environ.get("ADMIN_SEED_PASSWORD_HAKIM", "")
    if hakim_pass:
        admins.append({
            "full_name": "Ahmed Hakim",
            "email": "hakim@nassaqapp.com",
            "password": hakim_pass,
            "role": "platform_admin",
        })

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

    # Optional error/alert sink — no-op unless SENTRY_DSN is configured.
    try:
        from services.observability import init_observability

        init_observability()
    except Exception as obs_err:  # never block boot on observability
        logger.warning(f"Observability init skipped: {obs_err}")

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
        schema_status = await init_pg_tables()
        logger.info("PostgreSQL tables verified on startup")
        # Runtime-only sequences (not Alembic-owned). Isolated from the schema
        # gate so a DDL/privilege issue here can never block production boot.
        try:
            from src.core.database.db import ensure_runtime_sequences
            await ensure_runtime_sequences()
        except Exception as seq_err:
            logger.warning(f"Runtime sequence ensure skipped: {seq_err}")
        # DEPLOYMENT SAFETY: in production, refuse to serve traffic against a
        # schema that is not at the latest Alembic head. This fails fast on a
        # partial/forgotten migration instead of silently serving 500s (or, on
        # a fresh/empty DB, booting with no tables at all).
        if config.is_production() and not schema_status.get("at_head"):
            msg = (
                "DEPLOYMENT SAFETY: Database schema is not at the latest Alembic head "
                f"(db={schema_status.get('db_version')}, head={schema_status.get('head_version')}). "
                "Run 'alembic upgrade head' against this database before serving traffic."
            )
            logger.critical(msg)
            raise RuntimeError(msg)
    except RuntimeError:
        raise
    except Exception as e:
        if config.is_production():
            logger.critical(f"DEPLOYMENT SAFETY: PostgreSQL schema verification failed in production: {e}")
            raise
        logger.warning(f"PostgreSQL init on startup: {e}")

    try:
        from src.core.database.db import get_sync_engine
        from src.core.middleware.query_monitor import install_query_timing, start_pool_monitor
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

    # Non-critical startup maintenance is deferred to a background task so the
    # ASGI lifespan startup returns promptly and the app begins serving (and
    # answering the autoscale healthcheck on GET /) without waiting on these DB
    # round-trips. The schema head-gate above stays BLOCKING — it is the
    # production safety guarantee and must complete before we serve any traffic.
    # Product-hub integrity is a self-healing maintenance pass and the data
    # snapshot is informational logging; both are safe to run a beat late.
    async def _deferred_startup_maintenance():
        # Yield once so the event loop can finish bringing the server up and
        # start answering the healthcheck before we hold a DB session.
        await _asyncio.sleep(0)

        async def _product_hub_integrity():
            try:
                from src.modules.platform.controllers.product_hub_routes import _ensure_issue_counter, _ensure_data_integrity
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

        # Always run platform admin seed if explicit ADMIN_SEED_EMAIL & ADMIN_SEED_PASSWORD are configured
        if (os.environ.get("ADMIN_SEED_EMAIL") and os.environ.get("ADMIN_SEED_PASSWORD")) or (config.seed_allowed() and not db_has_data):
            await _run_with_session("Seed admins", _seed_platform_admins)

        if config.seed_allowed() and not db_has_data:
            from seeds.timetable_hard_constraints import seed_hard_constraints
            result = await _run_with_session("Hard constraints", lambda: seed_hard_constraints(db))
            if result:
                logger.info(f"Timetable hard constraints: {result}")

            from seeds.timetable_soft_constraints import seed_soft_constraints
            result = await _run_with_session("Soft constraints", lambda: seed_soft_constraints(db))
            if result:
                logger.info(f"Timetable soft constraints: {result}")
        elif db_has_data:
            logger.info("DEPLOYMENT SAFETY: Demo seed scripts SKIPPED (database already has data)")
        else:
            logger.info(f"DEPLOYMENT SAFETY: Demo seed scripts SKIPPED (environment={config.ENVIRONMENT})")

    import asyncio as _asyncio
    try:
        global _deferred_maintenance_task
        _deferred_maintenance_task = _asyncio.create_task(_deferred_startup_maintenance())
        logger.info("Deferred startup maintenance scheduled (product-hub integrity + data snapshot)")
    except Exception as e:
        logger.warning(f"Could not schedule deferred startup maintenance: {e}")

    # Background task: periodically purge expired revoked tokens (D-02).
    # Runs once at startup (after a short delay) and then every 6 hours.
    import asyncio as _asyncio
    from datetime import datetime as _dt, timezone as _tz

    async def _purge_revoked_tokens_loop():
        try:
            await _asyncio.sleep(30)
            while True:
                try:
                    async def _purge():
                        from sqlalchemy import delete as _sa_delete
                        from src.common.entities import RevokedToken
                        now = _dt.now(_tz.utc)
                        res = await db.session.execute(
                            _sa_delete(RevokedToken).where(RevokedToken.expires_at < now)
                        )
                        deleted = getattr(res, "rowcount", 0) or 0
                        if deleted:
                            logger.info(f"Revoked-token cleanup: purged {deleted} expired token(s)")
                    # _run_with_session handles the commit, no need to commit inside _purge
                    await _run_with_session("Revoked token cleanup", _purge)
                except Exception as e:
                    logger.warning(f"Revoked-token cleanup loop: {e}")
                await _asyncio.sleep(6 * 60 * 60)
        except _asyncio.CancelledError:
            logger.info("Revoked-token cleanup loop cancelled (shutdown)")
            raise

    try:
        # Retain a handle so shutdown_tasks can cancel it cleanly.
        global _revoked_token_cleanup_task
        _revoked_token_cleanup_task = _asyncio.create_task(_purge_revoked_tokens_loop())
        logger.info("Revoked-token cleanup loop scheduled (every 6h)")
    except Exception as e:
        logger.warning(f"Could not schedule revoked-token cleanup: {e}")

    # Background task: scheduled sweep of expired rate_limit_counters rows.
    # The limiter's own opportunistic sweep (~1% of shared-store checks)
    # cannot be relied on: the deny cache short-circuits repeat hits against
    # a blocked key without touching the DB, so a credential-stuffing burst
    # grows the table and then stops generating the very traffic that would
    # clean it up. This loop guarantees reclamation with zero limiter
    # traffic. The sweep itself is bounded (batched DELETEs inside
    # SharedRateLimitStore._sweep) so it can never become a load spike.
    try:
        global _rate_limit_sweep_task
        _rate_limit_sweep_task = _asyncio.create_task(_rate_limit_sweep_loop())
        logger.info("Rate-limit counter sweep loop scheduled (every 15m)")
    except Exception as e:
        logger.warning(f"Could not schedule rate-limit counter sweep: {e}")

    # Background task: daily sweep that emails archived IT workspaces a
    # reminder ~3 days before their 30-day reactivation window closes.
    # Idempotent via schools.reactivation_reminder_sent_at — once stamped
    # we never re-send for the same archive cycle. Safe to run on every
    # backend instance: the row update + null-guard makes a duplicate
    # send vanishingly unlikely even with multiple workers (and a
    # duplicate email is still a non-event).
    async def _reactivation_reminder_loop():
        try:
            await _asyncio.sleep(60)
            while True:
                try:
                    await _run_with_session(
                        "Workspace reactivation reminder sweep",
                        _sweep_reactivation_reminders,
                    )
                except Exception as e:
                    logger.warning(f"Reactivation reminder loop: {e}")
                await _asyncio.sleep(24 * 60 * 60)
        except _asyncio.CancelledError:
            logger.info("Reactivation reminder loop cancelled (shutdown)")
            raise

    try:
        global _reactivation_reminder_task
        _reactivation_reminder_task = _asyncio.create_task(_reactivation_reminder_loop())
        logger.info("Workspace reactivation reminder loop scheduled (daily)")
    except Exception as e:
        logger.warning(f"Could not schedule reactivation reminder loop: {e}")

    # Background task: hourly sweep that mints a fresh single-use 24h
    # workspace export URL for every IT workspace whose
    # ``auto_export_enabled=TRUE`` AND whose chosen day-of-week + hour
    # matches the current UTC tick. Idempotent within 6h via
    # ``workspace_quota.auto_export_last_run_at``. See Task #275.
    async def _auto_export_loop():
        try:
            await _asyncio.sleep(90)
            while True:
                try:
                    await _run_with_session(
                        "Workspace auto-export sweep",
                        _sweep_auto_exports,
                    )
                except Exception as e:
                    logger.warning(f"Auto-export loop: {e}")
                await _asyncio.sleep(60 * 60)
        except _asyncio.CancelledError:
            logger.info("Auto-export loop cancelled (shutdown)")
            raise

    try:
        global _auto_export_task
        _auto_export_task = _asyncio.create_task(_auto_export_loop())
        logger.info("Workspace auto-export loop scheduled (hourly)")
    except Exception as e:
        logger.warning(f"Could not schedule auto-export loop: {e}")

    # Task #276 — daily sweep that physically purges IT workspaces
    # whose erasure grace window has elapsed (GDPR right-to-be-forgotten).
    async def _erasure_purge_loop():
        try:
            await _asyncio.sleep(90)
            while True:
                try:
                    await _run_with_session(
                        "Workspace erasure purge sweep",
                        _sweep_erasure_purges,
                    )
                except Exception as e:
                    logger.warning(f"Erasure purge loop: {e}")
                await _asyncio.sleep(24 * 60 * 60)
        except _asyncio.CancelledError:
            logger.info("Erasure purge loop cancelled (shutdown)")
            raise

    try:
        global _erasure_purge_task
        _erasure_purge_task = _asyncio.create_task(_erasure_purge_loop())
        logger.info("Workspace erasure purge loop scheduled (daily)")
    except Exception as e:
        logger.warning(f"Could not schedule erasure purge loop: {e}")

    # Background task: sweep that finalises any lesson left open past the end
    # of its school day (in the school's timezone), for both regular and IT
    # workspaces. Closes via the normal end-of-lesson pipeline; see the
    # ``_sweep_auto_close_sessions`` docstring for isolation/idempotency.
    async def _auto_close_loop():
        try:
            await _asyncio.sleep(120)
            while True:
                try:
                    await _sweep_auto_close_sessions()
                except Exception as e:
                    logger.warning(f"End-of-day auto-close loop: {e}")
                await _asyncio.sleep(_AUTO_CLOSE_INTERVAL_SECONDS)
        except _asyncio.CancelledError:
            logger.info("End-of-day auto-close loop cancelled (shutdown)")
            raise

    try:
        global _auto_close_task
        _auto_close_task = _asyncio.create_task(_auto_close_loop())
        logger.info("End-of-day lesson auto-close loop scheduled (every 30m)")
    except Exception as e:
        logger.warning(f"Could not schedule end-of-day auto-close loop: {e}")

    # Background task: Automated scheduled message and notification dispatch loop.
    # Runs every 30 seconds to automatically deliver scheduled communications when due.
    async def _scheduled_dispatch_loop():
        try:
            await _asyncio.sleep(10)
            while True:
                try:
                    async def _dispatch_job():
                        from src.modules.communication.services.scheduled_dispatch_service import dispatch_all_due_communications
                        await dispatch_all_due_communications(db)

                    await _run_with_session("Scheduled communication dispatch", _dispatch_job)
                except Exception as e:
                    logger.warning(f"Scheduled communication dispatch loop: {e}")
                await _asyncio.sleep(30)
        except _asyncio.CancelledError:
            logger.info("Scheduled communication dispatch loop cancelled (shutdown)")
            raise

    try:
        global _scheduled_dispatch_task
        _scheduled_dispatch_task = _asyncio.create_task(_scheduled_dispatch_loop())
        logger.info("Scheduled communication dispatch loop scheduled (every 30s)")
    except Exception as e:
        logger.warning(f"Could not schedule communication dispatch loop: {e}")


_revoked_token_cleanup_task = None
_rate_limit_sweep_task = None
_scheduled_dispatch_task = None


async def _rate_limit_sweep_loop(initial_delay_s: float = 60.0,
                                 interval_s: float = 15 * 60.0):
    """Scheduled sweep of expired ``rate_limit_counters`` rows.

    Module-level (rather than a startup closure) so tests can drive it with
    short delays. Re-raises ``CancelledError`` so the task ends in the
    proper CANCELLED state; the awaiter in ``shutdown_tasks`` catches it
    explicitly.
    """
    import asyncio as _a
    try:
        await _a.sleep(initial_delay_s)
        while True:
            try:
                from src.core.middleware.rate_limiter import rate_store
                deleted = await rate_store.cleanup(force=True)
                if deleted:
                    logger.info(f"Rate-limit counter sweep: purged {deleted} expired row(s)")
            except Exception as e:
                logger.warning(f"Rate-limit counter sweep loop: {e}")
            await _a.sleep(interval_s)
    except _a.CancelledError:
        logger.info("Rate-limit counter sweep loop cancelled (shutdown)")
        raise


async def _cancel_background_task(task) -> None:
    """Cancel a background loop and absorb its termination.

    ``asyncio.CancelledError`` inherits ``BaseException`` (not ``Exception``)
    on Python 3.8+, so a bare ``except Exception`` around ``await task``
    would let the cancellation propagate and abort the rest of shutdown.
    """
    import asyncio as _a
    if task is None or task.done():
        return
    task.cancel()
    try:
        await task
    except (_a.CancelledError, Exception):  # noqa: BLE001 — shutdown must continue
        pass
_reactivation_reminder_task = None
_auto_export_task = None
_erasure_purge_task = None
_auto_close_task = None
_deferred_maintenance_task = None


# Reminder copy is sent once when the remaining reactivation window is
# <= REMINDER_THRESHOLD_DAYS and > 0 (we never reminder-spam a workspace
# that's already past the deadline — the on-login sweep flips it to
# pending_hard_delete and platform-admin tooling takes it from there).
_REMINDER_THRESHOLD_DAYS = 3

# Auto-export sweep idempotency guard: skip workspaces whose
# auto_export_last_run_at is within this window of "now". This is a
# safety net beyond the (dow, hour) match — it guarantees that if the
# loop ticks twice within the same hour (e.g. because of a backend
# restart) we never double-mint a token + double-email the teacher.
_AUTO_EXPORT_MIN_INTERVAL = _td(hours=6)


# --- End-of-school-day lesson auto-close -------------------------------------
# A live lesson lives in ``class_sessions.status`` and only becomes
# ``completed`` via the manual "End Lesson" action or the lazy on-next-start
# cleanup. A teacher who opens a lesson and never ends it (and never starts
# another) leaves the row open forever. This sweep finalises any still-open
# lesson once its school day has ended, in the school's own timezone, for both
# regular and Independent-Teacher (IT) workspaces (they share one engine).
_AUTO_CLOSE_INTERVAL_SECONDS = 30 * 60
# Grace after the computed day-end before a lesson is force-closed, so a lesson
# legitimately running up to the final bell is never cut short.
_AUTO_CLOSE_GRACE_MINUTES = 15
# Fail-safe: a session this old is closed regardless of whether its tenant's
# day-end could be resolved (covers malformed date/tz rows so nothing is ever
# stuck open).
_AUTO_CLOSE_STALE_FALLBACK_HOURS = 18
_AUTO_CLOSE_SCAN_LIMIT = 5000
# Fixed namespace for the per-session advisory lock that serialises finalize
# across workers (pg_try_advisory_xact_lock(ns, hashtext(id))).
_AUTO_CLOSE_LOCK_NS = 0x4E41  # "NA"
_DEFAULT_SCHOOL_TZ = "Asia/Riyadh"


async def _sweep_auto_exports():
    """Hourly sweep — see Task #275.

    For every IT workspace where ``auto_export_enabled=TRUE`` AND the
    user-chosen day-of-week + hour matches ``now``, mint a fresh single
    use 24h export URL, stamp the school export columns (same as the
    manual ``POST /workspace/export`` path) and email the teacher a
    link-only notification. Status is recorded back on
    ``workspace_quota`` so the FE hub can render last-run + status.
    """
    from engines.sql_utils import gd_iter_rows as _gd_iter_rows, gd_find as _gd_find, gd_find_one as _gd_find_one, gd_update_one as _gd_update_one
    from engines.email_service import send_workspace_auto_export_email
    from services.email_client import send_email_off_loop
    from src.common.utils.tokens import mint_workspace_export_token, WORKSPACE_EXPORT_TOKEN_TTL
    from dependencies import audit_engine

    now = datetime.now(timezone.utc)
    today_dow = (now.weekday() + 1) % 7  # 0=Sunday convention
    current_hour = now.hour

    # Streamed: the sweep touches every enabled workspace, so it must not
    # scale its memory with the number of workspaces.
    swept = 0
    async for row in _gd_iter_rows(db.session, "workspace_quota", {"auto_export_enabled": True}):
        try:
            dow = row.get("auto_export_dow")
            hour = row.get("auto_export_hour")
            if dow is None or hour is None:
                continue
            if int(dow) != today_dow or int(hour) != current_hour:
                continue
            last_run_raw = row.get("auto_export_last_run_at")
            if last_run_raw:
                if isinstance(last_run_raw, datetime):
                    last_run = last_run_raw
                else:
                    try:
                        last_run = datetime.fromisoformat(str(last_run_raw).replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        last_run = None
                if last_run and last_run.tzinfo is None:
                    last_run = last_run.replace(tzinfo=timezone.utc)
                if last_run and (now - last_run) < _AUTO_EXPORT_MIN_INTERVAL:
                    continue

            workspace_id = row.get("workspace_school_id")
            school = await _gd_find_one(db.session, "schools", {"id": workspace_id})
            if not school:
                await _gd_update_one(
                    db.session, "workspace_quota",
                    {"workspace_school_id": workspace_id},
                    {"auto_export_last_run_at": now.isoformat(),
                     "auto_export_last_status": "failed_no_workspace"},
                )
                continue
            # Skip archived/pending-hard-delete — manual export is also
            # blocked there, and emailing them a backup link is noise.
            if (school.get("status") or "").lower() == "archived" or school.get("pending_hard_delete"):
                await _gd_update_one(
                    db.session, "workspace_quota",
                    {"workspace_school_id": workspace_id},
                    {"auto_export_last_run_at": now.isoformat(),
                     "auto_export_last_status": "skipped_archived"},
                )
                continue

            # Resolve the workspace owner (the IT user) so we know who
            # to email + who to bind the token to.
            owner_id = workspace_id.replace("itw_", "") if str(workspace_id).startswith("itw_") else None
            owner = None
            if owner_id:
                owner = await _gd_find_one(db.session, "users", {"id": owner_id})
            if not owner:
                # Fall back to any IT user pinned to this tenant.
                owners = await _gd_find(db.session, "users",
                                        {"tenant_id": workspace_id, "role": "independent_teacher"})
                owner = owners[0] if owners else None
            if not owner:
                await _gd_update_one(
                    db.session, "workspace_quota",
                    {"workspace_school_id": workspace_id},
                    {"auto_export_last_run_at": now.isoformat(),
                     "auto_export_last_status": "failed_no_owner"},
                )
                continue

            raw_token, raw_hash, expires_at = mint_workspace_export_token(
                workspace_id, owner["id"],
            )
            await _gd_update_one(
                db.session, "schools", {"id": workspace_id},
                {
                    "last_export_at": now.isoformat(),
                    "last_export_token_hash": raw_hash,
                    "last_export_consumed_at": None,
                    # Task #450 — auto-export has no bearer JTI (background
                    # sweep). Clearing this means the download endpoint will
                    # apply full is_active / last_password_change checks to
                    # whoever presents the URL, which is the desired posture
                    # for an out-of-band emailed export.
                    "last_export_initiator_jti": None,
                },
            )

            email = (owner.get("email") or "").strip()
            is_placeholder = email.endswith("@invite.nassaq.invalid") or not email
            sent = False
            if not is_placeholder:
                try:
                    sent = await send_email_off_loop(
                        send_workspace_auto_export_email,
                        to_email=email,
                        user_name=owner.get("full_name") or "",
                        workspace_name=school.get("name") or "",
                    )
                except Exception as email_exc:  # noqa: BLE001
                    logger.warning("Auto-export email send failed: %s", email_exc)
                    sent = False
            status = "success" if sent else ("email_skipped_placeholder" if is_placeholder else "email_failed")

            await _gd_update_one(
                db.session, "workspace_quota",
                {"workspace_school_id": workspace_id},
                {"auto_export_last_run_at": now.isoformat(),
                 "auto_export_last_status": status},
            )
            try:
                await audit_engine.log(
                    action="INDEPENDENT_TEACHER_AUTO_EXPORT",
                    performed_by=owner["id"],
                    tenant_id=workspace_id,
                    entity_type="school",
                    entity_id=workspace_id,
                    details={
                        "user_id": owner["id"],
                        "school_id": workspace_id,
                        "expires_at": expires_at.isoformat(),
                        "ttl_hours": int(WORKSPACE_EXPORT_TOKEN_TTL.total_seconds() // 3600),
                        "status": status,
                        "scheduled": True,
                    },
                    actor_name=owner.get("full_name"),
                    actor_role=owner.get("role"),
                    actor_email=owner.get("email"),
                )
            except Exception as audit_exc:  # noqa: BLE001
                logger.debug("auto-export audit failed: %s", audit_exc)
            swept += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("auto-export sweep row failed: %s", exc)
            continue
    if swept:
        logger.info("Workspace auto-export sweep: minted %d export(s)", swept)

_REACTIVATION_WINDOW_DAYS = 30


async def _sweep_reactivation_reminders():
    """Find every archived IT workspace whose reactivation deadline is
    within the threshold window AND has not yet received a reminder,
    then email the workspace owner. Best-effort per row.
    """
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    from engines.email_service import send_workspace_reactivation_reminder_email
    from services.email_client import send_email_off_loop

    now = _dt.now(_tz.utc)
    window = _td(days=_REACTIVATION_WINDOW_DAYS)
    threshold = _td(days=_REMINDER_THRESHOLD_DAYS)

    sent = 0
    async for school in gd_iter_rows(db.session, "schools", {"status": "archived"}):
        try:
            if school.get("pending_hard_delete"):
                continue
            if school.get("reactivation_reminder_sent_at"):
                continue
            archived_at = school.get("archived_at")
            if isinstance(archived_at, str):
                try:
                    archived_at = _dt.fromisoformat(archived_at.replace("Z", "+00:00"))
                except ValueError:
                    continue
            if archived_at is None:
                continue
            if archived_at.tzinfo is None:
                archived_at = archived_at.replace(tzinfo=_tz.utc)
            deadline = archived_at + window
            remaining = deadline - now
            if remaining <= _td(0) or remaining > threshold:
                continue

            workspace_id = school.get("id")
            owner_email = None
            owner_name = None
            if isinstance(workspace_id, str) and workspace_id.startswith("itw_"):
                user_id = workspace_id[len("itw_"):]
                owner = await gd_find_one(db.session, "users", {"id": user_id})
                if owner:
                    owner_email = (owner.get("email") or "").strip()
                    owner_name = owner.get("full_name")
            if not owner_email or "@" not in owner_email or "@invite.nassaq.invalid" in owner_email:
                # Stamp anyway so we don't re-scan this row every day for
                # a recipient we can't reach.
                await gd_update_one(
                    db.session, "schools", {"id": workspace_id},
                    {"reactivation_reminder_sent_at": now.isoformat()},
                )
                continue

            days_left = max(1, int(remaining.total_seconds() // 86400) or 1)

            # Task #249 — also surface the deadline reminder in the IT
            # inbox (in_app channel is non-suppressible) so a user with
            # email muted still sees the warning.
            try:
                from src.modules.notifications.controllers.notification_routes_mod import create_notification_internal
                from src.modules.independent_teacher.controllers.independent_teacher_notifications_routes import should_send_channel
                if owner and await should_send_channel(owner, "workspace_lifecycle", "in_app"):
                    await create_notification_internal(
                        title="تذكير: اقتراب موعد إعادة تفعيل مساحة العمل",
                        message=f"تبقّى {days_left} يومًا لإعادة تفعيل مساحة عملك.",
                        title_en="Reminder: workspace reactivation deadline approaching",
                        message_en=f"{days_left} day(s) left to reactivate your workspace.",
                        recipient_id=owner["id"],
                        notification_type="workspace_reactivation_reminder",
                        priority="high",
                        related_entity="school",
                        related_entity_id=workspace_id,
                        school_id=workspace_id,
                        category="workspace_lifecycle",
                        cta_url="/account-settings",
                        extra_data={
                            "days_left": days_left,
                            "reactivation_deadline": deadline.isoformat(),
                        },
                    )
            except Exception as exc:
                logger.debug(f"reactivation reminder inbox notify failed: {exc}")

            from src.modules.independent_teacher.controllers.independent_teacher_notifications_routes import should_send_channel
            email_allowed = await should_send_channel(
                owner, "workspace_lifecycle", "email",
            ) if owner else True
            if not email_allowed:
                # Stamp the row so we don't re-evaluate every sweep.
                await gd_update_one(
                    db.session, "schools", {"id": workspace_id},
                    {"reactivation_reminder_sent_at": now.isoformat()},
                )
                continue
            ok = await send_email_off_loop(
                send_workspace_reactivation_reminder_email,
                to_email=owner_email,
                user_name=owner_name or owner_email,
                workspace_name=(school.get("name") or "").strip() or workspace_id,
                reactivation_deadline=deadline.isoformat(),
                days_left=days_left,
            )
            if not ok:
                # Provider outage / Resend unconfigured. Leave the stamp
                # NULL so the next daily sweep retries — better to risk a
                # second email than to silently swallow the only warning
                # the user gets before hard-deletion.
                logger.warning(
                    "Reactivation reminder send failed for school=%s; will retry next sweep",
                    workspace_id,
                )
                continue
            await gd_update_one(
                db.session, "schools", {"id": workspace_id},
                {"reactivation_reminder_sent_at": now.isoformat()},
            )
            sent += 1
        except Exception as exc:
            logger.warning(f"Reactivation reminder skip for school={school.get('id')}: {exc}")
    if sent:
        logger.info(f"Workspace reactivation reminders sent: {sent}")
    return sent


async def _sweep_erasure_purges():
    """Find every IT workspace whose ``erasure_requested_at`` is older
    than its configured ``erasure_window_days`` and physically purge
    it via the shared ``purge_workspace_cascade`` helper.

    Called once daily from the background loop. Each workspace is
    processed in its own savepoint so a single failure does not block
    the rest of the batch. Audit row ``INDEPENDENT_TEACHER_ERASURE_COMPLETED``
    is written before the parent ``schools`` row is deleted (the audit
    table is in a separate schema and is not in ``_PURGE_TABLES``).
    """
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    from src.modules.platform.controllers.platform_workspace_purge_routes import purge_workspace_cascade
    from src.modules.independent_teacher.controllers.independent_teacher_workspace_lifecycle_routes import (
        AUDIT_ERASURE_COMPLETED,
    )
    from dependencies import audit_engine

    now = _dt.now(_tz.utc)

    purged = 0
    async for school in gd_iter_rows(db.session, "schools", {"status": "archived"}):
        try:
            requested_at = school.get("erasure_requested_at")
            if not requested_at:
                continue
            if isinstance(requested_at, str):
                try:
                    requested_at = _dt.fromisoformat(
                        requested_at.replace("Z", "+00:00"),
                    )
                except ValueError:
                    continue
            if requested_at.tzinfo is None:
                requested_at = requested_at.replace(tzinfo=_tz.utc)
            window_days = school.get("erasure_window_days") or 7
            try:
                window_days = int(window_days)
            except (TypeError, ValueError):
                window_days = 7
            deadline = requested_at + _td(days=window_days)
            if now < deadline:
                continue

            workspace_id = school.get("id")
            snapshot = {
                "name": school.get("name"),
                "status": school.get("status"),
                "erasure_requested_at": requested_at.isoformat(),
                "erasure_window_days": window_days,
                "purged_at": now.isoformat(),
            }
            try:
                async with db.session.begin_nested():
                    deleted_counts, skipped, _ = await purge_workspace_cascade(
                        workspace_id,
                    )
                    # The schools row is now gone — audit_logs.school_id
                    # is FK-constrained to schools(id), so we must NOT
                    # propagate the workspace_id onto that column. The
                    # workspace id is preserved in `details` for
                    # forensics + cross-referencing the
                    # INDEPENDENT_TEACHER_ERASURE_REQUESTED row.
                    await audit_engine.log(
                        action=AUDIT_ERASURE_COMPLETED,
                        performed_by=None,
                        actor_name="system:erasure-sweep",
                        actor_role="system",
                        tenant_id=None,
                        entity_type="school",
                        entity_id=workspace_id,
                        details={
                            "school_id": workspace_id,
                            "tenant_id": workspace_id,
                            "actor": "system:erasure-sweep",
                            "deleted_counts": deleted_counts,
                            "skipped_tables": skipped,
                            "snapshot": snapshot,
                        },
                    )
                purged += 1
                logger.info(
                    "erasure-sweep: purged workspace=%s deleted=%s skipped=%s",
                    workspace_id, deleted_counts, skipped,
                )
            except Exception as exc:
                logger.warning(
                    "erasure-sweep: purge failed for workspace=%s: %s",
                    workspace_id, exc,
                )
        except Exception as exc:
            logger.warning(
                "erasure-sweep: candidate skip for school=%s: %s",
                school.get("id"), exc,
            )
    if purged:
        logger.info(f"Workspace erasure purges completed: {purged}")
    return purged


def _ac_parse_hhmm(value) -> "int | None":
    """Parse ``"HH:MM"`` into minutes-since-midnight; ``None`` when unparseable."""
    if not value or not isinstance(value, str) or ":" not in value:
        return None
    try:
        parts = value.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return None


def _compute_day_end_minutes(settings, time_slots) -> "int | None":
    """Resolve the end-of-school-day, as minutes-since-midnight, for one tenant.

    Mirrors the resolution used by ``GET /school/day-status`` so the sweep and
    the live banner agree: real period ``time_slots`` win (most accurate —
    they include passing/prayer breaks); otherwise fall back to the timing
    settings formula ``start + periods*period_duration + break``. Works for IT
    workspaces too (they have no ``time_slots`` → formula path).
    """
    settings = settings or {}
    nested = settings.get("settings") or {}
    cs = settings.get("custom_settings") or {}

    def _first(*candidates, default=None):
        for c in candidates:
            if c is not None and c != "":
                return c
        return default

    day_start = _first(
        cs.get("school_day_start"),
        nested.get("school_day_start"),
        settings.get("school_day_start"),
        settings.get("start_time"),
        default="07:00",
    )
    periods = int(_first(
        cs.get("periods_per_day"),
        nested.get("periods_per_day"),
        settings.get("periods_per_day"),
        default=7,
    ) or 7)
    period_duration = int(_first(
        cs.get("period_duration_minutes"),
        nested.get("period_duration_minutes"),
        settings.get("period_duration_minutes"),
        settings.get("period_duration"),
        default=45,
    ) or 45)
    break_duration = int(_first(
        cs.get("break_duration_minutes"),
        nested.get("break_duration_minutes"),
        settings.get("break_duration_minutes"),
        settings.get("break_duration"),
        default=20,
    ) or 20)

    period_slots = [
        s for s in (time_slots or [])
        if not s.get("is_break", False)
        and _ac_parse_hhmm(s.get("start_time")) is not None
        and _ac_parse_hhmm(s.get("end_time")) is not None
    ]
    start_min = _ac_parse_hhmm(day_start) or 420
    formula_end = start_min + (periods * period_duration) + break_duration
    if period_slots:
        # ``time_slots`` arrive ordered by start_time → last slot is the
        # latest period; trust its end_time, fall back to the formula.
        return _ac_parse_hhmm(period_slots[-1].get("end_time")) or formula_end
    return formula_end


def _session_should_close(date_str, day_end_minutes, school_tz, now_local, grace_minutes) -> bool:
    """True when ``now_local`` is past the day-end (+grace) for the session's
    own calendar ``date``. Previous-day sessions are always past their day-end,
    so they close immediately; an unparseable date returns False (the stale
    fallback handles those)."""
    if not date_str:
        return False
    try:
        d = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return False
    day_end_dt = datetime(d.year, d.month, d.day, tzinfo=school_tz) + _td(
        minutes=int(day_end_minutes) + int(grace_minutes)
    )
    return now_local >= day_end_dt


def _ac_is_stale(session) -> bool:
    """Fail-safe close trigger: the session started (or was created) more than
    ``_AUTO_CLOSE_STALE_FALLBACK_HOURS`` ago. Used when the tenant's day-end
    cannot be resolved so a lesson is never left open indefinitely."""
    raw = session.get("start_time") or session.get("created_at")
    if not raw:
        return False
    try:
        if isinstance(raw, datetime):
            dt = raw
        else:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt) >= _td(hours=_AUTO_CLOSE_STALE_FALLBACK_HOURS)


async def _resolve_school_day_end(school_id):
    """Return ``(school_tz, day_end_minutes)`` for a tenant, or ``None`` when it
    cannot be resolved. Reads ``school_settings`` + ``time_slots`` on the active
    ``db.session``."""
    from zoneinfo import ZoneInfo
    settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    nested = (settings or {}).get("settings") or {}
    tz_name = nested.get("timezone") or (settings or {}).get("timezone") or _DEFAULT_SCHOOL_TZ
    try:
        school_tz = ZoneInfo(tz_name)
    except Exception:
        school_tz = ZoneInfo(_DEFAULT_SCHOOL_TZ)
    time_slots = await gd_find(
        db.session, "time_slots", {"school_id": school_id},
        order_by="start_time", desc_order=False, limit=30,
    )
    end_min = _compute_day_end_minutes(settings, time_slots)
    if end_min is None:
        return None
    return (school_tz, end_min)


async def _scan_auto_close_candidates():
    """Read every still-open lesson and return the slim {id, teacher_id} of
    those whose school day has ended (or that are stale). Runs read-only on the
    active ``db.session``; day-end is cached per tenant for the scan."""
    from engines.session_engine import TeacherSessionEngine
    active = await gd_find(
        db.session, "class_sessions",
        {"status": {"$in": list(TeacherSessionEngine.ACTIVE_STATUSES)}},
        limit=_AUTO_CLOSE_SCAN_LIMIT,
    )
    if not active:
        return []
    day_end_cache = {}
    out = []
    for s in active:
        school_id = s.get("school_id") or s.get("tenant_id")
        resolved = None
        if school_id:
            if school_id not in day_end_cache:
                try:
                    day_end_cache[school_id] = await _resolve_school_day_end(school_id)
                except Exception as e:
                    logger.debug(f"Auto-close: day-end resolve failed for {school_id}: {e}")
                    day_end_cache[school_id] = None
            resolved = day_end_cache[school_id]
        should = False
        if resolved is not None:
            school_tz, end_min = resolved
            should = _session_should_close(
                s.get("date"), end_min, school_tz,
                datetime.now(school_tz), _AUTO_CLOSE_GRACE_MINUTES,
            )
        if not should:
            should = _ac_is_stale(s)
        if should:
            out.append({"id": s.get("id"), "teacher_id": s.get("teacher_id")})
    return out


async def _finalize_auto_close(candidate):
    """Close one abandoned lesson on the active ``db.session``.

    Per product decision: behave exactly as if the teacher tapped "End Lesson"
    — ``end_session`` commits scores to student profiles and fires the normal
    parent/management notifications.

    Multi-instance safety: this sweep may run on every backend worker at once.
    Before doing any finalize work we take a transaction-scoped Postgres
    advisory lock keyed on the session id (``pg_try_advisory_xact_lock`` —
    non-blocking, auto-released on commit/rollback). If another worker already
    holds it we skip and let that worker finish, so the full-finalize side
    effects (parent/management notifications) fire exactly once.

    After winning the lock we re-read the row: if it is gone or already
    ``completed`` (closed since the scan) we skip. Whether a *full* finalize is
    possible is decided deterministically from attendance state — never by
    catching an opaque HTTP 400 — so a future unrelated 400 in ``end_session``
    can never silently mark a lesson done without committing scores. When
    attendance was never recorded a full finalize is impossible, so we fall back
    to a safe close (the lesson is never left open). ``auto_closed`` metadata is
    stamped either way for auditability. Returns True when the row was closed."""
    from sqlalchemy import text
    from dependencies import session_engine
    from engines.session_engine import SessionStatus, TeacherSessionEngine

    sid = candidate.get("id")
    tid = candidate.get("teacher_id")
    if not sid:
        return False

    # Cross-worker claim. ns is a fixed namespace; the per-session key is
    # hashtext(id). A hash collision only delays an unrelated close by one tick.
    got_lock = (
        await db.session.execute(
            text("SELECT pg_try_advisory_xact_lock(:ns, hashtext(:sid))"),
            {"ns": _AUTO_CLOSE_LOCK_NS, "sid": str(sid)},
        )
    ).scalar()
    if not got_lock:
        return False  # another worker owns this session this tick

    # Re-read fresh under the lock — it may have closed since the scan.
    session = await gd_find_one(db.session, "class_sessions", {"id": sid})
    if not session:
        return False
    if session.get("status") == SessionStatus.COMPLETED.value:
        return False
    if session.get("status") not in TeacherSessionEngine.ACTIVE_STATUSES:
        return False

    now = datetime.now(timezone.utc)

    # Decide finalize-ability deterministically (mirrors end_session's own
    # attendance prerequisite) instead of relying on a caught 400.
    attendance_approved = session.get("attendance_approved", False)
    attendance_records = await gd_find(
        db.session, "session_attendance", {"session_id": sid}, limit=1,
    )
    can_finalize = bool(attendance_approved) or len(attendance_records) > 0

    if can_finalize:
        # Full finalize: scores committed to profiles + normal notifications.
        await session_engine.end_session(session_id=sid, teacher_id=tid)
        update = {
            "auto_closed": True,
            "auto_closed_at": now.isoformat(),
            "auto_closed_reason": "end_of_school_day",
        }
    else:
        # Attendance never recorded — full finalize is impossible. Safe-close so
        # the lesson is not left open forever; no scores/notifications to emit.
        update = {
            "auto_closed": True,
            "auto_closed_at": now.isoformat(),
            "auto_closed_reason": "end_of_school_day_no_attendance",
            "status": SessionStatus.COMPLETED.value,
            "end_time": now.isoformat(),
        }
    await gd_update_one(db.session, "class_sessions", {"id": sid}, update)
    return True


async def _sweep_auto_close_sessions():
    """End-of-school-day sweep. Scans candidates in one short read transaction,
    then closes each in its OWN transaction so a single failure can never
    poison or roll back the others. Idempotent: a closed lesson leaves
    ACTIVE_STATUSES and is skipped on the next tick."""
    candidates = await _run_with_session("Auto-close scan", _scan_auto_close_candidates)
    if not candidates:
        return
    closed = 0
    for c in candidates:
        res = await _run_with_session(
            f"Auto-close lesson {c.get('id')}",
            lambda c=c: _finalize_auto_close(c),
        )
        if res:
            closed += 1
    if closed:
        logger.info(f"End-of-day auto-close: finalised {closed} abandoned lesson(s)")


async def shutdown_tasks():
    # Cancel the revoked-token cleanup loop cleanly.
    try:
        global _revoked_token_cleanup_task
        if _revoked_token_cleanup_task is not None and not _revoked_token_cleanup_task.done():
            _revoked_token_cleanup_task.cancel()
            try:
                await _revoked_token_cleanup_task
            except Exception:
                pass
            _revoked_token_cleanup_task = None
    except Exception as e:
        logger.debug(f"Cleanup loop cancellation: {e}")

    # Cancel the rate-limit counter sweep loop cleanly. CancelledError is
    # caught explicitly inside _cancel_background_task — it is a
    # BaseException, so a bare `except Exception` would let it abort the
    # rest of shutdown.
    try:
        global _rate_limit_sweep_task
        await _cancel_background_task(_rate_limit_sweep_task)
        _rate_limit_sweep_task = None
    except Exception as e:
        logger.debug(f"Rate-limit sweep loop cancellation: {e}")

    # Cancel the reactivation-reminder loop cleanly.
    try:
        global _reactivation_reminder_task
        if _reactivation_reminder_task is not None and not _reactivation_reminder_task.done():
            _reactivation_reminder_task.cancel()
            try:
                await _reactivation_reminder_task
            except Exception:
                pass
            _reactivation_reminder_task = None
    except Exception as e:
        logger.debug(f"Reminder loop cancellation: {e}")

    # Cancel the erasure purge loop cleanly.
    try:
        global _erasure_purge_task
        if _erasure_purge_task is not None and not _erasure_purge_task.done():
            _erasure_purge_task.cancel()
            try:
                await _erasure_purge_task
            except Exception:
                pass
            _erasure_purge_task = None
    except Exception as e:
        logger.debug(f"Erasure purge loop cancellation: {e}")

    # Cancel the end-of-day auto-close loop cleanly.
    try:
        global _auto_close_task
        if _auto_close_task is not None and not _auto_close_task.done():
            _auto_close_task.cancel()
            try:
                await _auto_close_task
            except Exception:
                pass
            _auto_close_task = None
    except Exception as e:
        logger.debug(f"Auto-close loop cancellation: {e}")

    # Cancel the scheduled communication dispatch loop cleanly.
    try:
        global _scheduled_dispatch_task
        if _scheduled_dispatch_task is not None and not _scheduled_dispatch_task.done():
            _scheduled_dispatch_task.cancel()
            try:
                await _scheduled_dispatch_task
            except Exception:
                pass
            _scheduled_dispatch_task = None
    except Exception as e:
        logger.debug(f"Scheduled dispatch loop cancellation: {e}")

    # Cancel the deferred startup-maintenance task if it's still running.
    try:
        global _deferred_maintenance_task
        if _deferred_maintenance_task is not None and not _deferred_maintenance_task.done():
            _deferred_maintenance_task.cancel()
            try:
                await _deferred_maintenance_task
            except Exception:
                pass
            _deferred_maintenance_task = None
    except Exception as e:
        logger.debug(f"Deferred maintenance cancellation: {e}")

    try:
        from src.modules.notifications.controllers.websocket_routes import get_connection_manager
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
    # SECURITY (audit M-4 / Phase 2 review): drain any in-flight audit
    # events so the last few hundred ms of activity before SIGTERM aren't
    # lost. Best-effort with a short timeout.
    try:
        from services.audit_sink import audit_sink as _sink
        pending = await _sink.drain(timeout=3.0)
        if pending:
            logger.warning(f"audit_sink: {pending} events still pending at shutdown")
    except Exception as e:
        logger.debug(f"audit_sink drain on shutdown: {e}")

    # Stop the render pool. Threads running ReportLab cannot be interrupted,
    # so don't wait on them — the process is going away regardless.
    try:
        from services.cpu_offload import shutdown as _cpu_offload_shutdown
        _cpu_offload_shutdown(wait=False)
    except Exception as e:
        logger.debug(f"cpu_offload shutdown: {e}")

    await close_pg_engine()
    logger.info("NASSAQ shutdown complete")
