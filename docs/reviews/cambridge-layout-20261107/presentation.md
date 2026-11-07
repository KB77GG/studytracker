# 听力题干行布局独立检查

实施树 `/private/tmp/studytracker-cambridge-fix-20261107`，分支 `codex/cambridge-explanations-fix-20261107`，开工 `be9b122f`、tracked clean；生产基线由交接记载为 `0f51632c`，本child未再次连生产。旧Desktop业务树未改。root负责全局交接、浏览器与发布。

## 根因与精确范围

基线探针 `node docs/reviews/cambridge-layout-20261107/presentation-layout-probe.js` 调用真实模板函数与renderer，扫描72套听力。结果保存 `presentation-layout-probe.json`，这是修复前候选快照。

- **桌面两栏误判**：165个form组中32个输出columns；29组原collect每行仅一道题，左右间距实为标签/值排版。renderer用任意cell.start>=24判两栏，1280窗口时form宽820、每列396，将不同源行的连续题并排，造成长短题干和输入上下参差。C18T1S1 Q2/Q3、Q4/Q5尤其明显；另外3组中C6T4S1 Q7–10、C8T4S1 Q8–9实际是同一cell多空，只有C7T2S1 Q6左/Q8右、Q7下一行左为真实不同源cell，但原自动流排列仍未保留它。root/听力agent已决定新renderer统一按题号flow，真实同句多空保留同行；**32为基线统计，不代表新renderer仍输出32组columns**。
- **静态标签被拆行**：10组同源行label/value输出两个block。例如C18T1S1 `Name: / Sadie Jones`、`Year of birth: / 1991`；C5T3S1 `Model: / Max`、`Part exchange? / yes`；C6T3S1 `Full name of applicant: / Pieter Henes`。完整候选源行见JSON。此项交听力agent处理JS。
- **C18T1S4错误副标题**：U+2212 `−`未被flowFact的bullet正则识别，`− poaching laws`、Q36/Q37之间`− tracking devices were fitted...`被升级为subheading，额外加粗及上下margin。交听力agent处理JS；anti/poaching本身源collect含换行，不能把这一点当新输入ID错误。
- **小屏CSS冲突**：`static/css/practice_shell.css`中columns选择器优先级0,2,0，原max980的`.practice-form`优先级0,1,0，1fr覆盖失败；子项却被强制grid-column:1，所有项挤左半列。C18T1S1基线可复现。新renderer走flow后，此CSS修复仍保护旧/其他带columns实例。
- **输入宽度与基线**：form内inline-flex外壳原无max-width，子输入min-width118与clamp可能阻止窄容器收缩。双空直接input的默认baseline与普通inline-answer的middle不同；限定听力text-parts统一middle。
- **结构表格只读检查**：63个table组、964个渲染cell，按实际rowspan/colspan顺序放置，与声明column_index逐格核对，偏移/占格冲突0。未发现这一类结构性错行；这不是所有表格的像素级视觉验收。

## 本child修改与验证

仅改 `static/css/practice_shell.css` 三项：窄屏columns同等优先级覆盖；form内inline-answer最大宽度和子input可收缩；听力双空input居中对齐。未改题库、答案/判分、rendererJS或模板。新增 `tests/test_cambridge_form_layout_css.js`：解析实际CSS媒体条件、选择器优先级与来源顺序，验证390/768/980单列胜出、1280 legacy columns保留；真实C18十控件应用宽度规则；双空对齐契约。

```sh
node --test tests/test_cambridge_form_layout_css.js tests/test_practice_renderers.js tests/test_cambridge_stem_controls.js
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_reading_practice_layout tests.test_question_type_practice_contract -q
git diff --check
```

结果52 Node、11 Python通过，diff通过（听力agent的后续JS集成由root最终再跑）。CSS回归验证级联逻辑，不模拟字体/真实浏览器换行；root正在真实1280/1024/980/390宽度验收。本child未使用共享浏览器，未commit/push/deploy；新修复与报告仍本机，先前be9b122f为已发布交接基线。
