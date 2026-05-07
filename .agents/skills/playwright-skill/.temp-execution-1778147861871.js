
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
    const TARGET_URL = 'http://localhost:5000';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const consoleMsgs = [];
  const pageErrors = [];
  page.on('console', (m) => consoleMsgs.push(`[${m.type()}] ${m.text()}`));
  page.on('pageerror', (e) => pageErrors.push(`PAGEERROR: ${e.message}\n${e.stack}`));

  console.log('1. Going to /login');
  await page.goto(`${TARGET_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);

  console.log('2. Filling credentials');
  await page.fill('input[type="email"], input[name="email"], input[placeholder*="بريد"], input[placeholder*="mail"]', 'mudeer@faarabi.edu');
  await page.fill('input[type="password"], input[name="password"]', 'Test@1234');
  await page.click('button[type="submit"]');

  console.log('3. Waiting for nav after login');
  await page.waitForTimeout(4000);
  console.log('   URL after login:', page.url());

  console.log('4. Navigating to /school/schedule');
  await page.goto(`${TARGET_URL}/school/schedule`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  console.log('   URL after schedule:', page.url());

  await page.screenshot({ path: '/tmp/schedule-error.png', fullPage: true });

  console.log('\n=== PAGE ERRORS ===');
  pageErrors.forEach(e => console.log(e));
  console.log('\n=== CONSOLE MESSAGES (errors/warnings only) ===');
  consoleMsgs.filter(m => m.startsWith('[error]') || m.startsWith('[warning]')).forEach(m => console.log(m));

  // Try to extract React error overlay text
  const bodyText = await page.evaluate(() => document.body.innerText);
  console.log('\n=== BODY TEXT (first 500 chars) ===');
  console.log(bodyText.slice(0, 500));

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
