"""
NASSAQ Route Module: AI operations, Hakim AI chat and engine, insights
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64

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
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, _gd_aggregate


from shared_models import (
    HakimMessage, HakimResponse
)
from openai import OpenAI
from typing import Literal

router = APIRouter()

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")

def _ai_is_configured() -> bool:
    return bool(AI_INTEGRATIONS_OPENAI_API_KEY and AI_INTEGRATIONS_OPENAI_BASE_URL)

_openai_client = None
def get_openai_client():
    global _openai_client
    if not _ai_is_configured():
        return None
    if _openai_client is None:
        _openai_client = OpenAI(
            api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
            base_url=AI_INTEGRATIONS_OPENAI_BASE_URL,
        )
    return _openai_client

AI_NOT_CONFIGURED_RESPONSE = {
    "success": False,
    "error": "AI not configured",
    "error_ar": "خدمة الذكاء الاصطناعي غير مُهيّأة",
    "message": "AI features are unavailable. Please configure the OpenAI integration.",
    "message_ar": "ميزات الذكاء الاصطناعي غير متوفرة. يرجى إعداد تكامل OpenAI."
}

_hakim_sessions: Dict[str, list] = {}



# ============== AI OPERATIONS ==============
@router.post("/ai/diagnosis")
async def ai_system_diagnosis(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    """تشخيص النظام بالذكاء الاصطناعي"""
    # Gather system metrics
    total_schools = await gd_count(db.session, "schools", {})
    active_schools = await gd_count(db.session, "schools", {"status": "active"})
    total_users = await gd_count(db.session, "users", {})
    active_users = await gd_count(db.session, "users", {"is_active": True})
    
    # Calculate health score
    health_score = 100
    issues = []
    recommendations = []
    
    # Check for inactive schools
    inactive_schools = total_schools - active_schools
    if inactive_schools > 0:
        health_score -= min(10, inactive_schools * 2)
        issues.append(f"{inactive_schools} مدرسة غير نشطة")
    
    # Check for low active users ratio
    if total_users > 0:
        active_ratio = (active_users / total_users) * 100
        if active_ratio < 70:
            health_score -= 10
            issues.append(f"نسبة المستخدمين النشطين منخفضة ({active_ratio:.1f}%)")
            recommendations.append("مراجعة حسابات المستخدمين غير النشطين")
    
    # Check pending requests
    pending = await gd_count(db.session, "registration_requests", {"status": "pending"})
    if pending > 10:
        health_score -= 5
        issues.append(f"{pending} طلب تسجيل معلق")
        recommendations.append("مراجعة طلبات التسجيل المعلقة")
    
    return {
        "success": True,
        "message": "تم تشخيص النظام بنجاح" if health_score >= 80 else "يحتاج النظام إلى متابعة",
        "message_en": "System diagnosis completed",
        "health_score": max(0, health_score),
        "issues_found": len(issues),
        "recommendations": len(recommendations),
        "details": {
            "issues": issues,
            "recommendations": recommendations,
            "metrics": {
                "total_schools": total_schools,
                "active_schools": active_schools,
                "total_users": total_users,
                "active_users": active_users,
                "pending_requests": pending
            }
        }
    }

@router.post("/ai/data-quality")
async def ai_data_quality_scan(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    """فحص جودة البيانات"""
    issues = []
    
    # Check students with missing data
    students_missing_phone = await gd_count(db.session, "students", {
        "$or": [{"parent_phone": None}, {"parent_phone": ""}]
    })
    if students_missing_phone > 0:
        issues.append({"type": "missing_data", "entity": "students", "count": students_missing_phone, "field": "parent_phone"})
    
    # Check teachers without rank
    teachers_no_rank = await gd_count(db.session, "teachers", {
        "$or": [{"rank": None}, {"rank": ""}]
    })
    if teachers_no_rank > 0:
        issues.append({"type": "missing_data", "entity": "teachers", "count": teachers_no_rank, "field": "rank"})
    
    # Check classes without teachers
    classes_no_teacher = await gd_count(db.session, "classes", {
        "$or": [{"teacher_id": None}, {"teacher_id": ""}]
    })
    if classes_no_teacher > 0:
        issues.append({"type": "incomplete", "entity": "classes", "count": classes_no_teacher, "issue": "no_teacher"})
    
    total_students_count = await gd_count(db.session, "students", {})
    total_teachers_count = await gd_count(db.session, "teachers", {})
    total_classes_count = await gd_count(db.session, "classes", {})
    total_records = total_students_count + total_teachers_count + total_classes_count
    total_issues = sum(i.get("count", 0) for i in issues)
    quality_score = max(0, 100 - (total_issues / max(1, total_records) * 100))
    
    return {
        "success": True,
        "message": f"جودة البيانات: {quality_score:.1f}%",
        "message_en": f"Data Quality: {quality_score:.1f}%",
        "health_score": int(quality_score),
        "issues_found": len(issues),
        "recommendations": len(issues),
        "details": {
            "quality_score": quality_score,
            "issues": issues,
            "total_records": total_records,
            "records_with_issues": total_issues
        }
    }

@router.post("/ai/tenant-health")
async def ai_tenant_health_check(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    """فحص صحة المدارس"""
    schools = await gd_find(db.session, "schools", {}, limit=1000)
    
    healthy = []
    warning = []
    critical = []
    
    school_ids = [s.get("id") for s in schools if s.get("id")]
    
    student_pipeline = [
        {"$match": {"school_id": {"$in": school_ids}}},
        {"$group": {"_id": "$school_id", "count": {"$sum": 1}}}
    ]
    teacher_pipeline = [
        {"$match": {"school_id": {"$in": school_ids}}},
        {"$group": {"_id": "$school_id", "count": {"$sum": 1}}}
    ]
    class_pipeline = [
        {"$match": {"school_id": {"$in": school_ids}}},
        {"$group": {"_id": "$school_id", "count": {"$sum": 1}}}
    ]
    
    student_counts_raw = await _gd_aggregate(db.session, "students", student_pipeline)
    teacher_counts_raw = await _gd_aggregate(db.session, "teachers", teacher_pipeline)
    class_counts_raw = await _gd_aggregate(db.session, "classes", class_pipeline)
    
    student_counts = {r["_id"]: r["count"] for r in student_counts_raw}
    teacher_counts = {r["_id"]: r["count"] for r in teacher_counts_raw}
    class_counts = {r["_id"]: r["count"] for r in class_counts_raw}
    
    for school in schools:
        school_id = school.get("id")
        student_count = student_counts.get(school_id, 0)
        teacher_count = teacher_counts.get(school_id, 0)
        class_count = class_counts.get(school_id, 0)
        
        if school.get("status") == "suspended":
            critical.append({"id": school_id, "name": school.get("name"), "reason": "موقوفة"})
        elif student_count == 0 or teacher_count == 0:
            warning.append({"id": school_id, "name": school.get("name"), "reason": "بيانات ناقصة"})
        elif class_count == 0:
            warning.append({"id": school_id, "name": school.get("name"), "reason": "لا توجد فصول"})
        else:
            healthy.append({"id": school_id, "name": school.get("name")})
    
    return {
        "success": True,
        "message": f"تم فحص {len(schools)} مدرسة",
        "message_en": f"Checked {len(schools)} schools",
        "health_score": int(len(healthy) / max(1, len(schools)) * 100),
        "issues_found": len(warning) + len(critical),
        "recommendations": len(warning) + len(critical),
        "details": {
            "healthy": len(healthy),
            "warning": len(warning),
            "critical": len(critical),
            "schools_healthy": healthy[:5],
            "schools_warning": warning,
            "schools_critical": critical
        }
    }

@router.post("/ai/executive-summary")
async def ai_executive_summary(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    """الملخص التنفيذي الذكي"""
    # Gather all stats
    total_schools = await gd_count(db.session, "schools", {})
    active_schools = await gd_count(db.session, "schools", {"status": "active"})
    total_students = await gd_count(db.session, "students", {})
    total_teachers = await gd_count(db.session, "teachers", {})
    total_classes = await gd_count(db.session, "classes", {})
    pending_requests = await gd_count(db.session, "registration_requests", {"status": "pending"})
    
    # Today's activity
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_events = await gd_count(db.session, "events", {"created_at": {"$gte": today_start.isoformat()}})
    
    summary_ar = f"""ملخص تنفيذي لمنصة نَسَّق

📊 إحصائيات عامة:
• إجمالي المدارس: {total_schools} ({active_schools} نشطة)
• إجمالي الطلاب: {total_students:,}
• إجمالي المعلمين: {total_teachers:,}
• إجمالي الفصول: {total_classes:,}

📈 نشاط اليوم:
• عدد العمليات: {today_events:,}

⚠️ يتطلب اهتمام:
• طلبات تسجيل معلقة: {pending_requests}

التوصيات:
{"• مراجعة طلبات التسجيل المعلقة" if pending_requests > 0 else "• لا توجد إجراءات مطلوبة حالياً"}
"""
    
    return {
        "success": True,
        "message": "تم إنشاء الملخص التنفيذي",
        "message_en": "Executive summary generated",
        "details": {
            "summary_ar": summary_ar,
            "summary_en": f"Platform Summary: {total_schools} schools, {total_students:,} students, {total_teachers:,} teachers",
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    }




# ============== AI ASSISTANT (HAKIM) ==============

class HakimContextualRequest(BaseModel):
    page: str
    role: str
    context_data: Optional[Dict[str, Any]] = None
    tenant_id: Optional[str] = None
    language: Optional[str] = "ar"

@router.post("/hakim/contextual-message")
async def hakim_contextual_message(req: HakimContextualRequest, current_user: dict = Depends(get_current_user)):
    try:
        client = get_openai_client()
        if client is None:
            return JSONResponse(status_code=503, content=AI_NOT_CONFIGURED_RESPONSE)

        school_id = current_user.get("tenant_id") or req.tenant_id
        school_context = ""
        if school_id:
            school = await gd_find_one(db.session, "schools", {"id": school_id})
            school_name = (school.get("name_ar") or school.get("name", "")) if school else ""
            if school_name:
                school_context = f"\nاسم المدرسة: {school_name}"

        context_str = ""
        if req.context_data:
            parts = []
            for k, v in req.context_data.items():
                parts.append(f"- {k}: {v}")
            context_str = "\nبيانات السياق:\n" + "\n".join(parts)

        page_map = {
            "/teacher/home": "الصفحة الرئيسية للمعلم",
            "/teacher/classes": "فصول المعلم",
            "/teacher/achievements": "إنجازات المعلم",
            "/teacher/reports": "تقارير وتحليلات المعلم",
            "/teacher/communication": "مركز التواصل",
            "/teacher/schedule": "الجدول الدراسي للمعلم",
            "/teacher/assessments": "اختبارات وتقييمات المعلم",
            "/teacher/attendance": "حضور الطلاب",
            "/teacher/behavior": "سلوك الطلاب",
            "/teacher/session/start": "بدء حصة جديدة",
            "/teacher/session/teach": "داخل الحصة",
            "/school/dashboard": "لوحة تحكم المدرسة",
            "/school/schedule": "الجدول المدرسي",
            "/school/ai-insights": "رؤى الذكاء الاصطناعي",
            "/student/dashboard": "لوحة الطالب",
            "/parent/dashboard": "لوحة ولي الأمر",
            "/notifications": "مركز الإشعارات",
        }
        page_name = page_map.get(req.page, req.page)

        role_map = {
            "teacher": "معلم",
            "school_principal": "مدير مدرسة",
            "school_admin": "مشرف إداري",
            "student": "طالب",
            "parent": "ولي أمر",
            "platform_admin": "مدير المنصة",
        }
        role_name = role_map.get(req.role, req.role)

        lang_instruction = "أجب باللغة العربية الفصحى." if req.language == "ar" else "Answer in English."

        system_prompt = f"""أنت حكيم، المساعد الذكي لمنصة نَسَّق التعليمية.
مهمتك: أنتج رسالة ترحيب/توجيه قصيرة جداً (جملة أو جملتين فقط) مناسبة للسياق الحالي.

القواعد:
1. الرسالة يجب أن تكون قصيرة جداً (أقصى 20 كلمة)
2. يجب أن تكون ذات صلة مباشرة بالصفحة والدور الحالي
3. استخدم أسلوب ودود ومحفز
4. لا تكرر نفس العبارات العامة
5. إذا توفرت بيانات سياقية، استخدمها لتخصيص الرسالة
6. {lang_instruction}

المستخدم الحالي: {role_name}
الصفحة: {page_name}{school_context}{context_str}

أنتج رسالة واحدة فقط بدون أي تنسيق أو رموز إضافية."""

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}],
            max_tokens=80,
            temperature=0.8,
        )
        message = response.choices[0].message.content.strip()
        message = message.strip('"').strip("'").strip()

        return {"message": message, "page": req.page, "role": req.role}
    except Exception as e:
        logger.error(f"Hakim contextual message error: {e}")
        fallback_messages = {
            "teacher": "مرحبًا أستاذ… أنا هنا لمساعدتك.",
            "student": "أهلاً… أنا حكيم، مساعدك الذكي!",
            "parent": "مرحبًا ولي الأمر… أنا حكيم.",
            "school_principal": "مرحبًا… إليك آخر المستجدات.",
        }
        return {"message": fallback_messages.get(req.role, "مرحبًا… أنا حكيم."), "page": req.page, "role": req.role}


class HakimChatRequest(BaseModel):
    message: str
    context: Optional[str] = None
    user_role: Optional[str] = None
    tenant_id: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None
    session_id: Optional[str] = None
    current_page: Optional[str] = None
    child_id: Optional[str] = None


async def _verify_parent_child_access(parent_user_id: str, child_id: str) -> bool:
    link = await gd_find_one(db.session, "guardian_links", {
        "parent_ref": parent_user_id, "student_id": child_id, "is_active": True
    })
    if link:
        return True
    student = await gd_find_one(db.session, "students", {"id": child_id})
    if student and (student.get("parent_id") == parent_user_id or student.get("parent_user_id") == parent_user_id):
        return True
    return False


async def _resolve_parent_linked_children(parent_user_id: str, school_id: str) -> List[Dict[str, Any]]:
    """
    Return the strict allow-list of students this parent may access.
    Combines `guardian_links` (active) with the legacy `students.parent_id`
    fallback. Always re-filtered by `school_id` (tenant) to prevent any
    cross-tenant leakage even if a stale link exists.
    """
    children: Dict[str, Dict[str, Any]] = {}

    # 1) Active guardian links — primary source of truth.
    link_query: Dict[str, Any] = {"parent_ref": parent_user_id, "is_active": True}
    if school_id:
        link_query["tenant_id"] = school_id
    links = await gd_find(db.session, "guardian_links", link_query, limit=100)
    student_ids_from_links = [l.get("student_id") for l in links if l.get("student_id")]

    if student_ids_from_links:
        student_query: Dict[str, Any] = {"id": {"$in": student_ids_from_links}}
        if school_id:
            student_query["school_id"] = school_id
        for s in await gd_find(db.session, "students", student_query, limit=100):
            children[s["id"]] = s

    # 2) Legacy fallback on the students table.
    legacy_query: Dict[str, Any] = {
        "$or": [{"parent_id": parent_user_id}, {"parent_user_id": parent_user_id}]
    }
    if school_id:
        legacy_query["school_id"] = school_id
    for s in await gd_find(db.session, "students", legacy_query, limit=100):
        children.setdefault(s["id"], s)

    return list(children.values())


async def _build_parent_child_context(child_id: str, school_id: str) -> str:
    # SECURITY: scope the lookup itself by tenant so a stale/cross-tenant
    # student id can never be hydrated, regardless of the allow-list path.
    query: Dict[str, Any] = {"id": child_id}
    if school_id:
        query["school_id"] = school_id
    student = await gd_find_one(db.session, "students", query)
    if not student:
        return ""

    student_name = student.get("full_name", "الطالب")
    class_id = student.get("class_id", "")
    # Hard-pin to the authenticated tenant — no fallback to record-supplied id.
    sid = school_id or student.get("school_id", "")

    cls = await gd_find_one(db.session, "classes", {"id": class_id, "school_id": sid}) if class_id else None
    class_name = cls.get("name", "") if cls else ""

    cutoff_30 = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    cutoff_90 = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")

    att_total = await gd_count(db.session, "attendance", {
        "student_id": child_id, "school_id": sid, "date": {"$gte": cutoff_30}
    })
    att_present = await gd_count(db.session, "attendance", {
        "student_id": child_id, "school_id": sid, "date": {"$gte": cutoff_30},
        "status": {"$in": ["present", "late"]}
    })
    att_absent = await gd_count(db.session, "attendance", {
        "student_id": child_id, "school_id": sid, "date": {"$gte": cutoff_30},
        "status": "absent"
    })
    att_rate = round((att_present / att_total) * 100, 1) if att_total > 0 else None

    grades = await gd_find(db.session, "student_grades", {
        "student_id": child_id, "tenant_id": sid
    }, order_by="graded_at", desc_order=True, limit=50)

    grades_text = ""
    if grades:
        subject_grades: Dict[str, list] = {}
        for g in grades:
            subj = g.get("subject_name") or g.get("subject_id", "غير محدد")
            if subj not in subject_grades:
                subject_grades[subj] = []
            subject_grades[subj].append(g.get("percentage", 0))

        grade_lines = []
        for subj, pcts in subject_grades.items():
            avg = round(sum(pcts) / len(pcts), 1)
            latest = pcts[0]
            grade_lines.append(f"  - {subj}: أحدث درجة {latest}%، متوسط {avg}%")
        grades_text = "\n".join(grade_lines)

        all_avg = round(sum(g.get("percentage", 0) for g in grades) / len(grades), 1)
        grades_text = f"المعدل العام: {all_avg}%\n" + grades_text

    daily_scores = await gd_find(db.session, "student_daily_scores", {
        "student_id": child_id, "school_id": sid, "date": {"$gte": cutoff_30}
    }, limit=100)
    daily_avg = None
    if daily_scores:
        total_s = sum(s.get("score", 0) for s in daily_scores)
        max_s = len(daily_scores) * 5
        daily_avg = round((total_s / max_s) * 100, 1) if max_s > 0 else None

    session_ids_raw = await gd_find(db.session, "class_sessions", {
        "school_id": sid, "status": "completed", "date": {"$gte": cutoff_30}
    }, limit=5000)
    session_ids = [s["id"] for s in session_ids_raw]

    behaviour_interactions = []
    if session_ids:
        behaviour_interactions = await gd_find(db.session, "session_interactions", {
            "student_id": child_id, "interaction_type": "behaviour",
            "session_id": {"$in": session_ids}
        }, limit=200)

    behaviour_records = await gd_find(db.session, "behaviour_records", {
        "student_id": child_id, "tenant_id": sid, "incident_date": {"$gte": cutoff_90}
    }, limit=100)

    positive_b = 0
    negative_b = 0
    behaviour_notes = []

    for inter in behaviour_interactions:
        bcat = inter.get("behaviour_category", inter.get("behaviour_type", ""))
        if bcat in ("positive", "respect", "teamwork"):
            positive_b += 1
        elif bcat in ("negative", "disruption"):
            negative_b += 1

    for rec in behaviour_records:
        cat = rec.get("category", "")
        if cat == "positive":
            positive_b += 1
        elif cat == "negative":
            negative_b += 1
        note = rec.get("description") or rec.get("behaviour_type_name", "")
        if note:
            behaviour_notes.append(note)

    weaknesses = []
    strengths = []
    if att_rate is not None:
        if att_rate < 80:
            weaknesses.append(f"انخفاض الحضور ({att_rate}%)")
        else:
            strengths.append(f"حضور جيد ({att_rate}%)")

    if grades:
        all_avg_val = sum(g.get("percentage", 0) for g in grades) / len(grades)
        if all_avg_val < 60:
            weaknesses.append(f"ضعف في التحصيل الأكاديمي (معدل {round(all_avg_val, 1)}%)")
        elif all_avg_val >= 85:
            strengths.append(f"تحصيل أكاديمي ممتاز (معدل {round(all_avg_val, 1)}%)")

        low_subjects = []
        for subj, pcts in subject_grades.items():
            subj_avg = sum(pcts) / len(pcts)
            if subj_avg < 60:
                low_subjects.append(f"{subj} ({round(subj_avg, 1)}%)")
        if low_subjects:
            weaknesses.append(f"مواد تحتاج تحسين: {', '.join(low_subjects)}")

    if negative_b > positive_b and negative_b > 3:
        weaknesses.append(f"ملاحظات سلوكية سلبية ({negative_b} سلبية مقابل {positive_b} إيجابية)")
    elif positive_b > 0 and positive_b >= negative_b * 2:
        strengths.append("سلوك إيجابي ومتميز")

    context_parts = [f"""
--- بيانات الطالب: {student_name} ---
الفصل: {class_name}"""]

    if att_rate is not None:
        context_parts.append(f"""
📊 الحضور (آخر 30 يوم):
- نسبة الحضور: {att_rate}%
- أيام الغياب: {att_absent} من أصل {att_total}""")

    if grades_text:
        context_parts.append(f"""
📝 الدرجات والتقييمات:
{grades_text}""")

    if daily_avg is not None:
        context_parts.append(f"- متوسط التقييم اليومي: {daily_avg}%")

    if positive_b > 0 or negative_b > 0:
        context_parts.append(f"""
🎯 السلوك:
- ملاحظات إيجابية: {positive_b}
- ملاحظات سلبية: {negative_b}""")
        if behaviour_notes:
            recent_notes = behaviour_notes[:5]
            context_parts.append("- أحدث الملاحظات: " + " | ".join(recent_notes))

    if strengths:
        context_parts.append("\n✅ نقاط القوة: " + "، ".join(strengths))
    if weaknesses:
        context_parts.append("\n⚠️ نقاط تحتاج اهتمام: " + "، ".join(weaknesses))

    return "\n".join(context_parts)


@router.post("/hakim/chat", response_model=HakimResponse)
async def chat_with_hakim(message: HakimChatRequest, current_user: dict = Depends(get_current_user)):
    try:
        client = get_openai_client()
        if client is None:
            return JSONResponse(status_code=503, content=AI_NOT_CONFIGURED_RESPONSE)

        school_id = current_user.get("tenant_id") or message.tenant_id
        # Trust the server-side role over anything the client claims; only fall
        # back to the request's `user_role` when the auth payload omits it.
        user_role = current_user.get("role") or (message.user_role or "unknown")
        is_parent = user_role == "parent" or message.context == "parent_portal"

        child_context = ""
        allowed_students: List[Dict[str, Any]] = []

        if is_parent:
            parent_user_id = current_user.get("id", "")

            # Always resolve the parent's full allow-list — used both for
            # validating any requested child_id AND for the AI scope guard.
            allowed_students = await _resolve_parent_linked_children(parent_user_id, school_id or "")
            allowed_ids = {s["id"] for s in allowed_students}

            # Graceful "no linked students" path — never let the AI hallucinate.
            if not allowed_students:
                return HakimResponse(
                    response=(
                        "مرحباً! أنا **حكيم** 🌟\n\n"
                        "لم أعثر على أي طالب مرتبط بحسابك حالياً. لذلك لا يمكنني عرض بيانات أكاديمية مخصصة. "
                        "يرجى التواصل مع إدارة المدرسة لربط حساب ولي الأمر بأبنائك."
                    ),
                    suggestions=["كيف أربط ابني بحسابي؟", "ما هي ميزات بوابة ولي الأمر؟"],
                )

            # If a specific child was requested, it MUST be inside the allow-list.
            if message.child_id:
                if message.child_id not in allowed_ids:
                    raise HTTPException(
                        status_code=403,
                        detail="ليس لديك صلاحية الوصول إلى بيانات هذا الطالب",
                    )
                child_context = await _build_parent_child_context(message.child_id, school_id or "")
            elif len(allowed_students) == 1:
                # Exactly one linked child — auto-scope without nagging the parent.
                only_child = allowed_students[0]
                child_context = await _build_parent_child_context(only_child["id"], school_id or "")

        school_context = ""
        if school_id and not is_parent:
            school = await gd_find_one(db.session, "schools", {"id": school_id})
            total_students = await gd_count(db.session, "students", {"school_id": school_id})
            total_teachers = await gd_count(db.session, "teachers", {"school_id": school_id})
            total_classes = await gd_count(db.session, "classes", {"school_id": school_id})
            attendance_query = {"school_id": school_id}
            total_att = await gd_count(db.session, "attendance", attendance_query)
            present_att = await gd_count(db.session, "attendance", {**attendance_query, "status": "present"})
            att_rate = round((present_att / total_att) * 100, 1) if total_att > 0 else 0
            school_name = (school.get("name_ar") or school.get("name", "")) if school else ""
            school_context = f"""
بيانات المدرسة الحالية ({school_name}):
- عدد الطلاب: {total_students}
- عدد المعلمين: {total_teachers}
- عدد الفصول: {total_classes}
- نسبة الحضور العامة: {att_rate}%"""

        page_context = ""
        if message.current_page:
            page_map = {
                "/school/dashboard": "مركز القيادة - لوحة التحكم الرئيسية للمدير",
                "/school/schedule": "الجدول الدراسي - إنشاء وإدارة الجداول",
                "/school/assessments": "الاختبارات والتقييمات - إدارة الاختبارات والدرجات",
                "/school/communication": "مركز التواصل والإشعارات",
                "/school/ai-insights": "رؤى الذكاء الاصطناعي - التحليلات والتنبؤات",
                "/admin/attendance": "إدارة الحضور والغياب",
                "/admin/students": "إدارة الطلاب",
                "/admin/teachers": "إدارة المعلمين",
                "/admin/users-management": "إدارة المستخدمين",
                "/admin/classes": "إدارة الفصول",
            }
            page_name = page_map.get(message.current_page, message.current_page)
            page_context = f"\nالمستخدم حالياً في صفحة: {page_name}"

        if is_parent:
            allowed_lines = "\n".join(
                f"- {s.get('full_name', 'طالب')} (المعرّف: {s['id']})"
                for s in allowed_students
            )
            scope_block = f"""
## نطاق الوصول الصارم (مهم جداً — قاعدة أمنية لا تُخالف):
- يُسمح لك حصراً بمناقشة الطلاب التاليين المرتبطين رسمياً بهذا ولي الأمر:
{allowed_lines}
- إذا سأل ولي الأمر عن أي طالب آخر بالاسم أو بأي معرّف غير مذكور أعلاه، يجب أن تعتذر بأدب وتوضّح أنك مخوّل فقط بمناقشة أبنائه المرتبطين بحسابه.
- لا تذكر أي بيانات تخص طلاباً آخرين، ولا تقارن بأسماء طلاب آخرين، ولا تكشف عن أي معلومة من خارج هذا النطاق.
- استخدم فقط البيانات الفعلية المُرفقة أدناه. لا تخترع درجات أو إحصاءات أو أحداثاً.
"""

            system_prompt = f"""أنت حكيم، المساعد الذكي لأولياء الأمور في منصة نَسَّق التعليمية.
مهمتك مساعدة ولي الأمر في فهم أداء ابنه/ابنته الدراسي وتقديم نصائح تربوية مخصصة.

## قواعد مهمة:
1. أجب دائماً باللغة العربية الفصحى بأسلوب ودود ومطمئن
2. استند في إجاباتك على بيانات الطالب الفعلية المتوفرة أدناه
3. قدم نصائح عملية وواقعية يمكن لولي الأمر تطبيقها في المنزل
4. استخدم Markdown للتنسيق (عناوين ##، قوائم -، نص **عريض**)
5. استخدم الرموز التعبيرية بشكل مناسب (📊 📝 ✅ ⚠️ 🎯 💡 📈)
6. اجعل الرد مختصراً ومفيداً
7. لا تخترع بيانات غير موجودة — إذا لم تتوفر معلومة، أوضح ذلك
8. عند الإشارة لنقاط ضعف، قدمها بأسلوب إيجابي مع اقتراحات التحسين

## خبراتك:
- تحليل أداء الطلاب الأكاديمي وتقديم توصيات
- تفسير الدرجات ومؤشرات الحضور لولي الأمر
- اقتراح أساليب تربوية لتحسين أداء الطالب
- تقديم نصائح حول المتابعة المنزلية
- شرح السلوكيات المدرسية وكيفية التعامل معها

{child_context}

{scope_block}

دور المستخدم: ولي أمر"""
        else:
            nav_links = """
روابط صفحات النظام المتاحة (استخدمها عند التوجيه):
- مركز القيادة: /school/dashboard
- الجدول الدراسي: /school/schedule
- الاختبارات والتقييمات: /school/assessments
- مركز التواصل: /school/communication
- رؤى الذكاء الاصطناعي: /school/ai-insights
- إدارة الحضور: /admin/attendance
- إدارة الطلاب: /admin/students
- إدارة المعلمين: /admin/teachers
- إدارة الفصول: /admin/classes
- إدارة المستخدمين: /admin/users-management
- التقارير: /admin/reports"""

            system_prompt = f"""أنت حكيم، المساعد الذكي الرسمي لمنصة نَسَّق لإدارة المدارس.
أنت خبير في الشؤون التعليمية والإدارية المدرسية.

## قواعد تنسيق الرد (مهمة جداً):
1. **نسّق ردك دائماً باستخدام Markdown** (عناوين ##، قوائم -، نص **عريض**، إلخ)
2. **اجعل الرد منظماً بصرياً** بأقسام واضحة وعناوين فرعية عند الحاجة
3. **أضف روابط تنقل** عند الإشارة لصفحات النظام بهذا الشكل: [اسم الصفحة](/المسار)
   مثال: [الجدول الدراسي](/school/schedule) أو [إدارة الحضور](/admin/attendance)
4. **استخدم الرموز التعبيرية** بشكل مناسب (📊 📅 👨‍🎓 ✅ ⚠️ 📝 🏫 📈 🎯) لتحسين القراءة
5. **اجعل الرد مختصراً ومفيداً** - لا تكرر ولا تطيل بلا فائدة
6. **عند تقديم بيانات رقمية** استخدم جداول أو قوائم منظمة
7. **عند تقديم خطوات** رقّمها بوضوح
{nav_links}

## مهمتك:
- مساعدة المستخدمين في فهم النظام وميزاته
- الإجابة على الأسئلة المتعلقة بإدارة المدارس
- تقديم توصيات ذكية بناءً على البيانات المتاحة
- توجيه المستخدم للصفحات المناسبة مع روابط مباشرة
- تحليل البيانات وتقديم رؤى مفيدة

## خبراتك:
- إنشاء جداول دراسية متوازنة ومحسّنة
- توزيع الحصص على المعلمين بشكل عادل
- تحليل الحضور والغياب وأنماطهما
- تقييم أداء الطلاب والمعلمين

## أسلوبك:
- ودود ومهني وراقٍ
- واضح ومنظم بصرياً
- تستخدم اللغة العربية الفصحى
- تقدم إجابات عملية مع روابط مباشرة للصفحات ذات الصلة
{school_context}{page_context}
دور المستخدم الحالي: {user_role}"""

        user_id = current_user.get('id', 'anon')
        if is_parent:
            # SECURITY: never honor a client-supplied session_id for parents.
            # Force a server-derived key so a parent cannot hop into another
            # parent's (or another child's) conversation history.
            session_child = message.child_id or (allowed_students[0]["id"] if len(allowed_students) == 1 else "all")
            session_key = f"hakim_{user_id}_{session_child}"
        else:
            session_key = message.session_id or f"hakim_{user_id}"

        messages_list = [{"role": "system", "content": system_prompt}]

        if session_key in _hakim_sessions:
            messages_list.extend(_hakim_sessions[session_key][-20:])

        if message.conversation_history:
            for msg in message.conversation_history[-10:]:
                role = msg.get("role", "user")
                if role in ("user", "assistant"):
                    messages_list.append({"role": role, "content": msg.get("content", "")})

        context_info = ""
        if message.context:
            context_info = f"\n\n[سياق إضافي: {message.context}]"

        user_content = message.message + context_info
        messages_list.append({"role": "user", "content": user_content})

        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=messages_list,
            max_completion_tokens=8192,
        )

        reply = response.choices[0].message.content or ""

        if session_key not in _hakim_sessions:
            _hakim_sessions[session_key] = []
        _hakim_sessions[session_key].append({"role": "user", "content": user_content})
        _hakim_sessions[session_key].append({"role": "assistant", "content": reply})
        if len(_hakim_sessions[session_key]) > 40:
            _hakim_sessions[session_key] = _hakim_sessions[session_key][-30:]

        suggestions = _generate_hakim_suggestions(message.message, is_parent=is_parent)

        return HakimResponse(response=reply, suggestions=suggestions)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Hakim LLM error: {str(e)}")
        return _hakim_fallback(message.message)


def _generate_hakim_suggestions(msg: str, is_parent: bool = False) -> list:
    msg_lower = msg.lower()
    if is_parent:
        if "رياضيات" in msg or "حساب" in msg or "math" in msg_lower:
            return ["كيف أساعده في الرياضيات؟", "ما هي درجاته في الرياضيات؟", "أنشطة تقوية منزلية"]
        elif "درجات" in msg or "نتائج" in msg or "علامات" in msg:
            return ["ما هي درجاته الأخيرة؟", "أي المواد يحتاج تحسين؟", "كيف أتابع أداءه؟"]
        elif "حضور" in msg or "غياب" in msg:
            return ["كم يوم تغيّب؟", "كيف أحسّن انتظامه؟", "ما تأثير الغياب على أدائه؟"]
        elif "سلوك" in msg or "تصرف" in msg:
            return ["كيف سلوكه في المدرسة؟", "نصائح لتحسين السلوك", "كيف أتواصل مع المعلم؟"]
        elif "ضعف" in msg or "مشكلة" in msg or "صعوبة" in msg:
            return ["ما نقاط الضعف لديه؟", "خطة تحسين منزلية", "هل يحتاج دروس تقوية؟"]
        return ["كيف أداء ابني الدراسي؟", "ما نقاط القوة والضعف؟", "نصائح للمتابعة المنزلية"]
    if "جدول" in msg or "schedule" in msg_lower:
        return ["إنشاء جدول جديد", "توليد جدول تلقائي", "كشف التعارضات"]
    elif "حصة" in msg or "حصص" in msg:
        return ["إضافة حصة", "نقل حصة", "عرض الجدول"]
    elif "تعارض" in msg or "conflict" in msg_lower:
        return ["عرض التعارضات", "حل التعارضات", "اقتراحات الإصلاح"]
    elif "معلم" in msg or "teacher" in msg_lower:
        return ["جدول المعلم", "نصاب المعلم", "توفر المعلم"]
    elif "طالب" in msg or "student" in msg_lower:
        return ["سجلات الطلاب", "تقارير الحضور", "تقييم الأداء"]
    elif "حضور" in msg or "attendance" in msg_lower:
        return ["تسجيل الحضور", "تقرير الحضور", "إشعارات الغياب"]
    elif "تقرير" in msg or "report" in msg_lower:
        return ["تقارير الحضور", "تقارير الأداء", "تصدير التقارير"]
    elif "اختبار" in msg or "تقييم" in msg or "درجات" in msg:
        return ["إنشاء اختبار", "تسجيل الدرجات", "تقارير الدرجات"]
    elif "سلوك" in msg or "behaviour" in msg_lower:
        return ["تسجيل ملاحظة سلوكية", "تقرير السلوك", "خطة تحسين"]
    return ["إدارة الجداول", "تقارير وتحليلات", "إدارة الطلاب"]


def _hakim_fallback(msg: str) -> HakimResponse:
    return HakimResponse(
        response="مرحباً! أنا حكيم، مساعدك الذكي في منصة نَسَّق لإدارة المدارس. يمكنني مساعدتك في:\n\n📅 **إدارة الجداول** — إنشاء وتعديل الجداول الدراسية\n🏫 **إدارة المدارس** — المستخدمين والصلاحيات\n📊 **التقارير** — الحضور والأداء والتحليلات\n📝 **التقييم** — الاختبارات والدرجات\n👨‍🎓 **شؤون الطلاب** — السلوك والمتابعة\n\nكيف يمكنني مساعدتك؟",
        suggestions=_generate_hakim_suggestions(msg),
    )




# ============== AI INSIGHTS APIs ==============

# --- AI Insights authorization sentinel (Task #154 / H1) ---------------------
#
# Tri-state contract used by every AI Insights endpoint:
#   * None                   -> caller is NOT a teacher-class role; continue
#                               on the existing principal / school-wide path.
#   * NO_AUTHORIZED_SCOPE    -> caller IS a teacher-class role and is
#                               authorized in principle, but has no resolvable
#                               owned/assigned records. Endpoint must return
#                               the documented empty-shape payload.
#   * dict                   -> populated scope; use _scope_query_for only.
#
# Authorization-resolution failures must surface as a controlled 403 with a
# safe Arabic message — never as an empty 200.
class _NoAuthorizedScopeType:
    """Sentinel for the NO_AUTHORIZED_SCOPE tri-state value."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "NO_AUTHORIZED_SCOPE"

    def __bool__(self) -> bool:
        return False


NO_AUTHORIZED_SCOPE = _NoAuthorizedScopeType()

_AI_INSIGHTS_SCOPE_DENIED_AR = "تعذّر التحقق من صلاحياتك للوصول إلى هذه البيانات"

_TEACHER_CLASS_ROLES = {
    UserRole.TEACHER.value,
    UserRole.INDEPENDENT_TEACHER.value,
}


def _empty_insights_overview() -> Dict[str, Any]:
    """Documented empty-shape payload for /ai/insights/overview.

    Schema parity with the populated response: every key/nested-key the
    populated path returns is present here with a zeroed/empty value.
    """
    return {
        "overall_score": 0,
        "trend": "flat",
        "trend_value": 0,
        "has_data": False,
        "score_available": False,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "attendance_rate": 0,
            "engagement_rate": 0,
            "student_teacher_ratio": 0,
            "total_students": 0,
            "total_teachers": 0,
            "has_attendance_data": False,
            "previous_month_score": 0,
        },
    }


async def resolve_ai_insights_scope(current_user: dict):
    """Single entry point for AI Insights scope resolution.

    Returns one of:
      * None                  -> non-teacher-class caller (principal/admin).
      * NO_AUTHORIZED_SCOPE   -> teacher-class caller with no owned data.
      * dict                  -> populated scope { school_id, class_ids,
                                  student_ids, teacher_id }.

    Raises HTTPException(403, safe Arabic) on any internal failure so a
    resolution error never silently degrades into an unscoped 200.
    """
    role = current_user.get("role", "")
    if role not in _TEACHER_CLASS_ROLES:
        return None

    try:
        if role == UserRole.INDEPENDENT_TEACHER.value:
            from auth_scope import independent_workspace_id as _itw_id
            workspace_id = _itw_id(current_user)
            if not workspace_id:
                raise HTTPException(403, _AI_INSIGHTS_SCOPE_DENIED_AR)
            workspace = await gd_find_one(db.session, "schools", {"id": workspace_id})
            if not workspace:
                # Authorization-resolution failure: the caller's workspace
                # could not be resolved at all. AI Insights is read-only and
                # must NOT lazy-create; fail closed with safe Arabic 403
                # rather than degrade into a silent empty 200 (which masks
                # real ACL/provisioning failures from monitoring).
                raise HTTPException(403, _AI_INSIGHTS_SCOPE_DENIED_AR)

            classes = await gd_find(db.session, "classes", {
                "school_id": workspace_id,
            }, limit=200)
            class_ids = [c.get("id") for c in classes if c.get("id")]

            student_filter: Dict[str, Any] = {
                "school_id": workspace_id,
                "is_active": True,
            }
            if class_ids:
                student_filter["class_id"] = {"$in": class_ids}
            students = await gd_find(db.session, "students", student_filter, limit=2000)
            student_ids = [s.get("id") for s in students if s.get("id")]

            if not class_ids and not student_ids:
                return NO_AUTHORIZED_SCOPE

            return {
                "teacher_id": current_user.get("teacher_id") or current_user.get("id"),
                "school_id": workspace_id,
                "class_ids": class_ids,
                "student_ids": student_ids,
            }

        # role == TEACHER (school-affiliated)
        teacher_id = current_user.get("teacher_id")
        school_id = current_user.get("tenant_id")
        if not teacher_id or not school_id:
            # Authorization-resolution failure: a school teacher with no
            # teacher_id or tenant_id on the token cannot have their scope
            # determined. Fail closed with safe Arabic 403 instead of
            # masking the failure as an empty 200 (which would be
            # indistinguishable from "authorized but no records").
            raise HTTPException(403, _AI_INSIGHTS_SCOPE_DENIED_AR)

        assignments = await gd_find(db.session, "teacher_assignments", {
            "teacher_id": teacher_id, "is_active": True,
        }, limit=200)
        tca_docs = await gd_find(db.session, "teacher_class_assignments", {
            "teacher_id": teacher_id,
        }, limit=200)
        class_ids = list({
            *(a.get("class_id") for a in assignments if a.get("class_id")),
            *(d.get("class_id") for d in tca_docs if d.get("class_id")),
        })

        student_ids: List[str] = []
        if class_ids:
            students = await gd_find(db.session, "students", {
                "school_id": school_id,
                "class_id": {"$in": class_ids},
                "is_active": True,
            }, limit=2000)
            student_ids = [s.get("id") for s in students if s.get("id")]

        if not class_ids and not student_ids:
            return NO_AUTHORIZED_SCOPE

        return {
            "teacher_id": teacher_id,
            "school_id": school_id,
            "class_ids": class_ids,
            "student_ids": student_ids,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "AI insights scope resolution failed for user %s: %s",
            current_user.get("id"), exc,
        )
        raise HTTPException(403, _AI_INSIGHTS_SCOPE_DENIED_AR)


async def _resolve_teacher_scope(current_user: dict) -> Optional[Dict[str, Any]]:
    """DEPRECATED (Task #155): use ``resolve_ai_insights_scope`` instead.

    Thin compatibility shim that flattens the canonical tri-state
    (``None`` / ``NO_AUTHORIZED_SCOPE`` / dict) into the legacy 2-state
    shape (``None`` for non-teacher OR no-scope, dict otherwise) that
    pre-#154 callers expected.

    No in-tree caller remains; this wrapper only exists to keep any
    out-of-tree caller from crashing while a separate cleanup task
    formally retires the symbol. Do NOT add new callers.
    """
    import warnings

    warnings.warn(
        "_resolve_teacher_scope is deprecated (Task #155); "
        "use resolve_ai_insights_scope instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    role = current_user.get("role", "")
    if role != UserRole.TEACHER.value:
        return None
    result = await resolve_ai_insights_scope(current_user)
    if result is None or result is NO_AUTHORIZED_SCOPE:
        return None
    return result


def _scope_query_for(scope: Optional[Dict[str, Any]], school_id: Optional[str], collection: str) -> Dict[str, Any]:
    """
    Build a base filter dict for a given collection. For teachers, narrows by
    class_id (or student_id where applicable). For non-teachers, scopes by
    school_id only.

    Task #155 audit row #12: the ``else {}`` baseline below is unreachable in
    the current codebase because every caller goes through
    ``resolve_ai_insights_scope`` first, which 403's on a missing school_id.
    Keep the shape conservative: any new caller MUST resolve school_id via
    the canonical resolver / ``require_request_school_id`` first; do NOT
    invoke this helper with a falsy school_id.
    """
    base: Dict[str, Any] = {"school_id": school_id} if school_id else {}
    if not scope:
        return base
    cids = scope.get("class_ids") or []
    sids = scope.get("student_ids") or []
    if collection in {"attendance", "grades", "behaviour_records", "assessments", "classes", "timetable_sessions", "schedule_sessions"}:
        if collection == "classes":
            base["id"] = {"$in": cids} if cids else {"$in": ["__none__"]}
        else:
            base["class_id"] = {"$in": cids} if cids else {"$in": ["__none__"]}
    elif collection == "students":
        base["id"] = {"$in": sids} if sids else {"$in": ["__none__"]}
    elif collection == "teachers":
        tid = scope.get("teacher_id")
        base["id"] = tid if tid else "__none__"
    return base


@router.get("/ai/insights/overview")
async def get_ai_insights_overview(
    current_user: dict = Depends(get_current_user)
):
    """Get AI-powered insights overview for the school (or for the current
    teacher's classes when the caller is a teacher)."""
    # Tri-state authorization sentinel must be resolved before ANY business
    # data query (Task #154 / H1).
    scope_result = await resolve_ai_insights_scope(current_user)
    if scope_result is NO_AUTHORIZED_SCOPE:
        return _empty_insights_overview()
    teacher_scope = scope_result if isinstance(scope_result, dict) else None
    school_id = teacher_scope["school_id"] if teacher_scope else current_user.get("tenant_id")

    # Platform admins (no tenant_id) get aggregate stats across ALL schools so
    # the overview, attendance and counts stay consistent. School-scoped users
    # only see their own school's data. Teachers see only their own classes.
    students_q = _scope_query_for(teacher_scope, school_id, "students")
    teachers_q = _scope_query_for(teacher_scope, school_id, "teachers")
    attendance_q = _scope_query_for(teacher_scope, school_id, "attendance")
    grades_q = _scope_query_for(teacher_scope, school_id, "grades")

    total_students = await gd_count(db.session, "students", students_q)
    total_teachers = await gd_count(db.session, "teachers", teachers_q)

    # Get attendance data using the same scope as students/teachers
    attendance_count = await gd_count(db.session, "attendance", {**attendance_q, "status": "present"})
    total_attendance = await gd_count(db.session, "attendance", attendance_q)

    has_attendance_data = total_attendance > 0
    has_any_data = total_students > 0 or total_teachers > 0 or has_attendance_data

    attendance_rate = round((attendance_count / total_attendance) * 100, 1) if has_attendance_data else 0
    student_teacher_ratio = round(total_students / total_teachers, 1) if total_teachers > 0 else 0

    # Real engagement rate: % of students with at least one assessment grade in the last 30 days.
    now_utc = datetime.now(timezone.utc)
    month_ago_iso = (now_utc - timedelta(days=30)).isoformat()
    engagement_rate = 0.0
    if total_students > 0:
        active_grades = await gd_find(
            db.session, "grades",
            {**grades_q, "created_at": {"$gte": month_ago_iso}},
            limit=10000,
        )
        active_student_ids = {g.get("student_id") for g in active_grades if g.get("student_id")}
        engagement_rate = round(len(active_student_ids) / total_students * 100, 1)

    def _score_from(att_rate: float, st_ratio: float, eng_rate: float) -> int:
        base = 70
        att_bonus = min(15, (att_rate - 80) / 2) if att_rate > 80 else 0
        ratio_bonus = max(0, 15 - abs(st_ratio - 15)) if st_ratio > 0 else 0
        eng_bonus = min(10, eng_rate / 10) if eng_rate > 0 else 0
        return int(min(100, base + att_bonus + ratio_bonus + eng_bonus))

    # The Smart Performance Index is only meaningful once the workspace
    # has both enrolled students AND recorded attendance — without those
    # signals the score collapses to its 70-point base value and gives
    # users a hallucinated "good" reading on a brand-new empty account.
    # Gate computation on the real prerequisites and surface a
    # ``score_available`` flag so the UI can render an "insufficient
    # data" empty state instead of a fake number.
    score_available = total_students > 0 and has_attendance_data

    if score_available:
        overall_score = _score_from(attendance_rate, student_teacher_ratio, engagement_rate)

        # Real month-over-month trend: recompute the same score using last month's data.
        prev_month_start = (now_utc - timedelta(days=60)).strftime("%Y-%m-%d")
        prev_month_end = (now_utc - timedelta(days=30)).strftime("%Y-%m-%d")
        prev_total = await gd_count(db.session, "attendance", {**attendance_q, "date": {"$gte": prev_month_start, "$lt": prev_month_end}})
        prev_present = await gd_count(db.session, "attendance", {**attendance_q, "date": {"$gte": prev_month_start, "$lt": prev_month_end}, "status": "present"})
        prev_att_rate = round((prev_present / prev_total) * 100, 1) if prev_total > 0 else attendance_rate

        prev_eng_rate = 0.0
        if total_students > 0:
            prev_grades = await gd_find(
                db.session, "grades",
                {**grades_q, "created_at": {"$gte": (now_utc - timedelta(days=60)).isoformat(), "$lt": month_ago_iso}},
                limit=10000,
            )
            prev_active_ids = {g.get("student_id") for g in prev_grades if g.get("student_id")}
            prev_eng_rate = round(len(prev_active_ids) / total_students * 100, 1)

        prev_score = _score_from(prev_att_rate, student_teacher_ratio, prev_eng_rate) if (prev_total > 0 or prev_eng_rate > 0) else overall_score
        delta = overall_score - prev_score
        trend = "up" if delta > 0 else ("down" if delta < 0 else "flat")
        trend_value = round(abs(delta), 1)
    else:
        overall_score = 0
        trend = "flat"
        trend_value = 0
        prev_score = 0

    return {
        "overall_score": overall_score,
        "trend": trend,
        "trend_value": trend_value,
        "has_data": has_any_data,
        "score_available": score_available,
        "last_updated": now_utc.isoformat(),
        "metrics": {
            "attendance_rate": attendance_rate,
            "engagement_rate": engagement_rate,
            "student_teacher_ratio": student_teacher_ratio,
            "total_students": total_students,
            "total_teachers": total_teachers,
            "has_attendance_data": has_attendance_data,
            "previous_month_score": prev_score if has_any_data else 0,
        }
    }

@router.get("/ai/insights/predictions")
async def get_ai_predictions(
    current_user: dict = Depends(get_current_user)
):
    """Get AI predictions for the school (or for the current teacher's classes
    when the caller is a teacher) based on real data analysis."""
    # Tri-state authorization sentinel must be resolved before ANY business
    # data query (Task #154 / H1).
    scope_result = await resolve_ai_insights_scope(current_user)
    if scope_result is NO_AUTHORIZED_SCOPE:
        return []
    teacher_scope = scope_result if isinstance(scope_result, dict) else None
    school_id = teacher_scope["school_id"] if teacher_scope else current_user.get("tenant_id")
    predictions = []
    pred_id = 0

    today = datetime.now(timezone.utc)
    week_ago = today - timedelta(days=7)
    two_weeks_ago = today - timedelta(days=14)
    week_ago_str = week_ago.strftime("%Y-%m-%d")
    two_weeks_ago_str = two_weeks_ago.strftime("%Y-%m-%d")

    attendance_q = _scope_query_for(teacher_scope, school_id, "attendance")
    grades_q = _scope_query_for(teacher_scope, school_id, "grades")

    this_week_total = await gd_count(db.session, "attendance", {**attendance_q, "date": {"$gte": week_ago_str}})
    this_week_present = await gd_count(db.session, "attendance", {**attendance_q, "date": {"$gte": week_ago_str}, "status": "present"})
    last_week_total = await gd_count(db.session, "attendance", {**attendance_q, "date": {"$gte": two_weeks_ago_str, "$lt": week_ago_str}})
    last_week_present = await gd_count(db.session, "attendance", {**attendance_q, "date": {"$gte": two_weeks_ago_str, "$lt": week_ago_str}, "status": "present"})

    this_rate = round((this_week_present / this_week_total) * 100, 1) if this_week_total > 0 else 0
    last_rate = round((last_week_present / last_week_total) * 100, 1) if last_week_total > 0 else 0
    att_trend = this_rate - last_rate

    pred_id += 1
    if att_trend > 2:
        predictions.append({
            "id": str(pred_id),
            "title": {"ar": "توقع تحسن الحضور", "en": "Attendance Improvement Predicted"},
            "description": {"ar": f"ارتفعت نسبة الحضور من {last_rate}% إلى {this_rate}%. من المتوقع استمرار التحسن الأسبوع القادم", "en": f"Attendance rose from {last_rate}% to {this_rate}%. Improvement expected to continue"},
            "confidence": min(90, 70 + int(att_trend)),
            "impact": "positive",
            "category": "attendance"
        })
    elif att_trend < -2:
        predictions.append({
            "id": str(pred_id),
            "title": {"ar": "تحذير: انخفاض الحضور", "en": "Warning: Attendance Decline"},
            "description": {"ar": f"انخفضت نسبة الحضور من {last_rate}% إلى {this_rate}%. يُنصح بالتدخل المبكر", "en": f"Attendance dropped from {last_rate}% to {this_rate}%. Early intervention advised"},
            "confidence": min(90, 70 + int(abs(att_trend))),
            "impact": "high",
            "category": "attendance"
        })
    else:
        predictions.append({
            "id": str(pred_id),
            "title": {"ar": "استقرار نسبة الحضور", "en": "Attendance Stable"},
            "description": {"ar": f"نسبة الحضور الحالية {this_rate}% مستقرة مقارنة بالأسبوع الماضي ({last_rate}%)", "en": f"Current attendance {this_rate}% is stable compared to last week ({last_rate}%)"},
            "confidence": 85,
            "impact": "medium",
            "category": "attendance"
        })

    recent_grades = await gd_find(db.session, "grades", {**grades_q, "created_at": {"$gte": week_ago.isoformat()}}, limit=500)
    older_grades = await gd_find(db.session, "grades", {**grades_q, "created_at": {"$gte": two_weeks_ago.isoformat(), "$lt": week_ago.isoformat()}}, limit=500)
    if recent_grades:
        recent_avg = sum(g.get("percentage", 0) for g in recent_grades) / len(recent_grades)
        older_avg = sum(g.get("percentage", 0) for g in older_grades) / len(older_grades) if older_grades else recent_avg
        grade_trend = recent_avg - older_avg
        pred_id += 1
        if grade_trend > 3:
            predictions.append({
                "id": str(pred_id),
                "title": {"ar": "تحسن أداء الطلاب الأكاديمي", "en": "Student Academic Improvement"},
                "description": {"ar": f"ارتفع متوسط الدرجات بمقدار {abs(grade_trend):.1f}% هذا الأسبوع. التوقع: استمرار التحسن", "en": f"Average grades increased by {abs(grade_trend):.1f}% this week. Expected to continue"},
                "confidence": min(88, 65 + int(grade_trend)),
                "impact": "positive",
                "category": "academic"
            })
        elif grade_trend < -3:
            predictions.append({
                "id": str(pred_id),
                "title": {"ar": "تحذير: تراجع الأداء الأكاديمي", "en": "Warning: Academic Performance Decline"},
                "description": {"ar": f"انخفض متوسط الدرجات بمقدار {abs(grade_trend):.1f}% هذا الأسبوع. يُنصح بمراجعة خطط التدريس", "en": f"Average grades dropped by {abs(grade_trend):.1f}%. Teaching plans review recommended"},
                "confidence": min(88, 65 + int(abs(grade_trend))),
                "impact": "high",
                "category": "academic"
            })
        else:
            predictions.append({
                "id": str(pred_id),
                "title": {"ar": "استقرار الأداء الأكاديمي", "en": "Stable Academic Performance"},
                "description": {"ar": f"متوسط الدرجات الحالي {recent_avg:.1f}% مستقر", "en": f"Current grade average {recent_avg:.1f}% is stable"},
                "confidence": 80,
                "impact": "medium",
                "category": "academic"
            })

    absent_pipeline = [
        {"$match": {**attendance_q, "status": "absent", "date": {"$gte": week_ago_str}}},
        {"$group": {"_id": "$student_id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gte": 3}}},
        {"$count": "total"}
    ]
    absent_result = await _gd_aggregate(db.session, "attendance", absent_pipeline)
    chronic_absent = absent_result[0]["total"] if absent_result else 0
    if chronic_absent > 0:
        pred_id += 1
        predictions.append({
            "id": str(pred_id),
            "title": {"ar": "طلاب يحتاجون متابعة عاجلة", "en": "Students Need Urgent Follow-up"},
            "description": {"ar": f"يوجد {chronic_absent} طالب غابوا 3 أيام أو أكثر خلال الأسبوع الماضي. يُنصح بالتواصل مع أولياء أمورهم", "en": f"{chronic_absent} students were absent 3+ days last week. Contact parents recommended"},
            "confidence": 92,
            "impact": "high",
            "category": "intervention"
        })

    return predictions

# --------------------------------------------------------------------------
# Role-aware recommendation builders.
#
# Every smart recommendation card carries explicit audience semantics so the
# backend (not the frontend) is the authoritative layer that decides:
#   * `audience`           -> which roles may see this card at all,
#   * `action_owner`       -> who is expected to act on it,
#   * `scope_level`        -> "school" vs "classroom",
#   * `recommendation_type`-> stable machine identifier of the rec family.
# Wording is selected per-role so a teacher never sees principal-directed
# operational instructions (e.g. "follow up with class teachers", "review
# school start times", "hire more teachers").
# --------------------------------------------------------------------------
_PRINCIPAL_AUDIENCE = [
    UserRole.SCHOOL_ADMIN.value,
    UserRole.SCHOOL_SUB_ADMIN.value,
    UserRole.SCHOOL_PRINCIPAL.value,
]
_TEACHER_AUDIENCE = [
    UserRole.TEACHER.value,
    UserRole.INDEPENDENT_TEACHER.value,
]
_ALL_SCHOOL_AUDIENCE = _PRINCIPAL_AUDIENCE + _TEACHER_AUDIENCE


def _is_teacher_role(role: str) -> bool:
    return role in _TEACHER_CLASS_ROLES


def _build_attendance_rec(rec_id: str, att_rate: float, *, is_teacher: bool) -> dict:
    if is_teacher:
        body = {
            "category": {"ar": "الحضور والانضباط", "en": "Attendance & Discipline"},
            "title": {"ar": "تحسين حضور فصلك",
                      "en": "Improve Your Class Attendance"},
            "description": {
                "ar": (f"نسبة حضور طلابك الحالية {att_rate}% أقل من المستوى "
                       "المطلوب (85%). تواصل مع طلابك وأولياء أمورهم وراجع "
                       "أسباب الغياب داخل فصلك."),
                "en": (f"Your students' attendance is {att_rate}% — below the "
                       "85% target. Reach out to your students and their "
                       "guardians and review absence causes inside your class."),
            },
            "action_owner": "teacher",
            "scope_level": "classroom",
        }
    else:
        body = {
            "category": {"ar": "الحضور والانضباط", "en": "Attendance & Discipline"},
            "title": {"ar": "تحسين نسبة الحضور", "en": "Improve Attendance Rate"},
            "description": {
                "ar": (f"نسبة الحضور الحالية {att_rate}% أقل من المستوى "
                       "المطلوب (85%). يُنصح بتطبيق نظام حوافز للحضور المنتظم "
                       "والتواصل مع أولياء الأمور"),
                "en": (f"Current attendance {att_rate}% is below target (85%). "
                       "Implement incentive system and parent outreach"),
            },
            "action_owner": "principal",
            "scope_level": "school",
        }
    return {
        "id": rec_id,
        "priority": "high" if att_rate < 75 else "medium",
        "expected_impact": int(85 - att_rate),
        "recommendation_type": "attendance_improve",
        "audience": _ALL_SCHOOL_AUDIENCE,
        **body,
    }


def _build_tardiness_rec(rec_id: str, late_pct: float, *, is_teacher: bool) -> dict:
    if is_teacher:
        body = {
            "category": {"ar": "الحضور والانضباط", "en": "Attendance & Discipline"},
            "title": {"ar": "متابعة تأخر طلابك",
                      "en": "Follow Up on Your Students' Tardiness"},
            "description": {
                "ar": (f"نسبة التأخر بين طلابك {late_pct}% مرتفعة. ذكّر "
                       "طلابك بأهمية الالتزام بموعد الحصة وتواصل مع أسر "
                       "المتأخرين باستمرار."),
                "en": (f"Your students' tardiness rate is {late_pct}%. Remind "
                       "your class about punctuality and contact the families "
                       "of the students who arrive late."),
            },
            "action_owner": "teacher",
            "scope_level": "classroom",
        }
    else:
        body = {
            "category": {"ar": "الحضور والانضباط", "en": "Attendance & Discipline"},
            "title": {"ar": "معالجة ظاهرة التأخر", "en": "Address Tardiness"},
            "description": {
                "ar": (f"نسبة التأخر {late_pct}% مرتفعة. يُنصح بمراجعة "
                       "أوقات بدء الدوام والتواصل مع الأسر"),
                "en": (f"Tardiness rate {late_pct}% is high. Review start "
                       "times and contact families"),
            },
            "action_owner": "principal",
            "scope_level": "school",
        }
    return {
        "id": rec_id,
        "priority": "medium",
        "expected_impact": 10,
        "recommendation_type": "tardiness_address",
        "audience": _ALL_SCHOOL_AUDIENCE,
        **body,
    }


def _build_low_att_classes_rec(rec_id: str, class_names: str,
                               *, is_teacher: bool) -> dict:
    """Class-level low-attendance card.

    Principal variant: school-wide coordination wording — "follow up with
    class teachers". Teacher variant: scoped to the teacher's own class —
    they ARE the class teacher, so "follow up with class teachers" would
    be nonsensical and is replaced with classroom-action wording.
    """
    if is_teacher:
        body = {
            "category": {"ar": "متابعة فصلك", "en": "Your Class Monitoring"},
            "title": {"ar": "فصل من فصولك يحتاج اهتمامك",
                      "en": "One of Your Classes Needs Attention"},
            "description": {
                "ar": (f"الحضور منخفض في: {class_names}. راجع أسباب الغياب "
                       "مع طلابك وتواصل مع أولياء أمورهم لمعالجة الوضع."),
                "en": (f"Low attendance in: {class_names}. Review absence "
                       "causes with your students and contact their guardians."),
            },
            "action_owner": "teacher",
            "scope_level": "classroom",
        }
    else:
        body = {
            "category": {"ar": "متابعة الفصول", "en": "Class Monitoring"},
            "title": {"ar": "فصول تحتاج اهتمام خاص",
                      "en": "Classes Needing Attention"},
            "description": {
                "ar": (f"الفصول التالية حضورها منخفض: {class_names}. يُنصح "
                       "بمتابعة أسباب الغياب مع معلمي الفصول"),
                "en": (f"Low attendance in: {class_names}. Investigate causes "
                       "with class teachers"),
            },
            "action_owner": "principal",
            "scope_level": "school",
        }
    return {
        "id": rec_id,
        "priority": "high",
        "expected_impact": 15,
        "recommendation_type": "class_low_attendance",
        "audience": _ALL_SCHOOL_AUDIENCE,
        **body,
    }


# Roles that are subject to audience filtering. Platform admins (and any
# future cross-tenant oversight role) are intentionally NOT in this set —
# they oversee the whole platform and must keep seeing every card the
# generator produced, regardless of the per-card school-audience tags.
_AUDIENCE_FILTERED_ROLES = frozenset({
    UserRole.SCHOOL_ADMIN.value,
    UserRole.SCHOOL_SUB_ADMIN.value,
    UserRole.SCHOOL_PRINCIPAL.value,
    UserRole.TEACHER.value,
    UserRole.INDEPENDENT_TEACHER.value,
})


def _filter_recommendations_for_role(
    recommendations: list, role: str
) -> list:
    """Authoritative, backend-side audience filter.

    For school-level roles (admin/principal/sub-admin/teacher), drops any
    card whose `audience` list does not include the caller's role. Items
    without an `audience` field are kept (legacy / safe defaults).

    Roles outside `_AUDIENCE_FILTERED_ROLES` (e.g. `platform_admin`) are
    pass-through: the per-card school-audience tags must not silently
    strip every card from a cross-tenant oversight caller.
    """
    if role not in _AUDIENCE_FILTERED_ROLES:
        return list(recommendations)
    out = []
    for r in recommendations:
        aud = r.get("audience")
        if aud and role not in aud:
            continue
        out.append(r)
    return out


@router.get("/ai/insights/recommendations")
async def get_ai_recommendations(
    current_user: dict = Depends(get_current_user)
):
    """Get AI-powered recommendations based on real school data (or the
    current teacher's classes when the caller is a teacher).

    Each returned recommendation carries explicit audience metadata
    (`audience`, `action_owner`, `scope_level`, `recommendation_type`) and
    a role-appropriate wording variant. Principal-only operational advice
    (HR/staffing) is dropped server-side for teacher callers, and shared
    recommendations are reworded so a teacher never sees principal-directed
    instructions like "follow up with class teachers"."""
    # Tri-state authorization sentinel must be resolved before ANY business
    # data query (Task #154 / H1).
    scope_result = await resolve_ai_insights_scope(current_user)
    if scope_result is NO_AUTHORIZED_SCOPE:
        return []
    teacher_scope = scope_result if isinstance(scope_result, dict) else None
    is_teacher = teacher_scope is not None
    role = current_user.get("role", "")
    school_id = teacher_scope["school_id"] if teacher_scope else current_user.get("tenant_id")
    recommendations = []
    rec_id = 0
    attendance_q = _scope_query_for(teacher_scope, school_id, "attendance")
    students_q = _scope_query_for(teacher_scope, school_id, "students")
    teachers_q = _scope_query_for(teacher_scope, school_id, "teachers")
    classes_q = _scope_query_for(teacher_scope, school_id, "classes")
    assessments_q = _scope_query_for(teacher_scope, school_id, "assessments")

    today = datetime.now(timezone.utc)
    month_ago = today - timedelta(days=30)
    month_ago_str = month_ago.strftime("%Y-%m-%d")

    total_att = await gd_count(db.session, "attendance", {**attendance_q, "date": {"$gte": month_ago_str}})
    present_att = await gd_count(db.session, "attendance", {**attendance_q, "date": {"$gte": month_ago_str}, "status": "present"})
    att_rate = round((present_att / total_att) * 100, 1) if total_att > 0 else 100

    if att_rate < 85:
        rec_id += 1
        recommendations.append(
            _build_attendance_rec(str(rec_id), att_rate, is_teacher=is_teacher)
        )

    late_count = await gd_count(db.session, "attendance", {**attendance_q, "date": {"$gte": month_ago_str}, "status": "late"})
    if total_att > 0 and (late_count / total_att * 100) > 5:
        rec_id += 1
        late_pct = round(late_count / total_att * 100, 1)
        recommendations.append(
            _build_tardiness_rec(str(rec_id), late_pct, is_teacher=is_teacher)
        )

    total_students = await gd_count(db.session, "students", students_q)
    total_teachers = await gd_count(db.session, "teachers", teachers_q)
    # The HR/staffing recommendation ("Strengthen Teaching Staff") is a
    # school-admin concern — teachers can't hire colleagues, so it carries
    # a principal-only `audience` and is additionally skipped before
    # generation when the caller is a teacher (their `teachers_q` filters
    # down to themselves and would produce an absurd N:1 ratio).
    if teacher_scope is None and total_teachers > 0:
        ratio = total_students / total_teachers
        if ratio > 25:
            rec_id += 1
            recommendations.append({
                "id": str(rec_id),
                "category": {"ar": "الموارد البشرية", "en": "Human Resources"},
                "title": {"ar": "تعزيز الكادر التعليمي", "en": "Strengthen Teaching Staff"},
                "description": {"ar": f"نسبة الطلاب للمعلمين ({ratio:.0f}:1) مرتفعة. يُنصح بتعيين معلمين إضافيين لتحسين جودة التعليم", "en": f"Student-teacher ratio ({ratio:.0f}:1) is high. Consider hiring additional teachers"},
                "priority": "high",
                "expected_impact": 20,
                "recommendation_type": "staffing_strengthen",
                "audience": list(_PRINCIPAL_AUDIENCE),
                "action_owner": "principal",
                "scope_level": "school",
            })

    classes_list = await gd_find(db.session, "classes", classes_q, limit=100)
    class_ids_all = [c["id"] for c in classes_list]
    cls_name_map = {c["id"]: c.get("name", c["id"]) for c in classes_list}

    cls_att_pipeline = [
        {"$match": {"class_id": {"$in": class_ids_all}, "date": {"$gte": month_ago_str}}},
        {"$group": {
            "_id": {"class_id": "$class_id", "status": "$status"},
            "count": {"$sum": 1}
        }}
    ]
    cls_att_raw = await _gd_aggregate(db.session, "attendance", cls_att_pipeline)
    cls_att_data = {}
    for r in cls_att_raw:
        cid = r["_id"]["class_id"]
        status = r["_id"]["status"]
        if cid not in cls_att_data:
            cls_att_data[cid] = {"total": 0, "present": 0}
        cls_att_data[cid]["total"] += r["count"]
        if status == "present":
            cls_att_data[cid]["present"] += r["count"]

    low_att_classes = []
    for cid, data in cls_att_data.items():
        if data["total"] > 10:
            cls_rate = round((data["present"] / data["total"]) * 100, 1)
            if cls_rate < 80:
                low_att_classes.append({"name": cls_name_map.get(cid, cid), "rate": cls_rate})
    if low_att_classes:
        rec_id += 1
        class_names = ", ".join([c["name"] for c in low_att_classes[:3]])
        recommendations.append(
            _build_low_att_classes_rec(
                str(rec_id), class_names, is_teacher=is_teacher
            )
        )

    recent_assessments = await gd_count(db.session, "assessments", {**assessments_q, "created_at": {"$gte": month_ago.isoformat()}})
    if recent_assessments == 0 and total_students > 0:
        rec_id += 1
        if is_teacher:
            assessment_body = {
                "category": {"ar": "التحصيل الأكاديمي",
                             "en": "Academic Achievement"},
                "title": {"ar": "فعّل التقييم المستمر في فصلك",
                          "en": "Activate Continuous Assessment in Your Class"},
                "description": {
                    "ar": ("لم تُسجَّل أي تقييمات لطلابك خلال الشهر الماضي. "
                           "أنشئ اختبارات قصيرة في فصلك لمتابعة مستوى طلابك."),
                    "en": ("No assessments recorded for your students this "
                           "month. Create short quizzes in your class to "
                           "track your students' progress."),
                },
                "action_owner": "teacher",
                "scope_level": "classroom",
            }
        else:
            assessment_body = {
                "category": {"ar": "التحصيل الأكاديمي",
                             "en": "Academic Achievement"},
                "title": {"ar": "تفعيل التقييم المستمر",
                          "en": "Activate Continuous Assessment"},
                "description": {
                    "ar": ("لم يتم تسجيل أي تقييمات خلال الشهر الماضي. يُنصح "
                           "بإنشاء اختبارات قصيرة لمتابعة مستوى الطلاب"),
                    "en": ("No assessments recorded this month. Create "
                           "quizzes to track student progress"),
                },
                "action_owner": "principal",
                "scope_level": "school",
            }
        recommendations.append({
            "id": str(rec_id),
            "priority": "high",
            "expected_impact": 25,
            "recommendation_type": "assessment_activate",
            "audience": _ALL_SCHOOL_AUDIENCE,
            **assessment_body,
        })

    # Authoritative server-side audience filter — defence in depth in case
    # any future builder forgets to skip an admin-only card for teachers.
    recommendations = _filter_recommendations_for_role(recommendations, role)

    if not recommendations:
        if teacher_scope is not None:
            recommendations.append({
                "id": "1",
                "category": {"ar": "الأداء التعليمي", "en": "Teaching Performance"},
                "title": {"ar": "فصولك تسير بشكل ممتاز", "en": "Your Classes Are Doing Great"},
                "description": {"ar": "لا توجد توصيات عاجلة لفصولك حالياً. استمر في متابعة الأداء والمشاركة الصفية", "en": "No urgent recommendations for your classes right now. Keep monitoring participation and progress"},
                "priority": "low",
                "expected_impact": 5,
                "recommendation_type": "all_clear",
                "audience": list(_TEACHER_AUDIENCE),
                "action_owner": "teacher",
                "scope_level": "classroom",
            })
        else:
            recommendations.append({
                "id": "1",
                "category": {"ar": "الأداء العام", "en": "General Performance"},
                "title": {"ar": "أداء المدرسة جيد", "en": "School Performance is Good"},
                "description": {"ar": "المؤشرات الحالية جيدة. استمر في متابعة الأداء بانتظام للحفاظ على هذا المستوى", "en": "Current indicators are good. Continue regular monitoring to maintain this level"},
                "priority": "low",
                "expected_impact": 5,
                "recommendation_type": "all_clear",
                "audience": list(_PRINCIPAL_AUDIENCE),
                "action_owner": "principal",
                "scope_level": "school",
            })

    return recommendations

@router.get("/ai/insights/alerts")
async def get_ai_alerts(
    current_user: dict = Depends(get_current_user)
):
    """Get AI-generated alerts based on real school data (or the current
    teacher's classes when the caller is a teacher)."""
    # Tri-state authorization sentinel must be resolved before ANY business
    # data query (Task #154 / H1).
    scope_result = await resolve_ai_insights_scope(current_user)
    if scope_result is NO_AUTHORIZED_SCOPE:
        return []
    teacher_scope = scope_result if isinstance(scope_result, dict) else None
    school_id = teacher_scope["school_id"] if teacher_scope else current_user.get("tenant_id")
    alerts = []
    attendance_q = _scope_query_for(teacher_scope, school_id, "attendance")
    sessions_q = _scope_query_for(teacher_scope, school_id, "timetable_sessions")
    behaviour_q = _scope_query_for(teacher_scope, school_id, "behaviour_records")
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")
    week_ago_str = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    consecutive_pipeline = [
        {"$match": {**attendance_q, "status": "absent", "date": {"$gte": week_ago_str}}},
        {"$group": {"_id": "$student_id", "days": {"$sum": 1}, "dates": {"$push": "$date"}}},
        {"$match": {"days": {"$gte": 3}}},
        {"$count": "total"}
    ]
    cons_result = await _gd_aggregate(db.session, "attendance", consecutive_pipeline)
    chronic_count = cons_result[0]["total"] if cons_result else 0
    if chronic_count > 0:
        alerts.append({
            "id": str(uuid.uuid4())[:8],
            "type": "warning",
            "title": {"ar": f"غياب متكرر: {chronic_count} طالب", "en": f"Chronic Absence: {chronic_count} students"},
            "description": {"ar": f"يوجد {chronic_count} طالب تغيبوا 3 أيام أو أكثر هذا الأسبوع. يجب التواصل مع أولياء أمورهم", "en": f"{chronic_count} students absent 3+ days this week. Contact parents immediately"},
            "timestamp": today.isoformat(),
            "category": "attendance",
            "route": "/admin/attendance"
        })

    today_total = await gd_count(db.session, "attendance", {**attendance_q, "date": today_str})
    today_present = await gd_count(db.session, "attendance", {**attendance_q, "date": today_str, "status": "present"})
    if today_total > 0:
        today_rate = round((today_present / today_total) * 100, 1)
        if today_rate < 80:
            alerts.append({
                "id": str(uuid.uuid4())[:8],
                "type": "warning",
                "title": {"ar": f"حضور اليوم منخفض: {today_rate}%", "en": f"Low Today's Attendance: {today_rate}%"},
                "description": {"ar": f"نسبة الحضور اليوم {today_rate}% أقل من المعدل الطبيعي. تحقق من الأسباب", "en": f"Today's attendance {today_rate}% is below normal. Investigate causes"},
                "timestamp": today.isoformat(),
                "category": "attendance",
                "route": "/admin/attendance"
            })
        elif today_rate >= 95:
            alerts.append({
                "id": str(uuid.uuid4())[:8],
                "type": "success",
                "title": {"ar": f"حضور ممتاز اليوم: {today_rate}%", "en": f"Excellent Attendance Today: {today_rate}%"},
                "description": {"ar": f"نسبة الحضور اليوم {today_rate}% ممتازة. استمروا في ذلك!", "en": f"Today's attendance {today_rate}% is excellent. Keep it up!"},
                "timestamp": today.isoformat(),
                "category": "attendance",
                "route": "/admin/attendance"
            })

    # Skip the "Unassigned Sessions" alert for teachers — assigning
    # teachers to timetable slots is a school-admin / scheduling task,
    # not something a teacher can act on from their own dashboard.
    if teacher_scope is None:
        unassigned_sessions = await gd_count(db.session, "timetable_sessions", {**sessions_q, "$or": [{"teacher_id": None}, {"teacher_id": ""}]})
        if unassigned_sessions > 0:
            alerts.append({
                "id": str(uuid.uuid4())[:8],
                "type": "warning",
                "title": {"ar": f"حصص بلا معلم: {unassigned_sessions}", "en": f"Unassigned Sessions: {unassigned_sessions}"},
                "description": {"ar": f"يوجد {unassigned_sessions} حصة بدون معلم مُعيّن. قم بتعيين معلمين لها", "en": f"{unassigned_sessions} sessions have no teacher assigned"},
                "timestamp": today.isoformat(),
                "category": "scheduling",
                "route": "/school/schedule"
            })

    recent_behaviour = await gd_count(db.session, "behaviour_records", {
        **behaviour_q,
        "type": "negative",
        "created_at": {"$gte": (today - timedelta(days=7)).isoformat()}
    })
    if recent_behaviour >= 5:
        alerts.append({
            "id": str(uuid.uuid4())[:8],
            "type": "warning",
            "title": {"ar": f"ملاحظات سلوكية: {recent_behaviour} هذا الأسبوع", "en": f"Behaviour Notes: {recent_behaviour} this week"},
            "description": {"ar": f"تم تسجيل {recent_behaviour} ملاحظة سلوكية سلبية هذا الأسبوع. يُنصح بمراجعة السلوك العام", "en": f"{recent_behaviour} negative behaviour notes this week. Review overall conduct"},
            "timestamp": today.isoformat(),
            "category": "behaviour",
            "route": "/admin/behaviour"
        })

    if not alerts:
        alerts.append({
            "id": str(uuid.uuid4())[:8],
            "type": "info",
            "title": {"ar": "لا توجد تنبيهات عاجلة", "en": "No Urgent Alerts"},
            "description": {"ar": "جميع المؤشرات طبيعية حالياً. استمر في المتابعة الدورية", "en": "All indicators are normal. Continue regular monitoring"},
            "timestamp": today.isoformat(),
            "category": "general",
            "route": ""
        })

    return alerts

_OVERVIEW_CACHE: Dict[str, tuple] = {}
_OVERVIEW_TTL_SEC = 300


@router.get("/ai/insights/students-overview")
async def get_students_overview(
    refresh: int = 0,
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")

    now_ts = datetime.now(timezone.utc).timestamp()
    cached = _OVERVIEW_CACHE.get(school_id)
    if not refresh and cached and now_ts - cached[0] < _OVERVIEW_TTL_SEC:
        return cached[1]

    students = await gd_find(db.session, "students", {"school_id": school_id}, limit=500)
    if not students:
        empty = {
            "summary": {
                "total_students": 0,
                "stable": {"count": 0, "percentage": 0},
                "needs_followup": {"count": 0, "percentage": 0},
                "at_risk": {"count": 0, "percentage": 0},
                "excelling": {"count": 0, "percentage": 0},
            },
            "risk_map": [],
            "intervention_list": [],
            "root_causes": {
                "attendance": {"count": 0, "percentage": 0},
                "participation": {"count": 0, "percentage": 0},
                "behaviour": {"count": 0, "percentage": 0},
                "academic": {"count": 0, "percentage": 0},
            },
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        _OVERVIEW_CACHE[school_id] = (now_ts, empty)
        return empty

    ids = [s["id"] for s in students]
    risks = await hakim_engine.analyze_students_risk_batch(school_id, ids, days_back=30)

    class_ids = list({r["class_id"] for r in risks if r.get("class_id")})
    class_docs = await gd_find(db.session, "classes", {"id": {"$in": class_ids}}, limit=500) if class_ids else []
    class_name = {c["id"]: c.get("name", "") for c in class_docs}

    academic_scores = sorted([r["breakdown"]["academic"] for r in risks], reverse=True)
    top_q = academic_scores[max(len(academic_scores) // 4 - 1, 0)] if academic_scores else 0

    buckets = {"stable": [], "needs_followup": [], "at_risk": [], "excelling": []}
    enriched = []
    for r in risks:
        cat_raw = r["risk_category"]
        if cat_raw == "low":
            ui_cat = "stable"
        elif cat_raw == "medium":
            ui_cat = "needs_followup"
        else:
            ui_cat = "at_risk"
        if r["risk_score"] >= 90 and r["breakdown"]["academic"] >= top_q:
            ui_cat = "excelling"
        buckets[ui_cat].append(r)

        weakest_key = min(r["breakdown"].items(), key=lambda kv: kv[1])[0]
        enriched.append({
            **r,
            "ui_category": ui_cat,
            "weakest": weakest_key,
            "class_name": class_name.get(r.get("class_id"), ""),
        })

    total = len(risks)

    def _pct(n):
        return round((n / total) * 100, 1) if total else 0

    summary = {
        "total_students": total,
        "stable": {"count": len(buckets["stable"]), "percentage": _pct(len(buckets["stable"]))},
        "needs_followup": {"count": len(buckets["needs_followup"]), "percentage": _pct(len(buckets["needs_followup"]))},
        "at_risk": {"count": len(buckets["at_risk"]), "percentage": _pct(len(buckets["at_risk"]))},
        "excelling": {"count": len(buckets["excelling"]), "percentage": _pct(len(buckets["excelling"]))},
    }

    risk_map = [
        {
            "student_id": e["student_id"],
            "name": e["student_name"],
            "class_name": e["class_name"],
            "x_academic": e["breakdown"]["academic"],
            "y_engagement": round((e["breakdown"]["attendance"] + e["breakdown"]["participation"]) / 2, 1),
            "risk_score": e["risk_score"],
            "category": e["ui_category"],
            "factors": e["factors"],
        }
        for e in enriched
    ]

    intervention_items = [e for e in enriched if e["ui_category"] in ("at_risk", "needs_followup")]
    intervention_items.sort(key=lambda x: x["risk_score"])
    intervention_items = intervention_items[:50]
    LABELS = {
        "attendance": "انخفاض الحضور",
        "participation": "انخفاض المشاركة",
        "behaviour": "مشاكل سلوكية",
        "academic": "تدني الأداء الأكاديمي",
    }
    intervention_list = [
        {
            "student_id": e["student_id"],
            "name": e["student_name"],
            "class_name": e["class_name"],
            "category": e["ui_category"],
            "issue_type": e["weakest"],
            "issue_label_ar": LABELS[e["weakest"]],
            "risk_score": e["risk_score"],
            "parent_id": e.get("parent_id"),
        }
        for e in intervention_items
    ]

    cause_counts = {"attendance": 0, "participation": 0, "behaviour": 0, "academic": 0}
    at_risk_like = [e for e in enriched if e["risk_score"] < 75]
    for e in at_risk_like:
        cause_counts[e["weakest"]] += 1
    causes_total = sum(cause_counts.values()) or 1
    root_causes = {
        k: {"count": v, "percentage": round((v / causes_total) * 100, 1)}
        for k, v in cause_counts.items()
    }

    payload = {
        "summary": summary,
        "risk_map": risk_map,
        "intervention_list": intervention_list,
        "root_causes": root_causes,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    _OVERVIEW_CACHE[school_id] = (now_ts, payload)
    return payload


def _invalidate_overview_cache(school_id: str) -> None:
    _OVERVIEW_CACHE.pop(school_id, None)


class InterventionRequest(BaseModel):
    student_id: str
    action_type: Literal["notify_parent", "remedial_plan", "schedule_followup"]
    data: Dict[str, Any] = Field(default_factory=dict)


@router.post("/ai/insights/intervention")
async def post_intervention(
    body: InterventionRequest,
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")

    student = await gd_find_one(db.session, "students",
                                {"id": body.student_id, "school_id": school_id})
    if not student:
        raise HTTPException(404, "الطالب غير موجود")

    now = datetime.now(timezone.utc)
    intervention_id = str(uuid.uuid4())
    d = body.data or {}

    if body.action_type == "notify_parent":
        parent_id = student.get("parent_id")
        if not parent_id:
            raise HTTPException(400, "لا يوجد ولي أمر مسجل للطالب")
        message = (d.get("message") or "").strip()
        if not message:
            raise HTTPException(400, "نص الرسالة مطلوب")
        parent_rec = await gd_find_one(db.session, "parents",
                                       {"id": parent_id, "school_id": school_id})
        parent_user_id = None
        if parent_rec and parent_rec.get("email"):
            parent_user = await gd_find_one(db.session, "users",
                                            {"email": parent_rec["email"]})
            if parent_user:
                parent_user_id = parent_user.get("id")
        if not parent_user_id:
            raise HTTPException(400, "ولي الأمر ليس لديه حساب مستخدم مفعّل")
        from routes.notification_routes_mod import create_notification_internal
        await create_notification_internal(
            title="متابعة أداء الطالب",
            message=message,
            recipient_id=parent_user_id,
            notification_type=d.get("issue_type", "general"),
            priority="high",
            sender_id=current_user.get("id"),
            related_entity="student",
            related_entity_id=body.student_id,
            school_id=school_id,
        )
        msg_ar = "تم إرسال الرسالة لولي الأمر بنجاح"

    elif body.action_type == "remedial_plan":
        doc = {
            "id": intervention_id,
            "school_id": school_id,
            "student_id": body.student_id,
            "type": "plan",
            "status": "active",
            "title": d.get("title", "خطة علاجية"),
            "description": d.get("description", ""),
            "data": {
                "issue_type": d.get("issue_type", "academic"),
                "start_date": now.strftime("%Y-%m-%d"),
                "target_date": d.get("target_date"),
                "milestones": [{"text": m, "completed": False} for m in (d.get("milestones") or [])],
            },
            "created_by": current_user.get("id"),
            "created_at": now, "updated_at": now,
        }
        await gd_insert(db.session, "ai_interventions", doc)
        msg_ar = "تم إنشاء الخطة العلاجية بنجاح"

    else:  # schedule_followup
        doc = {
            "id": intervention_id,
            "school_id": school_id,
            "student_id": body.student_id,
            "type": "followup",
            "status": "active",
            "title": "متابعة",
            "description": d.get("notes", ""),
            "data": {
                "issue_type": d.get("issue_type", "attendance"),
                "follow_up_date": d.get("follow_up_date"),
                "notes": d.get("notes", ""),
            },
            "created_by": current_user.get("id"),
            "created_at": now, "updated_at": now,
        }
        await gd_insert(db.session, "ai_interventions", doc)
        msg_ar = "تمت جدولة المتابعة بنجاح"

    await gd_insert(db.session, "audit_logs", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "performed_by": current_user.get("id"),
        "actor_role": current_user.get("role"),
        "action": f"intervention.{body.action_type}",
        "entity_type": "student",
        "entity_id": body.student_id,
        "target_id": body.student_id,
        "target_type": "student",
        "details": {"intervention_id": intervention_id, "issue_type": d.get("issue_type")},
        "created_at": now,
    })

    _invalidate_overview_cache(school_id)
    return {"success": True, "intervention_id": intervention_id, "message_ar": msg_ar}


_REC_CACHE: dict[str, tuple[float, dict]] = {}
_REC_TTL_SEC = 900
_ICONS = {"quantitative": "📊", "academic": "🎯", "statistical_alert": "⚠️",
          "positive": "✅", "administrative": "📋"}


async def _call_openai_for_recommendations(prompt: str) -> str:
    client = get_openai_client()
    if client is None:
        raise RuntimeError("openai_unavailable")
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "أنت مستشار تعليمي. أجب حصراً بمصفوفة JSON دون نص إضافي."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or "[]"


def _build_recs_prompt(overview: dict) -> str:
    s = overview["summary"]
    rc = overview["root_causes"]
    top_causes = ", ".join(
        f"{k}({v['count']})" for k, v in sorted(rc.items(), key=lambda kv: -kv[1]["count"])[:2]
    )
    return (
        "أنت مستشار تعليمي ذكي. بناءً على بيانات مدرسة:\n"
        f"- إجمالي الطلاب: {s['total_students']}\n"
        f"- في فئة الخطر: {s['at_risk']['count']}\n"
        f"- يحتاجون متابعة: {s['needs_followup']['count']}\n"
        f"- أسباب التعثر الشائعة: {top_causes}\n"
        "قدّم ما بين 4 إلى 6 توصيات كقائمة JSON حصراً بالصيغة:\n"
        '[{"type":"quantitative|academic|statistical_alert|positive|administrative","text":"..."}]'
    )


def _fallback_recommendation(overview: dict) -> list[dict]:
    at_risk = overview["summary"]["at_risk"]["count"]
    total = overview["summary"]["total_students"] or 1
    pct = round((at_risk / total) * 100)
    return [{"type": "statistical_alert",
             "text": f"{at_risk} طالب في فئة الخطر حالياً ({pct}%). يُنصح بمراجعة قائمة التدخل.",
             "icon": _ICONS["statistical_alert"]}]


@router.get("/ai/insights/recommendations-ai")
async def get_recommendations_ai(
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    school_id = current_user["tenant_id"]
    now = datetime.now(timezone.utc).timestamp()
    cached = _REC_CACHE.get(school_id)
    if cached and now - cached[0] < _REC_TTL_SEC:
        return cached[1]

    overview = await get_students_overview(refresh=0, current_user=current_user)
    prompt = _build_recs_prompt(overview)
    try:
        raw = await _call_openai_for_recommendations(prompt)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = parsed.get("recommendations") or parsed.get("items") or []
        if not (isinstance(parsed, list) and parsed):
            raise ValueError("invalid model output")
        clean = []
        for item in parsed[:6]:
            t = item.get("type")
            text = (item.get("text") or "").strip()
            if t in _ICONS and text:
                clean.append({"type": t, "text": text, "icon": _ICONS[t]})
        if not clean:
            raise ValueError("empty after validation")
        payload = {"recommendations": clean,
                   "generated_at": datetime.now(timezone.utc).isoformat(),
                   "source": "openai"}
    except Exception:
        payload = {"recommendations": _fallback_recommendation(overview),
                   "generated_at": datetime.now(timezone.utc).isoformat(),
                   "source": "fallback"}

    _REC_CACHE[school_id] = (now, payload)
    return payload


@router.get("/ai/insights/at-risk-students")
async def get_at_risk_students(
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN,
        UserRole.SCHOOL_PRINCIPAL, UserRole.TEACHER,
        UserRole.INDEPENDENT_TEACHER,
    ])),
):
    role = current_user.get("role", "")

    # Tri-state authorization sentinel must be resolved before ANY business
    # data query for teacher-class callers (Task #154 / H1).
    if role in _TEACHER_CLASS_ROLES:
        scope_result = await resolve_ai_insights_scope(current_user)
        if scope_result is NO_AUTHORIZED_SCOPE:
            return []
        scope = scope_result if isinstance(scope_result, dict) else {}
        student_ids = scope.get("student_ids") or []
        class_ids = scope.get("class_ids") or []
        school_id = scope.get("school_id") or current_user.get("tenant_id")
        if not student_ids:
            return []

        students = await gd_find(db.session, "students", {
            "school_id": school_id,
            "id": {"$in": student_ids},
        }, limit=2000)
        classes = await gd_find(db.session, "classes", {
            "school_id": school_id,
            "id": {"$in": class_ids},
        }, limit=200) if class_ids else []
        cls_name_map = {c["id"]: c.get("name", c["id"]) for c in classes}

        month_ago_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        month_ago_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

        att_rows = await gd_find(db.session, "attendance", {
            "school_id": school_id,
            "student_id": {"$in": student_ids},
            "date": {"$gte": month_ago_date},
        }, limit=20000)
        grade_rows = await gd_find(db.session, "grades", {
            "school_id": school_id,
            "student_id": {"$in": student_ids},
            "created_at": {"$gte": month_ago_iso},
        }, limit=20000)

        att_by_student: Dict[str, Dict[str, int]] = {}
        for r in att_rows:
            sid = r.get("student_id")
            if not sid:
                continue
            entry = att_by_student.setdefault(sid, {"total": 0, "present": 0})
            entry["total"] += 1
            if r.get("status") == "present":
                entry["present"] += 1

        grades_by_student: Dict[str, List[float]] = {}
        for g in grade_rows:
            sid = g.get("student_id")
            if not sid:
                continue
            pct = g.get("percentage")
            if isinstance(pct, (int, float)):
                grades_by_student.setdefault(sid, []).append(float(pct))

        at_risk: List[Dict[str, Any]] = []
        for s in students:
            sid = s.get("id")
            att = att_by_student.get(sid, {"total": 0, "present": 0})
            att_rate = round((att["present"] / att["total"]) * 100, 1) if att["total"] > 0 else 100.0
            grades = grades_by_student.get(sid, [])
            grade_avg = round(sum(grades) / len(grades), 1) if grades else 100.0

            factors: List[str] = []
            issue_type = None
            if att_rate < 80:
                factors.append("انخفاض الحضور")
                issue_type = "attendance"
            if grade_avg < 60:
                factors.append("تدني الأداء الأكاديمي")
                issue_type = issue_type or "academic"
            if not factors:
                continue

            risk_score = int(min(att_rate, grade_avg))
            at_risk.append({
                "id": sid,
                "name": s.get("full_name") or s.get("name") or "—",
                "grade": cls_name_map.get(s.get("class_id"), s.get("grade") or ""),
                "risk_level": risk_score,
                "risk_type": issue_type or "attendance",
                "factors": factors,
            })

        at_risk.sort(key=lambda r: r["risk_level"])
        return at_risk[:20]

    overview = await get_students_overview(refresh=0, current_user=current_user)
    result = []
    for row in overview["intervention_list"][:20]:
        result.append({
            "id": row["student_id"],
            "name": row["name"],
            "grade": row["class_name"],
            "risk_level": row["risk_score"],
            "risk_type": row["issue_type"],
            "factors": [row["issue_label_ar"]],
        })
    return result





# ============== PHASE 6: HAKIM AI ENGINE APIs ==============

ADMIN_ROLES_SET = {
    UserRole.PLATFORM_ADMIN.value, UserRole.SCHOOL_ADMIN.value,
    UserRole.SCHOOL_PRINCIPAL.value, UserRole.SCHOOL_SUB_ADMIN.value,
}

@router.get("/hakim/student/{student_id}/risk")
async def hakim_student_risk(
    student_id: str,
    days: int = Query(30, ge=7, le=365),
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    student = await gd_find_one(db.session, "students", {"id": student_id, "school_id": school_id})
    if not student:
        raise HTTPException(404, "الطالب غير موجود في هذه المدرسة")
    return await hakim_engine.analyze_student_risk(student_id, school_id, days)

@router.get("/hakim/class/{class_id}/participation")
async def hakim_class_participation(
    class_id: str,
    days: int = Query(30, ge=7, le=365),
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    cls = await gd_find_one(db.session, "classes", {"id": class_id, "school_id": school_id})
    if not cls:
        raise HTTPException(404, "الفصل غير موجود في هذه المدرسة")
    return await hakim_engine.analyze_class_participation(class_id, school_id, days)

@router.get("/hakim/student/{student_id}/behaviour")
async def hakim_student_behaviour(
    student_id: str,
    days: int = Query(60, ge=7, le=365),
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    student = await gd_find_one(db.session, "students", {"id": student_id, "school_id": school_id})
    if not student:
        raise HTTPException(404, "الطالب غير موجود في هذه المدرسة")
    return await hakim_engine.analyze_student_behaviour_patterns(student_id, school_id, days)

@router.get("/hakim/teacher/{teacher_id}/analytics")
async def hakim_teacher_analytics(
    teacher_id: str,
    days: int = Query(30, ge=7, le=365),
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id, "school_id": school_id})
    if not teacher:
        teacher_user = await gd_find_one(db.session, "users", {"teacher_id": teacher_id, "tenant_id": school_id})
        if not teacher_user:
            raise HTTPException(404, "المعلم غير موجود في هذه المدرسة")
    role = current_user.get("role", "")
    if role not in ADMIN_ROLES_SET and current_user.get("teacher_id") != teacher_id:
        raise HTTPException(403, "لا يمكنك عرض تحليلات معلم آخر")
    return await hakim_engine.analyze_teacher_sessions(teacher_id, school_id, days)

@router.get("/hakim/class/{class_id}/health")
async def hakim_class_health(
    class_id: str,
    days: int = Query(30, ge=7, le=365),
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    cls = await gd_find_one(db.session, "classes", {"id": class_id, "school_id": school_id})
    if not cls:
        raise HTTPException(404, "الفصل غير موجود في هذه المدرسة")
    return await hakim_engine.analyze_class_health(class_id, school_id, days)

@router.post("/hakim/school/analyze")
async def hakim_full_analysis_school(
    days: int = Query(30, ge=7, le=365),
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await hakim_engine.run_full_analysis(school_id, days)

@router.post("/hakim/analyze/{school_id}")
async def hakim_full_analysis_by_id(
    school_id: str,
    days: int = Query(30, ge=7, le=365),
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    role = current_user.get("role", "")
    if role != UserRole.PLATFORM_ADMIN.value:
        user_school = current_user.get("tenant_id")
        if user_school != school_id:
            raise HTTPException(403, "لا يمكنك تحليل مدرسة أخرى")
    school = await gd_find_one(db.session, "schools", {"id": school_id})
    if not school:
        raise HTTPException(404, "المدرسة غير موجودة")
    return await hakim_engine.run_full_analysis(school_id, days)

@router.get("/hakim/insights")
async def hakim_get_insights(
    limit: int = Query(20, ge=1, le=100),
    school_id: str = Query(None),
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("role", "")
    if school_id and role in ("platform_admin", "platform_operations_manager"):
        target_school = school_id
    else:
        target_school = current_user.get("tenant_id")
    if not target_school:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await hakim_engine.get_school_insights(target_school, limit)


# ============== AUTO-INTERVENTION SYSTEM ==============

@router.post("/hakim/auto-interventions")
async def hakim_auto_interventions(
    days: int = Query(30, ge=7, le=365),
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await hakim_engine.execute_auto_interventions(school_id, days)


@router.post("/hakim/auto-interventions/{school_id}")
async def hakim_auto_interventions_by_school(
    school_id: str,
    days: int = Query(30, ge=7, le=365),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
):
    school = await gd_find_one(db.session, "schools", {"id": school_id})
    if not school:
        raise HTTPException(404, "المدرسة غير موجودة")
    return await hakim_engine.execute_auto_interventions(school_id, days)


@router.get("/hakim/interventions")
async def hakim_get_interventions(
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    query = {"school_id": school_id}
    if status:
        query["status"] = status
    interventions = await gd_find(db.session, "ai_interventions", query, order_by="created_at", desc_order=True, limit=limit)
    return {"interventions": interventions, "total": len(interventions)}


@router.put("/hakim/interventions/{intervention_id}/status")
async def hakim_update_intervention_status(
    intervention_id: str,
    new_status: str = Query(..., pattern="^(active|completed|dismissed|expired)$"),
    notes: str = Query(None),
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    school_id = current_user.get("tenant_id")
    intervention = await gd_find_one(db.session, "ai_interventions", {"id": intervention_id, "school_id": school_id})
    if not intervention:
        raise HTTPException(404, "خطة التدخل غير موجودة")

    now = datetime.now(timezone.utc).isoformat()
    update = {"status": new_status, "updated_at": now, "updated_by": current_user.get("id")}

    follow_up = {"action": f"تغيير الحالة إلى {new_status}", "by": current_user.get("id"), "at": now}
    if notes:
        follow_up["notes"] = notes

    update["follow_ups"] = (await gd_find_one(db.session, "ai_interventions", {"id": intervention_id}) or {}).get("follow_ups", []) or []
    update["follow_ups"].append(follow_up)
    await gd_update_one(db.session, "ai_interventions", {"id": intervention_id}, update)
    return {"success": True, "message": "تم تحديث حالة خطة التدخل"}


# ============== IMPROVEMENT PLAN ==============

@router.get("/hakim/student/{student_id}/improvement-plan")
async def hakim_student_improvement_plan(
    student_id: str,
    days: int = Query(30, ge=7, le=365),
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    student = await gd_find_one(db.session, "students", {"id": student_id, "school_id": school_id})
    if not student:
        raise HTTPException(404, "الطالب غير موجود في هذه المدرسة")
    return await hakim_engine.generate_improvement_plan(student_id, school_id, days)


@router.post("/hakim/student/{student_id}/ai-plans")
async def hakim_student_ai_plans(
    student_id: str,
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    student = await gd_find_one(db.session, "students", {"id": student_id, "school_id": school_id})
    if not student:
        raise HTTPException(404, "الطالب غير موجود في هذه المدرسة")

    plan_data = await hakim_engine.generate_improvement_plan(student_id, school_id, 30)

    student_name = student.get("full_name", "الطالب")
    strengths = plan_data.get("strengths", [])
    weaknesses = plan_data.get("weaknesses", [])
    goals = plan_data.get("goals", [])
    risk_score = plan_data.get("risk_assessment", {}).get("score", 50)

    strengths_text = "، ".join(strengths) if strengths else "لا توجد نقاط قوة واضحة بعد"
    weaknesses_text = "، ".join(weaknesses) if weaknesses else "لا توجد نقاط ضعف"
    goals_text = "\n".join([f"- {g['goal_ar']}" for g in goals]) if goals else "لا توجد أهداف محددة"

    prompt = f"""أنت حكيم، المساعد الذكي لنظام نَسَّق التعليمي. أنشئ خطتين للطالب/ة {student_name}:

بيانات الطالب:
- مؤشر المخاطر: {risk_score}%
- نقاط القوة: {strengths_text}
- نقاط الضعف: {weaknesses_text}
- الأهداف: 
{goals_text}

أنشئ خطتين بتنسيق JSON:
1. الخطة العلاجية (remedial_plan): لمعالجة نقاط الضعف وتحسينها
2. الخطة الإثرائية (enrichment_plan): لتعزيز نقاط القوة وتطويرها

كل خطة يجب أن تحتوي على:
- title: عنوان الخطة
- summary: ملخص قصير (جملة واحدة)
- steps: مصفوفة من 3-5 خطوات، كل خطة تحتوي على (title, description, duration, responsible)
- expected_outcome: النتيجة المتوقعة

أجب بـ JSON فقط بدون أي نص إضافي بالشكل التالي:
{{"remedial_plan": {{...}}, "enrichment_plan": {{...}}}}"""

    try:
        client = get_openai_client()
        if client is None:
            plan_source = "fallback"
            raise ValueError("AI not configured")
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": "أنت مساعد تعليمي ذكي متخصص في إنشاء خطط تعليمية. أجب بـ JSON فقط."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        import json as json_module
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        plans = json_module.loads(raw)
        plan_source = "ai"
    except Exception as exc:
        import logging
        logging.getLogger("nassaq.ai_plans").warning("AI plan generation fell back to defaults: %s", exc)
        plan_source = "fallback"
        plans = {
            "remedial_plan": {
                "title": "الخطة العلاجية",
                "summary": f"خطة لمعالجة نقاط الضعف: {weaknesses_text}",
                "steps": [
                    {"title": "تشخيص نقاط الضعف", "description": "تحديد المهارات التي تحتاج تحسين بدقة", "duration": "أسبوع", "responsible": "معلم المادة"},
                    {"title": "جلسات تقوية فردية", "description": "حصص إضافية مركزة على المهارات الضعيفة", "duration": "أسبوعين", "responsible": "معلم المادة"},
                    {"title": "تقييم التقدم", "description": "اختبار قصير لقياس مدى التحسن", "duration": "أسبوع", "responsible": "المرشد الأكاديمي"},
                ],
                "expected_outcome": "تحسن ملموس في نقاط الضعف المحددة خلال شهر"
            },
            "enrichment_plan": {
                "title": "الخطة الإثرائية",
                "summary": f"خطة لتعزيز نقاط القوة: {strengths_text}",
                "steps": [
                    {"title": "تحديد مجالات التميز", "description": "رصد المهارات والمواد التي يتفوق فيها الطالب", "duration": "أسبوع", "responsible": "معلم المادة"},
                    {"title": "أنشطة إثرائية متقدمة", "description": "توفير تحديات ومشاريع إضافية تناسب مستوى الطالب", "duration": "شهر", "responsible": "معلم المادة"},
                    {"title": "برنامج القيادة الطلابية", "description": "إشراك الطالب في أدوار قيادية ومساعدة زملائه", "duration": "مستمر", "responsible": "المرشد الطلابي"},
                ],
                "expected_outcome": "تطوير مهارات الطالب المتميزة واستثمارها في مساعدة الآخرين"
            }
        }

    generated_at = datetime.now(timezone.utc).isoformat()
    history_doc = {
        "id": str(uuid.uuid4()),
        "student_id": student_id,
        "school_id": school_id,
        "plans": plans,
        "plan_source": plan_source,
        "generated_by": current_user.get("user_id"),
        "generated_by_name": current_user.get("full_name", ""),
        "generated_at": generated_at,
    }
    try:
        await gd_insert(db.session, "plan_history", history_doc)
    except Exception as e:
        print(f"[WARN] Failed to save plan history: {e}")

    return {
        "success": True,
        "student_name": student_name,
        "risk_score": risk_score,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "plans": plans,
        "plan_source": plan_source,
        "generated_at": generated_at
    }


@router.get("/hakim/student/{student_id}/plan-history")
async def get_student_plan_history(
    student_id: str,
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    records = await gd_find(db.session, "plan_history", {"student_id": student_id, "school_id": school_id}, order_by="generated_at", desc_order=True, limit=50)
    for r in records:
        r.pop("_id", None)
    return records


@router.post("/export/student-plans/{student_id}")
async def export_student_plans_docx(
    student_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    from docx import Document
    from docx.shared import Inches, Pt, Cm, RGBColor, Emu
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn, nsdecls
    from docx.oxml import parse_xml

    body = await request.json()
    plan_type = body.get("plan_type", "both")
    remedial_plan = body.get("remedial_plan")
    enrichment_plan = body.get("enrichment_plan")

    if plan_type == "remedial" and not remedial_plan:
        raise HTTPException(400, "الخطة العلاجية غير متوفرة")
    if plan_type == "enrichment" and not enrichment_plan:
        raise HTTPException(400, "الخطة الإثرائية غير متوفرة")
    if plan_type == "both" and not remedial_plan and not enrichment_plan:
        raise HTTPException(400, "لا توجد خطط للتصدير")

    school_id = current_user.get("tenant_id")
    student = await gd_find_one(db.session, "students", {"id": student_id, "school_id": school_id})
    if not student:
        raise HTTPException(404, "الطالب غير موجود")

    school = await gd_find_one(db.session, "schools", {"id": school_id})
    school_name = school.get("name", "") if school else ""

    class_name = ""
    class_id = student.get("class_id")
    if class_id:
        class_doc = await gd_find_one(db.session, "classes", {"id": class_id})
        class_name = class_doc.get("name", "") if class_doc else ""

    academic_year_name = ""
    ay_doc = await gd_find_one(db.session, "academic_years", {"school_id": school_id, "is_current": True})
    if ay_doc:
        academic_year_name = ay_doc.get("name", "")

    teacher_name = ""
    user_role = current_user.get("role", "")
    if user_role == "teacher":
        teacher_doc = await gd_find_one(db.session, "teachers", {"user_id": current_user.get("sub")})
        teacher_name = teacher_doc.get("full_name", "") if teacher_doc else current_user.get("full_name", "")
    else:
        teacher_name = current_user.get("full_name", user_role)

    student_name = student.get("full_name", "")
    student_grade = student.get("grade", "")
    export_date = datetime.now().strftime("%Y-%m-%d")

    plan_label_map = {
        "remedial": "الخطة العلاجية",
        "enrichment": "الخطة الإثرائية",
        "both": "الخطة العلاجية والإثرائية",
    }
    plan_label = plan_label_map.get(plan_type, "الخطة")

    doc = Document()

    style = doc.styles['Normal']
    font = style.font
    font.name = 'Arial'
    font.size = Pt(11)
    font.rtl = True

    for section in doc.sections:
        section.top_margin = Cm(1.5)
        section.bottom_margin = Cm(1.5)
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)
        section_properties = section._sectPr
        bidi = parse_xml('<w:bidi {} />'.format(nsdecls('w')))
        section_properties.append(bidi)

    BRAND_NAVY = RGBColor(0x1C, 0x3D, 0x74)
    BRAND_TURQUOISE = RGBColor(0x46, 0xC1, 0xBE)
    BRAND_PURPLE = RGBColor(0x61, 0x50, 0x90)
    REMEDIAL_COLOR = RGBColor(0xE1, 0x4D, 0x2A)
    ENRICHMENT_COLOR = RGBColor(0x10, 0xB9, 0x81)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    DARK_GRAY = RGBColor(0x33, 0x33, 0x33)
    MED_GRAY = RGBColor(0x66, 0x66, 0x66)

    header_table = doc.add_table(rows=1, cols=1)
    header_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    header_cell = header_table.cell(0, 0)
    header_cell._element.get_or_add_tcPr().append(
        parse_xml(f'<w:shd {nsdecls("w")} w:fill="1C3D74"/>')
    )

    p = header_cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("نَسَّق  |  NASSAQ")
    run.font.size = Pt(22)
    run.font.bold = True
    run.font.color.rgb = WHITE

    p2 = header_cell.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = p2.add_run(plan_label)
    run2.font.size = Pt(14)
    run2.font.color.rgb = RGBColor(0xA0, 0xD0, 0xD0)
    run2.font.bold = True

    doc.add_paragraph()

    info_items = [
        ("اسم المدرسة", school_name or "—"),
        ("السنة الدراسية", academic_year_name or "—"),
        ("اسم الطالب", student_name or "—"),
        ("الصف / الفصل", f"{student_grade} — {class_name}".strip(" —") if (student_grade or class_name) else "—"),
        ("اسم المعلم", teacher_name or "—"),
        ("تاريخ التصدير", export_date),
    ]
    info_table = doc.add_table(rows=len(info_items), cols=2)
    info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    info_table.autofit = True

    info_data = info_items
    for i, (label, value) in enumerate(info_data):
        label_cell = info_table.cell(i, 1)
        value_cell = info_table.cell(i, 0)

        lp = label_cell.paragraphs[0]
        lp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        lr = lp.add_run(f"{label}:")
        lr.font.bold = True
        lr.font.size = Pt(11)
        lr.font.color.rgb = BRAND_NAVY

        vp = value_cell.paragraphs[0]
        vp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        vr = vp.add_run(value)
        vr.font.size = Pt(11)
        vr.font.color.rgb = DARK_GRAY

    for row in info_table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2)

    def add_divider():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("─" * 60)
        run.font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
        run.font.size = Pt(8)

    def add_plan_section(plan, plan_type_key):
        color = REMEDIAL_COLOR if plan_type_key == "remedial" else ENRICHMENT_COLOR
        type_label = "الخطة العلاجية" if plan_type_key == "remedial" else "الخطة الإثرائية"
        icon_char = "🩺" if plan_type_key == "remedial" else "🚀"

        add_divider()

        title_p = doc.add_paragraph()
        title_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        title_run = title_p.add_run(f"  {icon_char}  {plan.get('title', type_label)}")
        title_run.font.size = Pt(16)
        title_run.font.bold = True
        title_run.font.color.rgb = color

        summary = plan.get("summary", "")
        if summary:
            sp = doc.add_paragraph()
            sp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            sr = sp.add_run(summary)
            sr.font.size = Pt(11)
            sr.font.color.rgb = MED_GRAY
            sr.font.italic = True

        steps = plan.get("steps", [])
        if steps:
            steps_heading = doc.add_paragraph()
            steps_heading.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            sh_run = steps_heading.add_run("خطوات التنفيذ:")
            sh_run.font.size = Pt(13)
            sh_run.font.bold = True
            sh_run.font.color.rgb = BRAND_NAVY
            steps_heading.paragraph_format.space_before = Pt(12)

            steps_table = doc.add_table(rows=len(steps) + 1, cols=4)
            steps_table.alignment = WD_TABLE_ALIGNMENT.CENTER
            steps_table.autofit = True

            headers = ["المسؤول", "المدة", "الوصف", "الخطوة"]
            for j, h in enumerate(headers):
                cell = steps_table.cell(0, j)
                cell._element.get_or_add_tcPr().append(
                    parse_xml(f'<w:shd {nsdecls("w")} w:fill="1C3D74"/>')
                )
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = p.add_run(h)
                r.font.bold = True
                r.font.size = Pt(10)
                r.font.color.rgb = WHITE

            for idx, step in enumerate(steps):
                row_cells = steps_table.row_cells(idx + 1)
                values = [
                    step.get("responsible", "—"),
                    step.get("duration", "—"),
                    step.get("description", "—"),
                    step.get("title", f"خطوة {idx + 1}"),
                ]
                bg_hex = "F9FAFB" if idx % 2 == 0 else "FFFFFF"
                for j, val in enumerate(values):
                    cell = row_cells[j]
                    cell._element.get_or_add_tcPr().append(
                        parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg_hex}"/>')
                    )
                    p = cell.paragraphs[0]
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    r = p.add_run(val)
                    r.font.size = Pt(10)
                    r.font.color.rgb = DARK_GRAY

        outcome = plan.get("expected_outcome", "")
        if outcome:
            doc.add_paragraph()
            outcome_p = doc.add_paragraph()
            outcome_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            ol = outcome_p.add_run("النتيجة المتوقعة: ")
            ol.font.bold = True
            ol.font.size = Pt(11)
            ol.font.color.rgb = color
            ov = outcome_p.add_run(outcome)
            ov.font.size = Pt(11)
            ov.font.color.rgb = DARK_GRAY

    if plan_type in ("remedial", "both") and remedial_plan:
        add_plan_section(remedial_plan, "remedial")

    if plan_type in ("enrichment", "both") and enrichment_plan:
        add_plan_section(enrichment_plan, "enrichment")

    add_divider()
    footer_p = doc.add_paragraph()
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = footer_p.add_run(f"تم التصدير من نظام نَسَّق  •  {export_date}")
    fr.font.size = Pt(9)
    fr.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    fr.font.italic = True

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    safe_name = student_name.replace(" ", "_")
    type_suffix = {"remedial": "Remedial_Plan", "enrichment": "Enrichment_Plan", "both": "Plans"}
    filename = f"{safe_name}_{type_suffix.get(plan_type, 'Plan')}_{export_date}.docx"

    from urllib.parse import quote
    encoded_filename = quote(filename)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
    )


@router.post("/export/student-plans/{student_id}/pdf")
async def export_student_plans_pdf(
    student_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    import arabic_reshaper
    from bidi.algorithm import get_display
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm, mm
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    try:
        pdfmetrics.registerFont(TTFont('DejaVuSans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
    except Exception as e:
        logger.debug(f"DejaVu font registration failed (PDF will use fallback fonts): {e}")

    def ar(text):
        if not text:
            return ""
        try:
            reshaped = arabic_reshaper.reshape(str(text))
            return get_display(reshaped)
        except Exception as e:
            logger.debug(f"Arabic text reshaping failed for '{str(text)[:30]}': {e}")
            return str(text)

    body = await request.json()
    plan_type = body.get("plan_type", "both")
    remedial_plan = body.get("remedial_plan")
    enrichment_plan = body.get("enrichment_plan")

    if plan_type == "remedial" and not remedial_plan:
        raise HTTPException(400, "الخطة العلاجية غير متوفرة")
    if plan_type == "enrichment" and not enrichment_plan:
        raise HTTPException(400, "الخطة الإثرائية غير متوفرة")
    if plan_type == "both" and not remedial_plan and not enrichment_plan:
        raise HTTPException(400, "لا توجد خطط للتصدير")

    school_id = current_user.get("tenant_id")
    student = await gd_find_one(db.session, "students", {"id": student_id, "school_id": school_id})
    if not student:
        raise HTTPException(404, "الطالب غير موجود")

    school = await gd_find_one(db.session, "schools", {"id": school_id})
    school_name = school.get("name", "") if school else ""

    class_name = ""
    class_id = student.get("class_id")
    if class_id:
        class_doc = await gd_find_one(db.session, "classes", {"id": class_id})
        class_name = class_doc.get("name", "") if class_doc else ""

    academic_year_name = ""
    ay_doc = await gd_find_one(db.session, "academic_years", {"school_id": school_id, "is_current": True})
    if ay_doc:
        academic_year_name = ay_doc.get("name", "")

    teacher_name = ""
    user_role = current_user.get("role", "")
    if user_role == "teacher":
        teacher_doc = await gd_find_one(db.session, "teachers", {"user_id": current_user.get("sub")})
        teacher_name = teacher_doc.get("full_name", "") if teacher_doc else current_user.get("full_name", "")
    else:
        teacher_name = current_user.get("full_name", user_role)

    student_name = student.get("full_name", "")
    student_grade = student.get("grade", "")
    export_date = datetime.now().strftime("%Y-%m-%d")

    plan_label_map = {
        "remedial": "الخطة العلاجية",
        "enrichment": "الخطة الإثرائية",
        "both": "الخطة العلاجية والإثرائية",
    }
    plan_label = plan_label_map.get(plan_type, "الخطة")

    NAVY = HexColor("#1C3D74")
    TURQUOISE = HexColor("#46C1BE")
    REMEDIAL_CLR = HexColor("#E14D2A")
    ENRICHMENT_CLR = HexColor("#10B981")
    LIGHT_GRAY = HexColor("#F3F4F6")
    MED_GRAY_CLR = HexColor("#666666")
    DARK_GRAY_CLR = HexColor("#333333")

    style_title = ParagraphStyle('Title', fontName='DejaVuSans-Bold', fontSize=18, alignment=TA_CENTER, textColor=white, leading=24)
    style_subtitle = ParagraphStyle('Subtitle', fontName='DejaVuSans-Bold', fontSize=12, alignment=TA_CENTER, textColor=HexColor("#A0D0D0"), leading=16)
    style_label = ParagraphStyle('Label', fontName='DejaVuSans-Bold', fontSize=10, alignment=TA_RIGHT, textColor=NAVY, leading=14)
    style_value = ParagraphStyle('Value', fontName='DejaVuSans', fontSize=10, alignment=TA_RIGHT, textColor=DARK_GRAY_CLR, leading=14)
    style_section = ParagraphStyle('Section', fontName='DejaVuSans-Bold', fontSize=14, alignment=TA_RIGHT, textColor=NAVY, leading=18)
    style_body = ParagraphStyle('Body', fontName='DejaVuSans', fontSize=10, alignment=TA_RIGHT, textColor=DARK_GRAY_CLR, leading=14, wordWrap='RTL')
    style_body_italic = ParagraphStyle('BodyItalic', fontName='DejaVuSans', fontSize=10, alignment=TA_RIGHT, textColor=MED_GRAY_CLR, leading=14)
    style_footer = ParagraphStyle('Footer', fontName='DejaVuSans', fontSize=8, alignment=TA_CENTER, textColor=MED_GRAY_CLR, leading=12)
    style_table_header = ParagraphStyle('TH', fontName='DejaVuSans-Bold', fontSize=9, alignment=TA_CENTER, textColor=white, leading=12)
    style_table_cell = ParagraphStyle('TD', fontName='DejaVuSans', fontSize=9, alignment=TA_RIGHT, textColor=DARK_GRAY_CLR, leading=12)

    story = []

    header_data = [[Paragraph(ar("NASSAQ  |  نَسَّق"), style_title)],
                    [Paragraph(ar(plan_label), style_subtitle)]]
    header_table = Table(header_data, colWidths=[17*cm])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NAVY),
        ('TOPPADDING', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('ROUNDEDCORNERS', [6, 6, 0, 0]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 12))

    grade_class = f"{student_grade} — {class_name}".strip(" —") if (student_grade or class_name) else "—"
    info_rows = [
        [Paragraph(ar(school_name or "—"), style_value), Paragraph(ar("اسم المدرسة"), style_label)],
        [Paragraph(ar(academic_year_name or "—"), style_value), Paragraph(ar("السنة الدراسية"), style_label)],
        [Paragraph(ar(student_name or "—"), style_value), Paragraph(ar("اسم الطالب"), style_label)],
        [Paragraph(ar(grade_class), style_value), Paragraph(ar("الصف / الفصل"), style_label)],
        [Paragraph(ar(teacher_name or "—"), style_value), Paragraph(ar("اسم المعلم"), style_label)],
        [Paragraph(ar(export_date), style_value), Paragraph(ar("تاريخ التصدير"), style_label)],
    ]
    info_tbl = Table(info_rows, colWidths=[11*cm, 6*cm])
    info_tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#DDDDDD")),
        ('BACKGROUND', (1, 0), (1, -1), LIGHT_GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(info_tbl)

    def add_plan_section(plan, plan_type_key):
        color = REMEDIAL_CLR if plan_type_key == "remedial" else ENRICHMENT_CLR
        type_label = "الخطة العلاجية" if plan_type_key == "remedial" else "الخطة الإثرائية"

        story.append(Spacer(1, 16))
        story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#CCCCCC")))
        story.append(Spacer(1, 10))

        section_style = ParagraphStyle('PlanTitle', fontName='DejaVuSans-Bold', fontSize=14, alignment=TA_RIGHT, textColor=color, leading=18)
        title_text = plan.get("title", type_label) if plan else type_label
        story.append(Paragraph(ar(title_text), section_style))
        story.append(Spacer(1, 6))

        summary = plan.get("summary", "") if plan else ""
        if summary:
            story.append(Paragraph(ar(summary), style_body_italic))
            story.append(Spacer(1, 8))

        goals = plan.get("goals", []) if plan else []
        if goals:
            story.append(Paragraph(ar("الأهداف:"), style_section))
            story.append(Spacer(1, 4))
            for g in goals:
                goal_text = g if isinstance(g, str) else g.get("description", str(g))
                story.append(Paragraph(ar(f"• {goal_text}"), style_body))
            story.append(Spacer(1, 8))

        steps = plan.get("steps", []) if plan else []
        if steps:
            story.append(Paragraph(ar("خطوات التنفيذ:"), style_section))
            story.append(Spacer(1, 6))

            step_headers = [
                Paragraph(ar("المسؤول"), style_table_header),
                Paragraph(ar("المدة"), style_table_header),
                Paragraph(ar("الوصف"), style_table_header),
                Paragraph(ar("الخطوة"), style_table_header),
            ]
            step_rows = [step_headers]
            for idx, step in enumerate(steps):
                step_rows.append([
                    Paragraph(ar(step.get("responsible", "—")), style_table_cell),
                    Paragraph(ar(step.get("duration", "—")), style_table_cell),
                    Paragraph(ar(step.get("description", "—")), style_table_cell),
                    Paragraph(ar(step.get("title", f"خطوة {idx + 1}")), style_table_cell),
                ])

            step_tbl = Table(step_rows, colWidths=[3.5*cm, 3*cm, 7*cm, 3.5*cm])
            step_style_cmds = [
                ('BACKGROUND', (0, 0), (-1, 0), NAVY),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#DDDDDD")),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]
            for idx in range(1, len(step_rows)):
                bg = LIGHT_GRAY if idx % 2 == 1 else white
                step_style_cmds.append(('BACKGROUND', (0, idx), (-1, idx), bg))
            step_tbl.setStyle(TableStyle(step_style_cmds))
            story.append(step_tbl)

        notes = plan.get("notes", "") if plan else ""
        if notes:
            story.append(Spacer(1, 8))
            story.append(Paragraph(ar(f"ملاحظات: {notes}"), style_body))

        outcome = plan.get("expected_outcome", "") if plan else ""
        if outcome:
            story.append(Spacer(1, 8))
            outcome_style = ParagraphStyle('Outcome', fontName='DejaVuSans-Bold', fontSize=10, alignment=TA_RIGHT, textColor=color, leading=14)
            story.append(Paragraph(ar(f"النتيجة المتوقعة: {outcome}"), outcome_style))

    if plan_type in ("remedial", "both") and remedial_plan:
        add_plan_section(remedial_plan, "remedial")

    if plan_type in ("enrichment", "both") and enrichment_plan:
        add_plan_section(enrichment_plan, "enrichment")

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#CCCCCC")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(ar(f"تم التصدير من نظام نَسَّق  •  {export_date}"), style_footer))

    buffer = io.BytesIO()
    pdf_doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        leftMargin=2*cm, rightMargin=2*cm,
        title=plan_label, author="NASSAQ"
    )
    pdf_doc.build(story)
    buffer.seek(0)

    safe_name = student_name.replace(" ", "_")
    type_suffix = {"remedial": "Remedial_Plan", "enrichment": "Enrichment_Plan", "both": "Plans"}
    filename = f"{safe_name}_{type_suffix.get(plan_type, 'Plan')}_{export_date}.pdf"

    from urllib.parse import quote
    encoded_filename = quote(filename)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
    )


# ============== GRADE DECLINE DETECTION ==============

@router.get("/hakim/student/{student_id}/grade-trend")
async def hakim_student_grade_trend(
    student_id: str,
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await hakim_engine.detect_student_grade_trend(student_id, school_id)


@router.get("/hakim/grade-decline-alerts")
async def hakim_grade_decline_alerts(
    threshold: float = Query(-10.0, le=0),
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await hakim_engine.detect_grade_decline_alerts(school_id, threshold)


# ============== SCHEDULE ADJUSTMENT SUGGESTIONS ==============

@router.get("/hakim/schedule-suggestions")
async def hakim_schedule_suggestions(
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await hakim_engine.suggest_schedule_adjustments(school_id)


# ============== PERIODIC SCAN ==============

@router.post("/hakim/periodic-scan")
async def hakim_periodic_scan(
    days: int = Query(30, ge=7, le=365),
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await hakim_engine.run_periodic_scan(school_id, days)


@router.post("/hakim/periodic-scan/{school_id}")
async def hakim_periodic_scan_by_school(
    school_id: str,
    days: int = Query(30, ge=7, le=365),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
):
    school = await gd_find_one(db.session, "schools", {"id": school_id})
    if not school:
        raise HTTPException(404, "المدرسة غير موجودة")
    return await hakim_engine.run_periodic_scan(school_id, days)


@router.get("/student/{student_id}/longitudinal")
async def get_student_longitudinal(
    student_id: str,
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    student = await gd_find_one(db.session, "students", {"id": student_id, "school_id": school_id})
    if not student:
        raise HTTPException(404, "الطالب غير موجود")

    attendance_records = await gd_find(db.session, "attendance", {"student_id": student_id, "school_id": school_id}, limit=10000)

    behaviour_records = await gd_find(db.session, "behaviour_records", {"student_id": student_id, "school_id": school_id}, limit=5000)

    activities = await gd_find(db.session, "student_activities", {"student_id": student_id, "school_id": school_id}, limit=500)

    certificates = await gd_find(db.session, "student_certificates", {"student_id": student_id, "school_id": school_id}, limit=500)

    grades_records = await gd_find(db.session, "grades", {"student_id": student_id, "school_id": school_id}, limit=5000)

    skill_records = await gd_find(db.session, "student_skills", {"student_id": student_id, "school_id": school_id}, limit=2000)

    classes = await gd_find(db.session, "classes", {"school_id": school_id}, limit=500)
    class_map = {c["id"]: c.get("name", "") for c in classes}

    teachers = await gd_find(db.session, "teachers", {"school_id": school_id}, limit=500)
    teacher_map = {t.get("id", ""): t.get("full_name", "") for t in teachers}

    def extract_year(date_str):
        if not date_str:
            return None
        try:
            if isinstance(date_str, str):
                for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%f"]:
                    try:
                        return datetime.strptime(date_str[:19], fmt[:len(date_str[:19])]).year
                    except ValueError:
                        continue
                if len(date_str) >= 4 and date_str[:4].isdigit():
                    return int(date_str[:4])
            return None
        except Exception as e:
            logger.debug(f"Date year extraction failed for '{date_str}': {e}")
            return None

    years_set = set()
    for r in attendance_records:
        y = extract_year(r.get("date"))
        if y:
            years_set.add(y)
    for r in behaviour_records:
        y = extract_year(r.get("incident_date") or r.get("created_at"))
        if y:
            years_set.add(y)
    for r in grades_records:
        y = extract_year(r.get("recorded_at") or r.get("created_at"))
        if y:
            years_set.add(y)
    for r in activities:
        y = extract_year(r.get("date") or r.get("created_at"))
        if y:
            years_set.add(y)
    for r in certificates:
        y = extract_year(r.get("date") or r.get("created_at"))
        if y:
            years_set.add(y)

    if not years_set:
        years_set.add(datetime.now().year)

    timeline = []
    for year in sorted(years_set):
        yr_attendance = [r for r in attendance_records if extract_year(r.get("date")) == year]
        present = sum(1 for r in yr_attendance if r.get("status") in ("present", "late"))
        total_att = len(yr_attendance) if yr_attendance else 1
        att_rate = round((present / total_att) * 100, 1) if total_att > 0 else 0

        yr_behaviour = [r for r in behaviour_records if extract_year(r.get("incident_date") or r.get("created_at")) == year]
        pos_count = sum(1 for r in yr_behaviour if r.get("category") == "positive")
        neg_count = sum(1 for r in yr_behaviour if r.get("category") == "negative")

        yr_grades = [r for r in grades_records if extract_year(r.get("recorded_at") or r.get("created_at")) == year]
        avg_grade = 0
        if yr_grades:
            percentages = [g.get("percentage", 0) for g in yr_grades if g.get("percentage") is not None]
            if percentages:
                avg_grade = round(sum(percentages) / len(percentages), 1)

        yr_activities = [a for a in activities if extract_year(a.get("date") or a.get("created_at")) == year]
        yr_certificates = [c for c in certificates if extract_year(c.get("date") or c.get("created_at")) == year]

        achievements = []
        for c in yr_certificates:
            achievements.append(c.get("title", ""))
        for a in yr_activities:
            if a.get("name"):
                achievements.append(a.get("name", ""))

        top_talents = student.get("talents", [])[:3]

        class_name = class_map.get(student.get("class_id", ""), "")

        timeline.append({
            "year": year,
            "academic_year": f"{year}-{year+1}",
            "grade": student.get("grade", ""),
            "class_name": class_name,
            "teacher": "",
            "attendance_rate": att_rate,
            "top_talents": top_talents,
            "behaviour_positive": pos_count,
            "behaviour_negative": neg_count,
            "achievements": achievements[:5],
            "academic_average": avg_grade,
            "activities_count": len(yr_activities),
            "certificates_count": len(yr_certificates),
        })

    skill_growth = {}
    for sr in skill_records:
        skill_name = sr.get("skill_name", "")
        y = extract_year(sr.get("recorded_at") or sr.get("created_at"))
        level = sr.get("level", 0)
        if skill_name and y:
            if skill_name not in skill_growth:
                skill_growth[skill_name] = {}
            if y not in skill_growth[skill_name] or level > skill_growth[skill_name][y]:
                skill_growth[skill_name][y] = level

    skill_growth_data = []
    for skill_name, year_data in skill_growth.items():
        data_points = [{"year": y, "level": lvl} for y, lvl in sorted(year_data.items())]
        skill_growth_data.append({"skill": skill_name, "data": data_points})

    total_records = len(attendance_records) + len(grades_records) + len(behaviour_records) + len(activities) + len(certificates)
    talent_list = student.get("talents", [])

    academic_score = min(100, round(sum(g.get("percentage", 0) for g in grades_records[-20:]) / max(len(grades_records[-20:]), 1)))
    behaviour_score_val = min(100, max(0, 50 + (sum(1 for b in behaviour_records if b.get("category") == "positive") - sum(1 for b in behaviour_records if b.get("category") == "negative")) * 5))
    leadership_score = min(100, len([a for a in activities if a.get("role") and "leader" in (a.get("role", "").lower() + a.get("activity_type", "").lower())]) * 20 + len(certificates) * 10)
    social_score = min(100, len(activities) * 8 + (sum(1 for b in behaviour_records if b.get("category") == "positive") * 3))

    cluster_scores = []
    stem_signals = sum(1 for t in talent_list if t in ("scientific", "technological", "academically_gifted"))
    arts_signals = sum(1 for t in talent_list if t in ("artistic", "musical", "literary"))
    business_signals = sum(1 for t in talent_list if t in ("leadership", "entrepreneurial"))

    if stem_signals > 0 or academic_score > 60:
        cluster_scores.append({
            "name_ar": "العلوم والتكنولوجيا (STEM)",
            "name_en": "Science & Technology (STEM)",
            "match": min(95, stem_signals * 25 + academic_score // 3),
            "reason_ar": "بناءً على المواهب العلمية والأداء الأكاديمي",
            "reason_en": "Based on scientific talents and academic performance",
        })
    if arts_signals > 0 or any(a.get("activity_type") in ("arts", "cultural") for a in activities):
        cluster_scores.append({
            "name_ar": "الفنون والإبداع",
            "name_en": "Arts & Creative",
            "match": min(95, arts_signals * 25 + len([a for a in activities if a.get("activity_type") in ("arts", "cultural")]) * 10),
            "reason_ar": "بناءً على المواهب الفنية والأنشطة الإبداعية",
            "reason_en": "Based on artistic talents and creative activities",
        })
    if business_signals > 0 or leadership_score > 30:
        cluster_scores.append({
            "name_ar": "الأعمال والقيادة",
            "name_en": "Business & Leadership",
            "match": min(95, business_signals * 25 + leadership_score // 3),
            "reason_ar": "بناءً على المهارات القيادية والأنشطة المجتمعية",
            "reason_en": "Based on leadership skills and community activities",
        })
    if len(cluster_scores) < 3:
        defaults = [
            {"name_ar": "العلوم والتكنولوجيا (STEM)", "name_en": "Science & Technology (STEM)", "match": max(20, academic_score // 3), "reason_ar": "بناءً على الأداء الأكاديمي", "reason_en": "Based on academic performance"},
            {"name_ar": "الفنون والإبداع", "name_en": "Arts & Creative", "match": 15, "reason_ar": "لا توجد بيانات كافية بعد", "reason_en": "Insufficient data yet"},
            {"name_ar": "الأعمال والقيادة", "name_en": "Business & Leadership", "match": 15, "reason_ar": "لا توجد بيانات كافية بعد", "reason_en": "Insufficient data yet"},
        ]
        existing_names = {c["name_en"] for c in cluster_scores}
        for d in defaults:
            if d["name_en"] not in existing_names and len(cluster_scores) < 3:
                cluster_scores.append(d)

    cluster_scores.sort(key=lambda c: c["match"], reverse=True)

    return {
        "timeline": timeline,
        "skill_growth": skill_growth_data,
        "readiness": {
            "academic": academic_score,
            "social_emotional": social_score,
            "leadership": leadership_score,
            "career_alignment": max(c["match"] for c in cluster_scores) if cluster_scores else 0,
        },
        "career_clusters": cluster_scores[:3],
        "total_data_points": total_records,
    }


@router.post("/export/student-profile/{student_id}")
async def export_student_full_profile_docx(
    student_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    from docx import Document
    from docx.shared import Inches, Pt, Cm, RGBColor, Emu
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn, nsdecls
    from docx.oxml import parse_xml

    body = await request.json()
    sections = body.get("sections", [])

    school_id = current_user.get("tenant_id")
    student = await gd_find_one(db.session, "students", {"id": student_id, "school_id": school_id})
    if not student:
        raise HTTPException(404, "الطالب غير موجود")

    school = await gd_find_one(db.session, "schools", {"id": school_id})
    school_name = school.get("name", "") if school else ""
    class_name = ""
    if student.get("class_id"):
        cls = await gd_find_one(db.session, "classes", {"id": student["class_id"], "school_id": school_id})
        class_name = cls.get("name", "") if cls else ""

    export_date = datetime.now().strftime("%Y-%m-%d")
    exported_by = current_user.get("full_name", current_user.get("role", ""))

    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(11)

    section = doc.sections[0]
    section.top_margin = Cm(1.5)
    section.bottom_margin = Cm(1.5)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)
    sectPr = section._sectPr
    bidi_elem = parse_xml(f'<w:bidi {nsdecls("w")} />')
    sectPr.append(bidi_elem)

    def add_header_block():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("نَسَّق | NASSAQ")
        run.bold = True
        run.font.size = Pt(20)
        run.font.color.rgb = RGBColor(0x1C, 0x3D, 0x74)

        p2 = doc.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run2 = p2.add_run(school_name)
        run2.bold = True
        run2.font.size = Pt(14)
        run2.font.color.rgb = RGBColor(0x46, 0xC1, 0xBE)

        p3 = doc.add_paragraph()
        p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run3 = p3.add_run("الملف الشامل للطالب — Student Full Profile")
        run3.font.size = Pt(12)
        run3.font.color.rgb = RGBColor(0x61, 0x50, 0x90)

        info_table = doc.add_table(rows=1, cols=4)
        info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cells = info_table.rows[0].cells
        cells[0].text = f"الطالب: {student.get('full_name', '')}"
        cells[1].text = f"الرقم: {student.get('student_number', '')}"
        cells[2].text = f"الصف: {student.get('grade', '')} - {class_name}"
        cells[3].text = f"التاريخ: {export_date}"
        for cell in cells:
            for par in cell.paragraphs:
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for r in par.runs:
                    r.font.size = Pt(9)
        doc.add_paragraph()

    def add_section_title(title):
        p = doc.add_paragraph()
        run = p.add_run(f"■ {title}")
        run.bold = True
        run.font.size = Pt(14)
        run.font.color.rgb = RGBColor(0x1C, 0x3D, 0x74)
        p_fmt = p.paragraph_format
        p_fmt.space_before = Pt(12)
        p_fmt.space_after = Pt(6)

    def add_key_value(key, value):
        p = doc.add_paragraph()
        kr = p.add_run(f"{key}: ")
        kr.bold = True
        kr.font.size = Pt(10)
        kr.font.color.rgb = RGBColor(0x1C, 0x3D, 0x74)
        vr = p.add_run(str(value) if value else "—")
        vr.font.size = Pt(10)

    add_header_block()

    if "personal" in sections:
        add_section_title("المعلومات الشخصية وولي الأمر — Personal & Guardian Info")
        add_key_value("الاسم الكامل", student.get("full_name", ""))
        add_key_value("الاسم بالعربي", student.get("name_ar", ""))
        add_key_value("الجنس", student.get("gender", ""))
        add_key_value("تاريخ الميلاد", student.get("date_of_birth", ""))
        add_key_value("الرقم الوطني", student.get("national_id", ""))
        add_key_value("البريد الإلكتروني", student.get("email", ""))
        add_key_value("رقم ولي الأمر", student.get("parent_phone", ""))
        add_key_value("اسم ولي الأمر", student.get("parent_name", ""))
        add_key_value("بريد ولي الأمر", student.get("parent_email", ""))
        doc.add_paragraph()

    if "academic" in sections:
        add_section_title("الأداء الأكاديمي — Academic Performance")
        att_records = await gd_find(db.session, "attendance", {"student_id": student_id, "school_id": school_id}, limit=5000)
        total_att = len(att_records)
        present_c = sum(1 for r in att_records if r.get("status") in ("present", "late"))
        att_rate = round((present_c / max(total_att, 1)) * 100, 1)
        add_key_value("نسبة الحضور", f"{att_rate}%")

        gr = await gd_find(db.session, "grades", {"student_id": student_id, "school_id": school_id}, limit=5000)
        if gr:
            percs = [g.get("percentage", 0) for g in gr if g.get("percentage") is not None]
            avg = round(sum(percs) / max(len(percs), 1), 1) if percs else 0
            add_key_value("المعدل الأكاديمي", f"{avg}%")
            add_key_value("عدد التقييمات", len(gr))
        doc.add_paragraph()

    if "talents" in sections:
        add_section_title("المواهب والمهارات — Talents & Skills")
        talents = student.get("talents", [])
        if talents:
            add_key_value("المواهب", "، ".join(talents))
        else:
            add_key_value("المواهب", "لا توجد مواهب مسجلة")
        char_traits = student.get("character_traits", [])
        if char_traits:
            add_key_value("السمات الشخصية", "، ".join(char_traits))
        doc.add_paragraph()

    if "behaviour" in sections:
        add_section_title("السلوك — Behavior Record")
        beh = await gd_find(db.session, "behaviour_records", {"student_id": student_id, "school_id": school_id}, order_by="incident_date", desc_order=True, limit=500)
        pos = sum(1 for b in beh if b.get("category") == "positive")
        neg = sum(1 for b in beh if b.get("category") == "negative")
        add_key_value("إجمالي السجلات", len(beh))
        add_key_value("إيجابي", pos)
        add_key_value("سلبي", neg)
        if beh:
            table = doc.add_table(rows=1, cols=4)
            table.style = 'Table Grid'
            hdr = table.rows[0].cells
            hdr[0].text = "التاريخ"
            hdr[1].text = "العنوان"
            hdr[2].text = "التصنيف"
            hdr[3].text = "النقاط"
            for h in hdr:
                for p in h.paragraphs:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for r in p.runs:
                        r.bold = True
                        r.font.size = Pt(9)
            for b in beh[:30]:
                row = table.add_row().cells
                row[0].text = str(b.get("incident_date", ""))[:10]
                row[1].text = b.get("title", "")
                row[2].text = b.get("category", "")
                row[3].text = str(b.get("points", 0))
                for cell in row:
                    for p in cell.paragraphs:
                        for r in p.runs:
                            r.font.size = Pt(8)
        doc.add_paragraph()

    if "activities" in sections:
        add_section_title("الأنشطة والإنجازات — Activities & Achievements")
        acts = await gd_find(db.session, "student_activities", {"student_id": student_id, "school_id": school_id}, limit=200)
        certs = await gd_find(db.session, "student_certificates", {"student_id": student_id, "school_id": school_id}, limit=200)
        add_key_value("عدد الأنشطة", len(acts))
        add_key_value("عدد الشهادات", len(certs))
        if acts:
            for a in acts:
                p = doc.add_paragraph()
                run = p.add_run(f"• {a.get('name', '')} ({a.get('activity_type', '')}) — {a.get('date', '')}")
                run.font.size = Pt(9)
        if certs:
            p = doc.add_paragraph()
            run = p.add_run("الشهادات والجوائز:")
            run.bold = True
            run.font.size = Pt(10)
            for c in certs:
                p = doc.add_paragraph()
                run = p.add_run(f"🏆 {c.get('title', '')} — {c.get('issuing_body', '')} ({c.get('date', '')})")
                run.font.size = Pt(9)
        doc.add_paragraph()

    if "plans" in sections:
        add_section_title("الخطط العلاجية والإثرائية — Plans")
        plans = await gd_find_one(db.session, "student_ai_plans", {"student_id": student_id, "school_id": school_id})
        if plans:
            rp = plans.get("remedial_plan")
            ep = plans.get("enrichment_plan")
            if rp:
                p = doc.add_paragraph()
                run = p.add_run("الخطة العلاجية:")
                run.bold = True
                run.font.size = Pt(11)
                run.font.color.rgb = RGBColor(0xE1, 0x4D, 0x2A)
                if isinstance(rp, dict):
                    for key in ["title", "objective", "duration"]:
                        if rp.get(key):
                            add_key_value(key, rp[key])
                    steps = rp.get("steps", [])
                    for i, step in enumerate(steps, 1):
                        if isinstance(step, dict):
                            p = doc.add_paragraph()
                            run = p.add_run(f"  {i}. {step.get('title', '')} — {step.get('description', '')}")
                            run.font.size = Pt(9)
            if ep:
                p = doc.add_paragraph()
                run = p.add_run("الخطة الإثرائية:")
                run.bold = True
                run.font.size = Pt(11)
                run.font.color.rgb = RGBColor(0x10, 0xB9, 0x81)
                if isinstance(ep, dict):
                    for key in ["title", "objective", "duration"]:
                        if ep.get(key):
                            add_key_value(key, ep[key])
                    steps = ep.get("steps", [])
                    for i, step in enumerate(steps, 1):
                        if isinstance(step, dict):
                            p = doc.add_paragraph()
                            run = p.add_run(f"  {i}. {step.get('title', '')} — {step.get('description', '')}")
                            run.font.size = Pt(9)
        else:
            add_key_value("الخطط", "لا توجد خطط مسجلة")
        doc.add_paragraph()

    if "longitudinal" in sections:
        add_section_title("السجل التراكمي — Longitudinal Summary")
        add_key_value("الصف الحالي", f"{student.get('grade', '')} - {class_name}")
        add_key_value("حالة الطالب", "نشط" if student.get("is_active") != False else "معلق")
        talents = student.get("talents", [])
        add_key_value("المواهب", "، ".join(talents) if talents else "—")
        doc.add_paragraph()

    footer_p = doc.add_paragraph()
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = footer_p.add_run(f"تم التصدير بواسطة: {exported_by} | التاريخ: {export_date} | نَسَّق NASSAQ")
    fr.font.size = Pt(8)
    fr.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    filename = f"NASSAQ_Profile_{student.get('full_name', 'student')}_{export_date}.docx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/export/student-profile/{student_id}/pdf")
async def export_student_full_profile_pdf(
    student_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    import arabic_reshaper
    from bidi.algorithm import get_display
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    try:
        pdfmetrics.registerFont(TTFont('DejaVuSans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
    except Exception as e:
        logger.debug(f"DejaVu font registration failed (PDF will use fallback fonts): {e}")

    def ar(text):
        if not text:
            return ""
        try:
            reshaped = arabic_reshaper.reshape(str(text))
            return get_display(reshaped)
        except Exception as e:
            logger.debug(f"Arabic text reshaping failed for '{str(text)[:30]}': {e}")
            return str(text)

    body = await request.json()
    sections = body.get("sections", [])

    school_id = current_user.get("tenant_id")
    student = await gd_find_one(db.session, "students", {"id": student_id, "school_id": school_id})
    if not student:
        raise HTTPException(404, "الطالب غير موجود")

    school = await gd_find_one(db.session, "schools", {"id": school_id})
    school_name = school.get("name", "") if school else ""
    class_name = ""
    if student.get("class_id"):
        cls = await gd_find_one(db.session, "classes", {"id": student["class_id"], "school_id": school_id})
        class_name = cls.get("name", "") if cls else ""

    export_date = datetime.now().strftime("%Y-%m-%d")
    exported_by = current_user.get("full_name", current_user.get("role", ""))

    NAVY = HexColor("#1C3D74")
    TURQUOISE = HexColor("#46C1BE")
    LIGHT_GRAY = HexColor("#F3F4F6")

    style_title = ParagraphStyle('PTitle', fontName='DejaVuSans-Bold', fontSize=18, alignment=TA_CENTER, textColor=white, leading=24)
    style_subtitle = ParagraphStyle('PSubtitle', fontName='DejaVuSans-Bold', fontSize=12, alignment=TA_CENTER, textColor=TURQUOISE, leading=16)
    style_section = ParagraphStyle('PSection', fontName='DejaVuSans-Bold', fontSize=13, alignment=TA_RIGHT, textColor=NAVY, leading=18)
    style_label = ParagraphStyle('PLabel', fontName='DejaVuSans-Bold', fontSize=10, alignment=TA_RIGHT, textColor=NAVY, leading=14)
    style_value = ParagraphStyle('PValue', fontName='DejaVuSans', fontSize=10, alignment=TA_RIGHT, textColor=HexColor("#333333"), leading=14)
    style_body = ParagraphStyle('PBody', fontName='DejaVuSans', fontSize=9, alignment=TA_RIGHT, textColor=HexColor("#333333"), leading=13)
    style_footer = ParagraphStyle('PFooter', fontName='DejaVuSans', fontSize=8, alignment=TA_CENTER, textColor=HexColor("#999999"), leading=10)

    elements = []

    header_data = [[Paragraph(ar("NASSAQ | نَسَّق"), style_title)]]
    header_table = Table(header_data, colWidths=[17*cm])
    header_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), NAVY), ('TOPPADDING', (0,0), (-1,-1), 14), ('BOTTOMPADDING', (0,0), (-1,-1), 14)]))
    elements.append(header_table)
    elements.append(Spacer(1, 6))

    sub_data = [[Paragraph(ar(school_name), style_subtitle)]]
    sub_table = Table(sub_data, colWidths=[17*cm])
    sub_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), HexColor("#1C3D74CC")), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    elements.append(sub_table)
    elements.append(Spacer(1, 10))

    info_text = f"{ar(student.get('full_name', ''))} | {ar(student.get('grade', ''))} - {ar(class_name)} | {export_date}"
    elements.append(Paragraph(info_text, ParagraphStyle('Info', fontName='DejaVuSans', fontSize=10, alignment=TA_CENTER, textColor=HexColor("#555555"), leading=14)))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=TURQUOISE))
    elements.append(Spacer(1, 10))

    def pdf_section(title):
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(ar(f"■ {title}"), style_section))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY))
        elements.append(Spacer(1, 4))

    def pdf_kv(key, value):
        elements.append(Paragraph(f"{ar(str(value) if value else '—')} :{ar(key)}", style_value))

    if "personal" in sections:
        pdf_section("المعلومات الشخصية وولي الأمر")
        pdf_kv("الاسم الكامل", student.get("full_name", ""))
        pdf_kv("الاسم بالعربي", student.get("name_ar", ""))
        pdf_kv("الجنس", student.get("gender", ""))
        pdf_kv("تاريخ الميلاد", student.get("date_of_birth", ""))
        pdf_kv("رقم ولي الأمر", student.get("parent_phone", ""))
        pdf_kv("بريد ولي الأمر", student.get("parent_email", ""))

    if "academic" in sections:
        pdf_section("الأداء الأكاديمي")
        att_records = await gd_find(db.session, "attendance", {"student_id": student_id, "school_id": school_id}, limit=5000)
        total_att = len(att_records)
        present_c = sum(1 for r in att_records if r.get("status") in ("present", "late"))
        att_rate = round((present_c / max(total_att, 1)) * 100, 1)
        pdf_kv("نسبة الحضور", f"{att_rate}%")
        gr = await gd_find(db.session, "grades", {"student_id": student_id, "school_id": school_id}, limit=5000)
        if gr:
            percs = [g.get("percentage", 0) for g in gr if g.get("percentage") is not None]
            avg = round(sum(percs) / max(len(percs), 1), 1) if percs else 0
            pdf_kv("المعدل الأكاديمي", f"{avg}%")

    if "talents" in sections:
        pdf_section("المواهب والمهارات")
        talents = student.get("talents", [])
        pdf_kv("المواهب", "، ".join(talents) if talents else "لا توجد")
        char_traits = student.get("character_traits", [])
        if char_traits:
            pdf_kv("السمات الشخصية", "، ".join(char_traits))

    if "behaviour" in sections:
        pdf_section("السلوك")
        beh = await gd_find(db.session, "behaviour_records", {"student_id": student_id, "school_id": school_id}, limit=500)
        pos = sum(1 for b in beh if b.get("category") == "positive")
        neg = sum(1 for b in beh if b.get("category") == "negative")
        pdf_kv("إجمالي السجلات", len(beh))
        pdf_kv("إيجابي", pos)
        pdf_kv("سلبي", neg)

    if "activities" in sections:
        pdf_section("الأنشطة والإنجازات")
        acts = await gd_find(db.session, "student_activities", {"student_id": student_id, "school_id": school_id}, limit=200)
        certs = await gd_find(db.session, "student_certificates", {"student_id": student_id, "school_id": school_id}, limit=200)
        pdf_kv("عدد الأنشطة", len(acts))
        pdf_kv("عدد الشهادات", len(certs))
        for a in acts:
            elements.append(Paragraph(ar(f"• {a.get('name', '')} ({a.get('activity_type', '')})"), style_body))
        for c in certs:
            elements.append(Paragraph(ar(f"🏆 {c.get('title', '')} — {c.get('issuing_body', '')}"), style_body))

    if "plans" in sections:
        pdf_section("الخطط العلاجية والإثرائية")
        plans = await gd_find_one(db.session, "student_ai_plans", {"student_id": student_id, "school_id": school_id})
        if plans:
            rp = plans.get("remedial_plan")
            ep = plans.get("enrichment_plan")
            if rp and isinstance(rp, dict):
                elements.append(Paragraph(ar("الخطة العلاجية:"), style_label))
                if rp.get("title"):
                    pdf_kv("العنوان", rp["title"])
                if rp.get("objective"):
                    pdf_kv("الهدف", rp["objective"])
            if ep and isinstance(ep, dict):
                elements.append(Paragraph(ar("الخطة الإثرائية:"), style_label))
                if ep.get("title"):
                    pdf_kv("العنوان", ep["title"])
                if ep.get("objective"):
                    pdf_kv("الهدف", ep["objective"])
        else:
            pdf_kv("الخطط", "لا توجد خطط مسجلة")

    if "longitudinal" in sections:
        pdf_section("السجل التراكمي")
        pdf_kv("الصف الحالي", f"{student.get('grade', '')} - {class_name}")
        pdf_kv("حالة الطالب", "نشط" if student.get("is_active") != False else "معلق")
        talents = student.get("talents", [])
        pdf_kv("المواهب", "، ".join(talents) if talents else "—")

    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GRAY))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"{ar(f'تم التصدير بواسطة: {exported_by}')} | {export_date} | NASSAQ", style_footer))

    buf = io.BytesIO()
    pdf_doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm, leftMargin=2*cm, rightMargin=2*cm)
    pdf_doc.build(elements)
    buf.seek(0)

    filename = f"NASSAQ_Profile_{student.get('full_name', 'student')}_{export_date}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
