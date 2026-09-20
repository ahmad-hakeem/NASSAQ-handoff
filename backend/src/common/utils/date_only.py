"""Shared validation for optional Gregorian date-only values."""

import re
from datetime import date, datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo


_STRICT_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SAUDI_TIMEZONE = ZoneInfo("Asia/Riyadh")


def saudi_today() -> date:
    """Return the calendar day in Saudi Arabia, independent of server timezone."""
    return datetime.now(_SAUDI_TIMEZONE).date()


def normalize_optional_past_date(
    value: Any, *, today: Optional[date] = None
) -> Optional[str]:
    """Normalize an optional strict Gregorian YYYY-MM-DD value.

    Null and whitespace-only strings become ``None``. Non-string, malformed,
    impossible, and future values are rejected. The canonical return value is
    always the original strict ISO date string.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("date must use YYYY-MM-DD format")
    if not value.strip():
        return None
    if not _STRICT_DATE_ONLY.fullmatch(value):
        raise ValueError("date must use YYYY-MM-DD format")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must be a valid Gregorian date") from exc
    if parsed > (today if today is not None else saudi_today()):
        raise ValueError("date must not be in the future")
    return value