"""
NoorImport Repository
= NestJS @InjectRepository()

Database access layer for NoorImport.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class NoorImportRepository:
    """Data access for NoorImport domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
