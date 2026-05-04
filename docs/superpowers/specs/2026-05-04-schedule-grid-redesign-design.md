# Schedule Grid Redesign — Design Spec

**Date:** 2026-05-04
**Status:** Approved (pending user spec review)
**Scope:** Frontend visual + interaction redesign of all schedule grids in the Nassaq app. No backend, API, or schema changes.

---

## 1. Objective

Modernize the look and feel of the schedule grids (master grid, teacher's own schedule view, class schedule view) to match the visual richness of the supplied reference image while staying coherent with Nassaq brand identity. Add an interactive cell-click pop-up that surfaces session detail and provides quick access to existing edit / move / lock actions.

This is a **view-layer** change. Data shapes, API endpoints, drag-and-drop wiring, and lock/edit business logic are reused as-is.

## 2. Non-Goals

- No new API endpoints; no DB schema migrations.
- No changes to substitution, absence, or generation flows.
- No replacement of `@dnd-kit` / native HTML5 drag handlers — the new modal calls the same handlers the grid already exposes.
- No changes to authentication, permissions, or role logic.

## 3. Day Color System (Brand-extended)

Five pastel day tints anchored to Nassaq brand (navy / turquoise / purple), extended with two complementary pastels (sand, sage) to cover all five school days.

| Day | Anchor | Tint (cell bg) | Band (header) |
|---|---|---|---|
| الأحد (Sunday) | Brand navy | `#EAF0F9` | `#1C3D74` |
| الإثنين (Monday) | Brand turquoise | `#E4F5F4` | `#46C1BE` |
| الثلاثاء (Tuesday) | Soft sand (new) | `#FBF1DC` | `#D4A23C` |
| الأربعاء (Wednesday) | Sage green (new) | `#E8F1E4` | `#7AA169` |
| الخميس (Thursday) | Brand purple | `#ECE9F4` | `#615090` |

Tokens are defined as HSL CSS variables in `frontend/src/index.css` and exported as a JS map from `frontend/src/components/schedule/grid-theme/dayPalette.js` (single source of truth). All band colors meet WCAG AA against white text. All cell tints meet WCAG AA against the navy body text used inside cells.

Saturday is treated as a non-school day and is not rendered as a day group.

## 4. Grid Layout

- **Teacher column** pinned to the right (RTL): circular avatar (40 px), full name in Cairo 600, subject specialty subtitle in Tajawal 400 muted-navy. Sticky during horizontal scroll.
- **Day groups** — each day is a contiguous block with:
  - A colored **band header** (day name, white text, Cairo 700) above
  - A row of small period-number cells (`١`–`٧`) carrying the same day's tint at lower opacity, matching the reference image's banded structure.
- **Cells** carry the day's tint; subject (Cairo 600) and class (Tajawal 400) stack vertically. Locked / relocated badges sit in the top-left corner as small icon chips (no text; tooltip on hover) to keep cell density.
- **Empty / break / admin-zone rows** keep their existing semantics with refined treatment:
  - Empty row: striped pastel background with the existing "no scheduled classes" message.
  - Admin block: soft red wash with the existing "admin block" label.
- Horizontal scroll preserved on small screens; teacher column stays sticky.

## 5. Cell Pop-up Modal (Glass)

**Trigger.** Click any filled cell. Backdrop fades to `rgba(28, 61, 116, 0.35)` with `backdrop-blur(12px)`.

**Card.** Centered, 420 px wide, `bg-white/70` + `backdrop-blur(24px)`, navy-tinted 1 px border, soft inner highlight on the top edge, layered shadow. Framer Motion `AnimatePresence` with scale 0.95 → 1 + opacity fade, ~220 ms ease-out enter / ~140 ms ease-in exit.

**Header strip.** Thin band in the day's color showing day name + period number + time range (e.g. `الأحد · الحصة ٣ · ١١:٣٥ - ١٢:١٥`).

**Body content.**
- Subject name (large, Cairo 600)
- Class / section
- Teacher row (avatar + name + specialty)
- Classroom chip
- Status badges when present: locked, relocated, substitute

**Footer — quick actions.** Three buttons wired to the grid's existing handlers:
- **Edit** (turquoise primary) → calls the existing `onSessionClick` / edit handler the grid already passes down.
- **Move** (ghost) → enables drag mode for the selected session, reusing the existing drag/drop pipeline.
- **Lock / Unlock** (ghost, label toggles based on `is_locked`) → calls the existing lock handler.

**Dismiss.** X button in the top-left (RTL), Esc key, and backdrop click. Focus returns to the originating cell.

## 6. Component Architecture

New shared module: **`frontend/src/components/schedule/grid-theme/`**

- `dayPalette.js` — single source of truth for the five day color tokens (and helpers: `getDayTint(dayIndex)`, `getDayBand(dayIndex)`).
- `DayHeaderBand.jsx` — colored band + period-number sub-row used at the top of each day group.
- `SessionCell.jsx` — the cell renderer with day-tinted background, hover/press states, and a11y wiring. Replaces the current inline cell rendering inside `FilledCell.jsx`.
- `SessionDetailModal.jsx` — the glass pop-up. Receives `session`, `onClose`, and the existing handler refs as props, so wiring stays at the parent grid level.

**Refactor targets**
- `frontend/src/components/schedule/TeacherScheduleGrid.jsx` — adopts the new primitives.
- `frontend/src/components/schedule/FilledCell.jsx` — slimmed to delegate visuals to `SessionCell.jsx`.
- Teacher's own schedule view and class schedule view (exact filenames confirmed during implementation) — adopt the same primitives so all three grids look and behave consistently.

No prop or data-shape changes flow upward; the parent pages keep passing the same session / teacher / time-slot data they pass today.

## 7. Polish & Accessibility

- **Hover.** `scale(1.02)` + soft elevated shadow, 180 ms ease-out. Cursor pointer.
- **Keyboard.** Cells get `role="button"` with `tabIndex={0}`; Enter/Space opens the modal; Esc closes it.
- **Aria.** Each cell carries an `aria-label` describing subject + class + day + period + time. Modal has `role="dialog"` and `aria-labelledby` pointing at its header strip.
- **Focus.** Modal traps focus while open and restores focus to the originating cell on close.
- **Reduced motion.** `prefers-reduced-motion: reduce` disables scale and stagger; opacity fades only.
- **Contrast.** All band-on-white-text and cell-on-navy-text pairs verified to meet WCAG AA (≥4.5:1 for body text, ≥3:1 for the band labels at Cairo 700).
- **RTL.** All visual decisions assume RTL; close button sits top-left, day order remains right-to-left.

## 8. Out of Scope (Explicit)

- Bulk multi-cell selection inside the modal.
- Editing classroom / time directly inside the modal (handled by the existing edit dialog the Edit button opens).
- Animations on data updates (no enter/exit per session beyond the modal itself).
- Theming for dark mode (current grids are light-mode only; a dark variant is a future spec).

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Visual regression in the existing master grid | Day palette and primitives are additive; old `FilledCell` markup is replaced behind the same prop interface. Manual visual QA on master grid before touching the other two views. |
| Drag-and-drop breakage when the modal is open | Modal closes immediately when the Move action is invoked, returning control to the existing drag pipeline. |
| Performance on large schools (many teachers × many periods) | Cells use `transform`/`opacity` only for hover; modal mounts once at the grid root via `AnimatePresence`. No per-cell motion components. |
| Color fatigue across all three views | All three grids share the same five-color palette — no extra hues introduced per view. |

## 10. Acceptance Criteria

- All three schedule grids render with the five day-color groups, banded headers, and tinted cells.
- Clicking any filled cell opens the glass modal with the seven listed content fields and three quick actions.
- Edit / Move / Lock from the modal trigger the same flows that the existing grid already supports — verified by manual QA in the master grid.
- Esc, X, and backdrop click all dismiss the modal; focus returns to the originating cell.
- No backend code changed; no API contract changed; no schema migration produced.
- Lighthouse and a quick a11y pass show no new contrast or focus regressions.
