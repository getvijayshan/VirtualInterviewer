import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.constants import PREDEFINED_ROLES, PREDEFINED_TOPICS
from app.db import get_db
from app.models import Candidate, InterviewSession, SessionStatus, TargetType
from app.schemas.session import SessionCreateRequest, SessionResponse, TargetOptionsResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/target-options", response_model=TargetOptionsResponse)
async def get_target_options():
    """FL-03: predefined role/topic choices for the frontend pickers."""
    return TargetOptionsResponse(roles=PREDEFINED_ROLES, topics=PREDEFINED_TOPICS)


@router.post("", response_model=SessionResponse)
async def create_session(payload: SessionCreateRequest, db: DBSession = Depends(get_db)):
    """FL-03/FL-04: create a session with target_type ('jd'|'role'|'topic'),
    the corresponding target value, and consent — fixed 30 min duration.

    Validation (target/consent required combinations) happens on
    SessionCreateRequest itself — an invalid payload never reaches here,
    FastAPI returns 422 before this body executes.
    """
    candidate = db.get(Candidate, payload.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    session = InterviewSession(
        id=uuid.uuid4(),
        candidate_id=payload.candidate_id,
        target_type=TargetType(payload.target_type),
        jd_text=payload.jd_text,
        target_role=payload.target_role,
        target_topic=payload.target_topic,
        duration_min=settings.session_duration_min,  # FL-04.2/.3: fixed for Phase 1
        status=SessionStatus.pending,
        consent_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: uuid.UUID, db: DBSession = Depends(get_db)):
    """Session status/state for resuming a dropped session (FL-05.7)."""
    session = db.get(InterviewSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session
