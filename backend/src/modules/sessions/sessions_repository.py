"""
Sessions Repository
= NestJS @InjectRepository()

Database access layer for Sessions.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class SessionsRepository:
    """Data access for Sessions domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
