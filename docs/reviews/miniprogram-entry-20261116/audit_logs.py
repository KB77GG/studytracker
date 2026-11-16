"""Read-only production log summary; omit identities, URLs, IPs and tokens."""
import collections
import json
import re
import subprocess
from pathlib import Path


def safe_path(raw):
    path = raw.split("?", 1)[0]
    return re.sub(r"/\d+(?=/|$)", "/:id", path)


def parse(line):
    match = re.search(r'\[([^\]]+)\] "(GET|POST|PUT|DELETE|HEAD) ([^ ]+) HTTP/[^ ]+" (\d+) (\d+|-)', line)
    if not match:
        return None
    stamp, method, raw, status, size = match.groups()
    if not raw.startswith('/api/miniprogram/'):
        return None
    ver = re.search(r'servicewechat\.com/[^/]+/(\d+)/', line)
    device = 'Mac' if 'MacWechat/' in line else 'iPhone' if 'iPhone' in line else 'Android' if 'Android' in line else 'other'
    return dict(time=stamp, method=method, path=safe_path(raw), status=int(status), bytes=size,
                version=ver.group(1) if ver else None, device=device)


def in_window(stamp):
    return ('15/Nov/2026:17:1' in stamp or '16/Nov/2026:10:4' in stamp)


journal = subprocess.run(['journalctl', '-u', 'studytracker', '--since', '2026-11-15 00:00:00', '--no-pager', '-o', 'cat'], capture_output=True, text=True, check=True).stdout
rows = [r for line in journal.splitlines() if (r := parse(line))]
counts = collections.Counter((r['path'], r['status']) for r in rows)
errors = collections.Counter(re.findall(r'\b(?:[A-Za-z]+Error|WORKER TIMEOUT|database is locked|database disk image is malformed)\b', journal))
nginx = []
for name in ('access.log', 'access.log.1'):
    path = Path('/var/log/nginx') / name
    if path.exists():
        for line in path.read_text().splitlines():
            row = parse(line)
            if row and (in_window(row['time']) or row['status'] >= 500):
                nginx.append(row)
print(json.dumps(dict(journal_window=[r for r in rows if in_window(r['time'])],
                     status_counts=[dict(path=p, status=s, count=c) for (p, s), c in sorted(counts.items())],
                     exception_type_counts=errors, nginx_window=nginx), ensure_ascii=False, indent=2))
