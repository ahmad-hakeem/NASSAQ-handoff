const { chromium } = require('playwright');

const BASE_URL = 'http://localhost:5000';
const EMAIL = 'amyra.alsaady@faarabi.edu';
const PASSWORD = 'Test@1234';
const TEST_INTRO = 'مقدمة اختبار للتحقق من الحفظ: ' + Date.now();

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(25000);

  try {
    console.log('1. Navigating to login...');
    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('networkidle');

    console.log('2. Logging in as teacher...');
    await page.fill('input[type="email"], input[name="email"]', EMAIL);
    await page.fill('input[type="password"], input[name="password"]', PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/teacher/, { timeout: 15000 });
    console.log('   Logged in, at:', page.url());

    console.log('3. Navigating to Teacher Achievements / Portfolio...');
    await page.goto(`${BASE_URL}/teacher/achievements`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);
    console.log('   At:', page.url());

    await page.screenshot({ path: '/tmp/portfolio-loaded.png' });

    // Find all textareas
    const textareas = await page.$$('textarea');
    console.log(`   Found ${textareas.length} textareas`);

    if (textareas.length === 0) {
      console.log('   No textarea found. Looking for expandable intro section...');
      // Check for collapsed section buttons
      const buttons = await page.$$eval('button', bs => bs.map(b => b.textContent?.trim()).filter(Boolean));
      console.log('   Buttons:', buttons.slice(0, 20).join(' | '));
      await page.screenshot({ path: '/tmp/portfolio-no-textarea.png' });

      // Try clicking "المقدمة" to expand it
      try {
        const introBtn = await page.$('text=المقدمة');
        if (introBtn) {
          await introBtn.click();
          await page.waitForTimeout(1000);
          const textareasAfter = await page.$$('textarea');
          console.log(`   After expanding: ${textareasAfter.length} textareas`);
        }
      } catch {}
    }

    const textareasNow = await page.$$('textarea');
    if (textareasNow.length === 0) {
      console.log('   ERROR: Still no textarea. Test cannot proceed.');
      process.exit(1);
    }

    // Read current intro value
    const currentValue = await textareasNow[0].inputValue();
    console.log(`   Current intro value: "${currentValue.substring(0, 60)}"`);

    // Intercept API call
    const apiResponses = [];
    page.on('response', async response => {
      if (response.url().includes('/teacher/portfolio/intro') && response.request().method() === 'PUT') {
        const status = response.status();
        let body = '';
        try { body = await response.text(); } catch {}
        apiResponses.push({ status, body });
        console.log(`   PUT /teacher/portfolio/intro → ${status}: ${body.substring(0, 200)}`);
      }
    });

    // Fill the textarea with test text
    await textareasNow[0].fill(TEST_INTRO);
    console.log('4. Filled intro textarea with test text');

    // Find and click the حفظ button
    const saveBtn = await page.$('button:has-text("حفظ")');
    if (!saveBtn) {
      const buttons = await page.$$eval('button', bs => bs.map(b => b.textContent?.trim()));
      console.log('   ERROR: Save button not found. Available:', buttons.join(' | '));
      process.exit(1);
    }

    console.log('5. Clicking save button...');
    await saveBtn.click();
    await page.waitForTimeout(3000);

    await page.screenshot({ path: '/tmp/portfolio-after-save.png' });
    console.log('   Screenshot: /tmp/portfolio-after-save.png');

    // Check what's visible
    const sonnerToasts = await page.$$('[data-sonner-toaster] li');
    const alertDialogs = await page.$$('[role="alertdialog"]');
    console.log(`   Sonner toasts: ${sonnerToasts.length}, Alert dialogs: ${alertDialogs.length}`);

    for (const toast of sonnerToasts) {
      const text = await toast.innerText();
      const dataType = await toast.getAttribute('data-type');
      console.log(`   Toast: type=${dataType}, text="${text}"`);
    }
    for (const dialog of alertDialogs) {
      const text = await dialog.innerText();
      console.log(`   AlertDialog: "${text.substring(0, 100)}"`);
    }

    // 6. Reload to verify persistence
    console.log('6. Reloading to verify persistence...');
    await page.reload();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2500);

    const textareasAfterReload = await page.$$('textarea');
    if (textareasAfterReload.length > 0) {
      const savedValue = await textareasAfterReload[0].inputValue();
      if (savedValue === TEST_INTRO) {
        console.log('   ✅ SAVE PERSISTS CORRECTLY');
      } else {
        console.log(`   ❌ SAVE DID NOT PERSIST`);
        console.log(`   Expected: "${TEST_INTRO.substring(0, 60)}"`);
        console.log(`   Got:      "${savedValue.substring(0, 60)}"`);
      }
    }

    await page.screenshot({ path: '/tmp/portfolio-after-reload.png' });
    console.log('   Screenshot: /tmp/portfolio-after-reload.png');

    console.log('\n✅ Test completed');
  } catch (err) {
    console.error('Test failed:', err.message);
    await page.screenshot({ path: '/tmp/portfolio-error.png' }).catch(() => {});
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
