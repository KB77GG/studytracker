# 发布前题干与输入契约审查（展示子任务）

工作树 `/private/tmp/studytracker-cambridge-fix-20261107`，分支 `codex/cambridge-explanations-fix-20261107`，基线/审查时HEAD `40cd8225db1b0a5da188b1dd99d4521dc5853328`。开始时已有前轮修复和两交接的已知未提交内容；本子任务不提交、推送、部署或写数据库，规范交接由root统一更新。

## 当前结果

执行实际页面的 `renderGroup`、实际共享renderer、实际 `build_simulation_payload` 与 `build_snapshot/public_snapshot`。普通及模考听读各72套/2880题，共5760题；专项以单来源Section/Passage构建真实重编号快照，听2843题、读2859题。全部逻辑控件与题目ID一一对应，显示题号符合当前题号，无缺题、重复逻辑控件或原始 `$内部ID$`/`【编号】`残留。collect英文词覆盖扫描最终无候选遗漏。它是结构/保留性验证，不能替代全部题目逐句语义终审，也不是全套音频实听。

听力7组37题、阅读4组21题保持既有 `manual_review` 专项发布门禁；其中同ID双空题未因客户端改进而自动开放专项发布。普通/模考仍覆盖全部题。详见 `presentation-stems.json` 的 `blocked` 和逐组记录，禁止将专项5702题宣称成5760题。

## 本次确认并修复的新增展示问题

1. 剑18T3 Q1–4 的题干是 `【1】` 至 `【4】`，旧renderer只认空括号，把输入追加到整句末。现在仅识别匹配当前 `number` 或冻结 `source_number` 的编号框，在原位插入输入；不篡改题号或源标题。源数字题号在普通、重编号快照中均不会复现错位。
2. 同一题号有两个物理空：听力C4T1Q11、C6T1Q7/Q19/Q32、C6T3Q36、C9T1Q33、C9T2Q12；阅读C4T1Q21、C7T2Q26、C9T3Q33/Q35、C10T2Q23。旧form把第二空及尾句截断，table/collect把第二空变成不能填写的ghost。现在同一逻辑题包两个输入，按源句连接词 `and/or/to` 合成原答卷字符串，仍一个ID、一分。C4阅读Q21保留屏幕上的 `whales and`，只将 `and` 写入答卷串。恢复既有值时保留原字符串，包括历史只填一个词的记录；不重新判历史分数。
3. 剑19T4 Q37/38、剑20T1 Q39/40没有独立title，原先每题重复整个collect句子并漏出另一题的 `$ID$`。现在按同一source cell的真实不同ID顺序建立共享句，完整题干仅显示一次，每个控件仍在其原始空位。
4. 13个听力题组存在可复现的源文显示遗漏。9组主要丢左列冒号标签（如剑18T1 `Complaints about bus service:`、剑6T4 `Three day cost:`、剑14T1 `Items stolen:`）；另外4组的抽取title短于真实collect cell（电影/书名、固定年龄、枫糖句前半）。现在保留所属题之前的未显示source cell，且当原collect单空句包含title全部词并有额外内容时使用完整collect。修前候选见 `presentation-word-loss.json`，修后全模式 `sourceWordCandidates=[]`。既有来源位置去重与同文不同cell回归仍通过。
5. 补充清理专项重编号后仍露出的源题号（如剑20T1原Q36的 `display 36`）；按 `source_number` 去掉紧贴空白的OCR题号，输入的aria-label、ID和当前题号仍用当前值。
6. 专项说明曾显示原 `Questions 31–40` 而控件为Q1–10。共享 `groupDescription` 现在只转换desc首行标准Questions数字范围，使用当前题号；其余正文数字、日期、词数要求、原desc/冻结hash不变，旧snapshot显示副本应用文案更正后同样有效。

业务改动限 `static/js/practice_renderers.js`、两科练习模板；此前21题ID碰撞修复保持。新增 `tests/test_cambridge_stem_controls.js` 和仅用于测试的 `tests/helpers/practice_template_runtime.js`；既有renderer共享句计数37→39（多出上述2句/4题）有真实句子顺序断言，未仅修改计数掩盖丢文。

## 冻结任务、评分与安全边界

只读复审root的更正helper及 `public_snapshot` 接线：以 `deepcopy` 副本按 `source_test_id/source_number` 应用审定展示字段，再递归删除答案/解析/原文/音频依据。原冻结JSON/hash、学生答卷和保存分数不写回。真实旧剑18快照重编号回归仍通过，未知subject保持无操作副本。此次组件也不新增任何答案/解析字段；模考或未提交专项仍使用原脱敏路径。

听力agent已实现4处独立审定答案更正（C4T1Q11，C6T1Q7/19/32），保留历史保存成绩。新增 `tests/test_cambridge_pair_grading.py` 通过Node实际 `renderGroup` 提取控件，再调用听力真实 `unitValue` /阅读真实 `handleAnswerChange`，把实际保存值交给Python正式整套grader；130子场景覆盖12题普通/模考的完整、缺一项、错一项、空答，以及4题允许的顺序和固定时间方向、显式AM/PM。全部通过；每题仍1分、源payload不变。子任务未修改评分函数或答案字段。

独立复审另发现既有模考答案定位泄露：`build_simulation_payload` 删除answer/analysis，却保留阅读 `central_sentences` 和 `locating_words`，真实C18T1阅读Q1的脱敏JSON仍包含lettuces答案句。现补入这两字段及 `audio_review/practice_audio/audio_timeline` 禁项，原文章正文、题干、选项和响应结构保持；既有 `tests/test_ielts_exam_payload.py` 新增真实C18、全144套、已派生音频依据三个回归，全部6项通过。这个修复与专项 `public_snapshot` 脱敏独立。

## 音频接线性能

普通页/API仍调用现有纯Python `derive_listening_payload`，原轨/切割轨选择沿用sidecar契约与已有受信媒体size/SHA版本检查。没有重模型或联网推理。C18T1本机实际MP3存在情况下，6次派生耗时4.66、3.04、2.921、2.906、2.905、2.881毫秒；详见 `presentation-performance.json`。这是本机单进程微基准，不是生产负载压测。需校验SHA的文件已有按path/size/mtime缓存，未放宽未知媒体门禁。

## 精确验证

在此工作树运行：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-release-20261107/presentation-stems.py
node --test tests/test_cambridge_stem_controls.js tests/test_practice_renderers.js tests/test_listening_review_audio.js tests/test_cambridge_reading_introduction.js tests/test_question_type_review_readonly.js tests/test_listening_practice_navigation.js tests/test_reading_practice_navigation.js
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_cambridge_content_corrections tests.test_cambridge_review_delivery tests.test_mock_exam_review tests.test_question_type_review tests.test_mock_exam_template_isolation -q
node --check static/js/practice_renderers.js
node --check tests/helpers/practice_template_runtime.js
node --check tests/test_cambridge_stem_controls.js
git diff --check
```

上述展示阶段结果72 Node/57 Python通过。追加集成阶段精确命令：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_cambridge_content_corrections tests.test_cambridge_answer_corrections tests.test_cambridge_listening_corrections tests.test_cambridge_reading_corrections tests.test_cambridge_reading_stems tests.test_cambridge_pair_grading tests.test_ielts_exam_payload tests.test_cambridge_review_delivery tests.test_question_type_review tests.test_question_type_practice tests.test_mock_exam_review tests.test_mock_exam_template_isolation tests.test_question_type_practice_contract -q
node --test tests/test_practice_renderers.js tests/test_cambridge_reading_introduction.js tests/test_cambridge_reading_figures.js tests/test_cambridge_stem_controls.js tests/test_listening_review_audio.js tests/test_question_type_review_readonly.js tests/test_listening_clip_player.js tests/test_practice_scoring.js tests/test_listening_practice_navigation.js tests/test_reading_practice_navigation.js
```

最终117 Python（其中pair suite有130子场景）+82 Node通过，语法和diff检查通过；CI已收录全部上述套件，两个helper由对应测试执行。诊断再次运行仍无结构/词覆盖候选；C6T2Q40的collect旧OCR `Lighis ofNew` 仅在词覆盖检查中明确归一为已审定title中的 `Lights of New`，避免把修正OCR误报成丢词。新增Node套件现20项。浏览器双空的真实键入、手机宽度和最终生产校验由root继续；本报告不将VM/合成测试声称为浏览器或微信真机验收。

本子任务产物与业务改动目前仅本机可见，未commit/push/deploy；root持有用户发布授权并负责最终集成与规范交接。
