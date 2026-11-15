# 热榜题目版本核对（2026-11-15）

本轮从公开热榜的 140 条中筛出 32 个有本地候选的条目，逐题比较公开题面。
最终只确认 **16 条听力**，分布为 Part 1 / 2 / 3 / 4：**4 / 2 / 3 / 7**。
阅读的 3 个候选均未通过版本核对，目前 **0 条阅读**可以在此模块开放作答。
未核实条目不作标题模糊匹配，也不从解析生成标准答案。

## 核对依据

- 每个接受的听力条目均有 10 题；来源与本地的题号、去除排版后的题干、选项文字和字母逐题一致。
- 本轮接受的条目没有依赖图片的题组；不会把图片、地图差异误当作排版差异忽略。
- 单独比较公开录音文字与本地既有录音文字。来源文字在本地文字中的有序 token 覆盖率为 92.4%–100%；保留的差异主要是提示语、转写、标点和数字书写方式。这是文字版本核对，**不是两份音频文件字节相同的证明**。
- 填空题继续使用本地已有答案。临时病历题的街道数字、电话号码及日期写法已比照公开句子核对；没有将来源空答案自动填充。
- `source_content_sha256` 覆盖公开 exam 响应的完整 `data`；`target_sha256` 覆盖现有题目 JSON 的原始字节。后续同步必须重新校验，变更后先撤销可练链接，等待复核。
- 16 份目标 MP3 均在主资料树 `/Users/zhouxin/Desktop/studytracker/static/listening_jijing/audio/` 可见；未复制或修改这些音频。新工作树及生产环境仍需各自核对媒体是否存在。

## 明确拒绝的候选

`Lifeguard Application` 与现有同名题的姓名、地址、题面版本不同；`Renting an Apartment` 的录音和题面也不同。不能因为名称一致而绑定现有答案。

三个阅读候选为 Thomas Young、Learning By Example V2、The Causes of Linguistic Change；题干、题组或顺序存在实质差异，均没有生成映射。

其他候选中有些仅差排版或局部措辞，但本轮只开放全题干/选项一致的 16 条。完整候选计数和决定见 `mapping-candidates.json`；通过结果和文字比对值见 `mapping-audit.json`。

## 复现

原始公开响应仅保留在 `/private/tmp/ninefen-public-assets-20261115/`，不含登录信息，也没有访问超出每 Part 20 条的权限接口。该临时缓存未纳入 Git，跨机复现时需从公开接口按映射 ID 重新取 exam 响应。

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B scripts/audit_exam_sprint_matches.py --source-dir /private/tmp/ninefen-public-assets-20261115 --mapping-output data/exam_sprint/mappings.json --report-output docs/reviews/exam-sprint-20261115/mapping-audit.json
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_exam_sprint_matching -q
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check scripts/audit_exam_sprint_matches.py tests/test_exam_sprint_matching.py
```

结果分别为 16 条版本核对通过、8 个测试通过、Ruff 通过。两个 Python 文件已 Black 格式化，`git diff --check` 通过。没有学生数据写入、生产访问、commit、push 或部署。
