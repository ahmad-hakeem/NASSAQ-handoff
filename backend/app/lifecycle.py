"""
NASSAQ — Application startup and shutdown hooks.
"""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta as _td

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
                        from pg_models import RevokedToken
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


_revoked_token_cleanup_task = None
_reactivation_reminder_task = None
_auto_export_task = None
_erasure_purge_task = None


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


async def _sweep_auto_exports():
    """Hourly sweep — see Task #275.

    For every IT workspace where ``auto_export_enabled=TRUE`` AND the
    user-chosen day-of-week + hour matches ``now``, mint a fresh single
    use 24h export URL, stamp the school export columns (same as the
    manual ``POST /workspace/export`` path) and email the teacher a
    link-only notification. Status is recorded back on
    ``workspace_quota`` so the FE hub can render last-run + status.
    """
    from engines.sql_utils import gd_find as _gd_find, gd_find_one as _gd_find_one, gd_update_one as _gd_update_one
    from engines.email_service import send_workspace_auto_export_email
    from utils.tokens import mint_workspace_export_token, WORKSPACE_EXPORT_TOKEN_TTL
    from dependencies import audit_engine

    now = datetime.now(timezone.utc)
    today_dow = (now.weekday() + 1) % 7  # 0=Sunday convention
    current_hour = now.hour

    rows = await _gd_find(db.session, "workspace_quota", {"auto_export_enabled": True})
    if not rows:
        return
    swept = 0
    for row in rows:
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
                    sent = send_workspace_auto_export_email(
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

    now = _dt.now(_tz.utc)
    window = _td(days=_REACTIVATION_WINDOW_DAYS)
    threshold = _td(days=_REMINDER_THRESHOLD_DAYS)

    candidates = await gd_find(db.session, "schools", {"status": "archived"})
    sent = 0
    for school in candidates or []:
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
                from routes.notification_routes_mod import create_notification_internal
                from routes.independent_teacher_notifications_routes import should_send_channel
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

            from routes.independent_teacher_notifications_routes import should_send_channel
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
            ok = send_workspace_reactivation_reminder_email(
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
    from routes.platform_workspace_purge_routes import purge_workspace_cascade
    from routes.independent_teacher_workspace_lifecycle_routes import (
        AUDIT_ERASURE_COMPLETED,
    )
    from dependencies import audit_engine

    now = _dt.now(_tz.utc)

    candidates = await gd_find(db.session, "schools", {"status": "archived"})
    purged = 0
    for school in candidates or []:
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

    await close_pg_engine()
    logger.info("NASSAQ shutdown complete")
