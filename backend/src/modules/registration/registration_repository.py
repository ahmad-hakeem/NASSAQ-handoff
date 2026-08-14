"""
Registration Repository
= NestJS @InjectRepository()

Database access layer for Registration.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class RegistrationRepository:
    """Data access for Registration domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
