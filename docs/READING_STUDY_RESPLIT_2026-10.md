# 阅读解析重新拆句记录（2026-10）

> 依据：`docs/GRAMMAR_ITEM_CANDIDATES_PLAN_V0_2.md` 第 A 部分。共 28 个单元，修复后得到 59 句。
> 原文修改记在 `data/reading_jijing_text_fixes.json`，由 `scripts/reading_jijing_text_fixes.py` 和构建脚本应用。
> ID 规则：拆出的第一句沿用原 ID，其后依次加 b、c……；同文件的 `sentence_index` 重新连续编号，其他字段不变。
> 本文件由脚本生成，供 Claude 和老师核对。

## 1. `reading_jijing_10_test_78_p3` E-04

- **原句**：It is argued that packaging should be designed for moments such as these."Manufacturers are not aware of the complex situations into which products go.
- **原文修改**：`hese."Manufa` → `hese. "Manufa`（missing_space_between_sentences）
- **修复后**：
  - `E-04` It is argued that packaging should be designed for moments such as these.
    - 有人主张，包装应当针对这类时刻来设计。
  - `E-04b` "Manufacturers are not aware of the complex situations into which products go.
    - “制造商并没有意识到产品会进入多么复杂的使用情境。

## 2. `reading_jijing_10_test_78_p3` P-01

- **原句**：The RCA innovation exhibition this year revealed designs for a number of innovative objects."The popper", by Hugo Glover, aims to help arthritis sufferers remove tablets from blister packs, and "pluspoint", by James Cobb, is an adrenaline auto-injector that aims to overcome the fact that many patients do not carry their auto-injectors due to their prohibitive size.
- **原文修改**：`ects."The po` → `ects. "The po`（missing_space_between_sentences）
- **修复后**：
  - `P-01` The RCA innovation exhibition this year revealed designs for a number of innovative objects.
    - 今年的皇家艺术学院创新展展出了多种创新产品的设计。
  - `P-01b` "The popper", by Hugo Glover, aims to help arthritis sufferers remove tablets from blister packs, and "pluspoint", by James Cobb, is an adrenaline auto-injector that aims to overcome the fact that many patients do not carry their auto-injectors due to their prohibitive size.
    - 雨果·格洛弗设计的“The popper”旨在帮助关节炎患者从泡罩包装中取出药片；詹姆斯·科布设计的“pluspoint”则是一种肾上腺素自动注射器，旨在解决许多患者因注射器体积过大而不随身携带的问题。

## 3. `reading_jijing_14_test_23_p1` G-02

- **原句**：Rock was the least preferred across both gender groups and produced the longest waiting time estimates.'The rock music's driving beat kind of aggravates people calling customer assistance with a problem,' said Kellaris.
- **原文修改**：`ates.'The ro` → `ates. 'The ro`（missing_space_between_sentences）
- **修复后**：
  - `G-02` Rock was the least preferred across both gender groups and produced the longest waiting time estimates.
    - 摇滚乐在男女两组中都最不受欢迎，而且让人估计的等待时间最长。
  - `G-02b` 'The rock music's driving beat kind of aggravates people calling customer assistance with a problem,' said Kellaris.
    - “摇滚乐强劲的节拍多少会让那些因遇到问题而拨打客服的人更加烦躁，”凯拉里斯说。

## 4. `reading_jijing_14_test_23_p3` H-01

- **原句**：Jason Steiner, a school teacher in a Pittsburgh secondary school, is inclined to agree with Susie.'Whilst I'm not averse to driving, I would swap the stressful daily commute by car to a driverless one if I had the chance!
- **原文修改**：`usie.'Whilst` → `usie. 'Whilst`（missing_space_between_sentences）
- **修复后**：
  - `H-01` Jason Steiner, a school teacher in a Pittsburgh secondary school, is inclined to agree with Susie.
    - 匹兹堡一所中学的教师杰森·斯坦纳倾向于赞同苏茜的看法。
  - `H-01b` 'Whilst I'm not averse to driving, I would swap the stressful daily commute by car to a driverless one if I had the chance!
    - “虽然我并不排斥开车，但如果有机会，我愿意把每天充满压力的驾车通勤换成无人驾驶出行！

## 5. `reading_jijing_16_test_97_p2` B-09

- **原句**："If I happen to miss a birthday or anniversary, I know things are out of control."Being "too busy" is highly subjective.
- **原文修改**：`trol."Being ` → `trol." Being `（missing_space_between_sentences）
- **修复后**：
  - `B-09` "If I happen to miss a birthday or anniversary, I know things are out of control."
    - “如果我碰巧错过了生日或纪念日，我就知道事情已经失控了。”
  - `B-09b` Being "too busy" is highly subjective.
    - 所谓“太忙”是非常主观的。

## 6. `reading_jijing_16_test_97_p2` F-36

- **原句**：The Australian vice-president of AT Kearney, Neil Plumridge, says: "Often stress is caused by our setting unrealistic expectations of ourselves. I'll promise a client I'll do something tomorrow, and then promise another client the same thing, when I really know it's not going to happen.I've put stress on myself when I could have said to the clients: 'Why don't I give that to you in 48 hours?' The client doesn't care." Over-committing is something people experience as an individual problem.
- **原文修改**：`appen.I've p` → `appen. I've p`（missing_space_between_sentences）
- **修复后**：
  - `F-36` The Australian vice-president of AT Kearney, Neil Plumridge, says: "Often stress is caused by our setting unrealistic expectations of ourselves.
    - AT Kearney 澳大利亚区副总裁尼尔·普拉姆里奇说：“压力往往源于我们给自己设定了不切实际的期望。
  - `F-36b` I'll promise a client I'll do something tomorrow, and then promise another client the same thing, when I really know it's not going to happen.
    - 我会答应一个客户明天做完某件事，然后又对另一个客户做同样的承诺，而我心里其实很清楚这不可能做到。
  - `F-36c` I've put stress on myself when I could have said to the clients: 'Why don't I give that to you in 48 hours?'
    - 我本可以对客户说“我48小时后给你怎么样？”，却给自己施加了压力。
  - `F-36d` The client doesn't care."
    - 客户其实并不在意。”
  - `F-36e` Over-committing is something people experience as an individual problem.
    - 过度承诺是人们当作个人问题来经历的事情。

## 7. `reading_jijing_18_test_53_p2` E-01

- **原句**：Steve Sinnott, General Secretary of the National Union of Teachers, said England's testing system was having a 'devastating' impact on schools.'Uniquely, England is a country where testing is used to police schools and control what is taught,' he said.'When it comes to testing in England, the tail wags the dog.
- **原文修改**：`ools.'Unique` → `ools. 'Unique`（missing_space_between_sentences）；`said.'When i` → `said. 'When i`（missing_space_between_sentences）
- **修复后**：
  - `E-01` Steve Sinnott, General Secretary of the National Union of Teachers, said England's testing system was having a 'devastating' impact on schools.
    - 全国教师工会总书记史蒂夫·辛诺特说，英格兰的考试制度正在对学校造成“毁灭性”的影响。
  - `E-01b` 'Uniquely, England is a country where testing is used to police schools and control what is taught,' he said.
    - “英格兰与众不同之处在于，考试被用来监管学校、控制教学内容，”他说。
  - `E-01c` 'When it comes to testing in England, the tail wags the dog.
    - “说到英格兰的考试，完全是本末倒置。

## 8. `reading_jijing_23_test_46_p1` B-04

- **原句**：Certain researchers, such as Dr Michael Crawley, argue: 'even though this natural phenomenon does exist it is without a doubt human activity that has worsened its effect; this is evident when comparing data regarding the earth's temperature in the last one hundred years with the one hundred years prior to that.'Some scientists, however, dispute this as Dr Ray Ellis suggests: 'human activity may be contributing a small amount to climate change but this increase in temperature is an unavoidable fact based on the research data we have compiled.
- **原文修改**：`that.'Some s` → `that.' Some s`（missing_space_between_sentences）
- **修复后**：
  - `B-04` Certain researchers, such as Dr Michael Crawley, argue: 'even though this natural phenomenon does exist it is without a doubt human activity that has worsened its effect; this is evident when comparing data regarding the earth's temperature in the last one hundred years with the one hundred years prior to that.'
    - 一些研究者（如迈克尔·克劳利博士）认为：“尽管这种自然现象确实存在，但毫无疑问，是人类活动加剧了它的影响；把过去一百年的地球温度数据与此前一百年相比，这一点就很明显。”
  - `B-04b` Some scientists, however, dispute this as Dr Ray Ellis suggests: 'human activity may be contributing a small amount to climate change but this increase in temperature is an unavoidable fact based on the research data we have compiled.
    - 然而，也有科学家对此提出异议，正如雷·埃利斯博士所说：“人类活动也许对气候变化有少量影响，但根据我们汇总的研究数据，这种升温是不可避免的事实。

## 9. `reading_jijing_24_test_56_p1` D-01

- **原句**：According to Dr. Colin Groves, of the Department of Archaeology and Anthropology at Australian National University, early humans came to rely on dogs' keen ability to hear, smell and see - allowing certain areas of the human brain to shrink in size relative to oilier areas.'Dogs acted as human's alarm systems, trackers and hunting aids, garbage disposal facilities, hot-water bottles and children's guardians and playmates.
- **原文修改**：`reas.'Dogs a` → `reas. 'Dogs a`（missing_space_between_sentences）
- **修复后**：
  - `D-01` According to Dr. Colin Groves, of the Department of Archaeology and Anthropology at Australian National University, early humans came to rely on dogs' keen ability to hear, smell and see - allowing certain areas of the human brain to shrink in size relative to oilier areas.
    - 澳大利亚国立大学考古与人类学系的科林·格罗夫斯博士认为，早期人类逐渐依赖狗敏锐的听觉、嗅觉和视觉，这使人脑的某些区域相对于其他区域缩小了。
  - `D-01b` 'Dogs acted as human's alarm systems, trackers and hunting aids, garbage disposal facilities, hot-water bottles and children's guardians and playmates.
    - “狗充当了人类的警报系统、追踪者和狩猎助手、垃圾处理设施、热水袋，以及孩子的守护者和玩伴。

## 10. `reading_jijing_38_test_22_p1` E-03

- **原句**：As a Conservative white paper concluded in 1990, 'We know that prison is an expensive way of making bad people worse.'Interestingly, the report also argued that there should be a range of community-based sentences which would be cheaper and more effective alternatives to prison.
- **原文修改**：`orse.'Intere` → `orse.' Intere`（missing_space_between_sentences）
- **修复后**：
  - `E-03` As a Conservative white paper concluded in 1990, 'We know that prison is an expensive way of making bad people worse.'
    - 正如一份保守党白皮书在1990年得出的结论：“我们知道，监狱是一种代价高昂、只会让坏人变得更坏的方式。”
  - `E-03b` Interestingly, the report also argued that there should be a range of community-based sentences which would be cheaper and more effective alternatives to prison.
    - 有意思的是，这份报告还主张，应当设立一系列社区刑罚，作为比监禁更便宜、更有效的替代方案。

## 11. `reading_jijing_44_test_29_p1` H-03

- **原句**：In the insect's most famous literary appearance - Franz Kafka's 'The Metamorphosis' - a man, Gregor, is transformed overnight into a monstrous insect, probably a cockroach (although the story never quite makes that clear).Gregor's transformation results in very predictable responses from his family and friends, who can never accept him again.
- **原文修改**：`lear).Gregor` → `lear). Gregor`（missing_space_between_sentences）
- **修复后**：
  - `H-03` In the insect's most famous literary appearance - Franz Kafka's 'The Metamorphosis' - a man, Gregor, is transformed overnight into a monstrous insect, probably a cockroach (although the story never quite makes that clear).
    - 在这种昆虫最著名的文学形象——弗兰茨·卡夫卡的《变形记》中，一个名叫格里高尔的人一夜之间变成了一只可怕的昆虫，很可能是蟑螂（尽管故事从未完全说清楚）。
  - `H-03b` Gregor's transformation results in very predictable responses from his family and friends, who can never accept him again.
    - 格里高尔的变形引起了家人和朋友完全可以预料的反应：他们再也无法接受他了。

## 12. `reading_jijing_46_test_84_p1` B-09

- **原句**：Thailand, Malaysia, and China are three economies widely seen as the future of Asia.Thailand's economic boom in recent years has prompted many leaders in the region to look at its growth strategy.
- **原文修改**：` Asia.Thaila` → ` Asia. Thaila`（missing_space_between_sentences）
- **修复后**：
  - `B-09` Thailand, Malaysia, and China are three economies widely seen as the future of Asia.
    - 泰国、马来西亚和中国是被普遍视为亚洲未来的三个经济体。
  - `B-09b` Thailand's economic boom in recent years has prompted many leaders in the region to look at its growth strategy.
    - 近年来泰国的经济繁荣促使该地区许多领导人研究其增长战略。

## 13. `reading_jijing_53_test_83_p2` B-03

- **原句**：You'd be far better off giving it up and relying on other forms of transport."I'm 47 and I've never owned a car, despite having a job that requires me to travel all over the South-East to visit clients," says Donnachadh McCarthy, an environmental expert who specialises in advising people how to be greener.
- **原文修改**：`port."I'm 47` → `port. "I'm 47`（missing_space_between_sentences）
- **修复后**：
  - `B-03` You'd be far better off giving it up and relying on other forms of transport.
    - 放弃开车、改用其他交通方式，你的处境会好得多。
  - `B-03b` "I'm 47 and I've never owned a car, despite having a job that requires me to travel all over the South-East to visit clients," says Donnachadh McCarthy, an environmental expert who specialises in advising people how to be greener.
    - “我47岁了，从没拥有过汽车，尽管我的工作需要我跑遍英格兰东南部去拜访客户。”唐纳查德·麦卡锡说。他是一名环境专家，专门指导人们如何过得更环保。

## 14. `reading_jijing_56_test_64_p2` G-03

- **原句**：Venter has found that t his may not be the case.The culprit could be bacterial viruses phages - which keep microbe levels low in some seas.
- **原文修改**：` case.The cu` → ` case. The cu`（missing_space_between_sentences）；`that t his may` → `that this may`（typo）
- **修复后**：
  - `G-03` Venter has found that this may not be the case.
    - 文特尔发现，情况可能并非如此。
  - `G-03b` The culprit could be bacterial viruses phages - which keep microbe levels low in some seas.
    - 罪魁祸首可能是细菌病毒，即噬菌体，它们使某些海域的微生物数量保持在较低水平。

## 15. `reading_jijing_65_test_69_p1` I-03

- **原句**：And music may have had an even more important role.'All music has a message.' he says.
- **原文修改**：`role.'All mu` → `role. 'All mu`（missing_space_between_sentences）
- **修复后**：
  - `I-03` And music may have had an even more important role.
    - 而音乐也许还发挥过更重要的作用。
  - `I-03b` 'All music has a message.' he says.
    - “所有的音乐都传达着某种信息，”他说。

## 16. `reading_jijing_71_test_1_p2` E-01

- **原句**：The most immediate translation issue relates to the movie's title, 'Lo Scopone Scientifico',translates as 'Scientific Scopone', whereas the English title is, 'The Scientific Card Player'.'Scopone' is the name of a traditional Italian card game of great antiquity.
- **原文修改**：`yer'.'Scopon` → `yer'. 'Scopon`（missing_space_between_sentences）；`Scientifico',translates` → `Scientifico', translates`（missing_space）
- **修复后**：
  - `E-01` The most immediate translation issue relates to the movie's title, 'Lo Scopone Scientifico', translates as 'Scientific Scopone', whereas the English title is, 'The Scientific Card Player'.
    - 最直接的翻译问题与片名有关：《Lo Scopone Scientifico》直译为“科学斯科波内”，而英文片名却是《科学纸牌玩家》。
  - `E-01b` 'Scopone' is the name of a traditional Italian card game of great antiquity.
    - “Scopone”是一种历史非常悠久的意大利传统纸牌游戏的名字。

## 17. `reading_jijing_71_test_1_p3` A-01

- **原句**：The idea that the continents are moving was first proposed by a German meteorologist,.Alfred Wegener, in a book published in 1915.
- **原文修改**：`meteorologist,.Alfred` → `meteorologist, Alfred`（typo）
- **修复后**：
  - `A-01` The idea that the continents are moving was first proposed by a German meteorologist, Alfred Wegener, in a book published in 1915.
    - 大陆正在移动这一观点，最早由德国气象学家阿尔弗雷德·魏格纳在1915年出版的一本书中提出。

## 18. `reading_jijing_73_test_5_p1` H-01

- **原句**：This is all possible only because Harare is 1600 feet above sea level, has cloudless skies, little humidity and rapid temperature swings days as warm as 31°C commonly drop to 14°C at night.'You couldn't do this in New York, with its fantastically hot summers and fantastically cold winters,' Pearce said.
- **原文修改**：`ight.'You co` → `ight. 'You co`（missing_space_between_sentences）
- **修复后**：
  - `H-01` This is all possible only because Harare is 1600 feet above sea level, has cloudless skies, little humidity and rapid temperature swings days as warm as 31°C commonly drop to 14°C at night.
    - 这一切之所以可行，只是因为哈拉雷海拔1600英尺，天空少云，湿度低，而且气温变化快：白天高达31°C，夜里通常会降到14°C。
  - `H-01b` 'You couldn't do this in New York, with its fantastically hot summers and fantastically cold winters,' Pearce said.
    - “在纽约就没法这样做，那里的夏天酷热、冬天严寒，”皮尔斯说。

## 19. `reading_jijing_76_test_43_p2` E-04

- **原句**：Railing against the dehumanising effects of industrialisation, reformers like John Ruskin and William Morris made a concerted effort to return to hand-crafted, pre-industrial manufacturing techniques.Morris's influence grew from the production of furniture and textiles, until by the 1880s a generation of principled young architects was following his call for good, honest construction.
- **原文修改**：`iques.Morris` → `iques. Morris`（missing_space_between_sentences）
- **修复后**：
  - `E-04` Railing against the dehumanising effects of industrialisation, reformers like John Ruskin and William Morris made a concerted effort to return to hand-crafted, pre-industrial manufacturing techniques.
    - 约翰·拉斯金和威廉·莫里斯等改革者强烈反对工业化带来的非人化影响，齐心协力要回归手工制作的前工业时代生产技术。
  - `E-04b` Morris's influence grew from the production of furniture and textiles, until by the 1880s a generation of principled young architects was following his call for good, honest construction.
    - 莫里斯的影响从家具和纺织品生产领域不断扩大，到19世纪80年代，一代有原则的年轻建筑师都在响应他对优质、诚实建造的倡导。

## 20. `reading_jijing_78_test_102_p2` G-01

- **原句**：The quality that people seek most of all in a food, its flavour, is usually present in a quantity too infinitesimal to be measured by any traditional culinary terms such as ounces or teaspoons.Today's sophisticated spectrometers, gas chromatograph, and headspace vapor analyzers provide a detailed map of a food's flavour components, detecting chemical aromas in amounts as low as one part per billion.
- **原文修改**：`poons.Today'` → `poons. Today'`（missing_space_between_sentences）
- **修复后**：
  - `G-01` The quality that people seek most of all in a food, its flavour, is usually present in a quantity too infinitesimal to be measured by any traditional culinary terms such as ounces or teaspoons.
    - 人们在食物中最看重的品质——风味——通常含量极其微小，无法用盎司或茶匙这类传统烹饪单位来衡量。
  - `G-01b` Today's sophisticated spectrometers, gas chromatograph, and headspace vapor analyzers provide a detailed map of a food's flavour components, detecting chemical aromas in amounts as low as one part per billion.
    - 如今先进的光谱仪、气相色谱仪和顶空蒸气分析仪能绘制出食物风味成分的详细图谱，检测出含量低至十亿分之一的化学香气。

## 21. `reading_jijing_78_test_102_p3` E-03

- **原句**：But to save energy, chipmakers such as Intel and AMD have shifted to so-called multicore technology, which packs multiple processors into one circuit rather than separating them."When we moved to multicore-away from a linear focus on megahertz and gigahertz— and throttled down microprocessors, the energy savings were pretty substantial," says Allyson Klein, Intel's marketing manager for its Ecotech Initiative.
- **原文修改**：`them."When w` → `them. "When w`（missing_space_between_sentences）
- **修复后**：
  - `E-03` But to save energy, chipmakers such as Intel and AMD have shifted to so-called multicore technology, which packs multiple processors into one circuit rather than separating them.
    - 但为了节能，英特尔和AMD等芯片制造商已经转向所谓的多核技术：把多个处理器封装进一个电路，而不是把它们分开。
  - `E-03b` "When we moved to multicore-away from a linear focus on megahertz and gigahertz— and throttled down microprocessors, the energy savings were pretty substantial," says Allyson Klein, Intel's marketing manager for its Ecotech Initiative.
    - “当我们转向多核技术——不再只盯着兆赫和吉赫这种线性指标——并降低微处理器的运行速度后，节能效果相当可观，”英特尔生态技术计划营销经理艾莉森·克莱因说。

## 22. `reading_jijing_82_test_4_p1` F-04

- **原句**：Still, 10 years later, in 1942, the operation could only produce a paltry 750 tons of latex rubber.Ford's factories were hoping for almost 40,000.
- **原文修改**：`ubber.Ford's` → `ubber. Ford's`（missing_space_between_sentences）
- **修复后**：
  - `F-04` Still, 10 years later, in 1942, the operation could only produce a paltry 750 tons of latex rubber.
    - 然而十年之后，也就是1942年，这项经营也只能生产区区750吨乳胶橡胶。
  - `F-04b` Ford's factories were hoping for almost 40,000.
    - 而福特的工厂原本期望的产量接近四万吨。

## 23. `reading_jijing_83_test_95_p1` G-08

- **原句**："What's different?"Pepperberg asked.
- **原文修改**：`rent?"Pepper` → `rent?" Pepper`（missing_space）
- **修复后**：
  - `G-08` "What's different?" Pepperberg asked.
    - “有什么不同？”佩珀伯格问。

## 24. `reading_jijing_85_test_12_p1` C-05

- **原句**："We didn't want to use chlorine, simple as that,"he says."It offers bad working conditions and there's no money in it."Peter looked at citrus ingredients, such as orange peel, to replace the petroleum by-products in cleaners.
- **原文修改**：`says."It off` → `says. "It off`（missing_space_between_sentences）；`n it."Peter ` → `n it." Peter `（missing_space_between_sentences）；`as that,"he says` → `as that," he says`（missing_space）
- **修复后**：
  - `C-05` "We didn't want to use chlorine, simple as that," he says.
    - “我们就是不想用氯，就这么简单，”他说。
  - `C-05b` "It offers bad working conditions and there's no money in it."
    - “它会带来恶劣的工作条件，而且也无利可图。”
  - `C-05c` Peter looked at citrus ingredients, such as orange peel, to replace the petroleum by-products in cleaners.
    - 彼得研究了橙皮等柑橘类原料，用来替代清洁剂中的石油副产品。

## 25. `reading_jijing_88_test_98_p2` D-02

- **原句**：Many products fail because of a universal, but largely ignored, psychological bias: People irrationally overvalue benefits they currently possess relative to those they don't.The bias leads consumers to value the advantages of products they own more than the benefits of new ones.
- **原文修改**：`don't.The bi` → `don't. The bi`（missing_space_between_sentences）
- **修复后**：
  - `D-02` Many products fail because of a universal, but largely ignored, psychological bias: People irrationally overvalue benefits they currently possess relative to those they don't.
    - 许多产品失败，是因为一种普遍存在却常被忽视的心理偏差：人们会不理性地高估自己现有的好处，而看轻自己没有的那些。
  - `D-02b` The bias leads consumers to value the advantages of products they own more than the benefits of new ones.
    - 这种偏差使消费者更看重自己已有产品的优点，而不是新产品的好处。

## 26. `reading_jijing_88_test_98_p2` G-04

- **原句**：Fourth, and most important, losses have a far greater impact on people than similarly sized gains, a phenomenon that Kahneman and Tversky called "loss aversion."For instance, studies show that most people will not accept a bet in which there is a 50% chance of winning $100 and a 50% chance of losing $100.
- **原文修改**：`sion."For in` → `sion." For in`（missing_space_between_sentences）
- **修复后**：
  - `G-04` Fourth, and most important, losses have a far greater impact on people than similarly sized gains, a phenomenon that Kahneman and Tversky called "loss aversion."
    - 第四点，也是最重要的一点：损失对人的影响远大于同等规模的收益，卡尼曼和特沃斯基把这种现象称为“损失厌恶”。
  - `G-04b` For instance, studies show that most people will not accept a bet in which there is a 50% chance of winning $100 and a 50% chance of losing $100.
    - 例如，研究表明，大多数人不会接受这样一个赌局：有50%的概率赢100美元，也有50%的概率输100美元。

## 27. `reading_jijing_88_test_98_p3` D-10

- **原句**：When it comes time to recall, Cooke takes a mental walk along his route and translates the images into cards.That's why the MRIs of the memory contestants showed activation in the brain areas associated with visual imagery and spatial navigation.
- **原文修改**：`cards.That's` → `cards. That's`（missing_space_between_sentences）
- **修复后**：
  - `D-10` When it comes time to recall, Cooke takes a mental walk along his route and translates the images into cards.
    - 到了需要回忆的时候，库克会沿着自己的路线在脑中走一遍，把那些画面重新转换成扑克牌。
  - `D-10b` That's why the MRIs of the memory contestants showed activation in the brain areas associated with visual imagery and spatial navigation.
    - 这就是为什么记忆选手的核磁共振扫描显示，与视觉想象和空间导航有关的脑区出现了激活。

## 28. `reading_jijing_91_test_49_p1` F-07

- **原句**："Our data suggest that in an optimal setting we could get 90 percent of the energy value of the gases into our fuel."After the bugs eat the gases, they release ethanol into the surrounding water.
- **原文修改**：`fuel."After ` → `fuel." After `（missing_space_between_sentences）
- **修复后**：
  - `F-07` "Our data suggest that in an optimal setting we could get 90 percent of the energy value of the gases into our fuel."
    - “我们的数据表明，在最理想的条件下，我们能把气体中90%的能量转化到燃料里。”
  - `F-07b` After the bugs eat the gases, they release ethanol into the surrounding water.
    - 细菌吃掉这些气体后，会把乙醇释放到周围的水中。
