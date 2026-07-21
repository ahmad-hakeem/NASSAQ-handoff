const { chromium } = require('playwright');
const fs = require('fs');

const BASE = 'http://localhost:5000';
const TOKEN = fs.readFileSync('/tmp/qa_teacher_token.txt', 'utf8').trim();

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 300)); });

  await page.addInitScript((tok) => {
    window.localStorage.setItem('nassaq_token', tok);
  }, TOKEN);

  // Entry point 1: طلابي (TeacherStudentsPage — same dialog Risk Radar deep-links into)
  await page.goto(`${BASE}/teacher/students`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid^="student-card-"]', { timeout: 20000 });
  await page.locator('[data-testid^="student-card-"]').first().click();
  await page.waitForSelector('[role="dialog"]', { timeout: 15000 });
  await page.waitForTimeout(2000);

  const plansTab = page.locator('[role="dialog"] [role="tab"]:has-text("الخطط")').first();
  const vis1 = await plansTab.isVisible().catch(() => false);
  console.log('ENTRY1 plans tab visible:', vis1);
  if (!vis1) {
    const tabs = await page.locator('[role="dialog"] [role="tab"]').allInnerTexts().catch(() => []);
    console.log('tabs found:', JSON.stringify(tabs));
    await page.screenshot({ path: '/tmp/qa2_student_dialog.png' });
    await browser.close();
    return;
  }
  await plansTab.click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: '/tmp/qa3_plans_tab.png' });

  // Generate the remedial plan (live LLM call)
  const genBtn = page.locator('[role="dialog"] button:has-text("أنشئ الخطة العلاجية")').first();
  if (await genBtn.isVisible().catch(() => false)) {
    console.log('clicking generate remedial...');
    await genBtn.click();
    try {
      await page.waitForSelector('[role="dialog"] button:has-text("تصدير")', { timeout: 80000 });
      console.log('GENERATED: export button appeared');
    } catch {
      console.log('no export button within 80s');
    }
    await page.waitForTimeout(1500);
    await page.screenshot({ path: '/tmp/qa4_after_generate.png' });
    const after = await page.locator('[role="dialog"]').first().innerText().catch(() => '');
    console.log('--- ENTRY1 after generate (1000) ---');
    console.log(after.slice(0, 1000));
  } else {
    const btns = await page.locator('[role="dialog"] button').allInnerTexts().catch(() => []);
    console.log('generate button not found; dialog buttons:', JSON.stringify(btns).slice(0, 500));
  }

  console.log('console errors:', errors.length ? JSON.stringify(errors.slice(0, 5)) : 'none');
  await browser.close();
})();
