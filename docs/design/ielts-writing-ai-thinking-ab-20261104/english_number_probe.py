"""Offline reproduction of unsourced English-number advice in the high/t2-mid fixture.

Reads only the shared synthetic-essay reports; never reads .env, builds a model
client, or sends a request. An exit of zero confirms reproduction, not correctness.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, default=Path.cwd())
parser.add_argument('--fixtures', type=Path,
                    help='Shared report directory (default: repo/docs/design/ielts-writing-ai-thinking-ab-20261104)')
parser.add_argument('--output', type=Path, default=Path(__file__).with_suffix('.json'))
args = parser.parse_args()
repo = args.repo.expanduser().resolve()
fixtures = (args.fixtures or repo / 'docs/design/ielts-writing-ai-thinking-ab-20261104').expanduser().resolve()
sys.path.insert(0, str(repo))
sys.dont_write_bytecode = True
network_attempts = 0

def forbid_network(event, args):
    global network_attempts
    if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
        network_attempts += 1
        raise AssertionError('This probe may not use network or DNS')

sys.addaudithook(forbid_network)
from tools.ielts_writing_ai import copytext, figures, review
from tools.ielts_writing_ai.llm import extract_json_object

run_path = fixtures / 'high/run_data.json'
raw_path = fixtures / 'high/raw_calls.jsonl'
run_data = json.loads(run_path.read_text(encoding='utf-8'))
sample = next(row for row in run_data['samples'] if row['id'] == 't2-mid')
calls = [(number, json.loads(line)) for number, line in enumerate(raw_path.read_text(encoding='utf-8').splitlines(), 1)]
line_number, call = next((number, row) for number, row in calls
                         if row['sample'] == 't2-mid' and row['kind'] == 'evaluate' and row['ok'])
raw = extract_json_object(call['text'])
raw_issue_index, raw_issue = next((number, row) for number, row in enumerate(raw['criteria']['task']['issues'])
                                if 'forty times' in row.get('suggestion', ''))
advice = raw_issue['suggestion']
submission = sample['submission']
source_text = '\n'.join(submission.get(key) or '' for key in ('essay_text', 'prompt_text', 'image_description'))
assert not re.search(r'\b(?:40|forty)\b', source_text, re.IGNORECASE)
sources = figures.for_submission(submission)
assert '40' not in sources.values
assert figures.figures(advice) == []
assert sources.unsourced(advice) == []

def matching_issue(result):
    criterion = next(c for c in result['criteria'] if c['key'] == 'task')
    return next(i for i in criterion['issues'] if i['quote'] == raw_issue['quote'])

stored = sample['generations']['evaluate']['result']
fresh = review.normalize_evaluation(copy.deepcopy(raw), submission)
stored_issue = matching_issue(stored)
fresh_issue = matching_issue(fresh)
fresh_copy = copytext.evaluation_text(fresh, {'model': 'deepseek-flash'})
stored_copy = copytext.evaluation_text(stored, {'model': 'deepseek-flash'})
assert stored_issue['suggestion'] == fresh_issue['suggestion'] == advice
assert stored_issue['suggestion_removed'] is False and fresh_issue['suggestion_removed'] is False
assert fresh['suggestions_removed']['total'] == 0
assert advice in fresh_copy and advice in stored_copy

# Same advice, same quote and input, only the numeral spelling changes.
arabic_raw = copy.deepcopy(raw)
arabic_advice = advice.replace('forty times', '40 times')
arabic_raw['criteria']['task']['issues'][raw_issue_index]['suggestion'] = arabic_advice
arabic = review.normalize_evaluation(arabic_raw, submission)
arabic_issue = matching_issue(arabic)
assert sources.unsourced(arabic_advice) == ['40']
assert arabic_issue['suggestion_removed'] is True and arabic_issue['suggestion'] == ''
assert arabic['suggestions_removed']['total'] == 1
assert arabic_advice not in copytext.evaluation_text(arabic, {'model': 'deepseek-flash'})

boundaries = []
for name, source, suggestion, expected_actual, correct_missing in (
    ('arabic_unsourced_percent', 'Public transport can reduce emissions.',
     'Reduce emissions by 40 percent.', ['40 percent'], True),
    ('english_unsourced_percent', 'Public transport can reduce emissions.',
     'Reduce emissions by forty percent.', [], True),
    ('arabic_sourced_percent', 'Emissions fell by 40 percent.',
     'Reduce emissions by 40%.', [], False),
    ('english_source_arabic_advice', 'Emissions fell by forty percent.',
     'Reduce emissions by 40%.', ['40%'], False),
    ('different_percent_does_not_source_forty', 'Emissions fell by 41%.',
     'Reduce emissions by forty percent.', [], True),
):
    actual = figures.Sources(source).unsourced(suggestion)
    assert actual == expected_actual
    boundaries.append({'case': name, 'source': source, 'suggestion': suggestion,
                       'parsed_figures': figures.figures(suggestion), 'unsourced': actual,
                       'correct_behavior_should_remove': correct_missing,
                       'current_behavior_matches_requirement': bool(actual) == correct_missing})

def reference(path):
    try:
        relative = str(path.relative_to(repo))
    except ValueError:
        relative = str(path)
    return {'path': relative, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

result = {
    'source_head': subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip(),
    'fixtures': {'run_data': reference(run_path), 'raw_calls': reference(raw_path),
                 'raw_calls_line': line_number, 'sample': 't2-mid', 'thinking': 'high',
                 'raw_path': f'criteria.task.issues[{raw_issue_index}].suggestion'},
    'real_response_reproduction': {
        'advice': advice, 'source_contains_40_or_forty': False,
        'numeric_source_values': sorted(sources.values),
        'parsed_figures': figures.figures(advice), 'filter_unsourced': sources.unsourced(advice),
        'stored_result_preserves_advice': True, 'fresh_normalization_preserves_advice': True,
        'suggestion_removed': fresh_issue['suggestion_removed'],
        'removed_total': fresh['suggestions_removed']['total'],
        'stored_and_fresh_copy_preserve_advice': True},
    'arabic_control': {'advice': arabic_advice, 'filter_unsourced': sources.unsourced(arabic_advice),
                       'suggestion_removed': True, 'removed_total': 1, 'copy_preserves_advice': False},
    'percent_boundaries': boundaries,
    'conclusion': {'defect_reproduced': True, 'priority': 'P2',
                   'reason': 'English written numbers bypass the shared figure parser, so unsupported factual advice reaches final evaluation and copy text.',
                   'business_code_changed': False, 'real_model_requests': 0,
                   'network_attempts': network_attempts, 'credentials_read': False}}
output = args.output.expanduser().resolve()
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
