"""
Attendance Repository
= NestJS @InjectRepository()

Database access layer for Attendance.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class AttendanceRepository:
    """Data access for Attendance domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
