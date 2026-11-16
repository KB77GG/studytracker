"""Read-only daily counts from retained Nginx logs, without identifiers."""
import collections
import gzip
import json
import re
from pathlib import Path

groups = {}
for path in Path('/var/log/nginx').glob('access.log*'):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', errors='replace') as stream:
        for line in stream:
            match = re.search(r'\[([^\]]+)\] "GET (/api/miniprogram/[^ ]+) HTTP/[^ ]+" (\d+) ', line)
            if not match:
                continue
            stamp, raw, status = match.groups()
            route = raw.split('?', 1)[0]
            if route.endswith('/vocabulary-queue'):
                endpoint = 'queue'
            elif route.endswith('/vocabulary-review/preflight'):
                endpoint = 'preflight'
            elif route.endswith('/vocabulary-review/summary'):
                endpoint = 'summary'
            else:
                continue
            day = stamp.split(':', 1)[0]
            key = (day, endpoint)
            item = groups.setdefault(key, dict(day=day, endpoint=endpoint, count=0,
                                               status_counts=collections.Counter(),
                                               versions=collections.Counter(), first_failure=None))
            item['count'] += 1
            item['status_counts'][status] += 1
            version = re.search(r'servicewechat\.com/[^/]+/(\d+)/', line)
            item['versions'][version.group(1) if version else 'unknown'] += 1
            if int(status) >= 400 and (item['first_failure'] is None or stamp < item['first_failure']):
                item['first_failure'] = stamp
print(json.dumps({'retained_logs_only': True, 'daily': sorted(groups.values(), key=lambda x:(x['day'],x['endpoint']))}, indent=2))
