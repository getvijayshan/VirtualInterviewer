"""FL-06: OTP generation, hashing, and delivery.

Delivery goes through Fast2SMS (settings.sms_provider == "fast2sms") using its
dedicated OTP route. With no provider configured, send_otp() only logs the code
(local dev / OTP_ECHO_CODE test mode).
"""

import hashlib
import logging
import re
import secrets

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

FAST2SMS_URL = "https://www.fast2sms.com/dev/bulkV2"

OTP_LENGTH = 6
OTP_TTL_MINUTES = 5
MAX_VERIFY_ATTEMPTS = 5


def generate_code() -> str:
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class SmsDeliveryError(Exception):
    """Raised when the SMS provider rejects or fails to send the OTP."""


def _indian_mobile(phone: str) -> str:
    """Normalise to the 10-digit national number Fast2SMS expects (+91 / 0 prefixes dropped)."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise SmsDeliveryError("Enter a valid 10-digit Indian mobile number.")
    return digits


def _send_fast2sms(phone: str, code: str) -> None:
    if not settings.fast2sms_api_key:
        raise SmsDeliveryError("SMS is not configured.")
    try:
        resp = httpx.post(
            FAST2SMS_URL,
            headers={"authorization": settings.fast2sms_api_key},
            json={"route": "otp", "variables_values": code, "numbers": _indian_mobile(phone)},
            timeout=10,
        )
        body = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("Fast2SMS request failed: %s", exc)
        raise SmsDeliveryError("Could not send the SMS. Please try again.") from exc
    if resp.status_code != 200 or not body.get("return"):
        logger.error("Fast2SMS rejected OTP: %s %s", resp.status_code, body)
        raise SmsDeliveryError("Could not send the SMS. Please try again.")


def send_otp(phone: str, code: str) -> None:
    """Deliver the OTP to the candidate's phone."""
    if settings.sms_provider == "fast2sms":
        _send_fast2sms(phone, code)
        return
    print(f"[otp] would SMS {phone}: your Candidate True Companion code is {code}")
