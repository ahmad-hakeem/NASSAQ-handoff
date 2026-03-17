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
from bson import ObjectId
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
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="المستخدم غير مرتبط بمدرسة")
    
    # Get student count
    total_students = await db.students.count_documents({"school_id": school_id})
    
    # Get teacher count
    total_teachers = await db.teachers.count_documents({"school_id": school_id})
    
    # Get class count
    total_classes = await db.classes.count_documents({"school_id": school_id})
    
    # Get attendance stats
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    attendance_records = await db.attendance.find({
        "school_id": school_id,
        "date": today
    }, {"_id": 0}).to_list(10000)
    
    present_count = len([a for a in attendance_records if a.get("status") == "present"])
    absent_count = len([a for a in attendance_records if a.get("status") == "absent"])
    late_count = len([a for a in attendance_records if a.get("status") == "late"])
    total_attendance = len(attendance_records)
    
    attendance_rate = round((present_count / total_attendance) * 100, 1) if total_attendance > 0 else 0
    
    # Get grade stats
    grades = await db.grades.find({"school_id": school_id}, {"_id": 0, "grade": 1}).to_list(10000)
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
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="المستخدم غير مرتبط بمدرسة")
    
    # Get all classes
    class_query = {"school_id": school_id}
    if class_id:
        class_query["id"] = class_id
    
    classes = await db.classes.find(class_query, {"_id": 0}).to_list(100)
    
    report_data = []
    for cls in classes:
        # Get attendance for this class
        attendance = await db.attendance.find({
            "class_id": cls.get("id"),
            "school_id": school_id
        }, {"_id": 0}).to_list(10000)
        
        present = len([a for a in attendance if a.get("status") == "present"])
        absent = len([a for a in attendance if a.get("status") == "absent"])
        late = len([a for a in attendance if a.get("status") == "late"])
        total = len(attendance)
        
        rate = round((present / total) * 100, 1) if total > 0 else 0
        
        report_data.append({
            "class": cls.get("name_ar") or cls.get("name"),
            "class_en": cls.get("name_en") or cls.get("name_ar") or cls.get("name"),
            "present": present,
            "absent": absent,
            "late": late,
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
    
    # Get all subjects
    subject_query = {"school_id": school_id}
    if subject_id:
        subject_query["id"] = subject_id
    
    subjects = await db.subjects.find(subject_query, {"_id": 0}).to_list(100)
    
    report_data = []
    for subject in subjects:
        # Get grades for this subject
        grades = await db.grades.find({
            "subject_id": subject.get("id"),
            "school_id": school_id
        }, {"_id": 0, "grade": 1}).to_list(10000)
        
        if grades:
            grade_values = [g.get("grade", 0) for g in grades]
            avg = round(sum(grade_values) / len(grade_values), 1)
            highest = max(grade_values)
            lowest = min(grade_values)
            passed = len([g for g in grade_values if g >= 50])
            pass_rate = round((passed / len(grades)) * 100, 0)
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
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="المستخدم غير مرتبط بمدرسة")
    
    # Get all behavior records for the school
    behavior_records = await db.behavior.find(
        {"school_id": school_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(1000)
    
    # Count by type
    positive_count = len([b for b in behavior_records if b.get("type") == "positive" or b.get("behavior_type") == "positive"])
    negative_count = len([b for b in behavior_records if b.get("type") == "negative" or b.get("behavior_type") == "negative"])
    warning_count = len([b for b in behavior_records if b.get("type") == "warning" or b.get("behavior_type") == "warning"])
    appreciation_count = len([b for b in behavior_records if b.get("type") == "appreciation" or b.get("behavior_type") == "appreciation"])
    
    # Get recent behavior notes (last 10)
    recent_notes = []
    for record in behavior_records[:10]:
        student_id = record.get("student_id")
        student = await db.students.find_one({"id": student_id}, {"_id": 0, "name": 1, "name_ar": 1})
        student_name = student.get("name_ar") or student.get("name") if student else "طالب"
        
        recent_notes.append({
            "id": record.get("id"),
            "student_name": student_name,
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
    
    # Get all classes
    classes = await db.classes.find({"school_id": school_id}, {"_id": 0}).to_list(100)
    
    class_performance = []
    for cls in classes:
        class_id = cls.get("id")
        
        # Get attendance rate
        attendance = await db.attendance.find({"class_id": class_id}, {"_id": 0}).to_list(10000)
        present_count = len([a for a in attendance if a.get("status") == "present"])
        total_attendance = len(attendance)
        attendance_rate = round((present_count / total_attendance) * 100, 1) if total_attendance > 0 else 0
        
        # Get positive behavior count
        positive_behavior = await db.behavior.count_documents({
            "class_id": class_id,
            "$or": [
                {"type": "positive"},
                {"behavior_type": "positive"},
                {"type": "appreciation"},
                {"behavior_type": "appreciation"}
            ]
        })
        
        # Calculate score (70% attendance, 30% behavior)
        behavior_score = min(30, positive_behavior * 3)  # Cap at 30
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
        total_students = await db.students.count_documents({"school_id": school_id})
        total_teachers = await db.teachers.count_documents({"school_id": school_id})
        total_classes = await db.classes.count_documents({"school_id": school_id})
        
        # Get attendance
        attendance = await db.attendance.find({"school_id": school_id}, {"_id": 0}).to_list(10000)
        present = len([a for a in attendance if a.get("status") == "present"])
        attendance_rate = round((present / len(attendance)) * 100, 1) if attendance else 0
        
        # Get positive behavior
        positive_behavior = await db.behavior.count_documents({
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
        classes = await db.classes.find({"school_id": school_id}, {"_id": 0}).to_list(100)
        attendance_data = []
        
        for cls in classes:
            attendance = await db.attendance.find({"class_id": cls.get("id")}, {"_id": 0}).to_list(10000)
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
        behavior_records = await db.behavior.find({"school_id": school_id}, {"_id": 0}).to_list(1000)
        
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
        stu = await db.students.find_one({"id": student_id, "school_id": school_id})
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
    resolved_school_id = current_user.get("tenant_id")

    if school_id and role == UserRole.PLATFORM_ADMIN.value:
        resolved_school_id = school_id
    elif not resolved_school_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")

    school_id = resolved_school_id

    if report_type.startswith("school_") or report_type in ("class_report", "timetable"):
        allowed_roles = ADMIN_ROLES_SET | {UserRole.TEACHER.value}
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
        stu = await db.students.find_one({"id": student_id, "school_id": school_id})
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



