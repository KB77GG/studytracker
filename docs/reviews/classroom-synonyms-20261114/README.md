# 课堂三列同义替换：实现与验收

工作树 `/private/tmp/studytracker-classroom-vocabulary-20261114`，分支 `codex/classroom-vocabulary-20261114`，基线 `75ff855d381e4f872a466b7038177382452cbe5b`。延续用户本会话对课堂录入功能的部署授权；发布结果在本文后续更新，不以本地实现代替上线事实。

## 行为

- 仍在 `/materials/classroom-vocabulary` 录入。逐行识别第二列 `=` / `＝`，第一、三列分别为完整英文单词或词组，可以与「单词、词性、中文」混表。TSV、CSV、XLSX首表及可选表头均支持。
- 一个替换占一行；多个替换分行。两侧各最多100字符，拒绝空项、自等、重复、多个并列答案和括号注释。弯引号、Unicode连字符会统一并显示提示；普通行纯英文释义提示老师核对是否应填等号，不擅自改变旧数据语义。
- 同义关系保存在现有 `VocabularySense` 的独立命名空间、lemma/definition_en和关系标记，词条关联sense；translation中的 `= 替换词组` 仅用于展示。无schema迁移、不把替换词作为原词的拼写可接受答案。保存全事务，重试复用须核对关系资料；保存本身不创建Task、不发送通知。
- 默认reading目标：显示原表达，回忆课堂表中的完整替换表达；复用旧客户端 `context_fill` 自由输入展示，仍记录 `meaning_recall`。写作目标支持反向；没有凭空生成例句或听音任务。同义项不进入普通中文干扰选项；坏关系元数据拒绝出题且不虚报到期队列。
- 英文整体判分允许大小写/连续空格，不接受 `take`、`take part`、`takepartin` 替代 `take part in`。沿用首次成绩、重试与到期复习规则。
- 顺带修复现有自主复习页一处未定义变量：`attempt_id` 改为 `attempt_id: attemptId`。真实页面JS测试修复前5通过/2失败，修复后7通过。**这行小程序修复需要独立上传/提审/发布；Git推送与后端部署不会更新微信包。实际当前已发布微信包未核验。**

## 精确验证命令

cwd均为上述实现树：

```bash
TZ=UTC PYTHONWARNINGS=ignore /Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest tests.test_classroom_vocabulary tests.test_classroom_vocabulary_learning tests.test_dictation_answers tests.test_vocabulary_mastery tests.test_vocabulary_group_learning tests.test_vocabulary_group_learning_api tests.test_vocabulary_autonomous_review tests.test_dictation_review -q
node --test tests/test_classroom_vocabulary.js tests/test_task_dictation_preset.js tests/test_classroom_synonym_client.js
node tests/test_dictation_spell_queue.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check services/classroom_vocabulary.py services/vocabulary_synonyms.py tests/test_classroom_vocabulary.py tests/test_classroom_vocabulary_learning.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m black --check services/classroom_vocabulary.py services/vocabulary_synonyms.py tests/test_classroom_vocabulary.py tests/test_classroom_vocabulary_learning.py
git diff --check
```

结果：185项Python、28项Node、旧拼写队列守卫、4文件Ruff/Black、7文件Python3.10 AST通过。没有跑全仓测试或声称存量大型模块全部lint通过。新Node测试已接CI，Python测试沿已有CI入口。

首次组合命令误带不存在的 `tests.test_vocabulary_context`；另旧听写测试 `test_strict_task_score_is_server_merged_score` 在本机23时用naive datetime.now再当UTC转换，产生次日任务遭403。相应测试/日期门禁/听写业务相对基线均未改；显式 `TZ=UTC` 后整套通过，未为测试改生产日期规则。

## 验证范围

- 内存SQLite真实API：混合4行→熟悉→同义词组错误首答→组末正确重试→75%任务结算；推进到真实next_due→实际复习提交→拼连答案判错→完整表达订正→75%复习结算，教师任务原分数不变。无生产业务写入。
- Node真实加载学习/复习页面及共享request封装，仅mock微信原生网络；检查完整词组/多空格/撇号提交、认证、维度保留、失败重试稳定幂等键及既有WXML输入分支。非微信真机测试。
- 浏览器用原 `docs/reviews/classroom-vocabulary-20261114/preview.py --port 5099`：合成账户、内存库，混排3行预览/全角等号提示/保存成功/正确预选词书与reading并打开布置面板。学生栏空，未提交Task。见 `preview.jpg`、`assignment.jpg`。
- 初次合成页面并发资源请求触发夹具synthetic_login取不到内存用户，继而预览CSRF403；刷新后资源、预览、保存、预选成功。夹具未提供申诉接口产生404。不能据此声称整个页面零错误；没有放宽真实鉴权。测试服务已停、浏览器页已关闭。
- XLSX由后端测试覆盖；本轮未操作浏览器文件选择器、未做真实教师生产导入、真实学生学习/微信设备验证。独立代码审计GO，修复了残留关系标记而key损坏时误退回中文判分的缺口。

## 发布与交接

业务 **2e82331a9960b5ce09f2636daca1e36f428a2058** 已commit/push功能分支与main，并部署后台。分支CI43608808499、main CI43609063955总体success（三测试job成功，旧advisory lint failure）；Deploy43609064011成功，详见 `release-state.json`。报告及交接另以skip-ci文档提交同步，不重复部署。

生产 `/root/apps/studytracker` HEAD2e82331a，tracked clean、113untracked保持，23:14:39 CST起active/running、NRestarts0，5002/worker1/gthread6不变。23:22:59 CST验收9运行SHA一致，匿名入口302到登录、login200、公网JS200且SHA相同、重启后warning0，`production-acceptance.json` ok=true。小程序1行修复**仅源码已同步，未上传/提审/发布**；当前微信包未知，必须从包含本提交的最新miniprogram目录发包后真机验证。

验收复用前轮只读脚本，只核文件/systemd/匿名HTTP，不import app/config或读取学生表：

```bash
SYNONYM_MANIFEST_B64=$(base64 < docs/reviews/classroom-synonyms-20261114/runtime-manifest.json | tr -d '\n')
ssh root@47.110.45.193 "cd /root/apps/studytracker && .venv/bin/python - --expected-head 2e82331a9960b5ce09f2636daca1e36f428a2058 --manifest-b64 $SYNONYM_MANIFEST_B64" < docs/reviews/classroom-vocabulary-20261114/verify_release.py > docs/reviews/classroom-synonyms-20261114/production-acceptance.json
```

主资料树 `/Users/zhouxin/Desktop/studytracker` 仍旧main@6ded77d2，只增量更新两交接，保留原7modified/23untracked入口和其他任务资料，5个既有业务文件SHA未变，不从旧树发布。后端/报告可通过远端接续，旧树未提交资料仍仅本机。下一步为小程序发包与真实教师/学生验收，无需重复部署同一后端版本。
