"""
NASSAQ Behaviour Engine
محرك السلوك لمنصة نَسَّق

Handles:
- Behaviour recording and tracking
- Violations and disciplinary actions
- Behaviour categories and severity
- Follow-up workflows
- Principal review process
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid

from models.foundation import (
    BehaviourRecord, BehaviourType, DisciplinaryAction,
    BehaviourCategory, BehaviourSeverity, BehaviourStatus,
    AuditLog, AuditAction
)


class BehaviourEngine:
    """
    Core Behaviour Engine for NASSAQ
    Manages student behaviour tracking and disciplinary workflows
    """
    
    def __init__(self, db):
        self.db = db
        self.behaviour_types_collection = db.behaviour_types
        self.behaviour_records_collection = db.behaviour_records
        self.disciplinary_actions_collection = db.disciplinary_actions
        self.audit_collection = db.audit_logs
        self.students_collection = db.students
        self.users_collection = db.users
    
    # ============== BEHAVIOUR TYPES ==============
    
    async def create_behaviour_type(
        self,
        name_ar: str,
        category: BehaviourCategory,
        default_severity: BehaviourSeverity,
        created_by: str,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new behaviour type"""
        type_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        type_doc = {
            "id": type_id,
            "tenant_id": tenant_id,
            "name_ar": name_ar,
            "name_en": kwargs.get("name_en"),
            "description": kwargs.get("description"),
            "category": category.value,
            "default_severity": default_severity.value,
            "default_points": kwargs.get("default_points", 0),
            "auto_escalate": kwargs.get("auto_escalate", False),
            "escalation_threshold": kwargs.get("escalation_threshold"),
            "is_active": True,
            "is_global": tenant_id is None,
            "created_at": now,
            "created_by": created_by,
        }
        
        await self.behaviour_types_collection.insert_one(type_doc)
        return type_doc
    
    async def get_behaviour_types(
        self,
        tenant_id: Optional[str] = None,
        category: Optional[BehaviourCategory] = None,
        include_global: bool = True
    ) -> List[Dict[str, Any]]:
        """Get behaviour types for a tenant"""
        query = {"is_active": True}
        
        if tenant_id:
            if include_global:
                query["$or"] = [
                    {"tenant_id": tenant_id},
                    {"is_global": True}
                ]
            else:
                query["tenant_id"] = tenant_id
        else:
            query["is_global"] = True
        
        if category:
            query["category"] = category.value
        
        return await self.behaviour_types_collection.find(
            query,
            {"_id": 0}
        ).to_list(1000)
    
    async def seed_default_behaviour_types(self):
        """Seed default/global behaviour types"""
        default_types = [
            # Positive behaviours
            {
                "name_ar": "تميز أكاديمي",
                "name_en": "Academic Excellence",
                "category": BehaviourCategory.POSITIVE.value,
                "default_severity": BehaviourSeverity.MINOR.value,
                "default_points": 10
            },
            {
                "name_ar": "مساعدة الزملاء",
                "name_en": "Helping Peers",
                "category": BehaviourCategory.POSITIVE.value,
                "default_severity": BehaviourSeverity.MINOR.value,
                "default_points": 5
            },
            {
                "name_ar": "مشاركة فعالة",
                "name_en": "Active Participation",
                "category": BehaviourCategory.POSITIVE.value,
                "default_severity": BehaviourSeverity.MINOR.value,
                "default_points": 3
            },
            {
                "name_ar": "سلوك قيادي",
                "name_en": "Leadership Behaviour",
                "category": BehaviourCategory.POSITIVE.value,
                "default_severity": BehaviourSeverity.MODERATE.value,
                "default_points": 15
            },
            
            # Negative behaviours
            {
                "name_ar": "تأخر عن الحصة",
                "name_en": "Late to Class",
                "category": BehaviourCategory.NEGATIVE.value,
                "default_severity": BehaviourSeverity.MINOR.value,
                "default_points": -2
            },
            {
                "name_ar": "عدم إحضار الواجب",
                "name_en": "Missing Homework",
                "category": BehaviourCategory.NEGATIVE.value,
                "default_severity": BehaviourSeverity.MINOR.value,
                "default_points": -3
            },
            {
                "name_ar": "تشويش في الفصل",
                "name_en": "Classroom Disruption",
                "category": BehaviourCategory.NEGATIVE.value,
                "default_severity": BehaviourSeverity.MODERATE.value,
                "default_points": -5,
                "auto_escalate": True,
                "escalation_threshold": 3
            },
            {
                "name_ar": "استخدام الهاتف",
                "name_en": "Phone Usage",
                "category": BehaviourCategory.NEGATIVE.value,
                "default_severity": BehaviourSeverity.MODERATE.value,
                "default_points": -5
            },
            {
                "name_ar": "تنمر",
                "name_en": "Bullying",
                "category": BehaviourCategory.NEGATIVE.value,
                "default_severity": BehaviourSeverity.MAJOR.value,
                "default_points": -20,
                "auto_escalate": True,
                "escalation_threshold": 1
            },
            {
                "name_ar": "شجار",
                "name_en": "Fighting",
                "category": BehaviourCategory.NEGATIVE.value,
                "default_severity": BehaviourSeverity.SEVERE.value,
                "default_points": -30,
                "auto_escalate": True,
                "escalation_threshold": 1
            },
            {
                "name_ar": "غش في الاختبار",
                "name_en": "Cheating",
                "category": BehaviourCategory.NEGATIVE.value,
                "default_severity": BehaviourSeverity.MAJOR.value,
                "default_points": -25,
                "auto_escalate": True,
                "escalation_threshold": 1
            },
        ]
        
        for behaviour_type in default_types:
            # Check if exists
            existing = await self.behaviour_types_collection.find_one({
                "name_ar": behaviour_type["name_ar"],
                "is_global": True
            })
            
            if not existing:
                behaviour_type["id"] = str(uuid.uuid4())
                behaviour_type["tenant_id"] = None
                behaviour_type["is_global"] = True
                behaviour_type["is_active"] = True
                behaviour_type["created_at"] = datetime.now(timezone.utc).isoformat()
                behaviour_type["created_by"] = "system"
                
                await self.behaviour_types_collection.insert_one(behaviour_type)
    
    # ============== BEHAVIOUR RECORDS ==============
    
    async def record_behaviour(
        self,
        tenant_id: str,
        student_id: str,
        behaviour_type_id: str,
        recorded_by: str,
        incident_date: str,
        title: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Record a new behaviour incident"""
        record_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Get behaviour type for defaults
        behaviour_type = await self.behaviour_types_collection.find_one(
            {"id": behaviour_type_id},
            {"_id": 0}
        )
        
        if not behaviour_type:
            raise ValueError("نوع السلوك غير موجود")
        
        # Get student info
        student = await self.students_collection.find_one(
            {"id": student_id},
            {"_id": 0}
        )
        
        if not student:
            raise ValueError("الطالب غير موجود")
        
        # Calculate edit window (48 hours by default)
        edit_until = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
        
        record_doc = {
            "id": record_id,
            "tenant_id": tenant_id,
            "student_id": student_id,
            "student_name": student.get("full_name"),
            "class_id": kwargs.get("class_id") or student.get("class_id"),
            "behaviour_type_id": behaviour_type_id,
            "behaviour_type_name": behaviour_type.get("name_ar"),
            "category": kwargs.get("category") or behaviour_type.get("category"),
            "severity": kwargs.get("severity") or behaviour_type.get("default_severity"),
            "title": title,
            "description": kwargs.get("description"),
            "points": kwargs.get("points") or behaviour_type.get("default_points", 0),
            "incident_date": incident_date,
            "incident_location": kwargs.get("incident_location"),
            "witnesses": kwargs.get("witnesses", []),
            "status": BehaviourStatus.PENDING.value,
            "requires_follow_up": kwargs.get("requires_follow_up", False),
            "follow_up_date": kwargs.get("follow_up_date"),
            "follow_up_notes": None,
            "parent_notified": False,
            "principal_reviewed": False,
            "is_confidential": kwargs.get("is_confidential", False),
            "visible_to_parent": kwargs.get("visible_to_parent", True),
            "recorded_by": recorded_by,
            "recorded_at": now,
            "editable_until": edit_until,
        }
        
        await self.behaviour_records_collection.insert_one(record_doc)
        
        # Check for auto-escalation
        if behaviour_type.get("auto_escalate"):
            await self._check_auto_escalation(
                tenant_id, student_id, behaviour_type_id, 
                behaviour_type.get("escalation_threshold", 3)
            )
        
        # Audit log
        await self._log_action(
            AuditAction.BEHAVIOUR_RECORDED,
            actor_id=recorded_by,
            target_type="student",
            target_id=student_id,
            target_name=student.get("full_name"),
            tenant_id=tenant_id,
            details={
                "behaviour_type": behaviour_type.get("name_ar"),
                "category": record_doc["category"],
                "severity": record_doc["severity"]
            }
        )
        
        return record_doc
    
    async def get_student_behaviour_history(
        self,
        tenant_id: str,
        student_id: str,
        category: Optional[BehaviourCategory] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get behaviour history for a student"""
        query = {
            "tenant_id": tenant_id,
            "student_id": student_id
        }
        
        if category:
            query["category"] = category.value
        
        if start_date or end_date:
            query["incident_date"] = {}
            if start_date:
                query["incident_date"]["$gte"] = start_date
            if end_date:
                query["incident_date"]["$lte"] = end_date
        
        total = await self.behaviour_records_collection.count_documents(query)
        
        records = await self.behaviour_records_collection.find(
            query,
            {"_id": 0}
        ).sort("incident_date", -1).skip(skip).limit(limit).to_list(limit)
        
        # Calculate summary
        all_records = await self.behaviour_records_collection.find(
            {"tenant_id": tenant_id, "student_id": student_id},
            {"category": 1, "points": 1, "severity": 1, "_id": 0}
        ).to_list(1000)
        
        summary = {
            "total_records": len(all_records),
            "positive_count": sum(1 for r in all_records if r.get("category") == BehaviourCategory.POSITIVE.value),
            "negative_count": sum(1 for r in all_records if r.get("category") == BehaviourCategory.NEGATIVE.value),
            "total_points": sum(r.get("points", 0) for r in all_records),
            "severity_breakdown": {}
        }
        
        for severity in BehaviourSeverity:
            summary["severity_breakdown"][severity.value] = sum(
                1 for r in all_records if r.get("severity") == severity.value
            )
        
        return {
            "records": records,
            "total": total,
            "summary": summary,
            "skip": skip,
            "limit": limit
        }
    
    async def get_class_behaviour_summary(
        self,
        tenant_id: str,
        class_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get behaviour summary for a class"""
        query = {
            "tenant_id": tenant_id,
            "class_id": class_id
        }
        
        if start_date or end_date:
            query["incident_date"] = {}
            if start_date:
                query["incident_date"]["$gte"] = start_date
            if end_date:
                query["incident_date"]["$lte"] = end_date
        
        records = await self.behaviour_records_collection.find(
            query,
            {"_id": 0}
        ).to_list(10000)
        
        # Group by student
        student_stats = {}
        for record in records:
            student_id = record.get("student_id")
            if student_id not in student_stats:
                student_stats[student_id] = {
                    "student_id": student_id,
                    "student_name": record.get("student_name"),
                    "positive_count": 0,
                    "negative_count": 0,
                    "total_points": 0
                }
            
            if record.get("category") == BehaviourCategory.POSITIVE.value:
                student_stats[student_id]["positive_count"] += 1
            else:
                student_stats[student_id]["negative_count"] += 1
            
            student_stats[student_id]["total_points"] += record.get("points", 0)
        
        # Sort by total points
        sorted_students = sorted(
            student_stats.values(),
            key=lambda x: x["total_points"],
            reverse=True
        )
        
        return {
            "class_id": class_id,
            "total_records": len(records),
            "positive_total": sum(1 for r in records if r.get("category") == BehaviourCategory.POSITIVE.value),
            "negative_total": sum(1 for r in records if r.get("category") == BehaviourCategory.NEGATIVE.value),
            "student_rankings": sorted_students
        }
    
    async def update_behaviour_record(
        self,
        record_id: str,
        updates: Dict[str, Any],
        updated_by: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """Update a behaviour record"""
        now = datetime.now(timezone.utc).isoformat()
        
        record = await self.behaviour_records_collection.find_one(
            {"id": record_id},
            {"_id": 0}
        )
        
        if not record:
            raise ValueError("سجل السلوك غير موجود")
        
        # Check edit window
        if not force and record.get("editable_until"):
            if now > record["editable_until"]:
                raise ValueError("انتهت فترة التعديل المسموحة. يرجى التواصل مع المدير")
        
        # Protected fields
        protected = ["id", "tenant_id", "student_id", "recorded_by", "recorded_at"]
        for field in protected:
            updates.pop(field, None)
        
        updates["updated_at"] = now
        updates["updated_by"] = updated_by
        
        await self.behaviour_records_collection.update_one(
            {"id": record_id},
            {"$set": updates}
        )
        
        return await self.behaviour_records_collection.find_one(
            {"id": record_id},
            {"_id": 0}
        )
    
    # ============== REVIEW & WORKFLOW ==============
    
    async def principal_review(
        self,
        record_id: str,
        reviewed_by: str,
        notes: Optional[str] = None,
        new_status: BehaviourStatus = BehaviourStatus.REVIEWED
    ) -> Dict[str, Any]:
        """Principal reviews a behaviour record"""
        now = datetime.now(timezone.utc).isoformat()
        
        record = await self.behaviour_records_collection.find_one(
            {"id": record_id},
            {"_id": 0}
        )
        
        if not record:
            raise ValueError("سجل السلوك غير موجود")
        
        await self.behaviour_records_collection.update_one(
            {"id": record_id},
            {
                "$set": {
                    "principal_reviewed": True,
                    "principal_reviewed_by": reviewed_by,
                    "principal_reviewed_at": now,
                    "principal_notes": notes,
                    "status": new_status.value,
                    "updated_at": now
                }
            }
        )
        
        await self._log_action(
            AuditAction.BEHAVIOUR_REVIEWED,
            actor_id=reviewed_by,
            target_type="behaviour_record",
            target_id=record_id,
            target_name=record.get("student_name"),
            tenant_id=record.get("tenant_id"),
            details={
                "new_status": new_status.value,
                "has_notes": bool(notes)
            }
        )
        
        return await self.behaviour_records_collection.find_one(
            {"id": record_id},
            {"_id": 0}
        )
    
    async def notify_parent(
        self,
        record_id: str,
        notified_by: str
    ) -> Dict[str, Any]:
        """Mark parent as notified"""
        now = datetime.now(timezone.utc).isoformat()
        
        await self.behaviour_records_collection.update_one(
            {"id": record_id},
            {
                "$set": {
                    "parent_notified": True,
                    "parent_notified_at": now,
                    "parent_notified_by": notified_by
                }
            }
        )
        
        return await self.behaviour_records_collection.find_one(
            {"id": record_id},
            {"_id": 0}
        )
    
    # ============== DISCIPLINARY ACTIONS ==============
    
    async def create_disciplinary_action(
        self,
        tenant_id: str,
        behaviour_record_id: str,
        student_id: str,
        action_type: str,
        description: str,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a disciplinary action"""
        action_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        action_doc = {
            "id": action_id,
            "tenant_id": tenant_id,
            "behaviour_record_id": behaviour_record_id,
            "student_id": student_id,
            "action_type": action_type,
            "description": description,
            "start_date": kwargs.get("start_date"),
            "end_date": kwargs.get("end_date"),
            "is_active": True,
            "is_completed": False,
            "approved_by": kwargs.get("approved_by"),
            "approved_at": kwargs.get("approved_at"),
            "created_by": created_by,
            "created_at": now,
        }
        
        await self.disciplinary_actions_collection.insert_one(action_doc)
        
        # Update behaviour record
        await self.behaviour_records_collection.update_one(
            {"id": behaviour_record_id},
            {
                "$set": {
                    "disciplinary_action": action_type,
                    "disciplinary_action_date": now,
                    "status": BehaviourStatus.RESOLVED.value
                }
            }
        )
        
        # Get student name for audit
        student = await self.students_collection.find_one(
            {"id": student_id},
            {"full_name": 1, "_id": 0}
        )
        
        await self._log_action(
            AuditAction.DISCIPLINARY_ACTION,
            actor_id=created_by,
            target_type="student",
            target_id=student_id,
            target_name=student.get("full_name") if student else None,
            tenant_id=tenant_id,
            details={
                "action_type": action_type,
                "behaviour_record_id": behaviour_record_id
            },
            is_sensitive=True
        )
        
        return action_doc
    
    async def get_student_disciplinary_actions(
        self,
        tenant_id: str,
        student_id: str,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get disciplinary actions for a student"""
        query = {
            "tenant_id": tenant_id,
            "student_id": student_id
        }
        
        if active_only:
            query["is_active"] = True
            query["is_completed"] = False
        
        return await self.disciplinary_actions_collection.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)
    
    # ============== AUTO-ESCALATION ==============
    
    async def _check_auto_escalation(
        self,
        tenant_id: str,
        student_id: str,
        behaviour_type_id: str,
        threshold: int
    ):
        """Check if behaviour should be escalated"""
        # Count recent occurrences (last 30 days)
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        
        count = await self.behaviour_records_collection.count_documents({
            "tenant_id": tenant_id,
            "student_id": student_id,
            "behaviour_type_id": behaviour_type_id,
            "incident_date": {"$gte": thirty_days_ago}
        })
        
        if count >= threshold:
            # Mark the latest record as escalated
            latest = await self.behaviour_records_collection.find_one(
                {
                    "tenant_id": tenant_id,
                    "student_id": student_id,
                    "behaviour_type_id": behaviour_type_id
                },
                sort=[("incident_date", -1)]
            )
            
            if latest:
                await self.behaviour_records_collection.update_one(
                    {"id": latest["id"]},
                    {
                        "$set": {
                            "status": BehaviourStatus.ESCALATED.value,
                            "requires_follow_up": True
                        }
                    }
                )
    
    # ============== STUDENT BEHAVIOUR PROFILE ==============
    
    async def get_student_behaviour_profile(
        self,
        tenant_id: str,
        student_id: str
    ) -> Dict[str, Any]:
        """Get comprehensive behaviour profile for a student"""
        student = await self.students_collection.find_one(
            {"id": student_id},
            {"_id": 0}
        )
        
        if not student:
            raise ValueError("الطالب غير موجود")
        
        # Get all records
        records = await self.behaviour_records_collection.find(
            {"tenant_id": tenant_id, "student_id": student_id},
            {"_id": 0}
        ).to_list(10000)
        
        # Calculate metrics
        total_points = sum(r.get("points", 0) for r in records)
        positive_count = sum(1 for r in records if r.get("category") == BehaviourCategory.POSITIVE.value)
        negative_count = sum(1 for r in records if r.get("category") == BehaviourCategory.NEGATIVE.value)
        
        # Get active disciplinary actions
        active_actions = await self.disciplinary_actions_collection.count_documents({
            "tenant_id": tenant_id,
            "student_id": student_id,
            "is_active": True,
            "is_completed": False
        })
        
        # Calculate behaviour score (0-100)
        if len(records) > 0:
            # Start at 100, adjust based on points
            behaviour_score = min(100, max(0, 100 + total_points))
        else:
            behaviour_score = 100  # No records = perfect score
        
        # Determine behaviour level
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
            "student_name": student.get("full_name"),
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
    
    # ============== AUDIT LOGGING ==============
    
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
        """Log an action to audit trail"""
        log_entry = {
            "id": str(uuid.uuid4()),
            "action": action.value,
            "action_category": "behaviour",
            "actor_id": actor_id,
            "actor_name": "",
            "actor_role": "",
            "target_type": target_type,
            "target_id": target_id,
            "target_name": target_name,
            "tenant_id": tenant_id,
            "details": details or {},
            "is_sensitive": is_sensitive,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        await self.audit_collection.insert_one(log_entry)


# Export
__all__ = ["BehaviourEngine"]
