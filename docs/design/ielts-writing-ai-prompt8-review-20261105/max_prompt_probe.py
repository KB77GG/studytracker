"""Offline, portable max/CLI/evaluation-scope and prompt .8 regression checks.

Uses the production Generator, ChatClient serialization, validators and reporters,
intercepting the transport boundary with deterministic synthetic responses.
Never reads .env, private model reasoning, or student material.
"""
import argparse
import contextlib
import copy
import io
import json
import logging
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, default=Path.cwd())
parser.add_argument('--output', type=Path, default=Path(__file__).with_suffix('.json'))
args = parser.parse_args()
repo = args.repo.expanduser().resolve()
head = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
sys.path.insert(0, str(repo))
sys.dont_write_bytecode = True
network_attempts = 0

def deny_network(event, args):
    global network_attempts
    if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
        network_attempts += 1
        raise AssertionError('This probe may not use sockets or DNS')

sys.addaudithook(deny_network)
from tools.ielts_writing_ai import __main__ as cli
from tools.ielts_writing_ai import copytext, prompts, realcheck, realcheck_compare
from tools.ielts_writing_ai.config import ConfigError, load_settings
from tools.ielts_writing_ai.llm import ChatClient, FakeClient, LLMError

logging.disable(logging.CRITICAL)
result = {'source_head': head, 'prompt_version': prompts.PROMPT_VERSION}

class OfflineChat(ChatClient):
    def __init__(self, settings, scenario='empty_issues'):
        super().__init__(provider=settings.llm_provider, base_url=settings.llm_base_url,
                         api_key='synthetic-only-not-a-key', model=settings.llm_model,
                         timeout=settings.llm_timeout)
        self.scenario = scenario
        self.requests = []
        self.active = None
        self.fake = FakeClient(model=settings.llm_model)

    def complete(self, messages, **kwargs):
        self.active = (messages, kwargs)
        return super().complete(messages, **kwargs)

    def _open(self, request, timeout=None):
        body = json.loads(request.data)
        options = self.active[1]
        context = options.get('context') or {}
        self.requests.append({'kind': context.get('kind'), 'body': body,
                              'timeout': self.timeout if timeout is None else timeout,
                              'retries': options.get('retries', 1)})
        fake = self.fake.complete(self.active[0], **options)
        raw = json.loads(fake.text)
        if context.get('kind') == 'evaluate':
            for criterion in raw['criteria'].values():
                if isinstance(criterion, dict):
                    criterion['issues'] = []
            if self.scenario == 'one_criterion_no_evidence':
                raw['criteria']['grammar']['strengths'] = []
            elif self.scenario == 'one_criterion_fabricated_quote':
                raw['criteria']['grammar']['strengths'] = [{
                    'quote': 'This sentence is not present in the source essay at all.',
                    'comment': '此句展示了复杂的句式结构。'}]
        payload = {'model': self.model, 'usage': {'prompt_tokens': 100, 'completion_tokens': 900,
                   'completion_tokens_details': {'reasoning_tokens': 600}},
                   'choices': [{'finish_reason': 'stop', 'message': {
                       'content': json.dumps(raw, ensure_ascii=False),
                       'reasoning_content': 'synthetic test content only'}}]}
        return io.BytesIO(json.dumps(payload).encode())

def settings(path, mode='max', provider='deepseek', model=None):
    # An explicit nonexistent path and env mapping prevent any developer .env read.
    return load_settings(env={'IWA_EVALUATE_THINKING': mode, 'IWA_LLM_PROVIDER': provider,
                              'IWA_LLM_API_KEY': 'synthetic-only-not-a-key'},
                         env_file=path / 'never-created.env', data_dir=path / 'trial-unused',
                         llm_model=model or ('deepseek-flash' if provider == 'deepseek' else 'qwen-plus'),
                         llm_base_url='https://offline.invalid/chat/completions',
                         vision_provider='none', job_mode='inline')

with tempfile.TemporaryDirectory(prefix='iwa-max-prompt-probe-') as temporary:
    directory = Path(temporary)
    maximum = settings(directory, ' MAX ')
    maximum.validate()
    assert maximum.evaluate_thinking == 'max'
    assert (maximum.evaluate_thinking_max_tokens, maximum.evaluate_thinking_timeout) == (16000, 300.0)
    assert maximum.public_summary()['evaluate_thinking'] == 'max'
    assert 'llm_api_key' not in maximum.public_summary()
    try:
        settings(directory, 'xhigh').validate()
    except ConfigError:
        result['xhigh_rejected_by_settings'] = True
    else:
        raise AssertionError('xhigh incorrectly allowed')
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            cli.build_parser().parse_args(['realcheck', '--evaluate-thinking', 'xhigh'])
        except SystemExit as error:
            assert error.code == 2
        else:
            raise AssertionError('CLI xhigh incorrectly allowed')

    sample = realcheck.load_samples('builtin', limit=1)
    max_client = OfflineChat(maximum)
    max_data = realcheck.run(maximum, sample, client=max_client,
                            kinds=('evaluate', 'refine', 'rewrite'), max_calls=3)
    assert len(max_client.requests) == 3
    by_kind = {request['kind']: request for request in max_client.requests}
    for kind, expected_tokens, expected_timeout in (
            ('evaluate', 16000, 300), ('refine', 6000, 120), ('rewrite', 2400, 120)):
        request = by_kind[kind]
        assert request['body']['max_tokens'] == expected_tokens
        assert request['timeout'] == expected_timeout and request['retries'] == 0
        assert request['body']['thinking'] == {'type': 'enabled' if kind == 'evaluate' else 'disabled'}
        assert request['body'].get('reasoning_effort') == ('max' if kind == 'evaluate' else None)
    evaluation = max_data['samples'][0]['generations']['evaluate']
    assert evaluation['status'] == 'ready'
    assert all(c['issues'] == [] and any(s['quote_found'] for s in c['strengths'])
               for c in evaluation['result']['criteria'])
    assert evaluation['result']['thinking'] == 'max'
    assert '思考模式 max' in copytext.evaluation_text(evaluation['result'], {'model': maximum.llm_model})
    result['max_scope'] = {kind: {'thinking': request['body']['thinking'],
                                  'reasoning_effort': request['body'].get('reasoning_effort'),
                                  'max_tokens': request['body']['max_tokens'],
                                  'timeout': request['timeout'], 'retries': request['retries']}
                           for kind, request in by_kind.items()}
    result['empty_issues_with_verified_strengths'] = {'status': 'ready', 'criteria': 4, 'issues': 0}

    for mode in ('high', 'off'):
        configured = settings(directory, mode)
        client = OfflineChat(configured)
        data = realcheck.run(configured, sample, client=client, kinds=('evaluate',), max_calls=2)
        request = client.requests[0]
        assert request['body']['max_tokens'] == (16000 if mode == 'high' else 4500)
        assert request['timeout'] == (300 if mode == 'high' else 120)
        assert request['body'].get('reasoning_effort') == ('high' if mode == 'high' else None)
        assert data['samples'][0]['generations']['evaluate']['status'] == 'ready'
        result[mode + '_budget'] = {'max_tokens': request['body']['max_tokens'], 'timeout': request['timeout']}

    result['evidence_rejections'] = []
    for scenario in ('one_criterion_no_evidence', 'one_criterion_fabricated_quote'):
        client = OfflineChat(maximum, scenario)
        data = realcheck.run(maximum, sample, client=client, kinds=('evaluate',), max_calls=2)
        generation = data['samples'][0]['generations']['evaluate']
        assert generation['status'] == 'failed' and generation['error_code'] == 'invalid_output'
        assert len(client.requests) == 2
        assert generation.get('result') is None
        result['evidence_rejections'].append({'scenario': scenario, 'status': 'failed',
                                              'requests_including_retry': 2, 'score_produced': False})

    # Exercise the real CLI command, including mode override, report output and client construction.
    cli_settings = settings(directory, 'off')
    cli_args = cli.build_parser().parse_args(['realcheck', '--evaluate-thinking', 'max',
        '--limit', '1', '--kinds', 'evaluate', '--max-calls', '2', '--confirm-paid',
        '--out', str(directory / 'cli-max')])
    cli_clients = []
    def build_offline(configured, *, vision=False):
        if vision:
            return None
        client = OfflineChat(configured)
        cli_clients.append(client)
        return client
    with patch.object(realcheck, 'build_client', build_offline), contextlib.redirect_stdout(io.StringIO()) as stdout:
        code = cli.cmd_realcheck(cli_settings, cli_args)
    assert code == 0 and cli_settings.evaluate_thinking == 'max'
    assert len(cli_clients) == 1 and len(cli_clients[0].requests) == 1
    assert cli_clients[0].requests[0]['body']['reasoning_effort'] == 'max'
    cli_report = json.loads((directory / 'cli-max/report.json').read_text())
    assert cli_report['evaluate_thinking'] == 'max'
    assert cli_report['kinds']['evaluate']['thinking'] == ['max']
    assert '评价思考模式：max' in stdout.getvalue()
    assert '评价思考模式 max' in (directory / 'cli-max/report.md').read_text()
    result['cli_to_report'] = {'returncode': code, 'mode_override': 'off -> max',
                               'request_reasoning_effort': 'max', 'report_label': 'max', 'calls': 1}

    result['other_provider_boundaries'] = []
    for provider in ('qwen', 'openai_compatible'):
        configured = settings(directory, 'max', provider)
        try:
            configured.validate()
        except ConfigError:
            pass
        else:
            raise AssertionError('non-DeepSeek max config accepted')
        client = OfflineChat(configured)
        try:
            client.complete([], json_mode=True, max_tokens=16000, thinking='max')
        except LLMError as error:
            assert error.code == 'unsupported'
        else:
            raise AssertionError('non-DeepSeek max client accepted')
        assert client.requests == []
        result['other_provider_boundaries'].append({'provider': provider, 'config_rejected': True,
                                                    'client_error': 'unsupported', 'transport_calls': 0})

    qwen = settings(directory, 'off', 'qwen')
    qwen.validate()
    qwen_client = OfflineChat(qwen)
    qwen_data = realcheck.run(qwen, sample, client=qwen_client, kinds=('evaluate',), max_calls=2)
    assert 'thinking' not in qwen_client.requests[0]['body']
    assert 'reasoning_effort' not in qwen_client.requests[0]['body']
    realcheck.write_report(qwen_data, realcheck.build_report(qwen_data), directory / 'qwen-off')
    try:
        realcheck_compare.compare(directory / 'cli-max', directory / 'qwen-off')
    except realcheck_compare.CompareError:
        pass
    else:
        raise AssertionError('model change allowed without flag')
    comparison = realcheck_compare.compare(directory / 'cli-max', directory / 'qwen-off', allow_model_change=True)
    md = realcheck_compare.render_markdown(comparison)
    manual = realcheck_compare.render_manual_review(comparison)
    assert 'deepseek-flash · 思考 max' in md and 'qwen-plus · 思考 off' in md
    assert 'deepseek-flash · 思考 max' in manual and 'qwen-plus · 思考 off' in manual
    assert any('不能单独归因' in w for w in comparison['warnings'])
    result['cross_model_labels'] = {'a': 'deepseek-flash · 思考 max', 'b': 'qwen-plus · 思考 off',
                                    'report_and_manual_match': True,
                                    'attribution_warning_present': True}

    result['prompt_rules'] = []
    for task_type in ('task1', 'task2'):
        submission = {'task_type': task_type, 'essay_text': sample[0]['essay'], 'prompt_text': sample[0]['prompt'],
                      'word_count': 250, 'target_band': 7.0, 'image_status': 'ready',
                      'image_description': 'synthetic chart summary'}
        messages, _ = prompts.build_evaluate(submission, [])
        text = messages[0]['content']
        assert '...0-4; [] when there is no clear error or weakness' in text
        assert 'never invent one to fill the list' in text
        assert 'A criterion with no verifiable quote will be rejected' in text
        assert 'Most essays by Chinese candidates' not in text and '5.0 and 6.5' not in text
        assert 'do not inflate or deflate' in text and 'do not assume a typical score for the writer' in text
        assert 'Award 7.0+' in text and 'award 8.0+' in text
        result['prompt_rules'].append({'task': task_type, 'zero_issues_explicitly_allowed': True,
            'verified_quote_still_required': True, 'population_score_prior_removed': True,
            'seven_and_eight_band_thresholds_retained': True})

    tests = ['test_argument_recheck_20261104.py', 'test_figures_recheck_20261104.py',
             'test_thinking_ab_20261104.py', 'test_prompt_confounds_20261104.py']
    for name in tests:
        source = (repo / 'tools/ielts_writing_ai/tests' / name).read_text()
        assert 'int(prompts.PROMPT_VERSION.rsplit(".", 1)[1])' in source
    assert int('iwa-2026-11-04.10'.rsplit('.', 1)[1]) >= 8
    result['version_assertions'] = {'comparison': 'integer suffix, not lexicographic',
                                    'suffix_10_passes_minimum_8': True,
                                    'production_bug': False,
                                    'maintenance_note': 'A future version scheme that resets the suffix may require test updates.'}
    assert not (directory / 'trial-unused').exists()

result['conclusion'] = {'findings': [], 'network_attempts': network_attempts,
                        'credentials_read': False, 'student_material_read': False,
                        'private_reasoning_read': False, 'business_code_modified': False,
                        'real_model_quality_not_measured': True}
output = args.output.expanduser().resolve()
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
