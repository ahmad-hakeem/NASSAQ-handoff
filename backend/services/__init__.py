"""
NASSAQ - Services Package
Central export for all service modules
"""

from .auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    create_get_current_user,
    require_roles_factory,
    generate_temp_password,
    security,
    JWT_SECRET,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE,
)

from .database_service import (
    get_database,
    get_client,
    close_database,
    serialize_doc,
    serialize_docs,
    create_indexes,
)

from .audit_service import (
    log_action,
    log_user_action,
    get_audit_logs,
)

# Re-export scheduling service
from .scheduling_service import *

__all__ = [
    # Auth
    "hash_password",
    "verify_password", 
    "create_access_token",
    "decode_token",
    "create_get_current_user",
    "require_roles_factory",
    "generate_temp_password",
    "security",
    "JWT_SECRET",
    "JWT_ALGORITHM",
    "ACCESS_TOKEN_EXPIRE",
    # Database
    "get_database",
    "get_client",
    "close_database",
    "serialize_doc",
    "serialize_docs",
    "create_indexes",
    # Audit
    "log_action",
    "log_user_action",
    "get_audit_logs",
]
