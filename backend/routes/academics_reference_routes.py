"""
NASSAQ Academics Sub-module
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64

logger = logging.getLogger("nassaq.academics")

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct


from shared_models import (
    TeacherCreate, TeacherUpdate, TeacherResponse, StudentCreate, StudentUpdate, StudentResponse, ClassCreate, ClassUpdate, ClassResponse, SubjectCreate, SubjectResponse
)

router = APIRouter()

# Reference Data APIs
@router.get("/reference/academic-structure")
async def get_academic_structure(current_user: dict = Depends(get_current_user)):
    """Get complete academic structure (stages, grades, tracks)"""
    # Try reference_* collections first (new naming), fall back to old names
    stages = await gd_find(db.session, "reference_stages", {}, order_by="order", desc_order=False, limit=10)
    if not stages:
        stages = await gd_find(db.session, "academic_stages", {"is_active": True}, order_by="order", desc_order=False, limit=10)
    
    grades = await gd_find(db.session, "reference_grades", {}, order_by="order", desc_order=False, limit=50)
    if not grades:
        grades = await gd_find(db.session, "academic_grades", {"is_active": True}, order_by="order", desc_order=False, limit=50)
    
    tracks = await gd_find(db.session, "reference_tracks", {}, limit=10)
    if not tracks:
        tracks = await gd_find(db.session, "education_tracks", {"is_active": True}, limit=10)
    
    subject_mappings = await gd_find(db.session, "subject_mappings", {}, limit=50)
    
    return {
        "stages": stages,
        "grades": grades,
        "tracks": tracks,
        "subject_mappings": subject_mappings
    }

@router.get("/reference/stages")
async def get_reference_stages(current_user: dict = Depends(get_current_user)):
    """Get all academic stages"""
    stages = await gd_find(db.session, "reference_stages", {}, order_by="order", desc_order=False, limit=10)
    if not stages:
        stages = await gd_find(db.session, "academic_stages", {"is_active": True}, order_by="order", desc_order=False, limit=10)
    return stages

@router.get("/reference/grades")
async def get_reference_grades(current_user: dict = Depends(get_current_user)):
    """Get all grades. Falls back across reference_grades → academic_grades →
    school's grade_levels → distinct grade values on the school's classes."""
    grades = await gd_find(db.session, "reference_grades", {}, order_by="order", desc_order=False, limit=50)
    if not grades:
        grades = await gd_find(db.session, "academic_grades", {"is_active": True}, order_by="order", desc_order=False, limit=50)

    if grades:
        return grades

    school_id = current_user.get("school_id")
    if not school_id:
        return []

    # Try the school's normalized grade_levels collection
    gl = await gd_find(
        db.session,
        "grade_levels",
        {"school_id": school_id, "is_active": {"$ne": False}},
        order_by="order",
        desc_order=False,
        limit=50,
    )
    if gl:
        return [
            {
                "id": g.get("id"),
                "name": g.get("name_ar") or g.get("name") or g.get("name_en"),
                "name_ar": g.get("name_ar"),
                "name_en": g.get("name_en"),
                "order": g.get("order") or g.get("grade_number") or 0,
            }
            for g in gl
        ]

    # Last-resort fallback: derive distinct grades from the school's classes
    classes = await gd_find(
        db.session,
        "classes",
        {"school_id": school_id, "is_active": {"$ne": False}},
        limit=1000,
    )
    derived = {}
    arabic_names = {
        "1": "الأول الابتدائي", "2": "الثاني الابتدائي", "3": "الثالث الابتدائي",
        "4": "الرابع الابتدائي", "5": "الخامس الابتدائي", "6": "السادس الابتدائي",
        "7": "الأول المتوسط", "8": "الثاني المتوسط", "9": "الثالث المتوسط",
        "10": "الأول الثانوي", "11": "الثاني الثانوي", "12": "الثالث الثانوي",
    }
    for c in classes:
        gid = c.get("grade_id") or c.get("grade_level")
        if gid is None or gid == "":
            continue
        key = str(gid)
        if key in derived:
            continue
        try:
            order_num = int(key)
            display_name = arabic_names.get(key, key)
        except (TypeError, ValueError):
            order_num = 0
            display_name = key
        derived[key] = {
            "id": key,
            "name": display_name,
            "name_ar": display_name,
            "name_en": key,
            "order": order_num,
        }
    return sorted(derived.values(), key=lambda x: x.get("order") or 0)

@router.get("/reference/tracks")
async def get_reference_tracks(current_user: dict = Depends(get_current_user)):
    """Get all education tracks"""
    tracks = await gd_find(db.session, "reference_tracks", {}, limit=10)
    if not tracks:
        tracks = await gd_find(db.session, "education_tracks", {"is_active": True}, limit=10)
    return tracks

@router.get("/reference/subjects")
async def get_reference_subjects(current_user: dict = Depends(get_current_user)):
    """Get all reference subjects"""
    subjects = await gd_find(db.session, "reference_subjects", {"is_active": True}, limit=500)
    if not subjects:
        subjects = await gd_find(db.session, "subjects", {"is_active": True}, limit=100)
    return subjects

@router.get("/reference/teacher-ranks")
async def get_reference_teacher_ranks(current_user: dict = Depends(get_current_user)):
    """Get all teacher ranks with teaching loads"""
    ranks = await gd_find(db.session, "reference_teacher_ranks", {}, order_by="order", desc_order=False, limit=20)
    if not ranks:
        ranks = await gd_find(db.session, "teacher_ranks", {"is_active": True}, order_by="order", desc_order=False, limit=20)
    return ranks

@router.get("/reference/admin-constraints")
async def get_reference_admin_constraints(current_user: dict = Depends(get_current_user)):
    """Get all administrative scheduling constraints"""
    constraints = await gd_find(db.session, "reference_admin_constraints", {"is_active": True}, limit=50)
    if not constraints:
        constraints = await gd_find(db.session, "admin_constraints", {"is_active": True}, limit=50)
    return constraints

@router.get("/reference/default-settings")
async def get_reference_default_settings(current_user: dict = Depends(get_current_user)):
    """Get default school settings template"""
    settings = await gd_find_one(db.session, "default_school_settings", {})
    if not settings:
        settings = await gd_find_one(db.session, "default_settings", {"id": "default-school-settings"})
    return settings or {}

