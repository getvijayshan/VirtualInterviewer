"""FL-06: OTP generation, hashing, and delivery.

No SMS provider is wired up yet (Phase 1 MVP) — send_otp() logs the code
instead of texting it. Bundle wiring a real provider (e.g. Twilio) with the
other real-credentials follow-up work already tracked in #14.
"""

import hashlib
import secrets

OTP_LENGTH = 6
OTP_TTL_MINUTES = 5
MAX_VERIFY_ATTEMPTS = 5


def generate_code() -> str:
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def send_otp(phone: str, code: str) -> None:
    """Deliver the OTP to the candidate's phone. Stub — see module docstring."""
    print(f"[otp] would SMS {phone}: your Candidate True Companion code is {code}")
