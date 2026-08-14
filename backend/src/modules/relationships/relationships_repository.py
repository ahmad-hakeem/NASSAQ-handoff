"""
Relationships Repository
= NestJS @InjectRepository()

Database access layer for Relationships.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class RelationshipsRepository:
    """Data access for Relationships domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
