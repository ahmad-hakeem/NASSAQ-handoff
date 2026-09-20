"""Separate retained timetable history from operational placements."""

from sqlalchemy import select

from engines.sql_utils import _build_filter_conditions, models_to_dicts
from pg_models import GenericDocument


async def find_live_timetable_sessions(session, filters: dict, *, limit=50000):
    """Exclude explicitly retired placements before applying the row limit.

    Teacher/class deletion keeps rows for history. Legacy live rows may omit
    both lifecycle fields (or contain null), so only explicit retirement counts.
    Do not filter by teacher/class existence here: active orphan references must
    still reach the publish integrity checks.
    """
    stmt = (
        select(GenericDocument)
        .where(
            GenericDocument._collection == "timetable_sessions",
            *_build_filter_conditions(GenericDocument, filters),
            GenericDocument.data["is_active"].astext.is_distinct_from("false"),
            GenericDocument.data["status"].astext.is_distinct_from("cancelled"),
        )
        .order_by(GenericDocument.data["day_of_week"].astext, GenericDocument.id)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return models_to_dicts(result.scalars().all())