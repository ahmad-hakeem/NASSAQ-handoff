// Slim IT-only persistence check: edit built-in behaviour score -> 7, wait for
// the 10s autosave, reload, reopen dialog, verify +7 restored.
const fs = require('fs');
const tokens = JSON.parse(fs.readFileSync('/tmp/qa_tokens.json', 'utf8'));
const BASE = 'http://localhost:5000';
const cfg = {
  token: tokens.it,
  classId: '22e4c159-ff1e-4efa-916d-3bc439014e8d',
  subjectId: 'b4ca0953-72a6-4113-a096-e034ab10516e',
  className: 'فصل E2E',
  subjectName: 'مادة',
};

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ locale: 'ar' });
  const page = await context.newPage();
  try {
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.evaluate((t) => localStorage.setItem('nassaq_token', t), cfg.token);
    const setup = await page.evaluate(async ({ classId, subjectId }) => {
      const tk = localStorage.getItem('nassaq_token');
      const h = { 'Content-Type': 'application/json', Authorization: `Bearer ${tk}` };
      const r = await fetch('/api/session/start', {
        method: 'POST', headers: h,
        body: JSON.stringify({ class_id: classId, subject_id: subjectId }),
      });
      const body = await r.json().catch(() => null);
      if (r.status >= 400) return { error: `start ${r.status}: ${JSON.stringify(body)}` };
      const sid = body.session_record_id || body.session_id || body.id;
      return { sid };
    }, cfg);
    if (setup.error) { console.log(`FAIL setup: ${setup.error}`); process.exit(1); }
    console.log(`session: ${setup.sid}`);
    await page.evaluate(({ sid, className, subjectName }) => {
      window.history.replaceState(
        { usr: { sessionId: sid, sessionInfo: { class_name: className, subject_name: subjectName }, startTime: new Date().toISOString() }, key: 'qa2', idx: 1 },
        '', '/teacher/session/teach'
      );
    }, { sid: setup.sid, className: cfg.className, subjectName: cfg.subjectName });
    await page.reload({ waitUntil: 'domcontentloaded' });

    const openBehaviours = async () => {
      const gear = page.locator('button:has(svg.lucide-settings)').first();
      await gear.waitFor({ state: 'visible', timeout: 45000 });
      await gear.click();
      const tab = page.getByText('السلوكيات', { exact: true }).first();
      await tab.waitFor({ state: 'visible', timeout: 15000 });
      await tab.click();
      await page.waitForTimeout(400);
    };

    await openBehaviours();
    const pencil = page.locator('button[aria-label="تعديل النقاط"], button[aria-label="Edit points"]').first();
    await pencil.waitFor({ state: 'visible', timeout: 10000 });
    await pencil.click();
    const editInput = page.locator('input[aria-label="تعديل النقاط"], input[aria-label="Edit points"]').first();
    await editInput.fill('7');
    await editInput.press('Enter');
    await page.waitForTimeout(300);
    console.log('edited to 7; waiting for autosave...');
    await page.waitForTimeout(12000);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await openBehaviours();
    const badges = await page.locator('span.tabular-nums').allInnerTexts();
    const still7 = badges.some((t) => t.replace(/\s/g, '').includes('7') && t.includes('+'));
    console.log(`IT persistence after reload: +7 restored = ${still7} (badges: ${badges.slice(0, 8).join(' | ')})`);
    await page.screenshot({ path: '/tmp/qa_it_persisted.png' });
  } catch (e) {
    console.log(`ERROR: ${e.message}`);
    try { await page.screenshot({ path: '/tmp/qa_it_persist_error.png' }); } catch (_) {}
  } finally {
    await browser.close();
  }
})();
