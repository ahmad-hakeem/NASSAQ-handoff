/**
 * Decides whether a *failed* write request is safe to auto-retry on a transient
 * blip (no response / timeout / 502 / 503).
 *
 * Why this exists (Task #785): the axios response interceptor already auto-retries
 * GET requests on a transient failure, but POST/PUT/PATCH do not — so a brief
 * network blip on a "save" silently collapses into a generic error and forces the
 * user to retry by hand (the same asymmetry behind the #784 transfer bug).
 *
 * Mirroring the GET retry for *every* write would be unsafe: re-sending a POST
 * create after a lost response could double-submit. So we mirror it only for a
 * SMALL, EXPLICIT allow-list of endpoints that are idempotent by contract —
 * re-applying them yields the identical result, so a retry is a safe no-op.
 *
 * Rules are matched by HTTP method + URL path. Each entry is intentionally
 * narrow; add a new line here (with a one-word reason) rather than widening an
 * existing pattern. NEVER add a non-idempotent create (a bare `POST /resource`).
 */

// One segment of a path that is NOT a slash or a query/hash delimiter — i.e. a
// single resource id. Kept deliberately tight so a rule for `/students/:id`
// cannot accidentally match a deeper sub-resource like `/students/:id/grades`.
const ID = '[^/?#]+';

export const IDEMPOTENT_WRITE_RETRY_RULES = [
  // Per-resource "update" endpoints (full PUT replace → idempotent by REST contract).
  { methods: ['PUT', 'PATCH'], pattern: new RegExp(`^/schools/${ID}$`) },
  { methods: ['PUT', 'PATCH'], pattern: new RegExp(`^/students/${ID}$`) },
  { methods: ['PUT', 'PATCH'], pattern: new RegExp(`^/teachers/${ID}$`) },
  { methods: ['PUT', 'PATCH'], pattern: new RegExp(`^/classes/${ID}$`) },
  { methods: ['PUT', 'PATCH'], pattern: new RegExp(`^/subjects/${ID}$`) },
  { methods: ['PUT', 'PATCH'], pattern: new RegExp(`^/assessments/${ID}$`) },
  { methods: ['PUT', 'PATCH'], pattern: new RegExp(`^/product-hub/issues/${ID}$`) },
  // Settings / preference saves (set-to-target-state → idempotent).
  { methods: ['PUT', 'PATCH'], pattern: /^\/auth\/preferences$/ },
  { methods: ['PUT', 'PATCH'], pattern: /^\/settings\/(general|contact|security)$/ },
  // Notification read-state (setting "read" twice is the same as once → idempotent).
  { methods: ['PUT', 'PATCH'], pattern: new RegExp(`^/notifications/${ID}/read$`) },
  { methods: ['PUT', 'PATCH'], pattern: /^\/notifications\/mark-all-read$/ },
];

/**
 * Normalizes an axios `config.url` to the bare path we match rules against:
 * drops any query string / hash, strips an absolute origin, and removes a
 * leading `/api` prefix (axios usually keeps the url relative to baseURL, but we
 * tolerate either form). A trailing slash is trimmed for stable matching.
 *
 * @param {string} url
 * @returns {string}
 */
export function normalizeRequestPath(url) {
  if (!url) return '';
  let path = String(url).split('#')[0].split('?')[0];
  path = path.replace(/^https?:\/\/[^/]+/i, '');
  path = path.replace(/^\/api(?=\/)/, '');
  if (path.length > 1 && path.endsWith('/')) path = path.slice(0, -1);
  return path;
}

/**
 * Returns true when this request targets an allow-listed idempotent write and is
 * therefore safe to auto-retry on a transient no-response/timeout blip.
 *
 * @param {{method?:string, url?:string}} config Axios request config.
 * @returns {boolean}
 */
export function isIdempotentWriteRetry(config) {
  if (!config) return false;
  const method = (config.method || '').toUpperCase();
  if (!method || method === 'GET') return false;
  const path = normalizeRequestPath(config.url);
  if (!path) return false;
  return IDEMPOTENT_WRITE_RETRY_RULES.some(
    (rule) => rule.methods.includes(method) && rule.pattern.test(path),
  );
}
