# 发布前最终交叉复核

复核人：listening_content agent。范围为 presentation agent 的双空控件、完整 collect 题干优先和共享题干合并，以及四题答案更正的边界。听力评分模块原由本 agent 实现；这里对它补做的是生产旧实现对照与独立输入探针，不将其表述为另一个作者的代码审查。

工作树 `/private/tmp/studytracker-cambridge-fix-20261107`，分支 `codex/cambridge-explanations-fix-20261107`，复核时 HEAD 为生产基线 `40cd8225db1b0a5da188b1dd99d4521dc5853328`。当前修复仍为本机未提交改动。本次只新增本报告，未修改业务、数据库、历史提交或分数，没有执行 commit/push/deploy。规范交接由主 agent 汇总。

## 结论

没有发现本次范围内的发布阻断问题。下列结论来自源码对照、全库结构输出和定向回归，不代表 5760 题语义或所有答案逐题重新验收。

- 双空保存为一个逻辑答案、一个 qid 和一分；输入框使用 `data-answer-part`，外层才拥有 `answer-unit`/`data-qid`，不会把两个物理输入误计成两题。连接词按原题保留，末尾句子使用切片而非限制长度的 split，避免第二空后题干被截断。
- `collapseRepeatedBlanks` 只合并同一占位符 ID 且中间文字末尾为 and/or/to 的双空；不同 ID 交给共享题干逻辑。共享合并要求源句的 ID 数量、顺序与连续题目完全一致。C19T4 Q37–38、C20T1 Q39–40 均只显示一份完整句子，各题控件仍按原顺序对应。
- `preferTargetTemplate` 的新选择在当前 144 套题中仅使三条已有 title 改为更完整的 collect：C7T4Q2 保留 `Age: 28 years`，C9T1Q40 保留书名 `Marine Mammals Ashore`，C17T4Q31 保留 maple sap 前句。三条逐一对照无矛盾。C6T2Q40 的正确电影名 title 不会被 collect 的 OCR 错字替换。
- 保存、恢复、重做和只读模式已有实际模板测试。旧单框答案无法按原连接词可靠拆开时保留原字符串，未编辑时重新保存保持完全相同；没有根据显示控件重算历史成绩。只读状态禁用内部输入，普通输入事件向外层冒泡后按一个答案保存。
- 数字方框仅在数字等于当前 number/source_number 时转为空格。题组范围替换仅针对开头单独一行 `Questions ...`，未改词数限制或正文中的其他数字。旧专项重编号已覆盖。

## 评分、构建与历史边界

四题答案修订与显示 manifest 分开；专用加载器只允许 C4T1Q11、C6T1Q7/19/32 的 answer，并从它派生 answers。未知题库不因题号相同而命中。helper 无数据库或网络依赖；builder 仅在显式构建完整试卷后调用，导入模块没有执行构建或写静态文件。

`grade_listening_test_answers` 对 deepcopy 应用修订，随后仍使用原判分器；没有扩大通用 normalize。专项按 source_test_id/source_meta.test_id 与 source_number 定位，保留本地重编号和新 ID。`review_snapshot` 同样先 deepcopy，仅更新授权复盘副本的当前题目 key，保存的 results、correct_count、total_count、IELTS 分数原样保留。已有旧专项未来新提交走正确 key，历史结果不重评。

C6T1Q7 的原题是 from/to，前空 10（可带 am），后空 4.30（可带 pm）；反序不正确。本次独立枚举左侧 `10 / 10 am / 10 a.m. / 10 AM`、右侧 `4.30 / 4:30 / 4.30 pm / 4:30 pm / 4.30 p.m. / 4:30 PM`、连接方式 to/and/空格，共 72 个完整输入及对应 72 个反序输入，另 7 个缺项、错误时段或重复端点，共 151 个断言全部通过。这里的时间异体覆盖既有 key 的全部部分形式和原 normalize 支持的大小写/标点变体，没有声称接受任意时间改写。

Q11 与 Q32 两项任意序；Q19 保留原有接受反序的范围。所有四题缺一项均拒绝。源证据、各 part 变体与顺序详见 `listening-answer-rules.json` 和 `listening-stems.md`。

额外从生产基线只读加载全部 84 个听力试卷（72 剑桥 + 12 其他听力，共 3360 题），使用同一旧 payload、同一答案分别调用生产旧 grader 和当前 grader：差异仅四条已授权题目。C6T1 三题的旧“只填一项”样例从 1 分变为 0 分；C4T1Q11 正序完整答案仍为 1 分，结果 key 增加反序等完整变体。其余 3356 题结果逐条完全一致，所有输入 payload 调用前后相等。再以当前 84 份静态 payload 对照旧/新 grader，结果完全相同；合成未知 bank（恰好含 Q7/Q19/Q32）也保持原判分。

## 实际执行的回归

以下命令从上述实施树执行，Python 使用主树现有虚拟环境：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_cambridge_answer_corrections tests.test_cambridge_pair_grading tests.test_listening_scoring tests.test_jijing_scoring tests.test_cambridge_review_delivery tests.test_mock_exam_review -q
node --test tests/test_cambridge_stem_controls.js tests/test_practice_renderers.js
```

Python 39 项通过，其中跨 JS/Python 测试包含 130 个 ordinary/simulation 场景。Node 49 项通过，包含全 144 套每个逻辑答案只显示一次、题号/ID 对应、无泄漏占位符、源 collect 内容保留，及 12 道双空题、JFDR/ZYZ 既有渲染回归。

独立时间探针可用以下只读命令复现：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python - <<'PY'
import itertools, json
from pathlib import Path
from services.ielts_practice_scoring import grade_listening_test_answers
data = json.loads(Path('static/listening_tests/ielts6_test1.json').read_text())
q = next(q for s in data['sections'] for g in s['groups'] for q in g['questions'] if q['number'] == 7)
payload = {'id': data['id'], 'groups': [{'questions': [q]}]}
left = ['10', '10 am', '10 a.m.', '10 AM']
right = ['4.30', '4:30', '4.30 pm', '4:30 pm', '4.30 p.m.', '4:30 PM']
count = 0
for a, b, joiner in itertools.product(left, right, [' to ', ' and ', ' ']):
    for value, expected in [(a + joiner + b, 1), (b + joiner + a, 0)]:
        assert grade_listening_test_answers(payload, {str(q['id']): value})['correct'] == expected, value
        count += 1
for value in ['10 pm to 4.30 am', '10 am', '4.30 pm', '10 to', 'to 4.30', '10 to 10', '4.30 to 4.30']:
    assert grade_listening_test_answers(payload, {str(q['id']): value})['correct'] == 0, value
    count += 1
print(count, 'passed')
PY
```

本次没有新增浏览器真实音频播放验收，也未逐一人工检查非剑桥题库语义；生产发布及发布后 smoke 由主 agent 执行。本文结论不替代其发布状态记录。
