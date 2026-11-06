# 提示词 .8 high 与旧 .6 high：TR/CC/论证人工复核

本轮可见输出的过严 TR/CC 批评减少，限定立场/合理支撑/离题标准分离有改善；还不能称语义全面通过。6/7交付，短文两次格式失败；存在上下文漏读的通用建议、good可选建议字段丢失、strong数字建议被过滤、Task1结构化证据年份选错。

本轮 9 次实际请求、6/7 份最终评价可用。这里只记录主审已经执行的批次；本审阅没有增加调用。判断为人工阅读意见，不是重新给分，也不把问题条目数或自动 sanity 当准确率。

## 逐篇对照

| 样本 | 旧 high 总分 | 新 high 总分 | 观察 |
|---|---:|---:|---|
| t2-weak | 5.5 | 5.5 | 基本保持正确的限定立场与真实道路因果问题；仍有衔接/结尾建议偏模板化。 |
| t2-mid | 7.0 | 7.0 | 旧 Another advantage / 篇幅不平衡的硬性 CC 缺陷不再出现；环境与农村段的既有解释被明确认可，TR/CC issues 均空。 |
| t2-good | 7.5 | 8.0 | 新 TR/CC 都明确承认机制、例外与自然衔接，不再因连接词常见列问题。 |
| t2-strong | 8.0 | 8.0 | 不再把短让步段正式列 TR 缺陷，也没有强制反驳、结尾冲突；TR/CC issues 均空。 |
| t2-off-topic | 5.5 | 6.0 | 重试后准确识别完全离题，并明确把 CC 的内部组织与 TR 的题目相关性分开；旧错指 Furthermore 位置及短段硬性问题未重现。 |
| t2-under-length | 5.5 | 失败 | 最终失败，不能声称旧问题已在可交付报告中解决。 |
| t1-no-image | 不可评 | 不可评 | 无图继续禁止 TA/总分，A/C 2020矛盾仍抓到；时态/时间连接词不再作为 CC 缺陷，五段识别正确。 |

## 仍需要处理或明确披露的内容

- **格式可靠性未过关**：off-topic 首次因 JSON 提前关闭后还有字段被拒，重试成功。under-length 两次均缺关闭括号，且 argument/overall/priorities 被错嵌在 criteria 下。系统拒绝正确；没有最终评价就不能算旧短文误批已在产品层解决。
- **good 的空改进列表不是纯语义改善**：三条原建议的引文都真实，但模型把 suggestion 写成 comment，三条均丢弃。应区分格式丢弃与虚构引文，不把“未显示”当“模型判断没有问题”。
- **strong 仍生成无来源数字**：原建议含 “a bus carrying forty passengers replaces dozens of cars”。服务端已经删除，说明数字守卫在这次输出中有效，但不能说新提示词根治了编数。
- **通用建议与细项理由仍有不一致**：mid 段落评语认可环境因果，优先建议却说避免“只有结论式断言”；good TR 认可充分机制，优先建议又称“点到为止”；strong 首先认可机制，整体评语又称减排“只有断言没有机制”。这些更适合可选深化，并需读完整上下文。
- **可能漏掉的精度提示**：weak 的 everybody 健康快乐仍是全称化表述；旧 high 指出它过度概括，本轮只说连接机械。不能因为少一个问题就认定更准。
- **Task 1 矛盾仍抓到，但结构化支持不匹配**：comment 正确对比2020年C≈80与A≈75；figures 却是2000年的70/55/40。引文存在检查不能保证选对决定性证据。

## 分样本剩余限制与旧记录追踪

### t2-weak

旧 high 对 everybody 健康快乐的过度概括有明确评论；本轮只在 CC 把这一句称为连接机械，没有再处理其全称范围。可视为未覆盖的合理精度建议，不据此给出新的专家分数。

旧81条记录（0起始）对应：37, 38, 39, 40, 41, 42, 43, 44, 45。这些对应仅追踪议题，不把重复条目当独立测量。

### t2-mid

仍把251词/每段再加一句作为提档路线；优先建议“避免只有结论式断言”与本条段落分析认可因果不完全一致。旧40倍未在 mid 再出现，但 strong 生成了40名乘客建议后被过滤。

旧81条记录（0起始）对应：46, 47, 48, 49, 50, 51。这些对应仅追踪议题，不把重复条目当独立测量。

### t2-good

模型返回3条可选改进，但字段用了 comment 而非 suggestion，全部被丢弃；最终 improvements 空不等于模型自判无需改进。优先建议仍把充分展开的原文称“点到为止”。

旧81条记录（0起始）对应：52, 53, 54, 55, 56。这些对应仅追踪议题，不把重复条目当独立测量。

### t2-strong

整体评论仍称减排只有断言、无机制，忽视同段步行/缩短出行链条；让步建议又说要建立边界，原文已有。无来源 forty passengers 已被服务端删除，不能宣布模型不再编数。

旧81条记录（0起始）对应：57, 58, 59, 60, 61。这些对应仅追踪议题，不把重复条目当独立测量。

### t2-off-topic

首轮 JSON 结构错误，无可用结果；第二轮成功。各离题条目是同一核心缺陷。整体总分从5.5变6.0不意味着离题被放过，TR由3降2、其余项独立计分；准确分数仍需校准。

旧81条记录（0起始）对应：62, 63, 64, 65, 66, 67, 68, 69, 70。这些对应仅追踪议题，不把重复条目当独立测量。

### t2-under-length

两次被拒正式文本中已经承认限定立场、城乡限定、既有因果；未再出现旧“没有城市背景”误读。但两次均结构错误，不给分是正确。仍有让步后再重申优先的重复建议。

旧81条记录（0起始）对应：71, 72, 73, 74, 75, 76, 77, 78。这些对应仅追踪议题，不把重复条目当独立测量。

### t1-no-image

末段“基本重复”的评价仍应保留新信息区别；矛盾 comment 用正确2020数值，但 figures 支持列表却抽2000的70/55/40，不是决定性证据。

旧81条记录（0起始）对应：79, 80。这些对应仅追踪议题，不把重复条目当独立测量。

## 最终可见条目的逐项证据

### t2-weak · criteria.task.issues.0

判断：**supported_precision_feedback**。道路必然制造更多汽车、污染的表述过强；增加诱导驾驶机制及 can/may 限定有据。

模型引文：Because the road make more car and more pollution.
模型comment：把道路建设直接等同于“制造更多汽车和污染”，因果过度简化且绝对化，缺乏限定，削弱论证精确度。
模型suggestion：改为有限定的因果表达，如：Building more roads can encourage more car use, which may increase pollution.

原稿完整同段：

> But I think public transport is more important than road. Because the road make more car and more pollution. The public transport can carry many people in one time and it is good for enviroment. Also if more people take bus, the city will be more quiet and the air will be more clean, so everybody can be more healthy and happy.

### t2-weak · criteria.coherence.issues.0

判断：**supported**。Because 从句独立成句是明确的句法片段，合并或改成主句有直接依据。

模型引文：Because many people dont have car and they need bus and train to go work and school.
模型comment：该句以 Because 开头独立成句，和前句断裂，形成句子片段，破坏句间衔接。
模型suggestion：与上句合并或去掉 Because：Many people do not have cars and need buses and trains to go to work and school.

原稿完整同段：

> Firstly, public transport is good for people. Because many people dont have car and they need bus and train to go work and school. If the bus is more better, people will use it more and the traffic will be less. In my city the bus is always late and very crowd so people dont like to take it. Also the train is too expensive for student. So goverment should make it cheap and more fast.

### t2-weak · criteria.coherence.issues.1

判断：**optional_style_overpresented_as_fault**。Also 与 so 在这里分别承担添加与结果功能，连用本身不证明衔接错误；全句虽长但因果方向清楚。可以拆分，建议中的 Furthermore/As a result 只是替换连接词，未直接改善 everybody 的过度概括。

模型引文：Also if more people take bus, the city will be more quiet and the air will be more clean, so everybody can be more healthy and happy.
模型comment：Also 和 so 连续使用，衔接较机械，且因果链过长，读者需要自行理顺层次。
模型suggestion：拆分并改用更明确的连接，如 Furthermore, ... As a result, ...

原稿完整同段：

> But I think public transport is more important than road. Because the road make more car and more pollution. The public transport can carry many people in one time and it is good for enviroment. Also if more people take bus, the city will be more quiet and the air will be more clean, so everybody can be more healthy and happy.

### t2-weak · argument.problems.0

判断：**supported_duplicate**。与 TR 的道路因果问题相同，合理但不是新增独立缺陷。

模型引文：Because the road make more car and more pollution.
模型comment：把道路建设直接说成会“制造更多汽车和污染”，因果过于绝对，缺少限定，削弱论证的严谨性。
模型suggestion：改为有限定的因果表达，如：Building more roads can encourage more car use, which may increase pollution.

原稿完整同段：

> But I think public transport is more important than road. Because the road make more car and more pollution. The public transport can carry many people in one time and it is good for enviroment. Also if more people take bus, the city will be more quiet and the air will be more clean, so everybody can be more healthy and happy.

### t2-weak · argument.improvements.0

判断：**reasonable_optional_expansion**。补贴票价、增加班次使措施具体；原段已经有昂贵/迟到导致不用公交的背景，不能理解为原先缺少理由。

模型引文：So goverment should make it cheap and more fast.
模型suggestion：可以具体说明政府如何投入，例如补贴票价、增加班次，使建议更有说服力：The government could subsidise fares and increase bus frequency.

原稿完整同段：

> Firstly, public transport is good for people. Because many people dont have car and they need bus and train to go work and school. If the bus is more better, people will use it more and the traffic will be less. In my city the bus is always late and very crowd so people dont like to take it. Also the train is too expensive for student. So goverment should make it cheap and more fast.

### t2-weak · argument.improvements.1

判断：**partly_redundant_optional**。具体连接载客量与私家车使用可深化，但同段已经写更多人乘公交→空气更干净，前文也写公交更好→使用更多→交通更少。“避免只作笼统断言”略忽视上下文。

模型引文：The public transport can carry many people in one time and it is good for enviroment.
模型suggestion：补充机制：公交运量大如何减少私家车使用和尾气排放，避免只作笼统断言。

原稿完整同段：

> But I think public transport is more important than road. Because the road make more car and more pollution. The public transport can carry many people in one time and it is good for enviroment. Also if more people take bus, the city will be more quiet and the air will be more clean, so everybody can be more healthy and happy.

原稿完整同段：

> Firstly, public transport is good for people. Because many people dont have car and they need bus and train to go work and school. If the bus is more better, people will use it more and the traffic will be less. In my city the bus is always late and very crowd so people dont like to take it. Also the train is too expensive for student. So goverment should make it cheap and more fast.

### t2-weak · argument.improvements.2

判断：**redundant_context_underread**。结论前一句已明确 more money for public transport but also build some road when necessary；建议基本重复现有限定立场。语法错误应与论证缺失分开。

模型引文：Both is important for the people and the country develop.
模型suggestion：结论可更明确地重申比例，如：Public transport should receive the larger share of funding, while road building should be limited to necessary cases.

原稿完整同段：

> In conclusion, I think goverment should spend more money for public transport but also build some road when it is necessary. Both is important for the people and the country develop.

### t2-mid · argument.improvements.0

判断：**reasonable_optional_expansion**。三句的计数正确；补假设比较可用。本段已有污染危害及人均污染→可持续性的解释，应保持可选深化定位，不倒推为无支撑。

模型引文：Another advantage is the environment.
模型suggestion：本段只有三句，展开较薄。可以在说明“人均污染更低”之后补一句具体机制或一个假设性的对比（例如同样一趟出行，坐满乘客的公交车与一人一车的排放差别），让环境论点更有说服力。

原稿完整同段：

> Another advantage is the environment. Cars produce a lot of air pollution and carbon emissions, which are harmful to people's health and contribute to climate change. Public transport produces less pollution per passenger, so it is a more sustainable option in the long term.

### t2-mid · argument.improvements.1

判断：**redundant_or_overrestrictive_optional**。全文结论已说公交不可行地区保留道路；要求本段再回扣是重复。同时当前货运理由并不完全等于“公交无法覆盖”，把所有道路投资限定于这类地区可能缩窄原论点。

模型引文：Also, goods are mostly transported by trucks, and poor roads can slow down the economy.
模型suggestion：建议在本段末尾加一句把例外收回到主立场，例如说明“因此道路建设应限于公共交通无法覆盖的地区”，让让步段与中心论点衔接更紧。

原稿完整同段：

> On the other hand, new roads are sometimes needed. In rural areas, there are not enough passengers to make train lines profitable, so people depend on cars. Also, goods are mostly transported by trucks, and poor roads can slow down the economy.

原稿完整同段：

> In conclusion, I agree that governments should give priority to public transport because it is more efficient and better for the environment. However, they should still build roads in places where public transport is not practical.

### t2-mid · argument.improvements.2

判断：**optional_depth_not_wordcount_rule**。251 词是事实；效率段已有载客量比较、服务吸引司机、地铁例子完整链条。补空间效率可选，不能仅以接近250词推定展开不足或自动排除更高档。

模型引文：The main reason to invest in public transport is that it can move a large number of people efficiently.
模型suggestion：全文仅251词，刚过下限。效率论点除了“载客多”，还可以补充一个层面（如占用道路空间更少或节省通勤时间），使主体段论证层次更丰富，也更接近更高档的充分展开。

原稿完整同段：

> The main reason to invest in public transport is that it can move a large number of people efficiently. A single train can carry hundreds of passengers, while the same number of people would need hundreds of cars. If buses and trains are frequent, cheap and reliable, many drivers will choose them, which will reduce traffic jams. For example, after my city opened a new metro line, the main road to the city centre became much less crowded during rush hour.

### t2-strong · argument.improvements.0

判断：**redundant_context_underread**。开头已明确 no realistic alternative exists，原段又举农村与货运且限定 targeted upgrades。医院情境可以增加具体性，但“这样例外就有边界”不应暗示原文没有边界。

模型引文：in such contexts targeted upgrades may represent genuine value for money
模型suggestion：让步段可以再补一句判定标准，说明什么情况下修路才符合你的立场，例如'where a bypass is the only way to connect a remote town to a hospital'，这样例外就有边界，而不只是举例。

原稿完整同段：

> That said, a blanket refusal to build roads would be misguided. Rural communities and freight logistics depend on reliable highways, and in such contexts targeted upgrades may represent genuine value for money.

原稿完整同段：

> How a government allocates its transport budget shapes not only how quickly people travel, but also the kind of cities they live in. Although there is an intuitive appeal to building new roads whenever traffic worsens, I am convinced that investment should be weighted decisively towards public transport, with road construction reserved for cases where no realistic alternative exists.

### t2-strong · argument.improvements.1

判断：**debatable_optional_restructure**。三方面信息确实密集，可分层；但原句有步行社区→缩短距离的因果，并非纯并列无展开。应作为可选重组而非每个论点必须另加一例。

模型引文：Well-designed transit also allows denser, more walkable neighbourhoods to develop around stations
模型suggestion：该段同时处理分配公平、城市密度与减排三个论点，每点都只有一句。可考虑分层：用一句话点明'社会回报'与'环境回报'两类，再各给一个具体后果，避免论点并列而缺乏展开。

原稿完整同段：

> Equally important are the distributional consequences. Road spending disproportionately benefits those who own cars, whereas frequent and affordable buses and trains extend opportunity to people who cannot or prefer not to drive. Well-designed transit also allows denser, more walkable neighbourhoods to develop around stations, reducing the distances people need to travel in the first place, and it cuts emissions at a time when the transport sector remains one of the most stubborn sources of carbon.

### t2-off-topic · criteria.task.issues.0

判断：**supported_duplicate**。所引内容全部讨论在线教育，确实未回应交通资金题。三条是同一整体离题问题的不同位置，不是三项独立准确性收益。

模型引文：Online learning has grown rapidly over the past decade, and many people now believe that it will eventually replace traditional classrooms.
模型comment：开头引入的是「线上学习」这一话题，与本题的公共交通/道路建设毫无关系，说明考生没有回应题目。
模型suggestion：开头应直接改写题目并表明立场，例如：While some argue that governments should prioritise public transport over new roads, I largely agree with this view because efficient buses and trains move far more people per unit of public spending.

原稿完整同段：

> Online learning has grown rapidly over the past decade, and many people now believe that it will eventually replace traditional classrooms. In my view, although online courses offer clear advantages, face-to-face education will remain essential.

### t2-off-topic · criteria.task.issues.1

判断：**supported_duplicate**。所引内容全部讨论在线教育，确实未回应交通资金题。三条是同一整体离题问题的不同位置，不是三项独立准确性收益。

模型引文：The most obvious benefit of online learning is flexibility.
模型comment：主体段讨论线上课程的好处，属于另一个题目的内容，对本题的立场没有任何支持作用。
模型suggestion：主体段应围绕公共交通的益处展开，例如：Investment in buses and rail can carry far more passengers per pound spent than extra lanes, which reduces congestion in the long term.

原稿完整同段：

> The most obvious benefit of online learning is flexibility. Students can watch lectures at any time and study at their own pace, which is especially useful for adults who work full-time or have family responsibilities. Online courses can also reach learners in remote areas who would otherwise have no access to good teachers. In addition, digital materials can be updated quickly, and learners can replay difficult explanations as many times as they need, which is impossible in a traditional lecture. For many people, these features make online study cheaper and more convenient than attending a college in person.

### t2-off-topic · criteria.task.issues.2

判断：**supported_duplicate**。所引内容全部讨论在线教育，确实未回应交通资金题。三条是同一整体离题问题的不同位置，不是三项独立准确性收益。

模型引文：Furthermore, many learners find it hard to stay motivated without the structure of a timetable and the presence of classmates.
模型comment：这一段继续讨论学习动机，与「政府该把钱花在哪里」完全脱节，属于严重偏题。
模型suggestion：可以改为让步或限定条件的段落，例如：Admittedly, new roads may be necessary in rural areas with no realistic rail option, but in cities the priority should still be public transport.

原稿完整同段：

> Furthermore, many learners find it hard to stay motivated without the structure of a timetable and the presence of classmates. Completion rates for many free online courses are notoriously low, which suggests that self-discipline is a serious obstacle.

### t2-off-topic · argument.problems.0

判断：**supported_with_scope**。文章对教育有明确立场，但对本题无立场；评论已明确“就本题而言”，因此标签可成立，不能脱离这段解释说作者本身不会表态。

模型引文：In my view, although online courses offer clear advantages, face-to-face education will remain essential.
模型comment：这是全文唯一表明立场的地方，但它回答的是另一个问题。读完文章后，读者完全无法判断作者认为政府该投资公共交通还是新建道路，因此就本题而言没有立场。
模型suggestion：把这句话改成对本题的直接立场，例如：In my view, governments should prioritise spending on public transport rather than building new roads, although extra road capacity may still be needed in a few rural areas.

原稿完整同段：

> Online learning has grown rapidly over the past decade, and many people now believe that it will eventually replace traditional classrooms. In my view, although online courses offer clear advantages, face-to-face education will remain essential.

### t2-off-topic · argument.problems.1

判断：**supported_duplicate**。该段与交通题无关；与整体离题判断重复，不应按条目数评价模型更准。

模型引文：The most obvious benefit of online learning is flexibility.
模型comment：主体段的核心论点与题目无关，整段的说服力无法转化为本题分数。
模型suggestion：用同样的论证方式处理本题：先提出分论点，例如公共交通每位乘客占用的公共资金更少，再用因果或对比说明它如何缓解拥堵、惠及没有私家车的人。

原稿完整同段：

> The most obvious benefit of online learning is flexibility. Students can watch lectures at any time and study at their own pace, which is especially useful for adults who work full-time or have family responsibilities. Online courses can also reach learners in remote areas who would otherwise have no access to good teachers. In addition, digital materials can be updated quickly, and learners can replay difficult explanations as many times as they need, which is impossible in a traditional lecture. For many people, these features make online study cheaper and more convenient than attending a college in person.

### t2-off-topic · argument.problems.2

判断：**supported_duplicate**。该段与交通题无关；与整体离题判断重复，不应按条目数评价模型更准。

模型引文：However, classroom learning provides things that are difficult to replicate on a screen.
模型comment：这一段虽与前一段形成对比，但对比的主题仍是教育形式，与道路建设或公交投资毫无关联。
模型suggestion：可以改为承认另一方的段落：有人主张新道路能缓解拥堵，但更多车道往往吸引更多车辆，长期效果有限。

原稿完整同段：

> However, classroom learning provides things that are difficult to replicate on a screen. Teachers can notice immediately when a student is confused and adapt their explanations. Students also develop social skills by working together, discussing ideas and building friendships, which are an important part of education, particularly for children.

### t2-off-topic · argument.problems.3

判断：**supported_duplicate**。该段与交通题无关；与整体离题判断重复，不应按条目数评价模型更准。

模型引文：Furthermore, many learners find it hard to stay motivated without the structure of a timetable and the presence of classmates.
模型comment：这一段是整篇偏离题目的延续，完全讨论学习动机，属于与题目无关的内容。
模型suggestion：替换为与本题相关的内容，例如讨论公共交通对低收入群体和无车家庭的重要性，从而说明政府资金的优先方向。

原稿完整同段：

> Furthermore, many learners find it hard to stay motivated without the structure of a timetable and the presence of classmates. Completion rates for many free online courses are notoriously low, which suggests that self-discipline is a serious obstacle.

### t2-off-topic · argument.improvements.0

判断：**supported_rewrite_direction**。建议保留背景—立场或机制说明的写法、替换为交通内容，方向合理；需要全文重写，不能只替换引文。

模型引文：Online learning has grown rapidly over the past decade, and many people now believe that it will eventually replace traditional classrooms.
模型suggestion：保留这种「背景—观点」的开头写法，但把它套到本题上：先陈述「有人认为政府应优先投资公共交通而非新建道路」，再给出自己的立场。

原稿完整同段：

> Online learning has grown rapidly over the past decade, and many people now believe that it will eventually replace traditional classrooms. In my view, although online courses offer clear advantages, face-to-face education will remain essential.

### t2-off-topic · argument.improvements.1

判断：**supported_rewrite_direction**。建议保留背景—立场或机制说明的写法、替换为交通内容，方向合理；需要全文重写，不能只替换引文。

模型引文：Teachers can notice immediately when a student is confused and adapt their explanations.
模型suggestion：这种「说明机制」的句子是本文最有效的论证方式，可以在新题目里同样使用，例如说明公交专用道如何让通勤时间更可预测。

原稿完整同段：

> However, classroom learning provides things that are difficult to replicate on a screen. Teachers can notice immediately when a student is confused and adapt their explanations. Students also develop social skills by working together, discussing ideas and building friendships, which are an important part of education, particularly for children.

### t1-no-image · criteria.coherence.issues.0

判断：**partly_supported_optional_compression**。开头和结尾重复“均增长”，可合并以紧凑。但结尾新增 C 增幅最大/A 最小，不能说内容全已在概述。此次不再明确捏造“第二段已写C最大”，较旧版改善。

模型引文：In summary, while every country saw an increase, the growth was particularly striking in Country C and much more modest in Country A
模型comment：末段基本重复开头 overview 的内容，作为独立段落功能较弱，使结构略显机械。
模型suggestion：可将这一点并入开头概述，或删除末段，让主体数据段承担主要展开功能，使结构更紧凑。

原稿完整同段：

> In summary, while every country saw an increase, the growth was particularly striking in Country C and much more modest in Country A.

原稿完整同段：

> Overall, car ownership increased in all four countries over the period, although the size of the rise varied considerably. Country A had the highest level of ownership in both years, while Country D remained the lowest.

## Task 1 数据自洽证据

{
  "quote": "Country A had the highest level of ownership in both years",
  "quote_found": true,
  "figures": [
    "around 70%",
    "roughly 55%",
    "about 40%"
  ],
  "comment": "2000年A的约70%高于其他三国；但2020年C的近80%高于A的约75%，所以“both years”不成立。"
}

评论正确识别2020年C近80>A约75，否定both years有据；但 figures 列表为2000的70/55/40，不能作为该矛盾的决定性结构化支持。所有引用存在不等于证据选择正确。

> Overall, car ownership increased in all four countries over the period, although the size of the rise varied considerably. Country A had the highest level of ownership in both years, while Country D remained the lowest.

> In 2000, around 70% of households in Country A owned a car, compared with roughly 55% in Country B and about 40% in Country C. Country D had by far the lowest figure, at only 15%.

> By 2020, the percentage in Country A had risen slightly to about 75%, and Country B had grown to approximately 65%. The most dramatic change was seen in Country C, where ownership almost doubled to nearly 80%, overtaking Country A. Country D also experienced significant growth, reaching around 35%, but it was still well behind the other three countries.

## 方法与边界

- 这是合成7篇、单次输出的小样本人工比较，非教师金标准校准，也不计算人工准确率。
- 比较 .6 high 与 .8 high 的完整提示词/校验版本；没有固定模型随机性，不能把变化因果归于某一提示句、思考强度或模型能力。
- 只审阅脱敏最终回答、正式输出文本、合成原稿与旧已提交报告；未读取思考正文、密钥、学生内容或本地私有 results。未发起任何网络/模型调用。
- 本报告聚焦 TR/CC/论证与数据自洽；LR/GRA 由主审另行补充，未给另一套专家分数。
- 旧81条包括两档及重复问题，本轮只追踪high相关的44条主要点；按组对应，不强造一对一的新条目。最终条目减少同时受提示行为、字段丢弃和数字过滤影响。
- under-length无最终结果：不能把被拒文本的合理判断算作产品成功，亦不能从问题少推出漏报不存在。

结构化 JSON 包含原建议/最终建议对照、三次拒绝的解析位置、被拒短文的只读结构取证与全部上述引文。所有原始共享输出未修改。
