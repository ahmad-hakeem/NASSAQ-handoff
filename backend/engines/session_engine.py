"""
Teacher Session Engine - محرك إدارة الحصة
نَسَّق | NASSAQ

This engine handles the complete "Start Class" journey:
1. Session Creation & Validation
2. Attendance Management
3. Student Interaction Tracking
4. Behaviour & Participation Recording
5. Student Score System
6. Random Student Selection Algorithm
7. Session Analytics & Summary
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid
import random
import logging

from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_count, gd_delete_one, gd_delete_many

logger = logging.getLogger("nassaq.session_engine")

# Create router for session endpoints
session_router = APIRouter(prefix="/session", tags=["Teacher Session"])


# ============== ENUMS ==============

class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class SessionStatus(str, Enum):
    SCHEDULED = "scheduled"
    READY_TO_START = "ready_to_start"
    NOT_STARTED = "not_started"
    SESSION_OPENED = "session_opened"
    ATTENDANCE_IN_PROGRESS = "attendance_in_progress"
    ATTENDANCE_APPROVED = "attendance_approved"
    IN_PROGRESS = "in_progress"
    TEACHING_IN_PROGRESS = "teaching_in_progress"
    INTERACTION_RUNNING = "interaction_running"
    SESSION_REVIEW = "session_review"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"


class NoteType(str, Enum):
    STUDENT = "student"
    GROUP = "group"
    SESSION = "session"
    EDUCATIONAL = "educational"
    BEHAVIOURAL = "behavioural"
    FOLLOWUP = "followup"


class EventType(str, Enum):
    SESSION_OPENED = "session_opened"
    ATTENDANCE_CHANGED = "attendance_changed"
    ATTENDANCE_APPROVED = "attendance_approved"
    STUDENT_SELECTED = "student_selected"
    ANSWER_RECORDED = "answer_recorded"
    PARTICIPATION_RECORDED = "participation_recorded"
    BEHAVIOUR_RECORDED = "behaviour_recorded"
    SKILL_RECORDED = "skill_recorded"
    HOMEWORK_RECORDED = "homework_recorded"
    NOTE_ADDED = "note_added"
    SEATING_UPDATED = "seating_updated"
    MODE_CHANGED = "mode_changed"
    SESSION_ENDED = "session_ended"
    SESSION_REVIEW_OPENED = "session_review_opened"
    SESSION_SUMMARY_GENERATED = "session_summary_generated"
    SESSION_REPORT_EXPORTED = "session_report_exported"
    AI_INSIGHTS_GENERATED = "ai_insights_generated"
    PARENT_NOTIFICATION_SENT = "parent_notification_sent"


class InteractionType(str, Enum):
    QUESTION = "question"
    PARTICIPATION = "participation"
    BEHAVIOUR = "behaviour"


class AnswerResult(str, Enum):
    CORRECT = "correct"
    WRONG = "wrong"
    NO_ANSWER = "no_answer"


class ParticipationType(str, Enum):
    ACTIVE = "active"          # مشاركة فعالة
    INITIATIVE = "initiative"  # طالب مبادر
    INACTIVE = "inactive"      # عدم التفاعل
    REFUSED = "refused"        # رفض التفاعل


class BehaviourCategory(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    SKILL = "skill"


class StudentLevel(str, Enum):
    NEEDS_ATTENTION = "needs_attention"  # 0-19
    ACCEPTABLE = "acceptable"            # 20-39
    GOOD = "good"                        # 40-59
    EXCELLENT = "excellent"              # 60-79
    STAR = "star"                        # 80+


# ============== PYDANTIC MODELS ==============

class SessionStartRequest(BaseModel):
    """Request to start a new class session"""
    schedule_session_id: str  # ID from schedule_sessions table
    teacher_id: str
    class_id: str
    subject_id: str
    

class SessionStartResponse(BaseModel):
    """Response after starting a session"""
    session_record_id: str
    session_status: SessionStatus
    start_time: str
    class_name: str
    subject_name: str
    teacher_name: str
    student_count: int
    message: str


class AttendanceUpdateRequest(BaseModel):
    """Request to update student attendance"""
    student_id: str
    status: AttendanceStatus


class AttendanceBulkRequest(BaseModel):
    """Request to update multiple students attendance"""
    attendance_records: List[AttendanceUpdateRequest]


class AttendanceApproveRequest(BaseModel):
    """Request to approve and finalize attendance"""
    session_record_id: str


class StudentInteractionRequest(BaseModel):
    """Request to record student interaction"""
    student_id: str
    interaction_type: InteractionType
    result: Optional[AnswerResult] = None
    participation_type: Optional[ParticipationType] = None
    behaviour_category: Optional[BehaviourCategory] = None
    behaviour_type: Optional[str] = None  # e.g., "respect", "disruption"
    behaviour_details: Optional[str] = None
    notes: Optional[str] = None


class SessionEndRequest(BaseModel):
    """Request to end a session"""
    session_record_id: str
    notes: Optional[str] = None


class StudentScoreResponse(BaseModel):
    """Student score information"""
    student_id: str
    student_name: str
    daily_score: int
    weekly_score: int
    monthly_score: int
    behaviour_score: int
    participation_score: int
    level: StudentLevel
    recent_achievements: List[str]


class SessionReviewPreview(BaseModel):
    """Review preview before ending session"""
    session_id: str
    duration_minutes: int
    attendance: Dict[str, Any]
    interactions: Dict[str, Any]
    behaviours: Dict[str, Any]
    skills: Dict[str, Any]
    notes: Dict[str, Any]
    warnings: List[str]
    top_participants: List[Dict[str, Any]]
    needs_attention: List[Dict[str, Any]]


class SessionSummaryResponse(BaseModel):
    """Session summary after ending"""
    session_record_id: str
    duration_minutes: int
    total_students: int
    present_count: int
    absent_count: int
    late_count: int
    excused_count: int
    attendance_rate: float
    questions_asked: int
    correct_answers: int
    wrong_answers: int
    participation_rate: float
    positive_behaviours: int
    negative_behaviours: int
    skills_recorded: int = 0
    evaluated_students: int = 0
    notes_sent: int = 0
    top_participants: List[Dict[str, Any]]
    needs_attention: List[Dict[str, Any]]
    # Task #486 — how many school-management recipients (principal +
    # sub-admin) actually received the end-of-session summary. The
    # frontend uses this to drive a truthful success toast: it claims
    # delivery to administration only when this value is > 0.
    management_notifications_sent: int = 0


# ============== SCORE RULES (defaults) ==============

DEFAULT_SCORE_RULES = {
    "correct_answer": 5,
    "no_answer_after_selection": -1,
    "active_participation": 2,
    "initiative": 2,
    "inactive": 0,
    "refused": -1,
    "respect": 2,
    "commitment": 2,
    "helping_others": 2,
    "special_skill": 3,
    "leadership": 3,
    "disruption": -2,
    "non_compliance": -2,
    "interruption": -1,
    "late_to_class": -2,
    "medium_violation": -4,
    "high_violation": -8,
    "present": 1,
    "absent_no_excuse": -3,
    "excused": 0,
    "late": -1,
    "three_correct_streak": 5,
    "no_negative_week": 10,
    "full_attendance_month": 15,
    "top_3_weekly": 10,
}

SCORE_RULES = DEFAULT_SCORE_RULES

DEFAULT_STUDENT_LEVELS = {
    "needs_attention": (0, 19),
    "acceptable": (20, 39),
    "good": (40, 59),
    "excellent": (60, 79),
    "star": (80, float('inf'))
}

STUDENT_LEVELS = DEFAULT_STUDENT_LEVELS


async def load_tenant_score_rules(db: Any, tenant_id: str) -> dict:
    """Load tenant-specific score rules, falling back to defaults"""
    try:
        settings = await gd_find_one(db.session, "tenant_settings", {"tenant_id": tenant_id, "setting_key": "score_rules"})
        if settings and isinstance(settings.get("value"), dict):
            merged = dict(DEFAULT_SCORE_RULES)
            merged.update(settings["value"])
            return merged
    except Exception as e:
        logger.warning("Failed to load tenant score rules for %s: %s", tenant_id, e)
    return DEFAULT_SCORE_RULES


async def load_tenant_student_levels(db: Any, tenant_id: str) -> dict:
    """Load tenant-specific student level thresholds, falling back to defaults."""
    try:
        settings = await gd_find_one(db.session, "tenant_settings", {"tenant_id": tenant_id, "setting_key": "student_levels"})
        if settings and isinstance(settings.get("value"), dict):
            return {
                k: tuple(v) if isinstance(v, list) else v
                for k, v in settings["value"].items()
            }
    except Exception as e:
        logger.warning("Failed to load tenant student levels for %s: %s", tenant_id, e)
    return DEFAULT_STUDENT_LEVELS


# ============== SESSION ENGINE CLASS ==============

class TeacherSessionEngine:
    """
    Main engine for managing teacher class sessions.
    All data operations go through the database.
    """
    
    def __init__(self, db):
        self.db = db
        self._tenant_rules_cache: Dict[str, dict] = {}
        self._tenant_levels_cache: Dict[str, dict] = {}

    @property
    def session(self):
        return self.db.session

    async def _get_score_rules(self, tenant_id: str) -> dict:
        if not tenant_id:
            return DEFAULT_SCORE_RULES
        if tenant_id not in self._tenant_rules_cache:
            self._tenant_rules_cache[tenant_id] = await load_tenant_score_rules(self.db, tenant_id)
        return self._tenant_rules_cache[tenant_id]

    async def _get_student_levels(self, tenant_id: str) -> dict:
        if not tenant_id:
            return DEFAULT_STUDENT_LEVELS
        if tenant_id not in self._tenant_levels_cache:
            self._tenant_levels_cache[tenant_id] = await load_tenant_student_levels(self.db, tenant_id)
        return self._tenant_levels_cache[tenant_id]

    async def _get_session_score_rules(self, session_id: str) -> dict:
        """Resolve tenant-aware score rules for a session, cached by tenant_id."""
        session_doc = await gd_find_one(self.session, "class_sessions", {"id": session_id})
        tid = (session_doc or {}).get("tenant_id") or (session_doc or {}).get("school_id") or ""
        return await self._get_score_rules(tid)

    # ---------- Session Management ----------
    
    ACTIVE_STATUSES = [
        SessionStatus.IN_PROGRESS.value,
        SessionStatus.SESSION_OPENED.value,
        SessionStatus.ATTENDANCE_IN_PROGRESS.value,
        SessionStatus.ATTENDANCE_APPROVED.value,
        SessionStatus.TEACHING_IN_PROGRESS.value,
        SessionStatus.INTERACTION_RUNNING.value,
        SessionStatus.SESSION_REVIEW.value,
    ]

    async def _log_event(
        self,
        session_id: str,
        event_type: str,
        actor_id: str,
        student_id: str = None,
        old_value: Any = None,
        new_value: Any = None,
        metadata: Dict = None
    ):
        now = datetime.now(timezone.utc)
        event = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "event_type": event_type,
            "actor_type": "teacher",
            "actor_id": actor_id,
            "student_id": student_id,
            "old_value": old_value,
            "new_value": new_value,
            "metadata": metadata or {},
            "timestamp": now.isoformat()
        }
        await gd_insert(self.session, "session_event_log", event)
        return event

    async def validate_session_start(self, teacher_id: str, schedule_session_id: str, force_new: bool = False) -> Dict[str, Any]:
        """
        Validate if a session can be started.
        Returns schedule_session dict with optional 'existing_active_session' key
        if there's already a running session to resume.
        If force_new=True, auto-complete any existing sessions and allow a fresh start.
        """
        schedule_session = await gd_find_one(self.session, "schedule_sessions", {"id": schedule_session_id})
        if not schedule_session:
            schedule_session = await gd_find_one(self.session, "timetable_sessions", {"id": schedule_session_id})

        if not schedule_session:
            schedule_session = {"id": schedule_session_id, "teacher_id": teacher_id}

        if schedule_session.get("teacher_id") and schedule_session.get("teacher_id") != teacher_id:
            raise HTTPException(status_code=403, detail="هذه الحصة ليست مخصصة لك")

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now = datetime.now(timezone.utc)

        active_sessions = await gd_find(self.session, "class_sessions", {
            "teacher_id": teacher_id,
            "status": {"$in": self.ACTIVE_STATUSES}
        })
        for active_session in active_sessions:
            should_complete = force_new
            if not should_complete:
                if active_session.get("date") != today:
                    should_complete = True
                elif active_session.get("schedule_session_id") != schedule_session_id:
                    should_complete = True
                else:
                    start_time = active_session.get("start_time") or active_session.get("created_at")
                    if start_time:
                        try:
                            if isinstance(start_time, str):
                                st = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                            else:
                                st = start_time
                            if st.tzinfo is None:
                                st = st.replace(tzinfo=timezone.utc)
                            if (now - st).total_seconds() > 7200:
                                should_complete = True
                        except Exception as e:
                            logger.debug("Could not parse session start_time: %s", e)

            if should_complete:
                await gd_update_one(self.session, "class_sessions",
                    {"id": active_session.get("id")},
                    {"status": SessionStatus.COMPLETED.value, "ended_at": now.isoformat()}
                )
            else:
                schedule_session["existing_active_session"] = active_session
                return schedule_session

        return schedule_session
    
    async def start_session(
        self, 
        teacher_id: str, 
        schedule_session_id: str,
        class_id: str,
        subject_id: str,
        force_new: bool = False
    ) -> Dict[str, Any]:
        """
        Start a new class session.
        If a session is already active, returns its info for resuming.
        Creates session record and initializes attendance drafts.
        """
        schedule_session = await self.validate_session_start(teacher_id, schedule_session_id, force_new=force_new)
        
        existing = schedule_session.pop("existing_active_session", None)
        if existing:
            existing_id = existing.get("id")
            ex_class_id = existing.get("class_id", class_id)
            ex_subject_id = existing.get("subject_id", subject_id)
            class_info = await gd_find_one(self.session, "classes", {"id": ex_class_id})
            subject_info = await gd_find_one(self.session, "subjects", {"id": ex_subject_id})
            students = await gd_find(self.session, "students", {"class_id": ex_class_id, "is_active": True}, limit=100)
            return {
                "session_record_id": existing_id,
                "session_status": existing.get("status"),
                "start_time": existing.get("start_time"),
                "class_name": class_info.get("name", "فصل") if class_info else "فصل",
                "subject_name": (subject_info.get("name_ar") or subject_info.get("name") or "مادة") if subject_info else "مادة",
                "teacher_name": existing.get("teacher_name", "معلم"),
                "student_count": len(students),
                "resumed": True,
                "message": "استكمال الحصة الجارية"
            }
        
        # Get teacher info
        teacher = await gd_find_one(self.session, "teachers", {"id": teacher_id})
        if not teacher:
            # Try to find from users
            user = await gd_find_one(self.session, "users", {"teacher_id": teacher_id})
            teacher = {"full_name": user.get("full_name") if user else "معلم"}
        
        # Get class info
        class_info = await gd_find_one(self.session, "classes", {"id": class_id})
        class_name = class_info.get("name", "فصل") if class_info else "فصل"
        
        # Get subject info
        subject = await gd_find_one(self.session, "subjects", {"id": subject_id})
        subject_name = subject.get("name_ar") or subject.get("name") or "مادة" if subject else "مادة"
        
        # Get students in this class
        students = await gd_find(self.session, "students", {"class_id": class_id, "is_active": True}, limit=100)
        
        # Create session record
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        
        school_id = teacher.get("school_id") or (class_info.get("tenant_id") if class_info else None)
        planned_start = schedule_session.get("start_time")
        planned_end = schedule_session.get("end_time")

        session_record = {
            "id": session_id,
            "schedule_session_id": schedule_session_id,
            "teacher_id": teacher_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "school_id": school_id,
            "date": today,
            "planned_start_time": planned_start,
            "planned_end_time": planned_end,
            "start_time": now.isoformat(),
            "end_time": None,
            "status": SessionStatus.ATTENDANCE_IN_PROGRESS.value,
            "attendance_approved": False,
            "interaction_mode": None,
            "created_by": teacher_id,
            "created_at": now.isoformat()
        }
        
        await gd_insert(self.session, "class_sessions", session_record)

        await self._log_event(
            session_id=session_id,
            event_type=EventType.SESSION_OPENED.value,
            actor_id=teacher_id,
            metadata={"class_id": class_id, "subject_id": subject_id, "student_count": len(students)}
        )
        
        # Create attendance draft records for all students (default: present)
        attendance_drafts = []
        for student in students:
            attendance_drafts.append({
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "student_id": student.get("id"),
                "status": AttendanceStatus.PRESENT.value,
                "is_draft": True,
                "recorded_by": teacher_id,
                "recorded_at": now.isoformat()
            })
        
        if attendance_drafts:
            await gd_insert_many(self.session, "session_attendance", attendance_drafts)
        
        try:
            from engines.portfolio_evidence_engine import PortfolioEvidenceEngine
            _pe = PortfolioEvidenceEngine(self)
            # Awaited inline (not detached as a task) so it shares the
            # request's DB session safely. SQLAlchemy AsyncSession is not
            # concurrency-safe; a background task using the same session
            # corrupts the transaction and breaks the final commit.
            await _pe.capture_evidence(
                teacher_id=teacher_id, school_id=school_id or "",
                evidence_type="lesson_plan",
                title_ar=f"خطة درس: {subject_name} - {class_name}",
                title_en=f"Lesson Plan: {subject_name} - {class_name}",
                description_ar=f"بدء حصة {subject_name} للفصل {class_name}",
                description_en=f"Started session for {subject_name} in {class_name}",
                source="auto", source_entity_type="class_session",
                source_entity_id=session_id,
                class_id=class_id, subject_id=subject_id,
                event_date=today,
            )
        except Exception as _pe_err:
            logger.debug("Portfolio evidence (lesson_plan) failed: %s", _pe_err)

        return {
            "session_record_id": session_id,
            "session_status": SessionStatus.IN_PROGRESS,
            "start_time": now.isoformat(),
            "class_name": class_name,
            "subject_name": subject_name,
            "teacher_name": teacher.get("full_name", "معلم"),
            "student_count": len(students),
            "message": "تم بدء الحصة بنجاح"
        }
    
    async def get_session_students(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all students for a session with their attendance status.
        Returns students grouped by gender.
        """
        # Get session
        session = await gd_find_one(self.session, "class_sessions", {"id": session_id})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
        
        # Get attendance records
        attendance_records = await gd_find(self.session, "session_attendance", {"session_id": session_id}, limit=200)
        
        attendance_map = {a["student_id"]: a for a in attendance_records}
        
        # Get students
        students = await gd_find(self.session, "students", {"class_id": session["class_id"], "is_active": True}, limit=200)
        
        # Enrich students with attendance
        result = []
        for student in students:
            attendance = attendance_map.get(student.get("id"), {})
            result.append({
                "id": student.get("id"),
                "full_name": student.get("full_name"),
                "student_code": student.get("student_id") or student.get("code"),
                "gender": student.get("gender", "male"),
                "avatar_url": student.get("avatar_url"),
                "attendance_status": attendance.get("status", AttendanceStatus.PRESENT.value),
                "attendance_id": attendance.get("id")
            })
        
        # Sort by gender (males first based on RTL layout)
        result.sort(key=lambda x: (0 if x["gender"] == "male" else 1, x["full_name"]))
        
        return result
    
    async def update_attendance(
        self, 
        session_id: str, 
        student_id: str, 
        status: AttendanceStatus,
        teacher_id: str
    ) -> Dict[str, Any]:
        """Update attendance status for a single student"""
        now = datetime.now(timezone.utc)
        
        result = await gd_update_one(self.session, "session_attendance",
            {"session_id": session_id, "student_id": student_id},
            {
                "status": status.value,
                "is_draft": True,
                "updated_by": teacher_id,
                "updated_at": now.isoformat()
            }
        )
        
        if result == 0:
            raise HTTPException(status_code=404, detail="سجل الحضور غير موجود")

        await self._log_event(
            session_id=session_id,
            event_type=EventType.ATTENDANCE_CHANGED.value,
            actor_id=teacher_id,
            student_id=student_id,
            new_value=status.value
        )
        
        return {"message": "تم تحديث الحضور", "student_id": student_id, "status": status.value}
    
    async def approve_attendance(self, session_id: str, teacher_id: str) -> Dict[str, Any]:
        """
        Approve and finalize attendance for a session.
        This triggers:
        1. Converting drafts to final records
        2. Updating attendance scores
        3. Sending notifications for absences
        """
        now = datetime.now(timezone.utc)
        
        # Get all attendance records
        records = await gd_find(self.session, "session_attendance", {"session_id": session_id}, limit=200)
        
        if not records:
            raise HTTPException(status_code=404, detail="لا توجد سجلات حضور")
        
        # Update all to final
        for rec in records:
            await gd_update_one(self.session, "session_attendance",
                {"id": rec["id"]},
                {
                    "is_draft": False,
                    "approved_by": teacher_id,
                    "approved_at": now.isoformat()
                }
            )
        
        await gd_update_one(self.session, "class_sessions",
            {"id": session_id},
            {
                "attendance_approved": True,
                "status": SessionStatus.TEACHING_IN_PROGRESS.value,
                "attendance_approved_at": now.isoformat()
            }
        )

        rules = await self._get_session_score_rules(session_id)

        for record in records:
            score_change = 0
            if record["status"] == AttendanceStatus.PRESENT.value:
                score_change = rules["present"]
            elif record["status"] == AttendanceStatus.ABSENT.value:
                score_change = rules["absent_no_excuse"]
            elif record["status"] == AttendanceStatus.LATE.value:
                score_change = rules["late"]
            elif record["status"] == AttendanceStatus.EXCUSED.value:
                score_change = rules["excused"]
            
            if score_change != 0:
                await self._update_student_score(
                    record["student_id"],
                    score_change,
                    "attendance",
                    f"حضور الحصة: {record['status']}"
                )
        
        # Count stats
        present = sum(1 for r in records if r["status"] == AttendanceStatus.PRESENT.value)
        absent = sum(1 for r in records if r["status"] == AttendanceStatus.ABSENT.value)
        late = sum(1 for r in records if r["status"] == AttendanceStatus.LATE.value)
        excused = sum(1 for r in records if r["status"] == AttendanceStatus.EXCUSED.value)

        # Sync approved attendance into the canonical `attendance` table so it
        # is visible in class-level absence logs / dashboards. The session
        # records remain the source of truth for the live lesson, but the
        # canonical table is what TeacherClassDetailPage and reports query.
        try:
            session = await gd_find_one(self.session, "class_sessions", {"id": session_id})
            if session and session.get("class_id") and session.get("school_id") and session.get("date"):
                from engines.attendance_engine import AttendanceEngine
                from dependencies import db as _db
                # Coerce session date into a datetime — the Attendance.date
                # column is DateTime(timezone=True) and rejects bare strings.
                _raw_date = session["date"]
                if isinstance(_raw_date, str):
                    try:
                        _att_date = datetime.fromisoformat(_raw_date.replace("Z", "+00:00"))
                    except ValueError:
                        _att_date = datetime.strptime(_raw_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                elif isinstance(_raw_date, datetime):
                    _att_date = _raw_date
                else:
                    # date object
                    _att_date = datetime(_raw_date.year, _raw_date.month, _raw_date.day, tzinfo=timezone.utc)
                if _att_date.tzinfo is None:
                    _att_date = _att_date.replace(tzinfo=timezone.utc)
                bulk = [
                    {
                        "student_id": r["student_id"],
                        "status": r["status"],
                        "session_id": session_id,
                    }
                    for r in records if r.get("student_id")
                ]
                if bulk:
                    # Run inside a SAVEPOINT so a failure here can be rolled
                    # back without aborting the outer request transaction
                    # (which still has _log_event and response work to do).
                    async with self.session.begin_nested():
                        att_engine = AttendanceEngine(_db)
                        await att_engine.record_bulk_attendance(
                            tenant_id=session["school_id"],
                            section_id=session["class_id"],
                            attendance_date=_att_date,
                            attendance_records=bulk,
                            recorded_by=teacher_id,
                        )
        except Exception as sync_err:  # pragma: no cover — never fail approval
            logging.getLogger("nassaq").warning(
                f"Failed to sync session {session_id} attendance into canonical table: {sync_err}"
            )

        await self._log_event(
            session_id=session_id,
            event_type=EventType.ATTENDANCE_APPROVED.value,
            actor_id=teacher_id,
            metadata={"present": present, "absent": absent, "late": late, "excused": excused}
        )
        
        return {
            "message": "تم اعتماد الحضور بنجاح",
            "total": len(records),
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "attendance_rate": round(present / len(records) * 100, 1) if records else 0
        }
    
    # ---------- Interaction Management ----------
    
    async def set_interaction_mode(self, session_id: str, mode: str, teacher_id: str = None) -> Dict[str, Any]:
        """Set the interaction mode for the session (homework, review, quiz)"""
        await gd_update_one(self.session, "class_sessions",
            {"id": session_id},
            {
                "interaction_mode": mode,
                "status": SessionStatus.INTERACTION_RUNNING.value
            }
        )
        if teacher_id:
            await self._log_event(
                session_id=session_id,
                event_type=EventType.MODE_CHANGED.value,
                actor_id=teacher_id,
                new_value=mode
            )
        return {"message": f"تم تحديد نمط التفاعل: {mode}"}
    
    async def select_random_student(self, session_id: str) -> Dict[str, Any]:
        """
        Select a random student using a fair algorithm.
        Prioritizes students who haven't been selected recently.
        """
        # Get session
        session = await gd_find_one(self.session, "class_sessions", {"id": session_id})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
        
        # Get present students only
        attendance = await gd_find(self.session, "session_attendance",
            {"session_id": session_id, "status": AttendanceStatus.PRESENT.value}, limit=200)
        
        if not attendance:
            raise HTTPException(status_code=400, detail="لا يوجد طلاب حاضرين")
        
        present_student_ids = [a["student_id"] for a in attendance]

        # Get interaction history for this session
        interactions = await gd_find(self.session, "session_interactions",
            {"session_id": session_id, "interaction_type": InteractionType.QUESTION.value}, limit=500)

        # Also count "selected but not yet answered" picks (so repeated random picks
        # without an answer still de-prioritise the same student)
        selection_events = await gd_find(self.session, "session_events",
            {"session_id": session_id, "event_type": EventType.STUDENT_SELECTED.value}, limit=500)

        # Count selections per student + remember last position (recency)
        selection_counts: Dict[str, int] = {}
        last_selection_order: Dict[str, int] = {}
        for i, interaction in enumerate(interactions):
            sid = interaction.get("student_id")
            if not sid:
                continue
            selection_counts[sid] = selection_counts.get(sid, 0) + 1
            last_selection_order[sid] = i
        # Offset selection events after interactions so they count as "more recent"
        offset = len(interactions)
        for j, ev in enumerate(selection_events):
            sid = ev.get("student_id")
            if not sid:
                continue
            selection_counts[sid] = selection_counts.get(sid, 0) + 1
            last_selection_order[sid] = offset + j

        # Shuffle first so equal weights tie-break randomly (otherwise stable sort
        # always picks the first students in roster order when no history exists)
        shuffled_ids = list(present_student_ids)
        random.shuffle(shuffled_ids)

        # Weight: fewer selections + older recency = lower weight = higher chance.
        # Add a small random jitter so identical weights still vary between calls.
        weights = []
        for sid in shuffled_ids:
            count = selection_counts.get(sid, 0)
            last_order = last_selection_order.get(sid, -1)
            jitter = random.random()  # 0..1 — breaks any remaining ties
            weight = count * 10 + (last_order + 1) * 0.5 + jitter
            weights.append((sid, weight))

        # Sort by weight (ascending). Use a wider pool when history is short so we
        # don't keep picking from a tiny set of "first" students.
        weights.sort(key=lambda x: x[1])
        n = len(weights)
        if sum(selection_counts.values()) < n:
            # Early in the session — give everyone a fair shot
            pool_size = n
        else:
            pool_size = max(n // 3, min(3, n))
        selection_pool = weights[:pool_size]

        # Random selection from pool
        selected_id = random.choice(selection_pool)[0]
        
        # Get student info
        student = await gd_find_one(self.session, "students", {"id": selected_id, "is_active": True})
        
        # Get participation count in this session
        participation_count = selection_counts.get(selected_id, 0)
        
        session = await gd_find_one(self.session, "class_sessions", {"id": session_id})
        if session:
            await self._log_event(
                session_id=session_id,
                event_type=EventType.STUDENT_SELECTED.value,
                actor_id=session.get("teacher_id", ""),
                student_id=selected_id,
                metadata={"participation_count": participation_count}
            )

        return {
            "student_id": selected_id,
            "full_name": student.get("full_name") if student else "طالب",
            "student_code": student.get("student_id") if student else "",
            "avatar_url": student.get("avatar_url") if student else None,
            "gender": student.get("gender", "male") if student else "male",
            "participation_count": participation_count
        }
    
    async def record_answer(
        self,
        session_id: str,
        student_id: str,
        result: AnswerResult,
        teacher_id: str
    ) -> Dict[str, Any]:
        """Record student answer (correct/wrong/no_answer)"""
        now = datetime.now(timezone.utc)
        
        # Create interaction record
        interaction = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "student_id": student_id,
            "type": InteractionType.QUESTION.value,
            "interaction_type": InteractionType.QUESTION.value,
            "answer_result": result.value,
            "recorded_by": teacher_id,
            "recorded_at": now.isoformat(),
            "timestamp": now.isoformat()
        }
        
        await gd_insert(self.session, "session_interactions", interaction)
        
        rules = await self._get_session_score_rules(session_id)
        score_change = 0
        if result == AnswerResult.CORRECT:
            score_change = rules["correct_answer"]

            streak = await self._check_answer_streak(session_id, student_id)
            if streak >= 3:
                score_change += rules["three_correct_streak"]

        elif result == AnswerResult.NO_ANSWER:
            score_change = rules["no_answer_after_selection"]
        
        if score_change != 0:
            await self._update_student_score(
                student_id,
                score_change,
                "answer",
                f"إجابة: {result.value}"
            )

        await self._log_event(
            session_id=session_id,
            event_type=EventType.ANSWER_RECORDED.value,
            actor_id=teacher_id,
            student_id=student_id,
            new_value=result.value,
            metadata={"score_change": score_change, "interaction_id": interaction["id"]}
        )
        
        return {
            "message": "تم تسجيل الإجابة",
            "result": result.value,
            "score_change": score_change
        }
    
    async def record_participation(
        self,
        session_id: str,
        student_id: str,
        participation_type: ParticipationType,
        teacher_id: str
    ) -> Dict[str, Any]:
        """Record student participation"""
        now = datetime.now(timezone.utc)
        
        # Create interaction record
        interaction = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "student_id": student_id,
            "type": InteractionType.PARTICIPATION.value,
            "interaction_type": InteractionType.PARTICIPATION.value,
            "participation_type": participation_type.value,
            "recorded_by": teacher_id,
            "recorded_at": now.isoformat(),
            "timestamp": now.isoformat()
        }
        
        await gd_insert(self.session, "session_interactions", interaction)
        
        rules = await self._get_session_score_rules(session_id)
        score_change = 0
        if participation_type == ParticipationType.ACTIVE:
            score_change = rules["active_participation"]
        elif participation_type == ParticipationType.INITIATIVE:
            score_change = rules["initiative"]
        elif participation_type == ParticipationType.REFUSED:
            score_change = rules.get("refused", -1)
        
        # Update student score
        if score_change != 0:
            await self._update_student_score(
                student_id,
                score_change,
                "participation",
                f"مشاركة: {participation_type.value}"
            )
        
        await self._log_event(
            session_id=session_id,
            event_type=EventType.PARTICIPATION_RECORDED.value,
            actor_id=teacher_id,
            student_id=student_id,
            new_value=participation_type.value,
            metadata={"score_change": score_change, "interaction_id": interaction["id"]}
        )

        return {
            "message": "تم تسجيل المشاركة",
            "type": participation_type.value,
            "score_change": score_change
        }
    
    async def record_behaviour(
        self,
        session_id: str,
        student_id: str,
        category: BehaviourCategory,
        behaviour_type: str,
        details: Optional[str],
        teacher_id: str
    ) -> Dict[str, Any]:
        """Record student behaviour (positive/negative/skill)"""
        now = datetime.now(timezone.utc)
        
        # Create interaction record
        interaction = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "student_id": student_id,
            "type": InteractionType.BEHAVIOUR.value,
            "interaction_type": InteractionType.BEHAVIOUR.value,
            "behaviour_category": category.value,
            "behaviour_type": behaviour_type,
            "behaviour_details": details,  # Only visible to admin
            "recorded_by": teacher_id,
            "recorded_at": now.isoformat(),
            "timestamp": now.isoformat(),
            "editable_until": (now + timedelta(hours=1)).isoformat()
        }
        
        await gd_insert(self.session, "session_interactions", interaction)
        
        rules = await self._get_session_score_rules(session_id)
        score_change = 0
        if category == BehaviourCategory.POSITIVE:
            score_change = rules.get(behaviour_type, 2)
        elif category == BehaviourCategory.NEGATIVE:
            score_change = rules.get(behaviour_type, -2)
        elif category == BehaviourCategory.SKILL:
            score_change = rules.get("special_skill", 3)
        
        # Update student score
        if score_change != 0:
            await self._update_student_score(
                student_id,
                score_change,
                "behaviour",
                f"سلوك ({category.value}): {behaviour_type}"
            )
        
        await self._log_event(
            session_id=session_id,
            event_type=EventType.BEHAVIOUR_RECORDED.value,
            actor_id=teacher_id,
            student_id=student_id,
            new_value=f"{category.value}:{behaviour_type}",
            metadata={"score_change": score_change, "details": details, "interaction_id": interaction["id"]}
        )

        return {
            "message": "تم تسجيل السلوك",
            "category": category.value,
            "type": behaviour_type,
            "score_change": score_change
        }
    
    # ---------- Homework Tracking ----------

    async def record_homework(
        self,
        session_id: str,
        student_id: str,
        status: str,
        teacher_id: str
    ) -> Dict[str, Any]:
        """Record homework status for a single student in a session."""
        if not student_id:
            raise HTTPException(status_code=400, detail="student_id مطلوب")
        if status not in ("done", "not_done"):
            raise HTTPException(status_code=400, detail="الحالة يجب أن تكون done أو not_done")
        att = await gd_find_one(self.session, "session_attendance", {"session_id": session_id, "student_id": student_id})
        if not att:
            raise HTTPException(status_code=400, detail="الطالب ليس في هذه الحصة")
        now = datetime.now(timezone.utc)
        existing = await gd_find_one(self.session, "session_homework", {"session_id": session_id, "student_id": student_id})
        if existing:
            await gd_update_one(self.session, "session_homework",
                {"session_id": session_id, "student_id": student_id},
                {
                    "status": status,
                    "recorded_by": teacher_id,
                    "recorded_at": now.isoformat()
                }
            )
        else:
            await gd_insert(self.session, "session_homework", {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "student_id": student_id,
                "status": status,
                "recorded_by": teacher_id,
                "recorded_at": now.isoformat()
            })
        await self._log_event(
            session_id=session_id,
            event_type=EventType.HOMEWORK_RECORDED.value,
            actor_id=teacher_id,
            student_id=student_id,
            new_value=status
        )
        return {"message": "تم تسجيل حالة الواجب", "student_id": student_id, "status": status}

    async def get_homework_statuses(self, session_id: str) -> Dict[str, str]:
        """Retrieve homework completion statuses for a session."""
        records = await gd_find(self.session, "session_homework", {"session_id": session_id}, limit=200)
        return {r["student_id"]: r["status"] for r in records}

    async def bulk_record_homework(
        self,
        session_id: str,
        records: list,
        teacher_id: str
    ) -> Dict[str, Any]:
        """Record homework completion status for multiple students in bulk."""
        if not records:
            return {"message": "لا توجد سجلات", "done": 0, "not_done": 0}
        for rec in records:
            if not rec.get("student_id") or rec.get("status") not in ("done", "not_done"):
                raise HTTPException(status_code=400, detail="بيانات غير صالحة: كل سجل يجب أن يحتوي student_id وstatus (done/not_done)")
        now = datetime.now(timezone.utc)
        for rec in records:
            existing = await gd_find_one(self.session, "session_homework", {"session_id": session_id, "student_id": rec["student_id"]})
            if existing:
                await gd_update_one(self.session, "session_homework",
                    {"session_id": session_id, "student_id": rec["student_id"]},
                    {
                        "status": rec["status"],
                        "recorded_by": teacher_id,
                        "recorded_at": now.isoformat()
                    }
                )
            else:
                await gd_insert(self.session, "session_homework", {
                    "id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "student_id": rec["student_id"],
                    "status": rec["status"],
                    "recorded_by": teacher_id,
                    "recorded_at": now.isoformat()
                })
        done = sum(1 for r in records if r["status"] == "done")
        not_done = sum(1 for r in records if r["status"] == "not_done")
        await self._log_event(
            session_id=session_id,
            event_type=EventType.HOMEWORK_RECORDED.value,
            actor_id=teacher_id,
            metadata={"done": done, "not_done": not_done, "total": len(records)}
        )
        return {"message": "تم حفظ حالات الواجب", "done": done, "not_done": not_done}

    # ---------- Session Review & End ----------

    async def get_review_preview(self, session_id: str, teacher_id: str) -> SessionReviewPreview:
        """Get session review data without ending the session (Section 7.5-7.8)"""
        now = datetime.now(timezone.utc)

        session = await gd_find_one(self.session, "class_sessions", {"id": session_id})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

        start_time = datetime.fromisoformat(session["start_time"].replace("Z", "+00:00"))
        duration = (now - start_time).total_seconds() / 60

        attendance = await gd_find(self.session, "session_attendance", {"session_id": session_id}, limit=200)

        present = sum(1 for a in attendance if a["status"] == AttendanceStatus.PRESENT.value)
        absent = sum(1 for a in attendance if a["status"] == AttendanceStatus.ABSENT.value)
        late = sum(1 for a in attendance if a["status"] == AttendanceStatus.LATE.value)
        excused = sum(1 for a in attendance if a["status"] == AttendanceStatus.EXCUSED.value)
        total = len(attendance)
        attendance_approved = session.get("attendance_approved", False)

        all_interactions_rv = await gd_find(self.session, "session_interactions", {"session_id": session_id}, limit=500)
        # Exclude reversed interactions so review preview reflects only active actions.
        interactions = [i for i in all_interactions_rv if not (i.get("data") or {}).get("reversed")]

        questions = [i for i in interactions if i.get("interaction_type") == InteractionType.QUESTION.value]
        correct = sum(1 for q in questions if q.get("answer_result") == AnswerResult.CORRECT.value)
        wrong = sum(1 for q in questions if q.get("answer_result") == AnswerResult.WRONG.value)

        participations = [i for i in interactions if i.get("interaction_type") == InteractionType.PARTICIPATION.value]
        participants = set(p["student_id"] for p in participations)
        participation_rate = len(participants) / present * 100 if present > 0 else 0

        behaviours = [i for i in interactions if i.get("interaction_type") == InteractionType.BEHAVIOUR.value]
        positive_behaviours = sum(1 for b in behaviours if b.get("behaviour_category") == BehaviourCategory.POSITIVE.value)
        negative_behaviours = sum(1 for b in behaviours if b.get("behaviour_category") == BehaviourCategory.NEGATIVE.value)

        # Count only non-reversed skill records.
        skills_docs = await gd_find(self.session, "student_skills", {"session_id": session_id})
        skills_docs = [d for d in skills_docs if not d.get("is_reversed")]
        skills_recorded = len(skills_docs)
        skills_students = list(set(d.get("student_id") for d in skills_docs))

        notes_count = await gd_count(self.session, "session_notes", {"session_id": session_id})
        sent_to_parents = await gd_count(self.session, "session_notes", {
            "session_id": session_id,
            "note_type": "parent"
        })
        # Teacher's private notes = everything except parent broadcasts
        teacher_notes = max(0, notes_count - sent_to_parents)

        tenant_id_scope = session.get("tenant_id") or session.get("school_id")
        student_interactions = {}
        for i in interactions:
            sid = i["student_id"]
            if sid not in student_interactions:
                student_interactions[sid] = {"correct": 0, "participation": 0}
            # Only count correct answers from QUESTION-type interactions (not behaviour/skill side-effects)
            if i.get("interaction_type") == InteractionType.QUESTION.value and i.get("answer_result") == AnswerResult.CORRECT.value:
                student_interactions[sid]["correct"] += 1
            if i.get("interaction_type") == InteractionType.PARTICIPATION.value:
                student_interactions[sid]["participation"] += 1

        # Stable sort: score desc, then correct desc, then participation desc, then sid asc
        sorted_students = sorted(
            student_interactions.items(),
            key=lambda x: (-(x[1]["correct"] * 2 + x[1]["participation"]), -x[1]["correct"], -x[1]["participation"], x[0])
        )

        top_participants = []
        for sid, st in sorted_students[:3]:
            score = st["correct"] * 2 + st["participation"]
            if score <= 0:
                # Skip students with no positive activity — they aren't truly "top"
                continue
            student_filter = {"id": sid, "is_active": True}
            if tenant_id_scope:
                student_filter["tenant_id"] = tenant_id_scope
            student = await gd_find_one(self.session, "students", student_filter)
            if student:
                top_participants.append({
                    "student_id": sid,
                    "name": student.get("full_name"),
                    "correct_answers": st["correct"],
                    "participations": st["participation"]
                })

        needs_attention = []
        interacted_ids = set(i["student_id"] for i in interactions)
        present_ids = [a["student_id"] for a in attendance if a["status"] == AttendanceStatus.PRESENT.value]
        for sid in present_ids:
            if sid not in interacted_ids:
                student_filter = {"id": sid, "is_active": True}
                if tenant_id_scope:
                    student_filter["tenant_id"] = tenant_id_scope
                student = await gd_find_one(self.session, "students", student_filter)
                if student:
                    needs_attention.append({
                        "student_id": sid,
                        "name": student.get("full_name"),
                        "reason": "لم يشارك في الحصة"
                    })
        neg_students = {}
        for b in behaviours:
            if b.get("behaviour_category") == BehaviourCategory.NEGATIVE.value:
                sid = b["student_id"]
                neg_students[sid] = neg_students.get(sid, 0) + 1
        for sid, count in neg_students.items():
            if count >= 2:
                student = await gd_find_one(self.session, "students", {"id": sid, "is_active": True})
                if student and not any(n["student_id"] == sid for n in needs_attention):
                    needs_attention.append({
                        "student_id": sid,
                        "name": student.get("full_name"),
                        "reason": f"سلوكيات سلبية متكررة ({count})"
                    })

        warnings = []
        if not attendance_approved:
            warnings.append("لم يتم اعتماد الحضور")
        no_status = sum(1 for a in attendance if not a.get("status"))
        if no_status > 0:
            warnings.append(f"يوجد {no_status} طالب لم يتم تسجيل حالتهم")
        if len(participations) == 0:
            warnings.append("لا توجد مشاركات مسجلة")
        if notes_count == 0:
            warnings.append("لا توجد ملاحظات للحصة")

        try:
            await self._log_event(
                session_id=session_id,
                event_type=EventType.SESSION_REVIEW_OPENED.value,
                actor_id=teacher_id,
                metadata={"warnings_count": len(warnings)}
            )
        except Exception as e:
            logger.debug("Failed to log session review event: %s", e)

        return SessionReviewPreview(
            session_id=session_id,
            duration_minutes=round(duration),
            attendance={
                "total": total,
                "present": present,
                "absent": absent,
                "late": late,
                "excused": excused,
                "rate": round(present / total * 100, 1) if total > 0 else 0,
                "approved": attendance_approved,
            },
            interactions={
                "total_participations": len(participations),
                "participating_students": len(participants),
                "evaluated_students": len(skills_students),
                "questions_asked": len(questions),
                "correct_answers": correct,
                "wrong_answers": wrong,
                "participation_rate": round(participation_rate, 1),
            },
            behaviours={
                "positive": positive_behaviours,
                "negative": negative_behaviours,
                "total": positive_behaviours + negative_behaviours,
            },
            skills={
                "recorded": skills_recorded,
                "students_count": len(skills_students),
            },
            notes={
                "total": notes_count,
                "teacher_notes": teacher_notes,
                "sent_to_parents": sent_to_parents,
            },
            warnings=warnings,
            top_participants=top_participants,
            needs_attention=needs_attention,
        )

    async def end_session(self, session_id: str, teacher_id: str, closing_note: str = None) -> SessionSummaryResponse:
        """
        End the session and generate summary.
        Full pipeline: validate → stats → update session → student profiles → analytics → AI insights → notifications → event log
        """
        now = datetime.now(timezone.utc)
        
        session = await gd_find_one(self.session, "class_sessions", {"id": session_id})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

        session_teacher = session.get("teacher_id")
        if session_teacher and session_teacher != teacher_id:
            user_record = await gd_find_one(self.session, "users", {"id": teacher_id})
            actual_teacher_id = user_record.get("teacher_id") if user_record else None
            if session_teacher != actual_teacher_id:
                raise HTTPException(status_code=403, detail="لا يمكنك إنهاء حصة لست مسؤولاً عنها")

        if session.get("status") == SessionStatus.COMPLETED.value:
            return await self._get_completed_session_summary(session, session_id, now)

        attendance_approved = session.get("attendance_approved", False)
        attendance_records = await gd_find(self.session, "session_attendance", {"session_id": session_id}, limit=200)
        if not attendance_approved and len(attendance_records) == 0:
            raise HTTPException(status_code=400, detail="لا يمكن إنهاء الحصة قبل تسجيل الحضور واعتماده")

        start_time = datetime.fromisoformat(session["start_time"].replace("Z", "+00:00"))
        duration = (now - start_time).total_seconds() / 60
        
        attendance = attendance_records
        present = sum(1 for a in attendance if a["status"] == AttendanceStatus.PRESENT.value)
        absent = sum(1 for a in attendance if a["status"] == AttendanceStatus.ABSENT.value)
        late = sum(1 for a in attendance if a["status"] == AttendanceStatus.LATE.value)
        excused = sum(1 for a in attendance if a["status"] == AttendanceStatus.EXCUSED.value)
        total = len(attendance)
        
        all_interactions_es = await gd_find(self.session, "session_interactions", {"session_id": session_id}, limit=500)
        # Exclude reversed interactions so end-session summary reflects only active actions.
        interactions = [i for i in all_interactions_es if not (i.get("data") or {}).get("reversed")]
        
        questions = [i for i in interactions if i.get("interaction_type") == InteractionType.QUESTION.value]
        correct = sum(1 for q in questions if q.get("answer_result") == AnswerResult.CORRECT.value)
        wrong = sum(1 for q in questions if q.get("answer_result") == AnswerResult.WRONG.value)
        
        participations = [i for i in interactions if i.get("interaction_type") == InteractionType.PARTICIPATION.value]
        participants = set(p["student_id"] for p in participations)
        participation_rate = len(participants) / present * 100 if present > 0 else 0
        
        behaviours = [i for i in interactions if i.get("interaction_type") == InteractionType.BEHAVIOUR.value]
        positive_behaviours = sum(1 for b in behaviours if b.get("behaviour_category") == BehaviourCategory.POSITIVE.value)
        negative_behaviours = sum(1 for b in behaviours if b.get("behaviour_category") == BehaviourCategory.NEGATIVE.value)
        
        # Count only non-reversed skill records.
        skills_docs_end = await gd_find(self.session, "student_skills", {"session_id": session_id})
        skills_docs_end = [d for d in skills_docs_end if not d.get("is_reversed")]
        skills_recorded = len(skills_docs_end)
        evaluated_students_count = len(set(d.get("student_id") for d in skills_docs_end if d.get("student_id")))
        notes_sent_count = await gd_count(self.session, "session_notes", {
            "session_id": session_id,
            "note_type": "parent",
        })

        tenant_id_scope_end = session.get("tenant_id") or session.get("school_id")
        student_interactions = {}
        for i in interactions:
            sid = i["student_id"]
            if sid not in student_interactions:
                student_interactions[sid] = {"correct": 0, "participation": 0, "negative": 0, "positive": 0}
            if i.get("interaction_type") == InteractionType.QUESTION.value and i.get("answer_result") == AnswerResult.CORRECT.value:
                student_interactions[sid]["correct"] += 1
            if i.get("interaction_type") == InteractionType.PARTICIPATION.value:
                student_interactions[sid]["participation"] += 1
            if i.get("behaviour_category") == BehaviourCategory.NEGATIVE.value:
                student_interactions[sid]["negative"] += 1
            if i.get("behaviour_category") == BehaviourCategory.POSITIVE.value:
                student_interactions[sid]["positive"] += 1
        
        # Stable sort: score desc, then correct desc, then participation desc, then sid asc
        sorted_students = sorted(
            student_interactions.items(),
            key=lambda x: (-(x[1]["correct"] * 2 + x[1]["participation"]), -x[1]["correct"], -x[1]["participation"], x[0])
        )
        
        top_participants = []
        for sid, stats in sorted_students[:3]:
            score = stats["correct"] * 2 + stats["participation"]
            if score <= 0:
                continue
            student_filter = {"id": sid, "is_active": True}
            if tenant_id_scope_end:
                student_filter["tenant_id"] = tenant_id_scope_end
            student = await gd_find_one(self.session, "students", student_filter)
            if student:
                top_participants.append({
                    "student_id": sid,
                    "name": student.get("full_name"),
                    "correct_answers": stats["correct"],
                    "participations": stats["participation"]
                })
        
        needs_attention = []
        interacted_student_ids = set(i["student_id"] for i in interactions)
        present_ids = [a["student_id"] for a in attendance if a["status"] == AttendanceStatus.PRESENT.value]
        for sid in present_ids:
            if sid not in interacted_student_ids:
                student_filter = {"id": sid, "is_active": True}
                if tenant_id_scope_end:
                    student_filter["tenant_id"] = tenant_id_scope_end
                student = await gd_find_one(self.session, "students", student_filter)
                if student:
                    needs_attention.append({
                        "student_id": sid,
                        "name": student.get("full_name"),
                        "reason": "لم يشارك في الحصة"
                    })
        neg_students = {}
        for b in behaviours:
            if b.get("behaviour_category") == BehaviourCategory.NEGATIVE.value:
                sid = b["student_id"]
                neg_students[sid] = neg_students.get(sid, 0) + 1
        for sid, count in neg_students.items():
            if count >= 2:
                student_filter = {"id": sid, "is_active": True}
                if tenant_id_scope_end:
                    student_filter["tenant_id"] = tenant_id_scope_end
                student = await gd_find_one(self.session, "students", student_filter)
                if student and not any(n["student_id"] == sid for n in needs_attention):
                    needs_attention.append({
                        "student_id": sid,
                        "name": student.get("full_name"),
                        "reason": f"سلوكيات سلبية متكررة ({count})"
                    })

        attendance_rate = round(present / total * 100, 1) if total > 0 else 0
        engagement_rate = round(participation_rate, 1)

        session_update = {
            "status": SessionStatus.COMPLETED.value,
            "end_time": now.isoformat(),
            "duration_minutes": round(duration),
            "summary": {
                "total_students": total,
                "present": present,
                "absent": absent,
                "late": late,
                "excused": excused,
                "attendance_rate": attendance_rate,
                "questions_asked": len(questions),
                "correct_answers": correct,
                "wrong_answers": wrong,
                "participation_rate": engagement_rate,
                "positive_behaviours": positive_behaviours,
                "negative_behaviours": negative_behaviours,
                "skills_recorded": skills_recorded,
                "top_participants": [tp["student_id"] for tp in top_participants],
                "needs_attention": [na["student_id"] for na in needs_attention],
            }
        }
        if closing_note:
            session_update["closing_note"] = closing_note

        # Task #863 — commit the session's accumulated live scores into the
        # persistent records the school + parent student profiles read. This
        # runs BEFORE the session is marked COMPLETED on purpose: a re-ended
        # COMPLETED session short-circuits to the cached summary and never
        # retries the commit, so committing first keeps a failed end fully
        # retryable. Idempotent (deterministic ids) so the retry never
        # duplicates. Blocking: if scores can't be persisted we must NOT report
        # a successful end — otherwise the report shows points the student /
        # parent profiles never received.
        try:
            await self.commit_session_scores(session_id)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Session score commit failed for session {session_id}: {e}")
            raise HTTPException(status_code=500, detail="تعذّر حفظ درجات الحصة")

        await gd_update_one(self.session, "class_sessions", {"id": session_id}, session_update)

        if closing_note:
            await gd_insert(self.session, "session_notes", {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "teacher_id": teacher_id,
                "note_type": "session",
                "text": closing_note,
                "is_closing_note": True,
                "created_at": now.isoformat(),
            })

        school_id = session.get("school_id", "")
        class_id = session.get("class_id", "")
        subject_id = session.get("subject_id", "")

        try:
            await self._update_student_profiles_after_session(
                session_id, school_id, attendance, interactions, student_interactions, now
            )
        except Exception as e:
            logger.error(f"Student profile update failed for session {session_id}: {e}")

        try:
            await self._trigger_session_analytics(
                session_id, school_id, class_id, subject_id, teacher_id,
                attendance_rate, engagement_rate, positive_behaviours, negative_behaviours,
                skills_recorded, total, present, now
            )
        except Exception as e:
            logger.error(f"Analytics trigger failed for session {session_id}: {e}")

        try:
            await self._generate_ai_session_insights(
                session_id, school_id, class_id, subject_id, teacher_id,
                top_participants, needs_attention, attendance_rate, engagement_rate, now
            )
        except Exception as e:
            logger.error(f"AI insights generation failed for session {session_id}: {e}")

        try:
            await self._send_smart_end_session_notifications(
                session_id, school_id, attendance, neg_students, student_interactions, now
            )
        except Exception as e:
            logger.error(f"Smart notifications failed for session {session_id}: {e}")

        # Task #486 — deliver the end-of-session summary to school management
        # (school_principal first, then school_sub_admin) of the session's
        # tenant. tenant_id is taken from the session row, never the caller,
        # so cross-tenant delivery is impossible. IT workspaces resolve to
        # an empty cohort and the call is a no-op there. The returned count
        # is propagated to the response so the FE toast can be truthful
        # about whether administration actually received the summary.
        management_sent = 0
        try:
            management_sent = await self._send_management_session_summary(
                session_id=session_id,
                tenant_id=session.get("tenant_id") or session.get("school_id") or "",
                subject_id=subject_id,
                class_id=class_id,
                duration_minutes=round(duration),
                present=present,
                absent=absent,
                total=total,
                attendance_rate=attendance_rate,
                questions_count=len(questions),
                correct=correct,
                engagement_rate=engagement_rate,
                now=now,
            )
        except Exception as e:
            logger.error(f"Management session summary failed for session {session_id}: {e}")
            management_sent = 0

        await self._log_event(
            session_id=session_id,
            event_type=EventType.SESSION_ENDED.value,
            actor_id=teacher_id,
            metadata={
                "duration_minutes": round(duration),
                "total_students": total,
                "present": present,
                "questions_asked": len(questions),
                "needs_attention_count": len(needs_attention),
                "attendance_rate": attendance_rate,
                "engagement_rate": engagement_rate,
            }
        )

        await self._log_event(
            session_id=session_id,
            event_type=EventType.SESSION_SUMMARY_GENERATED.value,
            actor_id=teacher_id,
            metadata={"summary_generated": True}
        )

        try:
            from engines.portfolio_evidence_engine import PortfolioEvidenceEngine
            _pe = PortfolioEvidenceEngine(self)
            _session_date = session.get("date", "")
            # Awaited inline; see note in start_session.
            if len(interactions) >= 5:
                await _pe.capture_evidence(
                    teacher_id=teacher_id, school_id=school_id,
                    evidence_type="applied_lesson_report",
                    title_ar=f"تقرير درس مطبق: {_session_date}",
                    title_en=f"Applied Lesson Report: {_session_date}",
                    description_ar=f"حصة مكتملة - {len(interactions)} تفاعل، حضور {attendance_rate}%",
                    description_en=f"Completed session - {len(interactions)} interactions, {attendance_rate}% attendance",
                    source="auto", source_entity_type="class_session",
                    source_entity_id=session_id,
                    class_id=class_id, subject_id=subject_id,
                    metadata={"interactions": len(interactions), "attendance_rate": attendance_rate,
                              "duration": round(duration)},
                    event_date=_session_date,
                )
            if total > 0:
                await _pe.capture_evidence(
                    teacher_id=teacher_id, school_id=school_id,
                    evidence_type="attendance_record",
                    title_ar=f"سجل حضور الحصة: {_session_date}",
                    title_en=f"Session Attendance: {_session_date}",
                    description_ar=f"حضور {present}/{total} طالب",
                    description_en=f"Attendance {present}/{total} students",
                    source="auto", source_entity_type="class_session",
                    source_entity_id=session_id,
                    class_id=class_id, subject_id=subject_id,
                    metadata={"present": present, "absent": absent, "late": late, "total": total},
                    event_date=_session_date,
                )
        except Exception as _pe_err:
            logger.debug("Portfolio evidence (end_session) failed: %s", _pe_err)

        return SessionSummaryResponse(
            session_record_id=session_id,
            duration_minutes=round(duration),
            total_students=total,
            present_count=present,
            absent_count=absent,
            late_count=late,
            excused_count=excused,
            attendance_rate=attendance_rate,
            questions_asked=len(questions),
            correct_answers=correct,
            wrong_answers=wrong,
            participation_rate=engagement_rate,
            positive_behaviours=positive_behaviours,
            negative_behaviours=negative_behaviours,
            skills_recorded=skills_recorded,
            evaluated_students=evaluated_students_count,
            notes_sent=notes_sent_count,
            top_participants=top_participants,
            needs_attention=needs_attention,
            management_notifications_sent=management_sent,
        )

    async def _get_completed_session_summary(self, session, session_id, now):
        """Return summary for an already-completed session."""
        end_time_str = session.get("ended_at") or session.get("end_time") or now.isoformat()
        try:
            st = datetime.fromisoformat(session["start_time"].replace("Z", "+00:00"))
            et = datetime.fromisoformat(end_time_str.replace("Z", "+00:00")) if isinstance(end_time_str, str) else now
            completed_duration = (et - st).total_seconds() / 60
        except Exception as e:
            logger.debug("Could not compute session duration: %s", e)
            completed_duration = 0
        attendance = await gd_find(self.session, "session_attendance", {"session_id": session_id}, limit=200)
        present = sum(1 for a in attendance if a["status"] == AttendanceStatus.PRESENT.value)
        absent = sum(1 for a in attendance if a["status"] == AttendanceStatus.ABSENT.value)
        late = sum(1 for a in attendance if a["status"] == AttendanceStatus.LATE.value)
        excused = sum(1 for a in attendance if a["status"] == AttendanceStatus.EXCUSED.value)
        total = len(attendance)
        interactions = await gd_find(self.session, "session_interactions", {"session_id": session_id}, limit=500)
        questions = [i for i in interactions if i.get("interaction_type") == InteractionType.QUESTION.value]
        correct = sum(1 for q in questions if q.get("answer_result") == AnswerResult.CORRECT.value)
        participations = [i for i in interactions if i.get("interaction_type") == InteractionType.PARTICIPATION.value]
        participants_set = set(p["student_id"] for p in participations)
        behaviours = [i for i in interactions if i.get("interaction_type") == InteractionType.BEHAVIOUR.value]
        positive_b = sum(1 for b in behaviours if b.get("behaviour_category") == BehaviourCategory.POSITIVE.value)
        negative_b = sum(1 for b in behaviours if b.get("behaviour_category") == BehaviourCategory.NEGATIVE.value)
        skills_count = await gd_count(self.session, "student_skills", {"session_id": session_id})
        skills_docs_c = await gd_find(self.session, "student_skills", {"session_id": session_id})
        evaluated_students_c = len(set(d.get("student_id") for d in skills_docs_c if d.get("student_id")))
        notes_sent_c = await gd_count(self.session, "session_notes", {
            "session_id": session_id,
            "note_type": "parent",
        })

        # Rehydrate top_participants and needs_attention for completed sessions
        tenant_id_scope_c = session.get("tenant_id") or session.get("school_id")
        student_stats_c = {}
        for i in interactions:
            sid = i["student_id"]
            if sid not in student_stats_c:
                student_stats_c[sid] = {"correct": 0, "participation": 0}
            if i.get("interaction_type") == InteractionType.QUESTION.value and i.get("answer_result") == AnswerResult.CORRECT.value:
                student_stats_c[sid]["correct"] += 1
            if i.get("interaction_type") == InteractionType.PARTICIPATION.value:
                student_stats_c[sid]["participation"] += 1
        sorted_c = sorted(
            student_stats_c.items(),
            key=lambda x: (-(x[1]["correct"] * 2 + x[1]["participation"]), -x[1]["correct"], -x[1]["participation"], x[0])
        )
        top_participants_c = []
        for sid, st in sorted_c[:3]:
            if st["correct"] * 2 + st["participation"] <= 0:
                continue
            sf = {"id": sid, "is_active": True}
            if tenant_id_scope_c:
                sf["tenant_id"] = tenant_id_scope_c
            stu = await gd_find_one(self.session, "students", sf)
            if stu:
                top_participants_c.append({
                    "student_id": sid,
                    "name": stu.get("full_name"),
                    "correct_answers": st["correct"],
                    "participations": st["participation"],
                })
        needs_attention_c = []
        interacted_c = set(i["student_id"] for i in interactions)
        for sid in [a["student_id"] for a in attendance if a["status"] == AttendanceStatus.PRESENT.value]:
            if sid not in interacted_c:
                sf = {"id": sid, "is_active": True}
                if tenant_id_scope_c:
                    sf["tenant_id"] = tenant_id_scope_c
                stu = await gd_find_one(self.session, "students", sf)
                if stu:
                    needs_attention_c.append({
                        "student_id": sid,
                        "name": stu.get("full_name"),
                        "reason": "لم يشارك في الحصة",
                    })

        return SessionSummaryResponse(
            session_record_id=session_id,
            duration_minutes=round(completed_duration),
            total_students=total,
            present_count=present,
            absent_count=absent,
            late_count=late,
            excused_count=excused,
            attendance_rate=round(present / total * 100, 1) if total > 0 else 0,
            questions_asked=len(questions),
            correct_answers=correct,
            wrong_answers=len(questions) - correct,
            participation_rate=round(len(participants_set) / present * 100, 1) if present > 0 else 0,
            positive_behaviours=positive_b,
            negative_behaviours=negative_b,
            skills_recorded=skills_count,
            evaluated_students=evaluated_students_c,
            notes_sent=notes_sent_c,
            top_participants=top_participants_c,
            needs_attention=needs_attention_c,
        )

    async def _update_student_profiles_after_session(self, session_id, school_id, attendance, interactions, student_interactions, now):
        """Update student profiles with session aggregates."""
        today_str = now.strftime("%Y-%m-%d")
        all_student_ids = list(set(
            [a["student_id"] for a in attendance] +
            list(student_interactions.keys())
        ))
        
        present_set = set(a["student_id"] for a in attendance if a["status"] == AttendanceStatus.PRESENT.value)
        
        for sid in all_student_ids:
            update_fields = {
                "last_session_date": today_str,
                "updated_at": now.isoformat(),
            }
            inc_fields = {}
            
            if sid in present_set:
                inc_fields["total_sessions_attended"] = 1
            
            si = student_interactions.get(sid, {})
            total_participations = si.get("participation", 0) + si.get("correct", 0)
            if total_participations > 0:
                inc_fields["total_participations"] = total_participations
            
            pos = si.get("positive", 0)
            neg = si.get("negative", 0)
            if pos > 0 or neg > 0:
                inc_fields["behavior_positive_count"] = pos
                inc_fields["behavior_negative_count"] = neg
            
            engagement = min(100, total_participations * 10 + pos * 5)
            update_fields["engagement_score"] = engagement
            
            if inc_fields:
                existing_student = await gd_find_one(self.session, "students", {"id": sid, "school_id": school_id, "is_active": True})
                if existing_student:
                    for field, inc_val in inc_fields.items():
                        update_fields[field] = existing_student.get(field, 0) + inc_val
            
            await gd_update_one(self.session, "students", {"id": sid, "school_id": school_id}, update_fields)

    # ==================================================================
    # Live-session scoring bridge (Task #863)
    # ------------------------------------------------------------------
    # One backend-owned pipeline: in-session interactions are the single
    # source of truth. The same aggregation feeds (a) the in-session
    # Follow-up Report ("كشف المتابعة") while the class is live, and
    # (b) the idempotent end-of-session commit into the persistent
    # student-record collections the school + parent profiles read.
    # ==================================================================

    # Canonical coursework buckets derived from live interactions.
    _CW_PARTICIPATION = "participation"
    _CW_HOMEWORK = "homework"
    _CW_PERFORMANCE = "performance_task"

    # How to match a class grade_column to a derived bucket. A column is a
    # match when it is a coursework column and its Arabic name equals the
    # canonical name OR its English name contains the canonical token.
    _CW_COLUMN_MATCHERS = {
        _CW_PARTICIPATION: ("المشاركة", "participation"),
        _CW_HOMEWORK: ("الواجبات", "homework"),
        _CW_PERFORMANCE: ("المهام الأدائية", "performance"),
    }

    # Default coursework/exam columns, mirrors the /class/{id}/grade-columns
    # route so the UUIDs the Follow-up Report keys on stay stable whether
    # they are first created here or by that route.
    _DEFAULT_GRADE_COLUMNS = [
        {"name": "المشاركة", "name_en": "Participation", "column_type": "coursework", "max_grade": 5, "order": 1},
        {"name": "الواجبات", "name_en": "Homework", "column_type": "coursework", "max_grade": 5, "order": 2},
        {"name": "المهام الأدائية", "name_en": "Performance Tasks", "column_type": "coursework", "max_grade": 10, "order": 3},
        {"name": "اختبار قصير", "name_en": "Short Quiz", "column_type": "exams", "max_grade": 10, "order": 4},
        {"name": "اختبار نهاية الفترة", "name_en": "End of Period Exam", "column_type": "exams", "max_grade": 20, "order": 5},
    ]

    async def _ensure_grade_columns(self, class_id: str) -> list:
        """Return the class grade columns, creating the canonical defaults
        on first access (idempotent — only when none exist)."""
        columns = await gd_find(self.session, "grade_columns", {"class_id": class_id}, order_by="order", limit=50)
        if columns:
            return columns
        now_iso = datetime.now(timezone.utc).isoformat()
        defaults = []
        for d in self._DEFAULT_GRADE_COLUMNS:
            doc = dict(d)
            doc["id"] = str(uuid.uuid4())
            doc["class_id"] = class_id
            doc["visible"] = True
            doc["created_at"] = now_iso
            defaults.append(doc)
        await gd_insert_many(self.session, "grade_columns", defaults)
        return defaults

    async def _resolve_coursework_columns(self, class_id: str) -> Dict[str, dict]:
        """Map each derived coursework bucket to its class grade_column doc."""
        columns = await self._ensure_grade_columns(class_id)
        resolved: Dict[str, dict] = {}
        for col in columns:
            if (col.get("column_type") or "coursework") != "coursework":
                continue
            name_ar = (col.get("name") or "").strip()
            name_en = (col.get("name_en") or "").strip().lower()
            for bucket, (ar, en) in self._CW_COLUMN_MATCHERS.items():
                if bucket in resolved:
                    continue
                if name_ar == ar or (name_en and en in name_en):
                    resolved[bucket] = col
        return resolved

    async def compute_session_scores(self, session_id: str) -> Dict[str, Any]:
        """Aggregate a session's interactions into per-student coursework
        values, participation totals, and behaviour events. Pure read — no
        writes. The session row is the only source of tenant/class/subject
        scope; the caller never supplies them.
        """
        session = await gd_find_one(self.session, "class_sessions", {"id": session_id})
        if not session:
            return {"session": None, "students": {}}

        rules = await self._get_session_score_rules(session_id)
        interactions = await gd_find(self.session, "session_interactions", {"session_id": session_id}, limit=2000)
        homework_rows = await gd_find(self.session, "session_homework", {"session_id": session_id}, limit=2000)

        students: Dict[str, Dict[str, Any]] = {}

        def _bucket(sid: str) -> Dict[str, Any]:
            if sid not in students:
                students[sid] = {
                    "participation_points": 0,
                    "performance_points": 0,
                    "homework_done": None,  # None=no homework row, True/False otherwise
                    "behaviour_events": [],
                }
            return students[sid]

        for it in interactions:
            sid = it.get("student_id")
            if not sid:
                continue
            b = _bucket(sid)
            itype = it.get("interaction_type") or it.get("type")
            if itype == InteractionType.QUESTION.value:
                res = it.get("answer_result")
                if res == AnswerResult.CORRECT.value:
                    b["participation_points"] += int(rules.get("correct_answer", 5))
                elif res == AnswerResult.NO_ANSWER.value:
                    b["participation_points"] += int(rules.get("no_answer_after_selection", -1))
            elif itype == InteractionType.PARTICIPATION.value:
                ptype = it.get("participation_type")
                if ptype == ParticipationType.ACTIVE.value:
                    b["participation_points"] += int(rules.get("active_participation", 2))
                elif ptype == ParticipationType.INITIATIVE.value:
                    b["participation_points"] += int(rules.get("initiative", 2))
                elif ptype == ParticipationType.REFUSED.value:
                    b["participation_points"] += int(rules.get("refused", -1))
            elif itype == InteractionType.BEHAVIOUR.value:
                cat = it.get("behaviour_category")
                btype = it.get("behaviour_type") or ""
                if cat == BehaviourCategory.SKILL.value:
                    b["performance_points"] += int(rules.get("special_skill", 3))
                elif cat == BehaviourCategory.POSITIVE.value:
                    pts = int(rules.get(btype, 2)) if not str(btype).startswith("custom:") else 2
                    b["behaviour_events"].append({
                        "interaction_id": it.get("id"),
                        "category": cat,
                        "behaviour_type": btype,
                        "points": pts,
                        "details": it.get("behaviour_details"),
                        "recorded_by": it.get("recorded_by"),
                        "recorded_at": it.get("recorded_at") or it.get("timestamp"),
                    })
                elif cat == BehaviourCategory.NEGATIVE.value:
                    pts = int(rules.get(btype, -2)) if not str(btype).startswith("custom:") else -2
                    b["behaviour_events"].append({
                        "interaction_id": it.get("id"),
                        "category": cat,
                        "behaviour_type": btype,
                        "points": pts,
                        "details": it.get("behaviour_details"),
                        "recorded_by": it.get("recorded_by"),
                        "recorded_at": it.get("recorded_at") or it.get("timestamp"),
                    })

        for hw in homework_rows:
            sid = hw.get("student_id")
            if not sid:
                continue
            b = _bucket(sid)
            status = (hw.get("status") or "").lower()
            done = status in ("done", "completed", "submitted", "true") or hw.get("done") is True
            # A single not_done overrides; any done with no recorded not_done counts as done.
            if b["homework_done"] is None:
                b["homework_done"] = done
            else:
                b["homework_done"] = b["homework_done"] and done

        return {"session": session, "students": students}

    @staticmethod
    def _coursework_value(bucket: str, agg: Dict[str, Any], max_grade: float):
        """Translate an aggregated bucket into a 0..max_grade column value.
        Returns None when there is nothing to show (no phantom values)."""
        try:
            mg = float(max_grade)
        except (TypeError, ValueError):
            mg = 0.0
        if bucket == TeacherSessionEngine._CW_HOMEWORK:
            done = agg.get("homework_done")
            if done is None:
                return None
            return round(mg) if done else 0
        if bucket == TeacherSessionEngine._CW_PARTICIPATION:
            pts = agg.get("participation_points", 0)
        elif bucket == TeacherSessionEngine._CW_PERFORMANCE:
            pts = agg.get("performance_points", 0)
        else:
            return None
        if pts <= 0:
            return None
        return int(min(pts, mg))

    async def build_followup_hydration(self, session_id: str, manual_data: Dict[str, Any]) -> Dict[str, Any]:
        """Overlay session-derived coursework values onto the Follow-up
        Report data map (keyed student_id -> {column_uuid: value}). Manual
        teacher entries are never clobbered; exam columns are untouched."""
        computed = await self.compute_session_scores(session_id)
        session = computed.get("session")
        if not session:
            return manual_data or {}
        columns = await self._resolve_coursework_columns(session.get("class_id"))
        if not columns:
            return manual_data or {}

        merged: Dict[str, Any] = {sid: dict(vals) for sid, vals in (manual_data or {}).items()}
        for sid, agg in computed["students"].items():
            row = merged.get(sid, {})
            for bucket, col in columns.items():
                col_id = col.get("id")
                if not col_id:
                    continue
                # Respect manual override: only fill when teacher hasn't set it.
                if col_id in row and row[col_id] not in (None, ""):
                    continue
                value = self._coursework_value(bucket, agg, col.get("max_grade", 0))
                if value is not None:
                    row[col_id] = value
            if row:
                merged[sid] = row
        return merged

    async def commit_session_scores(self, session_id: str) -> Dict[str, int]:
        """Idempotently materialize the session's accumulated per-student
        scores into the persistent records the school + parent profiles
        read: student_grades (school grades), grades (parent grades),
        participation_records, and behaviour_records.

        Records are keyed deterministically on session + student (+ bucket /
        interaction) so repeated saves / re-ends update in place rather than
        inserting duplicates. Tenant/class/subject scope come only from the
        session row.
        """
        computed = await self.compute_session_scores(session_id)
        session = computed.get("session")
        if not session:
            return {"grades": 0, "participation": 0, "behaviour": 0}

        tenant_id = session.get("tenant_id") or session.get("school_id") or ""
        class_id = session.get("class_id")
        subject_id = session.get("subject_id")
        session_date = session.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        academic_year = session.get("academic_year") or ""
        now_iso = datetime.now(timezone.utc).isoformat()

        # Pull any manual coursework overrides so committed profile values
        # agree with what the teacher sees in the report.
        followup_lookup = {"class_id": class_id, "subject_id": subject_id} if class_id and subject_id else {"session_id": session_id}
        followup = await gd_find_one(self.session, "followup_records", followup_lookup)
        manual_data = (followup or {}).get("data", {}) if followup else {}

        columns = await self._resolve_coursework_columns(class_id) if class_id else {}

        subject_name = ""
        if subject_id:
            subj = await gd_find_one(self.session, "subjects", {"id": subject_id})
            if subj:
                subject_name = subj.get("name_ar") or subj.get("name") or subj.get("name_en") or ""

        async def _upsert(collection: str, doc_id: str, doc: dict):
            existing = await gd_find_one(self.session, collection, {"id": doc_id})
            if existing:
                await gd_update_one(self.session, collection, {"id": doc_id}, doc)
            else:
                await gd_insert(self.session, collection, {**doc, "id": doc_id})

        grades_written = 0
        participation_written = 0
        behaviour_written = 0

        for sid, agg in computed["students"].items():
            student = await gd_find_one(self.session, "students", {"id": sid})
            if not student:
                continue
            # Defensive scoping: only ever materialize scores for students that
            # belong to the session's tenant (and class, when the session is
            # class-bound). The session row — never the caller — is the source
            # of tenant_id/class_id, so this fails closed if an interaction ever
            # references a foreign-tenant or out-of-class student id.
            student_tenant = student.get("tenant_id") or student.get("school_id") or ""
            if tenant_id and student_tenant and student_tenant != tenant_id:
                continue
            if class_id and student.get("class_id") and student.get("class_id") != class_id:
                continue
            student_name = student.get("full_name", "")

            # ---- Coursework grades -> student_grades (school) + grades (parent) ----
            for bucket, col in columns.items():
                col_id = col.get("id")
                max_grade = col.get("max_grade", 0)
                # Effective value: manual override wins, else derived.
                override = manual_data.get(sid, {}).get(col_id) if isinstance(manual_data.get(sid), dict) else None
                if override not in (None, ""):
                    try:
                        value = float(override)
                    except (TypeError, ValueError):
                        value = None
                else:
                    value = self._coursework_value(bucket, agg, max_grade)
                if value is None:
                    continue
                try:
                    max_f = float(max_grade) or 0.0
                except (TypeError, ValueError):
                    max_f = 0.0
                percentage = round((value / max_f) * 100, 1) if max_f > 0 else 0
                # generic_documents has a GLOBAL primary key on ``id`` alone
                # (not (collection, id)), so deterministic ids MUST be unique
                # across every target collection or the second upsert collides.
                sg_id = f"sess:{session_id}:{sid}:{bucket}:sg"
                pg_id = f"sess:{session_id}:{sid}:{bucket}:pg"
                graded_at = now_iso
                # School-side store
                await _upsert("student_grades", sg_id, {
                    "tenant_id": tenant_id,
                    "school_id": tenant_id,
                    "student_id": sid,
                    "student_name": student_name,
                    "class_id": class_id,
                    "subject_id": subject_id,
                    "subject": subject_name,
                    "subject_name": subject_name,
                    "assessment_id": f"session:{session_id}:{bucket}",
                    "assessment_type": "coursework",
                    "column_id": col_id,
                    "score": value,
                    "max_score": max_f,
                    "percentage": percentage,
                    "is_passing": percentage >= 50,
                    "academic_year": academic_year,
                    "graded_at": graded_at,
                    "date": session_date,
                    "session_id": session_id,
                    "source": "live_session",
                    "updated_at": now_iso,
                })
                # Parent-side store
                await _upsert("grades", pg_id, {
                    "tenant_id": tenant_id,
                    "school_id": tenant_id,
                    "student_id": sid,
                    "student_name": student_name,
                    "class_id": class_id,
                    "subject_id": subject_id,
                    "subject": subject_name,
                    "subject_name": subject_name,
                    "assessment_type": "coursework",
                    "score": value,
                    "max_score": max_f,
                    "percentage": percentage,
                    "date": session_date,
                    "session_id": session_id,
                    "source": "live_session",
                    "visible_to_parent": True,
                    "updated_at": now_iso,
                })
                grades_written += 1

            # ---- Participation -> participation_records ----
            part_pts = agg.get("participation_points", 0)
            if part_pts > 0:
                part_id = f"sess:{session_id}:{sid}:participation:pr"
                await _upsert("participation_records", part_id, {
                    "tenant_id": tenant_id,
                    "student_id": sid,
                    "student_name": student_name,
                    "class_id": class_id,
                    "subject_id": subject_id,
                    "session_id": session_id,
                    "participation_type": "session",
                    "quality": "good",
                    "points": int(part_pts),
                    "notes": "تجميع تفاعل الحصة المباشرة",
                    "date": session_date,
                    "source": "live_session",
                    "created_at": now_iso,
                    "updated_at": now_iso,
                })
                participation_written += 1

            # ---- Behaviour events -> behaviour_records ----
            for ev in agg.get("behaviour_events", []):
                iid = ev.get("interaction_id")
                if not iid:
                    continue
                beh_id = f"si:{iid}:br"
                cat = ev.get("category")
                await _upsert("behaviour_records", beh_id, {
                    "tenant_id": tenant_id,
                    "school_id": tenant_id,
                    "student_id": sid,
                    "student_name": student_name,
                    "class_id": class_id,
                    "subject_id": subject_id,
                    "session_id": session_id,
                    "type": cat or "incident",
                    "category": cat,
                    "behaviour_type": ev.get("behaviour_type"),
                    "points": ev.get("points", 0),
                    "description": ev.get("details"),
                    "incident_date": session_date,
                    "status": "recorded",
                    "visible_to_parent": True,
                    "recorded_by": ev.get("recorded_by"),
                    "recorded_at": ev.get("recorded_at") or now_iso,
                    "source": "live_session",
                    "updated_at": now_iso,
                })
                behaviour_written += 1

        return {
            "grades": grades_written,
            "participation": participation_written,
            "behaviour": behaviour_written,
        }

    async def _trigger_session_analytics(self, session_id, school_id, class_id, subject_id, teacher_id,
                                          attendance_rate, engagement_rate, positive_b, negative_b,
                                          skills_recorded, total_students, present_count, now):
        """Push session analytics to school/class/teacher analytics collections."""
        analytics_record = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "school_id": school_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "teacher_id": teacher_id,
            "date": now.strftime("%Y-%m-%d"),
            "attendance_rate": attendance_rate,
            "engagement_rate": engagement_rate,
            "behavior_distribution": {
                "positive": positive_b,
                "negative": negative_b,
            },
            "skills_recorded": skills_recorded,
            "total_students": total_students,
            "present_count": present_count,
            "created_at": now.isoformat(),
        }
        await gd_insert(self.session, "session_analytics", analytics_record)

    async def _generate_ai_session_insights(self, session_id, school_id, class_id, subject_id, teacher_id,
                                             top_participants, needs_attention, attendance_rate, engagement_rate, now):
        """Generate and store AI-driven session insights."""
        insights = []
        
        if attendance_rate < 70:
            insights.append({
                "type": "warning",
                "category": "attendance",
                "message_ar": f"نسبة الحضور منخفضة ({attendance_rate}%) — يُنصح بمتابعة أسباب الغياب",
                "message_en": f"Low attendance rate ({attendance_rate}%) — follow up on absence reasons",
            })
        
        if engagement_rate < 30:
            insights.append({
                "type": "warning",
                "category": "engagement",
                "message_ar": f"نسبة المشاركة منخفضة ({engagement_rate}%) — جرّب استراتيجيات تفاعلية مختلفة",
                "message_en": f"Low engagement ({engagement_rate}%) — try different interactive strategies",
            })
        elif engagement_rate > 70:
            insights.append({
                "type": "success",
                "category": "engagement",
                "message_ar": f"مشاركة ممتازة ({engagement_rate}%) — أداء رائع!",
                "message_en": f"Excellent engagement ({engagement_rate}%) — great performance!",
            })
        
        for na in needs_attention:
            insights.append({
                "type": "attention",
                "category": "student",
                "student_id": na["student_id"],
                "message_ar": f"{na['name']}: {na['reason']}",
                "message_en": f"{na['name']}: needs attention",
            })
        
        for tp in top_participants:
            insights.append({
                "type": "success",
                "category": "student",
                "student_id": tp["student_id"],
                "message_ar": f"{tp['name']}: أداء متميز — {tp['correct_answers']} إجابة صحيحة و{tp['participations']} مشاركة",
                "message_en": f"{tp['name']}: outstanding — {tp['correct_answers']} correct, {tp['participations']} participations",
            })

        if insights:
            await gd_insert(self.session, "ai_session_insights", {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "school_id": school_id,
                "class_id": class_id,
                "subject_id": subject_id,
                "teacher_id": teacher_id,
                "insights": insights,
                "insights_count": len(insights),
                "date": now.strftime("%Y-%m-%d"),
                "created_at": now.isoformat(),
            })

        await self._log_event(
            session_id=session_id,
            event_type=EventType.AI_INSIGHTS_GENERATED.value,
            actor_id=teacher_id,
            metadata={"insights_count": len(insights)}
        )

    async def _resolve_management_recipient_ids(self, tenant_id: str) -> List[str]:
        """Task #486 (+#490) — return active school-management user ids for a
        given tenant.

        Canonical school-management cohort across the codebase (see
        ``notification_routes_mod.create_notification``,
        ``role_dashboards_mod.get_parent_dashboard``,
        ``notification_routes.send_notification``):
        ``school_principal``, ``school_admin``, ``school_sub_admin``. The
        original Task #486 cohort omitted ``school_admin``, which silently
        delivered nothing in real-world tenants whose principal/vice
        principal are stored as ``school_admin`` (the most common
        provisioned shape). Ordering: principal-tier first
        (``school_principal`` then ``school_admin`` — same tier, stable
        by id), then ``school_sub_admin`` last.

        Independent-Teacher workspaces (tenant_id starting with ``itw_``)
        have no management recipient by design and always resolve to an
        empty list. The query is a single bulk ``gd_find`` — no N+1.
        """
        if not tenant_id:
            return []
        if isinstance(tenant_id, str) and tenant_id.startswith("itw_"):
            return []
        rows = await gd_find(
            self.session, "users",
            {
                "tenant_id": tenant_id,
                "role": {"$in": ["school_principal", "school_admin", "school_sub_admin"]},
                "is_active": True,
            },
            limit=50,
        )
        # school_principal and school_admin are both principal-tier in this
        # codebase (different tenants provision the head-of-school under
        # either name); rank them equally and put sub-admins last.
        priority = {"school_principal": 0, "school_admin": 0, "school_sub_admin": 1}
        rows.sort(key=lambda u: (priority.get(u.get("role"), 9), u.get("id") or ""))
        return [u["id"] for u in rows if u.get("id")]

    async def _send_management_session_summary(
        self,
        session_id: str,
        tenant_id: str,
        subject_id: str,
        class_id: str,
        duration_minutes: int,
        present: int,
        absent: int,
        total: int,
        attendance_rate: float,
        questions_count: int,
        correct: int,
        engagement_rate: float,
        now: datetime,
    ) -> int:
        """Task #486 — deliver an end-of-session summary to school management.

        Persists one ``notifications`` row per resolved management recipient
        (principal + sub-admin in the session's tenant). When no recipient
        exists (e.g. IT workspace, or a school that has not yet provisioned
        a principal), this is a logged no-op — never raises. ``tenant_id``
        MUST be the session's tenant; the caller passes it in so the engine
        can not silently widen scope from a caller-supplied value.
        Returns the number of notifications inserted.
        """
        recipient_ids = await self._resolve_management_recipient_ids(tenant_id)
        if not recipient_ids:
            logger.info(
                "end-session summary: no management recipients for tenant %s (session=%s)",
                tenant_id, session_id,
            )
            return 0

        subject_name = ""
        class_name = ""
        if subject_id:
            subj = await gd_find_one(self.session, "subjects", {"id": subject_id})
            if subj:
                subject_name = subj.get("name_ar") or subj.get("name_en") or ""
        if class_id:
            cls = await gd_find_one(self.session, "classes", {"id": class_id})
            if cls:
                class_name = cls.get("name") or ""

        title_ar = f"ملخص الحصة — {subject_name}" if subject_name else "ملخص الحصة"
        title_en = f"Session Summary — {subject_name}" if subject_name else "Session Summary"
        message_ar = (
            f"اكتملت حصة {subject_name} للصف {class_name}. "
            f"المدة {duration_minutes} دقيقة، الحضور {present}/{total} ({attendance_rate}%)، "
            f"الأسئلة {questions_count} والإجابات الصحيحة {correct}."
        )
        message_en = (
            f"Session for {subject_name} ({class_name}) completed. "
            f"Duration: {duration_minutes} min. Present: {present}/{total} ({attendance_rate}%). "
            f"Questions: {questions_count}, Correct: {correct}."
        )

        sent = 0
        for rid in recipient_ids:
            await gd_insert(self.session, "notifications", {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "user_id": rid,
                "title": title_ar,
                "title_en": title_en,
                "message": message_ar,
                "message_en": message_en,
                "type": "communication",
                "category": "session",
                "priority": "medium",
                "is_read": False,
                "entity_type": "session",
                "entity_id": session_id,
                "created_at": now.isoformat(),
            })
            sent += 1
        return sent

    async def _send_smart_end_session_notifications(self, session_id, school_id, attendance, neg_students, student_interactions, now):
        """Send automatic notifications on session end: absence, repeated negative behavior, improvement."""
        notifications_sent = 0
        
        absent_students = [a for a in attendance if a["status"] == AttendanceStatus.ABSENT.value]
        for a_rec in absent_students:
            sid = a_rec["student_id"]
            student = await gd_find_one(self.session, "students", {"id": sid, "is_active": True})
            if not student:
                continue
            parent_user_id = student.get("parent_user_id")
            if not parent_user_id:
                continue
            await gd_insert(self.session, "notifications", {
                "id": str(uuid.uuid4()),
                "tenant_id": school_id,
                "recipient_id": parent_user_id,
                "title": f"⚠️ غياب الطالب {student.get('full_name', '')}",
                "title_en": f"⚠️ Student {student.get('full_name', '')} was absent",
                "message": f"تم تسجيل غياب {student.get('full_name', '')} في الحصة اليوم. يرجى المتابعة.",
                "message_en": f"{student.get('full_name', '')} was marked absent in today's session.",
                "type": "alert",
                "category": "attendance",
                "priority": "high",
                "is_read": False,
                "entity_type": "session",
                "entity_id": session_id,
                "created_at": now.isoformat(),
            })
            notifications_sent += 1

        for sid, neg_count in neg_students.items():
            if neg_count >= 3:
                student = await gd_find_one(self.session, "students", {"id": sid, "is_active": True})
                if not student:
                    continue
                parent_user_id = student.get("parent_user_id")
                recipients = []
                if parent_user_id:
                    recipients.append(parent_user_id)
                # Task #486 — the old filter used ``school_id`` (the
                # ``users`` table is keyed by ``tenant_id``) and the role
                # value ``school_admin`` (a platform-tier role, not the
                # school management cohort), so this branch silently
                # delivered nothing. Use the shared canonical resolver so
                # the principal+sub-admin cohort is computed exactly the
                # same way the end-of-session summary uses (and IT
                # workspaces correctly resolve to an empty cohort).
                mgmt_ids = await self._resolve_management_recipient_ids(school_id)
                recipients.extend(mgmt_ids)
                
                for rid in recipients:
                    await gd_insert(self.session, "notifications", {
                        "id": str(uuid.uuid4()),
                        "tenant_id": school_id,
                        "recipient_id": rid,
                        "title": f"⚠️ سلوك سلبي متكرر — {student.get('full_name', '')}",
                        "title_en": f"⚠️ Repeated negative behavior — {student.get('full_name', '')}",
                        "message": f"سجّل الطالب {student.get('full_name', '')} {neg_count} سلوكيات سلبية في الحصة. يرجى المتابعة.",
                        "message_en": f"Student {student.get('full_name', '')} had {neg_count} negative behaviors in this session.",
                        "type": "warning",
                        "category": "behaviour",
                        "priority": "high",
                        "is_read": False,
                        "entity_type": "session",
                        "entity_id": session_id,
                        "created_at": now.isoformat(),
                    })
                    notifications_sent += 1

        for sid, si in student_interactions.items():
            if si.get("correct", 0) >= 3 or si.get("participation", 0) >= 5:
                student = await gd_find_one(self.session, "students", {"id": sid, "is_active": True})
                if not student:
                    continue
                parent_user_id = student.get("parent_user_id")
                if not parent_user_id:
                    continue
                await gd_insert(self.session, "notifications", {
                    "id": str(uuid.uuid4()),
                    "tenant_id": school_id,
                    "recipient_id": parent_user_id,
                    "title": f"⭐ أداء متميز — {student.get('full_name', '')}",
                    "title_en": f"⭐ Outstanding performance — {student.get('full_name', '')}",
                    "message": f"تميّز {student.get('full_name', '')} في حصة اليوم بمشاركة فعّالة وأداء ممتاز!",
                    "message_en": f"{student.get('full_name', '')} showed outstanding engagement and performance today!",
                    "type": "success",
                    "category": "academic",
                    "priority": "medium",
                    "is_read": False,
                    "entity_type": "session",
                    "entity_id": session_id,
                    "created_at": now.isoformat(),
                })
                notifications_sent += 1

        if notifications_sent > 0:
            await self._log_event(
                session_id=session_id,
                event_type=EventType.PARENT_NOTIFICATION_SENT.value,
                actor_id="system",
                metadata={"notifications_sent": notifications_sent}
            )
    
    async def export_session_report(self, session_id: str, teacher_id: str, fmt: str = "csv") -> dict:
        """Export session report as JSON data for frontend to download."""
        session = await gd_find_one(self.session, "class_sessions", {"id": session_id})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

        attendance = await gd_find(self.session, "session_attendance", {"session_id": session_id}, limit=200)
        interactions = await gd_find(self.session, "session_interactions", {"session_id": session_id}, limit=500)
        notes = await gd_find(self.session, "session_notes", {"session_id": session_id}, limit=100)

        student_ids = list(set(
            [a["student_id"] for a in attendance] +
            [i["student_id"] for i in interactions]
        ))
        students_map = {}
        for sid in student_ids:
            s = await gd_find_one(self.session, "students", {"id": sid, "is_active": True})
            if s:
                students_map[sid] = s.get("full_name", sid)

        student_rows = []
        for sid in student_ids:
            name = students_map.get(sid, sid)
            att = next((a for a in attendance if a["student_id"] == sid), {})
            sis = [i for i in interactions if i["student_id"] == sid]
            correct = sum(1 for i in sis if i.get("answer_result") == "correct")
            wrong = sum(1 for i in sis if i.get("answer_result") == "wrong")
            participations = sum(1 for i in sis if i.get("interaction_type") == "participation")
            pos = sum(1 for i in sis if i.get("behaviour_category") == "positive")
            neg = sum(1 for i in sis if i.get("behaviour_category") == "negative")
            student_rows.append({
                "student_name": name,
                "attendance_status": att.get("status", "N/A"),
                "correct_answers": correct,
                "wrong_answers": wrong,
                "participations": participations,
                "positive_behaviors": pos,
                "negative_behaviors": neg,
            })

        try:
            await self._log_event(
                session_id=session_id,
                event_type=EventType.SESSION_REPORT_EXPORTED.value,
                actor_id=teacher_id,
                metadata={"format": fmt}
            )
        except Exception as e:
            logger.debug("Failed to log session report export event: %s", e)

        return {
            "session_id": session_id,
            "subject": session.get("subject_name", ""),
            "class_name": session.get("class_name", ""),
            "date": session.get("start_time", "")[:10],
            "duration_minutes": session.get("duration_minutes", 0),
            "summary": session.get("summary", {}),
            "students": student_rows,
            "notes": [{"text": n.get("text", ""), "type": n.get("note_type", ""), "is_closing": n.get("is_closing_note", False)} for n in notes],
        }

    # ---------- Score System ----------
    
    async def _update_student_score(
        self,
        student_id: str,
        score_change: int,
        category: str,
        description: str,
        school_id: str = None
    ):
        """Update student score and create ledger entry"""
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        month = now.strftime("%Y-%m")

        if not school_id:
            student = await gd_find_one(self.session, "students", {"id": student_id, "is_active": True})
            school_id = student.get("school_id") if student else None
        
        ledger_entry = {
            "id": str(uuid.uuid4()),
            "student_id": student_id,
            "school_id": school_id,
            "score_change": score_change,
            "category": category,
            "description": description,
            "date": today,
            "week": week_start,
            "month": month,
            "created_at": now.isoformat()
        }
        
        await gd_insert(self.session, "student_score_ledger", ledger_entry)
        
        existing = await gd_find_one(self.session, "student_daily_scores", {"student_id": student_id, "date": today})
        if existing:
            await gd_update_one(self.session, "student_daily_scores",
                {"student_id": student_id, "date": today},
                {"score": existing.get("score", 0) + score_change}
            )
        else:
            await gd_insert(self.session, "student_daily_scores", {
                "id": str(uuid.uuid4()),
                "student_id": student_id,
                "school_id": school_id,
                "date": today,
                "score": score_change,
                "created_at": now.isoformat()
            })
    
    async def _check_answer_streak(self, session_id: str, student_id: str) -> int:
        """Check consecutive correct answers for a student in current session"""
        interactions = await gd_find(self.session, "session_interactions",
            {
                "session_id": session_id,
                "student_id": student_id,
                "interaction_type": InteractionType.QUESTION.value
            }, order_by="recorded_at", desc_order=True, limit=10)
        
        streak = 0
        for i in interactions:
            if i.get("answer_result") == AnswerResult.CORRECT.value:
                streak += 1
            else:
                break
        
        return streak
    
    async def get_student_score(self, student_id: str) -> StudentScoreResponse:
        """Get comprehensive score information for a student"""
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        month = now.strftime("%Y-%m")
        
        # Get student info
        student = await gd_find_one(self.session, "students", {"id": student_id, "is_active": True})
        if not student:
            raise HTTPException(status_code=404, detail="الطالب غير موجود")
        
        # Get daily score
        daily = await gd_find_one(self.session, "student_daily_scores", {"student_id": student_id, "date": today})
        daily_score = daily.get("score", 0) if daily else 0
        
        # Get weekly score
        weekly_scores = await gd_find(self.session, "student_score_ledger", {"student_id": student_id, "week": week_start}, limit=500)
        weekly_score = sum(s.get("score_change", 0) for s in weekly_scores)
        
        # Get monthly score
        monthly_scores = await gd_find(self.session, "student_score_ledger", {"student_id": student_id, "month": month}, limit=1000)
        monthly_score = sum(s.get("score_change", 0) for s in monthly_scores)
        
        # Get category scores
        behaviour_score = sum(
            s.get("score_change", 0) 
            for s in monthly_scores 
            if s.get("category") == "behaviour"
        )
        participation_score = sum(
            s.get("score_change", 0) 
            for s in monthly_scores 
            if s.get("category") in ["participation", "answer"]
        )
        
        student_tenant = student.get("tenant_id") or student.get("school_id") or ""
        levels = await self._get_student_levels(student_tenant)
        level = StudentLevel.NEEDS_ATTENTION
        for level_name, (min_score, max_score) in levels.items():
            if min_score <= weekly_score <= max_score:
                level = StudentLevel(level_name)
                break
        
        return StudentScoreResponse(
            student_id=student_id,
            student_name=student.get("full_name", "طالب"),
            daily_score=max(0, daily_score),  # No negative display
            weekly_score=weekly_score,
            monthly_score=monthly_score,
            behaviour_score=behaviour_score,
            participation_score=participation_score,
            level=level,
            recent_achievements=[]
        )
    
    # ---------- Skill Recording ----------

    async def record_skill(
        self,
        session_id: str,
        student_id: str,
        skill_type_id: str,
        teacher_id: str,
        notes: Optional[str] = None,
        custom_name: Optional[str] = None,
        points_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Record a skill observation for a student during a session.

        Custom (teacher-defined) skills that are not present in the
        ``skills_types`` table can be recorded by passing ``custom_name``
        together with an optional ``points_override``. In that case the
        record is stored with ``skill_type_id=None`` and the override
        points are applied to the student's score the same way positive
        behaviours do, instead of falling back to the fixed
        ``special_skill`` rule. This keeps the score in sync with what
        the teacher configured in the sidebar settings.
        """
        now = datetime.now(timezone.utc)

        session = await gd_find_one(self.session, "class_sessions", {"id": session_id})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

        # Detect a custom (locally-defined) skill: either explicitly
        # marked via ``custom_name`` or carrying the ``custom_`` prefix
        # the frontend uses for ad-hoc entries.
        is_custom = bool(custom_name) or (
            isinstance(skill_type_id, str) and skill_type_id.startswith("custom_")
        )

        skill_type = None
        if skill_type_id and not is_custom:
            skill_type = await gd_find_one(self.session, "skills_types", {"id": skill_type_id})
            if not skill_type:
                skill_type = await gd_find_one(self.session, "skills_types", {"name_ar": skill_type_id})
            if not skill_type:
                skill_type = await gd_find_one(self.session, "skills_types", {"name_en": skill_type_id})

        if not skill_type and not is_custom:
            existing = await gd_find(self.session, "skills_types", {}, limit=200)
            pre_seed_count = len(existing) if existing else 0
            if pre_seed_count == 0 and skill_type_id:
                now_iso = datetime.now(timezone.utc).isoformat()
                for s in DEFAULT_SKILLS_TYPES:
                    doc = dict(s)
                    doc["created_at"] = now_iso
                    try:
                        existing_one = await gd_find_one(self.session, "skills_types", {"id": doc["id"]})
                        if not existing_one:
                            await gd_insert(self.session, "skills_types", doc)
                    except Exception as seed_err:
                        logger.debug("Skipped seeding skill %s: %s", doc.get("id"), seed_err)
                logger.warning("skills_types table was empty — seeded default skill types on demand")
                for field in ("id", "name_ar", "name_en"):
                    skill_type = await gd_find_one(self.session, "skills_types", {field: skill_type_id})
                    if skill_type:
                        break

            if not skill_type:
                existing_after = await gd_find(self.session, "skills_types", {}, limit=200)
                logger.warning(
                    "Skill record rejected: skill_type_id=%r not found (count=%d, sample_ids=%s)",
                    skill_type_id,
                    len(existing_after) if existing_after else 0,
                    [x.get("id") for x in (existing_after or [])[:5]],
                )
                raise HTTPException(status_code=404, detail="نوع المهارة غير موجود")

        student = await gd_find_one(self.session, "students", {"id": student_id, "is_active": True})
        if not student:
            raise HTTPException(status_code=404, detail="الطالب غير موجود")

        if student.get("class_id") != session.get("class_id"):
            attendance = await gd_find_one(
                self.session,
                "session_attendance",
                {"session_id": session_id, "student_id": student_id},
            )
            if not attendance:
                logger.warning(
                    "Skill record rejected: student %s (class=%s) not in session %s (class=%s) and no attendance row",
                    student_id, student.get("class_id"), session_id, session.get("class_id"),
                )
                raise HTTPException(status_code=400, detail="الطالب لا ينتمي لهذا الفصل")

        # Resolve display name and persisted FK depending on whether
        # this is a registered skill type or a teacher-defined custom one.
        if is_custom:
            display_name = (custom_name or "").strip() or "مهارة"
            persisted_skill_type_id = None
            event_marker = f"custom:{display_name}"
        else:
            display_name = skill_type.get("name_ar", skill_type.get("name"))
            persisted_skill_type_id = skill_type_id
            event_marker = skill_type_id

        skill_record = {
            "id": str(uuid.uuid4()),
            "student_id": student_id,
            "class_id": session.get("class_id"),
            "session_id": session_id,
            "skill_type_id": persisted_skill_type_id,
            "skill_name": display_name,
            "recorded_by_teacher": teacher_id,
            "notes": notes,
            "timestamp": now.isoformat(),
            "school_id": student.get("school_id")
        }
        await gd_insert(self.session, "student_skills", skill_record)

        interaction = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "student_id": student_id,
            "type": InteractionType.BEHAVIOUR.value,
            "interaction_type": InteractionType.BEHAVIOUR.value,
            "behaviour_category": BehaviourCategory.SKILL.value,
            "behaviour_type": event_marker,
            "behaviour_details": notes,
            "recorded_by": teacher_id,
            "recorded_at": now.isoformat(),
            "timestamp": now.isoformat(),
            "editable_until": (now + timedelta(hours=1)).isoformat()
        }
        await gd_insert(self.session, "session_interactions", interaction)

        # Score change: prefer an explicit override (custom skills carry
        # their own configured magnitude); otherwise fall back to the
        # session's special_skill rule, mirroring positive-behaviour
        # scoring semantics.
        rules = await self._get_session_score_rules(session_id)
        if points_override is not None:
            try:
                score_change = int(points_override)
            except (TypeError, ValueError):
                score_change = rules.get("special_skill", 3)
        else:
            score_change = rules.get("special_skill", 3)

        if score_change != 0:
            await self._update_student_score(
                student_id,
                score_change,
                "skill",
                f"مهارة: {display_name}"
            )

        await self._log_event(
            session_id=session_id,
            event_type=EventType.SKILL_RECORDED.value,
            actor_id=teacher_id,
            student_id=student_id,
            new_value=event_marker,
            metadata={
                "score_change": score_change,
                "skill_name": display_name,
                "interaction_id": interaction["id"],
                "skill_record_id": skill_record["id"],
            }
        )

        return {
            "message": "تم تسجيل المهارة",
            "skill_name": display_name,
            "score_change": score_change,
            "skill_record_id": skill_record["id"]
        }

    # ---------- Activity Log ----------

    async def get_activity_log(self, session_id: str, limit: int = 50) -> list:
        """Fetch session interactions formatted as activity log entries.

        Reversed interactions are included and marked with ``reversed: True`` so
        the frontend can render them struck-through instead of hiding them.
        """
        all_interactions = await gd_find(self.session, "session_interactions",
            {"session_id": session_id}, order_by="recorded_at", desc_order=True, limit=limit * 3)

        interactions = all_interactions[:limit]

        if not interactions:
            return []

        student_ids = list(set(i["student_id"] for i in interactions if i.get("student_id")))
        students = {}
        if student_ids:
            student_docs = await gd_find(self.session, "students", {"id": {"$in": student_ids}, "is_active": True}, limit=len(student_ids))
            students = {s["id"]: s.get("full_name", "طالب") for s in student_docs}

        skill_ids = [i.get("behaviour_type") for i in interactions
                     if i.get("behaviour_category") == "skill" and i.get("behaviour_type")]
        skill_names = {}
        if skill_ids:
            skill_docs = await gd_find(self.session, "skill_types", {"id": {"$in": skill_ids}}, limit=len(skill_ids))
            skill_names = {s["id"]: s.get("name_ar", s.get("name", "مهارة")) for s in skill_docs}

        events = await gd_find(self.session, "session_event_log",
            {"session_id": session_id,
             "event_type": {"$in": ["answer_recorded", "participation_recorded",
                                     "behaviour_recorded", "skill_recorded"]}},
            order_by="timestamp", desc_order=True, limit=limit)
        score_map = {}
        for e in events:
            key = f"{e.get('student_id')}_{e.get('event_type')}_{e.get('timestamp','')[:19]}"
            score_map[key] = e.get("metadata", {}).get("score_change", 0)

        log_entries = []
        for i in interactions:
            itype = i.get("interaction_type")
            is_reversed = bool((i.get("data") or {}).get("reversed"))
            student_name = students.get(i.get("student_id"), "طالب")
            first_name = student_name.split(" ")[0] if student_name else "طالب"
            recorded_at = i.get("recorded_at", "")

            ts_prefix = recorded_at[:19] if recorded_at else ""

            if itype == "question":
                answer = i.get("answer_result", "correct")
                sc_key = f"{i.get('student_id')}_answer_recorded_{ts_prefix}"
                change = score_map.get(sc_key, 0)
                if answer == "correct":
                    emoji, text, color = "✅", f"{first_name} — إجابة صحيحة (+{change})", "text-green-700"
                elif answer == "wrong":
                    emoji, text, color = "❌", f"{first_name} — إجابة خاطئة", "text-red-600"
                else:
                    emoji, text, color = "⏭️", f"{first_name} — لم يجب ({change})", "text-amber-600"

            elif itype == "participation":
                ptype = i.get("participation_type", "active")
                sc_key = f"{i.get('student_id')}_participation_recorded_{ts_prefix}"
                change = score_map.get(sc_key, 0)
                labels = {"active": "مشاركة", "initiative": "مبادرة",
                          "inactive": "لا يتفاعل", "refused": "رفض"}
                label = labels.get(ptype, ptype)
                sign = f"+{change}" if change > 0 else str(change)
                if ptype in ("active", "initiative"):
                    emoji = "🙋"
                elif ptype == "refused":
                    emoji = "🚫"
                else:
                    emoji = "😐"
                text = f"{first_name} — {label} ({sign})"
                color = "text-blue-700" if change >= 0 else "text-amber-700"

            elif itype == "behaviour":
                bcat = i.get("behaviour_category", "positive")
                btype = i.get("behaviour_type", "")
                if bcat == "skill":
                    sc_key = f"{i.get('student_id')}_skill_recorded_{ts_prefix}"
                else:
                    sc_key = f"{i.get('student_id')}_behaviour_recorded_{ts_prefix}"
                change = score_map.get(sc_key, 0)

                if bcat == "skill":
                    skill_label = skill_names.get(btype, btype)
                    sign = f"+{change}" if change > 0 else str(change)
                    emoji, text, color = "⭐", f"{first_name} — {skill_label} ({sign})", "text-purple-700"
                else:
                    b_labels = {
                        "respect": "احترام", "commitment": "التزام", "helping_others": "مساعدة الآخرين",
                        "leadership": "قيادة", "disruption": "إزعاج", "cheating": "غش",
                        "non_compliance": "عدم التزام", "interruption": "مقاطعة",
                    }
                    label = b_labels.get(btype, btype)
                    sign = f"+{change}" if change > 0 else str(change)
                    emoji = "👍" if bcat == "positive" else "⚠️"
                    text = f"{first_name} — {label} ({sign})"
                    color = "text-purple-700" if bcat == "positive" else "text-red-600"
            else:
                continue

            try:
                from datetime import datetime as dt
                t = dt.fromisoformat(recorded_at.replace("Z", "+00:00"))
                time_str = t.strftime("%H:%M")
            except Exception as e:
                logger.debug("Could not parse interaction timestamp: %s", e)
                time_str = ""

            log_entries.append({
                "id": i.get("id", ""),
                "emoji": emoji,
                "text": text,
                "color": color,
                "time": time_str,
                "reversed": is_reversed,
            })

        # Append action_reversed events from the event log so the log shows an
        # explicit "تم التراجع" entry for each undo action.
        reversal_events = await gd_find(self.session, "session_event_log",
            {"session_id": session_id, "event_type": "action_reversed"},
            order_by="timestamp", desc_order=True, limit=limit)
        for ev in reversal_events:
            meta = ev.get("metadata") or {}
            student_name = meta.get("student_name", "")
            first_name = student_name.split(" ")[0] if student_name else ""
            text = f"تم التراجع — {first_name}" if first_name else "تم التراجع عن إجراء"
            ts = ev.get("timestamp", "")
            try:
                from datetime import datetime as dt
                t = dt.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = t.strftime("%H:%M")
            except Exception:
                time_str = ""
            log_entries.append({
                "id": ev.get("id", ""),
                "emoji": "action_reversed",
                "text": text,
                "color": "text-muted-foreground",
                "time": time_str,
                "reversed": False,
            })

        log_entries.sort(key=lambda e: e.get("time", ""), reverse=True)
        return log_entries

    # ---------- Class Metrics ----------

    async def get_class_metrics(self, teacher_id: str, class_id: str) -> Dict[str, Any]:
        """Get real metrics for a teacher's class from session data"""
        sessions = await gd_find(self.session, "class_sessions", {"class_id": class_id, "teacher_id": teacher_id}, limit=500)

        total_students = await gd_count(self.session, "students", {"class_id": class_id, "is_active": True})

        total_attendance = 0
        total_present = 0
        total_participation_events = 0
        total_present_in_sessions = 0
        total_correct = 0
        total_questions = 0
        completed_sessions = [s for s in sessions if s.get("status") == SessionStatus.COMPLETED.value]

        for s in completed_sessions:
            att_records = await gd_find(self.session, "session_attendance", {"session_id": s["id"]}, limit=200)
            present = sum(1 for a in att_records if a.get("status") == AttendanceStatus.PRESENT.value)
            total_attendance += len(att_records)
            total_present += present

            interactions = await gd_find(self.session, "session_interactions", {"session_id": s["id"]}, limit=500)
            participants = set()
            for i in interactions:
                if i.get("interaction_type") in [InteractionType.PARTICIPATION.value, InteractionType.QUESTION.value]:
                    participants.add(i["student_id"])
                if i.get("interaction_type") == InteractionType.QUESTION.value:
                    total_questions += 1
                    if i.get("answer_result") == AnswerResult.CORRECT.value:
                        total_correct += 1
            total_participation_events += len(participants)
            total_present_in_sessions += present

        attendance_rate = round(total_present / total_attendance * 100, 1) if total_attendance > 0 else 0
        participation_rate = round(total_participation_events / total_present_in_sessions * 100, 1) if total_present_in_sessions > 0 else 0
        avg_performance = round(total_correct / total_questions * 100, 1) if total_questions > 0 else 0

        next_session_info = None
        in_progress = await gd_find_one(self.session, "class_sessions",
            {"class_id": class_id, "teacher_id": teacher_id, "status": SessionStatus.IN_PROGRESS.value}
        )
        if in_progress:
            next_session_info = {"status": "in_progress", "start_time": in_progress.get("start_time")}

        return {
            "class_id": class_id,
            "attendance_rate": attendance_rate,
            "participation_rate": participation_rate,
            "avg_performance": avg_performance,
            "total_sessions": len(completed_sessions),
            "total_students": total_students,
            "next_session": next_session_info
        }

    # ---------- Session Notes ----------

    async def add_note(
        self,
        session_id: str,
        teacher_id: str,
        text: str,
        note_type: str = "session",
        student_id: str = None,
        student_ids: List[str] = None
    ) -> Dict[str, Any]:
        """Add a teacher note to a session."""
        now = datetime.now(timezone.utc)
        note = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "teacher_id": teacher_id,
            "text": text,
            "note_type": note_type,
            "student_id": student_id,
            "student_ids": student_ids or [],
            "created_at": now.isoformat()
        }
        await gd_insert(self.session, "session_notes", note)

        await self._log_event(
            session_id=session_id,
            event_type=EventType.NOTE_ADDED.value,
            actor_id=teacher_id,
            student_id=student_id,
            metadata={"note_type": note_type, "note_id": note["id"]}
        )

        return {"message": "تم إضافة الملاحظة", "note_id": note["id"], "note": {k: v for k, v in note.items() if k != "_id"}}

    async def get_session_notes(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve all notes attached to a session."""
        notes = await gd_find(self.session, "session_notes", {"session_id": session_id}, order_by="created_at", desc_order=True, limit=500)

        for note in notes:
            if note.get("student_id"):
                student = await gd_find_one(self.session, "students", {"id": note["student_id"], "is_active": True})
                note["student_name"] = student.get("full_name") if student else None
        return notes

    async def delete_note(self, note_id: str, teacher_id: str) -> Dict[str, Any]:
        """Remove a note from a session by note ID."""
        result = await gd_delete_one(self.session, "session_notes", {"id": note_id, "teacher_id": teacher_id})
        if result == 0:
            raise HTTPException(status_code=404, detail="الملاحظة غير موجودة")
        return {"message": "تم حذف الملاحظة"}

    # ---------- Live Metrics ----------

    async def get_live_metrics(self, session_id: str) -> Dict[str, Any]:
        """Return real-time participation and behaviour metrics for a session."""
        session = await gd_find_one(self.session, "class_sessions", {"id": session_id})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

        attendance = await gd_find(self.session, "session_attendance", {"session_id": session_id}, limit=200)

        all_interactions = await gd_find(self.session, "session_interactions", {"session_id": session_id}, limit=1000)
        # Exclude reversed interactions so live metrics reflect only active actions.
        interactions = [i for i in all_interactions if not (i.get("data") or {}).get("reversed")]

        present = sum(1 for a in attendance if a.get("status") == AttendanceStatus.PRESENT.value)
        absent = sum(1 for a in attendance if a.get("status") == AttendanceStatus.ABSENT.value)
        late = sum(1 for a in attendance if a.get("status") == AttendanceStatus.LATE.value)
        total = len(attendance)

        questions = [i for i in interactions if i.get("interaction_type") == InteractionType.QUESTION.value]
        correct = sum(1 for q in questions if q.get("answer_result") == AnswerResult.CORRECT.value)
        wrong = sum(1 for q in questions if q.get("answer_result") == AnswerResult.WRONG.value)

        participations = [i for i in interactions if i.get("interaction_type") == InteractionType.PARTICIPATION.value]
        unique_participants = set(p["student_id"] for p in participations)
        all_interacted = set(i["student_id"] for i in interactions)

        behaviours = [i for i in interactions if i.get("interaction_type") == InteractionType.BEHAVIOUR.value]
        pos_behaviours = sum(1 for b in behaviours if b.get("behaviour_category") == BehaviourCategory.POSITIVE.value)
        neg_behaviours = sum(1 for b in behaviours if b.get("behaviour_category") == BehaviourCategory.NEGATIVE.value)

        # Count only non-reversed skills.
        all_skills_docs = await gd_find(self.session, "student_skills", {"session_id": session_id}, limit=500)
        skills_count = sum(1 for s in all_skills_docs if not s.get("is_reversed"))
        notes_count = await gd_count(self.session, "session_notes", {"session_id": session_id})

        duration_minutes = 0
        if session.get("start_time"):
            start = datetime.fromisoformat(session["start_time"].replace("Z", "+00:00"))
            duration_minutes = round((datetime.now(timezone.utc) - start).total_seconds() / 60)

        return {
            "session_id": session_id,
            "status": session.get("status"),
            "duration_minutes": duration_minutes,
            "attendance": {
                "total": total,
                "present": present,
                "absent": absent,
                "late": late,
                "rate": round(present / total * 100, 1) if total > 0 else 0
            },
            "interaction": {
                "total_questions": len(questions),
                "correct_answers": correct,
                "wrong_answers": wrong,
                "accuracy_rate": round(correct / len(questions) * 100, 1) if questions else 0,
                "total_participations": len(participations),
                "unique_participants": len(unique_participants),
                "participation_rate": round(len(all_interacted) / present * 100, 1) if present > 0 else 0,
                "not_interacted": present - len(all_interacted)
            },
            "behaviour": {
                "positive": pos_behaviours,
                "negative": neg_behaviours
            },
            "skills_recorded": skills_count,
            "notes_count": notes_count
        }

    # ---------- Session History ----------

    async def get_teacher_sessions(
        self,
        teacher_id: str,
        page: int = 1,
        limit: int = 20,
        status_filter: str = None
    ) -> Dict[str, Any]:
        """List sessions for a teacher with optional date filters."""
        query = {"teacher_id": teacher_id}
        if status_filter:
            query["status"] = status_filter

        total = await gd_count(self.session, "class_sessions", query)
        sessions = await gd_find(self.session, "class_sessions", query,
            order_by="created_at", desc_order=True, offset=(page - 1) * limit, limit=limit)

        enriched = []
        for s in sessions:
            class_info = await gd_find_one(self.session, "classes", {"id": s.get("class_id")})
            subject = await gd_find_one(self.session, "subjects", {"id": s.get("subject_id")})

            att_count = await gd_count(self.session, "session_attendance", {"session_id": s["id"]})
            present_count = await gd_count(self.session, "session_attendance",
                {"session_id": s["id"], "status": AttendanceStatus.PRESENT.value}
            )
            interaction_count = await gd_count(self.session, "session_interactions", {"session_id": s["id"]})

            enriched.append({
                **s,
                "class_name": class_info.get("name") if class_info else "فصل",
                "subject_name": (subject.get("name_ar") or subject.get("name")) if subject else "مادة",
                "total_students": att_count,
                "present_students": present_count,
                "interaction_count": interaction_count,
                "attendance_rate": round(present_count / att_count * 100, 1) if att_count > 0 else 0
            })

        return {
            "sessions": enriched,
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit
        }

    async def get_session_report(self, session_id: str) -> Dict[str, Any]:
        """Generate a detailed post-session report."""
        session = await gd_find_one(self.session, "class_sessions", {"id": session_id})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

        class_info = await gd_find_one(self.session, "classes", {"id": session.get("class_id")})
        subject = await gd_find_one(self.session, "subjects", {"id": session.get("subject_id")})
        teacher = await gd_find_one(self.session, "teachers", {"id": session.get("teacher_id")})

        attendance = await gd_find(self.session, "session_attendance", {"session_id": session_id}, limit=200)

        interactions = await gd_find(self.session, "session_interactions", {"session_id": session_id}, limit=1000)

        notes = await gd_find(self.session, "session_notes", {"session_id": session_id}, limit=500)

        skills = await gd_find(self.session, "student_skills", {"session_id": session_id}, limit=200)

        events = await gd_find(self.session, "session_event_log", {"session_id": session_id}, order_by="timestamp", desc_order=False, limit=1000)

        student_details = {}
        for att in attendance:
            sid = att["student_id"]
            student = await gd_find_one(self.session, "students", {"id": sid, "is_active": True})
            student_details[sid] = {
                "student_id": sid,
                "name": student.get("full_name") if student else sid,
                "attendance": att.get("status"),
                "answers": [],
                "participations": [],
                "behaviours": [],
                "skills": []
            }

        for inter in interactions:
            sid = inter["student_id"]
            if sid not in student_details:
                student = await gd_find_one(self.session, "students", {"id": sid, "is_active": True})
                student_details[sid] = {
                    "student_id": sid,
                    "name": student.get("full_name") if student else sid,
                    "attendance": "unknown",
                    "answers": [],
                    "participations": [],
                    "behaviours": [],
                    "skills": []
                }
            itype = inter.get("interaction_type")
            if itype == InteractionType.QUESTION.value:
                student_details[sid]["answers"].append(inter.get("answer_result"))
            elif itype == InteractionType.PARTICIPATION.value:
                student_details[sid]["participations"].append(inter.get("participation_type"))
            elif itype == InteractionType.BEHAVIOUR.value:
                student_details[sid]["behaviours"].append({
                    "category": inter.get("behaviour_category"),
                    "type": inter.get("behaviour_type")
                })

        for sk in skills:
            sid = sk.get("student_id")
            if sid in student_details:
                student_details[sid]["skills"].append(sk.get("skill_name"))

        questions = [i for i in interactions if i.get("interaction_type") == InteractionType.QUESTION.value]
        correct = sum(1 for q in questions if q.get("answer_result") == AnswerResult.CORRECT.value)
        present = sum(1 for a in attendance if a.get("status") == AttendanceStatus.PRESENT.value)
        total = len(attendance)

        return {
            "session": {
                "id": session_id,
                "date": session.get("date"),
                "start_time": session.get("start_time"),
                "end_time": session.get("end_time"),
                "duration_minutes": session.get("duration_minutes"),
                "status": session.get("status"),
                "class_name": class_info.get("name") if class_info else None,
                "subject_name": (subject.get("name_ar") or subject.get("name")) if subject else None,
                "teacher_name": teacher.get("full_name") if teacher else None,
            },
            "summary": {
                "total_students": total,
                "present": present,
                "absent": total - present,
                "attendance_rate": round(present / total * 100, 1) if total > 0 else 0,
                "questions_asked": len(questions),
                "correct_answers": correct,
                "accuracy_rate": round(correct / len(questions) * 100, 1) if questions else 0,
                "skills_recorded": len(skills),
                "notes_count": len(notes)
            },
            "students": list(student_details.values()),
            "notes": notes,
            "timeline": events[:50]
        }

    # ---------- Event Log ----------

    async def get_session_events(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the chronological event log for a session."""
        events = await gd_find(self.session, "session_event_log",
            {"session_id": session_id}, order_by="timestamp", desc_order=True, limit=limit)
        return events

    # ---------- Auto-Close Stale Sessions ----------

    async def auto_close_stale_sessions(self, max_duration_hours: int = 4) -> Dict[str, Any]:
        """Close sessions that have been idle beyond the configured timeout."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_duration_hours)).isoformat()
        stale = await gd_find(self.session, "class_sessions", {
            "status": {"$in": self.ACTIVE_STATUSES},
            "start_time": {"$lt": cutoff}
        }, limit=100)

        closed_count = 0
        for session in stale:
            try:
                await self.end_session(session["id"], session.get("teacher_id", "system"))
                closed_count += 1
            except Exception as e:
                logger.warning("Graceful end_session failed for %s, force-closing: %s", session["id"], e)
                await gd_update_one(self.session, "class_sessions",
                    {"id": session["id"]},
                    {"status": SessionStatus.COMPLETED.value, "end_time": datetime.now(timezone.utc).isoformat(), "auto_closed": True}
                )
                closed_count += 1

        return {"message": f"تم إغلاق {closed_count} حصة متروكة", "closed_count": closed_count}

    # ---------- Undo Last Action ----------

    # Event types that are eligible to be reversed.
    # Attendance and homework changes are excluded: attendance is approved
    # collectively, and homework status is a toggle without a score ledger.
    REVERSIBLE_EVENT_TYPES = {
        EventType.ANSWER_RECORDED.value,
        EventType.PARTICIPATION_RECORDED.value,
        EventType.BEHAVIOUR_RECORDED.value,
        EventType.SKILL_RECORDED.value,
    }

    async def get_last_reversible_action(
        self,
        session_id: str,
        teacher_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent reversible event for this session and teacher.

        Returns None when there is nothing left to undo (all actions have
        already been reversed, or there are no eligible actions at all).
        The caller is responsible for checking session ownership and status.
        """
        events = await gd_find(
            self.session,
            "session_event_log",
            {
                "session_id": session_id,
                "actor_id": teacher_id,
                "event_type": {"$in": list(self.REVERSIBLE_EVENT_TYPES)},
            },
            order_by="timestamp",
            desc_order=True,
            limit=200,
        )
        for event in events:
            meta = event.get("metadata") or {}
            if meta.get("reversed"):
                continue
            return event
        return None

    async def count_reversible_actions(
        self,
        session_id: str,
        teacher_id: str,
        cap: int = 10,
    ) -> int:
        """Count how many unreversed reversible events exist for this teacher/session.

        The count is capped at *cap* so the UI can show "10+" without fetching
        an unbounded number of rows.  The same 200-row fetch used by
        get_last_reversible_action is sufficient because a session rarely
        exceeds that many interactions.
        """
        events = await gd_find(
            self.session,
            "session_event_log",
            {
                "session_id": session_id,
                "actor_id": teacher_id,
                "event_type": {"$in": list(self.REVERSIBLE_EVENT_TYPES)},
            },
            order_by="timestamp",
            desc_order=True,
            limit=200,
        )
        count = 0
        for event in events:
            meta = event.get("metadata") or {}
            if meta.get("reversed"):
                continue
            count += 1
            if count >= cap:
                break
        return count

    async def undo_last_action(
        self,
        session_id: str,
        teacher_id: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reverse the teacher's last reversible action in this session.

        The reversal is a real backend operation:
        - The original ``session_interactions`` row is marked as reversed.
        - A compensating ``student_score_ledger`` entry is inserted for any
          point-bearing action, and ``student_daily_scores`` is adjusted.
        - A reversal event is written to ``session_event_log``.
        - The original event's ``metadata.reversed`` flag is set to True so
          repeat calls do not re-reverse the same action.

        Raises HTTPException(400) when nothing is reversible.
        Raises HTTPException(409) when the session has already ended.
        """
        now = datetime.now(timezone.utc)

        # 1. Verify session exists and is active.
        session = await gd_find_one(self.session, "class_sessions", {"id": session_id})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

        if session.get("status") in (SessionStatus.COMPLETED.value, SessionStatus.CANCELLED.value, SessionStatus.ARCHIVED.value):
            raise HTTPException(
                status_code=409,
                detail="لا يمكن التراجع — الحصة منتهية أو مؤرشفة",
            )

        # 2. Resolve candidate actor ids.  Historically some action-recording
        #    routes logged events with the caller's Users.id while the session
        #    stores the Teachers.id, so an event's actor_id can be either one.
        #    Try every distinct candidate so undo works regardless of which id
        #    the original action was recorded under.
        session_teacher_id = session.get("teacher_id") or teacher_id
        candidate_actor_ids: List[str] = []
        for cid in (session_teacher_id, teacher_id, user_id):
            if cid and cid not in candidate_actor_ids:
                candidate_actor_ids.append(cid)

        # 3. Find last reversible event for this teacher in this session.
        event = None
        for cid in candidate_actor_ids:
            event = await self.get_last_reversible_action(session_id, cid)
            if event is not None:
                break
        if event is None:
            raise HTTPException(
                status_code=400,
                detail="لا توجد إجراءات يمكن التراجع عنها في هذه الحصة",
            )

        event_id = event.get("id")
        event_type = event.get("event_type", "")
        student_id = event.get("student_id")
        original_meta = event.get("metadata") or {}
        original_score_change = int(original_meta.get("score_change", 0))
        event_timestamp = event.get("timestamp", "")

        # 4. Mark the original interaction as reversed.
        #    Match on session_id + student_id + type + timestamp proximity so
        #    we avoid a missing-column migration. We update whichever row was
        #    most recently inserted just before or at the event timestamp.
        interaction_type_map = {
            EventType.ANSWER_RECORDED.value: InteractionType.QUESTION.value,
            EventType.PARTICIPATION_RECORDED.value: InteractionType.PARTICIPATION.value,
            EventType.BEHAVIOUR_RECORDED.value: InteractionType.BEHAVIOUR.value,
            EventType.SKILL_RECORDED.value: InteractionType.BEHAVIOUR.value,
        }
        itype = interaction_type_map.get(event_type)

        # Find matching interaction row to mark as reversed.
        interaction_filter: dict = {
            "session_id": session_id,
            "student_id": student_id,
        }
        if itype:
            interaction_filter["interaction_type"] = itype
        # For skill events, narrow to the skill sub-category.
        if event_type == EventType.SKILL_RECORDED.value:
            interaction_filter["behaviour_category"] = BehaviourCategory.SKILL.value

        candidate_interactions = await gd_find(
            self.session,
            "session_interactions",
            interaction_filter,
            order_by="recorded_at",
            desc_order=True,
            limit=50,
        )

        # Pick the first non-reversed one (most recent matching row).
        target_interaction = None
        for ci in candidate_interactions:
            ci_data = ci.get("data") or ci.get("metadata") or {}
            if ci_data.get("reversed"):
                continue
            target_interaction = ci
            break

        # Prefer the deterministic interaction_id stored in event metadata (written
        # for all new actions after this feature was introduced).  For older events
        # that lack it we fall back to the fuzzy type+student match above.
        if original_meta.get("interaction_id"):
            by_id = await gd_find_one(
                self.session, "session_interactions", {"id": original_meta["interaction_id"]}
            )
            if by_id:
                target_interaction = by_id

        if target_interaction:
            existing_data = target_interaction.get("data") or {}
            new_data = {**existing_data, "reversed": True, "reversed_at": now.isoformat(), "reversed_event_id": event_id}
            await gd_update_one(
                self.session,
                "session_interactions",
                {"id": target_interaction["id"]},
                {"data": new_data},
            )

        # For skill events: also mark the student_skills record so skill counts
        # in session summaries and live metrics stay accurate after undo.
        if event_type == EventType.SKILL_RECORDED.value:
            skill_record_id = original_meta.get("skill_record_id")
            if skill_record_id:
                existing_sk = await gd_find_one(self.session, "student_skills", {"id": skill_record_id})
                if existing_sk:
                    await gd_update_one(
                        self.session,
                        "student_skills",
                        {"id": skill_record_id},
                        {"is_reversed": True, "reversed_at": now.isoformat()},
                    )
            else:
                # Fallback: find the most recent non-reversed skill for this student/session
                skill_candidates = await gd_find(
                    self.session,
                    "student_skills",
                    {"session_id": session_id, "student_id": student_id},
                    order_by="timestamp",
                    desc_order=True,
                    limit=20,
                )
                for sk in skill_candidates:
                    if sk.get("is_reversed"):
                        continue
                    await gd_update_one(
                        self.session,
                        "student_skills",
                        {"id": sk["id"]},
                        {"is_reversed": True, "reversed_at": now.isoformat()},
                    )
                    break

        # 5. Compensate score if the original action was point-bearing.
        student_name = "الطالب"
        if student_id:
            st = await gd_find_one(self.session, "students", {"id": student_id, "is_active": True})
            if st:
                student_name = st.get("full_name") or student_name

        if original_score_change != 0 and student_id:
            compensating_change = -original_score_change
            today = now.strftime("%Y-%m-%d")
            week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
            month = now.strftime("%Y-%m")

            school_id = None
            if student_id:
                st_row = await gd_find_one(self.session, "students", {"id": student_id, "is_active": True})
                school_id = st_row.get("school_id") if st_row else None

            compensating_ledger = {
                "id": str(uuid.uuid4()),
                "student_id": student_id,
                "school_id": school_id,
                "score_change": compensating_change,
                "category": "undo",
                "description": f"تراجع: عكس إجراء ({event_type})",
                "date": today,
                "week": week_start,
                "month": month,
                "created_at": now.isoformat(),
            }
            await gd_insert(self.session, "student_score_ledger", compensating_ledger)

            # Adjust the daily aggregate.
            existing_daily = await gd_find_one(
                self.session, "student_daily_scores", {"student_id": student_id, "date": today}
            )
            if existing_daily:
                await gd_update_one(
                    self.session,
                    "student_daily_scores",
                    {"student_id": student_id, "date": today},
                    {"score": existing_daily.get("score", 0) + compensating_change},
                )
            else:
                await gd_insert(self.session, "student_daily_scores", {
                    "id": str(uuid.uuid4()),
                    "student_id": student_id,
                    "school_id": school_id,
                    "date": today,
                    "score": compensating_change,
                    "created_at": now.isoformat(),
                })

        # 6. Mark the original event as reversed so it is skipped on future calls.
        updated_meta = {**original_meta, "reversed": True, "reversed_at": now.isoformat()}
        await gd_update_one(
            self.session,
            "session_event_log",
            {"id": event_id},
            {"metadata": updated_meta},
        )

        # 7. Write a dedicated reversal event to the log.
        await self._log_event(
            session_id=session_id,
            event_type="action_reversed",
            actor_id=teacher_id,
            student_id=student_id,
            old_value=event_type,
            new_value="reversed",
            metadata={
                "reversed_event_id": event_id,
                "original_event_type": event_type,
                "original_score_change": original_score_change,
                "compensating_change": -original_score_change if original_score_change else 0,
                "student_name": student_name,
            },
        )

        return {
            "message": "تم التراجع عن الإجراء بنجاح",
            "reversed_event_type": event_type,
            "student_id": student_id,
            "student_name": student_name,
            "score_restored": -original_score_change if original_score_change else 0,
        }

    # ---------- Seating Order ----------

    async def update_seating_order(
        self,
        session_id: str,
        student_order: List[str],
        teacher_id: str = None
    ) -> Dict[str, Any]:
        """Update student seating order for current session"""
        await gd_update_one(self.session, "class_sessions",
            {"id": session_id},
            {"seating_order": student_order}
        )
        if teacher_id:
            await self._log_event(
                session_id=session_id,
                event_type=EventType.SEATING_UPDATED.value,
                actor_id=teacher_id,
                metadata={"student_count": len(student_order)}
            )
        return {"message": "تم حفظ ترتيب الجلوس"}


# ============== SKILLS SEED DATA ==============

DEFAULT_SKILLS_TYPES = [
    {"id": "skill-leadership", "name": "Leadership", "name_ar": "قيادة", "description": "القدرة على توجيه الآخرين", "category": "social"},
    {"id": "skill-cooperation", "name": "Cooperation", "name_ar": "تعاون", "description": "العمل الجماعي والتعاون مع الزملاء", "category": "social"},
    {"id": "skill-initiative", "name": "Initiative", "name_ar": "مبادرة", "description": "المبادرة والتقدم ذاتياً", "category": "personal"},
    {"id": "skill-creativity", "name": "Creativity", "name_ar": "إبداع", "description": "التفكير الإبداعي والابتكار", "category": "cognitive"},
    {"id": "skill-critical-thinking", "name": "Critical Thinking", "name_ar": "تفكير نقدي", "description": "التحليل والتفكير النقدي", "category": "cognitive"},
    {"id": "skill-responsibility", "name": "Responsibility", "name_ar": "مسؤولية", "description": "تحمل المسؤولية والالتزام", "category": "personal"},
    {"id": "skill-communication", "name": "Communication", "name_ar": "تواصل", "description": "مهارات التواصل الفعّال", "category": "social"},
    {"id": "skill-problem-solving", "name": "Problem Solving", "name_ar": "حل مشكلات", "description": "القدرة على حل المشكلات", "category": "cognitive"},
    {"id": "skill-time-management", "name": "Time Management", "name_ar": "إدارة الوقت", "description": "تنظيم الوقت والالتزام بالمواعيد", "category": "personal"},
    {"id": "skill-teamwork", "name": "Teamwork", "name_ar": "عمل جماعي", "description": "المشاركة الفعالة في الفريق", "category": "social"},
]


# ============== BEHAVIOUR CATEGORIES DATA ==============

DEFAULT_BEHAVIOUR_TYPES = {
    "skill": [
        {"id": "leadership", "name_ar": "قيادة", "name_en": "Leadership", "score": 3},
        {"id": "cooperation", "name_ar": "تعاون", "name_en": "Cooperation", "score": 2},
        {"id": "initiative", "name_ar": "مبادرة", "name_en": "Initiative", "score": 3},
    ],
    "positive": [
        {"id": "respect", "name_ar": "احترام", "name_en": "Respect", "score": 2},
        {"id": "commitment", "name_ar": "التزام", "name_en": "Commitment", "score": 2},
        {"id": "helping_others", "name_ar": "مساعدة الآخرين", "name_en": "Helping Others", "score": 2},
    ],
    "negative": [
        {"id": "disruption", "name_ar": "إزعاج", "name_en": "Disruption", "score": -2},
        {"id": "non_compliance", "name_ar": "عدم التزام", "name_en": "Non-compliance", "score": -2},
        {"id": "interruption", "name_ar": "مقاطعة التعليمات", "name_en": "Interruption", "score": -1},
    ]
}
