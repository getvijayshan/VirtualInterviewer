"""FL-06: OTP generation, hashing, and delivery.

Codes are emailed over SMTP (settings.smtp_host). With no SMTP host configured,
send_otp() only logs the code (local dev / OTP_ECHO_CODE test mode).
"""

import hashlib
import logging
import secrets
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_TTL_MINUTES = 5
MAX_VERIFY_ATTEMPTS = 5


def generate_code() -> str:
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class EmailDeliveryError(Exception):
    """Raised when the SMTP server rejects or fails to send the OTP."""


def _send_smtp(email: str, code: str) -> None:
    sender = settings.smtp_from or settings.smtp_username
    if not sender:
        raise EmailDeliveryError("Email is not configured.")

    msg = EmailMessage()
    msg["Subject"] = "Your Candidate True Companion verification code"
    msg["From"] = sender
    msg["To"] = email
    msg.set_content(
        f"Your verification code is {code}.\n\n"
        f"It expires in {OTP_TTL_MINUTES} minutes. If you didn't request it, you can ignore this email."
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("SMTP send failed: %s", exc)
        raise EmailDeliveryError("Could not send the email. Please try again.") from exc


def send_otp(email: str, code: str) -> None:
    """Deliver the OTP to the candidate's email address."""
    if settings.smtp_host:
        _send_smtp(email, code)
        return
    print(f"[otp] would email {email}: your Candidate True Companion code is {code}")
