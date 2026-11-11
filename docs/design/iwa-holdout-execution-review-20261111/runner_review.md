# 执行器离线复核：付费运行前仍有阻断项

审阅基线：`/private/tmp/studytracker-iwa-holdout-review-20261111`，`codex/iwa-holdout-review-20261111`，HEAD `76ab483fe0c944c1c7c0164cdf53d2bca9f1bbd7`。只读产品源码；两个探针及结果在主资料树本目录。未读取 Key、`.env`、学生答卷或机构材料，没有网络请求，没有改变两个业务工作树或提交。

## P1：请求预算只在内存中预留，中断和并发均可超过阶段上限

- `run_comparison.sh:71–76` 的 `calls_of` 只读取最终 `report.json`，没有报告即按 0 次计；`:83–105` 启动时合计一次；`:117–118` 将未完成目录改名，然后从头重跑这一组。整个 launcher 没有互斥锁或持久预算预留。
- `realcheck.py:53–61,103` 的 reservation 只是 `Recorder.records.append`，并没有落盘。CLI `__main__.py:177–195` 等整次 `realcheck.run` 完成后才生成报告；`realcheck.py:1779–1798` 才写 report / run_data / raw_calls。
- 实际 CLI 离线集成验证：一次评价先后两次调用时，结果目录都尚不存在。故实际请求发出后被中断，磁盘没有可供重启计数的记录。
- shell 原样运行 + 离线 transport stand-in 的复现：首次执行在 5 次模拟发送后自杀，exit 137；重跑相同命令时日志为“已用 0 次，剩余最坏 184，授权 184”，随后跑完 184 次。独立模拟账本合计 **189 > 184**。
- 同一输出目录同时启动两份原 shell：预置其他已完成步骤共156次，未完成dev/Flash最多28次，两个进程都看到156+28≤184，同时各发出28次。独立模拟账本合计 **212 > 184**。二者均进入模型步骤，没有第二实例拒绝。

这是离线调用替身的边界证明，不是实际超额付费记录。正向样例能跑通不证明中断上限有效。

建议在真实 HTTP 发出前用同一持久账本原子预留并 fsync；未知/中断的已预留请求保守计为已用。全批次持锁，重启核对 source/input/settings 指纹；每次发送检查总量及文字/识图子上限，不能只查报告。未完成步骤不能悄悄复用原整组上限。

## P1（第二阶段）：共享10次总上限没有落实“识图最多2次”

- shell `:53` 给 Flash 10次预算，假定8文字+2识图。
- `realcheck.py:345–363` 只有识图成功才缓存 `readings`。首次识别返回 HTTP200 但不可用时，第二轮会再次识图。
- 实际 `realcheck.run` 离线集成：2张合成图 × 2轮，识图替身每次返回不可读，得到 **4次识图 +4次文字 =8次**。总数没有超过10，但已超过明确的2次识图范围。
- 应为每张图缓存“已经尝试”的状态（含失败），或使用独立识图账本硬限2次；识图未成功时先停止第二阶段并报告，不将额外调用转嫁到文字预算。

## P2：说明规定失败超过一半要停，执行器实际全部失败也继续

- `codex-run.md` 要求某模型某组最终失败率超过一半时停止。
- CLI `__main__.py:197–200` 仅在 `report.aborted`（首次鉴权/网络失败）时返回3；所有回答都因为JSON/结构不合格也可以返回0。
- shell `:138–142` 只看 exit code，随即创建 `.done`；没有读取最终成功率。
- 实际 CLI 替身：1篇两次均非法JSON，结果失败、calls2、aborted=null，exit0。shell替身进一步模拟每组0成功，仍执行全部 **10个模型/组步骤**、写10个`.done`，最终exit0。
- 应完成每个模型/组后按所有计划样本作分母检查失败率并停机；成功率不应依赖进程exit0替代。

## P2：Mac 原生 bash 3.2 的中文紧邻裸变量会破坏日志编码

- 新 shell 又出现 `$STAGE：`（`:101`）、`$rc，`（`:137`）、`$rc（`（`:139`）和 `$v（`（`:41`）等写法。
- 原生 `/bin/bash` 下复现：阶段输出成为 `阶段 \xbc\x9a已用 ...`，严格 UTF-8 解码抛 `UnicodeDecodeError`，阶段值丢失；探针为继续核对预算才用 `errors=backslashreplace` 保存这个结果。不是对日志进行了修复。
- 全部变量统一 `${VAR}`，再用 Mac 原生 bash + UTF-8 严格解码验证正常和异常路径。

## 已有隔离与仍需显式配置的条件

- realcheck 用临时 SQLite，不打开主系统/试用数据库；文字/识图原始回答会包含正文和思考内容，只应写私有结果目录。
- `DRY=1` 显式fake及不存在的环境文件，正常路径不会使用真实模型；本次探针另外阻断socket或完全不导入HTTP客户端。
- 真实模式保留外部 `IWA_ENV_FILE`、`IWA_LLM_BASE_URL` 等环境覆盖；发布树本身没有本机试用Key。正式执行需显式绑定已核对的独立配置/官方端点，不能靠继承shell环境。该项是执行前条件，未读取真实配置核验，未另做假定性缺陷归类。
- 本轮没有跑真实服务、生产或完整产品套件，父agent负责正常彩排/全套验证与最终交接。

## 可复现命令

从 `/Users/zhouxin/Desktop/studytracker` 运行：

```sh
.venv/bin/python docs/design/iwa-holdout-execution-review-20261111/runner_probe.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out docs/design/iwa-holdout-execution-review-20261111/runner_probe.json
.venv/bin/python docs/design/iwa-holdout-execution-review-20261111/runner_realcheck_probe.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out docs/design/iwa-holdout-execution-review-20261111/runner_realcheck_probe.json
```

两探针只用自己的临时目录/合成资料，退出码0表示复现脚本正常完成，具体缺陷布尔与计数见JSON；不表示产品通过验收。所有证据与新增审阅脚本目前仅本机，未commit/push/deploy。

发布说明：以上是复核完成时的工作状态；本次报告与合成探针由主审一并同步功能分支，最终提交见 git log。私有数据与演示结果未提交。
