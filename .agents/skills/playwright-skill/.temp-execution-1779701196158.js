const { chromium } = require('playwright');

const TARGET_URL = 'http://localhost:5000';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });

  try {
    // Sign in as platform admin
    await page.goto(`${TARGET_URL}/login`);
    await page.waitForSelector('input[type="email"], input[name="email"]', { timeout: 10000 });
    await page.fill('input[type="email"], input[name="email"]', 'admin@nassaq.com');
    await page.fill('input[type="password"]', 'Test@1234');
    await page.click('button[type="submit"]');

    // Wait for redirect after login
    await page.waitForTimeout(3000);
    console.log('After login URL:', page.url());

    // Navigate directly to workspace purge page
    await page.goto(`${TARGET_URL}/admin/workspace-purge`);
    await page.waitForTimeout(2000);
    console.log('Purge page URL:', page.url());

    // Check if the testid element exists and its position
    const purgePageEl = await page.$('[data-testid="platform-workspace-purge-page"]');
    if (purgePageEl) {
      const box = await purgePageEl.boundingBox();
      console.log('Page element bounding box:', JSON.stringify(box));
      console.log('Page element top y:', box ? box.y : 'N/A');
      if (box && box.y < 100) {
        console.log('✅ PASS: Page content starts near the top (y=' + box.y + '), no blank viewport gap');
      } else {
        console.log('❌ FAIL: Page content starts at y=' + (box ? box.y : 'unknown') + ', likely still has blank gap');
      }
    } else {
      console.log('⚠️  data-testid element not found — checking page structure...');
    }

    // Take screenshot
    await page.screenshot({ path: '/tmp/purge-page-after-fix.png', fullPage: false });
    console.log('📸 Screenshot saved to /tmp/purge-page-after-fix.png');

    // Also check the Sidebar renders children
    const sidebarEl = await page.$('[data-testid="sidebar"]');
    console.log('Sidebar present:', !!sidebarEl);

    // Check for the refresh button which should be in the header area
    const refreshBtn = await page.$('[data-testid="refresh-purge-list"]');
    console.log('Refresh button present:', !!refreshBtn);

    if (refreshBtn) {
      const btnBox = await refreshBtn.boundingBox();
      console.log('Refresh button position:', JSON.stringify(btnBox));
      if (btnBox && btnBox.y < 200) {
        console.log('✅ PASS: Refresh button visible in top portion of viewport');
      } else {
        console.log('❌ FAIL: Refresh button is below fold at y=' + (btnBox ? btnBox.y : 'unknown'));
      }
    }

  } catch (err) {
    console.error('❌ Error:', err.message);
    await page.screenshot({ path: '/tmp/purge-page-error.png' });
  } finally {
    await browser.close();
  }
})();
