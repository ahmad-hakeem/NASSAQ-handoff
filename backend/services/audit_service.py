"""
NASSAQ - Audit Service  
Audit logging utilities
"""
from datetime import datetime, timezone
import uuid
from typing import Optional
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate


async def log_action(
    db,
    action: str,
    action_by: str,
    action_by_name: str = "",
    target_type: str = "",
    target_id: str = "",
    target_name: str = "",
    details: dict = None,
    tenant_id: str = None,
    ip_address: str = None,
    user_agent: str = None
):
    """Log an audit action to the database"""
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": action,
        "action_by": action_by,
        "action_by_name": action_by_name,
        "target_type": target_type,
        "target_id": target_id,
        "target_name": target_name,
        "details": details or {},
        "tenant_id": tenant_id,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_insert(db.session, "audit_logs", audit_log)
    return audit_log


async def log_user_action(db, current_user: dict, action: str, target_type: str, target_id: str, target_name: str = "", details: dict = None):
    """Convenience function to log user actions"""
    return await log_action(
        db=db,
        action=action,
        action_by=current_user.get("id", ""),
        action_by_name=current_user.get("full_name", ""),
        target_type=target_type,
        target_id=target_id,
        target_name=target_name,
        details=details,
        tenant_id=current_user.get("tenant_id")
    )


async def get_audit_logs(
    db,
    action: str = None,
    action_by: str = None,
    target_type: str = None,
    target_id: str = None,
    tenant_id: str = None,
    from_date: str = None,
    to_date: str = None,
    skip: int = 0,
    limit: int = 50
):
    """Get audit logs with filtering"""
    query = {}
    
    if action:
        query["action"] = action
    if action_by:
        query["action_by"] = action_by
    if target_type:
        query["target_type"] = target_type
    if target_id:
        query["target_id"] = target_id
    if tenant_id:
        query["tenant_id"] = tenant_id
    
    if from_date or to_date:
        query["timestamp"] = {}
        if from_date:
            query["timestamp"]["$gte"] = from_date
        if to_date:
            query["timestamp"]["$lte"] = to_date
    
    logs = await gd_find(db.session, "audit_logs", query, order_by="timestamp", desc_order=True, offset=skip, limit=limit)
    
    total = await gd_count(db.session, "audit_logs", query)
    
    return {
        "logs": logs,
        "total": total,
        "skip": skip,
        "limit": limit
    }
