"""
Portals Repository
= NestJS @InjectRepository()

Database access layer for Portals.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class PortalsRepository:
    """Data access for Portals domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
