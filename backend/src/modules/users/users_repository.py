"""
Users Repository
= NestJS @InjectRepository()

Database access layer for Users.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class UsersRepository:
    """Data access for Users domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
