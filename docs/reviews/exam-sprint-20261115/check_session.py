"""Read a known completed practice, reporting schema only, without exposing session data."""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from services.ninefen_session import NinefenSession, _private_write  # noqa: E402


def shape(value, depth=0):
    if depth > 3:
        return type(value).__name__
    if isinstance(value, dict):
        return {k: shape(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return {"count": len(value), "first_shape": shape(value[0], depth + 1) if value else None}
    return type(value).__name__


if __name__ == "__main__":
    session = NinefenSession(ROOT / "instance/exam_sprint/private/session.json")
    request = urllib.request.Request(
        "https://www.9fnnn.com/api/practice/v1/unit-status?unitIds=2102715008296194050",
        headers={"token": session._token, "Accept": "application/json"},
    )
    try:
        with session._opener.open(request, timeout=20) as response:
            result = json.loads(response.read(8 * 1024 * 1024))
    except urllib.error.HTTPError as exc:
        print({"http_status": exc.code})
        raise SystemExit(2) from None
    except Exception as exc:
        reason = getattr(exc, "reason", None)
        print(
            {
                "transport_error_type": type(exc).__name__,
                "reason_type": type(reason).__name__,
                "errno": getattr(reason, "errno", None),
                "reason": str(reason)[:200],
            }
        )
        raise SystemExit(2) from None
    print(shape(result))
    print({"code": result.get("code")})
    _private_write(ROOT / "instance/exam_sprint/private/session-check.json", result)
