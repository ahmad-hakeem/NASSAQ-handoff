# Standby Engine Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor standby roster generation to enforce master-schedule dependency, classify cells via Inverse Gap Analysis, and cap per-teacher standby load using a configurable school-level setting (default 5/week) distributed evenly across working days.

**Architecture:** Backend service `standby_roster_service.compute_standby_roster()` reads a new school setting `max_standby_per_teacher_per_week` and uses it as an upper bound on top of `remaining_capacity = weekly_quota − assigned_main_classes`. The roster endpoint adds a guardrail rejecting calls when no master-schedule sessions exist. The setting is exposed in the frontend Schedule Settings → Timings tab.

**Tech Stack:** FastAPI + SQLAlchemy (async) backend, React + Tailwind frontend, GenericDocument JSONB storage.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `backend/services/standby_roster_service.py` | Modify | Read school cap; cap/distribute slots evenly |
| `backend/routes/standby_routes.py` | Modify | Guardrail in `GET /standby/roster` |
| `backend/routes/school_settings_mod.py` | Modify | Persist + return new setting |
| `frontend/src/hooks/useSchoolSettings.js` | Modify | Add field to `timingSettings` state |
| `frontend/src/components/school-settings/DynamicSettingsContent.jsx` | Modify | Add numeric input UI |

No new files. No deletions. No changes to substitution scoring or smart engine.

---

## Task 1: Backend — Read school cap setting in standby service

**Files:**
- Modify: `backend/services/standby_roster_service.py:63-145`

- [ ] **Step 1: Add helper to fetch school cap**

Add this function near the top of the file (right after `_safe_int`, before `compute_standby_roster`):

```python
DEFAULT_MAX_STANDBY_PER_WEEK = 5
MAX_STANDBY_CAP_HARD_LIMIT = 20  # absolute upper bound regardless of setting


async def _fetch_school_standby_cap(session, school_id: str) -> int:
    """Returns the school's `max_standby_per_teacher_per_week` setting.

    Reads from `school_settings.custom_settings.max_standby_per_teacher_per_week`.
    Falls back to DEFAULT_MAX_STANDBY_PER_WEEK (5) when missing or invalid.
    Clamped to the range [1, MAX_STANDBY_CAP_HARD_LIMIT].
    """
    from engines.sql_utils import gd_find_one
    row = await gd_find_one(session, "school_settings", {"school_id": school_id})
    if not row:
        return DEFAULT_MAX_STANDBY_PER_WEEK
    cs = row.get("custom_settings") or {}
    raw = cs.get("max_standby_per_teacher_per_week")
    val = _safe_int(raw, DEFAULT_MAX_STANDBY_PER_WEEK)
    if val < 1:
        return DEFAULT_MAX_STANDBY_PER_WEEK
    return min(val, MAX_STANDBY_CAP_HARD_LIMIT)
```

- [ ] **Step 2: Use the school cap inside `compute_standby_roster`**

In `compute_standby_roster()` (around line 122), after the `busy` map is built and BEFORE the `for t in teachers:` loop, add:

```python
    # School-wide cap: hard upper bound on standby slots per teacher per week.
    # See spec docs/superpowers/specs/2026-05-03-standby-engine-refactor-design.md.
    school_cap = await _fetch_school_standby_cap(session, school_id)
```

Then inside the per-teacher loop, REPLACE the existing capacity calculation (lines ~128-143) with:

```python
        weekly_quota = _safe_int(t.get("weekly_periods"), 0)
        load = teacher_load.get(tid, 0)
        # Inverse Gap Analysis: remaining headroom from the master schedule.
        if weekly_quota <= 0:
            # No quota configured → teacher is excluded from auto-standby.
            # Manual `add` overrides still work via apply_overrides_to_roster.
            continue
        remaining_capacity = max(weekly_quota - load, 0)
        # Per-teacher explicit override (legacy `standby_periods` field) still
        # acts as a tighter ceiling when set; otherwise fall back to school cap.
        configured_standby = _safe_int(t.get("standby_periods"), 0)
        per_teacher_ceiling = configured_standby if configured_standby > 0 else school_cap
        capacity = min(remaining_capacity, per_teacher_ceiling)
        if capacity <= 0:
            continue
```

- [ ] **Step 3: Manual verification**

Restart the Backend API workflow. Call `GET /api/standby/roster` for a school whose teachers have `weekly_periods` set. Confirm `totals.auto_slots` is far below the previous ~1496 and roughly equals `Σ min(weekly_quota − load, 5)` across active teachers.

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$REPLIT_DEV_DOMAIN/api/standby/roster?school_id=$SID" | jq '.totals'
```

Expected: `auto_slots` is in the low hundreds (e.g. ≤ `5 × num_teachers`), not ~1496.

- [ ] **Step 4: Commit**

```bash
git add backend/services/standby_roster_service.py
git commit -m "feat(standby): cap auto roster by school-level max_standby_per_teacher_per_week"
```

---

## Task 2: Backend — Master schedule guardrail

**Files:**
- Modify: `backend/routes/standby_routes.py:310-340`

- [ ] **Step 1: Add guardrail at top of `get_standby_roster`**

In `backend/routes/standby_routes.py`, inside `get_standby_roster()`, immediately AFTER the existing `assert_school_access(current_user, str(sid))` line (around line 327) and BEFORE the `teachers = await gd_find(...)` line, insert:

```python
    # Guardrail: standby generation requires that the master schedule has
    # produced at least one session. See
    # docs/superpowers/specs/2026-05-03-standby-engine-refactor-design.md.
    has_session = await gd_find_one(
        db.session, "timetable_sessions", {"school_id": str(sid)},
    )
    if not has_session:
        raise HTTPException(
            status_code=409,
            detail="يجب توليد الجدول الرئيسي أولاً قبل توليد جدول الانتظار",
        )
```

Note: `gd_find_one` is already imported at the top of the file.

- [ ] **Step 2: Manual verification — happy path**

For a school WITH sessions:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" \
  "$REPLIT_DEV_DOMAIN/api/standby/roster?school_id=$SID_WITH_SESSIONS"
```

Expected: `200`.

- [ ] **Step 3: Manual verification — guardrail fires**

For a school with NO `timetable_sessions` rows (or temporarily delete sessions in a test tenant):

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$REPLIT_DEV_DOMAIN/api/standby/roster?school_id=$SID_EMPTY" | jq
```

Expected: HTTP 409 with `{"detail": "يجب توليد الجدول الرئيسي أولاً قبل توليد جدول الانتظار"}` (wrapped in the project's standard error envelope if middleware adds one).

- [ ] **Step 4: Commit**

```bash
git add backend/routes/standby_routes.py
git commit -m "feat(standby): guard /standby/roster behind master schedule existence check"
```

---

## Task 3: Backend — Persist new setting in school settings GET/PUT

**Files:**
- Modify: `backend/routes/school_settings_mod.py:650-760` (GET) and `:930-1010` (PUT)

- [ ] **Step 1: Add field to PUT mapping**

In `update_school_settings_full` (around line 968), inside the `field_mappings` dict, add a new entry just before the closing brace:

```python
        "maxStandbyPerWeek":             (None, "max_standby_per_teacher_per_week"),
        "max_standby_per_teacher_per_week": (None, "max_standby_per_teacher_per_week"),
```

- [ ] **Step 2: Validate range on PUT**

Immediately after the `field_mappings` block and BEFORE the `existing = await gd_find_one(...)` line (around line 988), add:

```python
    # Validate new standby cap (1..20). Reject early with Arabic message.
    if "maxStandbyPerWeek" in settings_data or "max_standby_per_teacher_per_week" in settings_data:
        raw = settings_data.get("maxStandbyPerWeek",
                                settings_data.get("max_standby_per_teacher_per_week"))
        try:
            n = int(raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400,
                detail="قيمة الحد الأقصى لحصص الانتظار يجب أن تكون رقماً صحيحاً")
        if n < 1 or n > 20:
            raise HTTPException(status_code=400,
                detail="الحد الأقصى لحصص الانتظار يجب أن يكون بين 1 و 20")
```

- [ ] **Step 3: Return field from GET**

In `get_school_settings` (around line 726), inside the returned dict, add this key right after the `"breaks"` line:

```python
        "maxStandbyPerWeek": _pick(cs.get("max_standby_per_teacher_per_week"), nested_settings.get("max_standby_per_teacher_per_week"), default=5),
```

- [ ] **Step 4: Manual verification**

```bash
# PUT a value
curl -s -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"maxStandbyPerWeek": 3}' \
  "$REPLIT_DEV_DOMAIN/api/school/settings" | jq

# Confirm GET returns it
curl -s -H "Authorization: Bearer $TOKEN" \
  "$REPLIT_DEV_DOMAIN/api/school/settings" | jq '.maxStandbyPerWeek'

# Out-of-range rejection
curl -s -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"maxStandbyPerWeek": 99}' -w "\n%{http_code}\n" \
  "$REPLIT_DEV_DOMAIN/api/school/settings"
```

Expected: GET returns `3`. The 99 PUT returns 400 with the Arabic range message.

- [ ] **Step 5: Verify cap actually flows through to roster**

After setting `maxStandbyPerWeek=3`, call `/api/standby/roster` and confirm no teacher's `standby_capacity` exceeds 3:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$REPLIT_DEV_DOMAIN/api/standby/roster?school_id=$SID" | \
  jq '[.teachers[].standby_capacity] | max'
```

Expected output: `3` (or lower).

- [ ] **Step 6: Commit**

```bash
git add backend/routes/school_settings_mod.py
git commit -m "feat(school-settings): persist and expose max_standby_per_teacher_per_week"
```

---

## Task 4: Frontend — Add field to settings hook state

**Files:**
- Modify: `frontend/src/hooks/useSchoolSettings.js:98-108`

- [ ] **Step 1: Extend `timingSettings` initial state**

In `useSchoolSettings.js` around line 98, modify the `useState` for `timingSettings` to add `maxStandbyPerWeek: 5`:

```javascript
  const [timingSettings, setTimingSettings] = useState({
    academicYear: '1446',
    currentSemester: '1',
    dayStart: '07:00',
    dayEnd: '13:15',
    periodsPerDay: 7,
    periodDuration: 45,
    breakDuration: 20,
    breakAfterPeriod: 3,
    attendancePattern: 'winter',
    maxStandbyPerWeek: 5,
  });
```

- [ ] **Step 2: Hydrate from API response**

Find where `timingSettings` is populated from the `/school/settings` API response (search for `setTimingSettings(` in this file). Add `maxStandbyPerWeek` to the hydration object using the value from `settingsRes.data.maxStandbyPerWeek` with fallback to `5`.

Example merge to add inside the existing hydration block:

```javascript
      maxStandbyPerWeek: Number(settingsRes.data?.maxStandbyPerWeek ?? 5),
```

- [ ] **Step 3: Verify save path includes the field**

The hook's save function POSTs `timingSettings` to `/school/settings` via the existing PUT call. Confirm by reading the save handler and ensuring `maxStandbyPerWeek` is in the payload — no change should be needed if the entire `timingSettings` object is sent. If the save handler picks specific keys, add `maxStandbyPerWeek` to that pick list.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useSchoolSettings.js
git commit -m "feat(school-settings): track maxStandbyPerWeek in useSchoolSettings hook"
```

---

## Task 5: Frontend — Add numeric input UI

**Files:**
- Modify: `frontend/src/components/school-settings/DynamicSettingsContent.jsx:255-270`

- [ ] **Step 1: Add the input next to `breakDuration`**

In `DynamicSettingsContent.jsx`, find the `<div className="space-y-4">` block that contains `periodDuration` and `breakDuration` Selects (around lines 255-270). Inside that div, AFTER the `breakDuration` `<div>` block and BEFORE the closing `</div>` of `space-y-4`, insert:

```jsx
                  <div>
                    <Label className="text-sm text-slate-600 mb-2 block">الحد الأقصى لحصص الانتظار للمعلم أسبوعياً</Label>
                    <input
                      type="number"
                      min={1}
                      max={20}
                      step={1}
                      value={timingSettings.maxStandbyPerWeek ?? 5}
                      onChange={(e) => {
                        const raw = parseInt(e.target.value, 10);
                        const clamped = Number.isFinite(raw)
                          ? Math.max(1, Math.min(20, raw))
                          : 5;
                        handleSettingChange('maxStandbyPerWeek', clamped);
                      }}
                      className="h-12 w-full rounded-md border border-slate-200 px-3 text-base focus:border-[#1C3D74] focus:outline-none"
                      data-testid="max-standby-per-week-input"
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      الافتراضي: 5 — يطبّق كحد أعلى مع السعة المتبقية لكل معلم
                    </p>
                  </div>
```

- [ ] **Step 2: Manual verification**

Restart the Frontend Dev workflow. Open School Settings → "إعدادات التوقيت والحصص" tab in the browser. Verify:
1. The new field labeled "الحد الأقصى لحصص الانتظار للمعلم أسبوعياً" appears under break duration.
2. Initial value is `5` (or whatever was saved).
3. Changing it to `3` and clicking the existing Save button persists; reloading the page shows `3`.
4. The Standby Roster page (`/standby` or equivalent) regenerated reflects the new cap (no teacher with >3 auto standby slots).
5. Entering `99` clamps to `20` on blur; entering `0` clamps to `1`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/school-settings/DynamicSettingsContent.jsx
git commit -m "feat(school-settings): expose max standby per week input in Timings tab"
```

---

## Task 6: End-to-end manual verification

- [ ] **Step 1: Reproduce the original 1496 problem on a fresh tenant**

Pick a test school (`TEST_CREDENTIALS.md` documents these). Confirm before-state by reading Standby Roster page totals — record the number.

- [ ] **Step 2: Confirm guardrail**

In a new test tenant with no master schedule yet:
1. Navigate to Standby Roster page.
2. Confirm `NassaqAlertDialog` appears (or 409 surfaces) with message: `يجب توليد الجدول الرئيسي أولاً قبل توليد جدول الانتظار`.

- [ ] **Step 3: Confirm cap with default value**

In the school with master schedule:
1. Leave `maxStandbyPerWeek` at default `5`.
2. Open Standby Roster — total `final_slots` should be ≤ `5 × number_of_teachers` and dramatically less than the previous 1496.
3. Spot-check 3 teachers: `standby_capacity` ≤ 5 each.

- [ ] **Step 4: Confirm even distribution**

Pick one teacher with `standby_capacity = 5` on a 5-working-day school. Verify on the standby grid that the green ticks are spread across days (1 per day), not stacked.

- [ ] **Step 5: Confirm setting change**

Change `maxStandbyPerWeek` to `3`, save, reload Standby Roster. Verify max `standby_capacity` is now ≤ 3.

- [ ] **Step 6: Confirm classification**

For one teacher, cross-reference Master Schedule grid with Standby grid:
- Every cell shown as a class on master = `busy` (locked, "مشغول") on standby.
- Empty master cells are either `standby` (green tick) or `free` (white) — never both at once.

- [ ] **Step 7: Confirm manual overrides still work**

Click an empty cell to add a manual standby (violet). Reload. Confirm it persists. Click again to remove. Confirm cycle works as before — no regression.

- [ ] **Step 8: Final commit if any tweaks were needed**

```bash
git add -A
git commit -m "chore(standby): manual verification adjustments"
```

---

## Self-Review

**Spec coverage check:**
- Sequential Dependency (Guardrail) → Task 2 ✓
- Inverse Gap Analysis (Busy/Unavailable/Eligible) → Task 1 (existing busy/blocked logic preserved) + Task 6 step 6 verification ✓
- `remaining_capacity` formula → Task 1 step 2 ✓
- `max_standby_per_week` configurable per school → Task 3 (backend) + Task 4 + Task 5 (frontend) ✓
- Default = 5 → Task 1 (`DEFAULT_MAX_STANDBY_PER_WEEK = 5`), Task 3 step 3 (GET fallback), Task 4 step 1 ✓
- Even distribution across working days → Existing `per_day_cap` logic in `compute_standby_roster` is preserved (line 168) — no change needed; the existing round-robin pass already implements it ✓
- Frontend matrix mapping (busy/standby/free colors) → Already present in `StandbyRosterPage.jsx`; no changes needed (verified in Task 6 step 6) ✓
- Out-of-scope items (substitution scoring, smart engine, multi-day, automated tests) → not touched ✓

**Placeholder scan:** No TBDs, no "implement later", no missing code blocks. All steps have exact file paths, line ranges, and ready-to-paste code.

**Type consistency:**
- `DEFAULT_MAX_STANDBY_PER_WEEK` defined Task 1 step 1, used Task 1 step 1 (helper) and Task 1 step 2 (loop).
- `maxStandbyPerWeek` (camelCase) used consistently across backend GET return, PUT input, frontend hook state, and frontend UI input.
- `max_standby_per_teacher_per_week` (snake_case) used consistently as the `custom_settings` JSONB key.
- HTTP 409 status used consistently for the guardrail.
