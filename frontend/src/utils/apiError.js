/**
 * Extracts the human-readable error message from an axios error against the
 * NASSAQ backend envelope `{ success:false, error:{ code, message, detail } }`.
 *
 * The backend's global handlers (see backend/server.py) wrap every error as
 * `data.error.message`. Older frontend handlers read `data.detail`, which is
 * always `undefined` against this envelope and silently falls back to a generic
 * message. This helper reads the canonical envelope first, then degrades through
 * the legacy/raw shapes, and finally returns the caller-supplied fallback.
 *
 * @param {*} error The caught axios error (or any thrown value).
 * @param {string} [fallback] Translated message to show when the backend
 *   provided nothing usable. Defaults to `undefined` so legacy call sites that
 *   apply their own `|| fallback` keep working unchanged.
 * @returns {string|undefined} The backend message, or `fallback`.
 */
export function getApiErrorMessage(error, fallback = undefined) {
  // Accept an axios error (`error.response.data`), an axios response /
  // resolved body (`error.data`), or a raw envelope body (`{success,error}`).
  // A bare Error exposes none of these keys, so its generic `.message`
  // (e.g. "Network Error") is intentionally not surfaced.
  const isEnvelope =
    error &&
    typeof error === 'object' &&
    (error.error !== undefined ||
      error.detail !== undefined ||
      error.success !== undefined);
  const data = error?.response?.data ?? error?.data ?? (isEnvelope ? error : undefined);
  if (data) {
    const envMsg = data?.error?.message;
    if (typeof envMsg === 'string' && envMsg.trim()) return envMsg;

    const detail = data?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const joined = detail
        .map((d) => (typeof d === 'string' ? d : d?.msg || d?.message || ''))
        .filter(Boolean)
        .join(', ');
      if (joined.trim()) return joined;
    }
    if (detail && typeof detail === 'object') {
      const m = detail.message || detail.msg;
      if (typeof m === 'string' && m.trim()) return m;
    }

    const topMsg = data?.message;
    if (typeof topMsg === 'string' && topMsg.trim()) return topMsg;
  }
  return fallback;
}

export default getApiErrorMessage;
