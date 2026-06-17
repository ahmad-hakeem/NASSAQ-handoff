# Product Hub — Edit Challenge API Reference

## Overview

The Product Hub is a **platform-wide** governance surface. Issues (`product_issues`) are not scoped to any particular school; they are created by any authenticated user and managed exclusively by `platform_admin` role holders. There is no `school_id` column on `product_issues`, so "cross-tenant isolation" is enforced by the role gate, not by a field-level comparison.

---

## PATCH `/api/product-hub/issues/{issue_id}`

### Purpose
Update one or more editable fields of an existing issue and write an immutable version row for full audit history.

### RBAC
| Caller role | Result |
|---|---|
| `platform_admin` with `UPDATE_ISSUE` permission | 200 OK |
| Any other role | 403 FORBIDDEN |
| Issue not found or soft-deleted | 404 NOT_FOUND |
| Tenant mismatch (future: if issue gains a tenant_id) | 404 NOT_FOUND |

### Editable fields (IssueUpdate schema)
| Field | Type | Notes |
|---|---|---|
| `title` | string | 1–300 chars, stripped |
| `current_behavior` | string | stripped |
| `expected_behavior` | string | stripped |
| `steps_to_reproduce` | string | stripped |
| `error_message` | string | stripped |
| `additional_details` | string | stripped |
| `reproducibility` | string | stripped |
| `impact` | list | JSONB array |
| `related_to` | string | stored under `technical.related_to` |

Sending a request with no editable changes returns 422 `NO_CHANGES`.

### IssueVersion row written on edit
Every PATCH that modifies at least one tracked field writes a row to `issue_versions`:

| Column | Type | Notes |
|---|---|---|
| `id` | varchar PK | UUID |
| `issue_id` | varchar FK→product_issues.id | CASCADE on delete |
| `revision` | integer NOT NULL | Sequential per issue; `SELECT MAX(revision)+1` within same txn; UNIQUE (issue_id, revision) |
| `tenant_id` | varchar nullable | Populated from editor's `tenant_id`/`school_id`; NULL for platform admins (platform-wide resource) |
| `changed_by_user_id` | varchar FK→users.id | SET NULL on delete |
| `changed_by_name` | varchar | Snapshot of editor's name |
| `changed_at` | timestamptz | UTC timestamp of edit |
| `changed_fields` | jsonb | Array of field names that changed |
| `previous_values` | jsonb | Snapshot of old values for tracked fields |
| `new_values` | jsonb | Snapshot of new values for tracked fields |

Tracked fields (versioned): `title`, `current_behavior`, `expected_behavior`, `steps_to_reproduce`, `error_message`, `additional_details`, `reproducibility`, `impact`.

### Response (200)
```json
{ "success": true, "updated_fields": ["title", "updated_at", "system.updated_at"] }
```

---

## GET `/api/product-hub/issues/{issue_id}/versions`

### Purpose
Retrieve the paginated edit history for an issue, newest-first by revision number.

### RBAC
Same as PATCH — `platform_admin` only; 403 for other roles, 404 if issue absent.

### Query params
| Param | Default | Max |
|---|---|---|
| `skip` | 0 | — |
| `limit` | 50 | 200 |

### Response (200)
```json
{
  "versions": [
    {
      "id": "...",
      "issue_id": "...",
      "revision": 5,
      "tenant_id": null,
      "changed_by_user_id": "...",
      "changed_by_name": "Dr. Ahmad Zalat",
      "changed_at": "2026-06-17T20:30:00+00:00",
      "changed_fields": ["title"],
      "previous_values": {"title": "old title"},
      "new_values": {"title": "new title"}
    }
  ],
  "total": 5,
  "skip": 0,
  "limit": 50,
  "issue_id": "..."
}
```

### Revert
The frontend sends a PATCH with `previous_values` from any older version to revert. Only `platform_admin` may revert (same gate as regular edit). Reverting creates a new version row rather than deleting the history.

---

## POST `/api/product-hub/issues/bulk-update`

### Purpose
Apply status, priority, or team assignment to multiple issues in a single operation.

### RBAC
`main_admin` only (stricter subset of platform_admin).

### Pre-write guards (422 path)
1. At least one of `status`, `priority`, `assigned_team` must be provided.
2. `status` value, if provided, must be a member of `IssueStatus` enum — validated by both Pydantic and explicit endpoint-level check.
3. `priority` value, if provided, must be a member of `IssuePriority` enum — same dual validation.
4. All `issue_ids` must resolve to existing, non-deleted issues — returns `ISSUES_NOT_FOUND` with `missing_ids` if any are absent.

### Response (200)
```json
{
  "success": true,
  "modified_count": 3,
  "requested_count": 3,
  "action_id": "..."
}
```

---

## Database schema (issue_versions)

```sql
CREATE TABLE issue_versions (
    id             VARCHAR PRIMARY KEY,
    issue_id       VARCHAR NOT NULL REFERENCES product_issues(id) ON DELETE CASCADE,
    revision       INTEGER NOT NULL,
    tenant_id      VARCHAR,
    changed_by_user_id  VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    changed_by_name     VARCHAR,
    changed_at     TIMESTAMPTZ DEFAULT NOW(),
    changed_fields JSONB DEFAULT '[]',
    previous_values JSONB DEFAULT '{}',
    new_values     JSONB DEFAULT '{}',
    CONSTRAINT uq_issue_versions_issue_revision UNIQUE (issue_id, revision)
);
CREATE INDEX idx_pg_versions_issue_time   ON issue_versions (issue_id, changed_at);
CREATE INDEX idx_pg_versions_issue_tenant ON issue_versions (issue_id, tenant_id);
```

Alembic revisions that created this table:
- `z4c5d6e7f8g9` — initial `issue_versions` table
- `z5d6e7f8g9h0` — merge head
- `z6e7f8g9h0i1` — added `revision` + `school_id`, backfill, unique constraint
- `z7f8g9h0i1j2` — renamed `school_id` → `tenant_id`, composite index `(issue_id, tenant_id)`
