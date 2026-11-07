# 听力行布局修复：独立复核

结论：**GO（本地代码与自动化复核）**。未发现本次修改引入的漏题、重复控件、题号映射错误或阅读渲染回归。浏览器实际宽度、截图和生产发布由主 agent 验收；本报告不把自动化结果等同于浏览器视觉检查。

- 日期：2026-11-07。
- 工作树：`/private/tmp/studytracker-cambridge-fix-20261107`。
- 分支：`codex/cambridge-explanations-fix-20261107`。
- 复核基线：`be9b122f49c5fd452dfb0b9fbc89e2f9f07cc0bc`；被复核的 JS/CSS 尚属该基线上的本机改动。
- 独立复核者只读业务文件；唯一写入为本报告。交接文档、提交和部署由主 agent 统一处理。
- 被复核文件 SHA-256：`static/js/practice_renderers.js` = `39385b6357d0a410dc118dd5e529605a3b363f8ac121b0275b5b5232e008697f`；`static/css/practice_shell.css` = `6fac00ee5658267385a582809397dffdc0bc857f89bb0d43812d279264deb2ab`。

## 直接核对的行为

1. 剑 13 T1 S4：Q35 的 `and to deal with new dangers.`、Q36 的 `of urban and rural blackbirds.`、Q37 句点、Q38 的 `by producing lower levels of hormones.` 均跟随所属题目的输入框。Jonathan Atwell 的介绍位于 Q37 与 Q38 之间。Q34 前面的 Emilie Snell-Rood 介绍仅出现一次。
2. 共享题干采用 `collect` 源行前，要求所有目标存在、行号不倒序、span 中的数字 ID 恰好与该组题目逐个同序且各出现一次。匹配失败保留完整已提取题干，不按猜测的题间边界拆句。
3. 共享 span 包含中间静态行；源单元格先标记已使用，避免后来再次作为上下文输出。单个源行的前缀、输入框和末尾文字一起渲染。
4. 静态 label/value 仅按同一源行合并；如剑 18 T1 的 `Name: Sadie Jones` 与 `Year of birth: 1991`。所有表单生成 flow 布局，避免纸面左右单元格被误判成两列题目。Unicode minus `−` 保留项目行语义。
5. CSS 的输入宽度约束只位于 `.practice-form__content`；双空基线规则只位于听力页面。980px 内的旧 columns 规则现在具有足够选择器优先级。阅读仍通过自身题干/控件路径渲染。
6. 最后增量已独立复核：共享源行分支不额外渲染仅从拼接 title 推断、没有源单元格索引的 label，剑 12 T7 Q34 的 Claire 前缀不再重复；源行已有的真实标签保留。缺失/外部 ID 的 fallback 是一个连续完整题干块。

## 覆盖与结果

剑 4–21 共 144 个 JSON。听力 165 个组、1252 题进入 `renderForm`；阅读当前题库 **0 个组**进入该路径。共享源行修复直接覆盖听力 39 个 cluster、102 题。

独立源行顺序探针将上述 39 个 cluster 的源单元格按原行连接，替换 ID 为当前题号，并在渲染文本中依次查找完整行。**86 行全部同序命中，其中 11 行是中间静态行；遗漏/倒序 0**。新布局测试进一步验证全部 165 个组的 **677 个非空题后后缀**仍在所属题目行上，避免仅检查“文本出现过”而漏掉上下行错位。

复跑真实模板函数（包括 `build_simulation_payload` 和正式专项快照转换）：

| 科目/模式 | payload 数 | 组数 | 题数 / 逻辑控件数 |
| --- | ---: | ---: | ---: |
| 听力普通 | 72 | 568 | 2880 / 2880 |
| 听力模拟 | 72 | 568 | 2880 / 2880 |
| 听力专项 | 287 | 561 | 2843 / 2843 |
| 阅读普通 | 72 | 613 | 2880 / 2880 |
| 阅读模拟 | 72 | 613 | 2880 / 2880 |
| 阅读专项 | 216 | 609 | 2859 / 2859 |

结果：缺失/重复/额外 ID、题号映射异常、原始占位符泄漏均为 0；源文本单词遗漏候选为 0。专项仍沿用既有隔离：听力 7 组 37 题、阅读 4 组 21 题为 `manual_review`，不纳入可发布专项；本次未新增隔离。

“原有 4 框”经数据与测试核实为剑 18 T3 Q1–4 的**数字占位框**。已有真实模板测试同时覆盖普通编号和专项 `source_number` 重编号；当前通过。未在剑桥表单找到对应的 4 个字母占位框。

## 可复现验证

工作目录均为上述实施树。最终增量后独立执行以下 Node 命令，**67 通过，0 失败**；真实模板全量探针也在最终增量后再次通过：

```sh
node --test tests/test_practice_renderers.js tests/test_cambridge_stem_controls.js tests/test_cambridge_form_layout_css.js tests/test_cambridge_reading_introduction.js tests/test_cambridge_reading_figures.js tests/test_cambridge_line_layout.js
```

复跑已有全库真实模板探针时，将结果写到临时路径，保留先前发布审计的历史 JSON：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python - <<'PY'
from pathlib import Path
path = Path('docs/reviews/cambridge-release-20261107/presentation-stems.py').resolve()
source = path.read_text().replace(
    "Path(__file__).with_suffix('.json').write_bytes(result)",
    "Path('/private/tmp/cambridge-layout-independent-controls.json').write_bytes(result)",
)
exec(compile(source, str(path), 'exec'), {'__file__': str(path), '__name__': '__main__'})
PY
```

本机结果：`/private/tmp/cambridge-layout-independent-controls.json`；源行顺序探针结果：`/private/tmp/cambridge-layout-independent-lines.json`。临时结果不属于提交产物，以上覆盖数字已记录于本报告。

## 边界

- 这是本次布局修改的结构、源行与回归复核，不是重新逐题进行全库语义终审，也没有操作共享浏览器。
- 不完整/外部 ID 的合成源 span 会回退到完整题干，保留已知题目的控件；若无效源本身含 `$99$` 一类外部标记，旧静态上下文仍可显示该原始标记。基线同样如此，当前 144 套真实数据未出现该情况，未作为本次修复扩张项。
- 本报告写入时，本轮布局代码尚未由独立复核者提交、推送或部署；最终状态以主 agent 的发布记录和交接文档为准。

## 追加复核：anti-poaching 精确断词修复

业务冻结提交 `be45283f`，基于已发布的 `038bd8e0`。独立复核结论 **GO**。本节更新上述首次审计的时间边界；最终部署状态仍以 README 和规范交接为准。JS SHA-256 为 `62dcdb5e5d1a6bc388f2bd931360ec87ee74d1ea42c1ed0dc5a0ee50d251affc`。

此次业务 diff 只有 `flowFactEntries` 的精确例外及专用测试：两条静态源行必须分别只有一个单元格，文本严格等于 `• strict enforcement of anti` 和 `− poaching laws`，单元格索引相邻，且源行号恰差 1，才显示为 `• strict enforcement of anti-poaching laws`。不依据 `anti` 前缀泛化处理其他连词，不改原 collect、题号、ID、答案或评分。

独立执行：

```sh
node --test --test-name-pattern='anti|minus' tests/test_cambridge_line_layout.js
```

2 个定向测试通过，包含真实 C18 T1 及四种近似文本/中间说明反例。另用只读合成探针验证四种边界：中间空行、前行额外并排 cell、后行额外并排 cell、中间为真实题目。这四种均不合并，原文字保留，输入对象未改变。真正的 `− tracking devices were fitted...` 条目继续单独显示。

快照兼容另作单套验证：以 C18 T1 S4 构造正式 `build_snapshot` 后序列化/反序列化的冻结结构，通过 `public_snapshot` 和 `review_snapshot`，再调用真实听力模板 `renderGroup`。普通、模拟、冻结作答、冻结复盘四种结果均只出现一次完整 anti-poaching 条目，并保留全部 10 个逻辑控件；前两种题号 31–40，后两种 1–10，ID 映射一致。冻结对象及渲染输入均未被修改。该例外只依赖保留的静态源文本和相邻行，所以旧快照的重编号/新 ID 不影响显示修正，无需改写存储快照或重算历史成绩。

本次未读取真实学生快照或数据库，未重复全库测试，未修改业务或执行发布。完整 Python/Node 回归及线上验收由主 agent 负责；独立 agent 仅追加本节。
