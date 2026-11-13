# `.15` realcheck 核图记录独立复核

源码：`/private/tmp/studytracker-iwa-prompt15-review-20261113`，分支 `codex/iwa-prompt15-review-20261113`，HEAD `652450ca03efaa3ae794202368a2f42a88fca18a`，基线 `cd82fc1b`。产品工作树未修改。

结论：正常的“读图文件 → 确认/改正 → checked 文件 → 评价”路径工作，但确认门禁还有两个 P2 数据完整性缺口和一个 P3 对照误拒。独立探针 **10/15**；5 个失败是下列三个缺陷的正确期望，并非运行异常。全部样本合成、模型为 FakeClient，socket.connect 被禁止，真实网络/Key/学生文件均未访问。

## P2-1：JSONL 内嵌确认记录绕过字段及题图校验

- 位置：`tools/ielts_writing_ai/realcheck.py:588`（将 `item.image_check` / `image_frozen.check` 直接交给 storage）；源入口 `load_samples` 的 199–208 行未验证或拒绝这些运行期字段。
- 已支持的 `image_description` 可以直接写进样本 JSONL。加上 `image_check` 后，加载流程保留该对象，而 `_run_sample` 不执行 `imagecheck.check_problem` 或 `require_same_image`。
- 复现：先通过正常 `imagecheck.confirm` 获得有效记录，换掉图片字节，再把读数和旧确认记录并入同一个 JSONL 样本；运行普通 `realcheck --kinds evaluate`。结果 exit 0、1 次 fake 文字调用、TA=5.0，仍向模型说明已由人核对。相同记录走 `--image-descriptions` 文件路径则正确拒绝，0 调用。
- 更小反例：`image_check={"status":"confirmed"}` 没有核对人、时间或图片SHA，也出 TA。删掉样本的 `image` 字段，同时显式加 `--require-checked-images` 和一个空 outcomes 文件，仍 exit 0 并出 TA。
- 影响：复制/合并 JSONL 与历史输入时，过期、缺审计依据的确认可被沿用，标准核图命令的保证没有覆盖所有入口。这不是恶意本机用户能否改文件的问题；两个公开输入路径对同一确认对象的核验不一致。
- 建议：要么明确拒绝 JSONL 中的 `image_check/image_frozen`，只允许受验证描述文件设置；要么统一检查记录完整性、题图SHA和确认读数指纹，并在构造模型前再次执行。没有图或无有效确认时不能出 TA/总分。

对应探针失败：`inline_check_same_image_required`、`inline_check_metadata_validated`、`require_checked_no_image_cannot_score_ta`。

## P2-2：确认记录没有绑定确认时的读数正文

- 位置：`tools/ielts_writing_ai/imagecheck.py:140`（记录只有图片SHA等元数据）及 `check_problem:39`（不核对当前 description 与确认时正文）。
- 复现：正常确认产生 checked 文件；只修改该文件的 `description`，把合成读数中的 40% 改成 90%，保持 `check` 对象完全不动；运行 `realcheck --image-descriptions edited.json --require-checked-images`。
- 结果 exit 0、1 次 fake 文字调用、TA=5.0；90% 被发给模型，仍带“checked against the image by a person”说明。这个新数值从未经过确认步骤。
- 影响：确认之后误改、误合并或替换正文不会使记录失效；“已核对”状态实际只证明题图文件没换，不能证明此次模型收到的就是已核对版本。
- 建议：记录规范化后的最终 description 指纹并在载入/生成前校验；原识图输出可另留指纹或原文。正文改变必须创建新确认，保留旧记录，不能只依靠图片SHA。

对应探针失败：`post_check_reading_change_requires_reconfirmation`。

## P3：仅核对人/时间不同也会拒绝同输入对照

- 位置：`tools/ielts_writing_ai/realcheck_compare.py:56` 把完整 `image_check` JSON（含 by/at/原模型读数）拼入样本输入指纹，随后 137–139 行在实际消息指纹校验前报“题目、作文或题图识别结果不同”。
- 复现：两份相同题目/作文/图片/最终读数，唯一区别为核对人和确认时间。各跑一次，实际消息SHA完全一致，`check_same_conditions` 仍报错。
- 影响：两个独立核对人确认同样内容后不能比较，错误信息也把审计元数据说成模型输入差异。
- 建议：对照的输入指纹只取影响模型的确认状态和最终读数；by/at等留作来源审计或提示，不影响输入一致性。保留实际messages指纹检查。

对应探针失败：`metadata_only_allows_same_input_comparison`。

## 已通过的控制场景

1. 原模型读数和题图SHA正确保留；改正不改原始文件。
2. 未确认文件只评语言、TA为空，模型没有人已核对声明。
3. `--require-checked-images` 对普通未确认文件请求前拒绝，0 次 fake 调用。
4. 正常改正并确认后，两次评价均出TA且消息指纹相同。
5. 已确认文件在题图变化后正确拒绝，0 次调用。
6. 输出路径已有不同确认文件时不覆盖。

## 复现

在任意目录执行，解释器和源码均显式指定：

```bash
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B \
  /Users/zhouxin/Desktop/studytracker/docs/design/iwa-prompt15-review-20261113/realcheck/probe.py \
  --source /private/tmp/studytracker-iwa-prompt15-review-20261113 \
  --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-prompt15-review-20261113/realcheck/evidence.json
```

当前 exit 1、10/15；修复后预期15/15。`evidence.json`只有合成输入的计数、布尔、哈希和错误文案；不含原稿或Key。

## 其他范围与限制

- `realcheck-batch`的Task 1识图阶段仍使用 `--require-ready-images`，没有确认步骤，所以新规则下只产生语言评价、无TA/总分。这与作者写明的新约定一致，此报告不把它重复列为bug；当前官方Task1的手工分阶段说明已采用 checked 文件。
- 未测试真实模型质量、真实图片读数或服务超时；未运行付费批次。没有改变现有账本、私有配置、试用服务或生产。
- 当前需要沿用“先改正、再确认、再评价”的用户选择；修复时不要自动把所有 ready 结果升级为 confirmed。
- 报告及探针仅本机新增，未commit/push/deploy；规范交接由主审统一更新，本子任务不改两份交接。
