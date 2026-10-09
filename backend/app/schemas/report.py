import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class QuestionFeedback(BaseModel):
    question: str
    quality: Literal["strong", "needs_work"]
    note: str


class ReportResponse(BaseModel):
    session_id: uuid.UUID
    overall_score: float
    questions: list[QuestionFeedback]
    communication_notes: str
    generated_at: datetime
