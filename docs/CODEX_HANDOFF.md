# StudyTracker — Codex 跨电脑开发交接

> 这是滚动更新的“当前状态”，不是聊天记录或永久变更日志。
> 最近更新：2026-07-22（Asia/Shanghai）。

## 使用规则

1. 开工先完整阅读根目录 `AGENTS.md`、`CLAUDE.md` 和本文件。
2. 随后运行 `git status --short --branch` 与 `git log -5 --oneline`。如果实际 Git 状态与本文不一致，以 Git 和可复现验证结果为准，并更新本文。
3. 不覆盖或删除来源不明的本地改动；先确认它们是否属于用户或另一项任务。
4. 收工或换电脑前更新“当前基线、近期完成、验证状态、发布状态、待办与下一步”。
5. 不在本文记录密码、令牌、Cookie、服务器密钥或学生隐私。

## 当前基线

| 项目 | 当前状态 |
|---|---|
| 仓库 | `git@github.com:KB77GG/studytracker.git` |
| 分支 | `main` |
| 业务代码基线 | `9607915a`（导入剑桥雅思21听力阅读真题（4套）） |
| 远端 | 准备提交本文时，业务基线 `main` 与 `origin/main` 一致；精确 HEAD 以 Git 为准 |
| 本次交接提交范围 | 仅 `AGENTS.md` 与 `docs/CODEX_HANDOFF.md` |
| 后端生产 | 本次建立交接机制时未重新核验当前 HEAD 是否已部署 |
| 小程序 | 上传、提审、发布状态尚未在本文件中得到确认 |

### 原电脑尚未同步的在途内容

准备提交本文时发现以下来源未确认的在途内容。它们不属于本次交接机制提交，另一台电脑拿不到其实际改动；不要擅自覆盖、删除或重复实现。

已跟踪文件的本地修改：

- `app.py`
- `models.py`
- `templates/admin/mock_exams_form.html`
- `templates/exam/process.html`
- `templates/exam/result.html`

未跟踪内容：

- `data/reading_study/browse.html`
- `data/reading_study/preview.html`
- `docs/dictation_input_policy_proposal.md`
- `prototypes/`
- `scripts/build_writing_test_practice.py`
- `scripts/migrate_mock_exam_writing.py`
- `services/mock_exam_writing.py`
- `static/listening_tests/images/ielts21_test2_s2_21-t2-p2-15-20.png`
- `static/writing_tests/`
- `templates/exam/writing.html`

从路径看，其中一批内容与写作模考有关，但本次没有审阅其实现或验证状态。

## 近期完成

### 单词任务严格拼写与提交失败防复发

- 提交：`ad258bc0`（2026-07-21，单词任务启用严格拼写与教师兼容授权）。
- `practice` 和 `spell` 两条学生答题流程均增加了切词锁，避免连续点击导致跨题或漏记。
- 提交接口报告队列缺题时，前端会根据 `queue_incomplete` 定位漏掉的单词并引导补做，不再只显示失败后卡住。
- 共用漏题识别逻辑位于 `miniprogram/utils/dictation-review.js`。
- 同批改动还包含严格英文输入和教师/助教兼容授权逻辑。

### 随后的主线改动

- `918126e4`（2026-07-21）：助教后台增加单词输入授权。
- `9607915a`（2026-07-21）：导入剑桥雅思21听力阅读真题（4套）。

## 验证状态

- 在 `ad258bc0` 状态下，Python 完整测试共 288 项通过，仓库内 JavaScript 测试全部通过。
- 本次只新增交接文档与入口规则，不涉及业务代码，未重复运行完整业务测试。
- 后续提交 `918126e4`、`9607915a` 的验证情况应以各自提交记录、CI 和实际复测为准；本文不推断未亲自验证的结果。

## 发布状态

- 后端和小程序是两条独立链路，详见 `CLAUDE.md`。
- 后端：建立本文时尚未重新核验生产服务器是否运行 `9607915a`。
- 小程序：此前已准备上传单词防复发改动，但本文没有“已上传/已提审/已发布”的确认记录。
- 下一位执行发布操作的 Codex 必须分别记录：后端生产提交、小程序上传版本、审核状态和实际发布时间。

## 当前待办与下一步

1. 如果继续单词任务问题，先确认小程序线上版本是否已经包含 `ad258bc0`，再做真实账号回归。
2. 如需核验生产，确认服务器 Git HEAD、`studytracker` 服务状态及生产端口 `5002`；禁止在生产机运行 Whisper/Kokoro 等本地重模型。
3. 处理本地未跟踪内容前先向用户确认归属，避免混入无关提交。
4. 每次换电脑前更新本文件，并在获得用户明确授权后 commit、push；否则在交付消息中明确说明仍只存在本地。

## 收工更新模板

更新时替换过期内容，不要在文件末尾无限追加：

```markdown
最近更新：YYYY-MM-DD HH:mm（Asia/Shanghai）

当前分支 / HEAD / 远端状态：
本次完成：
涉及文件或提交：
已运行验证及结果：
后端部署状态：
小程序上传 / 审核 / 发布状态：
尚未提交或未跟踪内容：
已知问题：
建议下一步：
```
