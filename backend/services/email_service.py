"""Minimal SMTP email sender. No-ops gracefully when unconfigured."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.config import settings

log = logging.getLogger("email")


def is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM)


def _send_sync(to: str, subject: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
        server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, [to], msg.as_string())


async def send_email(to: str, subject: str, html: str) -> bool:
    """Returns True on success; logs + returns False when disabled/failed."""
    if not is_configured():
        log.info("SMTP not configured - skipping email %r to %s", subject, to)
        return False
    import asyncio

    try:
        await asyncio.to_thread(_send_sync, to, subject, html)
        return True
    except Exception as e:
        log.error("send_email failed: %s", e)
        return False


def reset_email(to: str, link: str) -> tuple[str, str]:
    subject = "ORQEVA password reset"
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:24px">
      <h2 style="color:#22c55e">ORQEVA</h2>
      <p>We received a request to reset your password.</p>
      <p><a href="{link}" style="background:#22c55e;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none">Reset password</a></p>
      <p style="color:#666;font-size:13px">This link expires in 30 minutes and can be used once.
      If you didn't request this, ignore this email - your password stays unchanged.</p>
    </div>
    """
    return subject, html
