"""
NASSAQ - Models Package
Central export for all Pydantic models and enums
"""

# Enums
from .enums import (
    UserRole,
    SchoolStatus,
    RegistrationStatus,
    AttendanceStatus,
    AssessmentType,
    NotificationType,
    IntegrationType,
    IntegrationStatus,
    RuleCategory,
    RulePriority,
    RuleStatus,
)

# User Models
from .user import (
    UserBase,
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    PlatformUserCreate,
    PlatformUserResponse,
    PasswordChangeRequest,
    UserProfileUpdate,
    UserPreferencesUpdate,
    UserNotificationSettings,
)

# School Models
from .school import (
    SchoolBase,
    SchoolCreate,
    SchoolResponse,
    SchoolUpdate,
)

# Dashboard Models
from .dashboard import (
    DashboardStats,
    AIOperationResult,
    HakimMessage,
    HakimResponse,
    AlertItem,
    MetricValue,
    AttendanceBreakdown,
    SchoolDashboardData,
    PlatformActivityData,
)

# Academic Models
from .academic import (
    TeacherBase,
    TeacherCreate,
    TeacherResponse,
    StudentBase,
    StudentCreate,
    StudentResponse,
    ClassBase,
    ClassCreate,
    ClassResponse,
    SubjectBase,
    SubjectCreate,
    SubjectResponse,
    TeacherAssignment,
)

# Registration Models
from .registration import (
    RegistrationRequestBase,
    RegistrationRequestCreate,
    RegistrationRequestResponse,
    RegistrationApproval,
    RegistrationRejection,
    RegistrationMoreInfo,
    TeacherRegistrationRequest,
)

# Common Models
from .common import (
    StatusCheck,
    StatusCheckCreate,
    PaginatedResponse,
    BulkOperationResult,
    AuditLogEntry,
    MessageResponse,
    ErrorResponse,
    TimeSlot,
    TimeSlotCreate,
    DayOfWeek,
)

# Scheduling Models (keep existing)
from .scheduling import *

# Foundation Models (keep existing)
from .foundation import *

__all__ = [
    # Enums
    "UserRole",
    "SchoolStatus", 
    "RegistrationStatus",
    "AttendanceStatus",
    "AssessmentType",
    "NotificationType",
    "IntegrationType",
    "IntegrationStatus",
    "RuleCategory",
    "RulePriority",
    "RuleStatus",
    # User
    "UserBase",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "TokenResponse",
    "PlatformUserCreate",
    "PlatformUserResponse",
    "PasswordChangeRequest",
    "UserProfileUpdate",
    "UserPreferencesUpdate",
    "UserNotificationSettings",
    # School
    "SchoolBase",
    "SchoolCreate",
    "SchoolResponse",
    "SchoolUpdate",
    # Dashboard
    "DashboardStats",
    "AIOperationResult",
    "HakimMessage",
    "HakimResponse",
    "AlertItem",
    "MetricValue",
    "AttendanceBreakdown",
    "SchoolDashboardData",
    "PlatformActivityData",
    # Academic
    "TeacherBase",
    "TeacherCreate",
    "TeacherResponse",
    "StudentBase",
    "StudentCreate",
    "StudentResponse",
    "ClassBase",
    "ClassCreate",
    "ClassResponse",
    "SubjectBase",
    "SubjectCreate",
    "SubjectResponse",
    "TeacherAssignment",
    # Registration
    "RegistrationRequestBase",
    "RegistrationRequestCreate",
    "RegistrationRequestResponse",
    "RegistrationApproval",
    "RegistrationRejection",
    "RegistrationMoreInfo",
    "TeacherRegistrationRequest",
    # Common
    "StatusCheck",
    "StatusCheckCreate",
    "PaginatedResponse",
    "BulkOperationResult",
    "AuditLogEntry",
    "MessageResponse",
    "ErrorResponse",
    "TimeSlot",
    "TimeSlotCreate",
    "DayOfWeek",
]
