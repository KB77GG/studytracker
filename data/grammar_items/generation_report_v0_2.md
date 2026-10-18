# 语法候选题生成报告 v0.2

按执行计划 v0.2（在 v0.1 基础上的增量）生成；候选题尚未通过教师审核、未入库。

## 题型数量

| 题型 | auto_pass | needs_review | rejected |
|---|---:|---:|---:|
| main_verb_tap | 5935 | 367 | 6386 |
| clause_boundary | 4773 | 2400 | 2784 |
| clause_type_classify | 12929 | 1796 | 1430 |
| adverbial_relation | 446 | 589 | 2661 |
| subject_span | 5374 | 737 | 6577 |
| finite_or_not | 12755 | 1553 | 6572 |

## 范围

```json
{
  "passages": 317,
  "sentences": 12688,
  "candidates": 49654,
  "sentence_rejections": 1430,
  "template_rejections": 17830
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
  "reading_study_sha256": "2cd5c6e61e73d40210bf694262bb7144223a2812e15636a07704f6dbd728eef5",
  "grammar_graph_sha256": "c7b35ddb68db7601ccd01e38a210ad3dd772ff507302190f68a351e408b85a29"
}
```

## 知识点数量

```json
{
  "G-S01": {
    "auto_pass": 2765,
    "needs_review": 158
  },
  "G-S02": {
    "auto_pass": 5374,
    "needs_review": 737
  },
  "G-C02": {
    "auto_pass": 571,
    "needs_review": 644
  },
  "G-C03": {
    "auto_pass": 12929,
    "needs_review": 1796
  },
  "G-C04": {
    "auto_pass": 1796,
    "needs_review": 328
  },
  "G-C08": {
    "auto_pass": 1145,
    "needs_review": 739
  },
  "G-C10": {
    "auto_pass": 1261,
    "needs_review": 689
  },
  "G-C11": {
    "needs_review": 589,
    "auto_pass": 446
  },
  "G-N01": {
    "auto_pass": 10893,
    "needs_review": 1492
  },
  "G-N04": {
    "auto_pass": 1862,
    "needs_review": 61
  },
  "G-L01": {
    "auto_pass": 3170,
    "needs_review": 209
  }
}
```

## 原因码数量

```json
{
  "no_main_verb_tag": 12183,
  "coordinated_main_verbs": 3978,
  "split_subject": 3762,
  "coordinated_main_clauses": 3576,
  "clause_type_mismatch": 1896,
  "span_not_constituent": 1411,
  "ambiguous_span_location": 1371,
  "multiple_targets_same_type": 1354,
  "boundary_mismatch": 1291,
  "no_relation_label": 1231,
  "finiteness_mismatch": 666,
  "subject_mismatch": 562,
  "parser_root_outside_verb_span": 550,
  "unbalanced_quotes_or_brackets": 427,
  "subordinator_unknown": 322,
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
  "tagged_fragment": 36,
  "heading": 32,
  "parser_root_inside_subordinate_span": 22,
  "subordinator_mismatch": 18,
  "clause_attached_to_conjunction": 2
}
```

## 来源分布

```json
{
  "reading_jijing": 15966,
  "reading_test": 33688
}
```

## 难度分布

```json
{
  "easy": 16805,
  "hard": 18495,
  "medium": 14354
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
          "pool_size": 1131,
          "sample_size": 10
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 356,
          "sample_size": 3
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 468,
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
          "pool_size": 1058,
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
          "pool_size": 539,
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
          "pool_size": 987,
          "sample_size": 4
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 1560,
          "sample_size": 6
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 1158,
          "sample_size": 4
        },
        {
          "source_kind": "reading_test",
          "difficulty": "easy",
          "pool_size": 2282,
          "sample_size": 9
        },
        {
          "source_kind": "reading_test",
          "difficulty": "hard",
          "pool_size": 4199,
          "sample_size": 16
        },
        {
          "source_kind": "reading_test",
          "difficulty": "medium",
          "pool_size": 2743,
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
          "sample_size": 8
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 80,
          "sample_size": 9
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 92,
          "sample_size": 10
        },
        {
          "source_kind": "reading_test",
          "difficulty": "easy",
          "pool_size": 47,
          "sample_size": 5
        },
        {
          "source_kind": "reading_test",
          "difficulty": "hard",
          "pool_size": 80,
          "sample_size": 9
        },
        {
          "source_kind": "reading_test",
          "difficulty": "medium",
          "pool_size": 79,
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
          "pool_size": 1014,
          "sample_size": 9
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 341,
          "sample_size": 3
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 401,
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
          "pool_size": 1636,
          "sample_size": 6
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "hard",
          "pool_size": 1298,
          "sample_size": 5
        },
        {
          "source_kind": "reading_jijing",
          "difficulty": "medium",
          "pool_size": 1093,
          "sample_size": 4
        },
        {
          "source_kind": "reading_test",
          "difficulty": "easy",
          "pool_size": 2950,
          "sample_size": 12
        },
        {
          "source_kind": "reading_test",
          "difficulty": "hard",
          "pool_size": 3376,
          "sample_size": 13
        },
        {
          "source_kind": "reading_test",
          "difficulty": "medium",
          "pool_size": 2402,
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
  "distinct_targets": 109
}
```

## 重新拆句

```json
{
  "sentences": 12688,
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
- 无白名单目标的 T2/T3/T4 不生成题，也不虚构拒绝原因。T6(a) 单独记录主句选句拒绝。
- 字符偏移均为原句 [start,end)；evidence 中的 token 范围也是左闭右开。
- 分类答案使用固定选项文字；抽样 JSONL 的 pool_status 不写入工作簿。
- 同一模板完全相同的 item_id 和内容去重，ID 相同但内容不同则报错停止。
- XLSX 使用固定元数据和不压缩 ZIP，避免时间及压缩库版本影响字节复现。
