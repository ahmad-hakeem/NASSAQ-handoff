const fs = require('fs');
const { chromium } = require('playwright');

const BASE = 'http://localhost:5000';
const CREDS_FILE = '/home/runner/workspace/TEST_CREDENTIALS.md';

(async () => {
  const token = fs.readFileSync('/tmp/qa_parent_token.txt', 'utf8').trim();

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const paletteCalls = [];
  page.on('response', (r) => {
    if (r.url().includes('/api/search/palette')) paletteCalls.push(r.status());
  });

  // Inject minted QA token before app boot (parent form creds are stale).
  await page.addInitScript((tok) => { localStorage.setItem('nassaq_token', tok); }, token);
  await page.goto(`${BASE}/parent`, { waitUntil: 'domcontentloaded' });
  try {
    await page.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 25000 });
  } catch (e) {
    console.log('PARENT TOKEN AUTH FAILED — url still', page.url());
    await browser.close();
    process.exit(2);
  }
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(2500);

  const charter = page.locator('[data-testid="parent-charter-modal"]');
  if (await charter.isVisible().catch(() => false)) {
    const cb = page.locator('[data-testid="checkbox-accept-charter"]');
    if (await cb.isVisible().catch(() => false)) await cb.click();
    await page.click('[data-testid="button-accept-charter"]');
    await page.waitForTimeout(1500);
    console.log('[parent] charter modal accepted');
  }

  // badge check
  const badgeCount = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll('aside a, nav a, aside button'));
    const targets = links.filter((a) => /الإشعارات|التواصل|Notifications|Communication/.test(a.textContent || ''));
    let bad = 0;
    for (const t of targets) {
      for (const s of Array.from(t.querySelectorAll('span, div'))) {
        const txt = (s.textContent || '').trim();
        if (/^\d{1,3}\+?$/.test(txt) && txt !== '') bad += 1;
      }
    }
    return bad;
  });
  if (badgeCount > 0) throw new Error(`[parent] FOUND ${badgeCount} numeric badge(s) in sidebar`);
  console.log('[parent] OK: no numeric unread badges in sidebar');

  const btn = page.locator('[data-testid="sidebar-cmdk-btn"]').first();
  await btn.waitFor({ state: 'visible', timeout: 15000 });
  console.log('[parent] OK: sidebar search icon visible');
  await btn.click();
  await page.waitForSelector('[data-testid="cmdk-panel"]', { timeout: 10000 });
  console.log('[parent] OK: palette opens');

  await page.fill('[data-testid="cmdk-input"]', 'التواصل');
  await page.waitForTimeout(2000);
  if (paletteCalls.length) throw new Error('[parent] /search/palette WAS called — must be nav-only');
  const nNav = await page.locator('[data-testid^="cmdk-result-nav-"]').count();
  if (nNav === 0) throw new Error('[parent] no navigation results for sidebar label query');
  console.log(`[parent] OK: nav-only search, ${nNav} nav result(s), zero backend palette calls`);
  await page.screenshot({ path: '/tmp/qa-parent-palette.png' });

  await page.locator('[data-testid^="cmdk-result-nav-"]').first().click();
  await page.waitForTimeout(1500);
  console.log(`[parent] OK: nav result navigated to ${new URL(page.url()).pathname}`);
  console.log('PARENT PASS');
  await browser.close();
})().catch((e) => { console.error('QA FAILED:', e.message); process.exit(1); });
