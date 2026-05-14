"""
Server-side draft store for the Noor importer.

Persists the normalized preview as a single row in `noor_import_drafts`
keyed by a random UUID. /commit reads the rows back from this store —
NEVER from a client-supplied `rows[]` array. The draft is principal-bound
(`principal_id`) and tenant-bound (`school_id`) and TTL'd to one hour.
"""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)

DRAFT_TTL_SECONDS = 3600  # 1 hour


async def create_draft(
    session,
    *,
    principal_id: str,
    school_id: str,
    detected_type: str,
    header_row: int,
    sheet_name: Optional[str],
    mapped_columns: Dict[str, str],
    rows: list,
    counts: Dict[str, int],
) -> str:
    draft_id = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=DRAFT_TTL_SECONDS)
    payload = {
        "rows": rows,
        "mapped_columns": mapped_columns,
        "sheet_name": sheet_name,
    }
    await session.execute(
        text(
            """
            INSERT INTO noor_import_drafts
                (id, principal_id, school_id, detected_type, header_row,
                 payload, counts, created_at, expires_at)
            VALUES
                (:id, :pid, :sid, :dt, :hr,
                 CAST(:payload AS JSONB), CAST(:counts AS JSONB),
                 :now, :exp)
            """
        ),
        {
            "id": draft_id,
            "pid": principal_id,
            "sid": school_id,
            "dt": detected_type,
            "hr": header_row,
            "payload": json.dumps(payload, ensure_ascii=False),
            "counts": json.dumps(counts, ensure_ascii=False),
            "now": now,
            "exp": expires_at,
        },
    )
    return draft_id


async def load_draft(
    session, *, draft_id: str, principal_id: str, school_id: str
) -> Optional[Dict[str, Any]]:
    """
    Returns the draft only when ALL three checks pass:
      • id matches
      • principal_id matches
      • school_id matches
      • expires_at > now
    Any miss returns None — the route surfaces a safe 403.
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        text(
            """
            SELECT id, principal_id, school_id, detected_type, header_row,
                   payload, counts, created_at, expires_at
            FROM noor_import_drafts
            WHERE id = :id
              AND principal_id = :pid
              AND school_id = :sid
              AND expires_at > :now
            LIMIT 1
            """
        ),
        {"id": draft_id, "pid": principal_id, "sid": school_id, "now": now},
    )
    row = result.mappings().first()
    if not row:
        return None
    return dict(row)


async def delete_draft(session, *, draft_id: str) -> None:
    await session.execute(
        text("DELETE FROM noor_import_drafts WHERE id = :id"),
        {"id": draft_id},
    )


async def purge_expired(session) -> int:
    """Best-effort housekeeping; safe to call from any request path."""
    try:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            text("DELETE FROM noor_import_drafts WHERE expires_at <= :now"),
            {"now": now},
        )
        return result.rowcount or 0
    except Exception as e:  # noqa: BLE001
        logger.debug("noor draft purge skipped: %s", e)
        return 0
