import uuid
from datetime import datetime

from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    resume_file_url: Mapped[str | None] = mapped_column(String, nullable=True)
    resume_parsed_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # FL-06: set once the candidate proves control of their email (emailed OTP,
    # Google or LinkedIn) — gates report access (see app/routers/auth.py).
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    auth_provider: Mapped[str | None] = mapped_column(String, nullable=True)  # "email" | "google" | "linkedin"
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    sessions: Mapped[list["InterviewSession"]] = relationship(back_populates="candidate")
