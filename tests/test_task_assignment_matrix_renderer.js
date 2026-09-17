const assert = require('node:assert/strict')
const test = require('node:test')

const renderMatrix = require('../static/js/task_assignment_matrix.js')

test('question-type renderer keeps every student × requested group cell', () => {
  const result = {
    resource: {
      kind: 'question_type',
      units: [
        { id: 'G1', label: '题组 G1' },
        { id: 'G2', label: '题组 G2' }
      ]
    },
    students: [
      {
        student_name: '学生甲',
        matrix_rows: [
          { unit_id: 'G1', unit_label: '题组 G1', status_label: '已完成', overlap_type: 'exact', blocking: false, requires_confirmation: true, match: { task_id: 7, kind: 'question_type', status: 'completed', status_label: '已完成', overlap_type: 'partial', assigned_date: '2026-09-01', view_url: '/tasks/question-types/7/result', blocking: false, requires_confirmation: true } },
          { unit_id: 'G2', unit_label: '题组 G2', status: 'not_assigned', status_label: '未布置', match: null }
        ]
      },
      {
        student_name: '学生乙',
        matrix_rows: [
          { unit_id: 'G1', unit_label: '题组 G1', status: 'not_assigned', status_label: '未布置', match: null },
          { unit_id: 'G2', unit_label: '题组 G2', status: 'not_assigned', status_label: '未布置', match: null }
        ]
      }
    ]
  }
  const html = renderMatrix(result)
  assert.equal((html.match(/class="history-student-result/g) || []).length, 4)
  assert.equal((html.match(/学生甲 · 题组 G1/g) || []).length, 1)
  assert.equal((html.match(/学生甲 · 题组 G2/g) || []).length, 1)
  assert.equal((html.match(/学生乙 · 题组 G1/g) || []).length, 1)
  assert.equal((html.match(/学生乙 · 题组 G2/g) || []).length, 1)
  assert.match(html, /原任务 #7/)
  assert.match(html, /已完成 · 完全重复/)
  assert.match(html, /查看专项记录/)
  assert.doesNotMatch(html, /题组 G1[\s\S]*部分重复/)
  assert.equal((html.match(/未布置/g) || []).length, 3)
  assert.doesNotMatch(html, /token=/)
})

test('question-type renderer shows every matching task and trusts server decisions', () => {
  const html = renderMatrix({
    resource: { kind: 'question_type', units: [{ id: 'G1', label: '题组 G1' }] },
    students: [{
      student_name: '学生甲',
      matrix_rows: [{
        unit_id: 'G1',
        unit_label: '题组 G1',
        overlap_type: 'exact',
        blocking: false,
        requires_confirmation: false,
        match: null,
        matches: [
          { task_id: 9, kind: 'question_type', status: 'in_progress', status_label: '进行中', assigned_date: '2026-09-16', view_url: '/tasks/question-types/9/result', blocking: false, requires_confirmation: false, reassignable: true },
          { task_id: 8, kind: 'question_type', status: 'pending', status_label: '未开始', assigned_date: '2026-09-15', view_url: '/tasks/question-types/8/result', blocking: false, requires_confirmation: false, reassignable: true }
        ]
      }]
    }]
  })
  assert.match(html, /2 条历史/)
  assert.match(html, /原任务 #9/)
  assert.match(html, /原任务 #8/)
  assert.match(html, /可跨日再次布置/)
  assert.doesNotMatch(html, /is-blocking/)
  assert.equal((html.match(/查看专项记录/g) || []).length, 2)
  assert.doesNotMatch(html, /token=/)
})

test('question-type renderer uses server blocking instead of inferring from pending status', () => {
  const html = renderMatrix({
    resource: { kind: 'question_type', units: [{ id: 'G1', label: '题组 G1' }] },
    students: [{
      student_name: '学生甲',
      matrix_rows: [{
        unit_id: 'G1',
        unit_label: '题组 G1',
        overlap_type: 'exact',
        blocking: false,
        requires_confirmation: false,
        matches: [{ task_id: 1, kind: 'question_type', status: 'pending', status_label: '未开始', assigned_date: '2026-09-16', view_url: '/tasks/question-types/1/result', blocking: false, requires_confirmation: false }]
      }]
    }]
  })
  assert.doesNotMatch(html, /is-blocking/)
  assert.match(html, /可跨日再次布置/)
})

test('duplicate conflict maps to actionable Chinese copy without exposing the error code', () => {
  const message = renderMatrix.duplicateErrorMessage('duplicate_assignment_conflict')
  assert.match(message, /检测到重复任务：请查看下方历史记录/)
  assert.match(message, /二次确认并填写原因/)
  assert.doesNotMatch(message, /duplicate_assignment_conflict/)
  assert.equal(renderMatrix.duplicateErrorMessage('network_failure'), '')
})
