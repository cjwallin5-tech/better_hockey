"""Outgoing email over SMTP (settings in config.py). With SMTP_HOST unset nothing is sent."""
import logging
import smtplib
import time
from email.message import EmailMessage

import config

log = logging.getLogger("uvicorn.error")


def send(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email; True when the SMTP server accepted it."""
    if not config.SMTP_HOST:
        return False
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


def send_with_retry(to: str, subject: str, body: str, attempts: int = 3, wait: float = 5, sleep=time.sleep) -> bool:
    """send(), tried up to `attempts` times with a growing wait between tries (wait, 2 x wait, ...), for a network that is briefly
    down. False only when every try failed."""
    for i in range(attempts):
        if send(to, subject, body):
            return True
        if i < attempts - 1:
            sleep(wait * (i + 1))
    return False
