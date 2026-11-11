"""Numbers-only summary of the Flash / Pro comparison (run_comparison.sh writes the runs).

Reads <out>/<group>-flash, <out>/<group>-pro (report.json) and <out>/compare-<group>
(compare.json, blind_tally.json when present) and writes <out>/summary.md and
<out>/summary.json. Only sample ids, rates, scores, tokens and costs go into the
summary - no essay text, quotes, prompts or model answers - so it can be shared and
committed. Usage: python summarize_comparison.py <out dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

GROUPS = (
    ("dev", "开发集（7 篇内置样本，只看格式与历史问题）"),
    ("teacher", "学生作文 teacher-t2-01（老师总分）"),
    ("rated_t2", "留出集 Task 2（4 篇，双评委）"),
    ("rated_t1", "留出集 Task 1（2 篇，双评委，带题图）"),
    ("ordering", "排序集（10 篇 AI 参考文章，标称 9–7）"),
    ("lowband", "低分段合成作文（6 篇，标称 5–6，未经人工评分）"),
    ("official", "官方样卷（5 篇，官方总分 4–8.5）"),
)
SIDES = (("flash", "Flash"), ("pro", "Pro"))
SCORE_NAMES = {
    "overall": "总分",
    "task": "TR",
    "coherence": "CC",
    "lexical": "LR",
    "grammar": "GRA",
}


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def pct(value) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def num(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def run_numbers(report: dict) -> dict:
    evaluate = (report.get("kinds") or {}).get("evaluate") or {}
    tokens = ((report.get("usage") or {}).get("text") or {}).get("tokens") or {}
    findings = report.get("teacher_findings") or {}
    return {
        "model": report.get("model"),
        "served_models": report.get("served_models") or [],
        "prompt_version": report.get("prompt_version"),
        "code_sha256": (report.get("code_sha256") or "")[:16] or None,
        "calls": report.get("calls"),
        "first_attempt_json_ok": evaluate.get("first_attempt_json_ok"),
        "first_attempt_valid": evaluate.get("first_attempt_valid"),
        "final_ready": evaluate.get("final_ready"),
        "final_failures": evaluate.get("final_failures"),
        "truncated": evaluate.get("truncated", 0),
        "timeouts": evaluate.get("timeouts", 0),
        "latency_ms_p50": evaluate.get("latency_ms_p50"),
        "latency_ms_p90": evaluate.get("latency_ms_p90"),
        "completion_tokens_max": evaluate.get("completion_tokens_max"),
        "prompt_tokens": tokens.get("prompt"),
        "completion_tokens": tokens.get("completion"),
        "cache_hit_tokens": ((report.get("usage") or {}).get("text") or {}).get("cache_hit_tokens"),
        "estimated_cost": report.get("estimated_cost"),
        "cost_basis": (report.get("cost_estimate") or {}).get("basis"),
        "calibration": report.get("calibration"),
        "rater_agreement": report.get("rater_agreement"),
        "ordering": {
            name: {k: v for k, v in m.items() if k != "rows"}
            | {"chain": [(r["nominal"], r["ai"]) for r in m.get("rows") or []]}
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
                "scores": s.get("scores"),
                "teacher": s.get("teacher"),
                "statuses": s.get("statuses"),
                "errors": s.get("errors"),
            }
            for s in report.get("per_sample") or []
        ],
    }


def collect(out: Path) -> dict:
    data = {}
    for group, _label in GROUPS:
        runs = {}
        for side, _name in SIDES:
            report = load(out / f"{group}-{side}" / "report.json")
            if report:
                runs[side] = run_numbers(report)
        if not runs:
            continue
        cmp = load(out / f"compare-{group}" / "compare.json") or {}
        data[group] = {
            "runs": runs,
            "warnings": cmp.get("warnings") or [],
            "blind_tally": load(out / f"compare-{group}" / "blind_tally.json"),
        }
    return data


def markdown(data: dict) -> str:
    lines = [
        "# Flash / Pro 对照汇总（只有数字，不含作文、引文或模型回答）",
        "",
        "格式和费用是自动统计；**判断是否更准，看各组的盲评计数**（blind_tally，人工填写盲评表后生成）。",
    ]
    for group, label in GROUPS:
        if group not in data:
            continue
        entry = data[group]
        runs = entry["runs"]
        a, b = runs.get("flash") or {}, runs.get("pro") or {}
        lines += ["", f"## {label}", ""]
        if entry["warnings"]:
            lines += [f"- 注意：{w}" for w in entry["warnings"]] + [""]
        rows = (
            ("返回的模型名", lambda r: "、".join(r.get("served_models") or []) or "—"),
            (
                "提示词 / 源码指纹",
                lambda r: f"{num(r.get('prompt_version'))} / {num(r.get('code_sha256'))}",
            ),
            ("实际调用", lambda r: num(r.get("calls"))),
            ("首轮 JSON 合格", lambda r: pct(r.get("first_attempt_json_ok"))),
            ("首轮通过校验", lambda r: pct(r.get("first_attempt_valid"))),
            ("最终成功", lambda r: pct(r.get("final_ready"))),
            ("截断 / 超时", lambda r: f"{num(r.get('truncated'))} / {num(r.get('timeouts'))}"),
            (
                "延迟 p50 / p90（秒）",
                lambda r: (
                    "—"
                    if r.get("latency_ms_p50") is None
                    else f"{r['latency_ms_p50'] / 1000:.0f} / {(r.get('latency_ms_p90') or 0) / 1000:.0f}"
                ),
            ),
            ("输出峰值 token", lambda r: num(r.get("completion_tokens_max"))),
            (
                "输入 / 缓存命中 / 输出 token",
                lambda r: f"{num(r.get('prompt_tokens'))} / {num(r.get('cache_hit_tokens'))} / {num(r.get('completion_tokens'))}",
            ),
            ("估算费用（元）", lambda r: num(r.get("estimated_cost"))),
        )
        lines += ["| 项目 | Flash | Pro |", "|---|---|---|"]
        for name, fn in rows:
            lines.append(f"| {name} | {fn(a) if a else '—'} | {fn(b) if b else '—'} |")
        lines.append("")
        for side, name in SIDES:
            r = runs.get(side) or {}
            cal = r.get("calibration")
            if cal:
                parts = "；".join(
                    f"{SCORE_NAMES[k]} 平均差 {num(m['mae'])}、偏差 {m['bias']:+g}、±0.5 内 {pct(m['within_0_5'])}（{m['n']}）"
                    for k, m in cal.items()
                )
                lines.append(f"- {name} 与老师 / 官方分：{parts}")
            agreement = r.get("rater_agreement")
            if agreement:
                parts = "；".join(
                    f"{SCORE_NAMES[k]} 评委间 {num(m['rater_gap'])}、AI 与均值 {num(m['ai_gap'])}、"
                    f"偏差 {num(m['ai_bias'])}、区间内 {pct(m['within_range'])}"
                    for k, m in agreement.items()
                )
                lines.append(f"- {name} 与多位评委：{parts}")
            for gname, m in (r.get("ordering") or {}).items():
                chain = "；".join(f"{n:g}→{num(ai)}" for n, ai in m["chain"])
                lines.append(
                    f"- {name} 排序 {gname}：{chain}；逆序 {m['inversions']}/{m['pairs']}，"
                    f"同分 {m['ties']}，最高档−最低档 {num(m['spread'])}，未出分 {m['missing']}"
                )
            spread = r.get("repeat_spread")
            if spread:
                lines.append(
                    f"- {name} 重复运行总分差：平均 {num(spread['overall_spread_mean'])}、"
                    f"最大 {num(spread['overall_spread_max'])}，至少一次未出分 {spread['any_failed']} 篇"
                )
            findings = r.get("teacher_findings")
            if findings:
                lines.append(
                    f"- {name} 批注 / 预埋错误覆盖：{findings['covered']}/{findings['total']}"
                    f"（{pct(findings['rate'])}；只算评价成功的作文 {pct(findings['rate_evaluated'])}）"
                )
        tally = entry.get("blind_tally")
        if tally:
            lines.append("")
            lines.append("| 盲评计数 | Flash | Pro |")
            lines.append("|---|---|---|")
            for key, name in tally["labels"].items():
                lines.append(
                    f"| {name} | {tally['models']['a'].get(key, 0)} | {tally['models']['b'].get(key, 0)} |"
                )
            lines.append(
                f"| 已判断 / 未填写的条目 | {tally['models']['a'].get('filled', 0)} / {tally['models']['a'].get('blank', 0)} | {tally['models']['b'].get('filled', 0)} / {tally['models']['b'].get('blank', 0)} |"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    out = Path(argv[1])
    data = collect(out)
    (out / "summary.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (out / "summary.md").write_text(markdown(data), encoding="utf-8")
    print(f"汇总：{out / 'summary.md'}（{len(data)} 组）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
