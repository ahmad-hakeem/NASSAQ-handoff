"""
Schools Repository
Database access layer for Schools domain.
Provides standardized queries and access methods for schools, settings, time slots, and assignments.
"""
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from engines.sql_utils import (
    gd_find, gd_find_one, gd_insert, gd_update_one, gd_delete_one, gd_count,
)

logger = logging.getLogger("nassaq")


class SchoolsRepository:
    """Data access layer for Schools domain."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, school_id: str) -> Optional[dict]:
        return await gd_find_one(self.session, "schools", {"id": school_id})

    async def get_by_code(self, code: str) -> Optional[dict]:
        return await gd_find_one(self.session, "schools", {"code": code})

    async def list_schools(self, query: dict = None, limit: int = 1000) -> List[dict]:
        return await gd_find(self.session, "schools", query or {}, limit=limit)

    async def count_schools(self, query: dict = None) -> int:
        return await gd_count(self.session, "schools", query or {})

    async def get_settings(self, school_id: str) -> Optional[dict]:
        return await gd_find_one(self.session, "school_settings", {"school_id": school_id})

    async def get_time_slots(self, school_id: str) -> List[dict]:
        return await gd_find(self.session, "time_slots", {"school_id": school_id}, order_by="slot_number", desc_order=False, limit=50)

    async def get_unavailability_records(self, school_id: str, entity_type: str = None) -> List[dict]:
        query = {"school_id": school_id}
        if entity_type:
            query["entity_type"] = entity_type
        return await gd_find(self.session, "unavailability", query, limit=1000)
