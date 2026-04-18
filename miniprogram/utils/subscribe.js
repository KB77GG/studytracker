const getSubscribeSummary = (tmplIds = []) => new Promise((resolve) => {
    wx.getSetting({
        withSubscriptions: true,
        success: (res) => {
            const subscriptionsSetting = res.subscriptionsSetting || {}
            const itemSettings = subscriptionsSetting.itemSettings || {}
            const mainSwitch = subscriptionsSetting.mainSwitch !== false
            const statuses = {}
            tmplIds.forEach((id) => {
                statuses[id] = itemSettings[id] || ''
            })

            const accepted = tmplIds.filter((id) => statuses[id] === 'accept')
            const rejected = tmplIds.filter((id) => statuses[id] === 'reject')
            const banned = tmplIds.filter((id) => statuses[id] === 'ban')

            let state = 'unknown'
            if (!mainSwitch) {
                state = 'off'
            } else if (accepted.length === tmplIds.length && tmplIds.length > 0) {
                state = 'accept'
            } else if (accepted.length > 0) {
                state = 'partial'
            } else if (banned.length > 0) {
                state = 'ban'
            } else if (rejected.length > 0) {
                state = 'reject'
            }

            resolve({
                mainSwitch,
                statuses,
                state,
                acceptedCount: accepted.length,
                rejectedCount: rejected.length,
                bannedCount: banned.length
            })
        },
        fail: () => {
            resolve({
                mainSwitch: true,
                statuses: {},
                state: 'unknown',
                acceptedCount: 0,
                rejectedCount: 0,
                bannedCount: 0
            })
        }
    })
})

const requestTemplateSubscribe = (tmplIds = []) => new Promise((resolve, reject) => {
    wx.requestSubscribeMessage({
        tmplIds,
        success: (res) => resolve(res || {}),
        fail: (err) => reject(err)
    })
})

module.exports = {
    getSubscribeSummary,
    requestTemplateSubscribe
}
