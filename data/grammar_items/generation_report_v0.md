# 语法候选题生成报告 v0

按执行计划 v0.1 生成；候选题尚未通过教师审核、未入库。

## 题型数量

| 题型 | auto_pass | needs_review | rejected |
|---|---:|---:|---:|
| main_verb_tap | 5912 | 363 | 6382 |
| clause_boundary | 4814 | 2357 | 2763 |
| clause_type_classify | 12986 | 1737 | 1398 |
| adverbial_relation | 469 | 561 | 2631 |
| subject_span | 5353 | 734 | 6570 |
| finite_or_not | 12541 | 1737 | 6567 |

## 范围

```json
{
  "passages": 317,
  "sentences": 12657,
  "candidates": 49564,
  "sentence_rejections": 1398,
  "template_rejections": 17923
}
```

## 环境与输入指纹

```json
{
  "spacy": "3.8.16",
  "model_name": "en_core_web_trf",
  "model_version": "3.8.0",
  "device": "CPU",
  "python": "3.13.3",
  "torch": "2.14.1",
  "openpyxl": "3.1.5",
  "seed": 20261018,
  "reading_study_sha256": "e6e58691a2db4a59f5a8b7fdbd451074395498fcee9400a673dc8b512950ed63",
  "grammar_graph_sha256": "c7b35ddb68db7601ccd01e38a210ad3dd772ff507302190f68a351e408b85a29"
}
```

## 知识点数量

```json
{
  "G-S01": {
    "auto_pass": 2766,
    "needs_review": 157
  },
  "G-S02": {
    "auto_pass": 5353,
    "needs_review": 734
  },
  "G-C02": {
    "auto_pass": 570,
    "needs_review": 649
  },
  "G-C03": {
    "auto_pass": 12986,
    "needs_review": 1737
  },
  "G-C04": {
    "auto_pass": 1794,
    "needs_review": 328
  },
  "G-C08": {
    "auto_pass": 1139,
    "needs_review": 744
  },
  "G-C10": {
    "auto_pass": 1311,
    "needs_review": 636
  },
  "G-C11": {
    "needs_review": 561,
    "auto_pass": 469
  },
  "G-N01": {
    "auto_pass": 10681,
    "needs_review": 1673
  },
  "G-N04": {
    "auto_pass": 1860,
    "needs_review": 64
  },
  "G-L01": {
    "auto_pass": 3146,
    "needs_review": 206
  }
}
```

## 原因码数量

```json
{
  "no_main_verb_tag": 12258,
  "coordinated_main_verbs": 3990,
  "split_subject": 3786,
  "coordinated_main_clauses": 3591,
  "clause_type_mismatch": 1905,
  "ambiguous_span_location": 1565,
  "span_not_constituent": 1432,
  "multiple_targets_same_type": 1365,
  "boundary_mismatch": 1296,
  "no_relation_label": 1233,
  "finiteness_mismatch": 666,
  "subject_mismatch": 558,
  "parser_root_outside_verb_span": 540,
  "unbalanced_quotes_or_brackets": 425,
  "subordinator_unknown": 323,
  "unknown_span": 316,
  "existential": 304,
  "too_short": 253,
  "level_one_subordinate": 225,
  "subordinator_ambiguous": 210,
  "fragment": 186,
  "multiple_main_verbs": 186,
  "span_not_found": 153,
  "too_long": 54,
  "subject_after_verb": 44,
  "tagged_fragment": 36,
  "heading": 32,
  "parser_root_inside_subordinate_span": 22,
  "subordinator_mismatch": 16,
  "clause_attached_to_conjunction": 2
}
```

## 来源分布

```json
{
  "reading_jijing": 15815,
  "reading_test": 33749
}
```

## 难度分布

```json
{
  "easy": 16728,
  "hard": 18507,
  "medium": 14329
}
```

## 抽查清单

```json
{
  "rows": 360,
  "estimated_minutes": 180.0,
  "templates": {
    "main_verb_tap": {
      "auto_pass": 50,
      "needs_review": 10,
      "rows": 60,
      "auto_pool_shortfall": 0,
      "auto_strata": [
        {
          "source_kind": "reading_jijing",
          "difficulty": "easy",
          "pool_size": 1121,
          "sample_size": 10
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 348,
          "sample_size": 3
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 462,
          "sample_size": 4
        },
        {
          "source_kind": "reading_test",
          "difficulty": "easy",
          "pool_size": 1942,
          "sample_size": 16
        },
        {
          "source_kind": "reading_test",
          "difficulty": "hard",
          "pool_size": 1059,
          "sample_size": 9
        },
        {
          "source_kind": "reading_test",
          "difficulty": "medium",
          "pool_size": 980,
          "sample_size": 8
        }
      ]
    },
    "clause_boundary": {
      "auto_pass": 50,
      "needs_review": 10,
      "rows": 60,
      "auto_pool_shortfall": 0,
      "auto_strata": [
        {
          "source_kind": "reading_jijing",
          "difficulty": "easy",
          "pool_size": 462,
          "sample_size": 5
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 547,
          "sample_size": 6
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 542,
          "sample_size": 6
        },
        {
          "source_kind": "reading_test",
          "difficulty": "easy",
          "pool_size": 786,
          "sample_size": 8
        },
        {
          "source_kind": "reading_test",
          "difficulty": "hard",
          "pool_size": 1484,
          "sample_size": 15
        },
        {
          "source_kind": "reading_test",
          "difficulty": "medium",
          "pool_size": 993,
          "sample_size": 10
        }
      ]
    },
    "clause_type_classify": {
      "auto_pass": 50,
      "needs_review": 10,
      "rows": 60,
      "auto_pool_shortfall": 0,
      "auto_strata": [
        {
          "source_kind": "reading_jijing",
          "difficulty": "easy",
          "pool_size": 969,
          "sample_size": 4
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 1571,
          "sample_size": 6
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 1156,
          "sample_size": 4
        },
        {
          "source_kind": "reading_test",
          "difficulty": "easy",
          "pool_size": 2292,
          "sample_size": 9
        },
        {
          "source_kind": "reading_test",
          "difficulty": "hard",
          "pool_size": 4238,
          "sample_size": 16
        },
        {
          "source_kind": "reading_test",
          "difficulty": "medium",
          "pool_size": 2760,
          "sample_size": 11
        }
      ]
    },
    "adverbial_relation": {
      "auto_pass": 50,
      "needs_review": 10,
      "rows": 60,
      "auto_pool_shortfall": 0,
      "auto_strata": [
        {
          "source_kind": "reading_jijing",
          "difficulty": "easy",
          "pool_size": 68,
          "sample_size": 7
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 87,
          "sample_size": 9
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 94,
          "sample_size": 10
        },
        {
          "source_kind": "reading_test",
          "difficulty": "easy",
          "pool_size": 48,
          "sample_size": 5
        },
        {
          "source_kind": "reading_test",
          "difficulty": "hard",
          "pool_size": 88,
          "sample_size": 10
        },
        {
          "source_kind": "reading_test",
          "difficulty": "medium",
          "pool_size": 84,
          "sample_size": 9
        }
      ]
    },
    "subject_span": {
      "auto_pass": 50,
      "needs_review": 10,
      "rows": 60,
      "auto_pool_shortfall": 0,
      "auto_strata": [
        {
          "source_kind": "reading_jijing",
          "difficulty": "easy",
          "pool_size": 1005,
          "sample_size": 9
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 334,
          "sample_size": 3
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 395,
          "sample_size": 4
        },
        {
          "source_kind": "reading_test",
          "difficulty": "easy",
          "pool_size": 1781,
          "sample_size": 17
        },
        {
          "source_kind": "reading_test",
          "difficulty": "hard",
          "pool_size": 965,
          "sample_size": 9
        },
        {
          "source_kind": "reading_test",
          "difficulty": "medium",
          "pool_size": 873,
          "sample_size": 8
        }
      ]
    },
    "finite_or_not": {
      "auto_pass": 50,
      "needs_review": 10,
      "rows": 60,
      "auto_pool_shortfall": 0,
      "auto_strata": [
        {
          "source_kind": "reading_jijing",
          "difficulty": "easy",
          "pool_size": 1599,
          "sample_size": 6
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 1255,
          "sample_size": 5
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 1065,
          "sample_size": 4
        },
        {
          "source_kind": "reading_test",
          "difficulty": "easy",
          "pool_size": 2920,
          "sample_size": 12
        },
        {
          "source_kind": "reading_test",
          "difficulty": "hard",
          "pool_size": 3331,
          "sample_size": 13
        },
        {
          "source_kind": "reading_test",
          "difficulty": "medium",
          "pool_size": 2371,
          "sample_size": 10
        }
      ]
    }
  }
}
```

## 独立整句过滤命中

### tagged_fragment

实际 36 句；计划预期 36 句。

- `ielts17_test2_p3` F-07：No.
- `ielts17_test3_p2` A-04：Primarily because its unique properties – such as remaining solid at room temperature – make it an ideal ingredient for long-term preservation, allowing many packaged foods on supermarket shelves to have 'best before' dates of months, even years, into the future.
- `ielts4_test4_p1` A-04：At the 1908 Olympics, John Hayes of the U.S.
- `ielts4_test4_p1` A-05：team ran the marathon in a time of 2:55:18.
- `ielts4_test4_p1` C-14：But with the right training we can go much further with that one third than we've been going." Yessis believes that U.S.
- `ielts4_test4_p1` E-22："Many athletes are not getting the best nutrition, even though supplements," Yessis insists.
- `ielts4_test4_p1` I-42：Raglin, a sports psychologist at Indiana University.
- `ielts6_test1_p1` E-04：'A start of this much, each free-swimming period has to be this fast, with a certain stroke frequency and stroke length, with turns done in these times.'
- `reading_jijing_10_test_78_p1` C-16：Introduced Category 1: INTERPERSONAL ROLES.
- `reading_jijing_10_test_78_p1` D-26：Introduced Category 2: INFORMATIONAL ROLES.
- `reading_jijing_10_test_78_p1` F-35：Introduced Category 3: DECISIONAL ROLES.
- `reading_jijing_10_test_78_p3` H-06："Many child-resistant packs
- `reading_jijing_10_test_78_p3` I-01：are based on strength.
- `reading_jijing_11_test_103_p1` G-01：Researchers from the Center of Astrobiology (Spain) and the Catholic University of the North in Chile have found an 'oasis' of microorganisms two meters below the surface of the Atacama Desert, SOLID, a detector for signs of life which could be used in environments similar to subsoil on Mars.
- `reading_jijing_11_test_103_p1` H-01：Even more intriguing, however, is the alternative scenario by Spanish scientists: If those samples could be found to that use DNA, as Earthly life does, as their genetic code.
- `reading_jijing_11_test_103_p2` A-03：They under the banner of geoengineering generally defined as the intentional large-scale manipulation of the environment.
- `reading_jijing_16_test_97_p3` E-08：Steven Johnson, author of
- `reading_jijing_16_test_97_p3` F-01：Everything Bad is Good For You: How Today's Popular Culture, says gamers must deal with immediate problems while keeping their long-term goals on their horizon.
- `reading_jijing_22_test_90_p2` G-21：Jackson, Professor of Psychiatry and Human Behavior at Brown University's Alpert Medical School in Providence, and Director of Chronobiology at Bradley Hospital in East Providence.
- `reading_jijing_22_test_90_p3` G-08：One initiative, for example, requiring the writing, organisation and delivery of a theatrical performance to which all staff members will be invited to view.
- `reading_jijing_24_test_56_p3` C-02：These individuals were split into six groups; each pair common diet.
- `reading_jijing_24_test_56_p3` G-03：Phase 11(b) to evaluate effectiveness.
- `reading_jijing_26_test_72_p1` C-01：Montpellier, France.
- `reading_jijing_26_test_72_p1` E-01：International Plant Genetic Resources Institute.
- `reading_jijing_27_test_33_p3` E-02：Tate argues that a decision should be made after a consideration of all alternatives, and a hierarchical structure that then takes responsibility for the decision and, most importantly, follows that decision through to verify whether the problem has indeed been resolved.
- `reading_jijing_32_test_20_p3` D-07：The best advice for moms-to-be: Get fit before you get pregnant.
- `reading_jijing_50_test_30_p2` E-04：An acceptable profit margin.
- `reading_jijing_56_test_64_p2` B-02：Seven wars ago.
- `reading_jijing_5_test_59_p1` H-04：'The cost of accidents business, people tend to call such efforts failure.'
- `reading_jijing_62_test_44_p2` B-05：When cotton production started spreading through Andhra Pradesh state.
- `reading_jijing_65_test_69_p2` F-01：In The Environment Game, a vision of a utopia that would be at once high-tech and environmentalist.
- `reading_jijing_65_test_69_p3` E-02：Surveyor J. that had landed in a crater on April 19. 1967.
- `reading_jijing_73_test_5_p1` K-01：Standing on a roof catwalk, peering down inside at people as small as termites below.
- `reading_jijing_73_test_5_p1` K-03：like that termite fungus, further extending the whole 'organic machine' metaphor.
- `reading_jijing_73_test_5_p2` F-05：Many incidents of attacks on people involving villagers squatting or bending over to cut grass for fodder or building material.
- `reading_jijing_85_test_12_p1` C-08：The company is the recipe is in a vault somewhere and in my sole owner of the intellectual property.
### clause_attached_to_conjunction

实际 2 句；计划预期 2 句。

- `ielts13_test2_p2` C-04：Jennifer Bartz from Mount Sinai School of Medicine, New York, found that it improves people's ability to read emotions, but only if they are not very socially adept to begin with.
- `reading_jijing_56_test_64_p2` C-01：It did not deter him, and while many of the critics in the scientific establishment who vilified him disappeared from view.

## 回归例句逐模板结果

### ielts7_test3_p1 K-03 (bad)

Be careful of little lives.'

- **main_verb_tap**：rejected：too_short, unbalanced_quotes_or_brackets
- **clause_boundary**：rejected：too_short, unbalanced_quotes_or_brackets
- **clause_type_classify**：rejected：too_short, unbalanced_quotes_or_brackets
- **adverbial_relation**：rejected：too_short, unbalanced_quotes_or_brackets
- **subject_span**：rejected：too_short, unbalanced_quotes_or_brackets
- **finite_or_not**：rejected：too_short, unbalanced_quotes_or_brackets
### ielts8_test4_p1 C-04 (bad)

(One teacher was particularly keen to introduce colour and pictures into maths textbooks: he felt this would make them more accessible to pupils brought up in a cartoon culture.)

- **main_verb_tap**：rejected：no_main_verb_tag
- **clause_boundary**：无适用白名单目标。
- **clause_type_classify**：auto_pass；目标 `to introduce colour and pictures into maths textbooks`；答案 `不是从句（短语或非谓语）`；标注与解析器一致
- **adverbial_relation**：无适用白名单目标。
- **subject_span**：rejected：no_main_verb_tag
- **finite_or_not**：auto_pass；目标 `introduce`；答案 `非谓语（不定式、分词、动名词）`；标注与解析器一致；rejected：no_main_verb_tag
### reading_jijing_76_test_43_p2 H-02 (bad)

By the late 1980s the Modern Movement, unfairly blamed for the social experiments implicit in high- rise housing, had lost out to irony and spectacle in the shape of post-modernism, with its cheerful borrowings from anywhere and any period.

- **main_verb_tap**：auto_pass；目标 ``；答案 `had / lost / out`；标注与解析器一致
- **clause_boundary**：无适用白名单目标。
- **clause_type_classify**：无适用白名单目标。
- **adverbial_relation**：无适用白名单目标。
- **subject_span**：needs_review；目标 ``；答案 `By the late 1980s the Modern Movement, unfairly blamed for the social experiments implicit in high- rise housing`；subject_mismatch
- **finite_or_not**：auto_pass；目标 `lost`；答案 `主句谓语`；标注与解析器一致
### reading_jijing_73_test_5_p2 F-05 (bad)

Many incidents of attacks on people involving villagers squatting or bending over to cut grass for fodder or building material.

- **main_verb_tap**：rejected：tagged_fragment, unknown_span
- **clause_boundary**：rejected：tagged_fragment, unknown_span
- **clause_type_classify**：rejected：tagged_fragment, unknown_span
- **adverbial_relation**：rejected：tagged_fragment, unknown_span
- **subject_span**：rejected：tagged_fragment, unknown_span
- **finite_or_not**：rejected：tagged_fragment, unknown_span
### reading_jijing_56_test_64_p2 C-01 (bad)

It did not deter him, and while many of the critics in the scientific establishment who vilified him disappeared from view.

- **main_verb_tap**：rejected：clause_attached_to_conjunction
- **clause_boundary**：rejected：clause_attached_to_conjunction
- **clause_type_classify**：rejected：clause_attached_to_conjunction
- **adverbial_relation**：rejected：clause_attached_to_conjunction
- **subject_span**：rejected：clause_attached_to_conjunction
- **finite_or_not**：rejected：clause_attached_to_conjunction
### ielts13_test2_p2 C-04 (bad)

Jennifer Bartz from Mount Sinai School of Medicine, New York, found that it improves people's ability to read emotions, but only if they are not very socially adept to begin with.

- **main_verb_tap**：rejected：clause_attached_to_conjunction
- **clause_boundary**：rejected：clause_attached_to_conjunction
- **clause_type_classify**：rejected：clause_attached_to_conjunction
- **adverbial_relation**：rejected：clause_attached_to_conjunction
- **subject_span**：rejected：clause_attached_to_conjunction
- **finite_or_not**：rejected：clause_attached_to_conjunction
### reading_jijing_91_test_49_p3 D-02 (positive)

The meeting itself attended by over 4,000 delegates representing some 168 countries occurred almost 10 years to the day after the Great Hanshin earthquake in Kobe.

- **main_verb_tap**：auto_pass；目标 ``；答案 `occurred`；标注与解析器一致
- **clause_boundary**：无适用白名单目标。
- **clause_type_classify**：auto_pass；目标 `attended by over 4,000 delegates representing some 168 countries`；答案 `不是从句（短语或非谓语）`；标注与解析器一致；auto_pass；目标 `representing some 168 countries`；答案 `不是从句（短语或非谓语）`；标注与解析器一致；needs_review；目标 `almost 10 years to the day after the Great Hanshin earthquake in Kobe`；答案 `不是从句（短语或非谓语）`；span_not_constituent
- **adverbial_relation**：无适用白名单目标。
- **subject_span**：auto_pass；目标 ``；答案 `The meeting itself attended by over 4,000 delegates representing some 168 countries`；标注与解析器一致
- **finite_or_not**：auto_pass；目标 `occurred`；答案 `主句谓语`；标注与解析器一致；auto_pass；目标 `attended`；答案 `非谓语（不定式、分词、动名词）`；标注与解析器一致；auto_pass；目标 `representing`；答案 `非谓语（不定式、分词、动名词）`；标注与解析器一致
### ielts11_test3_p2 A-04 (positive)

The biologist Hugh Dingle has identified five characteristics that apply, in varying degrees and combinations, to all migrations.

- **main_verb_tap**：auto_pass；目标 ``；答案 `has / identified`；标注与解析器一致
- **clause_boundary**：auto_pass；目标 ``；答案 `that apply, in varying degrees and combinations, to all migrations`；标注与解析器一致
- **clause_type_classify**：auto_pass；目标 `that apply, in varying degrees and combinations, to all migrations`；答案 `定语从句`；标注与解析器一致
- **adverbial_relation**：无适用白名单目标。
- **subject_span**：auto_pass；目标 ``；答案 `The biologist Hugh Dingle`；标注与解析器一致
- **finite_or_not**：auto_pass；目标 `identified`；答案 `主句谓语`；标注与解析器一致；auto_pass；目标 `apply`；答案 `从句里的谓语`；标注与解析器一致
### ielts15_test2_p3 D-05 (positive)

Analysis revealed that, as expected, high-status individuals produced more dominant laughs and fewer submissive laughs relative to the low-status individuals.

- **main_verb_tap**：auto_pass；目标 ``；答案 `revealed`；标注与解析器一致
- **clause_boundary**：auto_pass；目标 ``；答案 `that, as expected, high-status individuals produced more dominant laughs and fewer submissive laughs relative to the low-status individuals`；标注与解析器一致
- **clause_type_classify**：auto_pass；目标 `that, as expected, high-status individuals produced more dominant laughs and fewer submissive laughs relative to the low-status individuals`；答案 `名词性从句`；标注与解析器一致；auto_pass；目标 `relative to the low-status individuals`；答案 `不是从句（短语或非谓语）`；标注与解析器一致
- **adverbial_relation**：无适用白名单目标。
- **subject_span**：auto_pass；目标 ``；答案 `Analysis`；标注与解析器一致
- **finite_or_not**：auto_pass；目标 `revealed`；答案 `主句谓语`；标注与解析器一致

## 计数和复现约定

- 候选题按 item_id 计数；模板 rejected 含每个整句拒绝一次，以及该模板的目标/选句拒绝记录。
- 原因码按候选题及拒绝记录计数；整句拒绝在 JSONL 中只记录一条，保留全部原因。
- 两条新增整句规则在全库独立统计，不受其他过滤顺序影响。
- 无白名单目标的 T2/T3/T4 不生成题，也不虚构拒绝原因。T6(a) 单独记录主句选句拒绝。
- 字符偏移均为原句 [start,end)；evidence 中的 token 范围也是左闭右开。
- 分类答案使用固定选项文字；抽样 JSONL 的 pool_status 不写入工作簿。
- 同一模板完全相同的 item_id 和内容去重，ID 相同但内容不同则报错停止。
- XLSX 使用固定元数据和不压缩 ZIP，避免时间及压缩库版本影响字节复现。
