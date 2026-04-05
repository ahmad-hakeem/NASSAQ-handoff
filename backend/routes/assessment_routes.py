"""
NASSAQ Assessment Routes
مسارات API للتقييم والاختبارات

Endpoints:
- Assessment CRUD
- Grading
- Grade calculations
- Report cards
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

logger = logging.getLogger("nassaq.assessment_routes")


# ============== MODELS ==============

class AssessmentCreate(BaseModel):
    subject_id: str
    section_ids: List[str]
    title: str
    title_en: Optional[str] = None
    description: Optional[str] = None
    assessment_type: str
    max_score: float
    passing_score: Optional[float] = None
    weight: float = 1.0
    due_date: Optional[str] = None
    assessment_date: Optional[str] = None
    duration_minutes: Optional[int] = None
    academic_year: Optional[str] = None
    semester: Optional[int] = None


class AssessmentResponse(BaseModel):
    id: str
    tenant_id: str
    subject_id: str
    section_ids: List[str]
    title: str
    title_en: Optional[str] = None
    assessment_type: str
    max_score: float
    passing_score: float
    weight: float
    is_published: bool
    is_graded: bool
    created_at: str
    metadata: Optional[dict] = None


class GradeCreate(BaseModel):
    student_id: str
    score: float
    feedback: Optional[str] = None
    notes: Optional[str] = None


class BulkGradeCreate(BaseModel):
    grades: List[GradeCreate]


class GradeResponse(BaseModel):
    id: str
    assessment_id: str
    student_id: str
    score: float
    max_score: float
    percentage: float
    is_passing: bool
    feedback: Optional[str] = None
    graded_at: str


class GradeWeightsCreate(BaseModel):
    subject_id: str
    weights: dict
    academic_year: Optional[str] = None
    semester: Optional[int] = None


class StudentAverageResponse(BaseModel):
    student_id: str
    subject_id: str
    final_average: float
    letter_grade: str
    grade_breakdown: dict
    total_assessments: int


def create_assessment_router(db, get_current_user, require_roles, UserRole):
    """Factory function to create assessment router with dependencies"""
    
    router = APIRouter(prefix="/assessments", tags=["Assessments"])
    
    # Initialize engine
    from engines.assessment_engine import AssessmentEngine
    from dependencies import audit_engine
    engine = AssessmentEngine(db, audit_engine=audit_engine)
    
    # ============== ASSESSMENTS ==============
    
    @router.post("/", response_model=AssessmentResponse)
    async def create_assessment(
        data: AssessmentCreate,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.TEACHER
        ]))
    ):
        """Create a new assessment"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        assessment = await engine.create_assessment(
            tenant_id=tenant_id,
            subject_id=data.subject_id,
            section_ids=data.section_ids,
            title=data.title,
            assessment_type=data.assessment_type,
            max_score=data.max_score,
            created_by=current_user["id"],
            title_en=data.title_en,
            description=data.description,
            passing_score=data.passing_score,
            weight=data.weight,
            due_date=data.due_date,
            assessment_date=data.assessment_date,
            duration_minutes=data.duration_minutes,
            academic_year=data.academic_year,
            semester=data.semester
        )
        
        return assessment
    
    @router.get("/", response_model=List[AssessmentResponse])
    async def get_assessments(
        subject_id: Optional[str] = None,
        section_id: Optional[str] = None,
        assessment_type: Optional[str] = None,
        academic_year: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        """Get assessments"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        assessments = await engine.get_assessments(
            tenant_id=tenant_id,
            subject_id=subject_id,
            section_id=section_id,
            assessment_type=assessment_type,
            academic_year=academic_year
        )
        
        return assessments
    
    @router.get("/{assessment_id}", response_model=AssessmentResponse)
    async def get_assessment(
        assessment_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get assessment by ID"""
        assessment = await engine.get_assessment_by_id(assessment_id)
        
        if not assessment:
            raise HTTPException(status_code=404, detail="التقييم غير موجود")
        
        return assessment
    
    @router.put("/{assessment_id}", response_model=AssessmentResponse)
    async def update_assessment(
        assessment_id: str,
        data: AssessmentCreate,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.TEACHER
        ]))
    ):
        """Update an assessment"""
        assessment = await engine.update_assessment(
            assessment_id=assessment_id,
            updates=data.dict(exclude_unset=True),
            updated_by=current_user["id"]
        )
        
        if not assessment:
            raise HTTPException(status_code=404, detail="التقييم غير موجود")
        
        return assessment
    
    @router.post("/{assessment_id}/publish")
    async def publish_assessment(
        assessment_id: str,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.TEACHER
        ]))
    ):
        """Publish an assessment"""
        assessment = await engine.publish_assessment(
            assessment_id=assessment_id,
            published_by=current_user["id"]
        )
        
        if not assessment:
            raise HTTPException(status_code=404, detail="التقييم غير موجود")
        
        return {"message": "تم نشر التقييم", "assessment": assessment}
    
    @router.delete("/{assessment_id}")
    async def delete_assessment(
        assessment_id: str,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.TEACHER
        ]))
    ):
        """Delete an assessment"""
        success = await engine.delete_assessment(
            assessment_id=assessment_id,
            deleted_by=current_user["id"]
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="التقييم غير موجود")
        
        return {"message": "تم حذف التقييم"}
    
    # ============== GRADING ==============
    
    @router.post("/{assessment_id}/grades", response_model=GradeResponse)
    async def record_grade(
        assessment_id: str,
        data: GradeCreate,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.TEACHER
        ]))
    ):
        """Record a grade for a student"""
        try:
            grade = await engine.record_grade(
                assessment_id=assessment_id,
                student_id=data.student_id,
                score=data.score,
                graded_by=current_user["id"],
                feedback=data.feedback,
                notes=data.notes
            )
            return grade
        except ValueError as e:
            raise HTTPException(status_code=400, detail="خطأ في البيانات المرسلة")
    
    @router.post("/{assessment_id}/grades/bulk")
    async def record_bulk_grades(
        assessment_id: str,
        data: BulkGradeCreate,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.TEACHER
        ]))
    ):
        """Record grades for multiple students"""
        results = await engine.record_bulk_grades(
            assessment_id=assessment_id,
            grades=[g.dict() for g in data.grades],
            graded_by=current_user["id"]
        )
        
        return {
            "message": f"تم رصد {results['processed']} درجة",
            "results": results
        }
    
    @router.get("/{assessment_id}/grades", response_model=List[GradeResponse])
    async def get_assessment_grades(
        assessment_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get all grades for an assessment"""
        grades = await engine.get_assessment_grades(assessment_id)
        return grades
    
    @router.get("/student/{student_id}/grades")
    async def get_student_grades(
        student_id: str,
        subject_id: Optional[str] = None,
        academic_year: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        """Get grades for a student"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        grades = await engine.get_student_grades(
            tenant_id=tenant_id,
            student_id=student_id,
            subject_id=subject_id,
            academic_year=academic_year
        )
        
        return {"student_id": student_id, "grades": grades, "total": len(grades)}
    
    # ============== GRADE WEIGHTS ==============
    
    @router.post("/grade-weights")
    async def set_grade_weights(
        data: GradeWeightsCreate,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL
        ]))
    ):
        """Set grade weights for a subject"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        try:
            weights = await engine.set_grade_weights(
                tenant_id=tenant_id,
                subject_id=data.subject_id,
                weights=data.weights,
                set_by=current_user["id"],
                academic_year=data.academic_year,
                semester=data.semester
            )
            return {"message": "تم تحديث أوزان الدرجات", "weights": weights}
        except ValueError as e:
            raise HTTPException(status_code=400, detail="خطأ في البيانات المرسلة")
    
    @router.get("/grade-weights/{subject_id}")
    async def get_grade_weights(
        subject_id: str,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
        current_user: dict = Depends(get_current_user)
    ):
        """Get grade weights for a subject"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        weights = await engine.get_grade_weights(
            tenant_id=tenant_id,
            subject_id=subject_id,
            academic_year=academic_year,
            semester=semester
        )
        
        return {"subject_id": subject_id, "weights": weights}
    
    # ============== CALCULATIONS ==============
    
    @router.get("/student/{student_id}/average/{subject_id}", response_model=StudentAverageResponse)
    async def calculate_student_average(
        student_id: str,
        subject_id: str,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
        current_user: dict = Depends(get_current_user)
    ):
        """Calculate weighted average for a student in a subject"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        average = await engine.calculate_student_average(
            tenant_id=tenant_id,
            student_id=student_id,
            subject_id=subject_id,
            academic_year=academic_year,
            semester=semester
        )
        
        return average
    
    @router.get("/{assessment_id}/statistics")
    async def get_assessment_statistics(
        assessment_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get statistics for an assessment"""
        stats = await engine.calculate_class_statistics(assessment_id)
        return stats
    
    # ============== REPORT CARDS ==============
    
    @router.post("/report-cards/generate")
    async def generate_report_card(
        student_id: str,
        academic_year: str,
        semester: int,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL
        ]))
    ):
        """Generate a report card for a student"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        report_card = await engine.generate_report_card(
            tenant_id=tenant_id,
            student_id=student_id,
            academic_year=academic_year,
            semester=semester,
            generated_by=current_user["id"]
        )
        
        return {"message": "تم إنشاء بطاقة التقرير", "report_card": report_card}
    
    @router.get("/report-cards/student/{student_id}")
    async def get_report_card(
        student_id: str,
        academic_year: str,
        semester: int,
        current_user: dict = Depends(get_current_user)
    ):
        """Get report card for a student"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        report_card = await engine.get_report_card(
            tenant_id=tenant_id,
            student_id=student_id,
            academic_year=academic_year,
            semester=semester
        )
        
        if not report_card:
            raise HTTPException(status_code=404, detail="بطاقة التقرير غير موجودة")
        
        return report_card

    @router.get("/compare-sections")
    async def compare_sections_route(
        assessment_id: Optional[str] = None,
        subject_id: Optional[str] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL
        ])),
    ):
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        return await engine.compare_sections(tenant_id, assessment_id, subject_id, academic_year, semester)

    @router.get("/student-ranking/{class_id}")
    async def student_ranking_route(
        class_id: str,
        subject_id: Optional[str] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
        current_user: dict = Depends(get_current_user),
    ):
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        return await engine.get_student_ranking(tenant_id, class_id, subject_id, academic_year, semester)

    @router.get("/performance-trend/{student_id}")
    async def performance_trend_route(
        student_id: str,
        subject_id: Optional[str] = None,
        periods: int = 6,
        current_user: dict = Depends(get_current_user),
    ):
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        return await engine.get_performance_trend(tenant_id, student_id, subject_id, periods)

    @router.get("/grade-decline-alerts")
    async def grade_decline_alerts_route(
        class_id: Optional[str] = None,
        threshold: float = -10.0,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.TEACHER
        ])),
    ):
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        return await engine.get_grade_decline_alerts(tenant_id, class_id, threshold)

    @router.get("/subject-statistics/{subject_id}")
    async def subject_statistics_route(
        subject_id: str,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.TEACHER
        ])),
    ):
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        return await engine.get_subject_statistics(tenant_id, subject_id, academic_year, semester)

    return router


# Export
__all__ = ["create_assessment_router"]
