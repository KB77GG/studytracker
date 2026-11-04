# off / high 人工语义复核

high 有局部改善，但本批不足以支持“全面更准”或评分已校准。两档都接受限定立场、识别离题和字数不足、抓到 Task 1 的 A/C 矛盾；high 对 good 作文已有机制的理解更准确，也更具体地指出弱文过度概括。与此同时，它新增了明确的上下文误读，并给出无来源的 forty times 数量建议。

仅查看共享的脱敏最终回答和合成原稿；没有读取 reasoning、凭据或增加模型调用。以下分数是模型输出记录，不是本审阅另给的专家分数。

| 样本 | off 总分 | high 总分 | 对照判断 |
|---|---:|---:|---|
| t2-weak | 5.5 | 5.5 | high的过度概括定位更具体，两档均正确接受限定立场；high没有为了提高问题数误判同段公交支撑。仍有可选结尾重复要求。 |
| t2-mid | 6.5 | 7.0 | high更明确认可农村/货运例外与原有因果，较off改进；但TR建议新增无来源forty times，CC仍把常规主题句和不均等篇幅当缺陷。 |
| t2-good | 7.5 | 7.5 | high终于承认as从句机制，纠正off的明确漏读；CC仍仅因连接词常见而降评价，可选机制建议仍重复。 |
| t2-strong | 7.5 | 8.0 | high更认可机制可以替代具名实例，未编造立场冲突；环境主题控制有可讨论空间，但仍要求让步段达到类似厚度。分数增加不能直接等于更准确。 |
| t2-off-topic | 5.0 | 5.5 | 两者均抓到整体离题。high CC从4到6，仍保留错话题拖累CC表述；新增段落长度与连接词批评部分无据。三条irrelevant是同一问题，不能用数量评优。 |
| t2-under-length | 5.0 | 5.5 | 两者识别97词/单段并接受限定立场。high结构块0问题不等更准，TR/CC反而误说没有城乡铺垫、没有主次关系；原文同段都有。 |
| t1-no-image | 不可评 | 不可评 | 两者均准确抓A75<C80与两年A最高冲突，保留TA/总体不可评；high新增概述已经写C涨幅最大这一具体误读。 |

## 最需要处理的反馈问题

- high / t2-mid：建议“a full bus carries about forty times as many people as a car”，原稿、题目没有40倍来源，服务端也没有删除。不能把写成英文单词的具体数量当作安全例子。
- high / t2-under-length：说没有城乡铺垫、没有让步与主旨关系；原文已写“in big cities”，最后一句已重申公交优先。
- high / Task 1：说第二段已经写C涨幅最大，实际第二段未写；可建议合并总结，但不能捏造重复依据。
- 两档仍把常见且正确的连接词、短让步段或未加具名例子当作缺点；需要区分明确错误和可选优化。
- high / good 已关闭 off 的“没有机制”漏读，但改进建议仍重复原句；问题数、改列数和自动 sanity 不能代替语义判断。

## 完整逐项证据

判断为人工推断；同段引文是可核查事实。每条附完整原段，避免只盯模型截取的短语。

### off · t2-weak · criteria.task.issues[0]

判断：**正确**（supported_precision_feedback）。开头只说some way but not all，具体优先关系要从后文得知；建议提前说明倾向合理。该批没有把部分同意误判成矛盾。

模型引文：I am agree with this opinion in some way but not all.

模型说明：立场表述含糊，“in some way but not all”没有说明在哪些方面同意，读者需读完全文才能推断。

模型建议：开头就点明倾向，例如：I largely agree that governments should prioritise public transport, although new roads are still needed in some cases.

原稿完整同段：

> Nowadays transport is very important problem in many country. Some people think goverment should spend money for public transport not for build new road. I am agree with this opinion in some way but not all.

### off · t2-weak · criteria.task.issues[1]

判断：**过严**（partly_supported_overstated）。everybody更健康快乐确有过度概括；但原段已经有载客量、少车少污染、空气更干净到健康的链条，称停留在断言、缺少机制过于笼统。可补细节而非认定没有解释。

模型引文：Also if more people take bus, the city will be more quiet and the air will be more clean, so everybody can be more healthy and happy.

模型说明：论证停留在断言层面，缺少机制说明，且“more quiet and happy”略显夸张，削弱说服力。

模型建议：补充因果链，例如：fewer cars means less exhaust and noise, which lowers respiratory illness and improves residents' quality of life.

原稿完整同段：

> But I think public transport is more important than road. Because the road make more car and more pollution. The public transport can carry many people in one time and it is good for enviroment. Also if more people take bus, the city will be more quiet and the air will be more clean, so everybody can be more healthy and happy.

### off · t2-weak · criteria.coherence.issues[0]

判断：**过严**（optional_style_overpresented_as_fault）。有限立场允许列出公交和道路各自价值，Firstly/Secondly枚举两方面并非必然逻辑错误。However可更清楚标示转向，但不应仅因这两个连接词就认定逻辑未体现。

模型引文：Secondly, new road is also important.

模型说明：连接词使用机械，且“Secondly”与前段“Firstly”并列，但两段实际是正反两面，逻辑关系未体现。

模型建议：改用体现让步关系的连接，例如：However, building new roads also matters, because...

原稿完整同段：

> Nowadays transport is very important problem in many country. Some people think goverment should spend money for public transport not for build new road. I am agree with this opinion in some way but not all.

原稿完整同段：

> Firstly, public transport is good for people. Because many people dont have car and they need bus and train to go work and school. If the bus is more better, people will use it more and the traffic will be less. In my city the bus is always late and very crowd so people dont like to take it. Also the train is too expensive for student. So goverment should make it cheap and more fast.

原稿完整同段：

> Secondly, new road is also important. Because the city is grow and more people buy car every year. If there is no new road the traffic jam will be very bad and people waste a lot of time. For example my father drive to work everyday and he spend two hour in the road. This is very bad for him and for the economy also.

### off · t2-weak · criteria.coherence.issues[1]

判断：**正确**（optional_style_feedback）。句末also较生硬可以优化，但This已明确指代上一句两小时通勤；不能据此说缺少自然指代。

模型引文：This is very bad for him and for the economy also.

模型说明：句末“also”位置生硬，句间衔接靠简单附加，缺乏自然的指代或过渡。

模型建议：改为：This wastes both his time and the economy's resources, which shows why some new roads are still necessary.

原稿完整同段：

> Secondly, new road is also important. Because the city is grow and more people buy car every year. If there is no new road the traffic jam will be very bad and people waste a lot of time. For example my father drive to work everyday and he spend two hour in the road. This is very bad for him and for the economy also.

### off · t2-mid · criteria.task.issues[0]

判断：**正确**（partly_supported_context_underread）。环境段可以更深入，但段内已有污染/碳排放影响健康及气候、公交人均污染更低到可持续性的解释。建议假设例子属合理可选扩展，不宜暗示只一句无解释，也不必量化减排。

模型引文：Public transport produces less pollution per passenger, so it is a more sustainable option in the long term.

模型说明：环境段只有一句因果断言，缺少具体展开（如减少多少排放、如何影响健康），论证略显单薄。

模型建议：可补充一句机制或假设例子，如 'For instance, if a commuter switches from a private car to a bus, the carbon emissions per person can fall sharply.'

原稿完整同段：

> Another advantage is the environment. Cars produce a lot of air pollution and carbon emissions, which are harmful to people's health and contribute to climate change. Public transport produces less pollution per passenger, so it is a more sustainable option in the long term.

### off · t2-mid · criteria.task.issues[1]

判断：**误判**（remaining_context_false_positive）。农村客流不足→铁路不盈利→依赖汽车，以及货运依靠卡车/劣质道路影响经济，已说明道路需求。要求再说这是必要经济条件，主要是重复已有联系；更适合优化，不能称未说明理由。

模型引文：Also, goods are mostly transported by trucks, and poor roads can slow down the economy.

模型说明：让步段两个理由都点到即止，未说明为何这构成“仍需修路”的充分理由。

模型建议：可加一句因果说明，如 'This means that in these areas road investment is not a luxury but a basic condition for economic activity.'

原稿完整同段：

> On the other hand, new roads are sometimes needed. In rural areas, there are not enough passengers to make train lines profitable, so people depend on cars. Also, goods are mostly transported by trucks, and poor roads can slow down the economy.

### off · t2-mid · criteria.coherence.issues[0]

判断：**过严**（optional_style_overpresented_as_fault）。主题句简短，但其后立即具体说明空气污染、碳排放与健康，不构成可证实的段落方向模糊。更明确主题句可选。

模型引文：Another advantage is the environment.

模型说明：主题句过于简短，未说明“环境”具体指哪方面的优势，段落方向略显模糊。

模型建议：可改为 'Another advantage is environmental: public transport produces far less pollution per passenger than private cars.'

原稿完整同段：

> Another advantage is the environment. Cars produce a lot of air pollution and carbon emissions, which are harmful to people's health and contribute to climate change. Public transport produces less pollution per passenger, so it is a more sustainable option in the long term.

### off · t2-mid · criteria.coherence.issues[1]

判断：**过严**（optional_expansion_overpresented_as_fault）。所引句已有which从句解释危害，下一句用so连接公交人均低污染与可持续性，不能简单归为并列堆叠、缺递进。增加层次可以建议，不是明确衔接故障。

模型引文：Cars produce a lot of air pollution and carbon emissions, which are harmful to people's health and contribute to climate change.

模型说明：段内句子多为并列陈述，缺少进一步递进或举例来深化层次。

模型建议：可加入递进连接，如 'As a result, ...' 或 'This is especially important in dense cities where ...' 使论证更有层次。

原稿完整同段：

> Another advantage is the environment. Cars produce a lot of air pollution and carbon emissions, which are harmful to people's health and contribute to climate change. Public transport produces less pollution per passenger, so it is a more sustainable option in the long term.

### off · t2-good · criteria.task.issues[0]

判断：**误判**（clear_context_false_positive）。模型说没有机制细节，但同一句as从句紧接着给出更便宜更快→更多人开车，下一句总结只是短暂缓堵。可以质疑considerable evidence概括程度，不能说机制未给；建议重复已有机制。

模型引文：there is considerable evidence that new roads tend to fill up quickly

模型说明：提及“大量证据”却未给出任何具体来源或机制细节，略显空泛。

模型建议：可补一句机制说明，如 'because extra capacity lowers journey times and attracts drivers who previously used other routes'，使论证更扎实。

原稿完整同段：

> The strongest argument for prioritising public transport is efficiency. Roads are an inherently limited resource: a lane of motorway can carry only a fixed number of private vehicles per hour, whereas a well-run rail or bus rapid transit line can move many times that number of people in the same space. Moreover, there is considerable evidence that new roads tend to fill up quickly, as cheaper and faster journeys encourage more people to drive. Expanding road networks may therefore offer only temporary relief before congestion returns.

### off · t2-good · criteria.coherence.issues[0]

判断：**误判**（clear_context_false_positive）。本段主题句明确预告social and environmental两方面，At the same time连接并列收益贴切；称转向突兀/机械缺乏证据。可提供替代表述，但不应作为明确衔接缺陷。

模型引文：At the same time, shifting journeys from cars to trains and buses reduces both air pollution and greenhouse gas emissions

模型说明：同一段内并列两个论点，衔接词 At the same time 略显机械，且社会效益与环境效益的转换稍显突兀。

模型建议：可改为 'Beyond access, public transport also delivers environmental gains: shifting journeys...'，使两个论点层次更分明。

原稿完整同段：

> Public transport also brings wider social and environmental benefits. It gives affordable mobility to those who cannot drive, such as students, the elderly and lower-income workers, thereby widening their access to jobs and services. At the same time, shifting journeys from cars to trains and buses reduces both air pollution and greenhouse gas emissions, which is increasingly important as cities attempt to meet climate targets.

### off · t2-strong · criteria.task.issues[0]

判断：**过严**（optional_expansion_overpresented_as_fault）。全文限定了无现实替代方案，乡村和货运依赖道路已提供例外情形。补稀疏人口机制有用，但并非让步必须展开到同样篇幅；summary还说未指出何种情形必要，与原文乡村/货运不符。

模型引文：Rural communities and freight logistics depend on reliable highways, and in such contexts targeted upgrades may represent genuine value for money.

模型说明：让步段仅两句，虽限定了立场范围，但未说明为何这些情形无法由公共交通替代，支撑略单薄。

模型建议：可补一句机制，例如：'Where populations are too sparse to sustain frequent bus services, a modest road upgrade may be the only way to keep goods and residents moving.'

原稿完整同段：

> How a government allocates its transport budget shapes not only how quickly people travel, but also the kind of cities they live in. Although there is an intuitive appeal to building new roads whenever traffic worsens, I am convinced that investment should be weighted decisively towards public transport, with road construction reserved for cases where no realistic alternative exists.

原稿完整同段：

> That said, a blanket refusal to build roads would be misguided. Rural communities and freight logistics depend on reliable highways, and in such contexts targeted upgrades may represent genuine value for money.

### off · t2-strong · criteria.task.issues[1]

判断：**正确**（partly_supported_context_underread）。人均能耗可进一步说明，但前文已有高容量及步行型社区缩短出行距离机制；仅抽取it cuts emissions称整个环境论点纯断言略绝对。适合作为可选深化。

模型引文：it cuts emissions at a time when the transport sector remains one of the most stubborn sources of carbon

模型说明：环境论点只作断言式提及，未解释为何公共交通能减排（如人均排放更低、替代私家车出行）。

模型建议：补充因果：'because a full bus carries far more passengers per unit of fuel than the cars it replaces.'

原稿完整同段：

> The case for new roads rests largely on the assumption that congestion is a shortage of capacity. Yet experience from many large cities suggests otherwise: widening a motorway lowers the cost of driving, which in turn draws additional traffic until the new lanes are as clogged as the old ones. This phenomenon, often described as induced demand, means that road building can become an expensive treadmill. Public transport, by contrast, increases the number of people a corridor can carry without a proportional increase in the space consumed, and a single metro line can relieve pressure on an entire network of streets.

原稿完整同段：

> Equally important are the distributional consequences. Road spending disproportionately benefits those who own cars, whereas frequent and affordable buses and trains extend opportunity to people who cannot or prefer not to drive. Well-designed transit also allows denser, more walkable neighbourhoods to develop around stations, reducing the distances people need to travel in the first place, and it cuts emissions at a time when the transport sector remains one of the most stubborn sources of carbon.

### off · t2-strong · criteria.coherence.issues[0]

判断：**误判**（unsupported_criterion_assignment）。expensive treadmill准确概括反复修路又拥堵的循环，未说明造成何种衔接困难。是否更正式属词汇/语域风格选择，直接列入CC问题依据不足。

模型引文：This phenomenon, often described as induced demand, means that road building can become an expensive treadmill.

模型说明：比喻 'expensive treadmill' 生动但略口语化，与前文较正式的学术语域稍有落差。

模型建议：可改为 'means that road building can become a costly cycle that never resolves congestion.'

原稿完整同段：

> The case for new roads rests largely on the assumption that congestion is a shortage of capacity. Yet experience from many large cities suggests otherwise: widening a motorway lowers the cost of driving, which in turn draws additional traffic until the new lanes are as clogged as the old ones. This phenomenon, often described as induced demand, means that road building can become an expensive treadmill. Public transport, by contrast, increases the number of people a corridor can carry without a proportional increase in the space consumed, and a single metro line can relieve pressure on an entire network of streets.

### off · t2-off-topic · criteria.task.issues[0]

判断：**正确**（supported_with_overstatement）。完全离题判断正确且是核心问题；但“整篇文章因此无法得分”字面过强，结果自身仍给TR3及其他分数。建议表述为未回应题目、TR显著受限。

模型引文：Online learning has grown rapidly over the past decade, and many people now believe that it will eventually replace traditional classrooms.

模型说明：开头引入的是在线学习与课堂教育之争，与公共交通、道路建设毫无关系，整篇文章因此无法得分。

模型建议：必须围绕题目改写，例如：Some people argue that governments should invest in public transport instead of building new roads. In my view, public transport deserves the larger share of funding, although new roads are still needed in some areas.

原稿完整同段：

> Online learning has grown rapidly over the past decade, and many people now believe that it will eventually replace traditional classrooms. In my view, although online courses offer clear advantages, face-to-face education will remain essential.

### off · t2-off-topic · criteria.task.issues[1]

判断：**正确**（supported）。结尾仍讨论在线学习，没有回应交通投资，判断正确。

模型引文：In conclusion, online learning is a valuable supplement that makes education more accessible and flexible

模型说明：结论同样停留在在线学习话题上，没有回应政府投资方向的问题。

模型建议：结论应回到交通投资，例如：In conclusion, governments should prioritise public transport, while road construction should be limited to cases where it is genuinely necessary.

原稿完整同段：

> In conclusion, online learning is a valuable supplement that makes education more accessible and flexible, but it is unlikely to replace traditional classrooms, which offer interaction, support and motivation that technology cannot fully provide.

### off · t2-off-topic · criteria.coherence.issues[0]

判断：**不确定**（criterion_conflation_needs_calibration）。离题事实成立。但CC总述先认可段落清楚、连接自然，随后因错误话题给CC4，可能把TR相关性缺陷重复用于CC；需按评分描述校准，不能仅据此人工审阅断言应得几分。

模型引文：The most obvious benefit of online learning is flexibility.

模型说明：主题句讨论在线学习的灵活性，与题目要求的公共交通或道路建设无关，全文的论证线索因此偏离任务。

模型建议：主题句应直接服务于立场，例如：The clearest argument for public transport is that it moves far more people per unit of road space than private cars.

原稿完整同段：

> The most obvious benefit of online learning is flexibility. Students can watch lectures at any time and study at their own pace, which is especially useful for adults who work full-time or have family responsibilities. Online courses can also reach learners in remote areas who would otherwise have no access to good teachers. In addition, digital materials can be updated quickly, and learners can replay difficult explanations as many times as they need, which is impossible in a traditional lecture. For many people, these features make online study cheaper and more convenient than attending a college in person.

### off · t2-under-length · criteria.task.issues[0]

判断：**正确**（supported）。97词无法充分展开且低于任务要求，反馈与警告有据。2-3句/特定段数属于一种建议写法，不是唯一合格格式。

模型引文：I agree that governments should spend more money on public transport than on new roads.

模型说明：全文仅97词，远低于250词要求，观点无法充分展开，直接压低任务完成度。

模型建议：把每个理由扩展成2-3句：先陈述观点，再解释原因或机制，最后加一个具体或假设的例子，使总词数达到250以上。

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### off · t2-under-length · criteria.task.issues[1]

判断：**正确**（supported_development_feedback）。成本更低的主张缺少为何更便宜的展开，该句虽解释无车人群受益，并未解释相对成本机制；补充机制是合理建议。不能把没有具名案例本身当硬性错误。

模型引文：It is also cheaper for students and old people who do not have cars.

模型说明：该论点只是断言，没有解释为什么便宜、便宜体现在哪里，支撑不足。

模型建议：补充说明，例如：'Because fares are shared among many passengers, a single ticket costs far less than running a car, which matters for students and pensioners on fixed incomes.'

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### off · t2-under-length · criteria.task.issues[2]

判断：**正确**（reasonable_optional_development）。污染减少→环境和健康受益已经有简短联系，可进一步说明呼吸健康；说没有展开可接受，说完全没有支撑则不准确。结构块已改列为可选优化。

模型引文：In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health.

模型说明：污染与健康的关系一带而过，没有展开机制。

模型建议：加一句因果链，例如：'Fewer emissions mean cleaner air, which can reduce respiratory illnesses in crowded cities.'

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### off · t2-under-length · criteria.coherence.issues[0]

判断：**正确**（supported_paragraphing_feedback）。实际仅一段；分开论点与结尾合理。文本已有引入、主体、结尾的功能顺序，不应把没有视觉分段等同没有任何篇章结构。

模型引文：I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time

模型说明：全文仅一段，没有分段，论点、让步和结论混在一起，缺乏清晰的篇章结构。

模型建议：至少分为四段：引言（改写题目+表明立场）、主体段一（环境与拥堵）、主体段二（经济可负担性，或让步段谈乡村道路）、结论段。

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### off · t2-under-length · criteria.coherence.issues[1]

判断：**正确**（supported_but_duplicates_paragraphing）。单独成段可帮助组织，属于前一条同一分段问题，不宜当成独立额外错误重复惩罚。

模型引文：In conclusion, public transport should be the priority, but some roads are still necessary.

模型说明：结论与前面的让步挤在同一段，没有独立成段，收束力度弱。

模型建议：把结论单独成段，先用一句话重申立场，再用一句话概括主要理由，不要引入新信息。

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### off · t1-no-image · criteria.coherence.issues[0]

判断：**正确**（partly_supported_optional_concision）。结尾重提总体增长，精简有价值；但新增C增幅最大/A最小比较，和前概述只说增幅不同并不完全重复。说完全未提供新信息过于绝对，建议把重要比较整合到概述更准确。

模型引文：In summary, while every country saw an increase, the growth was particularly striking in Country C and much more modest in Country A.

模型说明：末段总结与第二段Overall内容高度重复，未提供新信息，显得冗余，削弱了段落推进的有效性。

原稿完整同段：

> Overall, car ownership increased in all four countries over the period, although the size of the rise varied considerably. Country A had the highest level of ownership in both years, while Country D remained the lowest.

原稿完整同段：

> In summary, while every country saw an increase, the growth was particularly striking in Country C and much more modest in Country A.

### off · t1-no-image · criteria.coherence.issues[1]

判断：**过严**（optional_style_overpresented_as_fault）。两个数据段分别用In2000/By2020清楚组织两个年份；平行开头本身不是衔接问题，未展示任何读者理解障碍。可供选择的句式变化不应强制。

模型引文：In 2000, around 70% of households in Country A owned a car, compared with roughly 55% in Country B and about 40% in Country C.

模型说明：数据段以时间状语开头，两个数据段结构雷同（In 2000... / By 2020...），衔接方式略显机械。

原稿完整同段：

> In 2000, around 70% of households in Country A owned a car, compared with roughly 55% in Country B and about 40% in Country C. Country D had by far the lowest figure, at only 15%.

### off · t2-off-topic · argument.problems[0]

判断：**正确**（supported）。正确指出整篇在线教育没有回应交通投资；没有把文内立场一致误当作切题。

模型引文：Online learning has grown rapidly over the past decade, and many people now believe that it will eventually replace traditional classrooms.

模型说明：全文讨论的是在线学习是否会取代传统课堂，而题目问的是政府应投资公共交通还是修建新路，属于完全跑题，这是本文最严重的问题。

模型建议：必须重写全文，围绕公共交通与道路建设的投资取舍展开，例如先表明立场（公共交通应获更多资金，但在必要时仍需修路），再从缓解拥堵、环保、成本效益等角度论证。

原稿完整同段：

> Online learning has grown rapidly over the past decade, and many people now believe that it will eventually replace traditional classrooms. In my view, although online courses offer clear advantages, face-to-face education will remain essential.

### off · t2-under-length · argument.problems[0]

判断：**正确**（reasonable_but_label_stronger_than_comment）。原文确实没有成本机制，因此该批保留的这一条有比旧“农村无理由”更清楚的依据。作为提升空间合理；“没有任何理由支撑”分类仍较重，不能据此要求每个常识性句子都继续证明。

模型引文：It is also cheaper for students and old people who do not have cars.

模型说明：该句只是断言公共交通更便宜，没有说明原因或机制，也没有例子，属于纯断言。

模型建议：补充原因，例如：'Because the cost of a bus or train trip is shared by dozens of passengers, a ticket is far cheaper than running a car, which matters for students and pensioners.'

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### off · t2-weak · argument.improvements[0]

判断：**正确**（reasonable_optional_expansion）。建议进一步明确改善公交→少用私车可用，但同段已有改善→更多使用→少拥堵；作为可选而非缺失问题，较上一批好转。

模型引文：In my city the bus is always late and very crowd so people dont like to take it.

模型说明：可进一步说明改善公交后如何具体减少私家车使用，使论证更有层次。

原稿完整同段：

> Firstly, public transport is good for people. Because many people dont have car and they need bus and train to go work and school. If the bus is more better, people will use it more and the traffic will be less. In my city the bus is always late and very crowd so people dont like to take it. Also the train is too expensive for student. So goverment should make it cheap and more fast.

### off · t2-weak · argument.improvements[1]

判断：**正确**（reasonable_optional_expansion）。通勤时间浪费到经济损失可进一步展开，作为可选合理。

模型引文：This is very bad for him and for the economy also.

模型说明：可补充一句解释为何个人通勤时间浪费会影响经济，使例子与观点联系更紧密。

原稿完整同段：

> Secondly, new road is also important. Because the city is grow and more people buy car every year. If there is no new road the traffic jam will be very bad and people waste a lot of time. For example my father drive to work everyday and he spend two hour in the road. This is very bad for him and for the economy also.

### off · t2-mid · argument.improvements[0]

判断：**正确**（reasonable_optional_expansion）。环境段可举假设例子深化，不要求统计数据或具名城市。

模型引文：Public transport produces less pollution per passenger, so it is a more sustainable option in the long term.

模型说明：可补充一个假设例子或机制说明，使环境论点更有说服力。

原稿完整同段：

> Another advantage is the environment. Cars produce a lot of air pollution and carbon emissions, which are harmful to people's health and contribute to climate change. Public transport produces less pollution per passenger, so it is a more sustainable option in the long term.

### off · t2-mid · argument.improvements[1]

判断：**正确**（potentially_redundant_optional）。原文结尾已经重申公交优先及公交不实际地区修路；再写一遍原则是可选，不是遗漏。

模型引文：On the other hand, new roads are sometimes needed.

模型说明：可加一句说明为何这些情况不改变“公交优先”的总原则，使让步与主论点衔接更紧。

原稿完整同段：

> On the other hand, new roads are sometimes needed. In rural areas, there are not enough passengers to make train lines profitable, so people depend on cars. Also, goods are mostly transported by trucks, and poor roads can slow down the economy.

### off · t2-good · argument.improvements[0]

判断：**过严**（redundant_context_unread）。建议补充机制与同一句as cheaper and faster journeys已有内容重叠，说明即使列为可选仍会忽略上下文。

模型引文：there is considerable evidence that new roads tend to fill up quickly

模型说明：可补充一句机制说明，例如 'because extra capacity lowers journey times and attracts drivers who previously used other routes'，使“证据”更具体。

原稿完整同段：

> The strongest argument for prioritising public transport is efficiency. Roads are an inherently limited resource: a lane of motorway can carry only a fixed number of private vehicles per hour, whereas a well-run rail or bus rapid transit line can move many times that number of people in the same space. Moreover, there is considerable evidence that new roads tend to fill up quickly, as cheaper and faster journeys encourage more people to drive. Expanding road networks may therefore offer only temporary relief before congestion returns.

### off · t2-good · argument.improvements[1]

判断：**正确**（reasonable_optional_expansion）。低收入者就业可举假设例子，作为可选生动化合理；原文已有widening access to jobs因果，不要求再举例才算成立。

模型引文：It gives affordable mobility to those who cannot drive, such as students, the elderly and lower-income workers

模型说明：可加一个假设性例子，如某位低收入工人因公交线路延伸而获得更远的工作机会，使论证更生动。

原稿完整同段：

> Public transport also brings wider social and environmental benefits. It gives affordable mobility to those who cannot drive, such as students, the elderly and lower-income workers, thereby widening their access to jobs and services. At the same time, shifting journeys from cars to trains and buses reduces both air pollution and greenhouse gas emissions, which is increasingly important as cities attempt to meet climate targets.

### off · t2-strong · argument.improvements[0]

判断：**正确**（reasonable_optional_expansion）。补乡村交通替代困难可增强说明，但现有依赖公路已经给出理由，不属于矛盾或无理由。

模型引文：Rural communities and freight logistics depend on reliable highways, and in such contexts targeted upgrades may represent genuine value for money.

模型说明：可补一句说明为何这些情形公交难以替代，使让步更有分量。

原稿完整同段：

> That said, a blanket refusal to build roads would be misguided. Rural communities and freight logistics depend on reliable highways, and in such contexts targeted upgrades may represent genuine value for money.

### off · t2-strong · argument.improvements[1]

判断：**正确**（reasonable_optional_expansion）。细化人均排放可以提升具体性，现有城市形态/出行距离机制不应被忽略。

模型引文：it cuts emissions at a time when the transport sector remains one of the most stubborn sources of carbon

模型说明：补充减排机制（人均能耗更低、替代私家车出行），使环境论点更具体。

原稿完整同段：

> Equally important are the distributional consequences. Road spending disproportionately benefits those who own cars, whereas frequent and affordable buses and trains extend opportunity to people who cannot or prefer not to drive. Well-designed transit also allows denser, more walkable neighbourhoods to develop around stations, reducing the distances people need to travel in the first place, and it cuts emissions at a time when the transport sector remains one of the most stubborn sources of carbon.

### off · t2-off-topic · argument.improvements[0]

判断：**正确**（supported_rewrite_direction）。明确标注需换成题目话题，改立场和内容的方向正确。

模型引文：In my view, although online courses offer clear advantages, face-to-face education will remain essential.

模型说明：若换成题目话题，可写成：In my view, governments should give priority to public transport, although building some new roads may still be necessary in certain areas. 这样既表明立场，又为后文的分情况讨论留出空间。

原稿完整同段：

> Online learning has grown rapidly over the past decade, and many people now believe that it will eventually replace traditional classrooms. In my view, although online courses offer clear advantages, face-to-face education will remain essential.

### off · t2-under-length · argument.improvements[0]

判断：**正确**（reclassification_reasonable_semantic_limit）。污染低→环境健康有简短联系，作为可选深化合理。但support仅引用原断言的一部分，存在同段引文不能证明有效支撑这一已披露局限，不把reclassified1算独立语义证明。

模型引文：In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health.

模型说明：把比较和后果连起来，例如：'Since one bus replaces dozens of cars, emissions per passenger fall sharply, which means cleaner air and fewer respiratory problems in crowded cities.'

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### off · t2-under-length · argument.improvements[1]

判断：**正确**（reasonable_optional_expansion）。认可现有载客量→拥堵机制，再给假设例子作为选项合理。

模型引文：Public transport can carry many people at the same time, so it reduces traffic jams in big cities.

模型说明：这是全文最完整的论证，可再补一个具体或假设的例子，如高峰时段一列地铁替代数百辆私家车，使论证更有说服力。

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### off · t2-under-length · argument.improvements[2]

判断：**正确**（potentially_redundant_optional）。乡村where notmanybuses已有理由；下一句结论已经公交优先+保留道路。建议另加回扣可选，并非缺失。

模型引文：However, new roads are still useful in the countryside, where there are not many buses.

模型说明：让步之后可加一句回到立场，如 'but in cities the same money would serve far more people if it were spent on buses and trains'，使让步与主张衔接更紧。

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### high · t2-weak · criteria.task.issues[0]

判断：**正确**（supported_precision_feedback）。建路必然制造更多车/污染表述过强，补诱导驾车机制和can限定合理，比泛称无支撑更具体。

模型引文：Because the road make more car and more pollution.

模型说明：把建路直接说成“制造更多汽车和污染”，因果过强且没有解释机制，作为核心对比理由显得武断。

模型建议：改为限定表述，如 'More roads can encourage car use and increase pollution'，并补一句机制（更多车道可能诱导驾车出行）。

原稿完整同段：

> But I think public transport is more important than road. Because the road make more car and more pollution. The public transport can carry many people in one time and it is good for enviroment. Also if more people take bus, the city will be more quiet and the air will be more clean, so everybody can be more healthy and happy.

### high · t2-weak · criteria.task.issues[1]

判断：**正确**（supported）。everybody健康快乐过度概括，限定公共健康收益合理；原文已有空气变干净到健康联系，批评针对范围而非否认因果。

模型引文：so everybody can be more healthy and happy.

模型说明：从公交使用直接推到“所有人更健康快乐”，结论过宽，缺少限定，削弱论证可信度。

模型建议：改为 'this can improve air quality and benefit public health' 等有限定好处的表达，不要保证所有人都更健康快乐。

原稿完整同段：

> But I think public transport is more important than road. Because the road make more car and more pollution. The public transport can carry many people in one time and it is good for enviroment. Also if more people take bus, the city will be more quiet and the air will be more clean, so everybody can be more healthy and happy.

### high · t2-weak · criteria.coherence.issues[0]

判断：**正确**（supported）。Because从句被句号分隔是明确片段句/连接问题；合并修改有直接依据。

模型引文：Firstly, public transport is good for people. Because many people dont have car and they need bus and train to go work and school.

模型说明：Because 从句被句号独立成句，句间逻辑连接不自然；段落衔接依赖简单连接词。

模型建议：合并为 'Firstly, public transport is good for people because many people do not have cars and need buses and trains to go to work or school.'

原稿完整同段：

> Firstly, public transport is good for people. Because many people dont have car and they need bus and train to go work and school. If the bus is more better, people will use it more and the traffic will be less. In my city the bus is always late and very crowd so people dont like to take it. Also the train is too expensive for student. So goverment should make it cheap and more fast.

### high · t2-weak · criteria.coherence.issues[1]

判断：**过严**（optional_style_overpresented_as_fault）。Also确有重复，可建议更多句法连接；单把Also换In addition不必然更自然，属于风格优化而非明确错误。

模型引文：Also the train is too expensive for student.

模型说明：连接手段范围窄，Also/So/But 反复出现，推进方式偏机械。

模型建议：改用 'In addition'、'This is particularly important for students, who...' 等更自然的衔接，并合并短句。

原稿完整同段：

> Firstly, public transport is good for people. Because many people dont have car and they need bus and train to go work and school. If the bus is more better, people will use it more and the traffic will be less. In my city the bus is always late and very crowd so people dont like to take it. Also the train is too expensive for student. So goverment should make it cheap and more fast.

### high · t2-weak · argument.problems[0]

判断：**正确**（supported_precision_feedback）。限定因果强度的建议合理；不能因此要求所有常识观点另有具名案例。

模型引文：Because the road make more car and more pollution.

模型说明：把道路建设直接等同于“制造更多汽车和污染”，缺乏限定和机制，作为支持公共交通优先的理由略显绝对。

模型建议：改为 'More roads can encourage car use and worsen pollution'，并补充一句机制，如更多车道可能诱导驾车出行。

原稿完整同段：

> But I think public transport is more important than road. Because the road make more car and more pollution. The public transport can carry many people in one time and it is good for enviroment. Also if more people take bus, the city will be more quiet and the air will be more clean, so everybody can be more healthy and happy.

### high · t2-weak · argument.problems[1]

判断：**正确**（supported）。所有人更健康快乐的概括明显过宽，定位比off宽泛缺机制更准确。

模型引文：so everybody can be more healthy and happy.

模型说明：从公交使用直接推出所有人更健康快乐，结论过宽，削弱论证可信度。

模型建议：限定为 'this can improve air quality and public health' 或指出对居民健康的潜在好处，而非保证所有人幸福。

原稿完整同段：

> But I think public transport is more important than road. Because the road make more car and more pollution. The public transport can carry many people in one time and it is good for enviroment. Also if more people take bus, the city will be more quiet and the air will be more clean, so everybody can be more healthy and happy.

### high · t2-weak · argument.improvements[0]

判断：**正确**（supported_precision_feedback）。开篇保留意见具体化合理。

模型引文：I am agree with this opinion in some way but not all.

模型说明：开头直接说明保留在哪：优先投资公共交通，但道路在必要时仍需建设，使立场从首段就清晰。

原稿完整同段：

> Nowadays transport is very important problem in many country. Some people think goverment should spend money for public transport not for build new road. I am agree with this opinion in some way but not all.

### high · t2-weak · argument.improvements[1]

判断：**正确**（reasonable_optional_expansion）。原文载客量理由可以加比较；作为可选合理。

模型引文：The public transport can carry many people in one time and it is good for enviroment.

模型说明：加入具体比较或假设例子，如一辆公交车可替代多辆私家车，从而减少道路占用和尾气。

原稿完整同段：

> But I think public transport is more important than road. Because the road make more car and more pollution. The public transport can carry many people in one time and it is good for enviroment. Also if more people take bus, the city will be more quiet and the air will be more clean, so everybody can be more healthy and happy.

### high · t2-weak · argument.improvements[2]

判断：**过严**（redundant_context_unread）。结论上一句已经more money for public transport but also some road，重新点明优先顺序是重复要求；该句语法确需修正。

模型引文：Both is important for the people and the country develop.

模型说明：结论可再次点明优先顺序（公共交通为主、道路为辅），并修正该句语法，使收束更有力。

原稿完整同段：

> In conclusion, I think goverment should spend more money for public transport but also build some road when it is necessary. Both is important for the people and the country develop.

### high · t2-mid · criteria.task.issues[0]

判断：**正确**（reasonable_optional_qualification）。货运范围未限定，可建议in many countries，但mostly本来已留余地；并不证明原断言事实错误。相比off否认道路理由更具体。

模型引文：Also, goods are mostly transported by trucks, and poor roads can slow down the economy.

模型说明：“most goods are transported by trucks”是一个未加限定的全局性断言，读者可能质疑其适用范围，属于轻度过度概括，削弱了让步段的说服力。

模型建议：改成有保留的表述，如 “in many countries a large share of freight is moved by truck, so poor roads can slow the economy”，使论断更稳妥。

原稿完整同段：

> On the other hand, new roads are sometimes needed. In rural areas, there are not enough passengers to make train lines profitable, so people depend on cars. Also, goods are mostly transported by trucks, and poor roads can slow down the economy.

### high · t2-mid · criteria.task.issues[1]

判断：**不确定**（partly_supported_with_unsourced_numeric_advice）。环境段可深化，但原文已有per passenger比较；建议新增about forty times的40倍具体数量关系，无原稿/题目来源，也未标明纯假设，不能直接给学生当可靠支撑。

模型引文：Public transport produces less pollution per passenger, so it is a more sustainable option in the long term.

模型说明：环境段只有两句话的推理，没有具体化（例如按人均排放比较或举一个城市空气改善的情形），论证展开明显弱于第二段，使整体论证深度不均衡。

模型建议：补一句比较或后果，如 “because a full bus carries about forty times as many people as a car using only a fraction of the fuel per person”，让环境论点同样“落地”。

原稿完整同段：

> Another advantage is the environment. Cars produce a lot of air pollution and carbon emissions, which are harmful to people's health and contribute to climate change. Public transport produces less pollution per passenger, so it is a more sustainable option in the long term.

### high · t2-mid · criteria.coherence.issues[0]

判断：**过严**（optional_style_overpresented_as_fault）。两段并列不同收益有合理组织逻辑，主题句Another advantage本身无错；更均衡篇幅可优化，不应强制例子或递进模式。

模型引文：Another advantage is the environment.

模型说明：段落以“Another advantage is…”这种模板化短语开头，且该段仅两句、缺少例证或展开，与前后段的信息密度落差明显，读起来像清单而非连贯论证。

模型建议：改为带逻辑关系的主题句，如 “Investment in public transport also brings environmental benefits that roads cannot match.”，并在段内加一句展开或比较，使段落自然承接上一段。

原稿完整同段：

> Another advantage is the environment. Cars produce a lot of air pollution and carbon emissions, which are harmful to people's health and contribute to climate change. Public transport produces less pollution per passenger, so it is a more sustainable option in the long term.

### high · t2-mid · argument.improvements[0]

判断：**正确**（reasonable_optional_expansion）。三到四句是一种扩展方案，不能作为固定合格规则；已有因果不是无理由。

模型引文：Another advantage is the environment.

模型说明：把该段扩写到三到四句：先说明私家车的人均排放更高，再补一个比较或后果（例如空气质量、长期医疗成本），使环境论证与效率论证同样有分量。

原稿完整同段：

> Another advantage is the environment. Cars produce a lot of air pollution and carbon emissions, which are harmful to people's health and contribute to climate change. Public transport produces less pollution per passenger, so it is a more sustainable option in the long term.

### high · t2-mid · argument.improvements[1]

判断：**过严**（partly_redundant_optional）。加范围限定合理，但原句紧接poor roads can slow down economy已写后果，要求紧接后果说明忽略现有内容。

模型引文：Also, goods are mostly transported by trucks

模型说明：为这一全局论断加上限定语（如 in most countries / a large proportion of freight），并紧接一句后果说明，让步段会更稳妥也更有说服力。

原稿完整同段：

> On the other hand, new roads are sometimes needed. In rural areas, there are not enough passengers to make train lines profitable, so people depend on cars. Also, goods are mostly transported by trucks, and poor roads can slow down the economy.

### high · t2-mid · argument.improvements[2]

判断：**正确**（reasonable_optional_expansion）。人口密度和成本已在乡村段说明；结论可具体化，但不是缺失标准或必须重复。

模型引文：However, they should still build roads in places where public transport is not practical.

模型说明：结论可再点明判断标准（如人口密度或成本效益），让“不实际”这一限定更具体，例如 “in sparsely populated areas where running frequent services would not be cost-effective”。

原稿完整同段：

> In conclusion, I agree that governments should give priority to public transport because it is more efficient and better for the environment. However, they should still build roads in places where public transport is not practical.

### high · t2-good · criteria.task.issues[0]

判断：**正确**（improved_but_optional）。high明确承认随后已有机制，关闭off的字面错误；对considerable evidence概括程度可以优化，但建议因果仍重复原句，不应将未给具体统计视作必然扣分。

模型引文：there is considerable evidence that new roads tend to fill up quickly

模型说明：“considerable evidence”只是声称有证据，没有说明证据类型或具体表现；随后虽给出机制解释，整体仍偏笼统。

模型建议：可改为一句假设性说明，如“当新增道路缩短通勤时间，更多人会选择驾车，新增容量很快被抵消”，把证据落到实处，不必编造真实统计。

原稿完整同段：

> The strongest argument for prioritising public transport is efficiency. Roads are an inherently limited resource: a lane of motorway can carry only a fixed number of private vehicles per hour, whereas a well-run rail or bus rapid transit line can move many times that number of people in the same space. Moreover, there is considerable evidence that new roads tend to fill up quickly, as cheaper and faster journeys encourage more people to drive. Expanding road networks may therefore offer only temporary relief before congestion returns.

### high · t2-good · criteria.coherence.issues[0]

判断：**过严**（optional_style_overpresented_as_fault）。已承认连接词准确，仅因常见就归为套路/未够8分，缺少明确衔接困难证据；高分判断需教师校准。

模型引文：At the same time, shifting journeys from cars to trains and buses

模型说明：该处及“Moreover”“Nevertheless”等连接词准确，但属于常见套路，段落衔接略显程式化。

模型建议：可更多用关键词复现或指代来衔接，如重复“public transport investment”“road capacity”等核心词，减少对固定连接词的依赖。

原稿完整同段：

> Public transport also brings wider social and environmental benefits. It gives affordable mobility to those who cannot drive, such as students, the elderly and lower-income workers, thereby widening their access to jobs and services. At the same time, shifting journeys from cars to trains and buses reduces both air pollution and greenhouse gas emissions, which is increasingly important as cities attempt to meet climate targets.

### high · t2-good · argument.improvements[0]

判断：**过严**（redundant_context_unread）。建议更便宜更快→更多驾驶→容量被抵消与同段原机制基本一致；比off改进在于不再否认原机制。

模型引文：there is considerable evidence that new roads tend to fill up quickly

模型说明：把“大量证据”具体化为一句假设性因果说明，例如新增道路缩短通勤时间后更多人驾车，新增容量很快被抵消；不必编造真实城市或统计。

原稿完整同段：

> The strongest argument for prioritising public transport is efficiency. Roads are an inherently limited resource: a lane of motorway can carry only a fixed number of private vehicles per hour, whereas a well-run rail or bus rapid transit line can move many times that number of people in the same space. Moreover, there is considerable evidence that new roads tend to fill up quickly, as cheaper and faster journeys encourage more people to drive. Expanding road networks may therefore offer only temporary relief before congestion returns.

### high · t2-good · argument.improvements[1]

判断：**正确**（reasonable_optional_expansion）。低收入通勤者假设情境作为可选生动化可用，不能反推现有解释不足。

模型引文：It gives affordable mobility to those who cannot drive

模型说明：可补一个简短假设情境，如依赖公交去远处工作的低收入通勤者，使社会效益更有画面感。

原稿完整同段：

> Public transport also brings wider social and environmental benefits. It gives affordable mobility to those who cannot drive, such as students, the elderly and lower-income workers, thereby widening their access to jobs and services. At the same time, shifting journeys from cars to trains and buses reduces both air pollution and greenhouse gas emissions, which is increasingly important as cities attempt to meet climate targets.

### high · t2-good · argument.improvements[2]

判断：**正确**（optional_style_feedback）。长短句节奏是选择；该长句清晰，不是错误。

模型引文：Roads are an inherently limited resource: a lane of motorway can carry only a fixed number of private vehicles per hour

模型说明：偶尔把长句拆成短句，形成节奏变化，避免全文句式过于均匀。

原稿完整同段：

> The strongest argument for prioritising public transport is efficiency. Roads are an inherently limited resource: a lane of motorway can carry only a fixed number of private vehicles per hour, whereas a well-run rail or bus rapid transit line can move many times that number of people in the same space. Moreover, there is considerable evidence that new roads tend to fill up quickly, as cheaper and faster journeys encourage more people to drive. Expanding road networks may therefore offer only temporary relief before congestion returns.

### high · t2-strong · criteria.task.issues[0]

判断：**过严**（optional_expansion_overpresented_as_fault）。原文已给无现实替代、乡村与货运依赖公路的标准。更操作性例子可选，不要求让步段与主论证等长，短不能自动等于论证失衡。

模型引文：Rural communities and freight logistics depend on reliable highways, and in such contexts targeted upgrades may represent genuine value for money.

模型说明：让步段只有两句，虽然给出了理由，但没有说明“在什么条件下修路才划算”的判断标准，与前两个主体段相比开发明显偏薄，使全文论证重心略有失衡。

模型建议：补一句判断标准或简短例证，例如“当一条公路是某地区通往医院或港口的唯一通道时，升级改造的收益才足以抵消其带来的新增车流”。

原稿完整同段：

> That said, a blanket refusal to build roads would be misguided. Rural communities and freight logistics depend on reliable highways, and in such contexts targeted upgrades may represent genuine value for money.

### high · t2-strong · criteria.coherence.issues[0]

判断：**不确定**（debatable_coherence_feedback）。主题句distributional consequences与后面的环境收益范围不同，扩展主题句有一定依据；但同句通过walkable→shorter journeys过渡，且已有and，称没有任何过渡/突然切换过强。

模型引文：and it cuts emissions at a time when the transport sector remains one of the most stubborn sources of carbon

模型说明：该段主题句讲的是“分配后果”，此处却突然转向环境议题，且没有任何过渡词标示话题切换，段内一致性因此被削弱。

模型建议：要么在段首主题句中并列写出“公平与环境”两条线索，要么把排放论点单独成段或移入上一段，用 In addition 之类明确标示。

原稿完整同段：

> Equally important are the distributional consequences. Road spending disproportionately benefits those who own cars, whereas frequent and affordable buses and trains extend opportunity to people who cannot or prefer not to drive. Well-designed transit also allows denser, more walkable neighbourhoods to develop around stations, reducing the distances people need to travel in the first place, and it cuts emissions at a time when the transport sector remains one of the most stubborn sources of carbon.

### high · t2-strong · argument.improvements[0]

判断：**过严**（optional_expansion_overpresented_as_fault）。判断门槛可深化，但让步与支持段分量相当不是必要原则；避免机械加长。

模型引文：Rural communities and freight logistics depend on reliable highways, and in such contexts targeted upgrades may represent genuine value for money.

模型说明：可补一个判断门槛或清晰假设的例子，例如“当某条公路是偏远地区通往医院或港口的唯一通道时，升级才值得优先投入”，让例外条款更具操作性，也让让步段与前两段分量相当。

原稿完整同段：

> That said, a blanket refusal to build roads would be misguided. Rural communities and freight logistics depend on reliable highways, and in such contexts targeted upgrades may represent genuine value for money.

### high · t2-strong · argument.improvements[1]

判断：**正确**（reasonable_optional_expansion）。人均排放机制可补充；不应忽略同段缩短出行距离机制。

模型引文：and it cuts emissions at a time when the transport sector remains one of the most stubborn sources of carbon

模型说明：可补一句机制，如“因为同样客运量下轨道与公交的人均排放远低于私家车”，把断言升级为可验证的推理。

原稿完整同段：

> Equally important are the distributional consequences. Road spending disproportionately benefits those who own cars, whereas frequent and affordable buses and trains extend opportunity to people who cannot or prefer not to drive. Well-designed transit also allows denser, more walkable neighbourhoods to develop around stations, reducing the distances people need to travel in the first place, and it cuts emissions at a time when the transport sector remains one of the most stubborn sources of carbon.

### high · t2-strong · argument.improvements[2]

判断：**正确**（reasonable_optional_expansion）。首尾城市形态呼应可选；结论现已总结社会环境收益，没有遗漏必需内容。

模型引文：How a government allocates its transport budget shapes not only how quickly people travel, but also the kind of cities they live in.

模型说明：结论可回扣开篇“城市形态”这一框架（例如说明公交投资如何塑造更紧凑的城市），形成首尾呼应，使全文更完整。

原稿完整同段：

> How a government allocates its transport budget shapes not only how quickly people travel, but also the kind of cities they live in. Although there is an intuitive appeal to building new roads whenever traffic worsens, I am convinced that investment should be weighted decisively towards public transport, with road construction reserved for cases where no realistic alternative exists.

### high · t2-off-topic · criteria.task.issues[0]

判断：**正确**（supported）。线上教育与交通资金取舍完全无关，判断正确。

模型引文：The most obvious benefit of online learning is flexibility.

模型说明：主体段讨论线上学习的时间灵活性、对偏远地区学习者的可及性和数字教材的更新速度，与“公共交通 vs 新修道路”的政府支出话题毫无关系，属于典型的答非所问。

模型建议：整篇重写：开头明确表态（例如“我认为政府应优先投资公共交通，但在必要路段仍需修路”），主体段分别论证公共交通在缓解拥堵、减少排放、单位成本更低等方面的优势，并回应“修路”一方。

原稿完整同段：

> The most obvious benefit of online learning is flexibility. Students can watch lectures at any time and study at their own pace, which is especially useful for adults who work full-time or have family responsibilities. Online courses can also reach learners in remote areas who would otherwise have no access to good teachers. In addition, digital materials can be updated quickly, and learners can replay difficult explanations as many times as they need, which is impossible in a traditional lecture. For many people, these features make online study cheaper and more convenient than attending a college in person.

### high · t2-off-topic · criteria.task.issues[1]

判断：**正确**（supported）。让步论证属于另一题，判断正确。

模型引文：However, classroom learning provides things that are difficult to replicate on a screen.

模型说明：这是针对线上学习给出的让步与反驳，同样属于另一道题的论证线，对本题的立场没有提供任何支持。

模型建议：把这一段改为针对反方（修路）的让步段，例如承认“在人口分散地区，新建道路确实能改善连通性”，然后再说明为何总体上公共交通更值得投入。

原稿完整同段：

> However, classroom learning provides things that are difficult to replicate on a screen. Teachers can notice immediately when a student is confused and adapt their explanations. Students also develop social skills by working together, discussing ideas and building friendships, which are an important part of education, particularly for children.

### high · t2-off-topic · criteria.task.issues[2]

判断：**正确**（supported）。结论未回交通主题，判断正确。

模型引文：In conclusion, online learning is a valuable supplement that makes education more accessible and flexible

模型说明：结论段同样落在错误话题上，没有回到公共交通与道路建设的取舍，因此无法弥补任务回应上的缺失。

模型建议：结论应重申“我同意把大部分资金用于公共交通，但在必要路段保留修路预算”，并概括主体段的两个理由。

原稿完整同段：

> In conclusion, online learning is a valuable supplement that makes education more accessible and flexible, but it is unlikely to replace traditional classrooms, which offer interaction, support and motivation that technology cannot fully provide.

### high · t2-off-topic · criteria.coherence.issues[0]

判断：**过严**（optional_structure_overpresented_as_fault）。动机段含自律障碍和低完成率例证，和前段互动/社交是不同侧面，可独立成段；短或同向并不必然不连贯。

模型引文：Furthermore, many learners find it hard to stay motivated without the structure of a timetable

模型说明：该段只有两句，内容与第三段同属“课堂不可替代”的论证方向，独立成段使主体段落轻重失衡。

模型建议：并入上一段，作为该段最后一个小论点；或者补上一个具体例子（如某类线上课程辍学率高）使其独立成段更站得住。

原稿完整同段：

> Furthermore, many learners find it hard to stay motivated without the structure of a timetable and the presence of classmates. Completion rates for many free online courses are notoriously low, which suggests that self-discipline is a serious obstacle.

### high · t2-off-topic · criteria.coherence.issues[1]

判断：**误判**（clear_context_false_positive）。Furthermore在第四段开头，非所引第二段内连续出现。第二段还有which/these features等指代，概括成连续递进堆叠忽略实际组织。

模型引文：In addition, digital materials can be updated quickly

模型说明：段内连续使用“also / In addition / Furthermore”这类递进连接词，衔接手段略显机械，句间关系更多靠连接词而非指代或逻辑词。

模型建议：尝试用指代和逻辑关系衔接，例如“This flexibility matters most for…”，减少连接词的数量。

原稿完整同段：

> The most obvious benefit of online learning is flexibility. Students can watch lectures at any time and study at their own pace, which is especially useful for adults who work full-time or have family responsibilities. Online courses can also reach learners in remote areas who would otherwise have no access to good teachers. In addition, digital materials can be updated quickly, and learners can replay difficult explanations as many times as they need, which is impossible in a traditional lecture. For many people, these features make online study cheaper and more convenient than attending a college in person.

### high · t2-off-topic · argument.problems[0]

判断：**正确**（supported_with_score_limit_caveat）。整体离题正确；TR无法超过3的固定上限措辞需依据评分标准校准，本审阅不确认官方规则。

模型引文：In my view, although online courses offer clear advantages, face-to-face education will remain essential.

模型说明：全文的核心立场与题目要求讨论的话题完全不同：题目问政府资金的优先投向，文章谈教育形式。这属于整体性跑题，Task Response 无法超过3分。

模型建议：动笔前先圈出题目的关键词（governments、spend money、public transport、new roads），再写一句“我的立场是……因为A和B”确认不偏题，然后开始写。

原稿完整同段：

> Online learning has grown rapidly over the past decade, and many people now believe that it will eventually replace traditional classrooms. In my view, although online courses offer clear advantages, face-to-face education will remain essential.

### high · t2-off-topic · argument.problems[1]

判断：**正确**（supported_duplicate_finding）。主体偏题事实正确，但和全文离题是同一核心问题，不应按三条数量解释为三个独立缺陷。

模型引文：The most obvious benefit of online learning is flexibility.

模型说明：两个主体段所举的理由（灵活性、可及性、成本、课堂互动、学习动机）虽然展开充分，但全是另一道题的论据，对本题立场没有任何支撑作用。

模型建议：把同样的“优势/局限/结论”结构平移到正确话题上：公共交通的优势（缓解拥堵、减少污染、运量大、单位成本低）与修路的局限（诱导更多车流、占用土地、维护成本高）。

原稿完整同段：

> The most obvious benefit of online learning is flexibility. Students can watch lectures at any time and study at their own pace, which is especially useful for adults who work full-time or have family responsibilities. Online courses can also reach learners in remote areas who would otherwise have no access to good teachers. In addition, digital materials can be updated quickly, and learners can replay difficult explanations as many times as they need, which is impossible in a traditional lecture. For many people, these features make online study cheaper and more convenient than attending a college in person.

### high · t2-off-topic · argument.problems[2]

判断：**正确**（supported_duplicate_finding）。结尾仍离题正确，属于同一整体偏题问题。

模型引文：In conclusion, online learning is a valuable supplement that makes education more accessible and flexible

模型说明：结论段继续停留在错误话题上，使整篇文章从头到尾都没有回应题目，进一步锁死了任务回应分数。

模型建议：结论必须回到“公共交通 vs 修路”的取舍，用一句话重申立场并概括两段的主要理由。

原稿完整同段：

> In conclusion, online learning is a valuable supplement that makes education more accessible and flexible, but it is unlikely to replace traditional classrooms, which offer interaction, support and motivation that technology cannot fully provide.

### high · t2-off-topic · argument.improvements[0]

判断：**正确**（supported_rewrite_direction）。改用交通题的限定立场可用，全文仍需围绕该题重写，不能只换开头。

模型引文：In my view, although online courses offer clear advantages, face-to-face education will remain essential.

模型说明：这句话的“让步+保留立场”结构其实很适合本题，只需换成：Although building new roads may be necessary in some areas, I believe governments should direct most of their transport budget to public transport.

原稿完整同段：

> Online learning has grown rapidly over the past decade, and many people now believe that it will eventually replace traditional classrooms. In my view, although online courses offer clear advantages, face-to-face education will remain essential.

### high · t2-under-length · criteria.task.issues[0]

判断：**误判**（clear_context_false_positive）。乡村where notmanybuses给出理由，紧接结尾publictransportpriority给出分量关系；说没有主旨关系忽略同段结尾。增加展开可选，97词限制另有真实依据。

模型引文：However, new roads are still useful in the countryside, where there are not many buses.

模型说明：让步部分只有一句话，既没有说明这与主旨的分量关系，也没有进一步展开，导致论证非常单薄。

模型建议：把让步写成独立一段：先承认乡村地区公交覆盖率低、道路不可替代，再回到立场说明城市资金应以公交为主，形成'让步—回应'的完整链条。

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### high · t2-under-length · criteria.task.issues[1]

判断：**过严**（partly_supported_overstated）。更低成本对无车学生老人有显见可负担性联系，进一步解释公平/支出合理；说没有任何投资理由过强。

模型引文：It is also cheaper for students and old people who do not have cars.

模型说明：论点只是被陈述，没有说明为什么这构成政府应投资公交的理由（例如补贴公平、减少家庭交通支出）。

模型建议：补一句机制或后果，例如 'This means low-income families can travel to work and school without buying a car, which makes transport more equal.'

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### high · t2-under-length · criteria.task.issues[2]

判断：**正确**（supported）。97词与展开不足是有据的核心问题；260–290词目标保留正确，主题句+解释+例子是示例路线非唯一格式。

模型引文：In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health.

模型说明：全文约97词，三大论点平均只有一句，字数严重不足会直接限制任务回应分数。

模型建议：将每个论点扩展为'主题句＋解释＋例子'的三句结构，正文两段，总词数达到260–290词。

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### high · t2-under-length · criteria.coherence.issues[0]

判断：**正确**（supported）。只有一个自然段，分段建议有据；原文功能顺序存在，不等于逻辑完全不清楚。

模型引文：I agree that governments should spend more money on public transport than on new roads.

模型说明：全文只有一段，引言、主体、让步、结论挤在一起，缺少段落划分，读者无法从版面上看出论证层次。

模型建议：拆成四段：引言（改写题目＋表明立场）—主体1（缓解拥堵与公平）—主体2（环境）＋让步（乡村道路）—结论。

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### high · t2-under-length · criteria.coherence.issues[1]

判断：**误判**（clear_context_false_positive）。原文第二句已经in big cities，最后however转农村且有where从句；说前文没有任何城市/乡村铺垫与原文不符。

模型引文：However, new roads are still useful in the countryside

模型说明：转折出现得很突然，前文没有任何铺垫说明'城市/乡村'这一区分标准。

模型建议：在让步前加一句范围限定，例如 'This is especially true in cities, where most journeys are short.'，再引出乡村例外，逻辑会更顺。

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### high · t2-under-length · argument.improvements[0]

判断：**正确**（reasonable_optional_expansion）。增加可负担性的假设例子合理。

模型引文：It is also cheaper for students and old people who do not have cars.

模型说明：补一个假设性或生活化的例子，例如 'A student in a city with a reliable metro can travel to school for a fraction of the cost of driving, so investment in buses and trains helps those who can least afford a car.'

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### high · t2-under-length · argument.improvements[1]

判断：**不确定**（redundant_with_unsourced_generalization）。紧接结尾已经公交优先+保留道路；建议重申仍属重复，而且most journeys are made in cities是新增无来源经验性断言，不宜当事实兜底。

模型引文：However, new roads are still useful in the countryside, where there are not many buses.

模型说明：让步后明确回到立场，说明为什么总体仍应优先公交，例如 'Nevertheless, most journeys are made in cities, so the largest share of funding should still go to public transport.'

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### high · t2-under-length · argument.improvements[2]

判断：**正确**（reasonable_optional_expansion）。认可原有载客量→少拥堵，进一步比较可选；不应把现有机制算无展开。

模型引文：Public transport can carry many people at the same time, so it reduces traffic jams in big cities.

模型说明：把这一句当作主体段主题句，后面再补'机制＋结果'两句，如对比一条车道上公交车与小汽车的单位载客量，从而支撑'公交比修路更高效'的判断。

原稿完整同段：

> I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary.

### high · t1-no-image · criteria.coherence.issues[0]

判断：**误判**（clear_context_false_positive）。概述只说各国均增长且增幅不同、A最高/D最低，没有说C增幅最大。称C最大已经写在第二段是具体事实错误；整合概述可建议，但不是完全重复。

模型引文：In summary, while every country saw an increase, the growth was particularly striking in Country C

模型说明：结尾段重复了第二段概述已表达的内容（全部上升＋C国涨幅最大），对Task 1而言是冗余，且让五段结构显得松散。

模型建议：删除该总结段，或将其压缩为一句并入概述段，例如在概述末补充 "with Country C showing the steepest rise."，把篇幅留给数据描述。

原稿完整同段：

> In summary, while every country saw an increase, the growth was particularly striking in Country C and much more modest in Country A.

### high · t1-no-image · criteria.coherence.issues[1]

判断：**过严**（optional_style_overpresented_as_fault）。用时间状语区分2000与2020合理；仅In/By/Insummary不证明衔接机械。替换词语可选。

模型引文：By 2020, the percentage in Country A had risen slightly

模型说明：段落与句子的起头方式高度模式化（In 2000 / By 2020 / In summary），衔接手段种类偏窄，读来有清单感。

模型建议：改用更灵活的衔接，如 "Twenty years later, ..."、"Turning to 2020, ..."、"The same period saw ..."，或在段内用 "whereas"、"by contrast" 组织对比。

原稿完整同段：

> By 2020, the percentage in Country A had risen slightly to about 75%, and Country B had grown to approximately 65%. The most dramatic change was seen in Country C, where ownership almost doubled to nearly 80%, overtaking Country A. Country D also experienced significant growth, reaching around 35%, but it was still well behind the other three countries.

## 漏报与限制

- Both detect complete off-topic content, underlength/single paragraph and Task1 A/C contradiction. No new unequivocal material logic omission identified across this limited synthetic set.
- Off does not separately label weak-road/everybody overgeneralization in argument; its TR already flags broad health/happiness. High more precisely names the road mechanism/range and everybody claim.
- An empty problem list does not establish sound reasoning or grading accuracy; inspect TR/CC and optional advice too.
- One output per mode for seven synthetic essays; not a repeatability study and no teacher-scored gold labels.
- Manual labels reflect visible evidence and reviewer judgment; no replacement official scores supplied.
- Argument problem counts are affected by decomposition of one issue into multiple entries and by reclassification; not an accuracy metric.
- Same-paragraph quotes only prove provenance, not logical support.
- Some mechanical count/style judgments remain subjective; clear falsehoods are separated from optional or debatable advice.
- Language-specific LR/GRA review and cost/token accounting are handled separately by parent.
