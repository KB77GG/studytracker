#!/usr/bin/env node
/* Validate the standalone admin UI v2 preview and write screenshots.

   Usage:
     NODE_PATH=/path/to/node_modules node scripts/validate_admin_ui_v2_preview.cjs

   Optional:
     CHROME_EXECUTABLE=/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome
*/

const path = require('node:path');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '..');
const previewPath = path.join(root, 'static', 'admin_ui_v2_preview.html');
const outDir = path.join(root, 'tmp');
const chromeExecutable = process.env.CHROME_EXECUTABLE
  || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function inspect(page) {
  return page.evaluate(() => ({
    title: document.title,
    materialRows: document.querySelectorAll('#materialsTable tbody tr').length,
    taskRows: document.querySelectorAll('#tasksTable tbody tr').length,
    statCards: document.querySelectorAll('.admin-v2-stat').length,
    detailPanels: document.querySelectorAll('.admin-v2-detail-main, .admin-v2-detail-side').length,
    formSections: document.querySelectorAll('.admin-v2-form-section').length,
    descriptions: Array.from(document.querySelectorAll('.admin-v2-description')).map((el) => ({
      text: el.textContent.trim().slice(0, 30),
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight
    })),
    bodyWidth: document.body.scrollWidth,
    viewportWidth: window.innerWidth
  }));
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function renderViewport(browser, name, viewport) {
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 });
  await page.goto(`file://${previewPath}`, { waitUntil: 'networkidle' });
  const metrics = await inspect(page);
  await page.screenshot({ path: path.join(outDir, `admin-ui-v2-preview-${name}.png`), fullPage: true });
  await page.close();
  return metrics;
}

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: chromeExecutable
  });

  const desktop = await renderViewport(browser, 'desktop', { width: 1440, height: 980 });
  const mobile = await renderViewport(browser, 'mobile', { width: 390, height: 920 });
  await browser.close();

  assert(desktop.title === 'StudyTracker Admin UI v2 Preview', 'Unexpected preview title');
  assert(desktop.materialRows >= 4, 'Expected material sample rows');
  assert(desktop.taskRows >= 3, 'Expected task sample rows');
  assert(desktop.statCards >= 4, 'Expected stat summary cards');
  assert(desktop.detailPanels >= 2, 'Expected detail layout panels');
  assert(desktop.formSections >= 2, 'Expected form sections');
  assert(desktop.descriptions.some((item) => item.scrollHeight > item.clientHeight), 'Expected at least one clamped long description');
  assert(desktop.bodyWidth <= desktop.viewportWidth, 'Desktop preview should not overflow horizontally');
  assert(mobile.bodyWidth <= mobile.viewportWidth, 'Mobile preview should not overflow page horizontally');

  console.log(JSON.stringify({ desktop, mobile }, null, 2));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
