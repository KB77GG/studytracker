"""Read-only deployment probe; stdlib only, no app import or student DB access."""

import ast
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


ROOT = Path('/root/apps/studytracker')
FILES = (
    'services/task_planner_recovery.py',
    'templates/task_planner.html',
    'api/task_planner.py',
    'services/task_date_gate.py',
    'services/task_planner.py',
    'scripts/run_task_planner.py',
    'gunicorn.conf.py',
)


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def service(name, *properties):
    args = ['systemctl', 'show', name]
    for prop in properties:
        args.extend(['-p', prop])
    return dict(line.split('=', 1) for line in command(*args).splitlines())


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(path, method='GET'):
    req = Request('http://127.0.0.1:5002' + path, method=method)
    try:
        response = build_opener(NoRedirect).open(req, timeout=15)
    except HTTPError as exc:
        response = exc
    with response:
        return {'method': method, 'path': path, 'status': response.code,
                'location': response.headers.get('Location')}


gunicorn = {}
for node in ast.parse((ROOT / 'gunicorn.conf.py').read_text()).body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in (
                'bind', 'workers', 'worker_class', 'threads'
            ):
                gunicorn[target.id] = ast.literal_eval(node.value)

app_service = service('studytracker', 'ActiveState', 'SubState', 'NRestarts',
                      'ExecMainStartTimestamp', 'MainPID', 'ExecStart')
unit_files = {}
for suffix in ('timer', 'service'):
    name = 'studytracker-task-planner.' + suffix
    deployed = Path('/etc/systemd/system') / name
    expected = ROOT / 'deploy/task-planner' / name
    actual_bytes = deployed.read_bytes()
    unit_files[name] = {
        'sha256': hashlib.sha256(actual_bytes).hexdigest(),
        'matches_repository': actual_bytes == expected.read_bytes(),
    }

warnings = command('journalctl', '-u', 'studytracker', '--since',
                   app_service['ExecMainStartTimestamp'], '-p', 'warning',
                   '--no-pager', '-o', 'cat')
result = {
    'checked_at_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Read-only files, Git, systemd, anonymous HTTP. No app import or DB access.',
    'head': command('git', 'rev-parse', 'HEAD'),
    'tracked_clean': not command('git', 'status', '--porcelain', '--untracked-files=no'),
    'untracked_count': len(command('git', 'ls-files', '--others', '--exclude-standard').splitlines()),
    'sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
               for name in FILES},
    'gunicorn': gunicorn,
    'service': app_service,
    'timer': service('studytracker-task-planner.timer', 'ActiveState', 'SubState',
                     'UnitFileState', 'NextElapseUSecRealtime', 'LastTriggerUSec'),
    'planner_last_result': service('studytracker-task-planner.service', 'Result',
                                   'ExecMainStatus'),
    'unit_files': unit_files,
    'warnings_since_restart': len([line for line in warnings.splitlines()
                                  if line.strip() and line != '-- No entries --']),
    'http': [request('/login'), request('/task-planner'),
             request('/api/task-planner/bootstrap'), request('/api/task-planner/inbox'),
             request('/api/task-planner/inbox/preview', 'OPTIONS'),
             request('/api/task-planner/inbox/apply', 'OPTIONS'), request('/__e2e')],
}
print(json.dumps(result, ensure_ascii=False, indent=2))
