/* One-off report companion; all requests are fulfilled locally without a server. */
const fs = require('fs');
const path = require('path');
const { chromium } = require('/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const report = __dirname;
const types = { '.css': 'text/css', '.html': 'text/html', '.png': 'image/png', '.woff2': 'font/woff2' };
const widths = [1440, 1280, 1024, 768, 390];

(async () => {
  const browser = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
  const results = { scope: JSON.parse(fs.readFileSync(path.join(report, 'fixture-manifest.json'))).scope, browser: await browser.version(), cases: [], comparisons: [] };
  fs.mkdirSync(path.join(report, 'screenshots'), { recursive: true });
  try {
    for (const variant of ['baseline', 'current']) for (const width of widths) {
      const pair = [];
      for (const pageName of ['materials', 'tasks']) {
        const context = await browser.newContext({ viewport: { width, height: 900 }, deviceScaleFactor: 1, reducedMotion: 'reduce' });
        const page = await context.newPage();
        const errors = [];
        const missing = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', async route => {
          const url = new URL(route.request().url());
          if (url.hostname !== 'sidebar-qa.invalid') return route.abort();
          const filename = url.pathname.startsWith('/vendor/') || url.pathname.startsWith('/webfonts/')
            ? path.join(report, 'vendor', path.basename(url.pathname))
            : path.join(report, 'site', variant, url.pathname === '/' ? `${pageName}.html` : url.pathname.slice(1));
          if (!fs.existsSync(filename)) { missing.push(url.pathname); return route.fulfill({ status: 404, body: '' }); }
          return route.fulfill({ body: fs.readFileSync(filename), contentType: types[path.extname(filename)] || 'application/octet-stream' });
        });
        await page.goto('http://sidebar-qa.invalid/');
        await page.evaluate(() => document.fonts.ready);
        const mobile = width <= 768;
        const drawer = {};
        if (mobile) {
          drawer.initialClosed = await page.locator('#sidebarToggle').getAttribute('aria-expanded') === 'false';
          await page.locator('#sidebarToggle').click();
          await page.waitForTimeout(300);
          drawer.opened = await page.locator('#sidebarToggle').getAttribute('aria-expanded') === 'true';
        }
        const metrics = await page.evaluate(() => {
          const icon = document.querySelector('.brand-icon');
          const title = document.querySelector('.brand-title');
          const sidebar = document.querySelector('.sidebar');
          const range = document.createRange(); range.selectNodeContents(title);
          const titleRects = [...range.getClientRects()];
          const heading = document.querySelector('.main-header__title h1');
          const headingRange = document.createRange(); headingRange.selectNodeContents(heading);
          const headingSingleLine = headingRange.getClientRects().length === 1;
          const r = el => { const x = el.getBoundingClientRect(); return { x: x.x, y: x.y, width: x.width, height: x.height, right: x.right }; };
          return { headingSingleLine, icon: r(icon), image: r(icon.querySelector('img')), background: getComputedStyle(icon).backgroundColor,
            radius: getComputedStyle(icon).borderRadius, title: r(title), titleFont: getComputedStyle(title).fontSize,
            titleLineCount: titleRects.length, sidebar: r(sidebar),
            titleFitsSidebar: titleRects.every(x => x.right <= sidebar.getBoundingClientRect().right + .5),
            sidebarOverflow: sidebar.scrollWidth > sidebar.clientWidth + 1,
            documentOverflow: document.documentElement.scrollWidth > innerWidth + 1,
            imageLoaded: icon.querySelector('img').complete && icon.querySelector('img').naturalWidth > 0 };
        });
        const screenshot = `screenshots/${variant}-${pageName}-${width}${mobile ? '-drawer-open' : ''}.png`;
        await page.screenshot({ path: path.join(report, screenshot) });
        if (mobile) {
          await page.keyboard.press('Escape'); await page.waitForTimeout(300);
          drawer.escapeClosed = await page.locator('#sidebarToggle').getAttribute('aria-expanded') === 'false';
          await page.screenshot({ path: path.join(report, `screenshots/${variant}-${pageName}-${width}-drawer-closed.png`) });
          await page.locator('#sidebarToggle').click(); await page.waitForTimeout(300);
          await page.mouse.click(width - 8, 500); await page.waitForTimeout(300);
          drawer.overlayClosed = await page.locator('#sidebarToggle').getAttribute('aria-expanded') === 'false';
        }
        const item = { variant, page: pageName, width, metrics, drawer, errors, missing, screenshot };
        results.cases.push(item); pair.push(item);
        await context.close();
      }
      const a = pair[0].metrics, b = pair[1].metrics;
      const same = ['background', 'radius', 'titleFont'].every(key => a[key] === b[key]) && ['width', 'height'].every(key => a.icon[key] === b.icon[key] && a.image[key] === b.image[key] && a.sidebar[key] === b.sidebar[key]);
      results.comparisons.push({ variant, width, identicalBrand: same, bothSingleLine: a.titleLineCount === 1 && b.titleLineCount === 1, bothFit: a.titleFitsSidebar && b.titleFitsSidebar && !a.sidebarOverflow && !b.sidebarOverflow, noPageOverflow: !a.documentOverflow && !b.documentOverflow });
    }
    results.currentPass = results.comparisons.filter(x => x.variant === 'current').every(x => x.identicalBrand && x.bothSingleLine && x.bothFit && x.noPageOverflow) && results.cases.filter(x => x.variant === 'current').every(x => !x.errors.length && !x.missing.length && x.metrics.imageLoaded && x.metrics.headingSingleLine && Object.values(x.drawer).every(Boolean));
    fs.writeFileSync(path.join(report, 'visual-results.json'), JSON.stringify(results, null, 2) + '\n');
    console.log(JSON.stringify({ currentPass: results.currentPass, comparisons: results.comparisons, errors: results.cases.filter(x => x.errors.length || x.missing.length).map(x => ({ variant: x.variant, page: x.page, width: x.width, errors: x.errors, missing: x.missing })) }, null, 2));
    if (!results.currentPass) process.exitCode = 1;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
