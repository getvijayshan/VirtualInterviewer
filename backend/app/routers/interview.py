import uuid
from datetime import datetime, timedelta, timezone

import anthropic
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.db import get_db
from app.models import (
    Candidate,
    InterviewSession,
    SessionStatus,
    TranscriptionProvider,
    TranscriptTurn,
    TurnRole,
)
from app.schemas.interview import InterviewTurnResponse, TranscriptResponse
from app.services import llm, storage
from app.services.interview_prompts import build_system_prompt
from app.services.transcription import TranscriptionError, transcribe

router = APIRouter(prefix="/sessions/{session_id}", tags=["interview"])

KICKOFF_MESSAGE = "Begin the interview by asking your first question."


def _get_session_or_404(db: DBSession, session_id: uuid.UUID) -> InterviewSession:
    session = db.get(InterviewSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


def _ordered_turns(db: DBSession, session_id: uuid.UUID) -> list[TranscriptTurn]:
    return (
        db.query(TranscriptTurn)
        .filter_by(session_id=session_id)
        .order_by(TranscriptTurn.turn_index)
        .all()
    )


def _time_remaining_seconds(session: InterviewSession) -> int:
    if session.started_at is None:
        return session.duration_min * 60
    deadline = session.started_at + timedelta(minutes=session.duration_min)
    remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
    return max(0, int(remaining))


def _is_time_up(session: InterviewSession) -> bool:
    return session.started_at is not None and _time_remaining_seconds(session) <= 0


def _messages_for_claude(turns: list[TranscriptTurn]) -> list[dict]:
    """Map persisted turns to Anthropic messages, marking the last one as a
    cache breakpoint so the growing conversation prefix is reused turn over
    turn (FL-09) rather than only the system prompt being cached."""
    if not turns:
        return [{"role": "user", "content": KICKOFF_MESSAGE}]

    messages = [{"role": t.role.value, "content": t.content} for t in turns[:-1]]
    last = turns[-1]
    messages.append({"role": last.role.value, "content": llm.cacheable(last.content)})
    return messages


@router.post("/start", response_model=InterviewTurnResponse)
async def start_interview(session_id: uuid.UUID, db: DBSession = Depends(get_db)):
    """FL-05.1: session opens with an introductory message and first question."""
    session = _get_session_or_404(db, session_id)
    if session.status != SessionStatus.pending:
        raise HTTPException(status_code=409, detail="Session already started or ended.")

    candidate = db.get(Candidate, session.candidate_id)
    system_prompt = llm.cacheable(build_system_prompt(candidate, session))

    try:
        response = llm.create_message(
            model=settings.anthropic_model_interview,
            system=system_prompt,
            messages=_messages_for_claude([]),
            max_tokens=400,
            call_type="question_gen",
            session_id=str(session.id),
        )
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Could not start the interview: {exc}") from exc

    question_text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not question_text:
        raise HTTPException(status_code=502, detail="Claude did not return an opening question.")

    turn = TranscriptTurn(
        id=uuid.uuid4(),
        session_id=session.id,
        turn_index=0,
        role=TurnRole.assistant,
        content=question_text,
        created_at=datetime.now(timezone.utc),
    )
    session.status = SessionStatus.in_progress
    session.started_at = datetime.now(timezone.utc)
    db.add(turn)
    db.commit()
    db.refresh(session)

    return InterviewTurnResponse(
        question=question_text,
        turn_index=0,
        session_status=session.status.value,
        time_remaining_seconds=_time_remaining_seconds(session),
        ended=False,
    )


@router.post("/turns", response_model=InterviewTurnResponse)
async def submit_answer(session_id: uuid.UUID, audio: UploadFile, db: DBSession = Depends(get_db)):
    """FL-05.4: transcribe the candidate's spoken answer, append to the transcript,
    call Claude for the next question. FL-05.5: server-side duration hard stop,
    independent of model behavior — checked before any Claude call."""
    session = _get_session_or_404(db, session_id)
    if session.status == SessionStatus.completed or session.status == SessionStatus.abandoned:
        raise HTTPException(status_code=409, detail="Session has already ended.")
    if session.status != SessionStatus.in_progress:
        raise HTTPException(status_code=409, detail="Session has not started — call /start first.")

    audio_bytes = await audio.read()
    try:
        answer_text = transcribe(audio_bytes)
    except TranscriptionError as exc:
        raise HTTPException(status_code=422, detail=f"Could not transcribe your answer: {exc}") from exc

    existing_turns = _ordered_turns(db, session_id)
    next_index = len(existing_turns)

    audio_url = storage.upload_interview_answer_audio(
        session_id=str(session.id),
        turn_index=next_index,
        data=audio_bytes,
        content_type=audio.content_type or "audio/webm",
    )

    user_turn = TranscriptTurn(
        id=uuid.uuid4(),
        session_id=session.id,
        turn_index=next_index,
        role=TurnRole.user,
        content=answer_text,
        audio_file_url=audio_url,
        transcription_provider=TranscriptionProvider(settings.stt_provider),
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_turn)

    # FL-05.5: hard stop is time-based and checked here, before any further
    # Claude call — the candidate's final answer is still saved either way.
    if _is_time_up(session):
        session.status = SessionStatus.completed
        session.ended_at = datetime.now(timezone.utc)
        db.commit()
        return InterviewTurnResponse(
            question=None,
            turn_index=None,
            session_status=session.status.value,
            time_remaining_seconds=0,
            ended=True,
            answer_text=answer_text,
        )

    candidate = db.get(Candidate, session.candidate_id)
    system_prompt = llm.cacheable(build_system_prompt(candidate, session))
    all_turns = existing_turns + [user_turn]

    try:
        response = llm.create_message(
            model=settings.anthropic_model_interview,
            system=system_prompt,
            messages=_messages_for_claude(all_turns),
            max_tokens=400,
            call_type="question_gen",
            session_id=str(session.id),
        )
    except anthropic.APIError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Could not generate the next question: {exc}") from exc

    question_text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not question_text:
        db.rollback()
        raise HTTPException(status_code=502, detail="Claude did not return a question.")

    next_turn = TranscriptTurn(
        id=uuid.uuid4(),
        session_id=session.id,
        turn_index=next_index + 1,
        role=TurnRole.assistant,
        content=question_text,
        created_at=datetime.now(timezone.utc),
    )
    db.add(next_turn)
    db.commit()

    return InterviewTurnResponse(
        question=question_text,
        turn_index=next_index + 1,
        session_status=session.status.value,
        time_remaining_seconds=_time_remaining_seconds(session),
        ended=False,
        answer_text=answer_text,
    )


@router.get("/transcript", response_model=TranscriptResponse)
async def get_transcript(session_id: uuid.UUID, db: DBSession = Depends(get_db)):
    """FL-05.8: full ordered question/answer transcript. Also what the
    frontend re-fetches to resume a dropped/refreshed session (FL-05.7),
    since state lives here in Postgres, not in-memory."""
    session = _get_session_or_404(db, session_id)
    turns = _ordered_turns(db, session_id)
    return TranscriptResponse(
        session_id=session.id,
        status=session.status.value,
        time_remaining_seconds=_time_remaining_seconds(session),
        turns=turns,
    )


@router.post("/end", response_model=InterviewTurnResponse)
async def end_session(session_id: uuid.UUID, db: DBSession = Depends(get_db)):
    """FL-05.6: candidate ends the session early. Idempotent — ending an
    already-ended session just returns its current state."""
    session = _get_session_or_404(db, session_id)
    if session.status not in (SessionStatus.completed, SessionStatus.abandoned):
        session.status = SessionStatus.completed
        session.ended_at = datetime.now(timezone.utc)
        db.commit()

    return InterviewTurnResponse(
        question=None,
        turn_index=None,
        session_status=session.status.value,
        time_remaining_seconds=0,
        ended=True,
    )
