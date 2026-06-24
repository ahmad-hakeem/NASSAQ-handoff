/**
 * Centralized helpers for the platform's system-generated internal
 * identifiers — the auto-generated UUIDs (e.g. `ac838e0a-…`) that the
 * backend assigns to every record.
 *
 * These ids are real, load-bearing values: they key React lists, drive
 * selectors, filters, lookups and API calls, so they MUST stay in the data
 * layer untouched. What this module governs is purely whether the *rendered*
 * string is shown to the viewer. The platform rule is: only the Platform
 * Admin / مدير المنصة may see a raw internal identifier in the UI. Every
 * other role gets a neutral fallback instead.
 *
 * Pair these helpers with `useCanViewInternalIds()` (the single source of
 * truth for the role condition) so the visibility rule is not re-implemented
 * inconsistently across the many components that surface ids.
 */

// Canonical v4-style UUID. Mirrors the backend `_BARE_UUID_RE`
// (backend/routes/schedule_master_grid_routes.py) so the frontend and
// backend agree on exactly what "a bare internal id" looks like.
const BARE_UUID_RE =
  /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;

/**
 * True when `value` is a bare auto-generated identifier (a raw UUID).
 *
 * Used to detect when a field that should hold a human-readable label
 * (e.g. a teacher's subject/specialization) has degraded into a raw id that
 * leaked from imperfect data, so non-admins see a placeholder instead of the
 * internal reference.
 */
export function looksLikeInternalId(value) {
  if (value == null) return false;
  return BARE_UUID_RE.test(String(value).trim());
}

/**
 * Hide a value that is an internal id from viewers who may not see internal
 * ids. Real labels (names, numbers, codes, plain text) always pass through
 * unchanged — only bare UUIDs are masked, and only for non-admin viewers.
 *
 * The underlying data is never mutated; this only shapes what is rendered.
 *
 * @param {*} value    the value about to be rendered
 * @param {boolean} canView  result of `useCanViewInternalIds()`
 * @param {*} [fallback='']  what to render instead when the id is masked
 * @returns {*} the original value, or `fallback` when masked
 */
export function maskInternalId(value, canView, fallback = '') {
  if (canView) return value;
  return looksLikeInternalId(value) ? fallback : value;
}
