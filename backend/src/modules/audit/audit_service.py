"""
Audit Service
= NestJS @Injectable()

Business logic for Audit.
Engines used:
    - engines/audit_engine.py
    - engines/audit_sink.py
"""
import logging

logger = logging.getLogger("nassaq")


class AuditService:
    """
    Audit service — business logic layer.

    Source engines to migrate here:
    - engines/audit_engine.py
    - engines/audit_sink.py
    """

    def __init__(self):
        # Engine imports will be injected here during Phase 4
    # from engines.audit_engine import ...
    # from engines.audit_sink import ...
        pass
