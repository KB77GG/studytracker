// Anonymous production reads only; grading transitions are DOM-only in an isolated browser.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const base = 'https://studytracker.xin';
let browser;
(async()=>{
  browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const writes=[];
  await context.route('**/*',route=>{
    const request=route.request();
    if(!['GET','HEAD'].includes(request.method())) {writes.push(request.method()+' '+new URL(request.url()).pathname);return route.abort();}
    return new URL(request.url()).origin===base?route.continue():route.abort();
  });
  const page=await context.newPage();const errors=[];const cases=[];
  page.on('pageerror',e=>errors.push(e.message));
  for(const kind of ['reading','listening']) {
    const response=await page.goto(base+'/'+kind+'/test/ielts18_test1'+(kind==='reading'?'_reading':''));
    assert.equal(response.status(),200);await page.waitForTimeout(500);
    const selector=kind==='reading'?'#questionPanel':'#sectionsRoot';
    const selected=await page.evaluate(selector=>{
      const root=document.querySelector(selector);const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let n;
      while((n=walker.nextNode())) {
        if(!n.parentElement.getClientRects().length||n.parentElement.closest('button,input,select,textarea,.review-chrome,.review-card,.review-summary,.review-controls,.selection-hint')||n.textContent.trim().length<16)continue;
        const start=n.textContent.search(/\S/);const range=document.createRange();range.setStart(n,start);range.setEnd(n,start+16);const s=getSelection();s.removeAllRanges();s.addRange(range);document.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));return range.toString();
      }
      throw Error('No source text');
    },selector);
    await page.locator('.ex-hl-toolbar button').filter({hasText:'高亮'}).first().click();
    await page.evaluate(kind=>{
      document.body.classList.add('result-mode');setExperienceMode('review');
      if(kind==='reading') {resultMode=true;serverResult=PracticeScoring.gradeReadingTestAnswers(testData,{});renderPassage(testData.passages[0]);paintResults();}
      else {const results=Array.from(document.querySelectorAll('.answer-unit')).map(markUnit);applyServerResults(results);}
    },kind);
    await page.waitForTimeout(250);
    const restored=(await page.locator(selector+' .ex-hl').allTextContents()).join('');
    assert.equal(restored,selected);
    cases.push({kind,http:response.status(),selected,restored,framePolicy:response.headers()['x-frame-options']});
  }
  const denied=await context.request.get(base+'/exam/0/session/qa-invalid/review/reading?embed=1');
  assert.equal(denied.status(),404);assert.match(denied.headers()['cache-control'],/no-store/);
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);
  fs.writeFileSync('docs/reviews/review-highlights-20261111/production-browser.json',JSON.stringify({scope:'Anonymous GET/HEAD and local DOM transitions only; no real student or submission.',cases,invalidReviewStatus:denied.status(),writes,errors},null,2)+'\n');
  await browser.close();console.log('Production readonly browser smoke passed.');
})().catch(async e=>{console.error(e);if(browser)await browser.close();process.exitCode=1;});
