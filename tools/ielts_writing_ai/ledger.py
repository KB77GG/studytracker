"""Persistent request ledger for paid batches (realcheck --ledger).

Review of 2026-11-11 (docs/design/iwa-holdout-execution-review-20261111): requests were
only counted in memory and in the final report, so a run killed after five requests
was counted as zero on restart (189 of 184 allowed), and two launchers started at once
each saw room for the same 28 requests (212 of 184).

Every model request is now reserved here *before* it is sent. Under an exclusive lock
on the ledger file the reservations are counted, the caps are checked, a reservation
line is appended and fsync'd; only then does the request go out. A reservation that is
never completed (crash, kill, power loss, unknown outcome) still counts as used. Text
and image requests have separate caps. The ledger records which code it was opened
with and refuses another version, so a resumed batch cannot mix code.

Only ids, kinds, model names, error codes and token counts are written - never essay,
prompt or model text - so the ledger can be shared.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

VISION_KINDS = frozenset({"describe_image"})
TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "prompt_cache_hit_tokens")


class LedgerError(Exception):
    """A request may not be sent (cap reached, different code, unreadable ledger)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def category(kind: str) -> str:
    return "vision" if kind in VISION_KINDS else "text"


def _tokens(usage: dict | None) -> dict:
    usage = usage or {}
    out = {}
    for field in ("prompt_tokens", "completion_tokens"):
        value = usage.get(field)
        if type(value) is int and value >= 0:
            out[field] = value
    for value in (
        usage.get("prompt_cache_hit_tokens"),
        (usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
    ):
        if type(value) is int and value >= 0:
            out["prompt_cache_hit_tokens"] = value
            break
    return out


def read(path) -> list[dict]:
    """All ledger lines. A torn last line (killed while writing) is ignored; any other
    unreadable line is an error, because it could hide a reservation."""
    path = Path(path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").split("\n")
    out = []
    for n, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            if n == len(lines) - 1:
                continue  # the final line was being written when the process died
            raise LedgerError("ledger_corrupt", f"账本第 {n + 1} 行无法读取：{path}") from None
    return out


def summarize(entries: list[dict]) -> dict:
    """Reserved / completed / unknown counts per category, and per run (ledger run name)
    the requests, outcomes and token totals. A reservation without a completion line is
    "unknown": it may have been sent, so it counts as used and its tokens are unknown."""
    done = {e["id"]: e for e in entries if e.get("type") == "done"}
    out = {
        "text": {"reserved": 0, "ok": 0, "failed": 0, "unknown": 0},
        "vision": {"reserved": 0, "ok": 0, "failed": 0, "unknown": 0},
        "runs": {},
    }
    for entry in entries:
        if entry.get("type") != "reserve":
            continue
        cat = entry["category"]
        out[cat]["reserved"] += 1
        run = out["runs"].setdefault(
            entry.get("run") or "",
            {
                "text": 0,
                "vision": 0,
                "unknown": 0,
                "unknown_usage": 0,
                "cache_hits_unreported": 0,
                "models": [],
            }
            | dict.fromkeys(TOKEN_FIELDS, 0),
        )
        run[cat] += 1
        if entry.get("model") and entry["model"] not in run["models"]:
            run["models"].append(entry["model"])
        finished = done.get(entry["id"])
        if finished is None:
            out[cat]["unknown"] += 1
            run["unknown"] += 1
            continue
        out[cat]["ok" if finished.get("ok") else "failed"] += 1
        tokens = finished.get("tokens") or {}
        if "prompt_tokens" not in tokens or "completion_tokens" not in tokens:
            run["unknown_usage"] += 1
        elif "prompt_cache_hit_tokens" not in tokens:
            run["cache_hits_unreported"] += 1
        for field in TOKEN_FIELDS:
            run[field] += tokens.get(field, 0)
    return out


class Ledger:
    def __init__(
        self,
        path,
        *,
        text_cap: int,
        vision_cap: int,
        run: str,
        code_sha256: str,
        prompt_version: str,
    ):
        for name, value in (("text_cap", text_cap), ("vision_cap", vision_cap)):
            if type(value) is not int or value < 0:
                raise LedgerError("ledger_cap", f"账本的 {name} 必须是非负整数")
        self.path = Path(path)
        self.text_cap, self.vision_cap = text_cap, vision_cap
        self.run = run
        self.code_sha256 = code_sha256
        self.prompt_version = prompt_version

    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield fd
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _append(self, fd: int, entry: dict) -> None:
        os.write(fd, (json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8"))
        os.fsync(fd)

    def _check_header(self, fd: int, entries: list[dict]) -> None:
        headers = [e for e in entries if e.get("type") == "header"]
        if not headers:
            self._append(
                fd,
                {
                    "type": "header",
                    "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "code_sha256": self.code_sha256,
                    "prompt_version": self.prompt_version,
                },
            )
            return
        header = headers[0]
        if (header.get("code_sha256"), header.get("prompt_version")) != (
            self.code_sha256,
            self.prompt_version,
        ):
            raise LedgerError(
                "ledger_code",
                "账本是另一版代码建立的（源码指纹或提示词版本不同），同一批次不能混用代码："
                f"{self.path}",
            )

    def check(self) -> dict:
        """Before a run: the ledger is readable and from this code. Returns the summary."""
        with self._locked() as fd:
            entries = read(self.path)
            self._check_header(fd, entries)
            return summarize(entries)

    def reserve(self, *, sample: str, kind: str, model: str, attempt: int) -> str:
        cat = category(kind)
        cap = self.vision_cap if cat == "vision" else self.text_cap
        with self._locked() as fd:
            entries = read(self.path)
            self._check_header(fd, entries)
            used = summarize(entries)[cat]["reserved"]
            if used >= cap:
                name = "识图" if cat == "vision" else "文字"
                raise LedgerError(
                    "ledger_cap",
                    f"已达到批次账本的{name}请求上限（已预留 {used} 次，上限 {cap} 次）",
                )
            rid = uuid.uuid4().hex
            self._append(
                fd,
                {
                    "type": "reserve",
                    "id": rid,
                    "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "run": self.run,
                    "sample": sample,
                    "kind": kind,
                    "category": cat,
                    "model": model,
                    "attempt": attempt,
                    "cap": cap,
                },
            )
        return rid

    def complete(self, rid: str, *, ok: bool, error: str | None, usage: dict | None) -> None:
        with self._locked() as fd:
            self._append(
                fd,
                {
                    "type": "done",
                    "id": rid,
                    "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "ok": bool(ok),
                    "error": error,
                    "tokens": _tokens(usage),
                },
            )
