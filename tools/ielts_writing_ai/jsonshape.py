"""Why a model reply is not one valid JSON object, in words the model (retry note) and
a reviewer (realcheck report) can act on.

Diagnosis only: nothing here repairs a reply or makes it usable - llm.parse_strict_json
stays the only way in. Real runs showed the same failure again and again: a long
evaluation with one closing bracket too few or too many where a long block ends
(2026-11-04 weak, 2026-11-06 under-length x2: argument / overall_comment / priorities
written inside criteria; 2026-11-06 off-topic: argument closed early, priorities after
the end of the object). A retry told only "text outside the JSON" repeated the error.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping

_FENCE_RE = re.compile(r"```(?:json|JSON)?[ \t]*\r?\n(.*?)\r?\n[ \t]*```", re.S)
_PAIR = {"}": "{", "]": "["}
MAX_FINDINGS = 3


def unwrap(text: str | None) -> str:
    """The reply without surrounding whitespace or a single ```json fence."""
    content = (text or "").strip()
    fence = _FENCE_RE.fullmatch(content)
    return fence.group(1).strip() if fence else content


def _names(keys: Iterable[str]) -> str:
    return "、".join(dict.fromkeys(keys))


class _Scan:
    """One pass over strings and brackets, remembering which key opened each container."""

    def __init__(self, content: str):
        self.keys: list[tuple[str, int, str | None]] = []  # (key, depth, parent)
        self.after_root: list[str] = []  # keys written after the root object closed
        self.trailing_text = False  # non-key text after the root object closed
        self.root_end: int | None = None
        self.last_root_key: str | None = None  # last top-level key before the root closed
        self.mismatch: tuple[int, str, str] | None = None  # (position, expected, found)
        self.unterminated_string = False
        self.stack: list[tuple[str, str | None]] = []  # (bracket, name)
        self._run(content)

    def _run(self, content: str) -> None:
        n, i, pending = len(content), 0, None
        while i < n:
            char = content[i]
            if char == '"':
                j = i + 1
                while j < n and content[j] != '"':
                    j += 2 if content[j] == "\\" else 1
                if j >= n:
                    self.unterminated_string = True
                    return
                k = j + 1
                while k < n and content[k] in " \t\r\n":
                    k += 1
                if k < n and content[k] == ":":
                    key = content[i + 1 : j]
                    if self.stack and self.stack[-1][0] == "{":
                        self.keys.append((key, len(self.stack), self.stack[-1][1]))
                        if len(self.stack) == 1 and self.root_end is None:
                            self.last_root_key = key
                        pending = key
                    elif not self.stack and self.root_end is not None:
                        self.after_root.append(key)
                elif not self.stack and self.root_end is not None:
                    self.trailing_text = True
                i = j + 1
                continue
            if char in "{[":
                if self.stack and self.stack[-1][0] == "{":
                    name = pending
                elif self.stack:
                    name = self.stack[-1][1]  # items of a list share its name
                else:
                    name = None
                    if self.root_end is not None:
                        self.trailing_text = True
                self.stack.append((char, name))
                pending = None
            elif char in "}]":
                if not self.stack:
                    if self.root_end is not None:
                        self.trailing_text = True
                elif self.stack[-1][0] != _PAIR[char]:
                    if self.mismatch is None:
                        expected = "}" if self.stack[-1][0] == "{" else "]"
                        self.mismatch = (i, expected, char)
                    self.stack.pop()
                else:
                    self.stack.pop()
                    if not self.stack and self.root_end is None:
                        self.root_end = i
            elif not self.stack and self.root_end is not None and not char.isspace():
                if char not in ",:":
                    self.trailing_text = True
            i += 1


def diagnose(
    text: str | None,
    root_keys: Iterable[str] = (),
    homes: Mapping[str, str] | None = None,
) -> str:
    """A short Chinese description of what is wrong with a reply that is not one JSON
    object. root_keys: keys that belong at the top level; homes: key -> the object it
    belongs in (e.g. "improvements" -> "argument"), used for keys found at the wrong
    level. A top-level key found inside its home is accepted (the older nested form,
    criteria -> task / coherence / lexical / grammar)."""
    content = unwrap(text)
    if not content:
        return "回复是空的，没有 JSON"
    if not content.startswith("{"):
        return "回复不是以 { 开头的 JSON 对象（JSON 前面有其他文字）"
    try:
        value = json.loads(content)
    except ValueError as exc:
        error = exc
    else:
        if isinstance(value, dict):
            return "JSON 本身合法"  # not reached for replies parse_strict_json rejected
        return "最外层不是 JSON 对象"
    root = set(root_keys)
    homes = dict(homes or {})
    scan = _Scan(content)
    findings = []

    nested = {}  # parent -> top-level keys written inside it
    for key, depth, parent in scan.keys:
        if key in root and depth > 1 and parent and homes.get(key) != parent:
            nested.setdefault(parent, []).append(key)
    for parent, keys in nested.items():
        findings.append(
            f"{_names(keys)} 被写进了 {parent} 里面：{parent} 写完后少了一个 }}，"
            "这些键必须在最外层"
        )
    if scan.root_end is not None and (scan.after_root or scan.trailing_text):
        where = f"在 {scan.last_root_key} 之后" if scan.last_root_key else ""
        if scan.after_root:
            findings.append(
                f"最外层对象{where}就结束了（多了一个 }} 或 ]），后面的 "
                f"{_names(scan.after_root)} 落在了 JSON 之外"
            )
        else:
            findings.append(f"最外层对象{where}就结束了，JSON 后面还有其他文字")
    strays = [
        key
        for key, depth, _parent in scan.keys
        if depth == 1 and root and key not in root and homes.get(key)
    ]
    for key in dict.fromkeys(strays):
        findings.append(
            f"{key} 出现在最外层，但它属于 {homes[key]}：{homes[key]} 提前结束了（多了一个 }}）"
        )
    if scan.mismatch:
        position, expected, found = scan.mismatch
        findings.append(f"第 {position + 1} 个字符处括号不配对（应为 {expected}，实际是 {found}）")
    if scan.unterminated_string:
        findings.append("有字符串没有结束（引号不配对或回复被截断）")
    elif scan.stack and not nested:
        names = [name or "最外层" for _bracket, name in reversed(scan.stack)]
        findings.append(f"到结尾还有 {len(scan.stack)} 层括号没有闭合（{_names(names)}）")
    if not findings:
        position = getattr(error, "pos", None)
        message = getattr(error, "msg", str(error))
        where = f"，第 {position + 1} 个字符" if isinstance(position, int) else ""
        findings.append(f"JSON 语法错误（{message}{where}）")
    return "；".join(findings[:MAX_FINDINGS])
