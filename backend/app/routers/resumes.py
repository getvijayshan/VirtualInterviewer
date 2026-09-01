from fastapi import APIRouter, UploadFile

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("")
async def upload_resume(file: UploadFile):
    """FL-01: accept PDF/DOCX, store in S3, extract structured data via Claude."""
    raise NotImplementedError


@router.get("/{resume_id}")
async def get_resume(resume_id: str):
    """FL-02: return extracted fields for the confirmation screen."""
    raise NotImplementedError


@router.patch("/{resume_id}")
async def update_resume(resume_id: str):
    """FL-02: persist candidate corrections to extracted fields."""
    raise NotImplementedError
