# 阅读最终独立复审

**结论：本次阅读发布范围未发现剩余阻断项（GO）。** 初次复审仅读业务；末次追加检查确认并补齐模考复盘正文图，详见末尾。root负责浏览器、提交和发布。

实施树 `/private/tmp/studytracker-cambridge-fix-20261107`，分支 `codex/cambridge-explanations-fix-20261107`，审查HEAD `40cd8225db1b0a5da188b1dd99d4521dc5853328`；已存在本任务全部未提交修复、manifest、4张新图片与测试，均保留。没有生产、数据库、学生答卷/成绩写入，也没有commit/push/deploy操作。

## 核对结论

- **200个heading目标**：独立从原始 `sub_essay_code` 比对，全部与当前题干的Paragraph字母一致。原始数据SHA256为 `0487d669ad899761572d5361cf8dd992cd69d05d8763c5474db55e61a1f28b13`。builder仅在type6、原title为空、源代码为A–Z时补题干；有原title保持，缺代码不再按位置猜。模板取消按题目序号推段落，C10T1跳过F、其他例题/段落跳号不会再平移。C6T3同时保留Key Point命名，原A–Z与导语pre-A独立。
- **6组desc**：manifest作用域为各自test/group ID，C14T2、C9T4、C12T5、C13T2、C5T3的Reading Passage引用，以及C10T3 B–E/i–viii文字均通过专项测试。旧snapshot仍保留原group_id，helper也接受source_meta.group_id；因此不会按显示题号套错组。显示时 `groupDescription` 仅按当前题号转换首行Questions范围，词数要求和正文数字不改。
- **4张图**：3篇文章新增图片对应原 `paragraph_img`，after_paragraph分别为C4T1P3的1、9，C7T4P3的3，C10T3P3的2。四个本地资源存在，PNG/JPEG解码完整；尺寸分别833×291、418×878、2184×736、1356×622；SHA与源图回归一致。运行URL统一 `/static/reading_tests/images/<filename>`，不依赖源图床。真实renderPassage测试确认训练/模拟各出现一次，插入正确段落之后；pre-A不占用原段索引。
- **白名单扩展**：question仍仅允许analysis/central_sentences/locating_words/title/start/end/answer_sentences；group只允许desc；reading passage只允许introduction/images。图片必须为本地 `reading_tests/images/` 路径、明确alt、0–25的整数位置，拒绝外站URL、路径穿越、额外字段与布尔位置。答案/ID/题号/分数不能通过本editorial helper改写。group与image变更均deepcopy，未把缓存manifest对象暴露给调用者。
- **旧专项兼容**：独立将生产基线40cd8225的真实JSON生成65个受影响的可发布单组snapshot，再分别调用public_snapshot/review_snapshot。原题号重编号后题干、desc和图片与审定当前数据一致；ID/number/source_number/answer/answers不变，冻结JSON/hash无变化。未开放原manual_review题组，也未读取或重评真实历史成绩。
- **脱敏**：65个旧snapshot的public输出及再次模拟化后均无答案/解析/定位引文/听力依据等教学字段。新图片与alt是题面内容，可正常保留；原阅读正文保持。全144套模拟脱敏既有回归也通过，包含C18阅读原答案定位泄露的专门检查。

## 验证命令与结果

在实施树运行：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-release-20261107/final-reading-review.py --raw /Users/zhouxin/Desktop/studytracker/data/idictation_reading/raw.json
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_cambridge_reading_stems tests.test_cambridge_content_corrections tests.test_ielts_exam_payload -q
node --test tests/test_cambridge_reading_figures.js tests/test_cambridge_reading_introduction.js tests/test_cambridge_stem_controls.js
```

独立脚本：200 source targets、6 desc、4 local images、65真实旧snapshot均通过，frozen_mutations=0。目标Python **20项通过**，Node **24项通过**。另用Pillow对4张本地文件执行open/verify，无损坏。

边界：本轮是源字段、真实payload和renderer契约复审，不等于全部2880题逐题语义认证、真实学生登录或微信真机验收；浏览器实际资源加载/手机宽度及生产SHA验收仍由root完成。没有发现需要扩大本轮业务范围的剩余阻断。规范交接由root统一更新；本报告审查时仍仅本机可见，未commit/push/deploy。

## 末次补验：模考答后复盘正文图

HEAD已随root快进至 `ffee98a7`（仅文档变化）。确认原 `_unit_source` 与共享复盘宏丢失4张正文图，现窄补 `services/mock_exam_review.py`、`templates/exam/_review_components.html`、`templates/exam/_review_assets.html`：仅接收本地阅读位图路径，按原段索引插图，pre-A导语不平移源段；超出段索引的安全图片置于正文末尾。未变更持久答卷或历史分数。

`tests/test_mock_exam_review.py`新增真实4图Jinja渲染位置与带导语的安全路径回归，覆盖源payload/保存结果不变。运行 `PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_mock_exam_review tests.test_mock_exam_template_isolation -q`：**32项通过**。相关服务/测试Ruff与 `git diff --check` 通过，既有CI已涵盖；业务冻结交root集成。此补验仍仅本机，child未commit/push/deploy。
