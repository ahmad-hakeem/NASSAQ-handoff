"""
Behaviour Repository
= NestJS @InjectRepository()

Database access layer for Behaviour.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class BehaviourRepository:
    """Data access for Behaviour domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
