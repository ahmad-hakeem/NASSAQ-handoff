"""
SearchDirectory Repository
= NestJS @InjectRepository()

Database access layer for SearchDirectory.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class SearchDirectoryRepository:
    """Data access for SearchDirectory domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
