"""Bounded, read-only audit of canonical ``schools.status`` lifecycle data.

This command never changes school or user rows. It reports aggregate status and
contradiction counts. Raw school identifiers are only written when an explicit
local ``--report`` path is supplied; names and contact fields are never queried.

Run:
    cd backend
    python scripts/audit_school_lifecycle.py
    python scripts/audit_school_lifecycle.py --report /tmp/school-lifecycle.json
"""

import argparse
import asyncio
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ALLOWED_STATUSES = {
    "active",
    "suspended",
    "pending",
    "setup",
    "archived",
    "pending_hard_delete",
}
ARCHIVED_STATES = {"archived", "pending_hard_delete"}
DEFAULT_MAX_ROWS = 10_000


def _normalized_status(value):
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _lifecycle_projection(row):
    """Copy only non-PII lifecycle fields needed in an operator report."""
    return {
        "id": row.get("id"),
        "status": row.get("status"),
        "tenant_type": row.get("tenant_type"),
        "archived_at": (
            row.get("archived_at").isoformat()
            if hasattr(row.get("archived_at"), "isoformat")
            else row.get("archived_at")
        ),
        "pending_hard_delete": bool(row.get("pending_hard_delete")),
    }


def audit_rows(rows):
    """Classify an already bounded collection without mutating source rows."""
    status_counts = Counter()
    issue_counts = Counter()
    ambiguous_rows = []

    for source in rows:
        row = dict(source)
        raw_status = row.get("status")
        status = _normalized_status(raw_status)
        status_counts[status or "<null>"] += 1
        issues = []

        if status is None:
            issues.append("missing_status")
        elif status not in ALLOWED_STATUSES:
            issues.append("unknown_status")
        elif raw_status != status:
            # The API intentionally compares the stored lifecycle value exactly.
            # Values such as "ACTIVE" or " active " therefore render unknown and
            # must not disappear from the audit merely because they normalize.
            issues.append("noncanonical_status")

        archived_at = row.get("archived_at")
        pending_delete = bool(row.get("pending_hard_delete"))
        if status in ARCHIVED_STATES and not archived_at:
            issues.append("archived_without_archived_at")
        if archived_at and status not in ARCHIVED_STATES:
            issues.append("archived_at_on_non_archived_status")
        if pending_delete and status not in ARCHIVED_STATES:
            issues.append("pending_hard_delete_without_archived_state")

        if issues:
            issue_counts.update(issues)
            projected = _lifecycle_projection(row)
            projected["issues"] = issues
            ambiguous_rows.append(projected)

    return {
        "total_rows": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        "ambiguous_rows": ambiguous_rows,
    }


def write_ambiguous_report(path, result):
    """Atomically write a private report containing no school PII."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "total_rows": result["total_rows"],
        "status_counts": result["status_counts"],
        "issue_counts": result["issue_counts"],
        "ambiguous_rows": result["ambiguous_rows"],
    }
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        dir=str(destination.parent),
        text=True,
    )
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
            handle.write("\n")
        os.replace(temporary_name, destination)
        os.chmod(destination, 0o600)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


async def _connect():
    import asyncpg

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    parsed = urlparse(url)
    sslmode = parse_qs(parsed.query).get("sslmode", [None])[0]
    ssl_arg = "require" if sslmode and sslmode != "disable" else False
    return await asyncpg.connect(url, ssl=ssl_arg)


async def run(max_rows=DEFAULT_MAX_ROWS, report=None):
    """Run one bounded audit in a PostgreSQL read-only transaction."""
    connection = await _connect()
    try:
        async with connection.transaction(readonly=True):
            rows = await connection.fetch(
                """
                SELECT id, status, tenant_type, archived_at, pending_hard_delete
                  FROM schools
                 ORDER BY id
                 LIMIT $1
                """,
                max_rows + 1,
            )
    finally:
        await connection.close()

    truncated = len(rows) > max_rows
    bounded_rows = rows[:max_rows]
    result = audit_rows(bounded_rows)
    result["truncated"] = truncated

    print("School lifecycle audit (read-only)")
    print(f"Rows inspected: {result['total_rows']}")
    print(f"Bound reached: {'yes' if truncated else 'no'}")
    print("Status counts:")
    for status, count in result["status_counts"].items():
        print(f"  {status}: {count}")
    print("Issue counts:")
    if result["issue_counts"]:
        for issue, count in result["issue_counts"].items():
            print(f"  {issue}: {count}")
    else:
        print("  none")

    if report:
        write_ambiguous_report(report, result)
        print(f"Private identifier report written to: {report}")
    elif result["ambiguous_rows"]:
        print("Identifiers omitted; pass --report PATH for a private local report.")

    if truncated:
        print("ERROR: row bound reached; rerun with a larger --max-rows.", file=sys.stderr)
        return 2
    return 1 if result["ambiguous_rows"] else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-rows",
        type=int,
        default=DEFAULT_MAX_ROWS,
        help=f"Maximum schools to inspect (default: {DEFAULT_MAX_ROWS}).",
    )
    parser.add_argument(
        "--report",
        help="Optional private JSON path for ambiguous school IDs.",
    )
    args = parser.parse_args()
    if not 1 <= args.max_rows <= 100_000:
        parser.error("--max-rows must be between 1 and 100000")
    sys.exit(asyncio.run(run(max_rows=args.max_rows, report=args.report)))


if __name__ == "__main__":
    main()