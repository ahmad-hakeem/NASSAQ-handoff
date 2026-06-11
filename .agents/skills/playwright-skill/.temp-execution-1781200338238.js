const { chromium } = require('playwright');

const BASE_URL = 'http://localhost:5000';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();

  // Collect API responses
  const apiLog = [];
  page.on('response', async (response) => {
    if (response.url().includes('/api/')) {
      const url = response.url().replace('http://localhost:8000', '');
      if (url.includes('my-subjects') || url.includes('auth/login') || url.includes('teacher')) {
        try {
          const body = await response.json();
          apiLog.push(`${response.status()} ${url}: ${JSON.stringify(body).substring(0, 200)}`);
        } catch (_) {
          apiLog.push(`${response.status()} ${url}: (non-json)`);
        }
      }
    }
  });

  console.log('Navigating to login page...');
  await page.goto(`${BASE_URL}/login`);
  await page.waitForLoadState('networkidle');

  // Fill login form
  const emailField = page.locator('input[type="email"], input[name="email"], input[placeholder*="email"], input[placeholder*="بريد"]').first();
  const passField = page.locator('input[type="password"]').first();
  
  await emailField.fill('hsn.alghamdy@faarabi.edu');
  await passField.fill('Test@1234');
  
  // Click login button
  const loginBtn = page.locator('button[type="submit"]').first();
  await loginBtn.click();
  
  console.log('Waiting for navigation after login...');
  await page.waitForTimeout(3000);
  
  console.log('Current URL:', page.url());
  await page.screenshot({ path: '/tmp/screenshot-after-login.png' });
  console.log('Screenshot saved: /tmp/screenshot-after-login.png');

  // Navigate to My Classes page
  console.log('Navigating to My Classes...');
  await page.goto(`${BASE_URL}/teacher/classes`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);
  
  console.log('Current URL:', page.url());
  await page.screenshot({ path: '/tmp/screenshot-my-classes.png' });
  console.log('Screenshot saved: /tmp/screenshot-my-classes.png');

  // Try to open settings modal - look for settings button
  const settingsBtn = page.locator('button').filter({ hasText: /إعداد|setting|ضبط|تحكم|session/i }).first();
  const gearBtn = page.locator('[aria-label*="setting"], [aria-label*="إعداد"], button:has(svg)').first();
  
  // Look for any button that might open settings
  const buttons = await page.locator('button').all();
  console.log(`Found ${buttons.length} buttons on the page`);
  
  // Log button texts
  for (let i = 0; i < Math.min(buttons.length, 20); i++) {
    const text = await buttons[i].textContent().catch(() => '');
    if (text.trim()) console.log(`  Button ${i}: "${text.trim().substring(0, 50)}"`);
  }

  console.log('\nAPI calls log:');
  apiLog.forEach(l => console.log(' ', l));
  
  await browser.close();
  console.log('Done.');
})();
