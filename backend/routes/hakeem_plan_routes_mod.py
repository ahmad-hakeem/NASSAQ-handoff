"""
NASSAQ Route Module: Hakeem's Daily Plan (خطة حكيم لليوم)

Per-user daily task list shown on the School Command Center. Supports both
manual user-created tasks and AI-injected proactive tasks from the Hakeem
analysis engine (distinguished by `source = 'manual' | 'ai'`).
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from dependencies import db, get_current_user
from engines.hakeem_plan_service import inject_ai_task
from engines.sql_utils import (
    gd_delete_one,
    gd_find,
    gd_find_one,
    gd_insert,
    gd_update_one,
)

logger = logging.getLogger("nassaq")

router = APIRouter(prefix="/v1/hakeem-plan", tags=["Hakeem Daily Plan"])

_MAIN_ADMIN_EMAILS = {"zalat@nassaqapp.com", "hakim@nassaqapp.com"}

_PRIORITY_WEIGHT = {"urgent": 0, "medium": 1, "normal": 2}


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _is_main_admin(user: dict) -> bool:
    """Defense-in-depth: must be a platform_admin AND have a main-admin email."""
    email = (user.get("email") or "").lower()
    role = (user.get("role") or "").lower()
    return email in _MAIN_ADMIN_EMAILS and role == "platform_admin"


def _serialize(row: Dict[str, Any]) -> Dict[str, Any]:
    if not row:
        return {}
    out = {
        "id": row.get("id"),
        "tenant_id": row.get("tenant_id"),
        "user_id": row.get("user_id"),
        "title": row.get("title") or "",
        "details": row.get("details") or "",
        "priority": row.get("priority") or "normal",
        "status": row.get("status") or "active",
        "source": row.get("source") or "manual",
        "task_date": row.get("task_date") or "",
        "ai_meta": row.get("ai_meta") or None,
    }
    for k in ("completed_at", "created_at", "updated_at"):
        v = row.get(k)
        if v is not None:
            out[k] = v if isinstance(v, str) else v.isoformat()
    return out


class DailyTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    details: Optional[str] = Field(default=None, max_length=2000)
    priority: Literal["urgent", "medium", "normal"] = "normal"
    task_date: Optional[str] = None


class DailyTaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    details: Optional[str] = Field(default=None, max_length=2000)
    priority: Optional[Literal["urgent", "medium", "normal"]] = None
    status: Optional[Literal["active", "completed"]] = None


class AIInjectPayload(BaseModel):
    user_id: str
    tenant_id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=300)
    details: Optional[str] = Field(default=None, max_length=2000)
    priority: Literal["urgent", "medium", "normal"] = "urgent"
    task_date: Optional[str] = None
    ai_meta: Optional[Dict[str, Any]] = None
    dedupe_key: Optional[str] = None


@router.get("/tasks")
async def list_daily_tasks(
    date: Optional[str] = Query(default=None, description="YYYY-MM-DD; defaults to today"),
    current_user: dict = Depends(get_current_user),
):
    """List the current user's daily tasks for a given date (today by default)."""
    target_date = date or _today_str()
    rows = await gd_find(
        db.session,
        "daily_tasks",
        {"user_id": current_user.get("id"), "task_date": target_date},
        order_by="created_at",
        desc_order=False,
    )
    items = [_serialize(r) for r in rows]
    # Stable sort: priority weight asc, then created_at asc (already preserved).
    items.sort(key=lambda x: _PRIORITY_WEIGHT.get(x.get("priority"), 9))
    return {"tasks": items, "date": target_date}


@router.post("/tasks", status_code=201)
async def create_daily_task(
    payload: DailyTaskCreate,
    current_user: dict = Depends(get_current_user),
):
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="عنوان المهمة مطلوب")
    priority = payload.priority  # Literal-validated by Pydantic
    task_date = payload.task_date or _today_str()

    doc = {
        "tenant_id": current_user.get("tenant_id"),
        "user_id": current_user.get("id"),
        "title": title,
        "details": (payload.details or "").strip() or None,
        "priority": priority,
        "status": "active",
        "source": "manual",
        "task_date": task_date,
        "ai_meta": None,
        "created_by": current_user.get("id"),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    new_id = await gd_insert(db.session, "daily_tasks", doc)
    row = await gd_find_one(db.session, "daily_tasks", {"id": new_id})
    return {"task": _serialize(row or {})}


@router.patch("/tasks/{task_id}")
async def update_daily_task(
    task_id: str,
    payload: DailyTaskUpdate,
    current_user: dict = Depends(get_current_user),
):
    filters: Dict[str, Any] = {"id": task_id, "user_id": current_user.get("id")}
    tenant_id = current_user.get("tenant_id")
    if tenant_id:
        filters["tenant_id"] = tenant_id
    existing = await gd_find_one(db.session, "daily_tasks", filters)
    if not existing:
        raise HTTPException(status_code=404, detail="المهمة غير موجودة")

    updates: Dict[str, Any] = {}
    if payload.title is not None:
        clean = payload.title.strip()
        if not clean:
            raise HTTPException(status_code=422, detail="عنوان المهمة مطلوب")
        updates["title"] = clean
    if payload.details is not None:
        updates["details"] = payload.details.strip() or None
    if payload.priority is not None:
        updates["priority"] = payload.priority
    if payload.status is not None:
        updates["status"] = payload.status
        updates["completed_at"] = (
            datetime.now(timezone.utc) if payload.status == "completed" else None
        )

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        await gd_update_one(db.session, "daily_tasks", filters, updates)

    row = await gd_find_one(db.session, "daily_tasks", filters)
    return {"task": _serialize(row or {})}


@router.delete("/tasks/{task_id}")
async def delete_daily_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    filters: Dict[str, Any] = {"id": task_id, "user_id": current_user.get("id")}
    tenant_id = current_user.get("tenant_id")
    if tenant_id:
        filters["tenant_id"] = tenant_id
    deleted = await gd_delete_one(db.session, "daily_tasks", filters)
    if not deleted:
        raise HTTPException(status_code=404, detail="المهمة غير موجودة")
    return {"success": True, "deleted_id": task_id}


@router.post("/tasks/ai-inject", status_code=201)
async def ai_inject_task(
    payload: AIInjectPayload,
    current_user: dict = Depends(get_current_user),
):
    """
    Programmatically inject a Hakeem-generated task into a user's daily plan.

    Restricted to platform main-admin accounts (zalat@/hakim@). In-process
    callers should prefer `engines.hakeem_plan_service.inject_ai_task` directly
    so that a Hakeem analysis pipeline doesn't need an HTTP round-trip.
    """
    if not _is_main_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="هذه العملية مقصورة على حسابات الإدارة الرئيسية",
        )
    row = await inject_ai_task(
        db.session,
        tenant_id=payload.tenant_id,
        user_id=payload.user_id,
        title=payload.title,
        details=payload.details,
        priority=payload.priority,
        task_date=payload.task_date,
        ai_meta=payload.ai_meta,
        dedupe_key=payload.dedupe_key,
    )
    if not row:
        raise HTTPException(status_code=422, detail="تعذر إنشاء المهمة")
    return {"task": _serialize(row)}
