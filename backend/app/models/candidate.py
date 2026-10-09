import uuid
from datetime import datetime

from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    resume_file_url: Mapped[str | None] = mapped_column(String, nullable=True)
    resume_parsed_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # FL-06: set once the candidate verifies this phone number via OTP —
    # gates report access (see app/routers/auth.py).
    phone_verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    sessions: Mapped[list["InterviewSession"]] = relationship(back_populates="candidate")
