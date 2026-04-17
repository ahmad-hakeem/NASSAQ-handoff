# Schedule Page Redesign — تحسين تجربة الجدول المدرسي

> Spec date: 2026-04-17
> Scope: `frontend/src/pages/SchedulePageNew.jsx` (main school schedule page only)

## What & Why

The current main schedule page renders **days as horizontal columns** across the top of a grid, while the **substitute/waiting sessions panel** (`CandidatesSidePanel`) sits on the right but feels crowded and unstructured. Users (schedule managers and teachers) struggle to scan a single day's flow and to triage which waiting sessions need coverage first.

We are redesigning the layout so days become **vertical rows on the left**, periods become **unified columns** for cross-day comparison, and the right-side waiting panel becomes a **clean, grouped, drag-source** for assigning substitutes. We are also adding a small set of **per-user view preferences** (week vs. day, panel collapsed/expanded) that persist between visits.

The Teacher schedule view (`TeacherScheduleGrid`) is intentionally **out of scope** for this iteration.

## Done looks like

A user opening the main schedule page sees:

- The five school days (Sunday → Thursday) listed as **vertical rows on the left** of the grid, each row containing that day's session cards laid out across **unified period columns** on large screens.
- On small screens (mobile/tablet), each day row turns into a **horizontally scrollable strip** of session cards instead of squeezing the columns.
- A header on each day row showing the day name, total session count, and a small badge with that day's number of waiting/substitute sessions.
- A **right-side waiting panel** that:
  - Is a fixed ~320–360px column, collapsible to a thin rail with one click.
  - Has a top "تحتاج تغطية الآن" (Needs coverage now) section pinning today's and imminently-upcoming waiting sessions.
  - Below it, lists remaining waiting sessions **grouped by day**, with each day group collapsible.
  - Lets the user **drag a waiting card and drop it onto an empty slot** in the grid (any day) to assign a substitute, with valid drop targets visually highlighted while dragging, and a success toast on completion.
- A **toolbar above the grid** containing:
  - Toggle: **Full week ↔ Single day expanded**.
  - Toggle: **Collapse / expand the right waiting panel**.
  - Existing filters (year, term, class) preserved as-is.
- The view-mode toggle and panel collapsed state are **saved per user** (browser local storage keyed by user id) and restored on the next visit.
- The existing data-loading, permissions, generation flows, and dialogs continue to work unchanged — only layout, the waiting panel structure, and the new toolbar/preferences are introduced.

## Out of scope

- Any changes to `TeacherScheduleGrid` or other schedule surfaces.
- Text search, advanced multi-criteria filters, or expanded statistics inside the waiting panel.
- Density toggle (compact/comfortable), column show/hide, or alternative card-coloring schemes.
- Server-side preference storage (local storage is sufficient for now).
- New backend endpoints; reuse existing schedule and substitute APIs.

## Tasks

1. **Layout inversion (days as rows, periods as columns)** — Restructure the grid section of the schedule page so days render as vertical rows on the left with unified period columns on large screens, and as horizontally scrollable per-day strips on small screens. Update each day-row header to include the session count and a waiting-count badge. Preserve all existing session interactions (click, drag from grid, dialogs).

2. **Redesigned waiting panel** — Rebuild the right-side substitute/waiting panel so it is collapsible to a rail, has a pinned "Needs coverage now" top section for today/imminent sessions, and groups the remaining waiting sessions by day with collapsible groups. Keep the existing data source; only the structure and visuals change.

3. **Drag-and-drop substitute assignment** — Make each waiting-panel card a drag source and each empty grid slot a valid drop target. Highlight valid targets while dragging, perform the assignment via the existing substitute API on drop, and show a success/error toast. Keep keyboard/click fallback for accessibility.

4. **View toolbar + week/day toggle** — Add a toolbar above the grid with a "Full week ↔ Single day expanded" toggle and a "Collapse/expand waiting panel" toggle. The single-day mode shows one selected day full-width with a day picker.

5. **Per-user preference persistence** — Persist view mode (week/day, selected day if any) and waiting-panel collapsed state to browser local storage keyed by the current user id. Restore on page mount. Fall back to defaults if no stored value.

6. **Polish, RTL, and regression check** — Verify RTL layout behaves correctly (left/right swap intentions hold under `dir="rtl"`), check that existing tests/flows (generation journey, candidates panel callbacks, session dialogs) still work, and update any affected snapshot/visual tests.

## Relevant files

- `frontend/src/pages/SchedulePageNew.jsx`
- `frontend/src/components/schedule/CandidatesSidePanel.jsx`
- `frontend/src/components/schedule/TeacherScheduleGrid.jsx`
- `frontend/src/hooks/useScheduleCandidates.js`
- `frontend/src/locales/ar.json`
- `frontend/src/locales/en.json`

## Architectural notes

- Keep the page a single route component; extract the new grid and the redesigned waiting panel into focused subcomponents inside `frontend/src/components/schedule/` rather than growing `SchedulePageNew.jsx` further (it is already ~1400 lines).
- Drag-and-drop should reuse whatever DnD primitive the existing grid drag already uses (HTML5 drag events appear to be in use today) to avoid pulling in a new dependency.
- Local-storage key suggestion: `nassaq.schedule.viewPrefs.<userId>` storing `{ viewMode: 'week' | 'day', selectedDay?: string, waitingPanelCollapsed: boolean }`.
- All new strings must be added to both `ar.json` and `en.json`.
