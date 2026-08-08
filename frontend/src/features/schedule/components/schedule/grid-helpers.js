/**
 * grid-helpers — pure utilities for the Master Schedule grid.
 *
 * استُخرجت لتكون قابلة للاختبار بمعزل عن الـproviders (ThemeContext،
 * Translation) التي يحتاجها مكوّن MasterMatrix الكامل. كل دالة هنا
 * نقيّة (Pure) ولا تعتمد على React.
 */

/**
 * Pick which days the grid should render based on the current view mode.
 *
 * - viewMode === 'daily'  → return only the selected day if it is part of
 *   the available days; otherwise fall back to the first available day.
 * - viewMode === 'weekly' (or anything else) → return the full days array.
 *
 * Always returns a new array (never mutates the input).
 */
export function computeDisplayDays(viewMode, selectedDay, days) {
  const all = Array.isArray(days) ? days : [];
  if (viewMode !== 'daily') return all.slice();
  if (selectedDay && all.includes(selectedDay)) return [selectedDay];
  return all.length > 0 ? [all[0]] : [];
}

/**
 * Clamp a page index into the valid `[0, totalPages-1]` range. Always
 * returns at least 0 even when there are no pages, so callers can treat
 * the result as a safe array index.
 */
export function clampPage(pageIndex, totalPages) {
  const total = Math.max(1, totalPages | 0);
  const idx = Math.max(0, pageIndex | 0);
  return Math.min(idx, total - 1);
}

/**
 * Slice an array of rows for a given page.
 *
 * Returns a new array (never mutates) containing the rows that belong to
 * the requested page. Out-of-range indices are clamped, and a
 * non-positive page size short-circuits to an empty slice.
 */
export function paginateRows(rows, pageSize, pageIndex) {
  if (!Array.isArray(rows) || pageSize <= 0) return [];
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const safe = clampPage(pageIndex, totalPages);
  const start = safe * pageSize;
  return rows.slice(start, start + pageSize);
}
