"""
Scheduling Repository
= NestJS @InjectRepository()

Database access layer for Scheduling.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class SchedulingRepository:
    """Data access for Scheduling domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
