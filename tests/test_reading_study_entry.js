const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')
const modes = require('../static/js/practice_modes.js')

const template = fs.readFileSync(path.join(__dirname, '../templates/reading/test_practice.html'), 'utf8')
const reveal = template.match(/async function revealReadingStudyEntry\(\) \{[\s\S]*?\n\}/)[0]

function fixture(mode = 'practice') {
  const entry = {
    dataset: { capability: 'canUseReadingStudy', revealWhenReady: 'false' },
    hidden: true,
    setAttribute(name, value) { this[name] = value }
  }
  const doc = { getElementById: () => entry, querySelectorAll: () => [entry] }
  const context = {
    document: doc, rawTestData: { id: 'synthetic_test' },
    experienceCapabilities: modes.capabilities(mode),
    fetch: async () => ({ ok: true, json: async () => ({ passages: [] }) })
  }
  const apply = (nextMode) => { context.experienceCapabilities = modes.apply(doc, nextMode) }
  return { entry, context, apply, run: () => vm.runInNewContext(reveal + '\nrevealReadingStudyEntry()', context) }
}

test('no analysis stays hidden after capability application and review transition', async () => {
  const page = fixture()
  page.apply('practice')
  assert.equal(page.entry.hidden, true)
  await page.run()
  page.apply('review')
  assert.equal(page.entry.hidden, true)
  assert.equal(page.entry['aria-hidden'], 'true')
})

test('ready analysis becomes available and survives repeat mode application', async () => {
  const page = fixture()
  page.context.fetch = async () => ({ ok: true, json: async () => ({ passages: [{}] }) })
  await page.run()
  assert.equal(page.entry.hidden, false)
  page.apply('review')
  assert.equal(page.entry.hidden, false)
  assert.equal(page.entry['aria-hidden'], 'false')
})

test('late catalog response cannot reveal study in simulation; leaving simulation restores ready entry', async () => {
  const page = fixture()
  let resolveFetch
  page.context.fetch = () => new Promise((resolve) => { resolveFetch = resolve })
  const pending = page.run()
  page.apply('simulation')
  resolveFetch({ ok: true, json: async () => ({ passages: [{}] }) })
  await pending
  assert.equal(page.entry.hidden, true)
  assert.equal(page.entry['aria-hidden'], 'true')
  page.apply('review')
  assert.equal(page.entry.hidden, false)
})

test('entering simulation hides an already ready analysis entry', async () => {
  const page = fixture()
  page.context.fetch = async () => ({ ok: true, json: async () => ({ passages: [{}] }) })
  await page.run()
  page.apply('simulation')
  assert.equal(page.entry.hidden, true)
})

for (const [name, fetch] of Object.entries({
  'non-200': async () => ({ ok: false }),
  'network failure': async () => { throw new Error('offline') },
  'invalid catalog shape': async () => ({ ok: true, json: async () => ({ passages: 'not an array' }) })
})) {
  test(`${name} never reveals the entry`, async () => {
    const page = fixture()
    page.context.fetch = fetch
    await page.run()
    page.apply('practice')
    assert.equal(page.entry.hidden, true)
  })
}
