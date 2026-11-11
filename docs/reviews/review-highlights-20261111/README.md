# 刷题/模考同页高亮与解析复盘（2026-11-11）

用户明确授权修好后部署，并要求现有复盘页直接展示原题、高亮、学生答案、对错和解析。最终版本已取消早期草案的额外「查看原卷」按钮。

实施树 `/private/tmp/studytracker-review-highlights-20261111`，分支 `codex/review-highlights-20261111`，基线 `a673a613786a397b855c2feff9c74ddca5e6f2ff`；业务提交 **fb5b2747f4428ee5383b763c3cceb0e9f72178a3**。发布结果见本文末节及规范交接。

## 最终行为

- 普通听读：提交、刷新和复盘重绘后保留原高亮。旧解析卡外围空白曾改变源文本指纹，已移除；动态答案工具不再改变源文本坐标。
- 两个既有学生模考复盘入口直接展示听力/阅读原题，恢复同场考试的标记；每道题的学生答案、正确答案、对错和解析默认展开，解析标明实际显示题号。保留写作、老师批改和全局「只看错题」，无需额外按钮或跳页。
- 使用同源、自动适应内容高度的原题工作区，隐藏重复页头与底栏，保留听力音频、Section/Passage和题号导航；不把两个原题脚本合并到同一全局作用域。父子消息同时校验origin与window来源；高度有界、可缩小，筛选可逆并保留混合对错的共享题干。
- 子页只读恢复高亮，不注册标记编辑工具条，不调用导航shell/添加浏览器历史，不提交答案或保存草稿；保存成绩直接复用，不新增判分路径。整场及对应科目交卷后才开放，错误token/无效科目/缺题库拒绝；保留no-store/no-referrer。
- 共享源渲染维持模拟/复盘response元数据，覆盖旧阅读C5T2/C9T3的控件推断差异；复盘音频资料恢复不改变旧定位空白。阅读考试定时器缺元素异常、复盘返回自身的历史上下文问题同步修复。
- 不改题库、评分规则、数据库schema、小程序。高亮仍是原浏览器localStorage及原14天清理策略，不能跨设备同步或恢复已清理记录。

## 验证与复跑

以下cwd为实施树；所有数据库测试使用合成内存库，不import生产app或读真实学生库。

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -W ignore::DeprecationWarning -W ignore::ResourceWarning -m unittest tests.test_practice_highlight_coordinates tests.test_selection_highlight_contract tests.test_ielts_exam_payload tests.test_mock_exam_student_review tests.test_mock_exam_template_isolation tests.test_mock_exam_review_workflow tests.test_practice_history tests.test_question_type_practice_contract tests.test_question_type_review tests.test_mock_exam_runtime -q
node --test tests/*.js
node --test tests/test_practice_renderers.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_practice_highlight_coordinates -q
node tests/test_dictation_spell_queue.js
git diff --check
```

- 主回归 **83 Python / 342 Node**通过，见python-tests-inline.log/node-tests-inline.log。最后加解析显示题号（不使用内部ID）后，相关renderer **30/30**及144套坐标 **4/4**另验通过；新增1条题号用例未混计前轮342。
- 全144套完整试卷（72听力/72阅读）普通作答→复盘、模拟→原题复盘的源文本逐字一致。定向Ruff、JS语法检查通过；新坐标、嵌入消息/筛选、权限测试已接CI。
- Chrome真浏览器C18T1：原考试页选择高亮→直接进入现有总复盘，不点额外原卷入口即恢复；两科保存的错误/正确答案及解析默认可见；只看错题开关可逆、换部分/刷新保留，返回成绩成功，两种学生入口一致。内嵌页不额外增加history，页面异常和提交/保存网络请求均为0。
- 1440与390px下无横向溢出或iframe纵向裁切；截图inline-desktop/inline-mobile/inline-reading-detail/inline-listening-detail.png已目视检查，inline-browser-result.json保留文本/可见性/几何证据。测试均为合成已交卷状态，不声称完整真实模考交卷/真机微信长按。预览无真实音频，出现音频404提示，不以此验收播放能力。

```sh
# 终端1：全新合成预览；内存SQLite单连接，因此串行处理QA请求。
/Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/review-highlights-20261111/preview.py
# 终端2：浏览器依赖位于独立QA目录，不加入产品依赖。
PLAYWRIGHT_MODULE=/private/tmp/studytracker-highlight-qa-runtime/node_modules/playwright node docs/reviews/review-highlights-20261111/browser-inline.cjs
```

runtime安装：`npm install --prefix /private/tmp/studytracker-highlight-qa-runtime --no-audit --no-fund playwright@1.58.2 jsdom@26`。脚本使用本机Chrome executablePath，其他系统需调整。证据无真实学生内容或凭据。

## 工作树与发布

旧资料树 `/Users/zhouxin/Desktop/studytracker` 仍main@6ded77d2，开工behind111、原7modified/23untracked入口未覆盖，只镜像交接；精确原状态在source-state.json。旧资料树不含修复，不能从它发布。其他既有worktree未改。本次29个业务/测试/CI文件已提交，报告及交接单独同步。

发布通过现有GitHub Actions主线推送链路，无schema迁移、人工生产业务库写入、付费调用或小程序上传/提审/发布。生产验收仅Git/文件哈希/systemd/匿名HTTP，不读取学生表。runtime-manifest.json覆盖14个运行文件及gunicorn.conf.py，保留workers1/gthread/threads6/5002。

## 发布验收结果

业务 **fb5b2747f4428ee5383b763c3cceb0e9f72178a3** 已push任务分支及main。分支CI [42957976383](https://github.com/KB77GG/studytracker/actions/runs/42957976383)、主线CI [42958318865](https://github.com/KB77GG/studytracker/actions/runs/42958318865)整体success，三个测试job均success；存量advisory lint failure未被当作全仓lint通过。Deploy [42958318830](https://github.com/KB77GG/studytracker/actions/runs/42958318830) success，对应JSON证据已保存。

生产 `/root/apps/studytracker` HEAD与业务提交一致，tracked clean/113 untracked（历史文件未动），2026-11-11 12:18:40 CST起active/running，NRestarts=0、验收时重启后warning以上0。runtime-manifest.json的15文件全匹配，公网7个JS/CSS响应200且SHA全匹配。只读服务器复跑命令（manifest仅路径/哈希，不含凭据）：

```sh
REVIEW_MANIFEST_B64=$(/Users/zhouxin/Desktop/studytracker/.venv/bin/python -c 'import base64,pathlib; print(base64.b64encode(pathlib.Path("docs/reviews/review-highlights-20261111/runtime-manifest.json").read_bytes()).decode())')
ssh -o BatchMode=yes -o ConnectTimeout=10 root@47.110.45.193 "cd /root/apps/studytracker && .venv/bin/python docs/reviews/cambridge-release-20261107/verify_release.py --expected-head fb5b2747f4428ee5383b763c3cceb0e9f72178a3 --manifest-b64 $REVIEW_MANIFEST_B64"
PLAYWRIGHT_MODULE=/private/tmp/studytracker-highlight-qa-runtime/node_modules/playwright node docs/reviews/review-highlights-20261111/production-smoke.cjs
```

production-browser.json：真实公网听读页面200，选择高亮后只在DOM触发客户端复盘展示，原高亮恢复；假token复盘404；pageerror和写网络请求均0。该脚本禁止GET/HEAD以外的网络方法；不读取真实学生会话、不真正提交作答。私人模考复盘由合成环境浏览器+权限测试及生产文件SHA一致性覆盖，不声称线上私人端到端已验。公网文件校验初次本机系统CA缺证书，改用certifi有效信任链后成功，没有关闭TLS校验。

本地5097预览已停止，测试浏览器已关闭；没有schema/依赖迁移或手工生产数据写入。报告和两交接作为独立 `[skip ci]` 文档提交同步，最终文档HEAD见git log，生产维持业务fb5b2747，避免文档更新触发无必要重启。学生用原作答浏览器刷新既有复盘页即可；原14天/本浏览器存储限制仍在，已清理的高亮无法找回。
