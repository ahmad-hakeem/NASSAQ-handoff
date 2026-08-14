"""
StudentManagement Repository
= NestJS @InjectRepository()

Database access layer for StudentManagement.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class StudentManagementRepository:
    """Data access for StudentManagement domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
