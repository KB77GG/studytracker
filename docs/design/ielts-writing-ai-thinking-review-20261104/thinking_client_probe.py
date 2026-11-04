"""Independent no-network thinking-mode regressions against bd93e1cf.

Intercept the real ChatClient transport boundary, retaining Generator, request
serialization, response parsing, RecordingClient, and report aggregation.
Only synthetic essays and a dummy credential are used. No .env is read.
"""
import argparse
import io
import json
import logging
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import urllib.error

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, default=Path.cwd(),
                    help='Repository checkout to probe (default: current directory)')
parser.add_argument('--output', type=Path, default=Path(__file__).with_suffix('.json'),
                    help='JSON report path (default: beside this script)')
args = parser.parse_args()
REPO = args.repo.expanduser().resolve()
if not (REPO / 'tools/ielts_writing_ai/llm.py').is_file():
    parser.error('--repo must point to the trial-tool repository checkout')
SOURCE_HEAD = subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'],
                                      text=True).strip()
sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True
NETWORK_ATTEMPTS = 0

def deny_network(event, args):
    global NETWORK_ATTEMPTS
    if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
        NETWORK_ATTEMPTS += 1
        raise AssertionError('This probe must not use sockets or DNS')

sys.addaudithook(deny_network)
from tools.ielts_writing_ai import prompts, realcheck, review
from tools.ielts_writing_ai.config import Settings
from tools.ielts_writing_ai.llm import ChatClient, FakeClient, LLMError, reasoning_tokens

logging.disable(logging.CRITICAL)
USAGE = {'prompt_tokens': 111, 'completion_tokens': 16000,
         'total_tokens': 16111,
         'completion_tokens_details': {'reasoning_tokens': 15900}}

class Response(io.BytesIO):
    status = 200

class TransportDouble(ChatClient):
    def __init__(self, actions):
        super().__init__(provider='deepseek', base_url='https://api.deepseek.com/chat/completions',
                         api_key='dummy-not-a-key', model='deepseek-flash', timeout=120.0)
        self.actions = list(actions)
        self.requests = []
        self.active = None
        self.fake = FakeClient()

    def complete(self, messages, **kwargs):
        self.active = (messages, kwargs)
        return super().complete(messages, **kwargs)

    def _open(self, request, timeout=None):
        body = json.loads(request.data)
        self.requests.append({'body': body, 'timeout': self.timeout if timeout is None else timeout,
                              'retries': self.active[1].get('retries', 1),
                              'kind': (self.active[1].get('context') or {}).get('kind')})
        if not self.actions:
            raise AssertionError('Unexpected extra transport attempt')
        action = self.actions.pop(0)
        if action == 'timeout':
            raise TimeoutError('synthetic')
        if action == 'network':
            raise urllib.error.URLError('synthetic')
        if action == '401':
            raise urllib.error.HTTPError(request.full_url, 401, 'synthetic', {}, io.BytesIO(b''))
        if action == 'invalid_json':
            text, finish = 'example only', 'stop'
        elif action == 'empty_length':
            text, finish = '', 'length'
        elif action == 'partial_length':
            text, finish = '{"criteria":', 'length'
        else:
            text, finish = self.fake.complete(self.active[0], **self.active[1]).text, 'stop'
        payload = {'model': self.model, 'choices': [{'finish_reason': finish,
                   'message': {'content': text, 'reasoning_content': '{"do_not_parse_me": true}'}}],
                   'usage': dict(USAGE)}
        return Response(json.dumps(payload).encode())

def run(actions, *, mode='high', kinds=('evaluate',), max_calls=2, samples=1):
    with tempfile.TemporaryDirectory(prefix='iwa-thinking-probe-') as tmp:
        settings = Settings(data_dir=Path(tmp), llm_provider='deepseek',
                            llm_api_key='dummy-not-a-key', evaluate_thinking=mode,
                            vision_provider='none', job_mode='inline')
        settings.validate()
        client = TransportDouble(actions)
        data = realcheck.run(settings, realcheck.load_samples('builtin', limit=samples),
                             client=client, kinds=kinds, max_calls=max_calls)
        report = realcheck.build_report(data)
        return client, data, report

results = {'metadata': {'source_repo': str(REPO), 'source_head': SOURCE_HEAD}}

client, data, report = run(['valid', 'valid', 'valid'], kinds=('evaluate', 'refine', 'rewrite'), max_calls=3)
requests = client.requests
assert len(requests) == 3
assert all(request['retries'] == 0 for request in requests)
by_kind = {request['kind']: request for request in requests}
evaluation = by_kind['evaluate']
assert evaluation['body']['thinking'] == {'type': 'enabled'}
assert evaluation['body']['reasoning_effort'] == 'high'
assert evaluation['body']['max_tokens'] == 16000 and evaluation['timeout'] == 300.0
assert evaluation['body']['response_format'] == {'type': 'json_object'}
for kind in ('refine', 'rewrite'):
    request = by_kind[kind]
    assert request['body']['thinking'] == {'type': 'disabled'}
    assert 'reasoning_effort' not in request['body']
    assert request['body']['max_tokens'] == prompts.MAX_TOKENS[kind]
    assert request['timeout'] == 120.0
assert data['samples'][0]['generations']['evaluate']['status'] == 'ready'
assert data['calls'][0]['reasoning_tokens'] == 15900
results['request_scope'] = {kind: {'thinking': row['body']['thinking'],
                                 'reasoning_effort': row['body'].get('reasoning_effort'),
                                 'max_tokens': row['body']['max_tokens'], 'timeout': row['timeout'],
                                 'transport_retries': row['retries']}
                            for kind, row in by_kind.items()}

off_client, off_data, _ = run(['valid'], mode='off')
off_request = off_client.requests[0]
assert off_request['body']['thinking'] == {'type': 'disabled'}
assert off_request['body']['max_tokens'] == prompts.MAX_TOKENS['evaluate']
assert off_request['timeout'] == 120.0
results['off_budget'] = {'max_tokens': off_request['body']['max_tokens'], 'timeout': off_request['timeout']}

client, data, report = run(['invalid_json', 'valid'])
assert len(client.requests) == len(data['calls']) == 2
assert data['samples'][0]['generations']['evaluate']['status'] == 'ready'
assert data['calls'][0]['json_ok'] is False
results['content_validation_retry'] = {'requests': len(client.requests), 'status': 'ready',
                                      'reasoning_not_parsed_instead_of_bad_content': True}

client, data, report = run(['invalid_json', 'invalid_json'], max_calls=1)
assert len(client.requests) == len(data['calls']) == 1
assert data['samples'][0]['generations']['evaluate']['error_code'] == 'call_budget'
results['cap_includes_validation_retry'] = {'requests': 1, 'error': 'call_budget'}

for action, code in [('timeout', 'timeout'), ('network', 'network'), ('401', 'http_401')]:
    client, data, report = run([action], samples=2)
    assert len(client.requests) == len(data['calls']) == 1
    assert data['aborted']['code'] == code and len(data['samples']) == 1
    results['first_' + action + '_aborts'] = {'requests': 1, 'error': code}

for action, expected_code in [('empty_length', 'empty'), ('partial_length', 'truncated')]:
    client, data, report = run([action])
    call = data['calls'][0]
    metrics = report['kinds']['evaluate']
    assert len(client.requests) == 1
    assert call['error'] == expected_code
    assert call['usage'] == USAGE
    assert metrics['reasoning_tokens'] is None
    results[action] = {'provider_finish_reason': 'length', 'actual_error': call['error'],
                       'reported_truncated': metrics['truncated'],
                       'provider_reasoning_tokens': reasoning_tokens(call['usage']),
                       'reported_reasoning_tokens': metrics['reasoning_tokens'],
                       'completion_tokens_max': metrics['completion_tokens_max'],
                       'requests': len(client.requests), 'retry_performed': False}

client, data, report = run(['partial_length', 'valid'], samples=2)
metrics = report['kinds']['evaluate']
assert len(client.requests) == 2
assert metrics['reasoning_tokens'] == 15900
assert sum(reasoning_tokens(c['usage']) or 0 for c in data['calls']) == 31800
assert metrics['tokens']['completion_tokens'] == 32000
results['mixed_success_failure_reasoning_underreported'] = {
    'provider_reasoning_total': 31800, 'reported_reasoning_total': metrics['reasoning_tokens'],
    'completion_tokens_total_correct': metrics['tokens']['completion_tokens'],
    'request_count': 2}

results['conclusion'] = {
    'paid_request_budget_blocker': False,
    'findings': ['Empty final content with finish_reason=length is classified as empty, not truncated.',
                 'Failed responses preserve nested usage but their reasoning tokens are excluded from aggregate metrics.'],
    'source_edited': False, 'network_attempts': 0, 'real_credentials_read': False}
results['metadata']['network_attempts'] = NETWORK_ATTEMPTS
out = args.output.expanduser().resolve()
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(results, ensure_ascii=False, indent=2))
