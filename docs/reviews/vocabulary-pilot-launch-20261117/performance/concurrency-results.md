# DELETE SQLite 独立并发实测

工作树 `/private/tmp/studytracker-vocabulary-error-pilot-20261117`，分支 `codex/vocabulary-error-pilot-20261117`，本阶段基线 `513c732f`。只在本机合成临时库执行，无生产访问、代答、学生数据或监听服务。

## 方法与计时

复用真实 Flask 路由 Harness，文件SQLite显式DELETE；一进程多线程、每一步用barrier同时发起Flask test client请求。这验证应用和SQLite竞争，不是网络、反向代理或真实gunicorn/微信测试。

每生2400旧学习历史＋试点后20个新错误能力，不把旧池全体导入；每生不同词书避免共享教材缓存美化结果。每case新库并清空纯字符串/资格LRU。1/3/6人，meaning/context，ON/OFF各3轮。37请求/生包括首页summary、门禁、领取20、20次首答、结算、首次学习取题、10次熟悉、学习首答及下一题；**不包含新词任务后续所有阶段**，完整任务正确性由正式回归另验。

409最多重试4次且显式计数，500不重试；某生失败时中止同组后续请求。每条原始记录含HTTP状态/耗时/SQL及fetch行数，未输出SQL正文、答案、token或身份。结果保存产品SHA和结束时`source_files_unchanged`；修改中的结果只能作诊断。

- `first_dml_execute_ms`包括首写SQL等待锁与SQL执行，不能称纯等待。
- `post_first_dml_to_finish_ms`从首写SQL完成至实际commit/rollback或外层SAVEPOINT RELEASE，为写锁持有时间下界，不含首写自身。
- 显式BEGIN IMMEDIATE另计`writer_begin_execute_ms`（等待与获取锁）和`post_writer_begin_to_finish_ms`（获取后至结束下界）。
- 时间包含线程/GIL/GC调度，锁前CPU仍可能拖慢另一线程持锁，不能以SQL少推断没有竞争。

调试证据保留：`delete-initial-py313.json`初始claim超2秒/首次flow409（当时尚未检测SAVEPOINT隐式提交）；`delete-diagnostic-py313.json`证实数据库锁升级冲突；`delete-quickfixed-py313.json`修冲突后仍claim1.42秒；`claim-profile-py313.txt`定位重复lemma解析；`delete-optimized-quick-py310.json`候选复用后仍擦线；`claim-profile-optimized-py310.txt`定位ORM装载；`delete-projection-quick-py310.json`轻量投影后claim551ms。`delete-matrix-py313.json/.log`为主动中止、源变化的10case，禁止作冻结验收。

## 主矩阵完成结果

按下面命令分别使用 Python 3.10.20 和 3.13.3，ON/OFF × 1/3/6人 × meaning/context，各3轮，共各36个case。每版本ON均2220/2220请求200、零409/500、零重试，无中断case；原始文件 `delete-final-py310.json` / `delete-final-py313.json`，结束SHA均稳定。每case清除纯lemma解析LRU，并使用新库。

```sh
/private/tmp/studytracker-stage2-py310/bin/python -B docs/reviews/vocabulary-pilot-launch-20261117/performance/benchmark_delete_concurrency.py --rounds 3 --output docs/reviews/vocabulary-pilot-launch-20261117/performance/delete-final-py310.json
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/vocabulary-pilot-launch-20261117/performance/benchmark_delete_concurrency.py --rounds 3 --output docs/reviews/vocabulary-pilot-launch-20261117/performance/delete-final-py313.json
```

主要路径（语境，单位ms；六人列为P50 / P95 / 最大，除逐答/熟悉外各18请求；单人每入口3请求）：

| 路径 | 3.10 单人P50 | 3.10 六人 | 3.13 六人 |
| --- | ---: | ---: | ---: |
| 首页计数 | 10.9 | 37 / 40 / 40 | 34 / 36 / 36 |
| 任务门禁 | 6.6 | 24 / 28 / 28 | 22 / 23 / 23 |
| 领取20题 | 53.4 | 458 / 567 / 567 | 462 / 602 / 602 |
| 复习首答 | 5.2 | 28 / 94 / 99 | 27 / 95 / 97 |
| 20题结算 | 11.8 | 73 / 159 / 159 | 69 / 160 / 160 |
| 首次学习取题 | 40.5 | 208 / 835 / 835 | 161 / 262 / 262 |
| 学习熟悉 | 4.2 | 29 / 94 / 99 | 27 / 92 / 100 |
| 学习首答 | 10.7 | 61 / 145 / 145 | 63 / 142 / 142 |
| 学习下一题 | 6.8 | 64 / 68 / 68 | 62 / 65 / 65 |

ON主矩阵每条实测请求均小于1秒，单人入口/领取为几十毫秒。不能写“所有ON路径比OFF快”：单人正式复习首答有约1.7–1.8ms固定开销，学习首答约1.6–2.1ms，首次flow约3–7ms；这些用于新事件和原子性保护，绝对时延仍低。入口/领取/结算改善明显。

OFF旧路径保留真实失败：3.10有116次409、3.13有108次409，各6个六人case在首次学习取题重试耗尽后中断；未完成的熟悉/学习回答路径不能称通过。summary中的wall分布包含所有状态，不能把OFF快失败时间与ON成功时间直接比较。

写锁：3.10语境六人复习首答，首DML execute最大81ms、写后持锁最大10ms；首次flow显式BEGIN等待最大737ms、获取写锁后最大310ms；领取首DML最大224ms、写后持锁最大157ms。含线程/GC调度，读准备并不等于零竞争。原始JSON保留所有拆分，不把等待混称业务写SQL成本。

### 大词书边界补测

主矩阵新任务固定10词、任务书也10词，另有2400旧复习历史。随后增加真实可遇边界：**2400词任务书选其中10词**（仍保留另外2400旧历史）。诊断 `taskbook-large-before-py310.json` 发现首次flow六人最大1658ms，候选装载/建题仍在写锁中；该轮源码正在修改，`source_files_unchanged=false`，只作诊断。

修复将试点候选轻量投影/预解析移到写锁前，保留原题型/种子/选项次序。受影响路径各用1/6人3轮复测，每版本777/777请求200、零重试、SHA稳定：`taskbook-large-final-py310.json` 与 `taskbook-large-final-py313.json`。首次flow 3.10单人P50 68/最大99ms、六人P50 503/最大829ms；3.13单人P50 62/最大64ms、六人P50 505/最大675ms。该复测覆盖全部37步，补充最终修复后的证据，不能冒称之前36case矩阵就是最终相同源码。

```sh
/private/tmp/studytracker-stage2-py310/bin/python -B docs/reviews/vocabulary-pilot-launch-20261117/performance/benchmark_delete_concurrency.py --rounds 3 --concurrency 1,6 --dimensions context --modes on --task-book-size 2400 --output docs/reviews/vocabulary-pilot-launch-20261117/performance/taskbook-large-final-py310.json
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/vocabulary-pilot-launch-20261117/performance/benchmark_delete_concurrency.py --rounds 3 --concurrency 1,6 --dimensions context --modes on --task-book-size 2400 --output docs/reviews/vocabulary-pilot-launch-20261117/performance/taskbook-large-final-py313.json
```

### 可选旧池最终结果与限制

合成可选极端fixture在临时库人为构造2400条队列排除状态，专测最坏排除成本，不代表当前试点规模。三种状态分别为：可领10题；所有到期能力均被活动/暂停队列排除；首个合格能力被排除、另一个到期能力未排除（partial，按旧首合格规则返回空）。每版1/6人、每场景3轮，18case/63请求全部200，无重试，结束SHA稳定。纯lemma/资格LRU均每case清空。

最终文件 `optional-paged-final-py310.json` / `optional-paged-final-py313.json`。六人列为P50 / P95 / 最大，单位ms：

| 可选状态 | 3.10 单人P50 | 3.10 六人 | 3.13 单人P50 | 3.13 六人 |
| --- | ---: | ---: | ---: | ---: |
| 可领10题 | 78.8 | 767 / 881 / 881 | 74.9 | 778 / 928 / 928 |
| 全部排除 | 30.2 | 176 / 258 / 258 | 26.9 | 159 / 185 / 185 |
| 部分排除空池 | 71.8 | 823 / 1071 / 1071 | 66.0 | 1116 / 1144 / 1144 |

**严格门槛未完全满足**：可选partial极端池六人最大为3.10的1071ms、3.13的1144ms；不能写所有可选请求都<1秒。必做主路径与大书学习已通过该门槛。所有可选请求均成功；是否接受该极端限制开启小试点，由主agent明确记录。没有以增加重试、减少题量或改变首合格能力顺序掩盖。

10,000旧池单人一轮只作量级：最终 `optional-10000-final-py310.json` 三请求全200、稳定SHA；全排除42ms/10011读取行，可领10题207ms/20262行，partial274ms/40011行。可选仍有随词池/词书增长的读和CPU工作，**不声称O(1)，没有验证10,000池六并发**。它的扫描不进入必做summary/门禁/claim路径；同一进程同时运行可选仍可能占用CPU，不能把纯路径独立性等同于完全无资源竞争。

```sh
/private/tmp/studytracker-stage2-py310/bin/python -B docs/reviews/vocabulary-pilot-launch-20261117/performance/benchmark_optional_pool.py --rounds 3 --scenarios available,blocked,partial --output docs/reviews/vocabulary-pilot-launch-20261117/performance/optional-paged-final-py310.json
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B docs/reviews/vocabulary-pilot-launch-20261117/performance/benchmark_optional_pool.py --rounds 3 --scenarios available,blocked,partial --output docs/reviews/vocabulary-pilot-launch-20261117/performance/optional-paged-final-py313.json
/private/tmp/studytracker-stage2-py310/bin/python -B docs/reviews/vocabulary-pilot-launch-20261117/performance/benchmark_optional_pool.py --rounds 1 --concurrency 1 --backlog 10000 --scenarios available,blocked,partial --output docs/reviews/vocabulary-pilot-launch-20261117/performance/optional-10000-final-py310.json
```

调试历史完整保留：`optional-final-py310.json` / `optional-10000-py310.json` 是全排除优化前；`optional-filtered-py310.json` 只修全排除；`optional-partial-py310.json` 捕获partial六人3.27秒；`optional-partial-scalar-py310.json` 为资格纯字段化快测；`optional-complete-py310.json` / `optional-complete-py313.json` 为固定512页时的中间结果。最终资格用完整纯字段key、按原排序/首合格语义判断，只物化最终最多10词；首128/续1024为同一游标分页，不截断结果。

### 收尾状态

所有本子任务临时进程已退出，未启动监听server/浏览器。上述探针只在本机合成库运行；未操作生产、提交、推送或启用学生。报告/脚本/结果由主agent纳入最终交接、版本管理与发布审核；代码随后仅格式化/明确无行为变动清理时，需在主报告写明，不把之前SHA冒充格式化后的SHA。

仪表脚本Black/Ruff、`git diff --check`通过；功能/等价性门禁由integration/core正式测试负责。最终强结论范围是合成请求与SQL工作量，不是公网或真机保证。

最终源码在本轮仪表之后还经过formatter、移除未使用迭代参数、孤儿词书fallback与import排序。正常词书只新增一个scalar投影列，fallback只影响孤儿书；不得称这里的preformat SHA等同最终发布SHA。主agent需结合该小增量的正式测试与最终源清单判断。

## 最终源码小增量复验

在integration最终396项双Python通过并冻结后，再用生产同版Python3.10，对包含最终Sense/book有限重校验、孤儿book fallback与formatter的源码补测：

```sh
/private/tmp/studytracker-stage2-py310/bin/python -B docs/reviews/vocabulary-pilot-launch-20261117/performance/benchmark_delete_concurrency.py --rounds 1 --concurrency 6 --dimensions context --modes on --task-book-size 2400 --output docs/reviews/vocabulary-pilot-launch-20261117/performance/final-source-flow-py310.json
/private/tmp/studytracker-stage2-py310/bin/python -B docs/reviews/vocabulary-pilot-launch-20261117/performance/benchmark_optional_pool.py --rounds 1 --concurrency 6 --scenarios available,blocked,partial --output docs/reviews/vocabulary-pilot-launch-20261117/performance/final-source-optional-py310.json
```

两份JSON均`source_files_unchanged=true`。6人主流程222/222请求200、零重试，领取最大619ms、首次大书学习最大718ms、全路径最大718ms。可选三场景18/18请求200，最大值：可领10题908ms、全部排除197ms、部分排除932ms。

这是最终源的一轮增量复验，不替代前面双版本三轮分布；前面观察到的极端可选1.144秒限制继续保留，不能用这次较快样本抹掉尾延迟。
