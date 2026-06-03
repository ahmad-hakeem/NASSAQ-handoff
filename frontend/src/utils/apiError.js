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
function getEnvelopeBody(error) {
  // Pulls the canonical envelope body out of whatever shape the caller passes —
  // an axios error (`error.response.data`), an axios response / resolved body
  // (`error.data`), or a raw envelope body (`{success,error,meta}`). A bare
  // Error exposes none of these keys, so it resolves to `undefined`.
  const isEnvelope =
    error &&
    typeof error === 'object' &&
    (error.error !== undefined ||
      error.detail !== undefined ||
      error.success !== undefined ||
      error.meta !== undefined);
  return error?.response?.data ?? error?.data ?? (isEnvelope ? error : undefined);
}

export function getApiErrorMessage(error, fallback = undefined) {
  // A bare Error's generic `.message` (e.g. "Network Error") is intentionally
  // not surfaced — only the structured backend envelope is read.
  const data = getEnvelopeBody(error);
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

/**
 * Classifies a caught axios error from ANY write request into one of three
 * mutually-exclusive outcomes, so a write handler never collapses a transient
 * no-response blip into the same generic message as a real backend rejection.
 *
 * - `canceled`: StrictMode double-mount / route change / AbortController abort —
 *   not a real failure, the caller should stay silent.
 * - `backend`: the server answered (`error.response` is present); surface its
 *   real Arabic message via the canonical envelope reader (or `null` when the
 *   response carried nothing usable, so the caller can pick a specific
 *   server-error message instead of the cause-hiding generic fallback).
 * - `network`: no response at all (network drop / timeout / proxy failure); the
 *   caller should show an accurate connection message.
 *
 * This is the generalized form of the transfer-specific classifier (Task #784)
 * and is the single source of truth for write-error triage app-wide (Task #785).
 *
 * @param {*} error The caught axios error (or any thrown value).
 * @returns {{kind:'canceled'} | {kind:'backend', message:(string|null)} | {kind:'network'}}
 */
export function classifyWriteError(error) {
  if (
    error &&
    (error.code === 'ERR_CANCELED' ||
      error.name === 'CanceledError' ||
      error.message === 'canceled')
  ) {
    return { kind: 'canceled' };
  }
  if (error && error.response) {
    return { kind: 'backend', message: getApiErrorMessage(error) || null };
  }
  return { kind: 'network' };
}

/**
 * Extracts the per-field validation breakdown the backend attaches to a 422
 * under `meta.validation_errors` (see the RequestValidationError handler in
 * backend/server.py). Returns a normalized array of `{ field, message }`, or an
 * empty array when there is no per-field detail.
 *
 * @param {*} error
 * @returns {Array<{field: string, message: string}>}
 */
export function getValidationErrors(error) {
  const data = getEnvelopeBody(error);
  const list = data?.meta?.validation_errors;
  if (!Array.isArray(list)) return [];
  return list
    .map((e) => ({
      field: typeof e?.field === 'string' ? e.field : '',
      message: typeof e?.message === 'string' ? e.message : '',
    }))
    .filter((e) => e.field || e.message);
}

// Maps a backend field path (e.g. "body.basic_info.email") to an existing
// locale key for a human label. The last non-index path segment is matched.
const FIELD_LABEL_KEYS = {
  name: 'name',
  full_name: 'fullName',
  fullname: 'fullName',
  email: 'email',
  phone: 'phone',
  mobile: 'phone',
  phone_number: 'phone',
  national_id: 'nationalId',
  nationality: 'nationality',
  address: 'address',
  city: 'city',
  country: 'country',
  password: 'password',
  gender: 'gender',
  grade: 'grade',
  subject: 'subject',
  class_name: 'className',
  school_name: 'schoolName',
};

// Maps a backend/Pydantic message to an existing locale key. Each entry tests
// (case-insensitively) whether the raw message contains the substring.
const MESSAGE_PATTERN_KEYS = [
  { test: 'field required', key: 'validationRequired' },
  { test: 'value_error.missing', key: 'validationRequired' },
  { test: 'none is not an allowed', key: 'validationRequired' },
  { test: 'valid email', key: 'validationInvalidEmail' },
  { test: 'at least', key: 'validationTooShort' },
  { test: 'too_short', key: 'validationTooShort' },
  { test: 'at most', key: 'validationTooLong' },
  { test: 'too_long', key: 'validationTooLong' },
  { test: 'valid integer', key: 'validationInvalidNumber' },
  { test: 'valid number', key: 'validationInvalidNumber' },
  { test: 'valid digits', key: 'validationInvalidNumber' },
];

function lastFieldSegment(field) {
  if (!field) return '';
  const segments = String(field)
    .split('.')
    .filter((s) => s && s !== 'body' && s !== 'query' && s !== 'path' && !/^\d+$/.test(s));
  return segments.length ? segments[segments.length - 1] : '';
}

function humanizeField(segment) {
  if (!segment) return '';
  return segment
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Formats `meta.validation_errors` into a readable, localized list of strings,
 * e.g. `["البريد: مطلوب", "الاسم: مطلوب"]`. Field paths and Pydantic messages
 * are mapped to locale keys when a translator is supplied; unmapped values fall
 * back to a humanized field label and the raw backend message.
 *
 * @param {*} error
 * @param {(key: string, params?: object) => string} [t] Translation function
 *   from `useTranslation()`. When omitted, raw English text is used.
 * @returns {string[]} Localized per-field lines (empty when no detail exists).
 */
export function formatValidationErrors(error, t) {
  const translate = typeof t === 'function' ? t : (k) => k;
  return getValidationErrors(error).map(({ field, message }) => {
    const segment = lastFieldSegment(field);
    const labelKey = FIELD_LABEL_KEYS[segment];
    const label = labelKey ? translate(labelKey) : humanizeField(segment);

    const lower = message.toLowerCase();
    const matched = MESSAGE_PATTERN_KEYS.find((p) => lower.includes(p.test));
    const reason = matched ? translate(matched.key) : message;

    if (label && reason) return `${label}: ${reason}`;
    return reason || label || message;
  });
}

/**
 * Builds the single message string to show in a NassaqAlertDialog when a request
 * fails. If the backend returned per-field validation detail, the specific
 * field reasons are surfaced as a bulleted list; otherwise it degrades to the
 * generic top-level message via `getApiErrorMessage`.
 *
 * @param {*} error
 * @param {object} [options]
 * @param {(key: string, params?: object) => string} [options.t] Translator.
 * @param {string} [options.fallback] Message when nothing usable is found.
 * @returns {string|undefined}
 */
export function getFormErrorMessage(error, { t, fallback } = {}) {
  const lines = formatValidationErrors(error, t);
  if (lines.length) {
    return lines.map((line) => `• ${line}`).join('\n');
  }
  return getApiErrorMessage(error, fallback);
}

export default getApiErrorMessage;
