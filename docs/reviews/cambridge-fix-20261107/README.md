# 剑桥阅读与听力修复验收（2026-11-07）

> 本文为首次本机修复阶段的历史验收。后续题干、双空评分修复及最新提交、CI、部署状态见 [发布记录](../cambridge-release-20261107/README.md)；下文“未提交发布”“答案不变”等仅描述当时范围。

本轮已完成本机修复与集成验证，**尚未 commit / push / deploy**。实施树 `/private/tmp/studytracker-cambridge-fix-20261107`，分支 `codex/cambridge-explanations-fix-20261107`，基线及当前 HEAD `40cd8225db1b0a5da188b1dd99d4521dc5853328`。开工 clean，所有本树未提交内容均为本轮修复、测试及报告。不要从旧桌面资料树发布。

## 已修复

1. **剑18 Test1 的主要展示根因：内部 ID 与题号混查。** 例如 Q14 的内部 ID=11，被 Q11 的显示题号抢先匹配，导致正确答案旁显示别题解析，导航/音频也跟错题。旧函数实际影响 Q14–20、Q27–40 共 **21题**，其中12题跨 Section。现按内部 ID 查题，成绩摘要显式将题号（含14,15组合标签）转为 ID。直接执行旧/新页面函数扫描剑4–21全部题目，听力错配21→0/2880；阅读本就严格按 ID，仍0/2880。详见 [冲突报告](question-id-collisions.md)。
2. **内容更正：** 听力26条解析、7题定位、2题单空题干；阅读3条串题/错误解析、3处引文、5篇漏失导语。涉及18套听力33题、9套阅读6题，修改字段有重叠，不应把字段数相加当题数。总计29条解析更正。剑18两组多选定位现在包含两个正确选项及双方认可的完整依据；剑4T3Q4逆时间和剑10T2Q1姓氏拼写定位一并修好。
3. **依据展示：** 普通听力页面/API接入现有可信音轨映射，2880/2880题有依据；阅读模考兼容列表形依据，2860/2860原本有依据的题均能显示，剩20题源依据为空，未编造。原始判分/模拟考试loader保持隔离。
4. **后续导入与历史任务：** 人工更正清单纳入构建流程；旧专项任务用原始 source_test_id/source_number 在副本应用更正，再按作答前权限脱敏。原冻结快照/hash、评分答案和历史成绩不改。导语显示无内部 pre-A 标签，A–Z段落与题号映射保留。

人工清单：`data/cambridge_content_corrections/{listening,reading}.json`；共享应用器：`services/cambridge_content_corrections.py`。只允许解析、依据、题干和定位字段，禁止更正清单改答案/ID/分值。具体证据见 [听力](listening.md)、[阅读](reading.md)、[展示](presentation.md)、[阅读独立复核](cross_reading_review.md)、[听力独立复核](reading_on_listening_fix.md)。前轮只读核查保留在旧资料树 `/Users/zhouxin/Desktop/studytracker/docs/reviews/cambridge-explanations-20261107/`。

## 最终验证

以下命令均在实施树执行，借用桌面树 `.venv`，不启动真实应用数据库，不访问学生记录：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_cambridge_content_corrections tests.test_cambridge_listening_corrections tests.test_cambridge_reading_corrections tests.test_cambridge_review_delivery tests.test_question_type_review tests.test_question_type_practice tests.test_mock_exam_review tests.test_mock_exam_template_isolation tests.test_question_type_practice_contract -q
node --test tests/test_practice_renderers.js tests/test_cambridge_reading_introduction.js tests/test_listening_review_audio.js tests/test_question_type_review_readonly.js tests/test_listening_clip_player.js tests/test_practice_scoring.js tests/test_listening_practice_navigation.js tests/test_reading_practice_navigation.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-fix-20261107/verify_scope.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-fix-20261107/question-id-collisions.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-fix-20261107/presentation_verify.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check --target-version py310 services/cambridge_content_corrections.py services/question_type_practice.py services/question_type_review.py services/mock_exam_review.py scripts/build_listening_test_practice.py scripts/build_reading_test_practice.py tests/test_cambridge_content_corrections.py tests/test_cambridge_review_delivery.py tests/test_cambridge_listening_corrections.py tests/test_cambridge_reading_corrections.py tests/test_mock_exam_review.py tests/test_question_type_review.py docs/reviews/cambridge-fix-20261107/preview.py docs/reviews/cambridge-fix-20261107/verify_scope.py docs/reviews/cambridge-fix-20261107/question-id-collisions.py
git diff --check
```

- 最终 **91 Python + 60 Node** 全过；上述3个全库脚本、targeted Ruff、diff-check全部 exit0。CI已纳入同组Python/Node，但未推送，尚无本轮远端CI结果。
- [scope-verification.json](scope-verification.json)：144/144静态JSON恰好等于基线应用审定manifest的结果；5760题所有非更正字段（包括答案、ID、题号、选项、评分字段）完全不变；阅读全部原A–Z正文不变；重复应用幂等。
- [question-id-collisions.json](question-id-collisions.json)：直接执行真实模板旧/新JS函数；全144套均无缺失/重复ID；修后两个学科均无查题错配。
- [presentation-corpus.json](presentation-corpus.json)：听力2880/2880具备依据；阅读模考2860/2860原有依据恢复。严格音轨合同回归还涵盖JFDR，共3360题/658组；未放宽未知音频版本和不完整映射的回退门禁。
- 修改/新增Python以 `ast.parse(..., feature_version=(3,10))` 检查20文件通过；两模板内联JS替换Jinja表达式后 `node --check` 通过。已有部分文件仍有格式检查差异，未为本任务全文件重排；未宣称全仓库lint/format通过。

## 页面验收

通过 `preview.py --audio-root /Users/zhouxin/Desktop/studytracker/static/listening` 在127.0.0.1:5098启动仅本地的最小Flask模板预览；使用合成空答卷与真实题库/本机音频，不导入app、不连接数据库、不提交学生答案。

- 首轮真实浏览器复现Q14/15显示Q11 seats解析、Q29/30显示Q20 first aid解析，补齐上面的ID根因修复。
- 重启预览服务并刷新后，Q14/15显示B,E及时间/奉献精神依据；从该题直接跳Q29正确切Section3，显示A,C及市场空缺/退货依据；Q34显示stress和自身单空，麻醉共享说明只出现一次。
- 剑6T2阅读正文现包含完整导语，原A–E仍对应原段落，heading题仍标Section A–E。检查了实际排版。
- 听力页面控制台无JS error，浏览器音频控件显示相应定位播放；未逐段人工实听。预览只提供必要路由，账号/历史/阅读精读目录等无关请求404是预览边界，不代表生产验收。
- 两预览标签已关闭；临时服务已Ctrl-C正常退出。未做微信真机、真实登录学生提交或生产发布验收。

## 边界与下一步

已修复本轮确认的内容及展示缺陷；全库规则/合同扫描不等于5760题逐题人工语义终审。源数据76处真伪题选项异常已由UI规范化遮蔽、37题/38条target_para元数据问题目前不参与显示，未混入本次修复。两个旧冻结transcript逆序项也未直接覆盖当前侧坐标；运行态已有正确sidecar映射，详见听力报告。

听力builder不再用时间回退决定解析来源，默认AI文本优先、无AI则源解析、最后人工清单覆盖。本轮仅窄改静态JSON，**没有重建原337条因定位回退选择的解析**；未来整库重建可能改变未审定文本，应审阅生成diff再发布。

生产只读核实仍在40cd8225、服务active，未上传本轮文件/重启/写数据库。网页后端/前端修复均仅本机；小程序未改、未上传/提审/发布。下一位先读本树两交接及git状态；获得用户明确提交发布授权后，fetch核对最新主线，在独立树处理可能新增提交，再提交任务分支、运行远端CI和发布核验。不得直接从落后且有其他改动的桌面main部署，也不得把本轮修复称为已上线。
