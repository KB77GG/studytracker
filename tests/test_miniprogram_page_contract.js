const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const root = path.resolve(__dirname, '..')
const miniRoot = path.join(root, 'miniprogram')

test('every page declared in app.json has a complete four-file bundle', () => {
    const appConfig = JSON.parse(fs.readFileSync(path.join(miniRoot, 'app.json'), 'utf8'))
    const pagePaths = [...(appConfig.pages || [])]
    for (const subpackage of appConfig.subpackages || []) {
        for (const page of subpackage.pages || []) {
            pagePaths.push(path.posix.join(subpackage.root, page))
        }
    }

    const missing = []
    for (const pagePath of pagePaths) {
        for (const extension of ['.js', '.json', '.wxml', '.wxss']) {
            const filePath = path.join(miniRoot, `${pagePath}${extension}`)
            if (!fs.existsSync(filePath)) missing.push(path.relative(root, filePath))
        }
    }

    assert.deepEqual(missing, [])
})
