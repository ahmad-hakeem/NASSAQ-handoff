"""
NASSAQ Route Module: Reports, reporting engine, export
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
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
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct


router = APIRouter()

ADMIN_ROLES_SET = {
    UserRole.PLATFORM_ADMIN.value, UserRole.SCHOOL_ADMIN.value,
    UserRole.SCHOOL_PRINCIPAL.value, UserRole.SCHOOL_SUB_ADMIN.value,
}

# ============== SCHOOL REPORTS APIs ==============
@router.get("/reports/school/overview")
async def get_school_overview_report(
    period: str = "current_term",
    current_user: dict = Depends(get_current_user)
):
    """Get school overview report with statistics"""
    import asyncio
    school_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id") or current_user.get("school_id")
    if not school_id:
        return {
            "total_students": 0, "total_teachers": 0, "total_classes": 0,
            "attendance_rate": 0, "avg_grade": 0,
            "attendance": {"present": 0, "absent": 0, "late": 0, "total": 0},
            "period": period,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    total_students, total_teachers, total_classes, attendance_records, grades = await asyncio.gather(
        gd_count(db.session, "students", {"school_id": school_id}),
        gd_count(db.session, "teachers", {"school_id": school_id}),
        gd_count(db.session, "classes", {"school_id": school_id}),
        gd_find(db.session, "attendance", {"school_id": school_id, "date": today}, limit=10000),
        gd_find(db.session, "grades", {"school_id": school_id}, limit=10000),
    )
    
    present_count = len([a for a in attendance_records if a.get("status") == "present"])
    absent_count = len([a for a in attendance_records if a.get("status") == "absent"])
    late_count = len([a for a in attendance_records if a.get("status") == "late"])
    total_attendance = len(attendance_records)
    
    attendance_rate = round((present_count / total_attendance) * 100, 1) if total_attendance > 0 else 0
    
    avg_grade = round(sum(g.get("grade", 0) for g in grades) / len(grades), 1) if grades else 0
    
    return {
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_classes": total_classes,
        "attendance_rate": attendance_rate,
        "avg_grade": avg_grade,
        "attendance": {
            "present": present_count,
            "absent": absent_count,
            "late": late_count,
            "total": total_attendance
        },
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }

@router.get("/reports/school/attendance")
async def get_school_attendance_report(
    period: str = "current_term",
    class_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed attendance report by class"""
    from auth_scope import independent_workspace_id as _itw_id
    school_id = current_user.get("tenant_id") or _itw_id(current_user)
    if not school_id:
        raise HTTPException(status_code=400, detail="المستخدم غير مرتبط بمدرسة")
    
    class_query = {"school_id": school_id}
    if class_id:
        class_query["id"] = class_id
    
    classes = await gd_find(db.session, "classes", class_query, limit=100)
    
    att_query = {"school_id": school_id}
    if class_id:
        att_query["class_id"] = class_id
    all_attendance = await gd_find(db.session, "attendance", att_query, limit=100000)
    
    att_by_class = {}
    for a in all_attendance:
        cid = a.get("class_id")
        if cid not in att_by_class:
            att_by_class[cid] = {"present": 0, "absent": 0, "late": 0, "total": 0}
        att_by_class[cid]["total"] += 1
        s = a.get("status")
        if s in ("present", "absent", "late"):
            att_by_class[cid][s] += 1
    
    report_data = []
    for cls in classes:
        cid = cls.get("id")
        stats = att_by_class.get(cid, {"present": 0, "absent": 0, "late": 0, "total": 0})
        rate = round((stats["present"] / stats["total"]) * 100, 1) if stats["total"] > 0 else 0
        
        report_data.append({
            "class": cls.get("name_ar") or cls.get("name"),
            "class_en": cls.get("name_en") or cls.get("name_ar") or cls.get("name"),
            "present": stats["present"],
            "absent": stats["absent"],
            "late": stats["late"],
            "rate": rate
        })
    
    return report_data

@router.get("/reports/school/grades")
async def get_school_grades_report(
    period: str = "current_term",
    subject_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get grades report by subject"""
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="المستخدم غير مرتبط بمدرسة")
    
    subject_query = {"school_id": school_id}
    if subject_id:
        subject_query["id"] = subject_id
    
    subjects = await gd_find(db.session, "subjects", subject_query, limit=100)
    
    grade_query = {"school_id": school_id}
    if subject_id:
        grade_query["subject_id"] = subject_id
    all_grades = await gd_find(db.session, "grades", grade_query, limit=100000)
    
    grades_by_subject = {}
    for g in all_grades:
        sid = g.get("subject_id")
        if sid not in grades_by_subject:
            grades_by_subject[sid] = []
        grades_by_subject[sid].append(g.get("grade", 0))
    
    report_data = []
    for subject in subjects:
        sid = subject.get("id")
        grade_values = grades_by_subject.get(sid, [])
        
        if grade_values:
            avg = round(sum(grade_values) / len(grade_values), 1)
            highest = max(grade_values)
            lowest = min(grade_values)
            passed = len([g for g in grade_values if g >= 50])
            pass_rate = round((passed / len(grade_values)) * 100, 0)
        else:
            avg = 0
            highest = 0
            lowest = 0
            pass_rate = 0
        
        report_data.append({
            "subject": subject.get("name_ar") or subject.get("name"),
            "subject_en": subject.get("name_en") or subject.get("name_ar") or subject.get("name"),
            "avg": avg,
            "highest": highest,
            "lowest": lowest,
            "pass_rate": pass_rate
        })
    
    return report_data


@router.get("/reports/school/behavior")
async def get_school_behavior_report(
    period: str = "current_term",
    current_user: dict = Depends(get_current_user)
):
    """Get behavior report with statistics"""
    school_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id") or current_user.get("school_id")
    if not school_id:
        return {
            "stats": {"positive": 0, "negative": 0, "warning": 0, "appreciation": 0, "total": 0},
            "recent_notes": [],
            "period": period,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    behavior_records = await gd_find(db.session, "behavior", {"school_id": school_id}, order_by="created_at", desc_order=True, limit=1000)
    
    positive_count = len([b for b in behavior_records if b.get("type") == "positive" or b.get("behavior_type") == "positive"])
    negative_count = len([b for b in behavior_records if b.get("type") == "negative" or b.get("behavior_type") == "negative"])
    warning_count = len([b for b in behavior_records if b.get("type") == "warning" or b.get("behavior_type") == "warning"])
    appreciation_count = len([b for b in behavior_records if b.get("type") == "appreciation" or b.get("behavior_type") == "appreciation"])
    
    recent_records = behavior_records[:10]
    student_ids = list({r.get("student_id") for r in recent_records if r.get("student_id")})
    student_map = {}
    if student_ids:
        students = await gd_find(db.session, "students", {"id": {"$in": student_ids}}, limit=len(student_ids))
        student_map = {s["id"]: s.get("name_ar") or s.get("name", "طالب") for s in students}
    
    recent_notes = []
    for record in recent_records:
        student_id = record.get("student_id")
        recent_notes.append({
            "id": record.get("id"),
            "student_name": student_map.get(student_id, "طالب"),
            "student_id": student_id,
            "note": record.get("note") or record.get("description") or record.get("notes", ""),
            "type": record.get("type") or record.get("behavior_type", "positive"),
            "date": record.get("created_at") or record.get("date"),
            "class_id": record.get("class_id")
        })
    
    return {
        "stats": {
            "positive": positive_count,
            "negative": negative_count,
            "warning": warning_count,
            "appreciation": appreciation_count,
            "total": len(behavior_records)
        },
        "recent_notes": recent_notes,
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/reports/school/top-classes")
async def get_top_performing_classes(
    current_user: dict = Depends(get_current_user)
):
    """Get top performing classes based on attendance and behavior"""
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="المستخدم غير مرتبط بمدرسة")
    
    classes = await gd_find(db.session, "classes", {"school_id": school_id}, limit=100)
    
    all_attendance = await gd_find(db.session, "attendance", {"school_id": school_id}, limit=100000)
    
    att_by_class = {}
    for a in all_attendance:
        cid = a.get("class_id")
        if cid not in att_by_class:
            att_by_class[cid] = {"present": 0, "total": 0}
        att_by_class[cid]["total"] += 1
        if a.get("status") == "present":
            att_by_class[cid]["present"] += 1
    
    all_positive_behavior = await gd_find(db.session, "behavior", {
        "school_id": school_id,
        "$or": [
            {"type": "positive"},
            {"behavior_type": "positive"},
            {"type": "appreciation"},
            {"behavior_type": "appreciation"}
        ]
    }, limit=100000)
    
    behavior_by_class = {}
    for b in all_positive_behavior:
        cid = b.get("class_id")
        behavior_by_class[cid] = behavior_by_class.get(cid, 0) + 1
    
    class_performance = []
    for cls in classes:
        class_id = cls.get("id")
        
        att = att_by_class.get(class_id, {"present": 0, "total": 0})
        attendance_rate = round((att["present"] / att["total"]) * 100, 1) if att["total"] > 0 else 0
        
        positive_behavior = behavior_by_class.get(class_id, 0)
        
        behavior_score = min(30, positive_behavior * 3)
        total_score = round(attendance_rate * 0.7 + behavior_score, 1)
        
        class_performance.append({
            "class_id": class_id,
            "class_name": cls.get("name") or cls.get("name_ar"),
            "attendance_rate": attendance_rate,
            "positive_behavior_count": positive_behavior,
            "score": total_score,
            "rank_reason": f"نسبة حضور {attendance_rate}% | {positive_behavior} سلوك إيجابي"
        })
    
    # Sort by score
    class_performance.sort(key=lambda x: x["score"], reverse=True)
    
    return class_performance[:5]  # Return top 5


@router.get("/reports/school/export")
async def export_school_report(
    report_type: str = "overview",
    format: str = "json",
    current_user: dict = Depends(get_current_user)
):
    """Export school report data"""
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="المستخدم غير مرتبط بمدرسة")
    
    # Get data based on report type
    if report_type == "overview":
        # Get counts
        total_students = await gd_count(db.session, "students", {"school_id": school_id})
        total_teachers = await gd_count(db.session, "teachers", {"school_id": school_id})
        total_classes = await gd_count(db.session, "classes", {"school_id": school_id})
        
        # Get attendance
        attendance = await gd_find(db.session, "attendance", {"school_id": school_id}, limit=10000)
        present = len([a for a in attendance if a.get("status") == "present"])
        attendance_rate = round((present / len(attendance)) * 100, 1) if attendance else 0
        
        # Get positive behavior
        positive_behavior = await gd_count(db.session, "behavior", {
            "school_id": school_id,
            "$or": [{"type": "positive"}, {"behavior_type": "positive"}]
        })
        
        data = {
            "report_type": "نظرة عامة",
            "school_id": school_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_students": total_students,
                "total_teachers": total_teachers,
                "total_classes": total_classes,
                "attendance_rate": attendance_rate,
                "positive_behavior_count": positive_behavior
            }
        }
    
    elif report_type == "attendance":
        # Get attendance by class
        classes = await gd_find(db.session, "classes", {"school_id": school_id}, limit=100)
        attendance_data = []
        
        for cls in classes:
            attendance = await gd_find(db.session, "attendance", {"class_id": cls.get("id")}, limit=10000)
            present = len([a for a in attendance if a.get("status") == "present"])
            absent = len([a for a in attendance if a.get("status") == "absent"])
            late = len([a for a in attendance if a.get("status") == "late"])
            total = len(attendance)
            rate = round((present / total) * 100, 1) if total > 0 else 0
            
            attendance_data.append({
                "class": cls.get("name"),
                "present": present,
                "absent": absent,
                "late": late,
                "rate": rate
            })
        
        data = {
            "report_type": "تقرير الحضور",
            "school_id": school_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "attendance": attendance_data
        }
    
    elif report_type == "behavior":
        behavior_records = await gd_find(db.session, "behavior", {"school_id": school_id}, limit=1000)
        
        data = {
            "report_type": "تقرير السلوك",
            "school_id": school_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "positive": len([b for b in behavior_records if b.get("type") == "positive"]),
                "negative": len([b for b in behavior_records if b.get("type") == "negative"]),
                "warning": len([b for b in behavior_records if b.get("type") == "warning"]),
                "appreciation": len([b for b in behavior_records if b.get("type") == "appreciation"])
            },
            "records": behavior_records[:100]
        }
    
    else:
        data = {"error": "نوع التقرير غير صالح"}
    
    return data





# ============== PHASE 6: REPORTING ENGINE APIs ==============

@router.get("/reports/student/{student_id}")
async def report_student(
    student_id: str,
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await reporting_engine.generate_student_report(student_id, school_id)

@router.get("/reports/class/{class_id}")
async def report_class(
    class_id: str,
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await reporting_engine.generate_class_report(class_id, school_id)

@router.get("/reports/attendance")
async def report_attendance(
    start_date: str = Query(...),
    end_date: str = Query(...),
    class_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await reporting_engine.generate_attendance_report(school_id, start_date, end_date, class_id)

@router.get("/reports/teacher/{teacher_id}")
async def report_teacher(
    teacher_id: str,
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    role = current_user.get("role", "")
    if role not in ADMIN_ROLES_SET and current_user.get("teacher_id") != teacher_id:
        raise HTTPException(403, "لا يمكنك عرض تقرير معلم آخر")
    return await reporting_engine.generate_teacher_report(teacher_id, school_id)

@router.get("/reports/school")
async def report_school(
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await reporting_engine.generate_school_report(school_id)





# ============== PHASE 6: UNIFIED REPORT GENERATION ==============

@router.get("/reports/generate/{report_type}")
async def generate_report(
    report_type: str,
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    class_id: Optional[str] = Query(None),
    teacher_id: Optional[str] = Query(None),
    student_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    if report_type not in REPORT_TYPES:
        raise HTTPException(400, f"نوع التقرير غير معروف. الأنواع المتاحة: {', '.join(REPORT_TYPES)}")

    school_id = current_user.get("tenant_id")
    role = current_user.get("role", "")

    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")

    if report_type.startswith("school_"):
        allowed_roles = ADMIN_ROLES_SET | {UserRole.TEACHER.value}
        if role not in allowed_roles:
            raise HTTPException(403, "ليس لديك صلاحية لعرض تقارير المدرسة")

    if report_type.startswith("teacher_"):
        if not teacher_id:
            teacher_id = current_user.get("teacher_id")
        if not teacher_id:
            raise HTTPException(400, "teacher_id مطلوب لتقارير المعلم")
        if role not in ADMIN_ROLES_SET and current_user.get("teacher_id") != teacher_id:
            raise HTTPException(403, "لا يمكنك عرض تقرير معلم آخر")

    if report_type.startswith("student_"):
        if not student_id:
            raise HTTPException(400, "student_id مطلوب لتقارير الطالب")
        stu = await gd_find_one(db.session, "students", {"id": student_id, "school_id": school_id})
        if not stu:
            raise HTTPException(404, "الطالب غير موجود في هذه المدرسة")
        allowed_roles = ADMIN_ROLES_SET | {UserRole.TEACHER.value}
        if role not in allowed_roles and current_user.get("student_id") != student_id:
            raise HTTPException(403, "لا يمكنك عرض تقرير طالب آخر")

    result = await reporting_engine.generate(
        report_type=report_type,
        school_id=school_id,
        start_date=start_date,
        end_date=end_date,
        class_id=class_id,
        teacher_id=teacher_id,
        student_id=student_id,
    )
    return result

@router.get("/reports/types")
async def list_report_types(
    current_user: dict = Depends(get_current_user),
):
    return {
        "report_types": REPORT_TYPES,
        "categories": {
            "school": [t for t in REPORT_TYPES if t.startswith("school_")],
            "teacher": [t for t in REPORT_TYPES if t.startswith("teacher_")],
            "student": [t for t in REPORT_TYPES if t.startswith("student_")],
        },
    }





# ============== PHASE 6: UNIFIED REPORT EXPORT ==============

@router.get("/export/report/{report_type}")
async def export_report_file(
    report_type: str,
    format: str = Query("pdf", pattern="^(pdf|csv|xlsx)$"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    class_id: Optional[str] = Query(None),
    teacher_id: Optional[str] = Query(None),
    student_id: Optional[str] = Query(None),
    school_id: Optional[str] = Query(None, description="School ID (platform admins can specify)"),
    current_user: dict = Depends(get_current_user),
):
    if report_type not in REPORT_TYPES:
        raise HTTPException(400, f"نوع التقرير غير معروف. الأنواع المتاحة: {', '.join(REPORT_TYPES)}")

    role = current_user.get("role", "")
    from auth_scope import independent_workspace_id as _itw_id
    resolved_school_id = current_user.get("tenant_id") or _itw_id(current_user)

    if school_id and role == UserRole.PLATFORM_ADMIN.value:
        resolved_school_id = school_id
    elif not resolved_school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")

    school_id = resolved_school_id

    if report_type.startswith("school_") or report_type in ("class_report", "timetable"):
        allowed_roles = ADMIN_ROLES_SET | {UserRole.TEACHER.value, UserRole.INDEPENDENT_TEACHER.value}
        if role not in allowed_roles:
            raise HTTPException(403, "ليس لديك صلاحية لتصدير تقارير المدرسة")

    if report_type.startswith("teacher_"):
        if not teacher_id:
            teacher_id = current_user.get("teacher_id")
        if not teacher_id:
            raise HTTPException(400, "teacher_id مطلوب لتقارير المعلم")
        if role not in ADMIN_ROLES_SET and current_user.get("teacher_id") != teacher_id:
            raise HTTPException(403, "لا يمكنك تصدير تقرير معلم آخر")

    if report_type.startswith("student_"):
        if not student_id:
            raise HTTPException(400, "student_id مطلوب لتقارير الطالب")
        stu = await gd_find_one(db.session, "students", {"id": student_id, "school_id": school_id})
        if not stu:
            raise HTTPException(404, "الطالب غير موجود في هذه المدرسة")
        allowed_roles = ADMIN_ROLES_SET | {UserRole.TEACHER.value}
        if role not in allowed_roles and current_user.get("student_id") != student_id:
            raise HTTPException(403, "لا يمكنك تصدير تقرير طالب آخر")

    try:
        buf, media_type, filename = await export_engine.export(
            report_type=report_type,
            fmt=format,
            school_id=school_id,
            start_date=start_date,
            end_date=end_date,
            class_id=class_id,
            teacher_id=teacher_id,
            student_id=student_id,
        )
    except ValueError:
        raise HTTPException(400, "خطأ في معاملات التقرير")

    return StreamingResponse(
        buf,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )





# ============== PHASE 6: LEGACY EXPORT APIs ==============

@router.get("/export/students")
async def export_students(
    fmt: str = Query("csv", pattern="^(csv|json)$"),
    class_id: Optional[str] = Query(None),
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_SUB_ADMIN
    ])),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    result = await export_engine.export_students(school_id, class_id, fmt)
    return Response(
        content=result["content"],
        media_type=result["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )

@router.get("/export/attendance")
async def export_attendance(
    start_date: str = Query(...),
    end_date: str = Query(...),
    fmt: str = Query("csv", pattern="^(csv|json)$"),
    class_id: Optional[str] = Query(None),
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_SUB_ADMIN, UserRole.TEACHER
    ])),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    result = await export_engine.export_attendance(school_id, start_date, end_date, class_id, fmt)
    return Response(
        content=result["content"],
        media_type=result["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )

@router.get("/export/grades")
async def export_grades(
    fmt: str = Query("csv", pattern="^(csv|json)$"),
    class_id: Optional[str] = Query(None),
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_SUB_ADMIN, UserRole.TEACHER
    ])),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    result = await export_engine.export_grades(school_id, class_id, fmt)
    return Response(
        content=result["content"],
        media_type=result["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )

@router.post("/export/report")
async def export_report(
    data: dict = Body(...),
    fmt: str = Query("csv", pattern="^(csv|json)$"),
    current_user: dict = Depends(get_current_user),
):
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    result = await export_engine.export_report(data, fmt)
    return Response(
        content=result["content"],
        media_type=result["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )


@router.get("/export/{report_type}")
async def export_report_file_short(
    report_type: str,
    format: str = Query("pdf", pattern="^(pdf|csv|xlsx)$"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    class_id: Optional[str] = Query(None),
    teacher_id: Optional[str] = Query(None),
    student_id: Optional[str] = Query(None),
    school_id: Optional[str] = Query(None, description="School ID (platform admins can specify)"),
    current_user: dict = Depends(get_current_user),
):
    return await export_report_file(
        report_type=report_type, format=format,
        start_date=start_date, end_date=end_date,
        class_id=class_id, teacher_id=teacher_id,
        student_id=student_id, school_id=school_id,
        current_user=current_user,
    )



