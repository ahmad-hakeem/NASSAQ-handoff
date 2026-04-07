"""
NASSAQ Shared Dependencies
Central module exporting db, auth helpers, models, and engine instances.
All route modules should import from here instead of server.py.
"""
from fastapi import Depends, HTTPException, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, EmailStr
import os
import jwt
import bcrypt
import uuid
import logging
import qrcode
import io
import base64

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("nassaq")

from repositories import Repos
db = Repos()

JWT_SECRET = os.environ.get('JWT_SECRET_KEY', '')
if not JWT_SECRET:
    logger.critical("JWT_SECRET_KEY environment variable is not set — refusing to start with an ephemeral secret")
    raise SystemExit("FATAL: JWT_SECRET_KEY must be set. Aborting.")
JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES', 60))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get('REFRESH_TOKEN_EXPIRE_DAYS', 30))
REFRESH_TOKEN_SHORT_HOURS = int(os.environ.get('REFRESH_TOKEN_SHORT_HOURS', 2))

security = HTTPBearer()

from engines.audit_engine import AuditLogEngine, AuditAction, AuditSeverity
from engines.session_engine import TeacherSessionEngine
from engines.hakim_ai_engine import HakimAIEngine
from engines.reporting_engine import ReportingEngine, REPORT_TYPES
from engines.export_engine import ExportEngine
from engines.smart_scheduling_engine import (
    SmartSchedulingEngine,
    TimetableRunStatus,
    TimetableStatus,
    ConflictType,
    ConflictSeverity,
    PreValidationResult,
    GenerationResult
)

from db import get_pg_session, get_db, async_session_factory
from sqlalchemy.ext.asyncio import AsyncSession
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate

audit_engine = AuditLogEngine(db)
smart_scheduling_engine = SmartSchedulingEngine(db)
hakim_engine = HakimAIEngine(db)
reporting_engine = ReportingEngine(db, hakim_engine=hakim_engine)
export_engine = ExportEngine(db, reporting_engine=reporting_engine)
session_engine = TeacherSessionEngine(db)


def generate_secure_password(length=10):
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_student_qr_code(student_id: str, student_name: str, student_number: str) -> str:
    qr_data = f"NASSAQ|STUDENT|{student_id}|{student_number}|{student_name}"
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')


class UserRole(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    PLATFORM_SUB_ADMIN = "platform_sub_admin"
    PLATFORM_OPERATIONS_MANAGER = "platform_operations_manager"
    PLATFORM_TECHNICAL_ADMIN = "platform_technical_admin"
    PLATFORM_SUPPORT_SPECIALIST = "platform_support_specialist"
    PLATFORM_DATA_ANALYST = "platform_data_analyst"
    PLATFORM_SECURITY_OFFICER = "platform_security_officer"
    PLATFORM_SALES = "platform_sales"
    PLATFORM_MARKETING = "platform_marketing"
    PLATFORM_QUALITY = "platform_quality"
    MINISTRY_REP = "ministry_rep"
    SCHOOL_PRINCIPAL = "school_principal"
    SCHOOL_ADMIN = "school_admin"
    SCHOOL_SUB_ADMIN = "school_sub_admin"
    TEACHER = "teacher"
    INDEPENDENT_TEACHER = "independent_teacher"
    STUDENT = "student"
    PARENT = "parent"
    DRIVER = "driver"
    GATEKEEPER = "gatekeeper"
    TESTING_ACCOUNT = "testing_account"


class SchoolStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    SETUP = "setup"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(data: dict, remember_me: bool = False) -> str:
    to_encode = data.copy()
    if remember_me:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=REFRESH_TOKEN_SHORT_HOURS)
    to_encode.update({"exp": expire, "type": "refresh", "rm": remember_me})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_school_context: Optional[str] = Header(None, alias="X-School-Context")
) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") == "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = await gd_find_one(db.session, "users", {"id": user_id})

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        user.pop("_id", None)
        if "id" not in user or not user.get("id"):
            user["id"] = user_id

        if user.get("role") == UserRole.TEACHER.value and not user.get("teacher_id"):
            teacher = await gd_find_one(db.session, "teachers", {"email": user.get("email")})
            if teacher:
                user["teacher_id"] = teacher.get("id")

        if user.get("role") == UserRole.STUDENT.value and not user.get("student_id"):
            student = await gd_find_one(db.session, "students", {"email": user.get("email")})
            if student:
                user["student_id"] = student.get("id")

        if user.get("role") == UserRole.PARENT.value and not user.get("parent_id"):
            parent = await gd_find_one(db.session, "parents", {"email": user.get("email")})
            if parent:
                user["parent_id"] = parent.get("id")
            else:
                link = await gd_find_one(db.session, "guardian_links", {"parent_ref": user.get("id"), "is_active": True})
                if link:
                    user["parent_id"] = link.get("parent_ref")

        if payload.get("is_impersonating"):
            user["is_impersonating"] = True
            user["original_role"] = payload.get("original_role")
            user["original_user_id"] = payload.get("original_user_id")
            if payload.get("role"):
                user["role"] = payload["role"]
            if payload.get("tenant_id"):
                user["tenant_id"] = payload["tenant_id"]

        if payload.get("is_switched"):
            user["is_switched"] = True
            user["original_role"] = payload.get("original_role")
            if payload.get("role"):
                user["role"] = payload["role"]
            if payload.get("tenant_id"):
                user["tenant_id"] = payload["tenant_id"]

        if x_school_context and user.get("role") == UserRole.PLATFORM_ADMIN.value:
            school = await gd_find_one(db.session, "schools", {"id": x_school_context})
            if school:
                user["tenant_id"] = x_school_context
                user["is_impersonating"] = True
                user["original_role"] = user["role"]

        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_roles(allowed_roles: List[UserRole]):
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in [r.value for r in allowed_roles]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker
