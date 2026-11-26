const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:5055';
(async () => {
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await p.goto(BASE + '/practice', { waitUntil: 'networkidle' });
  await p.fill('#practiceStudentName', '测试学生'); await p.click('#practiceIdentitySubmit'); await p.waitForTimeout(1200);
  const url0 = p.url();
  await p.evaluate(() => { window.__m = 0; new MutationObserver((ms) => { window.__m += ms.length; }).observe(document.body, { subtree: true, childList: true, attributes: true }); });
  await p.locator('[data-practice-open-selected]').click(); await p.waitForTimeout(1500);
  console.log('进入练习 -> url changed:', p.url() !== url0, 'mutations:', await p.evaluate(() => window.__m), p.url().replace(BASE, ''));
  await p.goto(BASE + '/practice', { waitUntil: 'networkidle' }); await p.waitForTimeout(800);
  await Promise.all([p.waitForLoadState('networkidle'), p.locator('a:has-text("布置给学生")').click()]); await p.waitForTimeout(800);
  console.log('布置给学生 ->', p.url().replace(BASE, ''), await p.title());
  await p.goto(BASE + '/practice', { waitUntil: 'networkidle' }); await p.waitForTimeout(800);
  const sw = p.locator('.practice-exam-switch a').first(); console.log('考试切换:', await sw.getAttribute('href'));
  await b.close();
})();
