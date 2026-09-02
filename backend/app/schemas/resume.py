import uuid

from pydantic import BaseModel, EmailStr, field_validator


class ExperienceEntry(BaseModel):
    company: str
    role: str
    start_date: str | None = None
    end_date: str | None = None
    summary: str | None = None


class EducationEntry(BaseModel):
    institution: str
    degree: str | None = None
    year: str | None = None


class ProjectEntry(BaseModel):
    name: str
    summary: str | None = None


class ResumeFieldsUpdate(BaseModel):
    """FL-02: candidate-confirmed/corrected resume fields.

    name and email are the only hard-required fields (FL-02.4) — everything
    else can legitimately be empty for an early-career candidate.
    """

    name: str
    email: EmailStr
    phone: str | None = None
    skills: list[str] = []
    experience: list[ExperienceEntry] = []
    education: list[EducationEntry] = []
    projects: list[ProjectEntry] = []

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name is required.")
        return v.strip()


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
