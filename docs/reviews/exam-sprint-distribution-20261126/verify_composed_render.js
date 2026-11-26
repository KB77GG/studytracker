'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { templateRuntime, controls } = require('../../../tests/helpers/practice_template_runtime.js');
const documents = JSON.parse(fs.readFileSync(0,'utf8'));
let questions=0, images=0, placeholders=0;
for (const {subject,payload} of documents) {
 const ctx=templateRuntime(subject,payload);
 const units=payload[subject==='listening'?'sections':'passages'];
 for (let part=0;part<units.length;part++) for (const group of units[part].groups) {
   const html=ctx.renderGroup(group,part);
   const fields=controls(html,subject);
   for (const question of group.questions) {
     assert.ok(fields.some(field => field.id.split(',').includes(String(question.id))),`${subject} missing ${question.id}`);
     questions++;
   }
   if (group.img_url?.startsWith('/practice/sprint/assets/')) { assert.ok(html.includes(group.img_url)); images++; }
   for (const match of String(group.collect || '').matchAll(/\$([^$\s]+)\$/g)) {
     assert.ok(!html.includes(match[0]),`unreplaced ${match[0]}`); placeholders++;
   }
 }
}
const template=fs.readFileSync(path.join(__dirname,'../../../templates/listening/test_practice.html'),'utf8');
const start=template.indexOf('function sectionAudioUrl(');
const ctx={audioBase:'/static/listening/'};vm.createContext(ctx);
vm.runInContext(template.slice(start,template.indexOf('\n}',start)+2),ctx);
assert.equal(ctx.sectionAudioUrl({audio:'c20/test.mp3'}),'/static/listening/c20/test.mp3');
assert.equal(ctx.sectionAudioUrl({audio:'/practice/sprint/assets/hash.mp3'}),'/practice/sprint/assets/hash.mp3');
assert.equal(ctx.sectionAudioUrl({audio:'/static/listening_jijing/audio/a.mp3'}),'/static/listening_jijing/audio/a.mp3');
console.log(JSON.stringify({passed:true,documents:documents.length,questions,images,placeholders}));
