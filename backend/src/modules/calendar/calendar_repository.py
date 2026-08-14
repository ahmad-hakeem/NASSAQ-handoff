"""
Calendar Repository
= NestJS @InjectRepository()

Database access layer for Calendar.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class CalendarRepository:
    """Data access for Calendar domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
