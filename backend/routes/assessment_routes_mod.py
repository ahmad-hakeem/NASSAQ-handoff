"""
NASSAQ Route Module: Assessment engine endpoints
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
from enum import Enum

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

from routes.notification_routes_mod import create_notification_internal
from engines.assessment_engine import AssessmentEngine

router = APIRouter()

_assessment_engine = AssessmentEngine(db)



# ============== ASSESSMENT ENGINE ==============
# Data Models

class AssessmentType(str, Enum):
    QUIZ = "quiz"
    ASSIGNMENT = "assignment"
    EXAM = "exam"
    PARTICIPATION = "participation"
    PROJECT = "project"
    MIDTERM = "midterm"
    FINAL = "final"
    ORAL = "oral"
    PRACTICAL = "practical"

class AssessmentCreate(BaseModel):
    class_id: str
    subject_id: str
    title: str
    title_en: Optional[str] = None
    assessment_type: AssessmentType
    max_score: float = 100.0
    weight: float = 1.0  # Weight for GPA calculation (0.0 - 1.0)
    date: str  # YYYY-MM-DD
    description: Optional[str] = None
    is_published: bool = False

class AssessmentUpdate(BaseModel):
    title: Optional[str] = None
    title_en: Optional[str] = None
    max_score: Optional[float] = None
    weight: Optional[float] = None
    date: Optional[str] = None
    description: Optional[str] = None
    is_published: Optional[bool] = None

class AssessmentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    class_id: Optional[str] = None
    class_name: Optional[str] = None
    subject_id: Optional[str] = None
    subject_name: Optional[str] = None
    teacher_id: Optional[str] = None
    teacher_name: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    title_en: Optional[str] = None
    type: Optional[str] = None
    assessment_type: Optional[str] = None
    max_score: Optional[float] = 100
    weight: Optional[float] = 100
    date: Optional[str] = None
    description: Optional[str] = None
    term_id: Optional[str] = None
    status: Optional[str] = "graded"
    is_published: Optional[bool] = True
    school_id: Optional[str] = None
    created_at: Optional[str] = None
    grades_count: Optional[int] = 0

class GradeCreate(BaseModel):
    student_id: str
    score: float
    notes: Optional[str] = None

class GradeUpdate(BaseModel):
    score: Optional[float] = None
    notes: Optional[str] = None

class GradeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    assessment_id: str
    student_id: str
    student_name: Optional[str] = None
    student_code: Optional[str] = None
    score: float
    max_score: float
    percentage: float
    notes: Optional[str] = None
    recorded_by: str
    recorded_at: str

class BulkGradeEntry(BaseModel):
    assessment_id: str
    grades: List[GradeCreate]

class StudentGradeHistoryResponse(BaseModel):
    student_id: str
    student_name: str
    class_id: str
    class_name: str
    total_assessments: int
    average_percentage: float
    grades_by_subject: dict
    grades_by_type: dict
    recent_grades: List[dict]

class ClassGradeOverviewResponse(BaseModel):
    class_id: str
    class_name: str
    subject_id: Optional[str]
    subject_name: Optional[str]
    total_students: int
    total_assessments: int
    class_average: float
    highest_score: float
    lowest_score: float
    grade_distribution: dict
    recent_assessments: List[dict]

# Assessment APIs

@router.post("/assessments", response_model=AssessmentResponse)
async def create_assessment(
    assessment: AssessmentCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new assessment"""
    if current_user['role'] not in ['teacher', 'school_principal', 'school_sub_admin']:
        raise HTTPException(status_code=403, detail="Not authorized to create assessments")
    
    # Verify class exists
    class_info = await db.classes.find_one({"id": assessment.class_id}, {"_id": 0})
    if not class_info:
        raise HTTPException(status_code=404, detail="Class not found")
    
    # Verify subject exists
    subject = await db.subjects.find_one({"id": assessment.subject_id}, {"_id": 0})
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    assessment_id = str(uuid.uuid4())
    assessment_doc = {
        "id": assessment_id,
        "class_id": assessment.class_id,
        "subject_id": assessment.subject_id,
        "teacher_id": current_user['id'],
        "title": assessment.title,
        "title_en": assessment.title_en,
        "assessment_type": assessment.assessment_type.value,
        "max_score": assessment.max_score,
        "weight": assessment.weight,
        "date": assessment.date,
        "description": assessment.description,
        "is_published": assessment.is_published,
        "school_id": current_user.get('tenant_id') or class_info.get('school_id'),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.assessments.insert_one(assessment_doc)
    
    # Get teacher name
    teacher = await db.users.find_one({"id": current_user['id']}, {"_id": 0, "full_name": 1})
    
    return AssessmentResponse(
        id=assessment_id,
        class_id=assessment.class_id,
        class_name=class_info.get('name'),
        subject_id=assessment.subject_id,
        subject_name=subject.get('name'),
        teacher_id=current_user['id'],
        teacher_name=teacher.get('full_name') if teacher else None,
        title=assessment.title,
        title_en=assessment.title_en,
        assessment_type=assessment.assessment_type.value,
        max_score=assessment.max_score,
        weight=assessment.weight,
        date=assessment.date,
        description=assessment.description,
        is_published=assessment.is_published,
        created_at=assessment_doc['created_at'],
        grades_count=0
    )

@router.get("/assessments", response_model=List[AssessmentResponse])
async def get_assessments(
    class_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    assessment_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all assessments with optional filters"""
    query = {}
    
    # Filter by school for school-level users
    if current_user['role'] in ['school_principal', 'school_sub_admin', 'teacher']:
        if current_user.get('tenant_id'):
            query['school_id'] = current_user['tenant_id']
    
    if class_id:
        query['class_id'] = class_id
    if subject_id:
        query['subject_id'] = subject_id
    if assessment_type:
        query['assessment_type'] = assessment_type
    
    assessments = await db.assessments.find(query, {"_id": 0}).sort("date", -1).to_list(500)
    
    # Enrich with related data
    result = []
    for a in assessments:
        # Get class info
        class_id = a.get('class_id')
        class_info = await db.classes.find_one({"id": class_id}, {"_id": 0, "name": 1}) if class_id else None
        # Get subject info
        subject_id = a.get('subject_id')
        subject = await db.subjects.find_one({"id": subject_id}, {"_id": 0, "name": 1}) if subject_id else None
        # Get teacher info (teacher_id might not exist in demo data)
        teacher_id = a.get('teacher_id')
        teacher = await db.users.find_one({"id": teacher_id}, {"_id": 0, "full_name": 1}) if teacher_id else None
        # Count grades
        grades_count = await db.grades.count_documents({"assessment_id": a['id']})
        
        result.append(AssessmentResponse(
            id=a['id'],
            class_id=class_id,
            class_name=a.get('class_name') or (class_info.get('name') if class_info else None),
            subject_id=subject_id,
            subject_name=a.get('subject_name') or (subject.get('name') if subject else None),
            teacher_id=teacher_id,
            teacher_name=teacher.get('full_name') if teacher else None,
            name=a.get('name'),
            title=a.get('title') or a.get('name'),
            title_en=a.get('title_en') or a.get('name_en'),
            type=a.get('type'),
            assessment_type=a.get('assessment_type') or a.get('type'),
            max_score=a.get('max_score', 100),
            weight=a.get('weight', 1.0),
            date=a.get('date'),
            description=a.get('description'),
            term_id=a.get('term_id'),
            status=a.get('status', 'graded'),
            is_published=a.get('is_published', True),
            school_id=a.get('school_id'),
            created_at=a.get('created_at'),
            grades_count=grades_count
        ))
    
    return result

@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a single assessment by ID"""
    assessment = await db.assessments.find_one({"id": assessment_id}, {"_id": 0})
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Get related data
    class_info = await db.classes.find_one({"id": assessment['class_id']}, {"_id": 0, "name": 1})
    subject = await db.subjects.find_one({"id": assessment['subject_id']}, {"_id": 0, "name": 1})
    teacher = await db.users.find_one({"id": assessment['teacher_id']}, {"_id": 0, "full_name": 1})
    grades_count = await db.grades.count_documents({"assessment_id": assessment_id})
    
    return AssessmentResponse(
        id=assessment['id'],
        class_id=assessment['class_id'],
        class_name=class_info.get('name') if class_info else None,
        subject_id=assessment['subject_id'],
        subject_name=subject.get('name') if subject else None,
        teacher_id=assessment['teacher_id'],
        teacher_name=teacher.get('full_name') if teacher else None,
        title=assessment['title'],
        title_en=assessment.get('title_en'),
        assessment_type=assessment['assessment_type'],
        max_score=assessment['max_score'],
        weight=assessment.get('weight', 1.0),
        date=assessment['date'],
        description=assessment.get('description'),
        is_published=assessment.get('is_published', False),
        created_at=assessment['created_at'],
        grades_count=grades_count
    )

@router.put("/assessments/{assessment_id}", response_model=AssessmentResponse)
async def update_assessment(
    assessment_id: str,
    update: AssessmentUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update an assessment"""
    assessment = await db.assessments.find_one({"id": assessment_id}, {"_id": 0})
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Only owner or admin can update
    if current_user['role'] not in ['school_principal', 'school_sub_admin'] and assessment['teacher_id'] != current_user['id']:
        raise HTTPException(status_code=403, detail="Not authorized to update this assessment")
    
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
    
    await db.assessments.update_one({"id": assessment_id}, {"$set": update_data})
    
    return await get_assessment(assessment_id, current_user)

@router.delete("/assessments/{assessment_id}")
async def delete_assessment(
    assessment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete an assessment and its grades"""
    assessment = await db.assessments.find_one({"id": assessment_id}, {"_id": 0})
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Only owner or admin can delete
    if current_user['role'] not in ['school_principal', 'school_sub_admin'] and assessment['teacher_id'] != current_user['id']:
        raise HTTPException(status_code=403, detail="Not authorized to delete this assessment")
    
    # Delete all grades for this assessment
    await db.grades.delete_many({"assessment_id": assessment_id})
    # Delete the assessment
    await db.assessments.delete_one({"id": assessment_id})
    
    return {"message": "Assessment deleted successfully"}

# Grade APIs

@router.post("/grades/bulk")
async def create_bulk_grades(
    data: BulkGradeEntry,
    current_user: dict = Depends(get_current_user)
):
    """Create or update multiple grades at once for an assessment"""
    if current_user['role'] not in ['teacher', 'school_principal', 'school_sub_admin']:
        raise HTTPException(status_code=403, detail="Not authorized to enter grades")
    
    assessment = await db.assessments.find_one({"id": data.assessment_id}, {"_id": 0})
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    created = 0
    updated = 0
    errors = []
    
    for grade in data.grades:
        try:
            # Check if student exists
            student = await db.students.find_one({"id": grade.student_id}, {"_id": 0})
            if not student:
                errors.append(f"Student {grade.student_id} not found")
                continue
            
            # Validate score
            if grade.score < 0 or grade.score > assessment['max_score']:
                errors.append(f"Invalid score {grade.score} for student {grade.student_id}")
                continue
            
            # Check if grade already exists
            existing = await db.grades.find_one({
                "assessment_id": data.assessment_id,
                "student_id": grade.student_id
            })
            
            if existing:
                # Update existing grade
                await db.grades.update_one(
                    {"id": existing['id']},
                    {"$set": {
                        "score": grade.score,
                        "notes": grade.notes,
                        "recorded_by": current_user['id'],
                        "recorded_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                updated += 1
            else:
                # Create new grade
                grade_id = str(uuid.uuid4())
                grade_doc = {
                    "id": grade_id,
                    "assessment_id": data.assessment_id,
                    "student_id": grade.student_id,
                    "class_id": assessment['class_id'],
                    "subject_id": assessment['subject_id'],
                    "score": grade.score,
                    "max_score": assessment['max_score'],
                    "percentage": round((grade.score / assessment['max_score']) * 100, 2),
                    "notes": grade.notes,
                    "recorded_by": current_user['id'],
                    "recorded_at": datetime.now(timezone.utc).isoformat()
                }
                await db.grades.insert_one(grade_doc)
                created += 1
                
                # Create assessment event for notifications/analytics
                await db.events.insert_one({
                    "id": str(uuid.uuid4()),
                    "type": "grade_recorded",
                    "student_id": grade.student_id,
                    "assessment_id": data.assessment_id,
                    "score": grade.score,
                    "max_score": assessment['max_score'],
                    "recorded_by": current_user['id'],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
                # Create notification for new grade
                student_info = await db.students.find_one({"id": grade.student_id}, {"_id": 0})
                if student_info:
                    student_name = student_info.get('full_name', 'طالب')
                    percentage = round((grade.score / assessment['max_score']) * 100, 1)
                    assessment_title = assessment.get('title', 'تقييم')
                    
                    # Notify the student if they have a user account
                    if student_info.get('user_id'):
                        await create_notification_internal(
                            title=f"درجة جديدة: {assessment_title}",
                            title_en=f"New Grade: {assessment_title}",
                            message=f"حصلت على درجة {grade.score}/{assessment['max_score']} ({percentage}%) في {assessment_title}",
                            message_en=f"You scored {grade.score}/{assessment['max_score']} ({percentage}%) in {assessment_title}",
                            recipient_id=student_info['user_id'],
                            notification_type="assessment",
                            priority="medium",
                            sender_id=current_user['id'],
                            related_entity="assessment",
                            related_entity_id=data.assessment_id,
                            action_url="/student/grades",
                            school_id=current_user.get('tenant_id')
                        )
                    
                    # Notify parent if exists
                    if student_info.get('parent_phone'):
                        parent_user = await db.users.find_one({
                            "phone": student_info.get('parent_phone'),
                            "role": "parent"
                        }, {"_id": 0})
                        if parent_user:
                            await create_notification_internal(
                                title=f"درجة جديدة لـ {student_name}",
                                title_en=f"New Grade for {student_name}",
                                message=f"حصل {student_name} على درجة {grade.score}/{assessment['max_score']} ({percentage}%) في {assessment_title}",
                                message_en=f"{student_name} scored {grade.score}/{assessment['max_score']} ({percentage}%) in {assessment_title}",
                                recipient_id=parent_user['id'],
                                notification_type="assessment",
                                priority="medium",
                                sender_id=current_user['id'],
                                related_entity="assessment",
                                related_entity_id=data.assessment_id,
                                action_url="/parent/grades",
                                school_id=current_user.get('tenant_id')
                            )
        except Exception as e:
            errors.append(f"Error processing grade for student {grade.student_id}: {str(e)}")
    
    return {
        "success": True,
        "created": created,
        "updated": updated,
        "errors": errors,
        "total_processed": created + updated
    }

@router.get("/grades/assessment/{assessment_id}", response_model=List[GradeResponse])
async def get_grades_for_assessment(
    assessment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all grades for a specific assessment"""
    assessment = await db.assessments.find_one({"id": assessment_id}, {"_id": 0})
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    grades = await db.grades.find({"assessment_id": assessment_id}, {"_id": 0}).to_list(500)
    
    result = []
    for g in grades:
        student = await db.students.find_one({"id": g['student_id']}, {"_id": 0, "full_name": 1, "student_code": 1})
        result.append(GradeResponse(
            id=g['id'],
            assessment_id=g['assessment_id'],
            student_id=g['student_id'],
            student_name=student.get('full_name') if student else None,
            student_code=student.get('student_code') if student else None,
            score=g['score'],
            max_score=g['max_score'],
            percentage=g.get('percentage', round((g['score'] / g['max_score']) * 100, 2)),
            notes=g.get('notes'),
            recorded_by=g['recorded_by'],
            recorded_at=g['recorded_at']
        ))
    
    return result

@router.get("/grades/student/{student_id}")
async def get_student_grade_history(
    student_id: str,
    subject_id: Optional[str] = None,
    assessment_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get complete grade history for a student"""
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Get class info
    class_info = await db.classes.find_one({"id": student.get('class_id')}, {"_id": 0, "name": 1})
    
    query = {"student_id": student_id}
    if subject_id:
        query['subject_id'] = subject_id
    
    grades = await db.grades.find(query, {"_id": 0}).sort("recorded_at", -1).to_list(500)
    
    # Calculate statistics
    grades_by_subject = {}
    grades_by_type = {}
    total_percentage = 0
    
    for g in grades:
        # Get assessment details
        assessment = await db.assessments.find_one({"id": g['assessment_id']}, {"_id": 0})
        if not assessment:
            continue
        
        if assessment_type and assessment['assessment_type'] != assessment_type:
            continue
        
        # Get subject name
        subject = await db.subjects.find_one({"id": g['subject_id']}, {"_id": 0, "name": 1})
        subject_name = subject.get('name') if subject else "Unknown"
        
        # Aggregate by subject
        if subject_name not in grades_by_subject:
            grades_by_subject[subject_name] = {
                "subject_id": g['subject_id'],
                "grades": [],
                "average": 0
            }
        grades_by_subject[subject_name]['grades'].append({
            "assessment_id": g['assessment_id'],
            "title": assessment['title'],
            "type": assessment['assessment_type'],
            "score": g['score'],
            "max_score": g['max_score'],
            "percentage": g.get('percentage', 0),
            "date": assessment['date']
        })
        
        # Aggregate by type
        assessment_type_key = assessment['assessment_type']
        if assessment_type_key not in grades_by_type:
            grades_by_type[assessment_type_key] = {
                "count": 0,
                "total_percentage": 0,
                "average": 0
            }
        grades_by_type[assessment_type_key]['count'] += 1
        grades_by_type[assessment_type_key]['total_percentage'] += g.get('percentage', 0)
        
        total_percentage += g.get('percentage', 0)
    
    # Calculate averages
    for subj in grades_by_subject.values():
        if subj['grades']:
            subj['average'] = round(sum(g['percentage'] for g in subj['grades']) / len(subj['grades']), 2)
    
    for type_data in grades_by_type.values():
        if type_data['count'] > 0:
            type_data['average'] = round(type_data['total_percentage'] / type_data['count'], 2)
    
    average_percentage = round(total_percentage / len(grades), 2) if grades else 0
    
    # Get recent grades (last 10)
    recent_grades = []
    for g in grades[:10]:
        assessment = await db.assessments.find_one({"id": g['assessment_id']}, {"_id": 0})
        subject = await db.subjects.find_one({"id": g['subject_id']}, {"_id": 0, "name": 1})
        if assessment:
            recent_grades.append({
                "assessment_id": g['assessment_id'],
                "title": assessment['title'],
                "type": assessment['assessment_type'],
                "subject_name": subject.get('name') if subject else None,
                "score": g['score'],
                "max_score": g['max_score'],
                "percentage": g.get('percentage', 0),
                "date": assessment['date'],
                "recorded_at": g['recorded_at']
            })
    
    return {
        "student_id": student_id,
        "student_name": student.get('full_name'),
        "class_id": student.get('class_id'),
        "class_name": class_info.get('name') if class_info else None,
        "total_assessments": len(grades),
        "average_percentage": average_percentage,
        "grades_by_subject": grades_by_subject,
        "grades_by_type": grades_by_type,
        "recent_grades": recent_grades
    }

@router.get("/grades/class/{class_id}/overview")
async def get_class_grade_overview(
    class_id: str,
    subject_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get grade overview for a class"""
    class_info = await db.classes.find_one({"id": class_id}, {"_id": 0})
    if not class_info:
        raise HTTPException(status_code=404, detail="Class not found")
    
    # Get all students in class
    students = await db.students.find({"class_id": class_id}, {"_id": 0, "id": 1}).to_list(100)
    student_ids = [s['id'] for s in students]
    
    # Get grades query
    query = {"student_id": {"$in": student_ids}}
    if subject_id:
        query['subject_id'] = subject_id
    
    grades = await db.grades.find(query, {"_id": 0}).to_list(1000)
    
    # Get subject info
    subject_name = None
    if subject_id:
        subject = await db.subjects.find_one({"id": subject_id}, {"_id": 0, "name": 1})
        subject_name = subject.get('name') if subject else None
    
    # Calculate statistics
    if not grades:
        return {
            "class_id": class_id,
            "class_name": class_info.get('name'),
            "subject_id": subject_id,
            "subject_name": subject_name,
            "total_students": len(students),
            "total_assessments": 0,
            "class_average": 0,
            "highest_score": 0,
            "lowest_score": 0,
            "grade_distribution": {},
            "recent_assessments": []
        }
    
    percentages = [g.get('percentage', 0) for g in grades]
    class_average = round(sum(percentages) / len(percentages), 2)
    highest_score = max(percentages)
    lowest_score = min(percentages)
    
    # Grade distribution
    grade_distribution = {
        "excellent": len([p for p in percentages if p >= 90]),  # A
        "very_good": len([p for p in percentages if 80 <= p < 90]),  # B
        "good": len([p for p in percentages if 70 <= p < 80]),  # C
        "pass": len([p for p in percentages if 60 <= p < 70]),  # D
        "fail": len([p for p in percentages if p < 60])  # F
    }
    
    # Get unique assessments count
    assessment_ids = list(set(g['assessment_id'] for g in grades))
    
    # Get recent assessments
    recent_assessments = []
    assessments_query = {"class_id": class_id}
    if subject_id:
        assessments_query['subject_id'] = subject_id
    
    recent_assessment_docs = await db.assessments.find(
        assessments_query, 
        {"_id": 0}
    ).sort("date", -1).limit(5).to_list(5)
    
    for a in recent_assessment_docs:
        # Get grades for this assessment
        assessment_grades = [g for g in grades if g['assessment_id'] == a['id']]
        assessment_percentages = [g.get('percentage', 0) for g in assessment_grades]
        
        recent_assessments.append({
            "id": a['id'],
            "title": a['title'],
            "type": a['assessment_type'],
            "date": a['date'],
            "max_score": a['max_score'],
            "students_graded": len(assessment_grades),
            "average": round(sum(assessment_percentages) / len(assessment_percentages), 2) if assessment_percentages else 0
        })
    
    return {
        "class_id": class_id,
        "class_name": class_info.get('name'),
        "subject_id": subject_id,
        "subject_name": subject_name,
        "total_students": len(students),
        "total_assessments": len(assessment_ids),
        "class_average": class_average,
        "highest_score": highest_score,
        "lowest_score": lowest_score,
        "grade_distribution": grade_distribution,
        "recent_assessments": recent_assessments
    }

@router.get("/assessments/students-for-grading/{assessment_id}")
async def get_students_for_grading(
    assessment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get students with their grades for a specific assessment"""
    assessment = await db.assessments.find_one({"id": assessment_id}, {"_id": 0})
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Get class info
    class_info = await db.classes.find_one({"id": assessment['class_id']}, {"_id": 0})
    
    # Get subject info
    subject = await db.subjects.find_one({"id": assessment['subject_id']}, {"_id": 0, "name": 1})
    
    # Get all students in this class
    students = await db.students.find({"class_id": assessment['class_id']}, {"_id": 0}).to_list(100)
    
    # Get existing grades for this assessment
    existing_grades = await db.grades.find(
        {"assessment_id": assessment_id},
        {"_id": 0}
    ).to_list(100)
    
    # Create a map of student_id -> grade
    grades_map = {g['student_id']: g for g in existing_grades}
    
    # Build result with grade data
    result = []
    for student in students:
        student_id = student['id']
        grade_record = grades_map.get(student_id)
        
        result.append({
            "id": student_id,
            "student_code": student.get('student_code'),
            "full_name": student.get('full_name'),
            "full_name_en": student.get('full_name_en'),
            "avatar_url": student.get('avatar_url'),
            "gender": student.get('gender'),
            "score": grade_record.get('score') if grade_record else None,
            "notes": grade_record.get('notes') if grade_record else None,
            "grade_id": grade_record.get('id') if grade_record else None,
            "percentage": grade_record.get('percentage') if grade_record else None
        })
    
    graded_count = len([s for s in result if s['score'] is not None])
    
    return {
        "assessment_id": assessment_id,
        "assessment_title": assessment['title'],
        "assessment_type": assessment['assessment_type'],
        "max_score": assessment['max_score'],
        "date": assessment['date'],
        "class_id": assessment['class_id'],
        "class_name": class_info.get('name') if class_info else None,
        "subject_id": assessment['subject_id'],
        "subject_name": subject.get('name') if subject else None,
        "total_students": len(students),
        "graded_count": graded_count,
        "students": result
    }


# ============== GRADE WEIGHTS ENDPOINTS ==============

class GradeWeightInput(BaseModel):
    subject_id: str
    weights: Dict[str, float]
    academic_year: Optional[str] = None
    semester: Optional[int] = None

@router.post("/grade-weights")
async def set_grade_weights(
    data: GradeWeightInput,
    current_user: dict = Depends(get_current_user)
):
    """Set or update grade weights for a subject"""
    role = current_user.get("role", "")
    allowed = {UserRole.PLATFORM_ADMIN.value, UserRole.SCHOOL_ADMIN.value, UserRole.SCHOOL_PRINCIPAL.value, UserRole.TEACHER.value}
    if role not in allowed:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية لتعديل أوزان الدرجات")

    school_id = current_user.get("tenant_id")
    total = sum(data.weights.values())
    if abs(total - 100) > 0.01:
        raise HTTPException(status_code=400, detail=f"مجموع الأوزان يجب أن يساوي 100 (الحالي: {total})")

    existing = await db.grade_weights.find_one({
        "school_id": school_id,
        "subject_id": data.subject_id,
        "academic_year": data.academic_year,
        "semester": data.semester
    })

    now = datetime.now(timezone.utc).isoformat()
    if existing:
        await db.grade_weights.update_one(
            {"id": existing["id"]},
            {"$set": {"weights": data.weights, "updated_at": now, "updated_by": current_user["id"]}}
        )
        existing["weights"] = data.weights
        existing.pop("_id", None)
        return existing

    weight_id = str(uuid.uuid4())
    doc = {
        "id": weight_id,
        "school_id": school_id,
        "subject_id": data.subject_id,
        "weights": data.weights,
        "academic_year": data.academic_year,
        "semester": data.semester,
        "created_at": now,
        "created_by": current_user["id"]
    }
    await db.grade_weights.insert_one(doc)
    doc.pop("_id", None)
    return doc

@router.get("/grade-weights/{subject_id}")
async def get_grade_weights(
    subject_id: str,
    academic_year: Optional[str] = None,
    semester: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get grade weights for a subject"""
    school_id = current_user.get("tenant_id")
    query = {"school_id": school_id, "subject_id": subject_id}
    if academic_year:
        query["academic_year"] = academic_year
    if semester is not None:
        query["semester"] = semester

    weights = await db.grade_weights.find_one(query, {"_id": 0})
    if weights:
        return weights
    return {
        "subject_id": subject_id,
        "weights": {"quiz": 10, "assignment": 10, "midterm": 30, "final": 40, "participation": 10},
        "is_default": True
    }


# ============== STUDENT AVERAGE ENDPOINT ==============

@router.get("/grades/student/{student_id}/average/{subject_id}")
async def get_student_subject_average(
    student_id: str,
    subject_id: str,
    academic_year: Optional[str] = None,
    semester: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """Calculate weighted average for a student in a subject"""
    school_id = current_user.get("tenant_id")

    weight_doc = await db.grade_weights.find_one(
        {"school_id": school_id, "subject_id": subject_id},
        {"_id": 0}
    )
    weights = weight_doc.get("weights") if weight_doc else {
        "quiz": 10, "assignment": 10, "midterm": 30, "final": 40, "participation": 10
    }

    grade_query = {"student_id": student_id, "subject_id": subject_id}
    if school_id:
        grade_query["school_id"] = school_id
    grades = await db.grades.find(grade_query, {"_id": 0}).to_list(200)

    type_grades = {}
    for g in grades:
        assessment = await db.assessments.find_one({"id": g.get("assessment_id")}, {"_id": 0, "assessment_type": 1})
        if assessment:
            atype = assessment.get("assessment_type", "other")
            if atype not in type_grades:
                type_grades[atype] = []
            type_grades[atype].append(g.get("percentage", 0))

    weighted_sum = 0
    total_weight = 0
    breakdown = {}
    for atype, weight in weights.items():
        if atype in type_grades and type_grades[atype]:
            avg = sum(type_grades[atype]) / len(type_grades[atype])
            weighted_sum += avg * (weight / 100)
            total_weight += weight
            breakdown[atype] = {"average": round(avg, 1), "weight": weight, "count": len(type_grades[atype])}

    final_avg = round(weighted_sum * (100 / total_weight), 1) if total_weight > 0 else 0

    def get_letter(pct):
        if pct >= 95: return "A+"
        if pct >= 90: return "A"
        if pct >= 85: return "B+"
        if pct >= 80: return "B"
        if pct >= 75: return "C+"
        if pct >= 70: return "C"
        if pct >= 65: return "D+"
        if pct >= 60: return "D"
        return "F"

    return {
        "student_id": student_id,
        "subject_id": subject_id,
        "weighted_average": final_avg,
        "letter_grade": get_letter(final_avg),
        "breakdown": breakdown,
        "total_grades": len(grades)
    }


# ============== REPORT CARD ENDPOINT ==============

@router.get("/report-card/{student_id}")
async def generate_report_card(
    student_id: str,
    academic_year: Optional[str] = None,
    semester: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
):
    """Generate a report card for a student"""
    school_id = current_user.get("tenant_id")

    student_query = {"id": student_id}
    if school_id:
        student_query["tenant_id"] = school_id
    student = await db.students.find_one(student_query, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    class_query = {"id": student.get("class_id")}
    if school_id:
        class_query["tenant_id"] = school_id
    class_info = await db.classes.find_one(class_query, {"_id": 0})

    grade_query = {"student_id": student_id}
    if school_id:
        grade_query["school_id"] = school_id
    all_grades = await db.grades.find(grade_query, {"_id": 0}).to_list(500)

    subject_ids = set()
    for g in all_grades:
        if g.get("subject_id"):
            subject_ids.add(g["subject_id"])

    subjects_results = []
    total_avg = 0
    for sid in subject_ids:
        subject = await db.subjects.find_one({"id": sid}, {"_id": 0, "name": 1, "name_en": 1})
        sub_grades = [g for g in all_grades if g.get("subject_id") == sid]
        if sub_grades:
            avg = sum(g.get("percentage", 0) for g in sub_grades) / len(sub_grades)
            total_avg += avg

            def get_letter(pct):
                if pct >= 95: return "A+"
                if pct >= 90: return "A"
                if pct >= 85: return "B+"
                if pct >= 80: return "B"
                if pct >= 75: return "C+"
                if pct >= 70: return "C"
                if pct >= 65: return "D+"
                if pct >= 60: return "D"
                return "F"

            subjects_results.append({
                "subject_id": sid,
                "subject_name": subject.get("name") if subject else sid,
                "subject_name_en": subject.get("name_en") if subject else sid,
                "average": round(avg, 1),
                "letter_grade": get_letter(avg),
                "total_assessments": len(sub_grades),
                "highest": max(g.get("percentage", 0) for g in sub_grades),
                "lowest": min(g.get("percentage", 0) for g in sub_grades)
            })

    gpa = round(total_avg / len(subject_ids), 1) if subject_ids else 0

    att_base = {"student_id": student_id}
    if school_id:
        att_base["tenant_id"] = school_id
    att_total = await db.attendance.count_documents(att_base)
    att_present = await db.attendance.count_documents({**att_base, "status": "present"})
    att_absent = await db.attendance.count_documents({**att_base, "status": "absent"})
    att_late = await db.attendance.count_documents({**att_base, "status": "late"})

    behaviour_records = await db.behaviour_records.find(
        {"student_id": student_id, "tenant_id": school_id},
        {"_id": 0, "category": 1, "points": 1}
    ).to_list(500)
    behaviour_positive = sum(1 for b in behaviour_records if b.get("category") == "positive")
    behaviour_negative = sum(1 for b in behaviour_records if b.get("category") == "negative")
    behaviour_points = sum(b.get("points", 0) for b in behaviour_records)
    behaviour_score = min(100, max(0, 100 + behaviour_points))

    participation_records = await db.participation_records.find(
        {"student_id": student_id, "tenant_id": school_id},
        {"_id": 0, "points": 1}
    ).to_list(500)
    participation_total = len(participation_records)
    participation_points = sum(p.get("points", 0) for p in participation_records)

    return {
        "id": str(uuid.uuid4()),
        "student_id": student_id,
        "student_name": student.get("full_name"),
        "student_name_en": student.get("full_name_en"),
        "class_name": class_info.get("name") if class_info else None,
        "school_id": school_id,
        "academic_year": academic_year,
        "semester": semester,
        "gpa": gpa,
        "subjects": subjects_results,
        "attendance": {
            "total_days": att_total,
            "present": att_present,
            "absent": att_absent,
            "late": att_late,
            "rate": round((att_present / att_total * 100), 1) if att_total > 0 else 0
        },
        "behaviour": {
            "positive_count": behaviour_positive,
            "negative_count": behaviour_negative,
            "total_points": behaviour_points,
            "behaviour_score": behaviour_score
        },
        "participation": {
            "total_participations": participation_total,
            "total_points": participation_points
        },
        "status": "draft",
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/class-rankings/{class_id}")
async def get_class_rankings(
    class_id: str,
    subject_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get class rankings by student GPA or subject"""
    school_id = current_user.get("tenant_id")

    students = await db.students.find(
        {"class_id": class_id, "tenant_id": school_id},
        {"_id": 0, "id": 1, "full_name": 1}
    ).to_list(200)

    rankings = []
    for student in students:
        sid = student["id"]
        grade_query = {"student_id": sid}
        if school_id:
            grade_query["school_id"] = school_id
        if subject_id:
            grade_query["subject_id"] = subject_id

        grades = await db.grades.find(grade_query, {"_id": 0, "percentage": 1}).to_list(500)
        if grades:
            avg = round(sum(g.get("percentage", 0) for g in grades) / len(grades), 1)
        else:
            avg = 0

        def get_letter(pct):
            if pct >= 95: return "A+"
            if pct >= 90: return "A"
            if pct >= 85: return "B+"
            if pct >= 80: return "B"
            if pct >= 75: return "C+"
            if pct >= 70: return "C"
            if pct >= 65: return "D+"
            if pct >= 60: return "D"
            return "F"

        rankings.append({
            "student_id": sid,
            "student_name": student.get("full_name"),
            "average": avg,
            "letter_grade": get_letter(avg),
            "total_grades": len(grades)
        })

    rankings.sort(key=lambda x: x["average"], reverse=True)
    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    class_avg = round(sum(r["average"] for r in rankings) / max(1, len(rankings)), 1)

    return {
        "class_id": class_id,
        "subject_id": subject_id,
        "class_average": class_avg,
        "total_students": len(rankings),
        "rankings": rankings,
        "top_3": rankings[:3] if len(rankings) >= 3 else rankings
    }


# ============== CROSS-SECTION COMPARISON ==============

@router.get("/assessments/compare-sections")
async def compare_sections(
    assessment_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    academic_year: Optional[str] = None,
    semester: Optional[int] = None,
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ])),
):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await _assessment_engine.compare_sections(
        tenant_id=tenant_id,
        assessment_id=assessment_id,
        subject_id=subject_id,
        academic_year=academic_year,
        semester=semester,
    )


# ============== STUDENT RANKING ==============

@router.get("/assessments/student-ranking/{class_id}")
async def get_student_ranking(
    class_id: str,
    subject_id: Optional[str] = None,
    academic_year: Optional[str] = None,
    semester: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await _assessment_engine.get_student_ranking(
        tenant_id=tenant_id,
        class_id=class_id,
        subject_id=subject_id,
        academic_year=academic_year,
        semester=semester,
    )


# ============== PERFORMANCE TREND ==============

@router.get("/assessments/performance-trend/{student_id}")
async def get_performance_trend(
    student_id: str,
    subject_id: Optional[str] = None,
    periods: int = Query(6, ge=2, le=20),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await _assessment_engine.get_performance_trend(
        tenant_id=tenant_id,
        student_id=student_id,
        subject_id=subject_id,
        periods=periods,
    )


# ============== GRADE DECLINE ALERTS ==============

@router.get("/assessments/grade-decline-alerts")
async def get_grade_decline_alerts(
    class_id: Optional[str] = None,
    threshold: float = Query(-10.0, le=0),
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.TEACHER
    ])),
):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await _assessment_engine.get_grade_decline_alerts(
        tenant_id=tenant_id,
        class_id=class_id,
        threshold=threshold,
    )


# ============== SUBJECT STATISTICS ==============

@router.get("/assessments/subject-statistics/{subject_id}")
async def get_subject_statistics(
    subject_id: str,
    academic_year: Optional[str] = None,
    semester: Optional[int] = None,
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.TEACHER
    ])),
):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    return await _assessment_engine.get_subject_statistics(
        tenant_id=tenant_id,
        subject_id=subject_id,
        academic_year=academic_year,
        semester=semester,
    )


COMMITTEE_ROLES = [UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_SUB_ADMIN]

class CommitteeCreate(BaseModel):
    name: str
    location: Optional[str] = ""
    rows: int = 5
    cols: int = 6
    classes: List[str] = []
    students: List[dict] = []
    cancelledSeats: List[str] = []

class CommitteeUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    rows: Optional[int] = None
    cols: Optional[int] = None
    classes: Optional[List[str]] = None
    students: Optional[List[dict]] = None
    cancelledSeats: Optional[List[str]] = None


@router.get("/exam-committees")
async def get_exam_committees(
    current_user: dict = Depends(require_roles(COMMITTEE_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    committees = await db.exam_committees.find(
        {"school_id": tenant_id, "is_active": {"$ne": False}},
        {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    return {"success": True, "committees": committees}


@router.post("/exam-committees")
async def create_exam_committee(
    data: CommitteeCreate,
    current_user: dict = Depends(require_roles(COMMITTEE_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    now = datetime.now(timezone.utc).isoformat()
    committee_doc = {
        "id": str(uuid.uuid4()),
        "school_id": tenant_id,
        "name": data.name,
        "location": data.location or "",
        "rows": data.rows,
        "cols": data.cols,
        "classes": data.classes,
        "students": data.students,
        "cancelledSeats": data.cancelledSeats,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    await db.exam_committees.insert_one(committee_doc)
    committee_doc.pop("_id", None)
    return {"success": True, "committee": committee_doc}


@router.post("/exam-committees/bulk")
async def create_exam_committees_bulk(
    data: List[CommitteeCreate],
    current_user: dict = Depends(require_roles(COMMITTEE_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    now = datetime.now(timezone.utc).isoformat()
    docs = []
    for item in data:
        doc = {
            "id": str(uuid.uuid4()),
            "school_id": tenant_id,
            "name": item.name,
            "location": item.location or "",
            "rows": item.rows,
            "cols": item.cols,
            "classes": item.classes,
            "students": item.students,
            "cancelledSeats": item.cancelledSeats,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        docs.append(doc)
    if docs:
        await db.exam_committees.insert_many(docs)
    result = []
    for d in docs:
        d.pop("_id", None)
        result.append(d)
    return {"success": True, "committees": result, "count": len(result)}


@router.put("/exam-committees/{committee_id}")
async def update_exam_committee(
    committee_id: str,
    data: CommitteeUpdate,
    current_user: dict = Depends(require_roles(COMMITTEE_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    existing = await db.exam_committees.find_one({"id": committee_id, "school_id": tenant_id})
    if not existing:
        raise HTTPException(404, "اللجنة غير موجودة")
    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for field in ["name", "location", "rows", "cols", "classes", "students", "cancelledSeats"]:
        val = getattr(data, field, None)
        if val is not None:
            update_fields[field] = val
    await db.exam_committees.update_one(
        {"id": committee_id, "school_id": tenant_id},
        {"$set": update_fields}
    )
    updated = await db.exam_committees.find_one({"id": committee_id, "school_id": tenant_id}, {"_id": 0})
    return {"success": True, "committee": updated}


@router.delete("/exam-committees/{committee_id}")
async def delete_exam_committee(
    committee_id: str,
    current_user: dict = Depends(require_roles(COMMITTEE_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    result = await db.exam_committees.delete_one({"id": committee_id, "school_id": tenant_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "اللجنة غير موجودة")
    return {"success": True, "message": "تم حذف اللجنة"}


@router.get("/seating-card-settings")
async def get_seating_card_settings(
    current_user: dict = Depends(require_roles(COMMITTEE_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    doc = await db.seating_card_settings.find_one({"school_id": tenant_id}, {"_id": 0})
    if not doc:
        return {"success": True, "settings": None}
    return {"success": True, "settings": doc}


@router.put("/seating-card-settings")
async def save_seating_card_settings(
    body: dict = Body(...),
    current_user: dict = Depends(require_roles(COMMITTEE_ROLES))
):
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "school_id": tenant_id,
        "fields": body.get("fields", []),
        "cardWidth": body.get("cardWidth", 300),
        "cardHeight": body.get("cardHeight", 180),
        "updated_at": now,
    }
    await db.seating_card_settings.update_one(
        {"school_id": tenant_id},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True
    )
    return {"success": True, "settings": doc}
