# 阅读解析修订记录（2026-10，第三轮）

> 依据：用户 2026-10-19 决定修复乱码（转码丢失的字符）、CO₂ 下标、fagging 错字。
> 原文修改新增 30 条，记在 `data/reading_jijing_text_fixes.json`；带 `questions: true` 的修订同时修改该篇题目数据（题干、答案依据、定位词）里引用的相同文字，`paragraph_label: null` 的修订只出现在题目数据里。
> 控制字符用 JSON 转义写出（如 `\u0000`）。本文件由脚本生成；第一、二轮见 `READING_STUDY_RESPLIT_2026-10.md` 和 `READING_STUDY_RESPLIT_2026-10_ROUND2.md`。

## 一、改动的阅读解析句子

### 1. `reading_jijing_29_test_63_p1` B-03

- **原句**：This releases billions of tonnes of carbon dioxide (CO ) every year, although the changes may actually have started with the dawn of agriculture, 2 say some scientists.
- **原文修改**：`carbon dioxide (CO ) every year` → `carbon dioxide (CO2) every year`（lost_character）；`agriculture, 2 say some scientists` → `agriculture, say some scientists`（lost_character）
- **修改后**：This releases billions of tonnes of carbon dioxide (CO2) every year, although the changes may actually have started with the dawn of agriculture, say some scientists.
  - 这每年释放数十亿吨二氧化碳；不过，一些科学家认为，这种变化实际上可能早在农业诞生时就已开始。

### 2. `reading_jijing_29_test_63_p1` B-05

- **原句**：CO is a greenhouse gas that traps the Sun's radiation within the troposphere, the lower atmosphere.
- **原文修改**：`CO is a greenhouse gas` → `CO2 is a greenhouse gas`（lost_character）
- **修改后**：CO2 is a greenhouse gas that traps the Sun's radiation within the troposphere, the lower atmosphere.
  - 二氧化碳是一种温室气体，会把太阳辐射困在对流层，也就是大气低层。

### 3. `reading_jijing_29_test_63_p1` B-06

- **原句**：2 It has accumulated along with other manmade greenhouse gases, such as methane and chlorofluorocarbons (CFCs).
- **原文修改**：`2 It has accumulated` → `It has accumulated`（lost_character）
- **修改后**：It has accumulated along with other manmade greenhouse gases, such as methane and chlorofluorocarbons (CFCs).
  - 它与甲烷、氯氟烃等其他人造温室气体一道不断累积。

### 4. `reading_jijing_29_test_63_p1` C-01

- **原句**：If current trends continue, we will raise atmospheric CO concentrations to double pre-industrial levels during this century.
- **原文修改**：`atmospheric CO concentrations to double` → `atmospheric CO2 concentrations to double`（lost_character）
- **修改后**：If current trends continue, we will raise atmospheric CO2 concentrations to double pre-industrial levels during this century.
  - 如果当前趋势持续下去，本世纪大气中的二氧化碳浓度将被提高到工业化前水平的两倍。

### 5. `reading_jijing_29_test_63_p1` C-02

- **原句**：That will probably be enough 2 to raise global temperatures by around 2 to 5.
- **原文修改**：`enough 2 to raise global temperatures by around 2 to 5.` → `enough to raise global temperatures by around 2°C to 5°C.`（lost_character）
- **修改后**：That will probably be enough to raise global temperatures by around 2°C to 5°C.
  - 这很可能足以使全球气温上升约2至5摄氏度。

### 6. `reading_jijing_29_test_63_p1` E-01

- **原句**：The global warming would be more pronounced if it were not for sulphur particles and other pollutants that shade us, and because forests and oceans absorb around half of the CO we produce.
- **原文修改**：`half of the CO we produce` → `half of the CO2 we produce`（lost_character）
- **修改后**：The global warming would be more pronounced if it were not for sulphur particles and other pollutants that shade us, and because forests and oceans absorb around half of the CO2 we produce.
  - 如果没有硫颗粒及其他为地球遮挡阳光的污染物，并且如果森林和海洋没有吸收人类排放的约一半二氧化碳，全球变暖会更加明显。

### 7. `reading_jijing_29_test_63_p1` E-02

- **原句**：But the accumulation rate of atmospheric CO has doubled since 2001, suggesting 2 that nature's ability to absorb the gas could now be 2 stretched to the limit.
- **原文修改**：`atmospheric CO has doubled since 2001, suggesting 2 that` → `atmospheric CO2 has doubled since 2001, suggesting that`（lost_character）；`could now be 2 stretched` → `could now be stretched`（lost_character）
- **修改后**：But the accumulation rate of atmospheric CO2 has doubled since 2001, suggesting that nature's ability to absorb the gas could now be stretched to the limit.
  - 但自2001年以来，大气二氧化碳的累积速度已经翻倍，这表明自然吸收这种气体的能力如今可能已接近极限。

### 8. `reading_jijing_29_test_63_p1` E-03

- **原句**：Recent research suggests that natural CO \"sinks\", like peat bogs and forests, are actually starting to release 2 CO . 2
- **原文修改**：`natural CO \"sinks\"` → `natural CO2 \"sinks\"`（lost_character）；`starting to release 2\nCO . 2` → `starting to release CO2.`（lost_character）
- **修改后**：Recent research suggests that natural CO2 "sinks", like peat bogs and forests, are actually starting to release CO2.
  - 近期研究表明，泥炭沼泽和森林等天然二氧化碳“汇”实际上已开始释放二氧化碳。

### 9. `reading_jijing_29_test_63_p1` G-04

- **原句**：The bottom line is that we will need to cut CO emissions by 70% to 80% simply to stabilise atmospheric CO concentrations--and thus 2 temperatures.
- **原文修改**：`cut CO emissions` → `cut CO2 emissions`（lost_character）；`atmospheric CO concentrations--and thus 2 temperatures` → `atmospheric CO2 concentrations--and thus temperatures`（lost_character）
- **修改后**：The bottom line is that we will need to cut CO2 emissions by 70% to 80% simply to stabilise atmospheric CO2 concentrations--and thus temperatures.
  - 归根结底，我们需要把二氧化碳排放削减70%至80%，才能稳定大气二氧化碳浓度，进而稳定气温。

### 10. `reading_jijing_29_test_63_p1` G-05

- **原句**：The quicker we do that, the less unbearably hot our 2 future world will be.
- **原文修改**：`hot our 2 future world` → `hot our future world`（lost_character）
- **修改后**：The quicker we do that, the less unbearably hot our future world will be.
  - 我们越快做到这一点，未来世界令人难以忍受的炎热程度就越低。

### 11. `reading_jijing_29_test_63_p3` A-02

- **原句**：Last month's official revision of China's gross domestic product revealed an economy worth 16 trillion yuan (\u00001.9 trillion) in 2004, 17% more than previously thought.
- **原文修改**：`yuan (\u00001.9 trillion)` → `yuan ($1.9 trillion)`（lost_character）
- **修改后**：Last month's official revision of China's gross domestic product revealed an economy worth 16 trillion yuan ($1.9 trillion) in 2004, 17% more than previously thought.
  - 上月对中国国内生产总值的官方修订显示，2004年中国经济规模为16万亿元人民币（约1.9万亿美元），比此前估计高17%。

### 12. `reading_jijing_29_test_63_p3` A-03

- **原句**：Some\u0000265 billion of the increase - 93% of it - was ascribed to the services sector.
- **原文修改**：`Some\u0000265 billion` → `Some $265 billion`（lost_character）
- **修改后**：Some $265 billion of the increase - 93% of it - was ascribed to the services sector.
  - 新增部分中约2650亿美元——占93%——被归入服务业。

### 13. `reading_jijing_29_test_63_p3` F-02

- **原句**：Chinese families spend more on education than on anything except housing - the market for courses, books and materials more than doubled from 2002 levels, to \u000090 billion in 2005.
- **原文修改**：`to \u000090 billion in 2005` → `to $90 billion in 2005`（lost_character）
- **修改后**：Chinese families spend more on education than on anything except housing - the market for courses, books and materials more than doubled from 2002 levels, to $90 billion in 2005.
  - 中国家庭在教育上的支出仅次于住房——课程、书籍和材料市场比2002年扩大了一倍以上，2005年达到900亿美元。

### 14. `reading_jijing_29_test_63_p3` F-04

- **原句**：The World Travel & Tourism Council predicts that China's annual tourism market will more than triple to \u0000300 billion within a decade.
- **原文修改**：`triple to \u0000300 billion` → `triple to $300 billion`（lost_character）
- **修改后**：The World Travel & Tourism Council predicts that China's annual tourism market will more than triple to $300 billion within a decade.
  - 世界旅行与旅游理事会预测，中国年度旅游市场将在十年内增长到三倍以上，达到3000亿美元。

### 15. `reading_jijing_29_test_63_p3` G-02

- **原句**：In reality, it is bigger still, since the GDP revision cannot capture activities such as kerbside lending and tax-dodging cash transactions in property or entertainment--all of which Dong Tao, chief Asia economist at CSFB, another bank, reckons add another \u0000220 billion to the economy.
- **原文修改**：`another \u0000220 billion` → `another $220 billion`（lost_character）
- **修改后**：In reality, it is bigger still, since the GDP revision cannot capture activities such as kerbside lending and tax-dodging cash transactions in property or entertainment--all of which Dong Tao, chief Asia economist at CSFB, another bank, reckons add another $220 billion to the economy.
  - 实际上，服务业规模还要更大，因为GDP修订无法涵盖路边借贷以及房地产或娱乐业中逃税的现金交易；瑞信第一波士顿的亚洲首席经济学家陶冬估计，这些活动还为经济另外增加了2200亿美元。

### 16. `reading_jijing_83_test_95_p2` D-04

- **原句**：The primary threats to South America's tropical forests are deforestation caused by agricultural expansion, cattle ranching, fagging, oil extraction and spills, mining, illegal coca farming, and colonization initiatives.
- **原文修改**：`cattle ranching, fagging, oil` → `cattle ranching, logging, oil`（typo）
- **修改后**：The primary threats to South America's tropical forests are deforestation caused by agricultural expansion, cattle ranching, logging, oil extraction and spills, mining, illegal coca farming, and colonization initiatives.
  - 南美洲热带森林面临的主要威胁，是由农业扩张、放牧养牛、伐木、石油开采与泄漏、采矿、非法古柯种植以及殖民计划所造成的森林砍伐。

### 17. `reading_jijing_84_test_73_p2` C-17

- **原句**：From age six to 18\u0000British children received, on average, 106 minutes of PE a week.
- **原文修改**：`to 18\u0000British children` → `to 18, British children`（lost_character）
- **修改后**：From age six to 18, British children received, on average, 106 minutes of PE a week.
  - 从6岁到18岁，英国儿童平均每周只能上106分钟的体育课。

## 二、没有阅读解析句子对应的修订

| passage | 段落 | 修改 | 范围 |
|---|---|---|---|
| `reading_jijing_29_test_63_p1` | — | `thus  2 temperatures` → `thus temperatures` | 仅题目数据 |
| `reading_jijing_29_test_63_p1` | — | `atmospheric CO concentrations` → `atmospheric CO2 concentrations` | 仅题目数据 |
| `reading_jijing_29_test_63_p1` | — | `Peat bogs never release CO . 2` → `Peat bogs never release CO2.` | 仅题目数据 |
| `reading_jijing_29_test_63_p1` | — | `natural CO 'sinks'` → `natural CO2 'sinks'` | 仅题目数据 |
| `reading_jijing_29_test_63_p1` | — | `actually starting to release 2` → `actually starting to release CO2.` | 仅题目数据 |
| `reading_jijing_29_test_63_p1` | — | `hot our  2 future` → `hot our future` | 仅题目数据 |
| `reading_jijing_29_test_63_p3` | — | `more than\u0000300 billion` → `more than $300 billion` | 仅题目数据 |
| `reading_jijing_75_test_57_p2` | I | `1989\u0000and 1993 .` → `1989 and 1993.` | 段落和题目数据 |
| `reading_jijing_50_test_30_p2` | — | `rats\u0000learning` → `rats' learning` | 仅题目数据 |
