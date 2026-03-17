"""
NASSAQ Engines Package
محركات نَسَّق الأساسية

Core business logic engines for the NASSAQ platform.
Each engine handles a specific domain of the school management system.
"""

from engines.identity_engine import IdentityEngine
from engines.tenant_engine import TenantEngine
from engines.behaviour_engine import BehaviourEngine
from engines.academic_engine import AcademicStructureEngine
from engines.scheduling_engine import SchedulingEngine
from engines.attendance_engine import AttendanceEngine
from engines.assessment_engine import AssessmentEngine
from engines.notification_engine import NotificationEngine
from engines.audit_engine import AuditLogEngine
from engines.teacher_registration_engine import TeacherRegistrationEngine
from engines.student_management_engine import StudentManagementEngine
from engines.session_engine import TeacherSessionEngine, session_router

__all__ = [
    # Core Identity & Access
    "IdentityEngine",
    "TenantEngine",
    
    # Academic Structure
    "AcademicStructureEngine",
    
    # Operations
    "SchedulingEngine",
    "AttendanceEngine",
    "AssessmentEngine",
    "BehaviourEngine",
    
    # Communication
    "NotificationEngine",
    
    # System
    "AuditLogEngine",
    
    # Registration
    "TeacherRegistrationEngine",
    
    # Student Management
    "StudentManagementEngine",
    
    # Teacher Session
    "TeacherSessionEngine",
    "session_router",
]
