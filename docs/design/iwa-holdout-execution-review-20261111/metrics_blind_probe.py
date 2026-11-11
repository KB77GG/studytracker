"""Offline synthetic probes for comparison metrics and blind-review export.

No user data, .env, model calls, network, or product writes. Records observed
defects instead of failing at the first assertion so every case remains inspectable.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo))
    from tools.ielts_writing_ai import realcheck as rc
    from tools.ielts_writing_ai import realcheck_compare as cmp

    script_dir = args.repo / 'docs/design/ielts-writing-ai-model-comparison-plan-20261110'
    tally = module(script_dir / 'tally_blind.py', 'audit_tally')
    summary = module(script_dir / 'summarize_comparison.py', 'audit_summary')

    def sample(sample_id, score, **extra):
        result = None if score is None else {
            'overall_band': score,
            'criteria': [{'key': k, 'band': score, 'summary': '', 'issues': []}
                         for k in rc.CRITERION_KEYS],
        }
        return {'id': sample_id, 'task_type': 'task2',
                'submission': {'essay_text': 'First quote. Other quote. Support quote.'},
                'generations': {'evaluate': {'status': 'failed' if result is None else 'ready',
                                             'result': result}}, **extra}

    results = {'network_calls': 0, 'private_inputs_read': False, 'cases': {}}
    cases = results['cases']

    # Identical human scores on the one scored essay, wide human disagreement only
    # on the failed essay: the whole-batch baseline misleadingly permits AI error.
    mixed = {'samples': [
        sample('scored', 7.5, teachers=[{'overall': 7}, {'overall': 7}]),
        sample('failed', None, teachers=[{'overall': 6}, {'overall': 8}]),
    ]}
    whole = rc._rater_agreement(mixed)['overall']
    paired = rc._rater_agreement({'samples': mixed['samples'][:1]})['overall']
    assert whole['rater_gap'] == 1 and whole['ai_gap'] == .5
    assert paired['rater_gap'] == 0 and paired['ai_gap'] == .5
    cases['rater_population_mismatch'] = {
        'whole_batch': whole, 'same_scored_samples': paired,
        'current_ai_no_worse_than_humans': whole['ai_gap'] <= whole['rater_gap'],
        'paired_ai_no_worse_than_humans': paired['ai_gap'] <= paired['rater_gap'],
    }

    all_scored = {'samples': [sample('hi', 8, group='g', nominal_band=9),
                              sample('mid', 7, group='g', nominal_band=8),
                              sample('lo', 6, group='g', nominal_band=7)]}
    full = rc._ordering(all_scored)['g']
    missing_top = copy.deepcopy(all_scored)
    missing_top['samples'][0] = sample('hi', None, group='g', nominal_band=9)
    missing = rc._ordering(missing_top)['g']
    one = rc._ordering({'samples': [all_scored['samples'][0],
                                   sample('lo', None, group='g', nominal_band=7)]})['g']
    assert (full['spread'], full['pairs']) == (2, 3)
    assert (missing['spread'], missing['missing']) == (1, 1)
    assert (one['spread'], one['pairs']) == (0, 0)
    cases['missing_ranking_endpoint'] = {'all_scored': full, 'highest_failed': missing,
                                         'only_one_scored': one,
                                         'expected_missing_endpoint_spread': None}

    marked = sample('blind-synthetic', 7)
    result = marked['generations']['evaluate']['result']
    result['argument'] = {
        'position': {'consistent': False},
        'notes': ['SYNTHETIC_ARGUMENT_NOTE'],
        'problems': [{'type': 'contradiction', 'label': 'Contradiction',
                      'quote': 'First quote.', 'conflicts_with': 'SYNTHETIC_CONFLICT_PARTNER',
                      'needs_review': True, 'p': 3, 'comment': 'Synthetic comment.',
                      'suggestion': 'Synthetic suggestion.'}],
        'improvements': [{'quote': 'Support quote.', 'comment': 'Synthetic optional comment.',
                          'from_type': 'unsupported', 'support': ['SYNTHETIC_SUPPORT_EVIDENCE'],
                          'suggestion': 'Synthetic optional suggestion.'}],
    }
    result['count_corrections'] = ['SYNTHETIC_COUNT_CORRECTION']
    result['criteria'][3]['summary'] = 'SYNTHETIC_GRAMMAR_SUMMARY'
    result['criteria'][3]['issues'] = [{'quote': 'Other quote.',
        'comment': 'SYNTHETIC_GRAMMAR_COMMENT', 'suggestion': 'SYNTHETIC_REVISED_SENTENCE'}]
    view = cmp.sample_view({'calls': []}, marked)
    pair = {'samples': [{'a': view, 'b': copy.deepcopy(view)}]}
    sheet, key = cmp.render_blind_review(pair, seed=3)
    fields = {
        'grammar_summary': 'SYNTHETIC_GRAMMAR_SUMMARY',
        'grammar_issue': 'SYNTHETIC_GRAMMAR_COMMENT',
        'revised_sentence': 'SYNTHETIC_REVISED_SENTENCE',
        'conflicting_quote': 'SYNTHETIC_CONFLICT_PARTNER',
        'argument_note': 'SYNTHETIC_ARGUMENT_NOTE',
        'reclassification_support': 'SYNTHETIC_SUPPORT_EVIDENCE',
        'count_correction': 'SYNTHETIC_COUNT_CORRECTION',
        'needs_manual_review': '需人工确认',
        'paragraph_number': '第 3 段',
        'position_inconsistent': '前后不一致',
    }
    included = {name: token in sheet for name, token in fields.items()}
    assert all(included[k] for k in ('grammar_summary', 'grammar_issue', 'revised_sentence'))
    assert not any(included[k] for k in fields if k not in ('grammar_summary','grammar_issue','revised_sentence'))
    cases['blind_evidence_omitted'] = included

    minimal_key = {'samples': {'one': {'甲': 'a', '乙': 'b'}}}
    def count_cell(value):
        sheet = f'## one\n### 甲\n| 其他漏报 | — | — | — | {value} |  |\n'
        return tally.tally(sheet, minimal_key)['models']['a']
    cases['tally_non_integer'] = {cell: count_cell(cell) for cell in ('2', '', '0.5', '1–2', '-1')}
    assert cases['tally_non_integer']['0.5']['missed_other'] == 0
    assert cases['tally_non_integer']['0.5']['filled'] == 1
    assert cases['tally_non_integer']['1–2']['missed_other'] == 1

    # Export should contain numeric teacher fields only; currently the entire input
    # object survives. This is a schema boundary, not a claim about the private ZIP.
    report = {'per_sample': [{'id':'synthetic', 'teacher': {
        'overall': 6.5, 'comment': 'SYNTHETIC_PRIVATE_COMMENT'}, 'scores': {'overall':7}}]}
    exported = summary.run_numbers(report)
    cases['summary_teacher_allowlist_absent'] = {
        'private_marker_copied': 'SYNTHETIC_PRIVATE_COMMENT' in json.dumps(exported),
        'teacher_keys_after_export': list(exported['per_sample'][0]['teacher']),
        'scope': 'accepted-schema boundary; actual user ZIP not read by this probe',
    }
    assert cases['summary_teacher_allowlist_absent']['private_marker_copied']

    with tempfile.TemporaryDirectory(prefix='iwa-summary-synthetic-') as scratch:
        out = Path(scratch)
        for dirname, calls, cost in [('dev-flash', 4, .04),
                                     ('dev-flash.incomplete-20261111000000', 20, .20)]:
            folder = out / dirname
            folder.mkdir()
            (folder / 'report.json').write_text(json.dumps({
                'model': 'synthetic', 'calls': calls, 'estimated_cost': cost}))
        collected = summary.collect(out)
        observed = collected['dev']['runs']['flash']
        assert observed['calls'] == 4 and observed['estimated_cost'] == .04
        cases['summary_ignores_archived_attempts'] = {
            'current_summary_calls': observed['calls'],
            'all_reported_attempt_calls': 24,
            'current_summary_cost': observed['estimated_cost'],
            'all_reported_attempt_cost': .24,
            'archived_report_present': True,
        }

    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'cases':len(cases), 'network_calls':0, 'out':str(args.out)}))


if __name__ == '__main__':
    main()
