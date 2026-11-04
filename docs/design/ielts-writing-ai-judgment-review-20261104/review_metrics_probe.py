"""Offline verification of schema/language/Task1/report behavior after 93d47ec3.

Replays saved synthetic outputs and uses FakeClient only. No private configuration
is read, socket connections are prohibited, and all databases are temporary.
"""
import argparse
import copy
import json
import logging
from pathlib import Path
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', required=True, type=Path)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
repo = args.repo.resolve()

def block_network(event, _args):
    if event == 'socket.connect':
        raise RuntimeError('Offline probe does not permit network connections')

sys.addaudithook(block_network)
sys.path.insert(0, str(repo))
from tools.ielts_writing_ai import argument, realcheck, review, samples
from tools.ielts_writing_ai.config import Settings
from tools.ielts_writing_ai.llm import FakeClient, parse_strict_json
from tools.ielts_writing_ai.tests.test_argument import good_map, TASK2_ESSAY, sample, STRONG
from tools.ielts_writing_ai.tests.test_argument_recheck_20261104 import FX, chinese

logging.disable(logging.CRITICAL)
checks = []

def record(name, actual, passed):
    checks.append({'name': name, 'passed': bool(passed), 'actual': actual})

def normalize(sample_id, raw):
    return review.checked(review.normalize_evaluation, raw, FX['submissions'][sample_id])

def rejected(sample_id, raw):
    try:
        normalize(sample_id, raw)
    except review.InvalidOutput as exc:
        return str(exc)
    return None

weak_text = FX['evaluation_attempts']['t2-weak'][0]
record('old malformed JSON remains rejected', parse_strict_json(weak_text), parse_strict_json(weak_text) is None)
nested = json.loads(weak_text + '}')  # diagnostic fixture only; never adopted or saved over raw
root_problem = rejected('t2-weak', nested)
record('diagnostic nested JSON explicitly rejected', root_problem, root_problem and '放错了位置' in root_problem)

raw_t1 = parse_strict_json(FX['evaluation_attempts']['t1-no-image'][-1])
language_problem = rejected('t1-no-image', raw_t1)
record('old English Task1 rejected', language_problem, language_problem and '简体中文' in language_problem)
translated_t1 = chinese(copy.deepcopy(raw_t1))
t1_result = normalize('t1-no-image', translated_t1)
t1_item = {'id': 't1-no-image', 'task_type': 'task1', 'expect': samples.SAMPLES[-1]['expect'],
           'generations': {'evaluate': {'status': 'ready', 'result': t1_result}}, 'submission': FX['submissions']['t1-no-image']}
sanity_t1 = realcheck._sanity({'samples': [t1_item]})
known_check = next(c for c in sanity_t1['checks'] if c['check'].startswith('指出文内数据矛盾'))
record('translating old Task1 does not manufacture contradiction detection', known_check,
       t1_result['consistency_issues'] == [] and known_check['ok'] is False)

claim = 'Country A had the highest level of ownership in both years'
valid_comparison = {'claim': claim, 'figures': ['about 75%', 'nearly 80%', 'invented 99%'],
                    'holds': False, 'comment': '2020 年 C 约 80%，高于 A 的约 75%。'}
raw = copy.deepcopy(translated_t1)
raw['comparisons'] = [valid_comparison]
verified = normalize('t1-no-image', raw)
record('Task1 comparison retains verified claim and figures only', verified['consistency_issues'],
       len(verified['consistency_issues']) == 1
       and verified['consistency_issues'][0]['figures'] == ['about 75%', 'nearly 80%']
       and verified['comparisons_checked'] == 1)
for label, changes in (
    ('missing figures', {'figures': []}),
    ('invented figures', {'figures': ['invented 99%']}),
    ('same passage as claim', {'figures': [claim]}),
    ('invented claim', {'claim': 'A was the only country with cars.'}),
):
    invalid = copy.deepcopy(translated_t1)
    invalid['comparisons'] = [dict(valid_comparison, **changes)]
    result = normalize('t1-no-image', invalid)
    record('Task1 drops ' + label, result['consistency_issues'], not result['consistency_issues'])

strong_raw = parse_strict_json(FX['evaluation_attempts']['t2-strong'][-1])
strong_result = normalize('t2-strong', strong_raw)
strong_item = {'id': 't2-strong', 'task_type': 'task2', 'expect': samples.SAMPLES[3]['expect'],
               'generations': {'evaluate': {'status': 'ready', 'result': strong_result}}}
strong_checks = realcheck._argument_checks(strong_item, strong_item['expect'])
problem_limit = next(c for c in strong_checks if c['check'].startswith('论证问题'))
record('old strong two unsupported findings still fail unchanged threshold', problem_limit,
       problem_limit['ok'] is False and len(strong_result['argument']['problems']) == 2)

# Intentional semantic change: absent a quote pair, false does not imply a verified contradiction.
unpaired = good_map(problems=[])
unpaired['position']['consistent'] = False
normalized_unpaired = argument.normalize(unpaired, TASK2_ESSAY)
record('unpaired inconsistent judgment is withheld', {
    'consistent': normalized_unpaired['position']['consistent'], 'self_conflicts': normalized_unpaired['self_conflicts']},
    normalized_unpaired['position']['consistent'] is None and normalized_unpaired['self_conflicts'] == 1)
paired = copy.deepcopy(unpaired)
paired['problems'] = [{'type': 'inconsistent_position',
    'quote': 'i think this idea has advantages and disadvantages',
    'conflicts_with': 'I partly agree that university should be free', 'comment': '两处表述需要核对。'}]
normalized_pair = argument.normalize(paired, TASK2_ESSAY)
pair_checks = realcheck._argument_checks(sample('strong', paired, STRONG), STRONG)
record('paired judgment feeds new inconsistent_position signal', pair_checks,
       normalized_pair['position']['consistent'] is False
       and any('inconsistent_position' in c.get('detail', {}).get('hits', [])
               for c in pair_checks if isinstance(c.get('detail'), dict)))

mapped = good_map(problems=[], improvements=[{'quote': 'free education', 'suggestion': '可以补一个假设例子。'}] * 3)
metrics = realcheck._argument_metrics({'samples': [sample('improvements', mapped, {})]})
record('new improvements participate in accounting but not problem count', metrics,
       metrics['problems'] == 0 and metrics['improvements'] == 3
       and metrics['returned'] == sum(metrics[k] for k in ('kept','dropped','duplicates','over_limit')))

class Alter(FakeClient):
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
        if self.mode == 'empty':
            raw = {}
        elif self.mode == 'no_argument':
            raw.pop('argument', None)
        elif self.call_count == 1 and self.mode == 'english_t1':
            raw = copy.deepcopy(raw_t1)
        elif self.call_count == 1 and self.mode == 'nested':
            for key in ('argument', 'overall_comment', 'priorities'):
                raw['criteria']['task'][key] = raw.pop(key)
        result.text = json.dumps(raw, ensure_ascii=False)
        return result

def run(client, items, budget):
    with tempfile.TemporaryDirectory(prefix='iwa-judgment-review-') as tmp:
        data = realcheck.run(Settings(data_dir=Path(tmp)), items, client=client,
                             kinds=('evaluate',), max_calls=budget)
    return data, realcheck.build_report(data)

items = realcheck.load_samples('builtin')
for mode, item, expected in (('english_t1', items[-1], '简体中文'), ('nested', items[0], '放错了位置')):
    data, report = run(Alter(mode), [item], 2)
    reasons = report['kinds']['evaluate']['first_attempt_rejections']
    record(mode + ' retries once through production pipeline', {'calls': len(data['calls']), 'rejections': reasons},
           len(data['calls']) == 2 and data['samples'][0]['generations']['evaluate']['status'] == 'ready'
           and any(expected in reason for reason in reasons))

data, report = run(Alter('no_argument'), items, 14)
markdown = realcheck.render_markdown(report)
record('zero adopted argument still shows rejection section', report['argument'],
       report['argument']['task2_evaluations'] == 0
       and report['argument']['attempts_rejected_for_argument'] == 12
       and '## 论证结构' in markdown)

fake_data, fake_report = run(FakeClient(), items, 14)
skipped = [c for c in fake_report['sanity']['checks'] if c['ok'] is None]
record('unrun rewrite is skipped not passed', fake_report['sanity'],
       len(skipped) == fake_report['sanity']['skipped'] == 1
       and fake_report['sanity']['total'] == len(fake_report['sanity']['checks']) - 1
       and fake_report['sanity']['passed'] == sum(c['ok'] is True for c in fake_report['sanity']['checks'])
       and '另有 1 项本批未运行' in realcheck.render_markdown(fake_report))

client = Alter('empty')
data, report = run(client, items, 14)
record('evaluation ceiling remains fourteen fake requests', {'calls':len(data['calls']), 'options':client.options},
       len(data['calls']) == 14 and all(o == {'max_tokens':4500,'retries':0} for o in client.options))

output = {'source_head': subprocess.check_output(['git','rev-parse','HEAD'], cwd=repo, text=True).strip(),
          'network_calls':0, 'passed':sum(c['passed'] for c in checks), 'total':len(checks), 'checks':checks}
rendered = json.dumps(output, ensure_ascii=False, indent=2) + '\n'
if args.output:
    args.output.write_text(rendered, encoding='utf-8')
print(json.dumps({k:output[k] for k in ('source_head','network_calls','passed','total')}, ensure_ascii=False))
for check in checks:
    print(('PASS ' if check['passed'] else 'FAIL ') + check['name'])
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
