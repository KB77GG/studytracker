const { chromium } = require('playwright');
const fs = require('fs');
const BASE = 'http://127.0.0.1:5055';
const OUT = __dirname + '/out';
const rel = (u) => u.replace(BASE, '');
async function verified(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(BASE + '/practice', { waitUntil: 'networkidle' });
  await p.fill('#practiceStudentName', '测试学生'); await p.click('#practiceIdentitySubmit'); await p.waitForTimeout(1200);
  await p.close(); return ctx;
}
async function backButtons(p) {
  return p.evaluate(() => [...document.querySelectorAll('[data-practice-back],[data-practice-module-exit],.practice-shell__back,a,button')]
    .filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && /返回|退出/.test(e.innerText || ''); })
    .map((e) => (e.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 24)));
}
async function flow(ctx, name, startPath, clickSel, opts = {}) {
  const p = await ctx.newPage(); const steps = { name, start: startPath };
  try {
    await p.goto(BASE + startPath, { waitUntil: 'networkidle' });
    if (opts.scroll) { await p.evaluate((y) => window.scrollTo(0, y), opts.scroll); await p.waitForTimeout(200); }
    steps.scrollBefore = await p.evaluate(() => Math.round(scrollY));
    const target = p.locator(clickSel).first();
    steps.clickText = ((await target.innerText().catch(() => '')) || '').replace(/\s+/g, ' ').slice(0, 40);
    await Promise.all([p.waitForLoadState('networkidle'), target.click()]);
    await p.waitForTimeout(800);
    steps.landed = rel(p.url());
    steps.backButtons = await backButtons(p);
    const back = p.locator('[data-practice-back]:visible, .practice-shell__back:visible').first();
    if (await back.count()) {
      steps.backLabel = ((await back.innerText()) || '').trim();
      await Promise.all([p.waitForURL((u) => rel(u.toString()) !== steps.landed, { timeout: 8000 }).catch(() => {}), back.click()]);
      await p.waitForLoadState('networkidle').catch(() => {}); await p.waitForTimeout(800);
      steps.afterBack = rel(p.url()); steps.scrollAfterBack = await p.evaluate(() => Math.round(scrollY));
    } else steps.afterBack = '(无返回按钮)';
    // browser back from a fresh entry
    await p.goto(BASE + startPath, { waitUntil: 'networkidle' });
    await Promise.all([p.waitForLoadState('networkidle'), p.locator(clickSel).first().click()]); await p.waitForTimeout(600);
    await p.goBack().catch(() => {}); await p.waitForTimeout(1200);
    steps.afterBrowserBack = rel(p.url());
    const dlg = await p.evaluate(() => !!document.querySelector('dialog[open]'));
    if (dlg) steps.afterBrowserBack += ' (弹出对话框)';
  } catch (e) { steps.error = e.message.slice(0, 160); }
  await p.close(); return steps;
}
(async () => {
  const browser = await chromium.launch();
  const ctx = await verified(browser);
  const flows = [];
  // task cards
  const p = await ctx.newPage(); await p.goto(BASE + '/practice', { waitUntil: 'networkidle' }); await p.waitForTimeout(800);
  const cards = await p.$$eval('.practice-task:not(.practice-task--locked)', (as) => as.map((a) => a.getAttribute('href')));
  await p.close();
  for (let i = 0; i < cards.length; i++) flows.push(await flow(ctx, `任务卡片 ${i + 1}`, '/practice', `.practice-task:not(.practice-task--locked) >> nth=${i}`));
  flows.push(await flow(ctx, '剑雅听力目录→做题', '/listening/tests', 'a[href^="/listening/test/"]', { scroll: 1400 }));
  flows.push(await flow(ctx, '剑雅阅读目录→做题', '/reading/tests', 'a[href^="/reading/test/"]', { scroll: 900 }));
  flows.push(await flow(ctx, '听力机经目录→做题', '/listening/jijing', 'a[href^="/listening/jijing/"]', { scroll: 600 }));
  flows.push(await flow(ctx, '阅读机经目录→做题', '/reading/jijing', 'a[href^="/reading/jijing/"]', { scroll: 600 }));
  flows.push(await flow(ctx, '精听目录→精听', '/practices', 'a[href^="/listening/ielts"]', { scroll: 800 }));
  flows.push(await flow(ctx, '写作题库→范文', '/writing/', 'a[href^="/writing/t"]'));
  flows.push(await flow(ctx, '母题库→母题', '/writing/topics', 'a[href^="/writing/topics/"]'));
  flows.push(await flow(ctx, '阅读冲刺→做题', '/practice/sprint/reading', 'a[href^="/practice/sprint/reading/"], a[href^="/reading/"]'));
  flows.push(await flow(ctx, '练习中心→剑雅听力', '/practice', 'a[href="/listening/tests"]'));
  flows.push(await flow(ctx, '练习中心→题型专项', '/practice', 'a[href^="/practice/question-types"]'));
  flows.push(await flow(ctx, '练习中心→写作', '/practice', 'a[href^="/writing"]'));
  fs.writeFileSync(OUT + '/flows.json', JSON.stringify({ cards, flows }, null, 1));
  for (const f of flows) console.log(JSON.stringify(f));
  await browser.close();
})();
