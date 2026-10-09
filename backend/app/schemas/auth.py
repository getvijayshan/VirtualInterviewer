import uuid

from pydantic import BaseModel, field_validator


class OtpRequestPayload(BaseModel):
    candidate_id: uuid.UUID
    phone: str

    @field_validator("phone")
    @classmethod
    def phone_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Phone number is required.")
        return v.strip()


class OtpRequestResponse(BaseModel):
    expires_in_seconds: int
    # Dev-only convenience so this is testable without a real SMS provider —
    # never populated outside settings.app_env == "development".
    debug_code: str | None = None


class OtpVerifyPayload(BaseModel):
    candidate_id: uuid.UUID
    code: str


class OtpVerifyResponse(BaseModel):
    verified: bool
    candidate_id: uuid.UUID
