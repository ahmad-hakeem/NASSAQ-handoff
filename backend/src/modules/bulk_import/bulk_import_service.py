"""
BulkImport Service
= NestJS @Injectable()

Business logic for BulkImport.
Engines used:
    - engines/export_engine.py
"""
import logging

logger = logging.getLogger("nassaq")


class BulkImportService:
    """
    BulkImport service — business logic layer.

    Source engines to migrate here:
    - engines/export_engine.py
    """

    def __init__(self):
        # Engine imports will be injected here during Phase 4
    # from engines.export_engine import ...
        pass
