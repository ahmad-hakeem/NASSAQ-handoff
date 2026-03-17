"""
NASSAQ Audit Log Engine
محرك سجل التدقيق لمنصة نَسَّق

Handles:
- Comprehensive action logging
- Structured audit format
- Sensitive action tracking
- Audit trail queries
- Compliance reporting
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid
import json


class AuditAction(str, Enum):
    # Authentication
    LOGIN = "auth.login"
    LOGOUT = "auth.logout"
    LOGIN_FAILED = "auth.login_failed"
    PASSWORD_CHANGED = "auth.password_changed"
    PASSWORD_RESET = "auth.password_reset"
    
    # User Management
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_ACTIVATED = "user.activated"
    USER_SUSPENDED = "user.suspended"
    ROLE_ASSIGNED = "user.role_assigned"
    ROLE_REMOVED = "user.role_removed"
    
    # Tenant/School
    TENANT_CREATED = "tenant.created"
    TENANT_UPDATED = "tenant.updated"
    TENANT_SUSPENDED = "tenant.suspended"
    TENANT_ACTIVATED = "tenant.activated"
    
    # Academic
    GRADE_RECORDED = "academic.grade_recorded"
    GRADE_UPDATED = "academic.grade_updated"
    ASSESSMENT_CREATED = "academic.assessment_created"
    ASSESSMENT_PUBLISHED = "academic.assessment_published"
    REPORT_CARD_GENERATED = "academic.report_card_generated"
    
    # Attendance
    ATTENDANCE_RECORDED = "attendance.recorded"
    ATTENDANCE_BULK_RECORDED = "attendance.bulk_recorded"
    EXCUSE_SUBMITTED = "attendance.excuse_submitted"
    EXCUSE_APPROVED = "attendance.excuse_approved"
    
    # Behaviour
    BEHAVIOUR_NOTE_CREATED = "behaviour.note_created"
    DISCIPLINARY_ACTION_CREATED = "behaviour.action_created"
    DISCIPLINARY_ACTION_UPDATED = "behaviour.action_updated"
    
    # Schedule
    SCHEDULE_CREATED = "schedule.created"
    SCHEDULE_PUBLISHED = "schedule.published"
    SCHEDULE_MODIFIED = "schedule.modified"
    
    # Settings
    SETTINGS_UPDATED = "settings.updated"
    
    # Data
    DATA_EXPORTED = "data.exported"
    DATA_IMPORTED = "data.imported"
    DATA_MODIFY = "data.modify"
    
    # Session/Skills
    BEHAVIOUR_RECORDED = "behaviour.recorded"
    BEHAVIOUR_REVIEWED = "behaviour.reviewed"
    SKILL_RECORDED = "session.skill_recorded"
    
    # System
    SYSTEM_CONFIGURATION = "system.configuration"
    SYSTEM_CONFIG = "system.config"


class AuditSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditLogEngine:
    """
    Core Audit Log Engine for NASSAQ
    Provides comprehensive audit trail for all sensitive actions
    """
    
    def __init__(self, db):
        self.db = db
        self.audit_collection = db.audit_logs
        
        # Define action severity mapping
        self.severity_map = {
            AuditAction.LOGIN.value: AuditSeverity.LOW.value,
            AuditAction.LOGOUT.value: AuditSeverity.LOW.value,
            AuditAction.LOGIN_FAILED.value: AuditSeverity.MEDIUM.value,
            AuditAction.PASSWORD_CHANGED.value: AuditSeverity.MEDIUM.value,
            AuditAction.PASSWORD_RESET.value: AuditSeverity.MEDIUM.value,
            
            AuditAction.USER_CREATED.value: AuditSeverity.MEDIUM.value,
            AuditAction.USER_UPDATED.value: AuditSeverity.LOW.value,
            AuditAction.USER_DELETED.value: AuditSeverity.HIGH.value,
            AuditAction.USER_ACTIVATED.value: AuditSeverity.MEDIUM.value,
            AuditAction.USER_SUSPENDED.value: AuditSeverity.HIGH.value,
            AuditAction.ROLE_ASSIGNED.value: AuditSeverity.HIGH.value,
            AuditAction.ROLE_REMOVED.value: AuditSeverity.HIGH.value,
            
            AuditAction.TENANT_CREATED.value: AuditSeverity.CRITICAL.value,
            AuditAction.TENANT_UPDATED.value: AuditSeverity.MEDIUM.value,
            AuditAction.TENANT_SUSPENDED.value: AuditSeverity.CRITICAL.value,
            AuditAction.TENANT_ACTIVATED.value: AuditSeverity.CRITICAL.value,
            
            AuditAction.GRADE_RECORDED.value: AuditSeverity.MEDIUM.value,
            AuditAction.GRADE_UPDATED.value: AuditSeverity.MEDIUM.value,
            AuditAction.ASSESSMENT_CREATED.value: AuditSeverity.LOW.value,
            AuditAction.ASSESSMENT_PUBLISHED.value: AuditSeverity.MEDIUM.value,
            AuditAction.REPORT_CARD_GENERATED.value: AuditSeverity.MEDIUM.value,
            
            AuditAction.BEHAVIOUR_NOTE_CREATED.value: AuditSeverity.MEDIUM.value,
            AuditAction.DISCIPLINARY_ACTION_CREATED.value: AuditSeverity.HIGH.value,
            AuditAction.DISCIPLINARY_ACTION_UPDATED.value: AuditSeverity.HIGH.value,
            
            AuditAction.SCHEDULE_PUBLISHED.value: AuditSeverity.MEDIUM.value,
            
            AuditAction.SETTINGS_UPDATED.value: AuditSeverity.HIGH.value,
            AuditAction.DATA_EXPORTED.value: AuditSeverity.HIGH.value,
            AuditAction.DATA_IMPORTED.value: AuditSeverity.CRITICAL.value,
            AuditAction.SYSTEM_CONFIGURATION.value: AuditSeverity.CRITICAL.value,
        }
    
    # ============== AUDIT LOGGING ==============
    
    async def log(
        self,
        action: str,
        performed_by: str,
        tenant_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Log an audit entry"""
        audit_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Get severity from map or default to LOW
        severity = self.severity_map.get(action, AuditSeverity.LOW.value)
        
        audit_doc = {
            "id": audit_id,
            "action": action,
            "severity": severity,
            "performed_by": performed_by,
            "tenant_id": tenant_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": now,
            "metadata": kwargs.get("metadata", {})
        }
        
        await self.audit_collection.insert_one(audit_doc)
        
        return audit_doc
    
    async def log_auth_event(
        self,
        action: str,
        user_id: str,
        tenant_id: Optional[str] = None,
        success: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Log authentication events"""
        details = {
            "success": success,
            "email": kwargs.get("email"),
            "reason": kwargs.get("reason")
        }
        
        return await self.log(
            action=action,
            performed_by=user_id,
            tenant_id=tenant_id,
            entity_type="user",
            entity_id=user_id,
            details=details,
            ip_address=kwargs.get("ip_address"),
            user_agent=kwargs.get("user_agent")
        )
    
    async def log_data_change(
        self,
        action: str,
        performed_by: str,
        entity_type: str,
        entity_id: str,
        tenant_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Log data change events"""
        details = {
            "old_values": old_values,
            "new_values": new_values,
            "changed_fields": list(new_values.keys()) if new_values else []
        }
        
        return await self.log(
            action=action,
            performed_by=performed_by,
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            **kwargs
        )
    
    # ============== AUDIT RETRIEVAL ==============
    
    async def get_audit_logs(
        self,
        tenant_id: Optional[str] = None,
        action: Optional[str] = None,
        performed_by: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        severity: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get audit logs with filters"""
        query = {}
        
        if tenant_id:
            query["tenant_id"] = tenant_id
        if action:
            query["action"] = action
        if performed_by:
            query["performed_by"] = performed_by
        if entity_type:
            query["entity_type"] = entity_type
        if entity_id:
            query["entity_id"] = entity_id
        if severity:
            query["severity"] = severity
        
        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date
        
        logs = await self.audit_collection.find(
            query,
            {"_id": 0}
        ).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
        
        return logs
    
    async def get_entity_history(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get audit history for a specific entity"""
        logs = await self.audit_collection.find(
            {
                "entity_type": entity_type,
                "entity_id": entity_id
            },
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        return logs
    
    async def get_user_activity(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get activity log for a specific user"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        logs = await self.audit_collection.find(
            {
                "performed_by": user_id,
                "timestamp": {"$gte": cutoff}
            },
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        return logs
    
    async def get_critical_events(
        self,
        tenant_id: Optional[str] = None,
        days: int = 7,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get critical and high severity events"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        query = {
            "severity": {"$in": [AuditSeverity.HIGH.value, AuditSeverity.CRITICAL.value]},
            "timestamp": {"$gte": cutoff}
        }
        
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        logs = await self.audit_collection.find(
            query,
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        return logs
    
    # ============== AUDIT STATISTICS ==============
    
    async def get_audit_stats(
        self,
        tenant_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get audit statistics"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        query = {"timestamp": {"$gte": cutoff}}
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        logs = await self.audit_collection.find(
            query,
            {"_id": 0}
        ).to_list(100000)
        
        total = len(logs)
        
        # Group by action
        by_action = {}
        for log in logs:
            action = log.get("action", "unknown")
            by_action[action] = by_action.get(action, 0) + 1
        
        # Group by severity
        by_severity = {}
        for log in logs:
            sev = log.get("severity", "unknown")
            by_severity[sev] = by_severity.get(sev, 0) + 1
        
        # Group by entity type
        by_entity = {}
        for log in logs:
            entity = log.get("entity_type", "unknown")
            by_entity[entity] = by_entity.get(entity, 0) + 1
        
        # Top actors
        actors = {}
        for log in logs:
            actor = log.get("performed_by")
            if actor:
                actors[actor] = actors.get(actor, 0) + 1
        
        top_actors = sorted(actors.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "period_days": days,
            "total_events": total,
            "by_action": by_action,
            "by_severity": by_severity,
            "by_entity_type": by_entity,
            "top_actors": [{"user_id": a[0], "count": a[1]} for a in top_actors],
            "critical_count": by_severity.get(AuditSeverity.CRITICAL.value, 0),
            "high_count": by_severity.get(AuditSeverity.HIGH.value, 0)
        }
    
    async def get_login_analytics(
        self,
        tenant_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get login analytics"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        query = {
            "action": {"$in": [AuditAction.LOGIN.value, AuditAction.LOGIN_FAILED.value]},
            "timestamp": {"$gte": cutoff}
        }
        
        if tenant_id:
            query["tenant_id"] = tenant_id
        
        logs = await self.audit_collection.find(
            query,
            {"_id": 0}
        ).to_list(100000)
        
        successful = len([l for l in logs if l.get("action") == AuditAction.LOGIN.value])
        failed = len([l for l in logs if l.get("action") == AuditAction.LOGIN_FAILED.value])
        
        # Group by day
        daily = {}
        for log in logs:
            day = log.get("timestamp", "")[:10]
            if day not in daily:
                daily[day] = {"successful": 0, "failed": 0}
            if log.get("action") == AuditAction.LOGIN.value:
                daily[day]["successful"] += 1
            else:
                daily[day]["failed"] += 1
        
        return {
            "period_days": days,
            "total_logins": successful,
            "failed_attempts": failed,
            "success_rate": round((successful / (successful + failed) * 100) if (successful + failed) > 0 else 0, 2),
            "daily_breakdown": daily
        }
    
    # ============== COMPLIANCE HELPERS ==============
    
    async def export_audit_report(
        self,
        tenant_id: str,
        start_date: str,
        end_date: str,
        format_type: str = "json"
    ) -> Dict[str, Any]:
        """Export audit report for compliance"""
        logs = await self.get_audit_logs(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            limit=100000
        )
        
        stats = await self.get_audit_stats(tenant_id=tenant_id)
        
        report = {
            "report_id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period": {
                "start": start_date,
                "end": end_date
            },
            "summary": {
                "total_events": len(logs),
                "critical_events": len([l for l in logs if l.get("severity") == AuditSeverity.CRITICAL.value]),
                "high_events": len([l for l in logs if l.get("severity") == AuditSeverity.HIGH.value])
            },
            "statistics": stats,
            "events": logs if format_type == "json" else []
        }
        
        return report
    
    async def cleanup_old_logs(
        self,
        days_to_keep: int = 365
    ) -> int:
        """Cleanup audit logs older than specified days"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_to_keep)).isoformat()
        
        # Only delete low severity logs
        result = await self.audit_collection.delete_many({
            "timestamp": {"$lt": cutoff},
            "severity": AuditSeverity.LOW.value
        })
        
        return result.deleted_count


# Export
__all__ = [
    "AuditLogEngine",
    "AuditAction",
    "AuditSeverity"
]
