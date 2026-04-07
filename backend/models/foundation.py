"""
NASSAQ Foundation Models
نماذج الأساس لمنصة نَسَّق

This module contains all foundational data models for the platform.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
import uuid


# ============== ENUMS ==============

class UserRole(str, Enum):
    """User roles in the system"""
    PLATFORM_ADMIN = "platform_admin"
    PLATFORM_SUB_ADMIN = "platform_sub_admin"
    PLATFORM_OPERATIONS_MANAGER = "platform_operations_manager"
    PLATFORM_TECHNICAL_ADMIN = "platform_technical_admin"
    PLATFORM_SUPPORT_SPECIALIST = "platform_support_specialist"
    PLATFORM_DATA_ANALYST = "platform_data_analyst"
    PLATFORM_SECURITY_OFFICER = "platform_security_officer"
    PLATFORM_SALES = "platform_sales"
    PLATFORM_MARKETING = "platform_marketing"
    PLATFORM_QUALITY = "platform_quality"
    MINISTRY_REP = "ministry_rep"
    SCHOOL_PRINCIPAL = "school_principal"
    SCHOOL_ADMIN = "school_admin"
    SCHOOL_SUB_ADMIN = "school_sub_admin"
    TEACHER = "teacher"
    INDEPENDENT_TEACHER = "independent_teacher"
    STUDENT = "student"
    PARENT = "parent"
    DRIVER = "driver"
    GATEKEEPER = "gatekeeper"
    TESTING_ACCOUNT = "testing_account"


class PermissionScope(str, Enum):
    """Permission scope levels"""
    PLATFORM = "platform"  # Platform-wide access
    TENANT = "tenant"      # School/tenant level access
    CLASS = "class"        # Class level access
    OWN = "own"           # Own data only


class AccountStatus(str, Enum):
    """User account status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING_ACTIVATION = "pending_activation"
    PENDING_VERIFICATION = "pending_verification"
    ARCHIVED = "archived"
    LOCKED = "locked"  # Too many failed login attempts


class TenantStatus(str, Enum):
    """Tenant/School status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    SETUP = "setup"
    TRIAL = "trial"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class TenantType(str, Enum):
    """Type of tenant account"""
    PRODUCTION = "production"
    DEMO = "demo"
    TRIAL = "trial"
    MARKETING = "marketing"
    TESTING = "testing"


class RelationshipType(str, Enum):
    """Types of relationships between users"""
    PARENT_CHILD = "parent_child"          # Parent -> Student
    SIBLING = "sibling"                    # Student -> Student (siblings)
    TEACHER_CLASS = "teacher_class"        # Teacher -> Class
    TEACHER_SUBJECT = "teacher_subject"    # Teacher -> Subject
    PRINCIPAL_SCHOOL = "principal_school"  # Principal -> School
    GUARDIAN = "guardian"                  # Guardian -> Student (non-parent)
    ENROLLED_IN_SCHOOL = "enrolled_in_school"  # Student -> School
    BELONGS_TO_CLASS = "belongs_to_class"      # Student -> Class
    BELONGS_TO_GRADE = "belongs_to_grade"      # Student -> Grade
    EMPLOYED_AT = "employed_at"                # Teacher -> School
    MANAGES_SCHOOL = "manages_school"          # Admin -> School


class EducationalStage(str, Enum):
    """Educational stages in Saudi Arabia"""
    KINDERGARTEN = "kindergarten"      # رياض الأطفال
    PRIMARY = "primary"                # ابتدائي
    INTERMEDIATE = "intermediate"      # متوسط
    SECONDARY = "secondary"            # ثانوي
    SECONDARY_GENERAL = "secondary_general"        # ثانوية عامة
    SECONDARY_PATHWAYS = "secondary_pathways"      # ثانوية مسارات
    SCHOOL_COMPLEX = "school_complex"              # مجمع مدارس


class GenderType(str, Enum):
    """Gender types"""
    MALE = "male"
    FEMALE = "female"


class SchoolType(str, Enum):
    """Types of schools"""
    PUBLIC = "public"              # حكومية
    PRIVATE = "private"            # أهلية
    INTERNATIONAL = "international" # دولية
    SPECIAL_NEEDS = "special_needs" # تعليم خاص


# ============== PERMISSION MODELS ==============

class Permission(BaseModel):
    """Individual permission definition"""
    id: str
    code: str                              # e.g., "users.create", "attendance.view"
    name_ar: str
    name_en: str
    description_ar: Optional[str] = None
    description_en: Optional[str] = None
    category: str                          # e.g., "users", "attendance", "reports"
    scope: PermissionScope = PermissionScope.OWN
    is_sensitive: bool = False             # Requires additional logging


class RolePermissions(BaseModel):
    """Role to permissions mapping"""
    role: UserRole
    permissions: List[str]                 # List of permission codes
    inherits_from: Optional[UserRole] = None  # Role inheritance


# ============== IDENTITY MODELS ==============

class UserIdentity(BaseModel):
    """
    Core user identity model
    Represents the unified identity across all roles
    """
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Basic Info
    email: str
    phone: Optional[str] = None
    national_id: Optional[str] = None      # رقم الهوية الوطنية
    
    # Names
    full_name: str
    full_name_en: Optional[str] = None
    
    # Authentication
    password_hash: str
    must_change_password: bool = True
    last_password_change: Optional[str] = None
    failed_login_attempts: int = 0
    locked_until: Optional[str] = None
    
    # Status
    status: AccountStatus = AccountStatus.PENDING_ACTIVATION
    is_active: bool = True
    
    # Primary Role
    primary_role: UserRole
    
    # Multi-role support
    linked_roles: List[Dict[str, Any]] = []  # [{role, tenant_id, scope_id, is_active}]
    
    # Preferences
    preferred_language: str = "ar"
    preferred_theme: str = "light"
    avatar_url: Optional[str] = None
    
    # Tenant Association (for school-level users)
    primary_tenant_id: Optional[str] = None
    
    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: Optional[str] = None
    last_login: Optional[str] = None
    
    # Email/Phone verification
    email_verified: bool = False
    phone_verified: bool = False


class UserRelationship(BaseModel):
    """
    Relationship between users
    Enables parent-child, sibling, guardian relationships
    """
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Relationship details
    relationship_type: RelationshipType
    
    # Users involved
    user_id_1: str                         # e.g., Parent ID
    user_id_2: str                         # e.g., Student ID
    
    # Direction indicator (for asymmetric relationships)
    # user_id_1 is the "owner" of the relationship
    # e.g., Parent owns relationship to Student
    
    # Status
    is_active: bool = True
    is_verified: bool = False              # Admin verified
    
    # Auto-detection info
    detected_automatically: bool = False
    detection_method: Optional[str] = None  # phone, email, national_id
    detection_confidence: Optional[float] = None
    
    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None


class LinkedRole(BaseModel):
    """A role linked to a user identity"""
    role: UserRole
    tenant_id: Optional[str] = None        # School ID for school-level roles
    scope_id: Optional[str] = None         # Additional scope (class_id, etc.)
    is_active: bool = True
    assigned_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    assigned_by: Optional[str] = None


# ============== TENANT MODELS ==============

class TenantConfiguration(BaseModel):
    """Tenant-specific configuration"""
    # AI Features
    ai_enabled: bool = True
    ai_hakim_enabled: bool = True
    ai_analytics_enabled: bool = True
    ai_import_enabled: bool = True
    
    # Features
    attendance_enabled: bool = True
    behaviour_enabled: bool = True
    assessments_enabled: bool = True
    scheduling_enabled: bool = True
    notifications_enabled: bool = True
    
    # Limits
    max_students: Optional[int] = None
    max_teachers: Optional[int] = None
    max_classes: Optional[int] = None
    
    # Branding
    custom_logo: Optional[str] = None
    primary_color: Optional[str] = None
    
    # Working days (ISO weekday numbers: 0=Monday, 6=Sunday)
    working_days: List[int] = [6, 0, 1, 2, 3]  # Sun-Thu by default
    
    # Academic settings
    academic_year_start_month: int = 9     # September
    periods_per_day: int = 7


class Tenant(BaseModel):
    """
    Tenant (School) model
    Central entity for multi-tenant isolation
    """
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Basic Info
    name_ar: str
    name_en: Optional[str] = None
    code: Optional[str] = None             # Unique school code
    
    # Type & Status
    tenant_type: TenantType = TenantType.PRODUCTION
    status: TenantStatus = TenantStatus.PENDING
    
    # School Details
    school_type: SchoolType = SchoolType.PRIVATE
    gender: Optional[GenderType] = None    # Boys/Girls school
    
    # Contact
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    
    # Location
    region: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    
    # Ministry/Government IDs
    ministry_id: Optional[str] = None      # رقم الوزارة
    license_number: Optional[str] = None
    
    # Capacity
    student_capacity: Optional[int] = None
    current_students: int = 0
    current_teachers: int = 0
    
    # Configuration
    configuration: TenantConfiguration = TenantConfiguration()
    
    # Setup Progress
    setup_completed: bool = False
    setup_steps_completed: List[str] = []
    
    # Health
    health_score: Optional[float] = None
    last_health_check: Optional[str] = None
    
    # Subscription
    subscription_start: Optional[str] = None
    subscription_end: Optional[str] = None
    trial_end: Optional[str] = None
    
    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: Optional[str] = None
    
    # Principal
    principal_id: Optional[str] = None


# ============== ACADEMIC STRUCTURE MODELS ==============

class Grade(BaseModel):
    """
    Grade/Year level within an educational stage
    e.g., الصف الأول الابتدائي
    """
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    
    stage: EducationalStage
    grade_number: int                      # 1, 2, 3, etc.
    name_ar: str                           # الصف الأول
    name_en: Optional[str] = None
    
    # Order for display
    display_order: int = 0
    
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Section(BaseModel):
    """
    Section within a class
    e.g., الصف الأول أ، الصف الأول ب
    """
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    grade_id: str
    
    name: str                              # أ، ب، ج or A, B, C
    capacity: int = 30
    current_students: int = 0
    
    # Assigned homeroom teacher
    homeroom_teacher_id: Optional[str] = None
    
    # Physical classroom
    classroom_id: Optional[str] = None
    
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PhysicalClassroom(BaseModel):
    """
    Physical classroom/room in the school
    """
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    
    name: str                              # Room name/number
    building: Optional[str] = None         # Building name
    floor: Optional[int] = None
    
    room_type: str = "classroom"           # classroom, lab, gym, library, etc.
    capacity: int = 30
    
    # Equipment
    has_projector: bool = False
    has_smartboard: bool = False
    has_ac: bool = True
    
    # Availability
    is_available: bool = True
    notes: Optional[str] = None
    
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Subject(BaseModel):
    """Subject/Course"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: Optional[str] = None        # None for global subjects
    
    name_ar: str
    name_en: Optional[str] = None
    code: Optional[str] = None
    
    # Subject category
    category: str = "core"                 # core, elective, activity
    
    # Applicable stages
    applicable_stages: List[EducationalStage] = []
    
    # Weekly periods
    default_periods_per_week: int = 4
    
    is_active: bool = True
    is_global: bool = False                # Available to all tenants
    
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ============== BEHAVIOUR ENGINE MODELS ==============

class BehaviourCategory(str, Enum):
    """Categories of behaviour"""
    POSITIVE = "positive"                  # إيجابي
    NEGATIVE = "negative"                  # سلبي
    NEUTRAL = "neutral"                    # محايد


class BehaviourSeverity(str, Enum):
    """Severity levels for behaviour incidents"""
    MINOR = "minor"                        # بسيط
    MODERATE = "moderate"                  # متوسط
    MAJOR = "major"                        # كبير
    SEVERE = "severe"                      # خطير


class BehaviourStatus(str, Enum):
    """Status of behaviour record"""
    PENDING = "pending"                    # قيد المراجعة
    REVIEWED = "reviewed"                  # تمت المراجعة
    ESCALATED = "escalated"                # تم التصعيد
    RESOLVED = "resolved"                  # تم الحل
    ARCHIVED = "archived"                  # مؤرشف


class BehaviourType(BaseModel):
    """Type definition for behaviours"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: Optional[str] = None        # None for global types
    
    name_ar: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    
    category: BehaviourCategory
    default_severity: BehaviourSeverity
    default_points: int = 0                # Positive or negative points
    
    # Escalation
    auto_escalate: bool = False
    escalation_threshold: Optional[int] = None  # Number of occurrences
    
    is_active: bool = True
    is_global: bool = False
    
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BehaviourRecord(BaseModel):
    """Individual behaviour incident record"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    
    # Student
    student_id: str
    class_id: Optional[str] = None
    
    # Behaviour details
    behaviour_type_id: str
    category: BehaviourCategory
    severity: BehaviourSeverity
    
    # Description
    title: str
    description: Optional[str] = None
    
    # Points
    points: int = 0
    
    # Incident details
    incident_date: str
    incident_location: Optional[str] = None
    witnesses: List[str] = []              # List of user IDs
    
    # Status
    status: BehaviourStatus = BehaviourStatus.PENDING
    
    # Follow-up
    requires_follow_up: bool = False
    follow_up_date: Optional[str] = None
    follow_up_notes: Optional[str] = None
    
    # Parent notification
    parent_notified: bool = False
    parent_notified_at: Optional[str] = None
    
    # Principal review
    principal_reviewed: bool = False
    principal_reviewed_by: Optional[str] = None
    principal_reviewed_at: Optional[str] = None
    principal_notes: Optional[str] = None
    
    # Disciplinary action
    disciplinary_action: Optional[str] = None
    disciplinary_action_date: Optional[str] = None
    
    # Privacy
    is_confidential: bool = False          # Limited visibility
    visible_to_parent: bool = True
    
    # Created by
    recorded_by: str
    recorded_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Edit window
    editable_until: Optional[str] = None   # After this, changes need approval


class DisciplinaryAction(BaseModel):
    """Disciplinary action taken"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    
    behaviour_record_id: str
    student_id: str
    
    action_type: str                       # warning, detention, suspension, etc.
    description: str
    
    # Duration (for suspensions)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    
    # Status
    is_active: bool = True
    is_completed: bool = False
    completed_at: Optional[str] = None
    
    # Approval
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    
    created_by: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ============== AUDIT LOG MODELS ==============

class AuditAction(str, Enum):
    """Types of auditable actions"""
    # User actions
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_LOGIN_FAILED = "user_login_failed"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_SUSPENDED = "user_suspended"
    USER_ACTIVATED = "user_activated"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"
    ROLE_SWITCHED = "role_switched"
    
    # Tenant actions
    TENANT_CREATED = "tenant_created"
    TENANT_UPDATED = "tenant_updated"
    TENANT_SUSPENDED = "tenant_suspended"
    TENANT_ACTIVATED = "tenant_activated"
    
    # Academic actions
    SCHEDULE_PUBLISHED = "schedule_published"
    ATTENDANCE_SUBMITTED = "attendance_submitted"
    ATTENDANCE_MODIFIED = "attendance_modified"
    ASSESSMENT_CREATED = "assessment_created"
    GRADES_SUBMITTED = "grades_submitted"
    
    # Behaviour actions
    BEHAVIOUR_RECORDED = "behaviour_recorded"
    BEHAVIOUR_REVIEWED = "behaviour_reviewed"
    DISCIPLINARY_ACTION = "disciplinary_action"
    
    # System actions
    SETTINGS_UPDATED = "settings_updated"
    AI_FEATURE_TOGGLED = "ai_feature_toggled"
    DATA_IMPORTED = "data_imported"
    DATA_EXPORTED = "data_exported"
    REPORT_GENERATED = "report_generated"
    
    # Security actions
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    PERMISSION_CHANGED = "permission_changed"


class AuditLog(BaseModel):
    """Comprehensive audit log entry"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Action info
    action: AuditAction
    action_category: str                   # user, tenant, academic, etc.
    
    # Actor (who performed the action)
    actor_id: str
    actor_name: str
    actor_role: str
    actor_ip: Optional[str] = None
    actor_user_agent: Optional[str] = None
    
    # Target (what was affected)
    target_type: str                       # user, tenant, schedule, etc.
    target_id: str
    target_name: Optional[str] = None
    
    # Tenant context
    tenant_id: Optional[str] = None
    
    # Details
    details: Dict[str, Any] = {}
    
    # Before/After for updates
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    
    # Flags
    is_sensitive: bool = False
    requires_review: bool = False
    
    # Timestamp
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ============== NOTIFICATION MODELS ==============

class NotificationType(str, Enum):
    """Types of notifications"""
    SYSTEM = "system"
    ALERT = "alert"
    REMINDER = "reminder"
    MESSAGE = "message"
    ANNOUNCEMENT = "announcement"
    APPROVAL_REQUEST = "approval_request"


class NotificationPriority(str, Enum):
    """Priority levels for notifications"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationChannel(str, Enum):
    """Delivery channels"""
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class NotificationTemplate(BaseModel):
    """Notification template for automated notifications"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    code: str                              # Unique template code
    name_ar: str
    name_en: Optional[str] = None
    
    # Template content
    title_template_ar: str
    title_template_en: Optional[str] = None
    body_template_ar: str
    body_template_en: Optional[str] = None
    
    # Settings
    notification_type: NotificationType
    default_priority: NotificationPriority = NotificationPriority.NORMAL
    channels: List[NotificationChannel] = [NotificationChannel.IN_APP]
    
    # Variables
    variables: List[str] = []              # e.g., ["student_name", "class_name"]
    
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ============== REPORTING MODELS ==============

class ReportScope(str, Enum):
    """Scope of reports"""
    PLATFORM = "platform"
    TENANT = "tenant"
    GRADE = "grade"
    CLASS = "class"
    STUDENT = "student"
    TEACHER = "teacher"


class ReportCategory(str, Enum):
    """Categories of reports"""
    ATTENDANCE = "attendance"
    ACADEMIC = "academic"
    BEHAVIOUR = "behaviour"
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    AI_INSIGHTS = "ai_insights"


class ReportDefinition(BaseModel):
    """Definition of a report type"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    code: str                              # Unique report code
    name_ar: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    
    category: ReportCategory
    scope: ReportScope
    
    # Data sources
    data_sources: List[str] = []           # Collections/tables to query
    
    # KPIs included
    kpis: List[str] = []
    
    # Filters available
    available_filters: List[str] = []
    
    # Role visibility
    visible_to_roles: List[UserRole] = []
    
    # Export formats
    export_formats: List[str] = ["pdf", "excel"]
    
    is_active: bool = True
    is_ai_generated: bool = False
    
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GeneratedReport(BaseModel):
    """A generated report instance"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    report_definition_id: str
    tenant_id: Optional[str] = None
    
    # Scope details
    scope: ReportScope
    scope_id: Optional[str] = None         # tenant_id, class_id, etc.
    
    # Date range
    start_date: str
    end_date: str
    
    # Generated data
    data: Dict[str, Any] = {}
    summary: Optional[str] = None
    ai_insights: Optional[str] = None
    
    # Status
    status: str = "completed"              # pending, processing, completed, failed
    
    # Generated by
    generated_by: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Export
    export_url: Optional[str] = None
    export_format: Optional[str] = None


# ============== AI ENGINE MODELS ==============

class AIRecommendationType(str, Enum):
    """Types of AI recommendations"""
    INTERVENTION = "intervention"          # Student intervention needed
    OPTIMIZATION = "optimization"          # Process optimization
    RISK_ALERT = "risk_alert"             # Risk warning
    INSIGHT = "insight"                   # General insight
    PREDICTION = "prediction"             # Predictive analysis


class AIRecommendationStatus(str, Enum):
    """Status of AI recommendations"""
    PENDING = "pending"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    EXPIRED = "expired"


class AIRecommendation(BaseModel):
    """AI-generated recommendation"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    tenant_id: Optional[str] = None
    
    # Recommendation details
    recommendation_type: AIRecommendationType
    title: str
    description: str
    
    # Target
    target_type: Optional[str] = None      # student, class, school
    target_id: Optional[str] = None
    
    # Priority and confidence
    priority: str = "medium"               # low, medium, high, critical
    confidence_score: float = 0.0          # 0.0 to 1.0
    
    # Explainability
    reasoning: Optional[str] = None        # Why this recommendation
    data_points: List[Dict[str, Any]] = [] # Supporting data
    
    # Status
    status: AIRecommendationStatus = AIRecommendationStatus.PENDING
    
    # Review
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None
    
    # Implementation
    implemented_by: Optional[str] = None
    implemented_at: Optional[str] = None
    implementation_notes: Optional[str] = None
    
    # Expiry
    expires_at: Optional[str] = None
    
    # Metadata
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    model_version: Optional[str] = None


class StudentRiskIndicator(BaseModel):
    """Risk indicator for a student"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    tenant_id: str
    student_id: str
    
    # Risk assessment
    overall_risk_level: str = "low"        # low, medium, high, critical
    overall_risk_score: float = 0.0        # 0.0 to 1.0
    
    # Risk dimensions
    academic_risk: float = 0.0
    attendance_risk: float = 0.0
    behaviour_risk: float = 0.0
    social_risk: float = 0.0
    
    # Contributing factors
    factors: List[Dict[str, Any]] = []
    
    # Recommendations
    recommendation_ids: List[str] = []
    
    # Timestamps
    calculated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    valid_until: Optional[str] = None


# Export all models
__all__ = [
    # Enums
    "UserRole", "PermissionScope", "AccountStatus", "TenantStatus", "TenantType",
    "RelationshipType", "EducationalStage", "GenderType", "SchoolType",
    "BehaviourCategory", "BehaviourSeverity", "BehaviourStatus",
    "AuditAction", "NotificationType", "NotificationPriority", "NotificationChannel",
    "ReportScope", "ReportCategory", "AIRecommendationType", "AIRecommendationStatus",
    
    # Permission models
    "Permission", "RolePermissions",
    
    # Identity models
    "UserIdentity", "UserRelationship", "LinkedRole",
    
    # Tenant models
    "TenantConfiguration", "Tenant",
    
    # Academic models
    "Grade", "Section", "PhysicalClassroom", "Subject",
    
    # Behaviour models
    "BehaviourType", "BehaviourRecord", "DisciplinaryAction",
    
    # Audit models
    "AuditLog",
    
    # Notification models
    "NotificationTemplate",
    
    # Reporting models
    "ReportDefinition", "GeneratedReport",
    
    # AI models
    "AIRecommendation", "StudentRiskIndicator",
]
