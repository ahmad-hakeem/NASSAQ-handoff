"""
Reporting Repository
= NestJS @InjectRepository()

Database access layer for Reporting.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class ReportingRepository:
    """Data access for Reporting domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
