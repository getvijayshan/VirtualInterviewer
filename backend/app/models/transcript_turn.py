import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TurnRole(str, enum.Enum):
    assistant = "assistant"
    user = "user"


class TranscriptionProvider(str, enum.Enum):
    deepgram = "deepgram"
    azure_foundry = "azure_foundry"


class TranscriptTurn(Base):
    __tablename__ = "transcript_turns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"))

    turn_index: Mapped[int] = mapped_column(Integer)
    role: Mapped[TurnRole] = mapped_column(Enum(TurnRole, name="turn_role"))
    content: Mapped[str] = mapped_column(Text)

    # nullable — only set for 'user' turns, which originate as a recorded answer
    audio_file_url: Mapped[str | None] = mapped_column(String, nullable=True)
    transcription_provider: Mapped[TranscriptionProvider | None] = mapped_column(
        Enum(TranscriptionProvider, name="transcription_provider"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    session: Mapped["InterviewSession"] = relationship(back_populates="transcript_turns")
