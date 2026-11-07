# 剑桥解析展示修复（2026-11-07）

实施树 `/private/tmp/studytracker-cambridge-fix-20261107`，分支 `codex/cambridge-explanations-fix-20261107`，基线/HEAD `40cd8225db1b0a5da188b1dd99d4521dc5853328`。开工该树clean；本子任务只修改下述展示/验证文件，其他agent并行修题库、builder与内容更正清单。未修改旧桌面主树业务，未commit/push/deploy；未写任何学生作答、历史成绩或生产数据库。规范交接由主任务统一更新。

## 改动

- `app.py`仅新增导入，以及普通听力整套页面/API两处`derive_listening_payload`接线。**原始loader保持原样**：它还被判分和模考调用，不应把答后依据注入模拟考试payload。
- 使用实际 `app.static_folder/listening` 为媒体根。沿用既有sidecar文本完整映射、同名MP3大小/SHA版本检查、原轨/裁剪轨坐标选择和未知版本整Section回退。没有盲用原始秒数、没有放宽定位门禁，也没有改音频。
- `services/mock_exam_review.py`复用共享`reading_evidence`，兼容list和dict来源。模考复盘从原题提取依据，保存的results/分数不重写、不重算。
- `services/question_type_review.py:review_snapshot`先deep-copy，再对listening/reading副本应用主任务的`apply_content_corrections`，然后做听力坐标映射。未知subject保持旧的无操作复制行为。`api/question_type_practice.py:_result_rows`原本每次从review snapshot生成analysis/evidence，因而无需迁移历史attempt或重写snapshot/hash。
- `templates/reading/test_practice.html`隐藏恢复导语的内部`pre-A`标签，仍展示导语正文；自动生成heading题段落名称时只按A–Z段落索引。已有段落匹配选项过滤本就排除pre-A。模考复盘正文同样隐藏内部标签。
- 剑18T1Q33/34由听力agent修为各自单空title。实际renderForm核对发现初版Q34复带“麻醉”上下文，造成collect静态行重复；已反馈并由其缩为原位单空句，最终验证上下文仅显示一次、各输入对应原句且依源占位序列排列，模考复盘也不会混用两个空。

## 验证结果与精确命令

cwd均为实施树；使用主资料树Python环境，临时目录/内存数据，没有启动真实app数据库或访问网络。

```sh
TZ=UTC PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_cambridge_review_delivery tests.test_mock_exam_review tests.test_question_type_review tests.test_mock_exam_template_isolation -q
node --test tests/test_cambridge_reading_introduction.js tests/test_listening_review_audio.js tests/test_practice_renderers.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check --no-cache services/mock_exam_review.py services/question_type_review.py tests/test_cambridge_review_delivery.py tests/test_mock_exam_review.py tests/test_question_type_review.py
git diff --check
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-fix-20261107/presentation_verify.py
```

- 最终 **52 Python（0.660秒）+39 Node全部通过**；targeted Ruff及diff检查通过。
- `test_cambridge_review_delivery`执行真实app路由函数体+Flask test client+真实derive，以临时媒体/sidecar及精确hash版本登记验证：页面/API均正确选择原轨或裁剪轨；同名未知媒体禁用逐题定位；原始loader仍无audio_review；模拟考试仍不下发答案、解析或原文。render_template在此路由测试中替为payload捕获，不是完整页面布局测试。
- 全库脚本输出 `presentation-corpus.json`：剑4–21听力72套/2,880题全部具备依据；阅读72套/2,880题中原本有依据的2,860题均进入模考复盘，剩20题来源为空，没有伪补。
- 既有严格全库定位测试包含剑桥+JFDR：336 sections、3,360题、658组，当前全部有可用窗口，并验证每条选取原文被映射证据完整覆盖。此为sidecar合同测试，本worktree没有ignored MP3，不可宣称3,360题均做过实际音频播放验收。
- 剑18T1Q14/15现片段164.90–203.58秒，证据包含时间与dedication；Q29/30现331.27–361.12秒，包含市场空缺、退货原因及双方认可。实际证据文本在JSON报告。
- 两类旧测试更新原因已核实：Q33/34已拆单空，合法共享题干集群38→37、涉及Section31→30、题100→98；C4T3Q4及C10T2Q1无效源定位修好，可用窗口3358→3360。前者增补实际渲染的源句/控件位置/顺序断言，后者将无效窗口负测改为明确合成反例，保留“不可用则回退”防护，未删掉错误路径测试。

## 本子任务文件与边界

业务：`app.py`、`services/mock_exam_review.py`、`services/question_type_review.py`、`templates/reading/test_practice.html`。

测试：修改`tests/test_mock_exam_review.py`、`tests/test_question_type_review.py`、`tests/test_practice_renderers.js`；新增`tests/test_cambridge_review_delivery.py`、`tests/test_cambridge_reading_introduction.js`。

审计：本报告、`presentation_verify.py`、`presentation-corpus.json`。

未做完整浏览器/真机/真实MP3播放或生产访问，小程序解析产品功能未新增。下一步主任务合并确认三组改动，复跑整合后的目标套件与题库审计；获准发布前后核对生产实际媒体版本，尤其剑20T1S1仍可能为436秒原轨。部署、微信上传/提审/发布不在本子任务已完成范围。
