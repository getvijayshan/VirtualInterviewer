import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class OtpCode(Base):
    """FL-06: a one-time code sent to a candidate's phone before they can see
    their report. Only the hash is stored — see app/services/otp.py."""

    __tablename__ = "otp_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidates.id"))
    phone: Mapped[str] = mapped_column(String)
    code_hash: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime] = mapped_column()
    consumed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    candidate: Mapped["Candidate"] = relationship()
