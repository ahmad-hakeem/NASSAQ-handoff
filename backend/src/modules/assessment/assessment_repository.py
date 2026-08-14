"""
Assessment Repository
= NestJS @InjectRepository()

Database access layer for Assessment.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class AssessmentRepository:
    """Data access for Assessment domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
