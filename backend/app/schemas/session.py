import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator

from app.constants import PREDEFINED_ROLES, PREDEFINED_TOPIC_VALUES


class TopicOption(BaseModel):
    value: str
    label: str


class TargetOptionsResponse(BaseModel):
    roles: list[str]
    topics: list[TopicOption]


class SessionCreateRequest(BaseModel):
    """FL-03/FL-04: create a session from one of the three target-input paths,
    gated on explicit consent."""

    candidate_id: uuid.UUID
    target_type: Literal["jd", "role", "topic"]
    jd_text: str | None = None
    target_role: str | None = None
    target_topic: str | None = None
    consent: bool

    @model_validator(mode="after")
    def validate_target_and_consent(self) -> "SessionCreateRequest":
        # FL-04.4: declining consent halts the flow — no session gets created.
        if not self.consent:
            raise ValueError("Consent is required to start a session.")

        # FL-03.3: exactly the field matching target_type must be filled.
        if self.target_type == "jd":
            if not self.jd_text or not self.jd_text.strip():
                raise ValueError("jd_text is required when target_type is 'jd'.")
        elif self.target_type == "role":
            if not self.target_role or self.target_role not in PREDEFINED_ROLES:
                raise ValueError(f"target_role must be one of {PREDEFINED_ROLES}.")
        elif self.target_type == "topic":
            if not self.target_topic or self.target_topic not in PREDEFINED_TOPIC_VALUES:
                raise ValueError(f"target_topic must be one of {sorted(PREDEFINED_TOPIC_VALUES)}.")
        return self


class SessionResponse(BaseModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    target_type: str
    jd_text: str | None
    target_role: str | None
    target_topic: str | None
    duration_min: int
    status: str
    consent_at: datetime | None

    model_config = {"from_attributes": True}
