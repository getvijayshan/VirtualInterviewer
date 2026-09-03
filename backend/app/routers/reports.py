import uuid
from datetime import datetime, timezone

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.db import get_db
from app.models import Candidate, InterviewSession, Report, SessionStatus, TranscriptTurn
from app.schemas.report import QuestionFeedback, ReportResponse
from app.services import llm
from app.services.report_prompts import REPORT_TOOL, build_system_prompt, build_transcript_text

router = APIRouter(prefix="/sessions/{session_id}/report", tags=["reports"])


def _get_session_or_404(db: DBSession, session_id: uuid.UUID) -> InterviewSession:
    session = db.get(InterviewSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


def _require_verified_candidate(db: DBSession, session: InterviewSession) -> Candidate:
    """FL-06: the report is auth-gated, not just the frontend route to it —
    enforce phone verification here too, not only client-side."""
    candidate = db.get(Candidate, session.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if candidate.phone_verified_at is None:
        raise HTTPException(status_code=403, detail="Verify your phone before viewing the report.")
    return candidate


def _existing_report(db: DBSession, session_id: uuid.UUID) -> Report | None:
    reports = db.query(Report).filter_by(session_id=session_id).all()
    return reports[0] if reports else None


def _to_response(report: Report) -> ReportResponse:
    data = report.scorecard_json
    return ReportResponse(
        session_id=report.session_id,
        overall_score=data["overall_score"],
        questions=[QuestionFeedback(**q) for q in data["questions"]],
        communication_notes=report.feedback_text,
        generated_at=report.generated_at,
    )


@router.post("", response_model=ReportResponse)
async def generate_report(session_id: uuid.UUID, db: DBSession = Depends(get_db)):
    """FL-07: single Claude call over the full transcript -> scorecard + feedback,
    persisted so it's re-viewable without regenerating (FL-07.6). Gated behind
    OTP auth (FL-06)."""
    session = _get_session_or_404(db, session_id)
    candidate = _require_verified_candidate(db, session)

    if session.status != SessionStatus.completed:
        raise HTTPException(status_code=409, detail="Session has not ended yet.")

    existing = _existing_report(db, session_id)
    if existing is not None:
        return _to_response(existing)

    turns = (
        db.query(TranscriptTurn).filter_by(session_id=session_id).order_by(TranscriptTurn.turn_index).all()
    )
    if not turns:
        raise HTTPException(status_code=422, detail="No transcript to grade.")

    system_prompt = llm.cacheable(build_system_prompt(candidate, session))
    transcript_text = build_transcript_text(turns)

    try:
        response = llm.create_message(
            model=settings.anthropic_model_report,
            system=system_prompt,
            messages=[{"role": "user", "content": transcript_text}],
            max_tokens=2048,
            call_type="report_gen",
            session_id=str(session.id),
            tools=[REPORT_TOOL],
            tool_choice={"type": "tool", "name": "record_interview_report"},
        )
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Could not generate report: {exc}") from exc

    data = None
    for block in response.content:
        if block.type == "tool_use" and block.name == "record_interview_report":
            data = block.input
            break
    if data is None:
        raise HTTPException(status_code=502, detail="Claude did not return a structured report.")

    report = Report(
        id=uuid.uuid4(),
        session_id=session.id,
        scorecard_json={"overall_score": data["overall_score"], "questions": data["questions"]},
        feedback_text=data["communication_notes"],
        generated_at=datetime.now(timezone.utc),
    )
    db.add(report)
    db.commit()

    return _to_response(report)


@router.get("", response_model=ReportResponse)
async def get_report(session_id: uuid.UUID, db: DBSession = Depends(get_db)):
    """FL-07.6: return the persisted report."""
    session = _get_session_or_404(db, session_id)
    _require_verified_candidate(db, session)

    report = _existing_report(db, session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found — generate it first.")
    return _to_response(report)
