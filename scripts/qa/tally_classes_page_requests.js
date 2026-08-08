/**
 * Network-audit harness: log in as a school teacher against the
 * production build served by the backend (port 8000), open the فصولي
 * page (/teacher/classes), and tally every /api request by FULL URL.
 *
 * Duplicates = the same full URL requested more than once during the
 * page-load window. The window is kept under 30s so the notification
 * bell's poll tick is not miscounted as a duplicate.
 *
 * Usage: node scripts/qa/tally_classes_page_requests.js <email> <password>
 */
const { chromium } = require('/home/runner/workspace/.agents/skills/playwright-skill/node_modules/playwright-core');

const BASE = process.env.BASE_URL || 'http://localhost:8000';

(async () => {
  const [email, password] = process.argv.slice(2);
  if (!email || !password) {
    console.error('usage: node tally_classes_page_requests.js <email> <password>');
    process.exit(1);
  }

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

  // --- login ---
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[type="email"], input[name="email"]', email);
  await page.fill('input[type="password"], input[name="password"]', password);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 30000 }),
    page.click('button[type="submit"]'),
  ]);
  await page.waitForTimeout(3000);

  // --- measured window: فصولي page load ---
  recording = true;
  await page.goto(`${BASE}/teacher/classes`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(12000);
  recording = false;

  const rows = [...tally.entries()].sort((a, b) => b[1] - a[1]);
  let dupes = 0;
  console.log('--- /api requests on /teacher/classes (12s window) ---');
  for (const [url, n] of rows) {
    if (n > 1) dupes += 1;
    console.log(`${String(n).padStart(2)}x  ${url}`);
  }
  console.log(`--- total: ${rows.reduce((s, [, n]) => s + n, 0)} requests, ${rows.length} unique URLs, ${dupes} duplicated URL(s) ---`);

  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
