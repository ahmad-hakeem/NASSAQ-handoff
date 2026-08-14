"""
NASSAQ - Teacher Attendance Routes
Teacher attendance management endpoints (for Principal use)
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List, Literal
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid

# Canonical attendance status set — kept in sync with
# `backend/models/enums.py::AttendanceStatus`. Pydantic Literal here is the
# request-level boundary that rejects anything other than these four values
# with a 422 (safe Arabic message via FastAPI default), so unknown statuses
# never reach the persistence layer.
AttendanceStatusLiteral = Literal["present", "absent", "late", "excused"]
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct

import logging

logger = logging.getLogger("nassaq.teacher_attendance_routes")


# Maximum number of history entries kept per attendance row.
# Three is enough to surface "ألغاه/سجَّله" along with the prior state without
# bloating the document or the grid response.
MAX_HISTORY_ENTRIES = 3


class TeacherAttendanceRecord(BaseModel):
    teacher_id: str
    date: str
    status: AttendanceStatusLiteral  # present | absent | late | excused
    check_in_time: Optional[str] = None
    notes: Optional[str] = None
    subject_type: Optional[str] = "teacher"  # "teacher" or "admin"


class BulkTeacherAttendance(BaseModel):
    records: List[TeacherAttendanceRecord]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _classify_action(prev_status: Optional[str], new_status: str) -> str:
    """Return 'undone' when an existing absence is being cleared, else 'recorded'.

    The task asks us to surface "ألغاه" (undo) separately from "سجَّله"
    (record). Anything moving away from 'absent' counts as an undo so the audit
    trail captures the principal who flipped the record back.
    """
    if prev_status == "absent" and new_status != "absent":
        return "undone"
    return "recorded"


async def _resolve_user_name(db, user_id: Optional[str]) -> str:
    """Look up a display name for a user id; return '' if unknown."""
    if not user_id:
        return ""
    try:
        user = await gd_find_one(db.session, "users", {"id": user_id})
    except Exception:
        return ""
    if not user:
        return ""
    return user.get("full_name") or user.get("name") or user.get("email") or ""


def create_teacher_attendance_routes(db, get_current_user, require_roles, UserRole):
    """Create teacher attendance router"""
    from src.common.utils.avatar_serving import signed_image_url

    router = APIRouter(prefix="/teacher-attendance", tags=["Teacher Attendance"])
    
    @router.get("/school-admins")
    async def list_school_admins(
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.SCHOOL_ADMIN,
            UserRole.PLATFORM_ADMIN,
        ]))
    ):
        """List school-admin staff for the current tenant."""
        school_id = current_user.get("tenant_id")
        if not school_id and current_user.get("role") != "platform_admin":
            raise HTTPException(status_code=403, detail="No school association")

        query = {
            "role": {"$in": ["school_principal", "school_admin", "school_sub_admin"]},
        }
        if school_id:
            query["tenant_id"] = school_id

        users = await gd_find(db.session, "users", query, limit=500)

        def _label(u):
            return (u.get("full_name") or u.get("name") or u.get("email") or "").strip()

        users = sorted(users, key=_label)

        ROLE_LABEL_AR = {
            "school_principal": "مدير المدرسة",
            "school_admin": "مدير شؤون مدرسية",
            "school_sub_admin": "مساعد إداري",
        }

        result = []
        for u in users:
            if u.get("is_active") is False:
                continue
            role = u.get("role")
            result.append({
                "id": u.get("id"),
                "full_name": _label(u),
                "email": u.get("email"),
                "phone": u.get("phone"),
                "specialization": ROLE_LABEL_AR.get(role, role or ""),
                "role": role,
                "avatar_url": signed_image_url("avatar", u.get("id"), u.get("avatar_url")),
                "school_id": u.get("tenant_id"),
                "is_active": u.get("is_active", True),
            })
        return result

    @router.get("")
    async def get_teacher_attendance(
        date: str,
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.SCHOOL_ADMIN,
            UserRole.PLATFORM_ADMIN,
        ]))
    ):
        """Get teacher attendance for a specific date.

        Each row is enriched with `recorded_by_name` so the UI can show
        "سجَّله: …" without an extra round-trip per teacher.
        """
        # Get school_id from user's tenant
        school_id = current_user.get("tenant_id")
        if not school_id and current_user["role"] != "platform_admin":
            raise HTTPException(status_code=403, detail="No school association")
        
        query = {"date": date}
        if school_id:
            query["school_id"] = school_id
        
        records = await gd_find(db.session, "teacher_attendance", query, limit=1000)

        # Batch-resolve recorder names so the UI can render "سجَّله: …" inline.
        recorder_ids = {r.get("recorded_by") for r in records if r.get("recorded_by")}
        name_map: dict[str, str] = {}
        if recorder_ids:
            try:
                users = await gd_find(
                    db.session, "users", {"id": {"$in": list(recorder_ids)}},
                    limit=len(recorder_ids),
                )
                for u in users:
                    uid = u.get("id")
                    if uid:
                        name_map[uid] = (
                            u.get("full_name") or u.get("name") or u.get("email") or ""
                        )
            except Exception:
                # Best-effort enrichment only — leave the name map empty so
                # rows still serialize, just without `recorded_by_name`.
                name_map = {}

        for r in records:
            rid = r.get("recorded_by")
            if rid and not r.get("recorded_by_name"):
                r["recorded_by_name"] = name_map.get(rid, "")
        return records
    
    @router.post("/bulk")
    async def save_bulk_teacher_attendance(
        data: BulkTeacherAttendance,
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Save bulk teacher attendance records.

        Each save is appended to a per-row `history` list (capped at the last
        ``MAX_HISTORY_ENTRIES`` entries) with the actor and timestamp, plus an
        action tag of either ``recorded`` or ``undone``. This lets the UI show
        who marked a teacher absent and who later cleared the record.
        """
        school_id = current_user.get("tenant_id")
        if not school_id and current_user["role"] != "platform_admin":
            raise HTTPException(status_code=403, detail="No school association")

        actor_id = current_user.get("id")
        actor_name = (
            current_user.get("full_name")
            or current_user.get("name")
            or current_user.get("email")
            or ""
        )
        now_iso = _now_iso()

        saved_count = 0
        updated_count = 0

        for record in data.records:
            # Check if record already exists
            existing = await gd_find_one(db.session, "teacher_attendance", {
                "teacher_id": record.teacher_id,
                "date": record.date,
                "school_id": school_id
            })

            prev_status = existing.get("status") if existing else None
            action = _classify_action(prev_status, record.status)
            history_entry = {
                "status": record.status,
                "action": action,
                "actor_id": actor_id,
                "actor_name": actor_name,
                "at": now_iso,
            }

            existing_history = (existing.get("history") if existing else None) or []
            new_history = ([history_entry] + list(existing_history))[:MAX_HISTORY_ENTRIES]

            subject_type = (
                record.subject_type
                or (existing.get("subject_type") if existing else None)
                or "teacher"
            )

            attendance_doc = {
                "teacher_id": record.teacher_id,
                "date": record.date,
                "status": record.status,
                "check_in_time": record.check_in_time,
                "notes": record.notes,
                "school_id": school_id,
                "subject_type": subject_type,
                "recorded_by": actor_id,
                "recorded_by_name": actor_name,
                "recorded_at": now_iso,
                "history": new_history,
                "updated_at": now_iso,
            }

            if existing:
                existing_id = existing.get("id") or existing.get("_id")
                if not existing_id:
                    # Defensive: if we somehow can't identify the existing row,
                    # fall back to the full natural key so we never update a random row.
                    update_filter = {
                        "teacher_id": record.teacher_id,
                        "date": record.date,
                        "school_id": school_id,
                    }
                else:
                    update_filter = {"id": existing_id}
                await gd_update_one(db.session, "teacher_attendance", update_filter, attendance_doc)
                updated_count += 1
            else:
                attendance_doc["id"] = str(uuid.uuid4())
                attendance_doc["created_at"] = now_iso
                await gd_insert(db.session, "teacher_attendance", attendance_doc)
                saved_count += 1

        return {
            "message": "تم حفظ الحضور بنجاح",
            "saved": saved_count,
            "updated": updated_count
        }

    @router.get("/history")
    async def get_teacher_attendance_history_for_day(
        teacher_id: str = Query(..., description="معرف المعلم"),
        date: str = Query(..., description="التاريخ بصيغة YYYY-MM-DD"),
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.SCHOOL_ADMIN,
            UserRole.PLATFORM_ADMIN,
        ])),
    ):
        """Return the most recent changes for one teacher on one day.

        The list is already capped at ``MAX_HISTORY_ENTRIES`` on save, so this
        endpoint is a lightweight read used by the attendance page popover.
        """
        school_id = current_user.get("tenant_id")
        if not school_id and current_user["role"] != "platform_admin":
            raise HTTPException(status_code=403, detail="No school association")

        query = {"teacher_id": teacher_id, "date": date}
        if school_id:
            query["school_id"] = school_id

        record = await gd_find_one(db.session, "teacher_attendance", query)
        if not record:
            return {
                "teacher_id": teacher_id,
                "date": date,
                "status": None,
                "history": [],
            }

        history = list(record.get("history") or [])
        # Defensive: if the row predates the history feature, synthesize a
        # single entry from `recorded_by` so the UI still has something to show.
        if not history and record.get("recorded_by"):
            actor_name = record.get("recorded_by_name") or await _resolve_user_name(
                db, record.get("recorded_by")
            )
            history = [{
                "status": record.get("status"),
                "action": "recorded",
                "actor_id": record.get("recorded_by"),
                "actor_name": actor_name,
                "at": record.get("recorded_at") or record.get("updated_at") or record.get("created_at"),
            }]

        return {
            "teacher_id": teacher_id,
            "date": date,
            "status": record.get("status"),
            "recorded_by": record.get("recorded_by"),
            "recorded_by_name": record.get("recorded_by_name") or "",
            "recorded_at": record.get("recorded_at") or record.get("updated_at"),
            "history": history[:MAX_HISTORY_ENTRIES],
        }

    @router.get("/report/summary")
    async def get_teacher_attendance_summary(
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.SCHOOL_ADMIN,
            UserRole.PLATFORM_ADMIN,
            UserRole.TEACHER,
        ]))
    ):
        """Get teacher attendance summary report"""
        school_id = current_user.get("tenant_id")
        if not school_id and current_user["role"] != "platform_admin":
            raise HTTPException(status_code=403, detail="No school association")

        query = {}
        if school_id:
            query["school_id"] = school_id

        # Teachers may only see their own attendance records.
        if current_user["role"] == UserRole.TEACHER.value:
            teacher_id = current_user.get("teacher_id")
            if not teacher_id:
                raise HTTPException(status_code=403, detail="لا يوجد سجل معلم مرتبط بهذا الحساب")
            query["teacher_id"] = teacher_id

        # Get all records for this school (or this teacher only)
        all_records = await gd_find(db.session, "teacher_attendance", query, limit=10000)
        
        # Calculate stats
        present = sum(1 for r in all_records if r.get("status") == "present")
        absent = sum(1 for r in all_records if r.get("status") == "absent")
        late = sum(1 for r in all_records if r.get("status") == "late")
        excused = sum(1 for r in all_records if r.get("status") == "excused")
        total = len(all_records)
        
        attendance_rate = 0
        if total > 0:
            attendance_rate = round((present + late) / total * 100, 1)
        
        # Group by date for daily trend
        daily_stats = {}
        for record in all_records:
            date = record.get("date", "unknown")
            if date not in daily_stats:
                daily_stats[date] = {"present": 0, "absent": 0, "late": 0, "excused": 0, "total": 0}
            daily_stats[date][record.get("status", "present")] += 1
            daily_stats[date]["total"] += 1
        
        daily = []
        for date, stats in sorted(daily_stats.items(), reverse=True)[:30]:
            rate = 0
            if stats["total"] > 0:
                rate = round((stats["present"] + stats["late"]) / stats["total"] * 100, 1)
            daily.append({
                "date": date,
                "present": stats["present"],
                "absent": stats["absent"],
                "late": stats["late"],
                "excused": stats["excused"],
                "total": stats["total"],
                "attendance_rate": rate
            })
        
        return {
            "overall": {
                "attendance_rate": attendance_rate,
                "total_records": total,
                "present": present,
                "absent": absent,
                "late": late,
                "excused": excused
            },
            "daily": daily
        }
    
    @router.get("/teacher/{teacher_id}")
    async def get_teacher_attendance_history(
        teacher_id: str,
        current_user: dict = Depends(require_roles([
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.SCHOOL_ADMIN,
            UserRole.PLATFORM_ADMIN,
        ]))
    ):
        """Get attendance history for a specific teacher"""
        school_id = current_user.get("tenant_id")
        
        query = {"teacher_id": teacher_id}
        if school_id:
            query["school_id"] = school_id
        
        records = await gd_find(db.session, "teacher_attendance", query, order_by="date", desc_order=True, limit=100)
        
        # Calculate stats
        present = sum(1 for r in records if r.get("status") == "present")
        absent = sum(1 for r in records if r.get("status") == "absent")
        late = sum(1 for r in records if r.get("status") == "late")
        total = len(records)
        
        attendance_rate = 0
        if total > 0:
            attendance_rate = round((present + late) / total * 100, 1)
        
        return {
            "teacher_id": teacher_id,
            "total_days": total,
            "present": present,
            "absent": absent,
            "late": late,
            "attendance_rate": attendance_rate,
            "records": records[:30]  # Last 30 records
        }
    
    return router
