import uuid
from datetime import datetime

from pydantic import BaseModel


class TranscriptTurnResponse(BaseModel):
    turn_index: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TranscriptResponse(BaseModel):
    session_id: uuid.UUID
    status: str
    time_remaining_seconds: int
    turns: list[TranscriptTurnResponse]


class InterviewTurnResponse(BaseModel):
    """Returned by both /start and /turns — the next question to show,
    or ended=true (with question=None) once the session is over."""

    question: str | None
    turn_index: int | None
    session_status: str
    time_remaining_seconds: int
    ended: bool
    # Echoes back the transcribed text of the answer just submitted, so the
    # frontend can render it without a second round-trip. None for /start
    # and /end, which don't take an answer.
    answer_text: str | None = None
