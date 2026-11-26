const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:5055', OUT = __dirname + '/out';
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(BASE + '/practice', { waitUntil: 'networkidle' });
  await p.fill('#practiceStudentName', '测试学生'); await p.click('#practiceIdentitySubmit'); await p.waitForTimeout(1200);
  for (const [i, name] of [[0, 'intensive'], [1, 'reading'], [2, 'listening']]) {
    await p.goto(BASE + '/practice', { waitUntil: 'networkidle' }); await p.waitForTimeout(700);
    await Promise.all([p.waitForLoadState('networkidle'), p.locator('.practice-task:not(.practice-task--locked)').nth(i).click()]);
    await p.waitForTimeout(800);
    const before = p.url();
    await p.locator('[data-practice-back]:visible').first().click(); await p.waitForTimeout(800);
    const dlg = await p.evaluate(() => { const d = document.querySelector('dialog[open]'); return d ? d.innerText.replace(/\s+/g, ' ').slice(0, 200) : null; });
    await p.screenshot({ path: `${OUT}/shots/back-dialog-${name}.png` });
    let after = null;
    if (dlg) { await p.locator('dialog[open] [data-practice-exit-confirm]').click().catch(() => {}); await p.waitForTimeout(1500); after = p.url().replace(BASE, ''); }
    const status = await p.evaluate(() => (document.querySelector('[data-practice-save-status]') || {}).innerText || '');
    console.log(JSON.stringify({ name, dialog: dlg, urlChangedWithoutDialog: before !== p.url() && !dlg, afterConfirm: after, saveStatus: status }));
  }
  await b.close();
})();
