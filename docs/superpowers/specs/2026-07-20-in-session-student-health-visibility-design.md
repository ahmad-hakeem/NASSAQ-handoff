# In-Session Student Health Visibility — Design

Date: 2026-07-20
Scope approved by user: health issues **and** behavioral/learning aspects. Family
situation is excluded (never shown to teachers).

## Problem

During a live session (SessionTeachPage, shared by School Teacher and
Independent Teacher), teachers cannot see whether a student has recorded
health issues. The data exists but is never surfaced:

- `students.health_info` (JSONB) — medical record written by school admins /
  ITs / platform admins via `PUT /students/{id}` and the student wizard:
  blood_type, chronic_conditions, allergies, disabilities,
  current_medications, special_care_notes, emergency_medical_notes (flag +
  text pairs).
- `students.profile_settings` (JSONB) — the parent-portal "ملف الطالب":
  `health_conditions[]` (vocab: seasonal_allergy, nut_allergy, dust_allergy,
  asthma, diabetes, epilepsy, weak_vision, weak_hearing, food_allergy),
  `other_health_details`, `behavioral_aspects[]`, `other_behavior_details`,
  plus family fields (excluded).

Existing dead code: `StudentRow` / `SessionStartPage` already render
`HEALTH_BADGES` from `student.health_conditions` — but the session roster
serializer (`session_engine.get_session_students`) never returns that field,
and the badge vocabulary (`vision`, `allergy`, `special_needs`…) does not
match the stored vocabulary (`weak_vision`, `nut_allergy`…). Two locale keys
referenced by the badges (`healthBadgeEpilepsy`, `healthBadgeSpecialNeeds`)
are missing from both locale files.

## Design

### Backend

1. **New helper `backend/utils/student_health.py`** — single source of truth
   for merging both JSONBs into a teacher-facing view:
   - `summarize_student_health(student)` → roster-safe summary:
     `{health_conditions: [chip keys], behavioral_aspects: [chip keys],
     has_health_alert: bool, has_behavior_alert: bool}`. No free text in the
     roster payload. Malformed values coerce safely (non-list → empty,
     non-str entries dropped).
   - `build_student_health_detail(student)` → full read-only detail for the
     dialog: health chips + other_details + gated medical fields
     (flagged pairs included only when the flag is truthy AND text is
     non-empty; unflagged fields — blood_type, current_medications,
     emergency_medical_notes — included when non-empty), behavior chips +
     other_details, and `has_any`. Never includes family_situation,
     family_other_situations, emoji, guardian/contact data.

2. **Roster serializer** (`get_session_students` in
   `backend/engines/session_engine.py`): merge the summary fields into each
   student dict. This feeds both SessionTeachPage and SessionStartPage
   (they share `GET /session/{id}/students`).

3. **New endpoint** `GET /session/{session_id}/students/{student_id}/health`
   in `backend/routes/role_dashboards_mod.py`:
   - `await _verify_session_owner(session_id, current_user)` (same guard as
     every other in-session route; IT + school teacher both pass as owners,
     cross-tenant → 404 per §8 invariant 3).
   - Student must belong to the session's class and be active, else 404 —
     prevents using a session as a pivot to read other classes' students.
   - Returns `build_student_health_detail(...)` — fetched fresh on every
     dialog open, so the teacher always sees the latest saved data.

### Frontend

1. **Shared badge config `frontend/src/config/healthBadges.js`** with the
   REAL stored vocabulary (all 9 parent chips + legacy keys kept for
   compatibility), lucide icons, and i18n label keys. Missing locale keys
   added to `ar.json` / `en.json`. `SessionTeachPage` and `SessionStartPage`
   both import it (removes the duplicated, wrong maps).
2. **StudentRow**: existing chips now render (data + vocab fixed). New
   compact health-alert button (HeartPulse, rose) shown ONLY when
   `has_health_alert || has_behavior_alert`; click (stopPropagation) opens
   the detail dialog. Healthy students show nothing.
3. **New `StudentHealthDialog.jsx`** (TeacherModule): read-only Radix dialog,
   fetches the detail endpoint on open, sections: المشاكل الصحية (chips +
   أخرى + medical record rows), الجوانب السلوكية والتعلم (chips + أخرى).
   Loading skeleton, Arabic error state, clean empty state. RTL logical
   props, lucide strokeWidth 1.5, no raw hex, font-cairo.
4. Wire-up in SessionTeachPage: `loadStudents` passes the new fields
   through; one dialog instance at page level.

### Freshness

- Roster flags refresh with every roster load (page load, تحديث button,
  post-interaction refreshes).
- Detail dialog re-fetches on every open — never cached, never stale.

### Testing

- BE `backend/tests/test_session_student_health.py`: helper merge/coercion
  cases; endpoint — owner OK + merged shape, no family keys; foreign-tenant
  teacher 404; same-tenant non-owner teacher 403; student outside session
  class 404; IT workspace session works; malformed JSONB does not 500.
- FE test: indicator renders only for flagged students; click opens dialog;
  dialog shows fetched sections; healthy student → no indicator.
- Live Playwright QA as school teacher and IT.
