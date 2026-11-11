const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = 'http://127.0.0.1:5097';
let browser;
async function highlight(page, selector) {
  const text = await page.evaluate(selector => {
    const root=document.querySelector(selector);
    const exclude='input,select,textarea,button,audio,.inline-answer,.result-pill,.answer-pill,.option-feedback,.selection-hint,.review-chrome,.review-card,.review-summary,.review-controls,.analysis,.sel-tx-popover,.ex-hl-toolbar,.note-box';
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
    let node;
    while((node=walker.nextNode())) {
      if(node.parentElement.closest(exclude)||!node.parentElement.getClientRects().length||node.textContent.trim().length<16)continue;
      const start=node.textContent.search(/\S/);const range=document.createRange();range.setStart(node,start);range.setEnd(node,start+16);
      const sel=getSelection();sel.removeAllRanges();sel.addRange(range);document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));return range.toString();
    }
    throw Error('No highlight candidate');
  },selector);
  await page.locator('.ex-hl-toolbar button').filter({hasText:'高亮'}).first().click();
  await page.waitForTimeout(160);return text;
}
async function frameFor(page,kind) {
  const locator=page.locator(`iframe[src*="/review/${kind}?"]`);
  await locator.waitFor();
  const frame=await(await locator.elementHandle()).contentFrame();
  await frame.waitForSelector('body.result-mode');
  await frame.waitForSelector('.review-card__status');
  return frame;
}
async function cardState(frame) {
  return frame.locator('.review-card').evaluateAll(cards=>cards.map(card=>({
    id:card.dataset.reviewQuestion,status:card.querySelector('[data-status]')?.dataset.status,
    visible:!!card.getClientRects().length,text:card.textContent,
  })));
}
(async()=>{
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
  const page=await context.newPage();const errors=[];const mutations=[];
  page.on('pageerror',error=>errors.push(error.message));
  page.on('request',r=>{if(r.method()!=='GET'&&r.method()!=='HEAD')mutations.push({method:r.method(),url:r.url()});});
  const expected={};
  for(const kind of ['reading','listening']) {
    await page.goto(`${base}/exam/1/session/student-session-token/${kind}`);await page.waitForTimeout(400);
    const selectors=kind==='reading'?['#passagePanel','#questionPanel']:['#sectionsRoot'];expected[kind]={};
    for(const selector of selectors)expected[kind][selector]=await highlight(page,selector);
  }
  const historyBefore=await page.evaluate(()=>history.length);
  await page.goto(`${base}/exam/1/session/student-session-token/review`);
  assert.equal(await page.getByRole('link',{name:/查看原卷与高亮/}).count(),0,'no extra original-paper link');
  const frames={};const states={};
  for(const kind of ['reading','listening']) {
    const frame=await frameFor(page,kind);frames[kind]=frame;await page.waitForTimeout(250);
    for(const [selector,text] of Object.entries(expected[kind]))assert.equal((await frame.locator(selector+' .ex-hl').allTextContents()).join(''),text,kind+' inline old highlights');
    const cards=await cardState(frame);states[kind]=cards.map(({id,status,visible})=>({id,status,visible}));
    assert(cards.some(c=>c.status==='incorrect'&&c.visible&&c.text.includes('qa_wrong')),kind+' wrong answer and explanation open');
    assert(cards.some(c=>c.status==='correct'&&c.visible),kind+' correct answer visible initially');
    assert.equal(await frame.locator('.ex-hl-toolbar').count(),0);
    await frame.locator('.review-card').first().scrollIntoViewIfNeeded();
    await page.screenshot({path:`docs/reviews/review-highlights-20261111/inline-${kind}-detail.png`});
  }
  assert.equal(await page.evaluate(()=>history.length),historyBefore+2,'embedded papers must not add history entries');
  await page.locator('#wrongOnly').check();await page.waitForTimeout(350);
  for(const kind of ['reading','listening']) {
    const cards=await cardState(frames[kind]);
    assert(cards.some(c=>c.status==='incorrect'&&c.visible),kind+' wrong retained');
    assert(!cards.some(c=>c.status==='correct'&&c.visible),kind+' correct hidden');
  }
  await page.locator('#wrongOnly').uncheck();await page.waitForTimeout(300);
  for(const kind of ['reading','listening'])assert((await cardState(frames[kind])).some(c=>c.status==='correct'&&c.visible),kind+' filter reversible');
  for(const kind of ['reading','listening']) {
    const frame=frames[kind];const tabs=frame.locator(kind==='reading'?'[data-passage-tab]':'#sectionTabs [data-index]');
    await tabs.nth(1).click();await tabs.first().click();await page.waitForTimeout(250);
    for(const [selector,text] of Object.entries(expected[kind]))assert.equal((await frame.locator(selector+' .ex-hl').allTextContents()).join(''),text,kind+' switch restores highlights');
  }
  await page.screenshot({path:'docs/reviews/review-highlights-20261111/inline-desktop.png'});
  await page.reload();
  for(const kind of ['reading','listening']) {
    const frame=await frameFor(page,kind);await page.waitForTimeout(200);
    for(const [selector,text] of Object.entries(expected[kind]))assert.equal((await frame.locator(selector+' .ex-hl').allTextContents()).join(''),text,kind+' reload restores highlights');
  }
  const geometry={};
  for(const width of [1440,390]) {
    await page.setViewportSize({width,height:1000});await page.waitForTimeout(500);
    geometry[width]=await page.locator('iframe').evaluateAll(frames=>frames.map(frame=>({height:frame.clientHeight,content:frame.contentDocument.body.scrollHeight,width:frame.clientWidth,contentWidth:frame.contentDocument.documentElement.scrollWidth})));
    for(const row of geometry[width]) {assert(row.content<=row.height+10,'no frame vertical crop');assert(row.contentWidth<=row.width+2,'no horizontal overflow');}
  }
  await page.screenshot({path:'docs/reviews/review-highlights-20261111/inline-mobile.png'});
  await page.locator('[data-practice-back]').first().click();
  await page.waitForURL(base+'/exam/1/session/student-session-token/result');
  // Existing profile-authorized route must display the same direct review.
  await page.request.post(base+'/test-remember/1');
  await page.goto(base+'/practice/mock-exams/1/review');
  for(const kind of ['reading','listening']) {
    const frame=await frameFor(page,kind);await page.waitForTimeout(150);
    for(const [selector,text] of Object.entries(expected[kind]))assert.equal((await frame.locator(selector+' .ex-hl').allTextContents()).join(''),text,kind+' profile view highlights');
  }
  assert.deepEqual(errors,[]);
  assert.deepEqual(mutations,[],'readonly review must not submit or save drafts');
  fs.writeFileSync('docs/reviews/review-highlights-20261111/inline-browser-result.json',JSON.stringify({expected,states,geometry,errors,mutations},null,2)+'\n');
  console.log('Inline browser: direct highlights, saved answers, visible explanations, reversible filtering, refresh, both routes, responsive geometry passed.');
  await browser.close();
})().catch(async error=>{console.error(error);if(browser)await browser.close();process.exitCode=1;});
