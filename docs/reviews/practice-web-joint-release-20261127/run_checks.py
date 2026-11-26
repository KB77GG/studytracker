"""Run the existing reviewed suites against the joint release candidate."""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
V = ROOT / 'docs/reviews/web-vocabulary-task-page-20261126/main-integration'
B = ROOT / 'docs/reviews/practice-web-batch1-20261126'
parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=['py313', 'py310', 'node'])
mode = parser.parse_args().mode
if mode == 'node':
    old = json.loads((V / 'node-commands.json').read_text())[0]['argv'][2:]
    batch = json.loads((B / 'validation/node-command.json').read_text())['argv'][2:]
    commands = [['node', '--test', *dict.fromkeys(old + batch)],
                ['node', str(B / 'independent_exit_probe.js')],
                ['node', 'tests/test_dictation_spell_queue.js']]
else:
    python = '/Users/zhouxin/Desktop/studytracker/.venv/bin/python' if mode == 'py313' else '/Users/zhouxin/Desktop/studytracker/tmp/web-vocab-py310-20261126/bin/python'
    modules = json.loads((V / 'py313-commands.json').read_text())[0]['argv'][3:-1]
    prefix = [python, '-m', 'unittest'] if mode == 'py313' else [python, str(ROOT / 'docs/reviews/web-vocabulary-task-page-20261126/run_compat_tests.py')]
    batch = json.loads((B / 'validation/python-regression-commands.json').read_text())[0]['argv'][2:]
    commands = [[*prefix, *modules], [python, '-m', 'pytest', 'tests/test_task_date_gate.py', '-q'],
                [python, str(B / 'run_tests.py'), *batch]]
results = []
for index, argv in enumerate(commands):
    log = OUT / f'{mode}-{index+1}.log'
    start = time.monotonic()
    with log.open('w') as output:
        result = subprocess.run(argv, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, env=os.environ.copy())
    row = {'argv': argv, 'cwd': str(ROOT), 'returncode': result.returncode,
           'seconds': round(time.monotonic()-start, 3), 'log': log.name}
    results.append(row)
    (OUT / f'{mode}-commands.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(row), flush=True)
    print('\n'.join(log.read_text().splitlines()[-10:]), flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
