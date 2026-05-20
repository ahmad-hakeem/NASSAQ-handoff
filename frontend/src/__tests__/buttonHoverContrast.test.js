/**
 * Regression guard for the "disappearing text on hover" anti-pattern.
 *
 * Outline / ghost Button variants apply `hover:text-accent-foreground` as a
 * base style. When a callsite adds a custom colored `text-*` class AND a
 * tinted `hover:bg-*` class but omits an explicit `hover:text-*`, the base
 * variant's hover color wins and the text becomes unreadable against the
 * light tinted background.
 *
 * This test scans every JSX/JS/TSX source file at the JSX-element level
 * (multi-line aware: the full opening-tag text is extracted before checking)
 * and fails if any Button element matches the anti-pattern.
 *
 * Fix any hit by adding `hover:text-{color}` matching the button's existing
 * `text-{color}`.
 *
 * Exemptions applied per-token:
 *  - `text-white`  — intentional on dark / image backgrounds.
 *  - `text-muted*` / `text-foreground` — semantic tokens that stay readable.
 *  - `text-current` / `text-transparent` / `text-inherit` — CSS keywords.
 *  - `text-primary` / `text-secondary` / `text-destructive` / `text-accent`
 *    / `text-card` / `text-popover` — design-system semantic tokens.
 *  - Size utilities: `text-xs`, `text-sm`, `text-base`, `text-lg` … `text-9xl`.
 *  - Arbitrary values starting with `text-[` — not a named color class.
 *  - `hover:text-` already present — already fixed.
 */

const fs = require('fs');
const path = require('path');

const SRC_DIR = path.resolve(__dirname, '..');
const EXTENSIONS = new Set(['.jsx', '.js', '.tsx', '.ts']);

const SAFE_TEXT_RE = /\btext-(white|black|muted|foreground|current|transparent|inherit|primary|secondary|destructive|accent|card|popover|xs|sm|base|lg|xl|2xl|3xl|4xl|5xl|6xl|7xl|8xl|9xl|\[)/;

function collectFiles(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === '__tests__') continue;
      collectFiles(full, out);
    } else if (EXTENSIONS.has(path.extname(entry.name))) {
      out.push(full);
    }
  }
  return out;
}

/**
 * Extract the full text of every <Button …> opening tag from `src`.
 * Handles multi-line JSX by walking character-by-character until the
 * first unquoted / un-braced `>` after `<Button`.
 * Returns an array of { text, startLine } objects.
 */
function extractButtonOpeningTags(src) {
  const results = [];
  let i = 0;
  while (i < src.length) {
    const start = src.indexOf('<Button', i);
    if (start === -1) break;

    // Confirm it's <Button followed by whitespace, >, or / (not <ButtonFoo…)
    const charAfter = src[start + 7];
    if (charAfter !== undefined && /\w/.test(charAfter)) {
      i = start + 1;
      continue;
    }

    // Walk to end of opening tag, respecting quoted strings and braces
    let j = start + 7;
    let inStr = false;
    let strChar = '';
    let braceDepth = 0;
    while (j < src.length) {
      const ch = src[j];
      if (inStr) {
        if (ch === strChar && src[j - 1] !== '\\') inStr = false;
      } else {
        if (ch === '"' || ch === "'") {
          inStr = true;
          strChar = ch;
        } else if (ch === '{') {
          braceDepth++;
        } else if (ch === '}') {
          braceDepth--;
        } else if (ch === '>' && braceDepth === 0) {
          j++;
          break;
        }
      }
      j++;
    }

    const tagText = src.slice(start, j);
    const startLine = src.slice(0, start).split('\n').length;
    results.push({ text: tagText, startLine });
    i = start + 1;
  }
  return results;
}

function tagHasAntiPattern(tagText) {
  // Must have variant="outline" or variant="ghost"
  if (!/variant=["'](outline|ghost)["']/.test(tagText)) return false;

  // Must have a tinted hover background
  if (!/hover:bg-/.test(tagText)) return false;

  // Must have a custom text-* color that is NOT a safe/semantic token
  const textTokens = tagText.match(/\btext-[a-zA-Z0-9_/[\]-]+/g) || [];
  const hasCustomTextColor = textTokens.some(t => !SAFE_TEXT_RE.test(t));
  if (!hasCustomTextColor) return false;

  // Must NOT already have an explicit hover:text-
  if (/hover:text-/.test(tagText)) return false;

  return true;
}

test('no outline/ghost Button has tinted hover:bg-* with custom text-* but no hover:text-*', () => {
  const files = collectFiles(SRC_DIR);
  const offenders = [];

  for (const file of files) {
    const src = fs.readFileSync(file, 'utf8');
    const tags = extractButtonOpeningTags(src);

    for (const { text, startLine } of tags) {
      if (tagHasAntiPattern(text)) {
        const relFile = path.relative(SRC_DIR, file);
        const preview = text.replace(/\s+/g, ' ').slice(0, 180);
        offenders.push(`${relFile}:${startLine}  →  ${preview}`);
      }
    }
  }

  if (offenders.length > 0) {
    const msg = [
      '',
      'Found outline/ghost Button(s) with a custom text-* and tinted hover:bg-* but no hover:text-*.',
      "Add hover:text-{color} matching the button's existing text-{color} to each callsite below.",
      '',
      ...offenders,
      '',
    ].join('\n');
    throw new Error(msg);
  }
});
