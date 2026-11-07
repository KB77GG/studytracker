# 剑桥电脑网页听力错行追加修复

用户反馈电脑网页题干上下行错位，具体题号不记得。本轮从实际生产页面复现共性问题，追加修复到此前已发布的剑桥解析工作，不将上一轮结构核查视为完整视觉验收。

## 根因与范围

- 共享题干按占位符切片时，末尾文字移到下一题：如 C13 T1 Q35 的句尾出现在 Q36 开头。现在只有原始 `collect` 源行的 ID 数量、次序和归属完全匹配时才按源行显示；否则保留完整连续题干，不猜测分行。
- 原稿标签/值间的空格被误当双栏，32 组表单采用了不合适的网格；现按题号顺序连续展示，保留同一句的多个空。C7 T2 原稿分栏也按完整语义块 Q6→Q7→Q8 展开。
- 同一源行的静态标签和值合并展示；静态说明保留原位置，去掉重复前导。U+2212 项目符号按普通条目显示。
- 修复 980px 断点选择器优先级，并限制输入框宽度、统一双空控件基线。

相对 `be9b122f49c5fd452dfb0b9fbc89e2f9f07cc0bc`，首批业务提交 `038bd8e0` 仅 6 文件：2 个网页运行文件、3 个测试文件、CI。题库、答案、后端接口、评分、数据库、小程序均无增量改动。

### 线上验收发现的源数据断词

C18 T1 Section 4 抓取源把 `strict enforcement of anti-poaching laws` 误断成 `anti` 结尾及 `− poaching laws` 独立子项。原始 raw 与运行 JSON 一致不代表源排版正确。对照[题目扫描页的文本](https://cadscapacitaciones.com/pluginfile.php?file=%2F156268%2Fmod_resource%2Fcontent%2F0%2FExtra+Practice+and+Key.pdf)与[独立题目转录](https://www.learn-learn.com/ielts/listening/review_IP20260413000858.html)，应为一个完整要点。本轮追加精确静态行合并，仅处理这一审定字符串组合，不对其他连字符或子项作猜测；保留原始抓取数据备查。下方首次上线记录和源审计 JSON 为追加前快照，最终增补状态另行记录。

## 验证

- 源行对照：72 套听力、568 个 collect/table 原源不变；165 组表单、1252 逻辑题、677 条非空句尾全查。19 题/13 组句尾错行→0；57 条/21 组静态拆行→0；5 处重复前导→0。39 个共享题干簇含 102 题，86 源行（11 条静态行）完整保序。
- 真浏览器全量布局：165 组、1255 个物理输入框在 1280、1024、980、390px 下无控件越界、相交或整题逆序。C13 T1、C18 T1、C7 T2 逐屏检查；阅读 C7 T4 Passage 2/3 回归正常，原图加载成功。见 [browser-geometry.json](browser-geometry.json)。
- 普通/模拟 144 套 5760 题及专项 5702 题真实模板重跑无控件/题号/源词异常；原 11 组 58 题人工复核门禁保留。详见 [独立复核](independent-review.md)、[源行核对](listening-layout-source.md)、[样式审计](presentation.md)。
- 首批 **120 Python + 96 Node** 通过；断词增补后同一整套命令再次通过 **120 Python + 97 Node**，含 130 个真实 JS 序列化→Python 评分场景。目标 Ruff、JS syntax、spell queue guard、`git diff --check` 通过。`*-tests.log` 为首批、`*-tests-final.log` 为最终增补日志。

精确命令（cwd `/private/tmp/studytracker-cambridge-fix-20261107`）：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_cambridge_content_corrections tests.test_cambridge_answer_corrections tests.test_cambridge_listening_corrections tests.test_cambridge_reading_corrections tests.test_cambridge_reading_stems tests.test_cambridge_pair_grading tests.test_ielts_exam_payload tests.test_cambridge_review_delivery tests.test_question_type_review tests.test_question_type_practice tests.test_mock_exam_review tests.test_mock_exam_template_isolation tests.test_question_type_practice_contract -q
node --test tests/test_practice_renderers.js tests/test_cambridge_reading_introduction.js tests/test_cambridge_reading_figures.js tests/test_cambridge_stem_controls.js tests/test_cambridge_line_layout.js tests/test_cambridge_form_layout_css.js tests/test_listening_review_audio.js tests/test_question_type_review_readonly.js tests/test_listening_clip_player.js tests/test_practice_scoring.js tests/test_listening_practice_navigation.js tests/test_reading_practice_navigation.js
node --check static/js/practice_renderers.js
node tests/test_dictation_spell_queue.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check --no-cache docs/reviews/cambridge-layout-20261107/gallery.py docs/reviews/cambridge-layout-20261107/listening-layout-source.py
git diff --check
```

全量几何检查不等于 5760 题逐题人工语义终审；用户原先看到的具体题号未知。未执行真实学生提交或修改历史成绩。历史报告保留首次阶段状态，最终发布状态以本报告发布节及规范交接为准。

## 发布

首批业务提交 **038bd8e049e3a5719d05b54150ab649c97445bed** 已 push 任务分支和 main，首批生产同 HEAD。[分支 CI 42375565088](https://github.com/KB77GG/studytracker/actions/runs/42375565088)、[主线 CI 42375793132](https://github.com/KB77GG/studytracker/actions/runs/42375793132) 均 success，test/account-provisioning/task-planner 三测试 job 成功；仓库存量 advisory lint failure 保留。[部署 42375793140](https://github.com/KB77GG/studytracker/actions/runs/42375793140) 一次成功。

生产 `/root/apps/studytracker` tracked clean、113 个递归未跟踪文件数前后不变。自 **2026-11-07 21:11:46 CST** active/running，NRestarts0；单 worker/gthread/threads6、127.0.0.1:5002 不变，验收时重启以来 warning 以上 0。两运行文件及 gunicorn 配置 SHA 一致；公网 JS/CSS SHA 一致。真实线上 C13 T1 Q35/36 句尾和 Q34 前导、C18 T1 的姓名/年份及 980px 全宽布局已验收，见 `release-audit.json`、`public-proof.json`。

只读验收复用已审脚本（无 app import / DB 访问）：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -c 'import base64,json; from pathlib import Path; print(base64.b64encode(json.dumps(json.loads(Path("docs/reviews/cambridge-layout-20261107/runtime-manifest.json").read_text())).encode()).decode())'
# 将上一行输出作为下面 MANIFEST_BASE64 的值
ssh root@47.110.45.193 'cd /root/apps/studytracker && .venv/bin/python - --expected-head 038bd8e049e3a5719d05b54150ab649c97445bed --manifest-b64 MANIFEST_BASE64' < docs/reviews/cambridge-release-20261107/verify_release.py
```

本轮网页代码已上线；报告及两份规范交接随后独立 `[skip ci]` 提交同步，生产保留业务 HEAD。无需迁移、依赖安装或手工数据库写入，不重算历史成绩；小程序未改、未上传/提审/发布。预览 5098/5099 均已停，临时浏览器页已关、视口已恢复。旧页面刷新或重开后加载新 JS/CSS。

### 最终断词增补发布

精确静态断词合并提交 **be45283f1e337056991c1c1a59b3aba0d945cd94** 只改 renderer 与源行测试，已 push 任务分支/main 并部署。最终生产同 HEAD，自 **2026-11-07 21:24:12 CST** active/running，NRestarts0、warning0，tracked clean/113 untracked，运行文件/config SHA全匹配。公网 renderer SHA为 `62dcdb5e5d1a6bc388f2bd931360ec87ee74d1ea42c1ed0dc5a0ee50d251affc`；生产浏览器已看到完整 anti-poaching 要点，真正 tracking devices 子项保留，未作答/提交。见 `runtime-manifest-final.json`、`release-audit-final.json`、`public-proof-final.json`。

[增补分支CI42376568920](https://github.com/KB77GG/studytracker/actions/runs/42376568920) success，[部署42376752984](https://github.com/KB77GG/studytracker/actions/runs/42376752984) success；[主线CI42376753001](https://github.com/KB77GG/studytracker/actions/runs/42376753001) success，三个测试job成功，存量advisory lint failure保留。最终复验可沿用上方只读命令，把 manifest 文件换为 `runtime-manifest-final.json`、expected-head 换为 be45283f1e337056991c1c1a59b3aba0d945cd94；服务器上已有该验收脚本，也可直接通过 SSH 调用仓库相对路径，无需上传新脚本。最终120Python/97Node，以及独立4模式和4边界增补均通过。
