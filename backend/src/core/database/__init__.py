"""
src/core/database — Database layer.
Re-exports all public symbols from db.py and repository.py.
"""
from src.core.database.db import (  # noqa: F401
    Base,
    engine,
    async_session_factory,
    get_pg_session,
    get_db,
    get_sync_engine,
    init_pg_tables,
    is_replit_managed_deployment,
    schema_verification_is_fatal,
    expected_schema_contracts,
    verify_physical_schema,
    close_pg_engine,
    ensure_runtime_sequences,
    get_alembic_head_revision,
)
from src.core.database.repository import (  # noqa: F401
    Repos,
    get_repos,
)
