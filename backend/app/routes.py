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
    api_router.include_router(scheduling_smart_router)
    api_router.include_router(scheduling_smart_sess_router)
    api_router.include_router(schedule_candidates_router)
    api_router.include_router(schedule_master_grid_router)
    api_router.include_router(standby_router)
    api_router.include_router(attendance_mod_router)
    api_router.include_router(assessment_mod_router)
    api_router.include_router(behaviour_mod_router)
    api_router.include_router(notification_mod_router)
    api_router.include_router(participation_mod_router)
    api_router.include_router(platform_mod_router)
    api_router.include_router(reporting_mod_router)
    api_router.include_router(role_dashboards_mod_router)
    api_router.include_router(admin_mod_router)
    api_router.include_router(school_settings_mod_router)
    api_router.include_router(search_directory_mod_router)
    api_router.include_router(event_workflow_mod_router)
    api_router.include_router(relationship_mod_router)
    api_router.include_router(consent_privacy_mod_router)
    api_router.include_router(activities_mod_router)
    api_router.include_router(product_hub_router)
    api_router.include_router(portfolio_mod_router)
    api_router.include_router(calendar_mod_router)
    api_router.include_router(hakeem_plan_mod_router)

    from routes.principal_management_routes import router as principal_mgmt_router
    api_router.include_router(principal_mgmt_router)

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
    security_router = setup_security_routes(db, get_current_user, require_roles, UserRole)

    from routes.audit_routes import setup_audit_routes
    audit_router = setup_audit_routes(db, get_current_user, require_roles, UserRole)

    from routes.settings_routes import setup_settings_routes
    settings_router = setup_settings_routes(db, get_current_user, require_roles, UserRole)

    from routes.user_roles_routes import setup_user_roles_routes
    user_roles_router = setup_user_roles_routes(db, get_current_user, require_roles, UserRole, create_access_token)

    from routes.websocket_routes import create_websocket_routes

    def decode_token_for_ws(token: str):
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
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
    api_router.include_router(teacher_attendance_router)
    api_router.include_router(communication_router)
    api_router.include_router(bulk_teacher_router)
    api_router.include_router(student_creation_router)
    api_router.include_router(admin_dashboard_router)
    api_router.include_router(security_router)
    api_router.include_router(settings_router)
    api_router.include_router(user_roles_router)
    api_router.include_router(websocket_router)
    api_router.include_router(bulk_routes)
    api_router.include_router(import_tracking_routes)
    api_router.include_router(student_portal_routes)
    api_router.include_router(parent_portal_routes)

    app.include_router(api_router)

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
