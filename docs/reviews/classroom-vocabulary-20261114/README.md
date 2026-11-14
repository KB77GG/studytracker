# 课堂生词后台录入 — 已部署与验收

用户确认老师在电脑后台录入「单词、词性、中文」三列，学生在小程序学习。

## 当前状态与使用流程

实现树 `/private/tmp/studytracker-classroom-vocabulary-20261114`，分支 `codex/classroom-vocabulary-20261114`，原基线44f3bccd。用户授权部署后，业务ca54816c合入并行主线及交接，最终 **21fcd7d4d41025aa6741fe59fab91f00a73dbfce** 已commit/push任务分支与main并部署。报告/交接后续独立skip-ci提交，最终文档HEAD见Git。不要从旧桌面main发布。

后台材料库 → **录入课堂生词** → 填词表名 → 粘贴 Excel/WPS 三列或上传 `.xlsx` → 预览 → 保存词表 → **选择学生并布置**。新词表默认阅读训练，老师仍须在既有布置面板填写学生/日期并提交。保存词表本身不建 Task、不发送微信消息。

- 文本支持 TSV/CSV，表头可选，保留短语空格、顺序和不同义项；空行忽略，格式错误、空释义、完全重复行阻止保存。
- `.xlsx` 只读第一个工作表，多工作表有明确提示；旧 `.xls` 可另存或复制。每表上限 1,200 词、文件 2 MB；不执行公式。
- 中文词性规范为英文缩写并在预览提示，支持复合词性及 num/det/art/aux/int/interj/modal。词性前缀和中文一起保存，熟悉卡可见；复合词性、单字中文判分已验证。
- 复用 `DictationBook/DictationWord`，默认 `reading/general`。无例句仍可完成词义学习和后续词义复习；语境环节按现有规则跳过，小程序可能显示原有“资料降级”提示。未新增模型生成或语境材料。
- 教师/助教/admin角色与CSRF保护，预览不写库，保存全部校验后原子提交；同教师、同标题、同有序内容重试复用。进程内锁遵循生产 `workers=1`，不承诺多进程并发唯一性。
- 材料库两版模板词库“发布”按钮改接实际 `/tasks?preset_dictation_book=ID`；新独立JS复用既有任务面板处理函数。一般教辅材料的其他旧链接不在本轮范围。

## 改动清单

已有文件：`.github/workflows/ci.yml`、`api/__init__.py`、`dictation_answers.py`、`templates/materials.html`、`templates/materials_v2.html`、`templates/tasks.html`，以及两份交接文档。

新增：`api/classroom_vocabulary.py`、`services/classroom_vocabulary.py`、`templates/classroom_vocabulary.html`、`static/css/classroom_vocabulary.css`、`static/js/classroom_vocabulary.js`、`static/js/task_dictation_preset.js`、`tests/test_classroom_vocabulary.py`、`tests/test_classroom_vocabulary_learning.py`、`tests/test_classroom_vocabulary.js`、`tests/test_task_dictation_preset.js`，以及本报告目录。

`app.py`、`models.py`、小程序代码、真实数据库和外部配置未改。CI 的 Python 新项放有完整轻量依赖的 account-provisioning job，Node 项放现有 test job；四次分支/主线CI均已通过，见下方发布记录。

## 可复现验证

以下命令 cwd 均为实现树；Python 使用主资料树已有虚拟环境。主审复跑结果：**168 Python + 19 Node 通过**。

```sh
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_classroom_vocabulary tests.test_classroom_vocabulary_learning tests.test_dictation_answers -q
# 33 passed = 19 import + 1 integration + 13 existing answer tests
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_vocabulary_mastery tests.test_vocabulary_group_learning tests.test_vocabulary_group_learning_api tests.test_vocabulary_autonomous_review tests.test_dictation_review -q
# 135 passed
node --test tests/test_classroom_vocabulary.js tests/test_task_dictation_preset.js
# 19 passed = 13 import UI + 6 task preset
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check api/classroom_vocabulary.py services/classroom_vocabulary.py dictation_answers.py tests/test_classroom_vocabulary.py tests/test_classroom_vocabulary_learning.py docs/reviews/classroom-vocabulary-20261114/preview.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/black --check api/classroom_vocabulary.py services/classroom_vocabulary.py dictation_answers.py tests/test_classroom_vocabulary.py tests/test_classroom_vocabulary_learning.py docs/reviews/classroom-vocabulary-20261114/preview.py
node --check static/js/classroom_vocabulary.js
node --check static/js/task_dictation_preset.js
git diff --check
```

上述6个Python文件也以 `ast.parse(..., feature_version=(3,10))` 通过。全仓测试未运行；没有把旧仓库lint状态说成全通过。

集成测试真实调用导入API、学生熟悉/答题/结算API和复习API，内存合成4词词表，含中文词性、复合词性、单字中文和短语；全部裸中文首答正确，100%结算，推进服务时钟到真实 next_due 后获得4个词义复习项。老师布置Task在测试中用合成模型创建，未声称覆盖真实老师POST。

## 浏览器验收

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/classroom-vocabulary-20261114/preview.py --port 5099
```

该脚本只监听回环，自动登录合成教师，使用内存SQLite，不import app/config。真实模板/导入API/任务JS：材料库新入口、三列粘贴、中文词性规范提示、保存成功、跳转并自动选中词书和reading、展开布置面板且学生仍空均通过。页面证据 `preview.jpg`、`assignment.jpg`、`browser-check.json`。预览服务已停、测试页已关，临时库随进程消失。

夹具最初 `task_page.pages=1` 导致500，改为列表后测试客户端两页200，真实浏览器布置预选通过；这是夹具缺陷。夹具未提供无关申诉API，因此原任务页申诉区域有加载提示，不冒称整页零错误。没有浏览器上传文件/真实老师提交/微信真机操作，XLSX与学生流程由自动化覆盖。

## 交接与下一步

主资料树 `/Users/zhouxin/Desktop/studytracker` 仍 `main@6ded77d24586327ad94e151e172ae4811b4a2eed`、behind113、原7 modified/23 untracked顶层入口保留；本轮该树只增量更新两份交接，业务代码仅在实现树。精确路径、Git状态和收尾时已有业务文件SHA见 `source-state.json`（该快照在追加交接前）。本报告无真实学生信息或秘密。

已部署后端，生产验收仅只读文件/systemd/匿名HTTP，无人工生产业务DB/成绩/外部设置改动。课堂功能没有小程序改动/上传/提审/发布，沿用现有背词入口；并行小班前端发布由其任务单独负责。代码及已提交报告可从远端获取，旧主资料树其他未提交成果仍仅本机。真实教师生产提交/微信真机待实际使用，不创建生产测试词书或Task。

## 2026-11-14 发布验收

- 用户明确“部署吧”。首次33Python+19Node与旧拼写门禁再验通过；并行main新增63fa27f9，CI冲突保留双方步骤，合并后99Python+39Node通过。随后只合并7e203341文档，业务字节不变。相对7e203341净16文件，见release-scope.json。
- 原分支CI43586536996、集成CI43587031580、最终分支CI43587357100、main CI43587357663均success，三测试job通过；存量advisory lint failure如实保留。部署43587357675 success，全部摘要见ci-release.json。
- 生产21fcd7d4、tracked clean、113untracked计数不变，18:53:33 CST起active，NRestarts0；workers1/gthread/threads6/5002保持。12运行SHA相等、公网3资源200且SHA匹配、入口302到login、login200、warning0。production-acceptance.json ok=true。
- 验收不import app/config、不读取学生表、不生成模型请求；没有真实教师或学生生产提交。

合并后精确命令：

```sh
PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_classroom_vocabulary tests.test_classroom_vocabulary_learning tests.test_dictation_answers tests.test_teacher_homework_recipients tests.test_teacher_group_homework tests.test_teacher_practice_access -q
node --test tests/test_classroom_vocabulary.js tests/test_task_dictation_preset.js tests/test_teacher_group_homework.js
# 99 Python / 39 Node passed
CLASSROOM_MANIFEST_B64=$(base64 < docs/reviews/classroom-vocabulary-20261114/runtime-manifest.json | tr -d '\n')
ssh root@47.110.45.193 "cd /root/apps/studytracker && .venv/bin/python - --expected-head 21fcd7d4d41025aa6741fe59fab91f00a73dbfce --manifest-b64 $CLASSROOM_MANIFEST_B64" < docs/reviews/classroom-vocabulary-20261114/verify_release.py > docs/reviews/classroom-vocabulary-20261114/production-acceptance.json
```

线上入口：https://studytracker.xin/materials/classroom-vocabulary 。需要教师、助教或管理员登录。后台材料库顶部也有入口。刷新即可使用，不需要为本功能重发小程序包。
