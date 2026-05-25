"""
NASSAQ Route Module: Platform analytics, settings, API keys, integrations, contact, system rules
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, re, io, base64, secrets, hashlib
from cryptography.fernet import Fernet

from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate
from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security, logger,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code
)

router = APIRouter()

_ENCRYPTION_KEY = os.environ.get("NASSAQ_ENCRYPTION_KEY", "")
_IS_PRODUCTION = os.environ.get("ENVIRONMENT", "").lower() == "production"
_logger = logging.getLogger("nassaq.platform")

def _get_fernet():
    if _ENCRYPTION_KEY:
        key = base64.urlsafe_b64encode(hashlib.sha256(_ENCRYPTION_KEY.encode()).digest())
        return Fernet(key)
    return None

def _encrypt_api_key(value: str) -> str:
    if not value:
        return value
    f = _get_fernet()
    if f:
        return f.encrypt(value.encode()).decode()
    if _IS_PRODUCTION:
        raise ValueError("NASSAQ_ENCRYPTION_KEY required in production for API key encryption")
    _logger.warning("NASSAQ_ENCRYPTION_KEY not set — API key stored unencrypted")
    return value

def _decrypt_api_key(value: str) -> str:
    f = _get_fernet()
    if f and value:
        try:
            return f.decrypt(value.encode()).decode()
        except Exception:
            return value
    return value

# ============== PLATFORM ANALYTICS ROUTES ==============

@router.get("/analytics/overview")
async def get_analytics_overview(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get platform analytics overview"""
    total_schools = await gd_count(db.session, "schools", {})
    active_schools = await gd_count(db.session, "schools", {"status": "active"})
    total_students = await gd_count(db.session, "students", {})
    total_teachers = await gd_count(db.session, "teachers", {})
    total_users = await gd_count(db.session, "users", {})
    active_users = await gd_count(db.session, "users", {"is_active": True})
    
    # Get monthly growth data
    now = datetime.now(timezone.utc)
    monthly_data = []
    for i in range(6):
        month_start = (now - timedelta(days=30*(5-i))).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (now - timedelta(days=30*(4-i))).replace(day=1, hour=0, minute=0, second=0, microsecond=0) if i < 5 else now
        
        students_count = await gd_count(db.session, "students", {
            "created_at": {"$lte": month_end.isoformat()}
        })
        teachers_count = await gd_count(db.session, "teachers", {
            "created_at": {"$lte": month_end.isoformat()}
        })
        schools_count = await gd_count(db.session, "schools", {
            "created_at": {"$lte": month_end.isoformat()}
        })
        
        month_names = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
        monthly_data.append({
            "month": month_names[month_start.month - 1],
            "students": students_count,
            "teachers": teachers_count,
            "schools": schools_count
        })
    
    # Get school distribution by city
    pipeline = [
        {"$group": {"_id": "$city", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    city_distribution = await _gd_aggregate(db.session, "schools", pipeline)
    
    return {
        "stats": {
            "total_schools": total_schools,
            "active_schools": active_schools,
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_users": total_users,
            "active_users": active_users,
        },
        "monthly_data": monthly_data,
        "city_distribution": [
            {"name": c["_id"] or "غير محدد", "value": c["count"]} for c in city_distribution
        ]
    }

@router.get("/analytics/charts")
async def get_analytics_charts(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Return real chart data for the platform analytics page.
    All data is aggregated from the live database — no static fallbacks."""

    # ── 1. City distribution (schools per city) ─────────────────────────
    CITY_COLORS = ["#2563eb", "#16a34a", "#ea580c", "#9333ea", "#0891b2",
                   "#b45309", "#be185d", "#047857", "#7c3aed", "#0369a1"]
    pipeline_city = [
        {"$group": {"_id": "$city", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 8},
    ]
    cities_raw = await _gd_aggregate(db.session, "schools", pipeline_city)
    cities_data = [
        {
            "name": c["_id"] or "غير محدد",
            "name_en": c["_id"] or "Unknown",
            "value": c["count"],
            "color": CITY_COLORS[i % len(CITY_COLORS)],
        }
        for i, c in enumerate(cities_raw)
    ]

    # ── 2. Attendance breakdown (overall platform) ───────────────────────
    total_att = await gd_count(db.session, "attendance", {})
    if total_att > 0:
        present_count = await gd_count(db.session, "attendance", {"status": "present"})
        absent_count  = await gd_count(db.session, "attendance", {"status": "absent"})
        late_count    = await gd_count(db.session, "attendance", {"status": "late"})
        excused_count = await gd_count(db.session, "attendance", {"status": "excused"})
        present_pct = round(present_count / total_att * 100, 1)
        absent_pct  = round(absent_count  / total_att * 100, 1)
        late_pct    = round(late_count    / total_att * 100, 1)
        excused_pct = round(excused_count / total_att * 100, 1)
        attendance_data = [
            {"name": "حاضر",    "name_en": "Present", "value": present_pct, "color": "#16a34a"},
            {"name": "غائب",    "name_en": "Absent",  "value": absent_pct,  "color": "#dc2626"},
            {"name": "متأخر",   "name_en": "Late",    "value": late_pct,    "color": "#d97706"},
            {"name": "بعذر",    "name_en": "Excused", "value": excused_pct, "color": "#2563eb"},
        ]
        attendance_data = [d for d in attendance_data if d["value"] > 0]
    else:
        attendance_data = []

    # ── 3. Monthly growth trend (last 6 months) ──────────────────────────
    now = datetime.now(timezone.utc)
    month_names_ar = ['يناير','فبراير','مارس','أبريل','مايو','يونيو',
                      'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']
    growth_trend = []
    for i in range(5, -1, -1):
        target = now - timedelta(days=30 * i)
        cutoff = target.isoformat()
        students_cnt = await gd_count(db.session, "students", {"created_at": {"$lte": cutoff}})
        teachers_cnt = await gd_count(db.session, "teachers", {"created_at": {"$lte": cutoff}})
        schools_cnt  = await gd_count(db.session, "schools", {"created_at":  {"$lte": cutoff}})
        growth_trend.append({
            "month":    month_names_ar[target.month - 1],
            "students": students_cnt,
            "teachers": teachers_cnt,
            "schools":  schools_cnt,
        })

    return {
        "cities_data": cities_data,
        "attendance_data": attendance_data,
        "growth_trend": growth_trend,
    }

@router.get("/analytics/reports")
async def get_analytics_reports(
    report_type: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get available reports"""
    reports = await gd_find(db.session, "reports", {"type": report_type} if report_type else {}, order_by="created_at", desc_order=True, limit=50)
    
    return {"reports": reports}

@router.get("/analytics/insights")
async def get_ai_insights(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get AI-generated insights"""
    insights = []
    
    # Check attendance trends
    total_students = await gd_count(db.session, "students", {})
    if total_students > 100:
        insights.append({
            "id": str(uuid.uuid4()),
            "type": "trend",
            "title_ar": "نمو في أعداد الطلاب",
            "title_en": "Student Growth",
            "description_ar": f"إجمالي {total_students} طالب مسجل في المنصة",
            "description_en": f"Total of {total_students} students enrolled",
            "impact": "positive",
            "priority": "low"
        })
    
    # Check inactive schools
    inactive_schools = await gd_count(db.session, "schools", {"status": {"$ne": "active"}})
    if inactive_schools > 0:
        insights.append({
            "id": str(uuid.uuid4()),
            "type": "alert",
            "title_ar": f"{inactive_schools} مدرسة تحتاج متابعة",
            "title_en": f"{inactive_schools} schools need attention",
            "description_ar": "يوجد مدارس غير نشطة تحتاج مراجعة",
            "description_en": "There are inactive schools that need review",
            "impact": "negative",
            "priority": "high"
        })
    
    # Check AI usage
    ai_enabled_schools = await gd_count(db.session, "schools", {"ai_enabled": True})
    total_schools = await gd_count(db.session, "schools", {})
    if total_schools > 0 and ai_enabled_schools < total_schools * 0.5:
        insights.append({
            "id": str(uuid.uuid4()),
            "type": "recommendation",
            "title_ar": "فرصة لتفعيل AI",
            "title_en": "AI Activation Opportunity",
            "description_ar": f"{total_schools - ai_enabled_schools} مدرسة لم تفعّل ميزات AI",
            "description_en": f"{total_schools - ai_enabled_schools} schools haven't activated AI",
            "impact": "neutral",
            "priority": "medium"
        })
    
    return {"insights": insights}





# ============== PHASE 6: PLATFORM ANALYTICS ==============

@router.get("/platform/analytics")
async def platform_analytics(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
):
    total_schools = await gd_count(db.session, "schools", {"status": "active"})
    total_students = await gd_count(db.session, "students", {"is_active": True})
    total_teachers = await gd_count(db.session, "teachers", {})
    total_users = await gd_count(db.session, "users", {})
    total_classes = await gd_count(db.session, "classes", {"is_active": {"$ne": False}})
    total_sessions = await gd_count(db.session, "class_sessions", {"status": "completed"})

    att_total = await gd_count(db.session, "attendance", {})
    att_present = await gd_count(db.session, "attendance", {"status": {"$in": ["present", "late"]}})
    overall_attendance = round((att_present / att_total * 100) if att_total else 0, 1)

    schools = await gd_find(db.session, "schools", {"status": "active"}, limit=100)

    school_stats = []
    for school in schools:
        sid = school["id"]
        s_students = await gd_count(db.session, "students", {"school_id": sid, "is_active": True})
        s_teachers = await gd_count(db.session, "teachers", {"school_id": sid})
        s_sessions = await gd_count(db.session, "class_sessions", {"school_id": sid, "status": "completed"})
        s_att_total = await gd_count(db.session, "attendance", {"school_id": sid})
        s_att_present = await gd_count(db.session, "attendance", {"school_id": sid, "status": {"$in": ["present", "late"]}})
        s_att_rate = round((s_att_present / s_att_total * 100) if s_att_total else 0, 1)

        school_stats.append({
            "school_id": sid,
            "school_name": school.get("name") or school.get("name_ar", sid),
            "students": s_students,
            "teachers": s_teachers,
            "sessions": s_sessions,
            "attendance_rate": s_att_rate,
        })

    role_dist = {}
    pipeline = [
        {"$group": {"_id": "$role", "count": {"$sum": 1}}}
    ]
    for doc in await _gd_aggregate(db.session, "users", pipeline):
        role_dist[doc["_id"] or "unknown"] = doc["count"]

    return {
        "total_schools": total_schools,
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_users": total_users,
        "total_classes": total_classes,
        "total_sessions": total_sessions,
        "overall_attendance_rate": overall_attendance,
        "schools": school_stats,
        "role_distribution": role_dist,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

@router.get("/platform/analytics/growth")
async def platform_growth_analytics(
    months: int = Query(6, ge=1, le=24),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
):
    now = datetime.now(timezone.utc)
    monthly_data = []

    for i in range(months - 1, -1, -1):
        target = now - timedelta(days=i * 30)
        month_label = target.strftime("%Y-%m")
        cutoff = target.strftime("%Y-%m-%dT%H:%M:%S")

        students = await gd_count(db.session, "students", {
            "enrollment_date": {"$lte": target.strftime("%Y-%m-%d")}
        })
        sessions = await gd_count(db.session, "class_sessions", {
            "date": {"$lte": target.strftime("%Y-%m-%d")},
            "status": "completed",
        })

        monthly_data.append({
            "month": month_label,
            "students": students,
            "sessions": sessions,
        })

    return {
        "months_analyzed": months,
        "monthly_data": monthly_data,
        "generated_at": now.isoformat(),
    }


# Re-include api_router to pick up school settings routes
async def shutdown_db_client():
    client.close()



# ============== PLATFORM SETTINGS MODELS ==============
class GeneralSettingsModel(BaseModel):
    platform_name_ar: str = "نَسَّق | NASSAQ"
    platform_name_en: str = "NASSAQ"
    browser_title: str = "نَسَّق - منصة إدارة المدارس الذكية"
    default_language: str = "ar"
    date_format: str = "hijri"
    timezone: str = "Asia/Riyadh"
    email_notifications: bool = True
    sms_notifications: bool = False
    push_notifications: bool = True
    ai_features: bool = True
    registration_open: bool = True
    maintenance_mode: bool = False

class BrandSettingsModel(BaseModel):
    logo: Optional[str] = None
    favicon: Optional[str] = None
    primary_color: str = "#1e3a5f"
    secondary_color: str = "#3b82f6"
    accent_color: str = "#10b981"

class SocialMediaModel(BaseModel):
    twitter: Optional[str] = ""
    facebook: Optional[str] = ""
    instagram: Optional[str] = ""
    linkedin: Optional[str] = ""
    youtube: Optional[str] = ""

class ContactInfoModel(BaseModel):
    primary_email: str = "info@nassaqapp.com"
    support_email: str = "support@nassaqapp.com"
    primary_phone: str = "+966 11 234 5678"
    alternate_phone: Optional[str] = ""
    address: str = "الرياض، المملكة العربية السعودية"
    working_hours: str = "الأحد - الخميس: 8:00 ص - 4:00 م"
    website: str = "https://nassaqapp.com"
    owner_name: str = "شركة نَسَّق للتقنية التعليمية"
    social_media: SocialMediaModel = SocialMediaModel()

class LegalContentModel(BaseModel):
    content: str
    version: str = "1.0"
    effective_date: Optional[str] = None

class SecuritySettingsModel(BaseModel):
    two_factor_enabled: bool = False
    session_timeout: int = 30
    max_sessions: int = 5
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_numbers: bool = True
    password_require_special: bool = True

class PlatformSettingsResponse(BaseModel):
    general: GeneralSettingsModel
    brand: BrandSettingsModel
    contact: ContactInfoModel
    terms: LegalContentModel
    privacy: LegalContentModel
    security: SecuritySettingsModel
    updated_at: str

class APIKeyCreate(BaseModel):
    name: str
    permissions: str = "read_only"  # read_only, read_write, full_access

class APIKeyResponse(BaseModel):
    id: str
    name: str
    key: str
    secret: Optional[str] = None  # Only returned on creation
    permissions: str
    is_active: bool
    created_at: str
    last_used: Optional[str] = None





# ============== API KEYS MANAGEMENT ENDPOINTS ==============
@router.post("/settings/api-keys")
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Create a new API key"""
    import secrets
    
    # Generate API key and secret
    prefix = "nsk_live_" if key_data.permissions == "full_access" else "nsk_test_"
    api_key = prefix + secrets.token_hex(16)
    api_secret = "nss_" + secrets.token_hex(24)
    
    # Hash the secret for storage
    hashed_secret = hash_password(api_secret)
    
    new_key = {
        "id": str(uuid.uuid4()),
        "name": key_data.name,
        "key": api_key,
        "secret_hash": hashed_secret,
        "permissions": key_data.permissions,
        "is_active": True,
        "created_by": current_user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_used": None
    }
    
    await gd_insert(db.session, "api_keys", new_key)
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "api_key_created",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "api_key",
        "target_id": new_key["id"],
        "target_name": key_data.name,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    # Return with the secret (only time it's shown)
    return {
        "id": new_key["id"],
        "name": new_key["name"],
        "key": api_key,
        "secret": api_secret,  # Only returned on creation
        "permissions": new_key["permissions"],
        "is_active": new_key["is_active"],
        "created_at": new_key["created_at"],
        "last_used": None,
        "message": "تم إنشاء مفتاح API بنجاح. يرجى حفظ المفتاح السري، لن يتم عرضه مرة أخرى."
    }


@router.get("/settings/api-keys")
async def get_api_keys(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get all API keys"""
    keys = await gd_find(db.session, "api_keys", {}, order_by="created_at", desc_order=True, limit=100)
    
    return {"keys": keys}


@router.post("/settings/api-keys/{key_id}/revoke")
async def revoke_api_key(
    key_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Revoke (deactivate) an API key"""
    key = await gd_find_one(db.session, "api_keys", {"id": key_id})
    if not key:
        raise HTTPException(status_code=404, detail="مفتاح API غير موجود")
    
    await gd_update_one(db.session, "api_keys", {"id": key_id}, {"is_active": False})
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "api_key_revoked",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "api_key",
        "target_id": key_id,
        "target_name": key.get("name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم إلغاء مفتاح API بنجاح"}


@router.delete("/settings/api-keys/{key_id}")
async def delete_api_key(
    key_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Delete an API key"""
    key = await gd_find_one(db.session, "api_keys", {"id": key_id})
    if not key:
        raise HTTPException(status_code=404, detail="مفتاح API غير موجود")
    
    await gd_delete_one(db.session, "api_keys", {"id": key_id})
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "api_key_deleted",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "api_key",
        "target_id": key_id,
        "target_name": key.get("name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم حذف مفتاح API بنجاح"}





# ============== INTEGRATIONS MANAGEMENT ROUTES ==============

class IntegrationCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    type: str  # government, payment, sms, email, storage, ai, other
    description: Optional[str] = None
    description_en: Optional[str] = None
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    webhook_url: Optional[str] = None
    config: Optional[dict] = None

class IntegrationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    name_en: Optional[str] = None
    type: str
    description: Optional[str] = None
    description_en: Optional[str] = None
    status: str
    api_base_url: Optional[str] = None
    last_sync: Optional[str] = None
    created_at: str

@router.post("/integrations", response_model=IntegrationResponse)
async def create_integration(
    data: IntegrationCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Create a new integration"""
    integration_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    integration_doc = {
        "id": integration_id,
        "name": data.name,
        "name_en": data.name_en,
        "type": data.type,
        "description": data.description,
        "description_en": data.description_en,
        "api_base_url": data.api_base_url,
        "api_key": _encrypt_api_key(data.api_key) if data.api_key else None,
        "webhook_url": data.webhook_url,
        "config": data.config or {},
        "status": "pending",
        "is_active": False,
        "created_at": now,
        "updated_at": now,
        "created_by": current_user["id"]
    }
    
    await gd_insert(db.session, "integrations", integration_doc)
    
    return IntegrationResponse(
        id=integration_id,
        name=data.name,
        name_en=data.name_en,
        type=data.type,
        description=data.description,
        description_en=data.description_en,
        status="pending",
        api_base_url=data.api_base_url,
        last_sync=None,
        created_at=now
    )

@router.get("/integrations")
async def get_integrations(
    type: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get all integrations"""
    query = {}
    if type:
        query["type"] = type
    if status:
        query["status"] = status
    
    integrations = await gd_find(db.session, "integrations", query, limit=100)
    
    return {"integrations": integrations}

@router.get("/integrations/{integration_id}")
async def get_integration(
    integration_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get integration details"""
    integration = await gd_find_one(db.session, "integrations", {"id": integration_id})
    if not integration:
        raise HTTPException(status_code=404, detail="التكامل غير موجود")
    return integration

@router.put("/integrations/{integration_id}")
async def update_integration(
    integration_id: str,
    data: IntegrationCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Update integration"""
    integration = await gd_find_one(db.session, "integrations", {"id": integration_id})
    if not integration:
        raise HTTPException(status_code=404, detail="التكامل غير موجود")
    
    updates = {
        "name": data.name,
        "name_en": data.name_en,
        "type": data.type,
        "description": data.description,
        "description_en": data.description_en,
        "api_base_url": data.api_base_url,
        "webhook_url": data.webhook_url,
        "config": data.config or {},
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    if data.api_key:
        updates["api_key"] = _encrypt_api_key(data.api_key)
    
    await gd_update_one(db.session, "integrations", {"id": integration_id}, updates)
    
    return {"message": "تم تحديث التكامل بنجاح"}

@router.post("/integrations/{integration_id}/toggle")
async def toggle_integration(
    integration_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Enable/disable integration"""
    integration = await gd_find_one(db.session, "integrations", {"id": integration_id})
    if not integration:
        raise HTTPException(status_code=404, detail="التكامل غير موجود")
    
    new_status = not integration.get("is_active", False)
    
    await gd_update_one(db.session, "integrations", {"id": integration_id}, {
            "is_active": new_status,
            "status": "active" if new_status else "inactive",
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    return {
        "message": "تم تفعيل التكامل" if new_status else "تم تعطيل التكامل",
        "is_active": new_status
    }

@router.post("/integrations/{integration_id}/test")
async def test_integration(
    integration_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Test integration connection"""
    integration = await gd_find_one(db.session, "integrations", {"id": integration_id})
    if not integration:
        raise HTTPException(status_code=404, detail="التكامل غير موجود")
    
    raise HTTPException(
        status_code=501,
        detail="اختبار الاتصال غير مُهيأ بعد لهذا التكامل"
    )

@router.post("/integrations/{integration_id}/sync")
async def sync_integration(
    integration_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Trigger data sync for integration"""
    integration = await gd_find_one(db.session, "integrations", {"id": integration_id})
    if not integration:
        raise HTTPException(status_code=404, detail="التكامل غير موجود")
    
    # Create sync log
    sync_log = {
        "id": str(uuid.uuid4()),
        "integration_id": integration_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "in_progress",
        "triggered_by": current_user["id"]
    }
    await gd_insert(db.session, "integration_sync_logs", sync_log)
    
    # Simulate sync completion
    await gd_update_one(db.session, "integrations", {"id": integration_id}, {
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "sync_status": "completed"
        })
    
    # Update sync log
    await gd_update_one(db.session, "integration_sync_logs", {"id": sync_log["id"]}, {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "records_synced": 0
        })
    
    return {"message": "تم المزامنة بنجاح", "sync_id": sync_log["id"]}

@router.get("/integrations/{integration_id}/logs")
async def get_integration_logs(
    integration_id: str,
    limit: int = 50,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get integration sync logs"""
    integration = await gd_find_one(db.session, "integrations", {"id": integration_id})
    if not integration:
        raise HTTPException(status_code=404, detail="التكامل غير موجود")
    
    logs = await gd_find(db.session, "integration_sync_logs", {"integration_id": integration_id}, order_by="started_at", desc_order=True, limit=limit)
    
    return {"logs": logs}

@router.delete("/integrations/{integration_id}")
async def delete_integration(
    integration_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Delete integration"""
    integration = await gd_find_one(db.session, "integrations", {"id": integration_id})
    if not integration:
        raise HTTPException(status_code=404, detail="التكامل غير موجود")
    
    await gd_delete_one(db.session, "integrations", {"id": integration_id})
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "integration_deleted",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "integration",
        "target_id": integration_id,
        "target_name": integration.get("name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم حذف التكامل بنجاح"}





# ============== PLATFORM CONTACT API (PUBLIC) ==============
import time as _time_pc
_public_contact_cache = {"data": None, "expires": 0}
_PUBLIC_CONTACT_TTL = 120  # seconds — contact info changes rarely


@router.get("/public/contact-info")
async def get_public_contact_info():
    """Get public contact information for landing page (no auth required)."""
    _now = _time_pc.monotonic()
    if _public_contact_cache["data"] and _now < _public_contact_cache["expires"]:
        try:
            from middleware.cache_metrics import record_hit
            record_hit()
        except Exception:
            pass
        return _public_contact_cache["data"]
    try:
        from middleware.cache_metrics import record_miss
        record_miss()
    except Exception:
        pass

    settings = await gd_find_one(db.session, "platform_settings", {"type": "platform"})

    if not settings:
        result = {
            "primary_email": "info@nassaqapp.com",
            "support_email": "support@nassaqapp.com",
            "primary_phone": "+966 11 234 5678",
            "address": "الرياض، المملكة العربية السعودية",
            "working_hours": "الأحد - الخميس: 8:00 ص - 4:00 م",
            "website": "https://nassaqapp.com",
            "owner_name": "شركة نَسَّق للتقنية التعليمية",
            "social_media": {
                "twitter": "",
                "facebook": "",
                "instagram": "",
                "linkedin": "",
                "youtube": ""
            }
        }
        _public_contact_cache["data"] = result
        _public_contact_cache["expires"] = _now + _PUBLIC_CONTACT_TTL
        return result

    contact = settings.get("contact", {})
    result = {
        "primary_email": contact.get("primary_email", "info@nassaqapp.com"),
        "support_email": contact.get("support_email", "support@nassaqapp.com"),
        "primary_phone": contact.get("primary_phone", "+966 11 234 5678"),
        "alternate_phone": contact.get("alternate_phone"),
        "address": contact.get("address", "الرياض، المملكة العربية السعودية"),
        "working_hours": contact.get("working_hours", "الأحد - الخميس: 8:00 ص - 4:00 م"),
        "website": contact.get("website", "https://nassaqapp.com"),
        "owner_name": contact.get("owner_name", "شركة نَسَّق للتقنية التعليمية"),
        "social_media": contact.get("social_media", {})
    }
    _public_contact_cache["data"] = result
    _public_contact_cache["expires"] = _now + _PUBLIC_CONTACT_TTL
    return result





# ============== SYSTEM RULES APIs ==============
@router.get("/system/rules")
async def get_system_rules(
    category: str = None,
    status: str = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get all system rules"""
    query = {}
    if category:
        query["category"] = category
    if status:
        query["status"] = status
    
    rules = await gd_find(db.session, "system_rules", query, limit=100)
    
    return {"rules": rules, "count": len(rules)}

@router.post("/system/rules")
async def create_system_rule(
    rule_data: dict,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Create a new system rule"""
    rule_id = f"rule_{uuid.uuid4().hex[:8]}"
    
    new_rule = {
        "id": rule_id,
        "name_ar": rule_data.get("name_ar"),
        "name_en": rule_data.get("name_en"),
        "description_ar": rule_data.get("description_ar"),
        "description_en": rule_data.get("description_en"),
        "category": rule_data.get("category", "general"),
        "type": rule_data.get("type", "text"),
        "value": rule_data.get("value"),
        "unit": rule_data.get("unit", ""),
        "status": rule_data.get("status", "draft"),
        "priority": rule_data.get("priority", "medium"),
        "applies_to": rule_data.get("applies_to", "all"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user.get("id"),
    }
    
    await gd_insert(db.session, "system_rules", new_rule)
    
    return {"success": True, "rule": {k: v for k, v in new_rule.items() if k != "_id"}}

@router.put("/system/rules/{rule_id}")
async def update_system_rule(
    rule_id: str,
    rule_data: dict,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Update a system rule"""
    existing = await gd_find_one(db.session, "system_rules", {"id": rule_id})
    if not existing:
        raise HTTPException(status_code=404, detail="القاعدة غير موجودة")
    
    update_data = {
        "name_ar": rule_data.get("name_ar", existing.get("name_ar")),
        "name_en": rule_data.get("name_en", existing.get("name_en")),
        "description_ar": rule_data.get("description_ar", existing.get("description_ar")),
        "description_en": rule_data.get("description_en", existing.get("description_en")),
        "category": rule_data.get("category", existing.get("category")),
        "type": rule_data.get("type", existing.get("type")),
        "value": rule_data.get("value", existing.get("value")),
        "unit": rule_data.get("unit", existing.get("unit")),
        "status": rule_data.get("status", existing.get("status")),
        "priority": rule_data.get("priority", existing.get("priority")),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": current_user.get("id"),
    }
    
    await gd_update_one(db.session, "system_rules", {"id": rule_id}, update_data)
    
    return {"success": True, "message": "تم تحديث القاعدة بنجاح"}

@router.delete("/system/rules/{rule_id}")
async def delete_system_rule(
    rule_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Delete a system rule"""
    result = await gd_delete_one(db.session, "system_rules", {"id": rule_id})
    
    if result == 0:
        raise HTTPException(status_code=404, detail="القاعدة غير موجودة")
    
    return {"success": True, "message": "تم حذف القاعدة بنجاح"}


# ============== PLATFORM SETTINGS ADDITIONAL ENDPOINTS ==============

# ============== PLATFORM SETTINGS ENDPOINTS ==============
@router.get("/settings/platform")
async def get_platform_settings(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get all platform settings"""
    settings = await gd_find_one(db.session, "platform_settings", {"type": "platform"})
    
    if not settings:
        # Return default settings
        default_settings = {
            "general": GeneralSettingsModel().model_dump(),
            "brand": BrandSettingsModel().model_dump(),
            "contact": ContactInfoModel().model_dump(),
            "terms": {
                "content": """الشروط والأحكام الخاصة باستخدام منصة نَسَّق التعليمية

1. مقدمة
مرحباً بكم في منصة نَسَّق التعليمية. باستخدامكم لهذه المنصة، فإنكم توافقون على الالتزام بهذه الشروط والأحكام.

2. التعريفات
- "المنصة": تشير إلى منصة نَسَّق الإلكترونية وجميع خدماتها.
- "المستخدم": أي شخص يستخدم المنصة بأي صفة.
- "المدرسة": المؤسسة التعليمية المشتركة في المنصة.

3. الاستخدام المقبول
يتعهد المستخدم بعدم استخدام المنصة لأي أغراض غير مشروعة أو محظورة.

4. الخصوصية وحماية البيانات
نلتزم بحماية بيانات المستخدمين وفقاً لسياسة الخصوصية المعمول بها.

5. حقوق الملكية الفكرية
جميع حقوق الملكية الفكرية للمنصة محفوظة لشركة نَسَّق.""",
                "version": "2.1",
                "effective_date": datetime.now(timezone.utc).isoformat()
            },
            "privacy": {
                "content": """سياسة الخصوصية لمنصة نَسَّق التعليمية

1. جمع المعلومات
نقوم بجمع المعلومات التي تقدمها لنا مباشرة عند:
- إنشاء حساب
- استخدام خدماتنا
- التواصل معنا

2. استخدام المعلومات
نستخدم المعلومات المجمعة لـ:
- تقديم وتحسين خدماتنا
- التواصل معكم
- ضمان أمان المنصة

3. مشاركة المعلومات
لا نشارك معلوماتكم الشخصية مع أطراف ثالثة إلا في الحالات التالية:
- بموافقتكم الصريحة
- للامتثال للقوانين
- لحماية حقوقنا

4. أمان البيانات
نستخدم تقنيات تشفير متقدمة لحماية بياناتكم.

5. حقوقكم
لديكم الحق في الوصول إلى بياناتكم وتصحيحها أو حذفها.""",
                "version": "2.0",
                "effective_date": datetime.now(timezone.utc).isoformat()
            },
            "security": SecuritySettingsModel().model_dump(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        return default_settings
    
    # Remove internal _id
    settings.pop("_id", None)
    settings.pop("type", None)
    return settings


@router.put("/settings/platform/general")
async def update_general_settings(
    settings: GeneralSettingsModel,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Update general platform settings"""
    update_data = {
        "general": settings.model_dump(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_upsert(db.session, "platform_settings", {"type": "platform"}, update_data)
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "settings_updated",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "platform_settings",
        "target_id": "general",
        "details": {"section": "general"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم تحديث الإعدادات العامة بنجاح", "settings": settings.model_dump()}


@router.put("/settings/platform/brand")
async def update_brand_settings(
    settings: BrandSettingsModel,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Update brand/identity settings"""
    update_data = {
        "brand": settings.model_dump(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_upsert(db.session, "platform_settings", {"type": "platform"}, update_data)
    
    return {"message": "تم تحديث إعدادات الهوية البصرية بنجاح", "settings": settings.model_dump()}


@router.put("/settings/platform/contact")
async def update_contact_settings(
    settings: ContactInfoModel,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Update contact information settings"""
    update_data = {
        "contact": settings.model_dump(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_upsert(db.session, "platform_settings", {"type": "platform"}, update_data)

    # Invalidate public contact-info cache so updates are reflected immediately.
    _public_contact_cache["data"] = None
    _public_contact_cache["expires"] = 0

    return {"message": "تم تحديث بيانات التواصل بنجاح", "settings": settings.model_dump()}


@router.put("/settings/platform/terms")
async def update_terms_settings(
    content: LegalContentModel,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Update terms and conditions"""
    # Save to version history
    version_history = {
        "id": str(uuid.uuid4()),
        "type": "terms",
        "content": content.content,
        "version": content.version,
        "effective_date": content.effective_date or datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"],
        "created_by_name": current_user.get("full_name", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "legal_versions", version_history)
    
    update_data = {
        "terms": {
            "content": content.content,
            "version": content.version,
            "effective_date": content.effective_date or datetime.now(timezone.utc).isoformat()
        },
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_upsert(db.session, "platform_settings", {"type": "platform"}, update_data)
    
    return {"message": "تم تحديث الشروط والأحكام بنجاح", "version": content.version}


@router.put("/settings/platform/privacy")
async def update_privacy_settings(
    content: LegalContentModel,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Update privacy policy"""
    # Save to version history
    version_history = {
        "id": str(uuid.uuid4()),
        "type": "privacy",
        "content": content.content,
        "version": content.version,
        "effective_date": content.effective_date or datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"],
        "created_by_name": current_user.get("full_name", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "legal_versions", version_history)
    
    update_data = {
        "privacy": {
            "content": content.content,
            "version": content.version,
            "effective_date": content.effective_date or datetime.now(timezone.utc).isoformat()
        },
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_upsert(db.session, "platform_settings", {"type": "platform"}, update_data)
    
    return {"message": "تم تحديث سياسة الخصوصية بنجاح", "version": content.version}


@router.put("/settings/platform/security")
async def update_security_settings(
    settings: SecuritySettingsModel,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Update security settings"""
    update_data = {
        "security": settings.model_dump(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_upsert(db.session, "platform_settings", {"type": "platform"}, update_data)
    
    return {"message": "تم تحديث إعدادات الأمان بنجاح", "settings": settings.model_dump()}


@router.get("/settings/legal-versions/{doc_type}")
async def get_legal_versions(
    doc_type: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get version history for terms or privacy"""
    if doc_type not in ["terms", "privacy"]:
        raise HTTPException(status_code=400, detail="نوع المستند غير صالح")
    
    versions = await gd_find(db.session, "legal_versions", {"type": doc_type}, order_by="created_at", desc_order=True, limit=100)
    
    return {"versions": versions}

