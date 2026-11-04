"""Offline audit of the local paid-run adapter; every HTTP transport is replaced."""
import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import urllib.error
from unittest.mock import patch

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runner', type=Path, default=Path(__file__).with_name('run_ab.py'))
parser.add_argument('--output', type=Path, default=Path(__file__).with_name('runner-independent-audit.json'))
args = parser.parse_args()
RUNNER = args.runner.expanduser().resolve()
sys.dont_write_bytecode = True
def no_network(event, args):
    if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
        raise AssertionError('network forbidden')
sys.addaudithook(no_network)
spec = importlib.util.spec_from_file_location('runner_audit_target', RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
outcomes = []
for mode, expected_count, expected_complete in (
        ('401', 1, False), ('invalid_json', 2, False),
        ('empty_length', 1, False), ('valid', 15, True)):
    with tempfile.TemporaryDirectory(prefix='iwa-runner-audit-') as temporary:
        directory = Path(temporary)
        env_path = directory / 'synthetic.env'
        env_path.write_text('IWA_LLM_PROVIDER=deepseek\nIWA_LLM_API_KEY=synthetic-offline-key\n'
                            'IWA_LLM_MODEL=deepseek-flash\nIWA_VISION_PROVIDER=none\n')
        env_path.chmod(0o600)
        output = directory / 'results'
        requests = []
        fake = runner.llm.FakeClient()
        def transport(client, request, timeout=None):
            disk_ledger = json.loads((output / 'transport.json').read_text())
            assert disk_ledger['request_attempts'] == len(requests) + 1
            assert disk_ledger['responses'][-1]['status'] == 'sending'
            assert disk_ledger['responses'][-1]['stage'] == client.stage
            body = json.loads(request.data)
            requests.append({'stage': client.stage, 'sample_context': client.context,
                             'max_tokens': body['max_tokens']})
            if mode == '401':
                raise urllib.error.HTTPError(request.full_url, 401, 'synthetic', {}, io.BytesIO(b''))
            if mode == 'invalid_json':
                content, finish = 'synthetic invalid output', 'stop'
            elif mode == 'empty_length':
                content, finish = '', 'length'
            else:
                content = fake.complete(body['messages'], json_mode=True,
                                        max_tokens=body['max_tokens'], context=client.context).text
                finish = 'stop'
            return io.BytesIO(json.dumps({'model': 'deepseek-flash',
                'choices': [{'message': {'content': content, 'reasoning_content': 'synthetic'},
                             'finish_reason': finish}],
                'usage': {'prompt_tokens': 1, 'completion_tokens': 10,
                          'completion_tokens_details': {'reasoning_tokens': 8}}}).encode())
        raised = None
        with patch.multiple(runner, ENV=env_path, OUTPUT=output), \
             patch.object(runner.llm.ChatClient, '_open', transport), \
             patch.object(sys, 'argv', ['run_ab.py', '--confirm-paid']), \
             contextlib.redirect_stdout(io.StringIO()):
            try:
                runner.main()
            except RuntimeError as error:
                raised = str(error)
        ledger = json.loads((output / 'transport.json').read_text())
        assert len(requests) == expected_count == ledger['request_attempts']
        assert ledger['completed'] == expected_complete
        if expected_complete:
            assert raised is None and ledger['stage_counts'] == {'smoke_high': 1, 'off': 7, 'high': 7}
            assert (output / 'comparison' / 'compare.md').is_file()
        else:
            assert raised == 'smoke_failed_stop_before_ab'
            assert ledger['stage_counts']['off'] == ledger['stage_counts']['high'] == 0
            assert not (output / 'off').exists() and not (output / 'high').exists()
        outcomes.append({'case': mode, 'actual_stub_sends': len(requests),
                         'stage_counts': ledger['stage_counts'], 'completed': ledger['completed'],
                         'reservation_present_before_every_send': True,
                         'stopped_reason': raised})
result = {'runner': str(RUNNER), 'real_requests': 0,
          'real_credentials_read': False, 'source_edited': False, 'cases': outcomes}
args.output.expanduser().resolve().write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
