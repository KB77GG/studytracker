// Independent behavioral audit of real page modules; synthetic network only.
// Usage: node independent_client_probe.js /absolute/client-root
const assert = require('node:assert/strict')
const path = require('node:path')
const client = path.resolve(process.argv[2] || '/private/tmp/studytracker-vocabulary-forgot-client-20261114')
const requests = [], responses = [], redirects = [], played = [], definitions = {}, records = []
const store = new Map()
let registering
const app = { globalData: { baseUrl: 'https://synthetic.invalid/api', token: 'synthetic-token' } }
global.getApp = () => app
global.Page = value => { definitions[registering] = value }
global.wx = {
  request(value) { requests.push(value); assert.ok(responses.length, 'unexpected request'); responses.shift()(value) },
  getStorageSync: key => store.get(key), setStorageSync: (key,value) => store.set(key,value), removeStorageSync: key => store.delete(key),
  redirectTo: value => redirects.push(value.url), showToast() {}, reLaunch() {}, switchTab() {}
}
for (const kind of ['learning','review']) { registering = kind; require(path.join(client, `miniprogram/pages/student/vocabulary-${kind}/index.js`)) }
const good = value => request => request.success({ statusCode: 200, data: value })
const timeout = request => request.fail({ errMsg: 'request:fail timeout' })
function item(id=71) { return { learning_question_id:id, review_item_id:id, queue_item_id:id+100, question_id:`q-${id}`, word_id:id, sense_id:id, dimension:'form_recall', mode:'zh_to_en', question:{ prompt:{ meaning:`释义${id}`, word:`word${id}`, audio_url:`/prompt${id}.mp3` }, options:[] }, first_attempt_id:'', correction_required:false } }
function response(q, kind='learning', overrides={}) { return Object.assign({ ok:true, learning_question_id:q.learning_question_id, attempt_id:kind==='learning'?`vocabulary-group:42:first:${q.learning_question_id}`:`wx-vocabulary-review:8:${q.review_item_id}`, response_kind:'forgot', first_response_kind:'forgot', is_correct:false, student_answer:'', revealed_answer:`word${q.word_id}`, correction_required:false, answer_feedback:{ word:`word${q.word_id}`, core_meaning_zh:`释义${q.word_id}`, audio_url:`/answer${q.word_id}.mp3` } }, overrides) }
function learningQueue(q, overrides={}) { return Object.assign({ ok:true, task_id:42, queue_token:'queue-token', phase:'active_recall', current_question:q, supports_forgot_response:true, familiarity:[], completed:false }, overrides) }
function reviewSnapshot(items, overrides={}) { return Object.assign({ ok:true, session_id:8, session_token:'session-token', supports_forgot_response:true, status:'active', items }, overrides) }
function savedReview(q) { return Object.assign({},q,{ first_attempt_id:`wx-vocabulary-review:8:${q.review_item_id}`, first_response_kind:'forgot', first_is_correct:false, first_answer:'', revealed_answer:`word${q.word_id}`, answer_feedback:{ word:`word${q.word_id}`, core_meaning_zh:`释义${q.word_id}`, audio_url:`/answer${q.word_id}.mp3` } }) }
function page(kind, items=[item()]) {
  const result = Object.assign({}, definitions[kind]); result.data=JSON.parse(JSON.stringify(result.data))
  result.setData=function(data, callback) { Object.assign(this.data,data); if(callback) callback() }
  result.audioPlayer={ play: sources => played.push(sources), destroy() {} }
  if(kind==='learning') { result._learningPageActive=true; result._learningDeadlineTimers=new Set(); result.setData({ taskId:'42' }); result.applyQueue(learningQueue(items[0])) }
  else { result._reviewPageActive=true; result._reviewQueue=items; result._reviewSkippedItems=[]; result.returnTaskId=''; result.setData({ loading:false, sessionId:8, sessionToken:'session-token', supportsForgotResponse:true, totalCount:items.length }); result.showItem(0) }
  return result
}
function event(p, kind) { const q=kind==='learning'?p.data.currentQuestion:p.data.currentItem; return { currentTarget:{dataset:{ [kind==='learning'?'learningQuestionId':'reviewItemId']:q[kind==='learning'?'learning_question_id':'review_item_id'], questionId:q.question_id, renderEpoch:p.data.answerRenderEpoch }} } }
async function flush() { for(let i=0;i<25;i++) await Promise.resolve() }
async function check(name, run) { requests.length=responses.length=redirects.length=played.length=0; store.clear(); try { await run(); assert.equal(responses.length,0,'unused fixture responses'); records.push({ name,pass:true }) } catch(error) { records.push({ name,pass:false,error:error.message }) } }
;(async()=>{
  for(const kind of ['learning','review']) {
    await check(`${kind}: result stays; stale submit and keyboard confirm cannot advance`, async()=>{
      const p=page(kind,[item(),item(72)]), e=event(p,kind)
      responses.push(good(response(item(),kind)))
      await p.submitForgot(e)
      assert.equal(p.data.showResult,true); assert.equal(p.data.correctAnswer,'word71'); assert.equal(p.data.responseKind,'forgot'); assert.equal(requests.length,1)
      await p.submitAnswer(e); await p.submitForgot(e)
      assert.equal(requests.length,1); assert.equal((p.data.currentQuestion||p.data.currentItem).word_id,71)
      p.playAudio(); assert.deepEqual(played.at(-1),['/answer71.mp3'])
    })
    await check(`${kind}: saved timeout response restores original answer before continuation`, async()=>{
      const q=item(), p=page(kind,[q,item(72)])
      responses.push(timeout,good(kind==='learning'?learningQueue(item(72),{saved_response:response(q)}):reviewSnapshot([savedReview(q),item(72)])))
      await p.submitForgot(event(p,kind)); assert.equal(requests.length,2); assert.equal(p.data.showResult,true); assert.equal(p.data.correctAnswer,'word71'); assert.equal((p.data.currentQuestion||p.data.currentItem).word_id,71)
      p.playAudio(); assert.deepEqual(played.at(-1),['/answer71.mp3'])
    })
    await check(`${kind}: explicit continuation and repeated old event cannot skip unanswered word`, async()=>{
      const p=page(kind,[item(),item(72)]); responses.push(good(response(item(),kind))); await p.submitForgot(event(p,kind)); const old=event(p,kind)
      if(kind==='learning') responses.push(good(learningQueue(item(72))))
      await (kind==='learning'?p.continueAfterResult(old):p.nextItem(old))
      await (kind==='learning'?p.continueAfterResult(old):p.nextItem(old))
      assert.equal((p.data.currentQuestion||p.data.currentItem).word_id,72); assert.equal(p.data.showResult,false); assert.equal(requests.length,kind==='learning'?2:1)
    })
    await check(`${kind}: final forgotten answer is visible before settlement`, async()=>{
      const p=page(kind); let settlements=0; p.settle=()=>{settlements++;return Promise.resolve()}; p.finalize=()=>{settlements++;return Promise.resolve()}
      responses.push(good(response(item(),kind))); await p.submitForgot(event(p,kind)); assert.equal(settlements,0); assert.equal(p.data.showResult,true); assert.equal(p.data.finished,false)
      if(kind==='review') { p.nextItem(event(p,kind)); assert.equal(settlements,1) }
    })
  }
  await check('learning: timeout on final retry uses retry response rather than first result',async()=>{
    const q=item(),p=page('learning'); p.setData({phase:'retry'}); responses.push(timeout,good(learningQueue(null,{completed:true,phase:'complete',saved_response:response(q,'learning',{attempt_id:'vocabulary-group:42:retry:71'})})))
    await p.submitForgot(event(p,'learning')); assert.equal(p.data.correctAnswer,'word71'); assert.equal(p.data.showResult,true); assert.equal(p.data.finished,false); assert.equal(requests[0].data.retry,true)
  })
  await check('review: already-settled snapshot is restored without a second settlement',async()=>{
    const p=page('review'); responses.push(timeout,good(reviewSnapshot([savedReview(item())],{status:'settled',settlement:{accuracy:0,forgot_count:1,forgot_items:[]}})))
    await p.submitForgot(event(p,'review')); assert.equal(p.data.finished,true); assert.equal(p.data.result.accuracy,0); assert.equal(requests.length,2)
  })
  await check('learning: daily-review gate during timeout recovery still reveals saved forgotten answer',async()=>{
    const p=page('learning'); responses.push(timeout,good(learningQueue(null,{recovery_only:true,review_required:true,saved_response:response(item())})))
    await p.submitForgot(event(p,'learning')); assert.equal(p.data.showResult,true); assert.equal(p.data.correctAnswer,'word71'); assert.equal(redirects.length,0)
  })
  process.stdout.write(JSON.stringify({client,checks:records.length,passed:records.filter(r=>r.pass).length,results:records},null,2)+'\n')
  process.exitCode=records.some(r=>!r.pass)?1:0
})()
