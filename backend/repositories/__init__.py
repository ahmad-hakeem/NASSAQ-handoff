import contextvars
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from db import get_pg_session
from repositories.base import BaseRepository, GenericCollectionRepository

from pg_models import (
    User, School, Teacher, Student, Parent, Class, Subject,
    TeacherAssignment, TimeSlot, Timetable, TimetableRun, ScheduleSession,
    Attendance, ProductIssue, IssueComment, IssueDuplicateMap, IssueActivityLog,
    BulkActionHistory, AuditLog, Notification, Assessment, AssessmentSubmission,
    BehaviourRecord, SchoolSettings, RegistrationRequest, TeacherSession,
    HakimInsight, PlatformSettings, AcademicYear, AcademicTerm, Counter,
    LookupOption, Message, ApprovalEvent, SkillType, StudentSkill,
    SessionInteraction, AIInsight, AIIntervention, SessionNote,
    SessionEventLog, TeacherClassAssignment, GradeLevel, EducationalStage,
    PhysicalClassroom, BehaviourType, TimetableConstraint, ApprovalRequest,
    Event, SystemSetting, GenericDocument,
)

_repos_session_var = contextvars.ContextVar('_repos_session', default=None)

_repo_class_cache = {}


def _repo(model_cls):
    if model_cls not in _repo_class_cache:
        _repo_class_cache[model_cls] = type(
            f"{model_cls.__name__}Repo", (BaseRepository,), {"model": model_cls}
        )
    return _repo_class_cache[model_cls]


_MODEL_REGISTRY = {
    'users': User,
    'schools': School,
    'teachers': Teacher,
    'students': Student,
    'parents': Parent,
    'classes': Class,
    'subjects': Subject,
    'teacher_assignments': TeacherAssignment,
    'time_slots': TimeSlot,
    'timetables': Timetable,
    'timetable_runs': TimetableRun,
    'schedule_sessions': ScheduleSession,
    'timetable_sessions': ScheduleSession,
    'attendance': Attendance,
    'product_issues': ProductIssue,
    'issue_comments': IssueComment,
    'issue_duplicates_map': IssueDuplicateMap,
    'issue_activity_log': IssueActivityLog,
    'bulk_action_history': BulkActionHistory,
    'audit_logs': AuditLog,
    'audit_log': AuditLog,
    'notifications': Notification,
    'assessments': Assessment,
    'assessment_submissions': AssessmentSubmission,
    'behaviour_records': BehaviourRecord,
    'behavior': BehaviourRecord,
    'school_settings': SchoolSettings,
    'registration_requests': RegistrationRequest,
    'teacher_sessions': TeacherSession,
    'hakim_insights': HakimInsight,
    'platform_settings': PlatformSettings,
    'academic_years': AcademicYear,
    'academic_terms': AcademicTerm,
    'counters': Counter,
    'lookup_options': LookupOption,
    'messages': Message,
    'approval_events': ApprovalEvent,
    'skill_types': SkillType,
    'skills_types': SkillType,
    'student_skills': StudentSkill,
    'session_interactions': SessionInteraction,
    'ai_insights': AIInsight,
    'ai_interventions': AIIntervention,
    'session_notes': SessionNote,
    'session_event_log': SessionEventLog,
    'teacher_class_assignments': TeacherClassAssignment,
    'grade_levels': GradeLevel,
    'educational_stages': EducationalStage,
    'physical_classrooms': PhysicalClassroom,
    'behaviour_types': BehaviourType,
    'timetable_constraints': TimetableConstraint,
    'timetable_hard_constraints': TimetableConstraint,
    'timetable_soft_constraints': TimetableConstraint,
    'approval_requests': ApprovalRequest,
    'events': Event,
    'system_settings': SystemSetting,
    'generic_documents': GenericDocument,
    'guardian_links': GenericDocument,
}


class Repos:
    def __init__(self, session: AsyncSession = None):
        self._direct_session = session

    @property
    def session(self):
        return self._direct_session or _repos_session_var.get(None)

    @property
    def session_factory(self):
        from db import async_session_factory
        return async_session_factory

    def set_session(self, session):
        _repos_session_var.set(session)

    def _get_session(self):
        return self.session

    def __getattr__(self, name):
        if name.startswith('_') or name in ('session', 'session_factory', 'set_session'):
            raise AttributeError(name)
        model = _MODEL_REGISTRY.get(name)
        if model is not None:
            if model is GenericDocument:
                return GenericCollectionRepository(self, name)
            return _repo(model)(self)
        return GenericCollectionRepository(self, name)


async def get_repos(session: AsyncSession = Depends(get_pg_session)) -> Repos:
    return Repos(session)
