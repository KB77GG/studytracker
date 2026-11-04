"""Offline defect reproduction on 2ed268c1; exit 0 means the documented bugs reproduce.

No model calls or private configuration. Invert assertions after fixing the bugs.
"""
from pathlib import Path
import json,sys
repo=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(repo))
from tools.ielts_writing_ai import rewrite_quality as rq, review, essay
from tools.ielts_writing_ai.llm import parse_strict_json
fix=json.loads((repo/'tools/ielts_writing_ai/tests/fixtures/realcheck_20261104.json').read_text())

def check(raw,sub):
 r=review.normalize_rewrite(raw,sub)
 return {'words':r['word_count'],'quality_passed':r['quality_passed'],'issues':[x['code'] for x in r['quality_issues']],'notes':r['key_changes'],'rationale':r['band_rationale']}
weak=fix['rewrites']['t2-weak']
raw=parse_strict_json(weak['raw_text']);sub=dict(weak['submission'])
raw['band_rationale']='为了向目标分数段靠近，重组论证并修正语言。'
out={}
out['honest_weak_baseline']=check(raw,sub)
changed=dict(raw,key_changes=['改写稿共330词，扩展了原稿的论据。'])
out['false_count_330_whitelisted']=check(changed,sub)
out['false_count_330_whitelisted']['actual_claim']='330'
out['chinese_score_claim']=check(dict(raw,band_rationale='本篇已达到雅思写作7分标准。'),sub)
item=fix['rewrites']['t1-no-image']; raw1=parse_strict_json(item['raw_text']); sub1=item['submission']
raw1['key_changes']=['根据学生原稿整理段落，保留现有数字。']
raw1['band_rationale']='题图缺失，无法确认数据准确。'
out['negated_data_accuracy']=check(raw1,sub1)
raw1['band_rationale']='题图缺失，不能保证数据正确。'
out['negated_data_accuracy_2']=check(raw1,sub1)
prompt='In many countries, young people are encouraged to work or travel for a year between finishing high school and starting university studies. Discuss the advantages and disadvantages for young people who decide to do this.'
response='''Taking a gap year after graduation can be a valuable opportunity, but it also carries risks. In my view, the benefits depend on whether the break has a clear purpose and a realistic budget.

One advantage is greater maturity. A teenager who spends several months earning a salary must arrive on time, cooperate with colleagues and deal politely with customers. These responsibilities develop independence and help someone who has always relied on parents understand the demands of adult life. Visiting another country can have a similar effect: arranging accommodation, communicating in an unfamiliar language and adapting to different customs encourage confidence. Such experiences can also clarify career ambitions before an applicant commits to an expensive degree.

However, postponing higher education can bring financial difficulties. Air fares and accommodation are costly, especially for families with limited savings. Even a temporary job may offer little security, leaving the graduate with neither useful qualifications nor enough money for tuition. Another concern is the loss of academic habits. After months away from books, returning to lectures and examinations may feel difficult. Friends will already be further ahead in their courses, which can create pressure to abandon a degree altogether.

These drawbacks do not make every gap year a mistake. A structured plan can reduce them: the participant could save a fixed amount, undertake a short placement related to a future profession and reserve regular time for reading. Parents should discuss practical expectations without treating an overseas adventure as compulsory.

Overall, a planned break can broaden a teenager's perspective and strengthen independence, while an unstructured one can waste money and delay qualifications. The best choice therefore depends on personal circumstances rather than a universal rule.'''
sub2=dict(sub,prompt_text=prompt,essay_text=response,word_count=essay.count_words(response))
raw2={'essay':response,'key_changes':['明确两方面后果，并以规划是否充分作为判断依据。'],'band_rationale':'组织正反论证，补充具体解释；没有对改写稿另行评分。'}
out['on_topic_gap_year_paraphrase']=check(raw2,sub2)
out['on_topic_gap_year_paraphrase'].update({'prompt':prompt,'essay':response,'coverage':rq.prompt_coverage(prompt,response),'prompt_terms':sorted(rq.prompt_terms(prompt))})
# The same substantive answer, with test instructions appended to the question.
sub3=dict(sub2,prompt_text=prompt+' You should spend about 40 minutes on this task. Write at least 250 words.')
out['same_answer_with_exam_instructions']=check(raw2,sub3)
out['same_answer_with_exam_instructions']['coverage']=rq.prompt_coverage(sub3['prompt_text'],response)
out['case_only_legitimate_change']=check(dict(raw,key_changes=['将“i partly agree”改为“I partly agree”，修正句首大写。']),sub)
t=fix['evaluations']['t1-no-image']; evaluation_raw=parse_strict_json(t['raw_text'])
old=review.normalize_evaluation(evaluation_raw,t['submission'])
evaluation_raw['consistency_issues']=[{'quote':'Invented country Z has 999 percent ownership.','comment':'原文存在严重数字矛盾。'}]
new=review.normalize_evaluation(evaluation_raw,t['submission'])
out['task1_consistency_optional_field']={'without_field':old['consistency_issues'],'unverifiable':new['consistency_issues'],'warnings':new['warnings']}
off=fix['rewrites']['t2-off-topic']; off_raw=parse_strict_json(off['raw_text']); off_sub=off['submission']
off_raw['essay']='Government spending on public transport and building roads is a familiar question. However, this response considers online learning.\n\n'+off_raw['essay']
off_raw['key_changes']=['整理在线学习和课堂教学的优缺点。']
off_raw['band_rationale']='按两种教学形式组织论证，没有独立评定改写分数。'
out['off_topic_with_keyword_preface']=check(off_raw,off_sub)
out['off_topic_with_keyword_preface']['coverage']=rq.prompt_coverage(off_sub['prompt_text'],off_raw['essay'])
assert out['off_topic_with_keyword_preface']['quality_passed']
assert out['on_topic_gap_year_paraphrase']['issues']==['off_prompt']
assert out['negated_data_accuracy']['issues']==['data_claim']
assert out['false_count_330_whitelisted']['quality_passed']
assert out['chinese_score_claim']['quality_passed']
assert out['case_only_legitimate_change']['issues']==['noop_change','no_changes']
print(json.dumps(out,ensure_ascii=False,indent=2))
Path(__file__).with_suffix('.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
