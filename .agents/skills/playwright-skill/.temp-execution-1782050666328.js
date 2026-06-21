const { chromium } = require('playwright');

const TARGET_URL = 'http://localhost:5000';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.on('console', msg => {
    if (msg.type() === 'error') console.log('Browser error:', msg.text());
  });

  try {
    // Login as a teacher
    await page.goto(`${TARGET_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForSelector('input[type="email"], input[name="email"]', { timeout: 10000 });
    await page.fill('input[type="email"], input[name="email"]', 'amyra.alsaady@faarabi.edu');
    await page.fill('input[type="password"], input[name="password"]', 'Test@1234');
    await page.click('button[type="submit"]');

    // Wait for redirect after login
    await page.waitForURL('**', { timeout: 10000 });
    await page.waitForTimeout(2000);
    console.log('After login URL:', page.url());

    // Navigate to standby tab
    await page.goto(`${TARGET_URL}/teacher/classes?tab=standby`, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForTimeout(3000);

    console.log('Standby tab URL:', page.url());

    // Take a screenshot
    await page.screenshot({ path: '/tmp/standby-tab.png', fullPage: true });
    console.log('📸 Screenshot saved to /tmp/standby-tab.png');

    // Check if the new table is rendered
    const hasTable = await page.locator('table').count();
    const hasSearch = await page.locator('input[placeholder*="ابحث"]').count();
    const hasSortHeader = await page.locator('th').count();
    const hasStatusBadge = await page.locator('text=انتظار, text=مُسنَدة').count();
    const hasEmptyState = await page.locator('text=لا توجد لديك خانات انتظار').count();

    console.log('Table present:', hasTable > 0);
    console.log('Search box present:', hasSearch > 0);
    console.log('Table headers count:', hasSortHeader);
    console.log('Status badges:', hasStatusBadge);
    console.log('Empty state shown:', hasEmptyState > 0);

    if (hasTable > 0 || hasEmptyState > 0) {
      console.log('✅ StandbyTab renders correctly (table or empty state visible)');
    } else {
      console.log('⚠️  Neither table nor empty state found - check if still loading');
    }

  } catch (e) {
    console.error('❌ Error:', e.message);
    await page.screenshot({ path: '/tmp/standby-error.png', fullPage: true });
  } finally {
    await browser.close();
  }
})();
