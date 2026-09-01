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
          { unit_id: 'G1', unit_label: '题组 G1', status_label: '已完成', overlap_type: 'exact', match: { task_id: 7, status: 'done', status_label: '已完成', overlap_type: 'partial', assigned_date: '2026-09-01', view_url: '/tasks/7/review' } },
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
  assert.doesNotMatch(html, /题组 G1[\s\S]*部分重复/)
  assert.equal((html.match(/未布置/g) || []).length, 3)
  assert.doesNotMatch(html, /token=/)
})

test('duplicate conflict maps to actionable Chinese copy without exposing the error code', () => {
  const message = renderMatrix.duplicateErrorMessage('duplicate_assignment_conflict')
  assert.match(message, /检测到重复任务：请查看下方历史记录/)
  assert.match(message, /二次确认并填写原因/)
  assert.doesNotMatch(message, /duplicate_assignment_conflict/)
  assert.equal(renderMatrix.duplicateErrorMessage('network_failure'), '')
})
