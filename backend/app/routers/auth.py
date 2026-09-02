import hmac
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.db import get_db
from app.models import Candidate, OtpCode
from app.schemas.auth import OtpRequestPayload, OtpRequestResponse, OtpVerifyPayload, OtpVerifyResponse
from app.services import otp

router = APIRouter(prefix="/auth", tags=["auth"])


def _latest_otp_for_candidate(db: DBSession, candidate_id: uuid.UUID) -> OtpCode | None:
    records = db.query(OtpCode).filter_by(candidate_id=candidate_id).all()
    return max(records, key=lambda r: r.created_at) if records else None


@router.post("/otp/request", response_model=OtpRequestResponse)
async def request_otp(payload: OtpRequestPayload, db: DBSession = Depends(get_db)):
    """FL-06: send a time-limited OTP to the candidate's phone."""
    candidate = db.get(Candidate, payload.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    code = otp.generate_code()
    candidate.phone = payload.phone

    record = OtpCode(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        phone=payload.phone,
        code_hash=otp.hash_code(code),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=otp.OTP_TTL_MINUTES),
        attempt_count=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()

    otp.send_otp(payload.phone, code)

    return OtpRequestResponse(
        expires_in_seconds=otp.OTP_TTL_MINUTES * 60,
        debug_code=code if settings.app_env == "development" else None,
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
    candidate.phone_verified_at = datetime.now(timezone.utc)
    db.commit()

    return OtpVerifyResponse(verified=True, candidate_id=candidate.id)
