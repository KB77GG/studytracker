"""HTTP routes for the trial tool (pages + JSON API)."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from . import access, copytext, review, uploads
from . import essay as essay_lib
from .storage import KINDS, iso, utcnow

bp = Blueprint("iwa", __name__, static_folder="static", template_folder="templates")

PROMPT_LIMIT = 3000
ESSAY_CHAR_LIMIT = 9000
ESSAY_MIN_WORDS = 30
ESSAY_MAX_WORDS = 900
TARGET_BANDS = (5.5, 6.0, 6.5, 7.0, 7.5, 8.0)
ERROR_MESSAGES = {
    "interrupted": "服务重启导致生成中断，请重新生成。",
    "timeout": "模型响应超时，请重新生成。",
    "network": "无法连接模型服务，请稍后重试。",
    "missing_api_key": "服务端未配置模型 Key，请联系管理员。",
    "invalid_output": "模型输出格式不合格，请重新生成。",
    "invalid_json": "模型输出格式不合格，请重新生成。",
    "truncated": "模型输出过长被截断，请重新生成。",
}


def ctx():
    return current_app.extensions["iwa"]


def _json(payload, status=200):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _error(code: str, message: str, status: int):
    return _json({"ok": False, "error": code, "message": message}, status)


def _client_key() -> str:
    # Behind a reverse proxy set IWA_TRUST_PROXY=1 so ProxyFix fills remote_addr.
    return request.remote_addr or "unknown"


def _daily_limit(user: dict) -> int:
    value = user.get("daily_limit")
    return int(value) if value is not None else ctx().settings.daily_limit


def _quota(user: dict) -> dict:
    limit = _daily_limit(user)
    used = ctx().storage.usage_today(user["id"])
    return {"limit": limit, "used": used, "remaining": max(0, limit - used)}


# ---------------------------------------------------------------------------
# Session handling
# ---------------------------------------------------------------------------


@bp.before_app_request
def load_user():
    g.user = None
    uid = session.get("uid")
    if not uid:
        return
    user = ctx().storage.get_user(int(uid))
    if access.user_block_reason(user) or user["session_epoch"] != session.get("epoch"):
        session.clear()
        return
    g.user = user


def _csrf_ok() -> bool:
    expected = session.get("csrf")
    supplied = request.headers.get("X-IWA-CSRF", "")
    return bool(expected) and secrets.compare_digest(expected, supplied)


def require_user(api: bool):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                if api:
                    return _error("login_required", "请先输入试用码登录", 401)
                return redirect(url_for("iwa.login_page", next=request.path))
            if api and request.method not in {"GET", "HEAD"} and not _csrf_ok():
                return _error("csrf", "页面已过期，请刷新后重试", 403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def _draft_key(user: dict | None) -> str:
    """Opaque per-user key for browser drafts: stable for the same user, unguessable
    for others, and does not reveal the user id."""
    if not user:
        return ""
    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(secret, f"iwa-draft:{user['id']}".encode(), hashlib.sha256).hexdigest()[:32]


@bp.app_context_processor
def inject_globals():
    settings = ctx().settings
    return {
        "iwa_user": g.get("user"),
        "iwa_user_key": _draft_key(g.get("user")),
        "iwa_csrf": session.get("csrf", ""),
        "iwa_demo": settings.is_demo,
        "iwa_vision": settings.vision_enabled,
        "iwa_model": settings.llm_model,
        "iwa_max_upload_mb": settings.max_upload_mb,
    }


@bp.after_app_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' blob: data:; style-src 'self'; script-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
    )
    if response.mimetype == "text/html":
        # Pages show essays: never let the browser cache or restore them after logout.
        response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


@bp.get("/healthz")
def healthz():
    app_ctx = ctx()
    # pid/ppid let start.sh confirm the answer comes from the process it just launched
    # (ppid covers a gunicorn worker whose master is the launched process).
    return _json(
        {
            "ok": True,
            "provider": app_ctx.settings.llm_provider,
            "demo": app_ctx.settings.is_demo,
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "instance": app_ctx.lock.instance_id,
        }
    )


@bp.get("/login")
def login_page():
    if g.user is not None:
        return redirect(url_for("iwa.new_page"))
    if not session.get("csrf"):
        session["csrf"] = secrets.token_urlsafe(24)
    return render_template("login.html", page="login")


@bp.get("/")
@require_user(api=False)
def new_page():
    return render_template("new.html", page="new", quota=_quota(g.user), target_bands=TARGET_BANDS)


@bp.get("/history")
@require_user(api=False)
def history_page():
    return render_template("history.html", page="history", quota=_quota(g.user))


@bp.get("/s/<public_id>")
@require_user(api=False)
def submission_page(public_id: str):
    submission = ctx().storage.get_owned_submission(public_id, g.user["id"])
    if not submission:
        return render_template("not_found.html", page="missing"), 404
    return render_template(
        "submission.html", page="submission", public_id=public_id, quota=_quota(g.user)
    )


# ---------------------------------------------------------------------------
# Auth API
# ---------------------------------------------------------------------------


@bp.post("/api/login")
def api_login():
    if not _csrf_ok():
        return _error("csrf", "页面已过期，请刷新后重试", 403)
    key = _client_key()
    limiter = ctx().limiter
    if limiter.blocked(key):
        return _error("too_many_attempts", "尝试次数过多，请 15 分钟后再试", 429)
    data = request.get_json(silent=True) or {}
    code = str(data.get("code") or "")
    user = ctx().storage.get_user_by_code_hash(access.hash_code(code)) if code.strip() else None
    reason = access.user_block_reason(user)
    if reason:
        limiter.fail(key)
        message = {
            "disabled": "该试用码已停用",
            "expired": "该试用码已过期",
        }.get(reason, "试用码不正确")
        return _error(f"login_{reason}", message, 401)
    limiter.reset(key)
    session.clear()
    session.permanent = True
    session["uid"] = user["id"]
    session["epoch"] = user["session_epoch"]
    session["csrf"] = secrets.token_urlsafe(24)
    ctx().storage.update_user(user["id"], last_login_at=iso(utcnow()))
    return _json({"ok": True, "name": user["name"], "csrf": session["csrf"]})


@bp.post("/api/logout")
def api_logout():
    if g.user is not None and not _csrf_ok():
        return _error("csrf", "页面已过期，请刷新后重试", 403)
    session.clear()
    return _json({"ok": True})


@bp.get("/api/me")
@require_user(api=True)
def api_me():
    return _json({"ok": True, "name": g.user["name"], "quota": _quota(g.user)})


# ---------------------------------------------------------------------------
# Submissions API
# ---------------------------------------------------------------------------


def _parse_submission_form() -> tuple[dict | None, dict]:
    form = request.form
    errors: dict[str, str] = {}
    task_type = form.get("task_type", "")
    if task_type not in essay_lib.MIN_WORDS:
        errors["task_type"] = "请选择 Task 1 或 Task 2"
    prompt_text = essay_lib.normalize_newlines(form.get("prompt_text", "")).strip()
    if len(prompt_text) < 10:
        errors["prompt_text"] = "请填写完整题干"
    elif len(prompt_text) > PROMPT_LIMIT:
        errors["prompt_text"] = f"题干不能超过 {PROMPT_LIMIT} 字符"
    essay_text = essay_lib.normalize_newlines(form.get("essay_text", "")).strip()
    words = essay_lib.count_words(essay_text)
    if len(essay_text) > ESSAY_CHAR_LIMIT or words > ESSAY_MAX_WORDS:
        errors["essay_text"] = f"作文不能超过 {ESSAY_MAX_WORDS} 词"
    elif words < ESSAY_MIN_WORDS:
        errors["essay_text"] = f"作文至少需要 {ESSAY_MIN_WORDS} 词才能批改"
    try:
        target_band = float(form.get("target_band") or 7.0)
    except ValueError:
        target_band = -1
    if target_band not in TARGET_BANDS:
        errors["target_band"] = "目标分数无效"
    if errors:
        return None, errors
    return {
        "task_type": task_type,
        "prompt_text": prompt_text,
        "essay_text": essay_text,
        "word_count": words,
        "target_band": target_band,
    }, {}


@bp.post("/api/submissions")
@require_user(api=True)
def api_create_submission():
    app_ctx = ctx()
    parsed, errors = _parse_submission_form()
    if errors:
        return _json({"ok": False, "error": "invalid", "fields": errors}, 422)
    limit = _daily_limit(g.user)
    if app_ctx.storage.usage_today(g.user["id"]) + len(KINDS) > limit:
        return _error("quota_exceeded", f"今日额度不足（每次批改消耗 {len(KINDS)} 次）", 429)

    image_path = image_mime = None
    image_file = request.files.get("image")
    if parsed["task_type"] == "task1" and image_file and image_file.filename:
        try:
            image_path, image_mime = uploads.save_image(
                image_file,
                app_ctx.settings.upload_dir,
                g.user["id"],
                app_ctx.settings.max_upload_mb * 1024 * 1024,
            )
        except uploads.UploadError as exc:
            return _json({"ok": False, "error": exc.code, "fields": {"image": exc.message}}, 422)
        finally:
            image_file.close()

    public_id = secrets.token_urlsafe(9)
    created = app_ctx.storage.create_submission(
        public_id=public_id,
        user_id=g.user["id"],
        essay_sha256=hashlib.sha256(parsed["essay_text"].encode("utf-8")).hexdigest(),
        image_path=image_path,
        image_mime=image_mime,
        image_status="pending" if image_path else "none",
        daily_limit=limit,
        **parsed,
    )
    if created is None:
        uploads.remove(app_ctx.settings.upload_dir, image_path)
        return _error("quota_exceeded", f"今日额度不足（每次批改消耗 {len(KINDS)} 次）", 429)
    app_ctx.jobs.start_submission(
        created["id"],
        [created["generation_ids"][kind] for kind in KINDS],
        needs_image=bool(image_path),
    )
    return _json(
        {
            "ok": True,
            "public_id": public_id,
            "url": url_for("iwa.submission_page", public_id=public_id),
        },
        201,
    )


def _generation_view(generation: dict | None, submission: dict) -> dict | None:
    if not generation:
        return None
    ready = generation["status"] == "ready" and generation.get("result")
    view = {
        "id": generation["id"],
        "status": generation["status"],
        "result": generation.get("result") if generation["status"] == "ready" else None,
        "model": generation.get("model"),
        "prompt_version": generation.get("prompt_version"),
        "created_at": generation["created_at"],
        "finished_at": generation.get("finished_at"),
        "latency_ms": generation.get("latency_ms"),
        # Copy texts are built here so they always carry the page's limits/disclaimers.
        "copy": (
            copytext.copies_for(generation["kind"], generation["result"], generation, submission)
            if ready
            else None
        ),
    }
    if generation["status"] == "failed":
        code = generation.get("error_code") or "failed"
        view["error"] = {
            "code": code,
            "message": ERROR_MESSAGES.get(code)
            or generation.get("error_message")
            or "生成失败，请重新生成。",
        }
    return view


def _with_cross_notes(generations: dict) -> dict:
    """Add the evaluation's view of the original to the rewrite (display only)."""
    evaluation = generations.get("evaluate") or {}
    rewrite = generations.get("rewrite")
    if not (rewrite and rewrite.get("status") == "ready" and rewrite.get("result")):
        return generations
    notes = review.rewrite_cross_notes(
        evaluation.get("result") if evaluation.get("status") == "ready" else None
    )
    if not notes:
        return generations
    result = dict(rewrite["result"])
    result["warnings"] = list(result.get("warnings") or []) + notes
    return {**generations, "rewrite": dict(rewrite, result=result)}


def _submission_view(submission: dict) -> dict:
    generations = _with_cross_notes(ctx().storage.latest_generations(submission["id"]))
    task_type = submission["task_type"]
    return {
        "public_id": submission["public_id"],
        "task_type": task_type,
        "task_label": essay_lib.TASK_LABELS[task_type],
        "prompt_text": submission["prompt_text"],
        "essay_text": submission["essay_text"],
        "word_count": submission["word_count"],
        "minimum_words": essay_lib.MIN_WORDS[task_type],
        "target_band": submission["target_band"],
        "created_at": submission["created_at"],
        "image": (
            {
                "url": url_for("iwa.api_submission_image", public_id=submission["public_id"]),
                "status": submission["image_status"],
                "description": submission.get("image_description") or "",
                # Why the image cannot support TA (only set when it is not usable).
                "unusable_reason": (
                    review.ta_unassessable_reason(submission)
                    if submission["image_status"] in {"failed", "skipped"}
                    else ""
                ),
            }
            if submission.get("image_path")
            else None
        ),
        "generations": {
            kind: _generation_view(generations.get(kind), submission) for kind in KINDS
        },
    }


@bp.get("/api/submissions")
@require_user(api=True)
def api_list_submissions():
    try:
        before = int(request.args.get("before") or 0) or None
    except ValueError:
        before = None
    rows = ctx().storage.list_submissions(g.user["id"], limit=21, before_id=before)
    has_more = len(rows) > 20
    items = []
    for row in rows[:20]:
        gens = row["generations"]
        evaluation = gens.get("evaluate")
        band = band_state = None
        if evaluation and evaluation["status"] == "ready" and evaluation.get("result"):
            band = evaluation["result"].get("overall_band")
            band_state = "scored" if band is not None else "not_assessable"
        items.append(
            {
                "cursor": row["id"],
                "public_id": row["public_id"],
                "url": url_for("iwa.submission_page", public_id=row["public_id"]),
                "task_type": row["task_type"],
                "task_label": essay_lib.TASK_LABELS[row["task_type"]],
                "prompt_excerpt": (
                    row["prompt_text"][:140] + "…"
                    if len(row["prompt_text"]) > 140
                    else row["prompt_text"]
                ),
                "word_count": row["word_count"],
                "target_band": row["target_band"],
                "has_image": bool(row["has_image"]),
                "created_at": row["created_at"],
                "overall_band": band,
                "overall_state": band_state,
                "statuses": {kind: (gens.get(kind) or {}).get("status") for kind in KINDS},
            }
        )
    return _json({"ok": True, "items": items, "has_more": has_more})


@bp.get("/api/submissions/<public_id>")
@require_user(api=True)
def api_get_submission(public_id: str):
    submission = ctx().storage.get_owned_submission(public_id, g.user["id"])
    if not submission:
        return _error("not_found", "记录不存在", 404)
    return _json({"ok": True, "submission": _submission_view(submission), "quota": _quota(g.user)})


@bp.post("/api/submissions/<public_id>/generations/<kind>")
@require_user(api=True)
def api_regenerate(public_id: str, kind: str):
    if kind not in KINDS:
        return _error("not_found", "未知生成类型", 404)
    app_ctx = ctx()
    submission = app_ctx.storage.get_owned_submission(public_id, g.user["id"])
    if not submission:
        return _error("not_found", "记录不存在", 404)
    if submission["image_status"] == "pending":
        return _error("image_pending", "题图还在识别中，请稍候", 409)
    generation_id, error = app_ctx.storage.queue_regeneration(
        submission["id"], kind, g.user["id"], _daily_limit(g.user)
    )
    if error == "already_running":
        return _error(error, "正在生成中，请稍候", 409)
    if error == "quota_exceeded":
        return _error(error, "今日额度已用完", 429)
    app_ctx.jobs.start_generation(generation_id)
    return _json({"ok": True, "generation_id": generation_id}, 202)


@bp.delete("/api/submissions/<public_id>")
@require_user(api=True)
def api_delete_submission(public_id: str):
    app_ctx = ctx()
    submission = app_ctx.storage.get_owned_submission(public_id, g.user["id"])
    if not submission:
        return _error("not_found", "记录不存在", 404)
    app_ctx.storage.delete_submission(submission["id"])
    uploads.remove(app_ctx.settings.upload_dir, submission.get("image_path"))
    return _json({"ok": True})


@bp.get("/api/submissions/<public_id>/image")
@require_user(api=True)
def api_submission_image(public_id: str):
    submission = ctx().storage.get_owned_submission(public_id, g.user["id"])
    if not submission or not submission.get("image_path"):
        return _error("not_found", "题图不存在", 404)
    path = uploads.resolve(ctx().settings.upload_dir, submission["image_path"])
    if path is None:
        return _error("not_found", "题图不存在", 404)
    response = send_file(path, mimetype=submission["image_mime"], max_age=0)
    response.headers["Cache-Control"] = "private, no-store"
    return response
