"""
NASSAQ Academic Structure Routes
Holidays, Exam Periods, Promotion Rules, Academic Calendar, Publish/Archive workflows.
Extends the academic year & term CRUD in academics_year_term_routes.py.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, ConfigDict, Field, field_validator

from dependencies import db, get_current_user, require_roles, UserRole
import logging

logger = logging.getLogger("nassaq.academic_structure_routes")
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct


router = APIRouter(tags=["Academic Structure"])


class HolidayCreate(BaseModel):
    academic_year_id: str
    term_id: Optional[str] = None
    name: str
    name_en: Optional[str] = None
    start_date: str
    end_date: str
    type: str = "public"
    custom_type: Optional[str] = None


class HolidayResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    academic_year_id: str
    term_id: Optional[str] = None
    name: str
    name_en: Optional[str] = None
    start_date: str
    end_date: str
    type: str
    custom_type: Optional[str] = None
    school_id: str
    created_at: str


class ExamPeriodCreate(BaseModel):
    academic_year_id: str
    term_id: str
    name: str
    name_en: Optional[str] = None
    start_date: str
    end_date: str
    exam_type: str = "final"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    period_number: Optional[int] = None

    @field_validator('period_number', mode='before')
    @classmethod
    def coerce_period_number(cls, v):
        if v == '' or v is None:
            return None
        return int(v)

    @field_validator('start_time', 'end_time', mode='before')
    @classmethod
    def coerce_empty_time(cls, v):
        if v == '':
            return None
        return v


class ExamPeriodResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    academic_year_id: str
    term_id: str
    name: str
    name_en: Optional[str] = None
    start_date: str
    end_date: str
    exam_type: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    period_number: Optional[int] = None
    school_id: str
    created_at: str


ADMIN_ROLES = [UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]


def get_school_id(current_user: dict) -> str:
    return current_user.get("tenant_id") or current_user.get("school_id") or ""


async def get_school_id_from_year(year_id: str, current_user: dict) -> str:
    sid = get_school_id(current_user)
    if sid:
        return sid
    year = await gd_find_one(db.session, "academic_years", {"id": year_id})
    if year:
        return year.get("school_id", "")
    return ""


@router.get("/academic-structure/overview")
async def get_academic_overview(
    school_id: str = None,
    current_user: dict = Depends(get_current_user)
):
    user_school_id = get_school_id(current_user)
    role = current_user.get("role", "")
    if role == UserRole.PLATFORM_ADMIN:
        school_id = school_id or user_school_id
    else:
        school_id = user_school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="لم يتم تحديد المدرسة")

    current_year = await gd_find_one(db.session, "academic_years", {"school_id": school_id, "is_current": True})

    all_years = await gd_find(db.session, "academic_years", {"school_id": school_id}, order_by="start_date", desc_order=True, limit=50)

    current_term = None
    terms_count = 0
    remaining_days = 0

    if current_year:
        terms = await gd_find(db.session, "terms", {"school_id": school_id, "academic_year_id": current_year["id"]}, order_by="start_date", desc_order=False, limit=10)
        terms_count = len(terms)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for t in terms:
            if t.get("start_date", "") <= today <= t.get("end_date", ""):
                current_term = t
                break

        try:
            end = datetime.strptime(current_year.get("end_date", ""), "%Y-%m-%d")
            now_date = datetime.now(timezone.utc).replace(tzinfo=None)
            remaining_days = max(0, (end - now_date).days)
        except Exception as e:
            logger.debug(f"Failed to parse academic year end_date for remaining days calculation: {e}")
            remaining_days = 0

    def _normalize_year(y):
        if not y:
            return y
        d = dict(y)
        if "name" not in d and "name_ar" in d:
            d["name"] = d["name_ar"]
        if "name_en" not in d and "year" in d:
            d["name_en"] = d["year"]
        if "status" not in d:
            d["status"] = "active" if d.get("is_current") else "draft"
        return d

    return {
        "current_year": _normalize_year(current_year),
        "all_years": [_normalize_year(y) for y in all_years],
        "current_term": current_term,
        "terms_count": terms_count,
        "remaining_school_days": remaining_days,
    }


@router.post("/academic-years/{year_id}/publish")
async def publish_academic_year(
    year_id: str,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = await get_school_id_from_year(year_id, current_user)
    if not school_id:
        raise HTTPException(status_code=400, detail="لم يتم تحديد المدرسة")
    year = await gd_find_one(db.session, "academic_years", {"id": year_id, "school_id": school_id})
    if not year:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")

    if year.get("status") == "active" and year.get("is_current"):
        raise HTTPException(status_code=400, detail="العام الدراسي منشور بالفعل")

    terms = await gd_find(db.session, "terms", {"academic_year_id": year_id, "school_id": school_id}, limit=10)
    if not terms:
        raise HTTPException(status_code=400, detail="يجب إضافة فصول دراسية قبل النشر")

    await gd_update_many(db.session, "academic_years", {"school_id": school_id, "is_current": True}, {"is_current": False})

    now = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "academic_years", {"id": year_id, "school_id": school_id}, {
            "status": "active",
            "is_current": True,
            "published_at": now,
            "published_by": current_user.get("id"),
            "updated_at": now,
        })

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for t in terms:
        if t.get("start_date", "") <= today <= t.get("end_date", ""):
            await gd_update_many(db.session, "terms", {"academic_year_id": year_id, "school_id": school_id}, {"is_current": False})
            await gd_update_one(db.session, "terms", {"id": t["id"]}, {"is_current": True})
            break

    await gd_insert(db.session, "audit_logs", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "entity_type": "academic_year",
        "entity_id": year_id,
        "action": "academic_year_published",
        "performed_by": current_user.get("id"),
        "performed_by_email": current_user.get("email"),
        "timestamp": now,
        "details": {"year_name": year.get("name")},
    })

    return {"message": "تم نشر العام الدراسي بنجاح", "status": "active"}


@router.post("/academic-years/{year_id}/close")
async def close_academic_year(
    year_id: str,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = await get_school_id_from_year(year_id, current_user)
    if not school_id:
        raise HTTPException(status_code=400, detail="لم يتم تحديد المدرسة")
    year = await gd_find_one(db.session, "academic_years", {"id": year_id, "school_id": school_id})
    if not year:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")

    now = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "academic_years", {"id": year_id, "school_id": school_id}, {"status": "closed", "is_current": False, "closed_at": now, "updated_at": now})

    await gd_update_many(db.session, "terms", {"academic_year_id": year_id, "school_id": school_id}, {"is_current": False})

    await gd_insert(db.session, "audit_logs", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "entity_type": "academic_year",
        "entity_id": year_id,
        "action": "academic_year_closed",
        "performed_by": current_user.get("id"),
        "performed_by_email": current_user.get("email"),
        "timestamp": now,
    })

    return {"message": "تم إغلاق العام الدراسي", "status": "closed"}


@router.post("/academic-years/{year_id}/archive")
async def archive_academic_year(
    year_id: str,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = await get_school_id_from_year(year_id, current_user)
    if not school_id:
        raise HTTPException(status_code=400, detail="لم يتم تحديد المدرسة")
    year = await gd_find_one(db.session, "academic_years", {"id": year_id, "school_id": school_id})
    if not year:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")

    if year.get("status") == "active" and year.get("is_current"):
        raise HTTPException(status_code=400, detail="لا يمكن أرشفة عام دراسي نشط")

    now = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "academic_years", {"id": year_id, "school_id": school_id}, {"status": "archived", "is_current": False, "archived_at": now, "updated_at": now})

    return {"message": "تم أرشفة العام الدراسي", "status": "archived"}


@router.post("/academic-years/{year_id}/auto-terms")
async def auto_create_terms(
    year_id: str,
    num_terms: int = 3,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    if num_terms < 1 or num_terms > 6:
        raise HTTPException(status_code=400, detail="عدد الفصول يجب أن يكون بين 1 و 6")

    school_id = await get_school_id_from_year(year_id, current_user)
    if not school_id:
        raise HTTPException(status_code=400, detail="لم يتم تحديد المدرسة")
    year = await gd_find_one(db.session, "academic_years", {"id": year_id, "school_id": school_id})
    if not year:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")

    existing = await gd_count(db.session, "terms", {"academic_year_id": year_id, "school_id": school_id})
    if existing > 0:
        raise HTTPException(status_code=400, detail="توجد فصول دراسية بالفعل لهذا العام")

    try:
        start = datetime.strptime(year["start_date"], "%Y-%m-%d")
        end = datetime.strptime(year["end_date"], "%Y-%m-%d")
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="تواريخ العام الدراسي غير صحيحة")

    total_days = (end - start).days
    term_duration = total_days // num_terms
    now = datetime.now(timezone.utc).isoformat()

    term_names = {
        2: [("الفصل الأول", "Term 1"), ("الفصل الثاني", "Term 2")],
        3: [("الفصل الأول", "Term 1"), ("الفصل الثاني", "Term 2"), ("الفصل الثالث", "Term 3")],
    }
    names = term_names.get(num_terms, [(f"الفصل {i+1}", f"Term {i+1}") for i in range(num_terms)])

    created_terms = []
    for i in range(num_terms):
        t_start = start + timedelta(days=i * term_duration)
        if i == num_terms - 1:
            t_end = end
        else:
            t_end = start + timedelta(days=(i + 1) * term_duration - 1)

        term_doc = {
            "id": str(uuid.uuid4()),
            "name": names[i][0],
            "name_en": names[i][1],
            "academic_year_id": year_id,
            "start_date": t_start.strftime("%Y-%m-%d"),
            "end_date": t_end.strftime("%Y-%m-%d"),
            "is_current": i == 0,
            "school_id": school_id,
            "created_at": now,
            "updated_at": now,
            "created_by": current_user.get("id"),
        }
        await gd_insert(db.session, "terms", term_doc)
        term_doc.pop("_id", None)
        created_terms.append(term_doc)

    return {"message": f"تم إنشاء {num_terms} فصول دراسية", "terms": created_terms}


# ============== HOLIDAYS ==============

@router.post("/holidays", response_model=HolidayResponse)
async def create_holiday(
    data: HolidayCreate,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = await get_school_id_from_year(data.academic_year_id, current_user)
    now = datetime.now(timezone.utc).isoformat()

    holiday_doc = {
        "id": str(uuid.uuid4()),
        "academic_year_id": data.academic_year_id,
        "term_id": data.term_id,
        "name": data.name,
        "name_en": data.name_en,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "type": data.type,
        "custom_type": data.custom_type,
        "school_id": school_id,
        "created_at": now,
        "created_by": current_user.get("id"),
    }
    await gd_insert(db.session, "holidays", holiday_doc)
    holiday_doc.pop("_id", None)
    return HolidayResponse(**holiday_doc)


@router.get("/holidays", response_model=List[HolidayResponse])
async def get_holidays(
    academic_year_id: Optional[str] = None,
    term_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    school_id = get_school_id(current_user)
    query = {"school_id": school_id}
    if academic_year_id:
        query["academic_year_id"] = academic_year_id
    if term_id:
        query["term_id"] = term_id

    holidays = await gd_find(db.session, "holidays", query, order_by="start_date", desc_order=False, limit=200)
    return [HolidayResponse(**h) for h in holidays]


@router.put("/holidays/{holiday_id}", response_model=HolidayResponse)
async def update_holiday(
    holiday_id: str,
    data: HolidayCreate,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = get_school_id(current_user)
    holiday = await gd_find_one(db.session, "holidays", {"id": holiday_id, "school_id": school_id})
    if not holiday:
        raise HTTPException(status_code=404, detail="الإجازة غير موجودة")

    update_data = {
        "name": data.name,
        "name_en": data.name_en,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "type": data.type,
        "custom_type": data.custom_type,
        "term_id": data.term_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_update_one(db.session, "holidays", {"id": holiday_id}, update_data)
    updated = await gd_find_one(db.session, "holidays", {"id": holiday_id})
    return HolidayResponse(**updated)


@router.delete("/holidays/{holiday_id}")
async def delete_holiday(
    holiday_id: str,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = get_school_id(current_user)
    result = await gd_delete_one(db.session, "holidays", {"id": holiday_id, "school_id": school_id})
    if result == 0:
        raise HTTPException(status_code=404, detail="الإجازة غير موجودة")
    return {"message": "تم حذف الإجازة بنجاح"}


# ============== EXAM PERIODS ==============

@router.post("/exam-periods", response_model=ExamPeriodResponse)
async def create_exam_period(
    data: ExamPeriodCreate,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = await get_school_id_from_year(data.academic_year_id, current_user)
    now = datetime.now(timezone.utc).isoformat()

    exam_doc = {
        "id": str(uuid.uuid4()),
        "academic_year_id": data.academic_year_id,
        "term_id": data.term_id,
        "name": data.name,
        "name_en": data.name_en,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "exam_type": data.exam_type,
        "start_time": data.start_time,
        "end_time": data.end_time,
        "period_number": data.period_number,
        "school_id": school_id,
        "created_at": now,
        "created_by": current_user.get("id"),
    }
    await gd_insert(db.session, "exam_periods", exam_doc)
    exam_doc.pop("_id", None)
    return ExamPeriodResponse(**exam_doc)


@router.get("/exam-periods", response_model=List[ExamPeriodResponse])
async def get_exam_periods(
    academic_year_id: Optional[str] = None,
    term_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    school_id = get_school_id(current_user)
    query = {"school_id": school_id}
    if academic_year_id:
        query["academic_year_id"] = academic_year_id
    if term_id:
        query["term_id"] = term_id

    periods = await gd_find(db.session, "exam_periods", query, order_by="start_date", desc_order=False, limit=100)
    return [ExamPeriodResponse(**p) for p in periods]


@router.put("/exam-periods/{period_id}", response_model=ExamPeriodResponse)
async def update_exam_period(
    period_id: str,
    data: ExamPeriodCreate,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = get_school_id(current_user)
    period = await gd_find_one(db.session, "exam_periods", {"id": period_id, "school_id": school_id})
    if not period:
        raise HTTPException(status_code=404, detail="فترة الاختبارات غير موجودة")

    update_data = {
        "name": data.name,
        "name_en": data.name_en,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "exam_type": data.exam_type,
        "start_time": data.start_time,
        "end_time": data.end_time,
        "period_number": data.period_number,
        "term_id": data.term_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_update_one(db.session, "exam_periods", {"id": period_id}, update_data)
    updated = await gd_find_one(db.session, "exam_periods", {"id": period_id})
    return ExamPeriodResponse(**updated)


@router.delete("/exam-periods/{period_id}")
async def delete_exam_period(
    period_id: str,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = get_school_id(current_user)
    result = await gd_delete_one(db.session, "exam_periods", {"id": period_id, "school_id": school_id})
    if result == 0:
        raise HTTPException(status_code=404, detail="فترة الاختبارات غير موجودة")
    return {"message": "تم حذف فترة الاختبارات بنجاح"}


# ============== ACADEMIC CALENDAR VIEW ==============

@router.get("/academic-calendar/{year_id}")
async def get_academic_calendar(
    year_id: str,
    current_user: dict = Depends(get_current_user)
):
    school_id = await get_school_id_from_year(year_id, current_user)
    year = await gd_find_one(db.session, "academic_years", {"id": year_id})
    if not year:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")
    school_id = school_id or year.get("school_id", "")

    terms = await gd_find(db.session, "terms", {"academic_year_id": year_id, "school_id": school_id}, order_by="start_date", desc_order=False, limit=10)

    holidays = await gd_find(db.session, "holidays", {"academic_year_id": year_id, "school_id": school_id}, order_by="start_date", desc_order=False, limit=200)

    exam_periods = await gd_find(db.session, "exam_periods", {"academic_year_id": year_id, "school_id": school_id}, order_by="start_date", desc_order=False, limit=100)

    total_holiday_days = 0
    for h in holidays:
        try:
            s = datetime.strptime(h["start_date"], "%Y-%m-%d")
            e = datetime.strptime(h["end_date"], "%Y-%m-%d")
            total_holiday_days += (e - s).days + 1
        except (ValueError, KeyError):
            pass

    total_exam_days = 0
    for ep in exam_periods:
        try:
            s = datetime.strptime(ep["start_date"], "%Y-%m-%d")
            e = datetime.strptime(ep["end_date"], "%Y-%m-%d")
            total_exam_days += (e - s).days + 1
        except (ValueError, KeyError):
            pass

    try:
        year_start = datetime.strptime(year.get("start_date", ""), "%Y-%m-%d")
        year_end = datetime.strptime(year.get("end_date", ""), "%Y-%m-%d")
        total_days = (year_end - year_start).days + 1
        weekends = sum(1 for d in range(total_days) if (year_start + timedelta(days=d)).weekday() >= 4)
        school_days = total_days - weekends - total_holiday_days
    except (ValueError, TypeError):
        total_days = 0
        school_days = 0

    return {
        "academic_year": year,
        "terms": terms,
        "holidays": holidays,
        "exam_periods": exam_periods,
        "summary": {
            "total_days": total_days,
            "school_days": max(0, school_days),
            "holiday_days": total_holiday_days,
            "exam_days": total_exam_days,
            "terms_count": len(terms),
        }
    }


# ============== HAKIM AI ACADEMIC ANALYSIS ==============

@router.get("/academic-structure/ai-analysis/{year_id}")
async def hakim_academic_analysis(
    year_id: str,
    current_user: dict = Depends(get_current_user)
):
    school_id = await get_school_id_from_year(year_id, current_user)
    year = await gd_find_one(db.session, "academic_years", {"id": year_id})
    if not year:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")
    school_id = school_id or year.get("school_id", "")

    terms = await gd_find(db.session, "terms", {"academic_year_id": year_id, "school_id": school_id}, order_by="start_date", desc_order=False, limit=10)

    holidays = await gd_find(db.session, "holidays", {"academic_year_id": year_id, "school_id": school_id}, limit=200)

    exam_periods = await gd_find(db.session, "exam_periods", {"academic_year_id": year_id, "school_id": school_id}, limit=100)

    insights = []
    severity_map = {"warning": "تحذير", "info": "معلومة", "suggestion": "اقتراح"}

    if len(terms) >= 2:
        term_durations = []
        for t in terms:
            try:
                s = datetime.strptime(t["start_date"], "%Y-%m-%d")
                e = datetime.strptime(t["end_date"], "%Y-%m-%d")
                term_durations.append((t["name"], (e - s).days))
            except (ValueError, KeyError):
                pass

        if term_durations:
            avg = sum(d for _, d in term_durations) / len(term_durations)
            for name, days in term_durations:
                if days < avg - 14:
                    insights.append({
                        "type": "warning",
                        "message": f"الفصل '{name}' أقصر من المتوسط بـ {int(avg - days)} يوم",
                        "message_en": f"Term '{name}' is {int(avg - days)} days shorter than average",
                    })
                elif days > avg + 14:
                    insights.append({
                        "type": "warning",
                        "message": f"الفصل '{name}' أطول من المتوسط بـ {int(days - avg)} يوم",
                        "message_en": f"Term '{name}' is {int(days - avg)} days longer than average",
                    })

    terms_with_exams = set()
    for ep in exam_periods:
        terms_with_exams.add(ep.get("term_id"))
    for t in terms:
        if t["id"] not in terms_with_exams:
            insights.append({
                "type": "suggestion",
                "message": f"الفصل '{t['name']}' لا يحتوي على فترة اختبارات",
                "message_en": f"Term '{t['name']}' has no exam period defined",
            })

    for t in terms:
        try:
            t_start = datetime.strptime(t["start_date"], "%Y-%m-%d")
            t_end = datetime.strptime(t["end_date"], "%Y-%m-%d")
            t_days = (t_end - t_start).days
            t_weeks = t_days / 7
            if t_weeks < 10:
                insights.append({
                    "type": "warning",
                    "message": f"الفصل '{t['name']}' يحتوي على {int(t_weeks)} أسابيع فقط (الحد الأدنى المقترح: 10)",
                    "message_en": f"Term '{t['name']}' has only {int(t_weeks)} weeks (minimum suggested: 10)",
                })
        except (ValueError, KeyError):
            pass

    if not holidays:
        insights.append({
            "type": "suggestion",
            "message": "لم يتم إضافة أي إجازات للعام الدراسي",
            "message_en": "No holidays have been added for this academic year",
        })

    if not insights:
        insights.append({
            "type": "info",
            "message": "الهيكل الأكاديمي متوازن ومناسب",
            "message_en": "Academic structure is balanced and appropriate",
        })

    return {
        "year_id": year_id,
        "year_name": year.get("name"),
        "insights": insights,
        "stats": {
            "terms_count": len(terms),
            "holidays_count": len(holidays),
            "exam_periods_count": len(exam_periods),
        }
    }


class CalendarImportApply(BaseModel):
    import_data: dict


@router.post("/academic-calendar/{year_id}/import")
async def import_calendar_ai(
    year_id: str,
    file: UploadFile = File(...),
    instructions: Optional[str] = Form(None),
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    """Use AI to parse an uploaded Excel/CSV file and extract holidays and exam periods."""
    school_id = get_school_id(current_user)
    year = await gd_find_one(db.session, "academic_years", {"id": year_id, "school_id": school_id})
    if not year:
        raise HTTPException(status_code=404, detail="السنة الدراسية غير موجودة")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم الملف يتجاوز الحد المسموح (10 ميغابايت)")
    filename = file.filename or "calendar"

    try:
        import io
        import csv
        import os
        from openai import OpenAI

        text_content = ""
        if filename.endswith(".csv"):
            try:
                reader = csv.reader(io.StringIO(content.decode("utf-8-sig", errors="replace")))
                rows = [",".join(row) for row in reader]
                text_content = "\n".join(rows[:200])
            except Exception:
                text_content = content.decode("utf-8", errors="replace")[:3000]
        else:
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
                ws = wb.active
                rows = []
                for i, row in enumerate(ws.iter_rows(values_only=True)):
                    if i >= 200:
                        break
                    rows.append(" | ".join([str(c) if c is not None else "" for c in row]))
                text_content = "\n".join(rows)
            except Exception:
                text_content = content.decode("utf-8", errors="replace")[:3000]

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        system_prompt = (
            "You are an Arabic academic calendar analyzer. "
            "Extract holidays and exam periods from the provided table data. "
            "Return a JSON object with two arrays: 'holidays' and 'exam_periods'. "
            "Each holiday: {name, name_en, start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), type (public/school/activity/other)}. "
            "Each exam_period: {name, name_en, start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), exam_type (midterm/final)}. "
            "If dates are in Hijri format, convert to Gregorian. Respond with JSON only."
        )
        user_msg = f"Academic year: {year.get('name')}\nFile: {filename}\n\nTable data:\n{text_content}"
        if instructions:
            user_msg += f"\n\nAdditional instructions: {instructions}"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ],
            response_format={"type": "json_object"},
            max_tokens=2000
        )
        import json
        result = json.loads(response.choices[0].message.content)
        result["message"] = f"تم تحليل الملف بنجاح. تم اكتشاف {len(result.get('holidays', []))} إجازة و{len(result.get('exam_periods', []))} فترة اختبارات."
        return result
    except Exception as e:
        logger.error(f"Calendar import AI error: {e}")
        raise HTTPException(status_code=500, detail="فشل في تحليل الملف. يرجى المحاولة مجدداً أو التواصل مع الدعم الفني.")


@router.post("/academic-calendar/{year_id}/import/apply")
async def apply_calendar_import(
    year_id: str,
    body: CalendarImportApply,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    """Apply previously analyzed calendar data to create holidays and exam periods."""
    school_id = get_school_id(current_user)
    year = await gd_find_one(db.session, "academic_years", {"id": year_id, "school_id": school_id})
    if not year:
        raise HTTPException(status_code=404, detail="السنة الدراسية غير موجودة")

    import_data = body.import_data
    created_holidays = 0
    created_exams = 0
    now = datetime.now(timezone.utc).isoformat()

    for h in import_data.get("holidays", []):
        try:
            doc = {
                "id": str(uuid.uuid4()),
                "school_id": school_id,
                "academic_year_id": year_id,
                "term_id": h.get("term_id"),
                "name": h.get("name", "إجازة"),
                "name_en": h.get("name_en"),
                "start_date": h.get("start_date", ""),
                "end_date": h.get("end_date", h.get("start_date", "")),
                "type": h.get("type", "public"),
                "custom_type": h.get("custom_type"),
                "created_at": now
            }
            await gd_insert(db.session, "holidays", doc)
            created_holidays += 1
        except Exception as e:
            logger.warning(f"Failed to insert holiday: {e}")

    terms = await gd_find(db.session, "academic_terms", {"academic_year_id": year_id, "school_id": school_id})
    term_id = terms[0]["id"] if terms else None

    for ep in import_data.get("exam_periods", []):
        try:
            doc = {
                "id": str(uuid.uuid4()),
                "school_id": school_id,
                "academic_year_id": year_id,
                "term_id": ep.get("term_id") or term_id or "",
                "name": ep.get("name", "فترة اختبارات"),
                "name_en": ep.get("name_en"),
                "start_date": ep.get("start_date", ""),
                "end_date": ep.get("end_date", ep.get("start_date", "")),
                "exam_type": ep.get("exam_type", "final"),
                "start_time": ep.get("start_time"),
                "end_time": ep.get("end_time"),
                "period_number": ep.get("period_number"),
                "created_at": now
            }
            await gd_insert(db.session, "exam_periods", doc)
            created_exams += 1
        except Exception as e:
            logger.warning(f"Failed to insert exam period: {e}")

    return {
        "success": True,
        "created_holidays": created_holidays,
        "created_exam_periods": created_exams,
        "message": f"تم إنشاء {created_holidays} إجازة و{created_exams} فترة اختبارات بنجاح"
    }
