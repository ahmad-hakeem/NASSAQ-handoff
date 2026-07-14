const { chromium } = require('playwright');
const fs = require('fs');

const TOKEN = fs.readFileSync('/tmp/qa_token.txt', 'utf8').trim();
const BASE = 'http://localhost:5000';
const results = [];
const ok = (name, cond, detail = '') => {
  results.push(`${cond ? 'PASS' : 'FAIL'} — ${name}${detail ? ' — ' + detail : ''}`);
};

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });

  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.evaluate(t => localStorage.setItem('nassaq_token', t), TOKEN);
  await page.goto(BASE + '/principal/communication/notifications', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  // The notifications tab of communication center should be active; grab counter cards
  const getCards = async () => {
    // 4 counter cards: total, unread, read, read rate
    const nums = await page.$$eval('.grid.grid-cols-2 .text-xl.font-bold', els => els.map(e => e.textContent.trim()));
    return nums;
  };

  let cards = await getCards();
  console.log('cards initial:', cards);
  const total = parseInt(cards[0], 10);
  const unread = parseInt(cards[1], 10);
  ok('total card shows full inbox (64)', total === 64, `got ${cards[0]}`);
  ok('unread card shows 41', unread === 41, `got ${cards[1]}`);

  // Helper: count rendered notification cards inside the "all" tab list
  const countRows = async () =>
    (await page.$$('div[role="tabpanel"] .space-y-2\\.5 > div')).length;

  const initialRows = await countRows();
  console.log('rows unfiltered:', initialRows);
  ok('all rows rendered unfiltered', initialRows === 64, `got ${initialRows}`);

  // ---- Type filter ----
  // Open the type Select (first select trigger showing كل الأنواع)
  const selectByText = async (triggerText, optionText) => {
    const triggers = await page.$$('button[role="combobox"]');
    let found = false;
    for (const tr of triggers) {
      const txt = (await tr.textContent()).trim();
      if (txt.includes(triggerText)) { await tr.click(); found = true; break; }
    }
    if (!found) throw new Error('trigger not found: ' + triggerText);
    await page.waitForTimeout(300);
    await page.getByRole('option', { name: optionText, exact: true }).click();
    await page.waitForTimeout(600);
  };

  // Filter type = النظام (should now match warning/message/broadcast rows = 7)
  await selectByText('كل الأنواع', 'النظام');
  let n = await countRows();
  console.log('type=النظام rows:', n);
  ok('type filter النظام returns legacy-typed rows (7)', n === 7, `got ${n}`);
  cards = await getCards();
  ok('total card stays 64 while filtered', parseInt(cards[0], 10) === 64, `got ${cards[0]}`);

  // Filter type = التواصل (communication = 56)
  await selectByText('النظام', 'التواصل');
  n = await countRows();
  console.log('type=التواصل rows:', n);
  ok('type filter التواصل returns 56', n === 56, `got ${n}`);

  // Filter type = تعميم (circular = 1)
  await selectByText('التواصل', 'تعميم');
  n = await countRows();
  ok('type filter تعميم returns 1', n === 1, `got ${n}`);

  // Empty state: الحضور (attendance = 0)
  await selectByText('تعميم', 'الحضور');
  n = await countRows();
  const emptyState = await page.$('div[role="tabpanel"] >> text=/لا توجد|لا يوجد/');
  ok('type filter الحضور shows empty state, 0 rows', n === 0 && !!emptyState, `rows=${n} empty=${!!emptyState}`);

  // Back to all types
  await selectByText('الحضور', 'كل الأنواع');
  n = await countRows();
  ok('reset type filter restores 64', n === 64, `got ${n}`);

  // ---- Read/unread filter ----
  await selectByText('الكل', 'غير مقروء');
  n = await countRows();
  console.log('unread rows:', n);
  ok('read filter غير مقروء returns 41', n === 41, `got ${n}`);

  await selectByText('غير مقروء', 'مقروء');
  n = await countRows();
  ok('read filter مقروء returns 23', n === 23, `got ${n}`);

  await selectByText('مقروء', 'الكل');

  // ---- Priority filter ----
  // urgent(1) → حرجة (critical alias); normal(4)+medium(56)=60 متوسطة; high(3) مرتفعة
  await selectByText('كل الأولويات', 'حرجة');
  n = await countRows();
  ok('priority حرجة includes urgent alias (1)', n === 1, `got ${n}`);

  await selectByText('حرجة', 'متوسطة');
  n = await countRows();
  ok('priority متوسطة includes normal alias (60)', n === 60, `got ${n}`);

  await selectByText('متوسطة', 'مرتفعة');
  n = await countRows();
  ok('priority مرتفعة returns 3', n === 3, `got ${n}`);

  // ---- Combination: type النظام + priority متوسطة ----
  // النظام rows: warning(3, high) + message(2, normal) + broadcast(2, normal) → متوسطة matches 4
  await selectByText('مرتفعة', 'متوسطة');
  await selectByText('كل الأنواع', 'النظام');
  n = await countRows();
  ok('combo النظام+متوسطة returns 4', n === 4, `got ${n}`);

  // combo + read filter unread
  await selectByText('الكل', 'غير مقروء');
  n = await countRows();
  console.log('combo النظام+متوسطة+غير مقروء rows:', n);
  ok('combo with unread returns subset (<=4)', n <= 4, `got ${n}`);
  cards = await getCards();
  ok('total card still 64 under 3-filter combo', parseInt(cards[0], 10) === 64, `got ${cards[0]}`);

  await page.screenshot({ path: '/tmp/qa-notifications-combo.png' });

  // Reset all
  await selectByText('النظام', 'كل الأنواع');
  await selectByText('غير مقروء', 'الكل');
  await selectByText('متوسطة', 'كل الأولويات');
  n = await countRows();
  ok('full reset restores 64', n === 64, `got ${n}`);

  // ---- Period filter (اليوم) ----
  await selectByText('كل الفترات', 'اليوم');
  n = await countRows();
  console.log('period=اليوم rows:', n);
  ok('period اليوم returns fewer than 64', n < 64, `got ${n}`);
  await selectByText('اليوم', 'كل الفترات');

  await page.screenshot({ path: '/tmp/qa-notifications-final.png' });

  const realErrors = consoleErrors.filter(e => !e.includes('favicon') && !e.includes('manifest'));
  ok('no console errors', realErrors.length === 0, realErrors.slice(0, 3).join(' | '));

  console.log('\n===== RESULTS =====');
  results.forEach(r => console.log(r));
  const fails = results.filter(r => r.startsWith('FAIL')).length;
  console.log(`\n${results.length - fails}/${results.length} passed`);
  await browser.close();
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error('SCRIPT ERROR:', e.message); process.exit(2); });
