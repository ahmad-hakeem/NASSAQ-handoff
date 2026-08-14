"""
Shared helper for seed scripts to use PostgreSQL via repository layer.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from db import async_session_factory
from src.core.database.repository import Repos

_seed_repos = Repos()


class PgSeedContext:
    def __init__(self):
        self.session = None

    async def __aenter__(self):
        self.session = async_session_factory()
        s = await self.session.__aenter__()
        _seed_repos.set_session(s)
        return _seed_repos

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.session.__aexit__(exc_type, exc_val, exc_tb)
        else:
            s = _seed_repos._get_session()
            await s.commit()
            await self.session.__aexit__(None, None, None)
        _seed_repos.set_session(None)


def get_seed_db():
    return PgSeedContext()
