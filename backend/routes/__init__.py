"""
NASSAQ - Routes Package
Central export for all API routes
"""

from .auth_routes import create_auth_routes
from .user_routes import create_user_routes
from .school_routes import create_school_routes
from .dashboard_routes import create_dashboard_routes
from .public_routes import create_public_routes

# Existing routes (already modular)
from .scheduling_routes import create_scheduling_router
from .attendance_routes import create_attendance_router
from .assessment_routes import create_assessment_router
from .audit_routes import create_audit_router
from .teacher_registration_routes import create_teacher_registration_router
from .student_management_routes import create_student_routes
from .teacher_management_routes import create_teacher_management_routes
from .class_management_routes import create_class_management_routes
from .notification_routes import create_notification_routes
from .schedule_management_routes import create_schedule_management_routes
from .admin_dashboard_routes import setup_admin_routes
from .security_routes import setup_security_routes
from .audit_routes import setup_audit_routes
from .settings_routes import setup_settings_routes

__all__ = [
    # New modular routes
    "create_auth_routes",
    "create_user_routes",
    "create_school_routes",
    "create_dashboard_routes",
    "create_public_routes",
    # Existing routes
    "create_scheduling_router",
    "create_attendance_router",
    "create_assessment_router",
    "create_audit_router",
    "create_teacher_registration_router",
    "create_student_routes",
    "create_teacher_management_routes",
    "create_class_management_routes",
    "create_notification_routes",
    "create_schedule_management_routes",
    "setup_admin_routes",
    "setup_security_routes",
    "setup_audit_routes",
    "setup_settings_routes",
]
