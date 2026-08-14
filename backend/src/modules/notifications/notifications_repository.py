"""
Notifications Repository
= NestJS @InjectRepository()

Database access layer for Notifications.
Contains raw SQL / SQLAlchemy queries extracted from engines.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("nassaq")


class NotificationsRepository:
    """Data access for Notifications domain."""

    def __init__(self, session: AsyncSession):
        self.session = session
