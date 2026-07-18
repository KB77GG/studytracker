const assert = require('assert')
const fs = require('fs')
const path = require('path')
const { getLegalDocument } = require('../miniprogram/utils/legal-documents.js')

const root = path.join(__dirname, '..')
const appConfig = JSON.parse(fs.readFileSync(path.join(root, 'miniprogram/app.json'), 'utf8'))
const loginMarkup = fs.readFileSync(
    path.join(root, 'miniprogram/pages/index/index.wxml'),
    'utf8'
)

const terms = getLegalDocument('terms')
const privacy = getLegalDocument('privacy')

assert.strictEqual(terms.title, '用户协议')
assert.strictEqual(privacy.title, '隐私政策')
assert.ok(terms.sections.length >= 5)
assert.ok(privacy.sections.length >= 6)
assert.strictEqual(privacy.showOfficialGuide, true)
assert.strictEqual(getLegalDocument('unknown'), terms)

assert.ok(appConfig.pages.includes('pages/legal/index'))
assert.ok(loginMarkup.includes('bindtap="openUserAgreement"'))
assert.ok(loginMarkup.includes('bindtap="openPrivacyPolicy"'))
assert.ok(loginMarkup.includes('open-type="agreePrivacyAuthorization"'))
assert.ok(loginMarkup.includes('bindagreeprivacyauthorization="handlePrivacyAuthorization"'))

let pageDefinition = null
let navigatedTo = ''
global.getApp = () => ({ globalData: { baseUrl: '', token: null } })
global.wx = {
    navigateTo(options) {
        navigatedTo = options.url
    },
    showToast() {}
}
global.Page = definition => {
    pageDefinition = definition
}

require('../miniprogram/pages/index/index.js')

const navigationContext = {
    openLegalDocument: pageDefinition.openLegalDocument
}
pageDefinition.openUserAgreement.call(navigationContext)
assert.strictEqual(navigatedTo, '/pages/legal/index?type=terms')
pageDefinition.openPrivacyPolicy.call(navigationContext)
assert.strictEqual(navigatedTo, '/pages/legal/index?type=privacy')

let loginCalls = 0
const authorizationContext = {
    data: { privacyAgreed: true, privacyNeedAuth: true },
    setData(next) {
        Object.assign(this.data, next)
    },
    loginWithWechat() {
        loginCalls += 1
    }
}
pageDefinition.handlePrivacyAuthorization.call(authorizationContext)
assert.strictEqual(authorizationContext.data.privacyNeedAuth, false)
assert.strictEqual(loginCalls, 1)

console.log('miniprogram legal link tests passed')
