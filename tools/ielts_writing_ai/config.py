"""Configuration for the standalone IELTS writing AI trial tool.

Everything is read from ``IWA_*`` environment variables or an optional
``.env`` file next to this module.  Nothing is shared with the main
StudyTracker ``config.py``: the trial tool has its own API keys, data
directory, database, upload directory and session cookie.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = TOOL_DIR / ".env"
DEFAULT_DATA_DIR = TOOL_DIR / "var"

# Database file names that belong to the main application.  The trial tool
# refuses to open them even if someone points IWA_DB_PATH at them by mistake.
FORBIDDEN_DB_NAMES = {"app.db", "studytracker.db"}

PROVIDER_PRESETS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-flash",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model": "qwen-plus",
    },
    "openai_compatible": {"base_url": "", "model": ""},
    "fake": {"base_url": "", "model": "fake-demo"},
}

VISION_PRESETS = {
    # deepseek-flash reads images on the same endpoint and key (deepseek-v4-pro does not);
    # the client sends thinking disabled for DeepSeek, so the budget goes to the reading.
    "deepseek": {
        "base_url": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-flash",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model": "qwen-vl-max-latest",
    },
    "openai_compatible": {"base_url": "", "model": ""},
    "fake": {"base_url": "", "model": "fake-vision-demo"},
    "none": {"base_url": "", "model": ""},
}


class ConfigError(ValueError):
    """Raised when the trial tool configuration is unsafe or incomplete."""


def read_env_file(path: Path) -> dict[str, str]:
    """Parse a minimal KEY=VALUE env file (no interpolation, # comments)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def _as_int(value, default: int, *, minimum: int = 0) -> int:
    try:
        return max(minimum, int(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _as_float(value, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _as_bool(value, default: bool) -> bool:
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


# DeepSeek reasoning_effort levels (xhigh maps to high on the provider side, so it is
# not offered as a separate level).
THINKING_MODES = ("off", "high", "max")


@dataclass
class Settings:
    data_dir: Path = DEFAULT_DATA_DIR
    db_path: Path | None = None
    upload_dir: Path | None = None
    secret_key: str = ""
    host: str = "127.0.0.1"
    port: int = 5055
    url_prefix: str = ""
    cookie_secure: bool = False
    trust_proxy: bool = False
    session_days: int = 7

    llm_provider: str = "fake"
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    llm_timeout: float = 120.0
    llm_temperature: float = 0.2
    # Thinking mode for the original-essay evaluation only (refine/rewrite unchanged).
    # "off" keeps the tested behaviour; "high" asks DeepSeek to think before answering.
    # Thinking needs its own output budget and timeout: the 4500-token / 120 s limits
    # were measured without thinking and are not reused (provisional, to be calibrated
    # with realcheck).
    evaluate_thinking: str = "off"
    evaluate_thinking_max_tokens: int = 32000
    # 420 s: in the 2026-11-12 comparison deepseek-v4-pro took up to 255 s per
    # evaluation request (p90 176 s), too close to the earlier 300 s.
    evaluate_thinking_timeout: float = 420.0
    # The model of the original-essay evaluation only, on the same provider, endpoint
    # and key; empty means IWA_LLM_MODEL. The 2026-11-12 comparison chose
    # deepseek-v4-pro for the evaluation; refine / rewrite were not compared and keep
    # IWA_LLM_MODEL.
    evaluate_model: str = ""

    vision_provider: str = "none"
    vision_base_url: str = ""
    vision_model: str = ""
    vision_api_key: str = ""
    # The structured chart reading: 700 tokens was tight for a line graph with two
    # series; the evaluation's 32000 / 420 s do not apply to image reading.
    vision_max_tokens: int = 2000
    vision_timeout: float = 180.0

    daily_limit: int = 30
    max_workers: int = 2
    max_upload_mb: int = 5
    job_mode: str = "thread"  # "thread" in the server, "inline" in tests
    # Seconds to wait for the single-instance lock (covers a previous process still exiting).
    lock_wait: float = 5.0
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        self.data_dir = Path(self.data_dir).expanduser().resolve()
        self.db_path = Path(self.db_path or self.data_dir / "iwa.sqlite3").expanduser().resolve()
        self.upload_dir = Path(self.upload_dir or self.data_dir / "uploads").expanduser().resolve()
        self.url_prefix = "/" + self.url_prefix.strip("/") if self.url_prefix.strip("/") else ""

        provider = (self.llm_provider or "fake").strip().lower()
        if provider not in PROVIDER_PRESETS:
            raise ConfigError(f"IWA_LLM_PROVIDER 不支持：{provider}")
        self.llm_provider = provider
        preset = PROVIDER_PRESETS[provider]
        self.llm_base_url = self.llm_base_url or preset["base_url"]
        self.llm_model = self.llm_model or preset["model"]

        vision = (self.vision_provider or "none").strip().lower()
        if vision not in VISION_PRESETS:
            raise ConfigError(f"IWA_VISION_PROVIDER 不支持：{vision}")
        self.vision_provider = vision
        vpreset = VISION_PRESETS[vision]
        self.vision_base_url = self.vision_base_url or vpreset["base_url"]
        self.vision_model = self.vision_model or vpreset["model"]
        if not self.vision_api_key and vision not in {"none", "fake"}:
            self.vision_api_key = self.llm_api_key

        if self.job_mode not in {"thread", "inline"}:
            raise ConfigError("IWA_JOB_MODE 只能是 thread 或 inline")

    @property
    def is_demo(self) -> bool:
        return self.llm_provider == "fake"

    @property
    def vision_enabled(self) -> bool:
        return self.vision_provider != "none"

    def validate(self) -> None:
        """Reject configurations that could touch the main app or cannot work."""
        if self.db_path.name.lower() in FORBIDDEN_DB_NAMES:
            raise ConfigError(f"拒绝使用主应用数据库文件名：{self.db_path.name}")
        if self.port in {5000, 5002}:
            raise ConfigError("端口 5000/5002 属于主应用，试用工具请使用其他端口")
        if self.llm_provider != "fake":
            if not self.llm_api_key:
                raise ConfigError("真实模型需要配置 IWA_LLM_API_KEY")
            if not self.llm_base_url or not self.llm_model:
                raise ConfigError("需要配置 IWA_LLM_BASE_URL 与 IWA_LLM_MODEL")
        if self.evaluate_thinking not in THINKING_MODES:
            raise ConfigError(
                f"IWA_EVALUATE_THINKING 只能是 {' / '.join(THINKING_MODES)}：{self.evaluate_thinking}"
            )
        if self.evaluate_thinking != "off" and self.llm_provider not in {"deepseek", "fake"}:
            raise ConfigError("评价思考模式目前只支持 DeepSeek（IWA_LLM_PROVIDER=deepseek）")
        if self.vision_provider not in {"none", "fake"}:
            if not self.vision_api_key:
                raise ConfigError(
                    "识图模型需要配置 IWA_VISION_API_KEY（或与 IWA_LLM_API_KEY 共用）"
                )
            if not self.vision_base_url or not self.vision_model:
                raise ConfigError("需要配置 IWA_VISION_BASE_URL 与 IWA_VISION_MODEL")

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def resolve_secret_key(self) -> str:
        """Use IWA_SECRET_KEY, else a per-install key persisted in the data dir."""
        if self.secret_key:
            return self.secret_key
        self.ensure_dirs()
        key_file = self.data_dir / "secret_key"
        if key_file.is_file():
            self.secret_key = key_file.read_text(encoding="utf-8").strip()
        if not self.secret_key:
            self.secret_key = secrets.token_hex(32)
            key_file.write_text(self.secret_key, encoding="utf-8")
            os.chmod(key_file, 0o600)
        return self.secret_key

    def public_summary(self) -> dict:
        """Configuration facts that are safe to print (never the keys)."""
        return {
            "data_dir": str(self.data_dir),
            "db_path": str(self.db_path),
            "upload_dir": str(self.upload_dir),
            "bind": f"{self.host}:{self.port}{self.url_prefix}",
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_api_key_set": bool(self.llm_api_key),
            "evaluate_thinking": self.evaluate_thinking,
            "evaluate_thinking_max_tokens": self.evaluate_thinking_max_tokens,
            "evaluate_thinking_timeout": self.evaluate_thinking_timeout,
            "evaluate_model": self.evaluate_model or self.llm_model,
            "vision_provider": self.vision_provider,
            "vision_model": self.vision_model if self.vision_enabled else "",
            "vision_max_tokens": self.vision_max_tokens,
            "vision_timeout": self.vision_timeout,
            "vision_api_key_set": bool(self.vision_api_key),
            "daily_limit": self.daily_limit,
            "max_workers": self.max_workers,
            "cookie_secure": self.cookie_secure,
        }


def load_settings(
    env: dict | None = None, env_file: Path | str | None = None, **overrides
) -> Settings:
    """Build settings from (env file) < (process env) < (explicit overrides)."""
    source: dict[str, str] = {}
    file_path = (
        Path(env_file) if env_file else Path(os.environ.get("IWA_ENV_FILE") or DEFAULT_ENV_FILE)
    )
    source.update(read_env_file(file_path))
    source.update(
        {k: v for k, v in (os.environ if env is None else env).items() if k.startswith("IWA_")}
    )

    def get(name: str, default=""):
        return source.get(f"IWA_{name}", default)

    kwargs = {
        "data_dir": get("DATA_DIR") or DEFAULT_DATA_DIR,
        "db_path": get("DB_PATH") or None,
        "upload_dir": get("UPLOAD_DIR") or None,
        "secret_key": get("SECRET_KEY"),
        "host": get("HOST") or "127.0.0.1",
        "port": _as_int(get("PORT"), 5055, minimum=1),
        "url_prefix": get("URL_PREFIX"),
        "cookie_secure": _as_bool(get("COOKIE_SECURE"), False),
        "trust_proxy": _as_bool(get("TRUST_PROXY"), False),
        "session_days": _as_int(get("SESSION_DAYS"), 7, minimum=1),
        "llm_provider": get("LLM_PROVIDER") or "fake",
        "llm_base_url": get("LLM_BASE_URL"),
        "llm_model": get("LLM_MODEL"),
        "llm_api_key": get("LLM_API_KEY"),
        "llm_timeout": _as_float(get("LLM_TIMEOUT"), 120.0),
        "llm_temperature": _as_float(get("LLM_TEMPERATURE"), 0.2),
        "evaluate_thinking": (get("EVALUATE_THINKING") or "off").strip().lower(),
        "evaluate_thinking_max_tokens": _as_int(
            get("EVALUATE_THINKING_MAX_TOKENS"), 32000, minimum=1
        ),
        "evaluate_thinking_timeout": _as_float(get("EVALUATE_THINKING_TIMEOUT"), 420.0),
        "evaluate_model": (get("EVALUATE_MODEL") or "").strip(),
        "vision_provider": get("VISION_PROVIDER") or "none",
        "vision_base_url": get("VISION_BASE_URL"),
        "vision_model": get("VISION_MODEL"),
        "vision_api_key": get("VISION_API_KEY"),
        "vision_max_tokens": _as_int(get("VISION_MAX_TOKENS"), 2000, minimum=1),
        "vision_timeout": _as_float(get("VISION_TIMEOUT"), 180.0),
        "daily_limit": _as_int(get("DAILY_LIMIT"), 30, minimum=0),
        "max_workers": _as_int(get("MAX_WORKERS"), 2, minimum=1),
        "max_upload_mb": _as_int(get("MAX_UPLOAD_MB"), 5, minimum=1),
        "job_mode": get("JOB_MODE") or "thread",
        "lock_wait": _as_float(get("LOCK_WAIT"), 5.0),
    }
    kwargs.update(overrides)
    return Settings(**kwargs)
