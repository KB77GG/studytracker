"""Standalone IELTS writing AI trial tool.

Independent of the main StudyTracker app: it never imports ``app``, ``models``,
``config``, ``api`` or ``services`` from the repository root, and keeps its own
database, upload directory, configuration and session cookie.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from flask import Flask, jsonify

from .access import LoginLimiter
from .config import Settings, load_settings
from .instance import InstanceLock
from .jobs import JobRunner
from .llm import build_client
from .review import Generator
from .storage import Storage

__all__ = ["create_app", "load_settings"]


@dataclass
class ToolContext:
    settings: Settings
    storage: Storage
    generator: Generator
    jobs: JobRunner
    limiter: LoginLimiter
    lock: InstanceLock

    def close(self) -> None:
        """Stop background work and release the instance lock (tests, shutdown)."""
        self.jobs.shutdown()
        self.lock.release()


def create_app(settings: Settings | None = None, *, client=None, vision_client=None) -> Flask:
    settings = settings or load_settings()
    settings.validate()
    settings.ensure_dirs()

    # Take the single-instance lock BEFORE touching task state: a duplicate start must
    # fail without marking the running instance's queued/running work as interrupted.
    lock = InstanceLock(settings.db_path)
    lock.acquire(wait_seconds=settings.lock_wait)
    try:
        storage = Storage(settings.db_path)
        storage.init_schema()
        interrupted = storage.fail_interrupted()
    except Exception:
        lock.release()
        raise

    app = Flask(__name__, static_folder=None)
    app.config.update(
        SECRET_KEY=settings.resolve_secret_key(),
        SESSION_COOKIE_NAME="iwa_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.cookie_secure,
        SESSION_COOKIE_PATH=settings.url_prefix or "/",
        PERMANENT_SESSION_LIFETIME=timedelta(days=settings.session_days),
        MAX_CONTENT_LENGTH=(settings.max_upload_mb + 1) * 1024 * 1024,
        JSON_AS_ASCII=False,
    )
    app.json.ensure_ascii = False
    if settings.trust_proxy:
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    generator = Generator(
        storage,
        settings,
        client or build_client(settings),
        vision_client if vision_client is not None else build_client(settings, vision=True),
    )
    jobs = JobRunner(generator, mode=settings.job_mode, max_workers=settings.max_workers)
    app.extensions["iwa"] = ToolContext(settings, storage, generator, jobs, LoginLimiter(), lock)

    from .web import bp

    app.register_blueprint(bp, url_prefix=settings.url_prefix or None)

    @app.errorhandler(413)
    def too_large(_error):
        return (
            jsonify({"ok": False, "error": "too_large", "message": "上传内容过大"}),
            413,
        )

    logging.getLogger("iwa").setLevel(logging.INFO)
    if interrupted:
        app.logger.warning("marked %s interrupted generations as failed", interrupted)
    return app
