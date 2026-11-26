const { chromium } = require('playwright');
const BASE = 'http://127.0.0.1:5055';
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(BASE + '/practice', { waitUntil: 'networkidle' });
  await p.fill('#practiceStudentName', '测试学生'); await p.click('#practiceIdentitySubmit'); await p.waitForTimeout(1200);
  const r = await p.evaluate(() => {
    const f = document.getElementById('practiceIdentityForm');
    const vis = (e) => !!e && e.getBoundingClientRect().height > 0;
    const out = { formHiddenAttr: f.hidden, formVisible: vis(f), formDisplay: getComputedStyle(f).display };
    out.filters = [...document.querySelectorAll('.practice-suite-filters input, .practice-suite-filters button')].map((e) => ({ tag: e.tagName, text: (e.innerText || e.parentElement.innerText || '').trim().slice(0, 12), visible: vis(e) }));
    out.assignBtn = [...document.querySelectorAll('a,button')].filter((e) => /布置给学生|进入练习/.test(e.innerText) && vis(e)).map((e) => ({ text: e.innerText.trim(), href: e.getAttribute('href'), cls: e.className }));
    out.previewSection = (() => { const n = [...document.querySelectorAll('section,aside,div')].find((e) => /^练习预览/.test((e.innerText || '').trim()) && e.children.length < 12); return n ? { tag: n.tagName, cls: n.className, id: n.id } : null; })();
    out.selfBack = [...document.querySelectorAll('a')].filter((a) => /返回练习中心/.test(a.innerText) && vis(a)).map((a) => a.getAttribute('href'));
    return out;
  });
  console.log(JSON.stringify(r, null, 1));
  // click each filter control; detect any DOM change
  const results = [];
  const n = await p.locator('.practice-suite-filters input, .practice-suite-filters button').count();
  for (let i = 0; i < n; i++) {
    const el = p.locator('.practice-suite-filters input, .practice-suite-filters button').nth(i);
    if (!(await el.isVisible())) continue;
    const before = await p.evaluate(() => { window.__m = 0; window.__o && window.__o.disconnect(); window.__o = new MutationObserver((ms) => { window.__m += ms.filter((m) => !m.target.closest || !m.target.closest('.practice-suite-filters')).length; }); window.__o.observe(document.body, { subtree: true, childList: true, attributes: true }); return { y: scrollY, url: location.href }; });
    await el.click().catch(() => {}); await p.waitForTimeout(500);
    const after = await p.evaluate(() => ({ y: scrollY, url: location.href, m: window.__m }));
    results.push({ i, label: (await el.evaluate((e) => (e.innerText || e.parentElement.innerText || '').trim().slice(0, 14))), scrolled: after.y !== before.y, urlChanged: after.url !== before.url, outsideMutations: after.m });
    await p.evaluate(() => window.scrollTo(0, 0));
  }
  console.log('FILTER CLICKS', JSON.stringify(results));
  // preview panel buttons
  const pv = await p.locator('a:has-text("布置给学生"), button:has-text("布置给学生")').first();
  if (await pv.count()) { const href = await pv.getAttribute('href'); console.log('ASSIGN href', href); }
  await b.close();
})();
