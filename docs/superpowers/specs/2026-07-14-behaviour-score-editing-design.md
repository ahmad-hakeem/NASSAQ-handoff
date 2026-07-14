# Editable Behaviour Scores in Lesson Settings — Design

**Date:** 2026-07-14
**Status:** Approved (user selected Approach A; persistence scope: this lesson only)

## Problem

In Lesson Settings → السلوكيات, behaviour scores are fixed:

- Built-in behaviours (احترام، التزام، مساعدة الآخرين / إزعاج، عدم التزام، مقاطعة) are hardcoded
  constants (`BEHAVIOURS` in `SessionTeachPage.jsx`) rendered read-only; scores resolve
  server-side from default rules when recorded.
- Custom behaviours accept a score at creation but cannot be edited afterwards — only
  deleted and re-added.

Teachers need to edit the score of ANY listed behaviour (built-in or custom), and recording
that behaviour for a student must award the edited score. Applies to both School Teacher and
Independent Teacher (both render the same `SessionTeachPage`).

## Decision

**Approach A — mirror the Skills tab inline-edit pattern. Frontend only.**

Persistence scope (user decision): **this lesson only** — edits ride the existing
per-session `sessionStorage` state (`session_state_${sessionId}`) and reset next lesson.

Rejected alternatives:
- B: materialize built-ins into the custom arrays on edit — breaks labelKey localization,
  duplicates chip identity, changes delete semantics.
- C: persist per class+subject in the backend `session_settings` record — rejected by user
  (edits must reset next lesson).

## Design

### 1. `SidebarSettingsDialog.jsx` (السلوكيات tab)
- New optional prop `onUpdateBehaviourScore(category, id, magnitude)`. Callers that don't
  pass it (e.g. فصولي → تفاصيل الفصل) keep the read-only badge — backward compatible.
- New `behaviourEdit` state (`{key, value}`) + start/cancel/commit helpers, mirroring
  `skillEdit`. The points badge becomes tap-to-edit: pencil button → inline number input →
  Enter/✓ commits, Escape/✗ cancels.
- Validation at commit: integer magnitude 1–100 (matches backend `points_override`
  validation). Sign always derives from the group (positive/negative), never typed.
  Invalid input keeps the field open.

### 2. `SessionTeachPage.jsx`
- New state `behaviourScoreOverrides` — map of built-in behaviour id → magnitude.
  Included in the sessionStorage autosave blob and restore path (same lifecycle as
  `customPositiveBehaviours`).
- Accepted limitation: the shared autosave is a 10-second interval (recreated on
  every dep change, no flush on unmount/beforeunload), so an edit made <10s before
  an unexpected reload is lost. Same pre-existing window as custom behaviours/skills;
  in-memory state is unaffected during normal use.
- `updateBehaviourScore(category, id, magnitude)`:
  - built-in id → write to `behaviourScoreOverrides`;
  - custom id → update the entry's `points` in the matching custom array (signed by category).
- Effective-score display: the dialog union AND the sidebar recording popovers show
  `override ?? default` for built-ins, so the chip the teacher taps matches the award.
- `recordBehaviour`: sends `points_override` when the behaviour is custom (as today) OR a
  built-in with an override. Built-ins without overrides keep server-side resolution —
  zero change to existing flows.

### 3. Backend
No changes. `POST /session/{id}/behaviour` already validates `points_override` (1–100) and
snapshots the awarded points on the interaction, so `compute_session_scores`, the follow-up
sheet, and the gradebook stay consistent.

## Error handling
- Dialog rejects empty/zero/non-numeric/out-of-range magnitudes by keeping the edit field open.
- `recordBehaviour` only attaches `points_override` when the magnitude is a finite integer
  in 1–100; otherwise it falls back to existing behaviour (defaults for built-ins).

## Testing
QA end-to-end in BOTH roles (School Teacher + Independent Teacher, `TEST_CREDENTIALS.md`):
1. Edit a built-in score (e.g. احترام +2 → +5) and a custom behaviour score; save.
2. Reopen Lesson Settings — edited scores shown.
3. Record both behaviours on a student — toast/score reflect edited values; sidebar popover
   chips show edited values.
4. Follow-up sheet reflects the awarded points.
5. A different lesson starts at defaults (lesson-only scope).
