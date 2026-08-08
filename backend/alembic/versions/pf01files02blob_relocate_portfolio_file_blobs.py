"""Relocate inline portfolio attachment blobs into portfolio_files documents.

Evidence rows (portfolio_evidence) and CV items (teacher_portfolio_meta.cv_items)
used to store uploaded files inline as base64 data URLs. Every portfolio page
load re-downloaded all stored bytes (measured 11.5 MB / ~4 s for one teacher),
and every small meta edit read-modify-wrote the whole multi-MB document.

This migration moves each inline blob to its own generic document in the
`portfolio_files` collection and leaves a light `file_id` pointer behind.
The API fetches file bytes on demand via GET /teacher/portfolio/file/{file_id}.

Revision ID: pf01files02blob
Revises: tj01runs02data
Create Date: 2026-08-01
"""
import json
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "pf01files02blob"
down_revision = "tj01runs02data"
branch_labels = None
depends_on = None


def _mime(data_url: str) -> str:
    head = data_url.split(",", 1)[0]
    if head.startswith("data:"):
        return head[5:].split(";", 1)[0] or "application/octet-stream"
    return "application/octet-stream"


def _size(data_url: str) -> int:
    try:
        payload = data_url.split(",", 1)[1]
    except IndexError:
        return 0
    if ";base64" in data_url.split(",", 1)[0]:
        return (len(payload) * 3) // 4
    return len(payload)


def _store_file(conn, teacher_id, school_id, data_url, file_name):
    file_id = str(uuid.uuid4())
    doc = {
        "teacher_id": teacher_id or "",
        "school_id": school_id or "",
        "file_name": file_name or "",
        "content_type": _mime(data_url),
        "size_bytes": _size(data_url),
        "data_url": data_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    conn.execute(
        sa.text(
            "INSERT INTO generic_documents (id, collection, data, created_at) "
            "VALUES (:id, 'portfolio_files', CAST(:data AS jsonb), now())"
        ),
        {"id": file_id, "data": json.dumps(doc)},
    )
    return file_id


def upgrade():
    conn = op.get_bind()

    # 1) Evidence rows with inline data-URL attachments.
    rows = conn.execute(
        sa.text(
            "SELECT id, data FROM generic_documents "
            "WHERE collection = 'portfolio_evidence' AND data->>'file_url' LIKE :pat"
        ),
        {"pat": "data:%"},
    ).fetchall()
    for rid, data in rows:
        d = dict(data)
        file_id = _store_file(
            conn,
            d.get("teacher_id"),
            d.get("school_id"),
            d["file_url"],
            d.get("file_name"),
        )
        conn.execute(
            sa.text(
                "UPDATE generic_documents "
                "SET data = data || CAST(:patch AS jsonb) WHERE id = :rid"
            ),
            {"rid": rid, "patch": json.dumps({"file_url": None, "file_id": file_id})},
        )

    # 2) CV items inside teacher_portfolio_meta docs (one doc per teacher).
    rows = conn.execute(
        sa.text(
            "SELECT id, data FROM generic_documents "
            "WHERE collection = 'teacher_portfolio_meta'"
        )
    ).fetchall()
    for rid, data in rows:
        d = dict(data)
        items = d.get("cv_items") or []
        changed = False
        for it in items:
            fu = it.get("file_url")
            if isinstance(fu, str) and fu.startswith("data:"):
                fid = _store_file(
                    conn, d.get("teacher_id"), d.get("school_id"), fu, it.get("file_name")
                )
                it["file_url"] = None
                it["file_id"] = fid
                changed = True
        if changed:
            conn.execute(
                sa.text(
                    "UPDATE generic_documents "
                    "SET data = jsonb_set(data, '{cv_items}', CAST(:items AS jsonb)) "
                    "WHERE id = :rid"
                ),
                {"rid": rid, "items": json.dumps(items)},
            )


def downgrade():
    # Intentionally a no-op: the application reads both shapes (file_id pointer
    # and legacy inline file_url), and moving blobs back inline would recreate
    # the payload problem this migration fixes.
    pass
