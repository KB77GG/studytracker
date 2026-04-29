# 爱听写听力练习模式笔记

基于已导出的 `idictation_listening_jijing_raw.json`、页面截图和音频清单整理。后续部署时优先按这个模型实现。

## 数据范围

- 当前听力机经接口返回 58 套机经卡片。
- 每套 4 个 Part，共 232 个 Part。
- 已下载 232 个 MP3，本地路径见 `data/idictation_listening_jijing/audio_manifest.json` 的 `local_path` 字段。
- 原始数据里有 248 个 Part 响应，其中 232 个有音频、题目和逐句文本；16 个为空或非有效练习 Part。

## 入口列表

列表页的核心是“机经卡片”：

- 卡片标题：`机经 {in_book}`。
- 卡片内展示 `Part 1` 到 `Part 4`。
- 每个 Part 对应一个 `paper_id`，点击后进入该 Part 的练习页。
- 页面上看到的 `92` 是机经编号最大值，不是 92 套数量。

后续网站可以保留类似结构：

- 左侧或顶部筛选：听力 / 机经 / 题型。
- 主区网格：机经卡片。
- 卡片内直接展示 Part、题号范围、题型、完成情况。

## 路由建议

当前项目已经有 `/listening` 和 `/listening/<exercise_id>`，原本偏向“精听资源列表/播放器”。后续建议把 `/listening` 升级成听力总入口，而不是继续只代表精听。

推荐路由：

- `/listening`：听力总入口，展示学生任务、剑雅、机经入口。
- `/listening/cambridge`：剑雅列表。
- `/listening/cambridge/<book>`：剑雅某册，例如 Cambridge 20。
- `/listening/cambridge/<book>/<test>/<part>`：剑雅 Part 练习页，默认进入精听 Tab。
- `/listening/jijing`：机经列表。
- `/listening/jijing/<in_book>/<test>/<part>`：机经 Part 练习页，默认进入题目练习 Tab。
- `/student/tasks` 或学生首页：任务总入口，其中听力任务点击后跳到对应 `/listening/...` 详情页。

兼容现有老链接：

- 现有 `/listening/<exercise_id>` 不建议直接删除。
- 可以临时保留为旧精听播放器，或重定向到新的 `/listening/cambridge/...`。
- 后台布置任务里的旧 `listening_exercise_id` 需要继续可打开，避免已布置任务失效。

## Part 练习页

一个 Part 是最小练习单元，对应字段：

- `paper_id`
- `in_book`
- `test_name`
- `title`，例如 `Part 1`
- `question_name`，例如 `Q1-10`
- `question_type`
- `file_url` 或本地 `local_path`
- `content`
- `question`
- `practice_result`

推荐页面结构：

- 顶部：机经编号、Test、Part、题号范围、题型。
- 音频播放器：播放当前 Part 的 MP3。
- 题目区：按题组展示。
- 答题区：所有答案保存在本地状态，提交后判分。
- 原文区：可折叠，按时间轴展示英文/中文文本。
- 解析区：提交后显示每题答案、定位音频片段、解析。

## 音频和时间轴

每个 Part 有一个完整音频。

`content` 是逐句原文时间轴：

- `order`
- `en_text`
- `cn_text`
- `start_time`
- `end_time`

每道题也有定位时间：

- 题目字段：`start_time` / `end_time`
- 解析块里也可能有 `type: "audio"` 和 `location.start_time/end_time`

后续可实现：

- 点击题号，音频跳到该题 `start_time`。
- 解析里点击“定位音频”，播放该题片段。
- 原文逐句高亮，跟随 audio currentTime。

## 题型

已观察到的题型：

- `1` 单选题
- `2` 多选题
- `3` 表格/句子填空题
- `4` 匹配题/简答式匹配
- `5` 摘要/笔记填空题
- `6` 简答题
- `7` 地图题
- `8` 句子填空题，常带候选项
- `9` 多选题，选项在单题 `option`
- `10` 拖拽匹配题/表格匹配

题组字段：

- `type`
- `desc`
- `title`
- `question_title`
- `collect`
- `collect_option`
- `table`
- `img_url`
- `list`

题目字段：

- `id`
- `number`
- `title`
- `option`
- `display_answer`
- `analyze`
- `ai_analyze`
- `start_time`
- `end_time`
- `is_multiple`

## 渲染规则

填空类：

- `collect` 或 `table.content` 里会出现 `$题目id$` 占位。
- 渲染时替换为输入框，并绑定对应题目 `id`。
- `display_answer` 是标准答案。

选择类：

- 单选题通常使用题目自己的 `option`。
- 部分多选、流程图、匹配题使用题组的 `collect_option.list` 作为候选项。
- 多选答案通常是逗号分隔，例如 `C,D,E`。

图片类：

- 地图题、图片匹配题使用 `img_url`。
- 图片 URL 需要后续也做自托管，避免页面上线后继续依赖第三方 OSS。

表格类：

- `table.content` 是二维数组。
- 单元格里可能含 `$题目id$`，需要渲染成输入框或选择控件。

## 提交和判分

用户答案结构可按原站点风格保存：

```json
{
  "id": 14330,
  "type": 5,
  "answer": "11:30",
  "group_id": 3238
}
```

练习结果字段：

- `duration`：用时秒数。
- `zhengquegeshu`：正确个数。
- `zhengquelv`：正确率。
- `result_blanks`：每题的用户答案、正确答案、是否正确。

`result_blanks` 示例：

```json
{
  "answer": "rube",
  "blank_id": 14332,
  "group_id": 3238,
  "is_correct": false,
  "correct_answer": "tube"
}
```

后续网站可先做本地判分：

- 标准化大小写、空格、中文冒号/英文冒号。
- 标准答案里用 `/` 分隔的答案都算可接受答案。
- 多选答案按集合比较，忽略顺序。

## 推荐 MVP

第一版上线优先做：

- 机经卡片列表。
- Part 练习页。
- 本地 MP3 播放。
- 题目完整渲染：填空、单选、多选、地图/图片、表格。
- 提交判分。
- 结果页显示正确率、错题、正确答案。
- 学生登录后，把网页端练习记录同步进后台汇总，确保助教端和家长报告可见。

第二版再做：

- 逐句原文高亮。
- 点击题目跳转音频定位。
- 错题本。
- 做题记录持久化。
- 图片资源自托管。

## 后台同步要求

网页端精听和机经练习不能只保存在浏览器本地。只要学生登录，练习数据必须写入后台，否则助教端看不到，家长报告也不会汇总。

统一原则：

- 前台展示学生姓名，数据绑定使用稳定的 `student_id`。
- 剑雅精听、机经做题都写入同一套“听力练习记录”管道。
- 后台报告按学生、课程、日期、资源类型聚合。
- 助教端看到的是网页、小程序合并后的练习记录。
- 家长端报告使用同一个汇总结果，不区分学生是在网页还是小程序完成。

建议记录字段：

- `student_id`
- `student_name`
- `source`：`cambridge` 或 `jijing`
- `mode`：`intensive_listening` 或 `question_practice`
- `book`
- `test`
- `part`
- `paper_id`
- `started_at`
- `submitted_at`
- `duration_seconds`
- `audio_play_seconds`
- `completion_status`
- `score`
- `correct_count`
- `total_count`
- `answers`
- `mistakes`
- `transcript_progress`

精听需要额外记录：

- 听写句子数量
- 完成句子数量
- 单句循环次数
- 显示原文/翻译次数或状态
- 每句听写内容和核对结果

机经做题需要额外记录：

- 每题答案
- 每题是否正确
- 标准答案
- 错题列表
- 题型维度正确率

后续部署时要优先确认现有小程序/后台的报告接口和数据表。如果已有练习记录表，网页端应直接复用；如果没有覆盖精听模式，再新增一层兼容表或事件表。
