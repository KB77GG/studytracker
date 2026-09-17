const { getLegalDocument } = require('../../utils/legal-documents.js')

Page({
    data: {
        legal: getLegalDocument('terms')
    },

    onLoad(options) {
        const legal = getLegalDocument(options && options.type)
        this.setData({ legal })
        wx.setNavigationBarTitle({ title: legal.title })
    },

    openOfficialPrivacyGuide() {
        if (typeof wx.openPrivacyContract !== 'function') {
            wx.showModal({
                title: '当前版本暂不支持',
                content: '你仍可阅读本页隐私政策；升级微信后可查看微信隐私保护指引。',
                showCancel: false
            })
            return
        }

        wx.openPrivacyContract({
            fail: (error) => {
                console.warn('open privacy contract failed', error)
                wx.showModal({
                    title: '暂时无法打开',
                    content: '你仍可阅读本页隐私政策，请稍后再试。',
                    showCancel: false
                })
            }
        })
    }
})
