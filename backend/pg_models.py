"""
NASSAQ PostgreSQL ORM Models
Backward-compatible shim re-exporting domain entities from their module packages.
"""
from src.core.database.db import Base
from src.common.entities import (
    User, UserSession, RevokedToken, School, SchoolSettings, PhysicalClassroom, MfaFactor, MfaRecoveryCode, MfaPendingChallenge, MfaEmailOtp, MfaWebauthnChallenge, Teacher, Student, Parent, Class, Subject, TeacherAssignment, TeacherClassAssignment, AcademicYear, AcademicTerm, GradeLevel, EducationalStage, TimeSlot, Timetable, TimetableRun, ScheduleSession, TimetableConstraint, TeacherSession, SessionInteraction, SessionNote, SessionEventLog, SkillType, StudentSkill, LessonPlan, Attendance, Assessment, AssessmentSubmission, BehaviourRecord, BehaviourType, Notification, NotificationPreference, AuditLog, ProductIssue, IssueComment, IssueDuplicateMap, IssueActivityLog, BulkActionHistory, IssueVersion, PlatformSettings, SystemSetting, Counter, LookupOption, GenericDocument, RegistrationRequest, ApprovalRequest, ApprovalEvent, HakimInsight, AIInsight, AIIntervention, PublicHakimRateCounter, Message, Event, CalendarEvent, DailyTask, ParentInvitation, WorkspaceCollaborator, WorkspaceQuota, NoorImportHistory, NoorImportDraft, BulkImportBatch, RateLimitCounter
)

__all__ = [
    'Base',
    'User', 'UserSession', 'RevokedToken', 'School', 'SchoolSettings', 'PhysicalClassroom', 'MfaFactor', 'MfaRecoveryCode', 'MfaPendingChallenge', 'MfaEmailOtp', 'MfaWebauthnChallenge', 'Teacher', 'Student', 'Parent', 'Class', 'Subject', 'TeacherAssignment', 'TeacherClassAssignment', 'AcademicYear', 'AcademicTerm', 'GradeLevel', 'EducationalStage', 'TimeSlot', 'Timetable', 'TimetableRun', 'ScheduleSession', 'TimetableConstraint', 'TeacherSession', 'SessionInteraction', 'SessionNote', 'SessionEventLog', 'SkillType', 'StudentSkill', 'LessonPlan', 'Attendance', 'Assessment', 'AssessmentSubmission', 'BehaviourRecord', 'BehaviourType', 'Notification', 'NotificationPreference', 'AuditLog', 'ProductIssue', 'IssueComment', 'IssueDuplicateMap', 'IssueActivityLog', 'BulkActionHistory', 'IssueVersion', 'PlatformSettings', 'SystemSetting', 'Counter', 'LookupOption', 'GenericDocument', 'RegistrationRequest', 'ApprovalRequest', 'ApprovalEvent', 'HakimInsight', 'AIInsight', 'AIIntervention', 'PublicHakimRateCounter', 'Message', 'Event', 'CalendarEvent', 'DailyTask', 'ParentInvitation', 'WorkspaceCollaborator', 'WorkspaceQuota', 'NoorImportHistory', 'NoorImportDraft', 'BulkImportBatch', 'RateLimitCounter'
]
