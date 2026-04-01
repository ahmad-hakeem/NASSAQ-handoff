"""
Product Intelligence Hub — Database Models & Validation
نماذج قاعدة البيانات ونظام التحقق لمركز ذكاء المنتج

Production-ready Pydantic models with strict enum validation,
field constraints, and structured document schemas for MongoDB.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime, timezone
import uuid


class IssueType(str, Enum):
    BUG = "bug"
    ERROR = "error"
    UI_ISSUE = "ui_issue"
    UX_ISSUE = "ux_issue"
    PERFORMANCE_ISSUE = "performance_issue"
    CONTENT_ISSUE = "content_issue"
    FEATURE_REQUEST = "feature_request"
    IMPROVEMENT_SUGGESTION = "improvement_suggestion"
    PERMISSION_ISSUE = "permission_issue"
    WORKFLOW_ISSUE = "workflow_issue"
    INTEGRATION_ISSUE = "integration_issue"
    OTHER = "other"


class IssueStatus(str, Enum):
    NEW = "new"
    UNDER_REVIEW = "under_review"
    IN_PROGRESS = "in_progress"
    QA_VALIDATION = "qa_validation"
    DONE = "done"
    REJECTED = "rejected"
    USER_FEEDBACK_CONFIRMED = "user_feedback_confirmed"


class IssuePriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Reproducible(str, Enum):
    YES = "yes"
    NO = "no"
    SOMETIMES = "sometimes"


class TeamEnum(str, Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    QA = "qa"
    DESIGN = "design"
    PRODUCT = "product"
    INFRA = "infra"


class ImpactType(str, Enum):
    BLOCKS_PROCESS = "blocks_process"
    WRONG_RESULTS = "wrong_results"
    SLOW_PERFORMANCE = "slow_performance"
    USER_CONFUSION = "user_confusion"
    VISUAL_ISSUE = "visual_issue"
    DATA_LOSS = "data_loss"
    MINOR_IMPACT = "minor_impact"


class RelatedTo(str, Enum):
    API = "api"
    UI = "ui"
    DATABASE = "database"
    PERMISSIONS = "permissions"
    UPLOAD = "upload"
    AUTH = "auth"


class AccountType(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    SCHOOL_ADMIN = "school_admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"
    WEBSITE_USER = "website_user"
    ENTIRE_SYSTEM = "entire_system"


class Platform(str, Enum):
    WEB = "web"
    MOBILE = "mobile"
    API = "api"
    DESKTOP = "desktop"


class CommentType(str, Enum):
    ADMIN_NOTE = "admin_note"
    QA_NOTE = "qa_note"
    GENERAL = "general"


class AuditAction(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    AI_ANALYZED = "ai_analyzed"
    DUPLICATE_DETECTED = "duplicate_detected"
    PROMPT_GENERATED = "prompt_generated"
    COMMENT_ADDED = "comment_added"
    ATTACHMENT_ADDED = "attachment_added"
    CLOSED = "closed"
    REOPENED = "reopened"
    FEEDBACK_CONFIRMED = "feedback_confirmed"


class AuditRole(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    INTERNAL_USER = "internal_user"


ISSUE_TYPE_LABELS = {
    "bug": "خطأ برمجي",
    "error": "خطأ تقني",
    "ui_issue": "مشكلة واجهة",
    "ux_issue": "مشكلة تجربة مستخدم",
    "performance_issue": "مشكلة أداء",
    "content_issue": "مشكلة محتوى",
    "feature_request": "طلب ميزة",
    "improvement_suggestion": "اقتراح تحسين",
    "permission_issue": "مشكلة صلاحيات",
    "workflow_issue": "مشكلة سير عمل",
    "integration_issue": "مشكلة تكامل",
    "other": "أخرى",
}

ISSUE_TYPE_COMPAT = {
    "performance": "performance_issue",
    "content": "content_issue",
    "improvement": "improvement_suggestion",
    "permission": "permission_issue",
    "workflow": "workflow_issue",
    "integration": "integration_issue",
}

SECTION_OPTIONS = [
    "لوحة القيادة", "إدارة المدارس", "إدارة المستخدمين",
    "الجداول والمواعيد", "الحضور والغياب", "التقييمات",
    "التقارير", "الإعدادات", "التسجيل", "حكيم الذكي",
    "بوابة الطالب", "بوابة ولي الأمر", "بوابة المعلم",
    "التواصل", "الأمان", "أخرى"
]

ACCOUNT_TYPE_OPTIONS = [e.value for e in AccountType]

DYNAMIC_FIELDS_BY_TYPE = {
    "bug": ["steps_to_reproduce", "reproducibility", "error_message"],
    "error": ["error_message", "error_code", "steps_to_reproduce"],
    "ui_issue": ["screen_area", "affected_elements"],
    "ux_issue": ["user_journey", "pain_point"],
    "performance_issue": ["load_time", "affected_operation"],
    "content_issue": ["content_location", "content_type"],
    "feature_request": ["use_case", "business_value"],
    "improvement_suggestion": ["improvement_area", "expected_impact"],
    "permission_issue": ["affected_role", "expected_access"],
    "workflow_issue": ["workflow_name", "broken_step"],
    "integration_issue": ["integration_name", "api_endpoint"],
    "other": ["additional_details"],
}

VALID_ISSUE_TYPES = set(ISSUE_TYPE_LABELS.keys())
VALID_ACCOUNT_TYPES = set(ACCOUNT_TYPE_OPTIONS)
VALID_SECTIONS = set(SECTION_OPTIONS)
VALID_TEAMS = {"Frontend", "Backend", "DevOps", "Design", "QA", "Product"}

ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
    ".mp4", ".webm", ".mov",
    ".pdf",
}
MAX_ATTACHMENT_SIZE_MB = 10
MAX_ATTACHMENTS_PER_ISSUE = 10


class AttachmentModel(BaseModel):
    name: str
    url: str
    type: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("اسم المرفق مطلوب")
        return v.strip()

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        if not v or not v.strip():
            raise ValueError("رابط المرفق مطلوب")
        return v.strip()


class DuplicateCandidate(BaseModel):
    issue_id: str
    confidence: float = Field(ge=0.0, le=1.0)


class IssueContext(BaseModel):
    account_type: str
    platform: str = "web"
    section: str
    page: str
    url: Optional[str] = None
    device: Optional[str] = None
    browser: Optional[str] = None
    user_id: Optional[str] = None

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, v):
        if v not in VALID_ACCOUNT_TYPES:
            raise ValueError(f"نوع الحساب غير صالح: {v}")
        return v

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v):
        valid = {e.value for e in Platform}
        if v not in valid:
            raise ValueError(f"منصة غير صالحة: {v}")
        return v


class IssueDescription(BaseModel):
    current_behavior: str
    expected_behavior: str
    reproduction_steps: Optional[List[str]] = None
    reproducible: Optional[str] = None

    @field_validator("current_behavior", "expected_behavior")
    @classmethod
    def validate_behavior(cls, v):
        if not v or not v.strip():
            raise ValueError("هذا الحقل مطلوب")
        if len(v.strip()) > 5000:
            raise ValueError("النص طويل جداً (الحد الأقصى 5000 حرف)")
        return v.strip()

    @field_validator("reproducible")
    @classmethod
    def validate_reproducible(cls, v):
        if v is not None:
            valid = {e.value for e in Reproducible}
            if v not in valid:
                raise ValueError(f"قيمة غير صالحة لحقل قابلية إعادة الإنتاج: {v}")
        return v


class IssueTechnical(BaseModel):
    error_message: Optional[str] = None
    related_to: Optional[List[str]] = None

    @field_validator("related_to")
    @classmethod
    def validate_related_to(cls, v):
        if v:
            valid = {e.value for e in RelatedTo}
            for item in v:
                if item not in valid:
                    raise ValueError(f"قيمة غير صالحة في الحقل التقني: {item}")
        return v


class IssueBusiness(BaseModel):
    affected_users_count: Optional[int] = Field(default=None, ge=0)
    user_type_weight: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    impact_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)


class IssueAssignment(BaseModel):
    assigned_to: Optional[str] = None
    team: Optional[str] = None
    due_date: Optional[str] = None

    @field_validator("team")
    @classmethod
    def validate_team(cls, v):
        if v is not None:
            valid = {e.value for e in TeamEnum}
            if v.lower() not in valid:
                raise ValueError(f"فريق غير صالح: {v}")
        return v


class IssueAI(BaseModel):
    suggested_title: Optional[str] = None
    duplicate_detected: bool = False
    duplicate_candidates: Optional[List[DuplicateCandidate]] = None
    suggested_team: Optional[str] = None
    generated_prompt: Optional[str] = None
    priority_reasoning: Optional[str] = None
    team_reasoning: Optional[str] = None
    technical_notes: Optional[str] = None
    impact_assessment: Optional[str] = None


class SubmissionMetadata(BaseModel):
    employee_name: str
    employee_id: Optional[str] = None
    user_id: str
    created_at: str
    created_date: str
    created_time: str


class IssueVisibility(BaseModel):
    prompt_visible_to_admin_only: bool = True


class IssueSystem(BaseModel):
    created_by: str
    created_at: str
    updated_at: str
    last_status_changed_at: Optional[str] = None


ACCOUNT_SECTION_MAP = {
    "platform_admin": "إدارة المنصة",
    "school_admin": "إدارة المدرسة",
    "teacher": "المعلم",
    "student": "الطالب",
    "parent": "ولي الأمر",
    "website_user": "الموقع الإلكتروني",
}

class IssueCreate(BaseModel):
    issue_type: str
    employee_name: str
    employee_id: Optional[str] = None
    account_type: str
    title: Optional[str] = None
    section: Optional[str] = None
    page: str
    current_behavior: str
    expected_behavior: str
    steps_to_reproduce: Optional[str] = None
    reproducibility: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    screen_area: Optional[str] = None
    affected_elements: Optional[str] = None
    user_journey: Optional[str] = None
    pain_point: Optional[str] = None
    load_time: Optional[str] = None
    affected_operation: Optional[str] = None
    content_location: Optional[str] = None
    content_type: Optional[str] = None
    use_case: Optional[str] = None
    business_value: Optional[str] = None
    improvement_area: Optional[str] = None
    expected_impact: Optional[str] = None
    affected_role: Optional[str] = None
    expected_access: Optional[str] = None
    workflow_name: Optional[str] = None
    broken_step: Optional[str] = None
    integration_name: Optional[str] = None
    api_endpoint: Optional[str] = None
    additional_details: Optional[str] = None
    url: Optional[str] = None
    device: Optional[str] = None
    browser: Optional[str] = None
    platform: Optional[str] = "web"
    attachments: Optional[List[str]] = None
    impact: Optional[List[str]] = None
    related_to: Optional[List[str]] = None
    affected_users_count: Optional[int] = None

    @field_validator("issue_type")
    @classmethod
    def validate_issue_type(cls, v):
        if v in ISSUE_TYPE_COMPAT:
            return ISSUE_TYPE_COMPAT[v]
        if v not in VALID_ISSUE_TYPES:
            raise ValueError(f"نوع المشكلة غير صالح: {v}")
        return v

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, v):
        if v not in VALID_ACCOUNT_TYPES:
            raise ValueError(f"نوع الحساب غير صالح: {v}")
        return v

    @field_validator("employee_name")
    @classmethod
    def validate_employee_name(cls, v):
        if not v or not v.strip():
            raise ValueError("اسم الموظف مطلوب")
        v = v.strip()
        if len(v) < 3:
            raise ValueError("اسم الموظف يجب أن يكون 3 أحرف على الأقل")
        if len(v) > 200:
            raise ValueError("اسم الموظف طويل جداً")
        return v

    @field_validator("current_behavior", "expected_behavior")
    @classmethod
    def validate_behavior_fields(cls, v):
        if not v or not v.strip():
            raise ValueError("هذا الحقل مطلوب")
        if len(v.strip()) > 5000:
            raise ValueError("النص طويل جداً (الحد الأقصى 5000 حرف)")
        return v.strip()

    @field_validator("page")
    @classmethod
    def validate_required_string(cls, v):
        if not v or not v.strip():
            raise ValueError("هذا الحقل مطلوب")
        return v.strip()

    @model_validator(mode="after")
    def derive_section(self):
        if not self.section or not self.section.strip():
            self.section = ACCOUNT_SECTION_MAP.get(self.account_type, "عام")
        else:
            self.section = self.section.strip()
        return self

    @field_validator("reproducibility")
    @classmethod
    def validate_reproducibility(cls, v):
        if v is not None:
            valid = {e.value for e in Reproducible}
            if v not in valid:
                raise ValueError(f"قيمة غير صالحة لقابلية إعادة الإنتاج: {v}")
        return v

    @field_validator("impact")
    @classmethod
    def validate_impact(cls, v):
        if v:
            valid = {e.value for e in ImpactType}
            for item in v:
                if item not in valid:
                    raise ValueError(f"نوع التأثير غير صالح: {item}")
        return v

    @field_validator("related_to")
    @classmethod
    def validate_related_to(cls, v):
        if v:
            valid = {e.value for e in RelatedTo}
            for item in v:
                if item not in valid:
                    raise ValueError(f"حقل تقني غير صالح: {item}")
        return v

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v):
        if v:
            valid = {e.value for e in Platform}
            if v not in valid:
                raise ValueError(f"منصة غير صالحة: {v}")
        return v or "web"

    @field_validator("attachments")
    @classmethod
    def validate_attachments(cls, v):
        if v:
            if len(v) > MAX_ATTACHMENTS_PER_ISSUE:
                raise ValueError(f"الحد الأقصى للمرفقات هو {MAX_ATTACHMENTS_PER_ISSUE}")
            import os
            for filename in v:
                ext = os.path.splitext(filename.lower())[1]
                if ext and ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
                    raise ValueError(f"نوع الملف غير مسموح: {ext}")
        return v

    def to_issue_document(self, user_id: str, user: dict) -> dict:
        now = datetime.now(timezone.utc)
        issue_id = str(uuid.uuid4())

        return {
            "id": issue_id,
            "title": None,
            "type": self.issue_type,
            "issue_type": self.issue_type,

            "context": {
                "account_type": self.account_type,
                "platform": self.platform or "web",
                "section": self.section,
                "page": self.page,
                "url": self.url,
                "device": self.device,
                "browser": self.browser,
                "user_id": user_id,
            },

            "description": {
                "current_behavior": self.current_behavior,
                "expected_behavior": self.expected_behavior,
                "reproduction_steps": [self.steps_to_reproduce] if self.steps_to_reproduce else [],
                "reproducible": self.reproducibility,
            },

            "impact": self.impact or [],

            "technical": {
                "error_message": self.error_message,
                "related_to": self.related_to or [],
            },

            "business": {
                "affected_users_count": self.affected_users_count,
                "user_type_weight": None,
                "impact_score": None,
            },

            "priority": None,
            "ai_suggested_priority": None,

            "status": "new",

            "assignment": {
                "assigned_to": None,
                "team": None,
                "due_date": None,
            },

            "ai": {
                "suggested_title": None,
                "duplicate_detected": False,
                "duplicate_candidates": [],
                "suggested_team": None,
                "generated_prompt": None,
                "priority_reasoning": None,
                "team_reasoning": None,
                "technical_notes": None,
                "impact_assessment": None,
            },

            "attachments": [
                {"name": a, "url": a, "type": ""} for a in (self.attachments or [])
            ],

            "submission_metadata": {
                "employee_name": self.employee_name,
                "employee_id": self.employee_id,
                "user_id": user_id,
                "created_at": now.isoformat(),
                "created_date": now.strftime("%Y-%m-%d"),
                "created_time": now.strftime("%H:%M:%S"),
            },

            "visibility": {
                "prompt_visible_to_admin_only": True,
            },

            "system": {
                "created_by": user_id,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "last_status_changed_at": None,
            },

            "employee_name": self.employee_name,
            "employee_id": self.employee_id,
            "account_type": self.account_type,
            "section": self.section,
            "page": self.page,
            "current_behavior": self.current_behavior,
            "expected_behavior": self.expected_behavior,
            "steps_to_reproduce": self.steps_to_reproduce,
            "reproducibility": self.reproducibility,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "screen_area": self.screen_area,
            "affected_elements": self.affected_elements,
            "user_journey": self.user_journey,
            "pain_point": self.pain_point,
            "load_time": self.load_time,
            "affected_operation": self.affected_operation,
            "content_location": self.content_location,
            "content_type_field": self.content_type,
            "use_case": self.use_case,
            "business_value": self.business_value,
            "improvement_area": self.improvement_area,
            "expected_impact": self.expected_impact,
            "affected_role": self.affected_role,
            "expected_access": self.expected_access,
            "workflow_name": self.workflow_name,
            "broken_step": self.broken_step,
            "integration_name": self.integration_name,
            "api_endpoint": self.api_endpoint,
            "additional_details": self.additional_details,
            "url": self.url,
            "device": self.device,
            "browser": self.browser,
            "assigned_team": None,
            "assigned_to": None,
            "assigned_to_name": None,
            "assigned_at": None,
            "hakim_analysis": {},
            "generated_prompt": None,
            "duplicate_of": None,
            "sla_deadline": None,
            "sla_status": None,
            "sla_warning_emitted": False,
            "feedback_requested": False,
            "feedback_response": None,
            "created_by": user_id,
            "created_by_name": user.get("full_name", ""),
            "created_by_role": user.get("role", ""),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "resolved_at": None,
        }


class IssueUpdate(BaseModel):
    current_behavior: Optional[str] = None
    expected_behavior: Optional[str] = None
    steps_to_reproduce: Optional[str] = None
    error_message: Optional[str] = None
    additional_details: Optional[str] = None
    impact: Optional[List[str]] = None
    related_to: Optional[List[str]] = None
    reproducibility: Optional[str] = None

    @field_validator("current_behavior", "expected_behavior")
    @classmethod
    def validate_behavior_fields(cls, v):
        if v is not None:
            if not v.strip():
                raise ValueError("هذا الحقل لا يمكن أن يكون فارغاً")
            if len(v.strip()) > 5000:
                raise ValueError("النص طويل جداً (الحد الأقصى 5000 حرف)")
            return v.strip()
        return v

    @field_validator("impact")
    @classmethod
    def validate_impact(cls, v):
        if v:
            valid = {e.value for e in ImpactType}
            for item in v:
                if item not in valid:
                    raise ValueError(f"نوع التأثير غير صالح: {item}")
        return v

    @field_validator("related_to")
    @classmethod
    def validate_related_to(cls, v):
        if v:
            valid = {e.value for e in RelatedTo}
            for item in v:
                if item not in valid:
                    raise ValueError(f"حقل تقني غير صالح: {item}")
        return v

    @field_validator("reproducibility")
    @classmethod
    def validate_reproducibility(cls, v):
        if v is not None:
            valid = {e.value for e in Reproducible}
            if v not in valid:
                raise ValueError(f"قيمة غير صالحة لقابلية إعادة الإنتاج: {v}")
        return v


class IssueComment(BaseModel):
    content: str
    comment_type: Optional[str] = "general"

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError("محتوى التعليق مطلوب")
        if len(v.strip()) > 5000:
            raise ValueError("التعليق طويل جداً (الحد الأقصى 5000 حرف)")
        return v.strip()

    @field_validator("comment_type")
    @classmethod
    def validate_comment_type(cls, v):
        valid = {e.value for e in CommentType}
        if v and v not in valid:
            raise ValueError(f"نوع التعليق غير صالح: {v}")
        return v or "general"


class StatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid = {e.value for e in IssueStatus}
        if v not in valid:
            raise ValueError(f"حالة غير صالحة: {v}")
        return v


class AssignIssue(BaseModel):
    assigned_team: str
    assigned_to: Optional[str] = None
    note: Optional[str] = None

    @field_validator("assigned_team")
    @classmethod
    def validate_team(cls, v):
        if v not in VALID_TEAMS:
            raise ValueError(f"فريق غير صالح: {v}")
        return v


class FeedbackResponse(BaseModel):
    resolved: bool
    comment: Optional[str] = None

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, v):
        if v is not None:
            if len(v.strip()) > 5000:
                raise ValueError("التعليق طويل جداً (الحد الأقصى 5000 حرف)")
            return v.strip()
        return v


class TitleUpdate(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError("العنوان مطلوب")
        if len(v.strip()) > 500:
            raise ValueError("العنوان طويل جداً (الحد الأقصى 500 حرف)")
        return v.strip()


class PriorityUpdate(BaseModel):
    priority: str

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        valid = {e.value for e in IssuePriority}
        if v not in valid:
            raise ValueError(f"أولوية غير صالحة: {v}")
        return v
