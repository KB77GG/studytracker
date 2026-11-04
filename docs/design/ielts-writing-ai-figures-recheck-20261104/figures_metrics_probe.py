"""Read-only offline recheck of all advice paths, source counts and evaluate budget."""
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

def no_network(event, _args):
    if event == 'socket.connect':
        raise RuntimeError('Offline probe prohibits network connections')

sys.addaudithook(no_network)
sys.path.insert(0, str(repo))
from tools.ielts_writing_ai import copytext, figures, realcheck, review
from tools.ielts_writing_ai.config import Settings
from tools.ielts_writing_ai.llm import FakeClient, parse_strict_json

logging.disable(logging.CRITICAL)
fx = json.loads((repo / 'tools/ielts_writing_ai/tests/fixtures/realcheck_20261104c.json').read_text())
checks = []

def record(name, actual, passed):
    checks.append({'name': name, 'passed': bool(passed), 'actual': actual})

def advice_paths(result):
    entries = [(f'criteria.{c["key"]}.issues.{i}', x['suggestion'])
               for c in result['criteria'] for i, x in enumerate(c['issues'])]
    entries += [(f'priorities.{i}', p) for i, p in enumerate(result['priorities'])]
    mapped = result.get('argument') or {}
    for group in ('problems', 'improvements'):
        entries += [(f'argument.{group}.{i}', x.get('suggestion', ''))
                    for i, x in enumerate(mapped.get(group) or [])]
    return entries

mid_raw = parse_strict_json(fx['evaluation_attempts']['t2-mid'][-1])
mid_sub = fx['submissions']['t2-mid']
mid = review.normalize_evaluation(copy.deepcopy(mid_raw), mid_sub)
mid_copy = copytext.evaluation_text(mid, mid_sub)
record('real mid removes both old 80-percent advice paths', {
    'removed': mid['suggestions_removed'],
    'remaining_80percent_advice': [p for p, a in advice_paths(mid) if '80%' in a],
    'copy_contains_80percent': '80%' in mid_copy,
    'summary_warnings': [w for w in mid['warnings'] if '条建议包含' in w],
}, mid['suggestions_removed'] == {'criteria': 1, 'priorities': 0, 'argument': 1, 'total': 2}
   and all('80%' not in a for _p, a in advice_paths(mid)) and '80%' not in mid_copy
   and len([w for w in mid['warnings'] if '条建议包含' in w]) == 1)

for sample_id, attempts in fx['evaluation_attempts'].items():
    if sample_id == 't1-no-image':
        continue  # old English reply is deliberately rejected before display
    result = review.normalize_evaluation(parse_strict_json(attempts[-1]), fx['submissions'][sample_id])
    sources = figures.for_submission(fx['submissions'][sample_id])
    surviving = [(p, a, sources.unsourced(a)) for p, a in advice_paths(result) if sources.unsourced(a)]
    removed = result['suggestions_removed']
    record('all remaining advice sourced: ' + sample_id,
           {'removed': removed, 'surviving_unsourced_advice': surviving},
           not surviving and removed['total'] == sum(removed[k] for k in ('criteria', 'priorities', 'argument')))

injected = copy.deepcopy(mid_raw)
injected['priorities'][0] = '补充数据，例如 90% 的乘客受益。'
injected['argument']['improvements'] = [{'quote': mid_raw['argument']['paragraphs'][0]['main_point'],
    'suggestion': '补充例子，例如 70% 的乘客受益。'}]
all_paths = review.normalize_evaluation(injected, mid_sub)
record('criteria priorities problems and improvements counted together', all_paths['suggestions_removed'],
       all_paths['suggestions_removed'] == {'criteria': 1, 'priorities': 1, 'argument': 2, 'total': 4}
       and not all_paths['argument']['improvements']
       and all('90%' not in p for p in all_paths['priorities']))

for source, expected in [
    ('The service began in 1980.', ['80%']),
    ('There are 180 buses.', ['80%']),
    ('There are 80 buses.', ['80%']),
    ('The essay reports 80% fewer emissions.', []),
]:
    actual = figures.Sources(source).unsourced('补充 80% 的减排效果。')
    record('whole percentage sourcing: ' + source, actual, actual == expected)

provided = dict(mid_sub, prompt_text=mid_sub.get('prompt_text', '') + '\nThe question specifies an 80% reduction.')
known_result = review.normalize_evaluation(copy.deepcopy(mid_raw), provided)
record('question provides legitimate 80-percent source', known_result['suggestions_removed'],
       known_result['suggestions_removed']['total'] == 0
       and any('80%' in a for _p, a in advice_paths(known_result)))

chart_sub = {'task_type': 'task1', 'essay_text': 'Car ownership rose.', 'prompt_text': 'Years 2000 and 2020.',
    'word_count': 133, 'image_status': 'ready', 'image_description': 'Country C: 79% in 2020.'}
ready = figures.for_submission(chart_sub)
unusable = figures.for_submission(dict(chart_sub, image_status='failed'))
record('available chart only and structural word counts are sources', {
    'ready': ready.unsourced('2020 年 C 达 79%，原稿 133 词，至少写 150 词。'),
    'unusable': unusable.unsourced('C 达 79%'),
}, ready.unsourced('2020 年 C 达 79%，原稿 133 词，至少写 150 词。') == []
   and unusable.unsourced('C 达 79%') == ['79%'])

class Client(FakeClient):
    def __init__(self, empty=False):
        super().__init__()
        self.empty = empty
        self.options = []
    def complete(self, messages, **kwargs):
        self.options.append({k: kwargs.get(k) for k in ('max_tokens', 'retries')})
        result = super().complete(messages, **kwargs)
        result.text = json.dumps({} if self.empty else mid_raw, ensure_ascii=False)
        return result

def run(client, items, max_calls):
    with tempfile.TemporaryDirectory(prefix='iwa-figures-metrics-') as tmp:
        data = realcheck.run(Settings(data_dir=Path(tmp)), items, client=client, kinds=('evaluate',), max_calls=max_calls)
    return data, realcheck.build_report(data)

items = realcheck.load_samples('builtin')
data, report = run(Client(), [next(i for i in items if i['id'] == 't2-mid')], 2)
result = data['samples'][0]['generations']['evaluate']['result']
record('realcheck preserves per-path removals with one evaluation call', {
    'calls': len(data['calls']), 'normalized_removed': result['suggestions_removed'],
    'report_argument_removed': report['argument']['suggestions_removed'],
}, len(data['calls']) == 1 and result['suggestions_removed']['total'] == 2
   and report['argument']['suggestions_removed'] == result['suggestions_removed']['argument'] == 1)

client = Client(empty=True)
data, report = run(client, items, 14)
record('evaluate-only ceiling unchanged', {'calls': len(data['calls']), 'options': client.options},
       len(data['calls']) == 14 and all(o == {'max_tokens': 4500, 'retries': 0} for o in client.options)
       and set(report['kinds']) == {'evaluate'})

out = {'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
       'network_calls': 0, 'passed': sum(c['passed'] for c in checks), 'total': len(checks),
       'checks': checks,
       'report_scope_note': 'realcheck.argument.suggestions_removed counts argument advice only. For all advice removals, aggregate each adopted evaluation result.suggestions_removed.{criteria,priorities,argument,total} from run_data.json.'}
if args.output:
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: out[k] for k in ('source_head', 'network_calls', 'passed', 'total')}))
for c in checks:
    print(('PASS ' if c['passed'] else 'FAIL ') + c['name'])
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
