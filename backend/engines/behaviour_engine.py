"""
NASSAQ Behaviour Engine
محرك السلوك لمنصة نَسَّق
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid
import logging

from sqlalchemy import select, func, and_

from engines.sql_utils import (
    model_to_dict, models_to_dicts, apply_updates,
    gd_find, gd_find_one, gd_insert, gd_update_one, gd_count, gd_delete_one,
)

logger = logging.getLogger("nassaq.behaviour")


class BehaviourCategory(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class BehaviourSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BehaviourStatus(str, Enum):
    RECORDED = "recorded"
    REVIEWED = "reviewed"
    ESCALATED = "escalated"
    RESOLVED = "resolved"


class DisciplinaryAction(str, Enum):
    WARNING = "warning"
    VERBAL_WARNING = "verbal_warning"
    WRITTEN_WARNING = "written_warning"
    PARENT_MEETING = "parent_meeting"
    DETENTION = "detention"
    SUSPENSION = "suspension"
    EXPULSION = "expulsion"
    COMMUNITY_SERVICE = "community_service"
    COUNSELING = "counseling"


class AuditAction(str, Enum):
    BEHAVIOUR_RECORDED = "behaviour_recorded"
    BEHAVIOUR_UPDATED = "behaviour_updated"
    BEHAVIOUR_DELETED = "behaviour_deleted"
    DISCIPLINARY_CREATED = "disciplinary_created"
    DISCIPLINARY_UPDATED = "disciplinary_updated"


class BehaviourEngine:
    def __init__(self, db):
        self.db = db

    @property
    def session(self):
        return self.db.session

    async def create_behaviour_type(
        self,
        tenant_id: str,
        name_ar: str,
        category: str,
        points: int,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        from pg_models import BehaviourType
        type_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        obj = BehaviourType(
            id=type_id,
            tenant_id=tenant_id,
            name_ar=name_ar,
            name_en=kwargs.get("name_en"),
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        extra = {
            "category": category,
            "points": points,
            "severity": kwargs.get("severity", BehaviourSeverity.LOW.value),
            "description_ar": kwargs.get("description_ar"),
            "description_en": kwargs.get("description_en"),
            "auto_escalation_threshold": kwargs.get("auto_escalation_threshold"),
            "default_action": kwargs.get("default_action"),
            "is_global": kwargs.get("is_global", False),
            "created_by": created_by,
        }
        if hasattr(obj, "data"):
            obj.data = extra

        self.session.add(obj)
        await self.session.flush()

        d = model_to_dict(obj)
        return d

    async def get_behaviour_types(
        self,
        tenant_id: str,
        category: Optional[str] = None,
        include_global: bool = True
    ) -> List[Dict[str, Any]]:
        from pg_models import BehaviourType
        conditions = [BehaviourType.is_active == True]

        if include_global:
            conditions.append(
                (BehaviourType.tenant_id == tenant_id) | (BehaviourType.is_global == True)
            )
        else:
            conditions.append(BehaviourType.tenant_id == tenant_id)

        stmt = select(BehaviourType).where(*conditions)
        result = await self.session.execute(stmt)
        types = result.scalars().all()

        results = []
        for t in types:
            d = model_to_dict(t)
            if category and d.get("category") != category:
                continue
            results.append(d)

        return results

    async def update_behaviour_type(
        self,
        type_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        from pg_models import BehaviourType
        stmt = select(BehaviourType).where(BehaviourType.id == type_id).limit(1)
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        if not obj:
            raise ValueError("نوع السلوك غير موجود")

        updates.pop("id", None)
        updates.pop("tenant_id", None)
        updates["updated_by"] = updated_by
        apply_updates(obj, updates)
        obj.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return model_to_dict(obj)

    async def delete_behaviour_type(self, type_id: str) -> bool:
        from pg_models import BehaviourType
        stmt = select(BehaviourType).where(BehaviourType.id == type_id).limit(1)
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        if not obj:
            return False
        obj.is_active = False
        obj.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return True

    async def record_behaviour(
        self,
        tenant_id: str,
        student_id: str,
        behaviour_type_id: str,
        recorded_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        from pg_models import BehaviourType, BehaviourRecord
        stmt = select(BehaviourType).where(BehaviourType.id == behaviour_type_id).limit(1)
        result = await self.session.execute(stmt)
        btype = result.scalars().first()
        if not btype:
            raise ValueError("نوع السلوك غير موجود")

        btype_d = model_to_dict(btype)
        record_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        obj = BehaviourRecord(
            id=record_id,
            school_id=tenant_id,
            student_id=student_id,
            created_at=now,
            updated_at=now,
        )

        extra = {
            "behaviour_type_id": behaviour_type_id,
            "category": btype_d.get("category"),
            "points": btype_d.get("points", 0),
            "severity": btype_d.get("severity", BehaviourSeverity.LOW.value),
            "incident_date": kwargs.get("incident_date", now.isoformat()),
            "incident_location": kwargs.get("incident_location"),
            "description": kwargs.get("description"),
            "witnesses": kwargs.get("witnesses", []),
            "evidence": kwargs.get("evidence", []),
            "status": BehaviourStatus.RECORDED.value,
            "recorded_by": recorded_by,
            "requires_follow_up": kwargs.get("requires_follow_up", False),
            "follow_up_date": kwargs.get("follow_up_date"),
            "notes": kwargs.get("notes"),
            "tenant_id": tenant_id,
        }
        if hasattr(obj, "data"):
            obj.data = extra

        self.session.add(obj)
        await self.session.flush()

        threshold = btype_d.get("auto_escalation_threshold")
        if threshold:
            await self._check_auto_escalation(
                tenant_id, student_id, behaviour_type_id, threshold
            )

        await self._log_action(
            AuditAction.BEHAVIOUR_RECORDED,
            recorded_by,
            "behaviour_record",
            record_id,
            tenant_id=tenant_id,
            details={
                "student_id": student_id,
                "behaviour_type": btype_d.get("name_ar"),
                "category": btype_d.get("category"),
                "points": btype_d.get("points", 0)
            }
        )

        return model_to_dict(obj)

    async def get_student_behaviour_records(
        self,
        tenant_id: str,
        student_id: str,
        category: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        from pg_models import BehaviourRecord
        stmt = select(BehaviourRecord).where(
            BehaviourRecord.school_id == tenant_id,
            BehaviourRecord.student_id == student_id
        )
        result = await self.session.execute(stmt)
        all_records = result.scalars().all()

        records = []
        for rec in all_records:
            d = model_to_dict(rec)
            if category and d.get("category") != category:
                continue
            if status and d.get("status") != status:
                continue
            if start_date and d.get("incident_date", "") < start_date:
                continue
            if end_date and d.get("incident_date", "") > end_date:
                continue
            records.append(d)

        records.sort(key=lambda x: x.get("incident_date", ""), reverse=True)
        total = len(records)
        paged = records[skip:skip + limit]

        return {
            "records": paged,
            "total": total,
            "skip": skip,
            "limit": limit
        }

    async def update_behaviour_record(
        self,
        record_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        from pg_models import BehaviourRecord
        stmt = select(BehaviourRecord).where(BehaviourRecord.id == record_id).limit(1)
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        if not obj:
            raise ValueError("سجل السلوك غير موجود")

        updates.pop("id", None)
        updates.pop("school_id", None)
        updates.pop("tenant_id", None)
        updates["updated_by"] = updated_by
        apply_updates(obj, updates)
        obj.updated_at = datetime.now(timezone.utc)
        await self.session.flush()

        await self._log_action(
            AuditAction.BEHAVIOUR_UPDATED,
            updated_by,
            "behaviour_record",
            record_id,
            details={"updates": list(updates.keys())}
        )

        return model_to_dict(obj)

    async def delete_behaviour_record(
        self,
        record_id: str,
        deleted_by: str
    ) -> bool:
        from pg_models import BehaviourRecord
        stmt = select(BehaviourRecord).where(BehaviourRecord.id == record_id).limit(1)
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        if not obj:
            return False
        await self.session.delete(obj)
        await self.session.flush()

        await self._log_action(
            AuditAction.BEHAVIOUR_DELETED,
            deleted_by,
            "behaviour_record",
            record_id,
        )
        return True

    async def create_disciplinary_action(
        self,
        tenant_id: str,
        student_id: str,
        action_type: str,
        reason: str,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        action_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        action_doc = {
            "id": action_id,
            "tenant_id": tenant_id,
            "student_id": student_id,
            "action_type": action_type,
            "reason": reason,
            "description": kwargs.get("description"),
            "behaviour_record_ids": kwargs.get("behaviour_record_ids", []),
            "start_date": kwargs.get("start_date", now),
            "end_date": kwargs.get("end_date"),
            "duration_days": kwargs.get("duration_days"),
            "conditions": kwargs.get("conditions", []),
            "parent_notified": False,
            "parent_acknowledged": False,
            "is_active": True,
            "is_completed": False,
            "created_at": now,
            "created_by": created_by
        }

        await gd_insert(self.session, "disciplinary_actions", action_doc)

        await self._log_action(
            AuditAction.DISCIPLINARY_CREATED,
            created_by,
            "disciplinary_action",
            action_id,
            tenant_id=tenant_id,
            details={
                "student_id": student_id,
                "action_type": action_type,
                "reason": reason
            }
        )

        return action_doc

    async def get_student_disciplinary_actions(
        self,
        tenant_id: str,
        student_id: str,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        filters: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "student_id": student_id
        }
        if active_only:
            filters["is_active"] = True

        return await gd_find(self.session, "disciplinary_actions", filters, order_by="created_at", desc_order=True)

    async def update_disciplinary_action(
        self,
        action_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        updates.pop("id", None)
        updates.pop("tenant_id", None)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        updates["updated_by"] = updated_by

        await gd_update_one(self.session, "disciplinary_actions", {"id": action_id}, updates)

        await self._log_action(
            AuditAction.DISCIPLINARY_UPDATED,
            updated_by,
            "disciplinary_action",
            action_id,
            details={"updates": list(updates.keys())}
        )

        return await gd_find_one(self.session, "disciplinary_actions", {"id": action_id})

    async def complete_disciplinary_action(
        self,
        action_id: str,
        completed_by: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        updates = {
            "is_completed": True,
            "is_active": False,
            "completed_at": now,
            "completed_by": completed_by,
        }
        if notes:
            updates["completion_notes"] = notes

        return await self.update_disciplinary_action(action_id, updates, completed_by)

    async def get_section_behaviour_summary(
        self,
        tenant_id: str,
        section_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        from pg_models import BehaviourRecord, Student
        stmt = select(Student.id).where(
            Student.school_id == tenant_id,
            Student.class_id == section_id,
            Student.is_active == True
        )
        result = await self.session.execute(stmt)
        student_ids = [row[0] for row in result.all()]

        if not student_ids:
            return {
                "section_id": section_id,
                "total_records": 0,
                "positive_count": 0,
                "negative_count": 0,
                "students": []
            }

        stmt = select(BehaviourRecord).where(
            BehaviourRecord.school_id == tenant_id,
            BehaviourRecord.student_id.in_(student_ids)
        )
        result = await self.session.execute(stmt)
        all_records = result.scalars().all()

        records = []
        for rec in all_records:
            d = model_to_dict(rec)
            if start_date and d.get("incident_date", "") < start_date:
                continue
            if end_date and d.get("incident_date", "") > end_date:
                continue
            records.append(d)

        positive = sum(1 for r in records if r.get("category") == BehaviourCategory.POSITIVE.value)
        negative = sum(1 for r in records if r.get("category") == BehaviourCategory.NEGATIVE.value)

        by_student: Dict[str, Dict] = {}
        for r in records:
            sid = r.get("student_id")
            if sid not in by_student:
                by_student[sid] = {"positive": 0, "negative": 0, "points": 0}
            if r.get("category") == BehaviourCategory.POSITIVE.value:
                by_student[sid]["positive"] += 1
            elif r.get("category") == BehaviourCategory.NEGATIVE.value:
                by_student[sid]["negative"] += 1
            by_student[sid]["points"] += r.get("points", 0)

        student_summaries = [
            {"student_id": sid, **data}
            for sid, data in by_student.items()
        ]

        return {
            "section_id": section_id,
            "total_records": len(records),
            "positive_count": positive,
            "negative_count": negative,
            "students": student_summaries
        }

    async def _check_auto_escalation(
        self,
        tenant_id: str,
        student_id: str,
        behaviour_type_id: str,
        threshold: int
    ):
        from pg_models import BehaviourRecord
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

        stmt = select(BehaviourRecord).where(
            BehaviourRecord.school_id == tenant_id,
            BehaviourRecord.student_id == student_id,
        )
        result = await self.session.execute(stmt)
        all_recs = result.scalars().all()

        matching = []
        for rec in all_recs:
            d = model_to_dict(rec)
            if d.get("behaviour_type_id") == behaviour_type_id and d.get("incident_date", "") >= thirty_days_ago:
                matching.append(rec)

        if len(matching) >= threshold:
            matching.sort(key=lambda r: (model_to_dict(r).get("incident_date", "")), reverse=True)
            latest = matching[0]
            if hasattr(latest, "data"):
                current = dict(latest.data) if latest.data else {}
                current["status"] = BehaviourStatus.ESCALATED.value
                current["requires_follow_up"] = True
                latest.data = current
            await self.session.flush()

    async def get_student_behaviour_profile(
        self,
        tenant_id: str,
        student_id: str
    ) -> Dict[str, Any]:
        from pg_models import Student, BehaviourRecord
        stmt = select(Student).where(Student.id == student_id).limit(1)
        result = await self.session.execute(stmt)
        student = result.scalars().first()
        if not student:
            raise ValueError("الطالب غير موجود")

        student_d = model_to_dict(student)

        stmt = select(BehaviourRecord).where(
            BehaviourRecord.school_id == tenant_id,
            BehaviourRecord.student_id == student_id
        )
        result = await self.session.execute(stmt)
        all_recs = result.scalars().all()
        records = [model_to_dict(r) for r in all_recs]

        total_points = sum(r.get("points", 0) for r in records)
        positive_count = sum(1 for r in records if r.get("category") == BehaviourCategory.POSITIVE.value)
        negative_count = sum(1 for r in records if r.get("category") == BehaviourCategory.NEGATIVE.value)

        active_actions = await gd_count(self.session, "disciplinary_actions", {
            "tenant_id": tenant_id,
            "student_id": student_id,
            "is_active": True,
            "is_completed": False
        })

        if len(records) > 0:
            behaviour_score = min(100, max(0, 100 + total_points))
        else:
            behaviour_score = 100

        if behaviour_score >= 90:
            behaviour_level = "ممتاز"
        elif behaviour_score >= 75:
            behaviour_level = "جيد جداً"
        elif behaviour_score >= 60:
            behaviour_level = "جيد"
        elif behaviour_score >= 50:
            behaviour_level = "مقبول"
        else:
            behaviour_level = "يحتاج متابعة"

        return {
            "student_id": student_id,
            "student_name": student_d.get("full_name"),
            "total_records": len(records),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "total_points": total_points,
            "behaviour_score": behaviour_score,
            "behaviour_level": behaviour_level,
            "active_disciplinary_actions": active_actions,
            "last_incident": records[0]["incident_date"] if records else None,
            "needs_attention": behaviour_score < 60 or active_actions > 0
        }

    async def _log_action(
        self,
        action: AuditAction,
        actor_id: str,
        target_type: str,
        target_id: str,
        target_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        is_sensitive: bool = False
    ):
        from pg_models import AuditLog
        log_obj = AuditLog(
            id=str(uuid.uuid4()),
            action=action.value,
            entity_type=target_type,
            entity_id=target_id,
            performed_by=actor_id,
            tenant_id=tenant_id,
            created_at=datetime.now(timezone.utc),
        )
        extra = {
            "action_category": "behaviour",
            "actor_name": "",
            "actor_role": "",
            "target_name": target_name,
            "details": details or {},
            "is_sensitive": is_sensitive,
        }
        if hasattr(log_obj, "data"):
            log_obj.data = extra
        self.session.add(log_obj)
        await self.session.flush()


__all__ = ["BehaviourEngine"]
