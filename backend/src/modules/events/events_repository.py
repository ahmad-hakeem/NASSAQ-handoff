"""
Events Repository
= NestJS @InjectRepository()

Database access layer for Events.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class EventsRepository:
    """Data access for Events domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
