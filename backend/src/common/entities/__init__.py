"""Central Export of All Domain Entities in NASSAQ."""
from src.core.database.db import Base

from src.modules.users.entities import User, UserSession, RevokedToken
from src.modules.schools.entities import School, SchoolSettings, PhysicalClassroom
from src.modules.mfa.entities import MfaFactor, MfaRecoveryCode, MfaPendingChallenge, MfaEmailOtp, MfaWebauthnChallenge
from src.modules.academics.entities import Teacher, Student, Parent, Class, Subject, TeacherAssignment, TeacherClassAssignment, AcademicYear, AcademicTerm, GradeLevel, EducationalStage
from src.modules.scheduling.entities import TimeSlot, Timetable, TimetableRun, ScheduleSession, TimetableConstraint
from src.modules.sessions.entities import TeacherSession, SessionInteraction, SessionNote, SessionEventLog, SkillType, StudentSkill, LessonPlan
from src.modules.attendance.entities import Attendance
from src.modules.assessment.entities import Assessment, AssessmentSubmission
from src.modules.behaviour.entities import BehaviourRecord, BehaviourType
from src.modules.notifications.entities import Notification, NotificationPreference
from src.modules.audit.entities import AuditLog
from src.modules.platform.entities import ProductIssue, IssueComment, IssueDuplicateMap, IssueActivityLog, BulkActionHistory, IssueVersion, PlatformSettings, SystemSetting, Counter, LookupOption, GenericDocument
from src.modules.registration.entities import RegistrationRequest, ApprovalRequest, ApprovalEvent
from src.modules.ai.entities import HakimInsight, AIInsight, AIIntervention, PublicHakimRateCounter
from src.modules.communication.entities import Message
from src.modules.calendar.entities import Event, CalendarEvent, DailyTask
from src.modules.independent_teacher.entities import ParentInvitation, WorkspaceCollaborator, WorkspaceQuota
from src.modules.noor_import.entities import NoorImportHistory, NoorImportDraft
from src.modules.infrastructure.entities import RateLimitCounter

__all__ = ['User', 'UserSession', 'RevokedToken', 'School', 'SchoolSettings', 'PhysicalClassroom', 'MfaFactor', 'MfaRecoveryCode', 'MfaPendingChallenge', 'MfaEmailOtp', 'MfaWebauthnChallenge', 'Teacher', 'Student', 'Parent', 'Class', 'Subject', 'TeacherAssignment', 'TeacherClassAssignment', 'AcademicYear', 'AcademicTerm', 'GradeLevel', 'EducationalStage', 'TimeSlot', 'Timetable', 'TimetableRun', 'ScheduleSession', 'TimetableConstraint', 'TeacherSession', 'SessionInteraction', 'SessionNote', 'SessionEventLog', 'SkillType', 'StudentSkill', 'LessonPlan', 'Attendance', 'Assessment', 'AssessmentSubmission', 'BehaviourRecord', 'BehaviourType', 'Notification', 'NotificationPreference', 'AuditLog', 'ProductIssue', 'IssueComment', 'IssueDuplicateMap', 'IssueActivityLog', 'BulkActionHistory', 'IssueVersion', 'PlatformSettings', 'SystemSetting', 'Counter', 'LookupOption', 'GenericDocument', 'RegistrationRequest', 'ApprovalRequest', 'ApprovalEvent', 'HakimInsight', 'AIInsight', 'AIIntervention', 'PublicHakimRateCounter', 'Message', 'Event', 'CalendarEvent', 'DailyTask', 'ParentInvitation', 'WorkspaceCollaborator', 'WorkspaceQuota', 'NoorImportHistory', 'NoorImportDraft', 'RateLimitCounter']
