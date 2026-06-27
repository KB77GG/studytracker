# StudyTracker 架构地图 & 技术债清单

> 配套约定见根目录 [CLAUDE.md](../CLAUDE.md)。本文档回答两个问题：
> 1. 代码现在长什么样（地图）；2. 哪里在烂、按什么顺序还债（backlog）。
> 体检日期：2026-06-27。

## 1. 目录地图

```
studytracker/
├── app.py                 # ⚠️ 9,240 行：主应用 + 43 个 web 路由 + 报表/导出逻辑（巨型，待拆）
├── config.py              # 配置
├── models.py              # ⚠️ 1,562 行：50 个表全在一个文件（含未删的 legacy）
├── toefl_practice.py      # 1,641 行：托福练习模块
├── api/                   # API 蓝图（小程序 & 部分 web 接口）
│   ├── miniprogram.py     # ⚠️ 5,187 行 / 143 个函数：小程序主接口（巨型，待拆）
│   ├── dictation.py       # 1,688 行：听写
│   ├── materials.py       # 1,274 行：题库/材料
│   ├── entrance.py        # 1,011 行：入学测
│   ├── ielts_eval.py      # 雅思评测
│   ├── tencent_soe.py     # 腾讯口语评测
│   ├── auth_utils.py       # 鉴权工具（目前唯一的“公共工具”模块）
│   └── ...
├── miniprogram/           # 微信小程序前端
│   ├── pages/{student,teacher,parent}/...   # 27 个页面
│   ├── utils/request.js   # ✅ 统一请求封装（但有 5 个页面绕过它）
│   ├── utils/demo-data.js # 访客演示数据
│   └── app.wxss           # 全局样式（仅 5 行，几乎没用上）
├── scripts/               # 55 个一次性/迁移脚本（不参与 lint）
├── tests/                 # 17 个 unittest 文件
└── docs/                  # 文档
```

## 2. 当前的层次问题（为什么会烂）

- **没有 service/数据访问层**：校验、判分、统计、写库全挤在路由函数里。`app.py` 单文件出现 54 次 `db.session.commit`、87 次 `.query.filter`。
- **巨型文件 + 巨型函数**：`app.py` 里 `tasks_page()` 563 行；`api/miniprogram.py` 里 `submit_reading_vocab_practice()` 258 行，混了校验/解析/判分/写库/通知 6 件事。
- **逻辑重复**：`_normalize_*` 清洗函数在 7 个文件里各写一份；前端访客模式判断复制了 33+ 次；wxss 按钮/卡片样式几乎 95% 重复。
- **没有护栏**（已于本次补上）：之前无 lint / 格式化 / CI 测试关卡，坏代码能直达生产。

## 3. 已经立起来的护栏（2026-06-27）

| 文件 | 作用 |
|---|---|
| `CLAUDE.md` | 人 & AI agent 写代码前必读的硬约定 |
| `pyproject.toml` | ruff + black 配置（lint/格式化口径统一） |
| `.pre-commit-config.yaml` | 提交前自动检查（需 `pre-commit install` 启用） |
| `.github/workflows/ci.yml` | CI：轻量测试（强制）+ lint（先只报告） |
| `requirements-dev.txt` | 开发工具依赖 |
| `.editorconfig` | 编辑器基础风格统一 |

> CI 的 lint 现在是 `continue-on-error`（只报告不阻断）。**还债清单清到一定程度后，删掉那一行即可升级为强制门禁。**

## 4. 技术债清单（按性价比排序，逐项可独立做、独立验证）

> 原则：每项单独一个分支/commit，改完跑 `python -m unittest discover -s tests` 确认绿，再合并。
> 涉及行为的改动，先补/跑相关测试再动手。
>
> ⚠️ **验证前提**：后端重构需在能跑**完整测试套件**的环境做（本仓库 ML 依赖较重）；
> 前端（小程序）重构需在**微信开发者工具**里跑通后再合，CI/命令行无法验证小程序运行时。
> 不要在无法验证的环境盲改后直接 push 到已发布的线上代码。

### P0 — 高性价比、低风险（建议先做）

- [ ] **抽出共享文本归一化模块**（如 `api/text_utils.py`）。⚠️ **注意：不是无脑去重。**
  实测 `api/entrance.py:103` 与 `api/materials.py:70` 两个同名 `_normalize_question_options()`
  **逻辑不同**（entrance 版保留纯字母选项给配对/地图题），直接合并会改行为弄坏配对题。
  正确做法：只收敛**确实逐字节相同**的辅助函数（如可能共享的 `_split_inline_options`、
  `_option_text_starts_with_key`），分叉的版本要么保留、要么参数化后**配测试**再统一。
- [ ] **前端：堵掉绕过 `request.js` 的 5 处直连 `wx.request`**：`student/dictation/practice`（7 处）、`student/speaking/practice`（3 处）、`student/stats`（2 处）、`student/dictation/index`、`student/speaking/index`。改成统一封装，401/访客逻辑才一致。
- [ ] **前端：抽公共 wxss**（按钮/卡片/配色变量）进 `app.wxss` 或共享样式文件，消除“改个按钮色要动 5~10 个文件”。
- [ ] **访客模式收敛**：把 33+ 处 `guestMode` 判断抽成一个公共 helper（如 `utils/guest.js`）。

### P1 — 中等收益，需小心验证

- [ ] **拆 `api/miniprogram.py`（5,187 行）**：按主题切成多个蓝图文件（schedules / stats / grading / reading-vocab …），路由签名不变，纯搬运 + import，逐块搬、逐块测。
- [x] **`submit_reading_vocab_practice()`（256 行）已拆**（2026-06-27）：判分逻辑抽进纯模块
  `api/reading_vocab_grading.py` + 共享 `api/text_utils.py`，handler 瘦到 ~126 行，新增 14 例单测，
  完整套件 109 tests 全绿。**模式可复用到下面这些。**
- [x] **`get_parent_stats()` 聚合已抽离**（2026-06-27）：percent/今日状态/周趋势/学科分布下沉到
  `api/stats_utils.py`（单源化 round(x/y*100)），+10 例纯单测 + 首个 `/parent/stats` 路由测试。
  附带挖出并立项一个既有 bug：is_studying 查询用错列名（start_time→started_at），生产中指示灯从不亮。
- [x] **`get_student_stats()` 纯逻辑已抽离**（2026-06-27）：streak/勋章/均率/等级下沉到 `stats_utils.py`
  （含替换裸 `except: pass` 的 streak 算法），109→76 行，+12 纯单测 + `/student/stats` 路由测试。
- [~] **`get_student_today_tasks()` 评估后跳过**：~130 行是 ORM→dict 序列化（含 token 生成副作用），
  无可抽的纯计算，硬抽零可测性收益却有风险。如要瘦身需先补路由测试再拆 I/O，性价比低，暂缓。
- [ ] **其它超长函数**：`get_task_detail()`（122 行）、`get_student_today_tasks`（如上，需谨慎）等，按需评估。
- [x] **is_studying bug 已修**（2026-06-27）：除列名（start_time→started_at）外，还发现并修了
  **时区基准 bug**（检测用 datetime.now() 但 started_at 存的是 utcnow()，差 8 小时仍永远 False）；
  +4 回归用例。家长端"正在学习"指示灯现可正常点亮。
- [ ] **拆 `pages/student/hammer/index.js`（2,187 行 / 97 state 字段）**：把录音、TTS、评测、计时拆成独立模块/behavior。**改前务必先手动回归口语全流程**（这页最容易出锅）。

### P2 — 结构性，时间充裕再做

- [ ] **拆 `app.py`（9,240 行）**：报表/导出（`tasks_page` 563 行、`export_report_pdf` 377 行）抽成独立蓝图 + service。
- [ ] **`models.py` 按主题拆包**（user / task / dictation / material / speaking …）。
  ⚠️ **不要删所谓的 "legacy" 模型！** 实测 `Task` 全后端被引用 **238 次**、`StudySession` 8 次、
  `ListeningSegmentResult` 7 次——都还活着；且第 465 行 "Legacy models" 注释把
  `MaterialBank/Question/StudentAnswer` 等**核心表**也圈进去了，按注释删会删掉题库和学生答案。
  这块真正的工作是漫长的 `Task → PlanItem` 数据迁移（独立大工程），不是删代码。先把那条注释改准确。
- [ ] **给 `api/miniprogram.py` 的核心路由补测试**（目前 49 路由仅 5 个有覆盖）。

### 维护提醒

- 依赖用 `>=` 松绑定；若遇到第三方升级导致的诡异问题，考虑改为固定版本（pin）。
- `requirements.txt` 含较重的 ML 依赖（whisper/kokoro/weasyprint），完整测试套件因此较重；轻量逻辑测试已在 CI 独立跑。
