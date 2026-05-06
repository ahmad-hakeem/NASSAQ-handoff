# Master Schedule — Workspace Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the master timetable page so the matrix becomes the page's primary workspace surface (no card-framed table feel, no nested vertical scroll, sticky band for controls, RTL-correct horizontal scroll affordance in weekly mode), preserving all #141 (draft/publish + entropy) and #142 (daily/weekly + backend windowing) behavior verbatim.

**Architecture:** Frontend-only structural redesign. The page wrapper switches from a fixed `h-[calc(100dvh-3.5rem)] … overflow-hidden` shell to natural document flow with a single sticky action band and a matrix region that scrolls only horizontally (weekly) and never vertically. A new `MASTER_GRID_TEACHER_WINDOW` constant replaces inline page-size literals; the pager UI is removed but the backend `teacher_page` / `teacher_page_size` contract is preserved. A `ResizeObserver`-driven `data-density` attribute on the sticky band degrades title + button labels at 1024–1279 px to prevent wrapping.

**Tech Stack:** React (CRACO), Tailwind CSS, Radix UI, react-i18next, existing `NassaqAlertDialog`. No new dependencies. Build path: `cd frontend && DISABLE_ESLINT_PLUGIN=true npm run build`.

**Reference spec:** `docs/superpowers/specs/2026-05-06-master-schedule-workspace-redesign-design.md`

---

## File Structure

**Create:**
- `frontend/src/config/scheduleConfig.js` — exports `MASTER_GRID_TEACHER_WINDOW`. Single responsibility: master-grid request-window configuration.

**Modify:**
- `frontend/src/pages/SchedulePageNew.jsx` — page composition, sticky band with density attribute, KPI pill bar, drop pager UI + state, overflow detection + NassaqAlertDialog, MasterMatrix sticky offsets / row height / weekly cell `min-w`, MasterMatrixSkeleton row height alignment, weekly horizontal-overflow discoverability fades, page-level scroll architecture.
- `frontend/src/locales/ar.json` — add compact-density short labels + overflow-notice copy.
- `frontend/src/locales/en.json` — add the same keys (English mirrors).

**Do not touch (under any circumstances):**
- Any `backend/**` file (unless a §7 spec trigger fires; if so, add a separate task with explicit rationale).
- `appRoutes.js`, RBAC, tab strip, routing.
- Substitution / absence / publish / generate handler logic — only their layout container changes.
- The `FilledCell` component (cell hierarchy contract from #142 is frozen).

---

## Task 1: Add `MASTER_GRID_TEACHER_WINDOW` configuration constant

**Files:**
- Create: `frontend/src/config/scheduleConfig.js`

- [ ] **Step 1: Create the config file**

```js
// frontend/src/config/scheduleConfig.js
//
// Master-grid request-window configuration.
//
// MASTER_GRID_TEACHER_WINDOW represents "a large realistic single-school
// teacher window" — the number of teacher rows the master timetable
// requests in a single payload so every teacher in any realistic single
// school is rendered in one paint. It is NOT a pagination page size;
// the page no longer exposes a pager UI (see Task 3). The underlying
// backend `teacher_page` / `teacher_page_size` contract from Task #142
// is preserved exactly — only the UI affordance is removed.
//
// If a deployment ever exceeds this value, the no-silent-truncation
// fallback (see Task 9) surfaces a NassaqAlertDialog notice; the
// constant can then be bumped, or virtualization introduced as a
// follow-up. Do not inline this literal anywhere else; import it.

export const MASTER_GRID_TEACHER_WINDOW = 200;
```

- [ ] **Step 2: Verify the constant is imported nowhere yet**

Run: `rg -n "MASTER_GRID_TEACHER_WINDOW" frontend/src`
Expected: only one match — the definition site.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/config/scheduleConfig.js
git commit -m "feat(schedule): add MASTER_GRID_TEACHER_WINDOW config constant"
```

---

## Task 2: Wire `loadGrid` to use the constant and remove pager state

**Files:**
- Modify: `frontend/src/pages/SchedulePageNew.jsx` (imports near top; pagination state block ~lines 1182–1287; pager UI block ~lines 1764–1816)

- [ ] **Step 1: Add the constant import**

Open `frontend/src/pages/SchedulePageNew.jsx`. Find the existing imports near the top of the file. Add a new import line (placement: alongside other relative imports — after the React/library imports and before component imports):

```js
import { MASTER_GRID_TEACHER_WINDOW } from '../config/scheduleConfig';
```

- [ ] **Step 2: Replace the pagination state block with a single non-paged window**

Locate the block that begins with `// ── View mode + pagination state (Task #138) ─────────────────────────` (around line 1182) and ends just before the JSX return (around line 1287 — covers `PAGE_SIZE_OPTIONS`, `pageSize`, `pageIndex`, `paginationStateRef`, `safePage`, `totalPages`, `pageStartIdx`, `pageEndIdx`, the `useEffect` that resets `pageIndex` on `pageSize` change, and the `lastFetchedPaginationRef` window-fetch effect).

Replace that entire block (preserve `viewMode`, `selectedDay`, and the localStorage persistence of `viewMode` — those are Task #142 behavior and stay) with the following:

```js
  // ── View mode (Task #142) — pager removed (workspace redesign) ────
  // The master grid no longer exposes a pager UI. Instead it requests
  // a single large window sized by MASTER_GRID_TEACHER_WINDOW (see
  // config/scheduleConfig.js). The backend `teacher_page` /
  // `teacher_page_size` contract from Task #142 is preserved verbatim;
  // only the UI affordance is removed. If the server reports
  // `pagination.total > MASTER_GRID_TEACHER_WINDOW`, the
  // no-silent-truncation handler in Task 9 surfaces a NassaqAlertDialog.

  const [viewMode, setViewMode] = useState(() => {
    try {
      const v = localStorage.getItem('nassaq_master_grid_view_mode');
      return v === 'daily' ? 'daily' : 'weekly';
    } catch { return 'weekly'; }
  });
  useEffect(() => {
    try { localStorage.setItem('nassaq_master_grid_view_mode', viewMode); } catch {}
  }, [viewMode]);

  const [selectedDay, setSelectedDay] = useState(null);

  // Mirror current view/day into a ref so loadGrid's stable callback
  // can read it without re-creating on every render. The single window
  // size is constant across the session.
  const paginationStateRef = useRef({
    pageIndex: 0,
    pageSize: MASTER_GRID_TEACHER_WINDOW,
    day: null,
  });

  // Task #142 — totals come from the backend pagination block.
  const totalTeachersAll = grid?.pagination?.total ?? teacherRows.length;
  const pagedTeachers = teacherRows;

  const dayParam = viewMode === 'daily' ? selectedDay : null;

  // Re-fetch when the view-mode or selected day changes. The window
  // size never changes, so we drop the old pageSize-driven effect.
  const lastFetchedRef = useRef({ day: null, mode: null });
  useEffect(() => {
    if (tab !== 'master') return;
    paginationStateRef.current = {
      pageIndex: 0,
      pageSize: MASTER_GRID_TEACHER_WINDOW,
      day: dayParam,
    };
    const last = lastFetchedRef.current;
    if (last.day === dayParam && last.mode === viewMode) return;
    lastFetchedRef.current = { day: dayParam, mode: viewMode };
    loadGrid(undefined, {
      page: 1,
      pageSize: MASTER_GRID_TEACHER_WINDOW,
      day: dayParam,
    });
  }, [viewMode, dayParam, tab, loadGrid]);
```

(The `selectedDay` initialization-to-today effect that lived inside the old block — if any — should be preserved verbatim. Search for `setSelectedDay(` calls outside the block above and keep them as-is.)

- [ ] **Step 3: Remove the pager footer JSX**

Find the block that begins with the comment `{/* ── Pagination footer (Task #138) ─────────────────────────` (around line 1764) and ends with the closing `)}` of the `{!loading && !error && teacherRows.length > 0 && (...)}` conditional (around line 1816). **Delete the entire block.** Do not delete the `{/* ── Absence dialog ─────────────────────────────────────── */}` block that follows it.

- [ ] **Step 4: Update the `MasterMatrixSkeleton` invocation to use the window constant**

Find the `MasterMatrixSkeleton` invocation (around line 1669):

```js
            <MasterMatrixSkeleton
              rows={pageSize}
```

Replace `rows={pageSize}` with:

```js
              rows={Math.min(MASTER_GRID_TEACHER_WINDOW, totalTeachersAll || 12)}
```

(Rationale: skeleton row count tracks the actual teacher count when known, falling back to a reasonable 12-row sketch on first paint before any data has arrived. We never render the full `MASTER_GRID_TEACHER_WINDOW` rows of skeleton — that would be 200 placeholder rows on first paint.)

- [ ] **Step 5: Verify no other code references the removed pagination state**

Run: `rg -n "pageSize|pageIndex|setPageSize|setPageIndex|safePage|totalPages|pageStartIdx|pageEndIdx|PAGE_SIZE_OPTIONS|paginationPrev|paginationNext|paginationPageSize|paginationRangeLabel|paginationPageOf|page-prev|page-next|page-size-select|page-indicator" frontend/src/pages/SchedulePageNew.jsx`

Expected: no matches in `SchedulePageNew.jsx` after the changes. If any remain, remove them or audit whether they belong to an unrelated component (none should, per the spec's risk-register check).

- [ ] **Step 6: Verify the constant is now used**

Run: `rg -n "teacher_page_size|MASTER_GRID_TEACHER_WINDOW" frontend/src`
Expected: definition site in `scheduleConfig.js`, import + 2–3 uses in `SchedulePageNew.jsx`, and the existing `teacher_page_size` parameter inside the `loadGrid` request body (which reads from `effectivePageSize` derived from `paginationStateRef.current.pageSize`). No inline numeric literal `200` for page size anywhere in `frontend/src`.

- [ ] **Step 7: Build to confirm no syntax errors**

Run: `cd frontend && DISABLE_ESLINT_PLUGIN=true CI=false npm run build 2>&1 | tail -20`
Expected: build succeeds.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/SchedulePageNew.jsx
git commit -m "refactor(schedule): use MASTER_GRID_TEACHER_WINDOW; drop pager state and footer"
```

---

## Task 3: Drop the page-shell `overflow-hidden` and switch to document flow

**Files:**
- Modify: `frontend/src/pages/SchedulePageNew.jsx` (page wrapper ~line 1340; matrix container ~lines 1662–1666)

- [ ] **Step 1: Open the page wrapper and remove the fixed-height shell**

Locate the wrapper `<div>` immediately inside `<Sidebar>` (around line 1338–1341):

```jsx
      <div
        dir={direction}
        className="flex flex-col h-[calc(100dvh-3.5rem)] lg:h-[100dvh] p-4 md:p-6 gap-5 bg-slate-50 text-slate-900 overflow-hidden"
      >
```

Replace with:

```jsx
      <div
        dir={direction}
        data-master-schedule-root
        className="flex flex-col min-h-[100dvh] bg-slate-50 text-slate-900"
        style={{ '--sticky-band-h': '72px', '--day-band-h': '0px' }}
      >
```

Rationale: the page is no longer a flex column with `overflow-hidden`; vertical scroll is the document. The two CSS custom properties default-fall-back to safe values; Task 4 wires them to a real `ResizeObserver`. The `data-master-schedule-root` attribute lets us target the scroll context unambiguously in the spec self-check (`rg -n "overflow-y" … data-master-schedule-root` chain).

- [ ] **Step 2: Strip the matrix container's card framing and inner overflow**

Locate the `<div data-testid="master-matrix-container" …>` block (around lines 1662–1666):

```jsx
        <div
          data-testid="master-matrix-container"
          className={`relative flex-1 min-h-0 bg-white border border-slate-200/80 rounded-xl shadow-sm ${
            viewMode === 'daily' ? 'overflow-x-hidden overflow-y-auto' : 'overflow-auto'
          }`}
        >
```

Replace with:

```jsx
        <div
          data-testid="master-matrix-container"
          data-matrix-overflow={viewMode === 'weekly' ? 'horizontal' : 'none'}
          className={`relative bg-white border-t border-slate-200 ${
            viewMode === 'weekly' ? 'overflow-x-auto overflow-y-visible' : 'overflow-visible'
          }`}
        >
```

Rationale: removes the card framing (`rounded-xl`, `shadow-sm`, full border) that creates the "table embedded in a card" feel; replaces with a single inline-top border to separate the matrix from the sticky band; removes `flex-1 min-h-0`; drops `overflow-y-auto` entirely. Daily mode has no scroll on the wrapper; weekly mode scrolls horizontally only. The `data-matrix-overflow` attribute is read by the discoverability affordance in Task 8.

- [ ] **Step 3: Verify the no-nested-overflow-y rule**

Run: `rg -n "overflow-y" frontend/src/pages/SchedulePageNew.jsx`
Expected: only matches inside dialog/drawer/sheet content (e.g. `max-h-[55vh] overflow-y-auto pe-1` in the absence dialog, the bulk substitution drawer, etc.) — never on the page wrapper, the sticky band, the matrix container, or any ancestor in the master schedule content chain. If any match is on the schedule content chain, fix it before continuing.

- [ ] **Step 4: Build to confirm no syntax errors**

Run: `cd frontend && DISABLE_ESLINT_PLUGIN=true CI=false npm run build 2>&1 | tail -20`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SchedulePageNew.jsx
git commit -m "refactor(schedule): drop page-shell overflow-hidden; matrix uses document scroll"
```

---

## Task 4: Add the sticky action band with `--sticky-band-h` ResizeObserver and density attribute

**Files:**
- Modify: `frontend/src/pages/SchedulePageNew.jsx` (header block ~lines 1346–1490; day-tabs block ~lines 1612–1654)

This task changes the page composition: the existing header block (title + action buttons) and the day-tabs row are unified into a single sticky band. The KPI strip stays in its current position (above the sticky band) — Task 5 collapses its visual treatment into a slim pill bar that scrolls away.

- [ ] **Step 1: Add helper hooks at the top of the page component**

Find the line that begins `function SchedulePageNew(` (the main component). Inside the function, after the existing `useState`/`useRef` declarations and before `loadGrid`, add:

```js
  // ── Sticky band density + height tracking (workspace redesign) ────
  // The sticky action band exposes its measured height to the matrix
  // header offsets via the `--sticky-band-h` CSS custom property on
  // the page root. A second ResizeObserver on the band's own width
  // toggles `data-density` to prevent wrapping at 1024–1279 px.
  const stickyBandRef = useRef(null);
  useEffect(() => {
    const band = stickyBandRef.current;
    if (!band) return;
    const root = band.closest('[data-master-schedule-root]');
    if (!root) return;
    const updateHeight = () => {
      const h = band.getBoundingClientRect().height || 72;
      root.style.setProperty('--sticky-band-h', `${Math.round(h)}px`);
    };
    const updateDensity = () => {
      const w = band.getBoundingClientRect().width || 1280;
      let density = 'default';
      if (w < 1024) density = 'dense';
      else if (w < 1280) density = 'compact';
      band.setAttribute('data-density', density);
    };
    const ro = new ResizeObserver(() => {
      updateHeight();
      updateDensity();
    });
    ro.observe(band);
    updateHeight();
    updateDensity();
    return () => ro.disconnect();
  }, []);
```

- [ ] **Step 2: Replace the existing header + day-tabs block with a single sticky band**

Locate the block that starts with `{/* ── Header ───────────────────────────────────────────────── */}` (around line 1345) through the closing `</div>` of the header `<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 shrink-0">` (around line 1490). **Leave the lines above (the `<ScheduleTabNav>`) and the lines immediately below (the KPI strip block) untouched for now** — Task 5 handles KPI repositioning.

Currently the order on the page is:
1. ScheduleTabNav
2. Header (title + action buttons + view-mode toggle)
3. KPI strip
4. Draft banner
5. Smart alert banner
6. Hakim insights
7. Day-tabs row (daily mode only)
8. Matrix container

The new order will be:
1. ScheduleTabNav
2. KPI pill bar
3. Draft banner / alert banner / Hakim insights (slim, all `shrink-0`)
4. **STICKY BAND**: title + action buttons + view-mode toggle (row 1) + day-tabs (row 2, daily only)
5. Matrix container

Step 2a: **Delete** the existing header block (lines 1345–1490) entirely. **Delete** the existing day-tabs block (lines 1612–1654) entirely.

Step 2b: **Insert** a new sticky band block immediately above the matrix container `<div data-testid="master-matrix-container" …>`. The exact JSX:

```jsx
        {/* ── Sticky action band (workspace redesign) ─────────────────
            Top: 0; height exposed to matrix header offsets via
            --sticky-band-h. Density attribute degrades title +
            button labels at narrow band widths to prevent wrapping. */}
        <div
          ref={stickyBandRef}
          data-testid="master-schedule-sticky-band"
          data-density="default"
          className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-slate-200"
        >
          {/* Row 1: title + actions */}
          <div className="flex items-center justify-between gap-3 px-4 md:px-6 py-2 min-w-0">
            <div className="flex items-center gap-2 min-w-0">
              <Sparkles className="h-5 w-5 text-violet-600 shrink-0" />
              <h2
                data-band-title
                className="text-base md:text-lg font-bold text-[#1C3D74] truncate"
              >
                {t('smartSchedulesTitle')}
              </h2>
              {grid?.timetable_status === 'draft' && (
                <span
                  data-testid="draft-status-chip"
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300 shrink-0"
                  title={t('draftScheduleBanner')}
                >
                  <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                  <span data-band-chip-label>{t('scheduleViewDraft')}</span>
                </span>
              )}
            </div>

            <div className="flex items-center gap-1.5 shrink-0">
              {/* View toggle (draft/published) */}
              <div
                role="tablist"
                aria-label={t('scheduleViewToggleLabel')}
                className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 shadow-sm"
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={scheduleView === 'published'}
                  onClick={() => setScheduleView('published')}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                    scheduleView === 'published'
                      ? 'bg-emerald-600 text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                  data-testid="schedule-view-published"
                >
                  {t('scheduleViewPublished')}
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={scheduleView === 'draft'}
                  onClick={() => setScheduleView('draft')}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                    scheduleView === 'draft'
                      ? 'bg-amber-500 text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                  data-testid="schedule-view-draft"
                >
                  {t('scheduleViewDraft')}
                </button>
              </div>

              {/* View mode toggle (daily/weekly) */}
              <div
                role="tablist"
                aria-label={t('masterGridViewModeLabel')}
                className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 shadow-sm"
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={viewMode === 'daily'}
                  onClick={() => setViewMode('daily')}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                    viewMode === 'daily'
                      ? 'bg-[#1C3D74] text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                  data-testid="view-mode-daily"
                >
                  {t('dailyViewLabel')}
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={viewMode === 'weekly'}
                  onClick={() => setViewMode('weekly')}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                    viewMode === 'weekly'
                      ? 'bg-[#1C3D74] text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                  data-testid="view-mode-weekly"
                >
                  {t('weeklyViewLabel')}
                </button>
              </div>

              {/* Generate */}
              <Button
                onClick={handleAutoGenerate}
                disabled={generating}
                className="bg-violet-600 hover:bg-violet-700 text-white shadow-sm h-8 px-2.5"
                data-band-action="generate"
                title={t('autoGenerateSchedule')}
                aria-label={t('autoGenerateSchedule')}
              >
                {generating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Wand2 className="h-4 w-4" />
                )}
                <span data-band-action-label className="ms-1.5">
                  {generating ? t('generatingSchedule') : t('autoGenerateSchedule')}
                </span>
                <span data-band-action-label-short className="ms-1.5 hidden">
                  {t('autoGenerateScheduleShort')}
                </span>
              </Button>

              {/* Publish */}
              {(() => {
                const noDraft = !(grid?.timetable_status === 'draft');
                const disabled = publishing || noDraft;
                const tooltip = noDraft
                  ? t('publishScheduleNoDraftTooltip')
                  : t('publishScheduleAction');
                return (
                  <Button
                    onClick={handlePublish}
                    disabled={disabled}
                    title={tooltip}
                    aria-label={tooltip}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm disabled:opacity-50 disabled:cursor-not-allowed h-8 px-2.5"
                    data-testid="publish-schedule-btn"
                    data-band-action="publish"
                  >
                    {publishing ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4" />
                    )}
                    <span data-band-action-label className="ms-1.5">
                      {publishing ? t('publishingSchedule') : t('publishScheduleAction')}
                    </span>
                    <span data-band-action-label-short className="ms-1.5 hidden">
                      {t('publishScheduleActionShort')}
                    </span>
                  </Button>
                );
              })()}

              {/* Record absence */}
              <Button
                onClick={handleLogAbsence}
                variant="outline"
                className="border-slate-300 text-slate-700 hover:bg-slate-100 h-8 px-2.5"
                data-band-action="absence"
                title={t('recordAbsence')}
                aria-label={t('recordAbsence')}
              >
                <UserX className="h-4 w-4" />
                <span data-band-action-label className="ms-1.5">
                  {t('recordAbsence')}
                </span>
                <span data-band-action-label-short className="ms-1.5 hidden">
                  {t('recordAbsenceShort')}
                </span>
              </Button>

              {/* Refresh */}
              <Button
                onClick={handleRefresh}
                variant="ghost"
                size="icon"
                disabled={refreshing}
                title={t('refreshTooltip')}
                aria-label={t('refreshTooltip')}
                className="h-8 w-8"
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>

          {/* Row 2: day tabs (daily mode only) */}
          {viewMode === 'daily' && days.length > 0 && (
            <div
              data-testid="day-tabs-row"
              className="flex flex-wrap items-center gap-2 px-4 md:px-6 pb-2"
            >
              <div
                role="tablist"
                aria-label={t('selectDayLabel')}
                className={`inline-flex flex-wrap gap-1 rounded-lg border border-slate-200 bg-white p-0.5 shadow-sm ${loading ? 'opacity-70' : ''}`}
              >
                {days.map((dayKey) => {
                  const isActive = selectedDay === dayKey;
                  const isToday = todayKey === dayKey;
                  return (
                    <button
                      key={`day-tab-${dayKey}`}
                      type="button"
                      role="tab"
                      aria-selected={isActive}
                      disabled={loading}
                      onClick={() => setSelectedDay(dayKey)}
                      className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors flex items-center gap-1 disabled:cursor-wait ${
                        isActive
                          ? 'bg-[#2BB5A0] text-white shadow-sm'
                          : 'text-slate-600 hover:bg-slate-100'
                      }`}
                      data-testid={`day-tab-${dayKey}`}
                    >
                      {dayLabelMap[dayKey] || dayKey}
                      {isToday && (
                        <span className={`text-[9px] px-1 rounded ${isActive ? 'bg-white/25 text-white' : 'bg-emerald-100 text-emerald-700'}`}>
                          {t('todayBadge')}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
```

- [ ] **Step 3: Add density-driven CSS for label collapsing**

Tailwind alone cannot read a `data-density` attribute on the parent and toggle children. Add a small CSS block to the page module. The simplest path is a `<style>` tag in the page (acceptable for a page-scoped concern; no new file required). Insert immediately above the sticky band JSX block:

```jsx
        <style>{`
          [data-master-schedule-root] [data-testid="master-schedule-sticky-band"][data-density="compact"] [data-band-action-label] { display: none; }
          [data-master-schedule-root] [data-testid="master-schedule-sticky-band"][data-density="compact"] [data-band-action-label-short] { display: inline; }
          [data-master-schedule-root] [data-testid="master-schedule-sticky-band"][data-density="dense"] [data-band-action-label],
          [data-master-schedule-root] [data-testid="master-schedule-sticky-band"][data-density="dense"] [data-band-action-label-short],
          [data-master-schedule-root] [data-testid="master-schedule-sticky-band"][data-density="dense"] [data-band-title],
          [data-master-schedule-root] [data-testid="master-schedule-sticky-band"][data-density="dense"] [data-band-chip-label] { display: none; }
        `}</style>
```

(Note: at `dense` the sticky band drops the title text, the chip label, and all action labels — only icons remain. Tooltips on the buttons preserve discoverability.)

- [ ] **Step 4: Verify no duplicate header / day-tabs JSX remains**

Run: `rg -n "smartSchedulesTitle|day-tabs-row|publish-schedule-btn|view-mode-daily" frontend/src/pages/SchedulePageNew.jsx`
Expected: each testid appears exactly once. If any appear twice, the old block was not fully deleted in Step 2a.

- [ ] **Step 5: Build to confirm no syntax errors**

Run: `cd frontend && DISABLE_ESLINT_PLUGIN=true CI=false npm run build 2>&1 | tail -20`
Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SchedulePageNew.jsx
git commit -m "feat(schedule): unify header + day-tabs into sticky band with density fallback"
```

---

## Task 5: Reduce KPI strip to a thin pill row and remove the standalone draft banner

**Files:**
- Modify: `frontend/src/pages/SchedulePageNew.jsx` (KPI strip ~lines 1492–1540; draft banner ~lines 1542–1554)

The `KpiCard` component already produces a compact pill (it was reduced in Task #142). We only need to (a) tighten the strip's vertical chrome around it and (b) remove the standalone draft banner — its replacement (the chip in the sticky band) was added in Task 4.

- [ ] **Step 1: Tighten the KPI strip wrapper**

Locate the existing KPI strip block (around lines 1492–1540) — the comment begins `{/* ── KPI strip (Task #142) ────────────────────────────────────`. Replace the wrapper `<div className="grid grid-cols-2 sm:grid-cols-4 gap-2 shrink-0">` with:

```jsx
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 px-4 md:px-6 pt-3">
```

(Drop `shrink-0` — it's a no-op now that the page wrapper isn't a flex-with-overflow shell. Add horizontal padding to match the sticky band. Add `pt-3` so the KPIs sit close to the tab strip above them but the band below still has its own border separator.)

The four `<KpiCard>` children stay unchanged.

- [ ] **Step 2: Remove the standalone draft banner**

Locate the block:

```jsx
        {/* ── Task #141 — Draft banner ─────────────────────────────
            Shown whenever the currently-displayed timetable is a
            DRAFT, to make it visually obvious that what the admin is
            looking at is NOT yet visible to teachers/students. */}
        {grid?.timetable_status === 'draft' && (
          <div
            className="flex items-center gap-3 p-3 rounded-lg border border-amber-300 bg-amber-50 text-amber-900 shrink-0"
            data-testid="draft-banner"
          >
            <AlertTriangle className="h-5 w-5 shrink-0" />
            <p className="text-sm font-medium">{t('draftScheduleBanner')}</p>
          </div>
        )}
```

**Delete** this block entirely. The chip in the sticky band (added in Task 4 with `data-testid="draft-status-chip"`) replaces it.

- [ ] **Step 3: Tighten the smart-alert and Hakim banner wrappers**

Locate the smart alert banner block (immediately following the deleted draft banner). Replace the wrapper `className` `"flex items-center gap-3 p-3 rounded-lg border border-red-300 bg-red-50 text-red-800 shrink-0"` with the same string but drop `shrink-0`:

```jsx
            className="flex items-center gap-3 p-3 mx-4 md:mx-6 rounded-lg border border-red-300 bg-red-50 text-red-800"
```

Apply the same treatment (drop `shrink-0`, add `mx-4 md:mx-6`) to the `HakimInsightsBanner` wrapper inside its component if it has `shrink-0` — otherwise leave alone.

- [ ] **Step 4: Search for any orphaned references to the old draft banner testid**

Run: `rg -n "draft-banner" frontend/src`
Expected: zero matches (or only inside test files that should be migrated to `draft-status-chip`). If a test file references it, update the testid in that test to `draft-status-chip`.

- [ ] **Step 5: Build to confirm no syntax errors**

Run: `cd frontend && DISABLE_ESLINT_PLUGIN=true CI=false npm run build 2>&1 | tail -20`
Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SchedulePageNew.jsx frontend/src/**/*test*
git commit -m "refactor(schedule): collapse KPI strip padding; replace draft banner with band chip"
```

---

## Task 6: Update `MasterMatrix` sticky offsets to use CSS vars; bump row heights; weekly cell `min-w` 84 px

**Files:**
- Modify: `frontend/src/pages/SchedulePageNew.jsx` (`MasterMatrix` ~lines 2085–2349; `MasterMatrixSkeleton` ~lines 178–254)

- [ ] **Step 1: Update `MasterMatrix` row + cell sizing**

In `MasterMatrix`, locate the constants block (around lines 2120–2122):

```js
  const DAY_HEADER_HEIGHT = isDaily ? 40 : 36;
  const PERIOD_HEADER_HEIGHT = isDaily ? 44 : 38;
  const ROW_HEIGHT = isDaily ? 92 : 64;
```

Replace with:

```js
  const DAY_HEADER_HEIGHT = isDaily ? 40 : 36;
  const PERIOD_HEADER_HEIGHT = isDaily ? 44 : 38;
  const ROW_HEIGHT = isDaily ? 96 : 88;
```

(Daily 92 → 96 px and weekly 64 → 88 px per spec §3 / §5; weekly height bump trades a denser cell-text floor from #142 for visual breathing room at 100-row scale.)

- [ ] **Step 2: Update the `gridTemplate` to widen weekly cells to ≥84 px**

A few lines below, locate:

```js
  const gridTemplate = isDaily
    ? `clamp(220px, 22vw, 280px) repeat(${totalDataCols}, minmax(0, 1fr))`
    : `clamp(170px, 14vw, 210px) repeat(${totalDataCols}, minmax(76px, 1fr))`;
```

Replace with:

```js
  const gridTemplate = isDaily
    ? `clamp(220px, 22vw, 280px) repeat(${totalDataCols}, minmax(0, 1fr))`
    : `clamp(220px, 22vw, 280px) repeat(${totalDataCols}, minmax(84px, 1fr))`;
```

(Spec §3: weekly teacher column matches daily width — `clamp(220px, 22vw, 280px)` — and weekly cells anchor at ≥84 px per spec §3.)

- [ ] **Step 3: Replace sticky `top: 0` and `top: DAY_HEADER_HEIGHT` with CSS-var-driven offsets**

In `MasterMatrix`, locate the four sticky-positioned cells in the JSX (corner, day-band cells, period-row corner, period header cells). Update their `style` to read from `--sticky-band-h` and `--day-band-h`:

For the **corner cell** (around line 2148–2154), change:

```js
        style={{ insetInlineStart: 0, zIndex: 30, height: DAY_HEADER_HEIGHT }}
```

to:

```js
        style={{ top: 'var(--sticky-band-h, 72px)', insetInlineStart: 0, zIndex: 30, height: DAY_HEADER_HEIGHT }}
```

Also **remove the `sticky top-0`** from the className and replace with just `sticky`:

Change the className block from `\`sticky top-0 bg-slate-50 …\`` to `\`sticky bg-slate-50 …\``.

For each **day-band header cell** (around lines 2155–2169), change the className to drop `top-0`:

From `\`sticky top-0 z-20 ${getDayBandClass(dayKey)} …\`` to `\`sticky z-20 ${getDayBandClass(dayKey)} …\``.

And add `top` to the `style` prop:

```js
          style={{ top: 'var(--sticky-band-h, 72px)', gridColumn: `span ${periods.length}`, height: DAY_HEADER_HEIGHT }}
```

For the **period-row corner cell** (around lines 2172–2177), change:

```js
        style={{ top: DAY_HEADER_HEIGHT, insetInlineStart: 0, zIndex: 30, height: PERIOD_HEADER_HEIGHT }}
```

to:

```js
        style={{ top: `calc(var(--sticky-band-h, 72px) + ${DAY_HEADER_HEIGHT}px)`, insetInlineStart: 0, zIndex: 30, height: PERIOD_HEADER_HEIGHT }}
```

For each **period header cell** (around lines 2186–2197), change:

```js
              style={{ top: DAY_HEADER_HEIGHT, height: PERIOD_HEADER_HEIGHT }}
```

to:

```js
              style={{ top: `calc(var(--sticky-band-h, 72px) + ${DAY_HEADER_HEIGHT}px)`, height: PERIOD_HEADER_HEIGHT }}
```

Update the `--day-band-h` CSS var on the page root from `MasterMatrix` so the var stays in sync. Find the existing `useEffect` block in the page component (added in Task 4) that updates `--sticky-band-h`. **No change needed there** — the day-band height is constant per view-mode and is already encoded inside `MasterMatrix`'s `top: calc(...)` expression. We only need `--day-band-h` if a downstream consumer reads it; the matrix uses `DAY_HEADER_HEIGHT` directly.

- [ ] **Step 4: Update the teacher-column sticky cells (no z-index change, just verify)**

Locate the body-row teacher cell (around line 2214–2218):

```js
            <div
              data-testid={`master-matrix-teacher-${teacher.id}`}
              className={`sticky z-10 ${isDaily ? 'px-4 py-3' : 'px-3 py-2'} border-b border-l border-slate-200 ${rowBg} ${teacherStickyShadow}`}
              style={{ insetInlineStart: 0, minHeight: ROW_HEIGHT }}
            >
```

This is already correct — `sticky z-10` with `insetInlineStart: 0` matches the spec layering table. No change required.

- [ ] **Step 5: Update `MasterMatrixSkeleton` row height to match**

In `MasterMatrixSkeleton` (around line 186):

```js
  const rowH = isDaily ? 92 : 64;
```

Replace with:

```js
  const rowH = isDaily ? 96 : 88;
```

(Matches the live matrix so the skeleton → real grid swap doesn't shift layout.)

Also wire the skeleton's day-band header / period sub-header to be `position: sticky` with `--sticky-band-h` so the skeleton's first row aligns with the live matrix headers when the band is mounted above. Locate the day-band header div (around line 199):

```jsx
      <div
        className="bg-slate-100 border-b border-slate-200"
        style={{ height: dayBandH }}
      />
```

Replace with:

```jsx
      <div
        className="sticky bg-slate-100 border-b border-slate-200 z-30"
        style={{ top: 'var(--sticky-band-h, 72px)', insetInlineStart: 0, height: dayBandH }}
      />
```

(The skeleton corner stays sticky on both axes during loading. The other skeleton cells stay non-sticky — the skeleton is short enough that scrolling rarely happens during the loading state.)

- [ ] **Step 6: Build to confirm no syntax errors**

Run: `cd frontend && DISABLE_ESLINT_PLUGIN=true CI=false npm run build 2>&1 | tail -20`
Expected: build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/SchedulePageNew.jsx
git commit -m "feat(schedule): wire matrix sticky offsets to --sticky-band-h; bump row heights"
```

---

## Task 7: Cell visual deltas — empty-cell hairline + filled-cell inline-start subject bar

**Files:**
- Modify: `frontend/src/pages/SchedulePageNew.jsx` (`EmptyCell` ~line 264; outer cell wrapper inside `MasterMatrix` ~lines 2317–2334)

The `FilledCell` component lives in `frontend/src/components/schedule/FilledCell.jsx` (extracted in #142) and its hierarchy contract is **frozen** per the spec. The 3 px subject-color inline-start bar is added on the **outer wrapper** in `MasterMatrix` (not inside `FilledCell`), so the contract stays untouched.

- [ ] **Step 1: Update `EmptyCell` to include the dotted hairline + subtle background**

Locate the `EmptyCell` function (around lines 264–269):

```jsx
function EmptyCell() {
  return <div className="w-full h-full" />;
}
```

Replace with:

```jsx
function EmptyCell() {
  // Workspace-redesign visual: faint background tint + dotted hairline
  // at the bottom edge so the surface reads as structured, not as a
  // dead spreadsheet box. Stays quiet at 100-teacher density.
  return (
    <div className="w-full h-full bg-slate-50/40 border-b border-dashed border-slate-200/60" />
  );
}
```

- [ ] **Step 2: Add the 3 px inline-start subject bar to filled cells**

In `MasterMatrix`, locate the cell body wrapper (around lines 2318–2335):

```jsx
                return (
                  <div
                    key={`${teacher.id}-${dayKey}-${p}`}
                    className={`min-w-0 border-b border-l border-slate-100 p-0.5 ${conflictBg} ${isDayStart ? 'border-s-2 border-s-slate-300/70' : ''}`}
                    style={{ height: ROW_HEIGHT }}
                    title={conflictTip || undefined}
                  >
                    {cell ? (
                      <FilledCell
                        cell={cell}
                        dayKey={dayKey}
                        compact={!isDaily}
                        onClick={cell.is_vacant ? () => onVacantClick(cellData) : handleNormalClick}
                        onAcknowledgeRelocation={onAcknowledgeRelocation}
                      />
                    ) : (
                      <EmptyCell />
                    )}
                  </div>
                );
```

Replace with:

```jsx
                const subjectBarColor = cell && !cell.is_vacant
                  ? (cell.subject_color || '#1C3D74')
                  : null;
                return (
                  <div
                    key={`${teacher.id}-${dayKey}-${p}`}
                    className={`min-w-0 border-b border-l border-slate-100 p-0.5 ${conflictBg} ${isDayStart ? 'border-s-2 border-s-slate-300/70' : ''}`}
                    style={{
                      height: ROW_HEIGHT,
                      ...(subjectBarColor ? {
                        borderInlineStartWidth: '3px',
                        borderInlineStartStyle: 'solid',
                        borderInlineStartColor: subjectBarColor,
                      } : {}),
                    }}
                    title={conflictTip || undefined}
                  >
                    {cell ? (
                      <FilledCell
                        cell={cell}
                        dayKey={dayKey}
                        compact={!isDaily}
                        onClick={cell.is_vacant ? () => onVacantClick(cellData) : handleNormalClick}
                        onAcknowledgeRelocation={onAcknowledgeRelocation}
                      />
                    ) : (
                      <EmptyCell />
                    )}
                  </div>
                );
```

(Rationale: a 3 px inline-start bar uses the cell's `subject_color` if available, falling back to brand navy. The bar lives on the outer wrapper, so `FilledCell`'s internal hierarchy contract from #142 is untouched. RTL-correct via `borderInlineStart*`. Vacant cells skip the bar — they need to keep the conflict tint and existing affordances.)

If `cell.subject_color` is not present in the API payload, the fallback `'#1C3D74'` (brand navy) keeps the visual consistent. Verify the field exists by running:

`rg -n "subject_color" backend/`

If not present, the fallback is the only effective value — that is acceptable; the inline-start bar still provides the structural delta the spec requires. Do not change the backend payload.

- [ ] **Step 3: Build to confirm no syntax errors**

Run: `cd frontend && DISABLE_ESLINT_PLUGIN=true CI=false npm run build 2>&1 | tail -20`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SchedulePageNew.jsx
git commit -m "feat(schedule): add empty-cell hairline + filled-cell inline-start subject bar"
```

---

## Task 8: Add weekly horizontal-overflow discoverability affordance

**Files:**
- Modify: `frontend/src/pages/SchedulePageNew.jsx` (matrix container ~lines 1662–1666)

The matrix container currently scrolls horizontally in weekly mode but gives no visual cue that more content exists. This task adds RTL-aware inline-end and inline-start edge fades, toggled via a scroll listener.

- [ ] **Step 1: Add a scroll-position attribute hook near the existing density hook**

Inside the page component, near the existing `stickyBandRef` block (added in Task 4), add:

```js
  // ── Weekly matrix horizontal-overflow discoverability ──────────────
  // Toggles `data-can-scroll-end` and `data-can-scroll-start` on the
  // matrix container so the inline-end / inline-start edge fades
  // (defined in the JSX below) appear only when overflow exists in
  // that direction. RTL-correct: in RTL, `scrollLeft` is negative or
  // mirrored depending on browser; using `Math.abs(scrollLeft)` and
  // comparing against `scrollWidth - clientWidth` covers both.
  const matrixContainerRef = useRef(null);
  useEffect(() => {
    const el = matrixContainerRef.current;
    if (!el) return;
    const update = () => {
      const max = el.scrollWidth - el.clientWidth;
      const pos = Math.abs(el.scrollLeft);
      el.setAttribute('data-can-scroll-start', pos > 1 ? 'true' : 'false');
      el.setAttribute('data-can-scroll-end', pos < max - 1 ? 'true' : 'false');
    };
    update();
    el.addEventListener('scroll', update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => {
      el.removeEventListener('scroll', update);
      ro.disconnect();
    };
  }, [viewMode, grid]);
```

- [ ] **Step 2: Wire the matrix container to the ref and add edge-fade overlays**

Update the matrix container `<div>` (already modified in Task 3) to:

```jsx
        <div
          ref={matrixContainerRef}
          data-testid="master-matrix-container"
          data-matrix-overflow={viewMode === 'weekly' ? 'horizontal' : 'none'}
          className={`relative bg-white border-t border-slate-200 ${
            viewMode === 'weekly' ? 'overflow-x-auto overflow-y-visible' : 'overflow-visible'
          }`}
        >
          {/* Edge fades (weekly only) — toggled via data-can-scroll-{start,end} */}
          {viewMode === 'weekly' && (
            <>
              <div
                aria-hidden="true"
                data-testid="matrix-edge-fade-end"
                className="pointer-events-none sticky top-0 h-full w-6 z-[5] transition-opacity"
                style={{
                  insetInlineEnd: 0,
                  background: 'linear-gradient(to var(--fade-end-direction, left), rgba(248,250,252,0.95), rgba(248,250,252,0))',
                  opacity: 0,
                  marginInlineStart: 'auto',
                }}
              />
              <div
                aria-hidden="true"
                data-testid="matrix-edge-fade-start"
                className="pointer-events-none sticky top-0 h-full w-6 z-[5] transition-opacity"
                style={{
                  insetInlineStart: 0,
                  background: 'linear-gradient(to var(--fade-start-direction, right), rgba(248,250,252,0.95), rgba(248,250,252,0))',
                  opacity: 0,
                }}
              />
            </>
          )}
```

(Note: `sticky` overlays inside an `overflow-x-auto` container do not provide reliable edge-pinning across browsers when used naïvely. The simpler-and-correct alternative is an absolutely-positioned overlay outside the scroll container. Use this instead — replace the entire matrix container block with:)

Restart the matrix container block — discard the previous version of step 2 above and use this single canonical version:

```jsx
        <div className="relative" data-testid="master-matrix-region">
          {viewMode === 'weekly' && (
            <>
              <div
                aria-hidden="true"
                data-testid="matrix-edge-fade-end"
                className="pointer-events-none absolute top-0 bottom-0 w-6 z-[5] transition-opacity duration-150"
                style={{
                  insetInlineEnd: 0,
                  background: 'linear-gradient(to var(--scroll-fade-end-dir, left), rgba(255,255,255,1), rgba(255,255,255,0))',
                  opacity: 'var(--scroll-fade-end-opacity, 0)',
                }}
              />
              <div
                aria-hidden="true"
                data-testid="matrix-edge-fade-start"
                className="pointer-events-none absolute top-0 bottom-0 w-6 z-[5] transition-opacity duration-150"
                style={{
                  insetInlineStart: 0,
                  background: 'linear-gradient(to var(--scroll-fade-start-dir, right), rgba(255,255,255,1), rgba(255,255,255,0))',
                  opacity: 'var(--scroll-fade-start-opacity, 0)',
                }}
              />
            </>
          )}
          <div
            ref={matrixContainerRef}
            data-testid="master-matrix-container"
            data-matrix-overflow={viewMode === 'weekly' ? 'horizontal' : 'none'}
            className={`relative bg-white border-t border-slate-200 ${
              viewMode === 'weekly' ? 'overflow-x-auto overflow-y-visible' : 'overflow-visible'
            }`}
          >
```

(Wrap the existing `{loading ? <MasterMatrixSkeleton .../> : ... : <MasterMatrix .../>}` block and the `{generating && <HakimGeneratingOverlay />}` line inside this new container. The closing `</div>` of `master-matrix-container` and the closing `</div>` of `master-matrix-region` are both required.)

- [ ] **Step 3: Update the scroll-position hook to write CSS var opacities instead of attributes alone**

Replace the body of the `update` function inside the `matrixContainerRef` `useEffect` (added in Step 1 of this task) with:

```js
    const update = () => {
      const max = el.scrollWidth - el.clientWidth;
      const pos = Math.abs(el.scrollLeft);
      const region = el.parentElement;
      if (!region) return;
      const canStart = pos > 1;
      const canEnd = pos < max - 1;
      el.setAttribute('data-can-scroll-start', canStart ? 'true' : 'false');
      el.setAttribute('data-can-scroll-end', canEnd ? 'true' : 'false');
      region.style.setProperty('--scroll-fade-start-opacity', canStart ? '1' : '0');
      region.style.setProperty('--scroll-fade-end-opacity', canEnd ? '1' : '0');
      // Tailwind/RTL: fade direction always points away from the
      // matrix interior toward the viewport edge.
      const dir = document.documentElement.dir === 'rtl' ? 'rtl' : 'ltr';
      region.style.setProperty('--scroll-fade-end-dir', dir === 'rtl' ? 'right' : 'left');
      region.style.setProperty('--scroll-fade-start-dir', dir === 'rtl' ? 'left' : 'right');
    };
```

- [ ] **Step 4: Verify the JSX nests correctly**

Run: `rg -n "master-matrix-region|master-matrix-container|matrix-edge-fade" frontend/src/pages/SchedulePageNew.jsx`
Expected: each testid appears exactly once. The `master-matrix-region` opening `<div>` must wrap both the edge fades and the `master-matrix-container` div. Manually verify with a `read` of the relevant lines if uncertain.

- [ ] **Step 5: Build to confirm no syntax errors**

Run: `cd frontend && DISABLE_ESLINT_PLUGIN=true CI=false npm run build 2>&1 | tail -20`
Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SchedulePageNew.jsx
git commit -m "feat(schedule): add weekly horizontal-overflow discoverability fades"
```

---

## Task 9: Add no-silent-truncation guard via NassaqAlertDialog

**Files:**
- Modify: `frontend/src/pages/SchedulePageNew.jsx`

When the server returns `pagination.total > MASTER_GRID_TEACHER_WINDOW`, the page must surface this state to the user. The chosen fallback per the spec §4.5 is a NassaqAlertDialog notice (the "scoped pager restoration" path is heavier and not worth the carrying cost for an edge case that should rarely hit; the "bumped window" path is the real long-term answer if it ever does).

- [ ] **Step 1: Add NassaqAlertDialog import if not already present**

Run: `rg -n "NassaqAlertDialog" frontend/src/pages/SchedulePageNew.jsx | head -3`

If no import exists, add one. The import path for `NassaqAlertDialog` follows the pattern used elsewhere in the page; check via:

`rg -n "NassaqAlertDialog" frontend/src/components | head -3`

Add the import next to the other component imports near the top of the file (use whatever path the existing app convention has). If a hook-based variant `useNassaqAlert` is preferred (per the codebase pattern), use that instead — search the file for existing alert usages and follow the same pattern.

- [ ] **Step 2: Add overflow-detection state + effect**

Inside the page component, near the other `useState` declarations, add:

```js
  const [truncationNoticeShown, setTruncationNoticeShown] = useState(false);
```

Then, near the other effects, add:

```js
  // No-silent-truncation guard: if the server reports more teachers
  // than MASTER_GRID_TEACHER_WINDOW, surface a one-time NassaqAlertDialog
  // notice per session. The window itself is configurable (see
  // config/scheduleConfig.js); the long-term fix when this fires
  // repeatedly in a deployment is to bump the constant, not to
  // restore the pager UI. Tracked by `truncationNoticeShown` so the
  // notice only appears once per page mount.
  useEffect(() => {
    if (truncationNoticeShown) return;
    const total = grid?.pagination?.total;
    if (typeof total !== 'number') return;
    if (total <= MASTER_GRID_TEACHER_WINDOW) return;
    setTruncationNoticeShown(true);
    // Use whichever NassaqAlertDialog API the rest of the page uses.
    // If `nassaqWarning` is the imperative warning helper exposed via
    // a hook (see existing usages like nassaqError, nassaqConfirm,
    // nassaqWarning further up in this file), reuse it:
    if (typeof nassaqWarning === 'function') {
      nassaqWarning(
        t('masterGridTruncationTitle'),
        t('masterGridTruncationBody', {
          shown: MASTER_GRID_TEACHER_WINDOW,
          total,
        }),
      );
    }
  }, [grid?.pagination?.total, truncationNoticeShown, nassaqWarning, t]);
```

(Verify via `rg -n "nassaqWarning|nassaqError|nassaqConfirm" frontend/src/pages/SchedulePageNew.jsx | head -10` that the imperative helper exists and is already destructured from a hook in this file. The existing `handlePublish` and `handleAutoGenerate` use `nassaqError` and `nassaqConfirm` — follow the same destructuring pattern. If the helper isn't `nassaqWarning`, substitute the equivalent — `nassaqError` is acceptable as a fallback since this is an attention-required state.)

- [ ] **Step 3: Build to confirm no syntax errors**

Run: `cd frontend && DISABLE_ESLINT_PLUGIN=true CI=false npm run build 2>&1 | tail -20`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SchedulePageNew.jsx
git commit -m "feat(schedule): surface NassaqAlertDialog when teacher count exceeds window"
```

---

## Task 10: Add locale strings for compact-density labels and overflow notice

**Files:**
- Modify: `frontend/src/locales/ar.json`
- Modify: `frontend/src/locales/en.json`

- [ ] **Step 1: Add the new keys to `ar.json`**

Open `frontend/src/locales/ar.json`. Find an alphabetically reasonable insertion point (the existing keys are sorted neither alphabetically nor by feature — insert near related keys). Add:

```json
  "autoGenerateScheduleShort": "توليد",
  "publishScheduleActionShort": "نشر",
  "recordAbsenceShort": "غياب",
  "masterGridTruncationTitle": "عدد المعلمين يتجاوز نافذة العرض",
  "masterGridTruncationBody": "تُعرض حالياً أول {shown} معلماً من إجمالي {total}. يرجى التواصل مع الدعم لرفع حدّ النافذة.",
```

(The placement guidance: insert after the existing `paginationPageOf` / related schedule keys, or anywhere — the file is not sorted. Use a `read` + `edit` cycle: locate any existing key like `"recordAbsence"` and insert the new keys nearby.)

- [ ] **Step 2: Add the corresponding keys to `en.json`**

Open `frontend/src/locales/en.json` and add (at a parallel position):

```json
  "autoGenerateScheduleShort": "Generate",
  "publishScheduleActionShort": "Publish",
  "recordAbsenceShort": "Absence",
  "masterGridTruncationTitle": "Teacher count exceeds display window",
  "masterGridTruncationBody": "Showing the first {shown} of {total} teachers. Please contact support to raise the window limit.",
```

- [ ] **Step 3: Verify both locale files still parse as valid JSON**

Run: `node -e "JSON.parse(require('fs').readFileSync('frontend/src/locales/ar.json','utf8'));JSON.parse(require('fs').readFileSync('frontend/src/locales/en.json','utf8'));console.log('OK')"`
Expected: `OK`. If either file fails, fix the trailing-comma or quoting issue before continuing.

- [ ] **Step 4: Build to confirm no syntax errors**

Run: `cd frontend && DISABLE_ESLINT_PLUGIN=true CI=false npm run build 2>&1 | tail -20`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/locales/ar.json frontend/src/locales/en.json
git commit -m "i18n(schedule): add short-density labels and truncation-notice copy"
```

---

## Task 11: Self-check + visual verification + code review

**Files:** none (verification only)

- [ ] **Step 1: Restart frontend dev workflow and rebuild backend-served bundle**

The Backend API serves `frontend/build/` at port 8000 in production-like mode but the Frontend Dev workflow at port 5000 is what's normally used for in-browser preview. Restart Frontend Dev to pick up all changes:

```bash
# (use restart_workflow tool)
```

Verify both `Backend API` and `Frontend Dev` workflows are running.

- [ ] **Step 2: Run spec self-check #1 — no nested overflow-y in the schedule chain**

Run: `rg -n "overflow-y" frontend/src/pages/SchedulePageNew.jsx`
Expected: matches only inside the absence dialog, bulk substitution drawer, or HakimInsightsDrawer (`max-h-…vh] overflow-y-auto` patterns) — never on `data-master-schedule-root`, `master-schedule-sticky-band`, `master-matrix-region`, or `master-matrix-container`. If any match is on the master schedule content chain, fix it before continuing.

- [ ] **Step 3: Run spec self-check #2 — no inline `teacher_page_size` literals**

Run: `rg -n "teacher_page_size" frontend/src`
Expected: zero matches in `frontend/src` outside the `teacher_page_size: effectivePageSize` line in `loadGrid` (which derives the value from `paginationStateRef.current.pageSize` which itself is `MASTER_GRID_TEACHER_WINDOW`). Run a tighter check for inline numerics:

`rg -n "teacher_page_size:\s*\d" frontend/src`
Expected: zero matches.

- [ ] **Step 4: Run spec self-check #3 — production build**

Run: `cd frontend && DISABLE_ESLINT_PLUGIN=true CI=false npm run build 2>&1 | tail -25`
Expected: build succeeds; bundle size reasonable (no surprise blowup vs. baseline).

- [ ] **Step 5: Run spec self-check #4 — first-glance perception (visual)**

Take a screenshot of the master schedule page at 1280×800 in the running Frontend Dev preview:

```
# (use screenshot tool with type=app_preview, path=/school/schedule?tab=master)
```

Inspect the screenshot. The page must, **on first glance**, read as a workspace dominated by the matrix — not as a card-framed table sitting under dashboard chrome. Specifically check:

- The matrix has no rounded card framing.
- The KPI strip is a thin pill row, not tall cards.
- The sticky band sits directly above the matrix with a single inline-top border.
- The matrix region occupies ≥ 60 % of the viewport.

If any of these fail, iterate the relevant Task before continuing. Do not mark complete on a "technically correct but still feels boxed" result.

- [ ] **Step 6: Run spec self-check #5 — chrome budget**

In the same screenshot, measure (visually or via DOM inspection in DevTools) the total chrome stack above the matrix. Budget: `tab strip + KPI pill bar (≤ 48 px) + sticky band (≤ 88 px daily / ≤ 52 px weekly)`. If exceeded, iterate.

- [ ] **Step 7: Run spec self-check #6 — no-silent-truncation fallback exercised**

Temporarily edit `frontend/src/config/scheduleConfig.js` to set `MASTER_GRID_TEACHER_WINDOW = 5`. Reload the master schedule page. Confirm a NassaqAlertDialog appears with the truncation notice copy (Arabic). Restore the constant to `200` and reload to verify the dialog does not appear.

```bash
# After verification:
git checkout -- frontend/src/config/scheduleConfig.js
```

- [ ] **Step 8: Run spec self-check #7 — weekly horizontal-discoverability**

Switch to weekly mode in the running app. Confirm:
- At horizontal scroll position 0: the inline-end edge fade is visible; the inline-start fade is invisible.
- After scrolling fully to the inline-end-most position: the inline-end fade disappears and the inline-start fade appears.
- After scrolling back to position 0: the original state is restored.

Take a screenshot of weekly mode at 1280×800 to document.

- [ ] **Step 9: Run spec self-check #8 — sticky band no-wrap**

Resize the browser (or use DevTools device toolbar) to band widths 1024, 1280, 1366, and 1440 px. At each width:
- Confirm the sticky band stays on the intended number of rows (1 row in weekly, 2 rows in daily).
- Confirm `data-density` is `dense` at <1024 (which we don't formally support but should not crash), `compact` at 1024–1279, `default` at ≥1280.
- Confirm no buttons or labels wrap onto an extra line.

Inspect via DevTools: `document.querySelector('[data-testid="master-schedule-sticky-band"]').getAttribute('data-density')`.

- [ ] **Step 10: Run spec self-check #9 — daily mode visual smoke**

In daily mode at 1280×800:
- Matrix region occupies ≥ 60 % of viewport on first paint.
- Sticky band ≤ 88 px tall.
- Page-level scroll: scrolling the page scrolls the matrix rows; the sticky band stays glued to the top; the matrix headers stay glued under it; the teacher column stays glued at inline-start.

- [ ] **Step 11: Run spec self-check #10 — weekly mode visual smoke**

In weekly mode at 1280×800:
- Horizontal scroll inside the matrix only; the page chrome stays viewport-wide.
- Sticky teacher column stays glued during horizontal scroll.
- Sticky day-band stays glued during vertical scroll.
- No chrome bleed outside the viewport.

- [ ] **Step 12: Run spec self-check #11 — preserved behavior round-trip**

For each, confirm the existing behavior still works:
- Click "إنشاء الجدول تلقائياً" → after generation, view force-flips to draft and the new draft renders (Task #141 contract).
- Click "نشر الجدول" with a draft present → published view appears; success notification toast.
- Force a `PUBLISH_BLOCKED` (e.g. by publishing an inconsistent draft if one is available) → NassaqAlertDialog with violations appears (Task #141 contract).
- Switch days in daily mode → skeleton appears in the matrix region; sticky band stays mounted; new day renders.
- Click "تسجيل غياب" → absence dialog opens; recording an absence reloads the matrix in place.

If any of the above breaks, the layout restructure has touched logic that should have stayed frozen. Audit the relevant Task and fix.

- [ ] **Step 13: Backend perf check (per spec §7)**

If self-check #10 / #11 reveal a measurable slowdown (e.g. >300 ms p95) on the master-grid endpoint at `MASTER_GRID_TEACHER_WINDOW=200` that did not exist at the previous default `pageSize=10`, the spec §7 narrowly-scoped backend license activates. In that case:
- Add a new task to this plan with explicit rationale.
- Apply the fix at source (`selectinload`, missing index via Alembic migration, or serialization deduplication).
- Re-measure.
- Otherwise: no backend changes required.

- [ ] **Step 14: Code review (architect)**

Run code review per the `code_review` skill:

```js
await architect({
  task: "Master schedule workspace redesign — restructure SchedulePageNew.jsx to match docs/superpowers/specs/2026-05-06-master-schedule-workspace-redesign-design.md. Verify: hard rejection rule #11 (first-glance perception, not card-framed table), hard space-allocation rule #12, hard no-silent-truncation rule #13, hard horizontal-discoverability rule #14, hard no-wrap rule #15 are all satisfied. Verify Task #141 + #142 behavior is preserved verbatim. Backend frozen unless §7 license fired (in which case verify rationale and Alembic migration if applicable).",
  relevantFiles: [
    "frontend/src/pages/SchedulePageNew.jsx",
    "frontend/src/config/scheduleConfig.js",
    "frontend/src/locales/ar.json",
    "frontend/src/locales/en.json",
    "docs/superpowers/specs/2026-05-06-master-schedule-workspace-redesign-design.md",
  ],
  includeGitDiff: true,
});
```

Address every CRITICAL and HIGH severity finding before marking complete. MEDIUM/LOW findings are at the implementer's discretion but should be documented in the commit message if deferred.

- [ ] **Step 15: Final commit & complete**

If any post-review fixes were applied:

```bash
git add -A
git commit -m "fix(schedule): address code review findings"
```

Then mark the task complete.

---

## Notes for the implementer

1. **The page file is large (~2,350 lines).** Use `read` with offsets liberally; don't try to hold the whole file in context at once. The line numbers in this plan are approximate — verify with a fresh `read` before each `edit`.

2. **The MasterMatrix lives inside the same file** as the page component (`MasterMatrix` and `MasterMatrixSkeleton` are defined in the same file and exported alongside the default export). Do not split them into separate files in this task — the spec is explicit that file structure is out of scope.

3. **The `nassaqWarning` / `nassaqError` / `nassaqConfirm` functions** are destructured from a hook usage at the top of the page component. Verify the exact symbol names with `rg` before referencing them in Task 9; do not invent new function names.

4. **CRACO + Tailwind**: All Tailwind classes used in this plan are standard Tailwind v3. The `data-density` attribute selector is implemented as a `<style>` block, not a Tailwind plugin, to keep the change scoped to this page.

5. **RTL correctness is tested in production** by switching language to Arabic (default for this app). Always use `inset-inline-start` / `inset-inline-end` / `border-s-` / `border-e-` / `ms-` / `me-` and never `left` / `right` / `border-l-` / `border-r-` / `ml-` / `mr-` (except where the existing code already uses the wrong directional class — leave those alone unless the spec explicitly says to fix them).

6. **Frequent commits** per spec §3 — at the end of every task. Do not accumulate multi-task changes in a single commit. The Replit checkpoint system also auto-commits at task boundaries; the explicit commits in this plan are still helpful for reviewers reading the diff.

7. **Backend serves stale `frontend/build/`** at port 8000. After every frontend change, the Frontend Dev workflow at port 5000 picks up changes via HMR. If you also need to verify the production build, run the production build command and restart the Backend API workflow.
