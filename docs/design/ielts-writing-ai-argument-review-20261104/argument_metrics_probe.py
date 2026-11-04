"""Read-only synthetic argument diagnostics; records observed behavior, not acceptance.

Run with the repository's Python: argument_metrics_probe.py --repo /path/to/repo
Optional --output saves the same JSON that is printed. All clients are synthetic;
socket connections are blocked. No private configuration is loaded.
"""
import argparse
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
REPO = args.repo.expanduser().resolve()
if not (REPO / 'tools/ielts_writing_ai/realcheck.py').is_file():
    parser.error('--repo must contain tools/ielts_writing_ai/realcheck.py')

def block_network(event, _args):
    if event == 'socket.connect':
        raise RuntimeError('Offline probe prohibits network connections')

sys.addaudithook(block_network)
sys.path.insert(0, str(REPO))
from tools.ielts_writing_ai import argument, realcheck
from tools.ielts_writing_ai.config import Settings
from tools.ielts_writing_ai.llm import FakeClient
from tools.ielts_writing_ai.tests.test_argument import good_map, TASK2_ESSAY, sample, STRONG

logging.disable(logging.CRITICAL)
out = {
    'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
    'network_calls': 0,
    'scope': 'synthetic clients and temporary databases; no private configuration',
}

# Strong's paragraph verdict is a first-class finding yet forbidden check ignores it.
strong = good_map(problems=[])
for p in strong['paragraphs']:
    p['verdict'] = 'off_position'
item = sample('t2-strong', strong, STRONG)
out['strong_off_position_paragraphs'] = {
    'paragraphs': [p['verdict'] for p in item['generations']['evaluate']['result']['argument']['paragraphs']],
    'checks': realcheck._argument_checks(item, STRONG),
}

# The metric says all model-returned items, but ignores malformed entries.
malformed = good_map(problems=['not an object'] * 8)
mapped = argument.normalize(malformed, TASK2_ESSAY)
out['malformed_items_not_counted'] = {
    'raw_position_plus_list_entries': 1 + len(malformed['paragraphs']) + len(malformed['problems']),
    'malformed_entries': 8,
    'normalizer_dropped': mapped['dropped'],
    'metrics': realcheck._argument_metrics({'samples': [sample('malformed', malformed, {})]}),
}

class Invalid(FakeClient):
    def __init__(self):
        super().__init__()
        self.options = []
    def complete(self, messages, **kwargs):
        self.options.append({k: kwargs.get(k) for k in ('max_tokens', 'retries', 'context')})
        result = super().complete(messages, **kwargs)
        result.text = '{}'
        return result

with tempfile.TemporaryDirectory(prefix='iwa-argument-budget-') as tmp:
    client = Invalid()
    data = realcheck.run(Settings(data_dir=Path(tmp)), realcheck.load_samples('builtin'),
                         client=client, kinds=('evaluate',), max_calls=14)
    assert len(client.options) == len(data['calls']) == 14
    assert all(o['max_tokens'] == 4500 and o['retries'] == 0 for o in client.options)
    out['eval_budget'] = {
        'calls': len(data['calls']),
        'max_tokens': sorted({o['max_tokens'] for o in client.options}),
        'retries': sorted({o['retries'] for o in client.options}),
        'attempts': [c['attempt'] for c in data['calls']],
        'sample_states': [s['generations']['evaluate']['status'] for s in data['samples']],
        'metrics': realcheck._argument_metrics(data),
    }

# When report repeats first-attempt validation, unhashable enum crashes reporting too.
class BadRole(FakeClient):
    def __init__(self):
        super().__init__()
        self.call_count = 0
    def complete(self, messages, **kwargs):
        self.call_count += 1
        result = super().complete(messages, **kwargs)
        raw = json.loads(result.text)
        if self.call_count == 1:
            raw['argument']['paragraphs'][0]['role'] = ['body']
        result.text = json.dumps(raw)
        return result

with tempfile.TemporaryDirectory(prefix='iwa-argument-report-') as tmp:
    bad_role = BadRole()
    data = realcheck.run(Settings(data_dir=Path(tmp)), realcheck.load_samples('builtin', limit=1),
                         client=bad_role, kinds=('evaluate',), max_calls=2)
    assert data['calls'][0]['ok'] is True, 'fixture failed before model response'
    assert json.loads(data['calls'][0]['text'])['argument']['paragraphs'][0]['role'] == ['body']
    out['malformed_role_reporting'] = {
        'calls': len(data['calls']),
        'client_would_return_valid_on_second_call': True,
        'recorded_model_response_ok': data['calls'][0]['ok'],
        'recorded_role': json.loads(data['calls'][0]['text'])['argument']['paragraphs'][0]['role'],
        'generation': {k: data['samples'][0]['generations']['evaluate'][k] for k in ('status','error_code')},
        'report_exception': None,
    }
    try:
        realcheck.build_report(data)
    except Exception as exc:
        out['malformed_role_reporting']['report_exception'] = type(exc).__name__ + ': ' + str(exc)

rendered = json.dumps(out, ensure_ascii=False, indent=2) + '\n'
if args.output:
    args.output.write_text(rendered, encoding='utf-8')
print(rendered, end='')
