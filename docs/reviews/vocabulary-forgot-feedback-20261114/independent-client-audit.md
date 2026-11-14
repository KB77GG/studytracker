# 独立客户端复核

- 审阅对象：`/private/tmp/studytracker-vocabulary-forgot-client-20261114`，来源为实际固定发布树 `/Users/zhouxin/Desktop/studytracker-release` 的前端快照；没有拿旧桌面主线的小程序代替发布源码。
- 独立探针：`independent_client_probe.js`。直接加载两个真实页面模块和其真实 request/归一化工具，以合成 `wx` 网络和页面状态执行；没有外网、真实学生、真实微信运行时或数据库操作。
- 复现命令（cwd 本报告所在仓库）：`node docs/reviews/vocabulary-forgot-feedback-20261114/independent_client_probe.js /Users/zhouxin/Desktop/studytracker-release > docs/reviews/vocabulary-forgot-feedback-20261114/independent_client_probe_baseline.json`。
- 基线结果：11 个新行为契约检查中 2 通过、9 失败。失败涵盖正常/超时忘记结果直接消失、末题自动结算等；其中一项要求新增显式继续方法，因此该项基线失败同时反映旧接口不具备此动作，并不计为独立的另一个产品缺陷。
- 候选命令：`node docs/reviews/vocabulary-forgot-feedback-20261114/independent_client_probe.js > docs/reviews/vocabulary-forgot-feedback-20261114/independent_client_probe.json`。
- 候选结果：11/11，exit 0。覆盖两页面成功保存后停留、旧提交/键盘确认不推进、原词答案发音、超时保存响应恢复、显式继续与重复旧事件、末题确认前不结算、末题重练响应、已结算复习恢复、复习门禁发生时先展示已保存忘记答案。
- 未发现新的阻断性缺陷。修改仅调整展示与显式继续，不更改首答判分、后台排程或复习领取。跨日 recovery-only 原自动跳转已由实现方修复，本探针确认其新行为。
- 现有边界：退出后重新进入仍按后台已保存进度恢复；本轮没有引入跨退出持久化的“已读答案”状态。微信真机画面/音频、实际学生次日领取不在本探针证据范围。
- 本审阅未修改产品、实现方测试、生产、固定发布树、commit/push/deploy 或微信包状态；只在报告目录写入脚本、合成输出和本文。主任务负责规范交接汇总。
