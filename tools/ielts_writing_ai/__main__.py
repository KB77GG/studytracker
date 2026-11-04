"""Command line entry: ``python -m tools.ielts_writing_ai <command>``.

Commands:
  check                     print the effective (non-secret) configuration
  init                      create the data dir, database and secret key
  serve [--host --port]     run the trial server in the foreground
  user-add --name NAME [--days N] [--daily-limit N]
  user-list
  user-disable ID | user-enable ID
  user-reset-code ID        issue a new code and sign out existing sessions
  realcheck [--samples builtin|FILE.jsonl] [--confirm-paid] ...
                            small-sample check of the configured model (see README)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import timedelta
from pathlib import Path

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


def cmd_realcheck(settings, args) -> int:
    from . import realcheck

    if args.evaluate_thinking is not None:
        settings.evaluate_thinking = args.evaluate_thinking
    settings.validate()
    kinds = tuple(k.strip() for k in args.kinds.split(",") if k.strip())
    unknown = [k for k in kinds if k not in ("evaluate", "refine", "rewrite")]
    if unknown or not kinds:
        print(f"--kinds 只能是 evaluate,refine,rewrite 的组合：{unknown}", file=sys.stderr)
        return 2
    try:
        realcheck.validate_max_calls(args.max_calls)
        items = realcheck.load_samples(args.samples, args.limit)
    except realcheck.RealCheckError as exc:
        print(f"验证参数错误：{exc}", file=sys.stderr)
        return 2
    vision_needed = args.with_vision and any(i.get("image") for i in items)
    worst = len(items) * len(kinds) * 2 + (len(items) if vision_needed else 0)
    print(
        f"模型：{settings.llm_provider} / {settings.llm_model}（Key 已配置："
        f"{'是' if settings.llm_api_key else '否'}）；样本 {len(items)} 篇；"
        f"最多 {min(worst, args.max_calls)} 次调用（上限 {args.max_calls}）；评价思考模式："
        f"{settings.evaluate_thinking}"
        + (
            f"（输出上限 {settings.evaluate_thinking_max_tokens}，超时 "
            f"{settings.evaluate_thinking_timeout:g} 秒）"
            if settings.evaluate_thinking != "off"
            else ""
        )
    )
    if not settings.is_demo and not args.confirm_paid:
        print(
            "这会调用付费模型，并把样本作文发送给模型服务商。确认后请加 --confirm-paid 重新运行。",
            file=sys.stderr,
        )
        return 2
    if settings.vision_enabled and not args.with_vision:
        settings.vision_provider = "none"  # do not call the vision model unless asked
    run_data = realcheck.run(
        settings,
        items,
        kinds=kinds,
        max_calls=args.max_calls,
        target_band=args.target_band,
    )
    report = realcheck.build_report(run_data, price_in=args.price_in, price_out=args.price_out)
    out_dir = (
        Path(args.out)
        if args.out
        else (settings.data_dir / "realcheck" / time.strftime("%Y%m%d-%H%M%S"))
    )
    path = realcheck.write_report(run_data, report, out_dir)
    print(f"报告：{path}")
    if report["aborted"]:
        print(f"已中止：{report['aborted']['message']}", file=sys.stderr)
        return 3
    return 0


def cmd_realcheck_compare(_settings, args) -> int:
    from . import realcheck_compare

    try:
        cmp = realcheck_compare.compare(
            args.a,
            args.b,
            price_in=args.price_in,
            price_out=args.price_out,
            allow_model_change=args.allow_model_change,
        )
    except realcheck_compare.CompareError as exc:
        print(f"不能对照：{exc}", file=sys.stderr)
        return 2
    out_dir = Path(args.out) if args.out else Path(args.b) / "compare"
    path = realcheck_compare.write(cmp, out_dir)
    for warning in cmp["warnings"]:
        print(f"注意：{warning}", file=sys.stderr)
    print(f"对照报告：{path}（人工复核表：{path.parent / 'manual_review.md'}）")
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
    rc = sub.add_parser("realcheck", help="用配置的模型跑小样本验证")
    rc.add_argument("--samples", default="builtin", help="builtin 或 JSONL 文件路径")
    rc.add_argument("--kinds", default="evaluate,refine,rewrite")
    rc.add_argument("--limit", type=int, default=None, help="只跑前 N 篇")
    rc.add_argument("--max-calls", type=int, default=50, help="模型调用次数上限")
    rc.add_argument("--target-band", type=float, default=7.0)
    rc.add_argument("--with-vision", action="store_true", help="对带题图的样本调用识图模型")
    rc.add_argument("--price-in", type=float, default=None, help="输入单价（每百万 token）")
    rc.add_argument("--price-out", type=float, default=None, help="输出单价（每百万 token）")
    rc.add_argument("--out", default=None, help="报告目录（默认数据目录下 realcheck/时间戳）")
    rc.add_argument("--confirm-paid", action="store_true", help="确认调用付费模型")
    cmp = sub.add_parser(
        "realcheck-compare", help="对照两次 realcheck（同一提示词与作文，只改评价思考模式）"
    )
    cmp.add_argument("a", help="第一次运行的报告目录（例如思考关闭）")
    cmp.add_argument("b", help="第二次运行的报告目录（例如思考 high）")
    cmp.add_argument("--out", default=None, help="输出目录（默认 B 目录下的 compare/）")
    cmp.add_argument("--price-in", type=float, default=None, help="输入单价（每百万 token）")
    cmp.add_argument("--price-out", type=float, default=None, help="输出单价（每百万 token）")
    cmp.add_argument(
        "--allow-model-change",
        action="store_true",
        help="对照两个不同的模型（提示词和实际输入仍须相同）",
    )
    cmp.set_defaults(func=cmd_realcheck_compare)
    rc.add_argument(
        "--evaluate-thinking",
        choices=["off", "high", "max"],
        default=None,
        help="本次验证中原稿评价的思考模式（默认沿用 IWA_EVALUATE_THINKING；精修/改写不受影响）",
    )
    rc.set_defaults(func=cmd_realcheck)
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
