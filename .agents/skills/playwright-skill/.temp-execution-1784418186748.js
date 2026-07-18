const fs = require('fs');
const { chromium } = require('playwright');

const BASE = 'http://localhost:5000';

(async () => {
  const token = fs.readFileSync('/tmp/qa_parent_token.txt', 'utf8').trim();
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  await page.addInitScript((tok) => { localStorage.setItem('nassaq_token', tok); }, token);
  await page.goto(`${BASE}/parent`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(2500);

  // Accept first-login charter modal if present
  const charterBtn = page.locator('[data-testid="button-accept-charter"]');
  if (await charterBtn.count()) {
    const cb = page.locator('[data-testid="checkbox-accept-charter"]');
    if (await cb.count()) await cb.click().catch(() => {});
    await charterBtn.click().catch(() => {});
    await page.waitForTimeout(1000);
  }

  // Navigate to Student File (ملف الطالب)
  await page.locator('aside a, aside button').filter({ hasText: 'ملف الطالب' }).first().click();
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(3000);
  console.log('URL:', new URL(page.url()).pathname);

  // Open the cumulative details view if behind a toggle/button
  const cumBtn = page.locator('button, a').filter({ hasText: /التفاصيل التراكمية|التراكمية/ }).first();
  if (await cumBtn.count()) {
    await cumBtn.click().catch(() => {});
    await page.waitForLoadState('networkidle').catch(() => {});
    await page.waitForTimeout(3000);
  }

  // Find the homework completion metric near مؤشر المتابعة المنزلية
  const bodyText = await page.locator('body').innerText();
  const hasFollowUp = bodyText.includes('مؤشر المتابعة المنزلية');
  console.log('follow-up panel present:', hasFollowUp);

  const m = bodyText.match(/إنجاز الواجبات\s*\n?\s*([0-9.]+)%/) || bodyText.match(/الواجبات\s*\n?\s*([0-9.]+)%/);
  if (!m) {
    console.log('BODY SNIPPET:', JSON.stringify(bodyText.slice(bodyText.indexOf('المتابعة المنزلية') - 200, bodyText.indexOf('المتابعة المنزلية') + 400)));
    throw new Error('homework completion metric not found on page');
  }
  const rate = parseFloat(m[1]);
  console.log('homework completion shown:', rate + '%');
  if (rate === 0) throw new Error('STILL 0% — bug not fixed in UI');

  // Contradiction check: old false weakness must be gone
  if (bodyText.includes('واجبات غير مكتملة')) {
    console.log('WARN: واجبات غير مكتملة still shown — checking rate context');
    if (rate >= 60) throw new Error('weakness shown despite rate >= 60');
  } else {
    console.log('OK: no false "واجبات غير مكتملة" weakness');
  }

  await page.screenshot({ path: '/tmp/qa-parent-hw.png', fullPage: false });
  console.log('PARENT HOMEWORK METRIC PASS');
  await browser.close();
})().catch((e) => { console.error('QA FAILED:', e.message); process.exit(1); });
