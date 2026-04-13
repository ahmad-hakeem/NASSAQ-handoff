"""
NASSAQ Route Module: Participation Engine endpoints
Full participation tracking, statistics, and reporting.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid, logging

from dependencies import (
    db, get_current_user, require_roles, UserRole, logger
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct


router = APIRouter()


class ParticipationTypeEnum(str, Enum):
    HAND_RAISE = "hand_raise"
    VERBAL_ANSWER = "verbal_answer"
    BOARD_WORK = "board_work"
    GROUP_WORK = "group_work"
    PRESENTATION = "presentation"
    DISCUSSION = "discussion"
    QUESTION_ASKED = "question_asked"
    VOLUNTEER = "volunteer"
    HOMEWORK_REVIEW = "homework_review"
    OTHER = "other"


class ParticipationQualityEnum(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    BELOW_AVERAGE = "below_average"
    POOR = "poor"


class ParticipationCreate(BaseModel):
    student_id: str
    class_id: str
    subject_id: Optional[str] = None
    session_id: Optional[str] = None
    participation_type: ParticipationTypeEnum = ParticipationTypeEnum.HAND_RAISE
    quality: ParticipationQualityEnum = ParticipationQualityEnum.GOOD
    points: int = Field(default=1, ge=0, le=10)
    notes: Optional[str] = None


class BulkParticipationCreate(BaseModel):
    class_id: str
    subject_id: Optional[str] = None
    session_id: Optional[str] = None
    records: List[dict]


class ParticipationUpdate(BaseModel):
    participation_type: Optional[ParticipationTypeEnum] = None
    quality: Optional[ParticipationQualityEnum] = None
    points: Optional[int] = Field(default=None, ge=0, le=10)
    notes: Optional[str] = None


QUALITY_POINTS = {
    "excellent": 5,
    "good": 4,
    "average": 3,
    "below_average": 2,
    "poor": 1
}


@router.post("/participation")
async def record_participation(
    data: ParticipationCreate,
    current_user: dict = Depends(get_current_user)
):
    """Record a student participation event"""
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")

    student = await gd_find_one(db.session, "students", {"id": data.student_id, "tenant_id": school_id})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    record_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    auto_points = data.points or QUALITY_POINTS.get(data.quality.value, 3)

    record = {
        "id": record_id,
        "tenant_id": school_id,
        "student_id": data.student_id,
        "student_name": student.get("full_name"),
        "class_id": data.class_id,
        "subject_id": data.subject_id,
        "session_id": data.session_id,
        "participation_type": data.participation_type.value,
        "quality": data.quality.value,
        "points": auto_points,
        "notes": data.notes,
        "recorded_by": current_user["id"],
        "recorded_by_name": current_user.get("full_name"),
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_at": now,
        "updated_at": now
    }

    await gd_insert(db.session, "participation_records", record)
    record.pop("_id", None)
    return record


@router.post("/participation/bulk")
async def record_bulk_participation(
    data: BulkParticipationCreate,
    current_user: dict = Depends(get_current_user)
):
    """Record participation for multiple students at once"""
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")

    now = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    created = 0
    errors = []

    for entry in data.records:
        student_id = entry.get("student_id")
        if not student_id:
            errors.append({"error": "missing student_id"})
            continue

        student = await gd_find_one(db.session, "students", {"id": student_id, "tenant_id": school_id})
        if not student:
            errors.append({"student_id": student_id, "error": "student not found"})
            continue

        quality = entry.get("quality", "good")
        record = {
            "id": str(uuid.uuid4()),
            "tenant_id": school_id,
            "student_id": student_id,
            "student_name": student.get("full_name"),
            "class_id": data.class_id,
            "subject_id": data.subject_id,
            "session_id": data.session_id,
            "participation_type": entry.get("participation_type", "hand_raise"),
            "quality": quality,
            "points": entry.get("points", QUALITY_POINTS.get(quality, 3)),
            "notes": entry.get("notes"),
            "recorded_by": current_user["id"],
            "recorded_by_name": current_user.get("full_name"),
            "date": today,
            "created_at": now,
            "updated_at": now
        }
        await gd_insert(db.session, "participation_records", record)
        created += 1

    try:
        import asyncio
        from engines.portfolio_evidence_engine import PortfolioEvidenceEngine
        _pe = PortfolioEvidenceEngine(db)
        asyncio.create_task(_pe.capture_evidence(
            teacher_id=current_user["id"],
            school_id=school_id or "",
            evidence_type="participation_tracking",
            title_ar=f"متابعة مشاركة: {today}",
            title_en=f"Participation Tracking: {today}",
            description_ar=f"تسجيل {created} مشاركة للفصل",
            description_en=f"Recorded {created} participations for class",
            source="auto", source_entity_type="participation_bulk",
            source_entity_id=f"{data.class_id}_{today}",
            class_id=data.class_id,
            subject_id=data.subject_id,
            metadata={"created": created, "errors_count": len(errors)},
            event_date=today,
        ))
    except Exception as _pe_err:
        logging.getLogger(__name__).debug("Portfolio evidence (participation) failed: %s", _pe_err)

    return {"created": created, "errors": errors, "total_submitted": len(data.records)}


@router.get("/participation/student/{student_id}")
async def get_student_participation_history(
    student_id: str,
    class_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """Get participation history for a student"""
    school_id = current_user.get("tenant_id")
    query = {"tenant_id": school_id, "student_id": student_id}

    if class_id:
        query["class_id"] = class_id
    if subject_id:
        query["subject_id"] = subject_id
    if start_date:
        query.setdefault("date", {})["$gte"] = start_date
    if end_date:
        query.setdefault("date", {})["$lte"] = end_date

    records = await gd_find(db.session, "participation_records", query, order_by="created_at", desc_order=True, offset=skip, limit=limit)

    total = await gd_count(db.session, "participation_records", query)

    return {"records": records, "total": total}


@router.get("/participation/class/{class_id}")
async def get_class_participation(
    class_id: str,
    subject_id: Optional[str] = None,
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get participation records for a class"""
    school_id = current_user.get("tenant_id")
    query = {"tenant_id": school_id, "class_id": class_id}

    if subject_id:
        query["subject_id"] = subject_id
    if date:
        query["date"] = date
    if start_date:
        query.setdefault("date", {})["$gte"] = start_date
    if end_date:
        query.setdefault("date", {})["$lte"] = end_date

    records = await gd_find(db.session, "participation_records", query, order_by="created_at", desc_order=True, limit=5000)

    student_summary = {}
    for r in records:
        sid = r.get("student_id")
        if sid not in student_summary:
            student_summary[sid] = {
                "student_id": sid,
                "student_name": r.get("student_name"),
                "total_participations": 0,
                "total_points": 0,
                "types": {},
                "quality_distribution": {}
            }
        s = student_summary[sid]
        s["total_participations"] += 1
        s["total_points"] += r.get("points", 0)

        ptype = r.get("participation_type", "other")
        s["types"][ptype] = s["types"].get(ptype, 0) + 1

        qual = r.get("quality", "average")
        s["quality_distribution"][qual] = s["quality_distribution"].get(qual, 0) + 1

    students = sorted(student_summary.values(), key=lambda x: x["total_points"], reverse=True)

    return {
        "class_id": class_id,
        "total_records": len(records),
        "students": students,
        "student_count": len(students)
    }


@router.get("/participation/{record_id}")
async def get_participation_record(
    record_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific participation record"""
    school_id = current_user.get("tenant_id")
    record = await gd_find_one(db.session, "participation_records", {"id": record_id, "tenant_id": school_id})
    if not record:
        raise HTTPException(status_code=404, detail="السجل غير موجود")
    return record


@router.put("/participation/{record_id}")
async def update_participation_record(
    record_id: str,
    data: ParticipationUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a participation record"""
    school_id = current_user.get("tenant_id")
    record = await gd_find_one(db.session, "participation_records", {"id": record_id, "tenant_id": school_id})
    if not record:
        raise HTTPException(status_code=404, detail="السجل غير موجود")

    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if data.participation_type is not None:
        updates["participation_type"] = data.participation_type.value
    if data.quality is not None:
        updates["quality"] = data.quality.value
    if data.points is not None:
        updates["points"] = data.points
    if data.notes is not None:
        updates["notes"] = data.notes

    await gd_update_one(db.session, "participation_records", {"id": record_id, "tenant_id": school_id}, updates)

    return {"message": "تم تحديث السجل بنجاح", "id": record_id}


@router.delete("/participation/{record_id}")
async def delete_participation_record(
    record_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a participation record"""
    school_id = current_user.get("tenant_id")
    result = await gd_delete_one(db.session, "participation_records", {"id": record_id, "tenant_id": school_id})
    if result == 0:
        raise HTTPException(status_code=404, detail="السجل غير موجود")
    return {"message": "تم حذف السجل بنجاح"}


@router.get("/participation/statistics/student/{student_id}")
async def get_student_participation_statistics(
    student_id: str,
    class_id: Optional[str] = None,
    period: str = "month",
    current_user: dict = Depends(get_current_user)
):
    """Get detailed participation statistics for a student"""
    school_id = current_user.get("tenant_id")
    query = {"tenant_id": school_id, "student_id": student_id}

    if class_id:
        query["class_id"] = class_id

    now = datetime.now(timezone.utc)
    if period == "week":
        start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "month":
        start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    elif period == "semester":
        start = (now - timedelta(days=120)).strftime("%Y-%m-%d")
    else:
        start = (now - timedelta(days=365)).strftime("%Y-%m-%d")

    query["date"] = {"$gte": start}

    records = await gd_find(db.session, "participation_records", query, limit=5000)

    total_points = sum(r.get("points", 0) for r in records)
    total_count = len(records)
    avg_points = round(total_points / total_count, 2) if total_count > 0 else 0

    by_type = {}
    for r in records:
        ptype = r.get("participation_type", "other")
        by_type[ptype] = by_type.get(ptype, 0) + 1

    by_quality = {}
    for r in records:
        qual = r.get("quality", "average")
        by_quality[qual] = by_quality.get(qual, 0) + 1

    by_subject = {}
    for r in records:
        sid = r.get("subject_id", "unknown")
        if sid not in by_subject:
            by_subject[sid] = {"count": 0, "points": 0}
        by_subject[sid]["count"] += 1
        by_subject[sid]["points"] += r.get("points", 0)

    daily_trend = {}
    for r in records:
        d = r.get("date", "")
        if d not in daily_trend:
            daily_trend[d] = {"count": 0, "points": 0}
        daily_trend[d]["count"] += 1
        daily_trend[d]["points"] += r.get("points", 0)

    if total_count >= 10 and avg_points >= 4:
        level = "ممتاز"
    elif total_count >= 5 and avg_points >= 3:
        level = "جيد جداً"
    elif total_count >= 3 and avg_points >= 2:
        level = "جيد"
    elif total_count >= 1:
        level = "مقبول"
    else:
        level = "لا توجد مشاركات"

    score = min(100, round((total_points / max(1, total_count * 5)) * 100))

    return {
        "student_id": student_id,
        "period": period,
        "total_participations": total_count,
        "total_points": total_points,
        "average_points": avg_points,
        "participation_score": score,
        "participation_level": level,
        "by_type": by_type,
        "by_quality": by_quality,
        "by_subject": by_subject,
        "daily_trend": dict(sorted(daily_trend.items())),
        "most_active_type": max(by_type, key=by_type.get) if by_type else None,
        "dominant_quality": max(by_quality, key=by_quality.get) if by_quality else None
    }


@router.get("/participation/statistics/class/{class_id}")
async def get_class_participation_statistics(
    class_id: str,
    subject_id: Optional[str] = None,
    period: str = "month",
    current_user: dict = Depends(get_current_user)
):
    """Get participation statistics for a class with rankings"""
    school_id = current_user.get("tenant_id")
    query = {"tenant_id": school_id, "class_id": class_id}

    if subject_id:
        query["subject_id"] = subject_id

    now = datetime.now(timezone.utc)
    if period == "week":
        start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "month":
        start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    else:
        start = (now - timedelta(days=120)).strftime("%Y-%m-%d")

    query["date"] = {"$gte": start}

    records = await gd_find(db.session, "participation_records", query, limit=10000)

    class_students = await gd_find(db.session, "students", {"tenant_id": school_id, "class_id": class_id}, limit=100)
    all_student_ids = {s["id"] for s in class_students}

    student_stats = {}
    for s in class_students:
        student_stats[s["id"]] = {
            "student_id": s["id"],
            "student_name": s.get("full_name"),
            "total_participations": 0,
            "total_points": 0,
            "quality_avg": 0
        }

    for r in records:
        sid = r.get("student_id")
        if sid in student_stats:
            student_stats[sid]["total_participations"] += 1
            student_stats[sid]["total_points"] += r.get("points", 0)

    for sid, st in student_stats.items():
        if st["total_participations"] > 0:
            st["quality_avg"] = round(st["total_points"] / st["total_participations"], 2)

    rankings = sorted(student_stats.values(), key=lambda x: x["total_points"], reverse=True)
    for i, s in enumerate(rankings):
        s["rank"] = i + 1

    participating_students = [s["student_id"] for s in rankings if s["total_participations"] > 0]
    non_participating = [s for s in rankings if s["total_participations"] == 0]

    total_records = len(records)
    class_avg = round(total_records / max(1, len(all_student_ids)), 2)

    return {
        "class_id": class_id,
        "period": period,
        "total_records": total_records,
        "total_students": len(all_student_ids),
        "participating_students": len(participating_students),
        "non_participating_students": len(non_participating),
        "participation_rate": round(len(participating_students) / max(1, len(all_student_ids)) * 100, 1),
        "average_per_student": class_avg,
        "rankings": rankings,
        "non_participating": non_participating,
        "top_3": rankings[:3] if len(rankings) >= 3 else rankings,
        "needs_attention": [s for s in non_participating[:5]]
    }


@router.get("/participation/report/student/{student_id}")
async def get_student_participation_report(
    student_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Generate a comprehensive participation report for a student"""
    school_id = current_user.get("tenant_id")

    student = await gd_find_one(db.session, "students", {"id": student_id, "tenant_id": school_id})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    all_records = await gd_find(db.session, "participation_records", {"tenant_id": school_id, "student_id": student_id}, order_by="date", desc_order=True, limit=10000)

    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    month_start = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    week_records = [r for r in all_records if r.get("date", "") >= week_start]
    month_records = [r for r in all_records if r.get("date", "") >= month_start]

    def calc_summary(recs):
        total = len(recs)
        pts = sum(r.get("points", 0) for r in recs)
        return {"count": total, "points": pts, "avg": round(pts / max(1, total), 2)}

    class_id = student.get("class_id")
    class_rank = None
    if class_id:
        class_records = await gd_find(db.session, "participation_records", {"tenant_id": school_id, "class_id": class_id, "date": {"$gte": month_start}}, limit=10000)

        student_points = {}
        for r in class_records:
            sid = r.get("student_id")
            student_points[sid] = student_points.get(sid, 0) + r.get("points", 0)

        sorted_students = sorted(student_points.items(), key=lambda x: x[1], reverse=True)
        for i, (sid, pts) in enumerate(sorted_students):
            if sid == student_id:
                class_rank = i + 1
                break

    total_pts = sum(r.get("points", 0) for r in all_records)
    total_count = len(all_records)
    score = min(100, round((total_pts / max(1, total_count * 5)) * 100))

    return {
        "student_id": student_id,
        "student_name": student.get("full_name"),
        "class_id": class_id,
        "total_all_time": calc_summary(all_records),
        "this_week": calc_summary(week_records),
        "this_month": calc_summary(month_records),
        "participation_score": score,
        "class_rank": class_rank,
        "recent_activities": all_records[:10],
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/participation/leaderboard/{class_id}")
async def get_participation_leaderboard(
    class_id: str,
    period: str = "month",
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """Get participation leaderboard for a class"""
    school_id = current_user.get("tenant_id")

    now = datetime.now(timezone.utc)
    if period == "week":
        start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "month":
        start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    else:
        start = (now - timedelta(days=120)).strftime("%Y-%m-%d")

    records = await gd_find(db.session, "participation_records", {"tenant_id": school_id, "class_id": class_id, "date": {"$gte": start}}, limit=10000)

    student_scores = {}
    for r in records:
        sid = r.get("student_id")
        if sid not in student_scores:
            student_scores[sid] = {
                "student_id": sid,
                "student_name": r.get("student_name"),
                "total_points": 0,
                "total_participations": 0,
                "excellent_count": 0
            }
        student_scores[sid]["total_points"] += r.get("points", 0)
        student_scores[sid]["total_participations"] += 1
        if r.get("quality") == "excellent":
            student_scores[sid]["excellent_count"] += 1

    leaderboard = sorted(student_scores.values(), key=lambda x: x["total_points"], reverse=True)
    for i, s in enumerate(leaderboard):
        s["rank"] = i + 1
        if i == 0:
            s["badge"] = "🥇"
        elif i == 1:
            s["badge"] = "🥈"
        elif i == 2:
            s["badge"] = "🥉"
        else:
            s["badge"] = ""

    return {
        "class_id": class_id,
        "period": period,
        "leaderboard": leaderboard[:limit],
        "total_students": len(leaderboard)
    }
