# Master Schedule — Workspace Redesign (Daily + Weekly)

**Status**: design / awaiting user review
**Date**: 2026-05-06
**Owner**: Replit Agent (main)
**Predecessors**: Task #141 (draft/publish + entropy), Task #142 (daily/weekly + backend windowing)
**Scope**: Frontend layout only. Backend contract is frozen at the #142 surface.

---

## 1. Problem statement

The current `/school/schedule?tab=master` page still feels like a **dashboard with a table inserted into it**, not a real scheduling workspace. The matrix is visually trapped inside a constrained, short box because:

1. ~280 px of stacked chrome (title + KPI cards + action row + view toggle + day-tabs + draft banner) sits *above* the matrix on first paint.
2. The matrix region itself is wrapped in a card with rounded corners, shadow, border, and a fixed inner height that produces a short nested vertical scroll.
3. Pagination caps the visible teacher list at 10/25/50, reinforcing the "peeking through a window" feel.

The task is **structural**, not cosmetic. Cell typography, hierarchy, and density were already addressed in #142; the remaining problem is **page composition, container hierarchy, and scroll architecture**.

## 2. Non-negotiable acceptance criteria

Lifted from the user brief, codified here so the implementation has a hard checklist:

1. At first paint on a 1280×800 laptop, the matrix region occupies **≥ 60 %** of the viewport height.
2. There is **no nested `overflow-y`** on the matrix region. Vertical scroll happens at the page (document) level.
3. Horizontal scroll is permitted **only inside the matrix region in weekly mode**. The page chrome (sticky band, KPI bar) stays exactly viewport-wide.
4. The sticky teacher column (`inset-inline-start: 0`) stays glued in RTL throughout horizontal and vertical scroll.
5. The sticky day-band + period header stay glued to the bottom edge of the sticky action band (no 1 px float, no double-stick bug).
6. Daily mode does not look like a short strip; weekly mode does not look like five squeezed day groups.
7. All Task #141 + #142 behavior is preserved verbatim (publish gate, draft banner, in-place skeleton, substitution overlay scoping, generation force-flip to draft view, PUBLISH_BLOCKED dialog).
8. The control area (sticky band) is **visibly secondary** to the matrix.
9. RTL correctness: day order Sunday→Thursday right-to-left, sticky positioning uses `inset-inline-start`, never `left`/`right` literals.
10. Realistic scale assumption: ~100 teachers. The design must hold at that density without perf jank or layout drift.

## 3. Architecture decisions (from brainstorming Q&A)

| # | Decision | Rationale |
|---|----------|-----------|
| Q1 | **Page-level vertical scroll.** No nested `overflow-y` anywhere on the page. | Best matches "real workspace" feel; works with browser find; simplest sticky setup in RTL. |
| Q2 | **Aggressive chrome compression.** Sticky band = action row + day-tabs only (~52–88 px). KPIs become a horizontal pill bar above the sticky band and scroll away. Title becomes an inline `<h2>` inside the sticky band. Draft banner collapses to a chip. | KPIs are glance-and-go context; users do not need them while working *in* the grid. |
| Q3 | **Horizontal scroll inside the matrix region only (weekly mode).** Wrapper is `overflow-x-auto`, exactly viewport-wide, no fixed height. Teacher column stays sticky on both axes. | Only model that satisfies both "no boxed vertical scroll" *and* "weekly horizontal scroll allowed". |
| Q4 | **No pagination UI.** Frontend always sends `teacher_page=1&teacher_page_size=200`. Pager controls removed. | "Real workspace, not a small window." 100 sticky DOM rows is well within modern browser capacity; no virtualization needed. |
| Q5 (implicit) | **Backend untouched.** The #142 contract already supports this redesign exactly. | Lowest-risk path; preserves all RBAC, tenant scoping, N+1 protection, substitution overlay scoping. |

## 4. Page composition

```
┌─ /school/schedule?tab=master ─────────────────────────────────────────────┐
│  [tab strip: master | waiting | settings]                                  │  ← scrolls away
│  KPI pill bar (4 pills, one row, no card framing)                          │  ← scrolls away
│                                                                            │
│  ╔══════════ STICKY BAND (top: 0, height = --sticky-band-h) ═════════════╗ │
│  ║ <h2>الجدول الرئيسي</h2>  [draft pill]  ··· [توليد][نشر][غياب][↻] tgl ║ │
│  ║ [الأحد][الإثنين✓][الثلاثاء][الأربعاء][الخميس]    (daily mode only)    ║ │
│  ╚════════════════════════════════════════════════════════════════════════╝ │
│  ╔══════════ STICKY MATRIX HEADER (top: var(--sticky-band-h)) ═══════════╗ │
│  ║ corner │ day-band: الإثنين  ─ (weekly only) ─                          ║ │
│  ║ المعلم │  1  │  2  │  3  │  4  │  5  │  6  │  7                        ║ │
│  ╚════════════════════════════════════════════════════════════════════════╝ │
│  │ المعلم 1   │ … │ … │ … │ … │ … │ … │ …                                │ │
│  │ المعلم 2   │ … │ … │ … │ … │ … │ … │ …                                │ │
│  │     …      │   │   │   │   │   │   │                                  │ │  ← page scroll
│  │ المعلم 100 │ … │ … │ … │ … │ … │ … │ …                                │ │     (~9 200 px tall)
└────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 KPI pill bar

- Single `flex` row, `h-12`, `gap-2`, `px-4`, no card wrapper, no shadow.
- Each pill: `inline-flex items-center gap-2 px-3 py-2 rounded-full border text-sm`.
- Order (RTL): عدالة التوزيع · حصة شاغرة · معلم غائب · انتظار قسم.
- Color encoding via 1 px border + tinted icon only (no filled background) so the row stays visually quiet at 100-teacher density.

### 4.2 Sticky action band

- Container: `position: sticky; top: 0; z-index: 40;` `bg-white/95 backdrop-blur border-b border-slate-200`.
- Two rows when `viewMode === 'daily'` (action row + day-tabs row), one row when `viewMode === 'weekly'`.
- Height exposed to children via CSS custom property `--sticky-band-h` set on the page wrapper, measured at mount and on viewport resize via `ResizeObserver`. Default fallback: `88px` daily, `52px` weekly.
- Row 1 (action row, `h-13`):
  - Inline-start (RTL right): `<h2 class="text-lg font-bold">الجدول الرئيسي</h2>`, optional `draft` chip, view-mode toggle (يومي / أسبوعي) immediately to its left.
  - Inline-end (RTL left), in this order: `[إنشاء الجدول تلقائياً]` (violet primary) · `[نشر الجدول]` (emerald, gated by `grid?.timetable_status === 'draft'` per #141) · `[تسجيل غياب]` (outline) · `[↻ refresh]` (icon button).
- Row 2 (day-tabs, `h-9`, daily mode only): the existing tabs component, mounted *inside* the sticky band so the band height reflows from 52 → 88 px and the matrix-header sticky offset follows it via `--sticky-band-h`.

### 4.3 Matrix region

- Outer wrapper: **no card framing** (no `bg-white rounded-2xl shadow border` chrome around the matrix). The matrix sits directly on the page background with a single `border-t border-slate-200` separating it from the sticky band.
- No `height`, no `max-height`, no `overflow-y` on the wrapper or any of its ancestors up to `<body>`. Vertical scroll is the document.
- Daily mode wrapper: no horizontal scroll (`overflow: visible`).
- Weekly mode wrapper: `overflow-x: auto; overflow-y: visible;` — horizontal scroll is constrained to the matrix; vertical still bubbles up to the page.

### 4.4 Sticky tier layering

| Element | Position | Offset | z-index |
|---|---|---|---|
| Action band | `sticky` | `top: 0` | 40 |
| Matrix corner cell | `sticky` | `top: var(--sticky-band-h); inset-inline-start: 0` | 30 |
| Day-band row (weekly) | `sticky` | `top: var(--sticky-band-h)` | 20 |
| Period header row | `sticky` | `top: calc(var(--sticky-band-h) + var(--day-band-h))` | 15 |
| Teacher column cells | `sticky` | `inset-inline-start: 0` | 10 |
| Body cells | static | — | 0 |

`--day-band-h` is `0` in daily mode and `28px` in weekly mode (also exposed as a CSS custom property).

## 5. Cell visual treatment

`SessionCell` hierarchy contract from #142 stays unchanged (`session-cell-subject` / `session-cell-class` / `session-cell-meta` testids, ≥ 11 px floor in weekly). Only two visual deltas:

1. **Filled cell**: a 3 px subject-color bar on the inline-start edge (`border-s-[3px] border-s-{subject-color}`), with the subject text picking up the same color. No filled background — keeps the surface calm at 100-row density.
2. **Empty cell**: `bg-slate-50/40` with a faint `border-b border-dashed border-slate-200/60` hairline at the bottom — quiet and structured, not a dead spreadsheet box.

Daily row height: **96 px** (up from 92). Weekly row height: **88 px**. Weekly cell `min-w: 84px` so the total grid is ~3 200 px wide with comfortable readability.

## 6. Loading + in-place updates

- `MasterMatrixSkeleton` from #142 is reused. It mirrors the column template and stays inside the matrix region while the sticky band remains mounted. Wired to `--sticky-band-h` so its first row aligns with the live matrix headers.
- Every action that changes the matrix uses the existing `loadGrid(viewOverride?)` from #141:
  - **Auto-generate**: `loadGrid('draft')` after success. Force-flip view to draft.
  - **Publish**: `loadGrid('published')` after success. PUBLISH_BLOCKED → NassaqAlertDialog with violations (per #141, kept verbatim).
  - **View toggle / day switch**: existing useEffect on `[viewMode, day]` re-fetches; matrix → skeleton; sticky band stays mounted.
  - **Absence / substitution / undo**: existing `loadGrid()` reload after mutation. No optimistic updates (server-authoritative cascading effects).
  - **Refresh button**: `loadGrid()` with current view/day.

## 7. Backend (frozen)

Zero changes. The Task #142 contract already supports the redesign exactly:

- Frontend will always send `teacher_page=1&teacher_page_size=200` plus `view=draft|published` and (daily) `day=<sunday..thursday>`.
- Substitution overlay scoping via `visible_teacher_ids` continues to work — at `teacher_page_size=200` the visible set covers every teacher in any realistic single school, so the overlay correctly includes everyone.
- RBAC, tenant scoping, N+1 protection, audit trails — all preserved.

## 8. Files touched

**Frontend (only)**:
- `frontend/src/pages/SchedulePageNew.jsx` — page composition, sticky band, KPI pill bar, action row, day-tabs band, drop pager UI, `--sticky-band-h` + `--day-band-h` CSS vars via `ResizeObserver`.
- `frontend/src/pages/SchedulePageNew.jsx` (`MasterMatrix` + `MasterMatrixSkeleton`) — drop fixed `height`, switch to natural document flow, bump daily `ROW_HEIGHT` to 96, weekly cell `min-w` 84 px, sticky offsets read from CSS vars, z-index pass.
- `frontend/src/pages/SchedulePageNew.jsx` (`SessionCell`) — empty-cell hairline + filled-cell inline-start subject bar. No hierarchy/testid changes.
- `frontend/src/locales/ar.json` + `en.json` — only if new microcopy is required (none expected).

**Explicitly NOT touched**:
- Any `backend/**` file.
- `appRoutes.js`, RBAC, tab strip, routing.
- Substitution / absence / publish / generate handlers — only their *layout container* changes.

## 9. Self-check gates (run before marking complete)

1. `rg -n "overflow-y" frontend/src/pages/SchedulePageNew.jsx` returns no matrix-region matches.
2. Frontend production build succeeds with `DISABLE_ESLINT_PLUGIN=true npm run build` (matches existing project build path).
3. Manual visual smoke: 100-teacher fixture (or production-like), daily mode at 1280×800 — matrix region ≥ 60 % of viewport on first paint, sticky band ≤ 88 px, page-level scroll smooth.
4. Manual visual smoke: weekly mode at 1280×800 — horizontal scroll inside matrix; sticky teacher column stays glued; sticky day-band stays glued; no chrome bleed outside the viewport.
5. Round-trip test for each preserved behavior: generate → draft view appears, publish → published view appears with notification toast, PUBLISH_BLOCKED → NassaqAlertDialog with violations, day switch → skeleton + chrome stays mounted.
6. Code review (architect) APPROVED.

## 10. Out of scope

- Cell-level visual redesign beyond the two deltas in §5 (filled bar, empty hairline). The #142 hierarchy contract is frozen.
- Mobile / narrow-viewport (< 768 px) treatment. Master timetable is a desktop workspace by product definition; existing responsive fallbacks are kept untouched.
- Row virtualization. Plain DOM at 100 sticky rows is well within modern browser capacity; if a 500-teacher edge case ever appears, virtualization is a follow-up task.
- Optimistic updates on absence/substitution. Server-authoritative cascading effects make optimism risky for a small UX gain.
- Tab strip, routing, RBAC, backend.

## 11. Risk register

| Risk | Mitigation |
|---|---|
| Sticky-tier offset drift if the action band reflows on resize. | `ResizeObserver` on the action band writes `--sticky-band-h` to the page wrapper; matrix sticky offsets read the var. Verified at mount + on `window.resize`. |
| 100 sticky DOM rows performance. | Plain DOM is fine in Chrome/Edge/Firefox up to 500+ rows; virtualization deferred. |
| Substitution overlay missing rows when `teacher_page_size=200` is below actual teacher count. | 200 covers every realistic single school; if a deployment exceeds it, backend pagination contract still works — we'd just bump the constant. Not a structural risk. |
| Removing pager UI breaks an existing user flow. | No other code in the app reads `pagination.page` from the master-grid response; removal is safe. Verified via `rg "pagination" frontend/src`. |
| Drop of card framing makes the matrix bleed into adjacent UI. | A single `border-t` separates the matrix from the sticky band; the matrix's own header borders provide internal containment. |

## 12. Out-of-band changes to `replit.md`

None expected. The redesign does not change the stack, run/operate commands, architecture decisions, or user preferences. If any new gotcha emerges during implementation (e.g. a `--sticky-band-h` convention worth documenting), it gets added in a follow-up commit.
