const assert = require('assert')
const fs = require('fs')
const path = require('path')
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

const structured = PracticeTable.withStructuredPlaceholders(
  '<table class="w-full" onclick="alert(1)"><tr data-row="unsafe"><th colspan="2" style="color:red">Heading</th></tr><tr><td rowspan="2">$1$</td><td><img src=x onerror=alert(1)></td></tr><tr><td>$2$</td></tr></table>',
  id => `<input data-question="${id}">`
)
assert.ok(structured.includes('<div class="table-wrap practice-embedded-table-wrap"><table class="practice-table practice-embedded-table">'))
assert.ok(structured.includes('<th colspan="2">Heading</th>'))
assert.ok(structured.includes('<td rowspan="2"><input data-question="1"></td>'))
assert.ok(structured.includes('<td><input data-question="2"></td>'))
assert.ok(structured.includes('&lt;img src=x onerror=alert(1)&gt;'))
assert.ok(!structured.includes('onclick='))
assert.ok(!structured.includes('data-row='))
assert.ok(!structured.includes('style='))
assert.ok(!structured.includes('<img'))

const encodedBlocks = PracticeTable.withStructuredPlaceholders(
  '&lt;p class="unsafe"&gt;Intro&lt;/p&gt;&lt;ul onclick="bad()"&gt;&lt;li&gt;$7$&lt;/li&gt;&lt;/ul&gt;',
  id => `<input data-question="${id}">`
)
assert.ok(encodedBlocks.includes('<p class="practice-richtext-block">Intro</p>'))
assert.ok(encodedBlocks.includes('<ul class="practice-richtext-list"><li><input data-question="7"></li></ul>'))
assert.ok(!encodedBlocks.includes('unsafe'))
assert.ok(!encodedBlocks.includes('onclick'))

const malformedStructure = PracticeTable.withStructuredPlaceholders(
  '<td>orphan</td><ul><div>wrong parent</div><li>$8$</li></ul><table><tr><td>kept<td>escaped</td></tr></table>',
  id => `<input data-question="${id}">`
)
assert.ok(malformedStructure.includes('&lt;td&gt;orphan&lt;/td&gt;'))
assert.ok(malformedStructure.includes('<ul class="practice-richtext-list">&lt;div&gt;wrong parent&lt;/div&gt;<li><input data-question="8"></li></ul>'))
assert.ok(malformedStructure.includes('<table class="practice-table practice-embedded-table"><tr><td>kept</td><td>escaped</td></tr>'))
assert.ok(!malformedStructure.includes('<td>orphan'))

const boundedSpans = PracticeTable.withStructuredPlaceholders(
  '<table><colgroup><col span="3"><col span="0"></colgroup><tr><th scope="row" rowspan="2" colspan="101">A</th><td rowspan="0">B</td><td rowspan="-1" colspan="2.5">C</td></tr></table>',
  () => ''
)
assert.ok(boundedSpans.includes('<col span="3"><col>'))
assert.ok(boundedSpans.includes('<th scope="row" rowspan="2">A</th>'))
assert.ok(boundedSpans.includes('<td rowspan="0">B</td>'))
assert.ok(boundedSpans.includes('<td>C</td>'))
assert.ok(!boundedSpans.includes('101'))
assert.ok(!boundedSpans.includes('-1'))
assert.ok(!boundedSpans.includes('2.5'))

const optionalTableClosures = PracticeTable.withStructuredPlaceholders(
  '<table><tr><td>A<td>$1$</tr><tr><td>B<td>$2$</table>',
  id => `<input data-question="${id}">`
)
assert.strictEqual((optionalTableClosures.match(/<tr>/g) || []).length, 2)
assert.strictEqual((optionalTableClosures.match(/<td>/g) || []).length, 4)
assert.strictEqual((optionalTableClosures.match(/data-question=/g) || []).length, 2)
assert.ok(!optionalTableClosures.includes('&lt;td'))
assert.ok(!optionalTableClosures.includes('&lt;tr'))

const formattedTable = PracticeTable.withStructuredPlaceholders(
  '<table>\n<tr>\n<td>$1$</td>\n</tr>\n</table>',
  id => `<input data-question="${id}">`
)
assert.strictEqual((formattedTable.match(/<br>/g) || []).length, 0)
assert.ok(formattedTable.includes('<table class="practice-table practice-embedded-table"><tr><td><input data-question="1"></td></tr></table>'))

const optionalParagraphClose = PracticeTable.withStructuredPlaceholders(
  '<table><tr><td><p>A</td><td>$1$</td></tr><tr><td>B</td><td>$2$</td></tr></table>',
  id => `<input data-question="${id}">`
)
assert.strictEqual((optionalParagraphClose.match(/<tr>/g) || []).length, 2)
assert.strictEqual((optionalParagraphClose.match(/<td>/g) || []).length, 4)
assert.strictEqual((optionalParagraphClose.match(/data-question=/g) || []).length, 2)
assert.ok(!optionalParagraphClose.includes('&lt;/td'))

const optionalColgroupClose = PracticeTable.withStructuredPlaceholders(
  '<table><colgroup><col span="2"><tbody><tr><td>$1$</td><td>$2$</td></tr></tbody></table>',
  id => `<input data-question="${id}">`
)
assert.strictEqual((optionalColgroupClose.match(/<colgroup>/g) || []).length, 1)
assert.strictEqual((optionalColgroupClose.match(/<tr>/g) || []).length, 1)
assert.strictEqual((optionalColgroupClose.match(/<td>/g) || []).length, 2)
assert.strictEqual((optionalColgroupClose.match(/data-question=/g) || []).length, 2)
assert.ok(!optionalColgroupClose.includes('&lt;tbody'))

const cellBoundary = PracticeTable.withPlaceholders(
  'safe</td><td onclick="breakout()">$3$',
  id => `<input data-question="${id}">`
)
assert.ok(cellBoundary.includes('safe&lt;/td&gt;&lt;td onclick=&quot;breakout()&quot;&gt;'))
assert.ok(cellBoundary.includes('<input data-question="3">'))
assert.ok(!cellBoundary.includes('</td>'))
assert.ok(!cellBoundary.includes('<td'))

const missingLayout = JSON.parse(fs.readFileSync(
  path.join(__dirname, '..', 'static', 'listening_jijing', 'parts', 'jijing_76_test_113_part_3_1308.json'),
  'utf8'
)).groups.find(group => Number(group.group_id) === 2903)
const sourceMarkers = new Set(Array.from(
  String(missingLayout.collect || '').matchAll(/\$([^$\s]+)\$/g),
  match => String(match[1])
))
assert.deepStrictEqual(
  PracticeTable.unmappedItems(missingLayout.items, sourceMarkers).map(item => Number(item.number)),
  [27, 28, 29, 30]
)
assert.deepStrictEqual(
  PracticeTable.unmappedItems([{ number: 3 }, { id: 4, number: 4 }], new Set(['3'])),
  [{ id: 4, number: 4 }]
)

const reading = JSON.parse(fs.readFileSync(
  path.join(__dirname, '..', 'static', 'reading_tests', 'ielts21_test2_reading.json'),
  'utf8'
))
const sleepTable = reading.passages[0].groups[0]
const sleepHtml = PracticeTable.withStructuredPlaceholders(
  sleepTable.collect,
  id => `<input data-question="${id}">`
)
assert.ok(sleepHtml.includes('<table class="practice-table practice-embedded-table">'))
assert.ok(!sleepHtml.includes('&lt;table'))
assert.ok(!sleepHtml.includes('&lt;tr'))
assert.ok(!sleepHtml.includes('&lt;td'))
const renderedCells = Array.from(sleepHtml.matchAll(/<t[dh]\b[^>]*>([\s\S]*?)<\/t[dh]>/g), match => match[1])
const expectedCellByQuestion = {
  40233: 6,
  40234: 10,
  40235: 13,
  40236: 13,
  40237: 14
}
for (const [id, cellIndex] of Object.entries(expectedCellByQuestion)) {
  assert.strictEqual(
    renderedCells.filter(cell => cell.includes(`data-question="${id}"`)).length,
    1,
    `Question ${id} should render once in one cell`
  )
  assert.ok(renderedCells[cellIndex].includes(`data-question="${id}"`), `Question ${id} cell mapping`)
}
assert.strictEqual((sleepHtml.match(/<tr>/g) || []).length, 5)
assert.strictEqual((sleepHtml.match(/<th>/g) || []).length, 3)
assert.strictEqual((sleepHtml.match(/<td>/g) || []).length, 12)
assert.strictEqual((sleepHtml.match(/data-question=/g) || []).length, 5)

const miniLayout = tableLayout(source)
assert.strictEqual(miniLayout.columnCount, 3)
assert.strictEqual(miniLayout.cells[0].colspan, 3)
assert.ok(miniLayout.cells[0].gridStyle.includes('span 3'))
assert.ok(miniLayout.tableStyle.includes('repeat(3'))

console.log('practice table renderer tests passed')
