"""Independent read-only source and frozen-snapshot review; no app/DB imports."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.build_reading_test_practice import clean_text, unwrap_part
from services.ielts_exam_payload import build_simulation_payload
from services.question_type_practice import LibraryRoots, build_group_index, build_snapshot, public_snapshot
from services.question_type_review import review_snapshot

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--raw', type=Path, required=True)
args = parser.parse_args()
raw = json.loads(args.raw.read_text())
manifest = json.loads((ROOT / 'data/cambridge_content_corrections/reading.json').read_text())['tests']
current = {p.stem: json.loads(p.read_text()) for p in (ROOT / 'static/reading_tests').glob('ielts*.json')}
headings = images = checked = 0
for test_id, payload in current.items():
    for unit in payload['passages']:
        source = unwrap_part(raw['parts'], 'academic', unit['part_id'])
        groups = {g['group_id']: g for g in source['question']}
        for group in unit['groups']:
            for question in group['questions']:
                old = next(q for q in groups[group['group_id']]['list'] if str(q['id']) == str(question['id']))
                if str(group['type']) == '6' and not clean_text(old.get('title')):
                    label = clean_text(old.get('sub_essay_code'))
                    assert re.fullmatch('[A-Z]', label)
                    assert question['title'].startswith('Paragraph ' + label)
                    headings += 1
        source_images = source['content'].get('paragraph_img') or []
        for index, image in enumerate(unit['content'].get('images') or []):
            assert image['after_paragraph'] == source_images[index]['paragraph']
            assert re.fullmatch(r'reading_tests/images/[A-Za-z0-9_.-]+', image['url'])
            assert (ROOT / 'static' / image['url']).is_file()
            assert 0 <= image['after_paragraph'] < len([p for p in unit['content']['paragraphs'] if p['label'] != 'pre-A'])
            images += 1


def assert_redacted(value):
    if isinstance(value, dict):
        assert not {'answer', 'answers', 'analysis', 'central_sentences', 'locating_words', 'answer_sentences', 'audio_review', 'transcript'}.intersection(value)
        for child in value.values():
            assert_redacted(child)
    elif isinstance(value, list):
        for child in value:
            assert_redacted(child)


with tempfile.TemporaryDirectory(prefix='final-reading-') as temporary:
    folder = Path(temporary)
    (folder / 'reading').mkdir()
    (folder / 'listening').mkdir()
    for test_id in manifest:
        (folder / 'reading' / f'{test_id}.json').write_bytes(subprocess.check_output(['git', 'show', f'40cd8225:static/reading_tests/{test_id}.json'], cwd=ROOT))
    roots = LibraryRoots(reading=folder / 'reading', listening=folder / 'listening')
    for row in build_group_index(roots):
        if row['safety_status'] != 'publishable':
            continue
        live = current[row['test_id']]['passages'][row['unit_index']]
        group = live['groups'][row['group_index']]
        correction = manifest[row['test_id']]
        touched = (str(group['group_id']) in correction.get('groups', {}) or str(live['passage']) in correction.get('passages', {}) or any(str(q['number']) in correction.get('questions', {}) for q in group['questions']))
        if not touched:
            continue
        frozen = build_snapshot([row], pace='exam', standard_type='all', roots=roots)
        before = json.dumps(frozen, sort_keys=True)
        public = public_snapshot(frozen)
        reviewed = review_snapshot(frozen, static_root=ROOT / 'static')
        assert json.dumps(frozen, sort_keys=True) == before
        assert public['snapshot_hash'] == frozen['snapshot_hash']
        assert_redacted(public['payload'])
        assert_redacted(build_simulation_payload(public['payload'], 'reading'))
        actual = public['payload']['passages'][0]
        for question in actual['groups'][0]['questions']:
            original = next(q for q in group['questions'] if q['number'] == question['source_number'])
            assert question['title'] == original['title']
        assert actual['groups'][0]['desc'] == group['desc']
        if live['content'].get('images'):
            assert actual['content']['images'] == live['content']['images']
        for old, new in zip(frozen['payload']['passages'][0]['groups'][0]['questions'], reviewed['payload']['passages'][0]['groups'][0]['questions']):
            for key in ('id', 'number', 'source_number', 'answer', 'answers'):
                assert old.get(key) == new.get(key)
        checked += 1
print(json.dumps({'raw_sha256': hashlib.sha256(args.raw.read_bytes()).hexdigest(), 'heading_source_targets': headings, 'group_desc_corrections': sum(len(c.get('groups', {})) for c in manifest.values()), 'local_images_with_source_positions': images, 'real_baseline_frozen_group_snapshots_checked': checked, 'frozen_mutations': 0, 'redaction': 'passed', 'identity_and_answers': 'unchanged'}, indent=2))
