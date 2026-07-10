# Parent Communication Center — Child-First Messaging (2026-07-10)

## Objective
Multi-child parents must select the child FIRST; the teacher list then narrows to
that child's teachers; the stored message + the recipient's notification carry the
student name, the message type, and the full body. Child selection is REQUIRED for
BOTH recipient types (teacher AND administration) — user decision 2026-07-10.

## Problems fixed
1. No child selection step — teacher dropdown is a flat union across all children.
2. `POST /parent-portal/quick-message` carries no student identity; the stored
   message has no `student_name` (the parent inbox read model already returns the
   field, it is just never written).
3. The recipient NEVER sees the message body today: the message row has no
   `audience`, so `/communication/received` skips it, and the notification's
   `message` is only the subject line.

## Backend changes (`backend/routes/parent_portal_routes.py`)
### `_resolve_parent_teacher_recipients`
- Track children as `(student_id, label)` per class (not labels only).
- Each teacher entry gains `child_ids: [student_id, …]` alongside `child_labels`.
- Returns `{"teachers": [...], "children": [{"student_id", "name"}]}` where
  `children` is ALL tenant-scoped children of the parent (even without a class —
  needed for the admin flow).
- `GET /message-recipients/teachers` returns that dict (additive: `teachers` key
  unchanged in shape apart from the new `child_ids` field).

### `POST /quick-message`
- New REQUIRED field `student_id` (400 «يرجى تحديد الطالب المعني بالرسالة» when missing).
- Validate the student is one of the parent's tenant-scoped children — else 400
  «الطالب المحدد غير متاح» (fail closed, no existence disclosure).
- Teacher recipient: teacher must be allowed AND `student_id` must be in that
  teacher's `child_ids` (teacher actually teaches THAT child) — else the existing
  400 «المعلم المحدد غير متاح للمراسلة».
- Subject becomes `{نوع} من ولي الأمر {الاسم} بخصوص الطالب {اسم الطالب}`.
- Message row additions: `student_id`, `student_name`, `title` (=subject, the
  admin inbox renders `msg.title`), `audience: "custom"`,
  `audience_ids: [receiver_id]`, `sent_at` — the last three make the row appear
  in `/communication/received` (custom-audience branch, post-filtered by
  `user_id in audience_ids`) and pass the mark-read authz.
- Notification: `title` = subject (type + parent + student), `message` = full
  body content (teacher reads it in NotificationDetailDialog).

## Frontend changes (`frontend/src/pages/ParentPortal/ParentCommunicationCenter.jsx`)
- Child selector step rendered BEFORE the recipient/teacher step, fed from the
  recipients endpoint's `children` list; auto-selected when exactly one child;
  required for both recipient types (send disabled without it).
- Teacher dropdown filtered by `child_ids.includes(selectedStudentId)`; selected
  teacher resets when the child changes.
- Parent inbox: show a «بخصوص: {student_name}» badge when present.
- i18n keys added to `ar.json` / `en.json`.

## Out of scope
- Absence excuses, meeting requests, admin→parent messaging, broadcast flows.
- Teacher communication page redesign (teachers read via the notification dialog;
  the message row is now also inbox-visible for any receiver_id-holder surface).

## Invariants preserved
- Recipient resolver stays anchored to the single latest PUBLISHED timetable
  (docs/qa/2026-05-31-parent-dropdowns-audit.md Finding 1).
- All errors are safe Arabic strings; tenant scoping fail-closed.
