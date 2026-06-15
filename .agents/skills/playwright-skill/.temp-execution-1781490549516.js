
const { chromium, firefox, webkit, devices } = require('playwright');
const helpers = require('./lib/helpers');

// Extra headers from environment variables (if configured)
const __extraHeaders = helpers.getExtraHeadersFromEnv();

/**
 * Utility to merge environment headers into context options.
 * Use when creating contexts with raw Playwright API instead of helpers.createContext().
 * @param {Object} options - Context options
 * @returns {Object} Options with extraHTTPHeaders merged in
 */
function getContextOptionsWithHeaders(options = {}) {
  if (!__extraHeaders) return options;
  return {
    ...options,
    extraHTTPHeaders: {
      ...__extraHeaders,
      ...(options.extraHTTPHeaders || {})
    }
  };
}

(async () => {
  try {
    const TARGET = 'http://localhost:5000';
const EMAIL = process.env.QA_EMAIL;
const PW = process.env.QA_PW;
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto(`${TARGET}/login`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  await page.fill('input[type="email"]', EMAIL);
  await page.fill('input[type="password"]', PW);
  await page.click('button[type="submit"]');
  try { await page.waitForURL(u => !u.toString().includes('/login'), { timeout: 25000 }); }
  catch(e){ console.log('still on login, url=', page.url()); }
  await page.waitForTimeout(1500);
  console.log('after login url:', page.url());
  await page.goto(`${TARGET}/teacher/schedule`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  // wait for grid labels
  try { await page.waitForSelector('text=الحصة', { timeout: 20000 }); } catch(e){ console.log('no الحصة label found'); }
  await page.waitForTimeout(2000);
  const labels = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('table tbody tr').forEach(tr => {
      const cell = tr.querySelector('td .font-medium');
      const time = tr.querySelector('td .text-muted-foreground');
      if (cell) out.push(cell.textContent.trim() + (time ? '  ['+time.textContent.trim()+']' : ''));
    });
    return out;
  });
  console.log('PERIOD LABELS (first column):');
  labels.forEach(l => console.log('   ', l));
  const errs = await page.evaluate(() => window.__errs || []);
  await page.screenshot({ path: '/tmp/teacher-schedule.png', fullPage: true });
  console.log('screenshot saved');
  await browser.close();
})();

  } catch (error) {
    console.error('❌ Automation error:', error.message);
    if (error.stack) {
      console.error(error.stack);
    }
    process.exit(1);
  }
})();
