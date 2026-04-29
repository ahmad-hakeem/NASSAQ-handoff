"""
NASSAQ Route Module: Administrative Calendar (الروزنامة الإدارية)

Provides full CRUD plus CSV bulk-import for the school-scoped administrative
calendar widget that powers `frontend/src/components/dashboard/AdminCalendar.jsx`.
"""
import csv
import io
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from dependencies import db, get_current_user
from engines.sql_utils import (
    gd_delete_one,
    gd_find,
    gd_find_one,
    gd_insert,
    gd_insert_many,
    gd_update_one,
)

logger = logging.getLogger("nassaq")

router = APIRouter(prefix="/v1/calendar", tags=["Administrative Calendar"])


_ALLOWED_TYPES = {"trip", "parents", "report", "exam", "holiday", "meeting", "other"}

_TYPE_ALIASES: Dict[str, str] = {
    # Arabic synonyms
    "رحلة": "trip",
    "رحلات": "trip",
    "أولياء الأمور": "parents",
    "اولياء الامور": "parents",
    "أولياء": "parents",
    "تقرير": "report",
    "تقارير": "report",
    "اختبار": "exam",
    "إختبار": "exam",
    "اختبارات": "exam",
    "إجازة": "holiday",
    "اجازة": "holiday",
    "عطلة": "holiday",
    "اجتماع": "meeting",
    "إجتماع": "meeting",
    "اجتماعات": "meeting",
    "أخرى": "other",
    "اخرى": "other",
    # English synonyms
    "trip": "trip",
    "parents": "parents",
    "report": "report",
    "exam": "exam",
    "holiday": "holiday",
    "meeting": "meeting",
    "other": "other",
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CalendarEventCreate(BaseModel):
    title_ar: Optional[str] = Field(default=None)
    title_en: Optional[str] = Field(default=None)
    type: str = Field(default="meeting")
    date: str
    details_ar: Optional[str] = None
    details_en: Optional[str] = None


class CalendarEventUpdate(BaseModel):
    title_ar: Optional[str] = None
    title_en: Optional[str] = None
    type: Optional[str] = None
    date: Optional[str] = None
    details_ar: Optional[str] = None
    details_en: Optional[str] = None


def _normalize_type(raw: Optional[str]) -> str:
    if not raw:
        return "meeting"
    key = str(raw).strip()
    if not key:
        return "meeting"
    mapped = _TYPE_ALIASES.get(key) or _TYPE_ALIASES.get(key.lower())
    if mapped:
        return mapped
    if key in _ALLOWED_TYPES:
        return key
    return "other"


def _validate_date(value: str) -> str:
    if not value or not isinstance(value, str) or not _DATE_RE.match(value):
        raise HTTPException(status_code=422, detail="تاريخ غير صالح. استخدم الصيغة YYYY-MM-DD")
    return value


def _serialize(row: Dict[str, Any]) -> Dict[str, Any]:
    if not row:
        return {}
    out = {
        "id": row.get("id"),
        "tenant_id": row.get("tenant_id"),
        "title_ar": row.get("title_ar") or "",
        "title_en": row.get("title_en") or "",
        "type": row.get("type") or "meeting",
        "date": row.get("date") or "",
        "details_ar": row.get("details_ar") or "",
        "details_en": row.get("details_en") or "",
    }
    created_at = row.get("created_at")
    updated_at = row.get("updated_at")
    if created_at is not None:
        out["created_at"] = created_at if isinstance(created_at, str) else created_at.isoformat()
    if updated_at is not None:
        out["updated_at"] = updated_at if isinstance(updated_at, str) else updated_at.isoformat()
    return out


def _resolve_tenant(current_user: dict) -> Optional[str]:
    """Return the tenant_id scope. Platform admins see global (None) records too."""
    return current_user.get("tenant_id")


async def _fetch_sorted(tenant_id: Optional[str]) -> List[Dict[str, Any]]:
    filters: Dict[str, Any] = {}
    if tenant_id:
        filters["tenant_id"] = tenant_id
    rows = await gd_find(
        db.session,
        "calendar_events",
        filters,
        order_by="date",
        desc_order=False,
    )
    return [_serialize(r) for r in rows]


@router.get("/events")
async def list_calendar_events(current_user: dict = Depends(get_current_user)):
    """List upcoming calendar events for the current tenant, sorted by date asc."""
    tenant_id = _resolve_tenant(current_user)
    items = await _fetch_sorted(tenant_id)
    return {"events": items}


@router.post("/events", status_code=201)
async def create_calendar_event(
    payload: CalendarEventCreate,
    current_user: dict = Depends(get_current_user),
):
    if not (payload.title_ar or payload.title_en):
        raise HTTPException(status_code=422, detail="العنوان مطلوب (عربي أو إنجليزي)")
    date = _validate_date(payload.date)
    tenant_id = _resolve_tenant(current_user)

    doc = {
        "tenant_id": tenant_id,
        "title_ar": (payload.title_ar or payload.title_en or "").strip(),
        "title_en": (payload.title_en or "").strip() or None,
        "type": _normalize_type(payload.type),
        "date": date,
        "details_ar": (payload.details_ar or "").strip() or None,
        "details_en": (payload.details_en or "").strip() or None,
        "created_by": current_user.get("id"),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    new_id = await gd_insert(db.session, "calendar_events", doc)
    row = await gd_find_one(db.session, "calendar_events", {"id": new_id})
    return {"event": _serialize(row or {})}


@router.put("/events/{event_id}")
async def update_calendar_event(
    event_id: str,
    payload: CalendarEventUpdate,
    current_user: dict = Depends(get_current_user),
):
    tenant_id = _resolve_tenant(current_user)
    filters: Dict[str, Any] = {"id": event_id}
    if tenant_id:
        filters["tenant_id"] = tenant_id

    existing = await gd_find_one(db.session, "calendar_events", filters)
    if not existing:
        raise HTTPException(status_code=404, detail="الحدث غير موجود")

    updates: Dict[str, Any] = {}
    if payload.title_ar is not None:
        updates["title_ar"] = payload.title_ar.strip()
    if payload.title_en is not None:
        updates["title_en"] = payload.title_en.strip() or None
    if payload.type is not None:
        updates["type"] = _normalize_type(payload.type)
    if payload.date is not None:
        updates["date"] = _validate_date(payload.date)
    if payload.details_ar is not None:
        updates["details_ar"] = payload.details_ar.strip() or None
    if payload.details_en is not None:
        updates["details_en"] = payload.details_en.strip() or None

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        await gd_update_one(db.session, "calendar_events", filters, updates)

    row = await gd_find_one(db.session, "calendar_events", filters)
    return {"event": _serialize(row or {})}


@router.delete("/events/{event_id}")
async def delete_calendar_event(
    event_id: str,
    current_user: dict = Depends(get_current_user),
):
    tenant_id = _resolve_tenant(current_user)
    filters: Dict[str, Any] = {"id": event_id}
    if tenant_id:
        filters["tenant_id"] = tenant_id
    deleted = await gd_delete_one(db.session, "calendar_events", filters)
    if not deleted:
        raise HTTPException(status_code=404, detail="الحدث غير موجود")
    return {"success": True, "deleted_id": event_id}


@router.post("/import")
async def import_calendar_events(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Bulk-import calendar events from a CSV file.

    Expected columns (in order, header optional):
      1. اسم المهمة / Title
      2. التاريخ (YYYY-MM-DD) / Date
      3. نوع الحدث (رحلة، تقرير، إجازة، أخرى) / Type
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="لم يتم إرفاق ملف")

    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(
            status_code=415,
            detail="صيغة الملف غير مدعومة. الرجاء رفع ملف CSV.",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="الملف فارغ")
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="حجم الملف يتجاوز 2 ميجا")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("utf-16")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="تعذر قراءة محتوى الملف")

    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if r and any(cell.strip() for cell in r)]
    if not rows:
        raise HTTPException(status_code=400, detail="الملف لا يحتوي على بيانات")

    # Drop the header row when the second cell is not a YYYY-MM-DD date AND the first
    # cell matches a known header label. This avoids dropping a real data row whose
    # date happens to be malformed (such rows are skipped later instead).
    _HEADER_LABELS = {
        "title", "name", "task", "event", "date",
        "اسم المهمة", "المهمة", "العنوان", "التاريخ",
    }
    first = rows[0]
    if first:
        first_cell = (first[0] or "").strip().lower()
        second_cell = (first[1] if len(first) > 1 else "").strip()
        if not _DATE_RE.match(second_cell) and first_cell in {h.lower() for h in _HEADER_LABELS}:
            rows = rows[1:]

    tenant_id = _resolve_tenant(current_user)
    docs: List[Dict[str, Any]] = []
    skipped = 0
    now = datetime.now(timezone.utc)
    for idx, row in enumerate(rows):
        try:
            if len(row) < 2:
                skipped += 1
                continue
            title = (row[0] or "").strip()
            date_val = (row[1] or "").strip()
            type_val = (row[2] if len(row) > 2 else "").strip()
            details = (row[3] if len(row) > 3 else "").strip()
            if not title or not _DATE_RE.match(date_val):
                skipped += 1
                continue
            docs.append({
                "tenant_id": tenant_id,
                "title_ar": title,
                "title_en": title,
                "type": _normalize_type(type_val),
                "date": date_val,
                "details_ar": details or None,
                "details_en": details or None,
                "created_by": current_user.get("id"),
                "created_at": now,
                "updated_at": now,
            })
        except Exception as exc:  # defensive — never let a malformed row 500 the request
            logger.warning("[calendar.import] row %s skipped: %s", idx, exc)
            skipped += 1

    inserted_ids: List[str] = []
    if docs:
        inserted_ids = await gd_insert_many(db.session, "calendar_events", docs)

    items = await _fetch_sorted(tenant_id)
    return {
        "events": items,
        "inserted": len(inserted_ids),
        "skipped": skipped,
        "total": len(items),
    }
