const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('/private/tmp/exam-integrity-browser-tools/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  const failures = [];
  page.on('pageerror', error => failures.push(error.message));
  const output = __dirname;
  const url = 'http://127.0.0.1:5096/teacher/vocabulary-review?week=2026-11-17';
  const results = {};
  try {
    await page.goto(url);
    await page.getByRole('heading', {name: '词汇复习周清单', exact: true}).waitFor();
    assert.equal(await page.getByText('合成学生丙', {exact: true}).count(), 0);
    await page.locator('details summary').first().click();
    assert.equal(await page.locator('details[open]').count(), 1);
    assert.match(await page.locator('details[open]').innerText(), /词义回忆/);
    await page.screenshot({path: path.join(output, 'desktop-expanded.png'), fullPage: true});
    results.desktop = await page.evaluate(() => ({viewport: innerWidth, pageWidth: document.documentElement.scrollWidth}));
    assert.equal(results.desktop.pageWidth, results.desktop.viewport);
    await page.getByLabel('查看哪一周').fill('2026-11-10');
    await Promise.all([page.waitForURL('**week=2026-11-10'), page.getByRole('button', {name: '查看', exact: true}).click()]);
    await page.getByText('这一周暂无需要汇总的记录。').waitFor();
    assert.equal(await page.getByLabel('查看哪一周').inputValue(), '2026-11-09');
    results.weekFilter = 'selected date normalizes to Monday; previous week shows empty digest';
    await page.goto(url);
    await page.getByRole('link', {name: '合成学生甲', exact: true}).click();
    assert.equal(await page.getByRole('link', {name: '合成学生乙', exact: true}).count(), 0);
    await page.getByRole('link', {name: '返回全部授权学生'}).click();
    await page.setViewportSize({width: 390, height: 844});
    await page.locator('details summary').first().click();
    await page.screenshot({path: path.join(output, 'mobile-expanded.png'), fullPage: true});
    results.mobile = await page.evaluate(() => ({
      viewport: innerWidth,
      pageWidth: document.documentElement.scrollWidth,
      tables: [...document.querySelectorAll('.table-scroll')].map(element => ({client: element.clientWidth, scroll: element.scrollWidth, overflow: getComputedStyle(element).overflowX})),
    }));
    assert.equal(results.mobile.pageWidth, results.mobile.viewport);
    assert.ok(results.mobile.tables.every(table => table.overflow === 'auto'));
    results.javascriptErrors = failures;
    assert.deepEqual(failures, []);
    fs.writeFileSync(path.join(output, 'visual-results.json'), JSON.stringify(results, null, 2) + '\n');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
