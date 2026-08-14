"""
Academics Repository
= NestJS @InjectRepository()

Database access layer for Academics.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class AcademicsRepository:
    """Data access for Academics domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
