"""Unit coverage for the read-only school lifecycle data audit."""

import json
import stat

from scripts.audit_school_lifecycle import (
    ALLOWED_STATUSES,
    audit_rows,
    write_ambiguous_report,
)


def test_audit_rows_counts_statuses_and_flags_lifecycle_contradictions():
    rows = [
        {
            "id": "active-ok",
            "status": "active",
            "tenant_type": "production",
            "archived_at": None,
            "pending_hard_delete": False,
        },
        {
            "id": "missing",
            "status": None,
            "tenant_type": "production",
            "archived_at": None,
            "pending_hard_delete": False,
        },
        {
            "id": "unknown",
            "status": "paused",
            "tenant_type": "production",
            "archived_at": None,
            "pending_hard_delete": False,
        },
        {
            "id": "archive-without-date",
            "status": "archived",
            "tenant_type": "independent_teacher",
            "archived_at": None,
            "pending_hard_delete": False,
        },
        {
            "id": "active-with-archive-date",
            "status": "active",
            "tenant_type": "production",
            "archived_at": "2026-01-01T00:00:00+00:00",
            "pending_hard_delete": False,
        },
        {
            "id": "delete-mismatch",
            "status": "active",
            "tenant_type": "independent_teacher",
            "archived_at": None,
            "pending_hard_delete": True,
        },
    ]

    result = audit_rows(rows)

    assert ALLOWED_STATUSES == {
        "active",
        "suspended",
        "pending",
        "setup",
        "archived",
        "pending_hard_delete",
    }
    assert result["total_rows"] == 6
    assert result["status_counts"]["active"] == 3
    assert result["issue_counts"] == {
        "missing_status": 1,
        "unknown_status": 1,
        "archived_without_archived_at": 1,
        "archived_at_on_non_archived_status": 1,
        "pending_hard_delete_without_archived_state": 1,
    }
    assert {row["id"] for row in result["ambiguous_rows"]} == {
        "missing",
        "unknown",
        "archive-without-date",
        "active-with-archive-date",
        "delete-mismatch",
    }


def test_audit_reports_supported_but_noncanonical_stored_status_without_mutating_source():
    source = {
        "id": "school-1",
        "status": " Active ",
        "tenant_type": "production",
        "archived_at": None,
        "pending_hard_delete": False,
    }

    result = audit_rows([source])

    assert result["status_counts"] == {"active": 1}
    assert result["issue_counts"] == {"noncanonical_status": 1}
    assert result["ambiguous_rows"] == [
        {
            "id": "school-1",
            "status": " Active ",
            "tenant_type": "production",
            "archived_at": None,
            "pending_hard_delete": False,
            "issues": ["noncanonical_status"],
        }
    ]
    assert source["status"] == " Active "


def test_audit_does_not_flag_exact_canonical_status():
    result = audit_rows(
        [
            {
                "id": "school-1",
                "status": "active",
                "tenant_type": "production",
                "archived_at": None,
                "pending_hard_delete": False,
            }
        ]
    )

    assert result["issue_counts"] == {}
    assert result["ambiguous_rows"] == []


def test_ambiguous_report_contains_only_identifiers_and_lifecycle_fields(tmp_path):
    path = tmp_path / "school-lifecycle-audit.json"
    result = audit_rows(
        [
            {
                "id": "school-1",
                "status": "bogus",
                "tenant_type": "production",
                "archived_at": None,
                "pending_hard_delete": False,
                "name": "Must not leak",
                "email": "private@example.test",
            }
        ]
    )

    write_ambiguous_report(path, result)

    payload = json.loads(path.read_text())
    assert payload["ambiguous_rows"][0]["id"] == "school-1"
    assert "name" not in payload["ambiguous_rows"][0]
    assert "email" not in payload["ambiguous_rows"][0]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600