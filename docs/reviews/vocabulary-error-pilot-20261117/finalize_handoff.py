"""Synchronize local handoff only after the release evidence passes assertions."""

import json
import shutil
import subprocess
from pathlib import Path

BACKEND = Path("/private/tmp/studytracker-vocabulary-error-pilot-20261117")
MAIN = Path("/Users/zhouxin/Desktop/studytracker")
CLIENT = Path("/Users/zhouxin/Desktop/studytracker-release")
REPORT = BACKEND / "docs/reviews/vocabulary-error-pilot-20261117"


def replace_section(path, marker, section):
    text = path.read_text()
    current_marker = section.splitlines()[0]
    if current_marker in text:
        marker = current_marker
    if marker in text:
        start = text.index(marker)
        end = text.find("\n## ", start + len(marker))
        text = text[:start] + section + (text[end + 1 :] if end >= 0 else "")
    else:
        position = text.index("\n") + 1
        text = text[:position] + "\n" + section + text[position:]
    path.write_text(text)


def main():
    after = json.loads((REPORT / "production-after.json").read_text())
    preview = json.loads((REPORT / "production-preview.json").read_text())
    assert after["ok"] and after["process_feature_switch_off"] and after["old_schema_unchanged"]
    assert not any(after["policy_row_counts"].values())
    assert preview["read_only_preview"] and preview["historical_error_rows_to_import"] == 0
    for name in ("ci-branch.json", "ci-main.json", "deploy.json"):
        result = json.loads((REPORT / name).read_text())
        assert result["conclusion"] == "success" and result["headSha"] == after["head"]
    status = {}
    for root in (BACKEND, MAIN, CLIENT):
        status[str(root)] = {
            "branch": subprocess.check_output(
                ["git", "branch", "--show-current"], cwd=root, text=True
            ).strip(),
            "head": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            "status_before_final_docs_commit": subprocess.check_output(
                ["git", "status", "--short"], cwd=root, text=True
            ).splitlines(),
        }
    (REPORT / "worktree-status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n"
    )
    section = """## 2026-11-17 B3错词复习默认关闭版本已部署，未启用学生

- **授权与规则**：本会话明确确认的B2已实现：每日20含最多4抽查、两次隔2自然日首答成功、连续3复测日失败暂停7日/老师按词周清单、可选10不门禁；today-first，仅过载时>7日逾期转低频留事件，不导历史marker。B4试点名单/启用未确认，生产无人入组。
- **Git与工作树**：实施树 `/private/tmp/studytracker-vocabulary-error-pilot-20261117`，分支 `codex/vocabulary-error-pilot-20261117`，基线f414a126；产品188d29f6、发布HEAD **79dd34f4f07ff435e882908b5454f46fd8dff4f5** 已commit/push任务分支及main并部署。23产品/测试/CI文件SHA冻结；部署回读/后续C节/本交接独立skip-ci共享，不重复部署，最终文档HEAD用git核对。该树收尾后只应有文档提交且clean，不把当前main旧树混入发布。
- **验证**：双Python最终各349/349（3.10 43.233s、3.13 37.046s）；原259不改断言、新core32/integration24/teacher18/management16，精确命令/log在报告README。独立7边界/2双连接、教师JS6、验收器12mock+旧7安全通过；75旧model AST未变。分支CI44025269334/main CI44026399459三个业务job均success，旧advisory lint failure保留；Deploy44026399460 success。
- **生产**：13:46:47CST重启，13:48回读79dd34/23SHA一致、tracked clean、active/running、NRestarts0、实际单worker/gthread6/5002，公网200/匿名401。标准部署db.create_all新建5空表，旧schema摘要完全一致，总开关env/.env/默认OFF；0入组/队列/抽查/分配/事件。两历史样本只读preflight586/600ms、暖summary1.77/1.26ms，0写/无app或重模型导入。不是全体学生真机或并发验收。
- **预演/数据**：14:02默认SQLite ro预演20活跃、18可新入组/2有旧active批次，0历史导入/初始队列；没有--apply、生产数据写入、代答/代领/代结算或通知。管理摘要绑定显式IDs、开始时间、目标库hash、7参数，写锁下重验/全批回滚；本次默认活跃集合只用于预演，digest过期不能直接启用。指定名单后再预演，旧批需学生正常完成。
- **学生前端**：固定 `/Users/zhouxin/Desktop/studytracker-release`，`codex/miniprogram-release@d03a2749`，原76M/37U保留，本轮4原M页面文件增量+1新测试后76M/38U。451来源SHA核查、447非目标保持，实际固定源115/115、两JS语法和两页官方wcc/wcsc通过；备份 `/private/tmp/studytracker-error-policy-client-before-20261117`。完整上传根是 `/Users/zhouxin/Desktop/studytracker-release/miniprogram`，未整包/真机/上传/提审/发布。本轮精确增量归档可从远端取得，但固定源完整历史未提交包仍仅本Mac；禁止main整包覆盖。
- **新讨论与未验项**：fresh fetch看到Claude审计45167aad新增C2三日练到答对不清零，明确仍待用户确认，未替换本次B2。C节和研究补记已保留；C3差距见independent/new-plan-gap.md。双Python7路径在旧history0/2400/10000的SQL/fetch行数相同，但仅合成、未纳CI/未覆盖全部题型；非默认daily30/40会批30/40、锁内新队列扫描、完整1/3/6/ON-OFF/写锁和试点前后一周499仍待。因此不能称C2/C3完整验收，启用前先明确最终规则并补验收。教师权限/功能测试已过，但浏览器视觉因本地监听sandbox权限未完成，未留通过截图。
- **主资料与交接**：`/Users/zhouxin/Desktop/studytracker` 仍main6ded77d2，既有7M/24U保留；本轮只同步两交接、计划和报告镜像，业务未覆盖/未从此树提交。三树精确脏路径在报告worktree-status.json。后端/报告已共享；主资料和固定源其他脏业务仍仅本机。
- **下一步**：先读报告与git核最新文档HEAD；用户手动从固定根整包/真机后上传发布。试点最终规则（已实现B2或新C2）、名单和开启尚未确认；在此之前保持OFF。两周看负担/7日覆盖和保持率，D30须4–6周。不要重复询问已确认B2参数，也不要自行切换到未确认C2。未决DB锁两补丁仍未应用。

"""
    log = """## 2026-11-17 — B3错词复习默认关闭版本部署并回读通过

产品188d29f6/发布79dd34f4已commit/push分支与main；双Python349、固定前端115及两页官方编译通过，分支CI44025269334/main CI44026399459业务全过，Deploy44026399460成功（旧advisory lint仍失败）。13:46重启/13:48只读版本23SHA/服务健康/单worker6threads5002/旧schema不变/5空表/off；历史入口约0.59–0.60秒。14:02只读预演20活跃/18可入组/2旧批未完，0导入0开启。固定源4页增量+1测试精确应用，447非目标保持，未微信上传发布。审计分支新增C2未确认、C3完整验收待补，均保留为启用前待办。生产证据和交接skip-ci共享，不二次部署；旧主资料及固定其他脏业务保留。详见handoff顶部与vocabulary-error-pilot-20261117报告。

"""
    for root in (BACKEND, MAIN):
        replace_section(
            root / "docs/CODEX_HANDOFF.md", "## 2026-11-17 复习新规则B3实现完成", section
        )
        replace_section(root / "docs/WORKLOG.md", "## 2026-11-17 — B3错词复习默认关闭实现", log)
    replace_section(
        CLIENT / "docs/CODEX_HANDOFF.md", "## 2026-11-17 B3错词复习默认关闭版本已部署", section
    )
    replace_section(CLIENT / "docs/WORKLOG.md", "## 2026-11-17 — B3错词复习默认关闭版本部署", log)
    shutil.copyfile(
        BACKEND / "docs/VOCABULARY_REVIEW_PLAN.md", MAIN / "docs/VOCABULARY_REVIEW_PLAN.md"
    )
    shutil.copytree(
        REPORT, MAIN / "docs/reviews/vocabulary-error-pilot-20261117", dirs_exist_ok=True
    )
    other = Path("docs/reviews/vocabulary-cache-policy-20261117/independent-claude/README.md")
    (MAIN / other).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BACKEND / other, MAIN / other)
    print(
        "Updated three-tree handoff/worklog and original-main report mirror; no product or production changes."
    )


if __name__ == "__main__":
    main()
