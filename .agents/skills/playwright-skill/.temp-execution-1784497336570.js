const { chromium } = require('playwright');
const fs = require('fs');

const BASE = 'http://localhost:5000';
const state = JSON.parse(fs.readFileSync('/tmp/qa_state.json', 'utf8'));

async function testRole(browser, label, token, sessionId) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on('pageerror', (e) => consoleErrors.push(String(e)));

  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.evaluate((t) => localStorage.setItem('nassaq_token', t), token);

  await page.goto(BASE + '/teacher/classes?tab=sessions', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(6000);
  console.log(`[${label}] after load url:`, page.url());

  // Find the session card for our active session (active statuses render a blue icon;
  // just click the first card in the sessions list that is NOT completed/cancelled).
  // Cards are rendered as clickable Card elements; locate by the active-status badge text.
  const activeBadges = ['جارية', 'قيد الشرح', 'تفاعل جارٍ', 'مراجعة'];
  let clicked = false;
  for (const txt of activeBadges) {
    const card = page.locator('.cursor-pointer', { hasText: txt }).first();
    if (await card.count() > 0 && await card.isVisible().catch(() => false)) {
      await card.click();
      clicked = true;
      console.log(`[${label}] clicked card with badge:`, txt);
      break;
    }
  }
  if (!clicked) {
    // fallback: click first session card in list
    const firstCard = page.locator('[class*="cursor-pointer"]').first();
    await firstCard.click({ timeout: 10000 }).catch((e) => console.log(`[${label}] fallback card click failed:`, String(e).slice(0, 120)));
  }
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `/tmp/qa_${label}_dialog.png` });

  const btn = page.getByRole('button', { name: /متابعة الحصة|Continue Session/ }).first();
  const btnVisible = await btn.isVisible().catch(() => false);
  console.log(`[${label}] continue button visible:`, btnVisible);
  if (!btnVisible) {
    console.log(`[${label}] FAIL: continue button not found`);
    await ctx.close();
    return false;
  }
  await btn.click();
  await page.waitForTimeout(5000);
  const url = new URL(page.url());
  await page.screenshot({ path: `/tmp/qa_${label}_after.png` });
  console.log(`[${label}] after continue url:`, url.pathname);
  const onTeach = url.pathname === '/teacher/session/teach';
  const onLanding = url.pathname === '/' || url.pathname === '/landing';
  console.log(`[${label}] RESULT:`, onTeach ? 'PASS (on teach page)' : (onLanding ? 'FAIL (bounced to landing)' : `UNEXPECTED (${url.pathname})`));
  if (consoleErrors.length) console.log(`[${label}] page errors:`, consoleErrors.slice(0, 3));
  await ctx.close();
  return onTeach;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const r1 = await testRole(browser, 'school_teacher', state.school_teacher.token, state.school_teacher.session_id);
  const r2 = await testRole(browser, 'independent_teacher', state.independent_teacher.token, state.independent_teacher.session_id);
  await browser.close();
  console.log('FINAL:', r1 && r2 ? 'ALL PASS' : 'SOME FAILED');
  process.exit(r1 && r2 ? 0 : 1);
})();
