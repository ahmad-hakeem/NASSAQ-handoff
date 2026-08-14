"""
Schools Repository
= NestJS @InjectRepository()

Database access layer for Schools.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class SchoolsRepository:
    """Data access for Schools domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
