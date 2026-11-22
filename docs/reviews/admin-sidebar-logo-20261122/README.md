# 后台侧栏 Logo 统一（2026-11-22）

用户反馈材料库与任务管理左上角图标不一致。两页实际引用同一 `static/brand/sagepath-mark.png`，任务页的外部 CSS 和旧内联 CSS 重复覆盖公共侧栏：绿色底、压缩高度、176px侧栏、较小标题，并继承42px flex-basis，造成图标低对比、非正方形和窄侧栏下的标题换行风险。

## 修复

仅修改 `static/tasks_workspace.css` 与 `templates/tasks.html`：移除两处任务页侧栏/品牌/导航专属样式，统一继承 `static/admin_suite_v2.css`；在901–1120px将任务页搜索/操作区放到标题下，避免标准侧栏宽度挤压页头。图片、业务逻辑、表单及数据库不变；不新增 `!important` 覆盖层。

实施树 `/private/tmp/studytracker-admin-sidebar-logo-20261122`，分支 `codex/admin-sidebar-logo-20261122`，基线 `e9d1069a34407c00a0abbc4e164d5e5066836dfd`，产品发布提交 `b68d49d8ceec127871456c39f5a7d0b41cc75965`。开工 clean，2产品文件已commit并原子push至任务分支及main。主资料树 `/Users/zhouxin/Desktop/studytracker` 仍 `main@6ded77d24586327ad94e151e172ae4811b4a2eed`；没有把最新产品代码复制到旧主树。主树同名报告目录保留补丁和证据，防止临时实施树被清理后丢失。

## 已运行检查

在实施树运行：

```sh
node --test tests/test_admin_suite_v2_structure.js tests/test_tasks_workspace_structure.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -c 'from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader("templates")); env.get_template("tasks.html"); env.get_template("materials.html"); print("Jinja templates compile: 2 passed")'
git diff --check
```

结果：既有Node检查7/7通过，Jinja两模板编译通过，diff检查通过。未运行全仓业务测试，改动为局部CSS删除。

## 浏览器验收

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/admin-sidebar-logo-20261122/visual_check.py
```

Chrome本机运行；1440/1280/1024/768/390px，修前/修后各两页面，共20个场景。`visual-results.json` 中 `currentPass=true`，修后5组品牌样式一致：42×42容器、34×34图片、白底、17px标题；标题均单行且不超出侧栏、文档无水平滚动。768/390px两页验证抽屉打开、Escape关闭和遮罩点击关闭。无页面脚本异常、无缺失静态资源。主审人工查看1440/1280/1024桌面及390抽屉截图，修正了首次1024页头挤压，再复跑通过。

**范围**：实际 `base.html`、`tasks.html`、`materials.html` 全模板与全部页面样式，单条合成任务；移除业务JS，仅保留原侧栏脚本，不导入app、不连接数据库。素材/字体离线缓存于vendor、生成页面在site（可重建缓存，.gitignore排除，不进入提交）。未验证真实账号任务提交或线上页面；浏览器基线确认绿底/非方形差异，但未复现用户截图中的Sage Path换行，不将不同设备字体/缩放当成已确定原因。1024px任务筛选栏/列表存在修前即有的横向挤压，文档无滚动不代表这些既有内部布局全部正常，本次未扩修任务工作台。首轮Chrome被沙箱阻止，已通过授权在沙箱外完成；脚本仅离线页面，未访问生产。

## 发布结果（2026-11-22）

用户明确授权后，发布前fetch确认origin/main仍e9d1069a；独立复核产品两SHA与验收manifest一致，7项Node和部署spell queue守卫通过。产品 `b68d49d8ceec127871456c39f5a7d0b41cc75965` 已commit并原子push任务分支及main；部署 [44979890266](https://github.com/KB77GG/studytracker/actions/runs/44979890266) success。

11:17:23 CST服务器重启，11:17:56 CST只读验收 `ok=true`：HEAD正确、tracked clean、8文件SHA一致、5公网CSS/Logo资产200且SHA一致；5002 /tasks及/materials匿名302登录、/login 200；服务active/running、NRestarts0，运行时1worker，配置gthread/threads6/5002，重启后warning以上0。原113未跟踪服务器资源保留。

验证器 `verify_release.py` 经SSH stdin运行，精确参数与exit0见 `release-commands.json`，返回见 `production-acceptance.json`，未导入app或查询学生/数据库。标准部署脚本执行既有幂等迁移及服务重启；本任务无新增schema、业务数据操作或微信上传/提审/发布。未执行线上登录态视觉或真实任务写入验收。公网CSS为no-cache，刷新页面即可重新校验。

main CI44979890271、分支CI44979890021均success，三个业务job全过，既有advisory lint仍failure；完整状态见 `release-facts.json`。既有非阻断lint问题与此次CSS修改无关，未扩修。

## 交接与恢复

本次产品已上线，可从远端main或任务分支取得。验收报告、两交接以单独 `[skip ci]` 文档提交同步，不重复部署；文档提交后的工作树HEAD以Git回读为准，服务器业务HEAD仍b68d49d8。旧主资料树保留原7M/24U及并行D3复查记录，仅镜像本次报告和滚动交接；它的旧产品源码未升级，不能直接部署旧树。

下一位agent先核实际Git/服务状态再继续；无待发小程序。若需要回滚本次产品，明确回滚授权后对b68d49d8做revert并走标准部署（不要reset到落后155提交的旧主树）。

归档 `product.patch` 使用零上下文格式；移植到对应干净基线时用 `git apply --check --unidiff-zero` 和 `git apply --unidiff-zero`。已上线产品以发布提交为准。
