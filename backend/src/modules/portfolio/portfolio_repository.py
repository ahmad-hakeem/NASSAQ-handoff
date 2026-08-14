"""
Portfolio Repository
= NestJS @InjectRepository()

Database access layer for Portfolio.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class PortfolioRepository:
    """Data access for Portfolio domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
