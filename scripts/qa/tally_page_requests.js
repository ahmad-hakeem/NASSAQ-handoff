/**
 * Network-audit harness (generalized): log in against the production build,
 * open the given page, and tally every /api request by FULL URL (Chrome's
 * Name column hides N+1 fan-outs — always count full URLs on a prod build;
 * dev doubling is StrictMode).
 *
 * The dev backend does NOT serve the SPA, so serve `frontend/build` with
 * `scripts/qa/serve_spa_proxy.js` (proxies /api to the backend on :8000) and
 * point this harness at it with BASE_URL, e.g. BASE_URL=http://127.0.0.1:5050.
 *
 * Duplicates = same full URL requested more than once in the page-load
 * window. Window kept <30s so the notification bell's 30s poll tick is not
 * miscounted as a duplicate.
 *
 * Usage (UI login):
 *   node scripts/qa/tally_page_requests.js <email> <password> <path> [windowMs]
 *
 * Usage (token injection — for roles with stale/missing UI credentials):
 *   node scripts/qa/tally_page_requests.js --token <jwt> <path> [windowMs]
 *
 * e.g.:
 *   node scripts/qa/tally_page_requests.js mudeer@faarabi.edu 'pw' /principal/users-management
 *   node scripts/qa/tally_page_requests.js --token eyJ... /parent/children
 */
const { chromium } = require('/home/runner/workspace/.agents/skills/playwright-skill/node_modules/playwright-core');

const BASE = process.env.BASE_URL || 'http://localhost:8000';

(async () => {
  let email, password, path, windowMsArg, token;

  const args = process.argv.slice(2);
  if (args[0] === '--token') {
    // Token-injection mode: --token <jwt> <path> [windowMs]
    [, token, path, windowMsArg] = args;
    if (!token || !path) {
      console.error('usage (token mode): node tally_page_requests.js --token <jwt> <path> [windowMs]');
      process.exit(1);
    }
  } else {
    // UI-login mode: <email> <password> <path> [windowMs]
    [email, password, path, windowMsArg] = args;
    if (!email || !password || !path) {
      console.error('usage: node tally_page_requests.js <email> <password> <path> [windowMs]');
      process.exit(1);
    }
  }
  const windowMs = Number(windowMsArg) || 12000;

  const browser = await chromium.launch();
  const page = await browser.newPage();

  const tally = new Map();
  let recording = false;
  page.on('request', (req) => {
    const url = req.url();
    if (!recording || !url.includes('/api/')) return;
    const key = `${req.method()} ${url.replace(BASE, '')}`;
    tally.set(key, (tally.get(key) || 0) + 1);
  });

  if (token) {
    // --- token injection login (no UI form) ---
    // Load the SPA root so localStorage is scoped to the right origin
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
    await page.evaluate((tok) => {
      localStorage.setItem('nassaq_token', tok);
    }, token);
    // Navigate to target — the app should detect the stored token and skip the login gate
    recording = true;
    await page.goto(`${BASE}${path}`, { waitUntil: 'domcontentloaded' });
  } else {
    // --- UI login ---
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
    await page.fill('input[type="email"], input[name="email"]', email);
    await page.fill('input[type="password"], input[name="password"]', password);
    await Promise.all([
      page.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 30000 }),
      page.click('button[type="submit"]'),
    ]);
    await page.waitForTimeout(3000);

    // --- measured window ---
    recording = true;
    await page.goto(`${BASE}${path}`, { waitUntil: 'domcontentloaded' });
  }

  await page.waitForTimeout(windowMs);
  recording = false;

  const rows = [...tally.entries()].sort((a, b) => b[1] - a[1]);
  let dupes = 0;
  console.log(`--- /api requests on ${path} (${windowMs / 1000}s window) ---`);
  for (const [url, n] of rows) {
    if (n > 1) dupes += 1;
    console.log(`${String(n).padStart(2)}x  ${url}`);
  }
  console.log(`--- total: ${rows.reduce((s, [, n]) => s + n, 0)} requests, ${rows.length} unique URLs, ${dupes} duplicated URL(s) ---`);

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
