# 剑桥题干复核与发布记录（2026-11-07）

用户在上一轮本机修复后授权部署，并要求继续确认题干错位、不准确等问题。本轮先完成额外审查与修复，再走分支CI和正式发布。实施树 `/private/tmp/studytracker-cambridge-fix-20261107`，分支 `codex/cambridge-explanations-fix-20261107`；固定内容审计基线40cd8225，发布前已快进到仅增加交接文档的主线ffee98a7，业务改动均保留。

## 本轮确认与处理

| 问题 | 已实施处理 |
|---|---|
| 剑18T1共21题内部ID/题号碰撞 | 严格按ID查题，摘要题号显式转换；全2880题错配归零 |
| 阅读标题匹配42题错段、40题空题干 | 200道同类题全部采用来源明确段码；跳过示例段落不再错位 |
| 听力7题、阅读5题同题号双空 | 两个真实输入，保留预印连接词；一个逻辑答案、一分，兼容保存与恢复 |
| 四道双空题源评分表示错误 | 专用审定答案清单，完整两项才得分；C6T1Q7固定时间方向，按原题允许的组合接受 |
| 4题数字框、4题共享句，以及源标签/前后文遗漏 | 原空位插入控件，共享句只呈现一次，补回所属源文字 |
| 15组说明错误、5条新增题干错词或缺片段 | 限定题组/题号更正，专项说明首行跟随当前显示题号 |
| 5篇漏导语、4张缺失原图 | 恢复正文及原图位置；普通、模拟和答后复盘均支持 |
| 听力及阅读模考依据缺失 | 听力2880/2880，阅读原有依据2860/2860恢复；20题源空不伪造 |
| 模考JSON残留定位引文 | 脱敏时删除教学定位与音频依据元数据，保留题干/文章/选项 |

原已确认的29条解析更正、3条引文更正和定位/单空题干修复一并交付。上述计数跨层有交集，不能相加当作错题总数。

精确静态范围见 [release-scope.json](release-scope.json)：听力26套42题及9组说明；阅读39套205题及6组说明、5导语、3篇4图。144套当前数据完全等于固定基线应用审定内容清单与独立四题答案清单。全部5760题ID、题号、选项、非更正评分字段以及阅读原A–Z正文不变；仅C4T1Q11和C6T1Q7/19/32改answer与派生answers，其余5756题答案不变。**不迁移或重算已保存成绩，不改持久冻结快照。** 四题更正适用于之后的提交以及展示副本。

证据与互审：

- [听力题干及原书依据](listening-stems.md)、[四题评分规则](listening-answer-rules.json)
- [阅读段落、说明与图](reading-stems.md)、[实际旧新JS段码验证](reading-stems-render.json)
- [实际渲染与脱敏](presentation-stems.md)、[独立听力复审](final-independent-review.md)、[65个旧阅读快照复审](final-reading-review.md)
- 上一轮报告保留于 `../cambridge-fix-20261107/`；其中“仅本机/答案未改”等为上一轮历史状态，以本发布记录为准，旧scope JSON未覆盖。

## 验证与边界

全部普通及模拟模式144套/5760题使用真实模板renderGroup验证逻辑控件ID、显示题号、缺重题、占位残留和collect源词保留。专项只验证实际可发布的5702题，另外11组58题仍保留原manual_review门禁，没有为了通过测试扩大可发布范围。

Python目标命令与CI一致：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_cambridge_content_corrections tests.test_cambridge_answer_corrections tests.test_cambridge_listening_corrections tests.test_cambridge_reading_corrections tests.test_cambridge_reading_stems tests.test_cambridge_pair_grading tests.test_ielts_exam_payload tests.test_cambridge_review_delivery tests.test_question_type_review tests.test_question_type_practice tests.test_mock_exam_review tests.test_mock_exam_template_isolation tests.test_question_type_practice_contract -q
node --test tests/test_practice_renderers.js tests/test_cambridge_reading_introduction.js tests/test_cambridge_reading_figures.js tests/test_cambridge_stem_controls.js tests/test_listening_review_audio.js tests/test_question_type_review_readonly.js tests/test_listening_clip_player.js tests/test_practice_scoring.js tests/test_listening_practice_navigation.js tests/test_reading_practice_navigation.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-fix-20261107/verify_scope.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-release-20261107/presentation-stems.py
node tests/test_dictation_spell_queue.js
git diff --check
```

首次119 Python及82 Node通过，结果保存在 `final-python-tests.log`、`final-node-tests.log`、`release-scope.json`；130个真实JS序列化→Python评分场景包含在pair测试中。33个修改/新增Python文件3.10 AST和两模板内联JS语法通过，targeted Ruff通过；不是全仓库lint/format无存量问题。

分支初次CI暴露旧测试依赖未入库的本机音频，已在独立测试提交`0f51632c`移除绝对路径，使用临时文件存在性fixture并新增缺文件安全门回归；完整Python集现为120项，本机及无本机音频模拟均通过。见[CI隔离修复](ci-audio-isolation.md)。此修改没有放宽生产资源检查，也不等于音频播放验收。

本机浏览器使用最小Flask、合成作答和真实题库：C6T1Q7两时间分别输入10/4.30、刷新恢复；C4阅读Q21两个输入保留“whales and”；C10T1Q19–21正确显示Paragraph G/H/I；C7T4 Table1实际加载2184×736图。没有console error。预览标签及5098服务已关闭，不连接生产学生库，也未提交真实学生作答。

全量结构/源保留扫描与风险候选人工核实，**不等于5760题逐题语义终审**或全部听力实听。两条旧冻结transcript逆时间保留且当前sidecar正确；不参与运行态的target_para源元数据未顺手改。听力builder时间与解析来源解耦，未来全库重建可能改变337条未审文本，本轮只应用审定清单，仍须审阅未来导入diff。阅读其他来源副标题/注释未无条件扩张。

## 发布验收

部署前只读证据见 [predeploy-audit.json](predeploy-audit.json)：生产40cd8225、tracked clean、原113个未跟踪文件保留，服务active/running，单worker/gthread/6线程/5002，重启以来warning数0。没有生产重模型、数据库迁移或手动学生数据写入。

业务105文件提交 **5099ac411730062949a4341a9684dd62ade50c7d**，测试资源隔离单文件提交 **0f51632ca3bef9ac2b438e4efc88f83f3bd59ec3**；两者已push任务分支与main，生产HEAD为0f51632c。报告/两规范交接随后独立`[skip ci]`文档提交同步；最终文档HEAD见git log，生产保留已验收业务版本。原桌面main未切换或发布。

- [分支CI42366264621](https://github.com/KB77GG/studytracker/actions/runs/42366264621)、[主线CI42367466332](https://github.com/KB77GG/studytracker/actions/runs/42367466332)均success，test/account-provisioning/task-planner三测试job成功；剑桥步骤 **120 Python +82 Node** 成功，见[数量摘录](ci-test-counts.txt)。仓库存量advisory lint仍failure，未声称全仓lint通过。初次分支失败及修复完整保留，不隐藏失败。
- [Deploy42367466296](https://github.com/KB77GG/studytracker/actions/runs/42367466296)一次success。按现有受限部署脚本更新/重启，本次无新migration/schema、手动生产DB写入、重算历史成绩或外部服务配置。
- [生产验收](release-audit.json)：86个运行文件SHA全部一致；tracked clean，113个原未跟踪文件数前后不变；**2026-11-07 19:16:57 CST**起active/running，NRestarts0，5002/单worker/gthread/6线程，验收时重启以来warning以上0。
- 72套听力接口 **2880/2880** 有依据且clip可用；剑18两组多选完整依据通过；剑20T1S1真实媒体为production_seek_indexed_original/source_original、duration436.219。72套阅读 **2880题** API逐JSON哈希均与本机normalize_practice_tables后的审定数据一致；页面200且含新解析查题器/阅读导语。只读探针使用标准库，不import app、不读取学生表、不提交作答。
- [公网验收](public-acceptance.json)：共享renderer与4原图SHA和服务器/本机一致。真实线上页面C6T1Q7两个输入保留from/to且0/40未作答；C10T1例题F之后Q19/20/21对应G/H/I；C7T4 Table1实际加载2184×736。控制台error为空，临时标签已关闭。未填写或提交真实学生作答。

小程序代码未改，无微信上传、提审或发布步骤；真实微信设备与学生完整提交未验。已经打开旧页面的用户应刷新/重开页面以加载本次模板和共享JS。

只读生产复验的可复现命令（cwd本发布树；manifest无凭证或学生数据）：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python - <<'PYPROBE'
import base64
from pathlib import Path
p = Path('docs/reviews/cambridge-release-20261107')
args = ['verify_release.py', '--expected-head', '0f51632ca3bef9ac2b438e4efc88f83f3bd59ec3',
        '--manifest-b64', base64.b64encode((p / 'runtime-manifest.json').read_bytes()).decode(),
        '--reading-manifest-b64', base64.b64encode((p / 'reading-api-manifest.json').read_bytes()).decode(), '--runtime']
Path('/private/tmp/cambridge-verify-production.py').write_text('import sys\nsys.argv = ' + repr(args) + '\n' + (p / 'verify_release.py').read_text())
PYPROBE
ssh root@47.110.45.193 'cd /root/apps/studytracker && .venv/bin/python -' < /private/tmp/cambridge-verify-production.py
```

后续若生产已有其他发布，先确认新HEAD和manifest，不将此固定历史验收脚本的HEAD差异误作产品故障。
