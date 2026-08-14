"""
Auth Repository
= NestJS @InjectRepository()

Database access layer for Auth.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class AuthRepository:
    """Data access for Auth domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
