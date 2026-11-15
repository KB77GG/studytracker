/* Local Playwright acceptance. Only disposable fixture on loopback; synthetic identities. */
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || '/private/tmp/exam-integrity-browser-tools/node_modules/playwright');
const {spawn} = require('node:child_process');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../..');
const evidenceDir = process.env.INTEGRITY_EVIDENCE_DIR || __dirname;
const base = 'http://127.0.0.1:5098';
const evidence=[];
const report=(name,detail={})=>{evidence.push({name,ok:true,...detail});console.log('PASS '+name)};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
let server,browser,lastPage;
async function until(fn, timeout=20000){const start=Date.now();while(Date.now()-start<timeout){if(await fn())return;await wait(200)}throw Error('condition timeout')}
async function screen(page,name){await page.screenshot({path:path.join(evidenceDir,name+'.png'),fullPage:true})}
async function visibility(page, duration=2150){
  // Controlled visibility events exercise the shipped guard + real HTTP + DB.
  // Headless events do not stand in for iPad/App-switch OS verification.
  await page.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'hidden'});document.dispatchEvent(new Event('visibilitychange'))});
  await wait(duration);
  await page.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'visible'});document.dispatchEvent(new Event('visibilitychange'))});
  await wait(350);
}
async function clickStart(page,id){const link=page.locator(id);await link.evaluate(el=>el.scrollIntoView({block:'center'}));await link.click({force:true})}
async function login(page,mode){
  await page.goto(base+'/__integrity_fixture/new/'+mode);
  const examId=page.url().split('/').pop();
  await page.locator('#examName').fill('Synthetic Student');await page.locator('#btnLogin').click();
  await page.locator('#examPin').fill('TEST1');await page.locator('#btnLogin').click();
  await page.waitForURL(/\/session\//);
  const process=page.url(); const token=process.split('/').pop();
  if(mode==='enforce'){
    await page.getByRole('button',{name:'我已阅读并承诺遵守'}).waitFor();
    assert.equal(await page.locator('#btnStartListening').getAttribute('href'),null);
    await screen(page,'enforce-rules');
    await page.getByRole('button',{name:'我已阅读并承诺遵守'}).click();
    await until(async()=>!!await page.locator('#btnStartListening').getAttribute('href'));
  }
  if(mode==='monitor'){
    await page.getByRole('button',{name:'我已阅读并承诺遵守'}).waitFor();
    assert.ok(await page.locator('#btnStartListening').getAttribute('href'));
  }
  if(await page.locator('#btnConfirmPretest').isEnabled())await page.locator('#btnConfirmPretest').click();
  await page.locator('#cardListening summary').click();
  if(await page.locator('#btnConfirmListening').isEnabled())await page.locator('#btnConfirmListening').click();
  await page.locator('#cardListening summary').click();await clickStart(page,'#btnStartListening');
  await page.getByRole('button',{name:'开始 Listening',exact:true}).click();
  await page.getByRole('radio',{name:'Question 1 answer: TRUE',exact:true}).check();
  return {examId,process,token,api:base+'/api/exam/'+examId+'/session/'+token};
}
async function finish(page,kind){
  await page.locator('#examFinishBtn').waitFor({state:'visible',timeout:15000});
  await page.locator('#examFinishBtn').click();
  await page.waitForURL(kind==='writing'?/\/result(?:\?.*)?$/:/\/session\/[^/]+(?:\?.*)?$/);
}
async function state(page,info){return (await page.request.get(info.api+'/integrity/state?section=reading')).json()}
async function run(){
  await fs.mkdir(evidenceDir, {recursive:true});
  server=spawn(process.env.PYTHON || '/Users/zhouxin/Desktop/studytracker/.venv/bin/python',['-B','-m','tests.exam_integrity_e2e_support','--port','5098'],{cwd:root,stdio:['ignore','pipe','pipe']});
  let serverErr='';server.stderr.on('data',d=>{serverErr+=d.toString()});
  await until(async()=>{try{return (await fetch(base+'/exam/1')).ok}catch(_){return false}},15000);
  browser=await chromium.launch({executablePath:process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  for(const mode of ['off','monitor','enforce']){
    const context=await browser.newContext({viewport:{width:1280,height:900}});
    await context.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
    const page=await context.newPage();lastPage=page;page.on('dialog',d=>d.accept());
    const requests=[],errors=[];page.on('request',r=>requests.push(r.url()));page.on('pageerror',e=>errors.push(e.message));
    const info=await login(page,mode);
    if(mode!=='off'){
      for(let i=0;i<3;i++)await visibility(page);
      assert.equal((await state(page,info)).leave_count,3);
      assert.equal(await page.locator('.exam-integrity-overlay').isVisible(),false);
      report(mode+' listening: three controlled leaves, no overlay');
    }
    await finish(page,'listening');await clickStart(page,'#btnStartReading');
    await page.getByRole('textbox',{name:'Question 1 answer',exact:true}).fill('TRUE');
    if(mode==='enforce'){
      await visibility(page);
      await page.locator('.exam-integrity-overlay').waitFor({state:'visible'});
      assert.ok((await page.locator('.exam-integrity-overlay').innerText()).includes('计时仍在继续'));
      await screen(page,'reading-locked');
      const teacher=await context.newPage();teacher.on('dialog',d=>d.accept());
      await teacher.goto(base+'/__integrity_fixture/teacher?exam_id='+info.examId);
      await teacher.getByRole('button',{name:'解锁',exact:true}).click();
      await page.locator('.exam-integrity-overlay').waitFor({state:'hidden',timeout:10000});
      report('teacher unlock restores reading');
      await teacher.setViewportSize({width:390,height:844});
      assert.equal(await teacher.locator('#sidebar').isVisible(),false);
      assert.ok(await teacher.evaluate(()=>document.documentElement.scrollWidth<=390));
      const emergencyButton=teacher.getByRole('button',{name:'紧急关闭本场防作弊'});
      await emergencyButton.evaluate(el=>el.scrollIntoView({block:'center'}));
      assert.ok(await emergencyButton.evaluate(el=>{const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}));
      await screen(teacher,'teacher-mobile');
      assert.ok(await teacher.getByRole('button',{name:'紧急关闭本场防作弊'}).isVisible());
      report('mobile teacher panel controls visible');
      // Automatic submit under a real stored lock; only the fixture deadline is shortened.
      await visibility(page);await page.locator('.exam-integrity-overlay').waitFor({state:'visible'});
      await page.request.post(base+'/__integrity_fixture/expire',{data:{token:info.token,seconds:8}});
      await page.reload();
      await page.locator('.exam-integrity-overlay').waitFor({state:'visible'});
      await page.waitForURL(/\/session\/[^/]+(?:\?.*)?$/,{timeout:16000});
      report('locked reading timer automatically submits and returns to process');
      await teacher.getByRole('button',{name:'解锁',exact:true}).click();
      await teacher.close();
    }else await finish(page,'reading');
    await clickStart(page,'#btnStartWriting');await page.locator('#essayTask1').fill('My own text.');
    await page.locator('#essayTask2').fill('My second original essay.');
    if(mode!=='off'){
      const paste=async text=>page.locator('#essayTask1').evaluate((el,text)=>{const data=new DataTransfer();data.setData('text/plain',text);const e=new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:data});el.dispatchEvent(e);return e.defaultPrevented},text);
      assert.equal(await paste('External synthetic text'),mode==='enforce');
      await page.locator('#essayTask1').evaluate(el=>{el.focus();el.setSelectionRange(0,el.value.length);el.dispatchEvent(new ClipboardEvent('copy',{bubbles:true,cancelable:true,clipboardData:new DataTransfer()}))});
      assert.equal(await paste('My own text.'),false);
      report(mode+' external/internal clipboard event decisions');
    }
    if(mode==='enforce'){
      await visibility(page);await page.locator('.exam-integrity-overlay').waitFor({state:'visible'});
      const teacher=await context.newPage();teacher.on('dialog',d=>d.accept());
      await teacher.goto(base+'/__integrity_fixture/teacher?exam_id='+info.examId);
      const start=Date.now();await teacher.getByRole('button',{name:'紧急关闭本场防作弊'}).click();
      await page.locator('.exam-integrity-root').waitFor({state:'detached',timeout:20000});
      report('emergency off removes all overlays',{milliseconds:Date.now()-start});
      await teacher.close();
    }
    await finish(page,'writing');
    assert.equal(await page.locator('#exam-integrity-root').count(),0);
    await screen(page,mode+'-result');
    const review=page.locator('a[href*="/review"]').first();await review.click();
    assert.equal(await page.locator('#exam-integrity-config').count(),0);
    if(mode==='off')assert.equal(requests.filter(u=>u.includes('/integrity/')||u.includes('exam_guard')).length,0);
    assert.deepEqual(errors,[]);
    report(mode+' full login/listen/read/write/result/review',{integrityRequests:requests.filter(u=>u.includes('/integrity/')).length,consoleErrors:errors.length});
    await context.close();
  }
  report('browser engine',{version:browser.version()});
}
(async()=>{try{await run()}catch(e){console.error(e.stack);if(lastPage){await screen(lastPage,'failure');await fs.writeFile(path.join(evidenceDir,'failure.html'),await lastPage.content())}evidence.push({ok:false,error:e.message});process.exitCode=1}finally{await fs.writeFile(path.join(evidenceDir,'browser-results.json'),JSON.stringify(evidence,null,2)+'\n');if(browser)await browser.close();if(server)server.kill('SIGTERM')}})();
