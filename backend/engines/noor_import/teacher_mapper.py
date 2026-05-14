"""
Teacher mapping + email-fallback ladder for the Noor importer.

Login on this platform is email-based (auth_routes_mod.login keys on
credentials.email). Noor teacher reports often carry blank, malformed, or
duplicate emails, so the importer treats Noor email as untrusted and
applies a deterministic fallback before calling the canonical
`TeacherManagementEngine.create_teacher`.

Email-fallback ladder (ordered):
    1. Noor email IF it parses, is non-empty after trim, AND is unique.
    2. Mint `import.tch.{seq6}@{school_short_code}.nassaq.school` (deterministic
       per school, reset-able). Suffix `+{2hex}` if collision.

The mint scheme intentionally avoids `@noor.invalid` style sentinels so
password-reset flows still work after import.
"""
from __future__ import annotations

import logging
import re
import secrets
from typing import Any, Dict, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_structurally_valid_email(email: Optional[str]) -> bool:
    if not email:
        return False
    s = email.strip().lower()
    if len(s) > 254 or " " in s:
        return False
    return bool(_EMAIL_RE.match(s))


def _safe_school_domain(school_code: Optional[str]) -> str:
    """Build a deterministic, school-scoped fallback email domain."""
    code = (school_code or "sch").strip().lower()
    code = re.sub(r"[^a-z0-9-]", "", code) or "sch"
    return f"{code}.nassaq.school"


async def _email_in_use(session, email: str) -> bool:
    result = await session.execute(
        text("SELECT 1 FROM users WHERE LOWER(email) = LOWER(:e) LIMIT 1"),
        {"e": email},
    )
    return result.first() is not None


async def resolve_login_email(
    session,
    *,
    noor_email: Optional[str],
    school_code: Optional[str],
    seen_emails_in_batch: set,
) -> Dict[str, Any]:
    """
    Returns {"email": <login_email>, "source": "noor"|"fallback"}.
    `seen_emails_in_batch` is mutated to prevent two rows in the same
    upload landing on the same fallback address.
    """
    # Step 1 — try Noor email if structurally valid and free.
    if _is_structurally_valid_email(noor_email):
        candidate = noor_email.strip().lower()
        if candidate not in seen_emails_in_batch and not await _email_in_use(
            session, candidate
        ):
            seen_emails_in_batch.add(candidate)
            return {"email": candidate, "source": "noor"}

    # Step 2 — mint deterministic fallback.
    domain = _safe_school_domain(school_code)
    base = f"import.tch.{secrets.token_hex(3)}"
    candidate = f"{base}@{domain}"
    # Re-check for the (extremely unlikely) collision; suffix +{2hex}.
    for _ in range(8):
        if candidate not in seen_emails_in_batch and not await _email_in_use(
            session, candidate
        ):
            seen_emails_in_batch.add(candidate)
            return {"email": candidate, "source": "fallback"}
        candidate = f"{base}+{secrets.token_hex(1)}@{domain}"
    # Last-resort: append a longer entropy suffix.
    candidate = f"import.tch.{secrets.token_hex(8)}@{domain}"
    seen_emails_in_batch.add(candidate)
    return {"email": candidate, "source": "fallback"}


def build_create_teacher_request(
    row_data: Dict[str, Any],
    *,
    login_email: str,
):
    """Build a CreateTeacherRequest with sane defaults for fields Noor
    doesn't expose (subject_ids/grade_ids/primary_subject empty list,
    permanent contract). Imports the engine lazily to avoid a circular
    import."""
    from engines.teacher_management_engine import (
        CreateTeacherRequest,
        TeacherBasicInfo,
        TeacherQualifications,
        TeacherSubjectsAssignment,
        Gender,
        TeacherRank,
    )

    # National id must be 10 digits per engine validator; if Noor produced
    # something else we surface as a row error in the caller, not here.
    nid = (row_data.get("national_id") or "").strip()
    gender = row_data.get("gender") or "male"
    full_name = (row_data.get("full_name") or "").strip()

    basic_info = TeacherBasicInfo(
        full_name_ar=full_name,
        full_name_en=None,
        national_id=nid,
        date_of_birth=row_data.get("dob"),
        gender=Gender(gender),
        nationality="SA",
        phone=row_data.get("phone") or "0000000000",
        email=login_email,
    )
    qualifications = TeacherQualifications(
        academic_degree="بكالوريوس",
        specialization=None,
        university=None,
        graduation_year=None,
        years_of_experience=0,
        teacher_rank=TeacherRank.teacher,
        certifications=None,
    )
    subjects = TeacherSubjectsAssignment(
        subject_ids=[],
        grade_ids=[],
        primary_subject_id="",
        max_periods_per_week=24,
    )
    return CreateTeacherRequest(
        basic_info=basic_info,
        qualifications=qualifications,
        subjects=subjects,
        schedule=None,
    )
