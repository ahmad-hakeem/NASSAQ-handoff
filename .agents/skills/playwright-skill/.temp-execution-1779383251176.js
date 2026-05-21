const { chromium } = require('playwright');
const BASE = 'http://localhost:5000';
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto(`${BASE}/login`);
  await page.waitForSelector('input[type="password"]', { timeout: 10000 });
  await page.locator('input[type="email"]').first().fill('mudeer@faarabi.edu');
  await page.locator('input[type="password"]').first().fill('Test@1234');
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL(url => !url.toString().includes('/login'), { timeout: 15000 });
  await page.goto(`${BASE}/school/schedule`);
  await page.waitForTimeout(4000);

  // ── State 1: unscrolled ─────────────────────────────────────────────
  const unscrolled = await page.evaluate(() => {
    const container = document.querySelector('[data-testid="master-matrix-container"]');
    const corner = document.querySelector('[data-testid="master-matrix-corner"]');
    const teachers = document.querySelectorAll('[data-testid^="master-matrix-teacher-"]');
    const cntR = container?.getBoundingClientRect();
    const crR = corner?.getBoundingClientRect();
    const t1R = teachers[0]?.getBoundingClientRect();
    return {
      containerTop: cntR?.top.toFixed(1),
      cornerTop: crR?.top.toFixed(1),
      cornerBottom: crR?.bottom.toFixed(1),
      firstTeacherTop: t1R?.top.toFixed(1),
      gap_matrix_to_corner: (crR?.top - cntR?.top).toFixed(1),
      gap_corner_to_teacher1: (t1R?.top - crR?.bottom).toFixed(1),
      containerScrollTop: container?.scrollTop,
      containerH: container?.offsetHeight,
      containerScrollH: container?.scrollHeight,
    };
  });
  console.log('UNSCROLLED:', JSON.stringify(unscrolled, null, 2));
  await page.screenshot({ path: '/tmp/final-unscrolled.png' });

  // ── State 2: scroll container 400px ─────────────────────────────────
  await page.evaluate(() => {
    const container = document.querySelector('[data-testid="master-matrix-container"]');
    if (container) container.scrollTop = 400;
  });
  await page.waitForTimeout(600);

  const scrolled = await page.evaluate(() => {
    const container = document.querySelector('[data-testid="master-matrix-container"]');
    const corner = document.querySelector('[data-testid="master-matrix-corner"]');
    const teachers = document.querySelectorAll('[data-testid^="master-matrix-teacher-"]');
    const cntR = container?.getBoundingClientRect();
    const crR = corner?.getBoundingClientRect();
    const t1R = teachers[0]?.getBoundingClientRect();
    return {
      containerScrollTop: container?.scrollTop,
      containerTop: cntR?.top.toFixed(1),
      cornerTop: crR?.top.toFixed(1),  // should = containerTop (stuck at top:0)
      cornerBottom: crR?.bottom.toFixed(1),
      firstTeacherTop: t1R?.top.toFixed(1),
      // After scrolling 400px, first teacher is at: containerTop + 36 + 38 - 400 = containerTop - 326
      // Corner should be sticky at containerTop + 0 = containerTop
      headerIsSticky: crR && cntR ? Math.abs(crR.top - cntR.top) < 2 : null,
    };
  });
  console.log('SCROLLED 400px:', JSON.stringify(scrolled, null, 2));
  await page.screenshot({ path: '/tmp/final-scrolled.png' });

  await browser.close();
  console.log('Screenshots saved: /tmp/final-unscrolled.png, /tmp/final-scrolled.png');
})();
