# External import API

All routes use the existing `/bulk` prefix and authentication/school scope.

- `POST /bulk/preview/{students|teachers}`: multipart `file`, optional `supersedes_draft_id`. Returns `draft_id`, `fingerprint` (SHA-256 of exact bytes), `preview_version`, `expires_at`, `import_type`, `rows`, `summary`, `errors`, `warnings`, `can_confirm`.
- Rows contain `row`, `name`, `action`, normalized identity/contact/grade/class/parent fields, `errors`, `warnings`, and `relationships`. Actions are student `create/update/restore`, teacher `create/conflict`, or `error`.
- `POST /bulk/confirm`: JSON **only** `draft_id`, `fingerprint`, `preview_version`, `acknowledged: true`. Returns the existing bulk result including `errors`, `warnings`, batch/ownership identifiers. No client rows accepted.
- `POST /bulk/draft/{draft_id}/discard`: invalidates the actor/school-owned draft.
- Legacy `POST /bulk/import/students` and `/teachers` reject with 409 `preview_required`.

Blocking errors anywhere disable the entire confirmation. Stale plans require a fresh preview (409); expired/cancelled/superseded/foreign drafts are unavailable (409). Preview never writes domain records. Drafts expire after 30 minutes. Selection/type/context changes must discard the old draft and suppress late responses. Confirm must explicitly acknowledge that records and relationships will be created/updated.

## Exact response fields

`rows[]`: `row` (spreadsheet row, header=1), `name`, `action`, `errors[]`, `warnings[]`.
Valid student rows additionally expose `full_name`, `national_id`, `grade` (canonical object with `grade`/`label_ar`), `raw_class_name`, `section`, `parent_name`, `parent_phone`, `parent_email`, `optional_values`, and `relationships`.
Valid teacher rows expose `full_name`, `email`, `phone`, `national_id`, `gender`, `specialization`, `qualification`, `experience_years`, `subjects`, `grades`, `hire_date`, `notes`.
Errors have `row`, `field`, `message`; invalid rows can lack normalized optional fields.

`relationships` has `grade`, `class`, `parent`, `parent_account`, `assignment`, `guardian_link`; each has `action` and deterministic resource `key`. Keys starting with `new:` represent not-yet-created resources. Class relationships additionally expose `restore` and `repair_grade_link` when reusing a persisted class.

`summary` has `total_rows`, `blocking_errors`, `error_rows`, `warnings`, action counters (`create`, `update`, `restore`, `conflict`, `error`, omitted when zero), `grade_create`, `grade_reuse`, `class_create`, `class_reuse`, `parent_create`, `parent_reuse`, `parent_account_create`, `parent_account_reuse`, `assignments`, `guardian_links`. Resource counts count distinct resources; action counters count rows. All resource/count keys other than action counters are always present.

Errors follow the application error envelope (`error.code`, `error.message`, possibly `error.detail`). Validation failures for malformed request bodies return 422. Invalid file content returns 400. Confirmation rejections return 409.

Storage uses the existing `generic_documents` table with collection `external_import_drafts`, not a new table and not the optional physical Noor draft table. No migration is required. Atomic transaction locks protect consumption and revalidation. Successful previews automatically supersede all earlier live external drafts for that actor/school.

## Direct-caller inventory

- Main school external card: `UsersClassesManagement.jsx` (must use preview/confirm).
- Additional legacy caller: `SettingsModals.jsx` bulk upload modal. Student/teacher submissions now explicitly receive `preview_required`; unrelated configured import types retain their routes. It must direct users to the review card or adopt this API, never silently import.
- Live browser scripts: `frontend/e2e/open-ended-class-live.spec.ts`, `frontend/e2e/principal-import-live.spec.ts`.
- Legacy integration scripts/tests: `tests/test_open_ended_class_rosters_live.py`, `backend/tests/test_students_bulk_operations.py`, `backend/tests/test_bulk_import_export.py`, `backend/tests/test_bulk_student_import_atomic.py`. Direct-upload success assertions must be migrated to preview/confirm; mixed-invalid partial-success assertions are obsolete under the selected blocking policy.