function toPositiveInt(value, fallback) {
    const parsed = Number(value)
    return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : fallback
}

function buildFixedGroupSizes(totalValue, targetValue) {
    const total = toPositiveInt(totalValue, 0)
    const target = toPositiveInt(targetValue, total)
    if (!total || target >= total) return total ? [total] : []

    const sizes = []
    let remaining = total
    while (remaining > target) {
        const tail = remaining - target
        if (tail <= Math.ceil(target / 2)) {
            sizes.push(remaining)
            remaining = 0
            break
        }
        sizes.push(target)
        remaining = tail
    }
    if (remaining > 0) sizes.push(remaining)
    return sizes
}

function buildGroupPlans(totalValue) {
    const total = toPositiveInt(totalValue, 0)
    if (!total) return []

    const candidates = [[total]]
    if (total > 20) candidates.push(buildFixedGroupSizes(total, 20))
    if (total > 30) candidates.push(buildFixedGroupSizes(total, Math.ceil(total / 2)))
    if (total > 10) candidates.push(buildFixedGroupSizes(total, 10))

    const seen = {}
    const plans = []
    candidates.forEach((sizes) => {
        const key = sizes.join('_')
        if (!key || seen[key]) return
        seen[key] = true
        plans.push({
            key,
            sizes,
            label: sizes.join(' + '),
            groupCount: sizes.length,
            description: sizes.length === 1 ? `一次完成 ${total} 词` : `分 ${sizes.length} 组完成`,
            recommended: sizes.length > 1 && sizes[0] === 20
        })
    })
    return plans
}

function normalizeGroupSizes(sizesValue, totalValue) {
    const total = toPositiveInt(totalValue, 0)
    if (!total || !Array.isArray(sizesValue)) return total ? [total] : []
    const sizes = sizesValue.map(value => toPositiveInt(value, 0)).filter(Boolean)
    return sizes.reduce((sum, value) => sum + value, 0) === total ? sizes : [total]
}

function groupBounds(sizesValue, groupIndexValue) {
    const sizes = Array.isArray(sizesValue) ? sizesValue : []
    const lastIndex = Math.max(0, sizes.length - 1)
    const parsedIndex = Number(groupIndexValue)
    const groupIndex = Math.max(0, Math.min(Number.isFinite(parsedIndex) ? Math.floor(parsedIndex) : 0, lastIndex))
    const start = sizes.slice(0, groupIndex).reduce((sum, value) => sum + value, 0)
    const size = sizes[groupIndex] || 0
    return { groupIndex, start, end: start + size, size }
}

function findGroupIndex(sizesValue, wordIndexValue) {
    const sizes = Array.isArray(sizesValue) ? sizesValue : []
    const wordIndex = Math.max(0, Number(wordIndexValue) || 0)
    let end = 0
    for (let index = 0; index < sizes.length; index += 1) {
        end += sizes[index]
        if (wordIndex < end) return index
    }
    return Math.max(0, sizes.length - 1)
}

module.exports = {
    buildFixedGroupSizes,
    buildGroupPlans,
    findGroupIndex,
    groupBounds,
    normalizeGroupSizes
}
