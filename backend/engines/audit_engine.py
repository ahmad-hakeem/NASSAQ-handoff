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

from sqlalchemy import select, and_, or_, func, delete as sa_delete, desc as sa_desc

from pg_models import AuditLog
from engines.sql_utils import model_to_dict, models_to_dicts, dict_to_model


class AuditAction(str, Enum):
    LOGIN = "auth.login"
    LOGOUT = "auth.logout"
    LOGIN_FAILED = "auth.login_failed"
    PASSWORD_CHANGED = "auth.password_changed"
    PASSWORD_RESET = "auth.password_reset"
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_ACTIVATED = "user.activated"
    USER_SUSPENDED = "user.suspended"
    ROLE_ASSIGNED = "user.role_assigned"
    ROLE_REMOVED = "user.role_removed"
    TENANT_CREATED = "tenant.created"
    TENANT_UPDATED = "tenant.updated"
    TENANT_SUSPENDED = "tenant.suspended"
    TENANT_ACTIVATED = "tenant.activated"
    GRADE_RECORDED = "academic.grade_recorded"
    GRADE_UPDATED = "academic.grade_updated"
    GRADES_BULK_RECORDED = "academic.grades_bulk_recorded"
    ASSESSMENT_CREATED = "academic.assessment_created"
    ASSESSMENT_PUBLISHED = "academic.assessment_published"
    REPORT_CARD_GENERATED = "academic.report_card_generated"
    ATTENDANCE_RECORDED = "attendance.recorded"
    ATTENDANCE_BULK_RECORDED = "attendance.bulk_recorded"
    EXCUSE_SUBMITTED = "attendance.excuse_submitted"
    EXCUSE_APPROVED = "attendance.excuse_approved"
    BEHAVIOUR_NOTE_CREATED = "behaviour.note_created"
    DISCIPLINARY_ACTION_CREATED = "behaviour.action_created"
    DISCIPLINARY_ACTION_UPDATED = "behaviour.action_updated"
    SCHEDULE_CREATED = "schedule.created"
    SCHEDULE_PUBLISHED = "schedule.published"
    SCHEDULE_MODIFIED = "schedule.modified"
    SETTINGS_UPDATED = "settings.updated"
    DATA_EXPORTED = "data.exported"
    DATA_IMPORTED = "data.imported"
    DATA_MODIFY = "data.modify"
    BEHAVIOUR_RECORDED = "behaviour.recorded"
    BEHAVIOUR_REVIEWED = "behaviour.reviewed"
    SKILL_RECORDED = "session.skill_recorded"
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
            AuditAction.GRADES_BULK_RECORDED.value: AuditSeverity.MEDIUM.value,
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

    @property
    def session(self):
        return self.db.session

    async def log(
        self,
        action: str,
        performed_by: Optional[str] = None,
        tenant_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor_email: Optional[str] = None,
        device_info: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Log an audit entry with full user and device context"""
        from src.core.middleware.audit_middleware import parse_device_info as _parse_ua

        audit_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        severity = self.severity_map.get(action, AuditSeverity.LOW.value)

        if device_info is None and user_agent:
            device_info = _parse_ua(user_agent)

        obj = AuditLog(
            id=audit_id,
            action=action,
            severity=severity,
            performed_by=performed_by,
            actor_name=actor_name,
            actor_role=actor_role,
            actor_email=actor_email,
            school_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info or {},
            timestamp=now,
        )
        self.session.add(obj)
        await self.session.flush()

        audit_doc = {
            "id": audit_id,
            "action": action,
            "severity": severity,
            "performed_by": performed_by,
            "actor_name": actor_name,
            "actor_role": actor_role,
            "actor_email": actor_email,
            "tenant_id": tenant_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "device_info": device_info or {},
            "timestamp": now.isoformat(),
            "metadata": kwargs.get("metadata", {}),
        }
        return audit_doc

    async def log_auth_event(
        self,
        action: str,
        user_id: Optional[str] = None,
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
            user_agent=kwargs.get("user_agent"),
            # Enrich the human-readable actor columns so auth.* entries are
            # attributable at a glance. ``email`` is already passed by every
            # call site; ``role``/``full_name`` are passed where the user row
            # is in scope. Falls back to the explicit actor_* kwargs.
            actor_role=kwargs.get("role") or kwargs.get("actor_role"),
            actor_email=kwargs.get("email") or kwargs.get("actor_email"),
            actor_name=kwargs.get("full_name") or kwargs.get("actor_name"),
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
        conditions = []

        if tenant_id:
            conditions.append(AuditLog.school_id == tenant_id)
        if action:
            conditions.append(AuditLog.action == action)
        if performed_by:
            conditions.append(AuditLog.performed_by == performed_by)
        if entity_type:
            conditions.append(AuditLog.entity_type == entity_type)
        if entity_id:
            conditions.append(AuditLog.entity_id == entity_id)
        if severity:
            conditions.append(AuditLog.severity == severity)
        if start_date:
            conditions.append(AuditLog.timestamp >= start_date)
        if end_date:
            conditions.append(AuditLog.timestamp <= end_date)

        stmt = select(AuditLog)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(sa_desc(AuditLog.timestamp)).offset(skip).limit(limit)

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        logs = []
        for row in rows:
            d = model_to_dict(row)
            d.pop("_id", None)
            if d.get("school_id"):
                d["tenant_id"] = d["school_id"]
            logs.append(d)
        return logs

    async def get_entity_history(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50,
        tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get audit history for a specific entity.

        When ``tenant_id`` is provided the results are scoped to that school,
        preventing cross-tenant information disclosure.
        """
        conditions = [
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
        ]
        if tenant_id:
            conditions.append(AuditLog.school_id == tenant_id)
        stmt = (
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(sa_desc(AuditLog.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        logs = []
        for row in result.scalars().all():
            d = model_to_dict(row)
            d.pop("_id", None)
            logs.append(d)
        return logs

    async def get_user_activity(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 100,
        tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get activity log for a specific user.

        When ``tenant_id`` is provided the results are scoped to that school,
        preventing cross-tenant information disclosure.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        conditions = [
            AuditLog.performed_by == user_id,
            AuditLog.timestamp >= cutoff,
        ]
        if tenant_id:
            conditions.append(AuditLog.school_id == tenant_id)
        stmt = (
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(sa_desc(AuditLog.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        logs = []
        for row in result.scalars().all():
            d = model_to_dict(row)
            d.pop("_id", None)
            logs.append(d)
        return logs

    async def get_critical_events(
        self,
        tenant_id: Optional[str] = None,
        days: int = 7,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get critical and high severity events"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        conditions = [
            AuditLog.severity.in_([AuditSeverity.HIGH.value, AuditSeverity.CRITICAL.value]),
            AuditLog.timestamp >= cutoff,
        ]
        if tenant_id:
            conditions.append(AuditLog.school_id == tenant_id)

        stmt = (
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(sa_desc(AuditLog.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        logs = []
        for row in result.scalars().all():
            d = model_to_dict(row)
            d.pop("_id", None)
            logs.append(d)
        return logs

    async def get_audit_stats(
        self,
        tenant_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get audit statistics"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        conditions = [AuditLog.timestamp >= cutoff]
        if tenant_id:
            conditions.append(AuditLog.school_id == tenant_id)

        stmt = select(AuditLog).where(and_(*conditions))
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        logs = [model_to_dict(r) for r in rows]

        total = len(logs)

        by_action = {}
        for log in logs:
            a = log.get("action", "unknown")
            by_action[a] = by_action.get(a, 0) + 1

        by_severity = {}
        for log in logs:
            sev = log.get("severity", "unknown")
            by_severity[sev] = by_severity.get(sev, 0) + 1

        by_entity = {}
        for log in logs:
            entity = log.get("entity_type", "unknown")
            by_entity[entity] = by_entity.get(entity, 0) + 1

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
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        conditions = [
            AuditLog.action.in_([AuditAction.LOGIN.value, AuditAction.LOGIN_FAILED.value]),
            AuditLog.timestamp >= cutoff,
        ]
        if tenant_id:
            conditions.append(AuditLog.school_id == tenant_id)

        stmt = select(AuditLog).where(and_(*conditions))
        result = await self.session.execute(stmt)
        logs = [model_to_dict(r) for r in result.scalars().all()]

        successful = len([l for l in logs if l.get("action") == AuditAction.LOGIN.value])
        failed = len([l for l in logs if l.get("action") == AuditAction.LOGIN_FAILED.value])

        daily = {}
        for log in logs:
            day = (log.get("timestamp") or "")[:10]
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
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        stmt = sa_delete(AuditLog).where(
            and_(AuditLog.timestamp < cutoff, AuditLog.severity == AuditSeverity.LOW.value)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount


__all__ = [
    "AuditLogEngine",
    "AuditAction",
    "AuditSeverity"
]
