"""
NASSAQ Shared Dependencies
Central module exporting db, auth helpers, models, and engine instances.
All route modules should import from here instead of server.py.
"""
from fastapi import Depends, HTTPException, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorClient
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

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ.get('JWT_SECRET_KEY', '')
if not JWT_SECRET:
    import secrets as _secrets
    JWT_SECRET = _secrets.token_urlsafe(48)
    logger.warning("JWT_SECRET_KEY not set — generated ephemeral secret (tokens will invalidate on restart)")
JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES', 129600))

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
    PLATFORM_OPERATIONS_MANAGER = "platform_operations_manager"
    PLATFORM_TECHNICAL_ADMIN = "platform_technical_admin"
    PLATFORM_SUPPORT_SPECIALIST = "platform_support_specialist"
    PLATFORM_DATA_ANALYST = "platform_data_analyst"
    PLATFORM_SECURITY_OFFICER = "platform_security_officer"
    MINISTRY_REP = "ministry_rep"
    SCHOOL_PRINCIPAL = "school_principal"
    SCHOOL_ADMIN = "school_admin"
    SCHOOL_SUB_ADMIN = "school_sub_admin"
    TEACHER = "teacher"
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

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_school_context: Optional[str] = Header(None, alias="X-School-Context")
) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        from bson import ObjectId
        user = None
        try:
            user = await db.users.find_one({"_id": ObjectId(user_id)})
        except Exception:
            pass

        if not user:
            user = await db.users.find_one({"id": user_id})

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        if "_id" in user:
            if "id" not in user or not user.get("id"):
                user["id"] = str(user["_id"])
            del user["_id"]

        if user.get("role") == UserRole.TEACHER.value and not user.get("teacher_id"):
            teacher = await db.teachers.find_one({"email": user.get("email")}, {"_id": 0, "id": 1})
            if teacher:
                user["teacher_id"] = teacher.get("id")

        if user.get("role") == UserRole.STUDENT.value and not user.get("student_id"):
            student = await db.students.find_one({"email": user.get("email")}, {"_id": 0, "id": 1})
            if student:
                user["student_id"] = student.get("id")

        if user.get("role") == UserRole.PARENT.value and not user.get("parent_id"):
            parent = await db.parents.find_one({"email": user.get("email")}, {"_id": 0, "id": 1})
            if parent:
                user["parent_id"] = parent.get("id")
            else:
                link = await db.guardian_links.find_one({"parent_ref": user.get("id"), "is_active": True}, {"_id": 0, "parent_ref": 1})
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
            school = await db.schools.find_one({"id": x_school_context})
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
