/* Offline real-template browser audit; no request may leave this route handler. */
const fs = require('fs');
const path = require('path');
const { chromium } = require('/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const report = __dirname;
const repo = path.resolve(report, '../../..');
const vendor = path.join(repo, 'docs/reviews/admin-sidebar-logo-20261122/vendor');
const types = { '.css': 'text/css', '.html': 'text/html', '.png': 'image/png', '.js': 'application/javascript', '.woff2': 'font/woff2' };
const readMetrics = () => ({
  viewport: innerWidth,
  documentWidth: document.documentElement.scrollWidth,
  horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 1,
  visibleOverflow: [...document.querySelectorAll('.panel-content *')].filter(el => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && (r.right > innerWidth + 1 || r.left < -1);
  }).slice(0, 12).map(el => ({ tag: el.tagName, name: el.getAttribute('name'), class: el.className, right: el.getBoundingClientRect().right })),
});

(async () => {
  const browser = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
  const result = { browser: await browser.version(), scope: JSON.parse(fs.readFileSync(path.join(report, 'mock-visual-fixture.json'))).scope, cases: [] };
  fs.mkdirSync(path.join(report, 'screenshots'), { recursive: true });
  try {
    for (const width of [1440, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, deviceScaleFactor: 1, reducedMotion: 'reduce' });
      const page = await context.newPage();
      const errors = [], missing = [], blocked = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        let filename;
        if (url.hostname === 'sprint-qa.invalid' && url.pathname === '/admin/mock-exams/create') filename = path.join(report, 'mock-form-fixture.html');
        else if (url.hostname === 'sprint-qa.invalid' && url.pathname.startsWith('/static/')) {
          filename = path.resolve(repo, '.' + url.pathname);
          if (!filename.startsWith(path.join(repo, 'static') + path.sep)) { blocked.push(url.pathname); return route.abort(); }
        } else if (url.hostname === 'cdn.jsdelivr.net' && url.pathname.endsWith('/bootstrap.min.css')) filename = path.join(vendor, 'bootstrap.min.css');
        else if (url.hostname === 'cdnjs.cloudflare.com' && url.pathname.endsWith('/all.min.css')) filename = path.join(vendor, 'fontawesome.min.css');
        else if (url.hostname === 'cdnjs.cloudflare.com' && url.pathname.endsWith('.woff2')) filename = path.join(vendor, path.basename(url.pathname));
        else if (url.hostname === 'cdn.jsdelivr.net' && /\/(jquery\.slim\.min|popper\.min|bootstrap\.min)\.js$/.test(url.pathname)) return route.fulfill({ contentType: 'application/javascript', body: '' });
        else { blocked.push(url.origin + url.pathname); return route.abort(); }
        if (!fs.existsSync(filename)) { missing.push(url.pathname); return route.fulfill({ status: 404, body: '' }); }
        return route.fulfill({ body: fs.readFileSync(filename), contentType: types[path.extname(filename)] || 'application/octet-stream' });
      });
      await page.goto('http://sprint-qa.invalid/admin/mock-exams/create');
      await page.evaluate(() => document.fonts.ready);
      const initial = await page.evaluate(() => ({
        sprintPanelsHidden: [...document.querySelectorAll('[data-sprint-parts]')].every(el => el.hidden),
        sprintInputsDisabled: [...document.querySelectorAll('[data-sprint-part]')].every(el => el.disabled),
        existingEnabled: [...document.querySelectorAll('[data-existing-paper] select')].every(el => !el.disabled),
      }));
      for (const subject of ['listening', 'reading']) await page.locator(`#${subject}Source`).selectOption('sprint');
      const visibleSelectors = await page.locator('[data-sprint-part]:visible').count();
      for (const subject of ['listening', 'reading']) {
        await page.locator(`[data-sprint-picker]:has(#${subject}Source) [data-sprint-suggest]`).click();
      }
      const sprint = await page.evaluate(() => {
        const form = document.querySelector('form');
        const data = new FormData(form);
        return {
          statuses: [...document.querySelectorAll('[data-sprint-total]')].map(el => el.textContent),
          counts: [...document.querySelectorAll('[data-sprint-picker]')].map(el => [...el.querySelectorAll('[data-sprint-part]')].reduce((sum, select) => sum + Number(select.selectedOptions[0]?.dataset.count || 0), 0)),
          selectedCount: [...document.querySelectorAll('[data-sprint-part]')].filter(el => !!el.value).length,
          existingHiddenDisabled: [...document.querySelectorAll('[data-existing-paper]')].every(el => el.hidden && el.querySelector('select').disabled),
          validity: [...document.querySelectorAll('[data-sprint-part]')].every(el => el.checkValidity()),
          submittedPartCounts: [data.getAll('listening_sprint_part').length, data.getAll('reading_sprint_part').length],
          noOldPaperFields: !data.has('listening_test_id') && !data.has('reading_test_id'),
        };
      });
      const sprintMetrics = await page.evaluate(readMetrics);
      await page.screenshot({ path: path.join(report, 'screenshots', `mock-sprint-${width}.png`), fullPage: true });
      for (const subject of ['listening', 'reading']) await page.locator(`#${subject}Source`).selectOption('existing');
      const reverted = await page.evaluate(() => {
        const data = new FormData(document.querySelector('form'));
        return {
          sprintHiddenDisabled: [...document.querySelectorAll('[data-sprint-parts]')].every(el => el.hidden && [...el.querySelectorAll('select')].every(s => s.disabled)),
          existingVisibleEnabled: [...document.querySelectorAll('[data-existing-paper]')].every(el => !el.hidden && !el.querySelector('select').disabled),
          noSprintFields: !data.has('listening_sprint_part') && !data.has('reading_sprint_part'),
          oldPaperFields: data.has('listening_test_id') && data.has('reading_test_id'),
        };
      });
      const revertedMetrics = await page.evaluate(readMetrics);
      await page.screenshot({ path: path.join(report, 'screenshots', `mock-existing-${width}.png`), fullPage: true });
      const passed = Object.values(initial).every(Boolean) && visibleSelectors === 7 && sprint.counts.every(n => n === 40) && sprint.selectedCount === 7 && sprint.existingHiddenDisabled && sprint.validity && sprint.noOldPaperFields && sprint.submittedPartCounts.join(',') === '4,3' && Object.values(reverted).every(Boolean) && !sprintMetrics.horizontalOverflow && !revertedMetrics.horizontalOverflow && !errors.length && !missing.length && !blocked.length;
      result.cases.push({ width, initial, visibleSelectors, sprint, sprintMetrics, reverted, revertedMetrics, errors, missing, blocked, passed });
      await context.close();
    }
    result.passed = result.cases.every(c => c.passed);
    fs.writeFileSync(path.join(report, 'mock-visual-results.json'), JSON.stringify(result, null, 2) + '\n');
    console.log(JSON.stringify(result, null, 2));
    if (!result.passed) process.exitCode = 1;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
