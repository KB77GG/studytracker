'use strict';
// Independent black-box checks of the actual timing module, with deterministic
// clocks and fake browser storage. These are not native-device test claims.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ROOT = path.resolve(__dirname, '../../../..');
let ids = 0;
function storage() {
  const values = new Map();
  return {
    get length() { return values.size; },
    key(i) { return [...values.keys()][i] ?? null; },
    getItem(k) { return values.get(k) ?? null; },
    setItem(k, v) { values.set(k, String(v)); },
    removeItem(k) { values.delete(k); },
  };
}
function fixture(local = storage()) {
  const clock = { time: 1000000 };
  const win = { localStorage: local, crypto: { randomUUID: () => `independent-page-${++ids}` } };
  const sandbox = { window: win };
  for (const name of ['transport', 'timing']) vm.runInNewContext(
    fs.readFileSync(path.join(ROOT, `static/js/practice_vocabulary_${name}.js`), 'utf8'), sandbox);
  return { local, clock, make: (task = 1, user = 'synthetic-user') => new win.PracticeVocabularyTransport.Timing(task, user, () => clock.time) };
}
function learn(timer, review) {
  timer.observe(review == null ? { stage: 'learning' } : { stage: 'review', review: { session_id: review } });
  timer.setState(review == null ? 'question' : 'review_question');
}
function minutes(timer, clock, count) {
  for (let i = 0; i < count; i++) { clock.time += 60000; timer.activity(); }
}
const checks = [];
function check(name, run) {
  try { run(); checks.push({ name, ok: true }); }
  catch (error) { checks.push({ name, ok: false, error: error.message }); }
}

check('ten minutes + five-hour departure + fifteen minutes = twenty-five minutes', () => {
  const f = fixture(), first = f.make(); learn(first); minutes(first, f.clock, 10); first.visibility(false);
  f.clock.time += 5 * 60 * 60000;
  const next = f.make(); learn(next); minutes(next, f.clock, 15);
  assert.equal(next.snapshot(null), 25 * 60);
});
check('idle is capped at five minutes; resumed input never backfills idle gap', () => {
  const f = fixture(), t = f.make(); learn(t); f.clock.time += 10 * 60000; t.activity();
  f.clock.time += 60000; assert.equal(t.snapshot(null), 360);
});
check('hidden activity cannot renew or credit the hidden interval', () => {
  const f = fixture(), t = f.make(); learn(t); f.clock.time += 50000; t.visibility(false);
  f.clock.time += 3 * 60 * 60000; t.activity(); t.visibility(true);
  f.clock.time += 70000; assert.equal(t.snapshot(null), 120);
});
check('overlapping tabs use the union, in either flush order', () => {
  for (const reverse of [false, true]) {
    const f = fixture(), a = f.make(); learn(a); f.clock.time += 30000;
    const b = f.make(); learn(b); f.clock.time += 30000;
    if (reverse) b.tick(true); a.visibility(false); f.clock.time += 30000;
    assert.equal(b.snapshot(null), 90);
  }
});
check('review switch stops the old session; task retains both sessions', () => {
  const f = fixture(), t = f.make(); learn(t, 7); f.clock.time += 60000; learn(t, 8);
  f.clock.time += 60000;
  assert.equal(t.snapshot(7), 60); assert.equal(t.snapshot(8), 60); assert.equal(t.snapshot(null), 120);
});
check('task and identity isolate accumulated intervals', () => {
  const f = fixture(), a = f.make(1, 'a'); learn(a); f.clock.time += 60000; a.visibility(false);
  const b = f.make(1, 'b'), c = f.make(2, 'a'); learn(b); learn(c); f.clock.time += 20000;
  assert.equal(b.snapshot(null), 20); assert.equal(c.snapshot(null), 20); assert.equal(a.snapshot(null), 60);
});
check('late stale tab excludes frozen settlement wait after incomplete resume', () => {
  const f = fixture(), a = f.make(), b = f.make(); learn(a); learn(b);
  f.clock.time += 60000; assert.equal(a.snapshot(null), 60); assert.equal(b.snapshot(null), 60);
  f.clock.time += 60000; a.resume(null);
  f.clock.time += 60000; assert.equal(b.snapshot(null), 120); assert.equal(a.snapshot(null), 120);
});
check('refresh after frozen payload preserves seconds and adds no retry delay', () => {
  const f = fixture(), a = f.make(); learn(a); f.clock.time += 20000; assert.equal(a.snapshot(null), 20);
  a.visibility(false); f.clock.time += 10 * 60000;
  const b = f.make(); learn(b); f.clock.time += 60000; assert.equal(b.snapshot(null), 20);
});
check('completed value does not change on late finish or resume', () => {
  const f = fixture(), t = f.make(); learn(t); f.clock.time += 20000; t.finish(null, 20);
  f.clock.time += 20000; t.finish(null, 999); t.resume(null);
  assert.equal(t.snapshot(null), 20);
});
check('write failure keeps current-page intervals; restored storage survives reload', () => {
  const persisted = storage(); let fail = false;
  const wrapped = { get length() { return persisted.length; }, key: i => persisted.key(i), getItem: k => persisted.getItem(k), setItem(k,v) { if (fail) throw Error('synthetic quota'); persisted.setItem(k,v); } };
  const f = fixture(wrapped), t = f.make(); learn(t); fail = true;
  f.clock.time += 30000; t.tick(true); f.clock.time += 30000; t.tick(true);
  fail = false; t.visibility(false); const reloaded = f.make(); learn(reloaded);
  assert.equal(reloaded.snapshot(null), 60);
});
check('blocked/error/readonly/result views cannot accumulate after leaving learning', () => {
  for (const state of ['blocked', 'save_failed', 'settle_failed', 'read_only', 'locked_future', 'result']) {
    const f = fixture(), t = f.make(); learn(t); f.clock.time += 20000; t.setState(state);
    f.clock.time += 60000; t.activity(); f.clock.time += 60000;
    assert.equal(t.snapshot(null), 20, state);
  }
});
check('future or readonly domain state cannot start a timer even with question UI', () => {
  for (const access of [{ read_only: true }, { task_date_state: 'future' }, { can_write: false }]) {
    const f = fixture(), t = f.make(); t.observe({ stage: 'learning', access }); t.setState('question');
    f.clock.time += 60000; t.tick(true); assert.equal(t.entry(null, false), null);
  }
});
check('legacy wall-clock record is not converted into active learning time', () => {
  const f = fixture(); f.local.setItem('pv:1:synthetic-user:timer:task', JSON.stringify({ version:1, generation:0, startedAt:0, seconds:null, complete:false }));
  const t=f.make(); learn(t); f.clock.time += 60000; assert.equal(t.snapshot(null),60);
});
check('large forward clock jump never counts more than the idle grace window', () => {
  const f=fixture(), t=f.make(); learn(t); f.clock.time += 30 * 24 * 60 * 60000;
  assert.equal(t.snapshot(null),300);
});
check('damaged frozen value and future page ranges do not inflate time', () => {
  const f=fixture();
  f.local.setItem('pv:1:synthetic-user:active:v2:task', JSON.stringify({version:2,generation:0,windows:[[f.clock.time-1000,f.clock.time]],seconds:Number.MAX_SAFE_INTEGER,complete:false}));
  f.local.setItem('pv:1:synthetic-user:active:v2:task:page:corrupt', JSON.stringify({version:2,ranges:[[0,Number.MAX_SAFE_INTEGER]]}));
  const t=f.make(); learn(t); f.clock.time+=60000; assert.equal(t.snapshot(null),60);
});
check('actual event wiring ignores auto scroll/focus and repeated keys, honors IME and lifecycle', () => {
  const local=storage(), clock={time:1000000}, docListeners=new Map(), winListeners=new Map(), intervals=[];
  const on=(map,type,fn)=>{ if (!map.has(type)) map.set(type,[]); map.get(type).push(fn); };
  const fire=(map,type,event={})=>{ for(const fn of map.get(type)||[]) fn(event); };
  const control={addEventListener(){},closest(){return null;}};
  const dialog={open:false,querySelector:()=>control,showModal(){this.open=true;},close(){this.open=false;}};
  const doc={visibilityState:'visible',addEventListener:(type,fn)=>on(docListeners,type,fn),getElementById:id=>id==='pv-help-dialog'?dialog:control};
  const win={localStorage:local,crypto:{randomUUID:()=>`events-${++ids}`},addEventListener:(type,fn)=>on(winListeners,type,fn),setInterval(fn,ms){intervals.push({fn,ms});},PracticeVocabularyCore:require(path.join(ROOT,'static/js/practice_vocabulary_core.js'))};
  const sandbox={window:win,document:doc,setTimeout:fn=>fn(),Date:{now:()=>clock.time}};
  for(const name of ['transport','timing','events']) vm.runInNewContext(fs.readFileSync(path.join(ROOT,`static/js/practice_vocabulary_${name}.js`),'utf8'),sandbox);
  const t=new win.PracticeVocabularyTransport.Timing(1,'synthetic-user',()=>clock.time); learn(t);
  let refreshed=0, draftSaved=0, playerStopped=0;
  const app={timing:t,boot:{task_id:1},model:{state:'question',busy:false,q:null,audioUrl:''},feedbackUntil:0,player:{stop(){playerStopped++;}},view:{status(){}},saveDraft(){draftSaved++;},refresh(){refreshed++;},action(){}};
  win.PracticeVocabularyEvents.install(app);
  assert.equal(intervals.length,1); assert.equal(intervals[0].ms,5000);
  clock.time+=6*60000; fire(docListeners,'scroll',{isTrusted:true}); fire(winListeners,'focus'); intervals[0].fn();
  assert.equal(t.elapsed(null,t.entry(null)),300); assert.equal(refreshed,1);
  clock.time+=60000; fire(docListeners,'keydown',{isTrusted:true,repeat:true,key:'x',target:control,preventDefault(){}}); intervals[0].fn();
  assert.equal(t.elapsed(null,t.entry(null)),300);
  clock.time+=60000; fire(docListeners,'compositionstart',{isTrusted:true}); fire(docListeners,'input',{isTrusted:true,target:{id:'pv-answer',value:'词'}}); fire(docListeners,'compositionend',{isTrusted:true});
  clock.time+=60000; intervals[0].fn(); assert.equal(t.elapsed(null,t.entry(null)),360);
  doc.visibilityState='hidden'; fire(docListeners,'visibilitychange'); clock.time+=10*60000;
  fire(docListeners,'pointerdown',{isTrusted:true}); intervals[0].fn(); assert.equal(t.elapsed(null,t.entry(null)),360);
  doc.visibilityState='visible'; fire(winListeners,'pageshow'); clock.time+=20000; intervals[0].fn();
  assert.equal(t.elapsed(null,t.entry(null)),380);
  fire(winListeners,'pagehide'); clock.time+=60000; intervals[0].fn(); assert.equal(t.elapsed(null,t.entry(null)),380);
  assert.ok(draftSaved>=2); assert.equal(playerStopped,1);
});

const output = { kind:'independent mocked-clock timing probe', checks, passed:checks.filter(x=>x.ok).length, total:checks.length };
console.log(JSON.stringify(output, null, 2));
process.exitCode = output.passed === output.total ? 0 : 1;
