# 官方低分样卷准备与执行上限复核（2026-11-13）

用户已在消息中提供5篇完整转录。已将正文保存到本机私有目录并校验；真实请求 **0**。Task 2尚未获得新的4次付费授权；Task 1还需识图配置及单独16文字+4识图授权。

## 数据落地

仓库外 `/Users/zhouxin/iwa-calibration/`：

- `official_lowband_transcript.txt`：用户原文及存疑标记。
- `official_lowband_template.jsonl`：5篇题型、题干、总分、来源、图表、排序组。
- `official_lowband_t1.jsonl`：4篇；`official_lowband_t2.jsonl`：1篇。
- `img/official-1A.png`、`official-1B.png`、`official-1C.png`：3张图，1A两篇共用。
- `official-source-metadata.json`、`official_lowband_manifest.json`：私有来源详情和哈希。
- 修正旧`official_template.jsonl`的2B两行题目；原文件另存`official_template.before-tourism-fix-20261113.jsonl`，其余三行不变。

新ZIP不在本机附件或下载目录，未声称已取得Claude的9fdb…包；改用同一本已下载官方PDF重建题干/原始图。元数据和图像哈希见`source-summary.json`，不能拿重建文件哈希与Claude模板包要求逐字一致。

5篇类型/分数匹配：1A-A5.0、1A-B6.0、1B-A6.0、1C-A5.0、2B-A5.5。题目/图在PDF第3/4/5/7页，2B是旅游题而非第6页的家境题；2B答卷在23页，官方分数在24页。原始图导出后逐张视检，无裁掉坐标、图例或步骤。正文未重新逐字辨认手写稿；以用户提供的转录为准。

填稿先在ignored临时目录完成并逐项校验，再安装；不直接让未验证脚本覆盖私有正式稿。独立比对正文仅去除两处存疑标记的方括号/问号并留下notes，保留大小写、错误词、标点和段落。空白分词计数依次132/165/181/157/228（不是考试认可词数）；段数4/6/3/4/9。2B开头抄题保留，官方明确这部分不计分，未来解释模型分数与字数时须说明。只有官方总分，没有四项分；样卷公开且可能被模型见过，不能当作盲测校准。

## 执行参数修正

第二版说明A命令是`--max-calls 4 --ledger-text-cap 20`，只限制单次进程4次，不能锁住重启后的累计授权。离线替身复现两轮4+4=8。已将执行说明改为：

- A：独立`ledger-t2.jsonl`，持久文字上限4、识图0；重跑不能换账本或提额度。
- B：以后单独获授权再使用`ledger-t1.jsonl`，文字16、识图4；不借A余额。

不修改产品账本、提示词、模型客户端或评分逻辑。主审复跑`preflight_probe.py`：5个解析检查通过、原cap20可累计8、cap4再次执行0新增，visioncap切换本身没有冲突。脚本还缺标题分数/页码独立核对和覆盖保护，本次由PDF元数据交叉核对、临时目录验收与拒绝覆盖安装补足，没有放宽校验。

## 验证与状态

- `fill_transcripts.py --template .../official_lowband_template.jsonl --text .../official_lowband_transcript.txt` →4+1，loader和图片路径均通过。
- 主树 `.venv/bin/python -B tmp/iwa-official-prep-20261113/verify_data.py` →5篇逐段匹配；无网络的Task2×2演示均ready（不代表评分准确）。
- `.venv/bin/python -B docs/design/iwa-official-lowband-prep-20261113/preflight_probe.py` →解析与持久上限复现/修正通过，使用临时SQLite和网络禁用替身。
- 本轮只修改执行说明、新增脱敏复核资料和两交接；未重跑453全套（产品源码未变），未调用识图或文本服务，未改试用账号/配置/运行库。
- 当前Mac私有配置实际为`/Users/zhouxin/Desktop/studytracker/.tmp/ielts-writing-ai-trial/.env`，源码在`/private/tmp/studytracker-iwa-holdout-review-20261111`，Python用主树`.venv/bin/python`，不要误用不存在的默认`.env`。

仅脱敏说明、合成探针和数字随功能分支同步；全部正文、题图、私有数据和演示结果不提交。main未合并、生产和小程序均未部署/发布。
