"""Command line entry: ``python -m tools.ielts_writing_ai <command>``.

Commands:
  check                     print the effective (non-secret) configuration
  init                      create the data dir, database and secret key
  serve [--host --port]     run the trial server in the foreground
  user-add --name NAME [--days N] [--daily-limit N]
  user-list
  user-disable ID | user-enable ID
  user-reset-code ID        issue a new code and sign out existing sessions
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta

from . import access
from .config import ConfigError, load_settings
from .storage import Storage, iso, utcnow


def _storage(settings) -> Storage:
    settings.validate()
    settings.ensure_dirs()
    storage = Storage(settings.db_path)
    storage.init_schema()
    return storage


def cmd_check(settings, _args) -> int:
    settings.validate()
    print(json.dumps(settings.public_summary(), ensure_ascii=False, indent=2))
    return 0


def cmd_init(settings, _args) -> int:
    _storage(settings)
    settings.resolve_secret_key()
    print(f"已初始化：{settings.db_path}")
    return 0


def cmd_serve(settings, args) -> int:
    from . import create_app

    app = create_app(settings)
    host = args.host or settings.host
    port = args.port or settings.port
    if port in {5000, 5002}:
        raise ConfigError("端口 5000/5002 属于主应用，试用工具请使用其他端口")
    print(f"IELTS 写作 AI 试用工具：http://{host}:{port}{settings.url_prefix or '/'}", flush=True)
    app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)
    return 0


def cmd_user_add(settings, args) -> int:
    storage = _storage(settings)
    code = access.generate_code()
    expires = utcnow() + timedelta(days=args.days) if args.days else None
    user_id = storage.create_user(
        name=args.name.strip(),
        code_hash=access.hash_code(code),
        code_hint=access.code_hint(code),
        daily_limit=args.daily_limit,
        expires_at=expires,
    )
    print(f"已创建试用用户 #{user_id}（{args.name.strip()}）")
    print(f"试用码（只显示这一次，请妥善转交）：{code}")
    if expires:
        print(f"有效期至（UTC）：{iso(expires)}")
    return 0


def cmd_user_list(settings, _args) -> int:
    storage = _storage(settings)
    users = storage.list_users()
    if not users:
        print("暂无试用用户。用 user-add --name 姓名 创建。")
        return 0
    for user in users:
        state = access.user_block_reason(user) or "active"
        limit = (
            user["daily_limit"]
            if user["daily_limit"] is not None
            else f"默认{settings.daily_limit}"
        )
        print(
            f"#{user['id']:<4} {user['name']:<12} 状态={state:<8} 码尾={user['code_hint']}"
            f" 每日额度={limit} 今日已用={storage.usage_today(user['id'])}"
            f" 记录数={user['submissions']} 到期={user['expires_at'] or '-'}"
            f" 最近登录={user['last_login_at'] or '-'}"
        )
    return 0


def cmd_user_disable(settings, args) -> int:
    ok = _storage(settings).update_user(args.id, disabled_at=iso(utcnow()), bump_epoch=True)
    print("已停用并登出" if ok else "用户不存在")
    return 0 if ok else 1


def cmd_user_enable(settings, args) -> int:
    ok = _storage(settings).update_user(args.id, disabled_at=None)
    print("已启用" if ok else "用户不存在")
    return 0 if ok else 1


def cmd_user_reset_code(settings, args) -> int:
    code = access.generate_code()
    ok = _storage(settings).update_user(
        args.id,
        code_hash=access.hash_code(code),
        code_hint=access.code_hint(code),
        bump_epoch=True,
    )
    if not ok:
        print("用户不存在")
        return 1
    print(f"新试用码（只显示这一次）：{code}；旧码和已登录会话均已失效。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tools.ielts_writing_ai")
    parser.add_argument("--env-file", help="指定 .env 文件（默认 tools/ielts_writing_ai/.env）")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("init").set_defaults(func=cmd_init)
    serve = sub.add_parser("serve")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.set_defaults(func=cmd_serve)
    add = sub.add_parser("user-add")
    add.add_argument("--name", required=True)
    add.add_argument("--days", type=int, default=0, help="有效天数，0 表示不过期")
    add.add_argument("--daily-limit", type=int, default=None, help="每日生成次数上限")
    add.set_defaults(func=cmd_user_add)
    sub.add_parser("user-list").set_defaults(func=cmd_user_list)
    for name, func in (
        ("user-disable", cmd_user_disable),
        ("user-enable", cmd_user_enable),
        ("user-reset-code", cmd_user_reset_code),
    ):
        p = sub.add_parser(name)
        p.add_argument("id", type=int)
        p.set_defaults(func=func)
    return parser


def main(argv: list[str] | None = None) -> int:
    # Chinese messages must never crash the CLI on a non-UTF-8 terminal/locale.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    args = build_parser().parse_args(argv)
    try:
        settings = load_settings(env_file=args.env_file)
        return args.func(settings, args)
    except ConfigError as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
