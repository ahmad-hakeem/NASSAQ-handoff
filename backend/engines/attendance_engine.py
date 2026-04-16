"""
NASSAQ Attendance Engine
محرك الحضور والغياب لمنصة نَسَّق
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, date, timedelta
from collections import defaultdict
from enum import Enum
import uuid

from sqlalchemy import select, func, and_

from engines.sql_utils import (
    model_to_dict, models_to_dicts, apply_updates,
    gd_find, gd_find_one, gd_insert, gd_update_one, gd_count,
    gd_insert_many,
)


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"
    LEFT_EARLY = "left_early"
    PENDING_VERIFICATION = "pending_verification"


class ExcuseType(str, Enum):
    MEDICAL = "medical"
    FAMILY = "family"
    OFFICIAL = "official"
    OTHER = "other"


class AttendanceEngine:
    def __init__(self, db):
        self.db = db

    @property
    def session(self):
        return self.db.session

    async def record_attendance(
        self,
        tenant_id: str,
        student_id: str,
        section_id: str,
        attendance_date: str,
        status: str,
        recorded_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        from pg_models import Attendance
        now = datetime.now(timezone.utc).isoformat()

        stmt = select(Attendance).where(
            Attendance.school_id == tenant_id,
            Attendance.student_id == student_id,
            Attendance.date == attendance_date
        ).limit(1)
        result = await self.session.execute(stmt)
        existing = result.scalars().first()

        if existing:
            old_status = existing.status
            existing.status = status
            existing.updated_at = datetime.now(timezone.utc)
            if kwargs.get("notes"):
                existing.notes = kwargs["notes"]

            extra = {}
            if kwargs.get("arrival_time"):
                extra["arrival_time"] = kwargs["arrival_time"]
            if kwargs.get("departure_time"):
                extra["departure_time"] = kwargs["departure_time"]
            if extra and hasattr(existing, "data"):
                current_data = dict(existing.data) if existing.data else {}
                current_data.update(extra)
                existing.data = current_data

            await self.session.flush()
            d = model_to_dict(existing)
            d["old_status"] = old_status
            d["tenant_id"] = d.get("school_id")
            d["section_id"] = d.get("class_id")
            d["attendance_date"] = attendance_date
            return d

        attendance_id = str(uuid.uuid4())
        att_obj = Attendance(
            id=attendance_id,
            school_id=tenant_id,
            student_id=student_id,
            class_id=section_id,
            date=attendance_date,
            status=status,
            recorded_by=recorded_by,
            notes=kwargs.get("notes"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        extra_data = {}
        if kwargs.get("arrival_time"):
            extra_data["arrival_time"] = kwargs["arrival_time"]
        if kwargs.get("departure_time"):
            extra_data["departure_time"] = kwargs["departure_time"]
        if kwargs.get("session_id"):
            att_obj.session_id = kwargs["session_id"]
        if kwargs.get("period"):
            extra_data["period"] = kwargs["period"]
        if extra_data and hasattr(att_obj, "data"):
            att_obj.data = extra_data

        self.session.add(att_obj)
        await self.session.flush()

        d = model_to_dict(att_obj)
        d["tenant_id"] = tenant_id
        d["section_id"] = section_id
        d["attendance_date"] = attendance_date
        return d

    async def record_bulk_attendance(
        self,
        tenant_id: str,
        section_id: str,
        attendance_date: str,
        attendance_records: List[Dict[str, Any]],
        recorded_by: str
    ) -> Dict[str, Any]:
        from pg_models import Attendance
        results = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "errors": [],
            "transitions": []
        }
        now = datetime.now(timezone.utc)

        valid_records = []
        for record in attendance_records:
            sid = record.get("student_id")
            if not sid:
                results["errors"].append({"error": "معرف الطالب مفقود"})
                continue
            valid_records.append(record)

        if not valid_records:
            return results

        student_ids = [r["student_id"] for r in valid_records]
        stmt = select(Attendance).where(
            Attendance.school_id == tenant_id,
            Attendance.class_id == section_id,
            Attendance.date == attendance_date,
            Attendance.student_id.in_(student_ids),
        )
        result = await self.session.execute(stmt)
        existing_objs = result.scalars().all()
        existing_map = {obj.student_id: obj for obj in existing_objs}

        for record in valid_records:
            try:
                student_id = record["student_id"]
                status = record.get("status", AttendanceStatus.PRESENT.value)
                existing = existing_map.get(student_id)

                if existing:
                    old_status = existing.status
                    existing.status = status
                    existing.updated_at = now
                    existing.recorded_by = recorded_by
                    results["updated"] += 1
                    results["transitions"].append({
                        "student_id": student_id,
                        "old_status": old_status,
                        "new_status": status,
                    })
                else:
                    att_obj = Attendance(
                        id=str(uuid.uuid4()),
                        school_id=tenant_id,
                        student_id=student_id,
                        class_id=section_id,
                        date=attendance_date,
                        status=status,
                        recorded_by=recorded_by,
                        notes=record.get("notes"),
                        created_at=now,
                        updated_at=now,
                    )
                    if record.get("session_id") and hasattr(att_obj, "session_id"):
                        att_obj.session_id = record["session_id"]
                    self.session.add(att_obj)
                    results["created"] += 1
                    results["transitions"].append({
                        "student_id": student_id,
                        "old_status": None,
                        "new_status": status,
                    })
                results["processed"] += 1
            except Exception as e:
                results["errors"].append({
                    "student_id": record.get("student_id"),
                    "error": str(e),
                })

        await self.session.flush()
        return results

    async def create_bulk_class_attendance(
        self,
        tenant_id: str,
        class_id: str,
        date_str: str,
        time_slot_id: str,
        subject_id: Optional[str],
        records: List[Dict[str, Any]],
        recorded_by: str,
    ) -> Dict[str, Any]:
        from pg_models import Attendance, Class, Student
        now = datetime.now(timezone.utc)
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc) if isinstance(date_str, str) else date_str

        stmt = select(Class).where(Class.id == class_id, Class.school_id == tenant_id).limit(1)
        result = await self.session.execute(stmt)
        class_doc = result.scalars().first()
        if not class_doc:
            raise ValueError(f"Class {class_id} not found or does not belong to tenant")

        seen: set = set()
        deduped = []
        for r in records:
            sid = r.get("student_id")
            if sid and sid not in seen:
                seen.add(sid)
                deduped.append(r)

        student_ids = list(seen)

        stmt = select(Student.id).where(Student.id.in_(student_ids), Student.school_id == tenant_id)
        result = await self.session.execute(stmt)
        valid_student_set = {row[0] for row in result.all()}
        deduped = [r for r in deduped if r.get("student_id") in valid_student_set]
        student_ids = [r["student_id"] for r in deduped]

        stmt = select(Attendance).where(
            Attendance.class_id == class_id,
            Attendance.date == parsed_date,
            Attendance.school_id == tenant_id,
            Attendance.student_id.in_(student_ids),
        )
        result = await self.session.execute(stmt)
        existing_objs = result.scalars().all()
        existing_map = {obj.student_id: obj for obj in existing_objs}

        created = 0
        updated = 0
        errors: List[Dict] = []
        transitions: List[Dict] = []
        absent_late: List[tuple] = []

        for record in deduped:
            try:
                student_id = record.get("student_id")
                att_status = record.get("status", "present")
                notes = record.get("notes")

                existing = existing_map.get(student_id)
                if existing:
                    old_status = existing.status
                    existing.status = att_status
                    existing.notes = notes
                    existing.recorded_by = recorded_by
                    existing.updated_at = now
                    updated += 1
                    transitions.append({"student_id": student_id, "old_status": old_status, "new_status": att_status})
                else:
                    att_obj = Attendance(
                        id=str(uuid.uuid4()),
                        student_id=student_id,
                        class_id=class_id,
                        date=parsed_date,
                        status=att_status,
                        notes=notes,
                        recorded_by=recorded_by,
                        school_id=tenant_id,
                        created_at=now,
                        updated_at=now,
                    )
                    if hasattr(att_obj, "session_id"):
                        att_obj.session_id = None
                    extra = {}
                    if subject_id:
                        extra["subject_id"] = subject_id
                    if time_slot_id:
                        extra["time_slot_id"] = time_slot_id
                    extra["teacher_id"] = recorded_by
                    if extra and hasattr(att_obj, "data"):
                        att_obj.data = extra
                    self.session.add(att_obj)
                    transitions.append({"student_id": student_id, "old_status": None, "new_status": att_status})
                    created += 1

                    if att_status in ("absent", "late"):
                        await gd_insert(self.session, "events", {
                            "id": str(uuid.uuid4()),
                            "type": f"student_{att_status}",
                            "student_id": student_id,
                            "class_id": class_id,
                            "date": date_str,
                            "recorded_by": recorded_by,
                            "created_at": now.isoformat(),
                            "tenant_id": tenant_id,
                        })
                        absent_late.append((student_id, att_status))
            except Exception as e:
                errors.append({"student_id": record.get("student_id"), "error": str(e)})

        await self.session.flush()

        return {
            "created": created,
            "updated": updated,
            "errors": errors,
            "transitions": transitions,
            "absent_late": absent_late,
            "total_records": len(records),
        }

    async def mark_class_present(
        self,
        tenant_id: str,
        section_id: str,
        attendance_date: str,
        recorded_by: str,
        student_ids: List[str]
    ) -> Dict[str, Any]:
        records = [
            {"student_id": sid, "status": AttendanceStatus.PRESENT.value}
            for sid in student_ids
        ]

        return await self.record_bulk_attendance(
            tenant_id=tenant_id,
            section_id=section_id,
            attendance_date=attendance_date,
            attendance_records=records,
            recorded_by=recorded_by
        )

    async def get_student_attendance(
        self,
        tenant_id: str,
        student_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        from pg_models import Attendance
        conditions = [
            Attendance.school_id == tenant_id,
            Attendance.student_id == student_id
        ]

        if start_date:
            conditions.append(Attendance.date >= start_date)
        if end_date:
            conditions.append(Attendance.date <= end_date)
        if status:
            conditions.append(Attendance.status == status)

        stmt = select(Attendance).where(*conditions).order_by(Attendance.date.desc()).limit(1000)
        result = await self.session.execute(stmt)
        return [self._att_to_dict(a) for a in result.scalars().all()]

    async def get_section_attendance(
        self,
        tenant_id: str,
        section_id: str,
        attendance_date: str
    ) -> List[Dict[str, Any]]:
        from pg_models import Attendance
        stmt = select(Attendance).where(
            Attendance.school_id == tenant_id,
            Attendance.class_id == section_id,
            Attendance.date == attendance_date
        ).limit(1000)
        result = await self.session.execute(stmt)
        return [self._att_to_dict(a) for a in result.scalars().all()]

    async def get_daily_attendance_report(
        self,
        tenant_id: str,
        attendance_date: str,
        section_id: Optional[str] = None
    ) -> Dict[str, Any]:
        from pg_models import Attendance
        conditions = [Attendance.school_id == tenant_id, Attendance.date == attendance_date]
        if section_id:
            conditions.append(Attendance.class_id == section_id)

        base = and_(*conditions)

        total_stmt = select(func.count(Attendance.id)).where(base)
        present_stmt = select(func.count(Attendance.id)).where(base, Attendance.status == AttendanceStatus.PRESENT.value)
        absent_stmt = select(func.count(Attendance.id)).where(base, Attendance.status == AttendanceStatus.ABSENT.value)
        late_stmt = select(func.count(Attendance.id)).where(base, Attendance.status == AttendanceStatus.LATE.value)
        excused_stmt = select(func.count(Attendance.id)).where(base, Attendance.status == AttendanceStatus.EXCUSED.value)
        left_early_stmt = select(func.count(Attendance.id)).where(base, Attendance.status == AttendanceStatus.LEFT_EARLY.value)

        total = (await self.session.execute(total_stmt)).scalar() or 0
        present = (await self.session.execute(present_stmt)).scalar() or 0
        absent = (await self.session.execute(absent_stmt)).scalar() or 0
        late = (await self.session.execute(late_stmt)).scalar() or 0
        excused = (await self.session.execute(excused_stmt)).scalar() or 0
        left_early = (await self.session.execute(left_early_stmt)).scalar() or 0

        stmt = select(Attendance).where(base).limit(max(total, 1))
        result = await self.session.execute(stmt)
        records = [self._att_to_dict(a) for a in result.scalars().all()]

        return {
            "date": attendance_date,
            "tenant_id": tenant_id,
            "section_id": section_id,
            "total_students": total,
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "left_early": left_early,
            "attendance_rate": round((present / total * 100) if total > 0 else 0, 2),
            "records": records
        }

    async def get_student_attendance_summary(
        self,
        tenant_id: str,
        student_id: str,
        academic_year: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        from pg_models import Attendance
        conditions = [Attendance.school_id == tenant_id, Attendance.student_id == student_id]
        if start_date:
            conditions.append(Attendance.date >= start_date)
        if end_date:
            conditions.append(Attendance.date <= end_date)

        base = and_(*conditions)

        total = (await self.session.execute(select(func.count(Attendance.id)).where(base))).scalar() or 0
        present = (await self.session.execute(select(func.count(Attendance.id)).where(base, Attendance.status == AttendanceStatus.PRESENT.value))).scalar() or 0
        absent = (await self.session.execute(select(func.count(Attendance.id)).where(base, Attendance.status == AttendanceStatus.ABSENT.value))).scalar() or 0
        late = (await self.session.execute(select(func.count(Attendance.id)).where(base, Attendance.status == AttendanceStatus.LATE.value))).scalar() or 0
        excused = (await self.session.execute(select(func.count(Attendance.id)).where(base, Attendance.status == AttendanceStatus.EXCUSED.value))).scalar() or 0
        left_early = (await self.session.execute(select(func.count(Attendance.id)).where(base, Attendance.status == AttendanceStatus.LEFT_EARLY.value))).scalar() or 0

        return {
            "student_id": student_id,
            "total_days": total,
            "present_days": present,
            "absent_days": absent,
            "late_days": late,
            "excused_days": excused,
            "left_early_days": left_early,
            "attendance_rate": round((present / total * 100) if total > 0 else 100, 2),
            "absence_rate": round((absent / total * 100) if total > 0 else 0, 2),
            "late_rate": round((late / total * 100) if total > 0 else 0, 2)
        }

    async def get_section_attendance_summary(
        self,
        tenant_id: str,
        section_id: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        from pg_models import Attendance
        stmt = select(Attendance).where(
            Attendance.school_id == tenant_id,
            Attendance.class_id == section_id,
            Attendance.date >= start_date,
            Attendance.date <= end_date
        ).limit(5000)
        result = await self.session.execute(stmt)
        all_records = result.scalars().all()

        by_student: Dict[str, Dict] = {}
        total_records = 0
        total_present = 0
        for rec in all_records:
            sid = rec.student_id
            if sid not in by_student:
                by_student[sid] = {"total": 0, "present": 0, "absent": 0, "late": 0, "excused": 0}
            by_student[sid]["total"] += 1
            total_records += 1
            if rec.status == AttendanceStatus.PRESENT.value:
                by_student[sid]["present"] += 1
                total_present += 1
            elif rec.status == AttendanceStatus.ABSENT.value:
                by_student[sid]["absent"] += 1
            elif rec.status == AttendanceStatus.LATE.value:
                by_student[sid]["late"] += 1
            elif rec.status == AttendanceStatus.EXCUSED.value:
                by_student[sid]["excused"] += 1

        student_stats = []
        for sid, data in by_student.items():
            t = data["total"]
            p = data["present"]
            student_stats.append({
                "student_id": sid,
                "total": t,
                "present": p,
                "absent": data["absent"],
                "late": data["late"],
                "excused": data["excused"],
                "attendance_rate": round((p / t * 100) if t > 0 else 100, 2),
            })

        return {
            "section_id": section_id,
            "start_date": start_date,
            "end_date": end_date,
            "total_records": total_records,
            "overall_attendance_rate": round((total_present / total_records * 100) if total_records > 0 else 0, 2),
            "students": student_stats
        }

    async def get_tenant_attendance_overview(
        self,
        tenant_id: str,
        attendance_date: str
    ) -> Dict[str, Any]:
        from pg_models import Attendance
        conditions = [Attendance.school_id == tenant_id, Attendance.date == attendance_date]
        base = and_(*conditions)

        total = (await self.session.execute(select(func.count(Attendance.id)).where(base))).scalar() or 0
        present = (await self.session.execute(select(func.count(Attendance.id)).where(base, Attendance.status == AttendanceStatus.PRESENT.value))).scalar() or 0
        absent = (await self.session.execute(select(func.count(Attendance.id)).where(base, Attendance.status == AttendanceStatus.ABSENT.value))).scalar() or 0
        late = (await self.session.execute(select(func.count(Attendance.id)).where(base, Attendance.status == AttendanceStatus.LATE.value))).scalar() or 0

        stmt = select(Attendance).where(base).limit(5000)
        result = await self.session.execute(stmt)
        all_records = result.scalars().all()

        section_data: Dict[str, Dict] = {}
        for rec in all_records:
            cid = rec.class_id or "unknown"
            if cid not in section_data:
                section_data[cid] = {"total": 0, "present": 0, "absent": 0}
            section_data[cid]["total"] += 1
            if rec.status == AttendanceStatus.PRESENT.value:
                section_data[cid]["present"] += 1
            elif rec.status == AttendanceStatus.ABSENT.value:
                section_data[cid]["absent"] += 1

        sections = [
            {"section_id": cid, "total": d["total"], "present": d["present"], "absent": d["absent"]}
            for cid, d in section_data.items()
        ]

        return {
            "tenant_id": tenant_id,
            "date": attendance_date,
            "total_students": total,
            "present": present,
            "absent": absent,
            "late": late,
            "attendance_rate": round((present / total * 100) if total > 0 else 0, 2),
            "sections_count": len(sections),
            "sections": sections
        }

    async def create_excuse(
        self,
        tenant_id: str,
        student_id: str,
        excuse_type: str,
        start_date: str,
        end_date: str,
        reason: str,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        excuse_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        excuse_doc = {
            "id": excuse_id,
            "tenant_id": tenant_id,
            "student_id": student_id,
            "excuse_type": excuse_type,
            "start_date": start_date,
            "end_date": end_date,
            "reason": reason,
            "attachment_url": kwargs.get("attachment_url"),
            "is_approved": False,
            "created_at": now,
            "created_by": created_by
        }

        await gd_insert(self.session, "attendance_excuses", excuse_doc)
        return excuse_doc

    async def approve_excuse(
        self,
        excuse_id: str,
        approved_by: str,
        apply_to_attendance: bool = True
    ) -> Dict[str, Any]:
        from pg_models import Attendance
        now = datetime.now(timezone.utc)

        excuse = await gd_find_one(self.session, "attendance_excuses", {"id": excuse_id})
        if not excuse:
            raise ValueError("العذر غير موجود")

        await gd_update_one(self.session, "attendance_excuses", {"id": excuse_id}, {
            "is_approved": True,
            "approved_at": now.isoformat(),
            "approved_by": approved_by
        })

        if apply_to_attendance:
            stmt = select(Attendance).where(
                Attendance.school_id == excuse.get("tenant_id"),
                Attendance.student_id == excuse.get("student_id"),
                Attendance.date >= excuse.get("start_date"),
                Attendance.date <= excuse.get("end_date"),
                Attendance.status == AttendanceStatus.ABSENT.value
            )
            result = await self.session.execute(stmt)
            for att_obj in result.scalars().all():
                att_obj.status = AttendanceStatus.EXCUSED.value
                att_obj.updated_at = now
                if hasattr(att_obj, "data"):
                    current = dict(att_obj.data) if att_obj.data else {}
                    current["excuse_id"] = excuse_id
                    att_obj.data = current
            await self.session.flush()

        excuse["is_approved"] = True
        excuse["approved_at"] = now.isoformat()
        excuse["approved_by"] = approved_by

        return excuse

    async def get_student_excuses(
        self,
        tenant_id: str,
        student_id: str,
        pending_only: bool = False
    ) -> List[Dict[str, Any]]:
        filters: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "student_id": student_id
        }
        if pending_only:
            filters["is_approved"] = False

        return await gd_find(self.session, "attendance_excuses", filters, order_by="created_at", desc_order=True, limit=1000)

    async def get_students_with_low_attendance(
        self,
        tenant_id: str,
        threshold: float = 85.0,
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict[str, Any]]:
        from pg_models import Attendance
        conditions = [Attendance.school_id == tenant_id]
        if start_date:
            conditions.append(Attendance.date >= start_date)
        if end_date:
            conditions.append(Attendance.date <= end_date)

        stmt = select(Attendance).where(*conditions).limit(10000)
        result = await self.session.execute(stmt)
        all_records = result.scalars().all()

        by_student: Dict[str, Dict] = {}
        for rec in all_records:
            sid = rec.student_id
            if sid not in by_student:
                by_student[sid] = {"total": 0, "present": 0, "section_id": rec.class_id}
            by_student[sid]["total"] += 1
            if rec.status == AttendanceStatus.PRESENT.value:
                by_student[sid]["present"] += 1

        low_attendance = []
        for sid, data in by_student.items():
            t = data["total"]
            p = data["present"]
            rate = (p / t * 100) if t > 0 else 100
            if rate < threshold:
                low_attendance.append({
                    "student_id": sid,
                    "section_id": data["section_id"],
                    "total": t,
                    "present": p,
                    "attendance_rate": round(rate, 2),
                    "absent_days": t - p,
                })

        low_attendance.sort(key=lambda x: x["attendance_rate"])
        return low_attendance

    async def get_consecutive_absences(
        self,
        tenant_id: str,
        min_days: int = 3
    ) -> List[Dict[str, Any]]:
        from pg_models import Attendance
        end_dt = datetime.now(timezone.utc).date()
        start_dt = end_dt - timedelta(days=30)

        stmt = select(Attendance).where(
            Attendance.school_id == tenant_id,
            Attendance.date >= start_dt.isoformat(),
            Attendance.date <= end_dt.isoformat(),
            Attendance.status == AttendanceStatus.ABSENT.value,
        ).order_by(Attendance.student_id, Attendance.date).limit(10000)
        result = await self.session.execute(stmt)
        records = result.scalars().all()

        alerts = []
        current_student = None
        consecutive = 0
        last_date = None

        def _flush():
            if consecutive >= min_days:
                alerts.append({
                    "student_id": current_student,
                    "consecutive_days": consecutive,
                    "last_absence_date": last_date.isoformat() if last_date else None,
                })

        for rec in records:
            sid = rec.student_id
            try:
                if isinstance(rec.date, str):
                    record_date = datetime.fromisoformat(rec.date).date()
                elif isinstance(rec.date, datetime):
                    record_date = rec.date.date()
                elif isinstance(rec.date, date):
                    record_date = rec.date
                else:
                    continue
            except (ValueError, TypeError):
                continue

            if sid != current_student:
                _flush()
                current_student = sid
                consecutive = 1
                last_date = record_date
            else:
                if last_date and (record_date - last_date).days <= 2:
                    consecutive += 1
                else:
                    _flush()
                    consecutive = 1
                last_date = record_date

        _flush()
        return alerts

    def _att_to_dict(self, att_obj) -> Dict[str, Any]:
        d = model_to_dict(att_obj)
        d["tenant_id"] = d.get("school_id")
        d["section_id"] = d.get("class_id")
        att_date = d.get("date")
        if isinstance(att_date, datetime):
            d["attendance_date"] = att_date.isoformat()
        elif att_date:
            d["attendance_date"] = str(att_date)
        else:
            d["attendance_date"] = None
        return d


__all__ = ["AttendanceEngine", "AttendanceStatus", "ExcuseType"]
