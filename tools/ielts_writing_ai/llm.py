"""Model clients: an OpenAI-compatible chat client (stdlib urllib) and a demo fake.

The real client is used for DeepSeek, Qwen (DashScope compatible mode) or any
other OpenAI-compatible endpoint.  API keys are only ever sent as the
Authorization header and never logged or stored.
"""

from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

import certifi

from . import essay as essay_lib


class LLMError(Exception):
    def __init__(
        self,
        code: str,
        message: str = "",
        *,
        usage: dict | None = None,
        response_received: bool = False,
        http_status: int | None = None,
    ):
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        # Keep provider accounting even when its generated content is unusable.
        # None means unknown usage, not a confirmed zero-token request.
        self.usage = dict(usage) if isinstance(usage, dict) else None
        self.response_received = response_received
        self.http_status = http_status


@dataclass
class LLMResult:
    text: str
    model: str
    latency_ms: int
    usage: dict = field(default_factory=dict)
    # Thinking-mode chain of thought (never parsed, never shown to students).
    reasoning: str = ""

    def json(self) -> dict:
        return extract_json_object(self.text)


# The whole reply must be one JSON object, optionally wrapped in a single code fence.
# Text outside the JSON ("I can't read this, here is an example: {...}") is a
# statement about the JSON that we cannot validate, so such replies are rejected.
_FENCE_RE = re.compile(r"```(?:json|JSON)?[ \t]*\r?\n(.*?)\r?\n[ \t]*```", re.S)


def parse_strict_json(text: str | None) -> dict | None:
    content = (text or "").strip()
    fence = _FENCE_RE.fullmatch(content)
    if fence:
        content = fence.group(1).strip()
    if not (content.startswith("{") and content.endswith("}")):
        return None
    try:
        value = json.loads(content)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def extract_json_object(text: str) -> dict:
    value = parse_strict_json(text)
    if value is None:
        raise LLMError("invalid_json", "模型输出不是单独的 JSON 对象（JSON 之外不能有其他文字）")
    return value


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A model call must not silently send another request or forward its bearer key.
        return None


def _tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if not context.get_ca_certs():
        # Python.org builds on macOS may have no configured CA bundle at all.
        # Keep certificate and hostname validation enabled, adding trusted public CAs.
        context.load_verify_locations(cafile=certifi.where())
    return context


def reasoning_tokens(usage: dict | None) -> int | None:
    """Reasoning tokens if the provider reports them (OpenAI-style
    usage.completion_tokens_details.reasoning_tokens); None means not reported."""
    details = (usage or {}).get("completion_tokens_details")
    value = details.get("reasoning_tokens") if isinstance(details, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class ChatClient:
    """Minimal OpenAI-compatible /chat/completions client."""

    retry_statuses = {429, 500, 502, 503, 504}

    def __init__(self, *, provider: str, base_url: str, api_key: str, model: str, timeout: float):
        self.provider = provider
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._opener = urllib.request.build_opener(
            _NoRedirect(), urllib.request.HTTPSHandler(context=_tls_context())
        )

    def _open(self, request, timeout: float | None = None):
        """One transport attempt, with no automatic redirects or network retries."""
        return self._opener.open(request, timeout=timeout or self.timeout)

    def complete(
        self,
        messages: list[dict],
        *,
        json_mode: bool,
        max_tokens: int,
        temperature: float = 0.2,
        context: dict | None = None,
        retries: int = 1,
        thinking: str = "off",
        timeout: float | None = None,
    ) -> LLMResult:
        if not self.api_key:
            raise LLMError("missing_api_key", "未配置模型 API Key")
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if self.provider == "deepseek":
            # Flash defaults to thinking mode. It is off unless a caller asks for it
            # (only the evaluation, via IWA_EVALUATE_THINKING), with its own budget.
            if thinking and thinking != "off":
                body["thinking"] = {"type": "enabled"}
                body["reasoning_effort"] = thinking
            else:
                body["thinking"] = {"type": "disabled"}
        elif thinking and thinking != "off":
            raise LLMError("unsupported", f"{self.provider} 不支持思考模式设置")
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        last_error: LLMError | None = None
        for attempt in range(retries + 1):
            started = time.monotonic()
            response_details = {"response_received": False, "http_status": None}
            request = urllib.request.Request(
                self.base_url,
                data=payload,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                # Only the thinking evaluation overrides the timeout.
                opened = self._open(request) if timeout is None else self._open(request, timeout)
                with opened as response:
                    response_details.update(
                        response_received=True, http_status=getattr(response, "status", 200)
                    )
                    raw = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                exc.close()  # release the connection held by the error response
                last_error = LLMError(
                    f"http_{exc.code}",
                    f"模型服务返回 HTTP {exc.code}",
                    response_received=True,
                    http_status=exc.code,
                )
                if exc.code in self.retry_statuses and attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise last_error from None
            except TimeoutError:  # socket.timeout is an alias since 3.10
                last_error = LLMError("timeout", "模型响应超时", **response_details)
                if attempt < retries:
                    continue
                raise last_error from None
            except (urllib.error.URLError, OSError) as exc:
                last_error = LLMError(
                    "network", f"无法连接模型服务：{type(exc).__name__}", **response_details
                )
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise last_error from None
            except ValueError:
                raise LLMError(
                    "invalid_response", "模型服务返回了非 JSON 响应", **response_details
                ) from None
            latency = int((time.monotonic() - started) * 1000)
            usage = (
                raw.get("usage")
                if isinstance(raw, dict) and isinstance(raw.get("usage"), dict)
                else None
            )
            response_details["usage"] = usage
            try:
                choice = raw["choices"][0]
                text = choice["message"]["content"] or ""
            except (KeyError, IndexError, TypeError):
                raise LLMError(
                    "invalid_response", "模型响应缺少 choices", **response_details
                ) from None
            if isinstance(text, list):  # some providers return content parts
                text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
            if not str(text).strip():
                raise LLMError("empty", "模型返回为空", **response_details)
            if choice.get("finish_reason") == "length":
                raise LLMError("truncated", "模型输出被截断，请重试", **response_details)
            reasoning = choice["message"].get("reasoning_content") or ""
            return LLMResult(
                str(text),
                str(raw.get("model") or self.model),
                latency,
                usage or {},
                reasoning=str(reasoning),
            )
        raise last_error or LLMError("unknown")


# ---------------------------------------------------------------------------
# Demo provider: deterministic, offline, clearly labelled as not real AI.
# ---------------------------------------------------------------------------

_DEMO_FIXES = [
    (r"\balot\b", "a lot"),
    (r"\bdont\b", "don't"),
    (r"\bdoesnt\b", "doesn't"),
    (r"\bcant\b", "can't"),
    (r"\bi\b", "I"),
    (r"\bmore better\b", "better"),
    (r"\bpeoples\b", "people"),
    (r"\s+,", ","),
    (r" {2,}", " "),
]


def _demo_fix(sentence: str) -> str:
    fixed = sentence
    for pattern, replacement in _DEMO_FIXES:
        fixed = re.sub(pattern, replacement, fixed)
    if fixed and fixed[0].islower():
        fixed = fixed[0].upper() + fixed[1:]
    return fixed


class FakeClient:
    """Offline demo provider used for local trials and tests."""

    provider = "fake"

    def __init__(self, model: str = "fake-demo", fail_kinds: set[str] | None = None):
        self.model = model
        self.fail_kinds = set(fail_kinds or ())
        self.calls: list[str] = []

    def complete(
        self,
        messages,
        *,
        json_mode,
        max_tokens,
        temperature=0.2,
        context=None,
        retries=1,
        thinking="off",
        timeout=None,
    ):
        context = context or {}
        kind = context.get("kind", "")
        self.calls.append(kind)
        if kind in self.fail_kinds:
            raise LLMError("http_503", "演示模式：模拟模型服务失败")
        builder = {
            "evaluate": self._evaluate,
            "refine": self._refine,
            "rewrite": self._rewrite_notes if context.get("mode") == "notes" else self._rewrite,
            "describe_image": self._describe_image,
        }.get(kind)
        if builder is None:
            raise LLMError("invalid_request", "未知生成类型")
        value = builder(context)
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        return LLMResult(text, self.model, 5, {"demo": True})

    @staticmethod
    def _evaluate(context):
        words = int(context.get("word_count") or 0)
        minimum = int(context.get("minimum_words") or 250)
        base = 6.0 if words >= minimum else 5.0
        sentences = context.get("sentences") or []
        first = sentences[0]["text"] if sentences else ""
        quote = " ".join(first.split()[:8])
        crit = {
            "task": base,
            "coherence": base,
            "lexical": base - 0.5,
            "grammar": base - 0.5,
        }
        return {
            "criteria": {
                key: {
                    "band": band,
                    "summary": f"【演示】这是 {key} 维度的示例评语，未经过真实 AI 分析。",
                    "strengths": [
                        {"quote": quote, "comment": "【演示】示例优点：开头直接回应题目。"}
                    ],
                    "issues": [
                        {
                            "quote": quote,
                            "comment": "【演示】示例问题：这句可以表达得更具体。",
                            "suggestion": "【演示】补充一个具体的解释或例子。",
                        }
                    ],
                }
                for key, band in crit.items()
            },
            **(
                {"argument": FakeClient._demo_argument(sentences)}
                if context.get("task_type") == "task2"
                else {"comparisons": []}
            ),
            "overall_comment": "【演示】这是演示模式的固定评语。连接真实模型后，这里会给出整体评价。",
            "priorities": [
                "【演示】优先修正基础语法错误",
                "【演示】每个主体段补充具体例子",
                "【演示】减少重复用词",
            ],
        }

    @staticmethod
    def _demo_argument(sentences):
        """A structurally valid demo argument map built from the essay's own sentences."""
        firsts = {}
        for item in sentences:
            firsts.setdefault(item["paragraph"], item["text"])
        ordered = [firsts[k] for k in sorted(firsts)]
        paragraphs = []
        for n, text in enumerate(ordered):
            role = "introduction" if n == 0 else "conclusion" if n == len(ordered) - 1 else "body"
            paragraphs.append(
                {
                    "p": n + 1,
                    "role": role,
                    "main_point": text,
                    "verdict": "supports",
                    "comment": "【演示】示例判断，未经过真实 AI 分析。",
                }
            )
        problems = []
        if len(ordered) > 2:
            problems.append(
                {
                    "type": "unsupported",
                    "quote": ordered[1],
                    "comment": "【演示】示例问题：这一段的论点缺少解释。",
                    "suggestion": "【演示】补充“为什么”和一个回扣论点的例子。",
                }
            )
        return {
            "position": {
                "quote": ordered[0] if ordered else "",
                "consistent": True,
                "comment": "【演示】示例立场判断。",
            },
            "paragraphs": paragraphs,
            "problems": problems,
            "improvements": (
                [
                    {
                        "quote": ordered[-1],
                        "suggestion": "【演示】示例优化：结尾可以更简洁地重申立场（不是错误）。",
                    }
                ]
                if ordered
                else []
            ),
        }

    @staticmethod
    def _refine(context):
        items = []
        for sentence in context.get("sentences") or []:
            revised = _demo_fix(sentence["text"])
            changed = revised != sentence["text"]
            items.append(
                {
                    "i": sentence["i"],
                    "revised": revised,
                    "tags": ["grammar"] if changed else [],
                    "explanation": "【演示】按固定规则修正拼写/大小写。" if changed else "",
                }
            )
        return {"sentences": items, "summary": "【演示】仅按固定规则做了少量机械修正。"}

    @staticmethod
    def _rewrite(context):
        originals = context.get("sentences") or []
        sentences = [
            essay_lib.Sentence(s["i"], s["paragraph"], _demo_fix(s["text"])) for s in originals
        ]
        body = essay_lib.join_sentences(sentences)
        return {
            "essay": body,
            "original_addresses_question": True,
            **FakeClient._demo_notes([s["text"] for s in originals], [s.text for s in sentences]),
        }

    @staticmethod
    def _rewrite_notes(context):
        original = [s.text for s in essay_lib.split_sentences(context.get("original_essay", ""))]
        rewrite = [s.text for s in essay_lib.split_sentences(context.get("rewrite_essay", ""))]
        return {"original_addresses_question": True, **FakeClient._demo_notes(original, rewrite)}

    @staticmethod
    def _demo_notes(original: list[str], rewrite: list[str]) -> dict:
        """Structured, verifiable demo notes: sentence pairs that really differ."""
        changes = [
            {"before": old, "after": new, "why": "【演示】按固定规则修正拼写 / 大小写。"}
            for old, new in zip(original, rewrite, strict=False)
            if old != new
        ][:3]
        notes = {
            "answers": [
                {"part": f"【演示】题目要求 {n + 1}", "quote": text}
                for n, text in enumerate(rewrite[:2])
            ],
            "key_changes": changes,
            "band_rationale": "【演示】连接真实模型后，这里会说明为了向目标分数段靠近做了哪些修改。",
        }
        if not changes:
            notes["unchanged_reason"] = "【演示】固定规则没有找到需要修正的地方。"
        return notes

    @staticmethod
    def _describe_image(context):
        # A structurally sufficient demo reading, so the demo can show a scored Task 1.
        return json.dumps(
            {
                "readability": "sufficient",
                "visual_type": "bar_chart",
                "title": "【演示】示例数据，未真实识别图片",
                "units": "thousand visitors",
                "categories": ["Museum A", "Museum B", "Museum C", "Museum D"],
                "periods": ["2020"],
                "data_points": [
                    {"label": "Museum A", "value": "140"},
                    {"label": "Museum B", "value": "90"},
                    {"label": "Museum C", "value": "200"},
                    {"label": "Museum D", "value": "60"},
                ],
                "main_features": ["Museum C is the highest", "Museum D is the lowest"],
                "unclear": [],
                "summary": "【演示】固定示例读图结果，与上传的图片无关。",
            },
            ensure_ascii=False,
        )


def build_client(settings, *, vision: bool = False):
    if vision:
        if settings.vision_provider == "none":
            return None
        if settings.vision_provider == "fake":
            return FakeClient(model=settings.vision_model or "fake-vision-demo")
        return ChatClient(
            provider=settings.vision_provider,
            base_url=settings.vision_base_url,
            api_key=settings.vision_api_key,
            model=settings.vision_model,
            timeout=settings.llm_timeout,
        )
    if settings.llm_provider == "fake":
        return FakeClient(model=settings.llm_model or "fake-demo")
    return ChatClient(
        provider=settings.llm_provider,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=settings.llm_timeout,
    )
