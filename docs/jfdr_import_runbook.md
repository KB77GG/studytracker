# 9分达人听力 新书导入运维手册（给 Codex）

> 本手册让你把**任意一本《9分达人雅思听力》**（如 1/2/3/4/5/7…）按已跑通的流水线导入
> 听力刷题+精听系统。书 6（`jfdr6`）已完整上线，是你的**参照实现和金标准**。
> 全程只在**本地 Mac** 跑（生产机禁跑 whisper，会 OOM）。Python 一律用 `.venv/bin/python`。

---

## 0. 先读这段：为什么这件事现在很安全

- **后端/目录/前端对任意 `jfdr{book}` 已零改动支持。** 系列注册表 `api/listening_series.py`
  的 `jfdr` 条目用正则 `jfdr(\d+)_test{N}` 匹配任何书号，自动生成标题「9分达人听力{N}」、
  书目标签「9分达人 {N}」。app.py 三处目录函数、`api/miniprogram.py` 教师端目录、两个网页
  模板、小程序教师端标签**全部已改用它**。**你不需要动任何后端/前端代码。**
- 你只需要：① 把 3 个流水线脚本从写死 `jfdr6` 改成吃 `--book` 参数（一次性，向后兼容）；
  ② 对每本书重复「提取→合并→对齐→翻译→组装→验证→上线」。
- ID 命名固定：整卷 `jfdr{book}_test{N}`、精听/section `jfdr{book}_test{N}_s{S}`。

**验收总门槛（每本书上线前必须全绿）**：6/每套 40 题标准答案回填判分 = **满分/雅思9.0**；
每个 section 对齐置信度 ≥ 0.9（Part 1 允许因 whisper 稀疏偏低但须人工抽听确认）；
逐句中英文条数与原文 1:1；整卷+精听 JSON 数量 = 套数×(1+4)，mp3 数量 = 套数×4。

---

## 1. 每本书要先收集的输入

| 项 | 说明 | 书6 的值（参照） |
|---|---|---|
| 源 PDF | 扫描版，通常无文字层 | `《9分达人雅思听力真题还原及解析6（208页）.pdf》` |
| 源 mp3 目录 | 每套 4 个 Part，命名可能不规范 | `Test 1/Test 1 Part 1.mp3` … |
| 套数 | 从 PDF 目录页数 Test 数量确认 | 6 套 |
| **页码偏移** | 印刷页码 + 偏移 = PDF 页码（文件名 NNN）。**每本不同**，front matter 长度决定 | +16 |
| 各套/各 Part 板块页码 | 题目 / 听力原文 / 真题解析 / 答案总表 的 PDF 页范围 | 见 `data/jfdr6/page_map.json` |

> ⚠️ **页码偏移和板块页码是每本书唯一真正需要人肉/agent 摸清的东西**，务必先做「页码地图」
> （见 Phase 0），后面所有提取都依赖它。偏移算法：翻到 PDF 里印着「1」的正文首页，它的
> 文件名 NNN 就是偏移量（书6 印刷页1 = PDF 页17，偏移 16）。

---

## 2. 一次性：把 3 个脚本参数化（`--book`，默认 6 保持现状）

改动**只加参数、默认值 = 6**，不改书6 的既有行为（跑 `--book 6` 结果与现在完全一致）。
改完务必先 `--book 6` 重跑一遍比对 `git diff static/listening_tests/jfdr6_test1.json` 应为空，
证明没回归。

### 2.1 `scripts/prepare_jfdr6_assets.py`
- 加 `--book`（int，默认 6）、`--source`（源 PDF+mp3 所在目录，默认书6 的 `SOURCE_ROOT`）、
  `--tests`（套数，默认 6）、`--pdf-name`（PDF 文件名，默认书6）。
- 把 `SOURCE_ROOT` / `PDF_NAME` / `AUDIO_OUT`(`data/jfdr{book}/audio`) / `PAGES_OUT` /
  `MANIFEST_OUT` 全部按 `book` 拼；`range(1, 7)` 改 `range(1, tests+1)`；
  canonical 名 `jfdr{book}_test{N}_s{S}.mp3`。
- **保留 mp3 文件名清洗的健壮性**：用 `PART_RE = re.compile(r"part\s*(\d)", re.I)` 对
  `p.stem.strip()` 解析 Part 号（书6 Test6 的文件名无 "Test 6" 前缀且带前导空格，全靠这个兜住）。
  每套若解析不出恰好 4 个 Part（1-4）就报错退出。ffprobe 校验每个 mp3 时长在 5-13 分钟。

### 2.2 `scripts/align_jfdr_listening.py`
- 加 `--book`（默认 6）。把 `MERGED_DIR/AUDIO_DIR/ALIGNED_DIR/CACHE_DIR` 改成
  `data/jfdr{book}/…`；`iter_exercises()` 里 `exercise_id = f"jfdr{book}_test{N}_s{S}"`。
- **不要动对齐算法**：默认 `--method lcs`（全局单调对齐，见 `scripts/lcs_align.py`），
  `--prewarm` 转写缓存，`--only` 单条过滤。

### 2.3 `scripts/build_jfdr6_listening.py`
- 加 `--book`（默认 6）、`--tests`（默认 6）。把 `JFDR_ROOT = data/jfdr{book}`、
  所有 `f"jfdr6_test…"` → `f"jfdr{book}_test…"`、默认 `tests = range(1, tests+1)`。
- **标题统一走注册表**（去掉写死的「9分达人听力6」字符串）：
  `from api.listening_series import parse_test_id, parse_intensive_id`，
  整卷 `title = parse_test_id(f"jfdr{book}_test{N}")["title"]`，
  精听 `title = parse_intensive_id(exercise_id)["title"]`，
  `source` 字段可保留 `f"《9分达人雅思听力真题还原及解析{book}》"`。
  这样标题只有一个真相源，未来改名不用动脚本。
- **判分相关逻辑一个字都别改**（下面「关键坑」第 3、4 条已内建，跨书通用）。

> 可选但推荐：把 3 个脚本重命名为不带 6 的名字（如 `prepare_jfdr_assets.py`），
> 或建软链，避免「jfdr6」误导。非必须。

---

## 3. 每本书的执行流程（以 `--book B` 为例）

目录约定：中间产物全在 `data/jfdr{B}/`。`pages/`、`audio/`、`whisper_cache/` 已被
`.gitignore` 覆盖（书6 已加规则，新书号需在 `.gitignore` 补三行
`data/jfdr{B}/pages/`、`data/jfdr{B}/audio/`、`data/jfdr{B}/whisper_cache/`）。

### Phase 0 — 素材 + 页码地图
```bash
.venv/bin/python scripts/prepare_jfdr6_assets.py --book B --source "<源目录>" \
    --pdf-name "<PDF文件名>" --tests <套数> --render-pdf
```
产出：`data/jfdr{B}/audio/jfdr{B}_test{N}_s{S}.mp3`（24 或对应数量）、
`data/jfdr{B}/pages/page-NNN.jpg`（全书渲染，150dpi）、`audio_manifest.json`。

然后建 **`data/jfdr{B}/page_map.json`**（格式照抄 `data/jfdr6/page_map.json`）：
- 先算页码偏移（印刷页1 的 PDF 文件名 NNN）。
- 用 **Explore/general-purpose 子 agent（model: opus）逐套翻页**，让它输出每套
  `questions{1-4}` / `transcript{1-4}` / `analysis{1-4}` 的 PDF 页范围 + 答案总表页。
  **强制要求 agent 只用文件名 NNN（PDF 页码），并自检 transcript.1 < analysis.1 <
  transcript.2 < …（书6 曾有 agent 混淆印刷页/PDF页，务必让它逐页列 `page-NNN = 什么板块`
  自检）。** 范围可略宽 1-2 页，提取时按「黑色横幅」实位裁剪。

**验收**：mp3 数量/时长过 ffprobe；page_map 覆盖每套 4 Part 的题目/原文/解析 + 答案总表。

### Phase 1 — PDF 结构化提取（工作量大头，全用子 agent，model: opus）
先确保 `data/jfdr{B}/extract/SCHEMA.md` 存在（**直接复制 `data/jfdr6/extract/SCHEMA.md`**，
它是题型码表 + 4 类中间文件格式的唯一规范，跨书通用，不用改）。

按「每套 = 1 个题目 agent + 4 个（原文+解析）agent」派发（书6 就是这个粒度，稳）。
- **子 agent 必须 `model: opus`**（默认 fable 会撞用量上限；sonnet 也行但 opus 更准）。
- 每个 agent 的 prompt：给它 SCHEMA.md 路径、该 Part 的 page_map 页范围、一个已完成的
  书6 样例文件路径作参照、严格的输出 schema 和自检要求。**照抄 `data/jfdr6/` 里书6 的
  agent 任务模式**（见本手册末尾「附录 A：agent prompt 模板」）。
- 产出 4 类文件（均 UTF-8、缩进 JSON / jsonl）：
  `test{N}/part{S}.questions.json`、`.transcript.jsonl`（含下划线句的 `q:[题号]`）、
  `.analysis.json`、以及全书一份 `extract/answer_key.json`（240 或对应题数）。

**子 agent 会因用量上限中途挂**：**每批完成后用脚本核对文件是否齐全**（下面 Phase 2 前的
检查），只补跑缺失的单个文件，不要整套重来。书6 就出现过 agent 写完 transcript 没写
analysis 就挂了 —— 补跑那一个即可。

**提取质量约定（照抄书6）**：
- 题型码见 SCHEMA：1单选 2多选 3表格填空 4简答 5笔记填空 6流程图 7地图 8选项箱配对。
- **多选题「Choose TWO/THREE letters」→ type 2**（多题共享 `collect_option.list`、题任意顺序）。
  若 agent 误标成 type 9，Phase 2 前用脚本改回 type 2（见关键坑 #3）。
- 地图/平面图/流程图（type 6/7）→ `needs_image: true` + `image_pages: [PDF页]`，图后续裁（关键坑 #5）。
- 填空占位符写 `$N$`（**必须闭合的两个 `$`**），题目 title 里写 `【   】`（关键坑 #4）。

### Phase 2 — 合并 + 硬校验
```bash
.venv/bin/python scripts/build_jfdr6_listening.py merge --book B --tests <套数>
```
- 硬校验：每 Part 10 题连续、答案双源（总表 vs 解析标题）比对、`$N$` 占位符集合==题号集合、
  选择题 options 非空、每题≥1 个答案句标注。任一 error 不产出该 Part 的 merged。
- 产出 `data/jfdr{B}/merged/test{N}_part{S}.json` + 校对单 `data/jfdr{B}/review/test{N}.md`。
- **人只看校对单里的标红行**。**「答案双源不一致」若两边只是「拆字母 vs 合并 B & E」的
  格式差异 = 预期噪音，非真错**；真正要处理的是「占位符≠题号」「无答案句」「空字段」这类
  （书6 Test5 出过一次 `$3 $$$` 货币符号占位符错位，见关键坑 #4）。用这条过滤命令看真问题：
  ```bash
  grep -E "^\| [0-9]|warn" data/jfdr{B}/review/test{N}.md | grep -vE "IN EITHER ORDER|IN ANY ORDER| & "
  ```

### Phase 3 — 强制对齐（本地 whisper，先预热缓存）
```bash
# 一次性预热全书转写缓存（最耗时，几十分钟；small 模型，base 会丢尾部30s）
.venv/bin/python scripts/align_jfdr_listening.py --book B --prewarm --model small
# 对齐（LCS，秒级，吃缓存）
.venv/bin/python scripts/align_jfdr_listening.py --book B --model small --method lcs
# 逐句置信度审计
.venv/bin/python scripts/audit_jfdr_alignment.py --book B --model small   # 见下注
```
- **必须用 `--method lcs`**（默认就是）。原因见关键坑 #2。
- 审计脚本 `audit_jfdr_alignment.py` 目前是 glob `data/jfdr6/aligned`，你参数化 align 时
  也给它加 `--book`（或让它 glob `jfdr*`）。置信度 <0.9 的 section：**人工抽听**——切该
  section 几个答案句对应时间戳 ±1s 的音频，用 whisper 转一下看内容对不对（书6 Test1 s1
  就是这样确认 LCS 修好的）。审计的「drifted」很多是 whisper 该处没转出词导致的**假阳性**，
  不等于真漂移，以抽听为准。

### Phase 4 — 中文翻译（子 agent，model: opus）
对每套派一个翻译 agent：读 `data/jfdr{B}/merged/test{N}_part{S}.json`（或 extract 的
transcript.jsonl，二者 idx 一致）的每句 `en`，输出 `data/jfdr{B}/translations/test{N}_part{S}.json`
= `{"idx字符串": "中文译文"}`，**条数必须与 transcript 1:1、key 覆盖 0..N-1 无缺**。
口语化贴合场景；数字/人名/地名保留。

### Phase 5 — 组装 + 内置终检
```bash
.venv/bin/python scripts/build_jfdr6_listening.py build --book B --tests <套数>
```
产出 `static/listening_tests/jfdr{B}_test{N}.json`（整卷）+
`static/listening/jfdr{B}_test{N}_s{S}.json`（精听）+ 把 mp3 拷进 `static/listening/`。
build 内置 selfcheck：lyc_index 不越界、start<end、每题有答案句、音频存在。

### Phase 6 — 判分自测（不依赖 dev server）
**dev server（debug reloader）在你写 static 文件时会崩，别依赖它判分。** 用现成的独立判分器
`scripts/grade_jfdr_selfcheck.py`（已忠实复刻 app.py `_grade_listening_test_answers`，跨书通用）：
```bash
.venv/bin/python scripts/grade_jfdr_selfcheck.py --book B          # 全部套，期望每套 40/40
.venv/bin/python scripts/grade_jfdr_selfcheck.py --book B --tests 1,2   # 指定套
```
退出码非 0 即有套没满分（会打印 `wrong=[题号]`），去查该题的 answer/题型码/占位符。

### Phase 7 — 网页端目视抽验（可选但建议）
`preview_start flask`（端口 5001）起服务（若中途崩就重启），网页看：
`/listening/tests` 目录出现「9分达人 {B}」；点开一套 → 表格/填空/选项渲染正常、
`$金额` 类显示为文本不误判为填空、错题 seek、原文 tab 逐句中英文、精听逐句播放。

---

## 4. 关键坑（跨书通用，务必内化）

1. **子 agent 用 `model: opus`。** 默认 fable-5 会反复撞用量上限、中途挂。opus 最稳最准。
   每批完成后用脚本核对产物齐全，只补跑缺失的单个文件。

2. **对齐必须 LCS（`--method lcs`，默认）。** whisper `small` 在个别音频会漏转一大段
   （不是模型不行，是该段被跳过），贪心锚点法一旦丢轨会大幅漂移，导致错题 seek 全错。
   LCS 用完整书面文本 vs 稀疏 whisper 词流做最长公共子序列，漏转句在锚点间插值，稳健得多。
   **`medium` 模型在此网络下不了（自签证书代理拦 SSL，`curl -k` 被安全策略禁），别浪费时间试。**

3. **多选题判分靠 type 2 + 合并答案。** 「Choose TWO/THREE letters, in any order」必须
   type 2，且 build 会把该组每题 answer 设成合并字母串（如 `B,E` / `A,C,F`）才触发
   app.py 的 checkbox-set 乱序判分（`_listening_test_is_combined_multi` 要求 type==2 且
   各题同答案含逗号）。agent 有时把「Choose THREE」标成 type 9 —— Phase 2 前用脚本改回 2：
   ```python
   # 把某组 type 9→2（三/两选任意顺序）
   for g in doc['groups']:
       if g['type']==9 and g 是共享字母答案的多选组: g['type']=2
   ```
   **配对题（每题一个不同字母、共用词库，如 Choose FOUR 各配一项）保持 type 8**，各题独立判分。

4. **`$N$` 占位符 + 货币 `$` 冲突。** 前端/后端占位符正则都是 `\$(\d+)\$`（**要求闭合 `$`**）。
   所以 `$100`（无闭合）安全显示为文本；但「Cost: $ [空]」这种货币符号紧挨空格时 agent 易写
   出 `$3 $$$` 这类畸形（中间有空格→占位符失配）。正确编码 `$$3$`（字面 `$` + 占位 `$3$`）。
   Phase 2 的「占位符≠题号」校验会抓到，按此修。

5. **地图/图示题（type 6/7）要裁图。** 用 PIL 从对应 PDF 页 `data/jfdr{B}/pages/page-NNN.jpg`
   裁出图存 `static/listening_tests/images/jfdr{B}/jfdr{B}_test{N}_s{S}_map.png`，把该 group 的
   `img_local` 设成相对 static 的路径（如 `listening_tests/images/jfdr{B}/xxx.png`）、
   `needs_image` 置 false。裁前先 `Read` 那页图定位边界框（书6 Test2 平面图见既有实现）。

6. **页码偏移每本书不同**，front matter 长度决定。Phase 0 必须先算准，否则全套提取错位。

7. **别信 dev server 判分**，它会崩；用独立判分器（关键坑无关，纯工具健壮性）。

8. **中间产物 git 策略**：`extract/merged/translations/aligned/page_map/review` 进 git（便于复现/校对）；
   `pages/audio/whisper_cache` 和 `static/listening/*.mp3` 不进（.gitignore 已覆盖 `*.mp3`，
   但新书号的 pages/audio/whisper_cache 三个目录要在 .gitignore 补规则）。

---

## 5. 上线部署（每本书，顺序很重要）

前置：本地 6 步验收全绿（判分满分 + 对齐达标 + 翻译 1:1 + 文件齐全）。

```bash
# 1) 先把 mp3 传服务器（无副作用：JSON 未部署时无人引用）
#    本地 ~/.ssh/config 有 aliyun-server=47.110.45.193（root 直连），目标 static/listening/
ssh aliyun-server 'df -h /root/apps/studytracker/static | tail -1'     # 先看磁盘（书6 用了~242M）
rsync -az static/listening/jfdr{B}_test*_s*.mp3 \
    aliyun-server:/root/apps/studytracker/static/listening/
ssh aliyun-server 'ls /root/apps/studytracker/static/listening/jfdr{B}_*.mp3 | wc -l'  # 核对数量

# 2) 提交（只加文本产物，绝不加 mp3；确认暂存里 0 个 .mp3）
git add .gitignore \
    static/listening_tests/jfdr{B}_test*.json static/listening/jfdr{B}_test*_s*.json \
    static/listening_tests/images/jfdr{B}/ data/jfdr{B}/
git diff --cached --name-only | grep -c '\.mp3$'   # 必须是 0
git commit -m "feat: 导入《9分达人雅思听力{B}》N套Test（复用 jfdr 流水线）"

# 3) push main → GitHub Actions 自动部署到生产（端口 5002，reset --hard，不碰 untracked mp3）
git push origin main
gh run watch $(gh run list --workflow=deploy.yml --limit 1 --json databaseId -q '.[0].databaseId') --exit-status

# 4) 生产验证（student-facing API，务必做）
ssh aliyun-server 'curl -s http://127.0.0.1:5002/listening/tests | grep -oE "9分达人 {B}|jfdr{B}_test[0-9]" | sort -u'
ssh aliyun-server 'curl -s -I http://127.0.0.1:5002/static/listening/jfdr{B}_test1_s1.mp3 | grep -iE "HTTP/|accept-ranges"'
# 回填标准答案打到 5002 的 /api/listening/test/jfdr{B}_test{N}/submit，期望每套 40/40
```

**5) 小程序前端**：无需改代码（label 回退已兼容），但要**你人肉用微信开发者工具上传发版**
才能让小程序端学生看到——这步 Codex/CI 都做不了，交给人。若暂不发版，小程序端老板本
会把新书显示成默认拼法，但不影响网页端。

**回滚**：后端出问题 `git revert <commit> && git push`（Actions 重新部署）；mp3 是 untracked，
误传了直接 `ssh aliyun-server 'rm /root/apps/studytracker/static/listening/jfdr{B}_*.mp3'`。

---

## 6. 参照物清单（书6，你的金标准）

- 系列注册表：`api/listening_series.py`（已支持任意 jfdr 书号，别改）
- 提取格式规范：`data/jfdr6/extract/SCHEMA.md`（复制给新书，跨书通用）
- 提取产物样例：`data/jfdr6/extract/test1/part1.*`（题目/原文/解析各一份）
- 页码地图样例：`data/jfdr6/page_map.json`
- 成品金标准：`static/listening_tests/jfdr6_test1.json` + `static/listening/jfdr6_test1_s1.json`
- 对齐核心：`scripts/lcs_align.py`（别改）；驱动 `scripts/align_jfdr_listening.py`
- 判分逻辑真相源：`app.py` `_grade_listening_test_answers`（约 785-942 行）
- 上线参照：本仓库 commit `2db78ab6`（书6 导入的完整 diff）

---

## 附录 A：提取 agent prompt 模板（照抄书6 的成功模式）

**题目 agent**（每套一个）：给 SCHEMA.md 路径 + 书6 样例路径 + 该套 4 个 Part 的题目页范围；
要求按 SCHEMA 第1节写 4 个 `part{1..4}.questions.json`；忠实照抄题干/选项/指令；填空写 `$N$`+
`【   】`；判对 type 码；多选用 type 2 / 配对用 type 8；地图题 needs_image；自检每 Part 10 题
连续；**只报告每 Part 的 group 数/题型码/题数/地图页码/存疑点，不要粘贴题目正文**。

**原文+解析 agent**（每套每 Part 一个，共享同一 prompt 骨架）：给 SCHEMA.md（2、3节）+ 书6
transcript 样例；给该 Part 的听力原文页范围、真题解析页范围，**强调「以黑色横幅『听力原文』
/『真题解析』实位为准，页范围仅参考，中间『听力场景/词汇注释/交际与语言表达』跳过」**；
要求写 `.transcript.jsonl`（逐句、speaker 照抄或独白留空、按句号切句、下划线句+页边 Q 号写进
`q` 数组）和 `.analysis.json`（10 条、answer 照抄解析标题、多选合并题按合并字符串）；自检
analysis 10 条题号连续、q 覆盖题号；**只报告句数/q 覆盖/缺哪些/存疑点，不要粘贴正文**。

**翻译 agent**（每套一个）：读 merged/或 transcript.jsonl，逐句输出 `{"idx":"译文"}`，
条数与原文 1:1、口语化贴场景、数字/人名/地名保留；只报告每 Part 句数与是否一致。

**答案总表 agent**（全书一个）：读答案总表页（每页一套 40 题），照抄进 `extract/answer_key.json`
= `{"套号": {"题号": "答案"}}`，保留大小写/括号/斜杠备选；自检套数×40 条、每套题号连续。
