"""
NASSAQ Route Module: Teacher, student, parent dashboards, contact teacher
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Body, Request
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
import uuid

# Task #473 — Audit of role_dashboards_mod.py:
# Credential / session helpers (hash_password, verify_password,
# create_access_token, JWT_*, security, ACCESS_TOKEN_EXPIRE) are
# intentionally NOT imported here. The legacy PUT /users/{user_id}/password
# handler that referenced an unbound `pwd_context` (Task #470) was a symptom
# of those primitives being available in this catch-all router. Any new
# password change, role flip, account-state change, or credential-mint
# surface MUST live in auth_routes_mod.py / user_routes_mod.py where the
# canonical MFA, audit, and session-revocation side-effects are enforced.
from dependencies import (
    db, get_current_user, require_roles, UserRole, logger,
    audit_engine, AuditAction,
    session_engine,
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_count, gd_delete_one, _gd_aggregate


from shared_models import (
    SessionStatusEnum, ScheduleStatusEnum
)

router = APIRouter()


# ----- Task #145 — shared teacher-schedule resolver --------------------------
# Resolves the single latest *published* schedule for a teacher's school and
# returns enriched session rows with class/subject/slot details bulk-fetched
# in a single query each (no per-session N+1 lookups). Used by both
# ``GET /teacher/schedule/{teacher_id}`` and the schedule block inside
# ``GET /teacher/dashboard/{teacher_id}`` so the two paths can never disagree
# on which schedule is "current". Drafts and archived rows are intentionally
# excluded — only ``status == "published"`` is considered.
_DAY_ORDER = {"sunday": 0, "monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4, "friday": 5, "saturday": 6}


async def _latest_published_timetable(school_id: str) -> Optional[dict]:
    if not school_id:
        return None
    # Order: published_at desc, then updated_at desc as tiebreaker. We have
    # to do the secondary sort in Python because gd_find only takes one
    # order_by key.
    rows = await gd_find(
        db.session, "timetables",
        {"school_id": school_id, "status": "published"},
        order_by="published_at", desc_order=True, limit=10,
    )
    if not rows:
        return None
    rows.sort(key=lambda r: (r.get("published_at") or "", r.get("updated_at") or ""), reverse=True)
    return rows[0]


async def _latest_published_schedule(school_id: str) -> Optional[dict]:
    """Latest legacy ``schedules``-collection row in PUBLISHED status."""
    if not school_id:
        return None
    rows = await gd_find(
        db.session, "schedules",
        {"school_id": school_id, "status": "published"},
        order_by="updated_at", desc_order=True, limit=10,
    )
    if not rows:
        return None
    rows.sort(key=lambda r: (r.get("published_at") or "", r.get("updated_at") or ""), reverse=True)
    return rows[0]


async def _resolve_teacher_sessions(school_id: str, resolved_teacher_id: str, day_of_week: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return enriched session rows for a teacher from the latest PUBLISHED
    schedule for their school. Drafts and archived rows are excluded. All
    related class/subject/time-slot lookups are bulk-fetched. Pass
    ``day_of_week`` to restrict to a single day (used by the dashboard
    "today" path)."""
    if not school_id or not resolved_teacher_id:
        return []

    timetable = await _latest_published_timetable(school_id)
    legacy_schedule = await _latest_published_schedule(school_id)

    # Pick the more recently published of the two (timetable wins ties since
    # the smart-scheduling engine is the one that flips published_at).
    def _stamp(row):
        return (row.get("published_at") or row.get("updated_at") or "") if row else ""
    use_timetable = bool(timetable) and (not legacy_schedule or _stamp(timetable) >= _stamp(legacy_schedule))

    enriched: List[Dict[str, Any]] = []

    if use_timetable and timetable:
        tt_filter = {"timetable_id": timetable.get("id"), "teacher_id": resolved_teacher_id}
        if day_of_week:
            tt_filter["day_of_week"] = day_of_week
        sessions = await gd_find(db.session, "timetable_sessions", tt_filter, limit=500)
        # Deduplicate by (day, period) so a stale duplicate row can't double up.
        seen = set()
        unique = []
        for s in sessions:
            key = (s.get("day_of_week"), s.get("period_number"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(s)
        sessions = unique

        class_ids = [s.get("class_id") for s in sessions if s.get("class_id")]
        subj_ids = [s.get("subject_id") for s in sessions if s.get("subject_id")]
        classes = await gd_find(db.session, "classes", {"id": {"$in": list(set(class_ids))}}, limit=500) if class_ids else []
        subjects = await gd_find(db.session, "subjects", {"id": {"$in": list(set(subj_ids))}}, limit=500) if subj_ids else []
        cls_map = {c.get("id"): c for c in classes}
        subj_map = {s.get("id"): s for s in subjects}

        for ts in sessions:
            cls = cls_map.get(ts.get("class_id")) or {}
            subj = subj_map.get(ts.get("subject_id")) or {}
            enriched.append({
                "id": ts.get("id"),
                "schedule_session_id": ts.get("id"),
                "day_of_week": ts.get("day_of_week"),
                "period_number": ts.get("period_number"),
                "slot_number": ts.get("period_number"),
                "start_time": ts.get("start_time"),
                "end_time": ts.get("end_time"),
                "time": ts.get("start_time"),
                "period": ts.get("period_number"),
                "class_id": ts.get("class_id"),
                "class_name": cls.get("name") or "فصل",
                "subject_id": ts.get("subject_id"),
                "subject_name": subj.get("name_ar") or subj.get("name_en") or "مادة",
                "subject": subj.get("name_ar") or subj.get("name_en") or "مادة",
                "session_type": ts.get("session_type", "class"),
                "room_name": ts.get("room_name", ts.get("room_number", "")),
            })
    elif legacy_schedule:
        ss_filter = {
            "schedule_id": legacy_schedule.get("id"),
            "teacher_id": resolved_teacher_id,
            "status": "scheduled",
        }
        if day_of_week:
            ss_filter["day_of_week"] = day_of_week
        sessions = await gd_find(db.session, "schedule_sessions", ss_filter, limit=500)

        assignment_ids = list({s.get("assignment_id") for s in sessions if s.get("assignment_id")})
        slot_ids = list({s.get("time_slot_id") for s in sessions if s.get("time_slot_id")})
        assignments = await gd_find(db.session, "teacher_assignments", {"id": {"$in": assignment_ids}}, limit=500) if assignment_ids else []
        slots = await gd_find(db.session, "time_slots", {"id": {"$in": slot_ids}}, limit=500) if slot_ids else []
        a_map = {a.get("id"): a for a in assignments}
        slot_map = {sl.get("id"): sl for sl in slots}

        class_ids = list({(a_map.get(s.get("assignment_id")) or {}).get("class_id") or s.get("class_id") for s in sessions})
        class_ids = [cid for cid in class_ids if cid]
        subj_ids = list({(a_map.get(s.get("assignment_id")) or {}).get("subject_id") or s.get("subject_id") for s in sessions})
        subj_ids = [sid for sid in subj_ids if sid]
        classes = await gd_find(db.session, "classes", {"id": {"$in": class_ids}}, limit=500) if class_ids else []
        subjects = await gd_find(db.session, "subjects", {"id": {"$in": subj_ids}}, limit=500) if subj_ids else []
        cls_map = {c.get("id"): c for c in classes}
        subj_map = {s.get("id"): s for s in subjects}

        for s in sessions:
            assignment = a_map.get(s.get("assignment_id")) or {}
            slot = slot_map.get(s.get("time_slot_id")) or {}
            cid = assignment.get("class_id") or s.get("class_id")
            sid = assignment.get("subject_id") or s.get("subject_id")
            cls = cls_map.get(cid) or {}
            subj = subj_map.get(sid) or {}
            start_time = slot.get("start_time") or s.get("start_time")
            end_time = slot.get("end_time") or s.get("end_time")
            slot_number = slot.get("slot_number") or s.get("slot_number")
            enriched.append({
                "id": s.get("id"),
                "schedule_session_id": s.get("id"),
                "day_of_week": s.get("day_of_week"),
                "period_number": slot_number,
                "slot_number": slot_number,
                "start_time": start_time,
                "end_time": end_time,
                "time": start_time,
                "period": slot_number,
                "time_slot_id": s.get("time_slot_id"),
                "class_id": cid,
                "class_name": cls.get("name") or s.get("class_name") or "غير محدد",
                "subject_id": sid,
                "subject_name": subj.get("name_ar") or subj.get("name_en") or s.get("subject_name") or "غير محدد",
                "subject": subj.get("name_ar") or subj.get("name_en") or s.get("subject_name") or "غير محدد",
                "room_name": s.get("room_name") or s.get("room_number", ""),
            })

    enriched.sort(key=lambda x: (_DAY_ORDER.get(x.get("day_of_week", ""), 9), x.get("period_number") or 0))
    return enriched


# ============== TEACHER DASHBOARD APIs ==============
TEACHER_ADMIN_ROLES = {"admin", "super_admin", "platform_admin", "school_admin"}

def _verify_teacher_access(teacher_id: str, current_user: dict):
    caller_teacher = current_user.get("teacher_id") or current_user.get("id")
    if caller_teacher != teacher_id and current_user.get("role") not in TEACHER_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية للوصول لبيانات هذا المعلم")


def _check_teacher_tenant(teacher: Optional[dict], current_user: dict):
    """Reject school-scoped admins that try to access a teacher from another tenant."""
    if current_user.get("role") in ("school_admin", "school_principal"):
        caller_tenant = current_user.get("tenant_id")
        target_tenant = (teacher or {}).get("school_id")
        if caller_tenant and target_tenant and caller_tenant != target_tenant:
            raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات معلم من مدرسة أخرى")


async def _resolve_teacher_record(teacher_id: str):
    """
    Resolve the actual teachers-collection record from any of:
      - teachers.id (direct hit)
      - teachers.user_id (when caller passed the user id)
      - users.id -> teachers (matched strictly by school_id + unique email)

    Returns the teacher dict or None. This is needed because the frontend
    falls back to ``user.id`` when ``users.teacher_id`` is not populated,
    but admin-side links (teacher_class_assignments, teacher_assignments,
    schedule_sessions, ...) are stored against teachers.id, so a direct
    query by user.id returns nothing.

    SECURITY: name-based matching is intentionally NOT used because two
    teachers in the same school can share a full_name, which would let
    one teacher's "My Classes" page surface another teacher's data.
    Email is required for the user→teacher fallback, and the match must
    be unique (exactly one candidate). When ambiguous, we refuse to
    resolve and return None so the page shows "no classes" rather than
    leaking the wrong data; an admin must then explicitly link the
    user to the correct teachers row.
    """
    if not teacher_id:
        return None

    # 1) Direct match on teachers.id
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    if teacher:
        return teacher

    # 2) teachers row already linked via user_id
    teacher = await gd_find_one(db.session, "teachers", {"user_id": teacher_id})
    if teacher:
        return teacher

    # 3) Strict email-based fallback from users -> teachers
    user = await gd_find_one(db.session, "users", {"id": teacher_id})
    if not user or user.get("role") != "teacher":
        return None

    tenant_id = user.get("tenant_id") or user.get("school_id")
    email = (user.get("email") or "").strip().lower()
    if not tenant_id or not email:
        return None

    candidates = await gd_find(db.session, "teachers", {
        "school_id": tenant_id,
        "email": email,
    }, limit=2)

    if len(candidates) != 1:
        if len(candidates) > 1:
            logger.warning(
                "_resolve_teacher_record: ambiguous match for user %s "
                "in school %s (%d teachers share email)",
                teacher_id, tenant_id, len(candidates),
            )
        return None

    teacher = candidates[0]

    # Safe to backfill: the match is unique within the school AND keyed
    # on the verified login email of this very user.
    try:
        await gd_update_one(
            db.session, "users",
            {"id": teacher_id},
            {"$set": {"teacher_id": teacher.get("id")}}
        )
    except Exception as _e:
        logger.debug(f"_resolve_teacher_record: backfill users.teacher_id failed: {_e}")

    return teacher


@router.get("/teacher/dashboard/{teacher_id}")
async def get_teacher_dashboard(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على بيانات لوحة تحكم المعلم
    - الفصول المسندة
    - عدد الطلاب
    - الحصص اليومية
    - الإحصائيات
    """
    _verify_teacher_access(teacher_id, current_user)
    # Task #145 — use the same strict resolver as `/teacher/schedule`. The
    # previous fallback matched on ``full_name`` which can ambiguously
    # resolve to a different teacher in the same school and leak their
    # data. ``_resolve_teacher_record`` requires a unique-email match for
    # the user→teacher fallback and refuses to resolve when ambiguous.
    teacher = await _resolve_teacher_record(teacher_id)
    _check_teacher_tenant(teacher, current_user)

    if not teacher:
        # Return default data if teacher not found in teachers collection
        # This allows the dashboard to work even if data is only in users collection
        user = await gd_find_one(db.session, "users", {"id": teacher_id})
        if user and user.get("role") == "teacher":
            # Enforce tenant isolation on fallback user lookup for school-scoped roles
            _fb_caller_role = current_user.get("role", "")
            _fb_caller_tenant = current_user.get("tenant_id")
            if _fb_caller_role in ("school_admin", "school_principal"):
                _fb_target_tenant = user.get("tenant_id")
                if _fb_caller_tenant and _fb_target_tenant and _fb_caller_tenant != _fb_target_tenant:
                    raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات معلم من مدرسة أخرى")
            fb_school_id = user.get("tenant_id") or ""
            fb_school = await gd_find_one(db.session, "schools", {"id": fb_school_id}) if fb_school_id else None
            fb_school = fb_school or {}
            return {
                "teacher": {
                    "id": teacher_id,
                    "name": user.get("full_name") or "",
                    "full_name": user.get("full_name") or "",
                    "rank": "",
                    "qualification": "",
                    "specialization": "",
                    "email": user.get("email") or "",
                    "phone": "",
                    "hire_date": "",
                    "school_id": fb_school_id
                },
                "school_name": fb_school.get("name_ar") or fb_school.get("name") or "",
                "school_city": fb_school.get("city") or "",
                "school_type": fb_school.get("type") or "",
                "school_stage": fb_school.get("educational_stage") or fb_school.get("stage") or "",
                "stats": {
                    "my_classes": 0,
                    "my_students": 0,
                    "today_lessons": 0,
                    "pending_attendance": 0,
                    "weekly_sessions": 0,
                    "subjects_count": 0
                },
                "classes": [],
                "subjects": [],
                "subject_names": [],
                "today_schedule": [],
                "recent_activities": []
            }
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    
    # Use teacher's id from teachers collection for lookups
    actual_teacher_id = teacher.get("id")
    school_id = teacher.get("school_id")

    # Get teacher assignments using actual_teacher_id
    assignments = await gd_find(db.session, "teacher_assignments", {
        "teacher_id": actual_teacher_id,
        "is_active": True
    }, limit=100)

    class_ids = list(set(a.get("class_id") for a in assignments if a.get("class_id")))
    subject_ids = list(set(a.get("subject_id") for a in assignments if a.get("subject_id")))

    # Bug fix (Task: IT home empty-state stuck) — for Independent Teachers
    # the canonical source of truth for "my classes" is the workspace
    # `classes` table scoped to `itw_{user_id}`, NOT `teacher_assignments`:
    # `POST /classes/create` for IT only inserts the class row and does
    # not synthesize an assignment, so counting via assignments always
    # returned 0 and the homepage empty-state ("أنشئ فصلك الأول") stayed
    # visible after the first class was created. We re-derive class_ids
    # from the workspace classes here so dashboard stats match the
    # Classes page (`GET /classes`) and the empty-state flips off the
    # moment a class exists. Tenant scoping is preserved: we use the
    # IT's resolved workspace id (`itw_{user_id}`) — never widen scope.
    from auth_scope import is_independent_teacher as _is_it, independent_workspace_id as _itw_id
    if _is_it(current_user):
        _it_workspace = _itw_id(current_user) or school_id
        _it_classes = await gd_find(
            db.session, "classes",
            {"school_id": _it_workspace, "is_active": True},
            limit=500,
        )
        class_ids = [c.get("id") for c in _it_classes if c.get("id")]
        # Pin school_id to the workspace so downstream reads (today's
        # schedule, audit log) stay scoped correctly even if the
        # teachers-row school_id is stale or missing.
        school_id = _it_workspace

    classes = await gd_find(db.session, "classes", {"id": {"$in": class_ids}}, limit=500) if class_ids else []
    total_students = 0
    for cls_item in classes:
        count = await gd_count(db.session, "students", {"class_id": cls_item.get("id"), "is_active": True})
        cls_item["student_count"] = count
        total_students += count
    
    # Get subjects
    subjects = await gd_find(db.session, "subjects", {"id": {"$in": subject_ids}}, limit=50)
    
    # Get today's schedule
    today_day = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"][datetime.now().weekday()]
    # Map Python weekday to our system
    day_map = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}
    today_day = day_map.get(datetime.now().weekday(), "sunday")
    
    # Resolve today's lessons from the latest PUBLISHED schedule for this
    # school via the shared helper (Task #145). This ensures the teacher
    # dashboard always sees the same source-of-truth as the dedicated
    # ``/teacher/schedule`` endpoint, drafts/archived rows can never leak
    # in, and class/subject lookups are bulk-fetched (no N+1).
    today_lessons = await _resolve_teacher_sessions(school_id, actual_teacher_id, day_of_week=today_day)
    today_lessons.sort(key=lambda x: x.get("period") or 0)
    
    # Get pending attendance (classes where attendance not recorded today)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    recorded_attendance = await gd_find(db.session, "attendance", {
        "teacher_id": actual_teacher_id,
        "date": today_str
    }, limit=50)
    recorded_class_ids = [a.get("class_id") for a in recorded_attendance]
    pending_attendance = len([c for c in class_ids if c not in recorded_class_ids])
    
    # Recent activities
    recent_activities = await gd_find(db.session, "audit_log", {
        "user_id": current_user.get("id"),
        "school_id": school_id
    }, order_by="timestamp", desc_order=True, limit=5)
    
    school = await gd_find_one(db.session, "schools", {"id": school_id}) or {}
    school_name = school.get("name_ar") or school.get("name") or school.get("name_en") or ""
    school_city = school.get("city") or ""
    school_type = school.get("type") or school.get("school_type") or ""
    school_stage = school.get("educational_stage") or school.get("stage") or ""
    primary_subject = None
    primary_sub_id = teacher.get("primary_subject_id") or teacher.get("specialization")
    if primary_sub_id:
        sub_doc = await gd_find_one(db.session, "subjects", {"id": primary_sub_id})
        if sub_doc:
            primary_subject = sub_doc.get("name_ar") or sub_doc.get("name_en")
        elif not primary_sub_id.startswith("sub-"):
            primary_subject = primary_sub_id
    subject_names = [s.get("name_ar") or s.get("name_en") or "" for s in subjects]

    return {
        "teacher": {
            "id": teacher.get("id"),
            "name": teacher.get("full_name") or teacher.get("name"),
            "full_name": teacher.get("full_name") or teacher.get("name"),
            "rank": teacher.get("rank") or "",
            "qualification": teacher.get("qualification") or "",
            "specialization": primary_subject or "",
            "email": teacher.get("email") or "",
            "phone": teacher.get("phone") or "",
            "hire_date": str(teacher.get("hire_date") or ""),
            "school_id": school_id
        },
        "school_name": school_name,
        "school_city": school_city,
        "school_type": school_type,
        "school_stage": school_stage,
        "stats": {
            "my_classes": len(class_ids),
            "my_students": total_students,
            "today_lessons": len(today_lessons),
            "pending_attendance": pending_attendance,
            "subjects_count": len(subject_ids),
            "weekly_sessions": sum(a.get("weekly_sessions", 0) for a in assignments)
        },
        "today_schedule": today_lessons,
        "classes": [{"id": c.get("id"), "name": c.get("name"), "students": c.get("student_count", 0)} for c in classes],
        "subjects": [{"id": s.get("id"), "name": s.get("name_ar") or s.get("name_en")} for s in subjects],
        "subject_names": subject_names,
        "recent_activities": [
            {"type": a.get("action"), "message": a.get("details", {}).get("description", a.get("action")), "time": a.get("timestamp")}
            for a in recent_activities
        ]
    }





# ============== STUDENT DASHBOARD APIs ==============
@router.get("/student/dashboard/{student_id}")
async def get_student_dashboard(
    student_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على بيانات لوحة تحكم الطالب
    - الجدول اليومي
    - الدرجات
    - نسبة الحضور
    - الإشعارات
    """
    # SECURITY (audit C-3): tenant-scope the lookup itself so a foreign
    # student-id no longer reveals the school structure via 200 vs 404 timing.
    from utils.tenant_scope import tenant_scoped_find_one
    student = await tenant_scoped_find_one(db.session, "students", student_id, current_user)
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    user_tenant = current_user.get("tenant_id")
    student_school = student.get("school_id")
    if user_tenant:
        if not student_school or user_tenant != student_school:
            raise HTTPException(status_code=403, detail="لا يمكنك الوصول إلى بيانات طالب من مدرسة أخرى")

    _sd_caller_role = current_user.get("role", "")
    _sd_caller_id = current_user.get("id")
    _SD_ADMIN_ROLES = {"platform_admin", "admin", "super_admin", "school_principal", "school_admin", "school_sub_admin"}
    # Default: full access; overridden below for restricted guardian callers.
    _sd_can_view_attendance = True
    _sd_can_view_grades = True
    if _sd_caller_role not in _SD_ADMIN_ROLES:
        if _sd_caller_role == "student":
            if current_user.get("student_id") != student_id and _sd_caller_id != student_id:
                raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات طالب آخر")
        elif _sd_caller_role == "parent":
            _sd_parent = await gd_find_one(db.session, "parents", {"user_id": _sd_caller_id})
            _sd_parent_row_id = _sd_parent.get("id") if _sd_parent else None
            _sd_id_cond = (
                {"$or": [{"parent_user_id": _sd_caller_id}, {"parent_id": _sd_parent_row_id}]}
                if _sd_parent_row_id else {"parent_user_id": _sd_caller_id}
            )
            _sd_link = await gd_find_one(db.session, "guardian_links", {**_sd_id_cond, "student_id": student_id, "is_active": True})
            if not _sd_link:
                _sd_inactive = await gd_find_one(db.session, "guardian_links", {**_sd_id_cond, "student_id": student_id, "is_active": False})
                if _sd_inactive:
                    raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات هذا الطالب")
                if not _sd_parent or student_id not in (_sd_parent.get("student_ids") or []):
                    raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات هذا الطالب")
            # Capture per-guardian permission flags for response filtering below.
            _sd_link_perms = (_sd_link.get("permissions") or {}) if _sd_link else {}
            _sd_can_view_attendance = _sd_link_perms.get("can_view_attendance", True)
            _sd_can_view_grades = _sd_link_perms.get("can_view_grades", True)
        elif _sd_caller_role == "teacher":
            _sd_teacher_id = current_user.get("teacher_id") or _sd_caller_id
            _sd_class_id = student.get("class_id")
            _sd_assign = await gd_find_one(db.session, "teacher_assignments", {"teacher_id": _sd_teacher_id, "class_id": _sd_class_id})
            if not _sd_assign:
                _sd_sess = await gd_find_one(db.session, "class_sessions", {"teacher_id": _sd_teacher_id, "class_id": _sd_class_id})
                if not _sd_sess:
                    raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات هذا الطالب")
        else:
            raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات هذا الطالب")

    school_id = student_school
    class_id = student.get("class_id")
    
    # Get class info
    class_info = await gd_find_one(db.session, "classes", {"id": class_id})
    
    # Get today's schedule for the class
    day_map = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}
    today_day = day_map.get(datetime.now().weekday(), "sunday")
    
    schedule = await gd_find_one(db.session, "schedules", {
        "school_id": school_id,
        "status": {"$in": [ScheduleStatusEnum.DRAFT.value, ScheduleStatusEnum.PUBLISHED.value]}
    })
    
    today_lessons = []
    if schedule:
        sessions = await gd_find(db.session, "schedule_sessions", {
            "schedule_id": schedule.get("id"),
            "class_id": class_id,
            "day_of_week": today_day,
            "status": SessionStatusEnum.SCHEDULED.value
        }, limit=20)
        
        # Get details
        slot_ids = list(set(s.get("time_slot_id") for s in sessions))
        teacher_ids = list(set(s.get("teacher_id") for s in sessions if s.get("teacher_id")))
        subject_ids = list(set(s.get("subject_id") for s in sessions if s.get("subject_id")))
        
        slots = await gd_find(db.session, "time_slots", {"id": {"$in": slot_ids}}, limit=20)
        teachers = await gd_find(db.session, "teachers", {"id": {"$in": teacher_ids}}, limit=20)
        subjects = await gd_find(db.session, "subjects", {"id": {"$in": subject_ids}}, limit=20)
        
        slot_map = {s.get("id"): s for s in slots}
        teacher_map = {t.get("id"): t for t in teachers}
        subject_map = {s.get("id"): s for s in subjects}
        
        for session in sessions:
            slot = slot_map.get(session.get("time_slot_id"), {})
            teacher = teacher_map.get(session.get("teacher_id"), {})
            subject = subject_map.get(session.get("subject_id"), {})
            
            today_lessons.append({
                "time": slot.get("start_time", ""),
                "period": slot.get("slot_number", 0),
                "subject": subject.get("name_ar") or subject.get("name_en") or "غير محدد",
                "teacher": teacher.get("full_name", "غير محدد"),
                "room": session.get("room_name", "")
            })
        
        today_lessons.sort(key=lambda x: x.get("period", 0))
    
    # Get attendance summary — only when the caller is permitted to see it
    total_days = 0
    present_days = 0
    attendance_rate = None
    if _sd_can_view_attendance:
        attendance_records = await gd_find(db.session, "attendance", {
            "student_id": student_id,
            "school_id": school_id
        }, limit=200)
        total_days = len(attendance_records)
        present_days = len([a for a in attendance_records if a.get("status") == "present"])
        attendance_rate = round((present_days / total_days * 100) if total_days > 0 else 100, 1)
    
    # Get grade data — only when the caller is permitted to see it
    recent_grades = []
    average_grade = 0
    if _sd_can_view_grades:
        submissions = await gd_find(db.session, "assessment_submissions", {
            "student_id": student_id
        }, order_by="submitted_at", desc_order=True, limit=10)
        for sub in submissions:
            assessment = await gd_find_one(db.session, "assessments", {"id": sub.get("assessment_id")})
            subject_name = ""
            if assessment and assessment.get("subject_id"):
                subj = await gd_find_one(db.session, "subjects", {"id": assessment["subject_id"]})
                subject_name = subj.get("name_ar", subj.get("name", "")) if subj else assessment.get("title", "")
            elif assessment:
                subject_name = assessment.get("title", "")
            grade_val = sub.get("grade", sub.get("score", 0))
            recent_grades.append({
                "subject": subject_name or "غير محدد",
                "grade": grade_val,
                "date": sub.get("submitted_at", sub.get("graded_at", datetime.now().strftime("%Y-%m-%d")))
            })
        average_grade = sum(g.get("grade", 0) for g in recent_grades) / len(recent_grades) if recent_grades else 0
    
    # Get notifications
    notifications = await gd_find(db.session, "notifications", {
        "$or": [
            {"target_id": student_id},
            {"target_type": "all", "school_id": school_id}
        ]
    }, order_by="created_at", desc_order=True, limit=5)
    
    return {
        "student": {
            "id": student.get("id"),
            "name": student.get("full_name"),
            "class_name": class_info.get("name") if class_info else "غير محدد",
            "school_id": school_id
        },
        "stats": {
            "attendance_rate": attendance_rate,
            "average_grade": round(average_grade, 1),
            "present_days": present_days,
            "absent_days": total_days - present_days,
            "total_lessons_today": len(today_lessons)
        },
        "today_schedule": today_lessons,
        "recent_grades": recent_grades,
        "notifications": [
            {"title": n.get("title"), "message": n.get("message"), "time": n.get("created_at"), "type": n.get("type", "info")}
            for n in notifications
        ]
    }





# ============== PARENT DASHBOARD APIs ==============
@router.get("/parent/dashboard/{parent_id}")
async def get_parent_dashboard(
    parent_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على بيانات لوحة تحكم ولي الأمر
    - قائمة الأبناء
    - ملخص كل ابن (حضور، درجات، سلوك)
    """
    parent = await gd_find_one(db.session, "parents", {"id": parent_id})
    if not parent:
        raise HTTPException(status_code=404, detail="ولي الأمر غير موجود")

    school_id = parent.get("school_id")
    caller_role = current_user.get("role", "")
    caller_id = current_user.get("id")
    caller_tenant = current_user.get("tenant_id")

    if caller_role == "platform_admin":
        pass
    elif caller_role in ("school_admin", "school_principal", "school_sub_admin", "admin", "super_admin"):
        if caller_tenant and school_id and caller_tenant != school_id:
            raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات ولي أمر من مدرسة أخرى")
    else:
        parent_user_id = parent.get("user_id")
        if caller_id != parent_user_id and caller_id != parent_id:
            raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات ولي أمر آخر")
    
    # Get children — use active guardian_links as the authoritative source.
    # Fall back to parents.student_ids only for entries that have no
    # guardian_links record at all (legacy links created before the guardian_links
    # table was introduced).  Stale entries whose guardian_links row was
    # soft-deleted (is_active=False) are excluded so unlinked guardians lose access.
    parent_user_id_for_links = parent.get("user_id")
    _pd_parent_row_id = parent.get("id")
    _pd_id_cond: dict
    if parent_user_id_for_links and _pd_parent_row_id:
        _pd_id_cond = {"$or": [{"parent_user_id": parent_user_id_for_links}, {"parent_id": _pd_parent_row_id}]}
    elif parent_user_id_for_links:
        _pd_id_cond = {"parent_user_id": parent_user_id_for_links}
    else:
        _pd_id_cond = {"parent_id": _pd_parent_row_id}
    active_links = await gd_find(db.session, "guardian_links", {**_pd_id_cond, "is_active": True}) if (_pd_parent_row_id or parent_user_id_for_links) else []
    active_student_ids = {lnk["student_id"] for lnk in active_links if lnk.get("student_id")}
    # Build per-student permission map from active links (True when no link exists = legacy full access)
    _link_perms_map = {lnk["student_id"]: (lnk.get("permissions") or {}) for lnk in active_links if lnk.get("student_id")}

    legacy_student_ids = parent.get("student_ids") or []
    for _leg_sid in legacy_student_ids:
        if _leg_sid not in active_student_ids:
            any_link = await gd_find_one(db.session, "guardian_links", {**_pd_id_cond, "student_id": _leg_sid})
            if not any_link:
                active_student_ids.add(_leg_sid)

    student_ids = list(active_student_ids)
    children_data = []

    for student_id in student_ids:
        student = await gd_find_one(db.session, "students", {"id": student_id})
        if not student:
            continue

        # Resolve per-guardian permission flags for this child.
        # Legacy-linked students (no guardian_links row) receive full access.
        _child_perms = _link_perms_map.get(student_id)
        _can_view_attendance = _child_perms.get("can_view_attendance", True) if _child_perms is not None else True
        _can_view_grades = _child_perms.get("can_view_grades", True) if _child_perms is not None else True
        
        class_info = await gd_find_one(db.session, "classes", {"id": student.get("class_id")})
        
        # Get attendance summary — only when this guardian is permitted to see it
        total_days = 0
        present_days = 0
        absent_days = 0
        late_days = 0
        attendance_rate = None
        if _can_view_attendance:
            attendance_records = await gd_find(db.session, "attendance", {
                "student_id": student_id
            }, limit=200)
            total_days = len(attendance_records)
            present_days = len([a for a in attendance_records if a.get("status") == "present"])
            absent_days = len([a for a in attendance_records if a.get("status") == "absent"])
            late_days = len([a for a in attendance_records if a.get("status") == "late"])
            attendance_rate = round((present_days / total_days * 100) if total_days > 0 else 100, 1)
        
        # Get grade records — only when this guardian is permitted to see them
        recent_grades = []
        average_grade = 0
        if _can_view_grades:
            grade_records = await gd_find(db.session, "grades", {
                "student_id": student_id
            }, order_by="recorded_at", desc_order=True, limit=10)
            recent_grades = [
                {
                    "subject": g.get("subject_name", "غير محدد"),
                    "grade": g.get("score", 0),
                    "date": g.get("recorded_at", ""),
                }
                for g in grade_records
            ]
            average_grade = (
                sum(g.get("grade", 0) for g in recent_grades) / len(recent_grades)
                if recent_grades
                else 0
            )

        behaviour_records = await gd_find(db.session, "behaviour_records", {
            "student_id": student_id
        }, order_by="created_at", desc_order=True, limit=5)
        behaviour_notes = [
            {
                "type": b.get("type", "info"),
                "note": b.get("note", ""),
                "date": b.get("created_at", ""),
            }
            for b in behaviour_records
        ]
        
        # Get today's schedule
        day_map = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}
        today_day = day_map.get(datetime.now().weekday(), "sunday")
        
        schedule = await gd_find_one(db.session, "schedules", {
            "school_id": school_id,
            "status": {"$in": [ScheduleStatusEnum.DRAFT.value, ScheduleStatusEnum.PUBLISHED.value]}
        })
        
        today_schedule = []
        if schedule:
            sessions = await gd_find(db.session, "schedule_sessions", {
                "schedule_id": schedule.get("id"),
                "class_id": student.get("class_id"),
                "day_of_week": today_day
            }, limit=10)
            
            for session in sessions:
                slot = await gd_find_one(db.session, "time_slots", {"id": session.get("time_slot_id")})
                teacher = await gd_find_one(db.session, "teachers", {"id": session.get("teacher_id")})
                subject = await gd_find_one(db.session, "subjects", {"id": session.get("subject_id")})
                
                today_schedule.append({
                    "time": slot.get("start_time", "") if slot else "",
                    "subject": subject.get("name_ar") if subject else "غير محدد",
                    "teacher": teacher.get("full_name") if teacher else "غير محدد"
                })
        
        children_data.append({
            "id": student.get("id"),
            "name": student.get("full_name"),
            "class_name": class_info.get("name") if class_info else "غير محدد",
            "avatar": student.get("avatar_url"),
            "stats": {
                "attendance_rate": attendance_rate,
                "average_grade": round(average_grade, 1),
                "absences": absent_days,
                "lates": late_days
            },
            "recent_grades": recent_grades,
            "behaviour_notes": behaviour_notes,
            "today_schedule": today_schedule[:5]
        })
    
    # Get notifications for parent
    notifications = await gd_find(db.session, "notifications", {
        "$or": [
            {"target_id": parent_id},
            {"target_id": {"$in": student_ids}},
            {"target_type": "all", "school_id": school_id}
        ]
    }, order_by="created_at", desc_order=True, limit=10)
    
    return {
        "parent": {
            "id": parent.get("id"),
            "name": parent.get("full_name"),
            "phone": parent.get("phone"),
            "email": parent.get("email")
        },
        "children_count": len(children_data),
        "children": children_data,
        "notifications": [
            {"title": n.get("title"), "message": n.get("message"), "time": n.get("created_at"), "type": n.get("type", "info")}
            for n in notifications
        ]
    }





# ============== CONTACT TEACHER API ==============
@router.post("/parent/contact-teacher")
async def parent_contact_teacher(
    teacher_id: str,
    student_id: str,
    subject: str,
    message: str,
    current_user: dict = Depends(require_roles([UserRole.PARENT]))
):
    """
    إرسال رسالة من ولي الأمر للمعلم
    """
    parent_id = current_user.get("id")
    
    # Verify parent has this student
    parent = await gd_find_one(db.session, "parents", {"id": parent_id})
    if not parent or student_id not in parent.get("student_ids", []):
        raise HTTPException(status_code=403, detail="غير مصرح لك بالتواصل بشأن هذا الطالب")
    
    # Get teacher
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    
    # Create message
    msg_id = str(uuid.uuid4())
    msg_doc = {
        "id": msg_id,
        "type": "parent_teacher_message",
        "from_id": parent_id,
        "from_type": "parent",
        "from_name": parent.get("full_name"),
        "to_id": teacher_id,
        "to_type": "teacher",
        "to_name": teacher.get("full_name"),
        "student_id": student_id,
        "subject": subject,
        "message": message,
        "status": "sent",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read": False
    }
    
    await gd_insert(db.session, "messages", msg_doc)
    
    # Create notification for teacher
    await gd_insert(db.session, "notifications", {
        "id": str(uuid.uuid4()),
        "type": "parent_message",
        "title": f"رسالة من ولي أمر: {parent.get('full_name')}",
        "message": subject[:100],
        "target_id": teacher.get("user_id"),
        "target_type": "user",
        "school_id": parent.get("school_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read": False
    })
    
    return {
        "success": True,
        "message_id": msg_id,
        "message_ar": "تم إرسال الرسالة بنجاح",
        "message_en": "Message sent successfully"
    }





# ============== TEACHER MODULE APIs ==============

@router.get("/teacher/sessions/{teacher_id}")
async def get_teacher_sessions_list(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    _verify_teacher_access(teacher_id, current_user)
    teacher = await _resolve_teacher_record(teacher_id)
    _check_teacher_tenant(teacher, current_user)
    resolved_teacher_id = teacher.get("id") if teacher else teacher_id
    sessions_list = await gd_find(db.session, "teacher_sessions", {"teacher_id": resolved_teacher_id}, order_by="created_at", desc_order=True, limit=200)

    for s in sessions_list:
        if not s.get("class_name") and s.get("class_id"):
            cls = await gd_find_one(db.session, "classes", {"id": s["class_id"]})
            s["class_name"] = cls.get("name", "") if cls else ""
        if not s.get("subject_name") and s.get("subject_id"):
            subj = await gd_find_one(db.session, "subjects", {"id": s["subject_id"]})
            s["subject_name"] = subj.get("name", "") if subj else ""

    return {"sessions": sessions_list}


@router.get("/teacher/classes/{teacher_id}")
async def get_teacher_classes(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all classes assigned to a teacher with enriched data
    جلب جميع الفصول المسندة للمعلم مع بيانات مُثرَاة
    """
    _verify_teacher_access(teacher_id, current_user)

    teacher = await _resolve_teacher_record(teacher_id)
    _check_teacher_tenant(teacher, current_user)
    school_id = teacher.get("school_id") if teacher else None
    # Use the actual teachers.id for queries — admin-side assignments are
    # stored against teachers.id, not users.id.
    resolved_teacher_id = teacher.get("id") if teacher else teacher_id

    # First-touch initialization: if this school has never had teacher-class
    # assignments populated, run the one-shot auto-populate so newly created
    # teachers see their default classes without waiting for the principal to
    # open the assignments settings tab.
    if school_id:
        try:
            from routes.school_settings_mod import _auto_populate_teacher_class_assignments
            await _auto_populate_teacher_class_assignments(school_id)
        except Exception as e:
            logger.warning(f"teacher classes initial populate failed for school {school_id}: {e}")

    assignments = await gd_find(db.session, "teacher_assignments", {
        "teacher_id": resolved_teacher_id,
        "is_active": True
    }, limit=200)

    class_ids_from_assignments = set(a.get("class_id") for a in assignments if a.get("class_id"))

    tca_docs = await gd_find(db.session, "teacher_class_assignments", {
        "teacher_id": resolved_teacher_id
    }, limit=200)
    class_ids_from_tca = set(d.get("class_id") for d in tca_docs if d.get("class_id"))

    all_class_ids = list(class_ids_from_assignments | class_ids_from_tca)
    if not all_class_ids:
        return []

    classes = await gd_find(db.session, "classes", {"id": {"$in": all_class_ids}}, limit=100)

    schedule = await gd_find_one(db.session, "schedules", {"school_id": school_id, "status": {"$in": ["draft", "published"]}}) if school_id else None
    schedule_sessions = []
    time_slots_map = {}
    if schedule:
        schedule_sessions = await gd_find(db.session, "schedule_sessions", {"schedule_id": schedule["id"], "teacher_id": resolved_teacher_id, "status": "scheduled"}, limit=500)
        ts_docs = await gd_find(db.session, "time_slots", {"school_id": school_id, "is_break": {"$ne": True}}, limit=50)
        for ts in ts_docs:
            ts_id = ts.get("id") or ts.get("slot_number")
            if ts_id is not None:
                time_slots_map[str(ts_id)] = ts

    now = datetime.now()
    js_day_map = {6: "sunday", 0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday"}
    today_key = js_day_map.get(now.weekday())
    day_order = ["sunday", "monday", "tuesday", "wednesday", "thursday"]

    enriched_classes = []
    for cls in classes:
        cls_id = cls.get("id")
        class_assignments = [a for a in assignments if a.get("class_id") == cls_id]

        student_count = await gd_count(db.session, "students", {"class_id": cls_id, "is_active": True})

        subject_ids = list(set(a.get("subject_id") for a in class_assignments if a.get("subject_id")))
        if not subject_ids and schedule_sessions:
            subject_ids = list(set(
                s.get("subject_id") for s in schedule_sessions
                if s.get("class_id") == cls_id and s.get("subject_id")
            ))
        if not subject_ids:
            ta_for_class = await gd_find(db.session, "teacher_assignments", {"class_id": cls_id, "is_active": True}, limit=20)
            subject_ids = list(set(a.get("subject_id") for a in ta_for_class if a.get("subject_id")))
        if not subject_ids:
            subject_ids = list(set(a.get("subject_id") for a in assignments if a.get("subject_id")))

        subjects = []
        if subject_ids:
            subjects = await gd_find(db.session, "subjects", {"id": {"$in": subject_ids}}, limit=20)
        subject_names = [s.get("name_ar") or s.get("name_en") or "مادة" for s in subjects]
        subjects_data = [
            {"id": s.get("id"), "name": s.get("name_ar") or s.get("name_en") or "مادة"}
            for s in subjects if s.get("id")
        ]

        class_schedule = [s for s in schedule_sessions if s.get("class_id") == cls_id]
        weekly_periods = len(class_schedule) or sum(a.get("weekly_sessions", 0) for a in class_assignments)

        next_session_info = None
        if class_schedule and today_key:
            today_idx = day_order.index(today_key) if today_key in day_order else -1
            now_minutes = now.hour * 60 + now.minute
            best = None
            for s in class_schedule:
                s_day = s.get("day_of_week", "").lower()
                if s_day not in day_order:
                    continue
                s_idx = day_order.index(s_day)
                ts_id = s.get("time_slot_id") or s.get("slot_number")
                ts = time_slots_map.get(str(ts_id), {})
                start_str = ts.get("start_time", s.get("start_time", ""))
                try:
                    parts = start_str.replace(":", " ").split()
                    s_min = int(parts[0]) * 60 + int(parts[1])
                except (ValueError, IndexError, TypeError):
                    s_min = 0
                if s_idx > today_idx or (s_idx == today_idx and s_min > now_minutes):
                    dist = (s_idx - today_idx) * 1440 + (s_min - now_minutes)
                else:
                    dist = (s_idx - today_idx + 5) * 1440 + (s_min - now_minutes)
                if best is None or dist < best[0]:
                    subj = next((sb for sb in subjects if sb.get("id") == s.get("subject_id")), {})
                    best = (dist, {
                        "day": s_day,
                        "start_time": ts.get("start_time", s.get("start_time", "")),
                        "end_time": ts.get("end_time", s.get("end_time", "")),
                        "subject_name": subj.get("name_ar") or subj.get("name_en") or "",
                        "slot_number": ts.get("slot_number", s.get("slot_number")),
                        "room_name": s.get("room_name", ""),
                    })
            if best:
                next_session_info = best[1]

        grade_name = cls.get("grade_name", "")
        if not grade_name:
            gl = cls.get("grade_level") or cls.get("grade_id", "")
            grade_map = {"1": "الأول", "2": "الثاني", "3": "الثالث", "4": "الرابع", "5": "الخامس", "6": "السادس"}
            grade_name = f"الصف {grade_map.get(str(gl), gl)}" if gl else ""

        status = "active"
        if not class_schedule:
            status = "no_upcoming"

        enriched_classes.append({
            **cls,
            "student_count": student_count,
            "subjects": subject_names,
            "subject_ids": subject_ids,
            "subjects_data": subjects_data,
            "weekly_periods": weekly_periods,
            "grade_name": grade_name,
            "next_session": next_session_info,
            "status": status,
            "schedule_count": len(class_schedule),
        })

    enriched_classes.sort(key=lambda c: (c.get("grade_level", "0"), c.get("name", "")))
    return enriched_classes


@router.get("/teacher/schedule/{teacher_id}")
async def get_teacher_schedule(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get teacher's schedule
    جلب جدول المعلم
    """
    _verify_teacher_access(teacher_id, current_user)
    teacher = await _resolve_teacher_record(teacher_id)
    _check_teacher_tenant(teacher, current_user)
    if not teacher:
        return []

    school_id = teacher.get("school_id")
    resolved_teacher_id = teacher.get("id") or teacher_id

    # Task #145: delegate to the shared resolver. It returns enriched rows
    # from the latest PUBLISHED schedule for this teacher's school, with
    # class/subject/slot details bulk-fetched. Drafts and archived
    # timetables are intentionally excluded so a teacher can never see
    # in-progress edits, and an old published version is never returned
    # after a republish.
    return await _resolve_teacher_sessions(school_id, resolved_teacher_id)


@router.get("/teacher/assessments/{teacher_id}")
async def get_teacher_assessments(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get assessments created by teacher
    جلب تقييمات المعلم
    """
    _verify_teacher_access(teacher_id, current_user)
    teacher = await _resolve_teacher_record(teacher_id)
    _check_teacher_tenant(teacher, current_user)
    resolved_teacher_id = teacher.get("id") if teacher else teacher_id
    assessments = await gd_find(db.session, "assessments", {
        "teacher_id": resolved_teacher_id
    }, order_by="created_at", desc_order=True, limit=100)
    
    # Enrich with class names
    for assessment in assessments:
        if assessment.get("class_id"):
            cls = await gd_find_one(db.session, "classes", {"id": assessment.get("class_id")})
            assessment["class_name"] = cls.get("name") if cls else ""
    
    return assessments


@router.get("/assessments/{assessment_id}/grades")
async def get_assessment_grades(
    assessment_id: str,
    current_user: dict = Depends(require_roles([UserRole.TEACHER, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    """Get grades for an assessment"""
    _ag_role = current_user.get("role")
    if _ag_role != UserRole.PLATFORM_ADMIN:
        assessment = await gd_find_one(db.session, "assessments", {"id": assessment_id})
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        user_tenant = current_user.get("tenant_id")
        if user_tenant and assessment.get("school_id") and assessment["school_id"] != user_tenant:
            raise HTTPException(status_code=403, detail="غير مصرح بالوصول")
        if _ag_role == UserRole.TEACHER:
            _ag_teacher_id = current_user.get("teacher_id") or current_user.get("id")
            _ag_owned = (assessment.get("created_by") == _ag_teacher_id or assessment.get("teacher_id") == _ag_teacher_id)
            if not _ag_owned:
                _ag_assign = await gd_find_one(db.session, "teacher_assignments", {"teacher_id": _ag_teacher_id, "class_id": assessment.get("class_id")})
                if not _ag_assign:
                    raise HTTPException(status_code=403, detail="لا يمكنك الوصول لدرجات تقييم لا تملكه")
    grades = await gd_find(db.session, "grades", {"assessment_id": assessment_id}, limit=200)
    return grades


@router.post("/assessments/{assessment_id}/grades")
async def save_assessment_grades(
    assessment_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(require_roles([UserRole.TEACHER, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    """Save grades for assessment - حفظ درجات التقييم"""
    _sg_role = current_user.get("role")
    if _sg_role != UserRole.PLATFORM_ADMIN:
        assessment = await gd_find_one(db.session, "assessments", {"id": assessment_id})
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        user_tenant = current_user.get("tenant_id")
        if user_tenant and assessment.get("school_id") and assessment["school_id"] != user_tenant:
            raise HTTPException(status_code=403, detail="غير مصرح بالوصول")
        if _sg_role == UserRole.TEACHER:
            _sg_teacher_id = current_user.get("teacher_id") or current_user.get("id")
            _sg_owned = (assessment.get("created_by") == _sg_teacher_id or assessment.get("teacher_id") == _sg_teacher_id)
            if not _sg_owned:
                _sg_assign = await gd_find_one(db.session, "teacher_assignments", {"teacher_id": _sg_teacher_id, "class_id": assessment.get("class_id")})
                if not _sg_assign:
                    raise HTTPException(status_code=403, detail="لا يمكنك تعديل درجات تقييم لا تملكه")
    grades = data.get("grades", [])
    
    for grade in grades:
        grade_record = {
            "id": str(uuid.uuid4()),
            "assessment_id": assessment_id,
            "student_id": grade.get("student_id"),
            "score": grade.get("score"),
            "notes": grade.get("notes"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "graded_by": current_user["id"]
        }
        
        # Upsert grade
        await gd_update_one(db.session, "grades", {"assessment_id": assessment_id, "student_id": grade.get("student_id")}, grade_record)
    
    # Update assessment status
    await gd_update_one(db.session, "assessments", {"id": assessment_id}, {"status": "graded", "graded_at": datetime.now(timezone.utc).isoformat()})
    
    return {"message": "تم حفظ الدرجات"}


@router.get("/students/{student_id}/grades")
async def get_student_grades(
    student_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all grades for a student"""
    _stg_student = await gd_find_one(db.session, "students", {"id": student_id})
    if not _stg_student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    _stg_role = current_user.get("role", "")
    _stg_caller_id = current_user.get("id")
    _stg_caller_tenant = current_user.get("tenant_id")
    _STG_ADMIN_ROLES = {"platform_admin", "admin", "super_admin", "school_principal", "school_admin", "school_sub_admin"}
    if _stg_role not in _STG_ADMIN_ROLES:
        if _stg_role == "student":
            if current_user.get("student_id") != student_id and _stg_caller_id != student_id:
                raise HTTPException(status_code=403, detail="لا يمكنك الوصول لدرجات طالب آخر")
        elif _stg_role == "parent":
            _stg_parent = await gd_find_one(db.session, "parents", {"user_id": _stg_caller_id})
            _stg_parent_row_id = _stg_parent.get("id") if _stg_parent else None
            _stg_id_cond = (
                {"$or": [{"parent_user_id": _stg_caller_id}, {"parent_id": _stg_parent_row_id}]}
                if _stg_parent_row_id else {"parent_user_id": _stg_caller_id}
            )
            _stg_link = await gd_find_one(db.session, "guardian_links", {**_stg_id_cond, "student_id": student_id, "is_active": True})
            if _stg_link:
                _stg_perms = _stg_link.get("permissions") or {}
                if not _stg_perms.get("can_view_grades", True):
                    raise HTTPException(status_code=403, detail="لا يمكنك الوصول لدرجات هذا الطالب")
            else:
                _stg_inactive = await gd_find_one(db.session, "guardian_links", {**_stg_id_cond, "student_id": student_id, "is_active": False})
                if _stg_inactive:
                    raise HTTPException(status_code=403, detail="لا يمكنك الوصول لدرجات هذا الطالب")
                if not _stg_parent or student_id not in (_stg_parent.get("student_ids") or []):
                    raise HTTPException(status_code=403, detail="لا يمكنك الوصول لدرجات هذا الطالب")
        elif _stg_role == "teacher":
            _stg_teacher_id = current_user.get("teacher_id") or _stg_caller_id
            _stg_assign = await gd_find_one(db.session, "teacher_assignments", {"teacher_id": _stg_teacher_id, "class_id": _stg_student.get("class_id")})
            if not _stg_assign:
                raise HTTPException(status_code=403, detail="لا يمكنك الوصول لدرجات هذا الطالب")
        else:
            raise HTTPException(status_code=403, detail="لا يمكنك الوصول لدرجات هذا الطالب")
    else:
        if _stg_role != "platform_admin" and _stg_caller_tenant:
            if _stg_student.get("school_id") and _stg_student["school_id"] != _stg_caller_tenant:
                raise HTTPException(status_code=403, detail="لا يمكنك الوصول لدرجات طالب من مدرسة أخرى")

    grades = await gd_find(db.session, "grades", {"student_id": student_id}, limit=100)

    for grade in grades:
        assessment = await gd_find_one(db.session, "assessments", {"id": grade.get("assessment_id")})
        if assessment:
            grade["assessment_name"] = assessment.get("name")
            grade["type"] = assessment.get("type")
            grade["max_score"] = assessment.get("max_score", 100)

    return grades


@router.get("/students/{student_id}/attendance-stats")
async def get_student_attendance_stats(
    student_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get attendance statistics for a student"""
    _sas_student = await gd_find_one(db.session, "students", {"id": student_id})
    if not _sas_student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    _sas_role = current_user.get("role", "")
    _sas_caller_id = current_user.get("id")
    _sas_caller_tenant = current_user.get("tenant_id")
    _SAS_ADMIN_ROLES = {"platform_admin", "admin", "super_admin", "school_principal", "school_admin", "school_sub_admin"}
    if _sas_role not in _SAS_ADMIN_ROLES:
        if _sas_role == "student":
            if current_user.get("student_id") != student_id and _sas_caller_id != student_id:
                raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات حضور طالب آخر")
        elif _sas_role == "parent":
            _sas_parent = await gd_find_one(db.session, "parents", {"user_id": _sas_caller_id})
            _sas_parent_row_id = _sas_parent.get("id") if _sas_parent else None
            _sas_id_cond = (
                {"$or": [{"parent_user_id": _sas_caller_id}, {"parent_id": _sas_parent_row_id}]}
                if _sas_parent_row_id else {"parent_user_id": _sas_caller_id}
            )
            _sas_link = await gd_find_one(db.session, "guardian_links", {**_sas_id_cond, "student_id": student_id, "is_active": True})
            if _sas_link:
                _sas_perms = _sas_link.get("permissions") or {}
                if not _sas_perms.get("can_view_attendance", True):
                    raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات حضور هذا الطالب")
            else:
                _sas_inactive = await gd_find_one(db.session, "guardian_links", {**_sas_id_cond, "student_id": student_id, "is_active": False})
                if _sas_inactive:
                    raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات حضور هذا الطالب")
                if not _sas_parent or student_id not in (_sas_parent.get("student_ids") or []):
                    raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات حضور هذا الطالب")
        elif _sas_role == "teacher":
            _sas_teacher_id = current_user.get("teacher_id") or _sas_caller_id
            _sas_assign = await gd_find_one(db.session, "teacher_assignments", {"teacher_id": _sas_teacher_id, "class_id": _sas_student.get("class_id")})
            if not _sas_assign:
                raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات حضور هذا الطالب")
        else:
            raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات حضور هذا الطالب")
    else:
        if _sas_role != "platform_admin" and _sas_caller_tenant:
            if _sas_student.get("school_id") and _sas_student["school_id"] != _sas_caller_tenant:
                raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات طالب من مدرسة أخرى")

    total = await gd_count(db.session, "attendance", {"student_id": student_id})
    present = await gd_count(db.session, "attendance", {"student_id": student_id, "status": "present"})
    absent = await gd_count(db.session, "attendance", {"student_id": student_id, "status": "absent"})
    late = await gd_count(db.session, "attendance", {"student_id": student_id, "status": "late"})

    rate = (present / total * 100) if total > 0 else 0

    return {
        "total": total,
        "present": present,
        "absent": absent,
        "late": late,
        "rate": round(rate, 1)
    }


@router.get("/behavior")
async def get_behavior_records(
    class_id: str = Query(None),
    student_id: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get behavior records"""
    _beh_role = current_user.get("role", "")
    _beh_tenant = current_user.get("tenant_id")
    _BEH_ADMIN_ROLES = {"platform_admin", "admin", "super_admin", "school_principal", "school_admin", "school_sub_admin"}

    if _beh_role not in _BEH_ADMIN_ROLES and _beh_role != "teacher":
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول لسجلات السلوك")

    query = {}
    if class_id:
        query["class_id"] = class_id
    if student_id:
        query["student_id"] = student_id

    if _beh_role != "platform_admin" and _beh_tenant:
        query["school_id"] = _beh_tenant

    records = await gd_find(db.session, "behavior", query, order_by="date", desc_order=True, limit=200)
    return records


@router.post("/behavior")
async def create_behavior_record(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Create behavior record - تسجيل ملاحظة سلوكية"""
    _create_beh_role = current_user.get("role", "")
    _CREATE_BEH_ALLOWED = {
        "platform_admin", "admin", "super_admin",
        "school_principal", "school_admin", "school_sub_admin", "teacher"
    }
    if _create_beh_role not in _CREATE_BEH_ALLOWED:
        raise HTTPException(status_code=403, detail="غير مصرح بإضافة سجلات السلوك")

    caller_tenant = current_user.get("tenant_id")

    student_id = data.get("student_id")
    if not student_id:
        raise HTTPException(status_code=422, detail="student_id مطلوب")

    # Always resolve the student record to pin school_id canonically and
    # validate class_id consistency. platform_admin has global scope so no
    # tenant filter is applied, but we still need the student row.
    if _create_beh_role == "platform_admin":
        student = await gd_find_one(db.session, "students", {"id": student_id})
    else:
        student = await gd_find_one(db.session, "students", {"id": student_id, "tenant_id": caller_tenant})

    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود أو لا ينتمي لمدرستك")

    # Derive school_id from the canonical student record — never trust the client.
    canonical_school_id = student.get("school_id") or student.get("tenant_id")

    # Validate class_id consistency: if the caller supplies a class_id it must
    # match the student's enrolled class to prevent intra-tenant data poisoning.
    client_class_id = data.get("class_id")
    student_class_id = student.get("class_id")
    if client_class_id and student_class_id and client_class_id != student_class_id:
        raise HTTPException(status_code=422, detail="class_id لا يتطابق مع فصل الطالب")

    # Pull only the safe, expected fields from the request body;
    # never trust client-supplied school_id, tenant_id, or created_by.
    allowed_fields = {"student_id", "class_id", "type", "description", "points", "date"}
    safe_data = {k: v for k, v in data.items() if k in allowed_fields}

    # Server-side pin: school_id is always derived from the canonical student record.
    if canonical_school_id:
        safe_data["school_id"] = canonical_school_id

    record = {
        "id": str(uuid.uuid4()),
        **safe_data,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }

    await gd_insert(db.session, "behavior", record)
    record.pop("_id", None)

    return {"message": "تم تسجيل الملاحظة السلوكية", "record": record}


@router.get("/classes/{class_id}/student-stats")
async def get_class_student_stats(
    class_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get aggregated stats (attendance, grades, behavior) for all students in a class"""
    if current_user.get("role") not in ADMIN_ROLES:
        teacher_id = current_user.get("teacher_id") or current_user.get("id")
        assignment = await gd_find_one(db.session, "teacher_assignments", {"teacher_id": teacher_id, "class_id": class_id})
        if not assignment:
            class_session = await gd_find_one(db.session, "class_sessions", {"teacher_id": teacher_id, "class_id": class_id})
            if not class_session:
                # IT §6.7 (Task #210) — accepted cross-workspace collab
                # widens read access to this single class.
                from utils.collab_access import caller_can_access_class
                if not await caller_can_access_class(db.session, current_user, class_id):
                    raise HTTPException(status_code=403, detail="ليس لديك صلاحية لعرض هذا الفصل")

    students = await gd_find(db.session, "students", {"class_id": class_id}, limit=100)

    student_ids = [s["id"] for s in students]
    if not student_ids:
        return {}

    att_totals = {}
    att_present = {}

    attendance_pipeline = [
        {"$match": {"student_id": {"$in": student_ids}}},
        {"$group": {
            "_id": "$student_id",
            "total": {"$sum": 1},
            "present": {"$sum": {"$cond": [{"$eq": ["$status", "present"]}, 1, 0]}},
        }}
    ]
    __doc_list = await _gd_aggregate(db.session, "attendance", attendance_pipeline)
    for doc in __doc_list:
        sid = doc["_id"]
        att_totals[sid] = doc["total"]
        att_present[sid] = doc["present"]

    session_att_pipeline = [
        {"$match": {"student_id": {"$in": student_ids}, "is_draft": {"$ne": True}}},
        {"$group": {
            "_id": "$student_id",
            "total": {"$sum": 1},
            "present": {"$sum": {"$cond": [{"$eq": ["$status", "present"]}, 1, 0]}},
        }}
    ]
    __doc_list = await _gd_aggregate(db.session, "session_attendance", session_att_pipeline)
    for doc in __doc_list:
        sid = doc["_id"]
        att_totals[sid] = att_totals.get(sid, 0) + doc["total"]
        att_present[sid] = att_present.get(sid, 0) + doc["present"]

    attendance_results = {}
    for sid in student_ids:
        total = att_totals.get(sid, 0)
        present = att_present.get(sid, 0)
        attendance_results[sid] = round((present / total * 100) if total > 0 else 0, 1)

    grades_pipeline = [
        {"$match": {"student_id": {"$in": student_ids}}},
        {"$group": {
            "_id": "$student_id",
            "avg_score": {"$avg": "$score"},
            "count": {"$sum": 1}
        }}
    ]
    grades_results = {}
    __doc_list = await _gd_aggregate(db.session, "grades", grades_pipeline)
    for doc in __doc_list:
        grades_results[doc["_id"]] = round(doc["avg_score"] or 0, 1)

    behavior_pipeline = [
        {"$match": {"student_id": {"$in": student_ids}}},
        {"$group": {
            "_id": "$student_id",
            "total_points": {"$sum": "$points"},
        }}
    ]
    behavior_results = {}
    __doc_list = await _gd_aggregate(db.session, "behavior", behavior_pipeline)
    for doc in __doc_list:
        behavior_results[doc["_id"]] = doc.get("total_points", 0)

    session_behavior_pipeline = [
        {"$match": {"student_id": {"$in": student_ids}, "interaction_type": "behaviour"}},
        {"$group": {
            "_id": "$student_id",
            "count": {"$sum": 1},
        }}
    ]
    __doc_list = await _gd_aggregate(db.session, "session_interactions", session_behavior_pipeline)
    for doc in __doc_list:
        sid = doc["_id"]
        behavior_results[sid] = behavior_results.get(sid, 0) + doc.get("count", 0)

    result = {}
    for sid in student_ids:
        result[sid] = {
            "attendance_rate": attendance_results.get(sid, 0),
            "average_grade": grades_results.get(sid, 0),
            "behavior_points": behavior_results.get(sid, 0)
        }

    return result


@router.get("/students/{student_id}/analytics")
async def get_student_analytics(
    student_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive analytics for a single student"""
    _ana_role = current_user.get("role", "")
    _ana_tenant = current_user.get("tenant_id")
    _ANA_ADMIN_ROLES = {"platform_admin", "admin", "super_admin", "school_principal", "school_admin", "school_sub_admin"}
    student = await gd_find_one(db.session, "students", {"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    if _ana_role in _ANA_ADMIN_ROLES:
        if _ana_role != "platform_admin" and _ana_tenant:
            if student.get("school_id") and student["school_id"] != _ana_tenant:
                raise HTTPException(status_code=403, detail="لا يمكنك الوصول لبيانات طالب من مدرسة أخرى")
    else:
        teacher_id = current_user.get("teacher_id") or current_user.get("id")
        if student:
            class_id = student.get("class_id")
            assignment = await gd_find_one(db.session, "teacher_assignments", {"teacher_id": teacher_id, "class_id": class_id})
            if not assignment:
                session_check = await gd_find_one(db.session, "class_sessions", {"teacher_id": teacher_id, "class_id": class_id})
                if not session_check:
                    raise HTTPException(status_code=403, detail="ليس لديك صلاحية لعرض بيانات هذا الطالب")

    attendance_records = await gd_find(db.session, "attendance", {"student_id": student_id}, order_by="date", desc_order=True, limit=100)

    session_att_raw = await gd_find(db.session, "session_attendance", {"student_id": student_id, "is_draft": {"$ne": True}}, order_by="recorded_at", desc_order=True, limit=100)

    session_att = []
    for r in session_att_raw:
        date_val = r.get("recorded_at", "")
        if isinstance(date_val, str) and len(date_val) >= 10:
            date_val = date_val[:10]
        session_att.append({"date": date_val, "status": r.get("status")})

    all_attendance = attendance_records + session_att
    total_att = len(all_attendance)
    present_count = sum(1 for r in all_attendance if r.get("status") == "present")
    absent_count = sum(1 for r in all_attendance if r.get("status") == "absent")
    late_count = sum(1 for r in all_attendance if r.get("status") == "late")
    attendance_rate = round((present_count / total_att * 100) if total_att > 0 else 0, 1)

    monthly_attendance = {}
    for r in all_attendance:
        d = r.get("date", "")
        month_key = d[:7] if isinstance(d, str) and len(d) >= 7 else "unknown"
        if month_key == "unknown":
            continue
        if month_key not in monthly_attendance:
            monthly_attendance[month_key] = {"total": 0, "present": 0}
        monthly_attendance[month_key]["total"] += 1
        if r.get("status") == "present":
            monthly_attendance[month_key]["present"] += 1
    attendance_trend = [
        {"month": k, "rate": round(v["present"] / v["total"] * 100, 1) if v["total"] > 0 else 0}
        for k, v in sorted(monthly_attendance.items())
    ]

    grades = await gd_find(db.session, "grades", {"student_id": student_id}, order_by="created_at", desc_order=True, limit=50)
    avg_grade = round(sum(g.get("score", 0) for g in grades) / len(grades), 1) if grades else 0

    interactions = await gd_find(db.session, "session_interactions", {"student_id": student_id}, order_by="recorded_at", desc_order=True, limit=50)

    participation_count = sum(1 for i in interactions if i.get("interaction_type") == "participation")
    behavior_interactions = [i for i in interactions if i.get("interaction_type") == "behaviour"]

    interaction_records = []
    for i in interactions:
        itype = i.get("interaction_type", "")
        note = ""
        if itype == "participation":
            note = i.get("participation_type", "مشاركة")
        elif itype == "behaviour":
            note = i.get("behaviour_details") or i.get("behaviour_type") or "سلوك"
        elif itype == "question":
            note = i.get("answer_result", "سؤال")
        interaction_records.append({
            "type": itype,
            "note": note,
            "created_at": i.get("recorded_at", "")
        })

    skills = await gd_find(db.session, "student_skills", {"student_id": student_id}, order_by="recorded_at", desc_order=True, limit=50)

    behavior_records = await gd_find(db.session, "behavior", {"student_id": student_id}, order_by="date", desc_order=True, limit=20)

    total_behavior = sum(r.get("points", 0) for r in behavior_records) + len(behavior_interactions)

    session_beh_records = []
    for b in behavior_interactions:
        session_beh_records.append({
            "note": b.get("behaviour_details") or b.get("behaviour_type") or "سلوك",
            "points": 1 if b.get("behaviour_category") == "positive" else -1,
            "created_at": b.get("recorded_at", "")
        })

    return {
        "attendance": {
            "rate": attendance_rate,
            "total": total_att,
            "present": present_count,
            "absent": absent_count,
            "late": late_count,
            "trend": attendance_trend,
            "recent": all_attendance[:10]
        },
        "grades": {
            "average": avg_grade,
            "count": len(grades),
            "records": grades[:10]
        },
        "participation": {
            "total_interactions": len(interactions),
            "participation_count": participation_count,
            "recent": interaction_records[:10]
        },
        "behavior": {
            "total_points": total_behavior,
            "records": behavior_records[:10],
            "session_records": session_beh_records[:10]
        },
        "skills": skills[:20]
    }


@router.get("/resources")
async def get_resources(
    teacher_id: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get educational resources"""
    query = {}
    if teacher_id:
        query["teacher_id"] = teacher_id
    
    resources = await gd_find(db.session, "resources", query, order_by="created_at", desc_order=True, limit=100)
    return resources


@router.post("/resources")
async def create_resource(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Create educational resource - إضافة مصدر تعليمي"""
    resource = {
        "id": str(uuid.uuid4()),
        **data,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await gd_insert(db.session, "resources", resource)
    resource.pop("_id", None)
    
    return {"message": "تمت إضافة المصدر", "resource": resource}


@router.delete("/resources/{resource_id}")
async def delete_resource(
    resource_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete resource"""
    await gd_delete_one(db.session, "resources", {"id": resource_id})
    return {"message": "تم حذف المصدر"}


@router.get("/messages")
async def get_messages(
    sender_id: str = Query(None),
    recipient_id: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get messages filtered by sender or recipient"""
    query = {}
    caller_id = current_user.get("teacher_id") or current_user.get("id")
    _msg_role = current_user.get("role", "")
    _msg_tenant = current_user.get("tenant_id")
    _MSG_SCOPE_ROLES = ("platform_admin", "school_principal", "school_admin")

    if sender_id:
        if sender_id != caller_id and _msg_role not in _MSG_SCOPE_ROLES:
            raise HTTPException(status_code=403, detail="غير مصرح")
        if sender_id != caller_id and _msg_role in ("school_principal", "school_admin"):
            _msg_target_user = await gd_find_one(db.session, "users", {"id": sender_id})
            if _msg_tenant and _msg_target_user and _msg_target_user.get("tenant_id") != _msg_tenant:
                raise HTTPException(status_code=403, detail="لا يمكنك الوصول لرسائل مستخدم من مدرسة أخرى")
        query["sender_id"] = sender_id
    elif recipient_id:
        if recipient_id != caller_id and _msg_role not in _MSG_SCOPE_ROLES:
            raise HTTPException(status_code=403, detail="غير مصرح")
        if recipient_id != caller_id and _msg_role in ("school_principal", "school_admin"):
            _msg_target_user = await gd_find_one(db.session, "users", {"id": recipient_id})
            if _msg_tenant and _msg_target_user and _msg_target_user.get("tenant_id") != _msg_tenant:
                raise HTTPException(status_code=403, detail="لا يمكنك الوصول لرسائل مستخدم من مدرسة أخرى")
        query["$or"] = [{"recipient_ids": recipient_id}, {"recipient_id": recipient_id}]
    else:
        query["$or"] = [{"sender_id": caller_id}, {"recipient_ids": caller_id}, {"recipient_id": caller_id}]

    if _msg_role != "platform_admin" and _msg_tenant:
        query["school_id"] = _msg_tenant

    messages = await gd_find(db.session, "messages", query, order_by="created_at", desc_order=True, limit=100)
    return messages


@router.post("/messages")
async def send_message(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Send message to parents - إرسال رسالة لأولياء الأمور"""
    sender_user_id = current_user.get("id")
    _snd_role = current_user.get("role", "")

    if _snd_role == "parent":
        raise HTTPException(
            status_code=403,
            detail="أولياء الأمور يجب أن يستخدموا نقطة النهاية /parent-portal/quick-message لإرسال الرسائل"
        )

    raw_recipients = data.get("recipient_ids") or []
    if isinstance(raw_recipients, str):
        raw_recipients = [raw_recipients]
    single = data.get("recipient_id")
    if single and single not in raw_recipients:
        raw_recipients.append(single)

    _snd_tenant = current_user.get("tenant_id")

    resolved_recipient_id = None
    for rid in raw_recipients:
        if not rid:
            continue
        user = await gd_find_one(db.session, "users", {"id": rid})
        if user:
            if _snd_role != "platform_admin" and _snd_tenant:
                if user.get("tenant_id") and user["tenant_id"] != _snd_tenant:
                    raise HTTPException(status_code=403, detail="لا يمكنك إرسال رسائل لمستخدمين من مدرسة أخرى")
            resolved_recipient_id = user["id"]
            break
        student = await gd_find_one(db.session, "students", {"id": rid})
        if not student:
            student = await gd_find_one(db.session, "students", {"parent_id": rid})
        if student:
            if _snd_role != "platform_admin" and _snd_tenant:
                if student.get("school_id") and student["school_id"] != _snd_tenant:
                    raise HTTPException(status_code=403, detail="لا يمكنك إرسال رسائل لطلاب من مدرسة أخرى")
            parent_user = None
            if student.get("parent_email"):
                parent_user = await gd_find_one(db.session, "users", {"email": student["parent_email"], "role": "parent"})
            if not parent_user and student.get("parent_phone"):
                parent_user = await gd_find_one(db.session, "users", {"phone": student["parent_phone"], "role": "parent"})
            if not parent_user and student.get("parent_name"):
                parent_user = await gd_find_one(db.session, "users", {"full_name": student["parent_name"], "role": "parent"})
            if parent_user:
                if _snd_role != "platform_admin" and _snd_tenant:
                    if parent_user.get("tenant_id") and parent_user["tenant_id"] != _snd_tenant:
                        raise HTTPException(status_code=403, detail="لا يمكنك إرسال رسائل لمستخدمين من مدرسة أخرى")
                resolved_recipient_id = parent_user["id"]
                break

    message_doc = {
        "id": str(uuid.uuid4()),
        "sender_id": sender_user_id,
        "recipient_id": resolved_recipient_id,
        "school_id": current_user.get("tenant_id"),
        "subject": data.get("subject"),
        "body": data.get("body"),
        "is_read": False,
        "read_at": None,
        "created_at": datetime.now(timezone.utc),
    }

    await gd_insert(db.session, "messages", message_doc)

    return {"message": "تم إرسال الرسالة", "data": {"id": message_doc["id"]}}


@router.get("/grades")
async def get_grades(
    class_id: str = Query(None),
    student_id: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get grades with filters"""
    _gr_role = current_user.get("role", "")
    _gr_tenant = current_user.get("tenant_id")
    _GR_ADMIN_ROLES = {"platform_admin", "admin", "super_admin", "school_principal", "school_admin", "school_sub_admin"}

    if _gr_role not in _GR_ADMIN_ROLES and _gr_role != "teacher":
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول لسجلات الدرجات")

    if not class_id and not student_id and _gr_role not in ("platform_admin", "admin", "super_admin"):
        raise HTTPException(status_code=400, detail="يجب تحديد فصل أو طالب لعرض الدرجات")

    query = {}
    if class_id:
        assessments = await gd_find(db.session, "assessments", {"class_id": class_id}, limit=100)
        assessment_ids = [a.get("id") for a in assessments]
        query["assessment_id"] = {"$in": assessment_ids}
    if student_id:
        query["student_id"] = student_id

    if _gr_role != "platform_admin" and _gr_tenant:
        query["school_id"] = _gr_tenant

    grades = await gd_find(db.session, "grades", query, limit=500)
    return grades


@router.get("/users/{user_id}/notifications/settings")
async def get_notification_settings(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get user notification settings (self or admin only)"""
    caller_id = current_user.get("id")
    _ns_role = current_user.get("role", "")
    _ns_tenant = current_user.get("tenant_id")
    if user_id != caller_id:
        if _ns_role not in ("platform_admin", "school_principal", "school_admin"):
            raise HTTPException(status_code=403, detail="غير مصرح بالوصول لإعدادات مستخدم آخر")
        if _ns_role in ("school_principal", "school_admin"):
            _ns_target = await gd_find_one(db.session, "users", {"id": user_id})
            if _ns_tenant and _ns_target and _ns_target.get("tenant_id") != _ns_tenant:
                raise HTTPException(status_code=403, detail="لا يمكنك الوصول لإعدادات مستخدم من مدرسة أخرى")
    settings = await gd_find_one(db.session, "notification_settings", {"user_id": user_id})
    return settings or {}


@router.put("/users/{user_id}/notifications/settings")
async def update_notification_settings(
    user_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Update user notification settings (self or admin only)"""
    caller_id = current_user.get("id")
    _nsu_role = current_user.get("role", "")
    _nsu_tenant = current_user.get("tenant_id")
    if user_id != caller_id:
        if _nsu_role not in ("platform_admin", "school_principal", "school_admin"):
            raise HTTPException(status_code=403, detail="غير مصرح بتعديل إعدادات مستخدم آخر")
        if _nsu_role in ("school_principal", "school_admin"):
            _nsu_target = await gd_find_one(db.session, "users", {"id": user_id})
            if _nsu_tenant and _nsu_target and _nsu_target.get("tenant_id") != _nsu_tenant:
                raise HTTPException(status_code=403, detail="لا يمكنك تعديل إعدادات مستخدم من مدرسة أخرى")
    await gd_update_one(db.session, "notification_settings", {"user_id": user_id}, {**data, "updated_at": datetime.now(timezone.utc).isoformat()})
    return {"message": "تم حفظ الإعدادات"}


# Task #470: the legacy `PUT /users/{user_id}/password` handler was
# removed. It referenced an unbound `pwd_context` (passlib was never
# imported in this module), raised `NameError` → HTTP 500 on every
# call, and bypassed the security side-effects (audit log, refresh
# token revocation, `last_password_change`, MFA step-up) that the
# canonical `POST /auth/change-password` already enforces. All
# callers (Parent dialog, Teacher settings) have been repointed to
# `/auth/change-password`. Do not re-introduce this route.


@router.get("/teacher/profile/{teacher_id}/activity")
async def get_teacher_activity_log(
    teacher_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user)
):
    """Get teacher's own activity log for Profile & Settings page"""
    caller_id = current_user.get("teacher_id") or current_user.get("id")
    caller_role = current_user.get("role", "")
    if teacher_id != caller_id and caller_role not in ("platform_admin", "school_principal", "school_admin"):
        raise HTTPException(status_code=403, detail="غير مصرح")

    user = await gd_find_one(db.session, "users", {"$or": [{"id": teacher_id}, {"teacher_id": teacher_id}]})

    if teacher_id != caller_id and caller_role in ("school_principal", "school_admin"):
        caller_tenant = current_user.get("tenant_id")
        target_tenant = user.get("tenant_id") if user else None
        if caller_tenant and target_tenant and caller_tenant != target_tenant:
            raise HTTPException(status_code=403, detail="غير مصرح بالوصول لبيانات مدرسة أخرى")
    user_id = user.get("id") if user else teacher_id

    activities = await gd_find(db.session, "audit_logs", {"$or": [
            {"performed_by": user_id},
            {"action_by": user_id},
            {"performed_by": teacher_id},
            {"action_by": teacher_id},
        ]}, order_by="timestamp", desc_order=True, limit=limit)

    action_labels = {
        "auth.login": {"ar": "تسجيل دخول", "en": "Login", "icon": "login"},
        "auth.logout": {"ar": "تسجيل خروج", "en": "Logout", "icon": "logout"},
        "session.start": {"ar": "بدء حصة", "en": "Start Session", "icon": "session"},
        "session.end": {"ar": "إنهاء حصة", "en": "End Session", "icon": "session"},
        "attendance.record": {"ar": "تسجيل حضور", "en": "Record Attendance", "icon": "attendance"},
        "attendance.create": {"ar": "تسجيل حضور", "en": "Record Attendance", "icon": "attendance"},
        "behavior.create": {"ar": "تسجيل سلوك", "en": "Record Behavior", "icon": "behavior"},
        "grade.create": {"ar": "تسجيل درجات", "en": "Record Grades", "icon": "grade"},
        "message.send": {"ar": "إرسال رسالة", "en": "Send Message", "icon": "message"},
        "user.update": {"ar": "تحديث بيانات", "en": "Update Profile", "icon": "profile"},
        "user_updated": {"ar": "تحديث بيانات", "en": "Update Profile", "icon": "profile"},
        "password.change": {"ar": "تغيير كلمة المرور", "en": "Password Change", "icon": "security"},
    }

    formatted = []
    for act in activities:
        action = act.get("action", "")
        label_info = action_labels.get(action, {"ar": action, "en": action, "icon": "other"})
        formatted.append({
            "id": act.get("id", ""),
            "action": action,
            "label_ar": label_info["ar"],
            "label_en": label_info["en"],
            "icon": label_info["icon"],
            "description": act.get("description", act.get("details", "")),
            "timestamp": act.get("timestamp", act.get("created_at", "")),
            "entity_type": act.get("entity_type", ""),
            "page": act.get("page", act.get("path", "")),
        })

    return {"activities": formatted, "total": len(formatted)}



# ============== TEACHER SESSION ENGINE APIs ==============

ADMIN_ROLES = {"admin", "super_admin", "platform_admin", "school_admin"}

async def _verify_session_owner(session_id: str, current_user: dict):
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
    caller_teacher = current_user.get("teacher_id") or current_user.get("id")
    if session.get("teacher_id") and session["teacher_id"] != caller_teacher:
        if current_user.get("role") not in ADMIN_ROLES:
            raise HTTPException(status_code=403, detail="ليس لديك صلاحية على هذه الجلسة")


@router.post("/session/start")
async def start_class_session(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    بدء حصة جديدة
    Start a new class session
    
    Required fields:
    - schedule_session_id: ID from schedule_sessions
    - teacher_id: Teacher ID
    - class_id: Class ID
    - subject_id: Subject ID
    """
    caller_teacher = current_user.get("teacher_id") or current_user.get("id")
    requested_teacher = data.get("teacher_id") or caller_teacher
    if requested_teacher != caller_teacher and current_user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="لا يمكنك بدء حصة لمعلم آخر")
    result = await session_engine.start_session(
        teacher_id=requested_teacher,
        schedule_session_id=data.get("schedule_session_id"),
        class_id=data.get("class_id"),
        subject_id=data.get("subject_id"),
        force_new=data.get("force_new") is True
    )
    return result


@router.get("/session/current")
async def get_current_session(
    schedule_session_id: str = None,
    current_user: dict = Depends(get_current_user)
):
    """Get current in-progress session by schedule session ID or any active session for teacher"""
    teacher_id = current_user.get("teacher_id") or current_user.get("id")
    active_statuses = ["in_progress", "session_opened", "attendance_in_progress",
                       "attendance_approved", "teaching_in_progress", "interaction_running",
                       "session_review"]
    
    if schedule_session_id:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        query = {
            "schedule_session_id": schedule_session_id,
            "date": today,
            "status": {"$in": active_statuses}
        }
        if teacher_id:
            query["teacher_id"] = teacher_id
        session = await gd_find_one(db.session, "class_sessions", query)
    else:
        session = await gd_find_one(db.session, "class_sessions", {
            "teacher_id": teacher_id,
            "status": {"$in": active_statuses}
        })
    
    if not session:
        raise HTTPException(status_code=404, detail="لا توجد جلسة جارية")
    
    class_info = await gd_find_one(db.session, "classes", {"id": session.get("class_id")})
    subject = await gd_find_one(db.session, "subjects", {"id": session.get("subject_id")})
    teacher = await gd_find_one(db.session, "teachers", {"id": session.get("teacher_id")})
    
    student_count = await gd_count(db.session, "session_attendance", {"session_id": session.get("id")})
    
    return {
        "session_record_id": session.get("id"),
        "session_status": session.get("status"),
        "start_time": session.get("start_time"),
        "class_name": class_info.get("name") if class_info else "فصل",
        "subject_name": (subject.get("name_ar") or subject.get("name")) if subject else "مادة",
        "teacher_name": teacher.get("full_name") if teacher else "معلم",
        "student_count": student_count,
        "session_id": session.get("id"),
        "class_id": session.get("class_id"),
        "subject_id": session.get("subject_id"),
        "schedule_session_id": session.get("schedule_session_id")
    }


@router.get("/session/{session_id}")
async def get_session_info(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get session information"""
    await _verify_session_owner(session_id, current_user)
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
    return session


@router.get("/session/by-schedule/{schedule_session_id}")
async def get_session_by_schedule_id(
    schedule_session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get session information by schedule session ID"""
    session = await gd_find_one(db.session, "class_sessions", {"schedule_session_id": schedule_session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
    await _verify_session_owner(session["id"], current_user)
    return session


@router.get("/session/{session_id}/students")
async def get_session_students(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    جلب قائمة الطلاب للحصة مع حالة الحضور
    Get students list with attendance status for session
    """
    await _verify_session_owner(session_id, current_user)
    students = await session_engine.get_session_students(session_id)
    return {
        "session_id": session_id,
        "total": len(students),
        "students": students
    }


@router.put("/session/{session_id}/attendance/{student_id}")
async def update_student_attendance(
    session_id: str,
    student_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    تحديث حالة حضور طالب
    Update student attendance status
    """
    await _verify_session_owner(session_id, current_user)
    from engines.session_engine import AttendanceStatus
    status = AttendanceStatus(data.get("status", "present"))
    result = await session_engine.update_attendance(
        session_id=session_id,
        student_id=student_id,
        status=status,
        teacher_id=current_user["id"]
    )
    return result


@router.post("/session/{session_id}/attendance/approve")
async def approve_session_attendance(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    اعتماد الحضور
    Approve and finalize attendance
    """
    await _verify_session_owner(session_id, current_user)
    result = await session_engine.approve_attendance(
        session_id=session_id,
        teacher_id=current_user["id"]
    )
    return result


@router.post("/session/{session_id}/mode")
async def set_session_mode(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    تحديد نمط التفاعل (متابعة واجب / مراجعة / امتحان مفاجئ)
    Set interaction mode (homework / review / quiz)
    """
    await _verify_session_owner(session_id, current_user)
    mode = data.get("mode", "review")
    teacher_id = current_user.get("teacher_id") or current_user["id"]
    result = await session_engine.set_interaction_mode(session_id, mode, teacher_id=teacher_id)
    return result


@router.post("/session/{session_id}/random-student")
async def select_random_student(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    اختيار طالب عشوائي
    Select random student using fair algorithm
    """
    await _verify_session_owner(session_id, current_user)
    result = await session_engine.select_random_student(session_id)
    return result


@router.post("/session/{session_id}/answer")
async def record_student_answer(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    تسجيل إجابة الطالب
    Record student answer (correct/wrong/no_answer)
    """
    await _verify_session_owner(session_id, current_user)
    from engines.session_engine import AnswerResult
    result = await session_engine.record_answer(
        session_id=session_id,
        student_id=data.get("student_id"),
        result=AnswerResult(data.get("result", "correct")),
        teacher_id=current_user["id"]
    )
    return result


@router.get("/session/{session_id}/activity")
async def get_session_activity(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    log = await session_engine.get_activity_log(session_id, limit=50)
    return {"activity": log}


@router.post("/session/{session_id}/participation")
async def record_student_participation(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    تسجيل مشاركة الطالب
    Record student participation
    """
    await _verify_session_owner(session_id, current_user)
    from engines.session_engine import ParticipationType
    result = await session_engine.record_participation(
        session_id=session_id,
        student_id=data.get("student_id"),
        participation_type=ParticipationType(data.get("type", "active")),
        teacher_id=current_user["id"]
    )
    return result


@router.post("/session/{session_id}/behaviour")
async def record_student_behaviour(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    تسجيل سلوك الطالب
    Record student behaviour (positive/negative/skill)
    """
    await _verify_session_owner(session_id, current_user)
    from engines.session_engine import BehaviourCategory
    result = await session_engine.record_behaviour(
        session_id=session_id,
        student_id=data.get("student_id"),
        category=BehaviourCategory(data.get("category", "positive")),
        behaviour_type=data.get("behaviour_type"),
        details=data.get("details"),
        teacher_id=current_user["id"]
    )
    return result


@router.post("/session/{session_id}/homework")
async def record_homework_status(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    تسجيل حالة الواجب (حل / ما حل)
    Record homework status (done / not_done) for a single student
    """
    await _verify_session_owner(session_id, current_user)
    teacher_id = current_user.get("teacher_id") or current_user["id"]
    result = await session_engine.record_homework(
        session_id=session_id,
        student_id=data.get("student_id"),
        status=data.get("status", "done"),
        teacher_id=teacher_id
    )
    return result


@router.get("/session/{session_id}/homework")
async def get_homework_statuses(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    جلب حالات الواجب لجميع الطلاب
    Get homework statuses for all students in session
    """
    await _verify_session_owner(session_id, current_user)
    statuses = await session_engine.get_homework_statuses(session_id)
    return {"statuses": statuses}


@router.post("/session/{session_id}/homework/bulk")
async def bulk_record_homework(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    حفظ حالات الواجب لجميع الطلاب دفعة واحدة
    Bulk save homework statuses
    """
    await _verify_session_owner(session_id, current_user)
    teacher_id = current_user.get("teacher_id") or current_user["id"]
    result = await session_engine.bulk_record_homework(
        session_id=session_id,
        records=data.get("records", []),
        teacher_id=teacher_id
    )
    return result


@router.post("/session/{session_id}/seating")
async def update_seating_order(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    حفظ ترتيب جلوس الطلاب
    Save student seating order
    """
    await _verify_session_owner(session_id, current_user)
    teacher_id = current_user.get("teacher_id") or current_user["id"]
    result = await session_engine.update_seating_order(
        session_id=session_id,
        student_order=data.get("student_order", []),
        teacher_id=teacher_id
    )
    return result


@router.get("/session/{session_id}/review-preview")
async def get_session_review_preview(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    مراجعة ملخص الحصة قبل الإنهاء
    Get session review preview before ending (Section 7.5)
    """
    await _verify_session_owner(session_id, current_user)
    result = await session_engine.get_review_preview(
        session_id=session_id,
        teacher_id=current_user["id"]
    )
    return result


@router.post("/session/{session_id}/end")
async def end_class_session(
    session_id: str,
    request: Request = None,
    current_user: dict = Depends(get_current_user)
):
    """
    إنهاء الحصة
    End class session and get summary
    """
    await _verify_session_owner(session_id, current_user)
    closing_note = None
    try:
        body = await request.json()
        closing_note = body.get("closing_note") if body else None
    except Exception as e:
        logger.debug(f"No JSON body provided for end_session (optional): {e}")
    result = await session_engine.end_session(
        session_id=session_id,
        teacher_id=current_user["id"],
        closing_note=closing_note
    )
    return result


@router.get("/session/{session_id}/export-report")
async def export_session_report(
    session_id: str,
    format: str = "csv",
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    teacher_id = current_user.get("teacher_id") or current_user["id"]
    result = await session_engine.export_session_report(session_id, teacher_id, format)
    return result


@router.get("/student/{student_id}/score")
async def get_student_score(
    student_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    جلب نقاط الطالب
    Get student score information
    """
    from utils.tenant_scope import can_view_student, require_can_view_student_sync_check
    allowed = await can_view_student(db.session, current_user, student_id)
    require_can_view_student_sync_check(allowed)
    result = await session_engine.get_student_score(student_id)
    return result


@router.get("/session/behaviour-types/all")
async def get_behaviour_types(
    current_user: dict = Depends(get_current_user)
):
    """
    جلب أنواع السلوكيات المتاحة
    Get available behaviour types
    """
    from engines.session_engine import DEFAULT_BEHAVIOUR_TYPES
    return DEFAULT_BEHAVIOUR_TYPES


@router.get("/teacher/{teacher_id}/class-metrics")
async def get_teacher_class_metrics(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    جلب مقاييس الفصول الحقيقية للمعلم
    Get real class metrics for a teacher (attendance, participation, performance)
    """
    _verify_teacher_access(teacher_id, current_user)
    teacher = await _resolve_teacher_record(teacher_id)
    _check_teacher_tenant(teacher, current_user)
    resolved_teacher_id = teacher.get("id") if teacher else teacher_id
    assignments = await gd_find(db.session, "teacher_assignments", {"teacher_id": resolved_teacher_id, "is_active": True}, limit=200)
    class_ids_from_ta = set(a.get("class_id") for a in assignments if a.get("class_id"))

    tca_docs = await gd_find(db.session, "teacher_class_assignments", {"teacher_id": resolved_teacher_id}, limit=200)
    class_ids_from_tca = set(d.get("class_id") for d in tca_docs if d.get("class_id"))

    all_class_ids = list(class_ids_from_ta | class_ids_from_tca)
    metrics = {}
    for class_id in all_class_ids:
        metrics[class_id] = await session_engine.get_class_metrics(resolved_teacher_id, class_id)
    return metrics


@router.get("/skills-types")
async def get_skills_types(
    current_user: dict = Depends(get_current_user)
):
    """
    جلب أنواع المهارات المتاحة
    Get all available skill types
    """
    skills = await gd_find(db.session, "skills_types", {}, limit=100)
    if not skills:
        from engines.session_engine import DEFAULT_SKILLS_TYPES
        now = datetime.now(timezone.utc).isoformat()
        for s in DEFAULT_SKILLS_TYPES:
            s["created_at"] = now
        await gd_insert_many(db.session, "skills_types", [dict(s) for s in DEFAULT_SKILLS_TYPES])
        if audit_engine:
            try:
                await audit_engine.log(
                    action=AuditAction.SYSTEM_CONFIG,
                    performed_by=current_user.get("id", "system"),
                    details={"event": "skills_types_seeded", "count": len(DEFAULT_SKILLS_TYPES)}
                )
            except Exception:
                logger.debug("Skipped audit log for skills_types seed (FK constraint)")
        skills = await gd_find(db.session, "skills_types", {}, limit=100)
    return skills


@router.post("/skills-types")
async def create_skill_type(
    data: dict = Body(...),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL]))
):
    """
    إنشاء نوع مهارة جديد
    Create a new skill type (admin only)
    """
    now = datetime.now(timezone.utc)
    skill = {
        "id": f"skill-{str(uuid.uuid4())[:8]}",
        "name": data.get("name", ""),
        "name_ar": data.get("name_ar", ""),
        "description": data.get("description", ""),
        "category": data.get("category", "general"),
        "created_at": now.isoformat()
    }
    await gd_insert(db.session, "skills_types", skill)
    if audit_engine:
        await audit_engine.log(
            action=AuditAction.SYSTEM_CONFIG,
            performed_by=current_user.get("id"),
            details={"event": "skill_type_created", "skill_id": skill["id"], "name": skill["name"]}
        )
    return {"message": "تم إنشاء نوع المهارة", "skill": {k: v for k, v in skill.items() if k != "_id"}}


@router.post("/session/{session_id}/skill")
async def record_session_skill(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    تسجيل مهارة لطالب خلال الحصة
    Record a skill for a student during a session
    """
    await _verify_session_owner(session_id, current_user)
    teacher_id = current_user["id"]
    result = await session_engine.record_skill(
        session_id=session_id,
        student_id=data.get("student_id"),
        skill_type_id=data.get("skill_type_id"),
        teacher_id=teacher_id,
        notes=data.get("notes"),
        custom_name=data.get("custom_name"),
        points_override=data.get("points_override"),
    )
    if audit_engine:
        await audit_engine.log(
            action=AuditAction.DATA_MODIFY,
            performed_by=teacher_id,
            details={
                "event": "skill_recorded",
                "session_id": session_id,
                "student_id": data.get("student_id"),
                "skill_type_id": data.get("skill_type_id")
            }
        )
    return result


@router.post("/session/{session_id}/note")
async def add_session_note(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    teacher_id = current_user.get("teacher_id") or current_user["id"]
    result = await session_engine.add_note(
        session_id=session_id,
        teacher_id=teacher_id,
        text=data.get("text", ""),
        note_type=data.get("note_type", "session"),
        student_id=data.get("student_id"),
        student_ids=data.get("student_ids")
    )
    return result


@router.get("/session/{session_id}/notes")
async def get_session_notes(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    notes = await session_engine.get_session_notes(session_id)
    return {"session_id": session_id, "notes": notes}


@router.post("/session/{session_id}/note/parents")
async def broadcast_session_note_to_parents(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Save a quick note and dispatch a notification to the parents of selected students."""
    await _verify_session_owner(session_id, current_user)
    teacher_id = current_user.get("teacher_id") or current_user["id"]
    tenant_id = current_user.get("tenant_id") or current_user.get("school_id")

    text = (data.get("text") or "").strip()
    student_ids = data.get("student_ids") or []
    if not text:
        raise HTTPException(status_code=400, detail="نص الملاحظة مطلوب")
    if not isinstance(student_ids, list) or len(student_ids) == 0:
        raise HTTPException(status_code=400, detail="حدد طالباً واحداً على الأقل")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="سياق المدرسة مفقود")

    # Authorization: student_ids must belong to this session's roster
    roster = await gd_find(db.session, "session_attendance", {"session_id": session_id}, limit=500)
    roster_ids = {r.get("student_id") for r in roster if r.get("student_id")}
    requested_ids = {str(sid) for sid in student_ids if sid}
    valid_ids = [sid for sid in requested_ids if sid in roster_ids]
    skipped_ids = sorted(requested_ids - roster_ids)
    if not valid_ids:
        raise HTTPException(status_code=403, detail="الطلاب المحددون ليسوا ضمن هذه الحصة")

    # 1) save the note record (only with the validated subset)
    note_result = await session_engine.add_note(
        session_id=session_id,
        teacher_id=teacher_id,
        text=text,
        note_type="parent",
        student_id=None,
        student_ids=valid_ids,
    )

    # 2) fetch session + class info for context
    session_row = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    class_id = session_row.get("class_id") if session_row else None
    subject_id = session_row.get("subject_id") if session_row else None
    subject_name = ""
    class_name = ""
    if subject_id:
        subj = await gd_find_one(db.session, "subjects", {"id": subject_id})
        subject_name = (subj or {}).get("name") or (subj or {}).get("name_ar") or ""
    if class_id:
        cls = await gd_find_one(db.session, "classes", {"id": class_id})
        class_name = (cls or {}).get("name") or (cls or {}).get("name_ar") or ""

    # 3) build student-name map (validated subset only, tenant-scoped)
    students_map: Dict[str, str] = {}
    for sid in valid_ids:
        s = await gd_find_one(db.session, "students", {"id": sid, "tenant_id": tenant_id})
        if s:
            students_map[sid] = s.get("full_name") or s.get("name") or ""

    # 4) for each student, locate parent USER ids (notifications.user_id is
    # a users.id, not a parents.id). Three sources are merged, all bulk
    # and tenant-scoped to avoid N+1:
    #   (a) user_relationships (parent_of / guardian_of)
    #   (b) students.parent_id -> parents.id -> users (role=parent,
    #       users.parent_id = parents.id)   ← canonical school-student
    #       linkage missed by the old single-source lookup, which was
    #       the source of the false-positive "no parent linked" warning.
    #   (c) guardian_links (active links only) — parent_user_id when
    #       present, else resolved via parent_id -> users bridge.
    student_to_parent_user_ids: Dict[str, set] = {sid: set() for sid in valid_ids}

    # (a) user_relationships — bulk
    try:
        rels = await gd_find(
            db.session,
            "user_relationships",
            {
                "to_entity_type": "student",
                "status": "active",
                "tenant_id": tenant_id,
                "to_entity_id": {"$in": list(valid_ids)},
                "relationship_type": {"$in": ["parent_of", "guardian_of"]},
            },
            limit=2000,
        )
        for r in rels:
            sid = r.get("to_entity_id")
            pid = r.get("from_entity_id")
            if sid in student_to_parent_user_ids and pid:
                student_to_parent_user_ids[sid].add(pid)
    except Exception as e:  # noqa: BLE001
        logger.warning("Bulk user_relationships lookup failed: %s", e)

    # (b) students.parent_id -> parents.id -> users.parent_id
    try:
        student_rows = await gd_find(
            db.session,
            "students",
            {"id": {"$in": list(valid_ids)}, "tenant_id": tenant_id},
            limit=2000,
        )
        parent_record_to_students: Dict[str, list] = {}
        for s in student_rows:
            prid = s.get("parent_id")
            if prid:
                parent_record_to_students.setdefault(prid, []).append(s.get("id"))
        if parent_record_to_students:
            parent_user_rows = await gd_find(
                db.session,
                "users",
                {
                    "parent_id": {"$in": list(parent_record_to_students.keys())},
                    "role": "parent",
                    "tenant_id": tenant_id,
                },
                limit=2000,
            )
            for u in parent_user_rows:
                uid = u.get("id")
                prid = u.get("parent_id")
                if not (uid and prid):
                    continue
                for sid in parent_record_to_students.get(prid, []):
                    if sid in student_to_parent_user_ids:
                        student_to_parent_user_ids[sid].add(uid)
    except Exception as e:  # noqa: BLE001
        logger.warning("students.parent_id parent bridge lookup failed: %s", e)

    # (c) guardian_links — bulk, active only
    try:
        glinks = await gd_find(
            db.session,
            "guardian_links",
            {
                "tenant_id": tenant_id,
                "student_id": {"$in": list(valid_ids)},
                "is_active": True,
            },
            limit=2000,
        )
        unresolved_parent_record_ids: set = set()
        link_pending: list = []
        for ln in glinks:
            sid = ln.get("student_id")
            if sid not in student_to_parent_user_ids:
                continue
            puid = ln.get("parent_user_id")
            if puid:
                student_to_parent_user_ids[sid].add(puid)
                continue
            prid = ln.get("parent_id")
            if prid:
                unresolved_parent_record_ids.add(prid)
                link_pending.append((sid, prid))
        if unresolved_parent_record_ids:
            bridge_rows = await gd_find(
                db.session,
                "users",
                {
                    "parent_id": {"$in": list(unresolved_parent_record_ids)},
                    "role": "parent",
                    "tenant_id": tenant_id,
                },
                limit=2000,
            )
            prid_to_uid: Dict[str, str] = {}
            for u in bridge_rows:
                if u.get("parent_id") and u.get("id"):
                    prid_to_uid[u["parent_id"]] = u["id"]
            for sid, prid in link_pending:
                uid = prid_to_uid.get(prid)
                if uid:
                    student_to_parent_user_ids[sid].add(uid)
    except Exception as e:  # noqa: BLE001
        logger.warning("guardian_links bulk lookup failed: %s", e)

    sent = 0
    failed = 0
    students_with_parents = 0
    seen_pairs: set = set()

    for sid in valid_ids:
        parent_user_ids = student_to_parent_user_ids.get(sid) or set()
        if parent_user_ids:
            students_with_parents += 1
        for pid in parent_user_ids:
            key = (pid, sid)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            child_name = students_map.get(sid, "")
            title = f"ملاحظة من المعلم — {child_name}".strip() if child_name else "ملاحظة من المعلم"
            meta = {
                "session_id": session_id,
                "student_id": sid,
                "student_name": child_name,
                "subject_name": subject_name,
                "class_name": class_name,
                "note_id": note_result.get("note_id"),
                "source": "session_quick_note",
            }
            notif = {
                "id": str(uuid.uuid4()),
                "user_id": pid,
                "tenant_id": tenant_id,
                "title": title,
                "message": text,
                "type": "communication",
                "priority": "medium",
                "is_read": False,
                "data": meta,
                "created_at": datetime.now(timezone.utc),
            }
            try:
                await gd_insert(db.session, "notifications", notif)
                sent += 1
            except Exception as e:  # noqa: BLE001
                failed += 1
                logger.warning("Failed inserting parent notification (parent=%s student=%s): %s", pid, sid, e)

    # 5) auto-capture portfolio evidence: parent communication log
    if sent > 0:
        try:
            from engines.portfolio_evidence_engine import PortfolioEvidenceEngine
            _pe = PortfolioEvidenceEngine(db)
            _today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            _names_preview = ", ".join([n for n in students_map.values() if n][:3])
            _more = max(0, students_with_parents - 3)
            _names_str = _names_preview + (f" +{_more}" if _more > 0 else "")
            await _pe.capture_evidence(
                teacher_id=teacher_id,
                school_id=tenant_id,
                evidence_type="parent_communication_log",
                title_ar=f"تواصل مع أولياء الأمور — {subject_name or 'حصة'}".strip(),
                title_en=f"Parent Communication — {subject_name or 'Session'}".strip(),
                description_ar=(f"ملاحظة لأولياء أمور: {_names_str}" if _names_str else "ملاحظة مرسلة لأولياء الأمور خلال الحصة"),
                description_en=f"In-session note sent to {students_with_parents} parent(s)",
                source="auto",
                source_entity_type="session_note",
                source_entity_id=note_result.get("note_id") or session_id,
                class_id=class_id,
                subject_id=subject_id,
                metadata={
                    "session_id": session_id,
                    "note_id": note_result.get("note_id"),
                    "students_count": len(valid_ids),
                    "parents_notified": students_with_parents,
                    "notifications_sent": sent,
                    "channel": "in_session_quick_note",
                },
                event_date=_today,
            )
        except Exception as _pe_err:  # noqa: BLE001
            logger.debug("Portfolio evidence (parent note) failed: %s", _pe_err)

    return {
        "message": "تم إرسال الملاحظة لأولياء الأمور",
        "note_id": note_result.get("note_id"),
        "students_requested": len(requested_ids),
        "students_targeted": len(valid_ids),
        "students_skipped": skipped_ids,
        "students_with_parents": students_with_parents,
        "notifications_sent": sent,
        "notifications_failed": failed,
    }


@router.delete("/session/{session_id}/note/{note_id}")
async def delete_session_note(
    session_id: str,
    note_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    teacher_id = current_user.get("teacher_id") or current_user["id"]
    result = await session_engine.delete_note(note_id, teacher_id)
    return result


@router.get("/session/{session_id}/live-metrics")
async def get_session_live_metrics(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    metrics = await session_engine.get_live_metrics(session_id)
    return metrics


@router.get("/session/{session_id}/events")
async def get_session_events(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    events = await session_engine.get_session_events(session_id)
    return {"session_id": session_id, "events": events}


@router.get("/session/{session_id}/report")
async def get_session_report(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    report = await session_engine.get_session_report(session_id)
    return report


@router.get("/session/{session_id}/followup-record")
async def get_followup_record(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    if session:
        lookup = {"class_id": session.get("class_id"), "subject_id": session.get("subject_id")}
    else:
        lookup = {"session_id": session_id}
    record = await gd_find_one(db.session, "followup_records", lookup)
    if not record:
        return {
            "session_id": session_id,
            "columns": [
                {"id": "participation", "name": "المشاركة", "maxGrade": 10, "type": "grade", "group": "coursework"},
                {"id": "homework", "name": "الواجبات", "maxGrade": 10, "type": "grade", "group": "coursework"},
                {"id": "performance_task", "name": "المهام الأدائية", "maxGrade": 20, "type": "grade", "group": "coursework"},
                {"id": "short_test", "name": "الاختبار القصير", "maxGrade": 20, "type": "grade", "group": "exams"},
                {"id": "final_test", "name": "اختبار نهاية الفترة", "maxGrade": 40, "type": "grade", "group": "exams"},
            ],
            "data": {},
            "absences": {},
        }
    return {
        "session_id": session_id,
        "columns": record.get("columns", []),
        "data": record.get("data", {}),
        "absences": record.get("absences", {}),
    }


@router.post("/session/{session_id}/followup-record")
async def save_followup_record(
    session_id: str,
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    c_id = session.get("class_id") if session else None
    s_id = session.get("subject_id") if session else None
    lookup = {"class_id": c_id, "subject_id": s_id} if c_id and s_id else {"session_id": session_id}
    existing = await gd_find_one(db.session, "followup_records", lookup)
    record_data = {
        "class_id": c_id,
        "subject_id": s_id,
        "session_id": session_id,
        "columns": payload.get("columns", []),
        "data": payload.get("data", {}),
        "absences": payload.get("absences", {}),
        "updated_at": datetime.utcnow().isoformat(),
    }
    if existing:
        await gd_update_one(db.session, "followup_records", lookup, {"$set": record_data})
    else:
        record_data["created_at"] = datetime.utcnow().isoformat()
        await gd_insert(db.session, "followup_records", record_data)
    return {"success": True, "session_id": session_id}


@router.post("/session/{session_id}/followup-record/column")
async def add_followup_column(
    session_id: str,
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    column = {
        "id": payload.get("id", f"col_{int(datetime.utcnow().timestamp() * 1000)}"),
        "name": payload.get("name", "عمود جديد"),
        "maxGrade": payload.get("maxGrade", 10),
        "type": payload.get("type", "grade"),
    }
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    c_id = session.get("class_id") if session else None
    s_id = session.get("subject_id") if session else None
    lookup = {"class_id": c_id, "subject_id": s_id} if c_id and s_id else {"session_id": session_id}
    existing = await gd_find_one(db.session, "followup_records", lookup)
    if existing:
        columns = existing.get("columns", [])
        columns.append(column)
        await gd_update_one(db.session, "followup_records", lookup, {"$set": {"columns": columns}})
    else:
        await gd_insert(db.session, "followup_records", {
            **lookup,
            "session_id": session_id,
            "columns": [column],
            "data": {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        })
    return {"success": True, "column": column}


@router.get("/session/{session_id}/settings")
async def get_session_settings(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    if session:
        lookup = {"class_id": session.get("class_id"), "subject_id": session.get("subject_id")}
    else:
        lookup = {"session_id": session_id}
    record = await gd_find_one(db.session, "session_settings", lookup)
    default = {
        "subject_id": session.get("subject_id") if session else None,
        "participation_enabled": True,
        "homework_enabled": True,
        "homework_view_mode": "not_submitted",
        "recitation_enabled": False,
        "recitation_max_attempts": 1,
        "skill_enabled": False,
        "extra_columns": [],
    }
    if not record:
        return {"session_id": session_id, **default}
    return {
        "session_id": session_id,
        "subject_id": record.get("subject_id") or default["subject_id"],
        "participation_enabled": record.get("participation_enabled", True),
        "homework_enabled": record.get("homework_enabled", True),
        "homework_view_mode": record.get("homework_view_mode", "not_submitted"),
        "recitation_enabled": record.get("recitation_enabled", False),
        "recitation_max_attempts": record.get("recitation_max_attempts", 1),
        "skill_enabled": record.get("skill_enabled", False),
        "extra_columns": record.get("extra_columns", []),
    }


@router.post("/session/{session_id}/settings")
async def save_session_settings(
    session_id: str,
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    c_id = session.get("class_id") if session else None
    s_id = payload.get("subject_id") or (session.get("subject_id") if session else None)
    lookup = {"class_id": c_id, "subject_id": s_id} if c_id and s_id else {"session_id": session_id}
    existing = await gd_find_one(db.session, "session_settings", lookup)
    # Validate enum / numeric ranges
    hv_mode = payload.get("homework_view_mode", "not_submitted")
    if hv_mode not in ("not_submitted", "submitted"):
        hv_mode = "not_submitted"
    try:
        attempts = int(payload.get("recitation_max_attempts", 1) or 1)
    except (TypeError, ValueError):
        attempts = 1
    attempts = max(1, min(3, attempts))
    raw_cols = payload.get("extra_columns", []) or []
    extra_columns = []
    if isinstance(raw_cols, list):
        for c in raw_cols:
            if not isinstance(c, dict):
                continue
            extra_columns.append({
                "id": str(c.get("id") or f"col_{int(datetime.utcnow().timestamp() * 1000)}"),
                "name": str(c.get("name") or "")[:100],
                "type": c.get("type") if c.get("type") in ("grade", "check", "text") else "grade",
                "maxGrade": int(c.get("maxGrade") or 0),
                "group": c.get("group") if c.get("group") in ("coursework", "exams") else "coursework",
                "hidden": bool(c.get("hidden", False)),
            })
    record_data = {
        "class_id": c_id,
        "subject_id": s_id,
        "session_id": session_id,
        "participation_enabled": bool(payload.get("participation_enabled", True)),
        "homework_enabled": bool(payload.get("homework_enabled", True)),
        "homework_view_mode": hv_mode,
        "recitation_enabled": bool(payload.get("recitation_enabled", False)),
        "recitation_max_attempts": attempts,
        "skill_enabled": bool(payload.get("skill_enabled", False)),
        "extra_columns": extra_columns,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if existing:
        await gd_update_one(db.session, "session_settings", lookup, {"$set": record_data})
    else:
        record_data["created_at"] = datetime.utcnow().isoformat()
        await gd_insert(db.session, "session_settings", record_data)
    return {"success": True, "session_id": session_id, **record_data}


@router.get("/teacher/{teacher_id}/sessions-history")
async def get_teacher_sessions_history(
    teacher_id: str,
    page: int = 1,
    limit: int = 20,
    status: str = None,
    current_user: dict = Depends(get_current_user)
):
    _verify_teacher_access(teacher_id, current_user)
    teacher = await _resolve_teacher_record(teacher_id)
    resolved_teacher_id = teacher.get("id") if teacher else teacher_id
    result = await session_engine.get_teacher_sessions(
        teacher_id=resolved_teacher_id,
        page=page,
        limit=limit,
        status_filter=status
    )
    return result


@router.post("/sessions/auto-close")
async def auto_close_stale_sessions(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN]))
):
    result = await session_engine.auto_close_stale_sessions()
    return result


@router.get("/teacher/achievements/{teacher_id}")
async def get_teacher_achievements(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    _verify_teacher_access(teacher_id, current_user)
    teacher = await _resolve_teacher_record(teacher_id)
    school_id = teacher.get("school_id") if teacher else current_user.get("tenant_id")
    resolved_teacher_id = teacher.get("id") if teacher else teacher_id

    assignments = await gd_find(db.session, "teacher_assignments", {"teacher_id": resolved_teacher_id, "is_active": True}, limit=200)
    tca_docs = await gd_find(db.session, "teacher_class_assignments", {"teacher_id": resolved_teacher_id}, limit=200)
    class_ids = list(set(a.get("class_id") for a in assignments if a.get("class_id")) | set(d.get("class_id") for d in tca_docs if d.get("class_id")))

    total_classes = len(class_ids)
    total_students = 0
    if class_ids:
        for cid in class_ids:
            count = await gd_count(db.session, "students", {"class_id": cid})
            total_students += count

    sessions = await gd_find(db.session, "teacher_sessions", {"teacher_id": resolved_teacher_id}, limit=500)
    completed_sessions = [s for s in sessions if s.get("status") in ("completed", "ended")]
    total_sessions = len(completed_sessions)

    att_total = 0
    att_present = 0
    if class_ids:
        att_total = await gd_count(db.session, "attendance", {"class_id": {"$in": class_ids}})
        att_present = await gd_count(db.session, "attendance", {"class_id": {"$in": class_ids}, "status": "present"})
    attendance_rate = round((att_present / att_total) * 100) if att_total > 0 else 0

    behavior_records = await gd_find(db.session, "behaviour_records", {"teacher_id": teacher_id}, limit=1000)
    if not behavior_records:
        behavior_records = await gd_find(db.session, "behaviour_records", {"recorded_by": teacher_id}, limit=1000)
    positive_behavior = len([b for b in behavior_records if b.get("type") == "positive" or (b.get("points") or 0) > 0])
    negative_behavior = len([b for b in behavior_records if b.get("type") == "negative" or (b.get("points") or 0) < 0])

    teacher_assessments = await gd_find(db.session, "assessments", {"teacher_id": teacher_id}, limit=500)
    if not teacher_assessments and class_ids:
        teacher_assessments = await gd_find(db.session, "assessments", {"class_id": {"$in": class_ids}}, limit=500)
    total_assessments = len(teacher_assessments)

    avg_performance = 0
    assessment_ids = [a["id"] for a in teacher_assessments if a.get("id")]
    if assessment_ids:
        submissions = await gd_find(db.session, "assessment_submissions", {"assessment_id": {"$in": assessment_ids}}, limit=2000)
        if submissions:
            scores = [s.get("percentage") or s.get("score") or 0 for s in submissions]
            avg_performance = round(sum(scores) / len(scores)) if scores else 0

    participation_total = 0
    participation_active = 0
    if class_ids:
        participation_total = await gd_count(db.session, "participation", {"class_id": {"$in": class_ids}})
        participation_active = await gd_count(db.session, "participation", {"class_id": {"$in": class_ids}, "status": {"$in": ["active", "participated"]}})
    if participation_total == 0:
        participation_total = await gd_count(db.session, "session_interactions", {"teacher_id": teacher_id, "type": "participation"})
        participation_active = await gd_count(db.session, "session_interactions", {"teacher_id": teacher_id, "type": "participation", "response": {"$ne": "no_answer"}})
    participation_rate = round((participation_active / participation_total) * 100) if participation_total > 0 else 0

    regularity_rate = 0
    if total_sessions > 0:
        proper_sessions = len([s for s in completed_sessions if s.get("ended_at")])
        regularity_rate = round((proper_sessions / total_sessions) * 100)

    metrics = {
        "total_sessions": total_sessions,
        "total_students": total_students,
        "total_classes": total_classes,
        "attendance_rate": attendance_rate,
        "participation_rate": participation_rate,
        "avg_performance": avg_performance,
        "total_assessments": total_assessments,
        "positive_behavior": positive_behavior,
        "negative_behavior": negative_behavior,
        "regularity_rate": regularity_rate,
        "total_behavior_records": len(behavior_records),
    }

    badge_defs = [
        {"id": "sessions_10", "threshold": 10, "metric": "total_sessions", "category": "teaching"},
        {"id": "sessions_50", "threshold": 50, "metric": "total_sessions", "category": "teaching"},
        {"id": "sessions_100", "threshold": 100, "metric": "total_sessions", "category": "teaching"},
        {"id": "attendance_90", "threshold": 90, "metric": "attendance_rate", "category": "attendance"},
        {"id": "students_50", "threshold": 50, "metric": "total_students", "category": "impact"},
        {"id": "participation_80", "threshold": 80, "metric": "participation_rate", "category": "engagement"},
        {"id": "performance_85", "threshold": 85, "metric": "avg_performance", "category": "academic"},
        {"id": "classes_5", "threshold": 5, "metric": "total_classes", "category": "diversity"},
        {"id": "assessments_20", "threshold": 20, "metric": "total_assessments", "category": "assessment"},
        {"id": "behavior_positive_50", "threshold": 50, "metric": "positive_behavior", "category": "behavior"},
        {"id": "regularity_95", "threshold": 95, "metric": "regularity_rate", "category": "discipline"},
    ]

    earned_badges = []
    in_progress_badges = []
    for bd in badge_defs:
        current_val = metrics.get(bd["metric"], 0)
        progress = min(100, round((current_val / bd["threshold"]) * 100)) if bd["threshold"] > 0 else 0
        badge_info = {**bd, "current": current_val, "progress": progress, "earned": current_val >= bd["threshold"]}
        if badge_info["earned"]:
            earned_badges.append(badge_info)
        else:
            in_progress_badges.append(badge_info)

    monthly_sessions = {}
    for s in completed_sessions:
        ca = s.get("created_at")
        if ca:
            month_key = ca[:7] if isinstance(ca, str) else ca.strftime("%Y-%m") if hasattr(ca, "strftime") else str(ca)[:7]
            monthly_sessions[month_key] = monthly_sessions.get(month_key, 0) + 1

    school_avg = {}
    if school_id:
        all_teachers = await gd_find(db.session, "teachers", {"school_id": school_id}, limit=200)
        if len(all_teachers) > 1:
            all_t_ids = [t["id"] for t in all_teachers]
            all_sessions = await gd_count(db.session, "teacher_sessions", {"teacher_id": {"$in": all_t_ids}, "status": {"$in": ["completed", "ended"]}})
            school_avg["avg_sessions"] = round(all_sessions / len(all_teachers))
            school_avg["teacher_count"] = len(all_teachers)

    return {
        "metrics": metrics,
        "earned_badges": earned_badges,
        "in_progress_badges": in_progress_badges,
        "monthly_sessions": monthly_sessions,
        "school_comparison": school_avg,
        "total_earned": len(earned_badges),
        "total_badges": len(badge_defs),
    }
