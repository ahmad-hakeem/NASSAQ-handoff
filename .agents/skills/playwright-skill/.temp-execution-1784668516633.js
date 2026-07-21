const { chromium } = require('@playwright/test');

const BASE_URL = 'http://localhost:5000';
const EMAIL = 'it_qa_test_1778703764@nassaq.test';
const PASSWORD = 'Test@1234';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(15000);

  try {
    // 1. Log in
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector('input[type="email"], input[name="email"]', { timeout: 8000 });
    await page.fill('input[type="email"], input[name="email"]', EMAIL);
    await page.fill('input[type="password"], input[name="password"]', PASSWORD);
    await page.click('button[type="submit"]');

    // 2. Wait for home page
    await page.waitForURL(/\/teacher/, { timeout: 12000 });
    await page.waitForTimeout(2500); // let calendar fetch settle

    // 3. Screenshot the home page
    await page.screenshot({ path: '/tmp/it-home-calendar-widget.png', fullPage: false });
    console.log('LOGIN_OK url=' + page.url());

    // 4. Check for widget heading
    const calText = await page.$$eval('h2, p, span', els =>
      els.map(e => e.textContent.trim()).filter(t => t.includes('تقويمي الشخصي') || t.includes('My Personal Calendar'))
    );
    console.log('WIDGET_HEADINGS=' + JSON.stringify(calText));

    // 5. Check for empty state or event rows
    const emptyMsg = await page.$eval('[class*="border-dashed"] p, [class*="border-dashed"]', el => el?.textContent?.trim()).catch(() => null);
    console.log('EMPTY_STATE=' + emptyMsg);

    const eventRows = await page.$$eval('[class*="divide-y"] > div', rows => rows.map(r => r.textContent?.trim()?.slice(0, 60)));
    console.log('EVENT_ROWS=' + JSON.stringify(eventRows));

    // 6. Click "View All" button and verify navigation
    const viewAllBtn = page.getByText('عرض الكل').first();
    if (await viewAllBtn.isVisible().catch(() => false)) {
      await viewAllBtn.click();
      await page.waitForTimeout(1200);
      console.log('AFTER_VIEW_ALL url=' + page.url());
    } else {
      console.log('VIEW_ALL_BTN=not visible');
    }

    // 7. Final screenshot
    await page.screenshot({ path: '/tmp/it-home-after-viewall.png' });

  } catch (err) {
    console.error('ERROR:', err.message);
    await page.screenshot({ path: '/tmp/it-home-error.png' }).catch(() => {});
  } finally {
    await browser.close();
  }
})();
