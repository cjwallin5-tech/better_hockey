"""Outgoing email over SMTP (settings in config.py). With SMTP_HOST unset nothing is sent."""
import logging
import smtplib
import time
from email.message import EmailMessage

import requests

import config

log = logging.getLogger("uvicorn.error")


def send(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email; True when the SMTP server accepted it."""
    if not config.SMTP_HOST:
        return False
    if config.RESEND_API_KEY:
        return _send_resend(to, subject, body)
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = config.SMTP_FROM, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            if config.SMTP_USER:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD or "")
            smtp.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException):
        log.exception("Couldn't send an email to %s", to)
        return False


def _send_resend(to: str, subject: str, body: str) -> bool:
    """Send through Resend's HTTPS API (works where outbound SMTP is blocked)."""
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
            json={"from": config.SMTP_FROM, "to": [to], "subject": subject, "text": body},
            timeout=15,
        )
        if r.ok:
            return True
        log.error("Resend rejected the email to %s: %s %s", to, r.status_code, r.text[:300])
    except requests.RequestException:
        log.exception("Couldn't send an email to %s", to)
    return False


def send_with_retry(to: str, subject: str, body: str, attempts: int = 3, wait: float = 5, sleep=time.sleep) -> bool:
    """send(), tried up to `attempts` times with a growing wait between tries (wait, 2 x wait, ...), for a network that is briefly
    down. False only when every try failed."""
    for i in range(attempts):
        if send(to, subject, body):
            return True
        if i < attempts - 1:
            sleep(wait * (i + 1))
    return False
