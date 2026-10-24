"""Read-only exact-content guard before applying the compatibility rollback."""
import hashlib
import json
import sys
from pathlib import Path

manifest = json.loads((Path(__file__).parent / 'numeric-compatibility-rollback-manifest.json').read_text())
target = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
expected = manifest['full_candidate_sha256']
errors = []
for name, digest in expected.items():
    path = target / name
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'missing'
    if actual != digest:
        errors.append(name)
if errors:
    print('STOP: rollback baseline differs: ' + ', '.join(errors))
    raise SystemExit(1)
print('PASS: full candidate fingerprint ' + manifest['full_candidate_fingerprint'])
