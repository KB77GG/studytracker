# Git Workflow

这个仓库建议只保留一个长期分支：`main`。

## 基本规则

- `main` 只放已经验证、随时可以部署的代码
- 每次做一个需求或修一个问题，都从 `main` 拉一个短期分支
- 分支合并回 `main` 后就删掉，不保留长期功能分支
- 同时做多个需求时，用 `git worktree` 开多个目录并行处理

## 分支命名

- 新功能：`feat/<topic>`
- 修复：`fix/<topic>`
- 重构：`refactor/<topic>`
- 运维或发布：`chore/<topic>`

示例：

- `feat/reading-notebook-server-source`
- `feat/task-dictation-mode`
- `fix/wechat-task-submit`

## 推荐日常流程

1. 先同步主线：`git switch main && git pull`
2. 开新分支：`git switch -c feat/<topic>`
3. 完成修改后先本地验证
4. 只提交本次需求相关文件，不要直接 `git add .`
5. 合并回 `main`
6. 删除短期分支

更稳的做法：

- 先看状态：`git status --short`
- 按文件添加：`git add path/to/file`
- 提交前再看一次：`git diff --staged`

## Worktree 用法

当你要并行开发两个功能时，不要在一个目录里来回切分支。

示例：

```bash
git worktree add ../studytracker-reading feat/reading-notebook-server-source
git worktree add ../studytracker-dictation feat/task-dictation-mode
```

这样每个目录只负责一个需求，互不干扰。

## 提交前检查

- `git status --short` 里不要混入无关文件
- 不要把本地数据库、日志、生成数据直接提交
- 优先提交代码、模板、迁移脚本、必要文档
- 遇到很多 `??` 未跟踪文件时，先判断它们是不是你真正想进仓库的内容，再决定是否加入 `.gitignore`

## 当前仓库建议

- 平时不要直接在 `main` 上开发
- 小程序发布前，确认后端已部署且前端代码已上传
- 服务器不要手改业务文件；确实要改，也要尽快回写到仓库
