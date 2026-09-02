import uuid

from pydantic import BaseModel


class ResumeUploadResponse(BaseModel):
    candidate_id: uuid.UUID
    resume_file_url: str
    parsed: dict | None
    # FL-01.5: true when parsing/extraction failed — frontend should route to
    # manual entry instead of showing a broken confirmation screen.
    needs_manual_entry: bool
    error: str | None = None


class CandidateResponse(BaseModel):
    id: uuid.UUID
    name: str | None
    email: str | None
    phone: str | None
    resume_file_url: str | None
    resume_parsed_json: dict | None

    model_config = {"from_attributes": True}
