import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Candidate
from app.schemas.resume import CandidateResponse, ResumeUploadResponse
from app.services import llm, storage
from app.services.resume_parser import (
    FileTooLargeError,
    ResumeParsingError,
    UnsupportedFileTypeError,
    extract_text,
    validate_upload,
)

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("", response_model=ResumeUploadResponse)
async def upload_resume(file: UploadFile, db: Session = Depends(get_db)):
    """FL-01: accept PDF/DOCX, store in S3, extract structured data via Claude."""
    data = await file.read()

    try:
        validate_upload(file.filename or "", len(data))
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    candidate = Candidate(id=uuid.uuid4())

    resume_file_url = storage.upload_resume_file(
        candidate_id=str(candidate.id),
        filename=file.filename,
        data=data,
        content_type=file.content_type or "application/octet-stream",
    )
    candidate.resume_file_url = resume_file_url

    # FL-01.5: a parsing or extraction failure must not crash the request — persist
    # what we have (the uploaded file) and tell the frontend to route to manual entry.
    parsed: dict | None = None
    needs_manual_entry = False
    error: str | None = None
    try:
        text = extract_text(file.filename, data)
        parsed = llm.extract_candidate_fields(text)
    except (ResumeParsingError, llm.ExtractionError) as exc:
        needs_manual_entry = True
        error = str(exc)

    candidate.resume_parsed_json = parsed
    if parsed:
        candidate.name = parsed.get("name")
        candidate.email = parsed.get("email")
        candidate.phone = parsed.get("phone")

    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    return ResumeUploadResponse(
        candidate_id=candidate.id,
        resume_file_url=resume_file_url,
        parsed=parsed,
        needs_manual_entry=needs_manual_entry,
        error=error,
    )


@router.get("/{resume_id}", response_model=CandidateResponse)
async def get_resume(resume_id: uuid.UUID, db: Session = Depends(get_db)):
    """FL-02: return extracted fields for the confirmation screen."""
    candidate = db.get(Candidate, resume_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return candidate


@router.patch("/{resume_id}")
async def update_resume(resume_id: uuid.UUID):
    """FL-02: persist candidate corrections to extracted fields."""
    raise NotImplementedError
