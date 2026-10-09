import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TargetType(str, enum.Enum):
    jd = "jd"
    role = "role"
    topic = "topic"


class SessionStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    abandoned = "abandoned"


class InterviewSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidates.id"))

    target_type: Mapped[TargetType] = mapped_column(Enum(TargetType, name="target_type"))
    jd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_role: Mapped[str | None] = mapped_column(String, nullable=True)
    target_topic: Mapped[str | None] = mapped_column(String, nullable=True)

    duration_min: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"), default=SessionStatus.pending
    )

    consent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)

    candidate: Mapped["Candidate"] = relationship(back_populates="sessions")
    transcript_turns: Mapped[list["TranscriptTurn"]] = relationship(
        back_populates="session", order_by="TranscriptTurn.turn_index"
    )
    report: Mapped["Report | None"] = relationship(back_populates="session", uselist=False)
