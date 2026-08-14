"""
Participation Repository
= NestJS @InjectRepository()

Database access layer for Participation.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class ParticipationRepository:
    """Data access for Participation domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
