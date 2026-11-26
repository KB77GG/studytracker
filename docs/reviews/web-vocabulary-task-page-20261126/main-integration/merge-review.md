# 合入 main 的独立复核

2026-11-26，只读审计 `/private/tmp/studytracker-web-vocabulary-20261126` 的合并工作区。审查时 `HEAD=f6f0f10445c4746bdbd1153f46db2411a0bda577`，`MERGE_HEAD=f5b06cc3cb44fa1f77720ca771bde3134c83a71d`，共同基线 `f81a5e4a`。只写本报告；没有修改产品、Git 状态、提交、推送、服务或生产数据。测试结果由 root 的独立执行日志提供，本审计不把静态检查称为回归或真设备验收。

## 结论

未发现阻止本次合并的遗漏或语义覆盖。

- `app.py`：全部函数定义按 AST 对照双方与基线，结果为两边独立变更的完整并集。词汇的 `_practice_task_payload`、`api_practice_tasks` 与 main 的两个资源加载函数、`tasks_page`、`admin_mock_exams_create` 都与其来源版本相同，无同名函数双边改写。词汇列表仍通过默认关闭开关筛选和构造 payload，批量词书/状态排序接线保留；main 的热榜布置和固定模考加载接线保留。
- `api/miniprogram.py`：词汇共享结算、PlanItem 同步、原 dictation order helper 抽取与 main 的 ninefen 阅读/图片路径修改完整共存。所有函数 AST 对照匹配；新增 imports 无遗漏。`submit_task` 的词汇分支仍先经过现有日期门禁，再调用共享结算服务；main 未改写这段。
- `services/web_practice_tasks.py` 与 main 字节一致。新增热榜阅读网页引导没有覆盖词汇页 service。
- CI 解析后按每个 job 比较所有父版本步骤：四个 job 的非步骤配置不变；父版本所有具名步骤和 `uses` 均保留，`run` 的原命令 token 顺序均仍存在于对应合并后步骤。词汇 core/timing、Node 20 setup、pytest 依赖/日期测试，与 main 的 ninefen auth、冲刺目录/组卷、冲刺 HTTP tests 都在。
- 两份交接文档：两个父版本的全部非空行，均仍能按原顺序在合并文档中找到，不只是标题保留。

审查时三个产品文件 SHA256：

| 文件 | SHA256 |
|---|---|
| `app.py` | `39ca98aaebfd9aa67b23cf0762feb8408b08ebcf0de17005f84042606d5d4b92` |
| `api/miniprogram.py` | `abbdd73b7c545d7b56e37fbc480848360608506a599c2cf67ab572c7174d1383` |
| `services/web_practice_tasks.py` | `78ba58b69227f27020e33b3ecc0cff08107638104e3d8549f7241b69be68b398` |

## 批 1 重叠与只读三方预演

批 1 在 `/private/tmp/studytracker-practice-web-batch1-20261126`，仍从 `f81a5e4a` 开发、13 modified / 7 顶层 untracked。其 manifest 中 14 个产品/测试/CI 文件的 SHA256 全部匹配，未将该树改动应用到词汇树。

批 1 与当前“词汇 + main”候选重叠 3 个产品/CI 文件。将三个版本复制至 `/private/tmp` 临时目录，用 `git merge-file -p` 做文本预演，结果如下；临时文件退出后删除，没有操作任一树的 index 或产品文件。

| 文件 | exit / 冲突标记 | 预演输出 SHA256 |
|---|---|---|
| `.github/workflows/ci.yml` | 0 / 0 | `8001945fff4803b0c9f2d11f855461385ca4a0a9d9748b4f1e53a7a2e312640c` |
| `templates/practice/index_content.html` | 0 / 0 | `a0c1aef3e81c212eb6d118b5c2a17a96160fad1645ca9bc38fb361c7a4c9d42d` |
| `templates/listening/test_practice.html` | 0 / 0 | `cfd39a6639373831ba2ca5e008062201a0d81ab94d6e91c7965a681a3b6cc395` |

因此，就目前快照，`index_content.html` 虽然同文件被改，文本并不冲突。预演结果包含词汇的 bfcache `pageshow` 列表刷新、批 1 的身份更新和学生隐藏后台控件。听力模板同时保留 main 的冲刺音频/图片路径及批 1 的保存/恢复/退出状态；CI 同时保留三组新增步骤。

这只证明当前三份文本可自动合并，**未实际集成批 1、未运行联合产品测试，也不证明未来版本无冲突**。后续应从届时 main 整合，检查上述行为并重跑词汇、冲刺和批 1 套件；两份交接仍须保留双方条目。批 1 的 CI 测试引用 `docs/reviews/practice-web-batch1-20261126/run_tests.py`，提交批 1 时必须包含该 runner，不能只拿产品补丁。

## 复现命令

在词汇工作树执行，下列检查不更改 Git；临时三方文件仅存在于系统临时目录。两个固定父提交是本次审计快照，后续 HEAD 前进仍可对照。

```bash
git diff f6f0f104 -- app.py api/miniprogram.py services/web_practice_tasks.py .github/workflows/ci.yml
git diff f5b06cc3 -- app.py api/miniprogram.py services/web_practice_tasks.py .github/workflows/ci.yml
```

AST、CI、交接与批 1 的结构检查使用如下代码，执行解释器为 `/Users/zhouxin/Desktop/studytracker/.venv/bin/python`；Ruby 为 macOS 已有运行时，不安装依赖：

```python
import ast, hashlib, json, shlex, subprocess, tempfile
from pathlib import Path
root = Path.cwd()
refs = ['f81a5e4a', 'f6f0f104', 'f5b06cc3']
def show(ref, path):
    return subprocess.check_output(['git', 'show', f'{ref}:{path}'], text=True)
def functions(text):
    return {n.name: ast.dump(n, include_attributes=False)
            for n in ast.parse(text).body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
def imports(text):
    return {ast.dump(n, include_attributes=False) for n in ast.parse(text).body
            if isinstance(n, (ast.Import, ast.ImportFrom))}
for path in ['app.py', 'api/miniprogram.py', 'services/web_practice_tasks.py']:
    texts = [show(ref, path) for ref in refs] + [(root / path).read_text()]
    b, o, t, m = [functions(text) for text in texts]
    for name in set(b) | set(o) | set(t):
        assert not (o.get(name) != b.get(name) and t.get(name) != b.get(name)
                    and o.get(name) != t.get(name)), name
        assert m.get(name) == (o.get(name) if o.get(name) != b.get(name)
                               else t.get(name)), name
    added = (imports(texts[1]) | imports(texts[2])) - imports(texts[0])
    assert added <= imports(texts[3])
assert (root / 'services/web_practice_tasks.py').read_text() == show(
    'f5b06cc3', 'services/web_practice_tasks.py')
def yaml(text):
    ruby = ['ruby', '-rjson', '-ryaml', '-rdate', '-e',
            'puts JSON.generate(YAML.safe_load(STDIN.read, permitted_classes: [Date, Time], aliases: true))']
    return json.loads(subprocess.check_output(ruby, input=text, text=True))
merged = yaml((root / '.github/workflows/ci.yml').read_text())
for ref in refs[1:]:
    parent = yaml(show(ref, '.github/workflows/ci.yml'))
    for job, definition in parent['jobs'].items():
        current = merged['jobs'][job]
        for key, value in definition.items():
            if key != 'steps':
                assert current.get(key) == value
        for step in definition['steps']:
            key = 'name' if 'name' in step else 'uses'
            candidates = [s for s in current['steps'] if s.get(key) == step[key]]
            assert len(candidates) == 1
            for field, value in step.items():
                if field == 'run':
                    old = shlex.split(value.replace('\\\n', ' '))
                    new = iter(shlex.split(candidates[0][field].replace('\\\n', ' ')))
                    assert all(any(token == expected for token in new) for expected in old)
                else:
                    assert candidates[0].get(field) == value
    for path in ['docs/CODEX_HANDOFF.md', 'docs/WORKLOG.md']:
        lines = iter((root / path).read_text().splitlines())
        assert all(any(line == item for line in lines)
                   for item in show(ref, path).splitlines() if item.strip())
batch = Path('/private/tmp/studytracker-practice-web-batch1-20261126')
manifest = json.loads((batch / 'docs/reviews/practice-web-batch1-20261126/manifest.json').read_text())
for row in manifest['files']:
    assert hashlib.sha256((batch / row['path']).read_bytes()).hexdigest() == row['sha256']
for path in ['.github/workflows/ci.yml', 'templates/practice/index_content.html',
             'templates/listening/test_practice.html']:
    with tempfile.TemporaryDirectory(prefix='vocab-batch1-readonly-', dir='/private/tmp') as tmp:
        tmp = Path(tmp)
        (tmp / 'batch1').write_bytes((batch / path).read_bytes())
        (tmp / 'base').write_text(show('f81a5e4a', path))
        (tmp / 'vocabulary').write_bytes((root / path).read_bytes())
        probe = subprocess.run(['git', 'merge-file', '-p', str(tmp / 'batch1'),
                                str(tmp / 'base'), str(tmp / 'vocabulary')], capture_output=True)
        assert probe.returncode == 0 and b'<<<<<<<' not in probe.stdout
        print(path, hashlib.sha256(probe.stdout).hexdigest())
```

执行结果：AST 0 不匹配、0 缺失新增 import；CI 0 缺步骤/命令 token，4 jobs；两个父版本全部交接非空行顺序保留；批 1 的 14 SHA 匹配；3 项文本预演 exit 0，无冲突标记。
