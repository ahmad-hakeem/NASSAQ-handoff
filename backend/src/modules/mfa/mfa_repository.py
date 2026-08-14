"""
MFA Repository
= NestJS @InjectRepository()

Database access layer for MFA.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class MFARepository:
    """Data access for MFA domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
