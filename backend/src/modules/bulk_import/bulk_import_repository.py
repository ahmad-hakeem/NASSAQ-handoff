"""
BulkImport Repository
= NestJS @InjectRepository()

Database access layer for BulkImport.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class BulkImportRepository:
    """Data access for BulkImport domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
