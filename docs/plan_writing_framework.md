# 作文框架 + 话题默写 · 实施计划

## 背景

当前 studytracker 覆盖了听写、精听、选择题材料、口语等学习流程，但写作侧只有 AI 评分（`miniprogram/pages/student/hammer/`），没有"结构化写作训练"的入口。

这个功能的目标是把老师平时在 Word/讲义里整理的**作文框架原型句**和**话题范文**沉淀为结构化数据，让学生在小程序里：

1. 按题型（双边讨论/绝对化同意反对/趋势利弊/问题与解决/部分同意折中）默写**框架原型句里的占位符**，把骨架背熟；
2. 按话题（教育 / 目的与资金分配 / 大学的目的 ...）做**语料默写**——每段先翻转卡片，再看完整中英对照原文；
3. 每个话题可以关联一个作文框架，卡片按占位符顺序自动套用进框架，形成"背骨架 → 背具体话题"的闭环。

## 架构方针

- **双端分工**：Web 后台（老师/助教）负责上传、粘贴拆解、编辑；小程序（学生）只读练习。完全沿用项目既有的角色边界。
- **尽量复用，不重建**：
  - 粘贴→预览→保存：照搬 [api/materials.py:540](../api/materials.py:540) 的 `/parse` 路由模式。
  - 文本清洗：复用 [api/dictation.py:87-138](../api/dictation.py:87) 的 `_normalize_english_phrase` / `_normalize_chinese_translation`。
  - 判对：第一版精确归一化匹配（和 [api/dictation.py:542](../api/dictation.py:542) 一致），必要时二版再加模糊匹配。
- **最小闭环优先**：四个阶段逐级推进，每阶段独立可合并、可验收。

## 分支 / Worktree 策略

在开分支前，main 上先按之前讨论的顺序收尾：

1. `chore: 整理 docs/scripts，更新 .gitignore`（已暂存）
2. `feat: 听写模式扩展 + 阅读词汇错题重做 + 不确定标记`（主题 A，20 文件）
3. `chore: 前端加请求失败日志 + 清理残留 .DS_Store`

然后开 worktree：

```bash
git worktree add ../studytracker-writing feat/writing-framework-topics
```

新功能全部在 `../studytracker-writing/` 目录里开发，原目录保持干净用于随时热修线上问题。

---

## 数据模型

新增在 [models.py](../models.py) 的 `DictationBook` 相关模型之后。

### `WritingFramework` — 作文框架

```
id                  Integer PK
type_code           String(32)  unique  # discuss_both_views / absolute / trend / problem / partial
name_zh             String(64)          # "双边讨论型"
name_en             String(128)         # "Discuss both views"
description_zh      Text                # 可选，简介
sections            JSON                # 见下方结构
created_by          FK → user.id
created_at, updated_at
```

`sections` 结构：

```json
[
  {
    "heading": "引入段",
    "sort_order": 0,
    "prototype_en": "The assertion that 【讨论主体】 should focus on 【A方做法】 frequently pits 【A方现实好处】 against broader 【B方深层价值】. In my view, framing this as a binary choice is fundamentally flawed.",
    "prototype_zh": "关于【讨论主体】应侧重于【A方做法】的断言，常常把【A方现实好处】与更广泛的【B方深层价值】对立起来...",
    "blanks": [
      {"placeholder": "讨论主体", "hint": "discussion subject", "sample_answer": "university education"},
      {"placeholder": "A方做法", "hint": "A-side approach", "sample_answer": "vocational preparation"}
    ]
  }
]
```

> `blanks` 顺序和 `prototype_en` / `prototype_zh` 里 `【...】` 出现顺序严格对齐。`sample_answer` 是框架默认示范值，用于学生初学时的"看答案"模式和判对保底。

### `WritingCategory` — 话题分类（三级树）

```
id                  Integer PK
parent_id           FK → writing_category.id  nullable, index
name                String(64)
sort_order          Integer
owner_id            FK → user.id              nullable, index  # null = 公共
created_at
```

- 支持三层：大类（教育）→ 细类（目的与资金分配）→ 叶子（大学的目的 —— 话题挂这里）。
- `owner_id` 本期全部 `null`（公共）；保留字段为后续"老师私有分类"扩展用，不写业务代码。
- 自引用树用 `parent_id`，查询时用递归 CTE 或 Python 侧组装（数据量小，Python 组装够用）。

### `WritingTopic` — 话题条目

```
id                  Integer PK
category_id         FK → writing_category.id  index
title               String(128)               # "大学的目的"
question_text_en    Text                      # 英文原题
question_core_zh    Text                      # 核心探讨（中文审题要点）
tr_logic            JSON                      # 四段逻辑要点
framework_id        FK → writing_framework.id nullable  # 可关联一个框架
created_by, created_at, updated_at
```

`tr_logic` 结构：

```json
{
  "opening":   "破除二元对立表象 --- 定调\"职业准备\"与\"综合发展\"实为深度共生关系。",
  "body1":     "肯定就业导向合理性 --- 优质课程提供核心生存技能 --- 毕业生若脱离市场需求将被动落经济淘汰。",
  "body2":     "警惕极端功利化 --- 局限于谋生会扼杀创新与批判思维 --- ...",
  "conclusion":"重申双重目标绝不互斥 --- 整合职业训练保生存与学术熏陶促升华 --- 达成双赢。"
}
```

### `WritingTopicSection` — 话题的段落语料

```
id                  Integer PK
topic_id            FK → writing_topic.id  index
sort_order          Integer
heading             String(32)                # "开头段" / "主体段一" / ...
content_en          Text                      # 保留 【...】 标记的完整英文段
content_zh          Text                      # 保留 【...】 标记的完整中文段
cards               JSON                      # 自动解析出的卡片数组
```

`cards` 结构（解析时自动生成，下方"解析器"小节详述）：

```json
[
  {"zh": "大学教育", "en": "university education"},
  {"zh": "职业准备", "en": "vocational preparation"},
  {"zh": "对职业发展的眼下追求", "en": "the immediate pursuit of career advancement"},
  {"zh": "社会和个人发展", "en": "societal and personal development"}
]
```

**关联框架时的约束**：如果 `WritingTopic.framework_id` 非空，则每个 `WritingTopicSection` 的 `cards` 数量**必须等于**框架对应 section（按 `sort_order` 对齐）的 `blanks` 数量。保存时校验，不满足则返回 400。这样渲染"这道题填好的完整原型句"时，`cards[i].en` 正好替换 `blanks[i].placeholder`。

### `WritingPracticeRecord`（阶段 4）— 学生练习记录

```
id, student_id FK, practice_type  # 'framework_blank' / 'topic_card'
ref_id                             # framework.id 或 topic.id
section_index, card_index          # 定位到具体哪个空
user_input, is_correct, attempt_count, created_at
```

独立于 `StudentAnswer` / `DictationRecord`，粒度更细，不混入现有批改体系。

### 迁移脚本

新建 `create_writing_tables.py`（沿用现有 `add_*_column.py` 习惯），并追加到 [deploy.sh:28](../deploy.sh:28) 远端执行链里。

---

## 粘贴协议（老师在 Web 上传时复制的格式）

### 通用规则

- 顶层节用 `[节名]` **独占一行**（如 `[标签]`、`[题目]`、`[逻辑]`、`[语料]`）。
- 段落标题用 `【段名】` **独占一行**（如 `【开头段】`、`【主体段一】`）。
- 行内的关键词组用 `【...】` 嵌在文本里。**独占一行的 `【...】` 视为段落标题，嵌在句中的 `【...】` 视为卡片词组**——解析器靠"是否独占一行"来区分。

### 话题拆解模板

```
[标签]
教育 / 目的与资金分配 / 大学的目的

[题目]
题目: Some people believe the aim of university education is to help graduates get better jobs. Others believe there are much wider benefits of university education for both individuals and society. Discuss both views and give your opinion.
核心探讨: 大学教育的终极目的之争——是偏向现实功利的职业生存技能准备，还是兼顾深远的个人素养提升与社会宏观发展。

[框架]
discuss_both_views

[逻辑]
【开头段】
破除二元对立表象 --- 定调"职业准备"与"综合发展"实为深度共生关系。
【主体段一】
肯定就业导向合理性 --- 优质课程提供核心生存技能 --- 毕业生若脱离市场需求将被动落经济淘汰。
【主体段二】
警惕极端功利化 --- 局限于谋生会扼杀创新与批判思维 --- 倡导跨学科与伦理培养塑造全面公民。
【结论段】
重申双重目标绝不互斥 --- 整合职业训练保生存与学术熏陶促升华 --- 达成双赢。

[语料]
【开头段】
英文: The assertion that 【university education】 should focus on 【vocational preparation】 frequently pits 【the immediate pursuit of career advancement】 against broader 【societal and personal development】. In my view, framing this as a binary choice is fundamentally flawed.
中文: 关于【大学教育】应该侧重于【职业准备】的断言，经常将【对职业发展的眼下追求】与更广泛的【社会和个人发展】对立起来。在我看来，将此设定为非黑即白的二元选择是根本性错误的。

【主体段一】
英文: ...
中文: ...
```

> `[框架]` 是可选节。填了就把这条话题和已有框架关联起来。

### 作文框架模板

```
[类型]
discuss_both_views  双边讨论型  Discuss both views

[描述]
适用于 Discuss both views and give your opinion 题型，先破二元对立，再让步两方，最后整合双赢。

[段落]
【引入段】
原型英: The assertion that 【讨论主体】 should focus on 【A方做法】 frequently pits 【A方现实好处】 against broader 【B方深层价值】. In my view, framing this as a binary choice is fundamentally flawed.
原型中: 关于【讨论主体】应侧重于【A方做法】的断言，常常把【A方现实好处】与更广泛的【B方深层价值】对立起来。在我看来，将此设为非黑即白的选择是根本错误的。
示范值:
  讨论主体 = university education
  A方做法 = vocational preparation
  A方现实好处 = the immediate pursuit of career advancement
  B方深层价值 = societal and personal development

【主体段一 让步A】
原型英: ...
```

---

## 解析器

新建 `api/writing.py`，内部结构：

```
parse_topic_text(raw: str)     -> dict          # 模板 → 结构化预览
parse_framework_text(raw: str) -> dict
_extract_cards(en: str, zh: str) -> list[dict]  # 从两段文本里自动抽卡片
_split_into_sections(raw: str)  -> dict         # 通用分节器
```

### 卡片自动抽取（核心逻辑）

```
def _extract_cards(content_en: str, content_zh: str):
    # 只匹配"嵌在行中"的 【...】，不匹配独占一行的段落标题
    pattern = r'【([^【】\n]+)】'
    en_tokens = re.findall(pattern, content_en)
    zh_tokens = re.findall(pattern, content_zh)
    if len(en_tokens) != len(zh_tokens):
        raise ValueError(f"英文标记 {len(en_tokens)} 个，中文标记 {len(zh_tokens)} 个，无法对齐")
    return [
        {"zh": _normalize_chinese_translation(zh), "en": _normalize_english_phrase(en)}
        for zh, en in zip(zh_tokens, en_tokens)
    ]
```

复用 [api/dictation.py](../api/dictation.py) 里的归一化函数。

### 框架对齐校验

话题保存时（`POST /writing/topics`）：

```
if topic.framework_id:
    framework = WritingFramework.query.get(topic.framework_id)
    for section, fw_section in zip(topic.sections, framework.sections):
        if len(section.cards) != len(fw_section["blanks"]):
            return 400, f"'{section.heading}' 有 {len(section.cards)} 张卡片，但框架对应段需要 {len(fw_section['blanks'])} 个"
```

---

## 判对逻辑

```python
# api/writing.py
def judge_answer(user_input: str, target: str) -> bool:
    norm_user = _normalize_english_phrase(user_input).lower()
    norm_target = _normalize_english_phrase(target).lower()
    return norm_user == norm_target
```

第一版精确归一化匹配。小程序端也可以前端同步归一化 + 比对，省去每次调接口的网络开销，仅在"最终提交/打卡"时调一次服务端记录接口。

后续若需要模糊匹配（拼写一两个字母错也算对），再引入 Levenshtein，阈值 ≤2。

---

## 后端 API

### Web 管理端（`@role_required(TEACHER, ASSISTANT)`）

| 方法 | 路径 | 作用 |
|------|------|------|
| POST | `/writing/frameworks/parse` | 粘贴 → 预览 JSON，不落库 |
| GET  | `/writing/frameworks` | 列表 |
| POST | `/writing/frameworks` | 保存（接受预览 JSON） |
| PUT  | `/writing/frameworks/<id>` | 编辑 |
| DELETE | `/writing/frameworks/<id>` | 删除 |
| POST | `/writing/topics/parse` | 粘贴话题 → 预览 JSON |
| GET  | `/writing/topics?category_id=` | 按分类列话题 |
| POST | `/writing/topics` | 保存（若三级分类不存在自动创建） |
| PUT  | `/writing/topics/<id>` | 编辑 |
| DELETE | `/writing/topics/<id>` | 删除 |
| GET  | `/writing/categories/tree` | 完整三级分类树 |

### 小程序学生端（`@require_api_user(STUDENT)`）

| 方法 | 路径 | 作用 |
|------|------|------|
| GET  | `/miniprogram/student/writing/frameworks` | 框架列表 |
| GET  | `/miniprogram/student/writing/frameworks/<id>` | 框架详情（含 sections + blanks） |
| GET  | `/miniprogram/student/writing/categories/tree` | 话题分类树 |
| GET  | `/miniprogram/student/writing/topics/<id>` | 话题详情（含 sections + cards + 关联框架） |
| POST | `/miniprogram/student/writing/practice/record` | 阶段 4：记录一次练习（qid + user_input + is_correct） |

判对在前端完成（和服务端共用同一套归一化规则的 JS 实现）。服务端只在"记录"接口里保存结果，不做重复判对。

---

## Web 端页面

- `templates/writing_admin.html` + 对应路由挂在 [app.py](../app.py)
- 布局：
  - 顶部菜单沿用现有 base
  - 左侧两个 Tab：「作文框架」「话题分类」
  - 右侧：选中项的详情/编辑表单
  - 右上角「上传/编辑」按钮 → 弹 modal
    - modal 内三个下拉（类别 / 大类 / 细类，对应图二布局）
    - 两个按钮「填入话题拆解模板」「填入作文框架模板」→ prefill textarea
    - 「保存并生成特训」→ 先调 `/parse` 预览 → 用户确认 → POST 落库
- 交互追求可用，不追求设计，和现有 `templates/tasks.html` / `templates/materials.html` 对齐即可

---

## 小程序端页面

```
miniprogram/pages/student/writing/
  index/                 # 入口：两个 Tab [作文框架 | 话题]，各自列表
  framework/             # 某个框架的详情 + 占位符默写
  topic/                 # 某个话题完整学习页（对应图一）
  components/
    flip-card/           # 翻转卡片（CSS transform-style: preserve-3d; rotateY(180deg)）
    blank-input/         # 默写输入框（带实时判对、正确变绿、错误抖动）
```

- 学生首页 [miniprogram/pages/student/home/](../miniprogram/pages/student/home/) 加入口图标。
- 翻转卡片用纯 CSS 动画 + `wx:if` 切换面，不引第三方库。
- 判对：前端直接调归一化 JS（和后端 `_normalize_english_phrase` 同规则），无需网络往返。
- 话题页若关联了框架：在「TR 逻辑」下方、「语料默写」上方，多渲染一块"框架套入预览" —— 用 `cards[i].en` 替换 `framework.sections[i].blanks[i].placeholder` 生成完整英文，让学生一眼看到"骨架 + 具体内容"。

---

## 分阶段落地

| 阶段 | 内容 | 预估 | 验收 |
|------|------|------|------|
| **1. 骨架** | 4 表 + 迁移 + `parse_topic_text` / `parse_framework_text` + CRUD API + pytest | 1–2 天 | curl 走通"粘贴→解析→保存→读取"，框架对齐校验生效 |
| **2. Web 编辑端** | `writing_admin.html` + modal + 预览 | 1 天 | 老师在 Web 录入 1 个框架 + 1 个话题，刷新后仍在 |
| **3. 小程序学生端** | 3 个页面 + 2 个组件 + miniprogram API | 2–3 天 | 学生能浏览话题、翻卡、默写并实时判对 |
| **4. 统计打通**（可选） | `WritingPracticeRecord` + notebook 展示 + 老师侧查看 | 1 天 | 老师能看到学生做了哪些、错哪里 |

阶段 1 → 2 → 3 顺序严格，阶段 4 用起来再决定。每个阶段单独 PR。

---

## 验证清单

阶段 1：
- `pytest tests/test_writing_parser.py`（新增）覆盖：正常模板、卡片数量不匹配、框架对齐失败、分类自动创建。
- `curl -X POST /writing/topics/parse` 手测一个完整样例。

阶段 2：
- 浏览器里登录老师账号，走完"粘贴 → 预览 → 保存 → 刷新可见"全流程。
- 编辑已保存的话题并再次保存，分类不重复创建。

阶段 3：
- 小程序开发者工具里，学生账号进入写作入口，浏览列表 → 进某话题 → 翻卡 → 默写 → 看判对效果。
- 关联了框架的话题，渲染"框架套入预览"正确。

阶段 4：
- 做完一次练习 → 在老师端 Web 能看到记录 → notebook 里能看到错词。

---

## 开放项 / 已知风险

1. **模糊匹配何时引入**：第一版精确匹配若学生反馈"差一个逗号就判错"，阶段 3 末尾可加 Levenshtein（阈值 ≤2）。
2. **原型句变体**：一个框架可能有多套原型句（正式/口语），当前模型一个段落只存一组。若需要变体，下版给 `sections[].variants` 扩展。
3. **话题/框架的版本管理**：老师编辑后学生已做的练习是否要迁移？第一版简单处理——直接覆盖，练习记录保留 snapshot（存入 `WritingPracticeRecord.user_input` 已足够追溯）。
4. **中英分类名翻译**：前期只用中文，英文名字段留着以后 i18n 用。
