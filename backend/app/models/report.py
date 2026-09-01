import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), unique=True)

    scorecard_json: Mapped[dict] = mapped_column(JSON)
    feedback_text: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    session: Mapped["InterviewSession"] = relationship(back_populates="report")
