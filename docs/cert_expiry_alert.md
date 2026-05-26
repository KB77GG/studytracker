# Certificate Expiry Alert

`scripts/cert_expiry_alert.py` checks the public TLS certificate for
`studytracker.xin` and sends email when the remaining lifetime is below a
configured threshold.

The script is intentionally independent of the Flask app and uses only the
Python standard library.

## Current Production Finding

As of 2026-05-26:

- `studytracker.xin` serves a Let's Encrypt certificate expiring on
  2026-07-19 05:20:30 UTC.
- The certificate SAN contains `DNS:studytracker.xin` only.
- `certbot.timer` is active.
- `certbot certificates` reports the renewal config as invalid because
  Certbot 1.21.0 is calling an API that is no longer present in the installed
  `cryptography` package:

```text
'cryptography.hazmat.bindings._rust.openssl.rsa.RSA' object has no attribute 'verifier'
```

Fix the Certbot package compatibility before the renewal window becomes
urgent. The monitor is useful, but it is not a substitute for a working
renewal path.

## Configuration

Production keeps secrets outside Git in:

```text
/root/apps/studytracker/.env.alerts
```

Required keys:

```text
SMTP_HOST=smtp.163.com
SMTP_PORT=465
SMTP_USER=...
SMTP_PASS=...
ALERT_TO=...
ALERT_DOMAIN=studytracker.xin
ALERT_THRESHOLD_DAYS=30
```

Use `ALERT_THRESHOLD_DAYS=30` or higher so alerts begin around the same time
Certbot should normally renew the certificate.

## Manual Checks

Status-only check, no email:

```bash
cd /root/apps/studytracker
/usr/bin/python3 scripts/cert_expiry_alert.py --check
```

Test SMTP delivery:

```bash
cd /root/apps/studytracker
/usr/bin/python3 scripts/cert_expiry_alert.py --test
```

## Optional Systemd Installation

Install the service and timer after confirming `.env.alerts` is present and
Certbot renewal has been repaired:

```bash
sudo install -m 644 ops/systemd/cert-expiry-alert.service /etc/systemd/system/
sudo install -m 644 ops/systemd/cert-expiry-alert.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cert-expiry-alert.timer
```

Inspect status:

```bash
systemctl list-timers --all | grep cert-expiry-alert
journalctl -u cert-expiry-alert.service --since "7 days ago"
```
