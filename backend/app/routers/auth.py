import hmac
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session as DBSession
from urllib.parse import urlencode

from app.config import settings
from app.db import get_db
from app.models import Candidate, InterviewSession, OtpCode
from app.schemas.auth import (
    AuthMethodsResponse,
    OAuthStartResponse,
    OtpRequestPayload,
    OtpRequestResponse,
    OtpVerifyPayload,
    OtpVerifyResponse,
)
from app.services import oauth, otp

router = APIRouter(prefix="/auth", tags=["auth"])


def _latest_otp_for_candidate(db: DBSession, candidate_id: uuid.UUID) -> OtpCode | None:
    records = db.query(OtpCode).filter_by(candidate_id=candidate_id).all()
    return max(records, key=lambda r: r.created_at) if records else None


@router.post("/otp/request", response_model=OtpRequestResponse)
async def request_otp(payload: OtpRequestPayload, db: DBSession = Depends(get_db)):
    """FL-06: email a time-limited OTP to the candidate."""
    candidate = db.get(Candidate, payload.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    code = otp.generate_code()
    candidate.email = payload.email

    record = OtpCode(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        email=payload.email,
        code_hash=otp.hash_code(code),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=otp.OTP_TTL_MINUTES),
        attempt_count=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()

    try:
        otp.send_otp(payload.email, code)
    except otp.EmailDeliveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return OtpRequestResponse(
        expires_in_seconds=otp.OTP_TTL_MINUTES * 60,
        debug_code=code if (settings.app_env == "development" or settings.otp_echo_code) else None,
    )


@router.post("/otp/verify", response_model=OtpVerifyResponse)
async def verify_otp(payload: OtpVerifyPayload, db: DBSession = Depends(get_db)):
    """FL-06.2/.3: single-use, time-limited code; clear error on bad/expired
    code so the frontend can offer a retry (request a new code)."""
    candidate = db.get(Candidate, payload.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    record = _latest_otp_for_candidate(db, candidate.id)
    if record is None:
        raise HTTPException(status_code=400, detail="No active code found. Request a new one.")
    if record.consumed_at is not None:
        raise HTTPException(status_code=400, detail="This code has already been used. Request a new one.")
    if record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This code has expired. Request a new one.")
    if record.attempt_count >= otp.MAX_VERIFY_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many incorrect attempts. Request a new one.")

    if not hmac.compare_digest(otp.hash_code(payload.code), record.code_hash):
        record.attempt_count += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Incorrect code. Please try again.")

    record.consumed_at = datetime.now(timezone.utc)
    # FL-06.4: successful auth links the session to a persistent candidate account.
    candidate.verified_at = datetime.now(timezone.utc)
    candidate.auth_provider = "email"
    db.commit()

    return OtpVerifyResponse(verified=True, candidate_id=candidate.id)


@router.get("/methods", response_model=AuthMethodsResponse)
async def auth_methods():
    """FL-06: which OAuth buttons the auth gate should show."""
    return AuthMethodsResponse(oauth_providers=oauth.enabled_providers())


@router.get("/oauth/{provider}/start", response_model=OAuthStartResponse)
async def oauth_start(provider: str, session_id: uuid.UUID, db: DBSession = Depends(get_db)):
    """FL-06: begin Google/LinkedIn sign-in for the candidate who owns this session."""
    if db.get(InterviewSession, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    try:
        prov = oauth.get_provider(provider)
    except oauth.OAuthError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return OAuthStartResponse(authorize_url=oauth.authorize_url(prov, oauth.make_state(provider, str(session_id))))


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    state: str = "",
    code: str = "",
    error: str = "",
    db: DBSession = Depends(get_db),
):
    """FL-06: provider redirect target. Verifies the candidate and sends the
    browser back to the frontend (the report on success, the auth gate with an
    error message otherwise)."""
    frontend = settings.frontend_public_url.rstrip("/")
    try:
        prov = oauth.get_provider(provider)
        session_id = oauth.read_state(state, provider)
    except oauth.OAuthError as exc:
        return RedirectResponse(f"{frontend}/?{urlencode({'auth_error': str(exc)})}")

    def back_with_error(message: str) -> RedirectResponse:
        return RedirectResponse(f"{frontend}/sessions/{session_id}/auth?{urlencode({'error': message})}")

    if error or not code:
        return back_with_error("Sign-in was cancelled.")
    try:
        email = oauth.fetch_verified_email(prov, code)
    except oauth.OAuthError as exc:
        return back_with_error(str(exc))

    session = db.get(InterviewSession, uuid.UUID(session_id))
    candidate = db.get(Candidate, session.candidate_id) if session else None
    if candidate is None:
        return back_with_error("Session not found.")

    if not candidate.email:
        candidate.email = email
    candidate.verified_at = datetime.now(timezone.utc)
    candidate.auth_provider = provider
    db.commit()
    return RedirectResponse(f"{frontend}/sessions/{session_id}/report")
