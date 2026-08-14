"""
AI (Hakim) Repository
= NestJS @InjectRepository()

Database access layer for AI (Hakim).
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class AIRepository:
    """Data access for AI (Hakim) domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
