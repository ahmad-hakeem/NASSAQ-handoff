"""
NASSAQ Academic Structure Routes
Holidays, Exam Periods, Promotion Rules, Academic Calendar, Publish/Archive workflows.
Extends the academic year & term CRUD in academics_year_term_routes.py.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from dependencies import db, get_current_user, require_roles, UserRole
import logging

logger = logging.getLogger("nassaq.academic_structure_routes")

router = APIRouter(tags=["Academic Structure"])


class HolidayCreate(BaseModel):
    academic_year_id: str
    term_id: Optional[str] = None
    name: str
    name_en: Optional[str] = None
    start_date: str
    end_date: str
    type: str = "public"


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
    school_id: str
    created_at: str


class PromotionRuleCreate(BaseModel):
    academic_year_id: str
    mode: str = "auto"
    min_attendance_percent: float = 75.0
    min_grade_percent: float = 50.0
    max_failures: int = 2
    rules: Optional[dict] = None


class PromotionRuleResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    academic_year_id: str
    mode: str
    min_attendance_percent: float
    min_grade_percent: float
    max_failures: int
    rules: Optional[dict] = None
    school_id: str
    created_at: str
    updated_at: str


ADMIN_ROLES = [UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]


def get_school_id(current_user: dict) -> str:
    return current_user.get("tenant_id") or current_user.get("school_id") or ""


async def get_school_id_from_year(year_id: str, current_user: dict) -> str:
    sid = get_school_id(current_user)
    if sid:
        return sid
    year = await db.academic_years.find_one({"id": year_id}, {"school_id": 1})
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

    current_year = await db.academic_years.find_one(
        {"school_id": school_id, "is_current": True}, {"_id": 0}
    )

    all_years = await db.academic_years.find(
        {"school_id": school_id}, {"_id": 0}
    ).sort("start_date", -1).to_list(50)

    current_term = None
    terms_count = 0
    remaining_days = 0

    if current_year:
        terms = await db.terms.find(
            {"school_id": school_id, "academic_year_id": current_year["id"]}, {"_id": 0}
        ).sort("start_date", 1).to_list(10)
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
    year = await db.academic_years.find_one({"id": year_id, "school_id": school_id})
    if not year:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")

    if year.get("status") == "active" and year.get("is_current"):
        raise HTTPException(status_code=400, detail="العام الدراسي منشور بالفعل")

    terms = await db.terms.find(
        {"academic_year_id": year_id, "school_id": school_id}
    ).to_list(10)
    if not terms:
        raise HTTPException(status_code=400, detail="يجب إضافة فصول دراسية قبل النشر")

    await db.academic_years.update_many(
        {"school_id": school_id, "is_current": True},
        {"$set": {"is_current": False}}
    )

    now = datetime.now(timezone.utc).isoformat()
    await db.academic_years.update_one(
        {"id": year_id, "school_id": school_id},
        {"$set": {
            "status": "active",
            "is_current": True,
            "published_at": now,
            "published_by": current_user.get("id"),
            "updated_at": now,
        }}
    )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for t in terms:
        if t.get("start_date", "") <= today <= t.get("end_date", ""):
            await db.terms.update_many(
                {"academic_year_id": year_id, "school_id": school_id},
                {"$set": {"is_current": False}}
            )
            await db.terms.update_one(
                {"id": t["id"]},
                {"$set": {"is_current": True}}
            )
            break

    await db.audit_logs.insert_one({
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
    year = await db.academic_years.find_one({"id": year_id, "school_id": school_id})
    if not year:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")

    now = datetime.now(timezone.utc).isoformat()
    await db.academic_years.update_one(
        {"id": year_id, "school_id": school_id},
        {"$set": {"status": "closed", "is_current": False, "closed_at": now, "updated_at": now}}
    )

    await db.terms.update_many(
        {"academic_year_id": year_id, "school_id": school_id},
        {"$set": {"is_current": False}}
    )

    await db.audit_logs.insert_one({
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
    year = await db.academic_years.find_one({"id": year_id, "school_id": school_id})
    if not year:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")

    if year.get("status") == "active" and year.get("is_current"):
        raise HTTPException(status_code=400, detail="لا يمكن أرشفة عام دراسي نشط")

    now = datetime.now(timezone.utc).isoformat()
    await db.academic_years.update_one(
        {"id": year_id, "school_id": school_id},
        {"$set": {"status": "archived", "is_current": False, "archived_at": now, "updated_at": now}}
    )

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
    year = await db.academic_years.find_one({"id": year_id, "school_id": school_id}, {"_id": 0})
    if not year:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")

    existing = await db.terms.count_documents({"academic_year_id": year_id, "school_id": school_id})
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
        await db.terms.insert_one(term_doc)
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
        "school_id": school_id,
        "created_at": now,
        "created_by": current_user.get("id"),
    }
    await db.holidays.insert_one(holiday_doc)
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

    holidays = await db.holidays.find(query, {"_id": 0}).sort("start_date", 1).to_list(200)
    return [HolidayResponse(**h) for h in holidays]


@router.put("/holidays/{holiday_id}", response_model=HolidayResponse)
async def update_holiday(
    holiday_id: str,
    data: HolidayCreate,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = get_school_id(current_user)
    holiday = await db.holidays.find_one({"id": holiday_id, "school_id": school_id})
    if not holiday:
        raise HTTPException(status_code=404, detail="الإجازة غير موجودة")

    update_data = {
        "name": data.name,
        "name_en": data.name_en,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "type": data.type,
        "term_id": data.term_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.holidays.update_one({"id": holiday_id}, {"$set": update_data})
    updated = await db.holidays.find_one({"id": holiday_id}, {"_id": 0})
    return HolidayResponse(**updated)


@router.delete("/holidays/{holiday_id}")
async def delete_holiday(
    holiday_id: str,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = get_school_id(current_user)
    result = await db.holidays.delete_one({"id": holiday_id, "school_id": school_id})
    if result.deleted_count == 0:
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
        "school_id": school_id,
        "created_at": now,
        "created_by": current_user.get("id"),
    }
    await db.exam_periods.insert_one(exam_doc)
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

    periods = await db.exam_periods.find(query, {"_id": 0}).sort("start_date", 1).to_list(100)
    return [ExamPeriodResponse(**p) for p in periods]


@router.put("/exam-periods/{period_id}", response_model=ExamPeriodResponse)
async def update_exam_period(
    period_id: str,
    data: ExamPeriodCreate,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = get_school_id(current_user)
    period = await db.exam_periods.find_one({"id": period_id, "school_id": school_id})
    if not period:
        raise HTTPException(status_code=404, detail="فترة الاختبارات غير موجودة")

    update_data = {
        "name": data.name,
        "name_en": data.name_en,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "exam_type": data.exam_type,
        "term_id": data.term_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.exam_periods.update_one({"id": period_id}, {"$set": update_data})
    updated = await db.exam_periods.find_one({"id": period_id}, {"_id": 0})
    return ExamPeriodResponse(**updated)


@router.delete("/exam-periods/{period_id}")
async def delete_exam_period(
    period_id: str,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = get_school_id(current_user)
    result = await db.exam_periods.delete_one({"id": period_id, "school_id": school_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="فترة الاختبارات غير موجودة")
    return {"message": "تم حذف فترة الاختبارات بنجاح"}


# ============== PROMOTION RULES ==============

@router.post("/promotion-rules", response_model=PromotionRuleResponse)
async def create_promotion_rule(
    data: PromotionRuleCreate,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = await get_school_id_from_year(data.academic_year_id, current_user)
    now = datetime.now(timezone.utc).isoformat()

    existing = await db.promotion_rules.find_one({
        "school_id": school_id,
        "academic_year_id": data.academic_year_id
    })
    if existing:
        raise HTTPException(status_code=400, detail="توجد قواعد ترقية بالفعل لهذا العام")

    rule_doc = {
        "id": str(uuid.uuid4()),
        "academic_year_id": data.academic_year_id,
        "mode": data.mode,
        "min_attendance_percent": data.min_attendance_percent,
        "min_grade_percent": data.min_grade_percent,
        "max_failures": data.max_failures,
        "rules": data.rules or {},
        "school_id": school_id,
        "created_at": now,
        "updated_at": now,
        "created_by": current_user.get("id"),
    }
    await db.promotion_rules.insert_one(rule_doc)
    rule_doc.pop("_id", None)
    return PromotionRuleResponse(**rule_doc)


@router.get("/promotion-rules")
async def get_promotion_rules(
    academic_year_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    school_id = get_school_id(current_user)
    query = {"school_id": school_id}
    if academic_year_id:
        query["academic_year_id"] = academic_year_id

    rules = await db.promotion_rules.find(query, {"_id": 0}).to_list(50)
    return rules


@router.put("/promotion-rules/{rule_id}", response_model=PromotionRuleResponse)
async def update_promotion_rule(
    rule_id: str,
    data: PromotionRuleCreate,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = get_school_id(current_user)
    rule = await db.promotion_rules.find_one({"id": rule_id, "school_id": school_id})
    if not rule:
        raise HTTPException(status_code=404, detail="قواعد الترقية غير موجودة")

    update_data = {
        "mode": data.mode,
        "min_attendance_percent": data.min_attendance_percent,
        "min_grade_percent": data.min_grade_percent,
        "max_failures": data.max_failures,
        "rules": data.rules or {},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.promotion_rules.update_one({"id": rule_id}, {"$set": update_data})
    updated = await db.promotion_rules.find_one({"id": rule_id}, {"_id": 0})
    return PromotionRuleResponse(**updated)


@router.delete("/promotion-rules/{rule_id}")
async def delete_promotion_rule(
    rule_id: str,
    current_user: dict = Depends(require_roles(ADMIN_ROLES))
):
    school_id = get_school_id(current_user)
    result = await db.promotion_rules.delete_one({"id": rule_id, "school_id": school_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="قواعد الترقية غير موجودة")
    return {"message": "تم حذف قواعد الترقية بنجاح"}


# ============== ACADEMIC CALENDAR VIEW ==============

@router.get("/academic-calendar/{year_id}")
async def get_academic_calendar(
    year_id: str,
    current_user: dict = Depends(get_current_user)
):
    school_id = await get_school_id_from_year(year_id, current_user)
    year = await db.academic_years.find_one({"id": year_id}, {"_id": 0})
    if not year:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")
    school_id = school_id or year.get("school_id", "")

    terms = await db.terms.find(
        {"academic_year_id": year_id, "school_id": school_id}, {"_id": 0}
    ).sort("start_date", 1).to_list(10)

    holidays = await db.holidays.find(
        {"academic_year_id": year_id, "school_id": school_id}, {"_id": 0}
    ).sort("start_date", 1).to_list(200)

    exam_periods = await db.exam_periods.find(
        {"academic_year_id": year_id, "school_id": school_id}, {"_id": 0}
    ).sort("start_date", 1).to_list(100)

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
    year = await db.academic_years.find_one({"id": year_id}, {"_id": 0})
    if not year:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")
    school_id = school_id or year.get("school_id", "")

    terms = await db.terms.find(
        {"academic_year_id": year_id, "school_id": school_id}, {"_id": 0}
    ).sort("start_date", 1).to_list(10)

    holidays = await db.holidays.find(
        {"academic_year_id": year_id, "school_id": school_id}, {"_id": 0}
    ).to_list(200)

    exam_periods = await db.exam_periods.find(
        {"academic_year_id": year_id, "school_id": school_id}, {"_id": 0}
    ).to_list(100)

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
