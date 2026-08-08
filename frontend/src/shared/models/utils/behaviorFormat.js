/**
 * Behavior tab presentation helpers.
 *
 * The backend returns raw enum strings (``positive`` / ``negative`` /
 * ``neutral`` / ``conduct`` / ``academic`` / ``minor`` / ``moderate`` ...)
 * and ISO-8601 timestamps. The Behavior tab needs to render these as
 * localized, human-friendly text. Keep the logic in one place so every
 * surface (admin / teacher / parent) renders identically.
 *
 * Backend payload is intentionally untouched — this is presentation only.
 */

const SAFE_FALLBACK = '-';

/**
 * Translate a behavior enum value (category, type, severity, status) using
 * the active i18n ``t`` function with a stable, prefixed namespace. Falls
 * back to the raw enum string if no translation key exists, so a missing
 * key never leaves a blank cell on screen.
 *
 * @param {(key: string) => string} t — i18n translator from useTranslation
 * @param {string} value — raw enum value from the backend (may be falsy)
 * @param {string} [namespace='behaviorEnum'] — translation key prefix
 */
export function localizeBehaviorEnum(t, value, namespace = 'behaviorEnum') {
  if (value === null || value === undefined || value === '') return '';
  const raw = String(value);
  if (typeof t !== 'function') return raw;
  const key = `${namespace}_${raw}`;
  const translated = t(key);
  // ``t`` in this app returns the key itself when no translation exists.
  // Treat that as "missing" and fall back to the raw enum string so the
  // user never sees ``behaviorEnum_positive`` on screen.
  if (!translated || translated === key) return raw;
  return translated;
}

/**
 * Format a behavior record date into a localized, human-readable string.
 * Accepts ISO-8601 timestamps, plain ``YYYY-MM-DD`` dates, or ``Date``
 * instances. Returns a safe fallback for invalid / missing input so the
 * page never crashes on broken payloads.
 *
 * Output examples:
 *   ar  → ``31 مارس 2026``
 *   en  → ``31 Mar 2026``
 *
 * @param {string|Date|null|undefined} value
 * @param {string} [language='ar'] — active app language ('ar' | 'en')
 * @param {object} [options] — Intl.DateTimeFormat overrides
 */
export function formatBehaviorDate(value, language = 'ar', options) {
  if (value === null || value === undefined || value === '') return SAFE_FALLBACK;
  let date;
  try {
    // ``YYYY-MM-DD`` should be parsed as local-date (not UTC midnight) so
    // it never drifts a day in tz-east-of-UTC users.
    if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
      const [y, m, d] = value.split('-').map(Number);
      date = new Date(y, m - 1, d);
    } else {
      date = value instanceof Date ? value : new Date(value);
    }
  } catch (_err) {
    return SAFE_FALLBACK;
  }
  if (!date || isNaN(date.getTime())) return SAFE_FALLBACK;

  const locale = language === 'en' ? 'en-GB' : 'ar';
  const opts = options || { day: 'numeric', month: 'long', year: 'numeric' };
  try {
    return new Intl.DateTimeFormat(locale, opts).format(date);
  } catch (_err) {
    // Last-resort fallback if Intl rejects the locale tag.
    return date.toISOString().slice(0, 10);
  }
}
