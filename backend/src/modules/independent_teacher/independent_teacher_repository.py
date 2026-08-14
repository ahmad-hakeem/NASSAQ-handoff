"""
IndependentTeacher Repository
= NestJS @InjectRepository()

Database access layer for IndependentTeacher.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class IndependentTeacherRepository:
    """Data access for IndependentTeacher domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
