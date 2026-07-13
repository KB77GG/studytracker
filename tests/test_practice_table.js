const assert = require('assert')
const PracticeTable = require('../static/js/practice_table.js')
const { tableLayout } = require('../miniprogram/utils/practice-table.js')

const source = {
  content: [
    ['<bc>MEMBERSHIP SCHEMES</bc>', [0, 0], [0, 0]],
    ['<b>Type</b>', '<b>Cost</b>', '<b>Time</b>'],
    ['Gold', '$15$', 'Anytime']
  ]
}

const webLayout = PracticeTable.layout(source)
assert.strictEqual(webLayout.column_count, 3)
assert.strictEqual(webLayout.rows[0][0].colspan, 3)
assert.strictEqual(webLayout.rows[1][0].is_header, true)

const html = PracticeTable.withPlaceholders(
  '<b>Cost</b>: $15$ <script>alert(1)</script>',
  id => `<input aria-label="Question ${id} answer">`
)
assert.ok(html.includes('<strong>Cost</strong>'))
assert.ok(html.includes('aria-label="Question 15 answer"'))
assert.ok(html.includes('&lt;script&gt;alert(1)&lt;/script&gt;'))
assert.ok(!html.includes('<script>'))

const miniLayout = tableLayout(source)
assert.strictEqual(miniLayout.columnCount, 3)
assert.strictEqual(miniLayout.cells[0].colspan, 3)
assert.ok(miniLayout.cells[0].gridStyle.includes('span 3'))
assert.ok(miniLayout.tableStyle.includes('repeat(3'))

console.log('practice table renderer tests passed')
