const { chromium } = require('playwright');
const BASE = 'http://localhost:5000';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });

  // Login as principal
  await page.goto(`${BASE}/login`);
  await page.waitForSelector('input[type="email"]', { timeout: 8000 });
  await page.fill('input[type="email"]', 'mudeer@faarabi.edu');
  await page.fill('input[type="password"]', 'Test@1234');
  await page.click('button[type="submit"]');
  // Wait for dashboard to load
  await page.waitForSelector('text=مركز القيادة', { timeout: 15000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: '/tmp/qa-principal-loaded.jpg', fullPage: true });
  console.log('✅ Principal dashboard loaded');

  await browser.close();
})();
