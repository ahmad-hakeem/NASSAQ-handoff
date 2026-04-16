// NASSAQ School Admin E2E v2 — uses real testids discovered from dialog dumps.
// Strategy: shadcn Select = button[data-testid$="-select"] → click → pick first [role="option"]
const { chromium } = require('playwright');
const fs = require('fs');

const TARGET_URL = 'http://localhost:5000';
const API_URL    = 'http://localhost:8000';
const OUT        = '/tmp/e2e-school-admin';
const SHOTS      = `${OUT}/screenshots`;
fs.mkdirSync(SHOTS, { recursive: true });

const RUN_ID  = Date.now();
const MARKER  = `E2ETEST-${RUN_ID}`;
const ADMIN   = { email: 'mudeer@faarabi.edu', password: 'Test@1234' };
const ADMIN2  = { email: 'mudeer@ibnsina.edu', password: 'Test@1234' };

const report = []; const apiLog = []; const failures = []; const consoleMsgs = [];
let n = 0;
const log = (status, name, info={}) => {
  n++;
  const tag = status==='PASS'?'✓':status==='FAIL'?'✗':'•';
  console.log(`${tag} [${String(n).padStart(2,'0')}] ${name}${info.note?' — '+info.note:''}${info.error?' ERR='+info.error:''}`);
  report.push({ n, status, name, ...info, t: Date.now() });
};
const shot = async (page, name) => {
  const f = `${SHOTS}/${String(n).padStart(2,'0')}-${name.replace(/[^a-z0-9]+/gi,'_').slice(0,50)}.png`;
  try { await page.screenshot({ path: f, fullPage: true }); } catch {}
  return f;
};
const step = async (page, name, fn) => {
  const t0 = Date.now();
  try { const r = await fn(); log('PASS', name, { ms: Date.now()-t0, ...(r||{}) }); return r; }
  catch (e) { await shot(page, name+'-FAIL'); log('FAIL', name, { ms: Date.now()-t0, error: e.message.slice(0,200) }); return null; }
};

const login = async (page, who) => {
  await page.goto(`${TARGET_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.fill('#email', who.email);
  await page.fill('#password', who.password);
  await Promise.all([
    page.waitForURL(/\/(principal|admin|school|sub-admin|account)/, { timeout: 15000 }),
    page.click('[data-testid="login-submit-btn"]'),
  ]);
};
const logout = async (page) => {
  try {
    await page.click('[data-testid="logout-btn"]', { timeout: 3000 });
    await page.waitForTimeout(400);
    const yes = await page.$('button:has-text("تأكيد"), button:has-text("نعم"), button:has-text("Confirm")');
    if (yes) await yes.click();
    await page.waitForURL(/login/, { timeout: 8000 }).catch(()=>{});
  } catch { await page.goto(`${TARGET_URL}/login`); }
};
const goto = async (page, route) => {
  await page.goto(`${TARGET_URL}${route}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(900);
};

const successToast = async (page, t=5000) => {
  try {
    await Promise.race([
      page.waitForSelector('[data-sonner-toast][data-type="success"]', { timeout: t }),
      page.waitForSelector('[role="alertdialog"]:has-text("تم")', { timeout: t }),
      page.waitForSelector('text=/تم بنجاح|تمت الإضافة|تم الحفظ|تم الإنشاء|Successfully|Created|Saved/i', { timeout: t }),
    ]);
    return true;
  } catch { return false; }
};

// shadcn Select: button[data-testid$="-select"]; if none, any [role="combobox"]
const pickSelect = async (page, dialog, testidOrSelector, optionText=null) => {
  let btn;
  if (testidOrSelector.startsWith('[')) {
    btn = dialog.locator(testidOrSelector).first();
  } else {
    btn = dialog.locator(`[data-testid="${testidOrSelector}"]`).first();
  }
  if (!(await btn.count())) return false;
  await btn.click();
  await page.waitForTimeout(400);
  let opt;
  if (optionText) {
    opt = page.locator(`[role="option"]:has-text("${optionText}")`).first();
    if (!(await opt.count())) opt = page.locator(`[role="option"]`).first();
  } else {
    opt = page.locator(`[role="option"]:not([data-disabled])`).first();
  }
  if (!(await opt.count())) return false;
  await opt.click();
  return true;
};

const dismissError = async (page) => {
  // close any error dialog/toast that may be blocking
  const close = await page.$('[role="alertdialog"] button:has-text("حسناً"), [role="alertdialog"] button:has-text("OK"), [role="dialog"] button:has-text("حسناً")');
  if (close) { await close.click().catch(()=>{}); await page.waitForTimeout(300); }
};

const deleteByMarker = async (page, marker, max=10) => {
  let removed = 0;
  for (let i=0; i<max; i++) {
    await dismissError(page);
    const row = page.locator('tr', { hasText: marker }).first();
    if (!(await row.count())) break;
    // Try direct delete button first
    let clicked = false;
    const direct = row.locator('button[aria-label*="حذف"], button[title*="حذف"], button:has(svg.lucide-trash-2), button:has(svg.lucide-trash)').first();
    if (await direct.count()) { await direct.click().catch(()=>{}); clicked = true; }
    if (!clicked) {
      const menu = row.locator('button[aria-haspopup="menu"], button:has(svg.lucide-more-horizontal), button:has(svg.lucide-more-vertical)').first();
      if (await menu.count()) {
        await menu.click().catch(()=>{}); await page.waitForTimeout(250);
        const item = page.locator('[role="menuitem"]:has-text("حذف"), [role="menuitem"]:has-text("Delete")').first();
        if (await item.count()) { await item.click(); clicked = true; }
      }
    }
    if (!clicked) break;
    await page.waitForTimeout(500);
    const confirm = page.locator('[role="alertdialog"] button:has-text("حذف"), [role="alertdialog"] button:has-text("تأكيد"), button:has-text("نعم، احذف")').last();
    if (await confirm.count()) await confirm.click().catch(()=>{});
    await successToast(page, 4000);
    await page.waitForTimeout(700);
    removed++;
  }
  return removed;
};

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'ar-SA' });
  const page = await ctx.newPage();

  page.on('response', r => {
    const u = r.url();
    if (u.includes('/api/')) {
      const e = { method: r.request().method(), url: u.replace(API_URL,''), status: r.status() };
      apiLog.push(e); if (r.status() >= 400) failures.push(e);
    }
  });
  page.on('console', m => { if (m.type()==='error') consoleMsgs.push({ type:'error', text:m.text() }); });
  page.on('pageerror', e => consoleMsgs.push({ type:'pageerror', text:e.message }));

  console.log(`\n=== NASSAQ E2E v2 — ${MARKER} ===\n`);

  // 1. LOGIN
  await step(page, 'Login (Al-Farabi admin)', async () => { await login(page, ADMIN); return { url: page.url() }; });
  await shot(page, 'after-login');

  // 2. ACADEMIC STRUCTURE (read)
  await step(page, 'Academic Structure (read-only)', async () => {
    await goto(page, '/school/settings?section=academic');
    await page.waitForTimeout(1500);
    const t = await page.locator('body').innerText();
    if (!/أكاديمي|Academic|عام|Year|grade|مرحلة/i.test(t)) throw new Error('Academic content missing');
  });

  // 3. SUBJECTS — full CRUD (let's see what's actually there)
  await step(page, 'Subjects — open', async () => {
    await goto(page, '/admin/subjects');
    await page.waitForSelector('[data-testid="add-subject-btn"]', { timeout: 8000 });
  });

  await step(page, 'Subjects — create', async () => {
    await page.click('[data-testid="add-subject-btn"]');
    await page.waitForSelector('[role="dialog"]', { timeout: 5000 });
    await page.waitForTimeout(400);
    const dlg = page.locator('[role="dialog"]').first();
    // Dump for the record
    const dump = await page.evaluate(() => {
      const d = document.querySelector('[role="dialog"]'); if (!d) return null;
      const trim = s => (s||'').trim().replace(/\s+/g,' ').slice(0,60);
      return {
        title: trim(d.querySelector('h1,h2,h3')?.innerText||''),
        inputs: [...d.querySelectorAll('input,select,textarea')].map(i => ({type:i.type||i.tagName.toLowerCase(),placeholder:i.placeholder,testid:i.getAttribute('data-testid')})),
        buttons: [...d.querySelectorAll('button')].map(b => ({text:trim(b.innerText),testid:b.getAttribute('data-testid'),type:b.type})),
      };
    });
    fs.writeFileSync(`${OUT}/dialog-subject.json`, JSON.stringify(dump, null, 2));
    // Fill all visible text inputs
    const txts = await dlg.locator('input[type="text"], input:not([type])').all();
    if (txts[0]) await txts[0].fill(`${MARKER}-Math-AR`);
    if (txts[1]) await txts[1].fill(`${MARKER}-Math-EN`);
    if (txts[2]) await txts[2].fill(`E2E${RUN_ID.toString().slice(-5)}`);
    const num = dlg.locator('input[type="number"]').first();
    if (await num.count()) await num.fill('3');
    // Try any select buttons
    const selectBtns = await dlg.locator('button[data-testid$="-select"], button[role="combobox"]').all();
    for (const sb of selectBtns) {
      try {
        await sb.click(); await page.waitForTimeout(300);
        const opt = page.locator('[role="option"]:not([data-disabled])').first();
        if (await opt.count()) await opt.click();
        await page.waitForTimeout(200);
      } catch {}
    }
    await dlg.locator('button[data-testid="create-subject-btn"], button[type="submit"]:has-text("إضافة"), button:has-text("حفظ")').first().click();
    if (!(await successToast(page, 6000))) throw new Error('No success toast');
    await page.waitForTimeout(800);
  });
  await shot(page, 'subjects-after-create');

  await step(page, 'Subjects — verify in list', async () => {
    await goto(page, '/admin/subjects');
    await page.waitForTimeout(1200);
    const c = await page.locator(`text=${MARKER}`).count();
    if (!c) throw new Error('Subject not visible after create');
    return { matches: c };
  });

  // 4. TIME SLOTS
  await step(page, 'TimeSlots — create', async () => {
    await goto(page, '/admin/time-slots');
    await page.click('[data-testid="add-slot-btn"]');
    await page.waitForSelector('[role="dialog"]', { timeout: 5000 });
    await page.waitForTimeout(400);
    const dlg = page.locator('[role="dialog"]').first();
    await dlg.locator('[data-testid="slot-name-input"]').fill(`${MARKER}-Slot`).catch(()=>{});
    const times = await dlg.locator('input[type="time"]').all();
    if (times[0]) await times[0].fill('06:30');
    if (times[1]) await times[1].fill('07:15');
    const num = dlg.locator('input[type="number"]').first();
    if (await num.count()) await num.fill('99');
    await dlg.locator('[data-testid="create-slot-btn"], button[type="submit"]:has-text("إضافة")').first().click();
    if (!(await successToast(page, 6000))) throw new Error('No success toast');
  });

  // 5. CLASSES
  await step(page, 'Classes — create', async () => {
    await goto(page, '/admin/classes');
    await page.click('[data-testid="add-class-btn"]');
    await page.waitForSelector('[role="dialog"]', { timeout: 5000 });
    await page.waitForTimeout(400);
    const dlg = page.locator('[role="dialog"]').first();
    // pick grade then section then teacher (skip school select — usually pre-filled)
    await pickSelect(page, dlg, 'class-grade-select');
    await page.waitForTimeout(300);
    // The section/teacher buttons have no testid; pick the next select buttons
    const remaining = await dlg.locator('button:has-text("اختر")').all();
    for (const b of remaining) {
      try { await b.click(); await page.waitForTimeout(250);
        const opt = page.locator('[role="option"]:not([data-disabled])').first();
        if (await opt.count()) await opt.click();
        await page.waitForTimeout(200);
      } catch {}
    }
    // capacity
    const num = dlg.locator('input[type="number"]').first();
    if (await num.count()) await num.fill('30');
    await dlg.locator('[data-testid="create-class-btn"]').click();
    if (!(await successToast(page, 6000))) throw new Error('No success toast');
  });

  // 6. STUDENTS
  await step(page, 'Students — create', async () => {
    await goto(page, '/admin/students');
    await page.click('[data-testid="add-student-btn"]');
    await page.waitForSelector('[role="dialog"]', { timeout: 5000 });
    await page.waitForTimeout(500);
    const dlg = page.locator('[role="dialog"]').first();
    await dlg.locator('[data-testid="student-name-input"]').fill(`${MARKER}-Student`);
    await dlg.locator('[data-testid="student-number-input"]').fill(`E2E${RUN_ID.toString().slice(-5)}`);
    const date = dlg.locator('input[type="date"]').first();
    if (await date.count()) await date.fill('2015-01-01');
    // remaining text inputs (parent name, phone)
    const txts = await dlg.locator('input[type="text"]:not([data-testid="student-name-input"]):not([data-testid="student-number-input"])').all();
    if (txts[0]) await txts[0].fill(`${MARKER}-Parent`);
    if (txts[1]) await txts[1].fill('+966500000000');
    // shadcn selects
    const selectBtns = await dlg.locator('button:has-text("اختر")').all();
    for (const b of selectBtns) {
      try { await b.click(); await page.waitForTimeout(250);
        const opt = page.locator('[role="option"]:not([data-disabled])').first();
        if (await opt.count()) await opt.click();
        await page.waitForTimeout(200);
      } catch {}
    }
    await dlg.locator('[data-testid="create-student-btn"]').click();
    if (!(await successToast(page, 8000))) throw new Error('No success toast');
  });

  // 7. TEACHER ASSIGNMENT
  await step(page, 'Teacher Assignments — create', async () => {
    await goto(page, '/admin/teacher-assignments');
    await page.click('[data-testid="add-assignment-btn"]');
    await page.waitForSelector('[role="dialog"]', { timeout: 5000 });
    await page.waitForTimeout(400);
    const dlg = page.locator('[role="dialog"]').first();
    await pickSelect(page, dlg, 'teacher-select');
    await page.waitForTimeout(300);
    await pickSelect(page, dlg, 'subject-select');
    await page.waitForTimeout(300);
    await pickSelect(page, dlg, 'class-select');
    await page.waitForTimeout(300);
    await dlg.locator('[data-testid="weekly-sessions-input"]').fill('2');
    await dlg.locator('[data-testid="create-assignment-btn"]').click();
    if (!(await successToast(page, 8000))) throw new Error('No success toast');
  });

  // 8. PARENTS
  await step(page, 'Parents — list visible', async () => {
    await goto(page, '/principal/users-management');
    await page.waitForTimeout(1500);
    const t = await page.locator('body').innerText();
    if (!/ولي|Parent|أولياء/i.test(t)) throw new Error('Parents content missing');
  });

  // 9. SCHOOL TIMETABLE
  await step(page, 'School Timetable — view', async () => {
    await goto(page, '/admin/schedule');
    await page.waitForTimeout(2000);
  });

  // 10. TIMETABLE GENERATION (no publish)
  await step(page, 'Timetable Generation — open page (no publish)', async () => {
    await goto(page, '/principal/timetable');
    await page.waitForTimeout(2500);
  });

  // 11. COMMUNICATION CENTER — REAL SEND
  await step(page, 'Communication Center — REAL send', async () => {
    await goto(page, '/principal/communication');
    await page.waitForSelector('[data-testid="message-title-input"]', { timeout: 12000 });
    await page.fill('[data-testid="message-title-input"]', `${MARKER} — Automated E2E`);
    await page.fill('[data-testid="message-content-input"]',
      `Automated E2E test (${MARKER}) — sent ${new Date().toISOString()}. Safe to ignore.`);
    // pick first audience option
    const audCombos = await page.locator('button[role="combobox"], button[data-testid$="-select"]').all();
    for (const c of audCombos.slice(0,2)) {
      try { await c.click(); await page.waitForTimeout(300);
        const opt = page.locator('[role="option"]:not([data-disabled])').first();
        if (await opt.count()) await opt.click();
        await page.waitForTimeout(200);
      } catch {}
    }
    const send = page.locator('button:has-text("إرسال"), button[data-testid="send-message-btn"], button:has-text("Send")').first();
    if (!(await send.count())) throw new Error('Send button not found');
    await send.click();
    await page.waitForTimeout(800);
    const confirm = page.locator('[role="alertdialog"] button:has-text("تأكيد"), [role="alertdialog"] button:has-text("إرسال"), [role="alertdialog"] button:has-text("نعم")').last();
    if (await confirm.count() && await confirm.isVisible().catch(()=>false)) await confirm.click();
    if (!(await successToast(page, 12000))) throw new Error('No success after send');
  });

  // 12. TENANT ISOLATION
  await step(page, 'Tenant isolation — switch & verify', async () => {
    await logout(page);
    await login(page, ADMIN2);
    await goto(page, '/admin/subjects');
    await page.waitForTimeout(1500);
    const leak = await page.locator(`text=${MARKER}`).count();
    if (leak > 0) throw new Error(`Tenant leak: ${leak} records visible in Ibn Sina`);
    return { leak };
  });

  // 13. CLEANUP
  await step(page, 'Cleanup — login back as Al-Farabi', async () => {
    await logout(page); await login(page, ADMIN);
  });

  for (const route of ['/admin/teacher-assignments', '/admin/students', '/admin/classes', '/admin/time-slots', '/admin/subjects']) {
    await step(page, `Cleanup ${route}`, async () => {
      await goto(page, route);
      const removed = await deleteByMarker(page, MARKER);
      return { removed, note: `removed=${removed}` };
    });
  }

  // ---------------- WRITE REPORT ----------------
  fs.writeFileSync(`${OUT}/network.log`, apiLog.map(r=>`${r.status} ${r.method} ${r.url}`).join('\n'));
  fs.writeFileSync(`${OUT}/network-failures.log`,
    failures.length ? failures.map(r=>`${r.status} ${r.method} ${r.url}`).join('\n') : '(none)');
  fs.writeFileSync(`${OUT}/console.log`, consoleMsgs.map(c=>`[${c.type}] ${c.text}`).join('\n'));

  const lines = [];
  lines.push(`# NASSAQ School Admin E2E — Run ${RUN_ID}`);
  lines.push(`Marker: \`${MARKER}\``);
  lines.push(`PASS: ${report.filter(r=>r.status==='PASS').length}  FAIL: ${report.filter(r=>r.status==='FAIL').length}  Total: ${report.length}`);
  lines.push(`API requests: ${apiLog.length}  4xx/5xx: ${failures.length}`);
  lines.push(`Console errors: ${consoleMsgs.length}`);
  lines.push(``);
  lines.push(`| # | Status | Step | ms | Notes |`);
  lines.push(`|---|---|---|---|---|`);
  for (const r of report) {
    const note = r.error || r.note || '';
    lines.push(`| ${r.n} | ${r.status} | ${r.name} | ${r.ms||''} | ${String(note).replace(/\|/g,'\\|').slice(0,90)} |`);
  }
  lines.push(``);
  lines.push(`## Failed API requests (first 30)`);
  lines.push('```');
  lines.push(failures.slice(0,30).map(f=>`${f.status} ${f.method} ${f.url}`).join('\n') || '(none)');
  lines.push('```');
  lines.push(``);
  lines.push(`## Console errors (first 30)`);
  lines.push('```');
  lines.push(consoleMsgs.slice(0,30).map(c=>`[${c.type}] ${c.text}`.slice(0,200)).join('\n') || '(none)');
  lines.push('```');
  fs.writeFileSync(`${OUT}/report.md`, lines.join('\n'));

  console.log(`\nDONE — PASS=${report.filter(r=>r.status==='PASS').length} FAIL=${report.filter(r=>r.status==='FAIL').length} APIfails=${failures.length}`);
  await browser.close();
})().catch(e => { console.error('FATAL:', e); process.exit(1); });
