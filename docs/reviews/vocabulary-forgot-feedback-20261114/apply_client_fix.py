"""Apply only the five verified client files to the existing local release tree."""

import hashlib
import json
from pathlib import Path


REPORT = Path(__file__).resolve().parent
RELEASE = Path('/Users/zhouxin/Desktop/studytracker-release')
ALLOWED = {
    'miniprogram/pages/student/vocabulary-learning/index.js',
    'miniprogram/pages/student/vocabulary-learning/index.wxml',
    'miniprogram/pages/student/vocabulary-review/index.js',
    'miniprogram/pages/student/vocabulary-review/index.wxml',
    'tests/test_vocabulary_forgot_client.js',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((REPORT / 'client-manifest.json').read_text())
    baseline = json.loads((REPORT / 'release-source-sha256.json').read_text())
    assert set(manifest) == ALLOWED
    for name, hashes in manifest.items():
        assert sha(RELEASE / name) == hashes['before'], f'Source changed: {name}'
        assert sha(REPORT / 'client-files' / name) == hashes['after'], name
    unrelated = set(baseline) - ALLOWED - {'docs/CODEX_HANDOFF.md', 'docs/WORKLOG.md'}
    assert all((RELEASE / name).is_file() and sha(RELEASE / name) == baseline[name]
               for name in unrelated), 'An unrelated source changed; review before applying'
    replacements = {RELEASE / name: (REPORT / 'client-files' / name).read_bytes()
                    for name in ALLOWED}
    for filename, entryname in [('CODEX_HANDOFF.md', 'handoff-entry.md'),
                                ('WORKLOG.md', 'worklog-entry.md')]:
        target = RELEASE / 'docs' / filename
        content = target.read_text()
        heading, rest = content.split('\n', 1)
        entry = (REPORT / entryname).read_text()
        assert entry.splitlines()[0] not in content, 'Entry already applied'
        replacements[target] = (heading + '\n\n' + entry.rstrip() + '\n' + rest).encode()
    originals = {target: target.read_bytes() for target in replacements}
    try:
        for target, body in replacements.items():
            target.write_bytes(body)
        for name, hashes in manifest.items():
            assert sha(RELEASE / name) == hashes['after'], name
        assert all(sha(RELEASE / name) == baseline[name] for name in unrelated)
    except Exception:
        for target, body in originals.items():
            target.write_bytes(body)
        raise
    result = {'applied': sorted(ALLOWED), 'release': str(RELEASE),
              'unrelated_files_unchanged': len(unrelated),
              'handoff_updated': ['docs/CODEX_HANDOFF.md', 'docs/WORKLOG.md'],
              'committed': False, 'pushed': False, 'deployed': False,
              'miniprogram_uploaded': False}
    (REPORT / 'apply-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
