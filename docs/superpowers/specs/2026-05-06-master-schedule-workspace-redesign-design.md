# Master Schedule — Workspace Redesign (Daily + Weekly)

**Status**: design / awaiting user review (rev 2)
**Date**: 2026-05-06
**Owner**: Replit Agent (main)
**Predecessors**: Task #141 (draft/publish + entropy), Task #142 (daily/weekly + backend windowing)
**Scope**: Primarily frontend layout. Backend contract is treated as frozen by default; **narrowly scoped backend adjustments are permitted only if required for correctness or performance at the new ~100-teacher single-page layout scale**, and must be called out explicitly in the implementation plan with rationale before being applied.

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
11. **Hard visual rejection rule**: if the final result still reads as a *table embedded inside dashboard chrome* — i.e. a card-framed grid sitting under a stack of KPI cards — the implementation is rejected regardless of whether scroll, sticky, and RTL behavior are technically correct. The matrix must read as the page's primary surface.
12. **Hard space-allocation rule**: any solution that leaves excessive low-value vertical chrome above the matrix is a failure, even if scroll behavior is technically correct. Chrome above the matrix on first paint must stay within the budget defined in §4 (KPI pill bar ≤ 48 px + sticky band ≤ 88 px daily / ≤ 52 px weekly + tab strip if present). KPI cards, hero blocks, decorative spacers, or any per-page banner that pushes the matrix below the 60 % viewport floor are not acceptable.

## 3. Architecture decisions (from brainstorming Q&A)

| # | Decision | Rationale |
|---|----------|-----------|
| Q1 | **Page-level vertical scroll.** No nested `overflow-y` anywhere on the page. | Best matches "real workspace" feel; works with browser find; simplest sticky setup in RTL. |
| Q2 | **Aggressive chrome compression.** Sticky band = action row + day-tabs only (~52–88 px). KPIs become a horizontal pill bar above the sticky band and scroll away. Title becomes an inline `<h2>` inside the sticky band. Draft banner collapses to a chip. | KPIs are glance-and-go context; users do not need them while working *in* the grid. |
| Q3 | **Horizontal scroll inside the matrix region only (weekly mode).** Wrapper is `overflow-x-auto`, exactly viewport-wide, no fixed height. Teacher column stays sticky on both axes. | Only model that satisfies both "no boxed vertical scroll" *and* "weekly horizontal scroll allowed". |
| Q4 | **No pagination UI, but underlying large-window request model is preserved.** Frontend always requests a single large window via the existing `teacher_page` / `teacher_page_size` contract; pager controls are removed from the UI. The backend pagination contract itself is **not** removed — only the UI affordance is dropped. | "Real workspace, not a small window." 100 sticky DOM rows is well within modern browser capacity; no virtualization needed. Keeping the underlying paginated contract intact preserves substitution overlay scoping and leaves room for future virtualization without a contract change. |
| Q4a | **Window size is a named configurable constant**, not a literal `200`. See §4.5. | Avoids magic numbers; makes the realistic-scale assumption auditable and tunable per deployment. |
| Q5 | **Backend frozen by default; narrowly scoped backend changes permitted only if required for correctness/perf at the new layout scale**, with explicit rationale in the implementation plan. | Lowest-risk path while leaving an honest escape hatch — e.g. if the large single-window request reveals an N+1 or missing index at ~100 teachers, fixing it is in scope. |

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

**Compact fallback for narrow / common laptop widths** (mandatory, not optional):

To prevent wrapping or crowding on common laptop widths (1280–1440 px), the sticky band must degrade gracefully along these breakpoints — measured against the *band's own width* (not the viewport), so it works correctly when a sidebar is open:

| Breakpoint | Title | Action buttons | Draft chip |
|---|---|---|---|
| `≥ 1280 px` (default) | Full text `"الجدول الرئيسي"` | Full labels: `إنشاء الجدول تلقائياً` · `نشر الجدول` · `تسجيل غياب` · refresh icon | Full chip with label |
| `1024–1279 px` (compact) | Full text | Buttons collapse to **icon + short label** (`توليد` · `نشر` · `غياب` · refresh) | Full chip |
| `< 1024 px` (dense) | Drop the `<h2>` from the sticky band entirely (title only appears in the page header above the sticky band, which has scrolled away) | Buttons collapse to **icon-only** with `aria-label` and tooltip | Icon-only chip with tooltip |

Implementation: a single `ResizeObserver` on the sticky band toggles `data-density="default|compact|dense"` on the band element; CSS reads this attribute. **No JS-driven hide/show inside React render** — the attribute drives Tailwind classes, so no flicker on resize. The density floor for the action band is **never to wrap**: if at any width a wrap would occur, drop to the next density level instead.

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

### 4.5 Teacher window size — named configurable constant

The frontend never sends a magic literal `200`. Instead, it reads a single named constant exported from a central location:

```js
// frontend/src/config/scheduleConfig.js
export const MASTER_GRID_TEACHER_WINDOW = 200;
```

Naming rationale: the constant represents **"a large realistic single-school teacher window"**, not a pagination page size. Its semantic meaning is "request enough rows to display every teacher in any realistic single school in one paint." All call sites in the master-grid request path import this constant; no other file may inline the literal.

The underlying `teacher_page` / `teacher_page_size` paginated contract on the backend stays intact — only the UI affordance is removed (per Q4). If a deployment ever exceeds this value, the constant is bumped, or virtualization is introduced as a follow-up; no contract change required. The implementation plan must add a self-check that asserts `rg "teacher_page_size" frontend/src` returns no numeric literals other than this constant's definition.

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

## 7. Backend (frozen by default; narrowly scoped changes permitted)

The default expectation is **zero backend changes**. The Task #142 contract already supports the redesign exactly:

- Frontend will always send `teacher_page=1&teacher_page_size=MASTER_GRID_TEACHER_WINDOW` (see §4.5) plus `view=draft|published` and (daily) `day=<sunday..thursday>`.
- Substitution overlay scoping via `visible_teacher_ids` continues to work — at the configured window size the visible set covers every teacher in any realistic single school, so the overlay correctly includes everyone.
- RBAC, tenant scoping, N+1 protection, audit trails — all preserved.

**Permitted backend adjustments (only if required):**

The implementation may make narrowly scoped backend changes **only if** correctness or performance at the new ~100-teacher single-page layout scale demands it. Acceptable triggers:

1. A measurable N+1 surfaces on the master-grid endpoint at `MASTER_GRID_TEACHER_WINDOW`-sized requests that did not surface at the previous default page size (10/25/50). Fix: add eager-loading or `selectinload` on the affected relationship.
2. A missing index makes the windowed query exceed a reasonable budget (e.g. > 300 ms p95 at 100 teachers × 35 weekly slots). Fix: add the index via Alembic migration.
3. A response-payload bottleneck appears (e.g. duplicate teacher metadata serialized per slot) that materially affects time-to-first-paint. Fix: deduplicate at serialization.

**Not permitted under this license:**

- Changing the request/response schema of the master-grid endpoint.
- Changing publish / generate / absence / substitution contracts.
- Removing or renaming the `teacher_page` / `teacher_page_size` parameters.
- Any RBAC, tenant-scoping, or audit-trail change.

Any backend change must be called out **explicitly in the implementation plan** with a one-paragraph rationale before being applied, must ship with an Alembic migration if it touches schema, and must obey all `replit.md` deployment-safety rules (no destructive ops, Alembic-only schema changes, safe Arabic error envelopes).

## 8. Files touched

**Frontend (always)**:
- `frontend/src/config/scheduleConfig.js` — **new file**, exports `MASTER_GRID_TEACHER_WINDOW` (see §4.5).
- `frontend/src/pages/SchedulePageNew.jsx` — page composition, sticky band, KPI pill bar, action row, day-tabs band, drop pager UI, `--sticky-band-h` + `--day-band-h` CSS vars via `ResizeObserver`, density-attribute compact fallback (§4.2).
- `frontend/src/pages/SchedulePageNew.jsx` (`MasterMatrix` + `MasterMatrixSkeleton`) — drop fixed `height`, switch to natural document flow, bump daily `ROW_HEIGHT` to 96, weekly cell `min-w` 84 px, sticky offsets read from CSS vars, z-index pass.
- `frontend/src/pages/SchedulePageNew.jsx` (`SessionCell`) — empty-cell hairline + filled-cell inline-start subject bar. No hierarchy/testid changes.
- `frontend/src/services/apiClient.js` (or wherever the master-grid request is built) — import and use `MASTER_GRID_TEACHER_WINDOW` instead of any literal page-size value.
- `frontend/src/locales/ar.json` + `en.json` — short-label microcopy for compact density (`توليد` / `نشر` / `غياب`) plus tooltip strings for dense density.

**Backend (conditional)**: see §7. Files only touched if a §7 trigger fires; in that case the implementation plan must list them explicitly with rationale before edits begin.

**Explicitly NOT touched (under any circumstances)**:
- Master-grid endpoint request/response schema.
- `appRoutes.js`, RBAC, tab strip, routing.
- Substitution / absence / publish / generate handler logic — only their *layout container* changes.
- `replit.md` (unless a new gotcha emerges; tracked separately).

## 9. Self-check gates (run before marking complete)

1. `rg -n "overflow-y" frontend/src/pages/SchedulePageNew.jsx` returns no matrix-region matches.
2. `rg -n "teacher_page_size" frontend/src` returns only the `MASTER_GRID_TEACHER_WINDOW` definition site and call sites that import the constant — no inline numeric literals.
3. Frontend production build succeeds with `DISABLE_ESLINT_PLUGIN=true npm run build` (matches existing project build path).
4. **Hard visual rejection check** (criterion #11): subjective review of the rendered page must not read as a card-framed table under dashboard chrome. If it does, iterate; do not mark complete.
5. **Hard space-allocation check** (criterion #12): on a 1280×800 laptop, measure the chrome stack above the matrix on first paint. Total must be ≤ KPI pill bar (≤ 48 px) + sticky band (≤ 88 px daily / ≤ 52 px weekly) + tab strip. If exceeded, iterate; do not mark complete.
6. Manual visual smoke: 100-teacher fixture (or production-like), daily mode at 1280×800 — matrix region ≥ 60 % of viewport on first paint, sticky band ≤ 88 px, page-level scroll smooth.
7. Manual visual smoke: weekly mode at 1280×800 — horizontal scroll inside matrix; sticky teacher column stays glued; sticky day-band stays glued; no chrome bleed outside the viewport.
8. Compact-fallback smoke at 1280, 1366, 1440, and 1024 px band-widths — sticky band never wraps; density attribute correctly toggles `default` / `compact` / `dense`.
9. Round-trip test for each preserved behavior: generate → draft view appears, publish → published view appears with notification toast, PUBLISH_BLOCKED → NassaqAlertDialog with violations, day switch → skeleton + chrome stays mounted.
10. If any backend change was applied under §7 license: it has an Alembic migration if schema-touching, an explicit rationale paragraph in the implementation plan, and obeys all `replit.md` deployment-safety rules.
11. Code review (architect) APPROVED.

## 10. Out of scope

- Cell-level visual redesign beyond the two deltas in §5 (filled bar, empty hairline). The #142 hierarchy contract is frozen.
- Mobile / narrow-viewport (< 768 px) treatment. Master timetable is a desktop workspace by product definition; existing responsive fallbacks are kept untouched.
- Row virtualization. Plain DOM at 100 sticky rows is well within modern browser capacity; if a 500-teacher edge case ever appears, virtualization is a follow-up task.
- Optimistic updates on absence/substitution. Server-authoritative cascading effects make optimism risky for a small UX gain.
- Tab strip, routing, RBAC.
- **Removing the underlying backend pagination contract.** The UI affordance for pagination is removed (Q4), but the `teacher_page` / `teacher_page_size` parameters on the master-grid endpoint are preserved exactly as in #142. Any future virtualization or progressive-loading work will reuse them without a contract change.

## 11. Risk register

| Risk | Mitigation |
|---|---|
| Sticky-tier offset drift if the action band reflows on resize. | `ResizeObserver` on the action band writes `--sticky-band-h` to the page wrapper; matrix sticky offsets read the var. Verified at mount + on `window.resize`. |
| 100 sticky DOM rows performance. | Plain DOM is fine in Chrome/Edge/Firefox up to 500+ rows; virtualization deferred. |
| Substitution overlay missing rows when window size is below actual teacher count. | `MASTER_GRID_TEACHER_WINDOW` covers every realistic single school; if a deployment exceeds it, the underlying paginated backend contract still works — bump the constant or introduce virtualization. Not a structural risk. |
| Removing pager UI breaks an existing user flow. | No other code in the app reads `pagination.page` from the master-grid response; removal of the affordance is safe. Verified via `rg "pagination" frontend/src`. The backend contract is preserved. |
| Drop of card framing makes the matrix bleed into adjacent UI. | A single `border-t` separates the matrix from the sticky band; the matrix's own header borders provide internal containment. |
| Larger window-size request reveals a previously latent N+1 / missing index on the master-grid endpoint. | Covered by the §7 narrowly-scoped backend license; fix at source via `selectinload` or Alembic-managed index, with an explicit rationale paragraph in the implementation plan. |
| Sticky band wraps or crowds on common laptop widths (1280–1440 px), especially with a sidebar open. | Mandatory compact-fallback breakpoints in §4.2, driven by `ResizeObserver` on the band (not the viewport), with an explicit "never wrap" floor that drops density level instead of wrapping. Self-check #8 verifies at 1024 / 1280 / 1366 / 1440 px. |
| Hard visual rejection rule (criterion #11) is subjective and could be argued. | Implementation plan must include an explicit screenshot or app-preview check at the self-check stage, compared side-by-side against the rejection criteria; if ambiguous, iterate before marking complete. |

## 12. Out-of-band changes to `replit.md`

None expected. The redesign does not change the stack, run/operate commands, architecture decisions, or user preferences. If any new gotcha emerges during implementation (e.g. a `--sticky-band-h` convention worth documenting), it gets added in a follow-up commit.
