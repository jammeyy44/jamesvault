"""
Minimal SMTP sender. Without SMTP_HOST nothing is delivered; in development the message is logged
so the password-reset flow can be exercised locally. Never logs message bodies in production.
"""
import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

logger = logging.getLogger("jamesvault.mail")


def send_email(to, subject, body):
    cfg = current_app.config
    if not cfg.get("SMTP_HOST"):
        if cfg.get("JV_ENV") != "production":
            logger.warning("SMTP not configured; development email to %s: %s\n%s", to, subject, body)
        else:
            logger.error("SMTP not configured; email to %s was NOT sent", to)
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg["SMTP_FROM"], to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=10) as smtp:
            smtp.starttls()
            if cfg.get("SMTP_USER"):
                smtp.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            smtp.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False
