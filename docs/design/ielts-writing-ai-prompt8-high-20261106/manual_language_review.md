# .8 / high 本轮语言反馈人工复核

本次只读取脱敏 `shared-evidence/run_data.json`、`shared-evidence/raw_calls.jsonl`，并对照旧 `ielts-writing-ai-thinking-ab-20261104/manual_language_review.md`。源码 `cefd300c`，提示词 `iwa-2026-11-04.8`。没有读取 Key、私有思考正文或学生材料，没有新模型调用，也没有改业务代码。

7 篇合成作文中 6 篇成功、1 篇失败；共享证据记录 9 次请求。成功结果共 10 条 LR/GRA 问题建议，逐条核完：弱作文 8 条是针对真实语言问题的纠错，Task 1 两条是可用的表达精确化，但语法错误的定性过重。没有在这 10 条中发现新增无来源事实；其中一条把现实可能条件改成了假设条件，需要保留作者语气。

成功结果只是本机验证中可供渲染的 payload，本轮未发布给学生。97 词作文两次整体 JSON 都不合格，最终 `failed / invalid_output`、没有 result；其原始语言意见单列，不能混算为成功反馈。

## 本轮仍需处理的教学风险

1. **Task 1 的“主语偷换/分词悬垂”标签过重。** `Country B` 改为 `the figure for Country B` 能提高精确度，但两个并列分句允许有不同主语。`overtaking Country A` 可理解为省略“该国比例”的比较，不宜直接定为悬垂分词。成功结果的 `priorities[0]` 却写“修正分词悬垂和主语偷换”，这是本批明确保留的 P2 教学反馈风险。应说明“明确指标与比较对象”，不要向学生教成并列分句必须同主语；本审阅不据此倒推应增减几分。

2. **弱作文的局部修正不等于完整句子已修好。** `the city is grow → the city is growing` 是对的，但套回 `Because the city is grow and more people buy car every year.` 后仍是独立 Because 从句。模型已在总结/优先事项提醒残句，并在 CC 修了另一处 Because，不能说完全漏检；这条建议仍应补成完整可用句。

3. **可选句式/词汇升级要标清。** mid 的倒装/分词练习、strong 的长句清晰度提示，以及 Task 1 的同义变化可以是练习方向，不能仅凭句式常见或词汇简单认定有错误。失败篇原始输出仍有“old people 不够得体”“public transport 重复要换词”等过严倾向，但这些没有进入成功结果。

## 七篇覆盖范围

| 样本 | 词数 | 最终状态 | LR/GRA 问题数 | 模型 LR/GRA（仅记录，不背书） |
|---|---:|---|---|---|
| t2-weak | 270 | ready | 4 / 4 | 5.0 / 5.0 |
| t2-mid | 251 | ready | 0 / 0 | 7.0 / 7.0 |
| t2-good | 277 | ready | 0 / 0 | 8.0 / 8.0 |
| t2-strong | 298 | ready | 0 / 0 | 8.0 / 8.0 |
| t2-off-topic | 254 | ready | 0 / 0 | 7.0 / 7.0 |
| t2-under-length | 97 | failed | — / — | 无成功结果 / 无成功结果 |
| t1-no-image | 172 | ready | 0 / 2 | 7.0 / 7.0 |

mid、good、strong、off-topic 的 LR/GRA `issues` 均为空；已核它们的相关总结、优点和语言优先事项。空 issues 本身不是漏检证据，也不能证明分数准确。mid 总结笼统称有“分词结构”，而所列证据主要是 while/if/which；宜具体指明结构，避免把限定形容词与独立分词状语混说。这是解释精确度的小问题，不另算语法误改。

## 成功结果：全部 10 条 LR/GRA 建议

### 1. t2-weak / LR / issues[0]

原文：`If the bus is more better`

模型建议：`If the bus service were better, more people would use it.`

more better 确属双重比较级错误。新句语法正确，但 is/will 改为 were/would，把现实可能条件改成较假设性的条件；删除原句末尾交通减少的后果。宜标为可选整句改写，最小纠错不必改变语气。

审阅者可选改句：`If the bus service is better, people will use it more and there will be less traffic.`

### 2. t2-weak / LR / issues[1]

原文：`the bus is always late and very crowd`

模型建议：`the bus is always late and very crowded`

crowd 改为 crowded 正确，late 保留原意。提供的是原句中的主句片段，可作局部替换；不是因为小写或没有句号就构成语法残句。

### 3. t2-weak / LR / issues[2]

原文：`it is good for enviroment`

模型建议：`it is good for the environment`

environment 拼写及 the 冠词修正正确，未添加环境收益的具体事实。原句的其他部分没有被此局部建议覆盖。

### 4. t2-weak / LR / issues[3]

原文：`many people dont have car`

模型建议：`many people do not have cars`

dont/car 改为 do not/cars 正确，仍保留“没有车”，没有变成“买不起车”。但原句 Because many people... 独立成句；仅替换此引文仍不能修复整句残句。该问题已在本次 CC 另一条建议中明确处理，不能说模型完全漏检。

审阅者可选改句：`Many people do not have cars and need buses and trains to go to work and school.`

### 5. t2-weak / GRA / issues[0]

原文：`I am agree with this opinion`

模型建议：`I agree with this opinion to some extent, but not entirely.`

删除多余 am 正确；to some extent, but not entirely 对应原文 in some way but not all，立场未变。

### 6. t2-weak / GRA / issues[1]

原文：`goverment should spend money for public transport not for build new road`

模型建议：`the government should spend money on public transport rather than on building new roads.`

government、spend money on、building new roads 修正可用；rather than on building 与前面的 on public transport 对应。没有添加新的交通事实。

### 7. t2-weak / GRA / issues[2]

原文：`the city is grow`

模型建议：`the city is growing`

is grow 改为 is growing 正确；但原文完整句是 Because the city is grow and more people buy car every year.，局部替换后仍是独立 Because 从句，且 cars 尚未修。建议本身 the city is growing 是完整主谓结构，不应把它单独称为残句；未解决的是原句上下文。优先事项已提醒 Because 独立成句，仍欠此处完整可用改句。

审阅者可选改句：`New roads are also important because the city is growing and more people buy cars every year.`

### 8. t2-weak / GRA / issues[3]

原文：`my father drive to work everyday and he spend two hour`

模型建议：`my father drives to work every day and spends two hours on the road.`

drives/spends、two hours、every day 和 on the road 均合理，保留父亲每天开车、耗时两小时的原意。建议补出的 on the road 来自完整原句 in the road，并非新事实。

### 9. t1-no-image / GRA / issues[0]

原文：`and Country B had grown to approximately 65%`

模型建议：`By 2020, the percentage in Country A had risen slightly to about 75%, and the figure for Country B had grown to approximately 65%.`

the figure for Country B 比 Country B had grown to 65% 更精确，替换本身可用；但两个由 and 连接的完整分句可以有不同主语。理由应聚焦“国家”代指“该国比例”的精确度，不能把主语不同本身当语法错误。成功结果 priorities[0] 将其总括为“主语偷换”，属于过度定性。

### 10. t1-no-image / GRA / issues[1]

原文：`where ownership almost doubled to nearly 80%, overtaking Country A`

模型建议：`The most dramatic change was seen in Country C, where ownership almost doubled to nearly 80%, with Country C overtaking Country A.`

原文可按省略比较理解为 C 的拥车比例超过 A 的比例；直接定性为分词悬垂证据不足。with Country C overtaking Country A 能明确国家，却仍用国家代指其比例。更好的精确化是比较 ownership 与 the figure for Country A。建议未新增年份、数值或连续增长形状。

审阅者可选改句：`The most dramatic change was seen in Country C, where ownership almost doubled to nearly 80%, exceeding the figure for Country A.`

## 被拒的原始输出：不属于成功反馈

raw_calls 第 5 行（off-topic 第一次）整体 JSON 因 Extra data 被拒，LR/GRA 都没有问题建议；第二次成功的结果已在上面覆盖。第 7、8 行（under-length 两次）都在 JSON 末尾报 Expecting comma delimiter，最终失败。为人工阅读，仅单独解码其中完整的 LR/GRA 对象；这不是修复 JSON、绕过校验或将其发布。

| 原始位置 | 原文/建议 | 审阅 |
|---|---|---|
| line 7 / LR[0] | It is also cheaper for students and old people who do not have cars.<br>→ 改为 “It is also cheaper for students and elderly people who do not own a car.” | old people 是可理解的普通表达，并不是语法错误；older people/elderly people 可作语域选择。把原文一概定为“不够得体”过严。do not own a car 比 have 更具体地谈所有权，通常相近但不是必要替换；本次没有引入“负担不起”的新原因。 |
| line 8 / LR[0] | It is also cheaper for students and old people who do not have cars.<br>→ 可使用elderly people等更正式表达，并补充与交通费用相关的主题词汇。 | elderly people 和交通主题词可作可选词汇练习；不能只因简单常见就把原表达判错，新增词仍须服务原意。 |
| line 8 / LR[1] | In conclusion, public transport should be the priority, but some roads are still necessary.<br>→ 适当轮换使用public transit、buses and trains等表达，避免同一短语反复出现。 | public transport 是文章核心主题词，全文出现三次，重复本身不证明表达错误。public transit 可作同义选择；buses and trains 指交通方式集合，范围比 public transport 窄，须按具体语境选择，不应机械轮换。 |

以上两次 GRA 均无 issues。原始 LR 总结仍有以“更少见词”作为硬门槛的倾向；这里只记录教学风险，没有老师评分或完整成功反馈，不能得出本篇 LR 应是多少分。

## 与旧语言复核逐项对照

| 旧问题 | 本次观察 |
|---|---|
| mid which 指代模糊 | 本次 GRA strengths 明确说指代明确、标点正确，issues 为空。 |
| good 因果 as / 长句被当错误 | 本次 GRA 赞扬句式控制，issues 为空；未要求改掉因果 as。 |
| strong treadmill 太口语 / 省略关系词结构拥挤 | 本次 LR 赞扬 treadmill；GRA 明说省略关系词叠加仍清晰。剩余长句提醒应视为可选。 |
| Task 1 By 2020 + had grown 被强改 | 本次肯定过去完成时恰当。 |
| Task 1 并列主语不同被称省略不当 | 新理由较多聚焦国家/比例精确度，改句合理；但 priorities 仍叫“主语偷换”，未完全消除过重语法定性。 |
| under-length 无车变买不起车 | 两条原始改词建议均未出现 cannot afford；但本篇整体失败，没有成功结果，不能计为学生结果修复成功。 |
| Task 1 只有端点却建议 steady climb | 本次 LR issues 为空，GRA 替换未添加稳定/连续增长。 |
| mid/good 正确常用词被迫升级 | 本次不再点名 much less crowded 或 difficult choice 为错误；good 明说避免堆难词。LR 总结的高阶词倾向仍须谨慎，不能靠新词数校准分数。 |
| weak Because 局部修正后仍可残句 | 本次 GRA 仍只给 the city is growing，应用回完整原句仍残缺；但总结与优先事项已识别残句。 |

“本批未复现”不等于系统性修复已证明。旧 .6 与本轮 .8 还同时改变其他提示词和后处理，不能把改善全部归因于去掉问题下限、去掉分数预设或 high 本身。

## 证据与交接

逐条机器可读记录、原始字段路径、失败与成功可见性、文件 SHA256 均保存在同目录 `manual_language_review.json`。子审阅仅新增这两份报告，未直接执行commit/push/deploy；主审已汇总规范交接，最终交付状态见本目录README。未单独跑页面或复制视图，不把 JSON 审阅冒充浏览器验收。

下一步优先收紧 Task 1 的语法标签，并让弱作文局部建议附足够上下文；再以老师评分与批注做质量校准。不能用问题数量减少或模型分数上涨代替校准。
