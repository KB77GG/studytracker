"""Exercise real ordinary/simulation/specialty payloads in actual template renderers."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from practice_tables import normalize_practice_tables
from services.ielts_exam_payload import build_simulation_payload
from services.question_type_practice import LibraryRoots, build_group_index, build_snapshot, public_snapshot

roots = LibraryRoots(listening=ROOT / 'static/listening_tests', reading=ROOT / 'static/reading_tests')
index = build_group_index(roots)
cases = []
blocked = []
for subject, folder in [('listening', roots.listening), ('reading', roots.reading)]:
    for path in sorted(folder.glob('ielts*.json')):
        payload = normalize_practice_tables(json.loads(path.read_text()))
        for mode, current in [('ordinary', payload), ('simulation', build_simulation_payload(payload, subject))]:
            cases.append(dict(subject=subject, test=path.stem, mode=mode, payload=current))
        # Select one source unit at a time: Q11/Q14/Q31 become displayed Q1,
        # while a genuine snapshot rewrites every internal placeholder ID.
        rows = [row for row in index if row['test_id'] == path.stem and row['subject'] == subject]
        for unit_index in sorted({row['unit_index'] for row in rows}):
            selected = [row for row in rows if row['unit_index'] == unit_index and row['safety_status'] == 'publishable']
            blocked.extend({k: row[k] for k in ('subject', 'test_id', 'unit_index', 'group_index', 'safety_status')} for row in rows if row['unit_index'] == unit_index and row['safety_status'] != 'publishable')
            if selected:
                snapshot = build_snapshot(selected, pace='training', standard_type='all', roots=roots)
                cases.append(dict(subject=subject, test=path.stem, mode='specialty', payload=public_snapshot(snapshot)['payload']))
result = subprocess.check_output(['node', str(Path(__file__).with_suffix('.js'))], input=json.dumps(dict(cases=cases, blocked=blocked)).encode(), cwd=ROOT)
Path(__file__).with_suffix('.json').write_bytes(result)
report = json.loads(result)
print(json.dumps({key: value for key, value in report.items() if key != 'details'}, ensure_ascii=False, indent=2))
