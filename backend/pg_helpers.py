"""
NASSAQ PostgreSQL Helper Utilities
Replaces common MongoDB patterns with PostgreSQL equivalents.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def generate_id() -> str:
    return str(uuid.uuid4())


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def next_issue_number(session: AsyncSession) -> int:
    result = await session.execute(text("SELECT nextval('issue_number_seq')"))
    return result.scalar()


async def reset_issue_sequence(session: AsyncSession, restart_value: int):
    val = int(restart_value)
    await session.execute(text("ALTER SEQUENCE issue_number_seq RESTART WITH :val"), {"val": val})


async def ensure_issue_sequence(session: AsyncSession, current_max: int):
    val = max(int(current_max), 1)
    await session.execute(text("SELECT setval('issue_number_seq', :val, true)"), {"val": val})


def serialize_row(row) -> dict:
    if row is None:
        return None
    if hasattr(row, "__dict__"):
        d = {}
        for k, v in row.__dict__.items():
            if not k.startswith("_"):
                d[k] = v
        return d
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    return dict(row)


def serialize_rows(rows) -> list:
    return [serialize_row(r) for r in rows if r]
