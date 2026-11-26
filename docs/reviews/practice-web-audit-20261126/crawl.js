const { chromium } = require('playwright');
const fs = require('fs');
const BASE = 'http://127.0.0.1:5055';
const OUT = __dirname + '/out';
fs.mkdirSync(OUT + '/shots', { recursive: true });
const HUBS = ['/practice', '/practices', '/listening/tests', '/reading/tests', '/listening/jijing', '/reading/jijing', '/writing/', '/writing/topics', '/practice/question-types', '/practice/sprint/listening', '/practice/sprint/reading', '/exams', '/student/today', '/classroom'];
const DETAIL_PATTERNS = [/^\/listening\/test\/[^/?]+/, /^\/reading\/test\/[^/?]+/, /^\/listening\/jijing\/[^/?]+/, /^\/reading\/jijing\/[^/?]+/, /^\/listening\/(?!tests|test\/|jijing|upload)[^/?]+$/, /^\/writing\/(?!topics)[^/?]+$/, /^\/writing\/topics\/[^/?]+/, /^\/practice\/sprint\/reading\/[^/?]+/, /^\/reading\/study\/[^/?]+/, /^\/practice\/question-types\/.+/];
const slug = (p) => p.replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, '') || 'root';

async function inspect(ctx, path, tag) {
  const page = await ctx.newPage();
  const errs = [], fails = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + e.message.slice(0, 200)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 200)); });
  page.on('response', (r) => { if (r.status() >= 400 && r.url().startsWith(BASE)) fails.push(r.status() + ' ' + r.request().method() + ' ' + r.url().replace(BASE, '')); });
  let status = null;
  try { const resp = await page.goto(BASE + path, { waitUntil: 'networkidle', timeout: 20000 }); status = resp && resp.status(); } catch (e) { errs.push('goto: ' + e.message.slice(0, 120)); }
  await page.waitForTimeout(400);
  const info = await page.evaluate(() => {
    const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
    const links = [...document.querySelectorAll('a[href]')].map((a) => ({ href: a.getAttribute('href'), text: (a.innerText || a.getAttribute('aria-label') || '').trim().slice(0, 40), vis: vis(a) }));
    const deadAnchors = [...document.querySelectorAll('a')].filter((a) => vis(a) && (!a.getAttribute('href') || a.getAttribute('href') === '#' || /^javascript:/i.test(a.getAttribute('href') || '')) && !a.hasAttribute('aria-disabled')).map((a) => (a.innerText || '').trim().slice(0, 30));
    const buttons = [...document.querySelectorAll('button, [role=button], [data-href]')].filter(vis).map((b) => (b.innerText || b.getAttribute('aria-label') || b.title || '').trim().slice(0, 30));
    const overflow = document.documentElement.scrollWidth - window.innerWidth;
    const fonts = [...new Set([...document.querySelectorAll('h1,h2,h3,body,button')].map((e) => getComputedStyle(e).fontFamily.split(',')[0]))].slice(0, 6);
    const back = [...document.querySelectorAll('[data-practice-back], .practice-shell__back, a')].filter((e) => vis(e) && /返回|退出/.test(e.innerText || '')).map((e) => ({ text: e.innerText.trim().slice(0, 30), href: e.getAttribute('href') }));
    return { title: document.title, h1: (document.querySelector('h1') || {}).innerText || '', links, deadAnchors, buttons, overflow, fonts, back, url: location.pathname + location.search };
  });
  await page.screenshot({ path: `${OUT}/shots/${tag}-${slug(path)}.png`, fullPage: false });
  await page.close();
  return { path, status, errs, fails, ...info };
}

(async () => {
  const browser = await chromium.launch();
  const report = { pages: [], details: [], linkcheck: {}, flows: [], deadclicks: [] };
  // ---- anonymous + verified contexts
  const anon = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const student = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const sp = await student.newPage();
  await sp.goto(BASE + '/practice', { waitUntil: 'networkidle' });
  await sp.fill('#practiceStudentName', '测试学生');
  await sp.click('#practiceIdentitySubmit');
  await sp.waitForTimeout(1500);
  await sp.screenshot({ path: `${OUT}/shots/verified-practice.png`, fullPage: true });
  report.verifiedList = await sp.evaluate(() => [...document.querySelectorAll('.practice-task')].map((a) => ({ href: a.getAttribute('href'), title: a.innerText.replace(/\s+/g, ' ').trim().slice(0, 80), locked: a.classList.contains('practice-task--locked') })));
  await sp.close();
  for (const p of HUBS) { report.pages.push({ who: 'anon', ...(await inspect(anon, p, 'anon')) }); report.pages.push({ who: 'student', ...(await inspect(student, p, 'student')) }); }
  // ---- pick one detail page per pattern from hub links
  const hrefs = new Set();
  report.pages.forEach((p) => (p.links || []).forEach((l) => { if (l.href && l.href.startsWith('/')) hrefs.add(l.href.split('#')[0]); }));
  const chosen = [];
  for (const re of DETAIL_PATTERNS) { const h = [...hrefs].find((x) => re.test(x.split('?')[0])); if (h) chosen.push(h); }
  (report.verifiedList || []).forEach((t) => { if (t.href && t.href.startsWith('/')) chosen.push(t.href); });
  for (const p of [...new Set(chosen)]) report.details.push(await inspect(student, p, 'detail'));
  report.details.forEach((p) => (p.links || []).forEach((l) => { if (l.href && l.href.startsWith('/')) hrefs.add(l.href.split('#')[0]); }));
  // ---- link check (GET, no JS)
  const req = student.request;
  for (const h of [...hrefs].slice(0, 500)) { try { const r = await req.get(BASE + h, { maxRedirects: 0, timeout: 15000 }); report.linkcheck[h] = r.status(); } catch (e) { report.linkcheck[h] = 'ERR ' + e.message.slice(0, 60); } }
  // ---- mobile screenshots of hubs
  const mob = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, storageState: await student.storageState() });
  for (const p of ['/practice', '/listening/tests', '/reading/tests', '/practices', '/writing/', '/practice/question-types']) {
    const pg = await mob.newPage(); await pg.goto(BASE + p, { waitUntil: 'networkidle' }).catch(() => {}); await pg.waitForTimeout(400);
    const ov = await pg.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    report.pages.push({ who: 'mobile', path: p, overflow: ov });
    await pg.screenshot({ path: `${OUT}/shots/mobile-${slug(p)}.png`, fullPage: true }); await pg.close();
  }
  fs.writeFileSync(OUT + '/report.json', JSON.stringify(report, null, 1));
  await browser.close();
  console.log('done', report.pages.length, report.details.length, Object.keys(report.linkcheck).length);
})();
