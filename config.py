import os

# 获取当前文件所在的文件夹路径
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def _load_env_file(path: str) -> None:
    """Load environment variables from a .env file if present."""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'").strip('"')
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # Fail silently to avoid blocking app startup
        pass

_load_env_file(os.path.join(BASE_DIR, ".env"))

class Config:
    # 用于 Flask 的安全密钥（后面我们可以改成更安全的随机值）
    SECRET_KEY = "dev-key-change-later"

    # 数据库路径：在当前项目文件夹下自动生成 app.db
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "app.db")

    # 关闭不必要的警告
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 证据文件保存目录
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

    # WeChat credentials (from environment)
    WECHAT_APPID = os.environ.get("WECHAT_APPID") or os.environ.get("WECHAT_APP_ID") or "wx75cdd8fc1ca68c69"
    WECHAT_SECRET = os.environ.get("WECHAT_SECRET") or os.environ.get("WECHAT_APP_SECRET") or "d50cb0a992515238c9807950fed29bf1"
    WECHAT_TASK_TEMPLATE_ID = os.environ.get("WECHAT_TASK_TEMPLATE_ID", "AehPa5pMUTnQqXgq-q-wxTAMZyVU-qdkxaO9rbpo-QI")
    WECHAT_FEEDBACK_TEMPLATE_ID = os.environ.get(
        "WECHAT_FEEDBACK_TEMPLATE_ID",
        "jh8kXPp8x2qnzE3g894HlDzdJ5j7ItGHVG0Qx6oD7PA",
    )

    # Scheduler system integration
    SCHEDULER_BASE_URL = os.environ.get("SCHEDULER_BASE_URL", "http://aliyun-server:5000")
    SCHEDULER_PUSH_TOKEN = os.environ.get("SCHEDULER_PUSH_TOKEN")

    # DeepSeek API (IELTS speaking evaluation)
    DEEPSEEK_API_BASE = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
    DEEPSEEK_CHAT_URL = os.environ.get("DEEPSEEK_CHAT_URL")
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
    DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_TIMEOUT = os.environ.get("DEEPSEEK_TIMEOUT", "12")
    DEEPSEEK_RETRIES = os.environ.get("DEEPSEEK_RETRIES", "0")

    # Aliyun ASR (DashScope Model Studio)
    ALIYUN_API_KEY = os.environ.get("ALIYUN_API_KEY")
    ALIYUN_ASR_MODEL = os.environ.get("ALIYUN_ASR_MODEL", "paraformer-v2")
    ALIYUN_ASR_REGION = os.environ.get("ALIYUN_ASR_REGION", "cn-beijing")
    ALIYUN_ASR_HOST = os.environ.get("ALIYUN_ASR_HOST", "")
    ALIYUN_ASR_POLL_INTERVAL = os.environ.get("ALIYUN_ASR_POLL_INTERVAL", "1.0")
    ALIYUN_ASR_MAX_WAIT = os.environ.get("ALIYUN_ASR_MAX_WAIT", "45")
    ALIYUN_TTS_MODEL = os.environ.get("ALIYUN_TTS_MODEL", "qwen3-tts-flash")
    ALIYUN_TTS_VOICE = os.environ.get("ALIYUN_TTS_VOICE", "Cherry")
    ALIYUN_TTS_LANGUAGE = os.environ.get("ALIYUN_TTS_LANGUAGE", "English")
    ALIYUN_AICONTENT_AK_ID = os.environ.get("ALIYUN_AICONTENT_AK_ID")
    ALIYUN_AICONTENT_AK_SECRET = os.environ.get("ALIYUN_AICONTENT_AK_SECRET")
    ALIYUN_ORAL_APP_KEY = os.environ.get("ALIYUN_ORAL_APP_KEY")
    ALIYUN_ORAL_APP_SECRET = os.environ.get("ALIYUN_ORAL_APP_SECRET")
    ALIYUN_ORAL_AUTH_ENDPOINTS = os.environ.get(
        "ALIYUN_ORAL_AUTH_ENDPOINTS",
        "https://api.cloud.ssapi.cn/auth/authorize,https://gate-01.api.cloud.ssapi.cn/auth/authorize,https://gate-02.api.cloud.ssapi.cn/auth/authorize,https://gate-03.api.cloud.ssapi.cn/auth/authorize",
    )
    ALIYUN_ORAL_AUTH_TIMEOUT = os.environ.get("ALIYUN_ORAL_AUTH_TIMEOUT", "10")
    ALIYUN_ORAL_WARRANT_AVAILABLE = os.environ.get("ALIYUN_ORAL_WARRANT_AVAILABLE", "7200")
    ALIYUN_ORAL_TASK_SUBMIT_URL = os.environ.get(
        "ALIYUN_ORAL_TASK_SUBMIT_URL",
        "https://aiservice.ssapi.cn/api/v1/oralEvaluation/classTaskSubmit",
    )
    ALIYUN_ORAL_TASK_QUERY_URL = os.environ.get(
        "ALIYUN_ORAL_TASK_QUERY_URL",
        "https://aiservice.ssapi.cn/api/v1/oralEvaluation/classTaskQuery",
    )
    ALIYUN_ORAL_TASK_TIMEOUT = os.environ.get("ALIYUN_ORAL_TASK_TIMEOUT", "12")
    ALIYUN_ORAL_TASK_MAX_WAIT = os.environ.get("ALIYUN_ORAL_TASK_MAX_WAIT", "20")
    ALIYUN_ORAL_TASK_POLL_INTERVAL = os.environ.get("ALIYUN_ORAL_TASK_POLL_INTERVAL", "1.0")

    # Tencent SOE (spoken pronunciation engine)
    TENCENT_SOE_ENABLED = os.environ.get("TENCENT_SOE_ENABLED", "0")
    TENCENT_SECRET_ID = os.environ.get("TENCENT_SECRET_ID")
    TENCENT_SECRET_KEY = os.environ.get("TENCENT_SECRET_KEY")
    TENCENT_SOE_ENDPOINT = os.environ.get("TENCENT_SOE_ENDPOINT", "soe.tencentcloudapi.com")
    TENCENT_SOE_VERSION = os.environ.get("TENCENT_SOE_VERSION", "2018-07-24")
    TENCENT_SOE_REGION = os.environ.get("TENCENT_SOE_REGION", "")
    TENCENT_SOE_APP_ID = os.environ.get("TENCENT_SOE_APP_ID", "")
    TENCENT_SOE_SCORE_COEFF = os.environ.get("TENCENT_SOE_SCORE_COEFF", "4.0")
    TENCENT_SOE_TIMEOUT = os.environ.get("TENCENT_SOE_TIMEOUT", "20")
    TENCENT_SOE_MAX_AUDIO_BYTES = os.environ.get("TENCENT_SOE_MAX_AUDIO_BYTES", "980000")
