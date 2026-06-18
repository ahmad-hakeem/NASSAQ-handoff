"""
NASSAQ - Parent Portal Routes
مسارات بوابة ولي الأمر
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

SAUDI_TZ = ZoneInfo("Asia/Riyadh")
import uuid
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert

import logging

from sqlalchemy.exc import ProgrammingError, OperationalError

logger = logging.getLogger("nassaq.parent_portal_routes")

# Narrow set of DB errors that indicate the optional legacy linkage
# surfaces (`guardian_links` join table, `parents.student_ids` array)
# are unreachable in this environment — typically a missing table /
# missing column / connection blip. We swallow these so the canonical
# `students.parent_id` resolution still works; everything else (auth,
# tenant scoping, programming bugs) bubbles up as before.
_LEGACY_LINKAGE_DB_ERRORS = (ProgrammingError, OperationalError)


def setup_parent_portal_routes(db, get_current_user, require_roles, UserRole):
    """Setup parent portal routes"""

    router = APIRouter(prefix="/parent-portal", tags=["Parent Portal"])

    @router.post("/accept-charter")
    async def accept_parent_charter(
        current_user: dict = Depends(require_roles([UserRole.PARENT])),
    ):
        """Mark the authenticated parent as having accepted the mandatory
        ميثاق ولي الأمر. The FE CharterGuard blocks every /parent/* route
        until ``charter_accepted_at`` is non-NULL, so this is the single
        gateway out of the blocking modal. Idempotent — re-accepting
        keeps the original acceptance timestamp."""
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="غير مصرح")

        now = datetime.now(timezone.utc)
        # Atomic "set only if currently NULL" so two concurrent accept
        # requests cannot overwrite the original acceptance timestamp.
        await gd_update_one(
            db.session, "users",
            {"id": user_id, "charter_accepted_at": None},
            {"$set": {"charter_accepted_at": now}},
        )

        # Re-read so we return whatever value is actually persisted —
        # either ``now`` (we won the race / first acceptance) or the
        # previously stored timestamp (idempotent re-accept).
        existing = await gd_find_one(db.session, "users", {"id": user_id})
        if not existing:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")

        accepted_at = existing.get("charter_accepted_at") or now
        if isinstance(accepted_at, datetime):
            iso = accepted_at.isoformat()
        else:
            iso = str(accepted_at)

        return {
            "success": True,
            "charter_accepted_at": iso,
            "message": "تم قبول الميثاق",
        }

    def _parent_or_conditions(parent_user_id: str, parent_phone: Optional[str] = None, parent_record_id: Optional[str] = None, parent_email: Optional[str] = None) -> list:
        """Build an $or list that matches students based solely on canonical
        parent identifiers (user.id / parents.id).  Mutable contact fields
        such as phone and email are intentionally excluded because they can be
        changed by the authenticated user and must not be used as an
        authorization key.
        """
        conditions = []
        seen = set()
        for pid in (parent_user_id, parent_record_id):
            if pid and pid not in seen:
                conditions.append({"parent_id": pid})
                conditions.append({"parent_user_id": pid})
                seen.add(pid)
        return conditions

    def _parent_refs(current_user: dict) -> List[str]:
        """Return all identifiers that may have been used as a parent link: user.id
        and parents.id (if resolvable)."""
        refs = []
        uid = current_user.get("id")
        pid = current_user.get("parent_id")
        if uid:
            refs.append(uid)
        if pid and pid != uid:
            refs.append(pid)
        return refs

    async def _get_linked_student_ids(current_user: dict, school_id: Optional[str] = None) -> List[str]:
        """Resolve extra student ids via the non-canonical linkage paths
        (`guardian_links` join table and `parents.student_ids` array).

        Both paths are best-effort and MUST fail safe: the canonical
        `students.parent_id` resolution in `_find_children` is the primary
        source of truth, and a missing/empty join table or a malformed
        parent record must not 500 the parent dashboard. Each lookup is
        isolated so one broken path does not poison the other.
        """
        refs = _parent_refs(current_user)
        if not refs:
            return []
        student_ids: set = set()

        # Path A: guardian_links (preferred when present). Tolerate the
        # table being absent in environments that never installed it —
        # those installs rely entirely on parents.student_ids and the
        # canonical students.parent_id back-reference.
        query = {"parent_ref": {"$in": refs}, "is_active": True}
        if school_id:
            query["tenant_id"] = school_id
        try:
            links = await gd_find(db.session, "guardian_links", query, limit=50)
            for link in links:
                sid = link.get("student_id")
                if sid:
                    student_ids.add(sid)
        except _LEGACY_LINKAGE_DB_ERRORS as exc:
            logger.debug("guardian_links lookup degraded for parent %s: %s",
                         current_user.get("id"), exc)

        # Path B: parents.student_ids array on the parent record.
        parent_record_id = current_user.get("parent_id")
        if parent_record_id:
            try:
                parent_rec = await gd_find_one(db.session, "parents", {"id": parent_record_id})
                if parent_rec and isinstance(parent_rec.get("student_ids"), list):
                    for sid in parent_rec["student_ids"]:
                        if sid:
                            student_ids.add(sid)
            except _LEGACY_LINKAGE_DB_ERRORS as exc:
                logger.debug("parents.student_ids lookup degraded for parent %s: %s",
                             current_user.get("id"), exc)

        return list(student_ids)

    async def _find_children(current_user_or_id, parent_phone: Optional[str] = None, school_id: Optional[str] = None):
        """Back-compat signature: accepts either a full user dict or a user id
        followed by parent_phone/school_id. Delegates to the shared
        canonical resolver in `utils.parent_children_resolution` so the
        parent portal and the Hakim assistant always see the same
        allow-list of children."""
        if isinstance(current_user_or_id, dict):
            current_user = current_user_or_id
            school_id = school_id or current_user.get("tenant_id")
        else:
            current_user = {"id": current_user_or_id, "phone": parent_phone, "tenant_id": school_id}

        from utils.parent_children_resolution import resolve_parent_children
        return await resolve_parent_children(current_user, school_id)

    # ============= DASHBOARD =============

    @router.get("/dashboard")
    async def get_parent_dashboard(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """لوحة تحكم ولي الأمر"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        children = await _find_children(current_user, parent_phone, school_id)

        school_name_cache = {}
        children_data = []
        for child in children:
            child_id = child.get("id")

            total_days = await gd_count(db.session, "attendance", {"student_id": child_id})
            present_days = await gd_count(db.session, "attendance", {"student_id": child_id, "status": "present"})
            # Honest empty: when no attendance records exist, return null
            # rather than an invented "100%" that masks missing data. The
            # frontend renders a placeholder for null. (Audit 2026-05-10.)
            attendance_rate = (present_days / total_days * 100) if total_days > 0 else None

            recent_grades = await gd_find(db.session, "grades", {"student_id": child_id}, order_by="date", desc_order=True, limit=3)
            all_grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=500)
            # Honest empty for academics too — no grades => null, not a fake 0%.
            avg_score = (sum(g.get("percentage", 0) for g in all_grades) / len(all_grades)) if all_grades else None

            child_school_name = child.get("school_name")
            if not child_school_name:
                sid = child.get("school_id") or school_id
                if sid and sid not in school_name_cache:
                    s_doc = await gd_find_one(db.session, "schools", {"id": sid})
                    school_name_cache[sid] = s_doc.get("name") if s_doc else sid
                child_school_name = school_name_cache.get(sid, "")

            children_data.append({
                "id": child_id,
                "name": child.get("full_name"),
                "grade": child.get("grade_level") or child.get("grade"),
                "class_name": child.get("class_name"),
                "class_id": child.get("class_id"),
                "school_name": child_school_name,
                "profile_picture": child.get("profile_picture"),
                "attendance_rate": round(attendance_rate, 1) if attendance_rate is not None else None,
                "average_score": round(avg_score, 1) if avg_score is not None else None,
                "recent_grades": [
                    {
                        "subject": g.get("subject"),
                        "score": g.get("score"),
                        "max_score": g.get("max_score"),
                        "date": g.get("date")
                    }
                    for g in recent_grades
                ]
            })

        unread_notifications = await gd_count(db.session, "notifications", {
            "recipient_id": parent_id,
            "read_status": False
        })

        unread_messages = await gd_count(db.session, "messages", {
            "receiver_id": parent_id,
            "read_status": False
        })

        return {
            "parent": {
                "id": parent_id,
                "name": current_user.get("full_name"),
                "email": current_user.get("email"),
                "phone": parent_phone
            },
            "children": children_data,
            "children_count": len(children_data),
            "unread_notifications": unread_notifications,
            "unread_messages": unread_messages
        }

    # ============= CHILDREN LIST =============

    @router.get("/children")
    async def get_parent_children(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """قائمة أبناء ولي الأمر"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        students = await _find_children(current_user, parent_phone, school_id)

        school_name_cache = {}
        children = []
        for s in students:
            child_id = s.get("id")

            # Root-cause fix: some UI paths (e.g. "mark all present") only
            # write DB rows for present students; absent students get no row.
            # Counting only this student's own rows makes denominator == present
            # count → always 100%. The correct denominator is the number of
            # distinct calendar dates the class had ANY attendance recorded
            # (i.e. how many days the teacher took attendance). We also scope
            # every query by school_id to prevent cross-tenant bleed-in.
            child_school_id = s.get("school_id") or school_id
            child_class_id = s.get("class_id")

            if child_class_id and child_school_id:
                # gd_distinct returns ALL distinct date values with no row
                # limit, so there is no truncation risk.  The date column is
                # DateTime(tz), so multiple sessions on the same calendar day
                # produce different timestamps; str()[:10] normalises them to
                # YYYY-MM-DD before deduplication.
                class_dates = await gd_distinct(
                    db.session, "attendance", "date",
                    {"school_id": child_school_id, "class_id": child_class_id},
                )
                distinct_days = len({str(d)[:10] for d in class_dates if d})
                # Numerator is class-scoped (same school+class) so rate is
                # always ≤ 100% even if the student has records in past classes.
                present_days = await gd_count(
                    db.session, "attendance",
                    {"school_id": child_school_id, "class_id": child_class_id,
                     "student_id": child_id, "status": "present"},
                )
                # Null when truly empty so KPI cards can render a placeholder
                # instead of an invented 0%/100% claim. (Audit 2026-05-10.)
                att_rate = round((present_days / distinct_days * 100), 1) if distinct_days > 0 else None
            else:
                # No class context — use the student's own record count as a
                # best-effort denominator (still scoped by school_id).
                total_days = await gd_count(
                    db.session, "attendance",
                    {"school_id": child_school_id, "student_id": child_id},
                )
                present_days = await gd_count(
                    db.session, "attendance",
                    {"school_id": child_school_id, "student_id": child_id, "status": "present"},
                )
                att_rate = round((present_days / total_days * 100), 1) if total_days > 0 else None

            all_grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=500)
            avg_score = None
            if all_grades:
                avg_score = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1)

            child_school_name = s.get("school_name")
            if not child_school_name:
                sid = s.get("school_id") or school_id
                if sid and sid not in school_name_cache:
                    s_doc = await gd_find_one(db.session, "schools", {"id": sid})
                    school_name_cache[sid] = s_doc.get("name") if s_doc else sid
                child_school_name = school_name_cache.get(sid, "")

            # Task #277 — Independent-Teacher workspace context. When the
            # student lives in an `itw_{user_id}` workspace, surface the
            # owning teacher's display name + a flag so the parent FE can
            # swap school metadata for IT-context affordances. Falls back
            # silently if the user lookup misses.
            child_sid = s.get("school_id") or school_id
            is_it_ws = isinstance(child_sid, str) and child_sid.startswith("itw_")
            teacher_display_name = None
            if is_it_ws:
                owner_uid = child_sid[len("itw_"):]
                owner = await gd_find_one(db.session, "users", {"id": owner_uid}) if owner_uid else None
                teacher_display_name = (owner or {}).get("full_name") or None

            children.append({
                "id": child_id,
                "name": s.get("full_name", s.get("name", "")),
                "name_ar": s.get("full_name", ""),
                "grade": s.get("grade_level", s.get("grade", "")),
                "class_name": s.get("class_name", ""),
                "grade_id": s.get("grade_id"),
                "class_id": s.get("class_id"),
                "school_id": child_sid,
                "school_name": child_school_name,
                "is_independent_teacher_workspace": bool(is_it_ws),
                "teacher_display_name": teacher_display_name,
                "photo_url": s.get("photo_url", ""),
                "profile_picture": s.get("photo_url", s.get("profile_picture", "")),
                "attendance_rate": att_rate,
                "average_score": avg_score,
                "gender": s.get("gender", ""),
            })

        return {"children": children, "total": len(children)}

    # ============= CHILD DETAILS =============

    async def _verify_parent_access(parent_id: str, parent_phone: Optional[str], child_id: str, school_id: Optional[str] = None, *, current_user: Optional[dict] = None):
        parent_record_id = (current_user or {}).get("parent_id")
        parent_email = (current_user or {}).get("email")
        or_conds = _parent_or_conditions(parent_id, parent_phone, parent_record_id, parent_email)
        student_query = {"id": child_id}
        if or_conds:
            student_query["$or"] = or_conds
        if school_id:
            student_query["school_id"] = school_id
        child = await gd_find_one(db.session, "students", student_query)
        if child:
            return child
        # Fallback 1: guardian_links (optional join table — fail safe if
        # unreachable so by-id endpoints don't 500 in partial-schema
        # environments; the canonical lookup above is the access boundary).
        refs = [pid for pid in (parent_id, parent_record_id) if pid]
        if refs:
            link_query = {"parent_ref": {"$in": refs}, "student_id": child_id, "is_active": True}
            if school_id:
                link_query["tenant_id"] = school_id
            link = None
            try:
                link = await gd_find_one(db.session, "guardian_links", link_query)
            except _LEGACY_LINKAGE_DB_ERRORS as exc:
                logger.debug("guardian_links by-id lookup degraded for parent %s: %s",
                             parent_id, exc)
            if link:
                fallback_q = {"id": child_id}
                if school_id:
                    fallback_q["school_id"] = school_id
                return await gd_find_one(db.session, "students", fallback_q)
        # Fallback 2: parents.student_ids array (legacy linkage path).
        if parent_record_id:
            try:
                parent_rec = await gd_find_one(db.session, "parents", {"id": parent_record_id})
            except _LEGACY_LINKAGE_DB_ERRORS as exc:
                logger.debug("parents.student_ids by-id lookup degraded for parent %s: %s",
                             parent_id, exc)
                parent_rec = None
            if parent_rec and child_id in (parent_rec.get("student_ids") or []):
                fallback_q = {"id": child_id}
                if school_id:
                    fallback_q["school_id"] = school_id
                return await gd_find_one(db.session, "students", fallback_q)
        return None

    @router.get("/child/{child_id}")
    async def get_child_details(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """تفاصيل الابن"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)

        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        child_sid = child.get("school_id") or current_user.get("tenant_id")
        child_school_name = child.get("school_name")
        if not child_school_name and child_sid:
            s_doc = await gd_find_one(db.session, "schools", {"id": child_sid})
            child_school_name = s_doc.get("name") if s_doc else None

        # Task #277 — surface IT context so the parent FE swaps the school
        # label for the inviting teacher's workspace and hides school-only
        # surfaces (peer roster, principal contact, school events).
        is_it_ws = isinstance(child_sid, str) and child_sid.startswith("itw_")
        teacher_display_name = None
        if is_it_ws:
            owner_uid = child_sid[len("itw_"):]
            owner = await gd_find_one(db.session, "users", {"id": owner_uid})
            teacher_display_name = (owner or {}).get("full_name") or None

        return {
            "id": child.get("id"),
            "name": child.get("full_name"),
            "national_id": child.get("national_id"),
            "birth_date": child.get("date_of_birth"),
            "gender": child.get("gender"),
            "grade": child.get("grade_level"),
            "class_name": child.get("class_name"),
            "class_id": child.get("class_id"),
            "school_id": child_sid,
            "school_name": child_school_name,
            "is_independent_teacher_workspace": bool(is_it_ws),
            "teacher_display_name": teacher_display_name,
            "student_number": child.get("student_number"),
            "enrollment_date": child.get("enrollment_date"),
            "profile_picture": child.get("profile_picture"),
        }

    # ============= CHILD GRADES =============

    @router.get("/child/{child_id}/grades")
    async def get_child_grades(
        child_id: str,
        subject: Optional[str] = None,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """درجات الابن"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)

        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        query = {"student_id": child_id}
        school_id = current_user.get("tenant_id")
        if school_id:
            query["school_id"] = school_id
        if subject:
            query["$or"] = [
                {"subject": subject},
                {"subject_name": subject},
                {"subject_id": subject},
            ]

        grades = await gd_find(db.session, "grades", query, order_by="date", desc_order=True, limit=500)

        subjects_data = {}
        for grade in grades:
            subj = grade.get("subject_name") or grade.get("subject") or grade.get("subject_id") or "غير محدد"
            if subj not in subjects_data:
                subjects_data[subj] = {"subject": subj, "grades": [], "total_score": 0, "total_max": 0}

            subjects_data[subj]["grades"].append({
                "score": grade.get("score"),
                "max_score": grade.get("max_score"),
                "percentage": grade.get("percentage"),
                "assessment_type": grade.get("assessment_type"),
                "date": grade.get("date")
            })
            subjects_data[subj]["total_score"] += grade.get("score", 0)
            subjects_data[subj]["total_max"] += grade.get("max_score", 100)

        for subj in subjects_data:
            data = subjects_data[subj]
            data["average"] = round((data["total_score"] / data["total_max"]) * 100, 1) if data["total_max"] > 0 else 0

        total_grades = len(grades)
        overall_avg = sum(g.get("percentage", 0) for g in grades) / total_grades if total_grades > 0 else 0

        return {
            "child_name": child.get("full_name"),
            "subjects": list(subjects_data.values()),
            "total_grades": total_grades,
            "overall_average": round(overall_avg, 1)
        }

    # ============= CHILD ATTENDANCE =============

    @router.get("/child/{child_id}/attendance")
    async def get_child_attendance(
        child_id: str,
        month: Optional[int] = None,
        year: Optional[int] = None,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """سجل حضور الابن"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)

        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        # Scope queries by school_id to prevent cross-tenant bleed-in.
        child_school_id = child.get("school_id") or current_user.get("tenant_id")
        child_class_id = child.get("class_id")

        query = {"school_id": child_school_id, "student_id": child_id}

        date_filter = None
        if month and year:
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{month + 1:02d}-01"
            date_filter = {"$gte": start_date, "$lt": end_date}
            query["date"] = date_filter

        records = await gd_find(db.session, "attendance", query, order_by="date", desc_order=True, limit=500)

        # Statistics — scope numerator to the student's current class so
        # cross-class history cannot make rate > 100%.
        if child_class_id:
            stat_records = [r for r in records if r.get("class_id") == child_class_id]
        else:
            stat_records = records

        present = sum(1 for r in stat_records if r.get("status") == "present")
        absent = sum(1 for r in stat_records if r.get("status") == "absent")
        late = sum(1 for r in stat_records if r.get("status") == "late")
        excused = sum(1 for r in stat_records if r.get("status") == "excused")

        # Denominator fix: use the number of distinct calendar dates the class
        # had ANY attendance recorded, not just this student's own row count.
        # Some UI paths only write "present" rows; absent students get no row,
        # so student-level total == student-level present → always 100%.
        # gd_distinct returns all distinct date values without a row limit —
        # no truncation risk. str()[:10] normalises DateTime to calendar day.
        if child_class_id and child_school_id:
            class_date_q: dict = {"school_id": child_school_id, "class_id": child_class_id}
            if date_filter:
                class_date_q["date"] = date_filter
            class_dates = await gd_distinct(db.session, "attendance", "date", class_date_q)
            total_days = len({str(d)[:10] for d in class_dates if d})
        else:
            # No class context — fall back to the student's own record count.
            total_days = len(records)

        return {
            "child_name": child.get("full_name"),
            "records": [
                {
                    "date": r.get("date"),
                    "status": r.get("status"),
                    "check_in_time": r.get("check_in_time"),
                    "check_out_time": r.get("check_out_time"),
                    "notes": r.get("notes")
                }
                for r in records
            ],
            "statistics": {
                "total_days": total_days,
                "present": present,
                "absent": absent,
                "late": late,
                "excused": excused,
                # Honest empty: no records => null, not a fake 100%.
                # Frontend renders a placeholder when null. (Audit 2026-05-10.)
                "attendance_rate": round((present / total_days * 100), 1) if total_days > 0 else None
            }
        }

    # ============= CHILD SCHEDULE =============

    @router.get("/child/{child_id}/schedule")
    async def get_child_schedule(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """الجدول الدراسي للابن"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)

        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        school_id = child.get("school_id")

        day_en_to_ar = {
            "sunday": "الأحد", "monday": "الاثنين", "tuesday": "الثلاثاء",
            "wednesday": "الأربعاء", "thursday": "الخميس"
        }
        days_order = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"]
        schedule_by_day = {day: [] for day in days_order}

        if child.get("class_id"):
            timetable = await gd_find_one(db.session, "timetables", {"school_id": school_id, "status": "published"}) or await gd_find_one(db.session, "timetables", {"school_id": school_id},
                sort=[("created_at", -1)])
            if timetable:
                all_sessions = await gd_find(db.session, "timetable_sessions", {
                        "timetable_id": timetable.get("id"),
                        "class_id": child.get("class_id")
                    }, limit=500)

                sub_ids = list(set(s.get("subject_id") for s in all_sessions if s.get("subject_id")))
                tch_ids = list(set(s.get("teacher_id") for s in all_sessions if s.get("teacher_id")))
                subs = await gd_find(db.session, "subjects", {"id": {"$in": sub_ids}}, limit=100)
                tchs = await gd_find(db.session, "teachers", {"id": {"$in": tch_ids}}, limit=100)
                sub_map = {s["id"]: s.get("name_ar", "") for s in subs}
                tch_map = {t["id"]: t.get("full_name", "") for t in tchs}

                for session in all_sessions:
                    day_ar = day_en_to_ar.get(session.get("day_of_week", ""), "")
                    if day_ar in schedule_by_day:
                        schedule_by_day[day_ar].append({
                            "period": session.get("period_number"),
                            "subject": sub_map.get(session.get("subject_id"), "غير محدد"),
                            "teacher": tch_map.get(session.get("teacher_id"), "غير محدد"),
                            "start_time": session.get("start_time"),
                            "end_time": session.get("end_time")
                        })

        for day in schedule_by_day:
            schedule_by_day[day] = sorted(schedule_by_day[day], key=lambda x: x.get("period", 0))

        return {
            "child_name": child.get("full_name"),
            "class_name": child.get("class_name"),
            "schedule": schedule_by_day,
            "days": days_order
        }

    # ============= TODAY LIVE =============

    @router.get("/child/{child_id}/today-live")
    async def get_child_today_live(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id, current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        now = datetime.now(SAUDI_TZ)
        current_time = now.strftime("%H:%M")
        day_map = {6: "sunday", 0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday"}
        today_en = day_map.get(now.weekday(), "")

        today_sessions = []
        if child.get("class_id") and today_en:
            timetable = await gd_find_one(db.session, "timetables", {
                "school_id": child.get("school_id", school_id),
                "status": "published"
            }) or await gd_find_one(db.session, "timetables", {
                "school_id": child.get("school_id", school_id)
            }, sort=[("created_at", -1)])

            if timetable:
                sessions = await gd_find(db.session, "timetable_sessions", {
                    "timetable_id": timetable.get("id"),
                    "class_id": child.get("class_id"),
                    "day_of_week": today_en
                }, limit=20)

                sub_ids = list(set(s.get("subject_id") for s in sessions if s.get("subject_id")))
                tch_ids = list(set(s.get("teacher_id") for s in sessions if s.get("teacher_id")))
                subs = await gd_find(db.session, "subjects", {"id": {"$in": sub_ids}}, limit=50) if sub_ids else []
                tchs = await gd_find(db.session, "teachers", {"id": {"$in": tch_ids}}, limit=50) if tch_ids else []
                sub_map = {s["id"]: s.get("name_ar", s.get("name", "")) for s in subs}
                tch_map = {t["id"]: t.get("full_name", "") for t in tchs}

                for s in sorted(sessions, key=lambda x: x.get("period_number", 0)):
                    today_sessions.append({
                        "period": s.get("period_number"),
                        "subject": sub_map.get(s.get("subject_id"), "غير محدد"),
                        "subject_id": s.get("subject_id"),
                        "teacher": tch_map.get(s.get("teacher_id"), "غير محدد"),
                        "teacher_id": s.get("teacher_id"),
                        "start_time": s.get("start_time"),
                        "end_time": s.get("end_time"),
                    })

        current_class = None
        upcoming_classes = []
        completed_count = 0
        for session in today_sessions:
            start = session.get("start_time", "")
            end = session.get("end_time", "")
            if start and end:
                if current_time >= end:
                    completed_count += 1
                elif start <= current_time < end:
                    current_class = {**session, "is_current": True}
                else:
                    upcoming_classes.append(session)

        today_date = now.date()
        days_offset = today_date.weekday() + 1 if today_date.weekday() != 6 else 0
        week_start = today_date - timedelta(days=days_offset)
        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_start - timedelta(days=1)

        this_week_grades = await gd_find(db.session, "grades", {
            "student_id": child_id,
            "date": {"$gte": week_start.isoformat(), "$lte": today_date.isoformat()}
        }, limit=200)
        last_week_grades = await gd_find(db.session, "grades", {
            "student_id": child_id,
            "date": {"$gte": last_week_start.isoformat(), "$lte": last_week_end.isoformat()}
        }, limit=200)

        all_grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=500)
        overall_avg = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1) if all_grades else 0

        this_avg = round(sum(g.get("percentage", 0) for g in this_week_grades) / len(this_week_grades), 1) if this_week_grades else overall_avg
        last_avg = round(sum(g.get("percentage", 0) for g in last_week_grades) / len(last_week_grades), 1) if last_week_grades else this_avg
        trend = round(this_avg - last_avg, 1)

        if overall_avg >= 90:
            level = "ممتاز"
        elif overall_avg >= 80:
            level = "جيد جداً"
        elif overall_avg >= 70:
            level = "جيد ومستقر"
        elif overall_avg >= 60:
            level = "مقبول"
        else:
            level = "يحتاج تحسين"

        if trend > 2:
            phrase = "استمروا على هذا التقدم الرائع!"
        elif trend < -2:
            phrase = "لا تقلقوا، بالمتابعة سيتحسن الأداء"
        else:
            phrase = "أداء مستقر، واصلوا الدعم"

        child_school_name = child.get("school_name", "")
        if not child_school_name:
            sid = child.get("school_id") or school_id
            if sid:
                s_doc = await gd_find_one(db.session, "schools", {"id": sid})
                child_school_name = s_doc.get("name") if s_doc else ""

        # Task #277 — IT-workspace context for the parent home hero.
        child_sid = child.get("school_id") or school_id
        is_it_ws = isinstance(child_sid, str) and child_sid.startswith("itw_")
        teacher_display_name = None
        if is_it_ws:
            owner_uid = child_sid[len("itw_"):]
            owner = await gd_find_one(db.session, "users", {"id": owner_uid}) if owner_uid else None
            teacher_display_name = (owner or {}).get("full_name") or None

        return {
            "student": {
                "name": child.get("full_name"),
                "school_id": child_sid,
                "school_name": child_school_name,
                "grade_level": child.get("grade_level", child.get("grade", "")),
                "class_name": child.get("class_name", ""),
                "is_independent_teacher_workspace": bool(is_it_ws),
                "teacher_display_name": teacher_display_name,
            },
            "school_day": {
                "today": today_en,
                "total_periods": len(today_sessions),
                "completed_periods": completed_count,
                "remaining_periods": len(upcoming_classes) + (1 if current_class else 0),
                "all_sessions": today_sessions,
                "is_school_day": today_en in day_map.values(),
                "server_time": current_time,
            },
            "current_class": current_class,
            "upcoming_classes": upcoming_classes,
            "performance": {
                "level": level,
                "overall_average": overall_avg,
                "trend": trend,
                "trend_direction": "up" if trend > 2 else ("down" if trend < -2 else "stable"),
                "phrase": phrase,
            }
        }

    # ============= WEEKLY STORY =============

    def _rank_weekly_cards(signals: dict) -> list:
        """Build a small, ranked, UI-ready cards list from the weekly signals.

        Card schema: {kind, tone, icon, title_ar, value, metric}
          - kind:   participation | positive_behaviour | skill | strong_subject |
                    weak_subject | late | absent | homework_high | homework_low |
                    remedial
          - tone:   positive | concern | academic
          - icon:   stable lucide name the FE maps to a component
          - value:  optional short value (e.g. "92%", "3")
        Selection: at most 4 cards = top 2 positive + top 1 concern + top 1
        academic. Slots collapse upward when a tier is empty so we never pad
        with empty tiles. Returns [] when no usable signals exist.
        """
        positive: list = []
        concern: list = []
        academic: list = []

        participation = int(signals.get("participation_count") or 0)
        positive_b = int(signals.get("positive_behaviors") or 0)
        skills = signals.get("acquired_skills") or []
        strong = signals.get("strong_subjects") or []
        weak = signals.get("weak_subjects") or []
        remedial = signals.get("remedial_plans") or []
        late_count = int(signals.get("late_count") or 0)
        absent_count = int(signals.get("absent_count") or 0)
        hw_total = int(signals.get("homework_total") or 0)
        hw_done = int(signals.get("homework_done") or 0)
        hw_rate = round((hw_done / hw_total) * 100) if hw_total > 0 else None

        # ---- positive tier ----
        if participation >= 1:
            positive.append({
                "kind": "participation",
                "tone": "positive",
                "icon": "Star",
                "title_ar": f"شارك بفعالية في {participation} حصة" if participation > 1
                            else "شارك بفعالية في حصة واحدة",
                "value": str(participation),
                "metric": "participation_count",
            })
        if positive_b >= 1:
            positive.append({
                "kind": "positive_behaviour",
                "tone": "positive",
                "icon": "Award",
                "title_ar": f"حصل على {positive_b} ملاحظة إيجابية" if positive_b > 1
                            else "حصل على ملاحظة إيجابية",
                "value": str(positive_b),
                "metric": "positive_behaviors",
            })
        if skills:
            positive.append({
                "kind": "skill",
                "tone": "positive",
                "icon": "Sparkles",
                "title_ar": f"اكتسب مهارة: {skills[0]}",
                "value": None,
                "metric": "acquired_skills",
            })
        if hw_rate is not None and hw_rate >= 80:
            positive.append({
                "kind": "homework_high",
                "tone": "positive",
                "icon": "CheckCircle2",
                "title_ar": f"أتم {hw_rate}% من الواجبات",
                "value": f"{hw_rate}%",
                "metric": "homework_rate",
            })

        # ---- concern tier ----
        if late_count >= 1:
            concern.append({
                "kind": "late",
                "tone": "concern",
                "icon": "Clock",
                "title_ar": f"تأخر {late_count} مرات" if late_count > 1
                            else "تأخر مرة واحدة",
                "value": str(late_count),
                "metric": "late_count",
            })
        if absent_count >= 1:
            concern.append({
                "kind": "absent",
                "tone": "concern",
                "icon": "AlertCircle",
                "title_ar": f"تغيّب {absent_count} مرات" if absent_count > 1
                            else "تغيّب مرة واحدة",
                "value": str(absent_count),
                "metric": "absent_count",
            })
        if hw_rate is not None and hw_rate < 60:
            concern.append({
                "kind": "homework_low",
                "tone": "concern",
                "icon": "FileText",
                "title_ar": f"أتم {hw_rate}% فقط من الواجبات",
                "value": f"{hw_rate}%",
                "metric": "homework_rate",
            })
        if weak:
            w0 = weak[0]
            subj = w0.get("subject") if isinstance(w0, dict) else str(w0)
            avg = w0.get("average") if isinstance(w0, dict) else None
            concern.append({
                "kind": "weak_subject",
                "tone": "concern",
                "icon": "TrendingDown",
                "title_ar": f"يحتاج دعمًا في {subj}" + (f" ({avg}%)" if avg is not None else ""),
                "value": f"{avg}%" if avg is not None else None,
                "metric": "weak_subjects",
            })

        # ---- academic tier ----
        if strong:
            s0 = strong[0]
            subj = s0.get("subject") if isinstance(s0, dict) else str(s0)
            avg = s0.get("average") if isinstance(s0, dict) else None
            academic.append({
                "kind": "strong_subject",
                "tone": "academic",
                "icon": "GraduationCap",
                "title_ar": f"تميّز في {subj}" + (f" ({avg}%)" if avg is not None else ""),
                "value": f"{avg}%" if avg is not None else None,
                "metric": "strong_subjects",
            })
        if remedial:
            r0 = remedial[0]
            title = (r0.get("title") if isinstance(r0, dict) else str(r0)) or "خطة علاجية"
            academic.append({
                "kind": "remedial",
                "tone": "academic",
                "icon": "BookOpen",
                "title_ar": f"خطة علاجية: {title}",
                "value": None,
                "metric": "remedial_plans",
            })

        cards: list = []
        cards.extend(positive[:2])
        cards.extend(concern[:1])
        cards.extend(academic[:1])
        # Backfill if we have fewer than 4 and more available in any tier.
        if len(cards) < 4:
            extras = positive[2:] + concern[1:] + academic[1:]
            cards.extend(extras[: 4 - len(cards)])
        return cards[:4]

    async def _get_or_build_parent_weekly_insight(
        *,
        child_id: str,
        school_id: Optional[str],
        week_start: str,
        week_end: str,
        signals: dict,
        cards: Optional[list] = None,
    ) -> dict:
        """Return the Hakim-generated weekly story+tip envelope for a child.

        Status values:
          - "available"          → story + tip generated by Hakim (or served from this week's cache)
          - "insufficient_data"  → student has too few weekly signals; no LLM call, no fabrication
          - "unavailable"        → Hakim service is disabled or both attempts failed

        Cache key: ai_insights row with insight_type='parent_weekly_brief',
        entity_type='student', entity_id=child_id, school_id=school_id,
        and data.week_start matching the current Saudi week start.
        """
        # 1) Sufficiency gate — when the caller already ranked cards, defer
        #    to that decision (zero usable cards => insufficient data).
        #    Otherwise fall back to the legacy "≥2 of 5 raw signals" rule.
        if cards is not None:
            insufficient = len(cards) == 0
        else:
            signal_flags = [
                signals.get("participation_count", 0) > 0,
                signals.get("positive_behaviors", 0) > 0,
                bool(signals.get("strong_subjects")) or bool(signals.get("weak_subjects")),
                bool(signals.get("acquired_skills")),
                bool(signals.get("remedial_plans")),
            ]
            insufficient = sum(1 for f in signal_flags if f) < 2
        if insufficient:
            return {
                "status": "insufficient_data",
                "story": None,
                "tip": None,
                "generated_at": None,
                "week_start": week_start,
                "week_end": week_end,
            }

        # 2) Cache lookup (per child + per Saudi week)
        cached = None
        try:
            cached_row = await gd_find_one(db.session, "ai_insights", {
                "insight_type": "parent_weekly_brief",
                "entity_type": "student",
                "entity_id": child_id,
                "school_id": school_id,
            })
            if cached_row and isinstance(cached_row.get("data"), dict):
                if cached_row["data"].get("week_start") == week_start:
                    cached = cached_row["data"]
        except Exception as e:
            logger.debug(f"weekly_insight cache lookup failed: {e}")

        if cached and cached.get("story") and cached.get("tip"):
            return {
                "status": "available",
                "story": cached.get("story"),
                "tip": cached.get("tip"),
                "generated_at": cached.get("generated_at"),
                "week_start": week_start,
                "week_end": week_end,
                "from_cache": True,
            }

        # 3) Real Hakim generation — story + tip
        try:
            from services.hakim_llm_service import hakim_generate, is_available as hakim_available
        except Exception as e:
            logger.warning(f"hakim_llm_service import failed: {e}")
            return {
                "status": "unavailable",
                "story": None,
                "tip": None,
                "generated_at": None,
                "week_start": week_start,
                "week_end": week_end,
            }

        if not hakim_available():
            return {
                "status": "unavailable",
                "story": None,
                "tip": None,
                "generated_at": None,
                "week_start": week_start,
                "week_end": week_end,
            }

        ctx = {
            "week_start": week_start,
            "week_end": week_end,
            "grade_level": signals.get("grade_level") or "",
            "participation_count": signals.get("participation_count", 0),
            "positive_behaviors": signals.get("positive_behaviors", 0),
            "acquired_skills": signals.get("acquired_skills") or [],
            "strong_subjects": signals.get("strong_subjects") or [],
            "weak_subjects": signals.get("weak_subjects") or [],
            "remedial_plans": [
                f"{p.get('title','')} ({p.get('subject','')})".strip(" ()")
                for p in (signals.get("remedial_plans") or [])
            ],
        }

        # Tip context is intentionally tighter than the story context: the
        # advice card must be tied to the ranked headline metrics shown to
        # the parent, never to raw teacher notes or unbounded extras. We
        # pass only the short title strings of the chosen cards.
        tip_ctx = {
            "week_start": week_start,
            "week_end": week_end,
            "grade_level": signals.get("grade_level") or "",
            "acquired_skills": [
                c.get("title_ar") for c in (cards or [])
                if isinstance(c, dict) and c.get("title_ar")
            ],
        }

        # Wrap LLM calls so any unexpected exception fails closed to a
        # structured "unavailable" status rather than bubbling a 500.
        try:
            story_res = await hakim_generate(
                mode="generate", field="parent_weekly_story",
                text="", context=ctx, language="ar", tone="educational",
                tenant_id=school_id,
            )
            tip_res = await hakim_generate(
                mode="generate", field="parent_weekly_tip",
                text="", context=(tip_ctx if cards else ctx),
                language="ar", tone="educational",
                tenant_id=school_id,
            )
        except Exception as e:
            logger.warning(f"weekly_insight hakim_generate raised: {e}")
            return {
                "status": "unavailable",
                "story": None,
                "tip": None,
                "generated_at": None,
                "week_start": week_start,
                "week_end": week_end,
            }

        story_ok = bool(story_res.get("success")) and bool(story_res.get("text"))
        tip_ok = bool(tip_res.get("success")) and bool(tip_res.get("text"))
        if not (story_ok and tip_ok):
            return {
                "status": "unavailable",
                "story": None,
                "tip": None,
                "generated_at": None,
                "week_start": week_start,
                "week_end": week_end,
            }

        generated_at = datetime.now(timezone.utc).isoformat()
        payload_data = {
            "story": story_res["text"],
            "tip": tip_res["text"],
            "generated_at": generated_at,
            "week_start": week_start,
            "week_end": week_end,
            "model": story_res.get("model"),
        }

        # 4) Upsert cache row (best-effort; never fail the request on cache write)
        try:
            existing = await gd_find_one(db.session, "ai_insights", {
                "insight_type": "parent_weekly_brief",
                "entity_type": "student",
                "entity_id": child_id,
                "school_id": school_id,
            })
            if existing:
                await gd_update_one(db.session, "ai_insights", {
                    "insight_type": "parent_weekly_brief",
                    "entity_type": "student",
                    "entity_id": child_id,
                    "school_id": school_id,
                }, {"data": payload_data})
            else:
                await gd_insert(db.session, "ai_insights", {
                    "id": str(uuid.uuid4()),
                    "school_id": school_id,
                    "entity_type": "student",
                    "entity_id": child_id,
                    "insight_type": "parent_weekly_brief",
                    "title": "قصة الأسبوع",
                    "content": payload_data["story"][:500],
                    "data": payload_data,
                    "severity": "info",
                    "is_actionable": False,
                })
        except Exception as e:
            logger.debug(f"weekly_insight cache write failed: {e}")

        return {
            "status": "available",
            "story": payload_data["story"],
            "tip": payload_data["tip"],
            "generated_at": generated_at,
            "week_start": week_start,
            "week_end": week_end,
            "from_cache": False,
        }

    @router.get("/child/{child_id}/weekly-story")
    async def get_child_weekly_story(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id, current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        now = datetime.now(SAUDI_TZ)
        today = now.date()
        days_since_saturday = (today.weekday() + 2) % 7
        week_start = today - timedelta(days=days_since_saturday)
        week_end = week_start + timedelta(days=5)

        # Tenant scoping: enforce school_id on every weekly signal query so a
        # parent can never see data outside their tenant, even on UUID collision.
        tenant_school_id = child.get("school_id") or school_id

        participation = await gd_find(db.session, "participation_records", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
        }, limit=200)
        participation_count = len(participation)

        positive_behaviors = await gd_count(db.session, "behaviour_records", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "type": "positive",
            "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
        })

        skills = await gd_find(db.session, "session_interactions", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
        }, limit=200)
        acquired_skills = list(set(
            s.get("skill_tag") for s in skills if s.get("skill_tag")
        ))

        week_grades = await gd_find(db.session, "grades", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "date": {"$gte": week_start.isoformat(), "$lte": week_end.isoformat()}
        }, limit=200)
        subject_scores = {}
        for g in week_grades:
            subj = g.get("subject_name") or g.get("subject_id", "عام")
            if subj not in subject_scores:
                subject_scores[subj] = []
            subject_scores[subj].append(g.get("percentage", 0))

        strong_subjects = []
        weak_subjects = []
        for subj, scores in subject_scores.items():
            avg = sum(scores) / len(scores) if scores else 0
            if avg >= 80:
                strong_subjects.append({"subject": subj, "average": round(avg, 1)})
            elif avg < 60:
                weak_subjects.append({"subject": subj, "average": round(avg, 1)})

        remedial_plans = await gd_find(db.session, "student_plans", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "plan_type": "remedial",
            "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
        }, limit=20)

        # ----- Lateness / absence (this week) -----
        late_count = await gd_count(db.session, "attendance", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "status": "late",
            "date": {"$gte": week_start.isoformat(), "$lte": week_end.isoformat()}
        })
        absent_count = await gd_count(db.session, "attendance", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "status": "absent",
            "date": {"$gte": week_start.isoformat(), "$lte": week_end.isoformat()}
        })

        # ----- Homework completion (this week, best-effort) -----
        # Honest empty: when the school doesn't track assignments we leave
        # both at 0 so the ranker simply skips the homework cards.
        homework_total = 0
        homework_done = 0
        try:
            class_id = child.get("class_id")
            if class_id:
                week_assignments = await gd_find(db.session, "student_assignments", {
                    "class_id": class_id,
                    "school_id": tenant_school_id,
                    "due_date": {"$gte": week_start.isoformat(), "$lte": week_end.isoformat()},
                }, limit=50)
                if week_assignments:
                    assignment_ids = [a.get("id") for a in week_assignments if a.get("id")]
                    submissions = await gd_find(db.session, "assignment_submissions", {
                        "student_id": child_id,
                        "assignment_id": {"$in": assignment_ids},
                    }, limit=50) if assignment_ids else []
                    homework_total = len(week_assignments)
                    homework_done = len(submissions)
        except Exception as e:
            logger.debug(f"weekly homework signal lookup failed: {e}")

        daily_data = []
        day_names_ar = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"]
        for i in range(6):
            day_date = week_start + timedelta(days=i)
            day_str = day_date.isoformat()
            day_participation = sum(1 for p in participation if str(p.get("created_at", "")).startswith(day_str))
            day_behavior = await gd_count(db.session, "behaviour_records", {
                "student_id": child_id,
                "school_id": tenant_school_id,
                "type": "positive",
                "created_at": {"$gte": day_str, "$lt": (day_date + timedelta(days=1)).isoformat()}
            })
            daily_data.append({
                "day": day_names_ar[i],
                "date": day_str,
                "participation": day_participation,
                "positive_behavior": day_behavior,
            })

        remedial_plans_payload = [
            {
                "id": p.get("id"),
                "title": p.get("title", "خطة علاجية"),
                "description": p.get("description", ""),
                "subject": p.get("subject", ""),
                "teacher_name": p.get("teacher_name", ""),
                "created_at": p.get("created_at"),
            }
            for p in remedial_plans
        ]

        # ----- Compact ranked cards (top 2 positive + 1 concern + 1 academic)
        ranked_signals = {
            "grade_level": child.get("grade_level") or child.get("grade") or "",
            "participation_count": participation_count,
            "positive_behaviors": positive_behaviors,
            "acquired_skills": acquired_skills[:8],
            "strong_subjects": strong_subjects,
            "weak_subjects": weak_subjects,
            "remedial_plans": [
                {"title": p.get("title"), "subject": p.get("subject")}
                for p in remedial_plans_payload[:3]
            ],
            "late_count": late_count,
            "absent_count": absent_count,
            "homework_total": homework_total,
            "homework_done": homework_done,
        }
        cards = _rank_weekly_cards(ranked_signals)
        status = "available" if cards else "insufficient_data"

        # ----- Real Hakim insight (story + tip). The advice card is fed
        # ONLY by the structured ranked metrics — never by raw teacher notes.
        weekly_insight = await _get_or_build_parent_weekly_insight(
            child_id=child_id,
            school_id=child.get("school_id") or school_id,
            week_start=week_start.isoformat(),
            week_end=week_end.isoformat(),
            signals=ranked_signals,
            cards=cards,
        )

        # Advice card payload — present only when Hakim returned a real tip.
        # When the LLM is unavailable we omit it gracefully (FE skips it).
        advice = None
        if weekly_insight.get("status") == "available" and weekly_insight.get("tip"):
            advice = {
                "text_ar": weekly_insight.get("tip"),
                "generated_at": weekly_insight.get("generated_at"),
            }

        return {
            "status": status,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            # New compact, UI-ready payload (Task #324)
            "cards": cards,
            "advice": advice,
            # ---- Back-compat: keep legacy fields so older clients don't break
            "participation_count": participation_count,
            "positive_behaviors": positive_behaviors,
            "acquired_skills": acquired_skills,
            "strong_subjects": strong_subjects,
            "weak_subjects": weak_subjects,
            "remedial_plans": remedial_plans_payload,
            "daily_chart_data": daily_data,
            "weekly_insight": weekly_insight,
            "weekly_tip": weekly_insight.get("tip") if weekly_insight.get("status") == "available" else None,
        }

    # ============= WEEKLY ACADEMIC ANALYSIS =============
    # Backend-aggregated weekly pulse for the Parent Portal student profile
    # (التحليل الأكاديمي الأسبوعي). One endpoint, one student, one
    # parent-authorized context. Reuses _verify_parent_access as the sole
    # authorization boundary and enforces tenant scoping on every signal.
    @router.get("/child/{child_id}/weekly-analysis")
    async def get_child_weekly_analysis(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id, current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        # Saudi academic week: Saturday → Thursday (mirrors weekly-story).
        now = datetime.now(SAUDI_TZ)
        today = now.date()
        days_since_saturday = (today.weekday() + 2) % 7
        week_start = today - timedelta(days=days_since_saturday)
        week_end = week_start + timedelta(days=5)
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_end - timedelta(days=7)

        tenant_school_id = child.get("school_id") or school_id

        def _date_range(start, end):
            # inclusive [start, end] on a date column stored as ISO date.
            return {"$gte": start.isoformat(), "$lte": end.isoformat()}

        def _ts_range(start, end):
            # inclusive [start, end] on a timestamp column.
            return {"$gte": start.isoformat(), "$lt": (end + timedelta(days=1)).isoformat()}

        # ----- Attendance (this week) -----
        attendance_records = await gd_find(db.session, "attendance", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "date": _date_range(week_start, week_end),
        }, limit=50)

        att_counts = {"present": 0, "absent": 0, "late": 0, "excused": 0}
        per_day_status = {}
        for rec in attendance_records:
            status = (rec.get("status") or "").lower()
            if status in att_counts:
                att_counts[status] += 1
            day_key = str(rec.get("date") or "")[:10]
            if day_key:
                per_day_status[day_key] = status

        att_total = sum(att_counts.values())
        att_rate = round(((att_counts["present"] + att_counts["late"]) / att_total) * 100) if att_total > 0 else None

        # Prior-week attendance for trend
        prev_attendance = await gd_find(db.session, "attendance", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "date": _date_range(prev_week_start, prev_week_end),
        }, limit=50)
        prev_present = sum(1 for r in prev_attendance if (r.get("status") or "").lower() in ("present", "late"))
        prev_total = len(prev_attendance)
        prev_att_rate = round((prev_present / prev_total) * 100) if prev_total > 0 else None
        att_trend = (att_rate - prev_att_rate) if (att_rate is not None and prev_att_rate is not None) else None

        # ----- Behaviour (this week) -----
        positive_behaviour = await gd_count(db.session, "behaviour_records", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "type": "positive",
            "created_at": _ts_range(week_start, week_end),
        })
        negative_behaviour = await gd_count(db.session, "behaviour_records", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "type": "negative",
            "created_at": _ts_range(week_start, week_end),
        })
        behaviour_total = positive_behaviour + negative_behaviour
        behaviour_score = round((positive_behaviour / behaviour_total) * 100) if behaviour_total > 0 else None

        # ----- Assessments / grades (this week) -----
        week_grades = await gd_find(db.session, "grades", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "date": _date_range(week_start, week_end),
        }, limit=200)
        subj_buckets = {}
        all_pcts = []
        for g in week_grades:
            pct = g.get("percentage")
            if pct is None:
                continue
            try:
                pct_val = float(pct)
            except (TypeError, ValueError):
                continue
            all_pcts.append(pct_val)
            subj = g.get("subject_name") or g.get("subject_id") or "عام"
            subj_buckets.setdefault(subj, []).append(pct_val)
        grades_avg = round(sum(all_pcts) / len(all_pcts)) if all_pcts else None
        subjects_payload = [
            {"subject": s, "average": round(sum(v) / len(v), 1), "items": len(v)}
            for s, v in subj_buckets.items()
        ]
        subjects_payload.sort(key=lambda x: x["average"], reverse=True)

        # ----- Homework (this week, best-effort) -----
        hw_total = 0
        hw_done = 0
        hw_available = False
        try:
            class_id = child.get("class_id")
            if class_id:
                week_assignments = await gd_find(db.session, "student_assignments", {
                    "class_id": class_id,
                    "school_id": tenant_school_id,
                    "due_date": _date_range(week_start, week_end),
                }, limit=100)
                if week_assignments:
                    hw_available = True
                    assignment_ids = [a.get("id") for a in week_assignments if a.get("id")]
                    submissions = await gd_find(db.session, "assignment_submissions", {
                        "student_id": child_id,
                        "school_id": tenant_school_id,
                        "assignment_id": {"$in": assignment_ids},
                    }, limit=200) if assignment_ids else []
                    hw_total = len(week_assignments)
                    hw_done = len({s.get("assignment_id") for s in submissions if s.get("assignment_id")})
        except Exception as e:
            logger.debug(f"weekly-analysis homework lookup failed: {e}")
        hw_rate = round((hw_done / hw_total) * 100) if hw_total > 0 else None

        # ----- Per-day attendance series for the chart -----
        day_names_ar = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"]
        daily = []
        for i in range(6):
            d = week_start + timedelta(days=i)
            iso = d.isoformat()
            status = per_day_status.get(iso)
            daily.append({
                "day_ar": day_names_ar[i],
                "date": iso,
                "status": status,             # null when no record yet
                "is_future": d > today,
                "is_today": d == today,
            })

        # ----- Metric envelope (each carries an availability flag) -----
        metrics = [
            {
                "key": "attendance",
                "label_ar": "الحضور",
                "available": att_rate is not None,
                "value": att_rate,
                "unit": "%",
                "trend": att_trend,
                "details": {
                    "present": att_counts["present"],
                    "absent": att_counts["absent"],
                    "late": att_counts["late"],
                    "excused": att_counts["excused"],
                    "total": att_total,
                },
            },
            {
                "key": "assessments",
                "label_ar": "التقييمات",
                "available": grades_avg is not None,
                "value": grades_avg,
                "unit": "%",
                "trend": None,
                "details": {"items": len(all_pcts), "subjects": subjects_payload[:5]},
            },
            {
                "key": "behaviour",
                "label_ar": "السلوك",
                "available": behaviour_score is not None,
                "value": behaviour_score,
                "unit": "%",
                "trend": None,
                "details": {
                    "positive": positive_behaviour,
                    "negative": negative_behaviour,
                    "total": behaviour_total,
                },
            },
            {
                "key": "homework",
                "label_ar": "الواجبات",
                "available": hw_available,
                "value": hw_rate,
                "unit": "%",
                "trend": None,
                "details": {"done": hw_done, "total": hw_total},
            },
        ]

        any_available = any(m["available"] for m in metrics)
        status = "available" if any_available else "insufficient_data"

        # Short Arabic headline derived ONLY from real metrics (no LLM here).
        if not any_available:
            headline_ar = "لا توجد بيانات كافية للأسبوع الحالي"
        else:
            parts = []
            if att_rate is not None:
                parts.append(f"الحضور {att_rate}%")
            if grades_avg is not None:
                parts.append(f"المعدل {grades_avg}%")
            if behaviour_total > 0:
                parts.append(f"{positive_behaviour} ملاحظة إيجابية")
            headline_ar = " · ".join(parts) if parts else "ملخص الأسبوع متاح"

        return {
            "status": status,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "headline_ar": headline_ar,
            "metrics": metrics,
            "daily_attendance": daily,
            "last_updated": now.isoformat(),
            "empty_hint_ar": "لا توجد بيانات كافية للأسبوع الحالي",
        }

    # ============= STUDENT INSIGHTS (cohesive parent-facing) =============
    # GET /parent-portal/child/{child_id}/insights
    #
    # One backend-aggregated payload powering the cohesive Parent Portal
    # Student-Profile insights surface:
    #   - generalInsights.strengths / weaknesses  (deterministic tags from real data)
    #   - subjects[] accordion with per-subject score, trend, level, tags, action plan
    #   - hakimSummary  (grounded narrative; reuses existing hakim_llm_service)
    #   - parentTips    (Hakim subject-focused tip on the most attention-needing subject)
    #   - insufficientDataFlags
    #
    # Authorization: reuses _verify_parent_access (the sole parent ↔ student
    # boundary used everywhere in this module). Tenant scoping is enforced
    # on every signal query. Hakim is called at most twice and falls back
    # cleanly to deterministic output when unavailable / disabled.
    @router.get("/child/{child_id}/insights")
    async def get_child_insights(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id, current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        tenant_school_id = child.get("school_id") or school_id
        now = datetime.now(SAUDI_TZ)
        today = now.date()
        # Two ~30-day windows so we have a real "previous" baseline for trend.
        window_days = 30
        current_start = today - timedelta(days=window_days - 1)
        previous_start = today - timedelta(days=2 * window_days - 1)
        previous_end = current_start - timedelta(days=1)

        # ---- Grades (single bulk fetch, then split into current vs previous) ----
        all_grades = await gd_find(db.session, "grades", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "date": {"$gte": previous_start.isoformat(), "$lte": today.isoformat()},
        }, order_by="date", desc_order=True, limit=500)

        def _pct(g):
            v = g.get("percentage")
            if v is None:
                try:
                    score = float(g.get("score") or 0)
                    mx = float(g.get("max_score") or 0)
                    return (score / mx) * 100 if mx > 0 else None
                except (TypeError, ValueError):
                    return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        # Group per subject (key on subject_id when present, else name) and
        # keep both current and previous buckets in one O(N) pass.
        subjects_acc = {}
        for g in all_grades:
            pct = _pct(g)
            if pct is None:
                continue
            subj_id = g.get("subject_id") or ""
            subj_name = g.get("subject_name") or g.get("subject") or "غير محدد"
            key = subj_id or subj_name
            d_str = str(g.get("date") or "")[:10]
            if not d_str:
                continue
            try:
                d = datetime.fromisoformat(d_str).date()
            except ValueError:
                continue
            bucket = subjects_acc.setdefault(key, {
                "subject_id": subj_id or None,
                "subject_name": subj_name,
                "current": [],
                "previous": [],
                "teacher_id": g.get("teacher_id"),
            })
            if d >= current_start:
                bucket["current"].append(pct)
            elif previous_start <= d <= previous_end:
                bucket["previous"].append(pct)

        # ---- Bulk teacher-name lookup (no N+1) ----
        teacher_ids = {b["teacher_id"] for b in subjects_acc.values() if b.get("teacher_id")}
        teacher_name_map = {}
        if teacher_ids:
            try:
                tch_rows = await gd_find(db.session, "teachers", {
                    "id": {"$in": list(teacher_ids)},
                    "school_id": tenant_school_id,
                }, limit=200)
                for t in tch_rows:
                    teacher_name_map[t.get("id")] = t.get("full_name") or t.get("name")
                # Fallback to users table for any unresolved teacher_id.
                missing = [tid for tid in teacher_ids if tid not in teacher_name_map]
                if missing:
                    # Tenant-scope the users fallback so a foreign-tenant
                    # teacher_id stamped on a grade row can never resolve to
                    # a name from another school (PII isolation).
                    u_rows = await gd_find(db.session, "users", {
                        "id": {"$in": missing},
                        "school_id": tenant_school_id,
                    }, limit=200)
                    for u in u_rows:
                        teacher_name_map[u.get("id")] = u.get("full_name") or u.get("name")
            except Exception as e:
                logger.debug(f"insights teacher name lookup failed: {e}")

        # ---- Attendance & behaviour (current window only, for general tags) ----
        attendance_records = await gd_find(db.session, "attendance", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "date": {"$gte": current_start.isoformat(), "$lte": today.isoformat()},
        }, limit=500)
        att_present = sum(1 for r in attendance_records if (r.get("status") or "").lower() == "present")
        att_late = sum(1 for r in attendance_records if (r.get("status") or "").lower() == "late")
        att_absent = sum(1 for r in attendance_records if (r.get("status") or "").lower() == "absent")
        att_total = att_present + att_late + att_absent + sum(
            1 for r in attendance_records if (r.get("status") or "").lower() == "excused"
        )
        att_rate = round(((att_present + att_late) / att_total) * 100) if att_total > 0 else None

        positive_b = await gd_count(db.session, "behaviour_records", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "type": "positive",
            "created_at": {"$gte": current_start.isoformat(), "$lt": (today + timedelta(days=1)).isoformat()},
        })
        negative_b = await gd_count(db.session, "behaviour_records", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "type": "negative",
            "created_at": {"$gte": current_start.isoformat(), "$lt": (today + timedelta(days=1)).isoformat()},
        })

        # ---- Per-subject deterministic computation ----
        def _level(score):
            if score is None:
                return "insufficient"
            if score >= 85:
                return "advanced"        # متقدم
            if score >= 70:
                return "intermediate"    # متوسط
            return "needs_focus"         # يحتاج تركيز

        def _trend(curr_avg, prev_avg):
            if curr_avg is None or prev_avg is None:
                return "insufficient"
            delta = curr_avg - prev_avg
            if delta >= 3:
                return "improving"
            if delta <= -3:
                return "declining"
            return "stable"

        subjects_payload = []
        for key, b in subjects_acc.items():
            curr_avg = round(sum(b["current"]) / len(b["current"]), 1) if b["current"] else None
            prev_avg = round(sum(b["previous"]) / len(b["previous"]), 1) if b["previous"] else None
            level = _level(curr_avg)
            trend = _trend(curr_avg, prev_avg)

            # Deterministic per-subject tags. Empty by design when there is
            # not enough evidence — Hakim never invents tags.
            strengths = []
            weaknesses = []
            if curr_avg is not None:
                if curr_avg >= 90:
                    strengths.append("أداء متميز")
                elif curr_avg >= 80:
                    strengths.append("أداء قوي")
                if trend == "improving":
                    strengths.append("اتجاه تحسن")
                if curr_avg < 60:
                    weaknesses.append("معدل منخفض")
                elif curr_avg < 70:
                    weaknesses.append("يحتاج تعزيز")
                if trend == "declining":
                    weaknesses.append("اتجاه تراجع")

            # Deterministic action plan (rule-based; Hakim only refines wording).
            action_plan = None
            if curr_avg is not None and len(b["current"]) >= 1:
                if level == "advanced":
                    action_plan = {
                        "type": "enrichment",
                        "title": "خطة إثرائية",
                        "description": "اقترحوا أنشطة إثرائية بسيطة في المنزل تواكب تميّز الطالب في هذه المادة.",
                        "hint": "تحديات إضافية لتنمية الموهبة",
                    }
                elif level == "needs_focus":
                    action_plan = {
                        "type": "remedial",
                        "title": "خطة علاجية",
                        "description": "خصّصوا وقتاً قصيراً يومياً لمراجعة المفاهيم الأساسية بأسلوب هادئ ومتكرر.",
                        "hint": "خطوات يومية بسيطة في المنزل",
                    }

            subjects_payload.append({
                "id": b["subject_id"] or key,
                "name": b["subject_name"],
                "score": curr_avg,
                "previous_score": prev_avg,
                "trend_status": trend,
                "level": level,
                "teacher_name": teacher_name_map.get(b.get("teacher_id")) if b.get("teacher_id") else None,
                "items_current": len(b["current"]),
                "items_previous": len(b["previous"]),
                "strengths": strengths,
                "weaknesses": weaknesses,
                "action_plan": action_plan,
            })

        # Sort: weakest first if any are weak (parent attention), else strongest first.
        subjects_payload.sort(key=lambda s: (s["score"] is None, s["score"] or 0))

        # ---- General strengths / weaknesses (deterministic only) ----
        general_strengths = []
        general_weaknesses = []
        if att_rate is not None and att_rate >= 90:
            general_strengths.append("التزام جيد بالحضور")
        if att_rate is not None and att_rate < 75 and att_total >= 5:
            general_weaknesses.append("الحضور والانضباط")
        if positive_b >= 3 and positive_b > negative_b:
            general_strengths.append("سلوك إيجابي ملحوظ")
        if negative_b >= 3 and negative_b > positive_b:
            general_weaknesses.append("ملاحظات سلوكية تحتاج متابعة")

        strong_subjects_names = [s["name"] for s in subjects_payload if s["level"] == "advanced"]
        weak_subjects_names = [s["name"] for s in subjects_payload if s["level"] == "needs_focus"]
        improving_names = [s["name"] for s in subjects_payload if s["trend_status"] == "improving"]
        declining_names = [s["name"] for s in subjects_payload if s["trend_status"] == "declining"]

        if strong_subjects_names:
            general_strengths.append(f"تميّز في {('، '.join(strong_subjects_names[:2]))}")
        if improving_names and not strong_subjects_names:
            general_strengths.append(f"تحسّن في {('، '.join(improving_names[:2]))}")
        if weak_subjects_names:
            general_weaknesses.append(f"تركيز إضافي في {('، '.join(weak_subjects_names[:2]))}")
        if declining_names and not weak_subjects_names:
            general_weaknesses.append(f"تراجع في {('، '.join(declining_names[:2]))}")

        # Deduplicate while preserving order
        def _dedupe(lst):
            seen = set()
            out = []
            for x in lst:
                if x and x not in seen:
                    seen.add(x)
                    out.append(x)
            return out
        general_strengths = _dedupe(general_strengths)[:4]
        general_weaknesses = _dedupe(general_weaknesses)[:4]

        # ---- Insufficient-data flags ----
        insufficient_flags = {
            "general_strengths": len(general_strengths) == 0,
            "general_weaknesses": len(general_weaknesses) == 0,
            "subjects": len(subjects_payload) == 0,
            "no_grades_at_all": len(all_grades) == 0,
        }

        overall_trend = "stable"
        if improving_names and not declining_names:
            overall_trend = "improving"
        elif declining_names and not improving_names:
            overall_trend = "declining"
        elif not subjects_payload:
            overall_trend = "insufficient"

        # ---- Hakim narrative + per-subject tip (grounded; safe fallback) ----
        hakim_summary = {"status": "insufficient_data", "text": None}
        parent_tips = []
        try:
            from services.hakim_llm_service import hakim_generate, is_available as hakim_available
        except Exception as e:
            logger.debug(f"insights: hakim service unavailable: {e}")
            hakim_generate = None
            hakim_available = lambda: False  # noqa: E731

        # Only call Hakim when we actually have something factual to summarize.
        has_signal = bool(general_strengths or general_weaknesses or subjects_payload)

        # SECURITY (task #438): per-child, per-day AI cache.  Check the
        # ai_insights table before triggering any LLM calls.  This mirrors
        # the weekly-story cache pattern and ensures that repeated requests
        # from the same parent within a calendar day do not re-invoke Hakim.
        _insights_cache_date_key = today.isoformat()
        _insights_cached_ai = None
        if has_signal:
            try:
                _cache_row = await gd_find_one(db.session, "ai_insights", {
                    "insight_type": "parent_insights_daily",
                    "entity_type": "student",
                    "entity_id": child_id,
                    "school_id": tenant_school_id,
                })
                if _cache_row and isinstance(_cache_row.get("data"), dict):
                    if _cache_row["data"].get("cache_date") == _insights_cache_date_key:
                        _insights_cached_ai = _cache_row["data"]
            except Exception as _ce:
                logger.debug(f"insights: ai cache lookup failed: {_ce}")

        if _insights_cached_ai:
            hakim_summary = _insights_cached_ai.get("hakim_summary", {"status": "insufficient_data", "text": None})
            parent_tips = _insights_cached_ai.get("parent_tips", [])
        elif has_signal and hakim_generate and hakim_available():
            summary_ctx = {
                "grade_level": child.get("grade_level") or child.get("grade") or "",
                "general_strengths": general_strengths,
                "general_weaknesses": general_weaknesses,
                "strong_subjects": strong_subjects_names[:3],
                "weak_subjects": weak_subjects_names[:3],
                "overall_trend": {
                    "improving": "تحسن",
                    "declining": "تراجع",
                    "stable": "مستقر",
                    "insufficient": "غير كافٍ",
                }.get(overall_trend, "مستقر"),
            }
            try:
                summary_res = await hakim_generate(
                    mode="generate", field="parent_insights_summary",
                    text="", context=summary_ctx, language="ar", tone="educational",
                    tenant_id=tenant_school_id,
                )
                if summary_res.get("success") and summary_res.get("text"):
                    hakim_summary = {"status": "available", "text": summary_res["text"]}
                else:
                    hakim_summary = {"status": "unavailable", "text": None}
            except Exception as e:
                logger.warning(f"insights: parent_insights_summary failed: {e}")
                hakim_summary = {"status": "unavailable", "text": None}

            # Single subject-focused tip on the highest-attention subject
            # (weakest available with at least one current grade).
            focus_subject = next(
                (s for s in subjects_payload if s["score"] is not None and s["level"] == "needs_focus"),
                None,
            ) or next(
                (s for s in subjects_payload if s["score"] is not None and s["level"] == "advanced"),
                None,
            )
            if focus_subject:
                tip_ctx = {
                    "subject_name": focus_subject["name"],
                    "subject_score": focus_subject["score"],
                    "subject_trend": {
                        "improving": "تحسن",
                        "declining": "تراجع",
                        "stable": "مستقر",
                        "insufficient": "غير كافٍ",
                    }.get(focus_subject["trend_status"], "مستقر"),
                    "subject_strengths": focus_subject["strengths"],
                    "subject_weaknesses": focus_subject["weaknesses"],
                    "subject_level": {
                        "advanced": "متقدم",
                        "intermediate": "متوسط",
                        "needs_focus": "يحتاج تركيز",
                    }.get(focus_subject["level"], "متوسط"),
                }
                try:
                    tip_res = await hakim_generate(
                        mode="generate", field="parent_subject_focus_tip",
                        text="", context=tip_ctx, language="ar", tone="educational",
                        tenant_id=tenant_school_id,
                    )
                    if tip_res.get("success") and tip_res.get("text"):
                        parent_tips.append({
                            "subject": focus_subject["name"],
                            "text": tip_res["text"],
                        })
                except Exception as e:
                    logger.debug(f"insights: parent_subject_focus_tip failed: {e}")

            # SECURITY (task #438): persist AI results so repeat requests
            # within the same calendar day are served from cache without
            # triggering further LLM calls.  Best-effort — never fail the
            # request on a cache write error.
            if hakim_summary.get("status") == "available":
                try:
                    _cache_payload = {
                        "cache_date": _insights_cache_date_key,
                        "hakim_summary": hakim_summary,
                        "parent_tips": parent_tips,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    }
                    _existing_cache = await gd_find_one(db.session, "ai_insights", {
                        "insight_type": "parent_insights_daily",
                        "entity_type": "student",
                        "entity_id": child_id,
                        "school_id": tenant_school_id,
                    })
                    if _existing_cache:
                        await gd_update_one(db.session, "ai_insights", {
                            "insight_type": "parent_insights_daily",
                            "entity_type": "student",
                            "entity_id": child_id,
                            "school_id": tenant_school_id,
                        }, {"data": _cache_payload})
                    else:
                        await gd_insert(db.session, "ai_insights", {
                            "id": str(uuid.uuid4()),
                            "school_id": tenant_school_id,
                            "entity_type": "student",
                            "entity_id": child_id,
                            "insight_type": "parent_insights_daily",
                            "title": "رؤى الطالب اليومية",
                            "content": (hakim_summary.get("text") or "")[:500],
                            "data": _cache_payload,
                            "severity": "info",
                            "is_actionable": False,
                        })
                except Exception as _cwe:
                    logger.debug(f"insights: ai cache write failed: {_cwe}")
        elif has_signal:
            hakim_summary = {"status": "unavailable", "text": None}

        return {
            "status": "available" if has_signal else "insufficient_data",
            "window": {
                "current_start": current_start.isoformat(),
                "current_end": today.isoformat(),
                "previous_start": previous_start.isoformat(),
                "previous_end": previous_end.isoformat(),
            },
            "general_insights": {
                "strengths": general_strengths,
                "weaknesses": general_weaknesses,
            },
            "overall_trend": overall_trend,
            "subjects": subjects_payload,
            "hakim_summary": hakim_summary,
            "parent_tips": parent_tips,
            "insufficient_data_flags": insufficient_flags,
            "empty_hint_ar": "لا توجد بيانات كافية لعرض الرؤى بعد",
            "last_updated": now.isoformat(),
        }

    # ============= STUDENT PROFILE =============

    @router.get("/child/{child_id}/profile")
    async def get_child_profile(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        sid = child.get("school_id") or current_user.get("tenant_id")
        school_name = child.get("school_name", "")
        if not school_name and sid:
            s_doc = await gd_find_one(db.session, "schools", {"id": sid})
            school_name = s_doc.get("name") if s_doc else ""

        # Task #277 — IT context for the parent profile page header.
        is_it_ws = isinstance(sid, str) and sid.startswith("itw_")
        teacher_display_name = None
        if is_it_ws:
            owner_uid = sid[len("itw_"):]
            owner = await gd_find_one(db.session, "users", {"id": owner_uid})
            teacher_display_name = (owner or {}).get("full_name") or None

        return {
            "id": child.get("id"),
            "name": child.get("full_name"),
            "grade_level": child.get("grade_level", child.get("grade", "")),
            "class_name": child.get("class_name", ""),
            "school_id": sid,
            "school_name": school_name,
            "is_independent_teacher_workspace": bool(is_it_ws),
            "teacher_display_name": teacher_display_name,
            "emoji": (child.get("profile_settings") or {}).get("emoji") or child.get("emoji") or "👦",
            "profile_picture": child.get("profile_picture", ""),
            "gender": child.get("gender", ""),
            "health_conditions": (child.get("profile_settings") or {}).get("health_conditions", []),
            "behavioral_aspects": (child.get("profile_settings") or {}).get("behavioral_aspects", []),
            "family_situation": (child.get("profile_settings") or {}).get("family_situation", ""),
            "family_other_situations": (child.get("profile_settings") or {}).get("family_other_situations", []),
            # Free-text "Other" details for health and behavior — these
            # complement the strict enum lists above and let parents
            # describe conditions/aspects the curated catalogue does not
            # cover. Bounded by _PROFILE_OTHER_TEXT_MAX on write.
            "other_health_details": (child.get("profile_settings") or {}).get("other_health_details", ""),
            "other_behavior_details": (child.get("profile_settings") or {}).get("other_behavior_details", ""),
        }

    # Whitelist of values allowed in each list/single-value profile field.
    # Centralised so the FE chip catalogue and BE persisted values cannot
    # drift apart and so an attacker cannot persist arbitrary tag strings
    # on another family's child record.
    _PROFILE_HEALTH_ALLOWED = {
        "asthma", "weak_vision", "weak_hearing", "allergy", "heart",
        "food_allergy", "nut_allergy", "dust_allergy", "seasonal_allergy",
        "diabetes", "epilepsy",
    }
    _PROFILE_BEHAVIOR_ALLOWED = {
        "shyness", "severe_shyness", "hyperactivity", "motor_anxiety",
        "concentration_difficulty", "speech_difficulty", "stuttering",
        "aggression", "anger", "sleep_disorder", "eating_difficulty",
    }
    _PROFILE_FAMILY_ALLOWED = {
        "both_parents", "father_only", "mother_only", "other",
    }
    _PROFILE_FAMILY_OTHER_ALLOWED = {
        "parents_separation", "parent_traveling", "foster_family",
        "orphan", "second_marriage", "family_problems",
    }
    _PROFILE_EMOJI_ALLOWED = {
        "👦", "👧", "🧒", "👨‍🎓", "👩‍🎓", "🦸‍♂️", "🦸‍♀️",
        "🧑‍💻", "🎨", "⚽", "🎵", "📚", "🌟", "🦋", "🚀", "🎯",
    }
    # Hard cap on the free-text "Other" descriptions so a malicious
    # parent can't grow the per-student JSONB row indefinitely. 255
    # matches the FE textarea maxLength.
    _PROFILE_OTHER_TEXT_MAX = 255

    def _sanitize_other_text(raw) -> str:
        if not isinstance(raw, str):
            return ""
        cleaned = raw.strip()
        if not cleaned:
            return ""
        return cleaned[:_PROFILE_OTHER_TEXT_MAX]

    def _sanitize_str_list(raw, allowed: set) -> list:
        if not isinstance(raw, list):
            return []
        seen = set()
        out = []
        for item in raw:
            if isinstance(item, str) and item in allowed and item not in seen:
                seen.add(item)
                out.append(item)
        return out

    @router.put("/child/{child_id}/profile")
    async def update_child_profile(
        child_id: str,
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        child = await _verify_parent_access(
            parent_id, parent_phone, child_id,
            current_user.get("tenant_id"), current_user=current_user,
        )
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="بيانات غير صالحة")

        # Merge into the existing per-student profile_settings JSONB so a
        # partial save (e.g. only family_situation) does not clobber the
        # other groups the parent had previously stored for this child.
        current_settings = dict(child.get("profile_settings") or {})

        if "emoji" in data:
            emoji = data.get("emoji")
            if isinstance(emoji, str) and emoji in _PROFILE_EMOJI_ALLOWED:
                current_settings["emoji"] = emoji
        if "health_conditions" in data:
            current_settings["health_conditions"] = _sanitize_str_list(
                data.get("health_conditions"), _PROFILE_HEALTH_ALLOWED,
            )
        if "behavioral_aspects" in data:
            current_settings["behavioral_aspects"] = _sanitize_str_list(
                data.get("behavioral_aspects"), _PROFILE_BEHAVIOR_ALLOWED,
            )
        if "family_situation" in data:
            fs = data.get("family_situation")
            if fs in _PROFILE_FAMILY_ALLOWED:
                current_settings["family_situation"] = fs
            elif fs in (None, ""):
                current_settings["family_situation"] = ""
        if "family_other_situations" in data:
            current_settings["family_other_situations"] = _sanitize_str_list(
                data.get("family_other_situations"), _PROFILE_FAMILY_OTHER_ALLOWED,
            )
        # Free-text complements to the strict enum lists. Sending an
        # empty string clears the prior value so the FE can switch the
        # "أخرى" pill off without leaving stale text behind.
        if "other_health_details" in data:
            current_settings["other_health_details"] = _sanitize_other_text(
                data.get("other_health_details"),
            )
        if "other_behavior_details" in data:
            current_settings["other_behavior_details"] = _sanitize_other_text(
                data.get("other_behavior_details"),
            )

        if current_settings == (child.get("profile_settings") or {}):
            return {
                "success": True,
                "message": "لا توجد تغييرات",
                "profile_settings": current_settings,
            }

        # Write is scoped by students.id AND school_id so a parent cannot
        # widen the write past the tenant boundary enforced by
        # _verify_parent_access above (defence-in-depth).
        write_filter = {"id": child_id}
        sid = child.get("school_id") or current_user.get("tenant_id")
        if sid:
            write_filter["school_id"] = sid
        await gd_update_one(
            db.session, "students", write_filter,
            {"$set": {"profile_settings": current_settings}},
        )
        return {
            "success": True,
            "message": "تم تحديث الملف بنجاح",
            "profile_settings": current_settings,
        }

    # ============= ACHIEVEMENTS =============

    @router.get("/child/{child_id}/achievements")
    async def get_child_achievements(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        achievements = await gd_find(
            db.session, "student_achievements",
            {"student_id": child_id},
            order_by="created_at", desc_order=True, limit=100
        )
        return {"achievements": achievements, "total": len(achievements)}

    @router.post("/child/{child_id}/achievements")
    async def add_child_achievement(
        child_id: str,
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")
        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id, current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        ALLOWED_TYPES = {"academic", "sports", "arts", "behavior", "other"}

        ach_name = (data.get("name") or "").strip()
        if not ach_name:
            raise HTTPException(status_code=400, detail="اسم الإنجاز مطلوب")

        ach_type = data.get("type", "other")
        if ach_type not in ALLOWED_TYPES:
            ach_type = "other"

        achievement = {
            "id": str(uuid.uuid4()),
            "student_id": child_id,
            "school_id": child.get("school_id", school_id),
            "name": ach_name,
            "type": ach_type,
            "source": "parent",
            "source_user_id": parent_id,
            "file_url": "",
            "file_data": "",
            "file_name": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(db.session, "student_achievements", achievement)
        return {"success": True, "achievement": achievement}

    ALLOWED_ACHIEVEMENT_MIMES = {
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    @router.post("/child/{child_id}/achievements/upload")
    async def upload_child_achievement(
        child_id: str,
        name: str = Form(...),
        type: str = Form("other"),
        file: UploadFile = File(None),
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        import base64
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")
        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id, current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        clean_name = name.strip()
        if not clean_name:
            raise HTTPException(status_code=400, detail="اسم الإنجاز مطلوب")

        allowed_types = {"academic", "sports", "arts", "behavior", "other"}
        if type not in allowed_types:
            type = "other"

        file_data = ""
        file_name = ""
        if file and file.filename:
            if file.content_type not in ALLOWED_ACHIEVEMENT_MIMES:
                raise HTTPException(status_code=400, detail="نوع الملف غير مسموح — يرجى رفع صورة أو PDF أو مستند Word")
            content = await file.read()
            if len(content) > 5 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="حجم الملف يجب أن يكون أقل من 5 ميجابايت")
            encoded = base64.b64encode(content).decode("utf-8")
            file_data = f"data:{file.content_type};base64,{encoded}"
            file_name = file.filename

        achievement = {
            "id": str(uuid.uuid4()),
            "student_id": child_id,
            "school_id": child.get("school_id", school_id),
            "name": clean_name,
            "type": type,
            "source": "parent",
            "source_user_id": parent_id,
            "file_data": file_data,
            "file_name": file_name,
            "file_url": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(db.session, "student_achievements", achievement)
        return {"success": True, "achievement": achievement}

    # ============= ANALYTICS =============

    @router.get("/child/{child_id}/analytics")
    async def get_child_analytics(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")
        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id, current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        all_grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=1000)
        overall_avg = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1) if all_grades else 0

        # Build the radar from real subjects the student actually has grades
        # in — never inject hardcoded subject names with 0% scores, which
        # would invent failing subjects the student never took.
        # (Audit 2026-05-10.)
        subject_all = {}
        for g in all_grades:
            subj = g.get("subject_name") or g.get("subject_id", "عام")
            if subj not in subject_all:
                subject_all[subj] = []
            subject_all[subj].append(g.get("percentage", 0))

        radar_data = sorted(
            [
                {"subject": subj, "score": round(sum(scores) / len(scores), 1)}
                for subj, scores in subject_all.items() if scores
            ],
            key=lambda r: r["score"],
            reverse=True,
        )[:6]

        monthly_data = {}
        for g in all_grades:
            date_str = str(g.get("date", ""))
            if date_str and len(date_str) >= 7:
                month_key = date_str[:7]
                if month_key not in monthly_data:
                    monthly_data[month_key] = []
                monthly_data[month_key].append(g.get("percentage", 0))

        line_chart_data = sorted([
            {"month": k, "average": round(sum(v) / len(v), 1)}
            for k, v in monthly_data.items()
        ], key=lambda x: x["month"])

        class_id = child.get("class_id")
        class_avg = 0
        child_school_id = child.get("school_id") or school_id
        if class_id:
            classmates = await gd_find(db.session, "students", {"class_id": class_id, "school_id": child_school_id}, limit=100)
            classmate_ids = [c.get("id") for c in classmates if c.get("id") != child_id]
            if classmate_ids:
                class_grades = await gd_find(db.session, "grades", {
                    "student_id": {"$in": classmate_ids}
                }, limit=5000)
                class_avg = round(sum(g.get("percentage", 0) for g in class_grades) / len(class_grades), 1) if class_grades else 0

        strengths = []
        weaknesses = []
        for subj, scores in subject_all.items():
            avg = round(sum(scores) / len(scores), 1) if scores else 0
            if avg >= 80:
                strengths.append({"area": subj, "detail": f"متوسط {avg}%"})
            elif avg < 60:
                weaknesses.append({"area": subj, "detail": f"متوسط {avg}%"})

        total_participation = await gd_count(db.session, "participation_records", {"student_id": child_id})
        if total_participation > 20:
            strengths.append({"area": "مشاركة صفية", "detail": f"{total_participation} مشاركة مسجلة"})

        total_att = await gd_count(db.session, "attendance", {"student_id": child_id})
        present_att = await gd_count(db.session, "attendance", {"student_id": child_id, "status": "present"})
        # 0 (not the old fake 100) when no attendance — keeps the composite
        # follow-up math finite while not inflating the breakdown card.
        # (Audit 2026-05-10.)
        att_rate = round((present_att / total_att * 100), 1) if total_att > 0 else 0

        assignments = await gd_find(db.session, "student_assignments", {
            "$or": [{"class_id": class_id}, {"grade_id": child.get("grade_id")}]
        }, limit=200) if class_id else []
        submissions = await gd_find(db.session, "assignment_submissions", {
            "student_id": child_id
        }, limit=200)
        homework_rate = round(len(submissions) / max(1, len(assignments)) * 100, 1)

        if homework_rate < 60:
            weaknesses.append({"area": "واجبات غير مكتملة", "detail": f"نسبة إنجاز {homework_rate}%"})

        follow_up_score = (att_rate * 0.3) + (homework_rate * 0.3) + (min(total_participation, 50) / 50 * 100 * 0.2) + (overall_avg * 0.2)
        if follow_up_score >= 75:
            follow_up_status = "مستقر"
        elif follow_up_score >= 50:
            follow_up_status = "يحتاج متابعة"
        else:
            follow_up_status = "بحاجة دعم"

        if overall_avg >= 90:
            level = "ممتاز"
        elif overall_avg >= 80:
            level = "جيد جداً"
        elif overall_avg >= 70:
            level = "جيد"
        elif overall_avg >= 60:
            level = "مقبول"
        else:
            level = "ضعيف"

        return {
            "student_name": child.get("full_name"),
            "summary": {
                "overall_average": overall_avg,
                "level": level,
                "class_average": class_avg,
                "total_assessments": len(all_grades),
            },
            "gauge_data": {"value": overall_avg, "level": level},
            "line_chart_data": line_chart_data,
            "radar_data": radar_data,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "follow_up": {
                "score": round(follow_up_score, 1),
                "status": follow_up_status,
                "breakdown": {
                    "attendance_rate": att_rate,
                    "homework_rate": homework_rate,
                    "participation_score": round(min(total_participation, 50) / 50 * 100, 1),
                    "academic_average": overall_avg,
                }
            }
        }

    # ============= OPEN REQUESTS COUNT =============

    @router.get("/open-requests-count")
    async def get_open_requests_count(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        open_messages = await gd_count(db.session, "messages", {
            "sender_id": parent_id,
            "status": {"$in": ["open", "pending", "sent"]}
        })
        open_excuses = await gd_count(db.session, "absence_excuses", {
            "parent_id": parent_id,
            "status": {"$in": ["pending", "submitted"]}
        })
        open_meetings = await gd_count(db.session, "meeting_requests", {
            "parent_id": parent_id,
            "status": {"$in": ["pending", "submitted"]}
        })
        total_open = open_messages + open_excuses + open_meetings
        return {
            "total_open": total_open,
            "limit": 3,
            "can_submit": total_open < 3,
            "breakdown": {
                "messages": open_messages,
                "excuses": open_excuses,
                "meetings": open_meetings,
            }
        }

    # ============= MESSAGE RECIPIENTS (teachers of parent's children) =============

    async def _resolve_parent_teacher_recipients(current_user: dict) -> list:
        """Resolve the set of teacher *user* accounts that the authenticated
        parent is allowed to message. Walks parent → children → the child's
        current class schedule (``schedule_sessions``, the canonical live
        timetable table) → teachers.user_id → users(role=teacher,
        tenant_id=school_id, is_active=true). Returns a list of dicts:
        {recipient_user_id, teacher_name, child_labels: [..]}. Never includes
        cross-tenant users; on resolution ambiguity, omits the entry.

        NOTE: the recipient set is derived from ``schedule_sessions`` (scoped
        by both class and tenant), NOT the legacy ``timetable_sessions``
        document store. ``timetable_sessions`` accumulates a separate set of
        rows per historical timetable run and is no longer anchored to any
        ``timetables`` record, so querying it by class alone returned every
        teacher ever associated with the class (over-disclosure). Tenants whose
        live schedule lives only in ``schedule_sessions`` returned nothing.
        See docs/qa/2026-05-31-parent-dropdowns-audit.md (Finding 1)."""
        school_id = current_user.get("tenant_id")
        if not school_id:
            return []
        children = await _find_children(current_user, current_user.get("phone"), school_id)
        # Keep only children in this tenant and build class -> child label map
        class_to_children: dict = {}
        for child in children:
            if child.get("school_id") and child.get("school_id") != school_id:
                continue
            cid = child.get("class_id")
            if not cid:
                continue
            label = child.get("full_name") or child.get("name") or ""
            class_to_children.setdefault(cid, []).append(label)
        if not class_to_children:
            return []
        class_ids = list(class_to_children.keys())
        # Source of truth is ``schedule_sessions`` (the live timetable table),
        # scoped by BOTH class and tenant. See the function docstring / Finding
        # 1 for why ``timetable_sessions`` must not be used here.
        sessions = await gd_find(db.session, "schedule_sessions",
                                 {"class_id": {"$in": class_ids},
                                  "school_id": school_id}, limit=2000)
        teacher_to_classes: dict = {}
        for s in sessions:
            tid = s.get("teacher_id")
            cid = s.get("class_id")
            if not tid or not cid:
                continue
            teacher_to_classes.setdefault(tid, set()).add(cid)
        if not teacher_to_classes:
            return []
        teacher_ids = list(teacher_to_classes.keys())
        # Bulk-resolve teachers -> user_id in this tenant
        teacher_rows = await gd_find(db.session, "teachers",
                                     {"id": {"$in": teacher_ids},
                                      "school_id": school_id,
                                      "is_active": True},
                                     limit=1000)
        user_ids = [t.get("user_id") for t in teacher_rows if t.get("user_id")]
        if not user_ids:
            return []
        users = await gd_find(db.session, "users",
                              {"id": {"$in": user_ids},
                               "tenant_id": school_id,
                               "role": "teacher",
                               "is_active": True},
                              limit=1000)
        users_by_id = {u["id"]: u for u in users if u.get("id")}
        seen: set = set()
        recipients = []
        for t in teacher_rows:
            uid = t.get("user_id")
            if not uid or uid in seen:
                continue
            user = users_by_id.get(uid)
            if not user:
                continue
            child_labels = []
            for cid in teacher_to_classes.get(t.get("id"), set()):
                child_labels.extend(class_to_children.get(cid, []))
            # Dedupe child labels preserving order
            seen_labels = set()
            uniq_labels = []
            for lbl in child_labels:
                if lbl and lbl not in seen_labels:
                    seen_labels.add(lbl)
                    uniq_labels.append(lbl)
            recipients.append({
                "recipient_user_id": uid,
                "teacher_name": user.get("full_name") or t.get("full_name") or "",
                "child_labels": uniq_labels,
            })
            seen.add(uid)
        recipients.sort(key=lambda r: r.get("teacher_name") or "")
        return recipients

    @router.get("/message-recipients/teachers")
    async def list_message_recipient_teachers(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """Return the teachers a parent is allowed to message (teachers of
        the parent's children's classes, in the same tenant)."""
        teachers = await _resolve_parent_teacher_recipients(current_user)
        return {"teachers": teachers}

    async def _resolve_admin_recipient(school_id: str) -> Optional[dict]:
        """Deterministically resolve the principal user for a tenant. Prefers
        the earliest-created active school_principal; falls back to the
        earliest-created active school_admin if no principal exists."""
        if not school_id:
            return None
        principals = await gd_find(
            db.session, "users",
            {"tenant_id": school_id, "role": "school_principal", "is_active": True},
            order_by="created_at", desc_order=False, limit=1,
        )
        if principals:
            return principals[0]
        admins = await gd_find(
            db.session, "users",
            {"tenant_id": school_id, "role": "school_admin", "is_active": True},
            order_by="created_at", desc_order=False, limit=1,
        )
        return admins[0] if admins else None

    # ============= QUICK MESSAGE (Communication Center) =============

    @router.post("/quick-message")
    async def send_quick_message(
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        school_id = current_user.get("tenant_id")
        content = data.get("content", "").strip()
        message_type = data.get("message_type", "note")
        recipient_type = data.get("recipient_type", "admin")

        if not content:
            raise HTTPException(status_code=400, detail="محتوى الرسالة مطلوب")

        open_messages = await gd_count(db.session, "messages", {
            "sender_id": parent_id,
            "status": {"$in": ["open", "pending", "sent"]}
        })
        open_excuses = await gd_count(db.session, "absence_excuses", {
            "parent_id": parent_id,
            "status": {"$in": ["pending", "submitted"]}
        })
        open_meetings = await gd_count(db.session, "meeting_requests", {
            "parent_id": parent_id,
            "status": {"$in": ["pending", "submitted"]}
        })
        if (open_messages + open_excuses + open_meetings) >= 3:
            raise HTTPException(status_code=429, detail="لقد وصلت للحد الأقصى من الطلبات المفتوحة (3)")

        receiver = None
        if recipient_type == "admin":
            receiver = await _resolve_admin_recipient(school_id)
            if not receiver:
                raise HTTPException(
                    status_code=503,
                    detail="لا يوجد مسؤول متاح لاستلام الرسالة حالياً"
                )
        elif recipient_type == "teacher":
            requested_uid = (data.get("recipient_user_id") or "").strip()
            if not requested_uid:
                raise HTTPException(status_code=400, detail="المعلم المحدد غير متاح للمراسلة")
            allowed = await _resolve_parent_teacher_recipients(current_user)
            allowed_ids = {r["recipient_user_id"] for r in allowed}
            if requested_uid not in allowed_ids:
                raise HTTPException(status_code=400, detail="المعلم المحدد غير متاح للمراسلة")
            receiver = await gd_find_one(db.session, "users", {
                "id": requested_uid,
                "tenant_id": school_id,
                "role": "teacher",
                "is_active": True,
            })
            if not receiver:
                raise HTTPException(status_code=400, detail="المعلم المحدد غير متاح للمراسلة")
        else:
            raise HTTPException(status_code=400, detail="نوع المستلم غير صالح")

        receiver_id = receiver.get("id", "")
        receiver_name = receiver.get("full_name") or receiver.get("name", "") or ""

        type_labels = {"note": "ملاحظة", "suggestion": "اقتراح", "inquiry": "استفسار"}
        subject = type_labels.get(message_type, "رسالة") + f" من ولي الأمر {current_user.get('full_name', '')}"

        now_iso = datetime.now(timezone.utc).isoformat()
        message = {
            "id": str(uuid.uuid4()),
            "subject": subject,
            "body": content,
            "content": content,
            "sender_id": parent_id,
            "sender_name": current_user.get("full_name"),
            "sender_role": "parent",
            "recipient_id": receiver_id,
            "receiver_id": receiver_id,
            "receiver_name": receiver_name,
            "message_type": message_type,
            "is_read": False,
            "read_status": False,
            "status": "sent",
            "school_id": school_id,
            "created_at": now_iso,
        }
        await gd_insert(db.session, "messages", message)

        if receiver_id:
            await gd_insert(db.session, "notifications", {
                "id": str(uuid.uuid4()),
                "user_id": receiver_id,
                "recipient_id": receiver_id,
                "tenant_id": school_id,
                "type": "message",
                "notification_type": "message",
                "title": f"رسالة جديدة من ولي أمر: {current_user.get('full_name')}",
                "message": subject,
                "is_read": False,
                "read_status": False,
                "created_at": now_iso,
            })

        return {"success": True, "message": "تم استلام رسالتكم، رضاكم محل اهتمامنا"}

    # ============= MESSAGES =============

    @router.get("/messages")
    async def get_parent_messages(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """رسائل ولي الأمر"""
        parent_id = current_user.get("id")
        school_id = current_user.get("tenant_id")

        msg_query = {
            "$or": [
                {"sender_id": parent_id},
                {"receiver_id": parent_id},
                {"recipient_ids": parent_id}
            ]
        }
        if school_id:
            msg_query["school_id"] = school_id
        messages = await gd_find(db.session, "messages", msg_query, order_by="created_at", desc_order=True, limit=50)

        return {
            "messages": [
                {
                    "id": m.get("id"),
                    "subject": m.get("subject"),
                    "content": m.get("content") or m.get("body", ""),
                    "sender_id": m.get("sender_id"),
                    "sender_name": m.get("sender_name"),
                    "sender_type": m.get("sender_type"),
                    "receiver_id": m.get("receiver_id"),
                    "receiver_name": m.get("receiver_name"),
                    "student_name": m.get("student_name"),
                    "type": m.get("type"),
                    "is_sent": m.get("sender_id") == parent_id,
                    "read_status": m.get("read_status", False),
                    "created_at": m.get("created_at")
                }
                for m in messages
            ]
        }

    @router.post("/messages")
    async def send_parent_message(
        receiver_id: str,
        subject: str,
        content: str,
        child_id: Optional[str] = None,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """هذا المسار القديم مغلق — يُرجى استخدام /parent-portal/quick-message"""
        raise HTTPException(
            status_code=410,
            detail="هذا المسار غير متاح. يُرجى استخدام نقطة النهاية المعتمدة /parent-portal/quick-message"
        )

    # ============= CHILD TEACHERS =============

    @router.get("/child/{child_id}/teachers")
    async def get_child_teachers(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """معلمي الابن"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)

        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        school_id = child.get("school_id")
        teachers = []

        if child.get("class_id"):
            timetable = await gd_find_one(db.session, "timetables", {"school_id": school_id, "status": "published"}) or await gd_find_one(db.session, "timetables", {"school_id": school_id},
                sort=[("created_at", -1)])
            if timetable:
                sessions = await gd_find(db.session, "timetable_sessions", {
                        "timetable_id": timetable.get("id"),
                        "class_id": child.get("class_id")
                    }, limit=500)

                teacher_subject_map = {}
                for s in sessions:
                    tid = s.get("teacher_id")
                    sid = s.get("subject_id")
                    if tid:
                        if tid not in teacher_subject_map:
                            teacher_subject_map[tid] = set()
                        if sid:
                            teacher_subject_map[tid].add(sid)

                if teacher_subject_map:
                    sub_ids = list(set(sid for sids in teacher_subject_map.values() for sid in sids))
                    subs = await gd_find(db.session, "subjects", {"id": {"$in": sub_ids}}, limit=100)
                    sub_name_map = {s["id"]: s.get("name_ar", "") for s in subs}

                    teacher_docs = await gd_find(db.session, "teachers", {"id": {"$in": list(teacher_subject_map.keys())}, "school_id": school_id}, limit=100)

                    for t in teacher_docs:
                        tid = t.get("id")
                        subject_names = [sub_name_map.get(sid, "") for sid in teacher_subject_map.get(tid, set()) if sub_name_map.get(sid)]
                        teachers.append({
                            "id": tid,
                            "name": t.get("full_name"),
                            "subjects": subject_names,
                            "email": t.get("email"),
                            "profile_picture": t.get("profile_picture")
                        })

        return {
            "child_name": child.get("full_name"),
            "teachers": teachers
        }

    @router.get("/child/{child_id}/progress-report")
    async def get_child_progress_report(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """تقرير تقدم الطفل الشامل"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        total_attendance = await gd_count(db.session, "attendance", {"student_id": child_id})
        present = await gd_count(db.session, "attendance", {"student_id": child_id, "status": "present"})
        absent = await gd_count(db.session, "attendance", {"student_id": child_id, "status": "absent"})
        late = await gd_count(db.session, "attendance", {"student_id": child_id, "status": "late"})
        # Honest empty: null when no records (was a fake 100%). (Audit 2026-05-10.)
        attendance_rate = round((present / total_attendance * 100), 1) if total_attendance > 0 else None

        grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=500)
        subjects_grades = {}
        for g in grades:
            subj = g.get("subject_name") or g.get("subject_id", "عام")
            if subj not in subjects_grades:
                subjects_grades[subj] = []
            subjects_grades[subj].append(g.get("percentage", 0))

        subject_averages = {}
        for subj, scores in subjects_grades.items():
            subject_averages[subj] = round(sum(scores) / len(scores), 1) if scores else 0

        # Single authoritative overall_average path: arithmetic mean of raw
        # grade percentages (matches /grades and /analytics). The previous
        # mean-of-subject-means produced a different number for the same
        # student. (Audit 2026-05-10.)
        overall_avg = round(sum(g.get("percentage", 0) for g in grades) / len(grades), 1) if grades else None

        behaviour_pos = await gd_count(db.session, "behaviour_records", {"student_id": child_id, "type": "positive"})
        behaviour_neg = await gd_count(db.session, "behaviour_records", {"student_id": child_id, "type": "negative"})
        behaviour_total = behaviour_pos + behaviour_neg

        participation = await gd_find(db.session, "participation_records", {"student_id": child_id}, limit=500)
        total_participation_points = sum(p.get("points", 0) for p in participation)

        return {
            "student": {
                "id": child_id,
                "name": child.get("full_name"),
                "class": child.get("class_name"),
                "grade_level": child.get("grade_level")
            },
            "attendance": {
                "total_days": total_attendance,
                "present": present,
                "absent": absent,
                "late": late,
                "rate": attendance_rate
            },
            "academics": {
                "overall_average": overall_avg,
                "subject_averages": subject_averages,
                "total_assessments": len(grades)
            },
            "behaviour": {
                "positive": behaviour_pos,
                "negative": behaviour_neg,
                "total": behaviour_total,
                "ratio": round(behaviour_pos / max(1, behaviour_total) * 100, 1)
            },
            "participation": {
                "total_records": len(participation),
                "total_points": total_participation_points
            }
        }

    @router.get("/child/{child_id}/behaviour")
    async def get_child_behaviour(
        child_id: str,
        limit: int = 20,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """سجل سلوك الطفل"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        records = await gd_find(db.session, "behaviour_records", {"student_id": child_id}, order_by="created_at", desc_order=True, limit=limit)

        return {"records": records, "total": len(records)}

    # ============= CHILD HOMEWORK =============

    @router.get("/child/{child_id}/homework")
    async def get_child_homework(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        school_id = child.get("school_id")
        class_id = child.get("class_id")
        grade_id = child.get("grade_id") or child.get("grade")

        query = {"school_id": school_id, "is_active": True}
        if class_id:
            query["$or"] = [
                {"class_ids": class_id},
                {"class_id": class_id},
                {"grade_id": grade_id}
            ]

        assignments = await gd_find(db.session, "student_assignments", query, order_by="due_date", desc_order=True, limit=100)

        submissions = await gd_find(db.session, "assignment_submissions", {"student_id": child_id}, limit=500)
        submission_map = {s.get("assignment_id"): s for s in submissions}

        now = datetime.now(timezone.utc)
        result = []
        for a in assignments:
            aid = a.get("id")
            sub = submission_map.get(aid)
            due_str = a.get("due_date")
            try:
                if isinstance(due_str, str):
                    due = datetime.fromisoformat(due_str.replace('Z', '+00:00'))
                else:
                    due = due_str or (now + timedelta(days=7))
            except Exception as e:
                logger.debug(f"Failed to parse due_date '{due_str}': {e}")
                due = now + timedelta(days=7)

            if sub:
                st = "graded" if sub.get("grade") is not None else "submitted"
            elif due < now:
                st = "late"
            else:
                st = "pending"

            result.append({
                "id": aid,
                "title": a.get("title", ""),
                "subject_id": a.get("subject_id"),
                "due_date": due_str,
                "status": st,
                "grade": sub.get("grade") if sub else None,
                "submission_date": sub.get("submitted_at") if sub else None,
            })

        return {
            "child_name": child.get("full_name"),
            "assignments": result,
            "statistics": {
                "pending": len([a for a in result if a["status"] == "pending"]),
                "submitted": len([a for a in result if a["status"] == "submitted"]),
                "graded": len([a for a in result if a["status"] == "graded"]),
                "late": len([a for a in result if a["status"] == "late"])
            }
        }

    @router.get("/settings")
    async def get_parent_settings(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """إعدادات ولي الأمر"""
        settings = await gd_find_one(db.session, "user_preferences", {"user_id": current_user["id"]}) or {}

        return {
            "notification_preferences": settings.get("notification_preferences", {
                "email": True,
                "sms": True,
                "push": True,
                "attendance_alerts": True,
                "grade_alerts": True,
                "behaviour_alerts": True
            }),
            "language": settings.get("language", "ar"),
            "timezone": settings.get("timezone", "Asia/Riyadh")
        }

    @router.put("/settings")
    async def update_parent_settings(
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """تحديث إعدادات ولي الأمر"""
        now = datetime.now(timezone.utc).isoformat()

        await gd_upsert(
            db.session,
            "user_preferences",
            {"user_id": current_user["id"]},
            {**data, "user_id": current_user["id"], "updated_at": now},
        )

        return {"message": "تم تحديث الإعدادات بنجاح"}

    @router.get("/notifications")
    async def get_parent_notifications(
        limit: int = 20,
        unread_only: bool = False,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """إشعارات ولي الأمر"""
        query = {"recipient_id": current_user["id"]}
        if unread_only:
            query["read_status"] = False

        notifications = await gd_find(db.session, "notifications", query, order_by="created_at", desc_order=True, limit=limit)

        unread_count = await gd_count(db.session, "notifications", {"recipient_id": current_user["id"], "read_status": False})

        return {"notifications": notifications, "unread_count": unread_count}

    # ============= REPORTS =============

    @router.get("/reports")
    async def get_parent_reports(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """تقارير ولي الأمر - ملخص لجميع الأبناء"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        students = await _find_children(current_user, parent_phone, school_id)

        reports = []
        for s in students:
            sid = s.get("id")

            total_att = await gd_count(db.session, "attendance", {"student_id": sid})
            present = await gd_count(db.session, "attendance", {"student_id": sid, "status": "present"})
            absent = await gd_count(db.session, "attendance", {"student_id": sid, "status": "absent"})
            late = await gd_count(db.session, "attendance", {"student_id": sid, "status": "late"})
            att_rate = round((present / total_att * 100), 1) if total_att > 0 else 0

            grades = await gd_find(db.session, "grades", {"student_id": sid}, limit=500)
            avg_grade = 0
            if grades:
                avg_grade = round(sum(g.get("percentage", 0) for g in grades) / len(grades), 1)

            behaviour_records = await gd_find(db.session, "behaviour_records", {"student_id": sid}, limit=200)
            positive = sum(1 for b in behaviour_records if b.get("category") in ["positive", "إيجابي"])
            negative = sum(1 for b in behaviour_records if b.get("category") in ["negative", "سلبي"])

            reports.append({
                "student_id": sid,
                "student_name": s.get("full_name", s.get("name", "")),
                "grade": s.get("grade_level", s.get("grade", "")),
                "class_name": s.get("class_name", ""),
                "attendance": {
                    "rate": att_rate,
                    "present": present,
                    "absent": absent,
                    "late": late,
                    "total": total_att
                },
                "academic": {
                    "average_grade": avg_grade,
                    "total_grades": len(grades)
                },
                "behaviour": {
                    "positive": positive,
                    "negative": negative,
                    "total": len(behaviour_records)
                }
            })

        return {"reports": reports, "total": len(reports)}

    # ============= ABSENCE EXCUSES =============

    @router.post("/absence-excuse")
    async def submit_absence_excuse(
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        school_id = current_user.get("tenant_id")

        child_id = data.get("child_id")
        absence_date = data.get("absence_date")
        reason = data.get("reason", "").strip()

        if not child_id or not absence_date or not reason:
            raise HTTPException(status_code=400, detail="child_id, absence_date, and reason are required")

        open_total = (
            await gd_count(db.session, "messages", {"sender_id": parent_id, "status": {"$in": ["open", "pending", "sent"]}})
            + await gd_count(db.session, "absence_excuses", {"parent_id": parent_id, "status": {"$in": ["pending", "submitted"]}})
            + await gd_count(db.session, "meeting_requests", {"parent_id": parent_id, "status": {"$in": ["pending", "submitted"]}})
        )
        if open_total >= 3:
            raise HTTPException(status_code=429, detail="لقد وصلت للحد الأقصى من الطلبات المفتوحة (3)")

        children = await _find_children(current_user, current_user.get("phone"), school_id)
        child_ids = [c.get("id") for c in children]
        if child_id not in child_ids:
            raise HTTPException(status_code=403, detail="Child not linked to this parent")

        child = next((c for c in children if c.get("id") == child_id), {})

        excuse = {
            "id": str(uuid.uuid4()),
            "parent_id": parent_id,
            "parent_name": current_user.get("full_name", ""),
            "child_id": child_id,
            "child_name": child.get("full_name", child.get("name", "")),
            "school_id": school_id,
            "absence_date": absence_date,
            "reason": reason,
            "attachment_url": data.get("attachment_url"),
            "attachment_name": data.get("attachment_name"),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(db.session, "absence_excuses", excuse)
        excuse.pop("_id", None)
        return {"message": "تم إرسال العذر بنجاح", "excuse": excuse}

    @router.post("/upload-attachment")
    async def upload_attachment(
        file: UploadFile = File(...),
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        import base64
        MAX_SIZE = 5 * 1024 * 1024
        ALLOWED_TYPES = {
            "image/jpeg", "image/png", "image/gif", "image/webp",
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }

        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail="صيغة الملف غير مدعومة")

        content = await file.read()
        if len(content) > MAX_SIZE:
            raise HTTPException(status_code=400, detail="حجم الملف يتجاوز الحد المسموح (5 ميغابايت)")

        encoded = base64.b64encode(content).decode('utf-8')
        data_url = f"data:{file.content_type};base64,{encoded}"

        return {
            "success": True,
            "attachment_url": data_url,
            "attachment_name": file.filename,
        }

    @router.get("/absence-excuses")
    async def get_absence_excuses(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        excuses = await gd_find(db.session, "absence_excuses", {"parent_id": parent_id}, order_by="created_at", desc_order=True, limit=100)
        return {"excuses": excuses, "total": len(excuses)}

    # ============= MEETING REQUESTS =============

    @router.post("/meeting-request")
    async def submit_meeting_request(
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        school_id = current_user.get("tenant_id")

        preferred_date = data.get("preferred_date")
        preferred_time = data.get("preferred_time")
        topic = data.get("topic", "").strip()
        contact_preference = data.get("contact_preference", "in_person")

        if not preferred_date or not topic:
            raise HTTPException(status_code=400, detail="preferred_date and topic are required")

        open_total = (
            await gd_count(db.session, "messages", {"sender_id": parent_id, "status": {"$in": ["open", "pending", "sent"]}})
            + await gd_count(db.session, "absence_excuses", {"parent_id": parent_id, "status": {"$in": ["pending", "submitted"]}})
            + await gd_count(db.session, "meeting_requests", {"parent_id": parent_id, "status": {"$in": ["pending", "submitted"]}})
        )
        if open_total >= 3:
            raise HTTPException(status_code=429, detail="لقد وصلت للحد الأقصى من الطلبات المفتوحة (3)")

        meeting = {
            "id": str(uuid.uuid4()),
            "parent_id": parent_id,
            "parent_name": current_user.get("full_name", ""),
            "parent_phone": current_user.get("phone", ""),
            "parent_email": current_user.get("email", ""),
            "school_id": school_id,
            "preferred_date": preferred_date,
            "preferred_time": preferred_time or "",
            "topic": topic,
            "details": data.get("details", "").strip(),
            "contact_preference": contact_preference,
            "status": "pending",
            "admin_notes": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(db.session, "meeting_requests", meeting)
        meeting.pop("_id", None)
        return {"message": "تم إرسال طلب الاجتماع بنجاح", "meeting": meeting}

    @router.get("/meeting-requests")
    async def get_meeting_requests(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        meetings = await gd_find(db.session, "meeting_requests", {"parent_id": parent_id}, order_by="created_at", desc_order=True, limit=100)
        return {"meetings": meetings, "total": len(meetings)}

    return router
