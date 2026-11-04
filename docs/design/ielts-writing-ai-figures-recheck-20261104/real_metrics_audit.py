"""Independently recount a completed synthetic evaluation batch from saved files.

Reads only report/run_data/raw_calls/transport. No model calls or configuration.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--results', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
root = args.results
data = json.loads((root / 'run_data.json').read_text())
report = json.loads((root / 'report.json').read_text())
transport = json.loads((root / 'transport.json').read_text())
calls = [json.loads(line) for line in (root / 'raw_calls.jsonl').read_text().splitlines()]
assert calls == data['calls']
assert len(calls) == transport['request_attempts'] == len(transport['responses'])
assert transport['completed']

def norm(text):
    mapping = str.maketrans({'‘': "'", '’': "'", '“': '"', '”': '"', '—': '-', '–': '-'})
    return re.sub(r'\s+', ' ', text.translate(mapping)).strip().lower()

def located(essay, quote):
    key = norm(quote).strip(" .,;:!?\"'")
    return bool(key) and key in norm(essay)

decoded = []
json_failures = []
for call in calls:
    try:
        parsed = json.loads(call['text'])
        assert isinstance(parsed, dict)
        decoded.append((call, parsed))
    except (ValueError, AssertionError) as exc:
        json_failures.append({'sample': call['sample'], 'attempt': call['attempt'], 'error': str(exc)})
adopted_raw = {call['sample']: raw for call, raw in decoded}
first_calls = [call for call in calls if call['attempt'] == 0]
samples = {sample['id']: sample for sample in data['samples']}
usage = {key: sum(c['usage'][key] for c in calls)
         for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
assert usage == report['kinds']['evaluate']['tokens']
assert all(c['usage'] == r['usage'] for c, r in zip(calls, transport['responses']))

evidence = []
argument_quotes = []
conflict_quotes = []
argument_counts = Counter()
argument_types = Counter()
verdicts = Counter()
removed_total = Counter()
removed_by_sample = []
removed_texts = []
paragraphs = []
raw_argument_entry_total = 0
scored_criteria = 0
for sid, sample in samples.items():
    essay = sample['submission']['essay_text']
    result = sample['generations']['evaluate']['result']
    raw = adopted_raw[sid]
    removed = result['suggestions_removed']
    assert removed['total'] == sum(removed[k] for k in ('criteria', 'priorities', 'argument'))
    removed_total.update(removed)
    removed_by_sample.append({'sample': sid, **removed})
    criteria_flag_count = 0
    for criterion in result['criteria']:
        if criterion['state'] != 'scored':
            continue
        scored_criteria += 1
        for entry in criterion['strengths'] + criterion['issues']:
            if entry.get('quote'):
                evidence.append({'sample':sid, 'quote':entry['quote'],
                    'located':located(essay, entry['quote']), 'exact':entry['quote'] in essay})
        for i, entry in enumerate(criterion['issues']):
            if entry.get('suggestion_removed'):
                criteria_flag_count += 1
                original = raw['criteria'][criterion['key']]['issues'][i]
                assert original['quote'].strip().startswith(entry['quote'])
                removed_texts.append({'sample':sid, 'path':f'criteria.{criterion["key"]}.issues.{i}.suggestion',
                    'text':original['suggestion'], 'normalized_suggestion':entry['suggestion']})
    assert criteria_flag_count == removed['criteria']
    removed_priorities = Counter(raw['priorities'][:5]) - Counter(result['priorities'])
    assert sum(removed_priorities.values()) == removed['priorities']
    for text, count in removed_priorities.items():
        removed_texts.extend({'sample':sid, 'path':'priorities', 'text':text} for _ in range(count))
    mapped = result.get('argument')
    if not mapped:
        continue
    for key in ('returned', 'kept', 'dropped', 'duplicates', 'over_limit', 'self_conflicts', 'suggestions_removed'):
        argument_counts[key] += mapped[key]
    argument_counts['positions'] += mapped['position'] is not None
    argument_counts['paragraphs'] += len(mapped['paragraphs'])
    argument_counts['problems'] += len(mapped['problems'])
    argument_counts['improvements'] += len(mapped['improvements'])
    argument_types.update(p['type'] for p in mapped['problems'])
    verdicts.update(p['verdict'] for p in mapped['paragraphs'])
    quotes = []
    if mapped['position']:
        quotes.append(mapped['position']['quote'])
    quotes += [p['main_point'] for p in mapped['paragraphs']]
    quotes += [p['quote'] for p in mapped['problems']]
    quotes += [p['quote'] for p in mapped['improvements']]
    for quote in quotes:
        argument_quotes.append({'sample':sid, 'quote':quote, 'located':located(essay, quote), 'exact':quote in essay})
    for p in mapped['problems']:
        if p.get('conflicts_with'):
            conflict_quotes.append({'sample':sid, 'quote':p['conflicts_with'], 'located':located(essay, p['conflicts_with'])})
    raw_map = raw['argument']
    raw_argument_entry_total += int(raw_map.get('position') is not None) + sum(len(raw_map.get(k) or []) for k in ('paragraphs','problems','improvements'))
    source_paragraphs = [p for p in essay.replace('\r\n','\n').replace('\r','\n').split('\n') if p.strip()]
    paragraphs.append({'sample':sid, 'original':len(source_paragraphs), 'returned':len(raw_map['paragraphs']),
                       'adopted':len(mapped['paragraphs']), 'p':[p['p'] for p in mapped['paragraphs']]})

assert raw_argument_entry_total == argument_counts['returned']
assert argument_counts['returned'] == sum(argument_counts[k] for k in ('kept','dropped','duplicates','over_limit'))
for key in ('returned','kept','dropped','duplicates','over_limit','self_conflicts','suggestions_removed','paragraphs','problems','improvements'):
    assert argument_counts[key] == report['argument'][key], key
assert dict(argument_types) == report['argument']['problem_types']
assert dict(verdicts) == report['argument']['paragraph_verdicts']
assert scored_criteria == report['evidence']['scored_criteria']
assert len(evidence) == report['evidence']['quotes']

sanity = report['sanity']['checks']
active = [c for c in sanity if c['ok'] is not None]
skipped = [c for c in sanity if c['ok'] is None]
assert report['sanity']['total'] == len(active)
assert report['sanity']['passed'] == sum(c['ok'] is True for c in active)
assert report['sanity']['skipped'] == len(skipped)
argument_checks = [c for c in active if any(k in c['check'] for k in ('论证问题','不应出现','找到可核实的立场句','应标出'))]
task1_check = next(c for c in active if c['check'].startswith('指出文内数据矛盾'))

t1 = samples['t1-no-image']
t1_raw = adopted_raw['t1-no-image']
t1_result = t1['generations']['evaluate']['result']
t1_essay = t1['submission']['essay_text']
t1_quote_audit = []
for comparison in t1_raw['comparisons']:
    for kind, quote in [('claim',comparison['claim'])] + [('figure',q) for q in comparison.get('figures',[])]:
        t1_quote_audit.append({'kind':kind, 'quote':quote, 'located':located(t1_essay, quote)})
explanations = []
def collect(value, path=''):
    if isinstance(value, dict):
        for key, text in value.items():
            location = path + '/' + key
            if key in ('summary','comment','suggestion','overall_comment') and isinstance(text,str) and text.strip():
                explanations.append({'path':location, 'contains_chinese':bool(re.search(r'[\u4e00-\u9fff]',text)), 'text':text})
            elif key == 'priorities' and isinstance(text,list):
                for i, item in enumerate(text):
                    if isinstance(item,str):
                        explanations.append({'path':location+'/'+str(i), 'contains_chinese':bool(re.search(r'[\u4e00-\u9fff]',item)), 'text':item})
            else:
                collect(text, location)
    elif isinstance(value,list):
        for i, item in enumerate(value):
            collect(item,path+'/'+str(i))
collect(t1_raw)

out = {
    'source_head':report['audit']['source_head'], 'audit_network_calls':0,
    'transport':{'request_attempts':transport['request_attempts'],'limit':transport['limit'],'completed':transport['completed'],
        'status_counts':dict(Counter(str(r['http_status']) for r in transport['responses'])),
        'finish_reasons':dict(Counter(r['finish_reason'] for r in transport['responses'])),
        'kind_counts':dict(Counter(c['kind'] for c in calls))},
    'validation':{'first_attempts':len(first_calls),'json_decoded_objects':len(decoded),'json_failures':json_failures,
        'ready':sum(s['generations']['evaluate']['status']=='ready' for s in samples.values()),
        'retries':sum(c['attempt']>0 for c in calls)},
    'usage':usage, 'completion_peak':max(c['usage']['completion_tokens'] for c in calls), 'completion_cap':4500,
    'evidence':{'criteria':scored_criteria,'quotes':len(evidence),'located':sum(q['located'] for q in evidence),'exact':sum(q['exact'] for q in evidence)},
    'argument':{**dict(argument_counts), 'raw_entry_count':raw_argument_entry_total,
        'quotes':len(argument_quotes),'quotes_located':sum(q['located'] for q in argument_quotes),
        'quotes_exact':sum(q['exact'] for q in argument_quotes),
        'conflicts_with_quotes':len(conflict_quotes),'conflicts_with_located':sum(q['located'] for q in conflict_quotes),
        'problem_types':dict(argument_types),'paragraph_verdicts':dict(verdicts)},
    'paragraph_counts':paragraphs,
    'suggestions_removed_all_paths':dict(removed_total), 'suggestions_removed_by_sample':removed_by_sample,
    'removed_advice_texts':removed_texts,
    'removal_interpretation':'Both removed entries are 260-word target recommendations, not fabricated statistics. This is a conservative filter false positive; no model call was repeated.',
    'report_scope_note':'Automatic report.argument.suggestions_removed is argument-only (0); full evaluation advice removals are criteria1+priorities1+argument0=2, all in under-length sample.',
    'sanity':{'passed':sum(c['ok'] is True for c in active),'total':len(active),'skipped':skipped,
        'argument_passed':sum(c['ok'] for c in argument_checks),'argument_total':len(argument_checks),
        'task1_consistency_check':task1_check},
    'task1':{'comparisons_checked':t1_result['comparisons_checked'], 'raw_comparisons':t1_raw['comparisons'],
        'normalized_consistency_issues':t1_result['consistency_issues'],
        'quote_audit':t1_quote_audit,
        'ta_state':t1_result['criteria'][0]['state'], 'overall_band':t1_result['overall_band'],
        'explanation_fields':len(explanations),'fields_containing_chinese':sum(e['contains_chinese'] for e in explanations),
        'english_only_fields':[e for e in explanations if not e['contains_chinese']]},
    'automatic_metric_consistency':'All compared recorded metrics agree; full advice removal totals are supplementary and are not in automatic argument-only metric.',
}
assert all(q['located'] for q in evidence + argument_quotes + conflict_quotes)
args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:out[k] for k in ('transport','validation','usage','completion_peak','evidence','argument','suggestions_removed_all_paths','removed_advice_texts','sanity')},ensure_ascii=False,indent=2))
print('Task1 explanation fields:',len(explanations),'Chinese:',out['task1']['fields_containing_chinese'])
