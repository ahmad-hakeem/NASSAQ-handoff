"""
NASSAQ - Enums Module
All application enumerations
"""
from enum import Enum


class UserRole(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    PLATFORM_OPERATIONS_MANAGER = "platform_operations_manager"
    PLATFORM_TECHNICAL_ADMIN = "platform_technical_admin"
    PLATFORM_SUPPORT_SPECIALIST = "platform_support_specialist"
    PLATFORM_DATA_ANALYST = "platform_data_analyst"
    PLATFORM_SECURITY_OFFICER = "platform_security_officer"
    MINISTRY_REP = "ministry_rep"
    SCHOOL_PRINCIPAL = "school_principal"
    SCHOOL_ADMIN = "school_admin"
    SCHOOL_SUB_ADMIN = "school_sub_admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"
    DRIVER = "driver"
    GATEKEEPER = "gatekeeper"
    TESTING_ACCOUNT = "testing_account"


class SchoolStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    SETUP = "setup"


class RegistrationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MORE_INFO_REQUESTED = "more_info_requested"
    PENDING_REVIEW = "pending_review"


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class AssessmentType(str, Enum):
    QUIZ = "quiz"
    ASSIGNMENT = "assignment"
    EXAM = "exam"
    PARTICIPATION = "participation"
    PROJECT = "project"
    MIDTERM = "midterm"
    FINAL = "final"
    ORAL = "oral"
    PRACTICAL = "practical"


class NotificationType(str, Enum):
    INFO = "info"
    WARNING = "warning"
    SUCCESS = "success"
    ERROR = "error"
    ALERT = "alert"


class IntegrationType(str, Enum):
    GOVERNMENT = "government"
    PAYMENT = "payment"
    SMS = "sms"
    EMAIL = "email"
    STORAGE = "storage"
    AI = "ai"
    OTHER = "other"


class IntegrationStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ERROR = "error"


class RuleCategory(str, Enum):
    ATTENDANCE = "attendance"
    GRADING = "grading"
    SCHEDULING = "scheduling"
    BEHAVIOR = "behavior"
    ACADEMIC = "academic"
    TENANT = "tenant"
    SECURITY = "security"
    AI = "ai"


class RulePriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RuleStatus(str, Enum):
    ACTIVE = "active"
    DRAFT = "draft"
    DISABLED = "disabled"
