"""
NASSAQ — In-memory cache hit/miss tracking.

Provides ``record_hit()``, ``record_miss()``, and ``get_cache_metrics()``
for exposing cache effectiveness in ``/system/health``.
"""
import threading
from typing import Dict, Any

_lock = threading.Lock()
_hits: int = 0
_misses: int = 0


def record_hit() -> None:
    """Record a cache hit."""
    global _hits
    with _lock:
        _hits += 1


def record_miss() -> None:
    """Record a cache miss."""
    global _misses
    with _lock:
        _misses += 1


def get_cache_metrics() -> Dict[str, Any]:
    """Return cache hit/miss/rate metrics."""
    with _lock:
        total = _hits + _misses
        rate = round(_hits / total * 100, 1) if total > 0 else 0.0
        return {
            "hits": _hits,
            "misses": _misses,
            "total": total,
            "hit_rate_percent": rate,
        }
