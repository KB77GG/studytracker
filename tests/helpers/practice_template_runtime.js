'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');

function templateRuntime(subject, payload, extra = {}) {
  const source = fs.readFileSync(path.join(root, `templates/${subject}/test_practice.html`), 'utf8');
  const context = {
    test: payload, testData: payload, answers: {},
    practiceContext: null, isMockExamReview: false,
    experienceCapabilities: { simulationMode: true, canShowCorrectness: false },
    PracticeRenderers: require('../../static/js/practice_renderers.js'),
    PracticeTable: require('../../static/js/practice_table.js'),
    PracticeScoring: require('../../static/js/practice_scoring.js'),
    ...extra
  };
  vm.createContext(context);
  if (subject === 'reading') vm.runInContext(source.slice(source.indexOf('const readingJudgmentAliases'), source.indexOf('function canonicalJudgmentAnswer')), context);
  // Only real function declarations, without page bootstrapping, DB, or network.
  const names = subject === 'listening'
    ? ['escapeHtml', 'optionDisplayText', 'richText', 'usableImage', 'imageSrc', 'inputName', 'splitLetters', 'formatClock', 'questionAudioWindow', 'reviewAudioLocator', 'answerTools', 'reviewCard', 'groupAudioControls', 'optionBank', 'renderTable', 'isCombinedMulti', 'renderCombinedMulti', 'controlForQuestion', 'renderCollectText', 'renderQuestion', 'renderGroup', 'unitValue', 'applyAnswerRows', 'answerSnapshot', 'allQuestions', 'questionForId', 'lockReadOnlyReviewControls', 'focusableAnswerControl']
    : ['escapeHtml', 'optionDisplayText', 'canonicalJudgmentAnswer', 'groupLooksLikeJudgment', 'optionLooksLikeJudgment', 'shouldUseQuestionOptions', 'splitLetters', 'groupInstruction', 'passageForQuestion', 'passageLetterOptions', 'groupLooksLikeParagraphMatching', 'effectiveGroupOptions', 'shouldUseGroupOptions', 'questionControl', 'displayQuestionPrompt', 'reviewCard', 'inlineControl', 'replacePlaceholders', 'renderTable', 'renderQuestionRow', 'renderOptionBank', 'renderGroup', 'handleAnswerChange', 'lockReadOnlyReviewControls'];
  for (const name of names) {
    const start = source.indexOf(`function ${name}(`);
    if (start < 0) throw Error(`Missing ${subject} ${name}`);
    vm.runInContext(source.slice(start, source.indexOf('\n}', start) + 2), context);
  }
  return context;
}

function controls(html, subject) {
  return [...html.matchAll(/<(?:input|select|div|span)\b[^>]*>/g)].map(match => {
    const attrs = Object.fromEntries([...match[0].matchAll(/([\w-]+)="([^"]*)"/g)].map(item => [item[1], item[2]]));
    if (subject === 'listening' ? !String(attrs.class || '').split(' ').includes('answer-unit') : !attrs['data-qid']) return null;
    return { id: attrs['data-id'] || attrs['data-qid'], number: attrs['data-q'] || (attrs['aria-label'] || '').match(/^Question (\d+)/)?.[1], kind: attrs['data-kind'] || (match[0].startsWith('<select') ? 'select' : match[0].startsWith('<input') ? 'text' : 'choice'), attrs };
  }).filter(Boolean);
}

module.exports = { templateRuntime, controls };
