const { chromium } = require('playwright');

const BASE = 'http://localhost:5000';
const PASS = process.env.QA_PASS;

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="login-email-input"]', { timeout: 20000 });
  await page.fill('[data-testid="login-email-input"]', 'mudeer@faarabi.edu');
  await page.fill('[data-testid="login-password-input"]', PASS);
  await page.click('[data-testid="login-submit-btn"]');
  await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 30000 });
  await page.waitForTimeout(2000);

  await page.goto(BASE + '/school/schedule', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  const cnt = await page.locator('[data-testid="hakim-toggle-btn"]').count();
  const box = cnt ? await page.locator('[data-testid="hakim-toggle-btn"]').boundingBox() : null;
  console.log(`master schedule: launcher count=${cnt}${box ? ` at x=${Math.round(box.x)},y=${Math.round(box.y)}` : ''} url=${page.url()}`);
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(800);
  await page.screenshot({ path: '/tmp/qa_master_schedule.png' });
  await browser.close();
})();
