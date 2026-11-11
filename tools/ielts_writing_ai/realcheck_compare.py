"""Same-condition comparison of two realcheck runs (e.g. evaluation thinking off vs high).

The comparison is only meaningful when nothing but the thinking mode changed, so it
refuses runs whose prompt version, model, kinds or essays differ (each essay is
fingerprinted with its question). It lays the two runs side by side and writes a
manual-review sheet; it never decides which run is "right". Whether a criticism is
fair, whether a real problem was missed, and how far the bands are from a teacher's
are judgments for the reviewer (and teacher scores, when samples carry them).
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

from . import essay as essay_lib
from . import realcheck
from .realcheck import teacher_coverage

CRITERIA = ("task", "coherence", "lexical", "grammar")


class CompareError(ValueError):
    pass


def load_run(directory) -> dict:
    directory = Path(directory)
    try:
        run_data = json.loads((directory / "run_data.json").read_text(encoding="utf-8"))
        report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CompareError(
            f"{directory} 缺少 {Path(exc.filename).name}（需要 realcheck 生成的报告目录）"
        ) from None
    except json.JSONDecodeError as exc:
        raise CompareError(f"{directory} 的报告不是有效 JSON：{exc}") from None
    return {"dir": str(directory), "run_data": run_data, "report": report}


INPUT_FIELDS = (
    "task_type",
    "prompt_text",
    "essay_text",
    "target_band",
    "image_status",
    "image_description",
)


def _fingerprint(sample: dict) -> str:
    sub = sample.get("submission") or {}
    text = "\x1f".join(str(sub.get(k) or "") for k in INPUT_FIELDS)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _evaluate_input(run_data: dict, sample_id: str) -> str | None:
    """Fingerprint of what the first evaluation request actually sent the model
    (None in reports written before it was recorded)."""
    for call in run_data.get("calls") or []:
        if call["sample"] == sample_id and call["kind"] == "evaluate" and call["attempt"] == 0:
            return call.get("input_sha256")
    return None


def conditions(run: dict) -> dict:
    run_data, report = run["run_data"], run["report"]
    settings = run_data.get("settings") or {}
    return {
        "dir": run["dir"],
        "provider": report.get("provider"),
        "model": report.get("model"),
        "prompt_version": report.get("prompt_version"),
        "kinds": run_data.get("kinds") or [],
        "evaluate_thinking": settings.get("evaluate_thinking", "off"),
        "evaluate_max_tokens": (report.get("kinds", {}).get("evaluate") or {}).get("max_tokens"),
        "evaluate_timeout": (
            settings.get("evaluate_thinking_timeout")
            if settings.get("evaluate_thinking", "off") != "off"
            else None
        ),
        "served_models": report.get("served_models") or [],
        "code_sha256": report.get("code_sha256"),
        "samples": {s["id"]: _fingerprint(s) for s in run_data.get("samples") or []},
        "evaluate_inputs": {
            s["id"]: _evaluate_input(run_data, s["id"]) for s in run_data.get("samples") or []
        },
        # Annotations are not model input, so they are checked separately.
        "teacher_findings": {
            s["id"]: sorted(finding_key(f) for f in s.get("teacher_findings") or [])
            for s in run_data.get("samples") or []
        },
        "started_at": report.get("started_at"),
    }


def check_same_conditions(
    a: dict, b: dict, *, allow_model_change: bool = False
) -> tuple[list[str], list[str]]:
    """(errors, warnings). Anything but the thinking mode differing is an error; with
    allow_model_change the provider/model may differ too (a model comparison), but the
    prompt version and what reached the model must still be identical."""
    errors, warnings = [], []
    model_changed = (a["provider"], a["model"]) != (b["provider"], b["model"])
    for key, label in (("provider", "服务商"), ("model", "模型"), ("prompt_version", "提示词版本")):
        if a[key] != b[key] and not (allow_model_change and key in ("provider", "model")):
            errors.append(f"{label}不同：{a[key]} vs {b[key]}")
    if allow_model_change and model_changed:
        warnings.append(
            f"对照的是两个模型：{a['provider']} / {a['model']} vs {b['provider']} / {b['model']}"
            "（提示词与实际输入相同）"
        )
        if a["evaluate_thinking"] != b["evaluate_thinking"]:
            warnings.append("模型和思考模式同时不同：差异不能单独归因于其中一项")
        for key, label in (("evaluate_max_tokens", "输出上限"), ("evaluate_timeout", "超时")):
            if a.get(key) != b.get(key):
                warnings.append(
                    f"两个模型的{label}不同（{_fmt(a.get(key))} vs {_fmt(b.get(key))}）："
                    "差异不能单独归因于模型"
                )
    if a.get("code_sha256") and b.get("code_sha256") and a["code_sha256"] != b["code_sha256"]:
        warnings.append(
            "两次运行的工具源码不同（源码指纹不一致）：校验和过滤规则可能有差别，"
            "差异不能只归因于模型或思考模式"
        )
    if "evaluate" not in a["kinds"] or "evaluate" not in b["kinds"]:
        errors.append("两次运行都必须包含原稿评价（--kinds evaluate）")
    if a["kinds"] != b["kinds"]:
        errors.append(f"运行的类型不同：{a['kinds']} vs {b['kinds']}")
    if set(a["samples"]) != set(b["samples"]):
        errors.append("样本不同：" + "、".join(sorted(set(a["samples"]) ^ set(b["samples"]))))
    changed = [k for k in a["samples"] if k in b["samples"] and a["samples"][k] != b["samples"][k]]
    if changed:
        errors.append("同名样本的题目、作文或题图识别结果不同：" + "、".join(sorted(changed)))
    # The decisive check: what reached the evaluation model must be identical. Only
    # request options (thinking, output budget, timeout) may differ - they are not
    # part of the messages.
    inputs_a, inputs_b = a.get("evaluate_inputs") or {}, b.get("evaluate_inputs") or {}
    shared = [k for k in a["samples"] if k in b["samples"]]
    differing = [
        k for k in shared if inputs_a.get(k) and inputs_b.get(k) and inputs_a[k] != inputs_b[k]
    ]
    if differing:
        errors.append("实际发送给评价模型的输入不同：" + "、".join(sorted(differing)))
    notes_a, notes_b = a.get("teacher_findings") or {}, b.get("teacher_findings") or {}
    different_notes = [k for k in shared if notes_a.get(k, []) != notes_b.get(k, [])]
    if different_notes:
        warnings.append(
            "两次运行的老师批注不同（复核表按“引文 + 批注”逐条对齐，缺的一边标“无此批注”）："
            + "、".join(sorted(different_notes))
        )
    unknown = [k for k in shared if not (inputs_a.get(k) and inputs_b.get(k))]
    if unknown:
        warnings.append(
            "有样本缺少实际输入的指纹（旧版报告或首次请求未发出），只核对了题目、作文和题图"
            "识别结果：" + "、".join(sorted(unknown))
        )
    if a["evaluate_thinking"] == b["evaluate_thinking"] and not model_changed:
        warnings.append(
            f"两次的评价思考模式相同（{a['evaluate_thinking']}）：这是重复性对照，不是思考开关的对照"
        )
    return errors, warnings


def _evaluate_calls(run_data: dict, sample_id: str) -> list[dict]:
    return [
        c
        for c in run_data.get("calls") or []
        if c["sample"] == sample_id and c["kind"] == "evaluate"
    ]


def _int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def sample_view(run_data: dict, sample: dict) -> dict:
    generation = sample["generations"].get("evaluate") or {}
    result = generation.get("result") or {}
    criteria = {c["key"]: c for c in result.get("criteria") or []}
    argument = result.get("argument") or {}
    calls = _evaluate_calls(run_data, sample["id"])
    completion = [_int((c.get("usage") or {}).get("completion_tokens")) for c in calls]
    reasoning = [_int(c.get("reasoning_tokens")) for c in calls]
    return {
        "id": sample["id"],
        "task_type": sample.get("task_type"),
        "status": generation.get("status"),
        "error": generation.get("error_code"),
        "overall": result.get("overall_band"),
        "bands": {k: (criteria.get(k) or {}).get("band") for k in CRITERIA},
        "criteria": {
            k: {
                "summary": (criteria.get(k) or {}).get("summary", ""),
                "issues": [
                    {
                        "quote": i.get("quote"),
                        "comment": i.get("comment"),
                        "suggestion": i.get("suggestion"),
                    }
                    for i in (criteria.get(k) or {}).get("issues") or []
                ],
            }
            for k in CRITERIA
        },
        "overall_comment": result.get("overall_comment") or "",
        "priorities": list(result.get("priorities") or []),
        # Items the program reclassified (from_type) are listed once, under
        # "reclassified"; listing them here too counted the same advice twice
        # (review 76276d9).
        "optional": [
            {
                "quote": i.get("quote"),
                "comment": i.get("comment"),
                "suggestion": i.get("suggestion"),
            }
            for i in argument.get("improvements") or []
            if not i.get("from_type")
        ],
        "position_consistent": (argument.get("position") or {}).get("consistent"),
        "argument_notes": argument.get("notes") or [],
        "problems": [
            {
                "type": p["type"],
                "label": p.get("label"),
                "quote": p["quote"],
                "conflicts_with": p.get("conflicts_with"),
                "needs_review": bool(p.get("needs_review")),
                "p": p.get("p"),
                "comment": p.get("comment"),
                "suggestion": p.get("suggestion"),
                "suggestion_removed": bool(p.get("suggestion_removed")),
            }
            for p in argument.get("problems") or []
        ],
        "reclassified": [
            {
                "from_type": i["from_type"],
                "quote": i["quote"],
                "comment": i.get("comment"),
                "support": i.get("support") or [],
                "suggestion": i.get("suggestion"),
                "suggestion_removed": bool(i.get("suggestion_removed")),
            }
            for i in argument.get("improvements") or []
            if i.get("from_type")
        ],
        "improvements": len(argument.get("improvements") or []),
        "self_conflicts": argument.get("self_conflicts") or 0,
        "consistency_issues": [
            {
                "quote": c.get("quote"),
                "figures": c.get("figures") or [],
                "comment": c.get("comment"),
            }
            for c in result.get("consistency_issues") or []
        ],
        "comparisons_checked": result.get("comparisons_checked"),
        "count_corrections": result.get("count_corrections") or [],
        "suggestions_removed": (result.get("suggestions_removed") or {}).get("total", 0),
        "calls": len(calls),
        "latency_ms": sum(c.get("latency_ms") or 0 for c in calls),
        "completion_tokens": (
            sum(v for v in completion if v is not None)
            if any(v is not None for v in completion)
            else None
        ),
        "reasoning_tokens": (
            sum(v for v in reasoning if v is not None)
            if any(v is not None for v in reasoning)
            else None
        ),
        "teacher": sample.get("teacher") or {},
        "teacher_coverage": teacher_coverage(sample),
    }


def _prices(given: dict | None, shared: dict, report: dict) -> dict:
    """This run's prices: its own compare option, else the pair given for both runs,
    else what its realcheck was run with."""
    stored = report.get("prices") or {}
    out = {}
    for key in ("in", "cached_in", "out"):
        for source in (given or {}, shared, stored):
            if source.get(key) is not None:
                out[key] = source[key]
                break
        else:
            out[key] = None
    return out


def run_summary(run: dict, prices: dict | None = None) -> dict:
    report = run["report"]
    evaluate = report.get("kinds", {}).get("evaluate") or {}
    tokens = ((report.get("usage") or {}).get("text") or {}).get("tokens") or {}
    views = [sample_view(run["run_data"], s) for s in run["run_data"].get("samples") or []]
    text_usage = (report.get("usage") or {}).get("text") or {}
    cost, basis = realcheck.text_cost(text_usage, prices)
    return {
        "calls": report.get("calls"),
        "first_attempt_valid": evaluate.get("first_attempt_valid"),
        "final_ready": evaluate.get("final_ready"),
        "latency_ms_p50": evaluate.get("latency_ms_p50"),
        "latency_ms_p90": evaluate.get("latency_ms_p90"),
        "prompt_tokens": tokens.get("prompt"),
        "completion_tokens": tokens.get("completion"),
        "reasoning_tokens": evaluate.get("reasoning_tokens"),
        "reasoning_tokens_known": evaluate.get("reasoning_tokens_known"),
        "reasoning_unreported_calls": evaluate.get("reasoning_unreported_calls", 0),
        "completion_tokens_max": evaluate.get("completion_tokens_max"),
        "max_tokens": evaluate.get("max_tokens"),
        "truncated": evaluate.get("truncated", 0),
        "timeouts": evaluate.get("timeouts", 0),
        "estimated_cost": cost,
        "cost_basis": basis,
        "cache_hit_tokens": text_usage.get("cache_hit_tokens"),
        "sanity": {k: (report.get("sanity") or {}).get(k) for k in ("passed", "total", "skipped")},
        "problems": sum(len(v["problems"]) for v in views),
        "reclassified": sum(len(v["reclassified"]) for v in views),
        "self_conflicts": sum(v["self_conflicts"] for v in views),
        "count_corrections": sum(len(v["count_corrections"]) for v in views),
        "suggestions_removed": sum(v["suggestions_removed"] for v in views),
    }


def compare(
    a_dir,
    b_dir,
    *,
    price_in=None,
    price_out=None,
    prices_a: dict | None = None,
    prices_b: dict | None = None,
    allow_model_change=False,
) -> dict:
    """prices_a / prices_b ({"in", "cached_in", "out"}, per million tokens) price each
    run separately; price_in / price_out apply to both runs and are only accepted when
    both used the same model. Without either, each run keeps the prices its realcheck
    was given."""
    a, b = load_run(a_dir), load_run(b_dir)
    cond_a, cond_b = conditions(a), conditions(b)
    errors, warnings = check_same_conditions(cond_a, cond_b, allow_model_change=allow_model_change)
    if errors:
        raise CompareError("两次运行的条件不同，不能对照：" + "；".join(errors))
    shared = {"in": price_in, "out": price_out}
    model_changed = (cond_a["provider"], cond_a["model"]) != (cond_b["provider"], cond_b["model"])
    if model_changed and (price_in is not None or price_out is not None):
        raise CompareError(
            "两个模型的单价不同，--price-in / --price-out 会把同一组价格套在两边："
            "请用 --price-in-a / --price-out-a 和 --price-in-b / --price-out-b 分别提供，"
            "或在各自运行 realcheck 时提供单价"
        )
    paid_a = _prices(prices_a, shared, a["report"])
    paid_b = _prices(prices_b, shared, b["report"])
    views_b = {s["id"]: sample_view(b["run_data"], s) for s in b["run_data"]["samples"]}
    samples = [
        {"a": sample_view(a["run_data"], s), "b": views_b[s["id"]]}
        for s in a["run_data"]["samples"]
    ]
    return {
        "conditions": {"a": cond_a, "b": cond_b},
        "warnings": warnings,
        "summary": {"a": run_summary(a, paid_a), "b": run_summary(b, paid_b)},
        "samples": samples,
        "prices": {"a": paid_a, "b": paid_b},
        "common_rater_agreement": common_rater_agreement(a["run_data"], b["run_data"]),
    }


def common_rater_agreement(run_a: dict, run_b: dict) -> dict | None:
    """Both runs against the raters on the essays *both* scored, so that a run is not
    favoured by failing on the hard essays (review 2026-11-11). Failures are counted
    separately in the summary."""
    scored = []
    for run in (run_a, run_b):
        scored.append(
            {
                s["id"]
                for s in run.get("samples") or []
                if ((s["generations"].get("evaluate") or {}).get("result") or {}).get(
                    "overall_band"
                )
                is not None
            }
        )
    ids = scored[0] & scored[1]
    a = realcheck.rater_agreement(run_a.get("samples") or [], ids)
    b = realcheck.rater_agreement(run_b.get("samples") or [], ids)
    if not (a or b):
        return None
    return {"essays": len(ids), "a": a, "b": b}


def _fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, list):
        return " / ".join(_fmt(v) for v in value) or "—"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _reasoning_cell(summary: dict) -> str:
    known, missing = summary.get("reasoning_tokens_known"), summary.get(
        "reasoning_unreported_calls"
    )
    if known is None:
        return f"—（{missing} 次未报告）" if missing else "—"
    return f"已知 {known}（{missing} 次未报告，不完整）" if missing else str(known)


def _band(value) -> str:
    return "—" if value is None else f"{float(value):.1f}"


def _pct(value) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


RATE_KEYS = {"first_attempt_valid", "final_ready"}


def _label(cond: dict, other: dict | None = None) -> str:
    """'思考 high', or 'model · 思考 high' when the two runs use different models."""
    thinking = f"思考 {cond['evaluate_thinking']}"
    if other and other.get("model") and cond.get("model") and other["model"] != cond["model"]:
        return f"{cond['model']} · {thinking}"
    return thinking


def render_markdown(cmp: dict) -> str:
    ca, cb = cmp["conditions"]["a"], cmp["conditions"]["b"]
    sa, sb = cmp["summary"]["a"], cmp["summary"]["b"]
    la, lb = f"A（{_label(ca, cb)}）", f"B（{_label(cb, ca)}）"
    lines = [
        "# 评价对照：同一提示词、同一批作文",
        "",
        f"- 模型 {ca['provider']} / {ca['model']} · 提示词 {ca['prompt_version']} · 样本 {len(ca['samples'])} 篇",
        f"- A：{ca['dir']}（{ca['started_at']}）",
        f"- B：{cb['dir']}（{cb['started_at']}）",
        "- 自动指标只说明格式、耗时和用量；**判断是否更准，看下面的人工复核表**（另见 manual_review.md）。",
    ]
    lines += [f"- 注意：{w}" for w in cmp["warnings"]]
    rows = [
        ("实际调用", "calls"),
        ("评价首轮通过校验", "first_attempt_valid"),
        ("评价最终成功", "final_ready"),
        ("评价延迟 p50 (ms)", "latency_ms_p50"),
        ("评价延迟 p90 (ms)", "latency_ms_p90"),
        ("输入 token（文本，合计）", "prompt_tokens"),
        ("输出 token（文本，合计）", "completion_tokens"),
        ("其中思考 token（评价，含失败调用；— 为未报告）", None),
        ("评价单次输出峰值", "completion_tokens_max"),
        ("评价输出上限", "max_tokens"),
        ("截断 / 超时", None),
        ("输入中缓存命中的 token（— 为未报告）", "cache_hit_tokens"),
        ("估算费用（各按自己的单价，文本）", "estimated_cost"),
        ("论证问题条数", "problems"),
        ("改列可选优化（同段支撑）", "reclassified"),
        ("AI 判断自相矛盾", "self_conflicts"),
        ("计数说法更正", "count_corrections"),
        ("建议因无来源数字被删", "suggestions_removed"),
        ("合理性检查（通过 / 计入）", None),
    ]
    lines += ["", "## 汇总", "", f"| 项目 | {la} | {lb} |", "|---|---|---|"]
    for label, key in rows:
        if label.startswith("其中思考"):
            va, vb = _reasoning_cell(sa), _reasoning_cell(sb)
        elif label.startswith("截断"):
            va = f"{sa['truncated']} / {sa['timeouts']}"
            vb = f"{sb['truncated']} / {sb['timeouts']}"
        elif label.startswith("合理性"):
            va = f"{_fmt(sa['sanity']['passed'])} / {_fmt(sa['sanity']['total'])}"
            vb = f"{_fmt(sb['sanity']['passed'])} / {_fmt(sb['sanity']['total'])}"
        else:
            show = _pct if key in RATE_KEYS else _fmt
            va, vb = show(sa[key]), show(sb[key])
        lines.append(f"| {label} | {va} | {vb} |")
    lines.append("")
    for name, summary in (("A", sa), ("B", sb)):
        paid = cmp["prices"][name.lower()]
        if summary["estimated_cost"] is None:
            lines.append(f"{name}：没有单价或用量不完整，费用未知（不能视为零）。")
        elif summary["cost_basis"] == "cache_split":
            lines.append(
                f"{name}：输入 {_fmt(paid['in'])}（缓存命中 {_fmt(paid['cached_in'])}）、"
                f"输出 {_fmt(paid['out'])}，每百万 token；输入按命中 / 未命中分别计价。"
            )
        else:
            lines.append(
                f"{name}：输入 {_fmt(paid['in'])}、输出 {_fmt(paid['out'])}，每百万 token；"
                "全部输入按普通输入单价计算（没有缓存命中单价或服务商未报告命中量），"
                "有缓存命中时偏高。"
            )
    lines.append("思考 token 已含在输出 token 里，不另加。费用是估算，以服务商账单为准。")
    lines += [
        "",
        "## 运行条件",
        "",
        "消息指纹只保证发给模型的内容相同；下面几项不在消息里，需要自己核对是否一致。",
        "",
        "| 项目 | A | B |",
        "|---|---|---|",
    ]
    for label, key in (
        ("配置的模型", "model"),
        ("服务商返回的模型名", "served_models"),
        ("评价思考模式", "evaluate_thinking"),
        ("评价输出上限", "evaluate_max_tokens"),
        ("评价超时（秒）", "evaluate_timeout"),
        ("工具源码指纹", "code_sha256"),
        ("开始时间", "started_at"),
    ):
        va, vb = ca.get(key), cb.get(key)
        if key == "code_sha256":
            va, vb = (va or "")[:16] or None, (vb or "")[:16] or None
        if key == "served_models":
            va, vb = "、".join(va or []) or None, "、".join(vb or []) or None
        lines.append(f"| {label} | {_fmt(va)} | {_fmt(vb)} |")
    lines += [
        "",
        "## 逐篇分数与论证问题",
        "",
        "| 样本 | 总分 A / B | TR A / B | CC A / B | LR A / B | GRA A / B | 论证问题 A | 论证问题 B |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for pair in cmp["samples"]:
        a, b = pair["a"], pair["b"]
        bands = " | ".join(f"{_band(a['bands'][k])} / {_band(b['bands'][k])}" for k in CRITERIA)
        pa = ", ".join(p["type"] for p in a["problems"]) or "—"
        pb = ", ".join(p["type"] for p in b["problems"]) or "—"
        lines.append(
            f"| {a['id']} | {_band(a['overall'])} / {_band(b['overall'])} | {bands} | {pa} | {pb} |"
        )
    common = cmp.get("common_rater_agreement")
    if common:
        lines += [
            "",
            f"## 与多位评委对比：两次都出分的 {common['essays']} 篇",
            "",
            "同一组作文上比较，避免一边因为在难题上失败而显得更准；失败篇数见上面的汇总。",
            "",
            "| 项目 | 评委之间平均差 | A 与评委均值平均差 | B 与评委均值平均差 | A 区间内 | B 区间内 |",
            "|---|---|---|---|---|---|",
        ]
        for key in realcheck.SCORE_KEYS:
            ma = (common["a"] or {}).get(key)
            mb = (common["b"] or {}).get(key)
            if not (ma or mb):
                continue
            ref = (ma or mb)["rater_gap"]
            lines.append(
                f"| {key} | {_fmt(ref)} | {_fmt((ma or {}).get('ai_gap'))} | "
                f"{_fmt((mb or {}).get('ai_gap'))} | {_pct((ma or {}).get('within_range'))} | "
                f"{_pct((mb or {}).get('within_range'))} |"
            )
    teacher = [p for p in cmp["samples"] if p["a"]["teacher"]]
    if teacher:
        lines += [
            "",
            "## 与老师评分（总分）",
            "",
            "| 样本 | 老师 | A | B |",
            "|---|---|---|---|",
        ]
        for pair in teacher:
            lines.append(
                f"| {pair['a']['id']} | {_band(pair['a']['teacher'].get('overall'))} | "
                f"{_band(pair['a']['overall'])} | {_band(pair['b']['overall'])} |"
            )
    return "\n".join(lines) + "\n"


def finding_key(finding: dict) -> str:
    """Identity of a teacher annotation: its quote and note, never its position in
    the list (review of 1c865eb: a reordered list paired the wrong rows)."""
    return essay_lib.squash(finding.get("quote")) + "\x1f" + (finding.get("note") or "").strip()


def _aligned_findings(a: dict, b: dict) -> list[tuple[dict, dict | None, dict | None]]:
    rows_a = ((a.get("teacher_coverage") or {}).get("findings")) or []
    rows_b = ((b.get("teacher_coverage") or {}).get("findings")) or []
    by_key_b = {finding_key(r): r for r in rows_b}
    aligned, seen = [], set()
    for row in rows_a:
        key = finding_key(row)
        seen.add(key)
        aligned.append((row, row, by_key_b.get(key)))
    aligned += [(row, None, row) for row in rows_b if finding_key(row) not in seen]
    return aligned


def _coverage_mark(row: dict | None) -> str:
    if row is None:
        return "无此批注"
    state = row.get("coverage") or ("yes" if row.get("covered") else "no")
    return {"yes": "是", "no": "否", "uncertain": "不确定", "not_evaluated": "未评价"}[state]


def _quote(text) -> str:
    return (text or "").replace("|", "／").replace("\n", " ")


def render_manual_review(cmp: dict) -> str:
    """A sheet for the human comparison: every finding of both runs, with empty
    columns for the verdict. Missed problems are noted per sample."""
    la = _label(cmp["conditions"]["a"], cmp["conditions"]["b"])
    lb = _label(cmp["conditions"]["b"], cmp["conditions"]["a"])
    lines = [
        "# 人工复核表（填写“判断”和“备注”）",
        "",
        "判断建议用：正确 / 误判 / 过严 / 过松 / 不确定。改列为可选优化的条目也要看："
        "同段引文存在，不等于它真的构成有效支撑。",
        "每篇最后一行写两次都没有指出、但原文确实存在的问题（漏报）。",
    ]
    for pair in cmp["samples"]:
        a, b = pair["a"], pair["b"]
        lines += [
            "",
            f"## {a['id']}（总分 A {_band(a['overall'])} / B {_band(b['overall'])}）",
            "",
            "| 运行 | 位置 | 类型 | 引文 | 模型说明 | 判断 | 备注 |",
            "|---|---|---|---|---|---|---|",
        ]
        for tag, view in (("A " + la, a), ("B " + lb, b)):
            consistent = {True: "前后一致", False: "前后不一致", None: "不下结论 / 未判断"}
            if view["task_type"] == "task2":
                lines.append(
                    f"| {tag} | 立场判断 | — | — | {consistent[view['position_consistent']]} |  |  |"
                )
            for note in view["argument_notes"]:
                lines.append(f"| {tag} | 论证提示 | — | — | {_quote(note)} |  |  |")
            for p in view["problems"]:
                kind = (p["label"] or p["type"]) + ("（需人工确认）" if p["needs_review"] else "")
                quote = _quote(p["quote"])
                if p["conflicts_with"]:
                    quote += f" ↔ 与之矛盾：{_quote(p['conflicts_with'])}"
                where = f"论证问题（第 {p['p']} 段）" if p.get("p") else "论证问题"
                lines.append(
                    f"| {tag} | {where} | {kind} | {quote} | {_quote(p['comment'])} |  |  |"
                )
            for issue in view["consistency_issues"]:
                figures = "；".join(_quote(f) for f in issue["figures"]) or "—"
                lines.append(
                    f"| {tag} | Task 1 文内矛盾 | — | {_quote(issue['quote'])} | "
                    f"对照：{figures}。{_quote(issue['comment'])} |  |  |"
                )
            if view["task_type"] == "task1":
                lines.append(
                    f"| {tag} | Task 1 比较核对 | — | — | 核对了 "
                    f"{_fmt(view['comparisons_checked'])} 条比较说法，指出矛盾 "
                    f"{len(view['consistency_issues'])} 条 |  |  |"
                )
            for r in view["reclassified"]:
                support = "；".join(_quote(q) for q in r["support"])
                lines.append(
                    f"| {tag} | 改列可选优化 | 原判 {r['from_type']} | {_quote(r['quote'])} | "
                    f"同段支撑：{support} |  |  |"
                )
            for key, short in (("task", "TR/TA"), ("coherence", "CC")):
                for issue in view["criteria"][key]["issues"]:
                    lines.append(
                        f"| {tag} | {short} 问题 | — | {_quote(issue['quote'])} | "
                        f"{_quote(issue['comment'])} |  |  |"
                    )
            for note in view["count_corrections"]:
                lines.append(f"| {tag} | 计数更正 | — | — | {_quote(note)} |  |  |")
        for finding, row_a, row_b in _aligned_findings(a, b):
            lines.append(
                f"| 老师批注 | A 覆盖：{_coverage_mark(row_a)} / B 覆盖：{_coverage_mark(row_b)} | — | "
                f"{_quote(finding['quote'])} | {_quote(finding.get('note'))} |  |  |"
            )
        lines.append("| 两次都漏报 | — | — | — | — |  |  |")
    return "\n".join(lines) + "\n"


BLIND_VERDICTS = "正确 / ① 误读原文 / ② 改句改变原意或逻辑 / ③ 可选润色说成错误 / 不确定"
_BLIND_NAMES = {"task": "TR/TA", "coherence": "CC", "lexical": "LR", "grammar": "GRA"}


_POSITION = {True: "前后一致", False: "前后不一致", None: "不下结论 / 未判断"}
JUDGED = "judged"  # a row the reviewer gives a verdict on
CONTEXT = "context"  # evidence shown for the verdicts, not judged itself


def feedback_rows(view: dict) -> list[tuple[str, str, str, str, str]]:
    """Every part of one run's feedback, with the evidence and the program's own
    qualifiers, as (row kind, position, quote, explanation, suggestion). Review
    2026-11-11: the blind sheet had dropped the other half of a contradiction, the
    "needs review" flag, paragraph numbers, the position verdict, argument notes, the
    same-paragraph support of reclassified items and count corrections."""
    rows = []
    if view["task_type"] == "task2":
        rows.append((JUDGED, "立场判断", "—", _POSITION[view["position_consistent"]], "—"))
    for note in view["argument_notes"]:
        rows.append((JUDGED, "论证提示", "—", _quote(note), "—"))
    for k, short in _BLIND_NAMES.items():
        criterion = view["criteria"][k]
        if criterion["summary"]:
            rows.append((JUDGED, f"{short} 理由", "—", _quote(criterion["summary"]), "—"))
        for issue in criterion["issues"]:
            rows.append(
                (
                    JUDGED,
                    f"{short} 问题",
                    _quote(issue["quote"]),
                    _quote(issue["comment"]),
                    _quote(issue.get("suggestion")) or "—",
                )
            )
    for p in view["problems"]:
        where = f"论证问题（第 {p['p']} 段" if p.get("p") else "论证问题（"
        kind = f"{where}，{p['label'] or p['type']}）"
        quote = _quote(p["quote"])
        if p["conflicts_with"]:
            quote += f" ↔ 与之矛盾：{_quote(p['conflicts_with'])}"
        comment = _quote(p["comment"])
        if p["needs_review"]:
            comment = "【程序标注：需人工确认，不是确定的错误】" + comment
        rows.append((JUDGED, kind, quote, comment, _quote(p.get("suggestion")) or "—"))
    for r in view["reclassified"]:
        support = "；".join(_quote(q) for q in r["support"]) or "—"
        rows.append(
            (
                JUDGED,
                f"改列可选优化（原判 {r['from_type']}）",
                _quote(r["quote"]),
                (_quote(r.get("comment")) + "（" if r.get("comment") else "（")
                + f"程序发现同段有支撑，改列为可选：{support}）",
                _quote(r.get("suggestion")) or "—",
            )
        )
    for item in view["optional"]:
        rows.append(
            (
                JUDGED,
                "可选优化",
                _quote(item["quote"]),
                _quote(item["comment"]),
                _quote(item["suggestion"]) or "—",
            )
        )
    for issue in view["consistency_issues"]:
        figures = "；".join(_quote(f) for f in issue["figures"]) or "—"
        rows.append(
            (
                JUDGED,
                "Task 1 文内矛盾",
                _quote(issue["quote"]),
                f"{_quote(issue['comment'])}（对照：{figures}）",
                "—",
            )
        )
    if view["task_type"] == "task1":
        rows.append(
            (
                CONTEXT,
                "Task 1 比较核对",
                "—",
                f"程序核对了 {_fmt(view['comparisons_checked'])} 条比较说法，"
                f"指出矛盾 {len(view['consistency_issues'])} 条",
                "—",
            )
        )
    for note in view["count_corrections"]:
        rows.append((CONTEXT, "计数更正（程序已改）", "—", _quote(note), "—"))
    if view["suggestions_removed"]:
        rows.append(
            (
                CONTEXT,
                "被删的建议",
                "—",
                f"程序删掉了 {view['suggestions_removed']} 条含原文没有的数字的建议",
                "—",
            )
        )
    if view["overall_comment"]:
        rows.append((JUDGED, "总评", "—", _quote(view["overall_comment"]), "—"))
    for n, text in enumerate(view["priorities"], 1):
        rows.append((JUDGED, f"提升重点 {n}", "—", "—", _quote(text)))
    for finding in (view.get("teacher_coverage") or {}).get("findings") or []:
        rows.append(
            (
                CONTEXT,
                "评委批注（供 ④ 参考）",
                _quote(finding.get("quote")),
                _quote(finding.get("note")),
                f"程序按位置判断，这一方是否在同一处指出：{_coverage_mark(finding)}",
            )
        )
    return rows


COUNT_ROWS = ("④ 漏掉评委都指出的明确错误", "其他漏报")


def render_blind_review(cmp: dict, seed: int = 0) -> tuple[str, dict]:
    """(sheet, key). Every part of both runs' feedback (feedback_rows), but the two runs
    appear as 甲 / 乙 in an order shuffled per sample and without any model or setting
    name; the key says which is which and is written to a separate file, to be opened
    only after the verdicts are filled in. Every row has an id, and the key lists every
    row the sheet must contain with its kind (judged / context / count), so that a
    missing row or side, or a required row turned into a context row, is noticed when
    counting (review 76276d9)."""
    rng = random.Random(seed)
    key = {"seed": seed, "samples": {}, "rows": []}
    lines = [
        "# 盲评复核表（不显示模型和设置；先填完再看 blind_key.json）",
        "",
        f"“判断”一栏填：{BLIND_VERDICTS}。标“参考”的行是判断依据，不用填。",
        "每篇最后两行填非负整数：④ 评委（或预埋清单）列出、但这一方没有指出的明确错误条数；"
        "其他漏报条数。没有就填 0。不要删改“编号”一栏，也不要删行。",
    ]
    for pair in cmp["samples"]:
        sides = ["a", "b"]
        rng.shuffle(sides)
        sample_id = pair["a"]["id"]
        key["samples"][sample_id] = {"甲": sides[0], "乙": sides[1]}
        lines += ["", f"## {sample_id}"]
        for name, side in zip(("甲", "乙"), sides, strict=True):
            view = pair[side]
            bands = "；".join(
                f"{_BLIND_NAMES[k]} {_band(view['bands'].get(k))}" for k in _BLIND_NAMES
            )
            lines += [
                "",
                f"### {name}（总分 {_band(view['overall'])}；{bands}；状态 {view['status'] or '—'}）",
                "",
                "| 编号 | 位置 | 引文 | 说明 | 建议 | 判断 | 备注 |",
                "|---|---|---|---|---|---|---|",
            ]
            rows = [
                (kind, position, quote, comment, suggestion)
                for kind, position, quote, comment, suggestion in feedback_rows(view)
            ] + [("count", position, "—", "—", "—") for position in COUNT_ROWS]
            for n, (kind, position, quote, comment, suggestion) in enumerate(rows, 1):
                row_id = f"{sample_id}/{name}/{n:02d}"
                key["rows"].append({"id": row_id, "sample": sample_id, "side": name, "kind": kind})
                verdict = "参考" if kind == CONTEXT else ""
                lines.append(
                    f"| {row_id} | {position} | {quote} | {comment} | {suggestion} | {verdict} |  |"
                )
    return "\n".join(lines) + "\n", key


def write(cmp: dict, out_dir, *, blind_seed: int | None = None) -> Path:
    """Writes the comparison files. An existing blind sheet (possibly filled in by a
    reviewer) is never overwritten: review 76276d9 found a normal resume replacing a
    filled sheet with a blank one while the old tally still said complete."""
    out_dir = Path(out_dir)
    if blind_seed is not None:
        existing = [n for n in ("blind_review.md", "blind_key.json") if (out_dir / n).exists()]
        if existing:
            raise CompareError(
                f"{out_dir} 里已有盲评表（{'、'.join(existing)}），不覆盖；"
                "需要重新生成时请换一个输出目录"
            )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "compare.json").write_text(
        json.dumps(cmp, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (out_dir / "manual_review.md").write_text(render_manual_review(cmp), encoding="utf-8")
    path = out_dir / "compare.md"
    path.write_text(render_markdown(cmp), encoding="utf-8")
    if blind_seed is not None:
        # Last, the key after the sheet: a folder with blind_key.json is complete.
        sheet, key = render_blind_review(cmp, blind_seed)
        (out_dir / "blind_review.md").write_text(sheet, encoding="utf-8")
        key["conditions"] = cmp["conditions"]
        (out_dir / "blind_key.json").write_text(
            json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return path
