# Standby Engine Refactor — Inverse Gap Analysis

**Date:** 2026-05-03
**Status:** Approved
**Scope:** Backend standby roster service, school settings, frontend settings UI

## Problem

The current standby roster generator fills every empty period in the weekly matrix as a standby slot. With 104 teachers, this produces ~1496 inflated standby assignments (≈14 per teacher), making the roster meaningless and overloading teachers.

The roster must instead use **Inverse Gap Analysis**: only mark a period as standby if it is genuinely free *and* the teacher has not already exceeded a sensible weekly cap, distributed evenly across working days.

## Goals

1. Standby generation runs **strictly after** the master schedule exists.
2. Each cell is classified as **Busy / Unavailable / Eligible** before any assignment.
3. Per-teacher standby load is capped by `min(remaining_capacity, school_cap)` where `school_cap` defaults to **5** and is configurable per school.
4. Selected standby slots are distributed **evenly across working days**.
5. Frontend grid clearly distinguishes Busy (locked), Standby (green tick), and Empty (white).

## Non-Goals (YAGNI)

- No changes to the substitution scoring algorithm (`substitution_service.py`).
- No changes to manual override semantics (`add` / `remove` / `reset`).
- No changes to the smart scheduling engine itself.
- No multi-day absence coverage, no automated tests (covered by separate proposed tasks #110, #111).

## Architecture

```
[Guardrail: master schedule exists?]
        ↓ (409 if no)
[Build per-teacher week matrix: Days × Periods]
        ↓
[Classify each cell: BUSY | UNAVAILABLE | ELIGIBLE]
        ↓
[Compute effective_cap = min(remaining_capacity, school_cap)]
        ↓
[Distribute cap evenly across working days, pick first eligible periods per day]
        ↓
[Merge with manual overrides → return to UI]
```

## Backend Changes

### `backend/routes/standby_routes.py`

- `GET /api/standby/roster` (and any explicit generate endpoint): add a guardrail at the top.
  - Query: `SELECT 1 FROM sessions WHERE school_id = ? LIMIT 1`.
  - If no rows: return `409 Conflict` with Arabic message:
    `"يجب توليد الجدول الرئيسي أولاً قبل توليد جدول الانتظار"`
  - If rows exist: proceed.

### `backend/services/standby_roster_service.py` — `compute_standby_roster()`

Replace the current "fill all empties" logic with the following pipeline.

**1. Cell classification.** For each teacher × (day, period):
- `BUSY` → teacher has an assigned session in the master schedule for that slot. Locked.
- `UNAVAILABLE` → matches an entry in the `unavailability` collection for the teacher. Locked.
- `ELIGIBLE` → neither of the above.

**2. Cap calculation per teacher.**
```
remaining_capacity = max(weekly_quota - assigned_main_classes, 0)
school_cap         = school_settings.max_standby_per_teacher_per_week  # default 5
effective_cap      = min(remaining_capacity, school_cap)
```
- If `weekly_quota` is missing or invalid for a teacher → `effective_cap = 0` (logged at debug level, not an error).

**3. Even distribution across working days.** For `effective_cap = N` slots across `D` working days:
```
per_day = N // D
extras  = N % D
```
- The first `extras` working days get `per_day + 1` standby slots.
- The remaining days get `per_day` slots.
- Within each day, pick the first `k` eligible periods in period-order (deterministic).

**4. Merge with manual overrides** (existing `standby_overrides` collection):
- `add` overrides bypass the cap (principal authority is absolute).
- `remove` overrides clear auto-assigned slots.
- `reset` removes the override and falls back to the auto value.

## School Settings

### Backend

- Add field to the school settings GenericDocument: `max_standby_per_teacher_per_week: int = 5`, valid range **1–20**.
- Extend the existing School Settings `GET` and `PUT` endpoints to read/write this field. **No new endpoint.**
- Backend validation rejects out-of-range values with `400` and Arabic error message.

### Frontend

In `frontend/src/pages/.../SchoolSettingsPage.jsx` → Schedule Settings tab:
- Add a number input:
  - Label: `الحد الأقصى لحصص الانتظار للمعلم أسبوعياً`
  - Helper text: `الافتراضي: 5 — يطبّق كحد أعلى مع السعة المتبقية لكل معلم`
  - Min: 1, Max: 20, Default: 5.
- Inline validation for the 1–20 range.
- Persists via the existing settings PUT call. No new API client method needed.

## Frontend Matrix Mapping

`StandbyRosterPage.jsx` already supports the three states. Confirm rendering matches the spec:

| State | Visual | Source |
|---|---|---|
| `busy` (مشغول) | Slate cell + lock icon + "مشغول" label | Master schedule session |
| `standby` (انتظار) | Emerald cell + green tick | Algorithm output, capped |
| empty (فارغ) | White / empty cell | Eligible but not selected by cap |

Manual override colors (violet `add` / rose `remove`) are preserved unchanged.

## Data Flow

```
Master Schedule (sessions) ─┐
Unavailability ─────────────┼─→ classify cells ─→ apply cap ─→ distribute evenly
School Settings (cap) ──────┘                                          ↓
                                  Manual Overrides ─→ merge ─→ /api/standby/roster
                                                                       ↓
                                                              StandbyRosterPage UI
```

## Error Handling

- **No master schedule** → `409` + Arabic message rendered via `NassaqAlertDialog` on the frontend.
- **Missing/invalid `weekly_quota`** for a teacher → that teacher gets 0 standby slots (logged at debug, not errored).
- **Invalid cap setting** (outside 1–20) → backend `400` + Arabic message; frontend shows inline validation error before submit.

## Manual Verification Checklist

Per project conventions (no automated tests in this scope):

1. Generate master schedule → standby total drops from ~1496 to roughly `104 × 5 = ~520` (or less, since `remaining_capacity` may be tighter for many teachers).
2. With no master schedule sessions → calling standby generation returns 409 and the dialog appears.
3. Change cap from 5 → 3 in School Settings → regenerate → counts decrease proportionally.
4. Verify even distribution: a teacher with cap 5 on a 5-day week gets 1/day; cap 7 gets 2,2,1,1,1.
5. Spot-check classification: a `busy` cell on the standby grid corresponds to a real session on the master grid.
6. Manual `add` override on a busy slot is rejected (slot is locked); on an eligible/empty slot it appears violet and is preserved across regeneration.

## Files to Touch

- `backend/routes/standby_routes.py` — add guardrail.
- `backend/services/standby_roster_service.py` — refactor `compute_standby_roster`.
- School settings route file (existing) — add field to schema + persistence.
- `frontend/src/pages/.../SchoolSettingsPage.jsx` — add input field.
- (No changes to `substitution_service.py`, smart engine, or override semantics.)
