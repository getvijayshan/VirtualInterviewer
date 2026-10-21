import uuid

from pydantic import BaseModel, EmailStr


class OtpRequestPayload(BaseModel):
    candidate_id: uuid.UUID
    email: EmailStr


class OtpRequestResponse(BaseModel):
    expires_in_seconds: int
    # Dev-only convenience so this is testable without a real SMTP server —
    # only populated when settings.app_env == "development" or settings.otp_echo_code (test mode).
    debug_code: str | None = None


class OtpVerifyPayload(BaseModel):
    candidate_id: uuid.UUID
    code: str


class OtpVerifyResponse(BaseModel):
    verified: bool
    candidate_id: uuid.UUID


class AuthMethodsResponse(BaseModel):
    """Sign-in methods the gate can offer. Email OTP is always available."""

    oauth_providers: list[str]


class OAuthStartResponse(BaseModel):
    authorize_url: str
