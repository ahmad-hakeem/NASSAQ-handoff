"""
NASSAQ Database Index Management
Indexes are now managed via SQLAlchemy ORM models (pg_models.py)
and applied through Alembic migrations.
"""
import logging

logger = logging.getLogger("nassaq.indexes")


async def create_indexes():
    logger.info("Indexes managed via SQLAlchemy ORM + Alembic migrations")
