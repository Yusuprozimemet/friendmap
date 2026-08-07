"""Outbound email, behind one function.

Three backends, chosen by `MAIL_BACKEND`:

* `console` (default) — writes the message to stdout and returns success.
  Everything downstream is testable without picking a vendor or risking a
  real send during development.
* `smtp` — your own server. No vendor, but deliverability is your problem.
* `resend` — HTTP API, an API key and nothing else to run.

`send` returns True/False rather than raising: the alert job records "already
told them about this person" only on success, so a failure has to be a value
the caller can branch on, not an exception that skips the bookkeeping.
"""
from __future__ import annotations

import smtplib
import textwrap
from email.message import EmailMessage

import requests

from app import config


def _send_console(to: str, subject: str, body: str) -> bool:
    print("--- email (console backend, not actually sent) ---")
    print(f"To:      {to}")
    print(f"Subject: {subject}")
    print(textwrap.indent(body, "  "))
    print("--- end ---")
    return True


def _send_smtp(to: str, subject: str, body: str) -> bool:
    message = EmailMessage()
    message["From"] = config.MAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        if config.SMTP_SSL:
            server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=20)
        else:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20)
        with server:
            if config.SMTP_STARTTLS and not config.SMTP_SSL:
                server.starttls()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(message)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        print(f"  mail: SMTP send to {to} failed: {exc}")
        return False


def _send_resend(to: str, subject: str, body: str) -> bool:
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
            json={
                "from": config.MAIL_FROM,
                "to": [to],
                "subject": subject,
                "text": body,
            },
            timeout=20,
        )
        if resp.ok:
            return True
        print(f"  mail: Resend rejected send to {to}: {resp.status_code} {resp.text[:200]}")
        return False
    except requests.RequestException as exc:
        print(f"  mail: Resend send to {to} failed: {exc}")
        return False


_BACKENDS = {
    "console": _send_console,
    "smtp": _send_smtp,
    "resend": _send_resend,
}


def send(to: str, subject: str, body: str) -> bool:
    """True when the message was handed off successfully."""
    backend = _BACKENDS.get(config.MAIL_BACKEND)
    if backend is None:
        print(f"  mail: unknown MAIL_BACKEND {config.MAIL_BACKEND!r}, not sending")
        return False
    if not to:
        return False
    return backend(to, subject, body)
