/**
 * Bidirectional (BiDi) & Localization Text Utility
 * 
 * Provides robust helpers for handling mixed Arabic (RTL) and Latin/English (LTR)
 * text, isolating dynamic names, formatting numeric/date ranges without punctuation
 * inversion, and detecting text script direction.
 */

// Arabic and Hebrew Unicode block ranges (Arabic, Arabic Supplement, Arabic Extended-A, Hebrew)
const ARABIC_HEBREW_REGEX = /[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;

/**
 * Checks if a string contains any RTL characters (Arabic, Persian, Hebrew, Urdu, etc.)
 * @param {string} text
 * @returns {boolean}
 */
export function isRTLText(text) {
  if (typeof text !== 'string' || !text) return false;
  return ARABIC_HEBREW_REGEX.test(text);
}

/**
 * Determines text direction based on the first strong directional character.
 * @param {string} text
 * @param {'rtl'|'ltr'} defaultDir - Fallback direction if neutral
 * @returns {'rtl'|'ltr'}
 */
export function getTextDirection(text, defaultDir = 'ltr') {
  if (typeof text !== 'string' || !text.trim()) return defaultDir;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    // Ignore neutral characters, spaces, punctuation, digits
    if (/[\s\d\p{P}\p{S}]/u.test(char)) continue;
    if (ARABIC_HEBREW_REGEX.test(char)) return 'rtl';
    if (/[A-Za-z\u00C0-\u024F]/.test(char)) return 'ltr';
  }
  return defaultDir;
}

/**
 * Wraps text in First Strong Isolate (FSI \u2068 ... PDI \u2069)
 * to prevent punctuation and bidirectional bleeding in mixed text.
 * @param {string} text
 * @returns {string}
 */
export function bidiIsolate(text) {
  if (text === null || text === undefined) return '';
  const str = String(text);
  if (!str) return '';
  return `\u2068${str}\u2069`;
}

/**
 * Formats a range (e.g. time range "08:00 - 08:45" or date range "1448 - 1449")
 * with Left-to-Right Embedding to prevent the separator hyphen/slash from jumping.
 * @param {string|number} start
 * @param {string|number} end
 * @param {string} separator
 * @returns {string}
 */
export function formatBidiRange(start, end, separator = '—') {
  if (!start && !end) return '';
  if (!end) return String(start);
  if (!start) return String(end);
  return `\u2066${start} ${separator} ${end}\u2069`;
}

/**
 * Ensures numbers and codes (e.g. #1234, ID-55, A-2, 10/10) maintain LTR presentation
 * @param {string|number} value
 * @returns {string}
 */
export function bidiNumber(value) {
  if (value === null || value === undefined) return '';
  return `\u2066${value}\u2069`;
}
