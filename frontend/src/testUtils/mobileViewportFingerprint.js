/**
 * Task #281 — shared mobile-viewport snapshot helper.
 *
 * jsdom does not apply Tailwind's media-query CSS, so a true pixel
 * snapshot of `hidden sm:block` / `sm:hidden` branches is out of reach
 * here. Instead we capture a deterministic *structural* fingerprint of
 * the rendered DOM, plus the JS-observable viewport state, that
 * regresses on the kinds of changes a visual diff would catch:
 *
 *   - the root container's tag + class list (so a layout swap fails),
 *   - the total number of rendered elements (catches accidental
 *     mount/unmount),
 *   - the ordered set of Tailwind responsive utility classes used at
 *     this viewport (sm:/md:/lg:/xl:/2xl: prefixes — the breakpoints
 *     this task targets), with usage counts so swapping `sm:hidden`
 *     for `md:hidden` flips the snapshot,
 *   - the JS-observable viewport state (`innerWidth` plus the matched
 *     state of each Tailwind breakpoint via mocked `matchMedia`), so
 *     any component that branches off `useMediaQuery` / `matchMedia`
 *     genuinely produces a different snapshot per width.
 *
 * The fingerprint is intentionally insensitive to dynamic strings
 * (timestamps, ids, server text) so re-runs are stable.
 *
 * What this CANNOT catch (call out explicitly so reviewers know the
 * scope): pure-CSS responsive branches whose visibility is decided
 * only by Tailwind media queries. Both branches are mounted in jsdom
 * and only differ once real CSS is applied. A follow-up Playwright
 * lane (#318) is the right home for that class of regression.
 */

const BREAKPOINT_PREFIX = /^(sm|md|lg|xl|2xl):/;

// Tailwind default breakpoints — kept here so the fingerprint stays in
// sync with what the app actually uses.
const TAILWIND_BREAKPOINTS = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536,
};

function collectBreakpointClasses(container) {
  const counts = {};
  const all = container.querySelectorAll('*');
  for (const el of all) {
    if (!el.classList || !el.classList.length) continue;
    for (const cls of el.classList) {
      if (BREAKPOINT_PREFIX.test(cls)) {
        counts[cls] = (counts[cls] || 0) + 1;
      }
    }
  }
  // Stable key order so snapshots don't churn.
  const sorted = {};
  for (const k of Object.keys(counts).sort()) sorted[k] = counts[k];
  return sorted;
}

function rootSummary(container) {
  const root = container.firstElementChild;
  if (!root) return { tag: null, className: '' };
  return {
    tag: root.tagName.toLowerCase(),
    className: typeof root.className === 'string' ? root.className : '',
  };
}

function matchedBreakpoints(width) {
  const matched = {};
  for (const [name, minPx] of Object.entries(TAILWIND_BREAKPOINTS)) {
    matched[name] = width >= minPx;
  }
  return matched;
}

/**
 * Compute the fingerprint for a rendered container at a given width.
 * Returns a plain object suitable for `toMatchSnapshot()`.
 */
export function fingerprintContainer(container, width) {
  const root = rootSummary(container);
  const allEls = container.querySelectorAll('*');
  return {
    width,
    inner_width: typeof window !== 'undefined' ? window.innerWidth : null,
    matched_breakpoints: matchedBreakpoints(width),
    root_tag: root.tag,
    root_class: root.className,
    element_count: allEls.length,
    breakpoint_classes: collectBreakpointClasses(container),
  };
}

/**
 * Same as fingerprintContainer but for a node anywhere in document.body
 * — used by the OnboardingTour test, which renders into a portal.
 */
export function fingerprintBody(width) {
  return fingerprintContainer(document.body, width);
}

export const TARGET_WIDTHS = [360, 414, 768, 1024];

/**
 * Set the JS-observable viewport state for a test. Updates
 * `window.innerWidth` / `innerHeight`, installs a deterministic
 * `matchMedia` mock that resolves Tailwind-style `(min-width: Npx)`
 * queries against the new width, and dispatches a resize event so
 * components that listen for it recompute.
 */
export function setViewport(width, height = 720) {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: width });
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: height });

  const mqlListeners = new Set();
  const matchMediaImpl = (query) => {
    // Evaluate every (min-width: Npx) and (max-width: Npx) clause and
    // AND them together — matches CSS semantics for a single media
    // query. A query with no recognised clauses is treated as
    // non-matching so we never accidentally claim a match.
    const clauses = [];
    const minRe = /\(min-width:\s*(\d+)px\)/gi;
    const maxRe = /\(max-width:\s*(\d+)px\)/gi;
    let m;
    while ((m = minRe.exec(query))) clauses.push(width >= parseInt(m[1], 10));
    while ((m = maxRe.exec(query))) clauses.push(width <= parseInt(m[1], 10));
    const matches = clauses.length > 0 && clauses.every(Boolean);
    return {
      matches,
      media: query,
      onchange: null,
      addListener: (cb) => mqlListeners.add(cb),
      removeListener: (cb) => mqlListeners.delete(cb),
      addEventListener: (_type, cb) => mqlListeners.add(cb),
      removeEventListener: (_type, cb) => mqlListeners.delete(cb),
      dispatchEvent: () => false,
    };
  };
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: matchMediaImpl,
  });

  try { window.dispatchEvent(new Event('resize')); } catch (_e) { /* noop */ }
}
