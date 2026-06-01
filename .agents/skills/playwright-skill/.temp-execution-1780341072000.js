const { chromium } = require('playwright');

const BASE = 'http://localhost:5000';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();

  const consoleLogs = [];
  page.on('console', msg => {
    consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
    if (msg.type() === 'error' || msg.text().includes('NassaqAlert') || msg.text().includes('handleDelete') || msg.text().includes('callback')) {
      console.log(`CONSOLE: [${msg.type()}] ${msg.text()}`);
    }
  });

  // 1. Login
  await page.goto(`${BASE}/login`);
  await page.waitForSelector('input[type="email"], input[name="email"]', { timeout: 10000 });
  await page.fill('input[type="email"], input[name="email"]', 'mudeer@faarabi.edu');
  await page.fill('input[type="password"], input[name="password"]', 'Test@1234');
  await page.click('button[type="submit"]');
  await page.waitForNavigation({ timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(2000);
  console.log('After login URL:', page.url());

  // 2. Navigate to students
  await page.goto(`${BASE}/school/students`);
  await page.waitForTimeout(3000);
  console.log('Students page URL:', page.url());

  // 3. Take screenshot of page
  await page.screenshot({ path: '/tmp/students-page.png' });
  console.log('Screenshot saved to /tmp/students-page.png');

  // 4. Look for delete buttons
  const rows = await page.$$('[data-testid^="student-row-"]');
  console.log(`Found ${rows.length} student rows`);

  // Find first action menu / delete button
  const actionButtons = await page.$$('button[aria-haspopup], [data-testid*="action"], button:has-text("...")');
  console.log(`Found ${actionButtons.length} action buttons`);

  // Try to find and click the first dropdown trigger in table
  const dropdownTriggers = await page.$$('table button');
  console.log(`Found ${dropdownTriggers.length} buttons in table`);

  if (dropdownTriggers.length > 0) {
    await dropdownTriggers[0].click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: '/tmp/dropdown-open.png' });
    console.log('Dropdown screenshot saved');

    // Look for delete option
    const deleteOption = await page.$('[role="menuitem"]:has-text("حذف"), button:has-text("حذف"), [role="menuitem"]:has-text("Delete")');
    if (deleteOption) {
      const deleteText = await deleteOption.textContent();
      console.log('Delete option text:', deleteText);
      await deleteOption.click();
      await page.waitForTimeout(1000);

      // Check dialog
      const dialog = await page.$('[data-testid="nassaq-alert-dialog"]');
      if (dialog) {
        const dialogText = await dialog.textContent();
        console.log('Dialog appeared, text snippet:', dialogText.slice(0, 200));

        // Get all buttons in dialog
        const dialogButtons = await dialog.$$('button');
        for (const btn of dialogButtons) {
          const txt = await btn.textContent();
          console.log('Dialog button:', txt.trim());
        }

        // Click the first button (confirm)
        if (dialogButtons.length > 0) {
          const firstBtnText = await dialogButtons[0].textContent();
          console.log('Clicking button:', firstBtnText.trim());
          await dialogButtons[0].click();
          await page.waitForTimeout(2000);

          // Check console for debug logs
          console.log('\n--- Console logs after click ---');
          consoleLogs.forEach(l => console.log(l));
        }
      } else {
        console.log('No dialog found after clicking delete');
        await page.screenshot({ path: '/tmp/no-dialog.png' });
      }
    } else {
      console.log('No delete menu item found');
      const allMenuItems = await page.$$('[role="menuitem"]');
      for (const item of allMenuItems) {
        console.log('Menu item:', await item.textContent());
      }
    }
  }

  await page.screenshot({ path: '/tmp/final-state.png' });
  await browser.close();
  console.log('\nAll console logs:');
  consoleLogs.forEach(l => console.log(l));
})();
