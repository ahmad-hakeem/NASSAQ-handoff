"""
Platform Repository
= NestJS @InjectRepository()

Database access layer for Platform.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class PlatformRepository:
    """Data access for Platform domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
