"""Offline acceptance recheck for argument metrics, report replay and eval budget.

Uses synthetic clients only, temporary databases and no private configuration.
The repository supplied with --repo must contain the standalone tool and tests.
"""
import argparse
import copy
import json
import logging
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', required=True, type=Path)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
repo = args.repo.expanduser().resolve()

def no_network(event, _args):
    if event == 'socket.connect':
        raise RuntimeError('This offline probe blocks socket connections')

sys.addaudithook(no_network)
sys.path.insert(0, str(repo))
from tools.ielts_writing_ai import argument, realcheck, review
from tools.ielts_writing_ai.config import Settings
from tools.ielts_writing_ai.llm import FakeClient
from tools.ielts_writing_ai.tests.test_argument import good_map, TASK2_ESSAY, sample, STRONG

logging.disable(logging.CRITICAL)
checks = []
observations = []

def record(name, actual, passed):
    checks.append({'name': name, 'passed': bool(passed), 'actual': actual})

strong = good_map(problems=[])
for p in strong['paragraphs']:
    p['verdict'] = 'off_position'
strong_checks = realcheck._argument_checks(sample('strong', strong, STRONG), STRONG)
record('strong paragraph deviation is not a false pass', strong_checks,
       strong_checks[0]['ok'] and not strong_checks[1]['ok']
       and strong_checks[1]['detail']['hits'] == ['off_position'])

consistent = good_map(problems=[])
consistent['position']['consistent'] = False
position_checks = realcheck._argument_checks(sample('strong', consistent, STRONG), STRONG)
record('inconsistent stance is a forbidden signal', position_checks,
       not position_checks[1]['ok'] and position_checks[1]['detail']['hits'] == ['unclear_position'])

expect_position = dict(STRONG, argument_position=True)
no_position = good_map(problems=[], position=None)
missing_position_checks = realcheck._argument_checks(
    sample('strong', no_position, expect_position), expect_position)
record('strong stance required', missing_position_checks, not missing_position_checks[-1]['ok'])

control = realcheck._argument_checks(sample('strong', good_map(problems=[]), STRONG), STRONG)
record('valid strong map remains accepted', control, all(c['ok'] for c in control))

malformed = good_map(problems=['bad shape'] * 8)
metrics = realcheck._argument_metrics({'samples': [sample('malformed', malformed, {})]})
record('eight malformed entries count in denominator', metrics,
       metrics['returned'] == 13 and metrics['kept'] == 5 and metrics['dropped'] == 8
       and metrics['dropped_rate'] == round(8 / 13, 3))

many = good_map()
many['paragraphs'] = many['paragraphs'] * 3 + [None]
many['problems'] = [
    {'type': key, 'quote': 'free education', 'comment': 'c'}
    for key in argument.PROBLEM_TYPES
]
many['problems'] += [copy.deepcopy(many['problems'][0]), 'bad', {'type': 'circular'}]
counted = argument.normalize(many, TASK2_ESSAY)
buckets = {k: counted[k] for k in ('returned', 'kept', 'dropped', 'duplicates', 'over_limit')}
record('entry counts conserved with duplicates and caps', buckets,
       buckets == {'returned': 27, 'kept': 15, 'dropped': 3, 'duplicates': 1, 'over_limit': 8})

class Mutating(FakeClient):
    def __init__(self, mode):
        super().__init__()
        self.mode = mode
        self.call_count = 0
        self.options = []
    def complete(self, messages, **kwargs):
        self.call_count += 1
        self.options.append({k: kwargs.get(k) for k in ('max_tokens', 'retries')})
        result = super().complete(messages, **kwargs)
        raw = json.loads(result.text)
        if self.mode == 'invalid_json':
            raw = {}
        elif self.mode == 'no_map_always':
            raw.pop('argument', None)
        elif self.call_count == 1:
            if self.mode == 'one_bad_role':
                raw['argument']['paragraphs'][0]['role'] = ['body']
            elif self.mode == 'all_bad_roles':
                for p in raw['argument']['paragraphs']:
                    p['role'] = ['body']
        result.text = json.dumps(raw)
        return result

def run(client, items, budget):
    with tempfile.TemporaryDirectory(prefix='iwa-argument-metrics-recheck-') as tmp:
        data = realcheck.run(Settings(data_dir=Path(tmp)), items, client=client,
                             kinds=('evaluate',), max_calls=budget)
    return data, realcheck.build_report(data)

items = realcheck.load_samples('builtin')
one_bad_data, one_bad_report = run(Mutating('one_bad_role'), items[:1], 2)
one_bad = one_bad_data['samples'][0]['generations']['evaluate']
assert one_bad_data['calls'][0]['ok'], 'Synthetic model did not return a response'
record('old enum reproducer completes and report renders', {
    'calls': len(one_bad_data['calls']), 'status': one_bad['status'],
    'dropped': one_bad['result']['argument']['dropped'],
    'first_attempt_valid': one_bad_report['kinds']['evaluate']['first_attempt_valid'],
}, len(one_bad_data['calls']) == 1 and one_bad['status'] == 'ready'
   and one_bad['result']['argument']['dropped'] == 1)

retry_data, retry_report = run(Mutating('all_bad_roles'), items[:1], 2)
record('whole-map rejection retries once and counted separately', retry_report['argument'],
       len(retry_data['calls']) == 2 and retry_data['samples'][0]['generations']['evaluate']['status'] == 'ready'
       and retry_report['argument']['evaluate_attempts'] == 2
       and retry_report['argument']['attempts_rejected_for_argument'] == 1
       and retry_report['argument']['dropped'] == 0)

with patch.object(review, 'normalize_evaluation', side_effect=RuntimeError('synthetic replay failure')):
    replay_report = realcheck.build_report(one_bad_data)
record('unexpected replay exception cannot abort report',
       replay_report['kinds']['evaluate']['first_attempt_rejections'],
       replay_report['kinds']['evaluate']['first_attempt_rejections'] == {'复核时出错（RuntimeError）': 1})

budget_client = Mutating('invalid_json')
budget_data, budget_report = run(budget_client, items, 14)
record('seven evaluations maximum fourteen fake requests', {
    'calls': len(budget_data['calls']), 'options': budget_client.options,
    'attempts': [c['attempt'] for c in budget_data['calls']],
}, len(budget_data['calls']) == budget_client.call_count == 14
   and all(x == {'max_tokens': 4500, 'retries': 0} for x in budget_client.options)
   and [c['attempt'] for c in budget_data['calls']] == [0, 1] * 7)

missing_data, missing_report = run(Mutating('no_map_always'), items, 14)
record('complete argument failures remain in JSON attempt counts', missing_report['argument'],
       missing_report['argument']['task2_evaluations'] == 0
       and missing_report['argument']['evaluate_attempts'] == 12
       and missing_report['argument']['attempts_rejected_for_argument'] == 12)
observations.append({
    'name': 'All Task 2 evaluations fail: argument Markdown section is omitted',
    'present': '## 论证结构' in realcheck.render_markdown(missing_report),
    'scope': 'Non-blocking display limitation: JSON retains all 12 argument rejections; general evaluation failure metrics still render.',
})

output = {
    'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    'network_calls': 0,
    'passed': sum(c['passed'] for c in checks), 'total': len(checks),
    'checks': checks, 'observations': observations,
}
rendered = json.dumps(output, ensure_ascii=False, indent=2) + '\n'
if args.output:
    args.output.write_text(rendered, encoding='utf-8')
print(rendered, end='')
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
