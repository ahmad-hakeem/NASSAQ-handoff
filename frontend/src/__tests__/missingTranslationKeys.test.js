/**
 * Guard against English (raw key) text leaking into the Arabic UI.
 *
 * `useTranslation().t(key)` in `src/contexts/ThemeContext.js` returns the key
 * string itself when `key` is missing from BOTH `ar.json` and `en.json`. Because
 * a missing key resolves to a truthy string, the common `t('key') || 'fallback'`
 * idiom does NOT save us — the raw key is rendered to the user instead.
 *
 * This test statically scans every `t('...')` call site under `src/` and fails
 * if a referenced literal key is absent from either locale file. Dynamic keys
 * (variables, member expressions, or template literals with `${...}`) cannot be
 * resolved statically and are skipped.
 */
const fs = require('fs');
const path = require('path');

const SRC = path.resolve(__dirname, '..');
const AR = require('@/locales/ar.json');
const EN = require('@/locales/en.json');

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (/node_modules|__tests__|__mocks__/.test(full)) continue;
      walk(full, out);
    } else if (/\.(js|jsx)$/.test(entry.name) && !/\.test\.(js|jsx)$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

// Matches t('...'), t("..."), t(`...`). Captures the quote and the literal body.
const T_CALL = /\bt\(\s*(['"`])((?:\\.|(?!\1).)*)\1/g;

function collectKeys() {
  const found = new Map(); // key -> first "relativePath:line" where seen
  for (const file of walk(SRC)) {
    const src = fs.readFileSync(file, 'utf8');
    let m;
    T_CALL.lastIndex = 0;
    while ((m = T_CALL.exec(src)) !== null) {
      const quote = m[1];
      const key = m[2];
      // Template literal with interpolation -> dynamic, cannot resolve.
      if (quote === '`' && key.includes('${')) continue;
      if (!found.has(key)) {
        const line = src.slice(0, m.index).split('\n').length;
        found.set(key, `${path.relative(SRC, file)}:${line}`);
      }
    }
  }
  return found;
}

describe('translation key coverage', () => {
  const keys = collectKeys();

  test('every static t() key exists in both ar.json and en.json', () => {
    const missing = [];
    for (const [key, where] of keys) {
      const inAr = Object.prototype.hasOwnProperty.call(AR, key);
      const inEn = Object.prototype.hasOwnProperty.call(EN, key);
      if (!inAr || !inEn) {
        const which = [!inAr && 'ar.json', !inEn && 'en.json'].filter(Boolean).join(' + ');
        missing.push(`  "${key}" — missing from ${which} (e.g. src/${where})`);
      }
    }

    if (missing.length > 0) {
      throw new Error(
        `Found ${missing.length} translation key(s) referenced by t() but missing from a locale file.\n` +
          `Add each key to BOTH frontend/src/locales/ar.json and en.json (or make the key dynamic if it is not a real string).\n` +
          `A missing key renders its raw English-looking key to users because t() returns the key itself.\n\n` +
          missing.join('\n')
      );
    }
  });
});
