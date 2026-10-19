# 语法候选题生成报告 v0.2

按执行计划 v0.2（在 v0.1 基础上的增量）生成；候选题尚未通过教师审核、未入库。

## 题型数量

| 题型 | auto_pass | needs_review | rejected |
|---|---:|---:|---:|
| main_verb_tap | 5922 | 377 | 6389 |
| clause_boundary | 4772 | 2397 | 2791 |
| clause_type_classify | 11540 | 3176 | 1437 |
| adverbial_relation | 396 | 637 | 2668 |
| subject_span | 5370 | 737 | 6581 |
| finite_or_not | 12738 | 1561 | 6575 |

## 范围

```json
{
  "passages": 317,
  "sentences": 12688,
  "candidates": 49623,
  "sentence_rejections": 1437,
  "template_rejections": 17819
}
```

## 环境与输入指纹

```json
{
  "spacy": "3.8.16",
  "model_name": "en_core_web_trf",
  "model_version": "3.8.0",
  "device": "CPU",
  "python": "3.11.15",
  "torch": "2.14.1",
  "openpyxl": "3.1.5",
  "seed": 20261018,
  "reading_study_sha256": "8702bd2293d4070b0433e89b2864b09f826b810c94ee7fdaffd036a37e582933",
  "grammar_graph_sha256": "c7b35ddb68db7601ccd01e38a210ad3dd772ff507302190f68a351e408b85a29"
}
```

## 知识点数量

```json
{
  "G-S01": {
    "auto_pass": 2760,
    "needs_review": 163
  },
  "G-S02": {
    "auto_pass": 5370,
    "needs_review": 737
  },
  "G-C02": {
    "auto_pass": 571,
    "needs_review": 644
  },
  "G-C03": {
    "auto_pass": 11540,
    "needs_review": 3176
  },
  "G-C04": {
    "auto_pass": 1796,
    "needs_review": 328
  },
  "G-C08": {
    "auto_pass": 1144,
    "needs_review": 738
  },
  "G-C10": {
    "auto_pass": 1261,
    "needs_review": 687
  },
  "G-C11": {
    "needs_review": 637,
    "auto_pass": 396
  },
  "G-N01": {
    "auto_pass": 10880,
    "needs_review": 1499
  },
  "G-N04": {
    "auto_pass": 1858,
    "needs_review": 62
  },
  "G-L01": {
    "auto_pass": 3162,
    "needs_review": 214
  }
}
```

## 原因码数量

```json
{
  "no_main_verb_tag": 12174,
  "coordinated_main_verbs": 3974,
  "split_subject": 3760,
  "coordinated_main_clauses": 3576,
  "boundary_mismatch": 3052,
  "clause_type_mismatch": 1896,
  "span_not_constituent": 1405,
  "ambiguous_span_location": 1364,
  "multiple_targets_same_type": 1354,
  "no_relation_label": 1231,
  "finiteness_mismatch": 665,
  "verb_unit_outside_span": 578,
  "subject_mismatch": 562,
  "parser_root_outside_verb_span": 550,
  "unbalanced_quotes_or_brackets": 427,
  "subordinator_unknown": 321,
  "unknown_span": 313,
  "existential": 304,
  "too_short": 254,
  "possible_relative_adverb": 228,
  "level_one_subordinate": 225,
  "subordinator_ambiguous": 210,
  "fragment": 186,
  "multiple_main_verbs": 180,
  "span_not_found": 153,
  "multi_sentence_unit": 51,
  "too_long": 49,
  "subject_after_verb": 44,
  "tagged_fragment": 37,
  "heading": 32,
  "parser_root_inside_subordinate_span": 22,
  "subordinator_mismatch": 18,
  "suspected_split_word": 6,
  "clause_attached_to_conjunction": 2
}
```

## 来源分布

```json
{
  "reading_jijing": 15935,
  "reading_test": 33688
}
```

## 难度分布

```json
{
  "easy": 16804,
  "hard": 18486,
  "medium": 14333
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
          "pool_size": 1129,
          "sample_size": 10
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 353,
          "sample_size": 3
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 466,
          "sample_size": 4
        },
        {
          "source_kind": "reading_test",
          "difficulty": "easy",
          "pool_size": 1938,
          "sample_size": 16
        },
        {
          "source_kind": "reading_test",
          "difficulty": "hard",
          "pool_size": 1056,
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
          "pool_size": 468,
          "sample_size": 5
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 548,
          "sample_size": 6
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 538,
          "sample_size": 6
        },
        {
          "source_kind": "reading_test",
          "difficulty": "easy",
          "pool_size": 776,
          "sample_size": 8
        },
        {
          "source_kind": "reading_test",
          "difficulty": "hard",
          "pool_size": 1461,
          "sample_size": 15
        },
        {
          "source_kind": "reading_test",
          "difficulty": "medium",
          "pool_size": 981,
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
          "pool_size": 938,
          "sample_size": 4
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 1248,
          "sample_size": 5
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 1012,
          "sample_size": 4
        },
        {
          "source_kind": "reading_test",
          "difficulty": "easy",
          "pool_size": 2220,
          "sample_size": 10
        },
        {
          "source_kind": "reading_test",
          "difficulty": "hard",
          "pool_size": 3633,
          "sample_size": 16
        },
        {
          "source_kind": "reading_test",
          "difficulty": "medium",
          "pool_size": 2489,
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
          "pool_size": 67,
          "sample_size": 8
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 62,
          "sample_size": 8
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 83,
          "sample_size": 11
        },
        {
          "source_kind": "reading_test",
          "difficulty": "easy",
          "pool_size": 46,
          "sample_size": 6
        },
        {
          "source_kind": "reading_test",
          "difficulty": "hard",
          "pool_size": 64,
          "sample_size": 8
        },
        {
          "source_kind": "reading_test",
          "difficulty": "medium",
          "pool_size": 74,
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
          "pool_size": 1013,
          "sample_size": 9
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 340,
          "sample_size": 3
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 399,
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
          "pool_size": 964,
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
          "pool_size": 1634,
          "sample_size": 6
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 1294,
          "sample_size": 5
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 1090,
          "sample_size": 4
        },
        {
          "source_kind": "reading_test",
          "difficulty": "easy",
          "pool_size": 2946,
          "sample_size": 12
        },
        {
          "source_kind": "reading_test",
          "difficulty": "hard",
          "pool_size": 3374,
          "sample_size": 13
        },
        {
          "source_kind": "reading_test",
          "difficulty": "medium",
          "pool_size": 2400,
          "sample_size": 10
        }
      ]
    }
  }
}
```

## 关系副词风险

```json
{
  "items_by_template": {
    "adverbial_relation": 32,
    "clause_boundary": 87,
    "clause_type_classify": 109
  },
  "distinct_targets": 109,
  "targets": [
    {
      "passage_id": "ielts10_test1_p3",
      "sentence_id": "D-04",
      "target": "when threatened with a loss",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_2234a7824b3b"
      ]
    },
    {
      "passage_id": "ielts10_test1_p3",
      "sentence_id": "I-03",
      "target": "when the flight captain makes a clearly wrong-headed decision",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_bc3af7aac9e1"
      ]
    },
    {
      "passage_id": "ielts10_test1_p3",
      "sentence_id": "K-01",
      "target": "where it is due",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_606c938e562c",
        "gi_v02_f4d048911b02"
      ]
    },
    {
      "passage_id": "ielts10_test3_p1",
      "sentence_id": "A-01",
      "target": "when primitive man set out",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_b3ae78072853",
        "gi_v02_c1f39530c292"
      ]
    },
    {
      "passage_id": "ielts10_test3_p2",
      "sentence_id": "C-04",
      "target": "when it's already scrambling to withdraw and preserve the ones already there",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_2fbd19531069",
        "gi_v02_98ca768f5c4f"
      ]
    },
    {
      "passage_id": "ielts10_test3_p2",
      "sentence_id": "F-01",
      "target": "when they're busy packing up for the winter",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_20afb7529d35",
        "gi_v02_a69db5269459"
      ]
    },
    {
      "passage_id": "ielts10_test3_p2",
      "sentence_id": "F-03",
      "target": "when it is the natural world's supreme light absorber",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_388f37bc2e12",
        "gi_v02_39cf2c9af4a9"
      ]
    },
    {
      "passage_id": "ielts10_test4_p2",
      "sentence_id": "C-02",
      "target": "when he had an accident",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_43dfea81a23c",
        "gi_v02_a8dad5eb6b53"
      ]
    },
    {
      "passage_id": "ielts11_test2_p3",
      "sentence_id": "C-03",
      "target": "when they were actually seeing an acclaimed masterpiece",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_89b37849e8c8"
      ]
    },
    {
      "passage_id": "ielts11_test2_p3",
      "sentence_id": "H-01",
      "target": "when we see a handwritten letter",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_48578aaf7d01"
      ]
    },
    {
      "passage_id": "ielts11_test3_p2",
      "sentence_id": "E-03",
      "target": "when it's time for takeoff on their big journey",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_a2078dec2b9c"
      ]
    },
    {
      "passage_id": "ielts11_test3_p2",
      "sentence_id": "E-03",
      "target": "when it's appropriate to land",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_a6c54fca22bb"
      ]
    },
    {
      "passage_id": "ielts11_test4_p2",
      "sentence_id": "C-05",
      "target": "when compared with the magnificent technology created by man and the visual beauties of the universe",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_047170928ae7",
        "gi_v02_12a8205667cb"
      ]
    },
    {
      "passage_id": "ielts12_test5_p1",
      "sentence_id": "B-05",
      "target": "when you release the pressure",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_63ea22b3611a",
        "gi_v02_f5239933274c"
      ]
    },
    {
      "passage_id": "ielts12_test6_p2",
      "sentence_id": "D-02",
      "target": "when in pursuit of their prey",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_68f6dbcbd69c"
      ]
    },
    {
      "passage_id": "ielts12_test6_p3",
      "sentence_id": "C-09",
      "target": "when bilinguals have to switch from categorizing objects by colour (red or green) to categorizing them by shape (circle or triangle)",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_921aebca6e19"
      ]
    },
    {
      "passage_id": "ielts12_test6_p3",
      "sentence_id": "C-09",
      "target": "when having to make rapid changes of strategy",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_d9397e041a44"
      ]
    },
    {
      "passage_id": "ielts13_test2_p1",
      "sentence_id": "C-08",
      "target": "when shipping cinnamon over a journey of eight days from Ceylon to India",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_897a86f7ec2c",
        "gi_v02_910b944d83b6"
      ]
    },
    {
      "passage_id": "ielts13_test2_p1",
      "sentence_id": "D-04",
      "target": "when they overran and occupied their factories",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_7ad11545f2d7",
        "gi_v02_a4d77c406f87"
      ]
    },
    {
      "passage_id": "ielts13_test2_p2",
      "sentence_id": "C-02",
      "target": "when they beat other players",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_ad2c05353503"
      ]
    },
    {
      "passage_id": "ielts13_test4_p2",
      "sentence_id": "C-05",
      "target": "when plants grow",
      "templates": [
        "adverbial_relation",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_62bfd8bd4be7",
        "gi_v02_acc74fb5ee8b"
      ]
    },
    {
      "passage_id": "ielts14_test1_p1",
      "sentence_id": "N-03",
      "target": "when they first played with dolls representing characters in the story",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_5e22fe2a7d1d",
        "gi_v02_7d08a3a24897"
      ]
    },
    {
      "passage_id": "ielts14_test3_p1",
      "sentence_id": "G-02",
      "target": "when they wrote about the emergence of a cognitive (high-IQ) elite",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_0a23855be4fa",
        "gi_v02_41472f7b163f"
      ]
    },
    {
      "passage_id": "ielts15_test2_p2",
      "sentence_id": "A-03",
      "target": "when the last living specimen died at Cincinnati Zoo",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_326b1e2f8291",
        "gi_v02_3431ede772c1"
      ]
    },
    {
      "passage_id": "ielts15_test2_p2",
      "sentence_id": "F-02",
      "target": "when they think about de-extinction",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_e5830b008ce1",
        "gi_v02_f8051d9265b1"
      ]
    },
    {
      "passage_id": "ielts15_test2_p3",
      "sentence_id": "D-06",
      "target": "when they were in the 'powerful' role of teasers",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_0db9efd17ea5",
        "gi_v02_609ed269216f"
      ]
    },
    {
      "passage_id": "ielts15_test2_p3",
      "sentence_id": "E-03",
      "target": "when displaying a dominant versus submissive laugh",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_55f2fe7c626b",
        "gi_v02_dd32bfb07940"
      ]
    },
    {
      "passage_id": "ielts15_test2_p3",
      "sentence_id": "E-04",
      "target": "when the context allows",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_d4b6fa013c61",
        "gi_v02_d72e2be60b67"
      ]
    },
    {
      "passage_id": "ielts15_test3_p1",
      "sentence_id": "A-05",
      "target": "when he was sent to France to fight in the First World War",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_7e154808e972",
        "gi_v02_ceed8ff62376"
      ]
    },
    {
      "passage_id": "ielts15_test3_p1",
      "sentence_id": "F-04",
      "target": "when his contract expired",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_5ec67d9caa22",
        "gi_v02_95c1cbe1dd45"
      ]
    },
    {
      "passage_id": "ielts15_test3_p2",
      "sentence_id": "B-03",
      "target": "when he moved to the United Arab Emirates and saw large-scale water processing",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_3ba041009eca",
        "gi_v02_80176ec02a2b"
      ]
    },
    {
      "passage_id": "ielts15_test3_p3",
      "sentence_id": "H-02",
      "target": "when other features are not",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_16d17f856826",
        "gi_v02_3f2edd9fa68b"
      ]
    },
    {
      "passage_id": "ielts15_test4_p1",
      "sentence_id": "C-02",
      "target": "when their other crops failed",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_016fd994d53a"
      ]
    },
    {
      "passage_id": "ielts15_test4_p2",
      "sentence_id": "H-01",
      "target": "when Spain conquered the volcanic islands in the 15th century",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_652f7333e8dc",
        "gi_v02_7be3533cea95"
      ]
    },
    {
      "passage_id": "ielts16_test1_p1",
      "sentence_id": "G-01",
      "target": "when they have just missed out on a kill",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_ce0ac148441f"
      ]
    },
    {
      "passage_id": "ielts16_test2_p1",
      "sentence_id": "F-01",
      "target": "when 'White Horse Hill' is mentioned in documents from the nearby Abbey of Abingdon",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_b4388794abb6",
        "gi_v02_f392d8a913a6"
      ]
    },
    {
      "passage_id": "ielts16_test3_p2",
      "sentence_id": "G-03",
      "target": "when we think of Scandinavian expansion",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_49dabecbd20a"
      ]
    },
    {
      "passage_id": "ielts16_test4_p1",
      "sentence_id": "C-02",
      "target": "when the qanat method was not a practical alternative",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_3d24f8414552",
        "gi_v02_be90febb191e"
      ]
    },
    {
      "passage_id": "ielts16_test4_p2",
      "sentence_id": "C-02",
      "target": "when we innovate",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_8e10c80c6e50"
      ]
    },
    {
      "passage_id": "ielts16_test4_p2",
      "sentence_id": "G-02",
      "target": "when reading",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_118f549eeca3",
        "gi_v02_9a7574e389e4"
      ]
    },
    {
      "passage_id": "ielts16_test4_p2",
      "sentence_id": "I-02",
      "target": "when applied to critical thought in the reading brain",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_15ea166e44c4"
      ]
    },
    {
      "passage_id": "ielts17_test1_p2",
      "sentence_id": "F-05",
      "target": "when the stadium is not in use",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_09b482419693",
        "gi_v02_1c8f44166823"
      ]
    },
    {
      "passage_id": "ielts17_test2_p3",
      "sentence_id": "F-03",
      "target": "when turning on oval tracks",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_ac28feed8e39",
        "gi_v02_d369d34317e8"
      ]
    },
    {
      "passage_id": "ielts17_test3_p1",
      "sentence_id": "F-03",
      "target": "when he published his Mammals of Australia between 1848 and 1863",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_77a16e9ac1bf",
        "gi_v02_a91ed9ca00fc"
      ]
    },
    {
      "passage_id": "ielts17_test4_p3",
      "sentence_id": "C-01",
      "target": "when he was six years old",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_3d0f4607ec49",
        "gi_v02_ae15e82dda2f"
      ]
    },
    {
      "passage_id": "ielts18_test1_p2",
      "sentence_id": "F-01",
      "target": "when other seedlings have become established",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_12eb0e6c2a1c",
        "gi_v02_6de35c2e1cd2",
        "gi_v02_c80d0eec94bf"
      ]
    },
    {
      "passage_id": "ielts18_test3_p2",
      "sentence_id": "B-03",
      "target": "when the engines backfired",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_3c70bc3761ed",
        "gi_v02_c8d6a75d8c64",
        "gi_v02_d22f74703b02"
      ]
    },
    {
      "passage_id": "ielts18_test3_p2",
      "sentence_id": "E-02",
      "target": "when they should go forward",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_2192579f8df4",
        "gi_v02_6f8804a4a2c9",
        "gi_v02_bdb48705398a"
      ]
    },
    {
      "passage_id": "ielts18_test4_p2",
      "sentence_id": "D-02",
      "target": "when they applaud the benefits of a growth mindset",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_4dc0825bf402",
        "gi_v02_ae055a381d4e"
      ]
    },
    {
      "passage_id": "ielts19_test1_p3",
      "sentence_id": "G-04",
      "target": "when scanning and processing written information",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_60eff7dd3516",
        "gi_v02_ffc659439aef"
      ]
    },
    {
      "passage_id": "ielts19_test2_p2",
      "sentence_id": "E-01",
      "target": "when they're under pressure",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_69c4b3c21365",
        "gi_v02_8bdfc44fa6c0"
      ]
    },
    {
      "passage_id": "ielts20_test2_p2",
      "sentence_id": "F-39",
      "target": "when we should be focusing on the thing we should be getting on with",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_04d87142654c",
        "gi_v02_2f2ca74cb7df"
      ]
    },
    {
      "passage_id": "ielts20_test2_p2",
      "sentence_id": "F-41",
      "target": "when we procrastinate",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_63ade38709dd",
        "gi_v02_755efcc1472a"
      ]
    },
    {
      "passage_id": "ielts20_test2_p3",
      "sentence_id": "B-08",
      "target": "when DeJesus announced calls",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_182bc77bff80",
        "gi_v02_ddc661d8a41f"
      ]
    },
    {
      "passage_id": "ielts20_test2_p3",
      "sentence_id": "F-32",
      "target": "when the hundred-mile-an-hour fastball, which is difficult to hit and control, entered the game",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_42564e300883",
        "gi_v02_dc3a6ecd6050"
      ]
    },
    {
      "passage_id": "ielts20_test4_p3",
      "sentence_id": "A-02",
      "target": "when such predators were largely exterminated",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_39a07a233cdb",
        "gi_v02_f252be3f87cd"
      ]
    },
    {
      "passage_id": "ielts4_test2_p1",
      "sentence_id": "D-19",
      "target": "when a small community finds itself alongside a larger, wealthier society",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_1ab1acbb8299",
        "gi_v02_88334279fca2",
        "gi_v02_e10472003655"
      ]
    },
    {
      "passage_id": "ielts4_test2_p2",
      "sentence_id": "G-31",
      "target": "when conventional medicine seems not to offer the answer",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_1822b538098a",
        "gi_v02_78edb489fe98",
        "gi_v02_ce1ff6547306"
      ]
    },
    {
      "passage_id": "ielts4_test2_p3",
      "sentence_id": "D-24",
      "target": "when they reached adulthood.",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_44399fba3ab2",
        "gi_v02_828954cb9539"
      ]
    },
    {
      "passage_id": "ielts4_test2_p3",
      "sentence_id": "I-46",
      "target": "when they interact with their peers.",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_0c72255dbcc0",
        "gi_v02_ea393cfaada4"
      ]
    },
    {
      "passage_id": "ielts4_test3_p3",
      "sentence_id": "C-09",
      "target": "when a language has not been described before",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_d2a958ea6e8a"
      ]
    },
    {
      "passage_id": "ielts5_test2_p1",
      "sentence_id": "D-10",
      "target": "when, as a young chemistry student in Belgium, he embarked on research into phenolic resins",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_5f020b6981a4",
        "gi_v02_823bf71c9286"
      ]
    },
    {
      "passage_id": "ielts5_test2_p2",
      "sentence_id": "B-12",
      "target": "when the punchline is either a nonsense or, though appearing silly, has a clever second meaning",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_87ed5a9d2305",
        "gi_v02_e22803a64985"
      ]
    },
    {
      "passage_id": "ielts5_test4_p1",
      "sentence_id": "C-38",
      "target": "when tourism has penetrated their homelands",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_783887450784",
        "gi_v02_97596db61ae8"
      ]
    },
    {
      "passage_id": "ielts6_test1_p2",
      "sentence_id": "H-04",
      "target": "when America began to deregulate its transportation industry",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_04654647925b",
        "gi_v02_7391c9386b42"
      ]
    },
    {
      "passage_id": "ielts6_test2_p2",
      "sentence_id": "K-37",
      "target": "when they need it",
      "templates": [
        "adverbial_relation",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_1f41dc73d4f3",
        "gi_v02_a26029f2d6e9"
      ]
    },
    {
      "passage_id": "ielts6_test4_p2",
      "sentence_id": "A-01",
      "target": "when their mothers can read and write",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_57dddc4b865f",
        "gi_v02_68d6ef46aba4",
        "gi_v02_8014e7c3aa8d"
      ]
    },
    {
      "passage_id": "ielts7_test2_p1",
      "sentence_id": "B-08",
      "target": "when it was built in 1968",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_1316a023e923",
        "gi_v02_957212f217d6"
      ]
    },
    {
      "passage_id": "ielts7_test4_p2",
      "sentence_id": "G-01",
      "target": "when, in the months leading up to MSC's final decision, salmon runs throughout western Alaska completely collapsed",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_0aff123f79be",
        "gi_v02_3d890b164cbc",
        "gi_v02_7e478f16ad90"
      ]
    },
    {
      "passage_id": "ielts7_test4_p3",
      "sentence_id": "C-06",
      "target": "when the subjects were required to proofread written material under conditions of no noise",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_0e063fdeb711",
        "gi_v02_86638c9670a3",
        "gi_v02_e2c514b1afeb"
      ]
    },
    {
      "passage_id": "ielts8_test4_p2",
      "sentence_id": "J-02",
      "target": "when Sri Lanka's flourishing coconut groves were plagued by leaf-mining hispides",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_388471339b2f",
        "gi_v02_508cfa56eabd",
        "gi_v02_91269ceab6c6"
      ]
    },
    {
      "passage_id": "ielts9_test1_p1",
      "sentence_id": "I-03",
      "target": "when she decided the new colour flattered her",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_978b04977909",
        "gi_v02_9c545b9e6af9"
      ]
    },
    {
      "passage_id": "ielts9_test2_p2",
      "sentence_id": "E-04",
      "target": "when it is seen just outside the Sun's disc",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_32095591a49e",
        "gi_v02_38f1dd48aa50",
        "gi_v02_8ad1b408e9f0"
      ]
    },
    {
      "passage_id": "ielts9_test3_p3",
      "sentence_id": "B-12",
      "target": "when still a student",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_a26dd219e32f",
        "gi_v02_f68d7d773186"
      ]
    },
    {
      "passage_id": "reading_jijing_10_test_78_p2",
      "sentence_id": "B-17",
      "target": "when one normally focuses and listens to one another",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_408e960a87a7",
        "gi_v02_aab7af3aefff"
      ]
    },
    {
      "passage_id": "reading_jijing_13_test_6_p1",
      "sentence_id": "H-04",
      "target": "when in fact this officer has functioned as 'Minister for Sickness and the Construction of Hospitals'",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_345f41f7478b",
        "gi_v02_748f4e77f787",
        "gi_v02_fbb3bf1a5a47"
      ]
    },
    {
      "passage_id": "reading_jijing_14_test_23_p2",
      "sentence_id": "G-05",
      "target": "when in actual fact they are simply based on an unthinking and directionless material count",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_0395b4cf7d2d",
        "gi_v02_1cc83fd4e466",
        "gi_v02_456f088a9576"
      ]
    },
    {
      "passage_id": "reading_jijing_16_test_97_p2",
      "sentence_id": "F-36b",
      "target": "when I really know it's not going to happen",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_4100dc63ab4c",
        "gi_v02_dcfc4beae473",
        "gi_v02_eb95d63a0d2f"
      ]
    },
    {
      "passage_id": "reading_jijing_24_test_56_p2",
      "sentence_id": "I-06",
      "target": "when the decision is not crucial",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_0ad2afd4b319",
        "gi_v02_25e57b23fe04",
        "gi_v02_481f3f71ff3a"
      ]
    },
    {
      "passage_id": "reading_jijing_24_test_56_p3",
      "sentence_id": "C-04",
      "target": "when supplies of fruit were depleted",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_38d49297c962",
        "gi_v02_690b3c1f3509",
        "gi_v02_7de3c89f34ea"
      ]
    },
    {
      "passage_id": "reading_jijing_38_test_22_p1",
      "sentence_id": "H-02",
      "target": "when custodial sentences are handed down to mothers caring for children",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_3e2c62bcb77f",
        "gi_v02_7211479b4b64",
        "gi_v02_f5f354897846"
      ]
    },
    {
      "passage_id": "reading_jijing_38_test_22_p3",
      "sentence_id": "B-01",
      "target": "when AACSB International. the most widely recognised global accrediting agency for business schools, announced it would consider changing the way it evaluates research",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_749abf062e90",
        "gi_v02_a250b556e86b",
        "gi_v02_c0b31ee16ce8"
      ]
    },
    {
      "passage_id": "reading_jijing_40_test_75_p1",
      "sentence_id": "C-01",
      "target": "when he was in his forties",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_5ed90cb62276",
        "gi_v02_8debe64ef90b",
        "gi_v02_a63300ee0f7f"
      ]
    },
    {
      "passage_id": "reading_jijing_44_test_29_p3",
      "sentence_id": "A-01",
      "target": "when they returned from school",
      "templates": [
        "adverbial_relation",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_54094ea3e4e3",
        "gi_v02_60344ae1f1fe"
      ]
    },
    {
      "passage_id": "reading_jijing_44_test_29_p3",
      "sentence_id": "A-02",
      "target": "when fathers had gone off to war, and mothers had gone into industry",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_695f59a749f1",
        "gi_v02_8b229a84a21f",
        "gi_v02_e4433836e04c"
      ]
    },
    {
      "passage_id": "reading_jijing_46_test_84_p1",
      "sentence_id": "E-03",
      "target": "when he said",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_a61003ab901b",
        "gi_v02_bf1532fb5bb5",
        "gi_v02_c15b484dcbf4"
      ]
    },
    {
      "passage_id": "reading_jijing_48_test_21_p3",
      "sentence_id": "D-03",
      "target": "when the development of global warming is accompanied by the falling snow line",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_350cda42e817",
        "gi_v02_3f496362b055",
        "gi_v02_c19e452a622b"
      ]
    },
    {
      "passage_id": "reading_jijing_50_test_30_p2",
      "sentence_id": "D-05",
      "target": "when she is still feeding on them",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_1bd1a43134c9",
        "gi_v02_80ad8496544d",
        "gi_v02_f2c2d182baea"
      ]
    },
    {
      "passage_id": "reading_jijing_53_test_83_p3",
      "sentence_id": "A-02",
      "target": "when their monthly fuel quota of four litres dried up in just a fortnight",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_44a78fb23d4e",
        "gi_v02_6801bb94f7a3",
        "gi_v02_89fd2d11daf3"
      ]
    },
    {
      "passage_id": "reading_jijing_5_test_59_p1",
      "sentence_id": "C-03",
      "target": "when drops of mercury from a shattered thermometer produced a photographic image",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_472b3e5a82b7",
        "gi_v02_cde790ece7e7"
      ]
    },
    {
      "passage_id": "reading_jijing_5_test_59_p1",
      "sentence_id": "C-06",
      "target": "when he used bits of adhesive office paper",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_ca9a2c9d5af1",
        "gi_v02_da26758657bc"
      ]
    },
    {
      "passage_id": "reading_jijing_5_test_59_p1",
      "sentence_id": "I-02",
      "target": "when it launched a new beer",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_388494a8a9d5",
        "gi_v02_ee5f6d0ec66b"
      ]
    },
    {
      "passage_id": "reading_jijing_5_test_59_p2",
      "sentence_id": "H-06",
      "target": "when profit-taking by retailers or packers is a more likely scenario",
      "templates": [
        "adverbial_relation",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_4142410319af",
        "gi_v02_b07f25ed1389"
      ]
    },
    {
      "passage_id": "reading_jijing_62_test_44_p3",
      "sentence_id": "B-03",
      "target": "when Sainsbury introduced shopping baskets into its 1950s stores",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_39369274a5f7",
        "gi_v02_71034136d4f2",
        "gi_v02_8da689cf2443"
      ]
    },
    {
      "passage_id": "reading_jijing_6_test_71_p1",
      "sentence_id": "D-01",
      "target": "when the first fashion store 'Ravissant' opened in Mumbai",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_01a3207497b7",
        "gi_v02_09f114e61e92",
        "gi_v02_4c4f9ee2d2df"
      ]
    },
    {
      "passage_id": "reading_jijing_72_test_15_p2",
      "sentence_id": "B-05",
      "target": "when he returns",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_7bb5b8a57f2e",
        "gi_v02_fb1b20bf8dbc"
      ]
    },
    {
      "passage_id": "reading_jijing_72_test_15_p2",
      "sentence_id": "D-05",
      "target": "when pretending a banana is a telephone",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_d05f2b63ecad",
        "gi_v02_fe742e071627"
      ]
    },
    {
      "passage_id": "reading_jijing_79_test_24_p1",
      "sentence_id": "C-04",
      "target": "when not on duty",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_c3e7cf202979",
        "gi_v02_e0b9121ca0dc"
      ]
    },
    {
      "passage_id": "reading_jijing_81_test_93_p1",
      "sentence_id": "C-05",
      "target": "when children stayed up late",
      "templates": [
        "adverbial_relation",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_11bfd7277fab",
        "gi_v02_f18cf9ccea5d"
      ]
    },
    {
      "passage_id": "reading_jijing_82_test_4_p3",
      "sentence_id": "F-03",
      "target": "when something more attractive comes along",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_80e0b92aedf6",
        "gi_v02_b84b561ef465"
      ]
    },
    {
      "passage_id": "reading_jijing_83_test_95_p1",
      "sentence_id": "A-02",
      "target": "when animals still were considered automatons",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_0c2f6ba1c549",
        "gi_v02_250fba7ae9d9",
        "gi_v02_cbe99dd2e12a"
      ]
    },
    {
      "passage_id": "reading_jijing_84_test_73_p2",
      "sentence_id": "D-24",
      "target": "when they leave school",
      "templates": [
        "adverbial_relation",
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_0087e03e6b6b",
        "gi_v02_488a091a620c",
        "gi_v02_48ee07de62a6"
      ]
    },
    {
      "passage_id": "reading_jijing_88_test_98_p2",
      "sentence_id": "C-06",
      "target": "when they switch from VCRs to DVD players",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_4548d50d85df",
        "gi_v02_905c6477311a"
      ]
    },
    {
      "passage_id": "reading_jijing_88_test_98_p2",
      "sentence_id": "K-02",
      "target": "when researchers presented people with evidence",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_5e937f86caff",
        "gi_v02_77c598c7a0ba"
      ]
    },
    {
      "passage_id": "reading_jijing_88_test_98_p3",
      "sentence_id": "C-01",
      "target": "when their techniques are revealed",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_488f7901926d",
        "gi_v02_c6f1e2319329"
      ]
    },
    {
      "passage_id": "reading_jijing_92_test_58_p1",
      "sentence_id": "B-04",
      "target": "when they witness a film character gets shot",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_00107f31b110",
        "gi_v02_b48b6bbf8a83"
      ]
    },
    {
      "passage_id": "reading_jijing_92_test_58_p1",
      "sentence_id": "C-02",
      "target": "when Professor Simon Baron-Cohen and his colleagues used fMRls on six synaesthetes and discovered",
      "templates": [
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_4757cfc9ef28"
      ]
    },
    {
      "passage_id": "reading_jijing_92_test_58_p2",
      "sentence_id": "B-02",
      "target": "when people increasingly demand more water than is available or safe for use",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_48df6847046a",
        "gi_v02_671ca54d1f25"
      ]
    },
    {
      "passage_id": "reading_jijing_92_test_58_p3",
      "sentence_id": "E-05",
      "target": "when three freak waves hit the beach",
      "templates": [
        "clause_boundary",
        "clause_type_classify"
      ],
      "item_ids": [
        "gi_v02_20bd5c1b2c28",
        "gi_v02_2965428387ff"
      ]
    }
  ]
}
```

## 重新拆句

```json
{
  "sentences_before": 12657,
  "sentences_after": 12688,
  "added": 31,
  "new_sentence_ids": [
    "reading_jijing_10_test_78_p3 E-04b",
    "reading_jijing_10_test_78_p3 P-01b",
    "reading_jijing_14_test_23_p1 G-02b",
    "reading_jijing_14_test_23_p3 H-01b",
    "reading_jijing_16_test_97_p2 B-09b",
    "reading_jijing_16_test_97_p2 F-36b",
    "reading_jijing_16_test_97_p2 F-36c",
    "reading_jijing_16_test_97_p2 F-36d",
    "reading_jijing_16_test_97_p2 F-36e",
    "reading_jijing_18_test_53_p2 E-01b",
    "reading_jijing_18_test_53_p2 E-01c",
    "reading_jijing_23_test_46_p1 B-04b",
    "reading_jijing_24_test_56_p1 D-01b",
    "reading_jijing_38_test_22_p1 E-03b",
    "reading_jijing_44_test_29_p1 H-03b",
    "reading_jijing_46_test_84_p1 B-09b",
    "reading_jijing_53_test_83_p2 B-03b",
    "reading_jijing_56_test_64_p2 G-03b",
    "reading_jijing_65_test_69_p1 I-03b",
    "reading_jijing_71_test_1_p2 E-01b",
    "reading_jijing_73_test_5_p1 H-01b",
    "reading_jijing_76_test_43_p2 E-04b",
    "reading_jijing_78_test_102_p2 G-01b",
    "reading_jijing_78_test_102_p3 E-03b",
    "reading_jijing_82_test_4_p1 F-04b",
    "reading_jijing_85_test_12_p1 C-05b",
    "reading_jijing_85_test_12_p1 C-05c",
    "reading_jijing_88_test_98_p2 D-02b",
    "reading_jijing_88_test_98_p2 G-04b",
    "reading_jijing_88_test_98_p3 D-10b",
    "reading_jijing_91_test_49_p1 F-07b"
  ]
}
```

## 独立整句过滤命中

### tagged_fragment

实际 37 句；计划预期 37 句。

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
- `reading_jijing_71_test_1_p2` E-01：The most immediate translation issue relates to the movie's title, 'Lo Scopone Scientifico', translates as 'Scientific Scopone', whereas the English title is, 'The Scientific Card Player'.
- `reading_jijing_73_test_5_p1` K-01：Standing on a roof catwalk, peering down inside at people as small as termites below.
- `reading_jijing_73_test_5_p1` K-03：like that termite fungus, further extending the whole 'organic machine' metaphor.
- `reading_jijing_73_test_5_p2` F-05：Many incidents of attacks on people involving villagers squatting or bending over to cut grass for fodder or building material.
- `reading_jijing_85_test_12_p1` C-08：The company is the recipe is in a vault somewhere and in my sole owner of the intellectual property.
### clause_attached_to_conjunction

实际 2 句；计划预期 2 句。

- `ielts13_test2_p2` C-04：Jennifer Bartz from Mount Sinai School of Medicine, New York, found that it improves people's ability to read emotions, but only if they are not very socially adept to begin with.
- `reading_jijing_56_test_64_p2` C-01：It did not deter him, and while many of the critics in the scientific establishment who vilified him disappeared from view.
### glued_sentence_boundary

实际 0 句；计划预期 0 句。

### multi_sentence_unit

实际 51 句；计划未设预期，只报告。

- `ielts18_test4_p2` F-03：She has also expressed concerns that her theories are being misappropriated in schools by being conflated with the self-esteem movement: 'For me the growth mindset is a tool for learning and improvement. It's not just a vehicle for making children feel good.'
- `ielts19_test4_p3` H-02：These were the traits that were prevalent in human life for tens of thousands of years. So presumably these traits are still strong in us now.
- `ielts20_test2_p3` I-51：He later told me, "This is part of a movement to use algorithms to take the hard choices of living out of life." Perhaps he's right.
- `ielts20_test4_p2` B-11：She knows that they’re essential and that the job is far from over. ‘We know that in 20, 30, 40 years, we'll need to go back in there and adjust to the changing environment,’ she says.
- `ielts20_test4_p2` C-16：The programme has seen moderate success, mainly in areas with less subsidence. ‘Unfortunately, traditional infrastructure is often single-solution focused,’ says Tol. ‘For long-term success, it’s critical that we transition towards multifunctional approaches that embed natural processes and that engage and benefit communities and local decision-makers.’
- `ielts20_test4_p2` D-19：The modifications were made by the Buoyant Foundation Project, a not-for-profit organisation that has been researching and retrofitting amphibious houses since 2006. ‘When I started this,’ explains founder Elizabeth English, ‘climate change was not on the tip of everybody’s tongue, but this technology is becoming necessary in places that didn’t previously need it.’ It’s much cheaper than permanently elevating houses, English explains – about a third of what it would cost to completely replace a building’s foundations.
- `ielts20_test4_p2` E-23：Most of the country is less than a metre above sea level and 80 per cent of its land lies on floodplains. ‘Almost 35 million people living on the coastal belt of Bangladesh are currently affected by soil and water salinity,’ says Raisa Chowdhury of the international development organisation ICCO Cooperation.
- `ielts4_test1_p3` I-31：For example, we asked: What goes with soft? A circle or a square? Which shape goes with hard?
- `ielts4_test2_p1` E-27："They cannot refuse to speak English if most commercial activity is in English." But are languages worth saving?
- `ielts4_test2_p2` B-06："We've had a tradition of doctors being fairly powerful and I guess they are pretty loath to allow any pretenders to their position to come into it." In many other industrialized countries, orthodox and alternative medicines have worked "hand in glove" for years.
- `ielts4_test2_p3` A-07：Playful young animals use around two or three per cent of their energy cavorting, and in children that figure can be closer to fifteen per cent. "Even two or three per cent is huge," says John Byers of Idaho University. "You just don't find animals wasting energy like that," he adds.
- `ielts4_test2_p3` C-19：But Byers points out that the benefits of increased exercise disappear rapidly after training stops, so any improvement in endurance resulting from juvenile play would be lost by adulthood. "If the function of play was to get into shape," says Byers, "the optimum time for playing would depend on when it was most advantageous for the young of a particular species to do so.
- `ielts4_test2_p3` C-20：But it doesn't work like that." Across species, play tends to peak about halfway through the suckling stage and then decline.
- `ielts4_test2_p3` E-29：Robert Barton of Durham University believes that, because large brains are more sensitive to developmental stimuli than smaller brains, they require more play to help mould them for adulthood. “I concluded it's to do with learning, and with the importance of environmental data to the brain during development,” he says.
- `ielts4_test2_p3` G-37：Bekoff likens it to a behavioural kaleidoscope, with animals at play jumping rapidly between activities. "They use behaviour from a lot of different contexts - predation, aggression, reproduction," he says. "Their developing brain is getting all sorts of stimulation.
- `ielts4_test2_p3` H-38：Not only is more of the brain involved in play than was suspected, but it also seems to activate higher cognitive processes. "There's enormous cognitive involvement in play", says Bekoff.
- `ielts4_test2_p3` H-43：He was surprised by the extent of the activation. "Play just lights everything up," he says.
- `ielts4_test4_p1` B-10："Was there someone like [sprinter] Michael Johnson in the 1920s?" Dapena asks.
- `ielts4_test4_p1` C-14：But with the right training we can go much further with that one third than we've been going." Yessis believes that U.S.
- `ielts4_test4_p1` I-45：We've got a long way to go." For the foreseeable future, records will be made to be broken.
- `ielts5_test2_p2` A-02：The left.' No, not funny.
- `ielts5_test2_p2` A-05：The outside.' Hah!
- `ielts5_test4_p2` J-45：'It was a very expensive and time-consuming process that took around six months to complete.' Though the project cost A$1.6 million (nearly £700,000), the alternative - re-cladding the entire building - would have cost ten times as much.
- `ielts6_test2_p1` A-01：In fact, Newman believes the main reason for adopting one sort of transport over another is politics: 'The more democratic the process, the more public transport is favored.' He considers Portland, Oregon, a perfect example of this.
- `ielts7_test1_p3` C-11：In suggestopedia, as he called his method, consciousness is shifted away from the curriculum to focus on something peripheral. The curriculum then becomes peripheral and is dealt with by the reserve capacity of the brain.
- `ielts7_test2_p1` I-44：'With the eaves extending out on all sides like balancing poles,' says Mr Ishida, 'the building responds to even the most powerful jolt of an earthquake with a graceful swaying, never an abrupt shaking.' Here again, Japanese master builders of a thousand years ago anticipated concepts of modern structural engineering.
- `ielts7_test3_p1` D-03：The ants therefore cultivate these fungi in their nests, bringing them leaves to feed on, and then use them as a source of food. Farmer ants secrete antibiotics to control other fungi that might act as 'weeds', and spread waste to fertilise the crop.
- `ielts8_test3_p1` I-03：Diels also hopes to see the birth of 'interactive meteorology' - not just forecasting the weather but controlling it. 'If we could discharge clouds, we might affect the weather,' he says.
- `ielts8_test3_p3` A-03：'Nothing lives forever!' However, in this statement we think of artificially produced, technical objects, products which are subjected to natural wear and tear during use.
- `reading_jijing_16_test_97_p2` G-44：That is, they discount future time investments relatively steeply." Why do we perceive a greater "surplus" of time in the future than in the present?
- `reading_jijing_22_test_90_p2` G-24：It's just not cut-and-dried." The findings could be of help in slowing down the ongoing increase in childhood obesity, but for the time being, parents should be observant of their children's wake-sleep cycles, and take steps to ensure they are getting enough sleep, the researchers advised.
- `reading_jijing_26_test_72_p1` G-11："One thing we can be sure of is that black Sigatoka won't lose in this battle." Poor farmers, who cannot afford chemicals, have it even worse.
- `reading_jijing_32_test_20_p2` B-01：1. Valid assessment considers cultural and linguistic diversity as well as differences in communication and behavioural factors.
- `reading_jijing_32_test_20_p2` C-01：2. The existence of limitations in adaptive skills occurs within the context of community environments typical of the individual's age-peers and is indexed to the person's individualised needs for support.
- `reading_jijing_32_test_20_p2` D-01：3. Specific adaptive limitations often co-exist with strengths in other adaptive skills or other personal capabilities.
- `reading_jijing_32_test_20_p2` E-01：4. With appropriate support over a sustained period, the life functioning of the person with mental retardation will generally improve.
- `reading_jijing_38_test_22_p3` G-07：A paper in a 2006 issue of Strategy & Leadership commented that"research is not designed with managers' needs in mind, nor is it communicated in the journals they read. For the most part, it has become a self-referential closed system irrelevant to corporate performance."
- `reading_jijing_48_test_21_p3` G-02：Further losses of ice can be reflected in Mt. Cook Region.
- `reading_jijing_5_test_59_p1` A-01：In 1894 Dr John Kellogg and his brother. Will, were supervising a hospital and health spa in Michigan.
- `reading_jijing_65_test_69_p2` H-03：In his recent book Free Flight. James Fallows, a pilot as well as a writer, describes serious attempts by both state and private entrepreneurs in the USA to promote an 'air taxi' system within the price range of today's middle class and perhaps tomorrow's global population.
- `reading_jijing_69_test_40_p2` E-04：This adaptation helps the bristlecone photosynthesize during particularly brutal months. Saving the energy of constant needle replacement and providing a stable supply of chlorophyll.
- `reading_jijing_71_test_1_p2` B-03：In addition, the dubbed voices may seem detached or inappropriate to the characters, or otherwise, the absurdity of having an undereducated American ranffian saying. 'Je voudrais déclarer un vol' becomes too much, affecting appreciation of the film.
- `reading_jijing_72_test_15_p2` F-02：They found that children who socially interact with more adults, who have more friends. And who have more older siblings tend to pass TOM tasks at a slightly earlier age than other children.
- `reading_jijing_73_test_5_p1` H-02：But then his eyes lit up at the challenge.' Perhaps you could store the summer's heat in water somehow.
- `reading_jijing_73_test_5_p3` D-03：In fact. Hooker knew well enough what might happen.
- `reading_jijing_76_test_43_p3` A-07：Differences and similarities between children's compliance with requests and prohibitions ("Do"vs. "Don't" demand contexts) were also explored.
- `reading_jijing_83_test_95_p1` C-03：Scrub jays know that other jays are thieves and that stashed food can spoil; sheep can recognize faces; chimpanzees use a variety of tools to probe termite mounds and even use weapons to hunt small mammals; dolphins can imitate human postures; the archerfish, which stuns insects with a sudden blast of water, can learn how to aim its squirt simply by watching an experienced fish perform the task. And Alex the parrot turned out to be a surprisingly good talker.
- `reading_jijing_83_test_95_p1` G-08："What's different?" Pepperberg asked.
- `reading_jijing_9_test_81_p1` F-02：Test subject was given an argument "All animals with furs hibernate. Rabbit has fur. Therefore, rabbit hibernate".
- `reading_jijing_9_test_81_p2` A-02：In addition to providing the traditional resort-leisure product, it has been argued that ecotourism resort management should have a particular focus on best-practice environmental management. an educational and interpretive component, and direct anil indirect contributions to the conservation of the natural and cultural environment (Ayala. I996).
- `reading_jijing_9_test_81_p2` B-01：Conran Cove Island Resort is a large integrated ecotourism-based resort located south of Brisbane on the Gold Coast, Queensland. Australia.
### suspected_split_word

实际 6 句；计划未设预期，只报告。

- `reading_jijing_38_test_22_p3` C-04：A psychology professor must publish competi tive research in the top neuroscience journals.
- `reading_jijing_46_test_84_p1` E-01：It may be 2005, yet having children is a career-ending decision for millions of bright, ambit ions, and well-educated Japanese,
- `reading_jijing_85_test_12_p3` C-05：The researchers had calcu lated that revenues from the sale of fruits could far exceed those from a one- off sale of trees to loggers.
- `reading_jijing_9_test_81_p2` I-03：The resort has embraced and has effectively implemented contem porary environmental management practices.
- `reading_jijing_9_test_81_p2` I-04：It has been argued that the successful implemen tation of the principles of sustainability should promote long-term social, economic and envi ronmental benefits, while ensuring and enhancing the prospects of continued viability for the tourism enterprise.
- `reading_jijing_9_test_81_p2` I-08：However, the number of interstate and international tourists visiting the resort is small, with the principal visitor markets com prising locals and residents front nearby towns and the Gold Coast region.

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
- **finite_or_not**：auto_pass；目标 `to introduce`；答案 `非谓语（不定式、分词、动名词）`；标注与解析器一致；rejected：no_main_verb_tag
### reading_jijing_76_test_43_p2 H-02 (bad)

By the late 1980s the Modern Movement, unfairly blamed for the social experiments implicit in high- rise housing, had lost out to irony and spectacle in the shape of post-modernism, with its cheerful borrowings from anywhere and any period.

- **main_verb_tap**：auto_pass；目标 ``；答案 `had / lost / out`；标注与解析器一致
- **clause_boundary**：无适用白名单目标。
- **clause_type_classify**：无适用白名单目标。
- **adverbial_relation**：无适用白名单目标。
- **subject_span**：needs_review；目标 ``；答案 `By the late 1980s the Modern Movement, unfairly blamed for the social experiments implicit in high- rise housing`；subject_mismatch
- **finite_or_not**：auto_pass；目标 `had lost out`；答案 `主句谓语`；标注与解析器一致
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
- **finite_or_not**：auto_pass；目标 `has identified`；答案 `主句谓语`；标注与解析器一致；auto_pass；目标 `apply`；答案 `从句里的谓语`；标注与解析器一致
### ielts15_test2_p3 D-05 (positive)

Analysis revealed that, as expected, high-status individuals produced more dominant laughs and fewer submissive laughs relative to the low-status individuals.

- **main_verb_tap**：auto_pass；目标 ``；答案 `revealed`；标注与解析器一致
- **clause_boundary**：auto_pass；目标 ``；答案 `that, as expected, high-status individuals produced more dominant laughs and fewer submissive laughs relative to the low-status individuals`；标注与解析器一致
- **clause_type_classify**：auto_pass；目标 `that, as expected, high-status individuals produced more dominant laughs and fewer submissive laughs relative to the low-status individuals`；答案 `名词性从句`；标注与解析器一致；auto_pass；目标 `relative to the low-status individuals`；答案 `不是从句（短语或非谓语）`；标注与解析器一致
- **adverbial_relation**：无适用白名单目标。
- **subject_span**：auto_pass；目标 ``；答案 `Analysis`；标注与解析器一致
- **finite_or_not**：auto_pass；目标 `revealed`；答案 `主句谓语`；标注与解析器一致
### ielts4_test2_p2 G-31 (bad)

Alternative medicine appears to be an adjunct, sought in times of disenchantment when conventional medicine seems not to offer the answer.

- **main_verb_tap**：rejected：no_main_verb_tag
- **clause_boundary**：needs_review；目标 ``；答案 `when conventional medicine seems not to offer the answer`；possible_relative_adverb
- **clause_type_classify**：needs_review；目标 `when conventional medicine seems not to offer the answer`；答案 `状语从句`；possible_relative_adverb
- **adverbial_relation**：needs_review；目标 `when conventional medicine seems not to offer the answer`；答案 `时间`；possible_relative_adverb
- **subject_span**：rejected：no_main_verb_tag, split_subject
- **finite_or_not**：auto_pass；目标 `seems`；答案 `从句里的谓语`；标注与解析器一致；rejected：no_main_verb_tag
### ielts6_test3_p1 C-06 (positive)

That was the moment when cinema was born.

- **main_verb_tap**：needs_review；目标 ``；答案 `was`；ambiguous_span_location
- **clause_boundary**：auto_pass；目标 ``；答案 `when cinema was born`；标注与解析器一致
- **clause_type_classify**：auto_pass；目标 `when cinema was born`；答案 `定语从句`；标注与解析器一致
- **adverbial_relation**：无适用白名单目标。
- **subject_span**：needs_review；目标 ``；答案 `That`；ambiguous_span_location
- **finite_or_not**：needs_review；目标 `was`；答案 `主句谓语`；ambiguous_span_location；auto_pass；目标 `was born`；答案 `从句里的谓语`；标注与解析器一致
### reading_jijing_88_test_98_p2 G-04 (positive)

Fourth, and most important, losses have a far greater impact on people than similarly sized gains, a phenomenon that Kahneman and Tversky called "loss aversion."

- **main_verb_tap**：auto_pass；目标 ``；答案 `have`；标注与解析器一致
- **clause_boundary**：auto_pass；目标 ``；答案 `that Kahneman and Tversky called "loss aversion."`；标注与解析器一致
- **clause_type_classify**：auto_pass；目标 `that Kahneman and Tversky called "loss aversion."`；答案 `定语从句`；标注与解析器一致
- **adverbial_relation**：无适用白名单目标。
- **subject_span**：auto_pass；目标 ``；答案 `losses`；标注与解析器一致
- **finite_or_not**：auto_pass；目标 `have`；答案 `主句谓语`；标注与解析器一致；auto_pass；目标 `called`；答案 `从句里的谓语`；标注与解析器一致
### reading_jijing_88_test_98_p2 G-04b (positive)

For instance, studies show that most people will not accept a bet in which there is a 50% chance of winning $100 and a 50% chance of losing $100.

- **main_verb_tap**：auto_pass；目标 ``；答案 `show`；标注与解析器一致
- **clause_boundary**：auto_pass；目标 ``；答案 `in which there is a 50% chance of winning $100 and a 50% chance of losing $100`；标注与解析器一致；auto_pass；目标 ``；答案 `that most people will not accept a bet in which there is a 50% chance of winning $100 and a 50% chance of losing $100`；标注与解析器一致
- **clause_type_classify**：auto_pass；目标 `that most people will not accept a bet in which there is a 50% chance of winning $100 and a 50% chance of losing $100`；答案 `名词性从句`；标注与解析器一致；auto_pass；目标 `in which there is a 50% chance of winning $100 and a 50% chance of losing $100`；答案 `定语从句`；标注与解析器一致
- **adverbial_relation**：无适用白名单目标。
- **subject_span**：auto_pass；目标 ``；答案 `studies`；标注与解析器一致
- **finite_or_not**：auto_pass；目标 `show`；答案 `主句谓语`；标注与解析器一致；auto_pass；目标 `is`；答案 `从句里的谓语`；标注与解析器一致

## 计数和复现约定

- 候选题按 item_id 计数；模板 rejected 含每个整句拒绝一次，以及该模板的目标/选句拒绝记录。
- 原因码按候选题及拒绝记录计数；整句拒绝在 JSONL 中只记录一条，保留全部原因。
- 整句规则在全库独立统计，不受其他过滤顺序影响；multi_sentence_unit 只报告不设预期。
- v0.2：动词目标和干扰项都显示完整动词单位（含助动词、否定词、小品词），target.parts 为连续片段。
- v0.2：when/where/why 状语从句紧跟名词时，T2/T3/T4 一律 needs_review（possible_relative_adverb）。
- v0.2：动词单位不受原标注范围截断；有成分落在标注范围外时，T1/T6 一律 needs_review（verb_unit_outside_span），T1 答案按计划保持不变。
- v0.2：suspected_split_word 以全库词频判断（两个相邻词都极少见、拼起来是语料里出现过的词），只报告不设预期。
- 拆句前句数 = 拆句后句数 − 新增 ID 数：重新拆句只新增 <原ID>b 等句子，不删除句子。
- 无白名单目标的 T2/T3/T4 不生成题，也不虚构拒绝原因。T6(a) 单独记录主句选句拒绝。
- 字符偏移均为原句 [start,end)；evidence 中的 token 范围也是左闭右开。
- 分类答案使用固定选项文字；抽样 JSONL 的 pool_status 不写入工作簿。
- 同一模板完全相同的 item_id 和内容去重，ID 相同但内容不同则报错停止。
- XLSX 使用固定元数据和不压缩 ZIP，避免时间及压缩库版本影响字节复现。
