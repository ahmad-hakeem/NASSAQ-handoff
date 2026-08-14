import contextvars
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from src.core.database.db import get_pg_session

_repos_session_var = contextvars.ContextVar('_repos_session', default=None)


class Repos:
    def __init__(self, session: AsyncSession = None):
        self._direct_session = session

    @property
    def session(self):
        return self._direct_session or _repos_session_var.get(None)

    @property
    def session_factory(self):
        from src.core.database.db import async_session_factory
        return async_session_factory

    def set_session(self, session):
        _repos_session_var.set(session)

    def _get_session(self):
        return self.session


async def get_repos(session: AsyncSession = Depends(get_pg_session)) -> Repos:
    return Repos(session)
