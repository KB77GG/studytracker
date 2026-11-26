# 网页背词审查分支：补测、推送与启用门槛

用户认可上一份验收记录，并授权提交、推送且运行 CI，**仅限 `codex/web-vocabulary-task-page-20261126`**。不合并或推送 main，不部署，不开启功能。原已认可的验收正文保留在 `claude-verification-paste.md`；其中“仅本机”等表述是当时状态，本文件记录后续变化。

## 本轮补测

本轮不改变产品行为。新增的两类自动验收纳入原有 CI 测试模块：

1. `tests/test_practice_vocabulary_routes.py::test_feature_off_blocks_all_registered_routes_before_any_sql`：从实际 blueprint `url_map` 枚举路由，以成功打开页面取得的学生会话、CSRF、身份头及同源 Origin 请求。全部页面/API 操作必须返回 `403 feature_disabled`；请求期间包括 SELECT 在内零 SQL，10 类学习表保持空，任务仍 pending。覆盖页面、state 和全部 9 个 POST，包含 sync 与所有 review 写操作。
2. A02：从 `f81a5e4a4d81282eb67b994a4cfcc5574fb78747` 的真实应用生成同一组合成任务的列表响应，与当前应用比较，不能用同一份新代码的开关差异代替历史基线。11 个输入任务筛选后输出 8 个任务（助教、老师各 4 个），每项 26 字段、每种开关状态 208 字段，与顶层字段/分组/顺序全部一致；涵盖未来、截止、今日、完成及未开始/进行中/已提交/已完成。当前 off/on 各自匹配历史响应，没有归一化或忽略字段。生成器及 fixture/历史 JSON 在 `tests/fixtures/`，说明见 `tests/fixtures/README-practice-task-list.md`，精确命令见 `validation/prepush-a02-commands.json`；Python 3.10 再生成历史快照与 3.13 字节一致。该缺口已补；它仍不代表浏览器跳转实测。

原 `manifest.json`、`verification-recheck.json` 及 `validation/full-*` 是上一轮冻结证据，保留原文。新增补测会改变测试文件散列；当前提交候选以 `prepush-manifest.json` 和 `validation/prepush-*` 为准，不把旧日志冒充本次测试。

## 本轮实际验证结果

| 检查 | 结果 |
|---|---|
| Python 3.13 合并回归 | 230/230，33.806 秒 |
| Python 3.10 合并回归 | 230/230，37.312 秒；仍仅对旧测试使用原 `datetime.UTC` 别名兼容入口 |
| 日期门禁 pytest | 两版本各 20/20，0.32 / 0.34 秒 |
| Node | 58/58 |
| 新增 Python/测试/捕获脚本 Ruff；diff check | 通过 |
| 历史来源独立复核 | 7 个源码 SHA 与 `git show f81a5e4:<path>` 一致 |

完整命令参数和输出见 `validation/prepush-commands.json`、`prepush-full-py313.log`、`prepush-full-py310.log`、`prepush-date-*`、`prepush-node.log`。新增 4 个测试（全路由关闭 1、历史来源及 off/on 对比 3），此前 226 个测试继续通过。原单独原生 3.10 产品编译结论仍有效，本轮产品文件 SHA 全部未变。

当前候选 `prepush-manifest.json` 含 34 文件，原 30 文件中仅 `.github/workflows/ci.yml`、两个测试文件变化；另新增 4 个历史 fixture/说明文件。CI 为调用 Node 的 Python 测试显式安装 Node 20，并把小程序判分 6 项、日期显示及 20 项 pytest 明确登记。全部新增模块已纳入 CI，无需 CI 拉历史 Git 对象或联网生成快照。

## 发布前的两道门槛

**默认关闭部署之前**：本轮两项补测通过、分支 CI 完成、Claude 代码审查，再取得明确部署授权。部署授权与本次分支推送授权不同。生产访问、配置和数据库变更本轮均不执行。

**给学生开启之前**：以下项目仍待实际操作，不因为自动测试通过而勾选：

| 必测项 | 操作与通过标准 |
|---|---|
| A08 系统中文输入法、长按 Enter | Mac 系统拼音在 Chrome 和 Safari 各测一次；候选确认不得提交或越题，长按不得多次提交。有条件再测 Windows 微软拼音。 |
| 订正页刷新 | 在订正中刷新页面，仍停在订正并显示正确答案，不跳过。 |
| A10 真断网和丢响应 | DevTools Offline 后提交；另在服务端保存后丢弃回包，再刷新，恢复到正确位置且只计一次。503 模拟不代替此项。 |
| A11 手机互切 | 真实手机或微信开发者工具，使用合成任务，不上传：正常答题中途切换，以及网页订正中途切换，核对手机不支持订正时的行为与薄弱词记录。 |
| A14 原生缩放 | Chrome 1280 和 1440 两档宽度分别原生 125%/150%；检查主要操作和溢出。缩小视口不代替此项。 |
| A13 真实界面 | 老师和家长实际界面查看同一合成任务的完成、成绩和用时。 |

可以在开启后补：音频慢加载/8 秒超时（建议假 Audio 单测）、两浏览器不同学生交叉操作、跨 03:00 截止、真实题库材料和音质。它们仍是未验证项，不写成通过。

现有开关为全局 `PRACTICE_VOCABULARY_WEB_ENABLED`，默认 false。本轮不新增名单开关；全量开启或名单试点留到启用决策，当前没有开启授权。小程序代码、上传、提审和发布均不在本轮范围。

## Git 与远端结果

实施工作树 `/private/tmp/studytracker-web-vocabulary-20261126`；开发基线及本轮 fetch 后 `origin/main` 均为 `f81a5e4a4d81282eb67b994a4cfcc5574fb78747`。Claude 文档来源仍为 `479cab8a`，未合并。

提交、推送与 CI 的最终结果将在执行后记录于本节及 `ci-review.json`。`.github/workflows/ci.yml` 监听全部分支；`deploy.yml` 仅监听 main。本轮只推任务分支，main 不变。
