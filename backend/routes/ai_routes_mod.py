"""
NASSAQ Route Module: AI operations, Hakim AI chat and engine, insights
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
from bson_compat import ObjectId
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

from shared_models import (
    HakimMessage, HakimResponse
)
from openai import OpenAI

router = APIRouter()

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")

_openai_client = None
def get_openai_client():
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(
            api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
            base_url=AI_INTEGRATIONS_OPENAI_BASE_URL,
        )
    return _openai_client

_hakim_sessions: Dict[str, list] = {}



# ============== AI OPERATIONS ==============
@router.post("/ai/diagnosis")
async def ai_system_diagnosis(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    """تشخيص النظام بالذكاء الاصطناعي"""
    # Gather system metrics
    total_schools = await db.schools.count_documents({})
    active_schools = await db.schools.count_documents({"status": "active"})
    total_users = await db.users.count_documents({})
    active_users = await db.users.count_documents({"is_active": True})
    
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
    pending = await db.registration_requests.count_documents({"status": "pending"})
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
    students_missing_phone = await db.students.count_documents({
        "$or": [{"parent_phone": None}, {"parent_phone": ""}]
    })
    if students_missing_phone > 0:
        issues.append({"type": "missing_data", "entity": "students", "count": students_missing_phone, "field": "parent_phone"})
    
    # Check teachers without rank
    teachers_no_rank = await db.teachers.count_documents({
        "$or": [{"rank": None}, {"rank": ""}]
    })
    if teachers_no_rank > 0:
        issues.append({"type": "missing_data", "entity": "teachers", "count": teachers_no_rank, "field": "rank"})
    
    # Check classes without teachers
    classes_no_teacher = await db.classes.count_documents({
        "$or": [{"teacher_id": None}, {"teacher_id": ""}]
    })
    if classes_no_teacher > 0:
        issues.append({"type": "incomplete", "entity": "classes", "count": classes_no_teacher, "issue": "no_teacher"})
    
    # Calculate quality score
    total_records = await db.students.count_documents({}) + await db.teachers.count_documents({}) + await db.classes.count_documents({})
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
    schools = await db.schools.find({}, {"_id": 0}).to_list(1000)
    
    healthy = []
    warning = []
    critical = []
    
    for school in schools:
        school_id = school.get("id")
        student_count = await db.students.count_documents({"school_id": school_id})
        teacher_count = await db.teachers.count_documents({"school_id": school_id})
        class_count = await db.classes.count_documents({"school_id": school_id})
        
        # Determine health
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
    total_schools = await db.schools.count_documents({})
    active_schools = await db.schools.count_documents({"status": "active"})
    total_students = await db.students.count_documents({})
    total_teachers = await db.teachers.count_documents({})
    total_classes = await db.classes.count_documents({})
    pending_requests = await db.registration_requests.count_documents({"status": "pending"})
    
    # Today's activity
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_events = await db.events.count_documents({"created_at": {"$gte": today_start.isoformat()}})
    
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
        if not AI_INTEGRATIONS_OPENAI_BASE_URL:
            raise ValueError("AI service not configured")

        school_id = current_user.get("tenant_id") or req.tenant_id
        school_context = ""
        if school_id:
            school = await db.schools.find_one({"id": school_id}, {"_id": 0, "name": 1, "name_ar": 1})
            school_name = school.get("name_ar") or school.get("name", "") if school else ""
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

@router.post("/hakim/chat", response_model=HakimResponse)
async def chat_with_hakim(message: HakimChatRequest, current_user: dict = Depends(get_current_user)):
    try:
        client = get_openai_client()
        if not AI_INTEGRATIONS_OPENAI_BASE_URL:
            raise ValueError("AI service not configured")

        school_id = current_user.get("tenant_id") or message.tenant_id
        school_context = ""
        if school_id:
            school = await db.schools.find_one({"id": school_id}, {"_id": 0, "name": 1, "name_ar": 1})
            total_students = await db.students.count_documents({"school_id": school_id})
            total_teachers = await db.teachers.count_documents({"school_id": school_id})
            total_classes = await db.classes.count_documents({"school_id": school_id})
            attendance_query = {"school_id": school_id}
            total_att = await db.attendance.count_documents(attendance_query)
            present_att = await db.attendance.count_documents({**attendance_query, "status": "present"})
            att_rate = round((present_att / total_att) * 100, 1) if total_att > 0 else 0
            school_name = school.get("name_ar") or school.get("name", "") if school else ""
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
دور المستخدم الحالي: {message.user_role or current_user.get('role', 'unknown')}"""

        session_key = message.session_id or f"hakim_{current_user.get('id', 'anon')}"

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

        suggestions = _generate_hakim_suggestions(message.message)

        return HakimResponse(response=reply, suggestions=suggestions)

    except Exception as e:
        logging.error(f"Hakim LLM error: {str(e)}")
        return _hakim_fallback(message.message)


def _generate_hakim_suggestions(msg: str) -> list:
    msg_lower = msg.lower()
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
@router.get("/ai/insights/overview")
async def get_ai_insights_overview(
    current_user: dict = Depends(get_current_user)
):
    """Get AI-powered insights overview for the school"""
    school_id = current_user.get("tenant_id")
    
    # Calculate overall performance score
    total_students = await db.students.count_documents({"school_id": school_id}) if school_id else 0
    total_teachers = await db.teachers.count_documents({"school_id": school_id}) if school_id else 0
    
    # Get attendance data
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    attendance_query = {"school_id": school_id} if school_id else {}
    attendance_count = await db.attendance.count_documents({**attendance_query, "status": "present"})
    total_attendance = await db.attendance.count_documents(attendance_query)
    attendance_rate = round((attendance_count / total_attendance) * 100, 1) if total_attendance > 0 else 85
    
    # Calculate score based on multiple factors
    base_score = 70
    attendance_bonus = min(15, (attendance_rate - 80) / 2) if attendance_rate > 80 else 0
    student_teacher_ratio = total_students / total_teachers if total_teachers > 0 else 20
    ratio_bonus = max(0, 15 - abs(student_teacher_ratio - 15))  # Best ratio is around 15:1
    
    overall_score = int(min(100, base_score + attendance_bonus + ratio_bonus))
    
    # Determine trend
    trend = "up"
    trend_value = round(3.2 + (overall_score - 85) / 10, 1)
    
    return {
        "overall_score": overall_score,
        "trend": trend,
        "trend_value": abs(trend_value),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "attendance_rate": attendance_rate,
            "student_teacher_ratio": round(student_teacher_ratio, 1),
            "total_students": total_students,
            "total_teachers": total_teachers
        }
    }

@router.get("/ai/insights/predictions")
async def get_ai_predictions(
    current_user: dict = Depends(get_current_user)
):
    """Get AI predictions for the school based on real data analysis"""
    school_id = current_user.get("tenant_id")
    predictions = []
    pred_id = 0

    today = datetime.now(timezone.utc)
    week_ago = today - timedelta(days=7)
    two_weeks_ago = today - timedelta(days=14)
    week_ago_str = week_ago.strftime("%Y-%m-%d")
    two_weeks_ago_str = two_weeks_ago.strftime("%Y-%m-%d")

    q = {"school_id": school_id} if school_id else {}

    this_week_total = await db.attendance.count_documents({**q, "date": {"$gte": week_ago_str}})
    this_week_present = await db.attendance.count_documents({**q, "date": {"$gte": week_ago_str}, "status": "present"})
    last_week_total = await db.attendance.count_documents({**q, "date": {"$gte": two_weeks_ago_str, "$lt": week_ago_str}})
    last_week_present = await db.attendance.count_documents({**q, "date": {"$gte": two_weeks_ago_str, "$lt": week_ago_str}, "status": "present"})

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

    recent_grades = await db.grades.find({**q, "created_at": {"$gte": week_ago.isoformat()}}).to_list(500)
    older_grades = await db.grades.find({**q, "created_at": {"$gte": two_weeks_ago.isoformat(), "$lt": week_ago.isoformat()}}).to_list(500)
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
        {"$match": {**q, "status": "absent", "date": {"$gte": week_ago_str}}},
        {"$group": {"_id": "$student_id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gte": 3}}},
        {"$count": "total"}
    ]
    absent_result = await db.attendance.aggregate(absent_pipeline).to_list(1)
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

@router.get("/ai/insights/recommendations")
async def get_ai_recommendations(
    current_user: dict = Depends(get_current_user)
):
    """Get AI-powered recommendations based on real school data"""
    school_id = current_user.get("tenant_id")
    recommendations = []
    rec_id = 0
    q = {"school_id": school_id} if school_id else {}

    today = datetime.now(timezone.utc)
    month_ago = today - timedelta(days=30)
    month_ago_str = month_ago.strftime("%Y-%m-%d")

    total_att = await db.attendance.count_documents({**q, "date": {"$gte": month_ago_str}})
    present_att = await db.attendance.count_documents({**q, "date": {"$gte": month_ago_str}, "status": "present"})
    att_rate = round((present_att / total_att) * 100, 1) if total_att > 0 else 100

    if att_rate < 85:
        rec_id += 1
        recommendations.append({
            "id": str(rec_id),
            "category": {"ar": "الحضور والانضباط", "en": "Attendance & Discipline"},
            "title": {"ar": "تحسين نسبة الحضور", "en": "Improve Attendance Rate"},
            "description": {"ar": f"نسبة الحضور الحالية {att_rate}% أقل من المستوى المطلوب (85%). يُنصح بتطبيق نظام حوافز للحضور المنتظم والتواصل مع أولياء الأمور", "en": f"Current attendance {att_rate}% is below target (85%). Implement incentive system and parent outreach"},
            "priority": "high" if att_rate < 75 else "medium",
            "expected_impact": int(85 - att_rate)
        })

    late_count = await db.attendance.count_documents({**q, "date": {"$gte": month_ago_str}, "status": "late"})
    if total_att > 0 and (late_count / total_att * 100) > 5:
        rec_id += 1
        late_pct = round(late_count / total_att * 100, 1)
        recommendations.append({
            "id": str(rec_id),
            "category": {"ar": "الحضور والانضباط", "en": "Attendance & Discipline"},
            "title": {"ar": "معالجة ظاهرة التأخر", "en": "Address Tardiness"},
            "description": {"ar": f"نسبة التأخر {late_pct}% مرتفعة. يُنصح بمراجعة أوقات بدء الدوام والتواصل مع الأسر", "en": f"Tardiness rate {late_pct}% is high. Review start times and contact families"},
            "priority": "medium",
            "expected_impact": 10
        })

    total_students = await db.students.count_documents(q)
    total_teachers = await db.teachers.count_documents(q)
    if total_teachers > 0:
        ratio = total_students / total_teachers
        if ratio > 25:
            rec_id += 1
            recommendations.append({
                "id": str(rec_id),
                "category": {"ar": "الموارد البشرية", "en": "Human Resources"},
                "title": {"ar": "تعزيز الكادر التعليمي", "en": "Strengthen Teaching Staff"},
                "description": {"ar": f"نسبة الطلاب للمعلمين ({ratio:.0f}:1) مرتفعة. يُنصح بتعيين معلمين إضافيين لتحسين جودة التعليم", "en": f"Student-teacher ratio ({ratio:.0f}:1) is high. Consider hiring additional teachers"},
                "priority": "high",
                "expected_impact": 20
            })

    classes_cursor = db.classes.find(q, {"_id": 0, "id": 1, "name": 1})
    classes_list = await classes_cursor.to_list(100)
    low_att_classes = []
    for cls in classes_list:
        cls_total = await db.attendance.count_documents({"class_id": cls["id"], "date": {"$gte": month_ago_str}})
        cls_present = await db.attendance.count_documents({"class_id": cls["id"], "date": {"$gte": month_ago_str}, "status": "present"})
        if cls_total > 10:
            cls_rate = round((cls_present / cls_total) * 100, 1)
            if cls_rate < 80:
                low_att_classes.append({"name": cls.get("name", cls["id"]), "rate": cls_rate})
    if low_att_classes:
        rec_id += 1
        class_names = ", ".join([c["name"] for c in low_att_classes[:3]])
        recommendations.append({
            "id": str(rec_id),
            "category": {"ar": "متابعة الفصول", "en": "Class Monitoring"},
            "title": {"ar": "فصول تحتاج اهتمام خاص", "en": "Classes Needing Attention"},
            "description": {"ar": f"الفصول التالية حضورها منخفض: {class_names}. يُنصح بمتابعة أسباب الغياب مع معلمي الفصول", "en": f"Low attendance in: {class_names}. Investigate causes with class teachers"},
            "priority": "high",
            "expected_impact": 15
        })

    recent_assessments = await db.assessments.count_documents({**q, "created_at": {"$gte": month_ago.isoformat()}})
    if recent_assessments == 0 and total_students > 0:
        rec_id += 1
        recommendations.append({
            "id": str(rec_id),
            "category": {"ar": "التحصيل الأكاديمي", "en": "Academic Achievement"},
            "title": {"ar": "تفعيل التقييم المستمر", "en": "Activate Continuous Assessment"},
            "description": {"ar": "لم يتم تسجيل أي تقييمات خلال الشهر الماضي. يُنصح بإنشاء اختبارات قصيرة لمتابعة مستوى الطلاب", "en": "No assessments recorded this month. Create quizzes to track student progress"},
            "priority": "high",
            "expected_impact": 25
        })

    if not recommendations:
        recommendations.append({
            "id": "1",
            "category": {"ar": "الأداء العام", "en": "General Performance"},
            "title": {"ar": "أداء المدرسة جيد", "en": "School Performance is Good"},
            "description": {"ar": "المؤشرات الحالية جيدة. استمر في متابعة الأداء بانتظام للحفاظ على هذا المستوى", "en": "Current indicators are good. Continue regular monitoring to maintain this level"},
            "priority": "low",
            "expected_impact": 5
        })

    return recommendations

@router.get("/ai/insights/alerts")
async def get_ai_alerts(
    current_user: dict = Depends(get_current_user)
):
    """Get AI-generated alerts based on real school data"""
    school_id = current_user.get("tenant_id")
    alerts = []
    q = {"school_id": school_id} if school_id else {}
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")
    week_ago_str = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    consecutive_pipeline = [
        {"$match": {**q, "status": "absent", "date": {"$gte": week_ago_str}}},
        {"$group": {"_id": "$student_id", "days": {"$sum": 1}, "dates": {"$push": "$date"}}},
        {"$match": {"days": {"$gte": 3}}},
        {"$count": "total"}
    ]
    cons_result = await db.attendance.aggregate(consecutive_pipeline).to_list(1)
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

    today_total = await db.attendance.count_documents({**q, "date": today_str})
    today_present = await db.attendance.count_documents({**q, "date": today_str, "status": "present"})
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

    unassigned_sessions = await db.timetable_sessions.count_documents({**q, "$or": [{"teacher_id": None}, {"teacher_id": ""}]})
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

    recent_behaviour = await db.behaviour_records.count_documents({
        **q,
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

@router.get("/ai/insights/at-risk-students")
async def get_at_risk_students(
    current_user: dict = Depends(get_current_user)
):
    """Get list of students who may need intervention based on real data"""
    school_id = current_user.get("tenant_id")
    q = {"school_id": school_id} if school_id else {}
    at_risk = []

    students = await db.students.find(q, {"_id": 0, "id": 1, "full_name": 1, "class_id": 1}).to_list(500)
    month_ago_str = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    for student in students:
        sid = student["id"]
        factors = []
        risk_score = 100

        total_att = await db.attendance.count_documents({"student_id": sid, "date": {"$gte": month_ago_str}})
        absent_att = await db.attendance.count_documents({"student_id": sid, "date": {"$gte": month_ago_str}, "status": "absent"})
        if total_att > 0:
            absence_rate = (absent_att / total_att) * 100
            if absence_rate > 30:
                risk_score -= 35
                factors.append(f"غياب مرتفع ({absence_rate:.0f}%)")
            elif absence_rate > 15:
                risk_score -= 20
                factors.append(f"غياب متوسط ({absence_rate:.0f}%)")

        recent_grades = await db.grades.find({"student_id": sid}).sort("created_at", -1).to_list(10)
        if recent_grades:
            avg_grade = sum(g.get("percentage", 0) for g in recent_grades) / len(recent_grades)
            if avg_grade < 50:
                risk_score -= 30
                factors.append(f"أداء أكاديمي ضعيف ({avg_grade:.0f}%)")
            elif avg_grade < 65:
                risk_score -= 15
                factors.append(f"أداء أكاديمي متوسط ({avg_grade:.0f}%)")

        neg_behaviour = await db.behaviour_records.count_documents({
            "student_id": sid,
            "type": "negative",
            "created_at": {"$gte": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()}
        })
        if neg_behaviour >= 3:
            risk_score -= 20
            factors.append(f"سلوك سلبي متكرر ({neg_behaviour} مرات)")
        elif neg_behaviour >= 1:
            risk_score -= 10
            factors.append(f"ملاحظات سلوكية ({neg_behaviour})")

        if risk_score < 70 and factors:
            class_info = await db.classes.find_one({"id": student.get("class_id")}, {"_id": 0, "name": 1})
            risk_type = "academic"
            if any("غياب" in f for f in factors):
                risk_type = "attendance"
            if any("سلوك" in f for f in factors):
                risk_type = "behavioral"

            at_risk.append({
                "id": sid,
                "name": student.get("full_name", "غير معروف"),
                "grade": class_info.get("name", "") if class_info else "",
                "risk_level": max(0, risk_score),
                "risk_type": risk_type,
                "factors": factors
            })

    at_risk.sort(key=lambda x: x["risk_level"])
    return at_risk[:20]





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
    student = await db.students.find_one({"id": student_id, "school_id": school_id})
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
    cls = await db.classes.find_one({"id": class_id, "school_id": school_id})
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
    student = await db.students.find_one({"id": student_id, "school_id": school_id})
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
    teacher = await db.teachers.find_one({"id": teacher_id, "school_id": school_id})
    if not teacher:
        teacher_user = await db.users.find_one({"teacher_id": teacher_id, "tenant_id": school_id})
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
    cls = await db.classes.find_one({"id": class_id, "school_id": school_id})
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
    school = await db.schools.find_one({"id": school_id})
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
    school = await db.schools.find_one({"id": school_id})
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
    interventions = await db.ai_interventions.find(
        query, {"_id": 0}
    ).sort("created_at", -1).to_list(limit)
    return {"interventions": interventions, "total": len(interventions)}


@router.put("/hakim/interventions/{intervention_id}/status")
async def hakim_update_intervention_status(
    intervention_id: str,
    new_status: str = Query(..., regex="^(active|completed|dismissed|expired)$"),
    notes: str = Query(None),
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    school_id = current_user.get("tenant_id")
    intervention = await db.ai_interventions.find_one(
        {"id": intervention_id, "school_id": school_id}
    )
    if not intervention:
        raise HTTPException(404, "خطة التدخل غير موجودة")

    now = datetime.now(timezone.utc).isoformat()
    update = {"status": new_status, "updated_at": now, "updated_by": current_user.get("id")}

    follow_up = {"action": f"تغيير الحالة إلى {new_status}", "by": current_user.get("id"), "at": now}
    if notes:
        follow_up["notes"] = notes

    await db.ai_interventions.update_one(
        {"id": intervention_id},
        {"$set": update, "$push": {"follow_ups": follow_up}}
    )
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
    student = await db.students.find_one({"id": student_id, "school_id": school_id})
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
    student = await db.students.find_one({"id": student_id, "school_id": school_id})
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
        await db.plan_history.insert_one(history_doc)
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
    records = await db.plan_history.find(
        {"student_id": student_id, "school_id": school_id}
    ).sort("generated_at", -1).to_list(50)
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
    student = await db.students.find_one({"id": student_id, "school_id": school_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "الطالب غير موجود")

    school = await db.schools.find_one({"id": school_id}, {"_id": 0})
    school_name = school.get("name", "") if school else ""

    class_name = ""
    class_id = student.get("class_id")
    if class_id:
        class_doc = await db.classes.find_one({"id": class_id}, {"_id": 0})
        class_name = class_doc.get("name", "") if class_doc else ""

    academic_year_name = ""
    ay_doc = await db.academic_years.find_one({"school_id": school_id, "is_current": True}, {"_id": 0})
    if ay_doc:
        academic_year_name = ay_doc.get("name", "")

    teacher_name = ""
    user_role = current_user.get("role", "")
    if user_role == "teacher":
        teacher_doc = await db.teachers.find_one({"user_id": current_user.get("sub")}, {"_id": 0})
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
    except Exception:
        pass

    def ar(text):
        if not text:
            return ""
        try:
            reshaped = arabic_reshaper.reshape(str(text))
            return get_display(reshaped)
        except Exception:
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
    student = await db.students.find_one({"id": student_id, "school_id": school_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "الطالب غير موجود")

    school = await db.schools.find_one({"id": school_id}, {"_id": 0})
    school_name = school.get("name", "") if school else ""

    class_name = ""
    class_id = student.get("class_id")
    if class_id:
        class_doc = await db.classes.find_one({"id": class_id}, {"_id": 0})
        class_name = class_doc.get("name", "") if class_doc else ""

    academic_year_name = ""
    ay_doc = await db.academic_years.find_one({"school_id": school_id, "is_current": True}, {"_id": 0})
    if ay_doc:
        academic_year_name = ay_doc.get("name", "")

    teacher_name = ""
    user_role = current_user.get("role", "")
    if user_role == "teacher":
        teacher_doc = await db.teachers.find_one({"user_id": current_user.get("sub")}, {"_id": 0})
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
    school = await db.schools.find_one({"id": school_id})
    if not school:
        raise HTTPException(404, "المدرسة غير موجودة")
    return await hakim_engine.run_periodic_scan(school_id, days)


@router.get("/student/{student_id}/longitudinal")
async def get_student_longitudinal(
    student_id: str,
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    student = await db.students.find_one({"id": student_id, "school_id": school_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "الطالب غير موجود")

    attendance_records = await db.attendance.find(
        {"student_id": student_id, "school_id": school_id}
    ).to_list(10000)

    behaviour_records = await db.behaviour_records.find(
        {"student_id": student_id, "school_id": school_id}
    ).to_list(5000)

    activities = await db.student_activities.find(
        {"student_id": student_id, "school_id": school_id}
    ).to_list(500)

    certificates = await db.student_certificates.find(
        {"student_id": student_id, "school_id": school_id}
    ).to_list(500)

    grades_records = await db.grades.find(
        {"student_id": student_id, "school_id": school_id}
    ).to_list(5000)

    skill_records = await db.student_skills.find(
        {"student_id": student_id, "school_id": school_id}
    ).to_list(2000)

    classes = await db.classes.find({"school_id": school_id}, {"_id": 0}).to_list(500)
    class_map = {c["id"]: c.get("name", "") for c in classes}

    teachers = await db.teachers.find({"school_id": school_id}, {"_id": 0}).to_list(500)
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
        except Exception:
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
    student = await db.students.find_one({"id": student_id, "school_id": school_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "الطالب غير موجود")

    school = await db.schools.find_one({"id": school_id}, {"_id": 0})
    school_name = school.get("name", "") if school else ""
    class_name = ""
    if student.get("class_id"):
        cls = await db.classes.find_one({"id": student["class_id"], "school_id": school_id}, {"_id": 0})
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
        att_records = await db.attendance.find({"student_id": student_id, "school_id": school_id}).to_list(5000)
        total_att = len(att_records)
        present_c = sum(1 for r in att_records if r.get("status") in ("present", "late"))
        att_rate = round((present_c / max(total_att, 1)) * 100, 1)
        add_key_value("نسبة الحضور", f"{att_rate}%")

        gr = await db.grades.find({"student_id": student_id, "school_id": school_id}).to_list(5000)
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
        beh = await db.behaviour_records.find({"student_id": student_id, "school_id": school_id}).sort("incident_date", -1).to_list(500)
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
        acts = await db.student_activities.find({"student_id": student_id, "school_id": school_id}).to_list(200)
        certs = await db.student_certificates.find({"student_id": student_id, "school_id": school_id}).to_list(200)
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
        plans = await db.student_ai_plans.find_one({"student_id": student_id, "school_id": school_id}, {"_id": 0})
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
    except Exception:
        pass

    def ar(text):
        if not text:
            return ""
        try:
            reshaped = arabic_reshaper.reshape(str(text))
            return get_display(reshaped)
        except Exception:
            return str(text)

    body = await request.json()
    sections = body.get("sections", [])

    school_id = current_user.get("tenant_id")
    student = await db.students.find_one({"id": student_id, "school_id": school_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "الطالب غير موجود")

    school = await db.schools.find_one({"id": school_id}, {"_id": 0})
    school_name = school.get("name", "") if school else ""
    class_name = ""
    if student.get("class_id"):
        cls = await db.classes.find_one({"id": student["class_id"], "school_id": school_id}, {"_id": 0})
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
        att_records = await db.attendance.find({"student_id": student_id, "school_id": school_id}).to_list(5000)
        total_att = len(att_records)
        present_c = sum(1 for r in att_records if r.get("status") in ("present", "late"))
        att_rate = round((present_c / max(total_att, 1)) * 100, 1)
        pdf_kv("نسبة الحضور", f"{att_rate}%")
        gr = await db.grades.find({"student_id": student_id, "school_id": school_id}).to_list(5000)
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
        beh = await db.behaviour_records.find({"student_id": student_id, "school_id": school_id}).to_list(500)
        pos = sum(1 for b in beh if b.get("category") == "positive")
        neg = sum(1 for b in beh if b.get("category") == "negative")
        pdf_kv("إجمالي السجلات", len(beh))
        pdf_kv("إيجابي", pos)
        pdf_kv("سلبي", neg)

    if "activities" in sections:
        pdf_section("الأنشطة والإنجازات")
        acts = await db.student_activities.find({"student_id": student_id, "school_id": school_id}).to_list(200)
        certs = await db.student_certificates.find({"student_id": student_id, "school_id": school_id}).to_list(200)
        pdf_kv("عدد الأنشطة", len(acts))
        pdf_kv("عدد الشهادات", len(certs))
        for a in acts:
            elements.append(Paragraph(ar(f"• {a.get('name', '')} ({a.get('activity_type', '')})"), style_body))
        for c in certs:
            elements.append(Paragraph(ar(f"🏆 {c.get('title', '')} — {c.get('issuing_body', '')}"), style_body))

    if "plans" in sections:
        pdf_section("الخطط العلاجية والإثرائية")
        plans = await db.student_ai_plans.find_one({"student_id": student_id, "school_id": school_id}, {"_id": 0})
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
