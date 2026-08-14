"""
Communication Repository
= NestJS @InjectRepository()

Database access layer for Communication.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class CommunicationRepository:
    """Data access for Communication domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
