function hasSectionNumber(value) {
    return value !== undefined && value !== null && value !== ''
}

function getTestParts(test) {
    if (!test) return []
    if (Array.isArray(test.parts)) return test.parts
    if (Array.isArray(test.sections)) return test.sections
    return []
}

function findIntensiveTest(catalog, testId) {
    for (const book of Array.isArray(catalog) ? catalog : []) {
        for (const test of Array.isArray(book.tests) ? book.tests : []) {
            // The catalog is the source of truth for both ielts... and jfdr... ids.
            if (test && test.id === testId) return { book, test }
        }
    }
    return null
}

function findMatchingIntensiveParts(catalog, listeningTask) {
    if (!listeningTask || listeningTask.source_type !== 'cambridge_listening') return []
    const match = findIntensiveTest(catalog, listeningTask.listening_exercise_id)
    if (!match) return []

    const sectionNumber = listeningTask.listening_section_number
    return getTestParts(match.test).filter(part => {
        if (!part || !part.id) return false
        if (!hasSectionNumber(sectionNumber)) return true
        return String(part.number) === String(sectionNumber)
    })
}

function buildQueueItem(match, part) {
    const bookLabel = (match.book && match.book.label) || `剑雅 ${match.test.book}`
    const partLabel = part.part_title || part.name || part.title || `Part ${part.number}`
    const detail = part.title || `${match.test.title || `Test ${match.test.test}`} ${partLabel}`
    const exerciseId = part.id
    return {
        key: `listening_intensive:${exerciseId}`,
        source_type: 'listening_intensive',
        practice_test_id: match.test.id,
        practice_exercise_id: exerciseId,
        practice_scope: 'part',
        practice_section_number: null,
        practice_passage_number: null,
        practice_part_number: part.number || null,
        category: '雅思-听力-精听',
        detail,
        plannedMinutes: 20,
        summary: `${bookLabel} Test ${match.test.test} · ${partLabel}`
    }
}

function buildIntensiveQueueItems({
    catalog,
    listeningTask,
    selectedPracticeList = [],
    existingTasks = [],
    date
}) {
    const match = findIntensiveTest(catalog, listeningTask && listeningTask.listening_exercise_id)
    if (!match || !listeningTask || listeningTask.source_type !== 'cambridge_listening') return []

    const sectionNumber = listeningTask.listening_section_number
    const parts = getTestParts(match.test).filter(part => {
        if (!part || !part.id) return false
        if (!hasSectionNumber(sectionNumber)) return true
        return String(part.number) === String(sectionNumber)
    })
    const queuedIds = new Set(
        (Array.isArray(selectedPracticeList) ? selectedPracticeList : [])
            .map(item => item && item.practice_exercise_id)
            .filter(Boolean)
    )
    const assignedIds = new Set(
        (Array.isArray(existingTasks) ? existingTasks : [])
            .filter(task => (
                task
                && task.source_type === 'listening_intensive'
                && task.date === date
            ))
            .map(task => task.listening_exercise_id)
            .filter(Boolean)
    )

    return parts
        .filter(part => !queuedIds.has(part.id) && !assignedIds.has(part.id))
        .map(part => buildQueueItem(match, part))
}

module.exports = {
    buildIntensiveQueueItems,
    findMatchingIntensiveParts
}
