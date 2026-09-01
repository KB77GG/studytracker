const assert = require('node:assert/strict')
const fs = require('node:fs')
const test = require('node:test')

const tasksTemplate = fs.readFileSync('templates/tasks.html', 'utf8')
const baseTemplate = fs.readFileSync('templates/base.html', 'utf8')
const workspaceCss = fs.readFileSync('static/tasks_workspace.css', 'utf8')
const finalCss = fs.readFileSync('static/tasks_workspace_final.css', 'utf8')
const workspaceJs = fs.readFileSync('static/js/tasks_workspace.js', 'utf8')

test('tasks workspace keeps direction 2 above-the-fold composition', () => {
  const order = [
    'task-period-tabs',
    'task-date-strip',
    'task-filter-bar',
    'task-list-inspector',
    'task-inspector'
  ].map(className => tasksTemplate.indexOf(className))
  assert.ok(order.every(index => index >= 0))
  assert.ok(order.every((index, position) => position === 0 || index > order[position - 1]))
  assert.doesNotMatch(tasksTemplate, /任务记录与计时/)
  assert.doesNotMatch(tasksTemplate, /<div class="student-group[" ]/)
  assert.match(tasksTemplate, /block page_subtitle %}TASKS/)
  assert.match(tasksTemplate, /block page_description %}布置、追踪并调整学生学习任务/)
  assert.match(tasksTemplate, /taskInspectorEdit[^>]+btn btn-primary/)
  assert.match(tasksTemplate, /taskInspectorProgress[^>]+btn btn-secondary/)
  assert.match(tasksTemplate, /task-assignment-drawer__body[\s\S]*task-form-row--publish/)
  for (const source of ['custom', 'material', 'listening', 'reading', 'question_type']) {
    assert.match(tasksTemplate, new RegExp(`value="${source}"`))
  }
})

test('tasks workspace exposes real navigation assets and responsive behaviors', () => {
  assert.match(baseTemplate, /brand\/sagepath-mark\.png/)
  assert.match(baseTemplate, /nav-link__icon fas fa-clipboard-list/)
  assert.match(tasksTemplate, /tasks_workspace\.css/)
  assert.match(tasksTemplate, /tasks_workspace_final\.css/)
  assert.match(tasksTemplate, /tasks_workspace\.js/)
  assert.match(workspaceCss, /tasks-header-wave\.png/)
  assert.match(workspaceCss, /task-inspector-mobile-open/)
  assert.match(workspaceCss, /task-form-row--publish/)
  assert.match(workspaceCss, /task-assignment-meta/)
  assert.match(workspaceCss, /task-subtable tbody td\.task-status,\s*\n?\s*\.task-subtable tbody td\.task-deadline\{ display:block !important/)
  assert.match(workspaceCss, /task-list-toolbar\{ display:none !important/)
  assert.match(workspaceCss, /height:clamp\(350px, calc\(100vh - 365px\), 660px\)/)
  assert.match(finalCss, /task-list-inspector \.task-subtable tbody tr td\.task-status,[\s\S]*?task-deadline\{[\s\S]*?display:block !important/)
  assert.match(finalCss, /task-list-inspector \.task-subtable tbody tr td\.task-deadline\{[\s\S]*?display:block !important/)
  assert.match(finalCss, /min-height:154px !important/)
  assert.match(finalCss, /task-period-tabs\{[\s\S]*?min-height:55px !important/)
  assert.match(finalCss, /task-date-choice\{[\s\S]*?min-height:46px !important/)
  assert.match(finalCss, /task-subtable tbody tr\{[\s\S]*?min-height:68px !important/)
  assert.match(finalCss, /grid-template-rows:minmax\(52px, auto\) !important/)
  assert.match(finalCss, /task-list-footer\{[\s\S]*?min-height:54px !important/)
  assert.match(finalCss, /taskInspectorEdit,[\s\S]*?grid-column:auto !important/)
  assert.match(finalCss, /task-assignment-drawer[^\{]*\{[\s\S]*?grid-template-rows:auto minmax\(0,1fr\) auto !important/)
  assert.match(finalCss, /task-assignment-drawer[^\{]*task-assignment-drawer__body[^\{]*\{[\s\S]*?overflow-y:auto/)
  assert.match(finalCss, /task-assignment-drawer[^\{]*task-assignment-drawer__body[^\{]*\{[\s\S]*?padding:0 0 16px/)
  assert.match(finalCss, /task-assignment-drawer[^\{]*\{[\s\S]*?align-items:stretch !important/)
  assert.match(finalCss, /task-assignment-drawer[^\{]*task-form-row--publish[^\{]*\{[\s\S]*?position:static !important/)
  assert.match(finalCss, /task-assignment-drawer[^\{]*task-form-row--publish[^\{]*\{[\s\S]*?grid-row:3/)
  assert.match(finalCss, /height:clamp\(510px, calc\(100vh - 378px\), 680px\) !important/)
  assert.match(finalCss, /@media \(min-width:1400px\)[\s\S]*?grid-template-columns:minmax\(0,1fr\) 390px !important/)
  assert.match(workspaceJs, /taskWorkspaceApplyPagination/)
  assert.match(workspaceJs, /task-date-choice/)
})
