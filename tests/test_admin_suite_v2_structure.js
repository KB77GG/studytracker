const assert = require('node:assert/strict')
const fs = require('node:fs')
const test = require('node:test')

function read(path) {
  return fs.readFileSync(path, 'utf8')
}

const base = read('templates/base.html')
const shellCss = read('static/admin_suite_v2.css')
const shellJs = read('static/js/admin_suite_v2.js')
const entrance = read('entrance_web/admin/invitations.html')

test('shared Direction 2 shell is wired for staff pages', () => {
  assert.match(base, /admin_suite_v2\.css/)
  assert.match(base, /admin_suite_v2\.js/)
  assert.match(base, /admin-suite-v2/)
  assert.match(base, /brand\/sagepath-mark\.png/)
  assert.match(base, /tasks-header-wave\.png|suite-header-search/)
  assert.match(shellCss, /--suite-navy:/)
  assert.match(shellCss, /\.brand-icon \{[\s\S]*?background: #fffaf2/)
  assert.match(shellCss, /\.suite-workspace/)
  assert.match(shellCss, /width: min\(100%, 1680px\)/)
  assert.match(shellJs, /admin-suite:search/)
  assert.match(entrance, /src="\/static\/brand\/sagepath-mark\.png"/)
  assert.doesNotMatch(entrance, /class="entrance-brand"><img src="\.\.\/assets\/logo\.png"/)
})

test('every sidebar destination has the selected design structure', () => {
  const routes = {
    materials: ['templates/materials.html', /materials-suite/, /materialInspector/],
    vocabulary: ['templates/word_examples.html', /vocabulary-suite/, /reviewInspector/],
    tasks: ['templates/tasks.html', /task-list-inspector/, /task-inspector/],
    grading: ['templates/teacher/grading_list.html', /grading-suite/, /gradingInspector/],
    plans: ['templates/admin/course_plan_list.html', /course-plan-suite/, /planEdit/],
    practice: ['templates/practice/index_content.html', /practice-suite-filters/, /practice-suite-preview/],
    mockExams: ['templates/admin/mock_exams_index.html', /mock-suite/, /mockResults/],
    entrance: ['entrance_web/admin/invitations.html', /entrance-workspace/, /entrance-inspector/],
    report: ['templates/report.html', /report-filter-panel/, /charts-grid/],
    stageReports: ['templates/admin/stage_report_list.html', /stage-report-suite/, /reportEdit/],
    bulk: ['templates/bulk.html', /bulk-suite/, /bulk-check-stats/],
    users: ['templates/users.html', /users-inspector/, /userInspectorReport/]
  }
  for (const [name, [path, listPattern, detailPattern]] of Object.entries(routes)) {
    const source = read(path)
    assert.match(source, listPattern, `${name} lacks its primary workspace`)
    assert.match(source, detailPattern, `${name} lacks its detail or supporting pane`)
  }
})

test('task workspace uses natural desktop proportions instead of the compressed cascade', () => {
  const css = read('static/tasks_workspace_final.css')
  assert.match(css, /task-subtable tbody tr\{[\s\S]*?min-height:68px !important/)
  assert.match(css, /task-filter-bar\{[\s\S]*?min-height:68px !important/)
  assert.doesNotMatch(css, /grid-template-rows:46px !important/)
  assert.doesNotMatch(css, /height:clamp\(460px, calc\(100vh - 564px\), 500px\)/)
})
