# 活跃计时独立复核结论

复核对象为本轮工作树中的实际 `practice_vocabulary_timing.js`、事件接线和页面状态接线，未修改产品或现有测试。

**结论：未发现剩余必须修项。** 独立探针 16/16 通过。检查时提出的两项边界已处理：完成值不被迟到 `finish()` 覆盖；损坏 v2 冻结秒数不能超过对应窗口的总跨度。旧 journal 的提交 payload 仍原样重放，旧墙钟值不导入新的活跃计时记录；服务器已保存的结算结果仍是显示依据。

精确命令，工作目录 `/private/tmp/studytracker-web-vocabulary-20261126`：

```bash
node docs/reviews/web-vocabulary-task-page-20261126/active-time/independent_timing_probe.js > docs/reviews/web-vocabulary-task-page-20261126/active-time/independent-timing-probe.json
```

探针读取真实模块。结果覆盖：10 分钟 + 离开 5 小时 + 15 分钟 = 25 分钟；空闲上限和重新操作；隐藏时操作不续命；重叠标签求并集；任务/身份/复习 session 隔离；迟到旧标签不补冻结等待；刷新重放；已完成不可变；仅写存储失败后恢复；禁用/错误界面停计；旧版本与损坏记录；大时钟前跳；真实事件接线对程序滚动、focus、重复按键的排除，以及 IME 和 pagehide/pageshow。

边界说明：

- 这是用户选定的“可见且最近 5 分钟有操作”估算，最后一次操作后的空闲宽限仍计入，不能称为逐秒的纯专注时长。
- 每 5 秒存一次区间；正常隐藏/离页立即落盘。进程崩溃或读取另一活跃页尚未落盘的最后区间可能保守少计，不能承诺零误差。
- 只在同一浏览器的本地存储范围汇总，不是跨设备累计。拒绝/清空本地存储后无法承诺跨刷新恢复。
- 假时钟、模拟浏览器事件、内存重建不是原生 Chrome/Safari、实际关机或网络端到端验收。

本轮没有 commit、push、部署或生产访问。规范交接由主 agent 汇总。
