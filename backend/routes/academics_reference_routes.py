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

from shared_models import (
    TeacherCreate, TeacherUpdate, TeacherResponse, StudentCreate, StudentUpdate, StudentResponse, ClassCreate, ClassUpdate, ClassResponse, SubjectCreate, SubjectResponse
)

router = APIRouter()

# Reference Data APIs
@router.get("/reference/academic-structure")
async def get_academic_structure(current_user: dict = Depends(get_current_user)):
    """Get complete academic structure (stages, grades, tracks)"""
    # Try reference_* collections first (new naming), fall back to old names
    stages = await db.reference_stages.find({}, {"_id": 0}).sort("order", 1).to_list(10)
    if not stages:
        stages = await db.academic_stages.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(10)
    
    grades = await db.reference_grades.find({}, {"_id": 0}).sort("order", 1).to_list(50)
    if not grades:
        grades = await db.academic_grades.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(50)
    
    tracks = await db.reference_tracks.find({}, {"_id": 0}).to_list(10)
    if not tracks:
        tracks = await db.education_tracks.find({"is_active": True}, {"_id": 0}).to_list(10)
    
    subject_mappings = await db.subject_mappings.find({}, {"_id": 0}).to_list(50)
    
    return {
        "stages": stages,
        "grades": grades,
        "tracks": tracks,
        "subject_mappings": subject_mappings
    }

@router.get("/reference/stages")
async def get_reference_stages(current_user: dict = Depends(get_current_user)):
    """Get all academic stages"""
    stages = await db.reference_stages.find({}, {"_id": 0}).sort("order", 1).to_list(10)
    if not stages:
        stages = await db.academic_stages.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(10)
    return stages

@router.get("/reference/grades")
async def get_reference_grades(current_user: dict = Depends(get_current_user)):
    """Get all grades"""
    grades = await db.reference_grades.find({}, {"_id": 0}).sort("order", 1).to_list(50)
    if not grades:
        grades = await db.academic_grades.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(50)
    return grades

@router.get("/reference/tracks")
async def get_reference_tracks(current_user: dict = Depends(get_current_user)):
    """Get all education tracks"""
    tracks = await db.reference_tracks.find({}, {"_id": 0}).to_list(10)
    if not tracks:
        tracks = await db.education_tracks.find({"is_active": True}, {"_id": 0}).to_list(10)
    return tracks

@router.get("/reference/subjects")
async def get_reference_subjects(current_user: dict = Depends(get_current_user)):
    """Get all reference subjects"""
    subjects = await db.reference_subjects.find({"is_active": True}, {"_id": 0}).to_list(500)
    if not subjects:
        subjects = await db.subjects.find({"is_active": True}, {"_id": 0}).to_list(100)
    return subjects

@router.get("/reference/teacher-ranks")
async def get_reference_teacher_ranks(current_user: dict = Depends(get_current_user)):
    """Get all teacher ranks with teaching loads"""
    ranks = await db.reference_teacher_ranks.find({}, {"_id": 0}).sort("order", 1).to_list(20)
    if not ranks:
        ranks = await db.teacher_ranks.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(20)
    return ranks

@router.get("/reference/admin-constraints")
async def get_reference_admin_constraints(current_user: dict = Depends(get_current_user)):
    """Get all administrative scheduling constraints"""
    constraints = await db.reference_admin_constraints.find({"is_active": True}, {"_id": 0}).to_list(50)
    if not constraints:
        constraints = await db.admin_constraints.find({"is_active": True}, {"_id": 0}).to_list(50)
    return constraints

@router.get("/reference/default-settings")
async def get_reference_default_settings(current_user: dict = Depends(get_current_user)):
    """Get default school settings template"""
    settings = await db.default_school_settings.find_one({}, {"_id": 0})
    if not settings:
        settings = await db.default_settings.find_one({"id": "default-school-settings"}, {"_id": 0})
    return settings or {}

