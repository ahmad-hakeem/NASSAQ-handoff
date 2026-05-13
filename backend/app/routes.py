"""
NASSAQ — Centralized route registration.
"""
import jwt
import logging

from fastapi import APIRouter, WebSocket

from dependencies import (
    db, get_current_user, require_roles, UserRole,
    hash_password, create_access_token,
    generate_secure_password,
    JWT_SECRET, JWT_ALGORITHM,
    smart_scheduling_engine,
)

logger = logging.getLogger("nassaq")


def register_routes(app, api_router: APIRouter):
    from routes.monitoring_routes import router as monitoring_router
    app.include_router(monitoring_router)
    api_router.include_router(monitoring_router)

    from routes.auth_routes_mod import router as auth_mod_router
    from routes.mfa_routes import router as mfa_router
    from routes.user_routes_mod import router as user_mod_router
    from routes.school_routes_mod import router as school_mod_router
    from routes.dashboard_routes_mod import router as dashboard_mod_router
    from routes.ai_routes_mod import router as ai_mod_router
    from routes.registration_routes_mod import router as registration_mod_router
    from routes.academics_reference_routes import router as academics_ref_router
    from routes.academics_student_routes import router as academics_student_router
    from routes.academics_class_routes import router as academics_class_router
    from routes.academics_subject_routes import router as academics_subject_router
    from routes.academics_year_term_routes import router as academics_year_term_router
    from routes.academics_structure_engine_routes import router as academics_structure_router
    from routes.academics_teacher_routes import router as academics_teacher_router
    from routes.scheduling_smart_engine_routes import router as scheduling_smart_router
    from routes.scheduling_smart_session_routes import router as scheduling_smart_sess_router
    from routes.schedule_candidates_routes import router as schedule_candidates_router
    from routes.schedule_master_grid_routes import router as schedule_master_grid_router
    from routes.standby_routes import router as standby_router
    from routes.attendance_routes_mod import router as attendance_mod_router
    from routes.assessment_routes_mod import router as assessment_mod_router
    from routes.behaviour_routes_mod import router as behaviour_mod_router
    from routes.notification_routes_mod import router as notification_mod_router
    from routes.platform_routes_mod import router as platform_mod_router
    from routes.reporting_routes_mod import router as reporting_mod_router
    from routes.role_dashboards_mod import router as role_dashboards_mod_router
    from routes.admin_routes_mod import router as admin_mod_router
    from routes.school_settings_mod import router as school_settings_mod_router
    from routes.participation_routes_mod import router as participation_mod_router
    from routes.search_directory_routes_mod import router as search_directory_mod_router
    from routes.event_workflow_routes_mod import router as event_workflow_mod_router
    from routes.relationship_routes_mod import router as relationship_mod_router
    from routes.consent_privacy_routes_mod import router as consent_privacy_mod_router
    from routes.activities_routes_mod import router as activities_mod_router
    from routes.product_hub_routes import router as product_hub_router
    from routes.portfolio_routes_mod import router as portfolio_mod_router
    from routes.calendar_routes_mod import router as calendar_mod_router
    from routes.hakeem_plan_routes_mod import router as hakeem_plan_mod_router

    api_router.include_router(auth_mod_router)
    api_router.include_router(mfa_router)
    api_router.include_router(user_mod_router)
    api_router.include_router(school_mod_router)
    api_router.include_router(dashboard_mod_router)
    api_router.include_router(ai_mod_router)
    api_router.include_router(registration_mod_router)
    api_router.include_router(academics_ref_router)
    api_router.include_router(academics_student_router)
    api_router.include_router(academics_class_router)
    api_router.include_router(academics_subject_router)
    api_router.include_router(academics_year_term_router)
    api_router.include_router(academics_structure_router)
    api_router.include_router(academics_teacher_router)

    from routes.academic_structure_routes import router as academic_structure_router
    api_router.include_router(academic_structure_router)
    # Phase 0 §4.B-2 — capability gate for routers reserved to full
    # school tenants. Independent-Teacher accounts get a friendly Arabic
    # 403 instead of a misleading "Permission denied" or 500.
    from auth_scope import require_full_school_tenant, require_workspace_materialised
    from fastapi import Depends as _Depends
    _full_tenant_dep = [_Depends(require_full_school_tenant)]

    # Phase 1 (#183) — Independent-Teacher workspace bootstrap router.
    # Registered BEFORE the global ``require_workspace_materialised``
    # dependency is attached at the api_router level, but the bootstrap
    # path is itself in the allow-list so this ordering is informational
    # rather than load-bearing.
    from routes.independent_teacher_bootstrap_routes import router as it_bootstrap_router
    api_router.include_router(it_bootstrap_router)
    # Phase 2 §5.2 (#189) — IT-only workspace settings (reduced surface).
    # Mounted WITHOUT _full_tenant_dep so IT callers can reach it; the
    # router itself enforces an IT role gate per-endpoint and a deny-by-
    # default allow-list on writes. Principal `/school/settings` paths
    # stay gated by `_full_tenant_dep` and continue to deny IT (Phase 0).
    from routes.independent_teacher_workspace_settings_routes import (
        router as it_workspace_settings_router,
    )
    api_router.include_router(it_workspace_settings_router)
    # Phase 1 §5.4 (#193) — IT-only manual schedule editor (upsert-by-
    # natural-key with optimistic concurrency on schedule_sessions.version).
    # Mounted WITHOUT _full_tenant_dep; the router itself enforces the IT
    # role gate per-endpoint and pins school_id to the caller's workspace.
    from routes.independent_teacher_schedule_routes import (
        router as it_schedule_router,
    )
    api_router.include_router(it_schedule_router)
    # Phase 1 §5.6 (Task #198) — IT-only communication recipients router.
    # Mounted WITHOUT _full_tenant_dep; the router itself enforces an IT
    # role gate per-endpoint and pins every join by school_id ==
    # itw_{user_id}. Send paths still go through notification_routes_mod
    # (with IT-specific hardening added in the same ticket).
    from routes.independent_teacher_communication_routes import (
        router as it_communication_router,
    )
    api_router.include_router(it_communication_router)
    # Phase 1 §5.6 (#199) — IT-only Invite-Parent (atomic Pending →
    # Linked) + pending-parent editor. Mounted WITHOUT
    # _full_tenant_dep; the router enforces the IT role gate per-
    # endpoint, requires fresh MFA via require_recent_mfa, and is
    # the SOLE backend writer that flips students.parent_id NULL →
    # non-NULL for an IT user.
    from routes.independent_teacher_invite_parent_routes import (
        router as it_invite_parent_router,
    )
    api_router.include_router(it_invite_parent_router)
    # Phase 2 §6.2b (#205) — IT parent-invitation envelope (create /
    # cancel / public accept). Router has no global gate; the IT-only
    # endpoints enforce the role + Tier-A MFA via per-route deps and
    # the public accept endpoint is unauthenticated + IP rate-limited.
    from routes.independent_teacher_invitation_routes import (
        router as it_invitation_router,
    )
    api_router.include_router(it_invitation_router)
    # Phase 2 §6.3 (#208) — IT-only personal calendar events. Mounted
    # WITHOUT _full_tenant_dep; the router enforces an IT role gate per-
    # endpoint and pins tenant_id == itw_{user_id} + created_by ==
    # current_user.id + is_personal=True on every read/write. The legacy
    # /v1/calendar surface in calendar_routes_mod stays untouched.
    from routes.independent_teacher_calendar_routes import (
        router as it_calendar_router,
    )
    api_router.include_router(it_calendar_router)
    # Phase 2 §6.1 (#207) — IT workspace-aware bulk student import.
    # Mounted WITHOUT _full_tenant_dep; the router enforces the IT
    # role gate per-endpoint, pins all writes to itw_{user_id}, and
    # gates /commit behind require_recent_mfa_403 (Tier-A step-up).
    from routes.independent_teacher_bulk_import_routes import (
        router as it_bulk_import_router,
    )
    api_router.include_router(it_bulk_import_router)
    # Phase 2 §6.7 (#210) — IT cross-workspace co-teaching envelope.
    # The ONLY sanctioned cross-tenant data path for IT workspaces;
    # single-tenant invariant (§8) is intentionally relaxed for the
    # named class. Mounted WITHOUT _full_tenant_dep; the router enforces
    # the IT role gate per-endpoint, requires fresh MFA on every write
    # surface, and gates host-side writes on `workspace.collab_manage`.
    from routes.independent_teacher_collab_routes import (
        router as it_collab_router,
    )
    api_router.include_router(it_collab_router)
    # Phase 2 §6.8 (#211) — IT workspace lifecycle (export +
    # soft-delete + reactivate + public download). No global gate;
    # IT-only endpoints enforce the role + Tier-A MFA per route, and
    # the public download endpoint is unauthenticated + IP rate-
    # limited. Hard-delete remains platform-admin out-of-band.
    from routes.independent_teacher_workspace_lifecycle_routes import (
        router as it_workspace_lifecycle_router,
    )
    api_router.include_router(it_workspace_lifecycle_router)
    # Phase 2 §6.4 (#209) — IT-only light AI lesson-planning assistant.
    # Mounted WITHOUT _full_tenant_dep; the router enforces the IT role
    # gate per-endpoint, pins workspace_school_id == itw_{user_id} +
    # created_by == current_user.id on every read/write, and bumps the
    # workspace_quota.lesson_plans_today daily counter on each generate.
    # NO MFA step-up (low-sensitivity content generation per spec).
    from routes.independent_teacher_lesson_plans_routes import (
        router as it_lesson_plans_router,
    )
    api_router.include_router(it_lesson_plans_router)
    # Task #250 — IT first-login onboarding tour state. Three IT-only
    # endpoints (state / complete / reset) gating the welcome card +
    # replay link. Mounted WITHOUT _full_tenant_dep; the router enforces
    # the IT role gate per-endpoint and only writes
    # ``users.it_onboarding_completed_at`` on the caller's own row.
    from routes.independent_teacher_onboarding_routes import (
        router as it_onboarding_router,
    )
    api_router.include_router(it_onboarding_router)
    # Task #248 — IT-only workspace audit-log view. Mounted WITHOUT
    # _full_tenant_dep; the router enforces the IT role gate per-
    # endpoint and pins school_id == itw_{user_id} on every read.
    # Cross-workspace ids return 404 per spec §8 inv. 3. Read-only;
    # no MFA step-up.
    from routes.independent_teacher_audit_routes import (
        router as it_audit_router,
    )
    api_router.include_router(it_audit_router)
    # Task #273 — IT-only workspace analytics dashboard. Mounted WITHOUT
    # _full_tenant_dep; the router enforces the IT role gate per-endpoint
    # and pins tenant_id == itw_{user_id} on every aggregation. Cross-
    # workspace class_id returns 404 per spec §8 inv. 3. Read-only;
    # no MFA step-up.
    from routes.independent_teacher_analytics_routes import (
        router as it_analytics_router,
    )
    api_router.include_router(it_analytics_router)
    # Task #249 — IT Notifications Inbox + per-category preferences.
    # Mounted WITHOUT _full_tenant_dep; the router enforces the IT role
    # gate per-endpoint and pins user_id + tenant_id == itw_{user_id}
    # on every read/write. Cross-workspace by-id reads return 404
    # per spec §8 inv. 3.
    from routes.independent_teacher_notifications_routes import (
        router as it_notifications_router,
    )
    api_router.include_router(it_notifications_router)
    # Task #217 — Platform-admin hard-delete tooling for workspaces
    # whose 30-day reactivation window has lapsed
    # (`schools.pending_hard_delete = TRUE`). Lives behind
    # `require_roles([PLATFORM_ADMIN])`; never reachable from the IT
    # surface itself, preserving the §6.8 trust boundary.
    from routes.platform_workspace_purge_routes import (
        router as platform_workspace_purge_router,
    )
    api_router.include_router(platform_workspace_purge_router)
    # Task #251 — IT workspace-wide command-palette search. IT-only,
    # workspace-pinned (school_id / tenant_id / workspace_school_id ==
    # itw_{user_id}); cross-workspace rows are never returned.
    from routes.independent_teacher_search_routes import (
        router as it_search_router,
    )
    api_router.include_router(it_search_router)
    api_router.include_router(scheduling_smart_router, dependencies=_full_tenant_dep)
    api_router.include_router(scheduling_smart_sess_router, dependencies=_full_tenant_dep)
    api_router.include_router(schedule_candidates_router, dependencies=_full_tenant_dep)
    api_router.include_router(schedule_master_grid_router, dependencies=_full_tenant_dep)
    api_router.include_router(standby_router, dependencies=_full_tenant_dep)
    api_router.include_router(attendance_mod_router)
    api_router.include_router(assessment_mod_router)
    api_router.include_router(behaviour_mod_router)
    api_router.include_router(notification_mod_router)
    api_router.include_router(participation_mod_router)
    api_router.include_router(platform_mod_router)
    api_router.include_router(reporting_mod_router)
    api_router.include_router(role_dashboards_mod_router)
    api_router.include_router(admin_mod_router)
    api_router.include_router(school_settings_mod_router, dependencies=_full_tenant_dep)
    api_router.include_router(search_directory_mod_router)
    api_router.include_router(event_workflow_mod_router)
    api_router.include_router(relationship_mod_router)
    api_router.include_router(consent_privacy_mod_router)
    api_router.include_router(activities_mod_router)
    api_router.include_router(product_hub_router)
    api_router.include_router(portfolio_mod_router)
    api_router.include_router(calendar_mod_router)
    api_router.include_router(hakeem_plan_mod_router, dependencies=_full_tenant_dep)

    from routes.principal_management_routes import router as principal_mgmt_router
    api_router.include_router(principal_mgmt_router, dependencies=_full_tenant_dep)

    from routes.timetable_readiness_routes import router as timetable_readiness_router, set_database as set_readiness_db
    set_readiness_db(db)
    api_router.include_router(timetable_readiness_router)

    # --- Factory-pattern routes (legacy) ---
    # These use a factory function and serve additional unique endpoints
    # that don't exist in the _mod sub-modules above.
    # Overlap analysis:
    #   attendance_routes: serves unique endpoints (mark-all-present, daily reports, teacher-attendance)
    #                      plus a few paths also in attendance_routes_mod (bulk, excuses) — _mod wins (registered first)
    #   assessment_routes: serves unique endpoints (statistics, report-cards/generate, publish)
    #                      plus a few paths also in assessment_routes_mod — _mod wins (registered first)
    #   student/teacher/class_management: serve /options, /validate, /drafts (unique to factory)
    # TODO: Migrate unique factory endpoints into _mod sub-modules, then remove factory registrations.
    from routes.attendance_routes import create_attendance_router
    from routes.assessment_routes import create_assessment_router
    from routes.teacher_registration_routes import create_teacher_registration_router
    from routes.student_management_routes import create_student_routes
    from routes.teacher_management_routes import create_teacher_management_routes
    from routes.class_management_routes import create_class_management_routes
    from routes.notification_routes import create_notification_routes

    attendance_router = create_attendance_router(db, get_current_user, require_roles, UserRole)
    assessment_router = create_assessment_router(db, get_current_user, require_roles, UserRole)
    teacher_registration_router = create_teacher_registration_router(db, get_current_user, require_roles, UserRole)
    student_routes = create_student_routes(db, get_current_user, require_roles, UserRole)
    teacher_management_routes = create_teacher_management_routes(db, get_current_user)
    class_management_routes = create_class_management_routes(db, get_current_user)
    notification_routes = create_notification_routes(db, get_current_user)

    from routes.teacher_attendance_routes import create_teacher_attendance_routes
    teacher_attendance_router = create_teacher_attendance_routes(db, get_current_user, require_roles, UserRole)

    from routes.communication_routes import create_communication_routes
    communication_router = create_communication_routes(db, get_current_user, require_roles, UserRole)

    from routes.bulk_teacher_routes import create_bulk_teacher_routes
    bulk_teacher_router = create_bulk_teacher_routes(db, get_current_user, require_roles, UserRole, hash_password, generate_secure_password)

    from routes.student_creation_routes import create_student_creation_routes
    student_creation_router = create_student_creation_routes(db, get_current_user, require_roles, UserRole, hash_password, generate_secure_password)

    from routes.admin_dashboard_routes import setup_admin_routes
    admin_dashboard_router = setup_admin_routes(db, get_current_user, require_roles, UserRole)

    from routes.security_routes import setup_security_routes
    from dependencies import require_recent_mfa as _require_recent_mfa
    security_router = setup_security_routes(db, get_current_user, require_roles, UserRole, _require_recent_mfa)

    from routes.audit_routes import setup_audit_routes
    audit_router = setup_audit_routes(db, get_current_user, require_roles, UserRole, _require_recent_mfa)

    from routes.settings_routes import setup_settings_routes
    settings_router = setup_settings_routes(db, get_current_user, require_roles, UserRole, _require_recent_mfa)

    from routes.user_roles_routes import setup_user_roles_routes
    user_roles_router = setup_user_roles_routes(db, get_current_user, require_roles, UserRole, create_access_token)

    from routes.websocket_routes import create_websocket_routes
    from db import async_session_factory as _ws_session_factory

    async def decode_token_for_ws(token: str):
        """
        Validate a JWT for WebSocket connections with the same rigour as HTTP
        routes:  verify signature+expiry, reject refresh tokens, check the JTI
        against revoked_tokens, and confirm the user is still active and not
        locked.  Returns the payload on success, None on any failure.
        """
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            # Reject refresh tokens — only access tokens may open a socket.
            if payload.get("type") == "refresh":
                return None
            jti = payload.get("jti")
            user_id = payload.get("sub")
            if not user_id:
                return None
            from engines.sql_utils import gd_find_one as _gdf
            async with _ws_session_factory() as ws_auth_session:
                # Check token revocation
                if jti:
                    revoked = await _gdf(ws_auth_session, "revoked_tokens", {"jti": jti})
                    if revoked:
                        logger.info(f"WebSocket auth rejected: revoked JTI={jti}")
                        return None
                # Check account is active and not locked
                user = await _gdf(ws_auth_session, "users", {"id": user_id})
                if not user:
                    return None
                if not user.get("is_active", True):
                    logger.info(f"WebSocket auth rejected: inactive user={user_id}")
                    return None
                if user.get("is_locked", False):
                    logger.info(f"WebSocket auth rejected: locked user={user_id}")
                    return None
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception):
            return None

    websocket_router, ws_manager = create_websocket_routes(db, decode_token_for_ws)

    from routes.bulk_import_export_routes import setup_bulk_routes, setup_import_tracking_routes
    bulk_routes = setup_bulk_routes(db, get_current_user, require_roles, UserRole)
    import_tracking_routes = setup_import_tracking_routes(db, get_current_user, require_roles, UserRole)

    from routes.student_portal_routes import setup_student_portal_routes
    student_portal_routes = setup_student_portal_routes(db, get_current_user, require_roles, UserRole)

    from routes.parent_portal_routes import setup_parent_portal_routes
    parent_portal_routes = setup_parent_portal_routes(db, get_current_user, require_roles, UserRole)

    api_router.include_router(attendance_router)
    api_router.include_router(assessment_router)
    api_router.include_router(audit_router)
    api_router.include_router(teacher_registration_router)
    api_router.include_router(student_routes)
    api_router.include_router(teacher_management_routes)
    api_router.include_router(class_management_routes)
    api_router.include_router(notification_routes)
    api_router.include_router(teacher_attendance_router, dependencies=_full_tenant_dep)
    api_router.include_router(communication_router)
    api_router.include_router(bulk_teacher_router, dependencies=_full_tenant_dep)
    api_router.include_router(student_creation_router)
    api_router.include_router(admin_dashboard_router)
    api_router.include_router(security_router)
    api_router.include_router(settings_router)
    api_router.include_router(user_roles_router)
    api_router.include_router(websocket_router)
    api_router.include_router(bulk_routes, dependencies=_full_tenant_dep)
    api_router.include_router(import_tracking_routes, dependencies=_full_tenant_dep)
    api_router.include_router(student_portal_routes)
    api_router.include_router(parent_portal_routes)

    # Phase 1 (#183) — fail-closed gate: every authenticated /api route
    # is checked. The dep is a no-op for non-IT callers and for the
    # explicit allow-list (auth surface, MFA enrolment, bootstrap).
    from auth_scope import require_workspace_materialised as _wm_dep
    from fastapi import Depends as _Depends2
    app.include_router(api_router, dependencies=[_Depends2(_wm_dep)])

    from engines.session_engine import session_router
    app.include_router(session_router)

    @app.websocket("/ws")
    async def reject_bare_ws(websocket: WebSocket):
        await websocket.close(code=1000)

    _register_static_fallback(app)


def _register_static_fallback(app):
    import os
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse, RedirectResponse

    frontend_build = (Path(__file__).parent.parent.parent / "frontend" / "build").resolve()
    if frontend_build.exists() and (frontend_build / "index.html").exists():
        app.mount("/static", StaticFiles(directory=str(frontend_build / "static")), name="static-assets")

        from fastapi import HTTPException as _HTTPException

        # Reserved prefixes that must never be served by the SPA fallback.
        # Match either an exact bare segment (e.g. "/api") OR a path
        # under that segment (e.g. "/api/users") — segment-boundary aware.
        _SPA_RESERVED_SEGMENTS = (
            "api", "system", "ws", "docs", "redoc", "openapi.json",
        )
        # B-18: explicit allow-list of file extensions the SPA fallback may
        # serve from the build directory. Anything else (.env, .yml, .json
        # config, etc.) accidentally dropped into frontend/build/ won't leak.
        _ALLOWED_STATIC_EXTS = {
            ".html", ".htm", ".js", ".mjs", ".css", ".map",
            ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".avif",
            ".woff", ".woff2", ".ttf", ".otf", ".eot",
            ".json",  # manifest.json, asset-manifest.json
            ".txt",   # robots.txt
            ".xml",   # sitemap.xml
            ".webmanifest",
            ".mp3", ".mp4", ".webm", ".ogg",
            ".pdf",
        }

        @app.get("/{full_path:path}")
        async def serve_react_app(full_path: str):
            # Never let the SPA fallback swallow backend / docs paths.
            first_segment = full_path.split("/", 1)[0]
            if first_segment in _SPA_RESERVED_SEGMENTS:
                raise _HTTPException(status_code=404, detail="Not Found")

            # B-01: path-traversal guard. Resolve the requested path and
            # confirm it stays inside the frontend_build directory before
            # serving it. Even though Starlette currently strips '..',
            # belt-and-braces prevents a future proxy/normaliser regression.
            try:
                requested = (frontend_build / full_path).resolve()
            except (OSError, RuntimeError):
                requested = None
            if requested is not None and requested.is_file():
                try:
                    requested.relative_to(frontend_build)
                except ValueError:
                    raise _HTTPException(status_code=404, detail="Not Found")
                # B-18: only serve approved extensions.
                if requested.suffix.lower() in _ALLOWED_STATIC_EXTS:
                    return FileResponse(str(requested))
                # Unknown extension → fall through to SPA index instead of leaking.
            return FileResponse(
                str(frontend_build / "index.html"),
                headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
            )
    else:
        @app.get("/")
        async def root_redirect():
            frontend_url = os.environ.get("FRONTEND_URL", "")
            if frontend_url:
                return RedirectResponse(url=frontend_url)
            return {"status": "NASSAQ API is running", "docs": "/docs", "health": "/system/health"}
