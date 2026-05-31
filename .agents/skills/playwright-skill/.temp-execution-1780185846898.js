const { chromium } = require('playwright');

const TARGET_URL = 'http://localhost:5000';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });
  try {
    await page.goto(TARGET_URL + '/login', { waitUntil: 'networkidle', timeout: 15000 });
    await page.fill('input[type="email"]', 'admin@nassaq.com');
    await page.fill('input[type="password"]', 'Test@1234');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/admin**', { timeout: 15000 });
    console.log('Logged in, URL:', page.url());

    await page.waitForSelector('[data-testid="sidebar"]', { timeout: 10000 });
    await page.waitForTimeout(1500);

    const hasRadixViewport = await page.$('[data-testid="sidebar"] [data-radix-scroll-area-viewport]');
    console.log('Radix viewport in sidebar:', hasRadixViewport !== null ? 'YES (unexpected)' : 'NO (good — removed)');

    const hasRadixScrollbar = await page.$('[data-testid="sidebar"] [data-radix-scroll-area-scrollbar]');
    console.log('Radix overlay scrollbar in sidebar:', hasRadixScrollbar !== null ? 'YES (ghost still present!)' : 'NO (eliminated)');

    const scrollDiv = await page.$('[data-testid="sidebar"] .sidebar-scrollbar');
    console.log('Plain sidebar-scrollbar div:', scrollDiv !== null ? 'YES (good)' : 'NO (missing!)');

    await page.screenshot({ path: '/tmp/sidebar-after-fix.png' });
    console.log('Screenshot saved to /tmp/sidebar-after-fix.png');
    console.log('All checks complete');
  } catch(e) {
    console.error('Error:', e.message);
    await page.screenshot({ path: '/tmp/error.png' }).catch(() => {});
  } finally {
    await browser.close();
  }
})();
