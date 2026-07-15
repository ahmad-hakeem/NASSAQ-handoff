const { chromium } = require('playwright');

const BASE = 'http://localhost:5000';
const PASS = process.env.QA_PASS;

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 150)); });

  await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="login-email-input"]', { timeout: 20000 });
  await page.fill('[data-testid="login-email-input"]', 'mudeer@faarabi.edu');
  await page.fill('[data-testid="login-password-input"]', PASS);
  await page.click('[data-testid="login-submit-btn"]');
  await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 30000 });
  await page.waitForTimeout(2000);

  await page.goto(BASE + '/principal/users-management', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="users-classes-management"]', { timeout: 30000 });
  await page.waitForTimeout(5000);

  // 1. Exactly ONE floating Hakim (the global launcher)
  const launchers = await page.locator('[data-testid="hakim-toggle-btn"]').count();
  const hakimImgs = await page.evaluate(() => {
    const imgs = [...document.querySelectorAll('img[src*="hakim-poses"]')];
    return imgs.map((img) => {
      let el = img, fixed = false;
      while (el && el !== document.body) {
        if (getComputedStyle(el).position === 'fixed') { fixed = true; break; }
        el = el.parentElement;
      }
      const inLauncher = !!img.closest('[data-testid="hakim-toggle-btn"]');
      return { src: img.getAttribute('src').split('/').pop(), fixed, inLauncher };
    });
  });
  const fixedNonLauncher = hakimImgs.filter((w) => w.fixed && !w.inLauncher);
  console.log('launcher count =', launchers);
  console.log('hakim imgs:', JSON.stringify(hakimImgs));
  console.log('FIXED non-launcher hakim elements =', fixedNonLauncher.length, '(must be 0)');

  // 2. Inline insights card
  const cardCount = await page.locator('[data-testid="hakim-insights-card"]').count();
  console.log('inline insights card count =', cardCount);
  if (cardCount > 0) {
    const txt = (await page.locator('[data-testid="hakim-insights-card"]').innerText()).replace(/\n/g, ' | ').slice(0, 250);
    console.log('card text:', txt);
    const actionBtns = await page.locator('[data-testid^="hakim-insight-action-"]').count();
    console.log('action buttons =', actionBtns);
    if (actionBtns > 0) {
      await page.locator('[data-testid^="hakim-insight-action-"]').first().click();
      await page.waitForTimeout(1500);
      const bodyTxt = await page.evaluate(() => document.body.innerText);
      console.log('after action click: filter banner present =', /إلغاء|فلتر|عرض الطلاب/.test(bodyTxt), 'url =', page.url());
    }
  }

  await page.screenshot({ path: '/tmp/hakim-dedup-after.png' });
  console.log('console errors:', consoleErrors.length ? consoleErrors.slice(0, 3) : 'none');
  await browser.close();
})();
