"""A person's check of Task 1 chart readings before they are used for realcheck.

The first real reading (2026-11-13, docs/design/ielts-writing-ai-official-t1-pro-20261113-
results) was well formed and passed every automatic gate, yet two values were clearly
wrong. So a frozen reading only lets Task Achievement be scored once a person has
compared it with the image and confirmed it (correcting the text where needed):

1. ``realcheck --images-only`` reads each chart once and writes image_descriptions.json
   plus image_check.md, a sheet with one data point per line.
2. The person compares the sheet with each image. Wrong values are corrected in a JSON
   file {sample id: full corrected reading}.
3. ``realcheck-check-images --confirm ...`` writes a new readings file in which those
   readings carry a check record bound to the image's sha256.
4. ``realcheck --image-descriptions <that file> --require-checked-images`` evaluates.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from . import visual

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CHECKER_MAX = 100


class ImageCheckError(ValueError):
    pass


def image_sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_problem(outcome: dict) -> str | None:
    """Why a stored check record is unusable, or None."""
    check = outcome.get("check")
    if outcome.get("status") != "ready":
        return "只有可用的读数才能核对"
    if not isinstance(check, dict) or check.get("status") != "confirmed":
        return "status 必须是 confirmed"
    by = check.get("by")
    if not isinstance(by, str) or not by.strip() or len(by) > CHECKER_MAX:
        return f"by（核对人）必须是 1–{CHECKER_MAX} 字"
    if not isinstance(check.get("at"), str) or not check["at"]:
        return "缺少核对时间 at"
    if not isinstance(check.get("image_sha256"), str) or not SHA256_RE.match(check["image_sha256"]):
        return "image_sha256 必须是题图文件的 sha256"
    if type(check.get("edited")) is not bool:
        return "edited 必须是 true / false"
    if check["edited"] and not (
        isinstance(check.get("model_description"), str) and check["model_description"].strip()
    ):
        return "改正过的读数必须保留识图模型的原始读数 model_description"
    return None


def require_same_image(item: dict, check: dict) -> None:
    """The reading was checked against this sample's image file, byte for byte."""
    from .realcheck import RealCheckError

    if not item.get("image"):
        raise RealCheckError(f"样本 {item['id']} 没有题图，不能使用核对过的读数")
    if image_sha256(item["image"]) != check["image_sha256"]:
        raise RealCheckError(f"样本 {item['id']} 的题图与核对读数时的题图不同")


def sheet(items: list[dict], outcomes: dict) -> str:
    """image_check.md: every Task 1 reading to compare with its image."""
    lines = [
        "# 题图读数核对表",
        "",
        "识图模型的读数格式正确，不等于数值正确。请打开每张题图逐条对照下面的读数：",
        "",
        "- 全部正确：记下样本 id，用 `realcheck-check-images --confirm <id,...> --by <核对人>` 确认。",
        '- 有错：把该样本的整段读数复制到一个 JSON 文件 `{"样本 id": "改正后的完整读数"}` 里改正，'
        "确认时加 `--corrections <文件>`。只改看错的数值或标签，不要补写题图上没有的内容。",
        "- 看不清或拿不准：不要确认。没有确认的读数不用于评 Task Achievement 和总分。",
        "",
    ]
    seen = set()
    for item in items:
        base = item.get("repeat_of") or item["id"]
        if item["task_type"] != "task1" or base in seen:
            continue
        seen.add(base)
        outcome = outcomes.get(base) or {}
        lines.append(f"## {base}")
        lines.append("")
        if item.get("image"):
            lines.append(f"- 题图：`{item['image']}`（sha256 `{image_sha256(item['image'])}`）")
        status = outcome.get("status") or "无"
        state = "已核对" if outcome.get("check") else "未核对"
        lines.append(f"- 读数状态：{status}（{state}）")
        lines.append("")
        if outcome.get("status") == "ready":
            lines += ["```text", visual.check_text(outcome.get("description")), "```", ""]
        else:
            lines += [f"没有可用读数：{outcome.get('error') or '未识别'}", ""]
    return "\n".join(lines)


def confirm(
    outcomes_file: dict,
    items: list[dict],
    ids: list[str],
    *,
    by: str,
    corrections: dict | None = None,
    now: datetime | None = None,
) -> dict:
    """A copy of an image_descriptions.json (version 2) in which the readings of
    ``ids`` carry a check record; corrected readings replace the model's text, which
    is kept as model_description. Other readings are copied unchanged."""
    images = dict(outcomes_file.get("images") or {})
    by = (by or "").strip()
    if not by or len(by) > CHECKER_MAX:
        raise ImageCheckError(f"--by（核对人）必须是 1–{CHECKER_MAX} 字")
    if not ids or len(set(ids)) != len(ids):
        raise ImageCheckError("--confirm 需要不重复的样本 id")
    corrections = corrections or {}
    stray = sorted(set(corrections) - set(ids))
    if stray:
        raise ImageCheckError("改正文件里有没有确认的样本：" + "、".join(stray))
    by_id = {item["id"]: item for item in items}
    at = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for sample_id in ids:
        outcome = images.get(sample_id)
        item = by_id.get(sample_id)
        if not item or item["task_type"] != "task1" or not item.get("image"):
            raise ImageCheckError(f"样本文件里没有带题图的 Task 1：{sample_id}")
        if not outcome or outcome.get("status") != "ready":
            raise ImageCheckError(f"{sample_id} 没有可用的读数，不能确认")
        if outcome.get("check"):
            raise ImageCheckError(f"{sample_id} 已经核对过")
        record = {
            "status": "confirmed",
            "by": by,
            "at": at,
            "image_sha256": image_sha256(item["image"]),
            "edited": False,
        }
        description = outcome["description"]
        if sample_id in corrections:
            text = corrections[sample_id]
            if not isinstance(text, str) or not text.strip():
                raise ImageCheckError(f"{sample_id} 的改正读数必须是非空字符串")
            text = text.replace("\r\n", "\n").strip()
            if len(text) > visual.CHECK_MAX_CHARS:
                raise ImageCheckError(f"{sample_id} 的改正读数超过 {visual.CHECK_MAX_CHARS} 字")
            if not visual.same_reading(text, description):
                record.update(edited=True, model_description=description)
                description = text
        images[sample_id] = dict(outcome, description=description, check=record)
    return {"version": outcomes_file.get("version", 2), "images": images}


def load_corrections(path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ImageCheckError(f"读不了改正文件 {path}：{exc}") from None
    if not isinstance(data, dict):
        raise ImageCheckError("改正文件必须是 {样本 id: 改正后的完整读数}")
    return data
