"""
Official Curriculum Routes - المنهج الرسمي
بيانات المنهج الرسمي من وزارة التعليم السعودية
هذه البيانات للقراءة فقط ولا يمكن تعديلها

ALL DATA IS READ-ONLY AND CANNOT BE MODIFIED
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
import logging
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct


logger = logging.getLogger("nassaq.official_curriculum_routes")

router = APIRouter(prefix="/official-curriculum", tags=["Official Curriculum"])

# Database dependency
db = None

def set_database(database):
    """Set the database connection"""
    global db
    db = database


# ============================================
# Response Models
# ============================================

class StageResponse(BaseModel):
    id: str
    name_ar: str
    name_en: str
    order: int
    grades_count: int
    is_official: bool = True
    is_locked: bool = True

class TrackResponse(BaseModel):
    id: str
    name_ar: str
    name_en: str
    applicable_stages: List[str]
    order: int
    is_official: bool = True
    is_locked: bool = True

class GradeResponse(BaseModel):
    id: str
    stage_id: str
    track_id: str
    name_ar: str
    name_en: str
    grade_number: int
    order: int
    is_official: bool = True
    is_locked: bool = True
    stage_name_ar: Optional[str] = None
    track_name_ar: Optional[str] = None

class SubjectResponse(BaseModel):
    id: str
    name_ar: str
    name_en: str
    category: str
    is_official: bool = True
    is_locked: bool = True

class SubjectDetailResponse(BaseModel):
    id: str
    grade_id: str
    subject_id: str
    annual_periods: int
    weekly_periods: float
    period_type: str
    order: int
    is_official: bool = True
    is_locked: bool = True
    subject_name_ar: Optional[str] = None
    subject_name_en: Optional[str] = None

class TeacherRankResponse(BaseModel):
    id: str
    rank_name_ar: str
    rank_name_en: str
    weekly_periods: int
    is_special_ed: bool
    is_official: bool = True
    is_locked: bool = True
    order: int

class CurriculumStatsResponse(BaseModel):
    stages: int
    tracks: int
    grades: int
    subjects: int
    grade_subject_mappings: int
    teacher_rank_loads: int


# ============================================
# API Endpoints
# ============================================

@router.get("/stats")
async def get_curriculum_stats():
    """
    الحصول على إحصائيات المنهج الرسمي
    Get official curriculum statistics
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    stages = await gd_count(db.session, "official_curriculum_stages", {})
    tracks = await gd_count(db.session, "official_curriculum_tracks", {})
    grades = await gd_count(db.session, "official_curriculum_grades", {})
    subjects = await gd_count(db.session, "official_curriculum_subjects", {})
    details = await gd_count(db.session, "official_curriculum_grade_subjects", {})
    ranks = await gd_count(db.session, "official_teacher_rank_loads", {})
    
    return {
        "stages": stages,
        "tracks": tracks,
        "grades": grades,
        "subjects": subjects,
        "grade_subject_mappings": details,
        "teacher_rank_loads": ranks,
        "is_official": True,
        "is_locked": True,
        "source": "وزارة التعليم - المملكة العربية السعودية"
    }


@router.get("/stages")
async def get_stages():
    """
    الحصول على جميع المراحل الدراسية
    Get all official stages
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    stages = await gd_find(db.session, "official_curriculum_stages", {}, order_by="order", desc_order=False, limit=10)
    
    return stages


@router.get("/tracks")
async def get_tracks(stage_id: Optional[str] = None):
    """
    الحصول على جميع المسارات التعليمية
    Get all official tracks, optionally filtered by stage
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    query = {}
    if stage_id:
        query["applicable_stages"] = stage_id
    
    tracks = await gd_find(db.session, "official_curriculum_tracks", query, order_by="order", desc_order=False, limit=20)
    
    return tracks


@router.get("/grades")
async def get_grades(
    stage_id: Optional[str] = None,
    track_id: Optional[str] = None
):
    """
    الحصول على جميع الصفوف والسنوات
    Get all official grades, optionally filtered by stage and/or track
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    query = {}
    if stage_id:
        query["stage_id"] = stage_id
    if track_id:
        query["track_id"] = track_id
    
    grades = await gd_find(db.session, "official_curriculum_grades", query, order_by="order", desc_order=False, limit=100)
    
    # Enrich with stage and track names
    stages_map = {}
    tracks_map = {}
    
    stages = await gd_find(db.session, "official_curriculum_stages", {}, limit=10)
    for s in stages:
        stages_map[s["id"]] = s["name_ar"]
    
    tracks = await gd_find(db.session, "official_curriculum_tracks", {}, limit=20)
    for t in tracks:
        tracks_map[t["id"]] = t["name_ar"]
    
    for grade in grades:
        grade["stage_name_ar"] = stages_map.get(grade.get("stage_id"), "")
        grade["track_name_ar"] = tracks_map.get(grade.get("track_id"), "")
    
    return grades


@router.get("/subjects")
async def get_subjects(category: Optional[str] = None):
    """
    الحصول على جميع المواد الدراسية
    Get all official subjects, optionally filtered by category
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    query = {}
    if category:
        query["category"] = category
    
    subjects = await gd_find(db.session, "official_curriculum_subjects", query, order_by="name_ar", desc_order=False, limit=200)
    
    return subjects


@router.get("/subject-categories")
async def get_subject_categories():
    """
    الحصول على تصنيفات المواد
    Get all subject categories
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    categories = await gd_distinct(db.session, "official_curriculum_subjects", "category")
    
    category_names = {
        "islamic": "التربية الإسلامية",
        "language": "اللغات",
        "science": "العلوم والرياضيات",
        "social": "الدراسات الاجتماعية",
        "technology": "التقنية والحاسب",
        "engineering": "الهندسة",
        "health": "الصحة والحياة",
        "business": "إدارة الأعمال",
        "law": "القانون",
        "skills": "المهارات",
        "physical": "التربية البدنية",
        "arts": "الفنون",
        "activity": "النشاط",
        "non_class": "الفترات اللاصفية",
        "project": "المشاريع",
        "optional": "المواد الاختيارية"
    }
    
    return [
        {"id": cat, "name_ar": category_names.get(cat, cat), "name_en": cat}
        for cat in sorted(categories)
    ]


@router.get("/grade-subjects/{grade_id}")
async def get_grade_subjects(grade_id: str):
    """
    الحصول على توزيع المواد لصف محدد
    Get subject distribution for a specific grade
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Get the grade info
    grade = await gd_find_one(db.session, "official_curriculum_grades", {"id": grade_id})
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")
    
    # Get subject details for this grade
    details = await gd_find(db.session, "official_curriculum_grade_subjects", {"grade_id": grade_id}, order_by="display_order", desc_order=False, limit=50)
    
    # Get subjects map
    subjects = await gd_find(db.session, "official_curriculum_subjects", {}, limit=200)
    subjects_map = {s["id"]: s for s in subjects}
    
    # Enrich details with subject names
    enriched_details = []
    total_annual = 0
    class_periods_count = 0
    
    for detail in details:
        subject = subjects_map.get(detail.get("subject_id"), {})
        detail["subject_name_ar"] = subject.get("name_ar", "")
        detail["subject_name_en"] = subject.get("name_en", "")
        detail["subject_category"] = subject.get("category", "")
        enriched_details.append(detail)
        
        sessions = detail.get("annual_sessions", detail.get("annual_periods", 0))
        detail["annual_periods"] = sessions
        total_annual += sessions
        if detail.get("item_type", detail.get("period_type", "class_period")) == "class_period":
            class_periods_count += sessions
    
    return {
        "grade": grade,
        "subjects": enriched_details,
        "summary": {
            "total_subjects": len(enriched_details),
            "total_annual_periods": total_annual,
            "class_periods": class_periods_count,
            "non_class_periods": total_annual - class_periods_count
        },
        "is_official": True,
        "is_locked": True
    }


@router.get("/teacher-rank-loads")
async def get_teacher_rank_loads():
    """
    الحصول على النصاب الرسمي للمعلمين حسب الرتب
    Get official teacher workload by rank
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    ranks = await gd_find(db.session, "official_teacher_rank_loads", {}, order_by="order", desc_order=False, limit=20)
    
    # Normalize field names for frontend compatibility
    normalized = []
    for r in ranks:
        r["rank_name_ar"] = r.get("rank_ar", r.get("rank_name_ar", ""))
        r["rank_name_en"] = r.get("rank_en", r.get("rank_name_en", ""))
        r["weekly_periods"] = r.get("weekly_load", r.get("weekly_periods", 0))
        normalized.append(r)
    
    return normalized


@router.get("/stage/{stage_id}/full")
async def get_stage_full_curriculum(stage_id: str):
    """
    الحصول على المنهج الكامل لمرحلة محددة
    Get complete curriculum for a stage including all tracks, grades, and subjects
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Get stage
    stage = await gd_find_one(db.session, "official_curriculum_stages", {"id": stage_id})
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    
    # Get tracks for this stage
    tracks = await gd_find(db.session, "official_curriculum_tracks", {"stage_id": stage_id}, order_by="order", desc_order=False, limit=20)
    
    # Get all grades for this stage
    grades = await gd_find(db.session, "official_curriculum_grades", {"stage_id": stage_id}, order_by="order", desc_order=False, limit=50)
    
    # Get subjects map
    subjects = await gd_find(db.session, "official_curriculum_subjects", {}, limit=200)
    subjects_map = {s["id"]: s for s in subjects}
    
    # Build curriculum by track
    curriculum_by_track = []
    
    for track in tracks:
        track_grades = [g for g in grades if g.get("track_id") == track["id"]]
        
        grades_with_subjects = []
        for grade in track_grades:
            # Get subject details for this grade
            details = await gd_find(db.session, "official_curriculum_grade_subjects", {"grade_id": grade["id"]}, order_by="display_order", desc_order=False, limit=50)
            
            # Enrich with subject names
            enriched_subjects = []
            for d in details:
                subj = subjects_map.get(d.get("subject_id"), {})
                sessions = d.get("annual_sessions", d.get("annual_periods", 0))
                enriched_subjects.append({
                    **d,
                    "annual_periods": sessions,
                    "subject_name_ar": subj.get("name_ar", d.get("subject_name_ar", "")),
                    "subject_name_en": subj.get("name_en", ""),
                    "category": subj.get("category", "")
                })
            
            grades_with_subjects.append({
                **grade,
                "subjects": enriched_subjects,
                "subjects_count": len(enriched_subjects),
                "total_annual_periods": sum(d.get("annual_sessions", d.get("annual_periods", 0)) for d in details)
            })
        
        curriculum_by_track.append({
            **track,
            "grades": grades_with_subjects,
            "grades_count": len(grades_with_subjects)
        })
    
    return {
        "stage": stage,
        "tracks": curriculum_by_track,
        "is_official": True,
        "is_locked": True
    }


@router.get("/complete")
async def get_complete_curriculum():
    """
    الحصول على المنهج الرسمي الكامل
    Get the complete official curriculum hierarchy
    
    WARNING: This returns a large dataset. Use stage-specific endpoints for better performance.
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Get all stages
    stages = await gd_find(db.session, "official_curriculum_stages", {}, order_by="order", desc_order=False, limit=10)
    
    result = []
    
    for stage in stages:
        stage_curriculum = await get_stage_full_curriculum(stage["id"])
        result.append(stage_curriculum)
    
    return {
        "curriculum": result,
        "teacher_rank_loads": await get_teacher_rank_loads(),
        "stats": await get_curriculum_stats(),
        "is_official": True,
        "is_locked": True,
        "source": "وزارة التعليم - المملكة العربية السعودية"
    }
