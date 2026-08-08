/**
 * CI guard: double-fetch regression detection.
 *
 * For each role the suite logs in once and navigates to 3–5 representative
 * pages. Every page is loaded cold (via about:blank) and every GET /api/*
 * request fired within a 4 s window starting from domcontentloaded is
 * tallied — short enough that the notification-bell's 30 s poll never ticks,
 * long enough for lazy-tab panels to settle. If any URL fires twice the test
 * fails, printing every duplicated URL and its count so the author can fix
 * the page rather than allowlist it.
 *
 * Prod-build note: React StrictMode is OFF in CRA production builds, so
 * there is no dev-mode double-invocation of effects. Any duplicate here is
 * a real application bug.
 *
 * Detection rule
 *   key  = "GET " + full URL with origin stripped (query string included)
 *   fail = key count >= 2, unless the key appears in the per-page ALLOWLIST
 *
 * Allowlist policy: add ONLY for genuinely unavoidable framework behaviour,
 * with an inline comment explaining why it cannot be fixed at the source.
 */

import { test, expect, type Page, type Request } from '@playwright/test';
import {
  getItBootstrappedCredentials,
  getPrincipalCredentials,
  getParentCredentials,
  getPlatformAdminCredentials,
} from './lib/credentials';
import { gotoLogin, signInWith, expectOnPath } from './lib/loginPage';

// ─── tunables ────────────────────────────────────────────────────────────────
// 4 s is ample for React effects + lazy-tab fetches to settle after navigation;
// well short of the 30 s notification-bell poll so that never fires a false hit.
const WINDOW_MS = 4_000;

// Per-test timeout budget (ms).
// Budget = login (~10 s) + N pages × (navigation + WINDOW_MS + margin)
// Worst case: 5 pages × 8 s = 40 s + 10 s login = 50 s → pad to 90 s.
const TEST_TIMEOUT_MS = 90_000;

/**
 * Per-page allowlist.  Key format: exact string "GET /api/..."  (origin already
 * stripped; query params included when relevant — use a prefix string only if
 * the query is non-deterministic).  Every entry MUST have a comment.
 *
 * Currently empty — all pages are clean.  Add entries here only after
 * demonstrating the call cannot be deduplicated at the source.
 */
const ALLOWLIST: Record<string, string[]> = {
  // Example (currently not needed):
  // '/principal': [
  //   // SchoolDashboard fires /api/school/day-status once from the page and
  //   // once from the shared DayStatusContext; deduplication requires a
  //   // context refactor (tracked in issue #XYZ).
  //   'GET /api/school/day-status',
  // ],
};

// ─── core helper ─────────────────────────────────────────────────────────────

interface DuplicateEntry { key: string; count: number }
interface AuditResult    { path: string; duplicates: DuplicateEntry[] }

/**
 * Navigate to `path`, record GET /api/* requests for WINDOW_MS milliseconds,
 * return any URL that fired more than once (minus allowlisted entries).
 */
async function auditPage(page: Page, path: string): Promise<AuditResult> {
  const tally = new Map<string, number>();

  const onRequest = (req: Request) => {
    if (req.method() !== 'GET') return;
    const url = req.url();
    if (!url.includes('/api/')) return;
    const key = `GET ${url.replace(/^https?:\/\/[^/]+/, '')}`;
    tally.set(key, (tally.get(key) ?? 0) + 1);
  };

  page.on('request', onRequest);

  // Tear the previous document down first, then drop anything it emitted.
  // Without this the requests the *previous* page had in flight (e.g. the
  // post-login landing fetch) are delivered into this page's tally and read
  // as a duplicate — a false positive that has nothing to do with the page
  // under audit. Each page is measured as a cold load, on its own.
  await page.goto('about:blank');
  await page.waitForTimeout(250);
  tally.clear();

  await page.goto(path, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(WINDOW_MS);
  page.off('request', onRequest);

  const allowed = new Set(ALLOWLIST[path] ?? []);
  const duplicates = [...tally.entries()]
    .filter(([key, n]) => n >= 2 && !allowed.has(key))
    .sort((a, b) => b[1] - a[1])
    .map(([key, count]) => ({ key, count }));

  return { path, duplicates };
}

/**
 * Assert no duplicates and emit a readable failure message when there are.
 */
function assertNoDuplicates(result: AuditResult): void {
  if (result.duplicates.length === 0) return;

  const lines = result.duplicates.map(
    ({ key, count }) => `  ${count}x  ${key}`,
  );
  const message = [
    `Double-fetch detected on ${result.path} (${WINDOW_MS / 1000}s window):`,
    ...lines,
    '',
    'Fix the page so each endpoint is called only once per load.',
    'Only add to the ALLOWLIST if the duplication is genuinely unavoidable,',
    'with an inline comment explaining why.',
  ].join('\n');

  expect.soft(result.duplicates, message).toHaveLength(0);
}

// ─── Role: Independent Teacher (bootstrapped IT workspace) ───────────────────
test.describe('double-fetch — Independent Teacher', () => {
  const PAGES = [
    '/teacher',           // home / dashboard
    '/teacher/classes',   // فصولي — class list + today's sessions
    '/teacher/students',  // students roster
    '/teacher/schedule',  // weekly schedule grid
    '/teacher/assessments', // assessments hub
  ];

  test('no double-fetch across IT pages', async ({ page }) => {
    test.setTimeout(TEST_TIMEOUT_MS);
    const { email, password } = getItBootstrappedCredentials();
    await gotoLogin(page);
    await signInWith(page, email, password);
    // IT bootstrapped: no active mfa_factors row → password login only
    await expectOnPath(page, '/teacher');

    const results: AuditResult[] = [];
    for (const path of PAGES) {
      results.push(await auditPage(page, path));
    }

    // Report ALL pages before failing so a single run surfaces every issue
    for (const result of results) {
      assertNoDuplicates(result);
    }
    // Flush soft assertions
    expect(results.flatMap(r => r.duplicates)).toHaveLength(0);
  });
});

// ─── Role: Principal (school_admin) ──────────────────────────────────────────
test.describe('double-fetch — Principal / school_admin', () => {
  const PAGES = [
    '/principal',              // school dashboard
    '/principal/classes',      // class list
    '/principal/students',     // students page
    '/principal/attendance',   // attendance
    '/principal/users-management', // staff management
  ];

  test('no double-fetch across principal pages', async ({ page }) => {
    test.setTimeout(TEST_TIMEOUT_MS);
    const { email, password } = getPrincipalCredentials();
    await gotoLogin(page);
    await signInWith(page, email, password);
    await expectOnPath(page, '/principal');

    const results: AuditResult[] = [];
    for (const path of PAGES) {
      results.push(await auditPage(page, path));
    }

    for (const result of results) {
      assertNoDuplicates(result);
    }
    expect(results.flatMap(r => r.duplicates)).toHaveLength(0);
  });
});

// ─── Role: Parent ─────────────────────────────────────────────────────────────
test.describe('double-fetch — Parent', () => {
  // Avoid child-id-specific pages (/parent/child/:id) since the ID is not
  // statically known; /parent and /parent/children cover the high-traffic
  // surfaces and the shared useParentDashboard hook.
  const PAGES = [
    '/parent',          // parent portal dashboard
    '/parent/children', // children list + profile hub
    '/parent/messages', // communication / messaging
  ];

  test('no double-fetch across parent pages', async ({ page }) => {
    test.setTimeout(TEST_TIMEOUT_MS);
    const { email, password, totpSecret } = getParentCredentials();
    await gotoLogin(page);
    // Parent has an active TOTP factor seeded by seed_ci_e2e.py
    await signInWith(page, email, password, totpSecret);
    await expectOnPath(page, '/parent');

    const results: AuditResult[] = [];
    for (const path of PAGES) {
      results.push(await auditPage(page, path));
    }

    for (const result of results) {
      assertNoDuplicates(result);
    }
    expect(results.flatMap(r => r.duplicates)).toHaveLength(0);
  });
});

// ─── Role: Platform Admin ─────────────────────────────────────────────────────
test.describe('double-fetch — Platform Admin', () => {
  const PAGES = [
    '/admin',         // command-centre dashboard
    '/admin/schools', // school/tenant management
    '/admin/users',   // platform users
  ];

  test('no double-fetch across platform-admin pages', async ({ page }) => {
    test.setTimeout(TEST_TIMEOUT_MS);
    const { email, password } = getPlatformAdminCredentials();
    await gotoLogin(page);
    await signInWith(page, email, password);
    await expectOnPath(page, '/admin');

    const results: AuditResult[] = [];
    for (const path of PAGES) {
      results.push(await auditPage(page, path));
    }

    for (const result of results) {
      assertNoDuplicates(result);
    }
    expect(results.flatMap(r => r.duplicates)).toHaveLength(0);
  });
});
