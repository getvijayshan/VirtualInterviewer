from fastapi import APIRouter

router = APIRouter(prefix="/sessions/{session_id}/report", tags=["reports"])


@router.post("")
async def generate_report(session_id: str):
    """FL-07: single Claude call over the full transcript -> scorecard + feedback,
    persisted so it's re-viewable without regenerating (FL-07.6). Gated behind
    OTP auth (FL-06) at the frontend/route level."""
    raise NotImplementedError


@router.get("")
async def get_report(session_id: str):
    """FL-07.6: return the persisted report."""
    raise NotImplementedError
