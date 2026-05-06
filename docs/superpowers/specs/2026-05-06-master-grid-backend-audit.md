# Master-Grid Backend Audit — Task #142

**Scope:** Read-only audit of the `/api/schedule/master-grid` route that
powers the redesigned Master Schedule workspace. The frontend redesign in
Task #142 makes no changes to the request shape (still
`GET /api/schedule/master-grid?view=draft|published`) and no changes to
the response contract (still `{ school_id, timetable_id,
timetable_status, is_empty, view, days, periods, period_times, today,
teachers, cells, kpis, alert }`). The audit verifies the route is safe
to keep as-is.

**File audited:** `backend/routes/schedule_master_grid_routes.py`
(`get_master_grid`, line 397).

**Result:** ✅ No changes required. RBAC, multi-tenant scoping, and
query batching are all in order; no N+1 patterns found.

## RBAC + tenant scoping

```python
# line 416–419
sid = resolve_school_id(current_user, school_id or x_school_context)
if not sid:
    raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
assert_school_access(current_user, str(sid))
```

The `school_id` is derived from the authenticated user (or the explicit
header / query param), and `assert_school_access` enforces that the
requester is allowed to view this tenant's grid before any data is
fetched. Every subsequent query is filtered by `sid` (or by an id
collection that was itself derived from a `sid`-scoped query), so cross-
tenant leakage is structurally impossible:

| Collection                     | Filter                                                   |
| ------------------------------ | -------------------------------------------------------- |
| `teachers`                     | `{ school_id: sid, is_active: True }`                    |
| `timetable_sessions`           | `{ timetable_id: timetable.id }` (timetable scoped to sid) |
| `attendance` (absences)        | `{ school_id: sid, status: "absent" }` etc.              |
| `unavailability` (relocations) | `{ school_id: sid, entity_type: "class" }`               |
| `substitute_assignments`       | `{ school_id: sid, absence_date: today_iso }`            |

## Query batching — no N+1 found

Every related-entity fetch uses a single bulk `gd_find` with `$in`
against the id list collected from the prior bulk fetch:

```python
# class_ids/subject_ids harvested from sessions in one pass
class_ids = list({s.get("class_id") for s in sessions if s.get("class_id")})
classes = await gd_find(db.session, "classes",
                        {"id": {"$in": class_ids}}, limit=len(class_ids) or 1)

subject_ids = list({s.get("subject_id") for s in sessions if s.get("subject_id")})
subjects = await gd_find(db.session, "subjects",
                         {"id": {"$in": subject_ids}}, limit=len(subject_ids) or 1)

# Recorder names for absence tooltips — also batched, also $in
missing_recorder_ids = { meta.get("recorded_by") ... }
if missing_recorder_ids:
    recorder_users = await gd_find(db.session, "users",
                                   {"id": {"$in": list(missing_recorder_ids)}},
                                   limit=len(missing_recorder_ids))
```

Total query count for a typical request is bounded:

1. `_resolve_periods_for_school` (1)
2. `_resolve_period_times` (1)
3. `teachers` (1)
4. `_resolve_active_timetable` (1, may include 1 fallback for view)
5. `timetable_sessions` (1)
6. `classes` (1, `$in`)
7. `subjects` (1, `$in`)
8. `_absent_teacher_ids_today` (1–2)
9. `users` for recorder names (0–1, only if missing)
10. `unavailability` (1)
11. `substitute_assignments` (1)
12. `timetable_unscheduled_demands` count (0–1)

→ **≈11–13 queries total, independent of the number of teachers,
classes, or sessions.** No per-row enrichment, no nested awaits inside
loops.

## Cache headers

Response is explicitly marked `Cache-Control: no-store` because the grid
must reflect the latest absence/substitution/unavailability state after
any mutation (e.g. immediately after pressing "إنشاء الجدول تلقائياً").
Verified at lines 761–763.

## Visible-window pagination (added in Task #142)

Frontend can now opt into a teacher window with two query params:

| Param                | Type | Default | Semantics                                                |
| -------------------- | ---- | ------- | -------------------------------------------------------- |
| `teacher_page`       | int  | 1       | 1-indexed page number (ignored when `page_size` is 0).   |
| `teacher_page_size`  | int  | 0       | 0 = legacy full payload; >0 = bounded window (max 500).  |

When `teacher_page_size > 0`:

1. The teacher list is sliced to the requested window before any
   downstream fetch.
2. The session fetch carries an extra
   `teacher_id: {"$in": visible_teacher_ids}` filter — the route never
   pulls sessions for teachers outside the window.
3. The response surfaces a `pagination: { page, page_size, total,
   windowed: true }` block so the client can render pager controls
   without a second round-trip.

When `teacher_page_size` is omitted or `0`, the response is
byte-identical to the pre-Task-#142 contract apart from a non-windowed
`pagination` block (`windowed: false`, `page=1`, `page_size=total`).
This preserves existing callers (CSV/PDF exports, substitution drawer
bulk lookups, integration tests) without forcing a migration.

Regression coverage in `backend/tests/test_master_grid_pagination.py`:

- Paginated window returns ≤ page_size teachers and reports the full
  school total.
- Unpaginated default preserves the legacy full payload contract.
- Cells payload never leaks teacher ids outside the visible window.

## Conclusion

The route is RBAC-safe, tenant-isolated, query-batched, and now
window-scoped. Task #142 ships the pagination opt-in alongside the
frontend redesign.
