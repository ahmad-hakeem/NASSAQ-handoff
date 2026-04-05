"""
NASSAQ PostgreSQL Helper Utilities
Replaces common MongoDB patterns with PostgreSQL equivalents.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type
from sqlalchemy import text, select, func, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from db import Base


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


def serialize_row(row) -> Optional[dict]:
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


async def find_one(session: AsyncSession, model: Type[Base], **filters) -> Optional[Any]:
    stmt = select(model)
    for k, v in filters.items():
        stmt = stmt.where(getattr(model, k) == v)
    result = await session.execute(stmt)
    return result.scalars().first()


async def find_many(
    session: AsyncSession,
    model: Type[Base],
    filters: Optional[Dict] = None,
    order_by: Optional[str] = None,
    order_dir: str = "desc",
    skip: int = 0,
    limit: Optional[int] = None,
) -> List[Any]:
    stmt = select(model)
    if filters:
        conditions = []
        for k, v in filters.items():
            if isinstance(v, list):
                conditions.append(getattr(model, k).in_(v))
            elif isinstance(v, dict) and "$ne" in v:
                conditions.append(getattr(model, k) != v["$ne"])
            else:
                conditions.append(getattr(model, k) == v)
        if conditions:
            stmt = stmt.where(and_(*conditions))
    if order_by and hasattr(model, order_by):
        col = getattr(model, order_by)
        stmt = stmt.order_by(desc(col) if order_dir == "desc" else asc(col))
    if skip:
        stmt = stmt.offset(skip)
    if limit:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


async def count_documents(
    session: AsyncSession,
    model: Type[Base],
    filters: Optional[Dict] = None,
) -> int:
    stmt = select(func.count()).select_from(model)
    if filters:
        for k, v in filters.items():
            if isinstance(v, dict) and "$ne" in v:
                stmt = stmt.where(getattr(model, k) != v["$ne"])
            else:
                stmt = stmt.where(getattr(model, k) == v)
    result = await session.execute(stmt)
    return result.scalar() or 0


async def insert_one(session: AsyncSession, model_instance) -> Any:
    session.add(model_instance)
    await session.flush()
    return model_instance


async def update_one(
    session: AsyncSession,
    model: Type[Base],
    filter_by: Dict,
    update_fields: Dict,
) -> Optional[Any]:
    obj = await find_one(session, model, **filter_by)
    if obj:
        for k, v in update_fields.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        await session.flush()
    return obj


async def delete_one(
    session: AsyncSession,
    model: Type[Base],
    **filters,
) -> bool:
    obj = await find_one(session, model, **filters)
    if obj:
        await session.delete(obj)
        await session.flush()
        return True
    return False
