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
    top_participants: List[Dict[str, Any]]
    needs_attention: List[Dict[str, Any]]


# ============== SCORE RULES ==============

SCORE_RULES = {
    # Answer scores
    "correct_answer": 5,
    "no_answer_after_selection": -1,
    
    # Participation scores
    "active_participation": 2,
    "initiative": 2,
    "inactive": 0,
    "refused": -1,
    
    # Positive behaviour scores
    "respect": 2,
    "commitment": 2,
    "helping_others": 2,
    "special_skill": 3,
    "leadership": 3,
    
    # Negative behaviour scores
    "disruption": -2,
    "non_compliance": -2,
    "interruption": -1,
    "late_to_class": -2,
    "medium_violation": -4,
    "high_violation": -8,
    
    # Attendance scores
    "present": 1,
    "absent_no_excuse": -3,
    "excused": 0,
    "late": -1,
    
    # Bonus scores
    "three_correct_streak": 5,
    "no_negative_week": 10,
    "full_attendance_month": 15,
    "top_3_weekly": 10,
}

STUDENT_LEVELS = {
    "needs_attention": (0, 19),
    "acceptable": (20, 39),
    "good": (40, 59),
    "excellent": (60, 79),
    "star": (80, float('inf'))
}


# ============== SESSION ENGINE CLASS ==============

class TeacherSessionEngine:
    """
    Main engine for managing teacher class sessions.
    All data operations go through the database.
    """
    
    def __init__(self, db):
        self.db = db
        
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
        await self.db.session_event_log.insert_one(event)
        return event

    async def validate_session_start(self, teacher_id: str, schedule_session_id: str, force_new: bool = False) -> Dict[str, Any]:
        """
        Validate if a session can be started.
        Returns schedule_session dict with optional 'existing_active_session' key
        if there's already a running session to resume.
        If force_new=True, auto-complete any existing sessions and allow a fresh start.
        """
        schedule_session = await self.db.schedule_sessions.find_one(
            {"id": schedule_session_id}, {"_id": 0}
        )
        if not schedule_session:
            schedule_session = await self.db.timetable_sessions.find_one(
                {"id": schedule_session_id}, {"_id": 0}
            )

        if not schedule_session:
            schedule_session = {"id": schedule_session_id, "teacher_id": teacher_id}

        if schedule_session.get("teacher_id") and schedule_session.get("teacher_id") != teacher_id:
            raise HTTPException(status_code=403, detail="هذه الحصة ليست مخصصة لك")

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now = datetime.now(timezone.utc)

        active_sessions = self.db.class_sessions.find({
            "teacher_id": teacher_id,
            "status": {"$in": self.ACTIVE_STATUSES}
        })
        async for active_session in active_sessions:
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
                        except Exception:
                            pass

            if should_complete:
                await self.db.class_sessions.update_one(
                    {"id": active_session.get("id")},
                    {"$set": {"status": SessionStatus.COMPLETED.value, "ended_at": now.isoformat()}}
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
            class_info = await self.db.classes.find_one({"id": ex_class_id}, {"_id": 0, "name": 1})
            subject_info = await self.db.subjects.find_one({"id": ex_subject_id}, {"_id": 0, "name_ar": 1, "name": 1})
            students = await self.db.students.find(
                {"class_id": ex_class_id, "is_active": True}, {"_id": 0}
            ).to_list(100)
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
        teacher = await self.db.teachers.find_one({"id": teacher_id}, {"_id": 0})
        if not teacher:
            # Try to find from users
            user = await self.db.users.find_one({"teacher_id": teacher_id}, {"_id": 0})
            teacher = {"full_name": user.get("full_name") if user else "معلم"}
        
        # Get class info
        class_info = await self.db.classes.find_one({"id": class_id}, {"_id": 0})
        class_name = class_info.get("name", "فصل") if class_info else "فصل"
        
        # Get subject info
        subject = await self.db.subjects.find_one({"id": subject_id}, {"_id": 0})
        subject_name = subject.get("name_ar") or subject.get("name") or "مادة" if subject else "مادة"
        
        # Get students in this class
        students = await self.db.students.find(
            {"class_id": class_id, "is_active": True},
            {"_id": 0}
        ).to_list(100)
        
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
        
        await self.db.class_sessions.insert_one(session_record)

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
            await self.db.session_attendance.insert_many(attendance_drafts)
        
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
        session = await self.db.class_sessions.find_one({"id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
        
        # Get attendance records
        attendance_records = await self.db.session_attendance.find(
            {"session_id": session_id},
            {"_id": 0}
        ).to_list(200)
        
        attendance_map = {a["student_id"]: a for a in attendance_records}
        
        # Get students
        students = await self.db.students.find(
            {"class_id": session["class_id"], "is_active": True},
            {"_id": 0}
        ).to_list(200)
        
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
        
        result = await self.db.session_attendance.update_one(
            {"session_id": session_id, "student_id": student_id},
            {
                "$set": {
                    "status": status.value,
                    "is_draft": True,
                    "updated_by": teacher_id,
                    "updated_at": now.isoformat()
                }
            }
        )
        
        if result.modified_count == 0:
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
        records = await self.db.session_attendance.find(
            {"session_id": session_id},
            {"_id": 0}
        ).to_list(200)
        
        if not records:
            raise HTTPException(status_code=404, detail="لا توجد سجلات حضور")
        
        # Update all to final
        await self.db.session_attendance.update_many(
            {"session_id": session_id},
            {
                "$set": {
                    "is_draft": False,
                    "approved_by": teacher_id,
                    "approved_at": now.isoformat()
                }
            }
        )
        
        await self.db.class_sessions.update_one(
            {"id": session_id},
            {"$set": {
                "attendance_approved": True,
                "status": SessionStatus.TEACHING_IN_PROGRESS.value,
                "attendance_approved_at": now.isoformat()
            }}
        )

        # Calculate attendance scores
        for record in records:
            score_change = 0
            if record["status"] == AttendanceStatus.PRESENT.value:
                score_change = SCORE_RULES["present"]
            elif record["status"] == AttendanceStatus.ABSENT.value:
                score_change = SCORE_RULES["absent_no_excuse"]
            elif record["status"] == AttendanceStatus.LATE.value:
                score_change = SCORE_RULES["late"]
            elif record["status"] == AttendanceStatus.EXCUSED.value:
                score_change = SCORE_RULES["excused"]
            
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
        await self.db.class_sessions.update_one(
            {"id": session_id},
            {"$set": {
                "interaction_mode": mode,
                "status": SessionStatus.INTERACTION_RUNNING.value
            }}
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
        session = await self.db.class_sessions.find_one({"id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
        
        # Get present students only
        attendance = await self.db.session_attendance.find(
            {"session_id": session_id, "status": AttendanceStatus.PRESENT.value},
            {"_id": 0}
        ).to_list(200)
        
        if not attendance:
            raise HTTPException(status_code=400, detail="لا يوجد طلاب حاضرين")
        
        present_student_ids = [a["student_id"] for a in attendance]
        
        # Get interaction history for this session
        interactions = await self.db.session_interactions.find(
            {"session_id": session_id, "interaction_type": InteractionType.QUESTION.value},
            {"_id": 0}
        ).to_list(500)
        
        # Count selections per student
        selection_counts = {}
        last_selection_order = {}
        for i, interaction in enumerate(interactions):
            sid = interaction["student_id"]
            selection_counts[sid] = selection_counts.get(sid, 0) + 1
            last_selection_order[sid] = i
        
        # Calculate selection weights (lower = more likely to be selected)
        weights = []
        for sid in present_student_ids:
            count = selection_counts.get(sid, 0)
            last_order = last_selection_order.get(sid, -1)
            
            # Weight formula: fewer selections = lower weight = higher chance
            # Recently selected students get higher weight (lower chance)
            weight = count * 10 + (last_order + 1) * 0.5
            weights.append((sid, weight))
        
        # Sort by weight (ascending) and select from bottom third
        weights.sort(key=lambda x: x[1])
        selection_pool = weights[:max(len(weights) // 3, 1)]
        
        # Random selection from pool
        selected_id = random.choice(selection_pool)[0]
        
        # Get student info
        student = await self.db.students.find_one({"id": selected_id}, {"_id": 0})
        
        # Get participation count in this session
        participation_count = selection_counts.get(selected_id, 0)
        
        session = await self.db.class_sessions.find_one({"id": session_id}, {"_id": 0, "teacher_id": 1})
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
            "interaction_type": InteractionType.QUESTION.value,
            "answer_result": result.value,
            "recorded_by": teacher_id,
            "recorded_at": now.isoformat()
        }
        
        await self.db.session_interactions.insert_one(interaction)
        
        # Calculate score
        score_change = 0
        if result == AnswerResult.CORRECT:
            score_change = SCORE_RULES["correct_answer"]
            
            # Check for streak bonus
            streak = await self._check_answer_streak(session_id, student_id)
            if streak >= 3:
                score_change += SCORE_RULES["three_correct_streak"]
                # TODO: Send notification to parent
                
        elif result == AnswerResult.NO_ANSWER:
            score_change = SCORE_RULES["no_answer_after_selection"]
        
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
            metadata={"score_change": score_change}
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
            "interaction_type": InteractionType.PARTICIPATION.value,
            "participation_type": participation_type.value,
            "recorded_by": teacher_id,
            "recorded_at": now.isoformat()
        }
        
        await self.db.session_interactions.insert_one(interaction)
        
        # Calculate score
        score_change = 0
        if participation_type == ParticipationType.ACTIVE:
            score_change = SCORE_RULES["active_participation"]
        elif participation_type == ParticipationType.INITIATIVE:
            score_change = SCORE_RULES["initiative"]
        elif participation_type == ParticipationType.REFUSED:
            score_change = SCORE_RULES.get("refused", -1)
        
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
            metadata={"score_change": score_change}
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
            "interaction_type": InteractionType.BEHAVIOUR.value,
            "behaviour_category": category.value,
            "behaviour_type": behaviour_type,
            "behaviour_details": details,  # Only visible to admin
            "recorded_by": teacher_id,
            "recorded_at": now.isoformat(),
            "editable_until": (now + timedelta(hours=1)).isoformat()
        }
        
        await self.db.session_interactions.insert_one(interaction)
        
        # Calculate score based on behaviour type
        score_change = 0
        if category == BehaviourCategory.POSITIVE:
            score_change = SCORE_RULES.get(behaviour_type, 2)
        elif category == BehaviourCategory.NEGATIVE:
            score_change = SCORE_RULES.get(behaviour_type, -2)
        elif category == BehaviourCategory.SKILL:
            score_change = SCORE_RULES.get("special_skill", 3)
        
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
            metadata={"score_change": score_change, "details": details}
        )

        return {
            "message": "تم تسجيل السلوك",
            "category": category.value,
            "type": behaviour_type,
            "score_change": score_change
        }
    
    # ---------- Session Review & End ----------

    async def get_review_preview(self, session_id: str, teacher_id: str) -> SessionReviewPreview:
        """Get session review data without ending the session (Section 7.5-7.8)"""
        now = datetime.now(timezone.utc)

        session = await self.db.class_sessions.find_one({"id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

        start_time = datetime.fromisoformat(session["start_time"].replace("Z", "+00:00"))
        duration = (now - start_time).total_seconds() / 60

        attendance = await self.db.session_attendance.find(
            {"session_id": session_id}, {"_id": 0}
        ).to_list(200)

        present = sum(1 for a in attendance if a["status"] == AttendanceStatus.PRESENT.value)
        absent = sum(1 for a in attendance if a["status"] == AttendanceStatus.ABSENT.value)
        late = sum(1 for a in attendance if a["status"] == AttendanceStatus.LATE.value)
        excused = sum(1 for a in attendance if a["status"] == AttendanceStatus.EXCUSED.value)
        total = len(attendance)
        attendance_approved = session.get("attendance_approved", False)

        interactions = await self.db.session_interactions.find(
            {"session_id": session_id}, {"_id": 0}
        ).to_list(500)

        questions = [i for i in interactions if i.get("interaction_type") == InteractionType.QUESTION.value]
        correct = sum(1 for q in questions if q.get("answer_result") == AnswerResult.CORRECT.value)
        wrong = sum(1 for q in questions if q.get("answer_result") == AnswerResult.WRONG.value)

        participations = [i for i in interactions if i.get("interaction_type") == InteractionType.PARTICIPATION.value]
        participants = set(p["student_id"] for p in participations)
        participation_rate = len(participants) / present * 100 if present > 0 else 0

        behaviours = [i for i in interactions if i.get("interaction_type") == InteractionType.BEHAVIOUR.value]
        positive_behaviours = sum(1 for b in behaviours if b.get("behaviour_category") == BehaviourCategory.POSITIVE.value)
        negative_behaviours = sum(1 for b in behaviours if b.get("behaviour_category") == BehaviourCategory.NEGATIVE.value)

        skills_recorded = await self.db.student_skills.count_documents({"session_id": session_id})
        skills_students = await self.db.student_skills.distinct("student_id", {"session_id": session_id})

        notes_count = await self.db.session_notes.count_documents({"session_id": session_id})
        teacher_notes = await self.db.session_notes.count_documents({
            "session_id": session_id,
            "note_type": "session"
        })

        student_interactions = {}
        for i in interactions:
            sid = i["student_id"]
            if sid not in student_interactions:
                student_interactions[sid] = {"correct": 0, "participation": 0}
            if i.get("answer_result") == AnswerResult.CORRECT.value:
                student_interactions[sid]["correct"] += 1
            if i.get("interaction_type") == InteractionType.PARTICIPATION.value:
                student_interactions[sid]["participation"] += 1

        sorted_students = sorted(
            student_interactions.items(),
            key=lambda x: x[1]["correct"] * 2 + x[1]["participation"],
            reverse=True
        )

        top_participants = []
        for sid, st in sorted_students[:3]:
            student = await self.db.students.find_one({"id": sid}, {"_id": 0})
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
                student = await self.db.students.find_one({"id": sid}, {"_id": 0, "full_name": 1})
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
                student = await self.db.students.find_one({"id": sid}, {"_id": 0, "full_name": 1})
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
        except Exception:
            pass

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
        
        session = await self.db.class_sessions.find_one({"id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

        session_teacher = session.get("teacher_id")
        if session_teacher and session_teacher != teacher_id:
            user_record = await self.db.users.find_one({"id": teacher_id}, {"_id": 0, "teacher_id": 1})
            actual_teacher_id = user_record.get("teacher_id") if user_record else None
            if session_teacher != actual_teacher_id:
                raise HTTPException(status_code=403, detail="لا يمكنك إنهاء حصة لست مسؤولاً عنها")

        if session.get("status") == SessionStatus.COMPLETED.value:
            return await self._get_completed_session_summary(session, session_id, now)

        attendance_approved = session.get("attendance_approved", False)
        attendance_records = await self.db.session_attendance.find({"session_id": session_id}, {"_id": 0}).to_list(200)
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
        
        interactions = await self.db.session_interactions.find(
            {"session_id": session_id}, {"_id": 0}
        ).to_list(500)
        
        questions = [i for i in interactions if i.get("interaction_type") == InteractionType.QUESTION.value]
        correct = sum(1 for q in questions if q.get("answer_result") == AnswerResult.CORRECT.value)
        wrong = sum(1 for q in questions if q.get("answer_result") == AnswerResult.WRONG.value)
        
        participations = [i for i in interactions if i.get("interaction_type") == InteractionType.PARTICIPATION.value]
        participants = set(p["student_id"] for p in participations)
        participation_rate = len(participants) / present * 100 if present > 0 else 0
        
        behaviours = [i for i in interactions if i.get("interaction_type") == InteractionType.BEHAVIOUR.value]
        positive_behaviours = sum(1 for b in behaviours if b.get("behaviour_category") == BehaviourCategory.POSITIVE.value)
        negative_behaviours = sum(1 for b in behaviours if b.get("behaviour_category") == BehaviourCategory.NEGATIVE.value)
        
        skills_recorded = await self.db.student_skills.count_documents({"session_id": session_id})
        
        student_interactions = {}
        for i in interactions:
            sid = i["student_id"]
            if sid not in student_interactions:
                student_interactions[sid] = {"correct": 0, "participation": 0, "negative": 0, "positive": 0}
            if i.get("answer_result") == AnswerResult.CORRECT.value:
                student_interactions[sid]["correct"] += 1
            if i.get("interaction_type") == InteractionType.PARTICIPATION.value:
                student_interactions[sid]["participation"] += 1
            if i.get("behaviour_category") == BehaviourCategory.NEGATIVE.value:
                student_interactions[sid]["negative"] += 1
            if i.get("behaviour_category") == BehaviourCategory.POSITIVE.value:
                student_interactions[sid]["positive"] += 1
        
        sorted_students = sorted(
            student_interactions.items(),
            key=lambda x: x[1]["correct"] * 2 + x[1]["participation"],
            reverse=True
        )
        
        top_participants = []
        for sid, stats in sorted_students[:3]:
            student = await self.db.students.find_one({"id": sid}, {"_id": 0})
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
                student = await self.db.students.find_one({"id": sid}, {"_id": 0, "full_name": 1})
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
                student = await self.db.students.find_one({"id": sid}, {"_id": 0, "full_name": 1})
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
        await self.db.class_sessions.update_one(
            {"id": session_id},
            {"$set": session_update}
        )

        if closing_note:
            await self.db.session_notes.insert_one({
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
            top_participants=top_participants,
            needs_attention=needs_attention
        )

    async def _get_completed_session_summary(self, session, session_id, now):
        """Return summary for an already-completed session."""
        end_time_str = session.get("ended_at") or session.get("end_time") or now.isoformat()
        try:
            st = datetime.fromisoformat(session["start_time"].replace("Z", "+00:00"))
            et = datetime.fromisoformat(end_time_str.replace("Z", "+00:00")) if isinstance(end_time_str, str) else now
            completed_duration = (et - st).total_seconds() / 60
        except Exception:
            completed_duration = 0
        attendance = await self.db.session_attendance.find({"session_id": session_id}, {"_id": 0}).to_list(200)
        present = sum(1 for a in attendance if a["status"] == AttendanceStatus.PRESENT.value)
        absent = sum(1 for a in attendance if a["status"] == AttendanceStatus.ABSENT.value)
        late = sum(1 for a in attendance if a["status"] == AttendanceStatus.LATE.value)
        excused = sum(1 for a in attendance if a["status"] == AttendanceStatus.EXCUSED.value)
        total = len(attendance)
        interactions = await self.db.session_interactions.find({"session_id": session_id}, {"_id": 0}).to_list(500)
        questions = [i for i in interactions if i.get("interaction_type") == InteractionType.QUESTION.value]
        correct = sum(1 for q in questions if q.get("answer_result") == AnswerResult.CORRECT.value)
        participations = [i for i in interactions if i.get("interaction_type") == InteractionType.PARTICIPATION.value]
        participants_set = set(p["student_id"] for p in participations)
        behaviours = [i for i in interactions if i.get("interaction_type") == InteractionType.BEHAVIOUR.value]
        positive_b = sum(1 for b in behaviours if b.get("behaviour_category") == BehaviourCategory.POSITIVE.value)
        negative_b = sum(1 for b in behaviours if b.get("behaviour_category") == BehaviourCategory.NEGATIVE.value)
        skills_count = await self.db.student_skills.count_documents({"session_id": session_id})
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
            top_participants=[],
            needs_attention=[],
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
            
            update_op = {"$set": update_fields}
            if inc_fields:
                update_op["$inc"] = inc_fields
            
            await self.db.students.update_one(
                {"id": sid, "school_id": school_id},
                update_op
            )

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
        await self.db.session_analytics.insert_one(analytics_record)

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
            await self.db.ai_session_insights.insert_one({
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

    async def _send_smart_end_session_notifications(self, session_id, school_id, attendance, neg_students, student_interactions, now):
        """Send automatic notifications on session end: absence, repeated negative behavior, improvement."""
        notifications_sent = 0
        
        absent_students = [a for a in attendance if a["status"] == AttendanceStatus.ABSENT.value]
        for a_rec in absent_students:
            sid = a_rec["student_id"]
            student = await self.db.students.find_one({"id": sid}, {"_id": 0})
            if not student:
                continue
            parent_user_id = student.get("parent_user_id")
            if not parent_user_id:
                continue
            await self.db.notifications.insert_one({
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
                student = await self.db.students.find_one({"id": sid}, {"_id": 0})
                if not student:
                    continue
                parent_user_id = student.get("parent_user_id")
                recipients = []
                if parent_user_id:
                    recipients.append(parent_user_id)
                principal = await self.db.users.find_one(
                    {"school_id": school_id, "role": {"$in": ["school_admin", "school_principal"]}},
                    {"_id": 0, "id": 1}
                )
                if principal:
                    recipients.append(principal["id"])
                
                for rid in recipients:
                    await self.db.notifications.insert_one({
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
                student = await self.db.students.find_one({"id": sid}, {"_id": 0})
                if not student:
                    continue
                parent_user_id = student.get("parent_user_id")
                if not parent_user_id:
                    continue
                await self.db.notifications.insert_one({
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
        session = await self.db.class_sessions.find_one({"id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

        attendance = await self.db.session_attendance.find({"session_id": session_id}, {"_id": 0}).to_list(200)
        interactions = await self.db.session_interactions.find({"session_id": session_id}, {"_id": 0}).to_list(500)
        notes = await self.db.session_notes.find({"session_id": session_id}, {"_id": 0}).to_list(100)

        student_ids = list(set(
            [a["student_id"] for a in attendance] +
            [i["student_id"] for i in interactions]
        ))
        students_map = {}
        for sid in student_ids:
            s = await self.db.students.find_one({"id": sid}, {"_id": 0, "full_name": 1, "id": 1})
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
        except Exception:
            pass

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
            student = await self.db.students.find_one({"id": student_id}, {"_id": 0, "school_id": 1})
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
        
        await self.db.student_score_ledger.insert_one(ledger_entry)
        
        await self.db.student_daily_scores.update_one(
            {"student_id": student_id, "date": today},
            {
                "$inc": {"score": score_change},
                "$setOnInsert": {
                    "id": str(uuid.uuid4()),
                    "student_id": student_id,
                    "school_id": school_id,
                    "date": today,
                    "created_at": now.isoformat()
                }
            },
            upsert=True
        )
    
    async def _check_answer_streak(self, session_id: str, student_id: str) -> int:
        """Check consecutive correct answers for a student in current session"""
        interactions = await self.db.session_interactions.find(
            {
                "session_id": session_id,
                "student_id": student_id,
                "interaction_type": InteractionType.QUESTION.value
            },
            {"_id": 0}
        ).sort("recorded_at", -1).to_list(10)
        
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
        student = await self.db.students.find_one({"id": student_id}, {"_id": 0})
        if not student:
            raise HTTPException(status_code=404, detail="الطالب غير موجود")
        
        # Get daily score
        daily = await self.db.student_daily_scores.find_one(
            {"student_id": student_id, "date": today},
            {"_id": 0}
        )
        daily_score = daily.get("score", 0) if daily else 0
        
        # Get weekly score
        weekly_scores = await self.db.student_score_ledger.find(
            {"student_id": student_id, "week": week_start},
            {"_id": 0}
        ).to_list(500)
        weekly_score = sum(s.get("score_change", 0) for s in weekly_scores)
        
        # Get monthly score
        monthly_scores = await self.db.student_score_ledger.find(
            {"student_id": student_id, "month": month},
            {"_id": 0}
        ).to_list(1000)
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
        
        # Determine level
        level = StudentLevel.NEEDS_ATTENTION
        for level_name, (min_score, max_score) in STUDENT_LEVELS.items():
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
            recent_achievements=[]  # TODO: Get from achievements table
        )
    
    # ---------- Skill Recording ----------

    async def record_skill(
        self,
        session_id: str,
        student_id: str,
        skill_type_id: str,
        teacher_id: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record a skill observation for a student during a session"""
        now = datetime.now(timezone.utc)

        session = await self.db.class_sessions.find_one({"id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

        skill_type = await self.db.skills_types.find_one({"id": skill_type_id}, {"_id": 0})
        if not skill_type:
            raise HTTPException(status_code=404, detail="نوع المهارة غير موجود")

        student = await self.db.students.find_one({"id": student_id}, {"_id": 0})
        if not student:
            raise HTTPException(status_code=404, detail="الطالب غير موجود")

        if student.get("class_id") != session.get("class_id"):
            raise HTTPException(status_code=400, detail="الطالب لا ينتمي لهذا الفصل")

        skill_record = {
            "id": str(uuid.uuid4()),
            "student_id": student_id,
            "class_id": session.get("class_id"),
            "session_id": session_id,
            "skill_type_id": skill_type_id,
            "skill_name": skill_type.get("name_ar", skill_type.get("name")),
            "recorded_by_teacher": teacher_id,
            "notes": notes,
            "timestamp": now.isoformat(),
            "school_id": student.get("school_id")
        }
        await self.db.student_skills.insert_one(skill_record)

        interaction = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "student_id": student_id,
            "interaction_type": InteractionType.BEHAVIOUR.value,
            "behaviour_category": BehaviourCategory.SKILL.value,
            "behaviour_type": skill_type_id,
            "behaviour_details": notes,
            "recorded_by": teacher_id,
            "recorded_at": now.isoformat(),
            "editable_until": (now + timedelta(hours=1)).isoformat()
        }
        await self.db.session_interactions.insert_one(interaction)

        score_change = SCORE_RULES.get("special_skill", 3)
        await self._update_student_score(
            student_id,
            score_change,
            "skill",
            f"مهارة: {skill_type.get('name_ar', skill_type.get('name'))}"
        )

        await self._log_event(
            session_id=session_id,
            event_type=EventType.SKILL_RECORDED.value,
            actor_id=teacher_id,
            student_id=student_id,
            new_value=skill_type_id,
            metadata={"score_change": score_change, "skill_name": skill_type.get("name_ar", skill_type.get("name"))}
        )

        return {
            "message": "تم تسجيل المهارة",
            "skill_name": skill_type.get("name_ar", skill_type.get("name")),
            "score_change": score_change,
            "skill_record_id": skill_record["id"]
        }

    # ---------- Activity Log ----------

    async def get_activity_log(self, session_id: str, limit: int = 50) -> list:
        """Fetch session interactions formatted as activity log entries"""
        interactions = await self.db.session_interactions.find(
            {"session_id": session_id}, {"_id": 0}
        ).sort("recorded_at", -1).to_list(limit)

        if not interactions:
            return []

        student_ids = list(set(i["student_id"] for i in interactions if i.get("student_id")))
        students = {}
        if student_ids:
            student_docs = await self.db.students.find(
                {"id": {"$in": student_ids}}, {"_id": 0, "id": 1, "full_name": 1}
            ).to_list(len(student_ids))
            students = {s["id"]: s.get("full_name", "طالب") for s in student_docs}

        skill_ids = [i.get("behaviour_type") for i in interactions
                     if i.get("behaviour_category") == "skill" and i.get("behaviour_type")]
        skill_names = {}
        if skill_ids:
            skill_docs = await self.db.skill_types.find(
                {"id": {"$in": skill_ids}}, {"_id": 0, "id": 1, "name_ar": 1, "name": 1}
            ).to_list(len(skill_ids))
            skill_names = {s["id"]: s.get("name_ar", s.get("name", "مهارة")) for s in skill_docs}

        events = await self.db.session_event_log.find(
            {"session_id": session_id,
             "event_type": {"$in": ["answer_recorded", "participation_recorded",
                                     "behaviour_recorded", "skill_recorded"]}},
            {"_id": 0, "student_id": 1, "event_type": 1, "metadata": 1, "timestamp": 1}
        ).sort("timestamp", -1).to_list(limit)
        score_map = {}
        for e in events:
            key = f"{e.get('student_id')}_{e.get('event_type')}_{e.get('timestamp','')[:19]}"
            score_map[key] = e.get("metadata", {}).get("score_change", 0)

        log_entries = []
        for i in interactions:
            itype = i.get("interaction_type")
            student_name = students.get(i.get("student_id"), "طالب")
            first_name = student_name.split(" ")[0] if student_name else "طالب"
            recorded_at = i.get("recorded_at", "")

            evt_key_prefix = f"{i.get('student_id')}_"
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
            except Exception:
                time_str = ""

            log_entries.append({
                "id": i.get("id", ""),
                "emoji": emoji,
                "text": text,
                "color": color,
                "time": time_str,
            })

        return log_entries

    # ---------- Class Metrics ----------

    async def get_class_metrics(self, teacher_id: str, class_id: str) -> Dict[str, Any]:
        """Get real metrics for a teacher's class from session data"""
        sessions = await self.db.class_sessions.find(
            {"class_id": class_id, "teacher_id": teacher_id},
            {"_id": 0}
        ).to_list(500)

        total_students = await self.db.students.count_documents({"class_id": class_id, "is_active": True})

        total_attendance = 0
        total_present = 0
        total_participation_events = 0
        total_present_in_sessions = 0
        total_correct = 0
        total_questions = 0
        completed_sessions = [s for s in sessions if s.get("status") == SessionStatus.COMPLETED.value]

        for s in completed_sessions:
            att_records = await self.db.session_attendance.find(
                {"session_id": s["id"]}, {"_id": 0}
            ).to_list(200)
            present = sum(1 for a in att_records if a.get("status") == AttendanceStatus.PRESENT.value)
            total_attendance += len(att_records)
            total_present += present

            interactions = await self.db.session_interactions.find(
                {"session_id": s["id"]}, {"_id": 0}
            ).to_list(500)
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
        in_progress = await self.db.class_sessions.find_one(
            {"class_id": class_id, "teacher_id": teacher_id, "status": SessionStatus.IN_PROGRESS.value},
            {"_id": 0}
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
        await self.db.session_notes.insert_one(note)

        await self._log_event(
            session_id=session_id,
            event_type=EventType.NOTE_ADDED.value,
            actor_id=teacher_id,
            student_id=student_id,
            metadata={"note_type": note_type, "note_id": note["id"]}
        )

        return {"message": "تم إضافة الملاحظة", "note_id": note["id"], "note": {k: v for k, v in note.items() if k != "_id"}}

    async def get_session_notes(self, session_id: str) -> List[Dict[str, Any]]:
        notes = await self.db.session_notes.find(
            {"session_id": session_id},
            {"_id": 0}
        ).sort("created_at", -1).to_list(500)

        for note in notes:
            if note.get("student_id"):
                student = await self.db.students.find_one({"id": note["student_id"]}, {"_id": 0, "full_name": 1})
                note["student_name"] = student.get("full_name") if student else None
        return notes

    async def delete_note(self, note_id: str, teacher_id: str) -> Dict[str, Any]:
        result = await self.db.session_notes.delete_one({"id": note_id, "teacher_id": teacher_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="الملاحظة غير موجودة")
        return {"message": "تم حذف الملاحظة"}

    # ---------- Live Metrics ----------

    async def get_live_metrics(self, session_id: str) -> Dict[str, Any]:
        session = await self.db.class_sessions.find_one({"id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

        attendance = await self.db.session_attendance.find(
            {"session_id": session_id}, {"_id": 0}
        ).to_list(200)

        interactions = await self.db.session_interactions.find(
            {"session_id": session_id}, {"_id": 0}
        ).to_list(1000)

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

        skills_count = await self.db.student_skills.count_documents({"session_id": session_id})
        notes_count = await self.db.session_notes.count_documents({"session_id": session_id})

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
        query = {"teacher_id": teacher_id}
        if status_filter:
            query["status"] = status_filter

        total = await self.db.class_sessions.count_documents(query)
        sessions = await self.db.class_sessions.find(
            query, {"_id": 0}
        ).sort("created_at", -1).skip((page - 1) * limit).limit(limit).to_list(limit)

        enriched = []
        for s in sessions:
            class_info = await self.db.classes.find_one({"id": s.get("class_id")}, {"_id": 0, "name": 1})
            subject = await self.db.subjects.find_one({"id": s.get("subject_id")}, {"_id": 0, "name_ar": 1, "name": 1})

            att_count = await self.db.session_attendance.count_documents({"session_id": s["id"]})
            present_count = await self.db.session_attendance.count_documents(
                {"session_id": s["id"], "status": AttendanceStatus.PRESENT.value}
            )
            interaction_count = await self.db.session_interactions.count_documents({"session_id": s["id"]})

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
        session = await self.db.class_sessions.find_one({"id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

        class_info = await self.db.classes.find_one({"id": session.get("class_id")}, {"_id": 0})
        subject = await self.db.subjects.find_one({"id": session.get("subject_id")}, {"_id": 0})
        teacher = await self.db.teachers.find_one({"id": session.get("teacher_id")}, {"_id": 0})

        attendance = await self.db.session_attendance.find(
            {"session_id": session_id}, {"_id": 0}
        ).to_list(200)

        interactions = await self.db.session_interactions.find(
            {"session_id": session_id}, {"_id": 0}
        ).to_list(1000)

        notes = await self.db.session_notes.find(
            {"session_id": session_id}, {"_id": 0}
        ).to_list(500)

        skills = await self.db.student_skills.find(
            {"session_id": session_id}, {"_id": 0}
        ).to_list(200)

        events = await self.db.session_event_log.find(
            {"session_id": session_id}, {"_id": 0}
        ).sort("timestamp", 1).to_list(1000)

        student_details = {}
        for att in attendance:
            sid = att["student_id"]
            student = await self.db.students.find_one({"id": sid}, {"_id": 0, "full_name": 1})
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
                student = await self.db.students.find_one({"id": sid}, {"_id": 0, "full_name": 1})
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
        events = await self.db.session_event_log.find(
            {"session_id": session_id}, {"_id": 0}
        ).sort("timestamp", -1).to_list(limit)
        return events

    # ---------- Auto-Close Stale Sessions ----------

    async def auto_close_stale_sessions(self, max_duration_hours: int = 4) -> Dict[str, Any]:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_duration_hours)).isoformat()
        stale = await self.db.class_sessions.find({
            "status": {"$in": self.ACTIVE_STATUSES},
            "start_time": {"$lt": cutoff}
        }, {"_id": 0}).to_list(100)

        closed_count = 0
        for session in stale:
            try:
                await self.end_session(session["id"], session.get("teacher_id", "system"))
                closed_count += 1
            except Exception:
                await self.db.class_sessions.update_one(
                    {"id": session["id"]},
                    {"$set": {"status": SessionStatus.COMPLETED.value, "end_time": datetime.now(timezone.utc).isoformat(), "auto_closed": True}}
                )
                closed_count += 1

        return {"message": f"تم إغلاق {closed_count} حصة متروكة", "closed_count": closed_count}

    # ---------- Seating Order ----------
    
    async def update_seating_order(
        self,
        session_id: str,
        student_order: List[str],
        teacher_id: str = None
    ) -> Dict[str, Any]:
        """Update student seating order for current session"""
        await self.db.class_sessions.update_one(
            {"id": session_id},
            {"$set": {"seating_order": student_order}}
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
