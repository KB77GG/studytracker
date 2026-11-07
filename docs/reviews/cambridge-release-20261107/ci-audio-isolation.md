# CI 音频测试资源隔离修复

工作树 `/private/tmp/studytracker-cambridge-fix-20261107`，分支 `codex/cambridge-explanations-fix-20261107`，基线 `5099ac41` 已由 root commit/push；本轮仅修改 `tests/test_question_type_practice.py`，报告目录为既有 untracked 内容。child 未 commit/push/deploy，不改服务、题库、数据库或小程序。规范交接由 root 统一更新。

分支 CI `42365904819` / job `128383786885` 的 6 failures + 1 error 均来自该测试：它读取个人 Mac 的绝对音频路径，Git 未包含 MP3；CI 缺文件导致真实 `validate_group` 安全门将听力组全部标为 blocked，内容分类/快照断言因无可发布样本失败。生产逻辑无需放宽。

修复：按真实题库 Section.audio 引用在独立 TemporaryDirectory 创建文件存在性 fixture（该服务仅检查 is_file，不进行音频解码）。保留全部原内容/分类/渲染器/快照断言。新增独立空音频目录回归，实际运行 build_group_index，确认所有听力组 blocked、缺文件原因明确、默认 filter/catalog 不可选择，阅读索引完全不变。不跳过测试，也不 mock validator 的返回值。

验证（cwd 为工作树）：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_question_type_practice -v
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check --no-cache tests/test_question_type_practice.py
git diff --check
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_cambridge_content_corrections tests.test_cambridge_answer_corrections tests.test_cambridge_listening_corrections tests.test_cambridge_reading_corrections tests.test_cambridge_reading_stems tests.test_cambridge_pair_grading tests.test_ielts_exam_payload tests.test_cambridge_review_delivery tests.test_question_type_review tests.test_question_type_practice tests.test_mock_exam_review tests.test_mock_exam_template_isolation tests.test_question_type_practice_contract -q
```

结果：目标 **12/12**；Ruff/diff 通过；完整 CI Python 集 **120/120**（原119项加新增资源门禁回归）。另以下无本机音频模拟 **12/12**：两个旧 static/listening 根的 exists 返回 false，任何非临时 fixture 的 MP3 的 is_file 返回 false；未改动实际本机资源。

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python - <<'PY'
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

real_is_file, real_exists = Path.is_file, Path.exists
def isolated_is_file(path):
    if path.suffix.lower() == '.mp3' and not any(part.startswith('question-type-practice-audio-') for part in path.parts):
        return False
    return real_is_file(path)
def isolated_exists(path):
    if str(path).endswith('/static/listening'):
        return False
    return real_exists(path)
with patch.object(Path, 'is_file', isolated_is_file), patch.object(Path, 'exists', isolated_exists):
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('tests.test_question_type_practice'))
sys.exit(not result.wasSuccessful())
PY
```

交接时核实 root 已将测试修复提交并推送为 `0f51632c`；工作树 tracked clean，报告目录仍 untracked。后续由 root 确认新 branch CI 成功后继续既有发布流程，child 未核实本轮部署。文件存在性 fixture 不代表播放/音频内容验收；实际媒体版本与播放安全由既有独立 audio contract 测试和生产资源核验覆盖。
