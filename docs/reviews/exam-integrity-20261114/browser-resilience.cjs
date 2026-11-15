/*
 * Extended local acceptance; disposable synthetic fixture only (port 5099).
 * Native mouse/keyboard for paper interaction; controlled visibility events for
 * lock setup. No claim of OS-level iPad/Safari app-switch or split-view coverage.
 * Run only after the parent runner's approval. This file does not install tools.
 */
'use strict';
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '/private/tmp/exam-integrity-browser-tools/node_modules/playwright');
const { spawn } = require('node:child_process');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../..');
const base = 'http://127.0.0.1:5099';
const evidence = [];
const errors = [];
const contexts = [];
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
let server, browser, lastPage;
let serverError = '';
function report(name, detail = {}) {
  evidence.push({ name, ok: true, ...detail });
  console.log('PASS ' + name);
}
async function until(fn, timeout = 20000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    if (await fn()) return;
    await wait(150);
  }
  throw Error('condition timeout');
}
async function screen(page, name) {
  await page.screenshot({ path: path.join(__dirname, 'resilience-' + name + '.png'), fullPage: true });
}
async function context() {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.route('**/*', route => {
    const url = new URL(route.request().url());
    return url.hostname === '127.0.0.1' ? route.continue() : route.abort();
  });
  contexts.push(ctx);
  return ctx;
}
async function page(ctx) {
  const p = await ctx.newPage();
  lastPage = p;
  p.on('dialog', dialog => dialog.accept());
  p.on('pageerror', error => errors.push(error.message));
  return p;
}
async function json(response) {
  assert.equal(response.ok(), true, 'fixture or real API request must succeed');
  const data = await response.json();
  assert.equal(data.ok, true, JSON.stringify(data));
  return data;
}
async function prepareReading(p, mode) {
  // Fast setup uses existing real login and Listening-submit routes, not DB edits.
  const created = await p.request.get(base + '/__integrity_fixture/new/' + mode);
  assert.equal(created.ok(), true);
  const examId = new URL(created.url()).pathname.split('/').pop();
  const logged = await json(await p.request.post(base + '/api/exam/' + examId + '/start', {
    data: { name: 'Synthetic Student', pincode: 'TEST1' },
  }));
  const processPath = new URL(logged.session_url, base).pathname;
  const token = processPath.split('/').pop();
  const api = base + '/api/exam/' + examId + '/session/' + token;
  await json(await p.request.post(api + '/submit-listening', {
    data: { answers: { 1: 'TRUE' }, duration_seconds: 1 },
  }));
  await p.goto(base + processPath + '/reading');
  await p.getByRole('textbox', { name: 'Question 1 answer', exact: true }).waitFor();
  await p.evaluate(() => document.fonts.ready);
  if (mode === 'enforce') {
    await p.locator('.exam-integrity-watermark').waitFor({ state: 'visible' });
    await p.locator('.exam-integrity-overlay').waitFor({ state: 'hidden' });
  }
  return { examId, processPath, token, api, reading: base + processPath + '/reading' };
}
async function state(p, info) {
  const device = await p.evaluate(() => localStorage.getItem('exam-integrity-device:v1') || '');
  const query = new URLSearchParams({ section: 'reading' });
  return json(await p.request.get(info.api + '/integrity/state?' + query, { headers: { 'X-Exam-Integrity-Device': device } }));
}
async function geometry(p) {
  const selectors = ['#passagePanel', '#questionPanel', '#questionNav', '#passagePanel .paragraph', '[data-qid="1"]'];
  const values = {};
  for (const selector of selectors) {
    values[selector] = await p.locator(selector).first().boundingBox();
    assert.ok(values[selector], 'visible geometry for ' + selector);
  }
  return values;
}
async function visibility(p, milliseconds = 2150) {
  await p.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await wait(milliseconds);
  await p.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await wait(350);
}
async function dismissSoft(p) {
  const button = p.locator('.exam-integrity-overlay').getByRole('button', { name: '点击继续答题', exact: true });
  if (await button.isVisible()) await button.click();
}
async function nativeHighlight(p) {
  await p.locator('#passagePanel .paragraph').scrollIntoViewIfNeeded();
  const before = await p.locator('#passagePanel .paragraph').boundingBox();
  // Read text geometry only; actual selection is made by real pointer drag.
  const target = await p.locator('#passagePanel .paragraph').evaluate(el => {
    const text = Array.from(el.childNodes).find(node => node.nodeType === Node.TEXT_NODE && node.textContent.includes('A quiet room'));
    if (!text) throw Error('synthetic passage text missing');
    const range = document.createRange();
    const start = text.textContent.indexOf('A quiet room');
    range.setStart(text, start);
    range.setEnd(text, start + 'A quiet room'.length);
    const rect = range.getBoundingClientRect();
    return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
  });
  await p.mouse.move(target.x + 1, target.y + target.height / 2);
  await p.mouse.down();
  await p.mouse.move(target.x + target.width - 1, target.y + target.height / 2, { steps: 16 });
  await p.mouse.up();
  const selectedText=await p.evaluate(()=>window.getSelection().toString());
  assert.ok(selectedText.trim().length>0);
  await p.locator('.ex-hl-toolbar').waitFor({ state: 'visible' });
  await p.locator('.ex-hl-toolbar').getByRole('button', { name: /高亮/ }).first().click();
  const mark = p.locator('#passagePanel .paragraph .ex-hl').first();
  await mark.waitFor({ state: 'visible' });
  assert.ok((await p.locator('#passagePanel .paragraph .ex-hl').allTextContents()).join('').includes(selectedText.trim()));
  const after = await p.locator('#passagePanel .paragraph').boundingBox();
  for (const axis of ['x', 'y', 'width', 'height']) assert.ok(Math.abs(before[axis] - after[axis]) < 1, 'highlight must preserve paragraph ' + axis);
  const markRect = await mark.boundingBox();
  assert.ok(markRect.x >= after.x - 1 && markRect.x + markRect.width <= after.x + after.width + 1);
  await screen(p, 'reading-highlight');
  report('native pointer selection and highlighter work under enforce', { before, after, highlightWidth: markRect.width });
}
async function finishReadingAndWriting(p, info) {
  const submitted = p.waitForResponse(response => new URL(response.url()).pathname === new URL(info.api).pathname + '/submit-reading' && response.request().method() === 'POST');
  await p.locator('#examFinishBtn').click();
  assert.equal((await submitted).ok(), true);
  await p.waitForURL(url => url.pathname === info.processPath);
  assert.match(await p.locator('#readingSummary').innerText(), /已完成：1\/1/);
  await p.locator('#btnStartWriting').evaluate(el => el.scrollIntoView({block:'center'}));
  await p.locator('#btnStartWriting').click({force:true});
  await p.locator('#essayTask1').fill('Synthetic original writing after integrity tables disappeared.');
  await p.locator('#essayTask2').fill('This second synthetic essay confirms the existing submission path stays available.');
  const writing = p.waitForResponse(response => new URL(response.url()).pathname === new URL(info.api).pathname + '/submit-writing' && response.request().method() === 'POST');
  await p.locator('#examFinishBtn').click();
  assert.equal((await writing).ok(), true);
  await p.waitForURL(url => url.pathname === info.processPath + '/result');
  assert.equal(await p.locator('#exam-integrity-root').count(), 0);
  await screen(p, 'tables-missing-result');
  report('after table removal, native Reading and Writing submission reaches result', { readingSubmitStatus: 200, writingSubmitStatus: 200 });
}
async function run() {
  server = spawn(process.env.PYTHON || '/Users/zhouxin/Desktop/studytracker/.venv/bin/python', ['-B', '-m', 'tests.exam_integrity_e2e_support', '--port', '5099'], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] });
  server.stderr.on('data', data => { serverError += data.toString(); });
  await until(async () => { try { return (await fetch(base + '/exam/1')).ok; } catch (_) { return false; } }, 15000);
  browser = await chromium.launch({ executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
  const oldContext = await context();
  const newContext = await context();

  const baseline = await page(oldContext);
  await prepareReading(baseline, 'off');
  const baselineGeometry = await geometry(baseline);
  const baselineNotes = await baseline.locator('.note-box, [data-note-editor]').count();
  assert.equal(await baseline.locator('#exam-integrity-config').count(), 0);
  await baseline.close();

  const oldPage = await page(oldContext);
  const oldEvents = [];
  oldPage.on('request', request => { if (request.url().includes('/integrity/event') && request.postData()) oldEvents.push(JSON.parse(request.postData()).type); });
  const info = await prepareReading(oldPage, 'enforce');
  const activeGeometry = await geometry(oldPage);
  for (const selector of Object.keys(baselineGeometry)) {
    for (const axis of ['x', 'y', 'width', 'height']) {
      assert.ok(Math.abs(activeGeometry[selector][axis] - baselineGeometry[selector][axis]) < 2, `${selector} ${axis}: fixed guard must not move the exam paper`);
    }
  }
  assert.equal(await oldPage.locator('.exam-integrity-watermark').evaluate(el => getComputedStyle(el).pointerEvents), 'none');
  report('off/enforce paper geometry stays within two pixels', { baselineGeometry, activeGeometry });
  const activeNotes = await oldPage.locator('.note-box, [data-note-editor]').count();
  assert.equal(activeNotes, baselineNotes);
  evidence.push({ name: 'in-exam notes', ok: null, status: 'not_available_in_baseline', offControls: baselineNotes, enforceControls: activeNotes, detail: 'Reading has no note editor; Listening answerTools hides error notes in simulationMode. No feature was invented for this test.' });

  // Native coordinate click proves the fixed watermark does not intercept answers.
  const input = oldPage.getByRole('textbox', { name: 'Question 1 answer', exact: true });
  const inputRect = await input.boundingBox();
  await oldPage.mouse.click(inputRect.x + inputRect.width / 2, inputRect.y + inputRect.height / 2);
  await oldPage.keyboard.type('TRUE');
  assert.equal(await input.inputValue(), 'TRUE');
  await oldPage.locator('#questionNav [data-question-nav="1"]').click();
  await oldPage.waitForFunction(() => document.activeElement && document.activeElement.getAttribute('data-qid') === '1');
  await oldPage.locator('#toggleQuestionFlag').click();
  assert.equal(await oldPage.locator('#toggleQuestionFlag').getAttribute('aria-pressed'), 'true');
  assert.match(await oldPage.locator('#questionNav [data-question-nav="1"]').getAttribute('class'), /is-flagged/);
  report('native answer click, question navigation and review flag remain usable');
  await nativeHighlight(oldPage);

  const newPage = await page(newContext);
  const newEvents = [];
  newPage.on('request', request => { if (request.url().includes('/integrity/event') && request.postData()) newEvents.push(JSON.parse(request.postData()).type); });
  await newPage.goto(info.reading);
  await newPage.locator('.exam-integrity-overlay').waitFor({ state: 'visible' });
  assert.match(await newPage.locator('.exam-integrity-overlay').innerText(), /另一台设备/);
  assert.equal((await state(newPage, info)).device_conflict, true);
  await screen(newPage, 'device-conflict');
  report('second isolated browser context receives real device conflict');

  const teacher = await page(oldContext);
  await teacher.goto(base + '/__integrity_fixture/teacher?exam_id=' + info.examId);
  const oldHelloCount = oldEvents.filter(type => type === 'hello').length;
  const resetResponse = teacher.waitForResponse(response => response.url().endsWith('/reset-device') && response.request().method() === 'POST');
  await teacher.getByRole('button', { name: '允许换设备', exact: true }).click();
  await json(await resetResponse);
  await newPage.bringToFront();
  await until(async () => !(await state(newPage, info)).device_conflict && (await state(newPage, info)).device_bound, 15000);
  await newPage.locator('.exam-integrity-overlay').waitFor({ state: 'hidden', timeout: 15000 });
  assert.equal(oldEvents.filter(type => type === 'hello').length, oldHelloCount, 'old page must not send a new hello to steal reset binding');
  assert.ok(newEvents.filter(type => type === 'hello').length >= 2, 'new conflicted page must retry hello after reset');
  assert.equal((await state(oldPage, info)).device_conflict, true);
  await oldPage.bringToFront();
  await until(async () => await oldPage.locator('.exam-integrity-overlay').isVisible() && /另一台设备/.test(await oldPage.locator('.exam-integrity-overlay').innerText()), 10000);
  await screen(oldPage, 'old-device-conflict-after-reset');
  await newPage.bringToFront();
  await dismissSoft(newPage);
  await screen(newPage, 'new-device-active');
  report('teacher reset lets the new device claim while old page cannot reclaim', { oldHelloBefore: oldHelloCount, oldHelloAfter: oldEvents.filter(type => type === 'hello').length, newHelloCount: newEvents.filter(type => type === 'hello').length });
  await teacher.close();

  const newAnswer = newPage.getByRole('textbox', { name: 'Question 1 answer', exact: true });
  await newAnswer.fill('TRUE');
  for (let i = 0; i < 3; i += 1) await visibility(newPage);
  await newPage.locator('.exam-integrity-overlay').waitFor({ state: 'visible' });
  assert.equal((await state(newPage, info)).is_locked, true);
  await screen(newPage, 'locked-before-table-drop');
  const droppedAt = Date.now();
  const dropped = await json(await newPage.request.post(base + '/__integrity_fixture/drop-integrity-tables'));
  assert.deepEqual(dropped.integrity_tables_remaining, []);
  assert.equal(dropped.legacy_session_table_present, true);
  await newPage.locator('#exam-integrity-root').waitFor({ state: 'detached', timeout: 20000 });
  assert.equal((await state(newPage, info)).mode, 'off');
  const saved = newPage.waitForResponse(response => response.url() === info.api + '/draft/reading' && response.request().method() === 'PUT');
  await newAnswer.fill('TRUE ');
  await json(await saved);
  const draft = await json(await newPage.request.get(info.api + '/draft/reading'));
  assert.equal(draft.answers['1'].trim(), 'TRUE');
  report('dropping only the three integrity tables removes the lock and preserves real draft saving', { milliseconds: Date.now() - droppedAt, legacySessionCount: dropped.legacy_session_count, eventMethod: 'controlled visibility events, not OS app switching' });
  await finishReadingAndWriting(newPage, info);
  assert.deepEqual(errors, []);
  report('extended browser console has no page errors', { browserVersion: browser.version(), consoleErrors: errors.length });
}
(async () => {
  try { await run(); }
  catch (error) {
    console.error(error.stack);
    if (lastPage && !lastPage.isClosed()) {
      await screen(lastPage, 'failure').catch(() => {});
      await fs.writeFile(path.join(__dirname, 'resilience-failure.html'), await lastPage.content()).catch(() => {});
    }
    evidence.push({ ok: false, error: error.message });
    process.exitCode = 1;
  } finally {
    await fs.writeFile(path.join(__dirname, 'browser-resilience-results.json'), JSON.stringify(evidence, null, 2) + '\n');
    for (const ctx of contexts) await ctx.close().catch(() => {});
    if (browser) await browser.close();
    if (server) server.kill('SIGTERM');
    // Server diagnostics include only synthetic fixture sessions, but no full log is published.
    if (process.exitCode && serverError) console.error(serverError.slice(-2500));
  }
})();
