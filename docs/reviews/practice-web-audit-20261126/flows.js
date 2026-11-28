// Run only against boot.py/serve_fixture.py synthetic local data, never production.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const BASE = (process.env.AUDIT_BASE || process.env.BASE || 'http://127.0.0.1:5055').replace(/\/$/, '');
const OUT = process.env.AUDIT_OUT || process.env.OUT || path.join(__dirname, 'out');
assert(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(BASE).hostname), 'Synthetic audit requires a loopback URL');
const rel = (value) => {
  const url = new URL(value, BASE);
  for (const key of [...url.searchParams.keys()]) {
    if (/token|csrf|session|password/i.test(key)) url.searchParams.set(key, 'REDACTED_SYNTHETIC');
    else if (/return|exit/.test(key) && url.searchParams.get(key).startsWith('/')) {
      url.searchParams.set(key, rel(url.searchParams.get(key)));
    }
  }
  return url.pathname + url.search + url.hash;
};
const pathname = (value) => new URL(value, BASE).pathname;
const results = [];
async function check(name, run) {
  const row = { name };
  try { await run(row); row.ok = true; }
  catch (error) { row.ok = false; row.error = error.message.split('\n')[0].replace(/([?&]token=)[^&\s)]+/g, '$1REDACTED_SYNTHETIC'); }
  results.push(row); console.log(JSON.stringify(row));
}
async function context(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  ctx.setDefaultTimeout(10000);
  // Match the original offline audit: external CDN/audio quality is not acceptance evidence.
  await ctx.route('**/*', (route) => new URL(route.request().url()).origin === new URL(BASE).origin ? route.continue() : route.abort());
  return ctx;
}
async function verify(page) {
  await page.goto(BASE + '/practice', { waitUntil: 'networkidle' });
  await page.fill('#practiceStudentName', '测试学生');
  await page.click('#practiceIdentitySubmit');
  await page.waitForFunction(() => document.querySelector('#practiceIdentityForm').hidden);
  assert.match(await page.locator('[data-practice-identity-label]').innerText(), /测试学生/);
  await page.locator('#practiceCurrentGroups .practice-task').first().waitFor({ state: 'visible' });
}
async function backButtons(page) {
  return page.locator('[data-practice-back]:visible, [data-practice-module-back]:visible, .practice-shell__back:visible').allTextContents();
}
async function flow(ctx, name, startPath, clickSel, opts = {}) {
  await check(name, async (row) => {
    const page = await ctx.newPage();
    const dialogs = [];
    page.on('dialog', async (dialog) => { dialogs.push(dialog.type()); await dialog.accept(); });
    async function prepare() {
      if (opts.openTest) {
        const test = page.locator('details[data-test-id]:visible').first();
        if (!await test.evaluate((element) => element.open)) await test.locator('summary').click();
      }
    }
    try {
      row.start = startPath;
      await page.goto(BASE + startPath, { waitUntil: 'networkidle' });
      await prepare();
      if (opts.scroll) await page.evaluate((y) => window.scrollTo(0, y), opts.scroll);
      const target = page.locator(clickSel).first();
      row.clickText = (await target.innerText()).trim().replace(/\s+/g, ' ').slice(0, 60);
      const expectedLanding = pathname(await target.getAttribute('href'));
      await target.click();
      await page.waitForURL((url) => url.pathname === expectedLanding);
      await page.waitForLoadState('networkidle');
      row.landed = rel(page.url());
      row.backButtons = (await backButtons(page)).map((text) => text.trim());
      const back = page.locator(opts.backSel || '[data-practice-back]:visible, [data-practice-module-back]:visible, .practice-shell__back:visible').first();
      row.backLabel = (await back.innerText()).trim();
      assert.match(row.backLabel, opts.label || /返回/);
      await back.click();
      await page.waitForURL((url) => url.pathname === pathname(startPath));
      await page.waitForLoadState('networkidle');
      row.afterBack = rel(page.url());
      assert.equal(pathname(page.url()), pathname(startPath));
      // Repeat the original browser-back check without swallowing navigation failures.
      await page.goto(BASE + startPath, { waitUntil: 'networkidle' });
      await prepare();
      await page.locator(clickSel).first().click();
      await page.waitForURL((url) => url.pathname === expectedLanding);
      await page.waitForLoadState('networkidle');
      await page.goBack({ waitUntil: 'networkidle' });
      await page.waitForURL((url) => url.pathname === pathname(startPath));
      await page.waitForLoadState('networkidle');
      row.afterBrowserBack = rel(page.url());
      assert.equal(pathname(page.url()), pathname(startPath));
      row.dialogs = dialogs;
      assert.deepEqual(dialogs, [], 'Untouched practice must not prompt to exit');
    } finally { await page.close(); }
  });
}
async function catalog(ctx, route, title, width = 1440) {
  await check(`目录 ${route} @${width}`, async (row) => {
    const page = await ctx.newPage();
    try {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
      await page.goto(BASE + route, { waitUntil: 'networkidle' });
      const header = page.locator('[data-practice-workspace-header]');
      assert.equal(await header.count(), 1);
      const brand = header.locator('[data-practice-home]');
      assert.equal(await brand.count(), 1);
      assert.match(await brand.innerText(), /Sage Path/);
      assert.equal(await brand.getAttribute('data-practice-module-back'), null);
      assert.equal(await brand.locator('img').count(), 1);
      assert.equal(await header.locator('.practice-workspace__subjects [data-practice-nav]').count(), 5);
      assert.equal(await header.locator('[data-practice-module-back]').count(), route === '/practice' ? 0 : 1);
      assert.equal(await header.locator('[data-practice-module-exit]').count(), 1);
      row.title = await page.title();
      assert.match(row.title, / · Sage Path$/);
      const headings = page.locator('h1');
      assert.equal(await headings.count(), 1);
      row.heading = (await headings.innerText()).trim();
      if (title) assert.equal(row.heading, title);
      row.backLabel = route === '/practice' ? null : (await header.locator('[data-practice-module-back]').innerText()).trim();
      if (row.backLabel) assert.match(row.backLabel, /返回练习中心/);
      row.backTarget = route === '/practice' ? null : rel(await header.locator('[data-practice-module-back]').getAttribute('href'));
      if (row.backTarget) assert.equal(pathname(row.backTarget), '/practice');
      row.identity = (await header.locator('[data-practice-identity-label]').innerText()).trim();
      assert.match(row.identity, /测试学生/);
      row.horizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
      assert.equal(row.horizontalOverflow, false);
      if (process.env.AUDIT_SCREENSHOTS === '1') await page.screenshot({ path: path.join(OUT, `${route.replace(/\W+/g, '-')}-${width}.png`), fullPage: false });
    } finally { await page.close(); }
  });
}
(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch(process.env.AUDIT_CHROMIUM ? { executablePath: process.env.AUDIT_CHROMIUM } : {});
  try {
    const ctx = await context(browser);
    const page = await ctx.newPage();
    await check('确认学生身份', async () => { await verify(page); });
    const cards = await page.locator('.practice-task:not(.practice-task--locked):visible').count();
    await check('合成任务数', async () => { assert.equal(cards, 3); });
    await page.close();
    for (let i = 0; i < cards; i++) await flow(ctx, `任务卡片 ${i + 1}`, '/practice', `.practice-task:not(.practice-task--locked):visible >> nth=${i}`, { label: /返回练习中心/ });
    const cases = [
      ['剑雅听力目录→做题', '/listening/tests', 'a[href^="/listening/test/"]:visible', { label: /返回剑雅听力/, openTest: true }],
      ['剑雅阅读目录→做题', '/reading/tests', 'a[href^="/reading/test/"]:visible', { label: /返回剑雅阅读/ }],
      ['听力机经目录→做题', '/listening/jijing', 'a[href^="/listening/jijing/"]:visible', { label: /返回听力机经/ }],
      ['阅读机经目录→做题', '/reading/jijing', 'a[href^="/reading/jijing/"]:visible', { label: /返回阅读机经/ }],
      ['精听目录→精听', '/practices', '#mainContent a[href^="/listening/ielts"]:visible', { label: /返回精听列表/ }],
      ['写作题库→范文', '/writing/', '.writing-card__link:visible', { label: /返回写作题库/ }],
      ['母题库→母题', '/writing/topics', 'a[href^="/writing/topics/"]:visible', { backSel: '.writing-back-link:visible', label: /返回.*母题/ }],
      ['阅读冲刺→做题', '/practice/sprint/reading', '.exam-sprint__start:visible', { label: /返回.*冲刺/ }],
      ['练习中心→剑雅听力', '/practice', '.practice-subjects a[href="/listening/tests"]:visible', { label: /返回练习中心/ }],
      ['练习中心→题型专项', '/practice', 'a[href^="/practice/question-types"]:visible', { label: /返回练习中心/ }],
      ['练习中心→写作', '/practice', '.practice-subjects a[href^="/writing"]:visible', { label: /返回练习中心/ }],
      ['阅读冲刺→剑雅目录', '/practice/sprint/reading', '.practice-workspace__source-nav a[href="/reading/tests"]:visible', { label: /返回.*冲刺/ }],
      ['听力冲刺→剑雅目录', '/practice/sprint/listening', '.practice-workspace__source-nav a[href="/listening/tests"]:visible', { label: /返回.*冲刺/ }],
    ];
    for (const args of cases) await flow(ctx, ...args);
    await check('冲刺→阅读目录→做题→目录→冲刺', async (row) => {
      const p = await ctx.newPage();
      try {
        await p.goto(BASE + '/practice/sprint/reading', { waitUntil: 'networkidle' });
        await p.locator('.practice-workspace__subjects a[href="/reading/tests"]').click();
        await p.waitForURL((url) => url.pathname === '/reading/tests');
        await p.locator('a[href^="/reading/test/"]:visible').first().click();
        await p.waitForURL((url) => url.pathname.startsWith('/reading/test/'));
        await p.locator('[data-practice-back]:visible, .practice-shell__back:visible').first().click();
        await p.waitForURL((url) => url.pathname === '/reading/tests');
        const back = p.locator('[data-practice-module-back]');
        row.catalogBackLabel = (await back.innerText()).trim();
        assert.match(row.catalogBackLabel, /返回考前冲刺/);
        await back.click();
        await p.waitForURL((url) => url.pathname === '/practice/sprint/reading');
        row.afterBack = rel(p.url());
      } finally { await p.close(); }
    });
    await check('听力→阅读→听力重访无返回循环', async (row) => {
      const p = await ctx.newPage();
      try {
        await p.goto(BASE + '/listening/tests', { waitUntil: 'networkidle' });
        await p.locator('.practice-workspace__subjects a[href="/reading/tests"]').click();
        await p.waitForURL((url) => url.pathname === '/reading/tests');
        await p.locator('.practice-workspace__subjects a[href="/listening/tests"]').click();
        await p.waitForURL((url) => url.pathname === '/listening/tests');
        await p.locator('[data-practice-module-back]').click();
        await p.waitForURL((url) => url.pathname === '/practice');
        row.afterBack = rel(p.url());
      } finally { await p.close(); }
    });
    const catalogs = [['/practice', '练习中心'], ['/practices', '精听练习'], ['/listening/tests', '剑雅听力'], ['/reading/tests', '剑雅阅读'], ['/listening/jijing', '听力机经'], ['/reading/jijing', '阅读机经'], ['/writing/'], ['/writing/topics'], ['/practice/sprint/reading', '阅读考前冲刺'], ['/practice/sprint/listening', '听力考前冲刺'], ['/practice/question-types']];
    for (const [route, title] of catalogs) for (const width of [1440, 390]) await catalog(ctx, route, title, width);
    await check('精听保留切换身份且无重复任务请求', async (row) => {
      const p = await ctx.newPage(); const requests = [];
      p.on('request', (request) => requests.push(pathname(request.url())));
      try {
        await p.goto(BASE + '/practices', { waitUntil: 'networkidle' });
        await p.locator('#practiceIntensiveIdentitySwitch').click();
        await p.locator('#studentName').waitFor({ state: 'visible' });
        await p.fill('#studentName', '测试学生'); await p.click('#btnVerify');
        await p.locator('#mainContent').waitFor({ state: 'visible' });
        assert.match(await p.locator('[data-practice-identity-label]').innerText(), /测试学生/);
        row.duplicateRequests = requests.filter((url) => /^\/api\/practice\/(tasks|history)(\/|$)/.test(url));
        assert.deepEqual(row.duplicateRequests, []);
        assert.equal(await p.locator('#practiceAssignedTasks, #practiceTaskList, #practiceHistoryList').count(), 0);
      } finally { await p.close(); }
    });
    // Teacher login only exists in the batch1 disposable fixture, never use real accounts.
    if (process.env.AUDIT_TEACHER === '1') await check('教师后台和精听管理入口保留', async (row) => {
      const staff = await context(browser); const p = await staff.newPage();
      try {
        await p.goto(BASE + '/login?next=/practice', { waitUntil: 'networkidle' });
        await p.fill('#username', 'audit_teacher'); await p.fill('#password', 'audit-fixture-only');
        await p.locator('button[type="submit"]').click();
        await p.waitForURL((url) => url.pathname === '/practice');
        assert.equal(await p.locator('body.admin-suite-v2').count(), 1);
        assert.equal(await p.locator('.practice-suite-filters').count(), 1);
        assert.equal(await p.locator('.practice-suite-preview').count(), 1);
        await p.goto(BASE + '/practices', { waitUntil: 'networkidle' });
        assert.equal(await p.locator('a[href="/listening/upload"]:visible').count(), 1);
        assert.match(await p.locator('[data-practice-identity-label]').innerText(), /教师/);
        assert.equal(await p.locator('a[href="/logout"]').count(), 1);
        row.staffControls = { upload: true, logout: true, assignmentPreview: true };
      } finally { await staff.close(); }
    });
    await ctx.close();
  } finally {
    await browser.close();
    const failed = results.filter((row) => !row.ok);
    fs.writeFileSync(path.join(OUT, 'flows.json'), JSON.stringify({ base: BASE, scope: 'synthetic local Chromium; external requests blocked', results, passed: results.length - failed.length, failed: failed.length }, null, 2) + '\n');
    if (failed.length) process.exitCode = 1;
  }
})().catch((error) => { console.error(error.message.split('\n')[0]); process.exitCode = 1; });
