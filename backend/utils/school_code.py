"""
Shared, hardened school-code generation and collision-safe school insert.

Both create-school paths — the public instant signup
(`registration_routes_mod._create_school_instant`) and the platform-admin
create-school route (`school_routes_mod.create_school`) — mint codes from the
same ``NSS-{COUNTRY}-{YY}-####`` sequence space. Generating a code with a
non-atomic "read max → +1 → single existence check → insert" leaves a window
where two near-concurrent (or cross-path) signups compute the same next value
and the second INSERT trips the ``ix_schools_code`` UNIQUE constraint.

This module centralises code generation and wraps the actual INSERT in a
bounded, savepoint-based retry loop so an auto-generated collision is resolved
silently by regenerating a fresh unique code instead of surfacing the
"رمز المدرسة مستخدم مسبقاً" error to a first-time school. Operator-supplied
custom codes are intentionally NOT retried — a genuine duplicate there is still
a real error the caller must fix.
"""
import uuid
import logging
from datetime import datetime

from sqlalchemy import select, desc as sa_desc
from sqlalchemy.exc import IntegrityError

from pg_models import School

logger = logging.getLogger("nassaq.school_code")

SCHOOL_CODE_CONSTRAINT = "ix_schools_code"


def is_school_code_conflict(exc: IntegrityError) -> bool:
    """True when an IntegrityError was raised by the schools.code UNIQUE index."""
    msg = str(getattr(exc, "orig", exc)).lower()
    if SCHOOL_CODE_CONSTRAINT in msg:
        return True
    return (
        "schools" in msg
        and "code" in msg
        and ("unique" in msg or "duplicate" in msg)
    )


def school_code_prefix(country: str = "SA") -> str:
    year_suffix = datetime.now().strftime("%y")
    country_code = country[:2].upper() if country else "SA"
    return f"NSS-{country_code}-{year_suffix}-"


async def generate_school_code(session, country: str = "SA", offset: int = 0) -> str:
    """Compute the next sequential school code for ``country``.

    ``offset`` is added to the next number so retries make monotonic progress
    even if an isolation level hides a just-committed competing row.
    """
    prefix = school_code_prefix(country)
    stmt = (
        select(School.code)
        .where(School.code.like(f"{prefix}%"))
        .order_by(sa_desc(School.code))
        .limit(1)
    )
    result = await session.execute(stmt)
    last_code = result.scalars().first()

    next_num = 1
    if last_code:
        try:
            next_num = int(last_code.split("-")[-1]) + 1
        except (ValueError, IndexError):
            next_num = 1

    return f"{prefix}{str(next_num + offset).zfill(4)}"


async def insert_school_with_unique_code(
    session,
    build_doc,
    country: str = "SA",
    max_attempts: int = 5,
):
    """Insert a schools row, auto-recovering from code collisions.

    ``build_doc(code)`` must return the schools document dict for the given
    code (it may also derive code-dependent fields such as a fallback email).
    Each attempt regenerates a fresh sequential code; the INSERT runs inside a
    SAVEPOINT so a ``ix_schools_code`` collision rolls back only that attempt,
    leaving the outer transaction usable. A final uuid-suffixed fallback code is
    tried if every sequential attempt collides.

    Returns ``(code, school_obj)``. Re-raises any non-code IntegrityError.
    """
    from engines.sql_utils import dict_to_model

    last_error = None
    for attempt in range(max_attempts):
        code = await generate_school_code(session, country=country, offset=attempt)
        doc = build_doc(code)
        try:
            async with session.begin_nested():
                obj = dict_to_model(School, doc)
                session.add(obj)
                await session.flush()
            return code, obj
        except IntegrityError as ie:
            if not is_school_code_conflict(ie):
                raise
            last_error = ie
            logger.warning(
                "School code collision on attempt %s (code=%s); regenerating.",
                attempt + 1, code,
            )
            continue

    # Sequential space exhausted under contention — fall back to a random suffix.
    code = f"{school_code_prefix(country)}{uuid.uuid4().hex[:6].upper()}"
    doc = build_doc(code)
    try:
        async with session.begin_nested():
            obj = dict_to_model(School, doc)
            session.add(obj)
            await session.flush()
        return code, obj
    except IntegrityError as ie:
        if not is_school_code_conflict(ie):
            raise
        logger.error("School code fallback also collided (code=%s).", code)
        raise last_error or ie


async def insert_school_with_custom_code(session, build_doc, code: str):
    """Insert a schools row using an operator-supplied custom ``code``.

    No regeneration: a genuine duplicate raises the original code IntegrityError
    so the caller can map it to the correct Arabic error. Returns the school_obj.
    """
    from engines.sql_utils import dict_to_model

    doc = build_doc(code)
    async with session.begin_nested():
        obj = dict_to_model(School, doc)
        session.add(obj)
        await session.flush()
    return obj
