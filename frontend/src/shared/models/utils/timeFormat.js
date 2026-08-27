/**
 * Time-format preference utilities.
 *
 * Single source of truth for converting a HH:MM string (or a Date) into a
 * display string that respects the user's saved time_format preference
 * ("12h" | "24h").  Import and use instead of hand-rolling toLocaleTimeString
 * calls scattered across dashboards.
 */

/**
 * Format a "HH:MM" or "HH:MM:SS" time string according to the user's
 * time-format preference.
 *
 * @param {string} timeStr  e.g. "14:30" or "08:05:00"
 * @param {string} timeFormat  "12h" (default) | "24h"
 * @param {function} t  optional i18n translate fn (used for am/pm labels)
 * @returns {string}
 */
export function formatTimeStr(timeStr, timeFormat = '12h', t = null) {
  if (!timeStr) return '';
  const [hStr, mStr = '00'] = String(timeStr).split(':');
  const h = parseInt(hStr, 10);
  const m = mStr.padStart(2, '0');
  if (isNaN(h)) return timeStr;

  if (timeFormat === '24h') {
    return `${String(h).padStart(2, '0')}:${m}`;
  }
  // 12-hour with am/pm
  const amLabel = t ? t('am') : 'ص';
  const pmLabel = t ? t('pm') : 'م';
  const period = h < 12 ? amLabel : pmLabel;
  const h12 = h > 12 ? h - 12 : h === 0 ? 12 : h;
  return `\u200E${h12}:${m} ${period}`;
}

/**
 * Format a Date object's time portion according to the user's preference.
 *
 * @param {Date} date
 * @param {string} timeFormat  "12h" | "24h"
 * @param {string} locale  e.g. "ar-SA" | "en-US"
 * @returns {string}
 */
export function formatDateObjTime(date, timeFormat = '12h', locale = 'en-US') {
  if (!(date instanceof Date) || isNaN(date)) return '';
  return date.toLocaleTimeString(locale, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: timeFormat !== '24h',
  });
}
