"""
ConsentPrivacy Repository
= NestJS @InjectRepository()

Database access layer for ConsentPrivacy.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class ConsentPrivacyRepository:
    """Data access for ConsentPrivacy domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
