"""Flash / Pro comparison batch: `realcheck-batch` (replaces run_comparison.sh).

Review of 2026-11-11 (docs/design/iwa-holdout-execution-review-20261111) found that the
shell launcher could exceed the authorised number of requests after an interruption
(189 of 184) or when started twice (212 of 184), could read a chart more than once and
hand the two models different chart input, carried on when every evaluation failed, and
broke its own Chinese output under macOS bash 3.2. This module runs the same plan with:

- one persistent ledger per stage (ledger.py): every request is reserved, fsync'd,
  before it is sent; separate text and image caps; unknown outcomes count as used;
- one batch at a time (exclusive lock on <out>/.batch.lock);
- each chart read once, before either text model runs; both models then use that
  frozen reading, and a chart without a usable reading stops the stage;
- a stop when a model's final failures in a group exceed half of the planned samples;
- the child environment built explicitly: no inherited IWA_* setting; a paid run needs
  an explicit --env-file and goes to the official DeepSeek endpoint;
- resumable: finished runs are skipped, an unfinished run directory is kept under a
  new name and its requests stay counted in the ledger.

Summaries (summary.md / summary.json) hold numbers and sample ids only.
"""

from __future__ import annotations

import dataclasses
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import ledger as ledger_lib
from . import prompts, realcheck, realcheck_compare
from .config import PROVIDER_PRESETS, load_settings

REPO = Path(__file__).resolve().parents[2]
MODELS = {"flash": "deepseek-flash", "pro": "deepseek-v4-pro"}
DRY_MODELS = {"flash": "fake-flash", "pro": "fake-pro"}
OFFICIAL_ENDPOINT = PROVIDER_PRESETS["deepseek"]["base_url"]
MAX_FAILURE_RATE = 0.5
THINKING = {"IWA_EVALUATE_THINKING": "high", "IWA_EVALUATE_THINKING_MAX_TOKENS": "32000"}
THINKING["IWA_EVALUATE_THINKING_TIMEOUT"] = "300"

EXIT_REFUSED = 2  # plan, configuration, cap or lock
EXIT_COMPARE = 6  # the two runs of a group are not comparable


@dataclasses.dataclass(frozen=True)
class Group:
    name: str
    label: str
    file: str  # "builtin" or a file in the data directory
    repeat: int
    first: str  # which model runs first ("flash" / "pro"), alternating by group
    optional: bool = False
    images: bool = False


STAGES = {
    "main": (
        Group("dev", "开发集（7 篇内置样本，只看格式与历史问题）", "builtin", 2, "flash"),
        Group("teacher", "学生作文 teacher-t2-01（老师总分）", "teacher.jsonl", 2, "pro"),
        Group("rated_t2", "留出集 Task 2（双评委）", "holdout_rated_t2.jsonl", 2, "flash"),
        Group("ordering", "排序集（AI 参考文章，标称 9–7）", "holdout_ordering.jsonl", 1, "pro"),
        Group(
            "lowband",
            "低分段合成作文（标称 5–6，未经人工评分）",
            "holdout_lowband.jsonl",
            2,
            "flash",
        ),
        Group("official", "官方样卷（官方总分）", "official.jsonl", 2, "pro", optional=True),
    ),
    "vision": (
        Group(
            "rated_t1",
            "留出集 Task 1（双评委，带题图）",
            "holdout_rated_t1.jsonl",
            2,
            "flash",
            images=True,
        ),
    ),
}


class Stop(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def plan(stage: str, data_dir: Path) -> list[dict]:
    """The groups of a stage with their sample counts and worst-case requests (every
    evaluation using its one validation retry). Missing optional files are skipped."""
    rows = []
    for group in STAGES[stage]:
        source = "builtin" if group.file == "builtin" else str(data_dir / group.file)
        if source != "builtin" and not Path(source).exists():
            if group.optional:
                rows.append({"group": group, "skip": f"{group.file} 不存在，这一组跳过"})
                continue
            raise Stop(EXIT_REFUSED, f"缺少数据文件：{source}")
        try:
            items = realcheck.load_samples(source)
        except realcheck.RealCheckError as exc:
            raise Stop(EXIT_REFUSED, f"{group.name}：{exc}") from None
        images = sum(1 for i in items if i["task_type"] == "task1" and i.get("image"))
        if group.images and not images:
            raise Stop(EXIT_REFUSED, f"{group.name}：没有带题图的 Task 1")
        evaluations = len(items) * group.repeat
        rows.append(
            {
                "group": group,
                "source": source,
                "samples": len(items),
                "evaluations": evaluations,
                "worst": evaluations * 2,
                "images": images if group.images else 0,
            }
        )
    return rows


def _done(path: Path) -> bool:
    return (path / ".done").exists()


def remaining(rows: list[dict], out: Path) -> tuple[int, int]:
    """Worst-case text and image requests of the runs not finished yet."""
    text = vision = 0
    for row in rows:
        if "skip" in row:
            continue
        name = row["group"].name
        for key in MODELS:
            if not _done(out / f"{name}-{key}"):
                text += row["worst"]
        if row["images"] and not _done(out / f"{name}-images"):
            vision += row["images"]
    return text, vision


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


def child_env(key: str, *, dry: bool, env_file: Path | None, out: Path) -> dict:
    """The environment of one realcheck run, built explicitly: inherited IWA_* settings
    (another endpoint, model or thinking budget) never reach the run."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("IWA_")}
    if dry:
        env.update(
            IWA_ENV_FILE=str(out / "no-such-env-file"),
            IWA_DATA_DIR=str(out / "data"),
            IWA_LLM_PROVIDER="fake",
            IWA_VISION_PROVIDER="fake",
            IWA_LLM_MODEL=DRY_MODELS[key],
        )
    else:
        env.update(
            IWA_ENV_FILE=str(env_file),
            IWA_LLM_PROVIDER="deepseek",
            IWA_LLM_BASE_URL=OFFICIAL_ENDPOINT,
            IWA_LLM_MODEL=MODELS[key],
        )
    env.update(THINKING)
    return env


def preflight(args, stage: str, out: Path) -> None:
    """A paid run: the configuration file is given explicitly, the key is there, the
    endpoint is the official one, and the image stage has a vision model."""
    if args.dry:
        return
    if not args.env_file:
        raise Stop(EXIT_REFUSED, "真实运行必须用 --env-file 明确指定配置文件")
    env_file = Path(args.env_file)
    if not env_file.is_file():
        raise Stop(EXIT_REFUSED, f"配置文件不存在：{env_file}")
    for key in MODELS:
        env = child_env(key, dry=False, env_file=env_file, out=out)
        settings = load_settings(env=env, env_file=env_file)
        settings.validate()
        if settings.llm_base_url != OFFICIAL_ENDPOINT or settings.llm_model != MODELS[key]:
            raise Stop(EXIT_REFUSED, f"{key}：端点或模型不对（{settings.llm_base_url}）")
        if not settings.llm_api_key:
            raise Stop(EXIT_REFUSED, "配置文件里没有 IWA_LLM_API_KEY")
        if stage == "vision" and not settings.vision_enabled:
            raise Stop(EXIT_REFUSED, "识图没有配置（IWA_VISION_PROVIDER / IWA_VISION_API_KEY）")


def parse_prices(values: list[str] | None) -> dict:
    """--price flash=IN,CACHED,OUT --price pro=IN,CACHED,OUT (yuan per million tokens)."""
    prices = {}
    for value in values or []:
        key, _, numbers = value.partition("=")
        parts = numbers.split(",")
        if key not in MODELS or len(parts) != 3:
            raise Stop(EXIT_REFUSED, f"--price 格式应为 flash=输入,缓存命中输入,输出：{value}")
        try:
            prices[key] = {
                name: float(part)
                for name, part in zip(("in", "cached_in", "out"), parts, strict=True)
            }
        except ValueError:
            raise Stop(EXIT_REFUSED, f"--price 里有不是数字的单价：{value}") from None
        if any(v < 0 for v in prices[key].values()):
            raise Stop(EXIT_REFUSED, f"--price 不能是负数：{value}")
    return prices


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


class Batch:
    def __init__(self, args, stage: str, out: Path, data_dir: Path, prices: dict, cap: int):
        self.args, self.stage, self.out, self.data_dir = args, stage, out, data_dir
        self.prices, self.cap = prices, cap
        self.ledger_path = out / f"ledger-{stage}.jsonl"
        self.log_path = out / "batch-log.txt"
        self.env_file = Path(args.env_file) if args.env_file else None

    def log(self, message: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
        print(line, flush=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def used(self) -> dict:
        return ledger_lib.summarize(ledger_lib.read(self.ledger_path))

    def realcheck(self, run_dir: Path, key: str, row: dict, extra: list[str], vision_cap: int):
        if _done(run_dir):
            self.log(f"跳过 {run_dir.name}（已完成）")
            return
        if run_dir.exists():
            kept = run_dir.with_name(f"{run_dir.name}.incomplete-{time.strftime('%Y%m%d%H%M%S')}")
            run_dir.rename(kept)
            self.log(f"{run_dir.name} 上次没有完成，结果目录保留为 {kept.name}（其请求仍计入账本）")
        command = [
            sys.executable,
            "-m",
            "tools.ielts_writing_ai",
            "realcheck",
            "--samples",
            row["source"],
            "--kinds",
            "evaluate",
            "--evaluate-thinking",
            "high",
            "--out",
            str(run_dir),
            "--ledger",
            str(self.ledger_path),
            "--ledger-text-cap",
            str(self.cap),
            "--ledger-vision-cap",
            str(vision_cap),
            "--ledger-run",
            run_dir.name,
            *extra,
        ]
        if not self.args.dry:
            price = self.prices[key]
            command += [
                "--confirm-paid",
                "--price-in",
                str(price["in"]),
                "--price-cached-in",
                str(price["cached_in"]),
                "--price-out",
                str(price["out"]),
            ]
        env = child_env(key, dry=self.args.dry, env_file=self.env_file, out=self.out)
        self.log(f"开始 {run_dir.name}（{env['IWA_LLM_MODEL']}）")
        code = subprocess.run(command, cwd=REPO, env=env, stdin=subprocess.DEVNULL).returncode
        runs = self.used()["runs"].get(run_dir.name) or {}
        self.log(
            f"结束 {run_dir.name}：退出码 {code}；这次运行名下累计文字请求 {runs.get('text', 0)}、"
            f"识图 {runs.get('vision', 0)}（结果未知 {runs.get('unknown', 0)}）"
        )
        if code < 0:  # the run was killed by a signal: its requests stay in the ledger
            raise Stop(
                3, f"{run_dir.name} 停止：进程被信号 {-code} 终止（已发出的请求已记在账本里）"
            )
        if code != 0:
            reasons = {
                2: "参数、数据或账本有误",
                3: "中止（首次调用就遇到 Key / 网络错误，或达到账本上限）",
                4: "最终失败超过计划篇数的一半",
                5: "有题图没有得到可用的识别结果",
            }
            raise Stop(code, f"{run_dir.name} 停止：{reasons.get(code, '未知错误')}")
        (run_dir / ".done").write_text(time.strftime("%Y-%m-%dT%H:%M:%S%z") + "\n")

    def run_group(self, row: dict, seed: int) -> None:
        group = row["group"]
        extra = ["--max-failure-rate", str(MAX_FAILURE_RATE), "--repeat", str(group.repeat)]
        extra += ["--max-calls", str(row["worst"])]
        if group.images:
            images_dir = self.out / f"{group.name}-images"
            self.realcheck(
                images_dir,
                "flash",
                row,
                ["--images-only", "--with-vision", "--max-calls", str(row["images"])],
                vision_cap=row["images"],
            )
            extra += [
                "--image-descriptions",
                str(images_dir / "image_descriptions.json"),
                "--require-ready-images",
            ]
        order = ["flash", "pro"] if group.first == "flash" else ["pro", "flash"]
        for key in order:
            self.realcheck(self.out / f"{group.name}-{key}", key, row, extra, vision_cap=0)
        try:
            cmp = realcheck_compare.compare(
                self.out / f"{group.name}-flash",
                self.out / f"{group.name}-pro",
                allow_model_change=True,
            )
        except realcheck_compare.CompareError as exc:
            raise Stop(EXIT_COMPARE, f"{group.name} 两次运行不能对照：{exc}") from None
        realcheck_compare.write(cmp, self.out / f"compare-{group.name}", blind_seed=seed)
        self.log(f"对照完成：compare-{group.name}（A = Flash，B = Pro；盲评表甲 / 乙随机）")


def _record_batch(out: Path, stage: str, args, prices: dict, cap: int) -> None:
    """batch-<stage>.json: what this stage runs with. A resumed stage must use the same
    code, prompt, models, prices and mode; only the cap may change (it is the user's
    authorisation) and every value used is kept."""
    path = out / f"batch-{stage}.json"
    current = {
        "stage": stage,
        "dry": bool(args.dry),
        "code_sha256": realcheck.code_fingerprint(),
        "prompt_version": prompts.PROMPT_VERSION,
        "models": DRY_MODELS if args.dry else MODELS,
        "prices": prices,
        "endpoint": None if args.dry else OFFICIAL_ENDPOINT,
        "max_failure_rate": MAX_FAILURE_RATE,
    }
    if path.exists():
        stored = json.loads(path.read_text(encoding="utf-8"))
        changed = [k for k in current if stored.get(k) != current[k]]
        if changed:
            raise Stop(
                EXIT_REFUSED,
                "这个结果目录的批次条件和本次不同，不能续跑：" + "、".join(changed),
            )
        caps = stored.get("caps") or []
    else:
        caps = []
    if not caps or caps[-1]["cap"] != cap:
        caps.append({"cap": cap, "time": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
    path.write_text(json.dumps(current | {"caps": caps}, ensure_ascii=False, indent=1) + "\n")


def run_stage(args) -> int:
    stage = args.stage
    out = Path(args.out).expanduser()
    data_dir = Path(args.data).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(out / ".batch.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Stop(EXIT_REFUSED, f"另一个批次正在使用 {out}，不能同时运行") from None
        prices = parse_prices(args.price)
        if not args.dry and set(prices) != set(MODELS):
            raise Stop(EXIT_REFUSED, "真实运行要给两个模型的单价：--price flash=… --price pro=…")
        preflight(args, stage, out)
        rows = plan(stage, data_dir)
        used = ledger_lib.summarize(ledger_lib.read(out / f"ledger-{stage}.jsonl"))
        text_left, vision_left = remaining(rows, out)
        image_total = sum(r.get("images", 0) for r in rows)
        need = used["text"]["reserved"] + text_left
        cap = args.cap if args.cap is not None else (need if args.dry else None)
        if cap is None:
            raise Stop(EXIT_REFUSED, "真实运行必须用 --cap 给出用户授权的本阶段文字请求上限")
        print(
            f"阶段 {stage}：文字请求已用 {used['text']['reserved']}（其中结果未知 "
            f"{used['text']['unknown']}），剩余步骤最坏 {text_left}，授权上限 {cap}；"
            f"识图已用 {used['vision']['reserved']}，剩余最坏 {vision_left}，上限 {image_total}"
        )
        for row in rows:
            if "skip" in row:
                print(f"注意：{row['skip']}")
        if need > cap:
            raise Stop(EXIT_REFUSED, f"已用 + 剩余最坏 = {need}，超过授权上限 {cap}，不开始")
        if used["vision"]["reserved"] + vision_left > image_total:
            raise Stop(EXIT_REFUSED, "识图请求会超过每张图一次，不开始")
        _record_batch(out, stage, args, prices, cap)
        batch = Batch(args, stage, out, data_dir, prices, cap)
        seed = {"main": 100, "vision": 200}[stage]
        for row in rows:
            seed += 1
            if "skip" not in row:
                batch.run_group(row, seed)
        write_summary(out)
        batch.log(f"阶段 {stage} 完成。汇总：{out / 'summary.md'}")
        return 0
    except Stop as exc:
        print(f"停止：{exc.message}", file=sys.stderr)
        log = out / "batch-log.txt"
        with log.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} 停止（{exc.code}）：{exc.message}\n")
        return exc.code
    finally:
        os.close(lock_fd)


# ---------------------------------------------------------------------------
# Summary (numbers only)
# ---------------------------------------------------------------------------

SCORE_NAMES = {
    "overall": "总分",
    "task": "TR",
    "coherence": "CC",
    "lexical": "LR",
    "grammar": "GRA",
}


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _scores_only(scores) -> dict:
    """Whitelisted numeric score fields (never comments or other attached text)."""
    return {k: _number((scores or {}).get(k)) for k in SCORE_NAMES if k in (scores or {})}


def _attempts(runs: dict, name: str, price: dict | None) -> dict:
    """All requests made under one run name, including interrupted attempts."""
    run = runs.get(name) or {}
    requests = run.get("text", 0) + run.get("vision", 0)
    cost = None
    if price and run:
        cached = price.get("cached_in", price["in"])
        hits = run.get("prompt_cache_hit_tokens", 0)
        prompt = run.get("prompt_tokens", 0)
        cost = round(
            (
                (prompt - hits) * price["in"]
                + hits * cached
                + run.get("completion_tokens", 0) * price["out"]
            )
            / 1e6,
            6,
        )
    return {
        "requests": requests,
        "text": run.get("text", 0),
        "vision": run.get("vision", 0),
        "unknown": run.get("unknown", 0),
        "unknown_usage": run.get("unknown_usage", 0),
        "estimated_cost": cost,
        "cost_is_lower_bound": bool(run.get("unknown") or run.get("unknown_usage")),
    }


def _quality(report: dict) -> dict:
    evaluate = (report.get("kinds") or {}).get("evaluate") or {}
    findings = report.get("teacher_findings") or {}
    return {
        "served_models": report.get("served_models") or [],
        "prompt_version": report.get("prompt_version"),
        "code_sha256": (report.get("code_sha256") or "")[:16] or None,
        "samples": report.get("samples"),
        "first_attempt_json_ok": evaluate.get("first_attempt_json_ok"),
        "first_attempt_valid": evaluate.get("first_attempt_valid"),
        "final_ready": evaluate.get("final_ready"),
        "final_failures": evaluate.get("final_failures"),
        "truncated": evaluate.get("truncated", 0),
        "timeouts": evaluate.get("timeouts", 0),
        "latency_ms_p50": evaluate.get("latency_ms_p50"),
        "latency_ms_p90": evaluate.get("latency_ms_p90"),
        "completion_tokens_max": evaluate.get("completion_tokens_max"),
        "calibration": report.get("calibration"),
        "rater_agreement": report.get("rater_agreement"),
        "ordering": {
            name: {k: v for k, v in m.items() if k != "rows"}
            | {"chain": [[r["nominal"], r["ai"]] for r in m.get("rows") or []]}
            for name, m in (report.get("ordering") or {}).items()
        }
        or None,
        "repeat_spread": (
            {k: v for k, v in report["repeat_spread"].items() if k != "samples"}
            if report.get("repeat_spread")
            else None
        ),
        "teacher_findings": (
            {
                k: findings.get(k)
                for k in ("covered", "total", "rate", "evaluated_total", "rate_evaluated")
            }
            if findings
            else None
        ),
        "per_sample": [
            {
                "id": s.get("id"),
                "scores": _scores_only(s.get("scores")),
                "teacher": _scores_only(s.get("teacher")),
                "statuses": {k: str(v) for k, v in (s.get("statuses") or {}).items()},
            }
            for s in report.get("per_sample") or []
        ],
    }


def collect(out: Path) -> dict:
    data = {"stages": {}, "groups": {}}
    for stage, groups in STAGES.items():
        entries = ledger_lib.read(out / f"ledger-{stage}.jsonl")
        if not entries:
            continue
        used = ledger_lib.summarize(entries)
        batch_file = out / f"batch-{stage}.json"
        batch = json.loads(batch_file.read_text(encoding="utf-8")) if batch_file.exists() else {}
        prices = batch.get("prices") or {}
        data["stages"][stage] = {
            "text": used["text"],
            "vision": used["vision"],
            "caps": batch.get("caps") or [],
        }
        for group in groups:
            entry = {"label": group.label, "runs": {}}
            for key in MODELS:
                name = f"{group.name}-{key}"
                run = {"attempts": _attempts(used["runs"], name, prices.get(key))}
                report_file = out / name / "report.json"
                if _done(out / name) and report_file.exists():
                    run["final"] = _quality(json.loads(report_file.read_text(encoding="utf-8")))
                entry["runs"][key] = run
            if group.images:
                entry["images"] = _attempts(used["runs"], f"{group.name}-images", None)
            cmp_file = out / f"compare-{group.name}" / "compare.json"
            if cmp_file.exists():
                cmp = json.loads(cmp_file.read_text(encoding="utf-8"))
                entry["warnings"] = cmp.get("warnings") or []
                entry["common_rater_agreement"] = cmp.get("common_rater_agreement")
            tally_file = out / f"compare-{group.name}" / "blind_tally.json"
            if tally_file.exists():
                tally = json.loads(tally_file.read_text(encoding="utf-8"))
                entry["blind_tally"] = {
                    k: tally.get(k) for k in ("labels", "models", "complete", "repeats_counted")
                }
            if any(r.get("attempts", {}).get("requests") for r in entry["runs"].values()):
                data["groups"][group.name] = entry
    return data


def _pct(value) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def _num(value) -> str:
    if value is None:
        return "—"
    return f"{value:g}" if isinstance(value, float) else str(value)


def markdown(data: dict) -> str:
    lines = [
        "# Flash / Pro 对照汇总（只有数字和样本 id，不含作文、引文或模型回答）",
        "",
        "质量指标只看每组最终完成的那次运行；请求数和费用计入全部尝试（含中断后保留的目录和结果未知的请求）。"
        "判断准不准，看各组的盲评计数。",
    ]
    for stage, m in data["stages"].items():
        caps = " → ".join(str(c["cap"]) for c in m["caps"]) or "—"
        lines.append(
            f"- 阶段 {stage}：文字请求 {m['text']['reserved']}（成功返回 {m['text']['ok']}、"
            f"失败 {m['text']['failed']}、结果未知 {m['text']['unknown']}），授权上限 {caps}；"
            f"识图 {m['vision']['reserved']}"
        )
    for entry in data["groups"].values():
        lines += ["", f"## {entry['label']}", ""]
        if entry.get("warnings"):
            lines += [f"- 注意：{w}" for w in entry["warnings"]] + [""]
        a = (entry["runs"]["flash"].get("final")) or {}
        b = (entry["runs"]["pro"].get("final")) or {}
        ta, tb = entry["runs"]["flash"]["attempts"], entry["runs"]["pro"]["attempts"]

        def money(t):
            if t["estimated_cost"] is None:
                return "—"
            return ("至少 " if t["cost_is_lower_bound"] else "") + _num(t["estimated_cost"])

        rows = (
            (
                "返回的模型名",
                "、".join(a.get("served_models") or []) or "—",
                "、".join(b.get("served_models") or []) or "—",
            ),
            (
                "提示词 / 源码指纹",
                f"{_num(a.get('prompt_version'))} / {_num(a.get('code_sha256'))}",
                f"{_num(b.get('prompt_version'))} / {_num(b.get('code_sha256'))}",
            ),
            (
                "首轮 JSON 合格",
                _pct(a.get("first_attempt_json_ok")),
                _pct(b.get("first_attempt_json_ok")),
            ),
            (
                "首轮通过校验",
                _pct(a.get("first_attempt_valid")),
                _pct(b.get("first_attempt_valid")),
            ),
            ("最终成功", _pct(a.get("final_ready")), _pct(b.get("final_ready"))),
            (
                "截断 / 超时",
                f"{_num(a.get('truncated'))} / {_num(a.get('timeouts'))}",
                f"{_num(b.get('truncated'))} / {_num(b.get('timeouts'))}",
            ),
            (
                "延迟 p50 / p90（毫秒）",
                f"{_num(a.get('latency_ms_p50'))} / {_num(a.get('latency_ms_p90'))}",
                f"{_num(b.get('latency_ms_p50'))} / {_num(b.get('latency_ms_p90'))}",
            ),
            (
                "输出峰值 token",
                _num(a.get("completion_tokens_max")),
                _num(b.get("completion_tokens_max")),
            ),
            (
                "全部尝试的请求（结果未知）",
                f"{ta['requests']}（{ta['unknown']}）",
                f"{tb['requests']}（{tb['unknown']}）",
            ),
            ("全部尝试的估算费用（元）", money(ta), money(tb)),
        )
        lines += ["| 项目 | Flash | Pro |", "|---|---|---|"]
        lines += [f"| {label} | {va} | {vb} |" for label, va, vb in rows]
        lines.append("")
        if entry.get("images"):
            img = entry["images"]
            lines.append(
                f"- 识图请求（两边共用一份结果）：{img['vision']}（结果未知 {img['unknown']}）"
            )
        for key, side in (("flash", "Flash"), ("pro", "Pro")):
            final = entry["runs"][key].get("final") or {}
            cal = final.get("calibration")
            if cal:
                parts = "；".join(
                    f"{SCORE_NAMES[k]} 平均差 {_num(m['mae'])}、偏差 {m['bias']:+g}、"
                    f"±0.5 内 {_pct(m['within_0_5'])}（{m['n']}）"
                    for k, m in cal.items()
                )
                lines.append(f"- {side} 与老师 / 官方分：{parts}")
            for gname, m in (final.get("ordering") or {}).items():
                chain = "；".join(f"{n:g}→{_num(ai)}" for n, ai in m["chain"])
                lines.append(
                    f"- {side} 排序 {gname}：{chain}；逆序 {m['inversions']}/{m['pairs']}，"
                    f"同分 {m['ties']}，{_num(m.get('highest'))} 档 − {_num(m.get('lowest'))} 档 "
                    f"{_num(m['spread'])}，未出分 {m['missing']}"
                )
            spread = final.get("repeat_spread")
            if spread:
                lines.append(
                    f"- {side} 重复运行总分差：平均 {_num(spread['overall_spread_mean'])}、"
                    f"最大 {_num(spread['overall_spread_max'])}，至少一次未出分 "
                    f"{spread['any_failed']} 篇"
                )
            findings = final.get("teacher_findings")
            if findings:
                lines.append(
                    f"- {side} 批注 / 预埋错误覆盖：{findings['covered']}/{findings['total']}"
                    f"（{_pct(findings['rate'])}；只算评价成功的作文 "
                    f"{_pct(findings['rate_evaluated'])}）"
                )
        common = entry.get("common_rater_agreement")
        if common:
            lines.append(f"- 与多位评委对比（两边都出分的 {common['essays']} 篇）：")
            for key in SCORE_NAMES:
                ma, mb = (common["a"] or {}).get(key), (common["b"] or {}).get(key)
                if ma or mb:
                    lines.append(
                        f"  - {SCORE_NAMES[key]}：评委之间 {_num((ma or mb)['rater_gap'])}；"
                        f"Flash {_num((ma or {}).get('ai_gap'))}（区间内 "
                        f"{_pct((ma or {}).get('within_range'))}）；Pro "
                        f"{_num((mb or {}).get('ai_gap'))}（区间内 "
                        f"{_pct((mb or {}).get('within_range'))}）"
                    )
        tally = entry.get("blind_tally")
        if tally:
            state = "完整" if tally.get("complete") else "**不完整（有空格或无法识别的填写）**"
            lines += ["", f"盲评计数（{state}）：", "", "| 项目 | Flash | Pro |", "|---|---|---|"]
            for key, label in tally["labels"].items():
                lines.append(
                    f"| {label} | {tally['models']['a'].get(key, 0)} | "
                    f"{tally['models']['b'].get(key, 0)} |"
                )
    return "\n".join(lines) + "\n"


def write_summary(out: Path) -> Path:
    data = collect(out)
    (out / "summary.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    path = out / "summary.md"
    path.write_text(markdown(data), encoding="utf-8")
    return path
