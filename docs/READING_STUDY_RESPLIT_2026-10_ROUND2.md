# 阅读解析修订记录（2026-10，第二轮）

> 依据：用户 2026-10-19 的三项决定——加入 claim mat 修订；修复并排除段首多余句点；重新拆分 51 个“一条里含多句”的单元。
> 原文修改新增 30 条，记在 `data/reading_jijing_text_fixes.json`，由 `scripts/reading_jijing_text_fixes.py` 和构建脚本应用。
> ID 规则同第一轮：拆出的第一句沿用原 ID，其后依次加 b、c……；同文件的 `sentence_index` 重新连续编号。
> 本文件由脚本生成，供 Codex 和老师核对；第一轮见 `docs/READING_STUDY_RESPLIT_2026-10.md`。

## 一、只改原文、不拆句（段首句点、claim mat、错误句点）

### 1. `reading_jijing_27_test_33_p1` B-09

- **原句**：The video footage has been discredited amid accusations of tampering, whilst others claim mat the image caught by Holmes could be nothing more than a tree trunk or even one of the otters that inhabit the loch.
- **原文修改**：`claim mat the image` → `claim that the image`（typo）
- **修改后**：
  - `B-09` The video footage has been discredited amid accusations of tampering, whilst others claim that the image caught by Holmes could be nothing more than a tree trunk or even one of the otters that inhabit the loch.
    - 在篡改指控之下，这段视频已失去可信度；另一些人则声称，霍姆斯拍到的影像可能只是一根树干，甚至只是栖息在湖中的一只水獭。

### 2. `reading_jijing_29_test_63_p1` C-01

- **原句**：. If current trends continue, we will raise atmospheric CO concentrations to double pre-industrial levels during this century.
- **原文修改**：`. If current trends continue` → `If current trends continue`（stray_leading_period）
- **修改后**：
  - `C-01` If current trends continue, we will raise atmospheric CO concentrations to double pre-industrial levels during this century.
    - 如果当前趋势持续下去，本世纪大气中的二氧化碳浓度将被提高到工业化前水平的两倍。

### 3. `reading_jijing_5_test_59_p1` A-01

- **原句**：In 1894 Dr John Kellogg and his brother. Will, were supervising a hospital and health spa in Michigan.
- **原文修改**：`his brother. Will, were` → `his brother, Will, were`（typo）
- **修改后**：
  - `A-01` In 1894 Dr John Kellogg and his brother, Will, were supervising a hospital and health spa in Michigan.
    - 1894年，约翰·凯洛格博士和他的弟弟威尔当时正在管理密歇根州的一家医院兼健康疗养中心。

### 4. `reading_jijing_65_test_69_p2` H-03

- **原句**：In his recent book Free Flight. James Fallows, a pilot as well as a writer, describes serious attempts by both state and private entrepreneurs in the USA to promote an 'air taxi' system within the price range of today's middle class and perhaps tomorrow's global population.
- **原文修改**：`Free Flight. James Fallows` → `Free Flight, James Fallows`（typo）
- **修改后**：
  - `H-03` In his recent book Free Flight, James Fallows, a pilot as well as a writer, describes serious attempts by both state and private entrepreneurs in the USA to promote an 'air taxi' system within the price range of today's middle class and perhaps tomorrow's global population.
    - 在近作《自由飞行》中，既是飞行员又是作家的詹姆斯·法洛斯描述了美国政府和私营企业家为推广“空中出租车”系统所作的认真尝试；其价格处于当今中产阶级、或许也包括未来全球人口的承受范围之内。

### 5. `reading_jijing_69_test_40_p2` E-04

- **原句**：This adaptation helps the bristlecone photosynthesize during particularly brutal months. Saving the energy of constant needle replacement and providing a stable supply of chlorophyll.
- **原文修改**：`brutal months. Saving the energy` → `brutal months, saving the energy`（typo）
- **修改后**：
  - `E-04` This adaptation helps the bristlecone photosynthesize during particularly brutal months, saving the energy of constant needle replacement and providing a stable supply of chlorophyll.
    - 这种适应有助于狐尾松在尤为严酷的月份进行光合作用，同时节省了不断更换松针所需的能量，并提供了稳定的叶绿素供应。

### 6. `reading_jijing_71_test_1_p2` B-03

- **原句**：In addition, the dubbed voices may seem detached or inappropriate to the characters, or otherwise, the absurdity of having an undereducated American ranffian saying. 'Je voudrais déclarer un vol' becomes too much, affecting appreciation of the film.
- **原文修改**：`American ranffian saying. 'Je voudrais` → `American ruffian saying 'Je voudrais`（typo）
- **修改后**：
  - `B-03` In addition, the dubbed voices may seem detached or inappropriate to the characters, or otherwise, the absurdity of having an undereducated American ruffian saying 'Je voudrais déclarer un vol' becomes too much, affecting appreciation of the film.
    - 此外，配音后的声音可能显得与人物脱节或不相称；又或者，让一个没受过多少教育的美国恶棍说出法语“我要报案说有盗窃”，其荒诞感会过于强烈，从而影响观众欣赏影片。

### 7. `reading_jijing_72_test_15_p2` F-02

- **原句**：They found that children who socially interact with more adults, who have more friends. And who have more older siblings tend to pass TOM tasks at a slightly earlier age than other children.
- **原文修改**：`more friends. And who have` → `more friends, and who have`（typo）
- **修改后**：
  - `F-02` They found that children who socially interact with more adults, who have more friends, and who have more older siblings tend to pass TOM tasks at a slightly earlier age than other children.
    - 他们发现，与更多成年人有社交互动、拥有更多朋友、有更多年长兄姐的儿童，往往能比其他儿童更早一点通过心理理论测试。

### 8. `reading_jijing_73_test_5_p3` D-03

- **原句**：In fact. Hooker knew well enough what might happen.
- **原文修改**：`In fact. Hooker knew` → `In fact, Hooker knew`（typo）
- **修改后**：
  - `D-03` In fact, Hooker knew well enough what might happen.
    - 事实上，胡克很清楚可能会发生什么。

### 9. `reading_jijing_76_test_43_p3` A-07

- **原句**：Differences and similarities between children's compliance with requests and prohibitions ("Do"vs. "Don't" demand contexts) were also explored.
- **原文修改**：`("Do"vs. "Don` → `("Do" vs. "Don`（missing_space）
- **修改后**：
  - `A-07` Differences and similarities between children's compliance with requests and prohibitions ("Do" vs. "Don't" demand contexts) were also explored.
    - 研究还探讨了儿童服从请求与服从禁令（即“做”与“不要做”两类要求情境）之间的差异与相似之处。

### 10. `reading_jijing_78_test_102_p1` A-01

- **原句**：. Despite gun battles in the capital of Chad, rioting in Kenya, and Galloping inflation in Zimbabwe, the economies of sub-Saharan Africa are, as a whole, in better shape than they were a few years ago.
- **原文修改**：`. Despite gun battles` → `Despite gun battles`（stray_leading_period）；`and Galloping inflation` → `and galloping inflation`（typo）
- **修改后**：
  - `A-01` Despite gun battles in the capital of Chad, rioting in Kenya, and galloping inflation in Zimbabwe, the economies of sub-Saharan Africa are, as a whole, in better shape than they were a few years ago.
    - 尽管乍得首都发生枪战、肯尼亚出现骚乱、津巴布韦通货膨胀迅猛，但撒哈拉以南非洲的经济总体上比几年前状况更好。

### 11. `reading_jijing_78_test_102_p1` C-01

- **原句**：. the prerequisites to prevent the next crash are not in place, according to a World Bank study issued in January, Is Africa's Recent Growth Robust?
- **原文修改**：`. the prerequisites to prevent` → `The prerequisites to prevent`（stray_leading_period）
- **修改后**：
  - `C-01` The prerequisites to prevent the next crash are not in place, according to a World Bank study issued in January, Is Africa's Recent Growth Robust?
    - 世界银行一月份发布的研究《非洲近期的增长稳健吗？》指出，防止下一次崩溃的必要条件尚未具备。

### 12. `reading_jijing_78_test_102_p1` D-01

- **原句**：. Perhaps the most incisive analysis of the volatility question comes from Paul Collier, a longtime specialist in African economics at the University of Oxford and author of the recent book The Bottom Billion.
- **原文修改**：`. Perhaps the most incisive` → `Perhaps the most incisive`（stray_leading_period）
- **修改后**：
  - `D-01` Perhaps the most incisive analysis of the volatility question comes from Paul Collier, a longtime specialist in African economics at the University of Oxford and author of the recent book The Bottom Billion.
    - 对于经济波动问题，最为深刻的分析或许来自保罗·科利尔；他长期研究非洲经济，任职于牛津大学，也是新近出版的《最底层的十亿人》一书作者。

### 13. `reading_jijing_78_test_102_p1` G-01

- **原句**：. To encourage reform, Collier recommends that the G8 nations agree to accept these measures as voluntary guidelines for multinationals doing business in Africa- companies, for instance, would only enter new contracts through auctions monitored by an international verification group.
- **原文修改**：`. To encourage reform` → `To encourage reform`（stray_leading_period）
- **修改后**：
  - `G-01` To encourage reform, Collier recommends that the G8 nations agree to accept these measures as voluntary guidelines for multinationals doing business in Africa- companies, for instance, would only enter new contracts through auctions monitored by an international verification group.
    - 为了推动改革，科利尔建议八国集团同意将这些措施作为在非洲经营的跨国公司的自愿准则；例如，企业只能通过由国际核查小组监督的拍卖来签订新合同。

### 14. `reading_jijing_78_test_102_p1` H-01

- **原句**：. These measures, he says, are more important than elevating aid levels, an approach emphasized by economist Jeffrey D. Sachs of Columbia University and celebrity activists such as Bono.
- **原文修改**：`. These measures, he says` → `These measures, he says`（stray_leading_period）
- **修改后**：
  - `H-01` These measures, he says, are more important than elevating aid levels, an approach emphasized by economist Jeffrey D. Sachs of Columbia University and celebrity activists such as Bono.
    - 他说，这些措施比提高援助水平更重要；提高援助正是哥伦比亚大学经济学家杰弗里·D·萨克斯以及波诺等明星活动人士所强调的方法。

### 15. `reading_jijing_92_test_58_p2` A-01

- **原句**：. As in New Delhi and Phoenix, policymakers worldwide wield great power over how water resources and managed.
- **原文修改**：`. As in New Delhi` → `As in New Delhi`（stray_leading_period）；`how water resources and managed` → `how water resources are managed`（typo）
- **修改后**：
  - `A-01` As in New Delhi and Phoenix, policymakers worldwide wield great power over how water resources are managed.
    - 与新德里和菲尼克斯的情况一样，世界各地的政策制定者对水资源如何管理拥有巨大的权力。

### 16. `reading_jijing_92_test_58_p2` B-01

- **原句**：. That the problem is well-known makes it no less disturbing: today one out of six people, more than a billion, suffer inadequate access to safe freshwater.
- **原文修改**：`. That the problem is well-known` → `That the problem is well-known`（stray_leading_period）
- **修改后**：
  - `B-01` That the problem is well-known makes it no less disturbing: today one out of six people, more than a billion, suffer inadequate access to safe freshwater.
    - 这个问题广为人知，却丝毫没有减轻其令人不安的程度：如今每六人中就有一人，也就是十亿多人，无法充分获得安全淡水。

### 17. `reading_jijing_92_test_58_p2` C-01

- **原句**：. Scientists expect water scarcity to become more common in large part because the world's population is rising and many people are getting richer (thus expanding demand) and because global climate change is exacerbating aridity and reducing supply in many regions.
- **原文修改**：`. Scientists expect water scarcity` → `Scientists expect water scarcity`（stray_leading_period）
- **修改后**：
  - `C-01` Scientists expect water scarcity to become more common in large part because the world's population is rising and many people are getting richer (thus expanding demand) and because global climate change is exacerbating aridity and reducing supply in many regions.
    - 科学家预计水资源短缺会越来越普遍，这在很大程度上是因为世界人口不断增长、许多人日益富裕（因而扩大了需求），也因为全球气候变化正在加剧干旱并减少许多地区的供应。

### 18. `reading_jijing_92_test_58_p2` D-01

- **原句**：. Because lack of access to water can lead to starvation, disease, political instability, and even armed conflict, failure to take action can have broad and grave consequences.
- **原文修改**：`. Because lack of access` → `Because lack of access`（stray_leading_period）
- **修改后**：
  - `D-01` Because lack of access to water can lead to starvation, disease, political instability, and even armed conflict, failure to take action can have broad and grave consequences.
    - 由于无法获得水可能导致饥饿、疾病、政治动荡甚至武装冲突，不采取行动会造成广泛而严重的后果。

### 19. `reading_jijing_92_test_58_p2` E-01

- **原句**：. The world's water problems require, as a start, an understanding of how much freshwater each person requires, along with knowledge of the factors that impede supply and increase demand in different parts of the world.
- **原文修改**：`. The world's water problems` → `The world's water problems`（stray_leading_period）
- **修改后**：
  - `E-01` The world's water problems require, as a start, an understanding of how much freshwater each person requires, along with knowledge of the factors that impede supply and increase demand in different parts of the world.
    - 要解决世界水资源问题，首先必须了解每个人需要多少淡水，同时还要知道世界不同地区有哪些因素会阻碍供应并增加需求。

### 20. `reading_jijing_92_test_58_p2` F-01

- **原句**：. Much of the Americas and northern Eurasia enjoy abundant water supplies.
- **原文修改**：`. Much of the Americas` → `Much of the Americas`（stray_leading_period）
- **修改后**：
  - `F-01` Much of the Americas and northern Eurasia enjoy abundant water supplies.
    - 美洲大部分地区和欧亚大陆北部拥有丰富的水资源。

### 21. `reading_jijing_92_test_58_p2` H-01

- **原句**：. Lots of water, but not always where it is needed one hundred and ten thousand cubic kilometers of precipitation, nearly 10 times the volume of Lake Superior, falls from the sky onto the earth's land surface every year.
- **原文修改**：`. Lots of water, but not always` → `Lots of water, but not always`（stray_leading_period）
- **修改后**：
  - `H-01` Lots of water, but not always where it is needed one hundred and ten thousand cubic kilometers of precipitation, nearly 10 times the volume of Lake Superior, falls from the sky onto the earth's land surface every year.
    - 水量很多，却并不总出现在需要它的地方：每年有十一万立方千米的降水从天空落到地球陆地表面，接近苏必利尔湖水量的10倍。

### 22. `reading_jijing_92_test_58_p2` I-01

- **原句**：. Waters run away in tremendous wildfires in recent years.
- **原文修改**：`. Waters run away` → `Waters run away`（stray_leading_period）
- **修改后**：
  - `I-01` Waters run away in tremendous wildfires in recent years.
    - 近年来，巨大的野火使水资源流失。

### 23. `reading_jijing_9_test_81_p2` A-02

- **原句**：In addition to providing the traditional resort-leisure product, it has been argued that ecotourism resort management should have a particular focus on best-practice environmental management. an educational and interpretive component, and direct anil indirect contributions to the conservation of the natural and cultural environment (Ayala. I996).
- **原文修改**：`environmental management. an educational` → `environmental management, an educational`（typo）；`direct anil indirect` → `direct and indirect`（typo）；`(Ayala. I996)` → `(Ayala, 1996)`（typo）
- **修改后**：
  - `A-02` In addition to providing the traditional resort-leisure product, it has been argued that ecotourism resort management should have a particular focus on best-practice environmental management, an educational and interpretive component, and direct and indirect contributions to the conservation of the natural and cultural environment (Ayala, 1996).
    - 有观点认为，生态旅游度假村的管理除了提供传统的度假休闲产品外，还应特别注重最佳环境管理实践、教育与讲解功能，以及对自然和文化环境保护的直接与间接贡献（Ayala，1996）。

### 24. `reading_jijing_9_test_81_p2` B-01

- **原句**：Conran Cove Island Resort is a large integrated ecotourism-based resort located south of Brisbane on the Gold Coast, Queensland. Australia.
- **原文修改**：`Queensland. Australia.` → `Queensland, Australia.`（typo）
- **修改后**：
  - `B-01` Conran Cove Island Resort is a large integrated ecotourism-based resort located south of Brisbane on the Gold Coast, Queensland, Australia.
    - 科兰湾岛度假村（Conran Cove Island Resort）是一家大型综合性生态旅游度假村，坐落于布里斯班以南的黄金海岸，属于澳大利亚昆士兰州。


## 二、重新拆句

### 25. `ielts18_test4_p2` F-03

- **原句**：She has also expressed concerns that her theories are being misappropriated in schools by being conflated with the self-esteem movement: 'For me the growth mindset is a tool for learning and improvement. It's not just a vehicle for making children feel good.'
- **修改后**：
  - `F-03` She has also expressed concerns that her theories are being misappropriated in schools by being conflated with the self-esteem movement: 'For me the growth mindset is a tool for learning and improvement.
    - 她还担心，自己的理论在学校里被与自尊运动混为一谈，因而遭到误用：“对我来说，成长型思维是学习和进步的工具。
  - `F-03b` It's not just a vehicle for making children feel good.'
    - 它并不只是让孩子自我感觉良好的手段。”

### 26. `ielts19_test4_p3` H-02

- **原句**：These were the traits that were prevalent in human life for tens of thousands of years. So presumably these traits are still strong in us now.
- **修改后**：
  - `H-02` These were the traits that were prevalent in human life for tens of thousands of years.
    - 这些特征在人类生活中盛行了数万年。
  - `H-02b` So presumably these traits are still strong in us now.
    - 所以，这些特征想必如今在我们身上仍然很强。

### 27. `ielts20_test2_p3` I-51

- **原句**：He later told me, "This is part of a movement to use algorithms to take the hard choices of living out of life." Perhaps he's right.
- **修改后**：
  - `I-51` He later told me, "This is part of a movement to use algorithms to take the hard choices of living out of life."
    - 后来他告诉我：“这是一场运动的一部分，这场运动要用算法把生活中的艰难抉择拿走。”
  - `I-51b` Perhaps he's right.
    - 也许他说得对。

### 28. `ielts20_test4_p2` B-11

- **原句**：She knows that they’re essential and that the job is far from over. ‘We know that in 20, 30, 40 years, we'll need to go back in there and adjust to the changing environment,’ she says.
- **修改后**：
  - `B-11` She knows that they’re essential and that the job is far from over.
    - 她知道这些策略不可或缺，也知道这项工作远未结束。
  - `B-11b` ‘We know that in 20, 30, 40 years, we'll need to go back in there and adjust to the changing environment,’ she says.
    - “我们知道，20年、30年或40年后，我们还得回到那里，适应不断变化的环境。”她说。

### 29. `ielts20_test4_p2` C-16

- **原句**：The programme has seen moderate success, mainly in areas with less subsidence. ‘Unfortunately, traditional infrastructure is often single-solution focused,’ says Tol. ‘For long-term success, it’s critical that we transition towards multifunctional approaches that embed natural processes and that engage and benefit communities and local decision-makers.’
- **修改后**：
  - `C-16` The programme has seen moderate success, mainly in areas with less subsidence.
    - 该项目取得了一定的成功，主要是在地面沉降较少的地区。
  - `C-16b` ‘Unfortunately, traditional infrastructure is often single-solution focused,’ says Tol.
    - “遗憾的是，传统基础设施往往只着眼于单一解决方案。”Tol说。
  - `C-16c` ‘For long-term success, it’s critical that we transition towards multifunctional approaches that embed natural processes and that engage and benefit communities and local decision-makers.’
    - “要想取得长期成功，关键是转向多功能的方法：这些方法要融入自然过程，也要让社区和地方决策者参与进来并从中受益。”

### 30. `ielts20_test4_p2` D-19

- **原句**：The modifications were made by the Buoyant Foundation Project, a not-for-profit organisation that has been researching and retrofitting amphibious houses since 2006. ‘When I started this,’ explains founder Elizabeth English, ‘climate change was not on the tip of everybody’s tongue, but this technology is becoming necessary in places that didn’t previously need it.’ It’s much cheaper than permanently elevating houses, English explains – about a third of what it would cost to completely replace a building’s foundations.
- **修改后**：
  - `D-19` The modifications were made by the Buoyant Foundation Project, a not-for-profit organisation that has been researching and retrofitting amphibious houses since 2006.
    - 这些改造由非营利组织Buoyant Foundation Project完成，该组织自2006年以来一直在研究并改造两栖房屋。
  - `D-19b` ‘When I started this,’ explains founder Elizabeth English, ‘climate change was not on the tip of everybody’s tongue, but this technology is becoming necessary in places that didn’t previously need it.’
    - “我刚开始做这件事的时候，”创始人Elizabeth English解释说，“气候变化还不是人人挂在嘴边的话题，但如今这项技术在一些以前不需要它的地方也变得必不可少。”
  - `D-19c` It’s much cheaper than permanently elevating houses, English explains – about a third of what it would cost to completely replace a building’s foundations.
    - English解释说，这比永久抬高房屋便宜得多——大约只需彻底更换建筑地基费用的三分之一。

### 31. `ielts20_test4_p2` E-23

- **原句**：Most of the country is less than a metre above sea level and 80 per cent of its land lies on floodplains. ‘Almost 35 million people living on the coastal belt of Bangladesh are currently affected by soil and water salinity,’ says Raisa Chowdhury of the international development organisation ICCO Cooperation.
- **修改后**：
  - `E-23` Most of the country is less than a metre above sea level and 80 per cent of its land lies on floodplains.
    - 该国大部分地区海拔不到一米，80%的土地位于洪泛平原上。
  - `E-23b` ‘Almost 35 million people living on the coastal belt of Bangladesh are currently affected by soil and water salinity,’ says Raisa Chowdhury of the international development organisation ICCO Cooperation.
    - “孟加拉国沿海地带近3500万人目前正受到土壤和水体盐碱化的影响。”国际发展组织ICCO Cooperation的Raisa Chowdhury说。

### 32. `ielts4_test1_p3` I-31

- **原句**：For example, we asked: What goes with soft? A circle or a square? Which shape goes with hard?
- **修改后**：
  - `I-31` For example, we asked: What goes with soft?
    - 例如，我们问道：什么和 soft（柔软）相配？
  - `I-31b` A circle or a square?
    - 圆形还是方形？
  - `I-31c` Which shape goes with hard?
    - 哪种形状和 hard（坚硬）相配？

### 33. `ielts4_test2_p1` E-27

- **原句**："They cannot refuse to speak English if most commercial activity is in English." But are languages worth saving?
- **修改后**：
  - `E-27` "They cannot refuse to speak English if most commercial activity is in English."
    - “如果大多数商业活动都使用英语，他们就不能拒绝说英语。”
  - `E-27b` But are languages worth saving?
    - 但语言值得拯救吗？

### 34. `ielts4_test2_p2` B-06

- **原句**："We've had a tradition of doctors being fairly powerful and I guess they are pretty loath to allow any pretenders to their position to come into it." In many other industrialized countries, orthodox and alternative medicines have worked "hand in glove" for years.
- **修改后**：
  - `B-06` "We've had a tradition of doctors being fairly powerful and I guess they are pretty loath to allow any pretenders to their position to come into it."
    - “我们一直有医生相当有权势的传统，我想他们很不愿意让任何觊觎其地位的人进入这一领域。”
  - `B-06b` In many other industrialized countries, orthodox and alternative medicines have worked "hand in glove" for years.
    - 在许多其他工业化国家，正统医学和替代医学多年来一直密切合作。

### 35. `ielts4_test2_p3` A-07

- **原句**：Playful young animals use around two or three per cent of their energy cavorting, and in children that figure can be closer to fifteen per cent. "Even two or three per cent is huge," says John Byers of Idaho University. "You just don't find animals wasting energy like that," he adds.
- **修改后**：
  - `A-07` Playful young animals use around two or three per cent of their energy cavorting, and in children that figure can be closer to fifteen per cent.
    - 活泼的幼兽会把大约百分之二到三的能量用于嬉戏，而儿童的这一比例可接近百分之十五。
  - `A-07b` "Even two or three per cent is huge," says John Byers of Idaho University.
    - “即便是百分之二到三也已经很多了，”爱达荷大学的约翰·拜尔斯说。
  - `A-07c` "You just don't find animals wasting energy like that," he adds.
    - “你根本看不到动物那样浪费能量，”他补充说。

### 36. `ielts4_test2_p3` C-19

- **原句**：But Byers points out that the benefits of increased exercise disappear rapidly after training stops, so any improvement in endurance resulting from juvenile play would be lost by adulthood. "If the function of play was to get into shape," says Byers, "the optimum time for playing would depend on when it was most advantageous for the young of a particular species to do so.
- **修改后**：
  - `C-19` But Byers points out that the benefits of increased exercise disappear rapidly after training stops, so any improvement in endurance resulting from juvenile play would be lost by adulthood.
    - 但拜尔斯指出，训练一停止，加强锻炼带来的好处就会迅速消失，因此幼年玩耍带来的任何耐力提升到成年时都会丧失。
  - `C-19b` "If the function of play was to get into shape," says Byers, "the optimum time for playing would depend on when it was most advantageous for the young of a particular species to do so.
    - 拜尔斯说：“如果玩耍的功能是让身体强健，那么最佳的玩耍时间就应取决于某个物种的幼崽何时最适合这样做。

### 37. `ielts4_test2_p3` C-20

- **原句**：But it doesn't work like that." Across species, play tends to peak about halfway through the suckling stage and then decline.
- **修改后**：
  - `C-20` But it doesn't work like that."
    - 但事实并非如此。”
  - `C-20b` Across species, play tends to peak about halfway through the suckling stage and then decline.
    - 就各个物种而言，玩耍往往在哺乳期进行到一半左右时达到高峰，然后减少。

### 38. `ielts4_test2_p3` E-29

- **原句**：Robert Barton of Durham University believes that, because large brains are more sensitive to developmental stimuli than smaller brains, they require more play to help mould them for adulthood. “I concluded it's to do with learning, and with the importance of environmental data to the brain during development,” he says.
- **修改后**：
  - `E-29` Robert Barton of Durham University believes that, because large brains are more sensitive to developmental stimuli than smaller brains, they require more play to help mould them for adulthood.
    - 达勒姆大学的罗伯特·巴顿认为，由于较大的大脑比较小的大脑对发育期刺激更敏感，所以需要更多玩耍来帮助它们为成年阶段塑形。
  - `E-29b` “I concluded it's to do with learning, and with the importance of environmental data to the brain during development,” he says.
    - 他说：“我的结论是，这和学习有关，也和发育期间环境信息对大脑的重要性有关。”

### 39. `ielts4_test2_p3` G-37

- **原句**：Bekoff likens it to a behavioural kaleidoscope, with animals at play jumping rapidly between activities. "They use behaviour from a lot of different contexts - predation, aggression, reproduction," he says. "Their developing brain is getting all sorts of stimulation.
- **修改后**：
  - `G-37` Bekoff likens it to a behavioural kaleidoscope, with animals at play jumping rapidly between activities.
    - 贝科夫把它比作行为的万花筒：玩耍中的动物会在不同活动之间快速切换。
  - `G-37b` "They use behaviour from a lot of different contexts - predation, aggression, reproduction," he says.
    - “它们使用来自许多不同情境的行为——捕食、攻击、繁殖，”他说。
  - `G-37c` "Their developing brain is getting all sorts of stimulation.
    - “它们正在发育的大脑得到了各种各样的刺激。

### 40. `ielts4_test2_p3` H-38

- **原句**：Not only is more of the brain involved in play than was suspected, but it also seems to activate higher cognitive processes. "There's enormous cognitive involvement in play", says Bekoff.
- **修改后**：
  - `H-38` Not only is more of the brain involved in play than was suspected, but it also seems to activate higher cognitive processes.
    - 参与玩耍的大脑区域不仅比原先猜想的更多，而且玩耍似乎还会激活更高层次的认知过程。
  - `H-38b` "There's enormous cognitive involvement in play", says Bekoff.
    - “玩耍中有大量的认知参与，”贝科夫说。

### 41. `ielts4_test2_p3` H-43

- **原句**：He was surprised by the extent of the activation. "Play just lights everything up," he says.
- **修改后**：
  - `H-43` He was surprised by the extent of the activation.
    - 激活的程度令他吃惊。
  - `H-43b` "Play just lights everything up," he says.
    - “玩耍简直把一切都点亮了，”他说。

### 42. `ielts4_test4_p1` C-14

- **原句**：But with the right training we can go much further with that one third than we've been going." Yessis believes that U.S.
- **修改后**：
  - `C-14` But with the right training we can go much further with that one third than we've been going."
    - 但只要训练得当，我们就能让这三分之一发挥得比以往好得多。”

### 43. `ielts4_test4_p1` C-15

- **原句**：runners, despite their impressive achievements, are "running on their genetics".
- **修改后**：
  - `C-15` Yessis believes that U.S. runners, despite their impressive achievements, are "running on their genetics".
    - 耶西斯认为，美国跑步运动员尽管成绩斐然，却仍是在“靠基因跑步”。

### 44. `ielts4_test4_p1` I-45

- **原句**：We've got a long way to go." For the foreseeable future, records will be made to be broken.
- **修改后**：
  - `I-45` We've got a long way to go."
    - 我们还有很长的路要走。”
  - `I-45b` For the foreseeable future, records will be made to be broken.
    - 在可预见的未来，纪录仍会不断被打破。

### 45. `ielts5_test2_p2` A-02

- **原句**：The left.' No, not funny.
- **修改后**：
  - `A-02` The left.'
    - 左边。”
  - `A-02b` No, not funny.
    - 不，不好笑。

### 46. `ielts5_test2_p2` A-05

- **原句**：The outside.' Hah!
- **修改后**：
  - `A-05` The outside.'
    - 外边。”
  - `A-05b` Hah!
    - 哈！

### 47. `ielts5_test4_p2` J-45

- **原句**：'It was a very expensive and time-consuming process that took around six months to complete.' Though the project cost A$1.6 million (nearly £700,000), the alternative - re-cladding the entire building - would have cost ten times as much.
- **修改后**：
  - `J-45` 'It was a very expensive and time-consuming process that took around six months to complete.'
    - “这是一个非常昂贵又耗时的过程，花了大约六个月才完成。”
  - `J-45b` Though the project cost A$1.6 million (nearly £700,000), the alternative - re-cladding the entire building - would have cost ten times as much.
    - 虽然该项目花费了160万澳元（近70万英镑），但另一种方案——给整栋楼重新装外墙——的花费会是它的十倍。

### 48. `ielts6_test2_p1` A-01

- **原句**：In fact, Newman believes the main reason for adopting one sort of transport over another is politics: 'The more democratic the process, the more public transport is favored.' He considers Portland, Oregon, a perfect example of this.
- **修改后**：
  - `A-01` In fact, Newman believes the main reason for adopting one sort of transport over another is politics: 'The more democratic the process, the more public transport is favored.'
    - 事实上，纽曼认为，选择某种交通方式而非另一种的主要原因是政治：“决策过程越民主，公共交通就越受青睐。”
  - `A-01b` He considers Portland, Oregon, a perfect example of this.
    - 他认为俄勒冈州的波特兰就是一个完美的例子。

### 49. `ielts7_test1_p3` C-11

- **原句**：In suggestopedia, as he called his method, consciousness is shifted away from the curriculum to focus on something peripheral. The curriculum then becomes peripheral and is dealt with by the reserve capacity of the brain.
- **修改后**：
  - `C-11` In suggestopedia, as he called his method, consciousness is shifted away from the curriculum to focus on something peripheral.
    - 在他称之为“暗示教学法”的方法中，意识从课程内容上被转移开，去关注一些外围的事物。
  - `C-11b` The curriculum then becomes peripheral and is dealt with by the reserve capacity of the brain.
    - 于是，课程内容反而变成了外围的东西，由大脑的储备能力来处理。

### 50. `ielts7_test2_p1` I-44

- **原句**：'With the eaves extending out on all sides like balancing poles,' says Mr Ishida, 'the building responds to even the most powerful jolt of an earthquake with a graceful swaying, never an abrupt shaking.' Here again, Japanese master builders of a thousand years ago anticipated concepts of modern structural engineering.
- **修改后**：
  - `I-44` 'With the eaves extending out on all sides like balancing poles,' says Mr Ishida, 'the building responds to even the most powerful jolt of an earthquake with a graceful swaying, never an abrupt shaking.'
    - “屋檐向四面伸出，就像平衡杆一样，”石田先生说，“即使面对最猛烈的地震冲击，建筑也只会优雅地摇摆，而绝不会突然剧烈晃动。”
  - `I-44b` Here again, Japanese master builders of a thousand years ago anticipated concepts of modern structural engineering.
    - 在这一点上，一千年前的日本建筑大师又一次预见了现代结构工程的理念。

### 51. `ielts7_test3_p1` D-03

- **原句**：The ants therefore cultivate these fungi in their nests, bringing them leaves to feed on, and then use them as a source of food. Farmer ants secrete antibiotics to control other fungi that might act as 'weeds', and spread waste to fertilise the crop.
- **修改后**：
  - `D-03` The ants therefore cultivate these fungi in their nests, bringing them leaves to feed on, and then use them as a source of food.
    - 因此，蚂蚁在巢穴中培育这些真菌，给它们带来叶子作为养料，然后把真菌当作食物来源。
  - `D-03b` Farmer ants secrete antibiotics to control other fungi that might act as 'weeds', and spread waste to fertilise the crop.
    - 农蚁分泌抗生素来控制其他可能充当“杂草”的真菌，并散布废物为作物施肥。

### 52. `ielts8_test3_p1` I-03

- **原句**：Diels also hopes to see the birth of 'interactive meteorology' - not just forecasting the weather but controlling it. 'If we could discharge clouds, we might affect the weather,' he says.
- **修改后**：
  - `I-03` Diels also hopes to see the birth of 'interactive meteorology' - not just forecasting the weather but controlling it.
    - 迪尔斯还希望看到“互动气象学”的诞生——不仅预报天气，还能控制天气。
  - `I-03b` 'If we could discharge clouds, we might affect the weather,' he says.
    - 他说：“如果我们能让云层放电，也许就能影响天气。”

### 53. `ielts8_test3_p3` A-03

- **原句**：'Nothing lives forever!' However, in this statement we think of artificially produced, technical objects, products which are subjected to natural wear and tear during use.
- **修改后**：
  - `A-03` 'Nothing lives forever!'
    - “没有什么能永远存在！”
  - `A-03b` However, in this statement we think of artificially produced, technical objects, products which are subjected to natural wear and tear during use.
    - 不过，说这句话时，我们想到的是人工制造的技术物品，也就是那些在使用中会自然磨损的产品。

### 54. `reading_jijing_16_test_97_p2` G-44

- **原句**：That is, they discount future time investments relatively steeply." Why do we perceive a greater "surplus" of time in the future than in the present?
- **修改后**：
  - `G-44` That is, they discount future time investments relatively steeply."
    - 也就是说，他们会大幅低估未来时间投入的分量。”
  - `G-44b` Why do we perceive a greater "surplus" of time in the future than in the present?
    - 为什么我们觉得未来比现在拥有更多的“剩余”时间？

### 55. `reading_jijing_22_test_90_p2` G-24

- **原句**：It's just not cut-and-dried." The findings could be of help in slowing down the ongoing increase in childhood obesity, but for the time being, parents should be observant of their children's wake-sleep cycles, and take steps to ensure they are getting enough sleep, the researchers advised.
- **修改后**：
  - `G-24` It's just not cut-and-dried."
    - 这件事并不是那么一清二楚。”
  - `G-24b` The findings could be of help in slowing down the ongoing increase in childhood obesity, but for the time being, parents should be observant of their children's wake-sleep cycles, and take steps to ensure they are getting enough sleep, the researchers advised.
    - 研究人员建议，这些发现可能有助于减缓儿童肥胖率的持续上升；但就目前而言，父母应留意孩子的睡眠—觉醒周期，并采取措施确保他们睡眠充足。

### 56. `reading_jijing_26_test_72_p1` G-11

- **原句**："One thing we can be sure of is that black Sigatoka won't lose in this battle." Poor farmers, who cannot afford chemicals, have it even worse.
- **修改后**：
  - `G-11` "One thing we can be sure of is that black Sigatoka won't lose in this battle."
    - “有一点我们可以肯定：黑叶斑病不会在这场较量中败下阵来。”
  - `G-11b` Poor farmers, who cannot afford chemicals, have it even worse.
    - 而那些买不起化学药剂的贫困农民，处境就更糟了。

### 57. `reading_jijing_38_test_22_p3` G-07

- **原句**：A paper in a 2006 issue of Strategy & Leadership commented that"research is not designed with managers' needs in mind, nor is it communicated in the journals they read. For the most part, it has become a self-referential closed system irrelevant to corporate performance."
- **原文修改**：`commented that"research` → `commented that "research`（missing_space）
- **修改后**：
  - `G-07` A paper in a 2006 issue of Strategy & Leadership commented that "research is not designed with managers' needs in mind, nor is it communicated in the journals they read.
    - 《Strategy & Leadership》2006年某期的一篇论文评论道：“研究在设计时并未考虑管理者的需求，也没有通过他们阅读的期刊传播。
  - `G-07b` For the most part, it has become a self-referential closed system irrelevant to corporate performance."
    - 总体而言，它已成为一个自我指涉的封闭体系，与企业绩效毫不相干。”

### 58. `reading_jijing_73_test_5_p1` H-02

- **原句**：But then his eyes lit up at the challenge.' Perhaps you could store the summer's heat in water somehow.
- **原文修改**：`challenge.' Perhaps you could store the summer's heat in water somehow.` → `challenge. 'Perhaps you could store the summer's heat in water somehow.'`（typo）
- **修改后**：
  - `H-02` But then his eyes lit up at the challenge.
    - 但随后，面对这个挑战，他的眼睛亮了起来。
  - `H-02b` 'Perhaps you could store the summer's heat in water somehow.'
    - “也许可以想办法把夏天的热量储存在水里。”

### 59. `reading_jijing_83_test_95_p1` C-03

- **原句**：Scrub jays know that other jays are thieves and that stashed food can spoil; sheep can recognize faces; chimpanzees use a variety of tools to probe termite mounds and even use weapons to hunt small mammals; dolphins can imitate human postures; the archerfish, which stuns insects with a sudden blast of water, can learn how to aim its squirt simply by watching an experienced fish perform the task. And Alex the parrot turned out to be a surprisingly good talker.
- **修改后**：
  - `C-03` Scrub jays know that other jays are thieves and that stashed food can spoil; sheep can recognize faces; chimpanzees use a variety of tools to probe termite mounds and even use weapons to hunt small mammals; dolphins can imitate human postures; the archerfish, which stuns insects with a sudden blast of water, can learn how to aim its squirt simply by watching an experienced fish perform the task.
    - 灌丛松鸦知道其他松鸦会偷东西，也知道藏起来的食物会变质；绵羊能够识别面孔；黑猩猩会使用多种工具探查白蚁丘，甚至会使用武器猎捕小型哺乳动物；海豚能模仿人类的姿势；射水鱼会突然喷出水柱击晕昆虫，它只要观察一条有经验的鱼完成任务，就能学会如何瞄准喷水。
  - `C-03b` And Alex the parrot turned out to be a surprisingly good talker.
    - 至于鹦鹉亚历克斯，结果它出人意料地很会“说话”。

## 三、规则误报，未改数据

- 列表编号：`reading_jijing_32_test_20_p2` B-01、C-01、D-01、E-01（`1. Valid assessment …`）。
- 引语问句后接说话人：`ielts4_test4_p1` B-10（`…?" Dapena asks.`）、`reading_jijing_83_test_95_p1` G-08（`"What's different?" Pepperberg asked.`）。
- 缩写：`reading_jijing_48_test_21_p3` G-02（`Mt. Cook`）。
- 以上由 `scripts/grammar_items/checks.py` 的 multi_sentence_unit 规则修正，不再命中。

## 四、保留为一条、继续排除出题

- `reading_jijing_9_test_81_p1` F-02：`Test subject was given an argument "All animals with furs hibernate. Rabbit has fur. Therefore, rabbit hibernate".` 三句三段论作为同位语嵌在一个句子里，拆开会破坏句子结构，因此保留；multi_sentence_unit 预期值为 1。
