// Real Chromium + real Flask + disposable synthetic identities. No production.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const port = process.argv[2] || '5113';
const BASE = 'http://127.0.0.1:' + port;
const OUT = path.join(__dirname, 'screenshots');
fs.mkdirSync(OUT, { recursive: true });
const results = [];
let browser;
async function check(name, run) {
  if (process.argv[3] && !name.includes(process.argv[3])) return;
  try { const evidence = await run(); results.push({ name, ok: true, evidence }); }
  catch (e) { results.push({ name, ok: false, error: e.message }); }
}
async function context(width = 1440, blockCDN = false) {
  const c = await browser.newContext({ viewport: { width, height: 900 } });
  if (blockCDN) await c.route('**/*', route => {
    const u = new URL(route.request().url());
    return u.origin === BASE ? route.continue() : route.abort();
  });
  return c;
}
async function verify(p) {
  await p.goto(BASE + '/practice', { waitUntil: 'networkidle' });
  await p.fill('#practiceStudentName', '测试学生');
  await p.click('#practiceIdentitySubmit');
  await p.locator('#practiceIdentitySwitch').waitFor({ state: 'visible' });
  await p.locator('.practice-task:not(.practice-task--locked)').first().waitFor();
}
async function centerState(p) {
  return p.evaluate(() => ({
    formVisible: document.querySelector('#practiceIdentityForm').getBoundingClientRect().height > 0,
    formDisplay: getComputedStyle(document.querySelector('#practiceIdentityForm')).display,
    staffFilters: document.querySelectorAll('.practice-suite-filters').length,
    preview: document.querySelectorAll('.practice-suite-preview').length,
    selfBack: [...document.querySelectorAll('a')].filter(a => a.textContent.includes('返回练习中心') && a.getAttribute('href') === '/practice').length,
    identity: window.PRACTICE_NAVIGATION_DEFAULTS.identityMode,
    overflow: document.documentElement.scrollWidth - innerWidth
  }));
}
(async () => {
  browser = await chromium.launch({ executablePath: process.env.AUDIT_CHROMIUM || undefined });
  for (const width of [1440, 1280, 1024, 390]) await check('student center ' + width + ' / blocked external CDN', async () => {
    const c = await context(width, true); const p = await c.newPage();
    try {
      await verify(p); const state = await centerState(p);
      await p.screenshot({ path: path.join(OUT, `student-${width}.png`), fullPage: true });
      assert.equal(state.formVisible, false); assert.equal(state.formDisplay, 'none');
      assert.equal(state.staffFilters, 0); assert.equal(state.preview, 0);
      assert.equal(state.selfBack, 0); assert.equal(state.identity, 'verified_student');
      assert.equal(state.overflow, 0);
      return state;
    } finally { await c.close(); }
  });
  await check('identity updates actual navigation without reload', async () => {
    const c = await context(); const p = await c.newPage();
    try {
      await verify(p);
      await p.locator('a[href*="/listening/tests"]').first().click();
      await p.waitForURL(u => u.pathname === '/listening/tests');
      assert.equal(new URL(p.url()).searchParams.get('practice_identity'), 'verified_student');
      await p.goto(BASE + '/practice', { waitUntil: 'networkidle' });
      await p.click('#practiceIdentitySwitch');
      await p.locator('#practiceIdentityForm').waitFor({ state: 'visible' });
      assert.equal(await p.evaluate(() => window.PRACTICE_NAVIGATION_DEFAULTS.identityMode), 'guest');
      await p.locator('a[href*="/listening/tests"]').first().click();
      // Existing identity gate intentionally blocks unverified catalog entry.
      assert.equal(new URL(p.url()).pathname, '/practice');
      assert.match(await p.locator('#practiceIdentityError').textContent(), /先输入学生姓名/);
      await p.fill('#practiceStudentName', '测试学生');
      await p.click('#practiceIdentitySubmit');
      await p.locator('#practiceIdentitySwitch').waitFor({ state: 'visible' });
      await p.locator('a[href*="/listening/tests"]').first().click();
      await p.waitForURL(u => u.pathname === '/listening/tests');
      assert.equal(new URL(p.url()).searchParams.get('practice_identity'), 'verified_student');
      return 'verified_student link → guest blocked by existing identity gate → reverified link';
    } finally { await c.close(); }
  });
  await check('three untouched tasks return without confirmation', async () => {
    const c = await context(); const p = await c.newPage();
    try {
      await verify(p);
      const cards = await p.locator('.practice-task:not(.practice-task--locked)').count();
      assert.equal(cards, 3); const states = [];
      for (let i = 0; i < cards; i++) {
        await p.goto(BASE + '/practice', { waitUntil: 'networkidle' });
        await p.locator('.practice-task:not(.practice-task--locked)').nth(i).click();
        await p.waitForLoadState('networkidle');
        const from = new URL(p.url()).pathname;
        const save = await p.locator('[data-practice-save-status]').textContent();
        assert.doesNotMatch(save, /^已保存/);
        await p.locator('[data-practice-back]:visible').first().click();
        await p.waitForURL(u => u.pathname === '/practice', { timeout: 5000 });
        states.push({ from, save, returned: new URL(p.url()).pathname });
      }
      return states;
    } finally { await c.close(); }
  });
  await check('bookmark task fallback goes to task section', async () => {
    const c = await context(); const p = await c.newPage();
    try {
      await verify(p);
      const href = await p.locator('.practice-task[href^="/reading/test/"]').getAttribute('href');
      await p.evaluate(() => sessionStorage.clear());
      await p.goto(BASE + href, { waitUntil: 'networkidle' });
      const label = await p.locator('[data-practice-back]:visible').first().textContent();
      assert.doesNotMatch(label, /任务详情/);
      await p.locator('[data-practice-back]:visible').first().click();
      await p.waitForURL(u => u.pathname === '/practice' && u.hash === '#practiceAssignedTasks');
      return label;
    } finally { await c.close(); }
  });
  await check('no analysis stays hidden, stale direct link redirects', async () => {
    const c = await context(); const p = await c.newPage();
    try {
      await p.goto(BASE + '/reading/test/ielts21_test1_reading', { waitUntil: 'networkidle' });
      assert.equal(await p.locator('#readingStudyMode').isVisible(), false);
      const response = await c.request.get(BASE + '/reading/study/ielts21_test1_reading', { maxRedirects: 0 });
      assert.equal(response.status(), 302);
      assert.equal(response.headers().location, '/reading/test/ielts21_test1_reading');
      await p.goto(BASE + '/reading/study/ielts21_test1_reading', { waitUntil: 'networkidle' });
      assert.equal(new URL(p.url()).pathname, '/reading/test/ielts21_test1_reading');
      return { visible: false, direct: 302, destination: new URL(p.url()).pathname };
    } finally { await c.close(); }
  });
  await check('teacher keeps styled suite and working subject selection', async () => {
    const c = await context(); const p = await c.newPage();
    try {
      await c.request.post(BASE + '/login', { form: { username: 'audit_teacher', password: 'audit-fixture-only', next: '/practice' } });
      await p.goto(BASE + '/practice', { waitUntil: 'networkidle' });
      assert.equal(await p.locator('.practice-suite-filters').isVisible(), true);
      assert.equal(await p.locator('.practice-suite-preview').isVisible(), true);
      assert.equal(await p.locator('.practice-suite-filters input[type=checkbox]').count(), 0);
      await p.locator('[data-practice-target-index="1"]').click();
      assert.match(await p.locator('.practice-suite-preview h3').textContent(), /阅读/);
      assert.equal(await p.locator('a:has-text("布置给学生")').getAttribute('href'), '/tasks');
      await p.screenshot({ path: path.join(OUT, 'teacher-1440.png'), fullPage: true });
      return { suite: true, deadCheckboxes: 0, subject: '阅读', assignment: '/tasks' };
    } finally { await c.close(); }
  });
  await browser.close();
  fs.writeFileSync(path.join(__dirname, process.argv[3] ? 'validation/acceptance-recheck.json' : 'validation/acceptance.json'), JSON.stringify(results, null, 2) + '\n');
  console.log(JSON.stringify(results, null, 2));
  process.exitCode = results.every(r => r.ok) ? 0 : 1;
})().catch(async e => { console.error(e); if (browser) await browser.close(); process.exitCode = 1; });
