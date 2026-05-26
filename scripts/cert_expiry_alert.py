#!/usr/bin/env python3
"""Send an email alert when a TLS certificate is close to expiry.

The script is intentionally standalone and only uses the Python standard
library. Configuration is read from /root/apps/studytracker/.env.alerts by
default, with environment variables taking precedence.
"""

import argparse
import datetime as dt
from email.message import EmailMessage
import os
from pathlib import Path
import smtplib
import socket
import ssl
import sys


DEFAULT_ENV_FILE = "/root/apps/studytracker/.env.alerts"
DEFAULT_STATE_FILE = "/var/lib/cert_expiry_alert.state"


def load_env(path: str) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def certificate_expiry(domain: str, port: int) -> tuple[int, dt.datetime]:
    context = ssl.create_default_context()
    with socket.create_connection((domain, port), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=domain) as wrapped:
            cert = wrapped.getpeercert()

    expiry = dt.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
    now = dt.datetime.utcnow()
    return (expiry - now).days, expiry


def should_send(state_file: str, min_hours_between_alerts: int) -> bool:
    path = Path(state_file)
    if not path.exists():
        return True
    try:
        last_sent = dt.datetime.fromisoformat(path.read_text().strip())
    except Exception:
        return True
    return (dt.datetime.utcnow() - last_sent) > dt.timedelta(
        hours=min_hours_between_alerts
    )


def mark_sent(state_file: str) -> None:
    path = Path(state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dt.datetime.utcnow().isoformat(), encoding="utf-8")


def send_email(subject: str, body: str) -> None:
    host = os.environ.get("SMTP_HOST", "smtp.163.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]
    recipient = os.environ["ALERT_TO"]

    message = EmailMessage()
    message["From"] = user
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as smtp:
        smtp.login(user, password)
        smtp.send_message(message)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="print status only")
    parser.add_argument("--test", action="store_true", help="send a test email")
    parser.add_argument("--env-file", default=DEFAULT_ENV_FILE)
    parser.add_argument("--state-file", default=DEFAULT_STATE_FILE)
    parser.add_argument("--domain", default=None)
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--threshold-days", type=int, default=None)
    parser.add_argument("--min-hours-between-alerts", type=int, default=20)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    load_env(args.env_file)

    domain = args.domain or os.environ.get("ALERT_DOMAIN", "studytracker.xin")
    threshold = args.threshold_days
    if threshold is None:
        threshold = int(os.environ.get("ALERT_THRESHOLD_DAYS", "30"))

    try:
        days, expiry = certificate_expiry(domain, args.port)
    except Exception as exc:
        print(f"ERROR checking {domain}:{args.port}: {exc}", file=sys.stderr)
        if args.check:
            return 2
        if should_send(args.state_file, args.min_hours_between_alerts):
            try:
                send_email(
                    f"[ALERT] {domain} certificate check failed",
                    (
                        f"Could not read the TLS certificate from "
                        f"{domain}:{args.port}.\n\nError: {exc}\n"
                    ),
                )
                mark_sent(args.state_file)
            except Exception as send_exc:
                print(f"ERROR sending alert email: {send_exc}", file=sys.stderr)
        return 2

    print(f"{domain}: {days} days remaining (expires {expiry.isoformat()} UTC)")

    if args.check:
        return 0 if days >= threshold else 1

    if args.test:
        send_email(
            f"[TEST] {domain} certificate monitor",
            (
                f"This is a test email.\n\n"
                f"{domain} has {days} days remaining. "
                f"Expiry: {expiry.isoformat()} UTC.\n"
            ),
        )
        print("Test email sent.")
        return 0

    if days >= threshold:
        print("OK, above threshold.")
        return 0

    if not should_send(args.state_file, args.min_hours_between_alerts):
        print("Under threshold but already alerted recently, skipping.")
        return 0

    if not os.environ.get("SMTP_PASS"):
        print("Under threshold but SMTP_PASS is not configured.", file=sys.stderr)
        return 3

    send_email(
        f"[ALERT] {domain} certificate expires in {days} days",
        (
            f"The TLS certificate for {domain} expires in {days} days "
            f"({expiry.isoformat()} UTC).\n\n"
            "Check certbot renewal and nginx certificate configuration.\n"
        ),
    )
    mark_sent(args.state_file)
    print("Alert email sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
