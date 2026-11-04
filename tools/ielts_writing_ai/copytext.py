"""Plain-text versions of results for the copy buttons.

Built on the server (not in the browser) so that every copied text carries the
same limits the page shows: AI-generated, not an official score, plus every
warning (missing chart data, unverifiable quotes, short rewrite, ...).
"""

from __future__ import annotations

DISCLAIMER = "AI 生成，仅供学习参考，不是正式成绩"


def _band(value) -> str:
    return "—" if value is None else f"{float(value):.1f}"


def _provenance(generation: dict) -> str:
    parts = []
    if generation.get("model"):
        parts.append(f"模型 {generation['model']}")
    if generation.get("prompt_version"):
        parts.append(f"提示词 {generation['prompt_version']}")
    return "——" + " · ".join(parts + [DISCLAIMER])


def _warning_lines(warnings) -> list[str]:
    warnings = [w for w in (warnings or []) if w]
    if not warnings:
        return []
    return ["限制提示："] + [f"- {w}" for w in warnings]


def _evidence_line(entry, mark: str) -> str:
    if isinstance(entry, str):  # results stored before evidence was required
        return f"  {mark} {entry}（未附原文引文）"
    quote = entry.get("quote") or ""
    text = ""
    if quote:
        text = f"“{quote}”"
        if not entry.get("quote_found"):
            text += "（未在原文中找到，不作为评分依据）"
        text += " "
    elif mark == "✓":
        text = "（未附原文引文）"
    text += entry.get("comment") or ""
    if entry.get("suggestion"):
        text += f" → 建议：{entry['suggestion']}"
    return f"  {mark} {text}".rstrip()


ARGUMENT_NOTE = "AI 标注，引文均已在原文中核实；不单独计分，用来解释 TR / CC 的分数"
CONSISTENT = {True: "前后一致", False: "前后不一致"}


def argument_lines(argument: dict | None) -> list[str]:
    if not argument:
        return []
    lines = [f"论证结构检查（{ARGUMENT_NOTE}）："]
    position = argument.get("position")
    if position:
        state = CONSISTENT.get(position.get("consistent"))
        text = f"立场：“{position['quote']}”" + (f"（{state}）" if state else "")
        if position.get("comment"):
            text += f" {position['comment']}"
        lines.append(text)
    else:
        lines.append("立场：没有找到可核实的立场句。")
    if argument.get("paragraphs"):
        lines.append("各段中心句：")
    for paragraph in argument.get("paragraphs") or []:
        text = (
            f"  · {paragraph.get('role_label') or paragraph.get('role')}"
            f"【{paragraph.get('verdict_label') or paragraph.get('verdict')}】"
            f"“{paragraph['main_point']}”"
        )
        if paragraph.get("comment"):
            text += f" {paragraph['comment']}"
        lines.append(text)
    problems = argument.get("problems") or []
    if problems:
        lines.append("论证问题：")
        for problem in problems:
            text = f"  ✗ [{problem.get('label') or problem.get('type')}] “{problem['quote']}” "
            text += problem.get("comment") or ""
            if problem.get("suggestion"):
                text += f" → 建议：{problem['suggestion']}"
            lines.append(text.rstrip())
    else:
        lines.append("论证问题：AI 没有标出明显问题（不代表论证没有可改进之处）。")
    return lines + [""]


def evaluation_text(result: dict, generation: dict) -> str:
    lines = [f"【AI 原稿评价】{DISCLAIMER}"]
    overall = result.get("overall_band")
    if overall is not None:
        lines.append(f"预估总分：Band {_band(overall)}（四项平均，按 0.5 就近进位）")
    else:
        lines.append("总分：不可评（有评分项无法评分，见下方说明）")
    lines += _warning_lines(result.get("warnings"))
    lines.append("")
    for criterion in result.get("criteria") or []:
        head = f"{criterion.get('label')}（{criterion.get('short')}）"
        if criterion.get("state") == "not_assessable" or criterion.get("band") is None:
            lines += [f"{head}：不可评。{criterion.get('reason') or ''}".rstrip(), ""]
            continue
        lines.append(f"{head} Band {_band(criterion.get('band'))}")
        if criterion.get("summary"):
            lines.append(f"理由：{criterion['summary']}")
        lines += [_evidence_line(s, "✓") for s in criterion.get("strengths") or []]
        lines += [_evidence_line(i, "✗") for i in criterion.get("issues") or []]
        lines.append("")
    consistency = [c for c in result.get("consistency_issues") or [] if c.get("comment")]
    if consistency:
        lines.append("文内数据自洽检查（只看作文内部是否矛盾，不代表与题图一致）：")
        lines += [_evidence_line(c, "✗") for c in consistency]
        lines.append("")
    lines += argument_lines(result.get("argument"))
    if result.get("overall_comment"):
        lines += [f"总评：{result['overall_comment']}", ""]
    priorities = result.get("priorities") or []
    if priorities:
        lines.append("提升重点：")
        lines += [f"{n}. {p}" for n, p in enumerate(priorities, 1)]
        lines.append("")
    lines.append(_provenance(generation))
    return "\n".join(lines).strip()


def _refine_limits(result: dict) -> list[str]:
    limits = list(result.get("warnings") or [])
    if result.get("missing_count"):
        limits.append(f"有 {result['missing_count']} 句 AI 没有返回结果，已保留原句。")
    return limits


def refine_texts(result: dict, generation: dict, target_band) -> dict:
    limits = _refine_limits(result)
    full = [
        result.get("refined_essay") or "",
        "",
        f"——以上为 AI 逐句精修稿（目标 Band {_band(target_band)}），{DISCLAIMER}",
    ] + _warning_lines(limits)
    sentences = result.get("sentences") or []
    changes = [
        f"【AI 逐句精修】{DISCLAIMER} · 共 {len(sentences)} 句，"
        f"修改 {result.get('changed_count', 0)} 句"
    ] + _warning_lines(limits)
    changes.append("")
    for sentence in sentences:
        if not sentence.get("changed"):
            continue
        changes.append(f"第 {sentence['i'] + 1} 句")
        changes.append(f"原句：{sentence['original']}")
        changes.append(f"改句：{sentence['revised']}")
        if sentence.get("explanation"):
            changes.append(f"说明：{sentence['explanation']}")
        changes.append("")
    changes.append(_provenance(generation))
    return {"full": "\n".join(full).strip(), "changes": "\n".join(changes).strip()}


QUALITY_FAILED = "改写质量检查未通过，请对照下方提示使用，或重新生成"


def change_line(change) -> str:
    """One key change as text; structured {before, after, why} or a legacy string."""
    if not isinstance(change, dict):
        return str(change)
    before, after, why = change.get("before"), change.get("after"), change.get("why")
    if before and after:
        text = f"“{before}” → “{after}”"
    elif after:
        text = f"新增“{after}”"
    else:
        text = f"删除“{before}”"
    return f"{text}（{why}）" if why else text


def rewrite_texts(result: dict, generation: dict) -> dict:
    target = _band(result.get("target_band"))
    failed = result.get("quality_passed") is False
    quality = [QUALITY_FAILED] if failed else []
    essay = [
        result.get("essay") or "",
        "",
        f"——以上为 AI 改写范文（目标 Band {target}，未经评分验证），{DISCLAIMER}",
        *quality,
    ] + _warning_lines(result.get("warnings"))
    notes = [
        f"【AI 整篇改写】{DISCLAIMER} · 目标 Band {target}（未经评分验证）· "
        f"{result.get('word_count', 0)} 词（服务端计数）",
        *quality,
    ] + _warning_lines(result.get("warnings"))
    notes += ["", result.get("essay") or "", ""]
    if result.get("answers"):
        notes.append("题目回应对照（AI 标注；服务端只核实引文在改写稿中，是否切题请人工判断）：")
        notes += [f"- {a['part']}：“{a['quote']}”" for a in result["answers"]]
        notes.append("")
    if result.get("key_changes"):
        notes.append("关键改动：")
        notes += [f"{n}. {change_line(c)}" for n, c in enumerate(result["key_changes"], 1)]
        notes.append("")
    if result.get("band_rationale"):
        notes += [f"AI 对目标分数段的说明（自述，未经评分验证）：{result['band_rationale']}", ""]
    notes.append(_provenance(generation))
    return {"essay": "\n".join(essay).strip(), "with_notes": "\n".join(notes).strip()}


def copies_for(kind: str, result: dict, generation: dict, submission: dict) -> dict:
    if kind == "evaluate":
        return {"evaluation": evaluation_text(result, generation)}
    if kind == "refine":
        return refine_texts(result, generation, submission.get("target_band"))
    return rewrite_texts(result, generation)
