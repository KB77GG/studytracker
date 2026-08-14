// Keep this pure CommonJS implementation in lockstep with
// static/js/listening-cloze.js. tests/test_listening_cloze.js executes the
// same fixture against both copies so the two clients cannot silently drift.

const LEVELS = Object.freeze([
    Object.freeze({ key: 'basic', label: '基础·关键词', description: '每句通常 1–2 个关键词' }),
    Object.freeze({ key: 'standard', label: '标准·辨音', description: '每句通常 2–4 个辨音点' }),
    Object.freeze({ key: 'challenge', label: '挑战·整句', description: '整句听写，不显示字数' })
])

const FILLER_WORDS = new Set([
    'hello', 'hi', 'thanks', 'thank', 'okay', 'ok', 'yes', 'yeah', 'yep',
    'oh', 'um', 'uh', 'er', 'ah', 'mmm', 'hmm'
])
// These can be acknowledgement turns, but are also content words in e.g.
// "turn right", "a fine table", and "make sure". They are only treated as
// fillers in a clearly response-like position.
const CONTEXTUAL_RESPONSE_WORDS = new Set(['right', 'fine', 'sure'])
const FUNCTION_WORDS = new Set([
    'a', 'an', 'the', 'and', 'or', 'but', 'if', 'then', 'than', 'that',
    'this', 'these', 'those', 'i', 'you', 'he', 'she', 'we', 'they', 'it',
    'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'our', 'their',
    'is', 'am', 'are', 'was', 'were', 'be', 'been', 'being', 'do', 'does',
    'did', 'have', 'has', 'had', 'will', 'would', 'can', 'could', 'may',
    'might', 'should', 'to', 'of', 'in', 'on', 'at', 'for', 'from', 'with',
    'by', 'as', 'not', 'no', 'so', 'just', 'very', 'really', 'quite', 'too',
    'only', 'there', 'here', 'where', 'when', 'what', 'which', 'who', 'why'
])
const NUMBER_WORDS = new Set([
    'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
    'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen',
    'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty', 'thirty',
    'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety', 'hundred',
    'thousand', 'million', 'first', 'second', 'third', 'fourth', 'fifth'
])
const DATE_TIME_WORDS = new Set([
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday',
    'sunday', 'january', 'february', 'march', 'april', 'may', 'june', 'july',
    'august', 'september', 'october', 'november', 'december', 'morning',
    'afternoon', 'evening', 'noon', 'midnight', 'o’clock', 'oclock'
])
const ADDRESS_WORDS = new Set([
    'street', 'road', 'avenue', 'lane', 'drive', 'court', 'square', 'floor',
    'flat', 'apartment', 'building', 'station', 'postcode', 'post', 'code',
    'number', 'telephone', 'phone', 'email'
])
const DEFAULT_PROPER_NOUN_WHITELIST = Object.freeze([...DATE_TIME_WORDS])
const SPEAKER_LABEL_PATTERN = /^(?:[A-Z][A-Z\s.'&/-]{0,40}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s*:\s*/

function stripSpeakerLabel(text) {
    return String(text || '')
        .trim()
        .replace(SPEAKER_LABEL_PATTERN, '')
}

function normalizeWord(value) {
    return String(value || '')
        .normalize('NFKD')
        .toLowerCase()
        .replace(/[^a-z0-9]/g, '')
}

function displayWord(value) {
    return String(value || '')
        .replace(/^[.,!?;:"'“”‘’()\[\]{}]+|[.,!?;:"'“”‘’()\[\]{}]+$/g, '')
}

function splitWords(value) {
    return String(value || '').trim().split(/\s+/).filter(Boolean)
}

function tokenizeSentence(text) {
    const sourceText = String(text || '').trim()
    const labelMatch = sourceText.match(SPEAKER_LABEL_PATTERN)
    const speakerLabelTokenCount = labelMatch ? splitWords(labelMatch[0]).length : 0
    let contentIndex = 0
    return splitWords(sourceText).map((raw, index) => {
        const display = displayWord(raw)
        const speakerLabel = index < speakerLabelTokenCount
        const tokenContentIndex = speakerLabel ? -1 : contentIndex++
        return {
            index,
            raw,
            display,
            normalized: normalizeWord(display),
            speakerLabel,
            contentIndex: tokenContentIndex
        }
    })
}

function isSpellingSequence(display) {
    return /^(?:[A-Za-z]-){2,}[A-Za-z]$/.test(String(display || ''))
}

function isSeparateLetterSequenceMember(token, tokens) {
    if (!/^[A-Z]$/.test(String(token && token.display || ''))) return false
    const allTokens = tokens || []
    let start = token.index
    let end = token.index
    while (start > 0 && /^[A-Z]$/.test(String(allTokens[start - 1]?.display || ''))) start -= 1
    while (end + 1 < allTokens.length && /^[A-Z]$/.test(String(allTokens[end + 1]?.display || ''))) end += 1
    // A single capital letter can be an ordinary word; require a clearly
    // transcribed sequence before treating it as spelling evidence.
    return end - start + 1 >= 3
}

function hasSpellingEvidence(text, tokens) {
    if (/(?:how\s+(?:do|did)\s+you\s+spell|\bspell(?:ed|t)?\b|\bspelling\b)/i.test(String(text || ''))) {
        return true
    }
    return (tokens || []).some(token => isSpellingSequence(token.display)
        || isSeparateLetterSequenceMember(token, tokens))
}

function isSpellingTarget(token, tokens, spellingEvidence) {
    if (isSpellingSequence(token.display) || isSeparateLetterSequenceMember(token, tokens)) return true
    if (!spellingEvidence) return false
    const previous = (tokens || [])[token.index - 1]
    return !!previous && /^(?:spell|spelled|spelt)$/i.test(previous.display || '')
}

function isContextualResponse(token, tokens) {
    if (!CONTEXTUAL_RESPONSE_WORDS.has(token.normalized)) return false
    const contentTokens = (tokens || []).filter(item => !item.speakerLabel)
    const isTurnStart = token.contentIndex === 0
    const hasSpeakerLabel = (tokens || []).some(item => item.speakerLabel)
    const commaOrResponsePunctuation = /[,!?…]$/.test(token.raw || '')
    const shortStandaloneResponse = contentTokens.length <= 2 && isTurnStart
    const labelledShortTurn = hasSpeakerLabel && isTurnStart && contentTokens.length <= 3
    return commaOrResponsePunctuation || shortStandaloneResponse || labelledShortTurn
}

function isStandaloneWell(token, tokens) {
    if (token.normalized !== 'well') return false
    const contentTokens = (tokens || []).filter(item => !item.speakerLabel)
    if (token.contentIndex === 0) return /[,!?…]$/.test(token.raw) || contentTokens.length <= 3
    return contentTokens.length === 1
}

function isLikelyUnspelledName(token, tokens, spellingTarget, options) {
    if (spellingTarget || !token.display || token.contentIndex === 0) return false
    const whitelist = new Set([
        ...DEFAULT_PROPER_NOUN_WHITELIST,
        ...((options && options.properNounWhitelist) || [])
    ].map(normalizeWord))
    if (whitelist.has(token.normalized)) return false
    return /^[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?$/.test(token.display)
        || /^[A-Z]{2,}(?:-[A-Z]{2,})?$/.test(token.display)
}

function isNumericOrTimeToken(token) {
    const raw = token.raw || ''
    return /\d/.test(raw)
        || /[£$€]/.test(raw)
        || NUMBER_WORDS.has(token.normalized)
        || DATE_TIME_WORDS.has(token.normalized)
}

function isAddressToken(token) {
    return ADDRESS_WORDS.has(token.normalized)
}

function analyseTokens(text, options) {
    const tokens = tokenizeSentence(text)
    const spellingEvidence = hasSpellingEvidence(text, tokens)
    return tokens.map(token => {
        const answerable = !!token.normalized && !token.speakerLabel
        const spelling = isSpellingTarget(token, tokens, spellingEvidence)
        const filler = FILLER_WORDS.has(token.normalized)
            || isContextualResponse(token, tokens)
            || isStandaloneWell(token, tokens)
        const name = isLikelyUnspelledName(token, tokens, spelling, options)
        const numericOrTime = isNumericOrTimeToken(token)
        const address = isAddressToken(token)
        const functionWord = FUNCTION_WORDS.has(token.normalized)
        const hardExcluded = !answerable || filler || name
        let score = 0
        if (numericOrTime) score += 100
        if (spelling) score += 95
        if (address) score += 70
        if (!functionWord && token.normalized.length >= 3) score += 45
        if (!functionWord && token.normalized.length >= 6) score += 10
        if (functionWord) score += 12
        if (token.normalized.length === 1 && !numericOrTime && !spelling) score -= 10
        return {
            ...token,
            answerable,
            filler,
            name,
            spelling,
            numericOrTime,
            address,
            functionWord,
            highValue: numericOrTime || spelling || address,
            hardExcluded,
            score
        }
    })
}

function stableHash(value) {
    let hash = 2166136261
    const text = String(value || '')
    for (let index = 0; index < text.length; index += 1) {
        hash ^= text.charCodeAt(index)
        hash = Math.imul(hash, 16777619)
    }
    return hash >>> 0
}

function getTargetCount(level, answerableCount) {
    if (level === 'challenge') return answerableCount
    if (level === 'basic') return answerableCount >= 9 ? 2 : 1
    if (answerableCount >= 15) return 4
    if (answerableCount >= 8) return 3
    return Math.min(2, Math.max(1, answerableCount))
}

function canSitNextTo(candidate, selected) {
    return selected.every(other => {
        if (Math.abs(other.index - candidate.index) !== 1) return true
        return candidate.highValue && other.highValue
    })
}

function rankCandidates(candidates, seed) {
    return [...candidates].sort((left, right) => {
        if (right.score !== left.score) return right.score - left.score
        const leftTie = stableHash(`${seed}:${left.index}`)
        const rightTie = stableHash(`${seed}:${right.index}`)
        if (leftTie !== rightTie) return leftTie - rightTie
        return left.index - right.index
    })
}

function selectHiddenWordIndices(text, level = 'standard', options = {}) {
    const analysed = analyseTokens(text, options)
    const answerable = analysed.filter(token => token.answerable)
    if (!answerable.length) return []
    if (level === 'challenge') return answerable.map(token => token.index)

    const desired = getTargetCount(level, answerable.length)
    const preferred = analysed.filter(token => token.answerable && !token.hardExcluded)
    const pool = preferred.length ? preferred : answerable
    const seed = options.seed || `${stripSpeakerLabel(text)}:${level}`
    const ranked = rankCandidates(pool, seed)
    const selected = []
    const deferred = []

    ranked.forEach(candidate => {
        if (selected.length >= desired) return
        if (canSitNextTo(candidate, selected)) selected.push(candidate)
        else deferred.push(candidate)
    })
    deferred.forEach(candidate => {
        if (selected.length < desired) selected.push(candidate)
    })

    return selected.map(token => token.index).sort((left, right) => left - right)
}

function expectedTokens(text, hiddenWordIndices) {
    const byIndex = new Map(tokenizeSentence(text).map(token => [token.index, token]))
    return (hiddenWordIndices || [])
        .map(index => byIndex.get(Number(index)))
        .filter(token => token && token.normalized)
}

function inferSavedDictationLevel(text, progress) {
    const savedIndices = (progress && Array.isArray(progress.hidden_word_indices)
        ? progress.hidden_word_indices
        : [])
        .map(Number)
        .filter(Number.isInteger)
    const uniqueSaved = [...new Set(savedIndices)].sort((left, right) => left - right)
    const allSpokenIndices = tokenizeSentence(text)
        .filter(token => token.normalized && !token.speakerLabel)
        .map(token => token.index)
    const isWholeSentence = allSpokenIndices.length > 0
        && uniqueSaved.length === allSpokenIndices.length
        && uniqueSaved.every((index, position) => index === allSpokenIndices[position])
    if (isWholeSentence) return 'challenge'
    const totalWords = Number(progress && progress.total_words) || uniqueSaved.length
    return totalWords <= 2 ? 'basic' : 'standard'
}

function splitChallengeAnswers(value, expectedCount) {
    const supplied = splitWords(value)
    const targetLength = Math.max(supplied.length, Math.max(0, Number(expectedCount) || 0))
    return Array.from({ length: targetLength }, (_, index) => supplied[index] || '')
}

function gradeAnswers(text, hiddenWordIndices, answers) {
    const expected = expectedTokens(text, hiddenWordIndices)
    const supplied = Array.isArray(answers)
        ? answers
        : splitChallengeAnswers(answers, expected.length)
    const results = expected.map((token, index) => {
        const rawAnswer = String(supplied[index] || '')
        const isCorrect = normalizeWord(rawAnswer) === token.normalized
        return {
            index,
            wordIndex: token.index,
            answer: token.display,
            rawAnswer,
            isCorrect,
            isExtra: false
        }
    })
    supplied.slice(expected.length).forEach((rawAnswer, extraIndex) => {
        results.push({
            index: expected.length + extraIndex,
            wordIndex: null,
            answer: '',
            rawAnswer: String(rawAnswer || ''),
            isCorrect: false,
            isExtra: true
        })
    })
    const correctWords = results.filter(result => result.isCorrect).length
    return {
        answers: results.map(result => result.rawAnswer),
        results,
        correctWords,
        totalWords: results.length,
        accuracy: results.length ? Number(((correctWords / results.length) * 100).toFixed(1)) : 0
    }
}

function createFirstAttemptGate(hasSavedProgress) {
    let firstAttemptClosed = !!hasSavedProgress
    let correction = false
    return {
        beginFirstAttempt() {
            if (firstAttemptClosed || correction) return false
            firstAttemptClosed = true
            return true
        },
        enterCorrection() {
            if (!firstAttemptClosed) return false
            correction = true
            return true
        },
        isCorrection() {
            return correction
        },
        canPost() {
            return firstAttemptClosed && !correction
        }
    }
}

function clearFreePracticeTransientState(containers, taskMode = false) {
    if (taskMode) return false
    [
        'dictationStartedSegments',
        'correctionSegments',
        'firstAttemptGates',
        'dictationDrafts',
        'dictationLevelsBySegment',
        'pendingFirstAttempts'
    ].forEach(key => {
        const collection = containers && containers[key]
        if (collection && typeof collection.clear === 'function') collection.clear()
    })
    return true
}

module.exports = {
    LEVELS,
    DEFAULT_PROPER_NOUN_WHITELIST,
    stripSpeakerLabel,
    normalizeWord,
    displayWord,
    tokenizeSentence,
    analyseTokens,
    getTargetCount,
    selectHiddenWordIndices,
    expectedTokens,
    inferSavedDictationLevel,
    splitChallengeAnswers,
    gradeAnswers,
    createFirstAttemptGate,
    clearFreePracticeTransientState
}
