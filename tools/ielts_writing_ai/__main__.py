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
    from . import ledger as ledger_lib
    from . import realcheck

    if args.evaluate_thinking is not None:
        settings.evaluate_thinking = args.evaluate_thinking
    settings.validate()
    kinds = tuple(k.strip() for k in args.kinds.split(",") if k.strip())
    unknown = [k for k in kinds if k not in ("evaluate", "refine", "rewrite")]
    if unknown or not kinds:
        print(f"--kinds 只能是 evaluate,refine,rewrite 的组合：{unknown}", file=sys.stderr)
        return 2
    if args.images_only:
        # Read each chart once before any text model runs (review 2026-11-11): both
        # models then get the same frozen reading via --image-descriptions.
        if not args.with_vision or args.image_descriptions or args.repeat != 1:
            print(
                "--images-only 需要 --with-vision，且不能和 --image-descriptions、--repeat 同用",
                file=sys.stderr,
            )
            return 2
        kinds = ()
    if args.max_failure_rate is not None and not 0 <= args.max_failure_rate < 1:
        print("--max-failure-rate 必须在 0 到 1 之间（不含 1）", file=sys.stderr)
        return 2
    try:
        realcheck.validate_max_calls(args.max_calls)
        items = realcheck.load_samples(args.samples, args.limit)
        if args.images_only:
            items = [i for i in items if i["task_type"] == "task1" and i.get("image")]
            if not items:
                raise realcheck.RealCheckError("样本里没有带题图的 Task 1")
        items = realcheck.expand_repeats(items, args.repeat)
        if args.image_descriptions:
            reused = realcheck.apply_image_descriptions(
                items, args.image_descriptions, require_ready=args.require_ready_images
            )
            print(f"沿用已有的题图识别结果：{reused} 个样本（不再调用识图模型）")
        ledger = None
        if args.ledger:
            if args.ledger_text_cap is None:
                raise realcheck.RealCheckError("用 --ledger 时必须给 --ledger-text-cap")
            ledger = ledger_lib.Ledger(
                args.ledger,
                text_cap=args.ledger_text_cap,
                vision_cap=args.ledger_vision_cap,
                run=args.ledger_run or Path(args.out or "realcheck").name,
                code_sha256=realcheck.code_fingerprint(),
                prompt_version=realcheck.review.prompts.PROMPT_VERSION,
            )
            used = ledger.check()
            vision = (
                f"识图已预留 {used['vision']['reserved']} / {args.ledger_vision_cap} 次"
                if args.ledger_vision_cap
                else "这次运行不允许识图"
            )
            print(
                f"批次账本 {args.ledger}：文字已预留 {used['text']['reserved']} / "
                f"{args.ledger_text_cap} 次，{vision}（已预留中结果未知的 "
                f"{used['text']['unknown'] + used['vision']['unknown']} 次）"
            )
    except realcheck.RealCheckError as exc:
        print(f"验证参数错误：{exc}", file=sys.stderr)
        return 2
    except ledger_lib.LedgerError as exc:  # unreadable ledger, different code, bad cap
        print(f"批次账本错误：{exc.message}", file=sys.stderr)
        return 2
    to_read = {
        i.get("repeat_of") or i["id"]
        for i in items
        if i.get("image") and not i.get("image_description")
    }
    worst = len(items) * len(kinds) * 2 + (len(to_read) if args.with_vision else 0)
    print(
        f"模型：{settings.llm_provider} / {settings.llm_model}"
        + (
            f"（评价用 {settings.evaluate_model}）"
            if settings.evaluate_model and settings.evaluate_model != settings.llm_model
            else ""
        )
        + "（Key 已配置："
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
    try:
        run_data = realcheck.run(
            settings,
            items,
            kinds=kinds,
            max_calls=args.max_calls,
            target_band=args.target_band,
            ledger=ledger,
        )
    except realcheck.RealCheckError as exc:
        print(f"验证参数错误：{exc}", file=sys.stderr)
        return 2
    report = realcheck.build_report(
        run_data,
        price_in=args.price_in,
        price_out=args.price_out,
        price_cached_in=args.price_cached_in,
    )
    out_dir = (
        Path(args.out)
        if args.out
        else (settings.data_dir / "realcheck" / time.strftime("%Y%m%d-%H%M%S"))
    )
    path = realcheck.write_report(run_data, report, out_dir)
    print(f"报告：{path}")
    code = _realcheck_outcome(realcheck, args, items, run_data, report)
    # How the run ended, written last: a batch whose parent died while this run went
    # on can accept the finished run instead of repeating it (review 76276d9).
    (out_dir / "exit_status.json").write_text(
        json.dumps({"code": code, "time": time.strftime("%Y-%m-%dT%H:%M:%S%z")}) + "\n",
        encoding="utf-8",
    )
    return code


def _realcheck_outcome(realcheck, args, items, run_data, report) -> int:
    if report["aborted"]:
        print(f"已中止：{report['aborted']['message']}", file=sys.stderr)
        return 3
    if args.images_only:
        bad = [
            i["id"]
            for i in items
            if (run_data["image_outcomes"].get(i["id"]) or {}).get("status") != "ready"
        ]
        if bad:
            print("这些题图没有得到可用的识别结果：" + "、".join(bad), file=sys.stderr)
            return 5
        return 0
    if args.max_failure_rate is not None:
        failed = realcheck.final_failures(run_data, len(items))
        if failed > args.max_failure_rate * len(items):
            print(
                f"最终失败 {failed} / {len(items)} 篇，超过 {args.max_failure_rate:.0%}，停止",
                file=sys.stderr,
            )
            return 4
    return 0


def cmd_realcheck_batch(_settings, args) -> int:
    from . import batch

    return batch.run_stage(args)


def cmd_realcheck_summary(_settings, args) -> int:
    from . import batch

    print(f"汇总：{batch.write_summary(Path(args.out).expanduser())}")
    return 0


def cmd_realcheck_tally(_settings, args) -> int:
    from . import blindtally

    result = blindtally.run(Path(args.folder).expanduser(), all_repeats=args.all_repeats)
    for side in ("a", "b"):
        counts = result["models"][side]
        shown = "，".join(f"{blindtally.LABELS[k]} {counts[k]}" for k in blindtally.LABELS)
        print(
            f"{side.upper()}（{result['conditions'][side]['model']}）：{shown}；"
            f"已判断 {counts['filled']}，未填写 {counts['blank']}，无法识别 {counts['unrecognized']}"
        )
    if not result["complete"]:
        print("盲评不完整，以下格子需要补填或改正：", file=sys.stderr)
        for problem in result["problems"][:30]:
            print(f"  {problem}", file=sys.stderr)
        return 1
    return 0


def cmd_realcheck_compare(_settings, args) -> int:
    from . import realcheck_compare

    try:
        cmp = realcheck_compare.compare(
            args.a,
            args.b,
            price_in=args.price_in,
            price_out=args.price_out,
            prices_a={
                "in": args.price_in_a,
                "cached_in": args.price_cached_in_a,
                "out": args.price_out_a,
            },
            prices_b={
                "in": args.price_in_b,
                "cached_in": args.price_cached_in_b,
                "out": args.price_out_b,
            },
            allow_model_change=args.allow_model_change,
        )
    except realcheck_compare.CompareError as exc:
        print(f"不能对照：{exc}", file=sys.stderr)
        return 2
    out_dir = Path(args.out) if args.out else Path(args.b) / "compare"
    try:
        path = realcheck_compare.write(cmp, out_dir, blind_seed=args.blind)
    except realcheck_compare.CompareError as exc:
        print(f"不能写入：{exc}", file=sys.stderr)
        return 2
    for warning in cmp["warnings"]:
        print(f"注意：{warning}", file=sys.stderr)
    print(f"对照报告：{path}（人工复核表：{path.parent / 'manual_review.md'}）")
    if args.blind is not None:
        print(
            f"盲评表：{path.parent / 'blind_review.md'}（甲 / 乙对应关系在 blind_key.json，"
            "填完判断再打开）"
        )
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
    rc.add_argument("--repeat", type=int, default=1, help="每篇作文运行几次（看波动）")
    rc.add_argument(
        "--images-only",
        action="store_true",
        help="只识别题图（每张一次，结果含失败写入 image_descriptions.json），不调用文字模型",
    )
    rc.add_argument(
        "--require-ready-images",
        action="store_true",
        help="与 --image-descriptions 同用：每篇带图的 Task 1 都必须有可用的识别结果",
    )
    rc.add_argument("--ledger", default=None, help="批次账本（JSONL）：每次请求前持久预留")
    rc.add_argument("--ledger-text-cap", type=int, default=None, help="账本的文字请求总上限")
    rc.add_argument("--ledger-vision-cap", type=int, default=0, help="账本的识图请求总上限")
    rc.add_argument("--ledger-run", default=None, help="账本里这次运行的名字")
    rc.add_argument(
        "--max-failure-rate",
        type=float,
        default=None,
        help="最终失败篇数占计划篇数超过这个比例时，以退出码 4 结束",
    )
    rc.add_argument(
        "--image-descriptions",
        default=None,
        help="沿用之前一次运行保存的题图识别结果（image_descriptions.json），两次运行看同一份结果",
    )
    rc.add_argument("--price-in", type=float, default=None, help="输入单价（每百万 token）")
    rc.add_argument("--price-out", type=float, default=None, help="输出单价（每百万 token）")
    rc.add_argument(
        "--price-cached-in",
        type=float,
        default=None,
        help="缓存命中的输入单价（每百万 token）；服务商报告命中量时分开计价",
    )
    rc.add_argument("--out", default=None, help="报告目录（默认数据目录下 realcheck/时间戳）")
    rc.add_argument("--confirm-paid", action="store_true", help="确认调用付费模型")
    cmp = sub.add_parser(
        "realcheck-compare", help="对照两次 realcheck（同一提示词与作文，只改评价思考模式）"
    )
    cmp.add_argument("a", help="第一次运行的报告目录（例如思考关闭）")
    cmp.add_argument("b", help="第二次运行的报告目录（例如思考 high）")
    cmp.add_argument("--out", default=None, help="输出目录（默认 B 目录下的 compare/）")
    cmp.add_argument(
        "--blind",
        type=int,
        default=None,
        metavar="SEED",
        help="另外生成盲评表：两次运行以甲 / 乙出现，每篇随机排序，不显示模型和设置",
    )
    batch_p = sub.add_parser(
        "realcheck-batch",
        help="Flash / Pro 对照批次：持久账本、批次锁、识图先行、失败过半停止、可续跑",
    )
    batch_p.add_argument("--stage", choices=("main", "vision"), required=True)
    batch_p.add_argument("--data", default="~/iwa-calibration", help="数据文件目录")
    batch_p.add_argument("--out", default="~/iwa-compare", help="结果目录")
    batch_p.add_argument("--cap", type=int, default=None, help="用户授权的本阶段文字请求上限")
    batch_p.add_argument(
        "--price",
        action="append",
        help="单价（元 / 百万 token）：flash=输入,缓存命中输入,输出；pro 同样，各给一次",
    )
    batch_p.add_argument("--dry", action="store_true", help="演示模型彩排，不调用付费服务")
    batch_p.set_defaults(func=cmd_realcheck_batch)
    summary_p = sub.add_parser("realcheck-summary", help="重新生成对照批次的数字汇总")
    summary_p.add_argument("--out", default="~/iwa-compare")
    summary_p.set_defaults(func=cmd_realcheck_summary)
    tally_p = sub.add_parser("realcheck-tally", help="统计填好的盲评表")
    tally_p.add_argument("folder", help="compare-<组> 目录")
    tally_p.add_argument("--all-repeats", action="store_true", help="重复运行也计入")
    tally_p.set_defaults(func=cmd_realcheck_tally)
    cmp.add_argument("--price-in", type=float, default=None, help="输入单价（每百万 token）")
    cmp.add_argument("--price-out", type=float, default=None, help="输出单价（每百万 token）")
    for side in ("a", "b"):
        for name, text in (
            ("price-in", "输入单价"),
            ("price-cached-in", "缓存命中的输入单价"),
            ("price-out", "输出单价"),
        ):
            cmp.add_argument(
                f"--{name}-{side}",
                type=float,
                default=None,
                help=f"只用于 {side.upper()} 的{text}（每百万 token）；比较两个模型时用",
            )
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
