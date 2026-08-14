"""
Audit Repository
= NestJS @InjectRepository()

Database access layer for Audit.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class AuditRepository:
    """Data access for Audit domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
