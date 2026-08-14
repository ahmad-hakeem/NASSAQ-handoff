"""Shim forwarding to src.core.database.db"""
from src.core.database.db import *  # noqa: F401, F403
import src.core.database.db as _src_mod
for _k, _v in _src_mod.__dict__.items():
    if not _k.startswith('__'):
        globals()[_k] = _v
