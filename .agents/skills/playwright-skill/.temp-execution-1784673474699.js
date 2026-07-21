const { chromium } = require('playwright-core');
const fs = require('fs');

(async () => {
  const token = fs.readFileSync('/tmp/qa_teacher_token.txt', 'utf8').trim();
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.addInitScript((t) => localStorage.setItem('nassaq_token', t), token);

  await page.goto('http://localhost:5000/teacher/students', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(4000);

  await page.locator('[data-testid^="student-card-"]').first().click();
  await page.waitForTimeout(3000);

  const plansTab = page.locator('[data-testid="tab-student-plans"]');
  console.log('plans tab count:', await plansTab.count());
  await plansTab.first().click();
  await page.waitForTimeout(3000);

  const dlgText = await page.locator('[role="dialog"]').last().innerText().catch(() => '');
  console.log('has enrichment label:', dlgText.includes('الإثرائية'));
  console.log('has remedial label (should be false):', dlgText.includes('العلاجية'));
  await page.screenshot({ path: '/tmp/teacher-plans-tab.png' });
  await browser.close();
})().catch(e => { console.error('FAIL:', e.message); process.exit(1); });
