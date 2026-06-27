#!/usr/bin/env python3
"""Build an original 60-part IELTS grammar practice pack.

This script does not read or copy exercises from the referenced textbook.
It uses the book's topic coverage only, then generates original questions in
the MaterialBank-compatible JSON shape plus review-friendly CSV exports.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "ielts_grammar_60"


def topic(unit, title_en, title_cn, focus, pairs):
    return {
        "unit": unit,
        "title_en": title_en,
        "title_cn": title_cn,
        "focus": focus,
        "pairs": pairs,
    }


# Pair format:
#   (sentence containing ___, correct fill, distractor fill, explanation)
TOPICS = [
    topic(1, "Present simple vs present continuous", "一般现在时与现在进行时",
          "区分常态、规律与当前阶段正在发生的动作。",
          [
              ("The research team usually ___ its findings in June.", "publishes", "is publishing", "usually 表示固定规律，用一般现在时。"),
              ("This semester, Maya ___ in the university library while her office is renovated.", "is working", "works", "this semester 表示暂时阶段，用现在进行时。"),
              ("Water ___ at 100 degrees Celsius at sea level.", "boils", "is boiling", "客观事实用一般现在时。"),
              ("Please be quiet; the candidates ___ the listening test now.", "are taking", "take", "now 指此刻正在进行。"),
          ]),
    topic(1, "State verbs", "状态动词",
          "掌握 know, believe, own, understand 等通常不用进行时的动词。",
          [
              ("I ___ why the chart shows a sudden decline.", "understand", "am understanding", "understand 表示认知状态，通常不用进行时。"),
              ("The college ___ three language laboratories.", "owns", "is owning", "own 表示拥有，是状态动词。"),
              ("She ___ the new timetable is more practical.", "believes", "is believing", "believe 表示观点状态。"),
              ("This soup ___ too salty to me.", "tastes", "is tasting", "taste 表示感官状态时不用进行时。"),
          ]),
    topic(2, "Past simple vs past continuous", "一般过去时与过去进行时",
          "用过去进行时交代背景，用一般过去时表示完成或打断的事件。",
          [
              ("While I ___ the report, the fire alarm rang.", "was editing", "edited", "持续背景动作使用过去进行时。"),
              ("The number of visitors ___ sharply in 2022.", "fell", "was falling", "明确时间内完成的变化用一般过去时。"),
              ("At 8 p.m. yesterday, the students ___ for the mock test.", "were preparing", "prepared", "过去某一时刻正在发生的动作。"),
              ("She ___ the email and immediately called her tutor.", "read", "was reading", "连续完成动作使用一般过去时。"),
          ]),
    topic(2, "Used to and would", "used to 与 would",
          "描述过去习惯及已不存在的过去状态。",
          [
              ("The building ___ a public library before it became a museum.", "used to be", "would be", "过去状态用 used to，不能用 would。"),
              ("Every summer, we ___ our grandparents by the coast.", "would visit", "would visited", "would + 动词原形可表示过去反复动作。"),
              ("People ___ rely on printed maps before smartphones became common.", "used to", "were used to", "used to + 动词原形表示过去习惯。"),
              ("My old teacher ___ give us a short quiz every Friday.", "would", "used", "would + 动词原形表示过去反复动作。"),
          ]),
    topic(3, "Present perfect vs past simple", "现在完成时与一般过去时",
          "区分未结束时间、当前结果与明确过去时间。",
          [
              ("Researchers ___ several solutions so far.", "have proposed", "proposed", "so far 与现在完成时连用。"),
              ("The council ___ the policy in 2019.", "introduced", "has introduced", "明确过去时间 in 2019 用一般过去时。"),
              ("I ___ this article twice, so I know its main argument.", "have read", "read", "经历与当前结果相关，用现在完成时。"),
              ("She ___ her degree last July.", "completed", "has completed", "last July 是已结束的过去时间。"),
          ]),
    topic(3, "Present perfect continuous", "现在完成进行时",
          "强调从过去持续至今的活动、过程或近期反复行为。",
          [
              ("The city ___ its cycle network since 2020.", "has been expanding", "is expanding", "since 2020 表示从过去持续至今。"),
              ("How long ___ for the IELTS exam?", "have you been preparing", "are you preparing", "询问持续到现在的时长用现在完成进行时。"),
              ("It ___ all morning, so the roads are wet.", "has been raining", "rained", "持续过程造成当前可见结果。"),
              ("They ___ data for three months and are not finished yet.", "have been collecting", "collected", "for three months 且尚未结束。"),
          ]),
    topic(4, "Past perfect simple", "过去完成时",
          "表达在另一过去动作或时间之前已经完成的事件。",
          [
              ("By the time the lecture began, we ___ our seats.", "had found", "found", "先于 began 完成的动作使用过去完成时。"),
              ("She was relieved because she ___ the application before the deadline.", "had submitted", "submitted", "提交发生在感到放心之前。"),
              ("After the company ___ the survey, it changed its strategy.", "had analysed", "analysed", "强调分析先于改变策略。"),
              ("The village looked different because several new roads ___ built.", "had been", "were", "过去参照点前已建成，用过去完成时被动。"),
          ]),
    topic(4, "Past perfect continuous", "过去完成进行时",
          "强调持续到某个过去参照点之前的过程及其结果。",
          [
              ("They ___ for two hours before the bus finally arrived.", "had been waiting", "were waiting", "等待持续到另一个过去事件之前。"),
              ("Her eyes were tired because she ___ all night.", "had been studying", "studied", "过去持续过程解释当时的结果。"),
              ("The river overflowed after it ___ heavily for several days.", "had been raining", "was raining", "降雨过程持续在河水泛滥之前。"),
              ("Before the funding ended, the team ___ the issue for a decade.", "had been researching", "researched", "for a decade 强调持续过程。"),
          ]),
    topic(5, "Future plans and intentions", "未来计划与打算",
          "用现在进行时表示已安排计划，用 be going to 表示意图。",
          [
              ("We ___ the admissions officer at 10 a.m. tomorrow.", "are meeting", "meet", "有具体时间的个人安排可用现在进行时。"),
              ("I ___ apply for a postgraduate course next year.", "am going to", "will going to", "be going to + 动词原形表示打算。"),
              ("The researchers ___ their results at Friday's conference.", "are presenting", "present", "已安排的近期计划用现在进行时。"),
              ("She has saved enough money and ___ buy a new laptop.", "is going to", "is buying to", "已有意图和准备，用 be going to。"),
          ]),
    topic(5, "Predictions with will and going to", "will 与 going to 表示预测",
          "区分基于观点的预测与基于当前证据的预测。",
          [
              ("I think online learning ___ remain important.", "will", "is going", "I think 引出的观点预测常用 will。"),
              ("Look at those dark clouds; it ___ rain.", "is going to", "will to", "基于眼前证据的预测用 be going to。"),
              ("Experts believe the population ___ continue to grow.", "will", "is continuing", "believe 表示观点预测。"),
              ("The glass is at the edge of the table; it ___ fall.", "is going to", "will falling", "当前迹象显示即将发生。"),
          ]),
    topic(6, "Future continuous and future perfect", "将来进行时与将来完成时",
          "表达将来某时正在进行或在将来期限前已经完成。",
          [
              ("This time next week, I ___ my final exam.", "will be taking", "will take", "将来某一时刻正在进行，用将来进行时。"),
              ("By 2030, the city ___ three new metro lines.", "will have built", "will build", "by 2030 强调届时已完成。"),
              ("At noon tomorrow, the committee ___ the proposal.", "will be discussing", "will have discussed", "将来具体时刻正在进行。"),
              ("By the end of the course, students ___ six essays.", "will have written", "will be writing", "by the end 表示截止时已完成。"),
          ]),
    topic(7, "Countable and uncountable nouns", "可数与不可数名词",
          "识别常见学术不可数名词及其正确数量表达。",
          [
              ("The report provides useful ___ about housing costs.", "information", "informations", "information 是不可数名词。"),
              ("The survey included 500 ___.", "participants", "participant", "可数名词在数量 500 后用复数。"),
              ("We need more ___ before drawing a conclusion.", "evidence", "evidences", "evidence 通常不可数。"),
              ("The laboratory purchased several new pieces of ___.", "equipment", "equipments", "equipment 不可数，可用 pieces of。"),
          ]),
    topic(7, "Quantifiers", "数量限定词",
          "正确使用 many, much, few, little, a number of 与 an amount of。",
          [
              ("Only ___ students attended the optional workshop.", "a few", "a little", "students 是可数复数，用 a few。"),
              ("The project received very ___ financial support.", "little", "few", "support 不可数，用 little。"),
              ("A large number of people ___ the new policy.", "support", "supports", "a number of + 复数名词，谓语用复数。"),
              ("There isn't ___ reliable information available.", "much", "many", "information 不可数，用 much。"),
          ]),
    topic(8, "Articles", "冠词",
          "在首次提及、特指、泛指及独一事物中选择 a/an, the 或零冠词。",
          [
              ("The study identified ___ unexpected pattern in the data.", "an", "the", "首次提及且 unexpected 以元音音素开头，用 an。"),
              ("___ pattern was most visible among younger participants.", "The", "A", "再次提及前句中的 pattern，用 the。"),
              ("___ can reduce social inequality.", "Education", "The education", "education 表示抽象泛指时用零冠词。"),
              ("The Earth moves around ___ Sun.", "the", "a", "独一的太阳用 the。"),
          ]),
    topic(8, "Other determiners", "其他限定词",
          "正确使用 each, every, both, either, neither, another 与 other。",
          [
              ("___ participant received a numbered questionnaire.", "Each", "Both", "each + 单数名词，强调个体。"),
              ("The two methods are useful, and ___ have clear limitations.", "both", "every", "指两者都，用 both。"),
              ("Neither of the explanations ___ fully convincing.", "is", "are", "正式英语中 neither of 常接单数谓语。"),
              ("We need ___ week to complete the analysis.", "another", "other", "another + 单数名词表示再一个。"),
          ]),
    topic(9, "Personal, possessive and reflexive pronouns", "人称、物主与反身代词",
          "根据句法位置和指代关系选择正确代词。",
          [
              ("The researchers designed the questionnaire ___.", "themselves", "theirselves", "反身代词应为 themselves。"),
              ("Maria and I submitted ___ assignments on time.", "our", "ours", "名词 assignments 前用形容词性物主代词。"),
              ("The tutor gave Daniel and ___ detailed feedback.", "me", "I", "介词/动词宾语位置用宾格 me。"),
              ("This desk is mine, and that one is ___.", "hers", "her", "不接名词时用名词性物主代词 hers。"),
          ]),
    topic(9, "Reference and avoiding repetition", "指代与避免重复",
          "使用 one/ones, this/that, these/those 等保持衔接并避免重复。",
          [
              ("The first proposal was expensive, but the second ___ was affordable.", "one", "it", "one 替代同类可数名词 proposal。"),
              ("Urban rents rose rapidly. ___ affected low-income families most.", "This", "These", "this 可指代前面整个情况。"),
              ("The old regulations were stricter than the current ___.", "ones", "one", "regulations 为复数，用 ones。"),
              ("Two explanations were offered, but neither of ___ was convincing.", "them", "those", "介词 of 后指代具体两项，用 them。"),
          ]),
    topic(10, "Adjectives and participle adjectives", "形容词与分词形容词",
          "区分 -ed/-ing 形容词并掌握常见形容词位置。",
          [
              ("The students found the lecture extremely ___.", "interesting", "interested", "事物令人产生感受，用 -ing 形容词。"),
              ("Many residents were ___ by the sudden announcement.", "surprised", "surprising", "人感到惊讶，用 -ed 形容词。"),
              ("The report presents a ___ analysis of the issue.", "detailed", "detail", "名词 analysis 前需形容词 detailed。"),
              ("It was a highly ___ experiment.", "successful", "success", "副词 highly 修饰形容词 successful。"),
          ]),
    topic(10, "Adverbs of manner, place, time and frequency", "方式、地点、时间与频率副词",
          "选择正确副词形式并安排常见副词位置。",
          [
              ("The speaker explained the process ___.", "clearly", "clear", "修饰动词 explained 用副词 clearly。"),
              ("Students usually ___ their results online.", "check", "are checking usually", "频率副词通常位于实义动词前。"),
              ("The population increased ___ between 2010 and 2020.", "steadily", "steady", "修饰 increased 用副词。"),
              ("The equipment is stored ___ in a secure room.", "downstairs", "downstair", "地点副词 downstairs 无复数形式。"),
          ]),
    topic(11, "Comparatives and superlatives", "比较级与最高级",
          "构成并使用形容词、副词的比较级和最高级。",
          [
              ("Public transport is ___ than driving during rush hour.", "more efficient", "more efficiently", "be 动词后作表语用形容词。"),
              ("This was the ___ result in the entire survey.", "most significant", "more significant", "在全部范围内比较用最高级。"),
              ("The second group responded ___ than the first.", "more quickly", "quicker", "修饰 responded 用副词比较级。"),
              ("Housing was ___ expensive in the capital.", "the most", "the more", "限定范围内最高程度用 the most。"),
          ]),
    topic(11, "Other ways of comparing", "其他比较结构",
          "使用 as...as, similar to, different from, twice as...as 等结构。",
          [
              ("The new system is not ___ the old one.", "as reliable as", "as reliable than", "同级比较用 as + 形容词 + as。"),
              ("The two regions are similar ___ population size.", "in", "with", "be similar in + 比较方面。"),
              ("City A has twice ___ residents as City B.", "as many", "more", "倍数结构：twice as many + 复数名词 + as。"),
              ("The results were significantly different ___ our expectations.", "from", "than", "标准搭配 different from。"),
          ]),
    topic(12, "Noun plus prepositional phrase", "名词加介词短语",
          "用介词短语准确后置修饰名词。",
          [
              ("The increase ___ online enrolment was particularly sharp.", "in", "of", "an increase in something。"),
              ("The demand ___ affordable housing continues to grow.", "for", "of", "demand for 是固定搭配。"),
              ("Researchers examined the effects ___ noise on concentration.", "of", "for", "the effects of A on B。"),
              ("The solution ___ the problem requires long-term funding.", "to", "of", "solution to a problem。"),
          ]),
    topic(12, "Participle and infinitive noun phrases", "分词与不定式名词短语",
          "使用分词短语或 to-infinitive 对名词进行紧凑修饰。",
          [
              ("Students ___ overseas often develop greater independence.", "studying", "studied", "主动进行的动作使用现在分词 studying。"),
              ("The data ___ from the survey were analysed twice.", "collected", "collecting", "data 与 collect 为被动关系，用过去分词。"),
              ("The next task ___ is the literature review.", "to complete", "completing", "the next + 名词常接 to-infinitive 表待做事项。"),
              ("Applicants ___ for funding must submit a budget.", "hoping", "hoped", "applicants 主动希望，使用现在分词。"),
          ]),
    topic(13, "Modals of ability and possibility", "能力与可能性情态动词",
          "使用 can, could, may, might 表达能力及不同程度可能性。",
          [
              ("This method ___ reduce energy use by up to 20 percent.", "may", "must to", "may + 动词原形表示可能性。"),
              ("When she was six, she ___ read in two languages.", "could", "can", "过去的一般能力用 could。"),
              ("The results ___ be affected by the small sample size.", "might", "might to", "might 后接动词原形。"),
              ("With further training, staff ___ use the software more effectively.", "could", "could to", "could 表示潜在能力。"),
          ]),
    topic(13, "Alternatives to modal verbs", "情态动词替代表达",
          "使用 be able to, be likely to, be allowed to 等替代结构。",
          [
              ("After the upgrade, users will ___ access the database remotely.", "be able to", "can to", "will 后用 be able to 表示将来能力。"),
              ("The policy is ___ reduce traffic in the city centre.", "likely to", "likely", "be likely to + 动词原形。"),
              ("Visitors are not ___ enter the laboratory.", "allowed to", "allowed", "be allowed to + 动词原形。"),
              ("The team has ___ solve the technical problem.", "managed to", "could to", "manage to 可表示成功完成某事。"),
          ]),
    topic(14, "Obligation and necessity", "义务与必要性",
          "区分 must, have to, need to, mustn't 与 don't have to。",
          [
              ("All candidates ___ bring photo identification.", "must", "must to", "must 后直接接动词原形。"),
              ("You ___ print the form; an electronic copy is acceptable.", "don't have to", "mustn't", "不必做用 don't have to，不是禁止。"),
              ("Laboratory users ___ wear protective glasses.", "have to", "have", "have to 表示外部规定。"),
              ("Students ___ share their login details with anyone.", "mustn't", "don't have to", "mustn't 表示禁止。"),
          ]),
    topic(14, "Suggestions and advice", "建议与劝告",
          "使用 should, ought to, had better 及建议句型。",
          [
              ("The council ___ invest more in public transport.", "should", "should to", "should 后接动词原形。"),
              ("You had better ___ your sources before submitting the essay.", "check", "to check", "had better 后接动词原形。"),
              ("I suggest ___ the introduction more concise.", "making", "to make", "suggest 后常接 -ing。"),
              ("Applicants ought ___ the instructions carefully.", "to read", "read", "ought 后需接 to-infinitive。"),
          ]),
    topic(15, "Reported statements and tense changes", "间接引语与时态变化",
          "在过去报告动词后进行常见时态后移。",
          [
              ("She said that she ___ the assignment.", "had finished", "has finished", "过去报告动词后，原现在完成时常后移为过去完成时。"),
              ("He explained that the course ___ difficult.", "was", "is", "原一般现在时在过去叙述中常后移为一般过去时。"),
              ("They said they ___ the following week.", "would return", "will return", "will 在间接引语中常变为 would。"),
              ("Mina told us that she ___ at home that day.", "was working", "is working", "现在进行时常后移为过去进行时。"),
          ]),
    topic(15, "Reported questions and time references", "间接问句与时间指代",
          "使用陈述语序，并调整代词、时间和地点表达。",
          [
              ("She asked me where I ___.", "lived", "did I live", "间接问句使用陈述语序。"),
              ("He asked whether the library ___ open.", "was", "was it", "whether 后使用陈述语序。"),
              ("They said they would finish the work ___.", "the next day", "tomorrow", "过去转述中 tomorrow 常变为 the next day。"),
              ("The tutor asked why I ___ the previous class.", "had missed", "did miss", "间接 why 问句不用助动词倒装。"),
          ]),
    topic(15, "Reporting verbs", "转述动词",
          "掌握 advise, suggest, admit, deny, promise 等动词的补语结构。",
          [
              ("The tutor advised me ___ the paragraph.", "to rewrite", "rewriting", "advise someone to do something。"),
              ("She admitted ___ the deadline.", "missing", "to miss", "admit 后接 -ing。"),
              ("They promised ___ the results by Friday.", "to publish", "publishing", "promise 后接 to-infinitive。"),
              ("The manager denied ___ the figures.", "changing", "to change", "deny 后接 -ing。"),
          ]),
    topic(16, "Verb plus to-infinitive", "动词加不定式",
          "掌握 decide, hope, plan, refuse, afford 等后接 to-infinitive。",
          [
              ("The university plans ___ a new research centre.", "to open", "opening", "plan 后接 to-infinitive。"),
              ("We cannot afford ___ the evidence.", "to ignore", "ignoring", "afford 后接 to-infinitive。"),
              ("She decided ___ the exam in October.", "to take", "taking", "decide 后接 to-infinitive。"),
              ("The company refused ___ further details.", "to provide", "providing", "refuse 后接 to-infinitive。"),
          ]),
    topic(16, "Verb plus -ing", "动词加 -ing",
          "掌握 avoid, consider, enjoy, finish, suggest 等后接动名词。",
          [
              ("Researchers should avoid ___ conclusions too quickly.", "drawing", "to draw", "avoid 后接 -ing。"),
              ("The committee considered ___ the deadline.", "extending", "to extend", "consider 后接 -ing。"),
              ("She finished ___ the final section.", "writing", "to write", "finish 后接 -ing。"),
              ("They suggested ___ a pilot study first.", "conducting", "to conduct", "suggest 后接 -ing。"),
          ]),
    topic(16, "Verb plus preposition plus -ing", "动词加介词再加 -ing",
          "识别介词后的动名词形式，如 insist on, succeed in, apologise for。",
          [
              ("The team succeeded in ___ the error.", "identifying", "identify", "介词 in 后接 -ing。"),
              ("He apologised for ___ the meeting.", "missing", "miss", "介词 for 后接 -ing。"),
              ("They insisted on ___ the data independently.", "checking", "check", "insist on 后接 -ing。"),
              ("The course focuses on ___ academic vocabulary.", "developing", "develop", "focus on 后接 -ing。"),
          ]),
    topic(16, "Bare infinitive", "不带 to 的不定式",
          "在情态动词、make/let 及部分感官结构后使用动词原形。",
          [
              ("The new software can ___ large datasets quickly.", "process", "to process", "情态动词 can 后接动词原形。"),
              ("The supervisor made us ___ the analysis.", "repeat", "to repeat", "主动语态 make someone do。"),
              ("The rules do not let visitors ___ photographs.", "take", "to take", "let someone do。"),
              ("We heard the speaker ___ our names.", "mention", "to mention", "hear + 宾语 + 动词原形可表示完整动作。"),
          ]),
    topic(17, "Zero and first conditionals", "零条件句与第一条件句",
          "表达普遍规律及真实可能的未来条件。",
          [
              ("If water reaches 0 degrees Celsius, it ___.", "freezes", "will freeze", "普遍规律用零条件句：一般现在时。"),
              ("If the weather improves, we ___ the fieldwork tomorrow.", "will continue", "continue would", "真实未来条件用 if + 现在时，主句 will。"),
              ("Plants die if they ___ enough light.", "do not receive", "will not receive", "普遍事实的 if 从句用一般现在时。"),
              ("Unless we leave now, we ___ the train.", "will miss", "missed", "unless 引导真实未来条件，主句用 will。"),
          ]),
    topic(17, "Second conditional", "第二条件句",
          "表达现在或未来不太可能、假设性的情况。",
          [
              ("If I had more time, I ___ another language.", "would learn", "will learn", "第二条件句：if + 过去时，would + 动词原形。"),
              ("The city would be quieter if fewer people ___ to work.", "drove", "would drive", "if 从句不用 would。"),
              ("If the course were cheaper, more students ___ it.", "would take", "took", "假设结果用 would + 动词原形。"),
              ("What would you do if you ___ the scholarship?", "received", "would receive", "if 从句使用过去式。"),
          ]),
    topic(17, "Unless, provided and other condition markers", "unless、provided 等条件连接词",
          "使用 unless, provided that, as long as, in case 等引入条件。",
          [
              ("You cannot enter the exam room ___ you show identification.", "unless", "provided", "unless = if not。"),
              ("You may borrow the equipment ___ you return it by Friday.", "provided that", "unless", "provided that 表示只要满足条件。"),
              ("We will finish on time ___ no further problems arise.", "as long as", "in case", "as long as 表示只要。"),
              ("Take a printed copy ___ the internet connection fails.", "in case", "unless", "in case 表示以防。"),
          ]),
    topic(18, "Third conditional", "第三条件句",
          "表达与过去事实相反的假设及其结果。",
          [
              ("If they had left earlier, they ___ the train.", "would have caught", "would catch", "第三条件句主句用 would have + 过去分词。"),
              ("The experiment would have succeeded if the equipment ___ properly.", "had worked", "worked", "if 从句用过去完成时。"),
              ("If I had known about the deadline, I ___ sooner.", "would have applied", "would apply", "过去未发生结果用 would have applied。"),
              ("She would not have made the error if she ___ the instructions.", "had read", "would have read", "if 从句不用 would have。"),
          ]),
    topic(18, "Mixed conditionals", "混合条件句",
          "连接过去条件与现在结果，或现在状态与过去结果。",
          [
              ("If I had studied engineering, I ___ in that field now.", "would be working", "would have worked", "过去条件造成现在结果。"),
              ("If she were more organised, she ___ the deadline yesterday.", "would not have missed", "would not miss", "现在特征影响过去结果。"),
              ("They would be healthier now if they ___ the advice earlier.", "had followed", "followed", "过去未做造成现在状态。"),
              ("If he spoke French, he ___ for the position last year.", "could have applied", "could apply", "现在能力不足影响过去机会。"),
          ]),
    topic(18, "Wishes, regrets and should have", "愿望、遗憾与 should have",
          "表达对现在或过去的非真实愿望、批评和遗憾。",
          [
              ("I wish I ___ more confident when speaking in public.", "were", "am", "对现在的非真实愿望用过去式。"),
              ("She wishes she ___ the offer last year.", "had accepted", "accepted", "对过去的遗憾用过去完成时。"),
              ("You should ___ the references before submitting.", "have checked", "checked", "should have + 过去分词表示过去本应做。"),
              ("If only the council ___ action sooner.", "had taken", "would take", "if only + 过去完成时表达过去遗憾。"),
          ]),
    topic(19, "Verb-dependent prepositions", "动词固定介词",
          "掌握 depend on, contribute to, result in/from, participate in 等搭配。",
          [
              ("Success often depends ___ careful planning.", "on", "of", "depend on 是固定搭配。"),
              ("Regular exercise contributes ___ better mental health.", "to", "for", "contribute to 是固定搭配。"),
              ("The delay resulted ___ a technical fault.", "from", "in", "result from 表示由某原因造成。"),
              ("More than 800 people participated ___ the survey.", "in", "at", "participate in 是固定搭配。"),
          ]),
    topic(19, "Adjective and noun prepositions", "形容词、名词固定介词",
          "掌握 responsible for, interested in, impact on, reason for 等搭配。",
          [
              ("Local authorities are responsible ___ waste collection.", "for", "of", "responsible for 是固定搭配。"),
              ("Students were interested ___ the exchange programme.", "in", "on", "interested in 是固定搭配。"),
              ("Technology has a major impact ___ working patterns.", "on", "to", "impact on 是固定搭配。"),
              ("The main reason ___ the decline remains unclear.", "for", "of", "reason for 是固定搭配。"),
          ]),
    topic(19, "Prepositional phrases", "介词短语",
          "使用 in contrast, in addition to, on behalf of, with regard to 等学术短语。",
          [
              ("___ contrast to the national trend, local sales increased.", "In", "On", "in contrast to 是固定短语。"),
              ("___ addition to lower costs, the plan offers greater flexibility.", "In", "At", "in addition to 是固定短语。"),
              ("She spoke ___ behalf of the research team.", "on", "in", "on behalf of 是固定短语。"),
              ("The report raises concerns ___ regard to data privacy.", "with", "by", "with regard to 是固定短语。"),
          ]),
    topic(20, "Defining relative clauses", "限定性定语从句",
          "使用 who, which, that, whose 等提供识别所必需的信息。",
          [
              ("Students ___ submit late work must provide a reason.", "who", "which", "指人并作主语用 who。"),
              ("The device ___ measures air quality is solar-powered.", "that", "who", "指物可用 that。"),
              ("The researcher ___ article won the prize teaches here.", "whose", "who", "表示所属关系用 whose。"),
              ("The town ___ we visited has expanded rapidly.", "that", "where", "关系代词作 visited 的宾语，可用 that。"),
          ]),
    topic(20, "Non-defining relative clauses", "非限定性定语从句",
          "使用逗号补充非必要信息，并避免误用 that。",
          [
              ("The new library, ___ opened in May, is already popular.", "which", "that", "非限定性定语从句不能用 that。"),
              ("Professor Lee, ___ leads the project, will present the findings.", "who", "that", "指人且为补充信息，用 who。"),
              ("The survey, ___ results were published yesterday, involved 2,000 people.", "whose", "which", "whose 可表示事物的所属关系。"),
              ("The conference was held in Kyoto, ___ I first met my supervisor.", "where", "which", "指地点并作地点状语用 where。"),
          ]),
    topic(20, "Prepositions and reduced relative clauses", "介词与简化定语从句",
          "使用正式介词前置及分词简化定语从句。",
          [
              ("The participants to ___ the email was sent replied quickly.", "whom", "who", "介词后指人用 whom。"),
              ("The method by ___ the data were collected is explained below.", "which", "that", "介词后不能用 that。"),
              ("Students ___ in campus housing pay a fixed fee.", "living", "lived", "who live 可简化为 living。"),
              ("The figures ___ in Table 2 exclude overseas sales.", "shown", "showing", "figures 与 show 为被动关系，用 shown。"),
          ]),
    topic(21, "Subject choice and information flow", "主语选择与信息流",
          "选择清晰主语，使已知信息在前、新信息在后。",
          [
              ("The survey covered three age groups. ___ showed the highest satisfaction.", "The oldest group", "There", "以前句已知组别作主语，衔接更清晰。"),
              ("Several factors explain the decline. ___ is the rise in housing costs.", "The most important", "It most important", "用明确名词短语作主语。"),
              ("The graph compares four cities. ___ experienced the fastest growth.", "City D", "It was City D that", "简洁主语更适合直接描述数据。"),
              ("Online courses offer greater flexibility. ___ attracts many working adults.", "This advantage", "These advantage", "用 this + 单数名词概括前句信息。"),
          ]),
    topic(21, "Introductory it", "形式主语 it",
          "使用 it is + adjective/noun + to/that 组织评价和长主语。",
          [
              ("___ is important to distinguish correlation from causation.", "It", "There", "to-infinitive 长主语可后置，it 作形式主语。"),
              ("It is likely ___ demand will continue to rise.", "that", "for", "It is likely that + 从句。"),
              ("___ was surprising that so few people responded.", "It", "This", "that 从句后置时用形式主语 it。"),
              ("It took the team six months ___ the data.", "to analyse", "analysing", "It takes/took + 时间 + to do。"),
          ]),
    topic(21, "Ellipsis and substitution", "省略与替代",
          "使用 do so, one/ones, so/not 等避免不必要重复。",
          [
              ("Some students revised daily, while others did ___.", "so", "it", "do so 替代前述动作 revised daily。"),
              ("The northern region grew faster than the southern ___ did.", "one", "region", "one 替代同类单数名词 region。"),
              ("Will prices fall next year? Experts do not think ___.", "so", "it", "think so/not 替代整个从句。"),
              ("The first two solutions were costly; the final ___ was affordable.", "one", "it", "one 替代同类名词 solution。"),
          ]),
    topic(21, "It-clauses and what-clauses", "it 从句与 what 从句",
          "使用强调结构和 what-clause 突出信息。",
          [
              ("It was in 2020 ___ the trend began to change.", "that", "when", "强调结构 It was...that。"),
              ("___ the city needs is a more reliable bus network.", "What", "That", "what = the thing that，可引导名词性从句。"),
              ("It is younger adults ___ use the service most frequently.", "who", "which", "强调人时可用 who。"),
              ("What surprised researchers ___ the speed of the recovery.", "was", "were", "what 从句整体作单数主语。"),
          ]),
    topic(22, "Passive forms and uses", "被动语态形式与用途",
          "正确构成不同时态的被动，并在关注过程或结果时使用。",
          [
              ("The questionnaires ___ online last month.", "were distributed", "distributed", "一般过去时被动：were + 过去分词。"),
              ("The final results ___ next week.", "will be announced", "will announce", "一般将来时被动：will be + 过去分词。"),
              ("Several errors ___ in the original calculation.", "have been found", "have found", "现在完成时被动：have been + 过去分词。"),
              ("The data ___ when the server failed.", "were being processed", "were processing", "过去进行时被动：were being + 过去分词。"),
          ]),
    topic(22, "Passive reporting structures", "被动转述结构",
          "使用 it is believed that 与 subject + is believed to 等正式结构。",
          [
              ("It is believed ___ the policy will reduce emissions.", "that", "to", "It is believed that + 从句。"),
              ("The policy is expected ___ emissions.", "to reduce", "that reduce", "主语 + be expected + to-infinitive。"),
              ("The company is reported ___ more than 5,000 staff.", "to employ", "employing", "be reported to + 动词原形。"),
              ("It has been suggested ___ the sample was too small.", "that", "for", "It has been suggested that + 从句。"),
          ]),
    topic(22, "Have something done and need -ing", "使役结构与 need -ing",
          "使用 have/get something done 及 need doing 表达服务或被动需要。",
          [
              ("We had the documents ___ before the interview.", "translated", "translate", "have + 宾语 + 过去分词。"),
              ("She is getting her laptop ___ tomorrow.", "repaired", "repairing", "get something done 表示请人处理。"),
              ("The classroom needs ___ before the next lesson.", "cleaning", "to cleaning", "need + -ing 可表达被动含义。"),
              ("You should have your eyes ___ regularly.", "tested", "testing", "have something done 使用过去分词。"),
          ]),
    topic(23, "Conjunctions", "并列与从属连词",
          "使用 although, because, while, whereas, so that 等连接逻辑关系。",
          [
              ("___ the initial cost is high, the system saves money over time.", "Although", "Because of", "although 后接完整从句。"),
              ("The first group improved, ___ the second group showed no change.", "whereas", "because", "whereas 表示对比。"),
              ("The survey was repeated ___ the results could be verified.", "so that", "despite", "so that + 从句表示目的。"),
              ("Many residents objected ___ they feared higher taxes.", "because", "because of", "because 后接完整从句。"),
          ]),
    topic(23, "Linking adverbials and prepositions", "连接副词与连接介词",
          "区分 however/despite, therefore/because of 等不同句法结构。",
          [
              ("The sample was small. ___, the findings were consistent.", "However", "Despite", "however 是连接副词，可连接两个独立句。"),
              ("___ the small sample, the findings were consistent.", "Despite", "However", "despite 后接名词短语。"),
              ("Demand increased; ___, prices rose.", "therefore", "because of", "therefore 是连接副词，表示结果。"),
              ("The event was cancelled ___ severe weather.", "because of", "because", "because of 后接名词短语。"),
          ]),
    topic(24, "Stance verbs and adjectives", "立场动词与形容词",
          "使用 argue, suggest, appear, likely, essential 等表达证据强度与评价。",
          [
              ("The findings ___ that sleep affects memory.", "suggest", "suggests", "主语 findings 为复数。"),
              ("It appears ___ the two variables are related.", "that", "to", "It appears that + 从句。"),
              ("Governments should ___ the long-term costs.", "consider", "consideration", "情态动词后用动词原形。"),
              ("It is essential ___ all participants give informed consent.", "that", "for to", "It is essential that + 从句。"),
          ]),
    topic(24, "Hedging and cautious claims", "限定语与审慎论断",
          "使用 may, tend to, appear to, relatively 等避免无依据的绝对化。",
          [
              ("The results ___ indicate a link between diet and sleep.", "may", "must to", "may 表示审慎可能性。"),
              ("Older participants tended ___ higher satisfaction.", "to report", "reporting", "tend to + 动词原形。"),
              ("The change was ___ small compared with earlier years.", "relatively", "relative", "修饰形容词 small 用副词。"),
              ("The intervention appears ___ effective for younger learners.", "to be", "being", "appear to be 是审慎表达。"),
          ]),
    topic(25, "Nominalising verbs", "动词名词化",
          "把动作转化为名词，使学术表达更紧凑并突出过程或结果。",
          [
              ("The government decided to expand the railway. Its ___ was announced in May.", "decision", "deciding", "decide 的名词形式是 decision。"),
              ("Researchers analysed the samples. The ___ took two weeks.", "analysis", "analyse", "analyse 的名词形式是 analysis。"),
              ("The population grew rapidly. This ___ created housing pressure.", "growth", "growing", "grow 的名词形式是 growth。"),
              ("The company failed to meet demand. Its ___ damaged public trust.", "failure", "failing", "fail 的名词形式是 failure。"),
          ]),
    topic(25, "Nominalising adjectives", "形容词名词化",
          "把形容词转化为抽象名词，如 available-availability、stable-stability。",
          [
              ("Public transport is widely available. Its ___ benefits commuters.", "availability", "available", "available 的名词形式是 availability。"),
              ("Prices remained stable. This ___ encouraged investment.", "stability", "stable", "stable 的名词形式是 stability。"),
              ("The two groups were different. The ___ was statistically significant.", "difference", "different", "different 的名词形式是 difference。"),
              ("The instructions were clear. Their ___ reduced errors.", "clarity", "clear", "clear 的名词形式是 clarity。"),
          ]),
    topic(25, "Nominalisation for academic cohesion", "名词化与学术衔接",
          "用名词化回指前句信息，并避免过度堆叠抽象名词。",
          [
              ("The city introduced a congestion charge. This ___ reduced traffic.", "introduction", "introducing", "用 introduction 回指 introduced。"),
              ("The team compared three methods. The ___ revealed clear differences.", "comparison", "comparing", "comparison 可概括前句动作。"),
              ("The policy was implemented gradually. Its gradual ___ limited disruption.", "implementation", "implement", "implementation 是正式名词形式。"),
              ("Sales declined by 12 percent. This ___ was smaller than expected.", "decline", "declining", "decline 可作名词概括前句趋势。"),
          ]),
]


def option_rows(correct: str, wrong: str, correct_first: bool):
    values = [correct, wrong] if correct_first else [wrong, correct]
    answer = "A" if correct_first else "B"
    return [{"key": "A", "text": values[0]}, {"key": "B", "text": values[1]}], answer


def build_material(topic_id: int, spec: dict) -> dict:
    questions = []
    sequence = 1
    code = f"IG60-{topic_id:03d}"

    for pair_index, (stem, correct, wrong, note) in enumerate(spec["pairs"], start=1):
        correct_first = (topic_id + pair_index) % 2 == 0
        options, answer = option_rows(correct, wrong, correct_first)
        questions.append({
            "sequence": sequence,
            "question_type": "choice",
            "content": stem,
            "reference_answer": answer,
            "hint": note,
            "explanation": note,
            "points": 1,
            "options": options,
        })
        sequence += 1

        correct_sentence = stem.replace("___", correct)
        wrong_sentence = stem.replace("___", wrong)
        options, answer = option_rows(correct_sentence, wrong_sentence, not correct_first)
        questions.append({
            "sequence": sequence,
            "question_type": "choice",
            "content": "Choose the grammatically correct sentence.",
            "reference_answer": answer,
            "hint": note,
            "explanation": note,
            "points": 1,
            "options": options,
        })
        sequence += 1

    for stem, correct, _wrong, note in spec["pairs"][:2]:
        questions.append({
            "sequence": sequence,
            "question_type": "auto_text",
            "content": f"Complete the sentence without choices:\n{stem}",
            "reference_answer": correct,
            "hint": note,
            "explanation": note,
            "points": 1,
            "options": [],
        })
        sequence += 1

    for stem, correct, wrong, note in spec["pairs"][2:]:
        questions.append({
            "sequence": sequence,
            "question_type": "writing",
            "content": (
                "Correct the sentence without changing its meaning:\n"
                + stem.replace("___", wrong)
            ),
            "reference_answer": stem.replace("___", correct),
            "hint": note,
            "explanation": note,
            "points": 2,
            "options": [],
        })
        sequence += 1

    return {
        "code": code,
        "unit": spec["unit"],
        "title": f"{code} U{spec['unit']:02d} {spec['title_cn']} | {spec['title_en']}",
        "title_cn": spec["title_cn"],
        "title_en": spec["title_en"],
        "type": "grammar",
        "description": (
            f"核心：{spec['focus']}\n"
            "结构：8 道辨析选择题 + 2 道自动判分填空 + 2 道人工批改改错题。\n"
            "建议用时：15-20 分钟；适合课后巩固、错题重练和分层布置。"
        ),
        "question_count": len(questions),
        "questions": questions,
    }


def validate(materials: list[dict]) -> list[str]:
    errors = []
    if len(materials) != 60:
        errors.append(f"expected 60 materials, got {len(materials)}")

    codes = set()
    titles = set()
    for material in materials:
        code = material["code"]
        if code in codes:
            errors.append(f"duplicate code: {code}")
        codes.add(code)
        if material["title"] in titles:
            errors.append(f"duplicate title: {material['title']}")
        titles.add(material["title"])
        if material["question_count"] != 12:
            errors.append(f"{code}: expected 12 questions")

        sequences = [q["sequence"] for q in material["questions"]]
        if sequences != list(range(1, 13)):
            errors.append(f"{code}: invalid sequences {sequences}")

        for question in material["questions"]:
            qtype = question["question_type"]
            if qtype == "choice":
                keys = {opt["key"] for opt in question["options"]}
                if question["reference_answer"] not in keys:
                    errors.append(
                        f"{code} Q{question['sequence']}: answer missing from options"
                    )
            elif qtype == "auto_text":
                if question["options"]:
                    errors.append(f"{code} Q{question['sequence']}: auto_text has options")
            elif qtype == "writing":
                if question["options"]:
                    errors.append(f"{code} Q{question['sequence']}: writing has options")
            else:
                errors.append(f"{code} Q{question['sequence']}: unknown type {qtype}")
    return errors


def write_json(path: Path, materials: list[dict]) -> None:
    payload = {
        "schema_version": 1,
        "pack_id": "ielts_grammar_60_original_v1",
        "title": "IELTS Grammar 60-Part Original Practice Pack",
        "language": "English questions with Chinese explanations",
        "copyright_note": (
            "All questions are original. Topic coverage is aligned to the referenced "
            "grammar syllabus; no textbook exercises are reproduced."
        ),
        "material_count": len(materials),
        "question_count": sum(m["question_count"] for m in materials),
        "materials": materials,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_catalog_csv(path: Path, materials: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "code", "unit", "title_cn", "title_en", "type",
                "question_count", "description",
            ],
        )
        writer.writeheader()
        for material in materials:
            writer.writerow({key: material[key] for key in writer.fieldnames})


def write_questions_csv(path: Path, materials: list[dict]) -> None:
    fieldnames = [
        "material_code", "unit", "material_title", "sequence", "question_type",
        "content", "option_a", "option_b", "reference_answer", "hint",
        "explanation", "points",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for material in materials:
            for question in material["questions"]:
                options = {opt["key"]: opt["text"] for opt in question["options"]}
                writer.writerow({
                    "material_code": material["code"],
                    "unit": material["unit"],
                    "material_title": material["title"],
                    "sequence": question["sequence"],
                    "question_type": question["question_type"],
                    "content": question["content"],
                    "option_a": options.get("A", ""),
                    "option_b": options.get("B", ""),
                    "reference_answer": question["reference_answer"],
                    "hint": question["hint"],
                    "explanation": question["explanation"],
                    "points": question["points"],
                })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    materials = [build_material(index, spec) for index, spec in enumerate(TOPICS, start=1)]
    errors = validate(materials)
    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1

    print(
        f"Validated {len(materials)} materials / "
        f"{sum(m['question_count'] for m in materials)} questions."
    )
    if args.validate_only:
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "materials.json", materials)
    write_catalog_csv(args.output_dir / "catalog.csv", materials)
    write_questions_csv(args.output_dir / "questions.csv", materials)
    print(f"Wrote files to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
